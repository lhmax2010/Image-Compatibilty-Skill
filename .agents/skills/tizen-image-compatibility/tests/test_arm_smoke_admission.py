"""Admission bookkeeping tests never call sudo or execute an ARM file."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


HELPERS = Path(__file__).resolve().parents[1] / 'scripts' / 'arm_smoke_admission'
sys.path.insert(0, str(HELPERS))
spec = importlib.util.spec_from_file_location('tizen_arm_admission', HELPERS / 'manage.py')
admission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admission)
sys.path.remove(str(HELPERS))
preflight = sys.modules['preflight']
INACTIVE = {'LoadState': 'loaded', 'ActiveState': 'inactive', 'Transient': 'no',
            'ControlGroup': '', 'FragmentPath': '', 'DropInPaths': ''}


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.dir = self.workspace / 'state'
        self.dir.mkdir(mode=0o700)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(admission, 'WORKSPACE', self.workspace))
        stack.enter_context(patch.object(admission, 'STATE', self.dir))
        stack.enter_context(patch.object(admission, 'CGROUP', self.workspace / 'cgroup'))
        self.command = stack.enter_context(patch.object(admission, 'command'))
        self.unit = stack.enter_context(patch.object(admission, 'properties', return_value=INACTIVE))
        self.user = stack.enter_context(patch.object(admission, 'get_user', return_value=None))
        self.group = stack.enter_context(patch.object(admission, 'get_group', return_value=None))
        self.ledger = admission.Ledger(dict(timestamp_utc='fixture', machine_sha256=admission.digest(Path('/etc/machine-id')),
                                            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                                            uid=os.getuid()))

    def test_placeholder_slice_is_available_but_existing_unit_is_not(self):
        self.assertFalse(admission.occupied(INACTIVE))
        for changes in ({'FragmentPath': '/some-unit'}, {'DropInPaths': '/other-unit'},
                        {'Transient': 'yes'}, {'ActiveState': 'active'}, {'ControlGroup': '/occupied'}):
            self.assertTrue(admission.occupied(INACTIVE | changes))

    def test_setup_refuses_account_collision_without_admin_call(self):
        self.user.return_value = SimpleNamespace(pw_uid=800)
        with self.assertRaisesRegex(admission.Blocked, 'name conflict'):
            admission.setup(self.ledger)
        self.command.assert_not_called()

    def test_existing_registration_stops_repeated_setup(self):
        self.ledger.created['account'] = {'uid': 950}
        with self.assertRaisesRegex(admission.Blocked, 'verified cleanup'):
            admission.setup(self.ledger)
        self.command.assert_not_called()

    def test_rebooted_snapshot_stops_setup_before_any_admin_call(self):
        self.ledger.data['boot_id'] = 'previous-boot'
        with self.assertRaisesRegex(admission.Blocked, 'Host rebooted'):
            admission.setup(self.ledger)
        self.command.assert_not_called()

    def test_missing_native_sudo_has_no_creations(self):
        self.command.return_value = SimpleNamespace(returncode=1)
        with patch.object(admission, 'staged_sources'):
            with self.assertRaisesRegex(admission.Blocked, 'sudo -n unavailable'):
                admission.setup(self.ledger)
        self.command.assert_called_once_with(['/usr/bin/true'], admin=True, check=False)
        self.assertFalse(any(self.ledger.created.values()))
        self.assertIsNone(self.ledger.data['pending'])

    def test_partial_failure_ledger_round_trips_and_refuses_duplicate_operation(self):
        self.ledger.begin('create account and group')
        other = admission.Ledger()
        self.assertEqual(other.data['pending'], 'create account and group')
        with self.assertRaisesRegex(admission.Blocked, 'Unresolved operation'):
            other.begin('create inputs')
        self.assertEqual(json.loads(other.path.read_text())['pending'], 'create account and group')

    def test_absent_pending_resource_allows_dry_run_without_change(self):
        self.ledger.begin('create inputs')
        before = self.ledger.path.read_bytes()
        with redirect_stdout(StringIO()) as data:
            admission.rollback(self.ledger, apply=False)
        self.assertEqual(json.loads(data.getvalue())['mode'], 'dry-run')
        self.assertEqual(self.ledger.path.read_bytes(), before)
        self.command.assert_not_called()

    def test_present_unattributed_partial_directory_stops_rollback(self):
        self.ledger.begin('create inputs')
        (self.dir / 'inputs').mkdir()
        with self.assertRaisesRegex(admission.Blocked, 'pending object exists'):
            admission.rollback(self.ledger, apply=True)
        self.command.assert_not_called()

    def test_unit_invocation_mismatch_stops_rollback(self):
        self.ledger.created['units'][admission.ANCHOR] = {'invocation_id': 'recorded'}
        active = INACTIVE | {'Transient': 'yes', 'ActiveState': 'active', 'InvocationID': 'replaced',
                             'Description': self.ledger.description(admission.ANCHOR)}
        self.unit.side_effect = lambda unit: active if unit == admission.ANCHOR else INACTIVE
        with self.assertRaisesRegex(admission.Blocked, 'replaced service'):
            admission.rollback(self.ledger, apply=True)
        self.command.assert_not_called()

    def test_unmanaged_kernel_cgroup_blocks_even_if_systemd_is_inactive(self):
        (admission.CGROUP / admission.SLICE).mkdir(parents=True)
        with self.assertRaisesRegex(admission.Blocked, 'kernel cgroup remains'):
            admission.rollback(self.ledger, apply=True)
        self.command.assert_not_called()

    def test_symlink_or_mount_cannot_be_removed(self):
        tree = self.dir / 'inputs'
        outside = self.workspace / 'outside'
        outside.mkdir()
        tree.symlink_to(outside, target_is_directory=True)
        self.ledger.created['input_dir'] = admission.file_id(outside)
        with self.assertRaisesRegex(admission.Blocked, 'identity or mount'):
            admission.verify_input_tree(self.ledger, admin=True)
        tree.unlink()
        tree.mkdir()
        self.ledger.created['input_dir'] = admission.file_id(tree)
        with patch.object(admission, 'mount_targets', return_value=[tree / 'nested']):
            with self.assertRaisesRegex(admission.Blocked, 'identity or mount'):
                admission.verify_input_tree(self.ledger, admin=True)
        self.command.assert_not_called()

    def test_live_dedicated_uid_stops_apply_before_any_deletion(self):
        self.ledger.created['account'] = {'created_here': True, 'uid': 950, 'gid': 950}
        self.user.return_value = SimpleNamespace(pw_uid=950)
        self.group.return_value = SimpleNamespace(gr_gid=950)
        with patch.object(admission, 'verify_account'), patch.object(admission, 'live_account', return_value=[90]):
            with redirect_stdout(StringIO()):
                with self.assertRaisesRegex(admission.Blocked, 'still has live processes'):
                    admission.rollback(self.ledger, apply=True)
        self.command.assert_not_called()

    def test_apply_removes_only_audited_entries_and_retains_the_ledger(self):
        root = self.dir / 'inputs'
        root.mkdir()
        (root / 'probe').write_bytes(b'fixture-not-executable')
        self.ledger.created['account'] = {'created_here': True, 'uid': 950, 'gid': 950}
        self.user.return_value = SimpleNamespace(pw_uid=950)
        self.group.return_value = SimpleNamespace(gr_gid=950, gr_mem=[])

        def fake_admin(argv, **kwargs):
            if argv[0] == '/usr/bin/rm':
                (root / 'probe').unlink()
            elif argv[0] == '/usr/bin/rmdir':
                root.rmdir()
            elif argv[0] == '/usr/sbin/userdel':
                self.user.return_value = None
            elif argv[0] == '/usr/sbin/groupdel':
                self.group.return_value = None
            else:
                self.fail(f'Unexpected privileged command: {argv}')

        self.command.side_effect = fake_admin
        with (patch.object(admission, 'verify_account'), patch.object(admission, 'live_account', return_value=[]),
              patch.object(admission, 'verify_input_tree', return_value=['probe']),
              patch.object(admission.pwd, 'getpwall', return_value=[]), redirect_stdout(StringIO())):
            admission.rollback(self.ledger, apply=True)
        self.assertEqual([c.args[0][0] for c in self.command.call_args_list],
                         ['/usr/bin/rm', '/usr/bin/rmdir', '/usr/sbin/userdel', '/usr/sbin/groupdel'])
        self.assertEqual(admission.Ledger().data['status'], 'ROLLED_BACK')

    def test_read_only_binding_leads_only_to_x86_fixture_entry(self):
        fixture = preflight.fixture_argv(SimpleNamespace(pw_uid=950, pw_gid=950), 'normal')
        program = fixture[fixture.index('--chdir') + 2]
        self.assertEqual(program, '/runner/host-only')
        self.assertIn('--disable-userns', fixture)
        self.assertIn('--unshare-all', fixture)
        self.assertIn('--fsize=1048576', fixture)
        self.assertEqual(sum(token == '--ro-bind' for token in fixture), 5)
        self.assertTrue(all(len(entry[1]) == 64 for entry in admission.STAGED.values()))

    def test_empty_verification_rejects_cgroup_replacement(self):
        with patch.object(preflight, 'sample', return_value={'identity': [2, 99], 'populated': '0',
                                                              'workers': [], 'pids_current': '0'}):
            with self.assertRaisesRegex(RuntimeError, 'inode changed'):
                preflight.assert_empty(self.dir, [2, 63])
