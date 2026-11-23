"""Host-only tests: the controller fabricates receipts and never runs fixture bytes."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ENTRY = Path(__file__).resolve().parents[1] / 'scripts' / 'frozen_runtime.py'
sys.path.insert(0, str(ENTRY.parent))
from compat.core import DEFAULTS, Tools
import frozen_runtime


def process_is_live(pid):
    try:
        state = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()[0]
    except FileNotFoundError:
        return False
    return state not in ('Z', 'X', 'x')


def stop_fixture(pid):
    if process_is_live(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


class FrozenRuntimeTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.bundle = self.root / 'artifacts'
        self.bundle.mkdir()
        self.manifest_path = self.root / 'manifest.json'
        self.enrollment_path = self.root / 'enrollment.json'
        self.controller = self.root / 'controller'
        self.mode = self.root / 'mode'
        self.mode.write_text('ok')
        self.calls = self.root / 'calls.jsonl'
        self.controller.write_text('#!' + sys.executable + '\n' + textwrap.dedent('''
            import hashlib, json, os, signal, subprocess, sys, time
            from pathlib import Path
            root = Path(__file__).parent
            command = sys.argv[1]
            args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
            mode = (root / 'mode').read_text()
            receipt = dict(environment_id=args['--environment-id'],
                           target_identity_sha256=args['--target-identity-sha256'],
                           plan_id=args['--plan-id'], run_id=args['--run-id'])
            with (root / 'calls.jsonl').open('a') as out:
                out.write(json.dumps([command, args]) + '\\n')
            if command == 'cleanup':
                receipt.update(schema='tizen-compat-runner-cleanup/v1', cleanup='ok')
                if mode == 'bad-cleanup':
                    receipt['run_id'] = 'other'
                if mode in ('forged-cleanup', 'escaped-fixture'):
                    receipt.update(target_process_cleanup_status='VERIFIED', remaining_processes=0)
                if mode == 'cleanup-disconnect':
                    print('transport disconnected', file=sys.stderr)
                    sys.exit(125)
                if mode == 'cleanup-timeout':
                    print('cleanup started', flush=True)
                    time.sleep(30)
                if mode == 'cleanup-interrupt':
                    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
                    (root / 'child.pid').write_text(str(proc.pid))
                    print('cleanup had partial output', flush=True)
                    os.kill(os.getppid(), signal.SIGINT)
                    time.sleep(30)
                print(json.dumps(receipt))
                sys.exit(0)
            payload = Path(args['--artifact']).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == args['--sha256']
            name = payload.decode()
            native = name.startswith(args['--environment-id'].removesuffix('-reference') + '-')
            receipt.update(schema='tizen-compat-runner/v1', deployment='ok', execution='ok',
                           binary_sha256=hashlib.sha256(payload).hexdigest(), returncode=0,
                           stdout=name + '\\n', stderr='')
            if name == 'vd-A-C' and native:
                if mode in ('lingering-child', 'escaped-fixture'):
                    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            start_new_session=mode == 'escaped-fixture')
                    (root / 'child.pid').write_text(str(proc.pid))
                if mode == 'wrong-environment':
                    receipt['environment_id'] = 'unrelated'
                if mode == 'wrong-hash':
                    receipt['binary_sha256'] = '0' * 64
                if mode == 'stale':
                    receipt['run_id'] = 'stale'
                if mode == 'deploy':
                    receipt['deployment'] = 'failed'
                if mode == 'exec-fail':
                    receipt['execution'] = 'failed'
                if mode == 'disconnect':
                    receipt['execution'] = 'disconnected'
                if mode == 'reserved':
                    receipt['returncode'] = 125
                if mode == 'native-mismatch':
                    receipt['stdout'] = 'different'
                if mode in ('timeout', 'interrupt'):
                    proc = subprocess.Popen([sys.executable, '-c',
                                              'import time; time.sleep(30)'])
                    (root / 'child.pid').write_text(str(proc.pid))
                    print('adapter had partial output', flush=True)
                    if mode == 'interrupt':
                        os.kill(os.getppid(), signal.SIGINT)
                    time.sleep(30)
            if mode == 'mismatch' and not native:
                receipt['stdout'] = 'different'
            print(json.dumps(receipt))
        '''))
        self.controller.chmod(0o700)
        images, targets, artifacts, rows = {}, {}, [], []
        compiler_hash = 'a' * 64
        for side, family, compilers, image_hash in (
                ('vd', 'gcc', ('gcc', 'g++'), 'b' * 64),
                ('llvm', 'clang', ('clang', 'clang++'), 'c' * 64)):
            rootfs = self.root / side
            rootfs.mkdir()
            targets[side] = dict(id=side + '-reference', rootfs=str(rootfs), image_sha256=image_hash,
                                 target_identity_sha256=hashlib.sha256(side.encode()).hexdigest())
            images[side] = dict(tool_family=family, image={'published_sha256': image_hash},
                                target_triple='armv7l-tizen-linux-gnueabi', sdk_base_snapshot=side,
                                sdk_package_lock_sha256=image_hash,
                                host_binary_sha256={c: compiler_hash for c in compilers})
            for probe, compiler in zip(('A-C', 'B-CPP'), compilers):
                ident = f'{side}-{probe}'
                payload = ident.encode()
                (self.bundle / ident).write_bytes(payload)
                sha = hashlib.sha256(payload).hexdigest()
                artifacts.append(dict(artifact_id=ident, bundle_path=ident, bytes=len(payload), sha256=sha,
                                      native_reference=side, purpose='four_quadrant_base',
                                      build=dict(compile_argv=[compiler], link_argv=[compiler]),
                                      elf=dict(machine='ARM', **{'class': 'ELF32'}, eabi=5, pcs='base',
                                               interpreter='/lib/ld-linux.so.3', role='exec' if side == 'vd' else 'pie'),
                                      runtime_expectation=dict(argv=[], exit_code=0, stdout=ident + '\n', stderr='')))
                for dest in ('vd', 'llvm'):
                    rows.append(dict(artifact_id=ident, destination_image=dest, artifact_sha256=sha,
                                     phase8d_expected_id=f'ET-{ident}-{dest}', status='NOT_EXECUTED',
                                     authorized_environment_id=None))
        self.manifest = dict(schema='tizen-compat-frozen-artifacts/v1', reference_images=images,
                             artifacts=artifacts, runtime_plan=rows)
        self.enrollment = dict(scope='SR_RUNTIME', enabled=True, authorized=True, timeout_seconds=2,
                               controller=str(self.controller), targets=targets,
                               controller_sha256=hashlib.sha256(self.controller.read_bytes()).hexdigest())
        self.reports = 0

    def launch(self, *, execute=False, enrollment=True, wrong_manifest_hash=False, verified_target_fixture=False):
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.enrollment_path.write_text(json.dumps(self.enrollment))
        self.reports += 1
        directory = self.root / f'report-{self.reports}'
        digest = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
        cmd = [sys.executable, str(ENTRY), '--manifest', str(self.manifest_path), '--manifest-sha256',
               '0' * 64 if wrong_manifest_hash else digest, '--bundle', str(self.bundle), '--output', str(directory)]
        if enrollment:
            cmd.extend(['--enrollment', str(self.enrollment_path)])
        if execute:
            cmd.append('--execute')
        if verified_target_fixture:
            run_case = frozen_runtime.run_case

            def with_simulated_independent_verification(case, *args):
                run_case(case, *args)
                case['target_process_cleanup_status'] = 'VERIFIED'

            # Exercise the post-verification matrix rules without trusting controller stdout.
            with patch.object(frozen_runtime, 'run_case', side_effect=with_simulated_independent_verification):
                code = frozen_runtime.frozen_runtime(self.manifest_path, digest, self.bundle, directory,
                                                     enrollment=self.enrollment_path, execute=execute)
            result = SimpleNamespace(returncode=code, stderr='')
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        report = directory / 'runtime.json'
        return result, json.loads(report.read_text())['cases'] if report.exists() else [], directory

    def test_plan_is_unbound_and_execution_default_off(self):
        result, plan, _ = self.launch(enrollment=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(plan), 8)
        self.assertEqual({(row['plan_id'], row['status']) for row in plan}, {(None, 'NOT_EXECUTED')})
        result, bound, _ = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len({r['plan_id'] for r in bound}), 8)
        self.enrollment['targets']['vd']['target_identity_sha256'] = '1' * 64
        result, rebound, _ = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        for first, second in zip(bound, rebound):
            self.assertEqual(first['plan_id'] == second['plan_id'],
                             first['native_image'] == first['destination_image'] == 'llvm')
        self.assertFalse(self.calls.exists())

    def test_authorization_pinned_bytes_and_input_identity(self):
        for field in ('enabled', 'authorized'):
            self.enrollment[field] = False
            self.assertEqual(self.launch(execute=True)[0].returncode, 2)
            self.enrollment[field] = True
        self.assertEqual(self.launch(execute=True, enrollment=False)[0].returncode, 2)
        self.assertEqual(self.launch(execute=True, wrong_manifest_hash=True)[0].returncode, 2)
        self.enrollment['scope'] = 'QEMU_USER_SMOKE'
        self.assertEqual(self.launch(execute=True)[0].returncode, 2)
        self.enrollment['scope'] = 'SR_RUNTIME'
        self.enrollment['targets']['vd']['image_sha256'] = 'd' * 64
        self.assertEqual(self.launch(execute=True)[0].returncode, 2)
        self.enrollment['targets']['vd']['image_sha256'] = 'b' * 64
        artifact = self.bundle / 'vd-A-C'
        artifact.write_bytes(b'change')
        self.assertEqual(self.launch(execute=True)[0].returncode, 2)
        artifact.unlink()
        outside = self.root / 'outside'
        outside.write_bytes(b'vd-A-C')
        artifact.symlink_to(outside)
        self.assertEqual(self.launch(execute=True)[0].returncode, 2)
        self.assertFalse(self.calls.exists())

    def test_build_family_and_plan_are_reconciled(self):
        artifact = self.manifest['artifacts'][0]
        artifact['build']['link_argv'][0] = 'clang'
        self.assertEqual(self.launch()[0].returncode, 2)
        artifact['build']['link_argv'][0] = 'gcc'
        self.manifest['runtime_plan'].pop()
        self.assertEqual(self.launch()[0].returncode, 2)
        self.assertFalse(self.calls.exists())

    def test_exact_bytes_native_first_fresh_receipts_and_cleanup(self):
        result, plan, out = self.launch(execute=True, verified_target_fixture=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({row['status'] for row in plan}, {'COMPATIBLE'})
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual([verb for verb, _ in calls], ['run', 'cleanup'] * 8)
        args = [args for verb, args in calls if verb == 'run']
        native = [Path(a['--artifact']).name.startswith(a['--environment-id'].split('-')[0]) for a in args]
        self.assertEqual(native, [True] * 4 + [False] * 4)
        self.assertEqual(len({row['attempt_id'] for row in plan}), 8)
        for row in plan:
            self.assertEqual(row['cleanup_status'], 'SUCCESS')
            self.assertEqual(row['verification_status'], 'VERIFIED')
            for path in row['runtime_evidence'] + row['cleanup_evidence']:
                self.assertTrue((out / path).is_file())

    def test_incomplete_or_unsuccessful_native_blocks_its_cross(self):
        for mode, stage, status in (('wrong-environment', 'deployment_status', 'UNKNOWN'),
                                    ('wrong-hash', 'deployment_status', 'UNKNOWN'),
                                    ('stale', 'deployment_status', 'UNKNOWN'),
                                    ('deploy', 'deployment_status', 'FAILED'),
                                    ('exec-fail', 'execution_status', 'FAILED'),
                                    ('disconnect', 'execution_status', 'DISCONNECTED'),
                                    ('reserved', 'behavior_status', 'UNKNOWN'),
                                    ('native-mismatch', 'behavior_status', 'MISMATCH')):
            with self.subTest(mode=mode):
                self.mode.write_text(mode)
                result, plan, _ = self.launch(execute=True, verified_target_fixture=True)
                self.assertEqual(result.returncode, 3, result.stderr)
                native, cross = (row for row in plan if row['artifact_id'] == 'vd-A-C')
                self.assertEqual(native['status'], 'UNKNOWN')
                self.assertEqual(native['stages'][stage], status)
                self.assertEqual(cross['status'], 'NOT_EXECUTED')
                self.assertNotIn('attempt_id', cross)

    def test_cross_mismatch_and_unconfirmed_cleanup(self):
        self.mode.write_text('mismatch')
        result, plan, _ = self.launch(execute=True, verified_target_fixture=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(sum(row['status'] == 'INCOMPATIBLE' for row in plan), 4)
        self.mode.write_text('bad-cleanup')
        result, plan, _ = self.launch(execute=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(plan[0]['cleanup_status'], 'UNKNOWN')
        self.assertEqual(sum('attempt_id' in row for row in plan), 1)

    def test_timeout_and_interrupt_preserve_evidence_and_reap_group(self):
        for mode, code, reason in (('timeout', 3, 'timeout'), ('interrupt', 130, 'interrupted')):
            with self.subTest(mode=mode):
                self.mode.write_text(mode)
                result, plan, out = self.launch(execute=True)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(plan[0]['adapter_error'], reason)
                self.assertEqual(plan[0]['cleanup_status'], 'UNKNOWN')
                self.assertEqual(plan[0]['cleanup_receipt_status'], 'ACCEPTED')
                self.assertEqual(plan[0]['run_local_process_group_status'], 'VERIFIED')
                self.assertTrue(any('partial output' in (out / path).read_text()
                                    for path in plan[0]['runtime_evidence']))
                pid = int((self.root / 'child.pid').read_text())
                self.addCleanup(stop_fixture, pid)
                self.assertFalse(process_is_live(pid))

    def test_cleanup_receipt_and_local_or_target_exit_are_distinct(self):
        for mode, alive in (('lingering-child', False), ('escaped-fixture', True)):
            with self.subTest(mode=mode):
                self.mode.write_text(mode)
                result, plan, _ = self.launch(execute=True)
                pid = int((self.root / 'child.pid').read_text())
                self.addCleanup(stop_fixture, pid)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(plan[0]['run_local_process_group_status'], 'VERIFIED')
                self.assertEqual(plan[0]['cleanup_receipt_status'], 'ACCEPTED')
                self.assertEqual(plan[0]['target_process_cleanup_status'], 'NOT_VERIFIED')
                self.assertEqual(plan[0]['stages']['behavior_status'], 'SUCCESS')
                self.assertEqual(plan[0]['status'], 'UNKNOWN')
                self.assertEqual(plan[0]['verification_status'], 'NOT_VERIFIED')
                self.assertTrue(all(row['status'] == 'NOT_EXECUTED' for row in plan[1:]))
                self.assertEqual(process_is_live(pid), alive)

    def test_unproven_target_cleanup_blocks_even_with_matching_behavior(self):
        for mode, receipt, error, evidence in (
                ('ok', 'ACCEPTED', '', 'cleanup'),
                ('forged-cleanup', 'ACCEPTED', '', 'remaining_processes'),
                ('cleanup-timeout', 'UNCONFIRMED', 'timeout', 'cleanup started'),
                ('cleanup-disconnect', 'UNCONFIRMED', '', 'transport disconnected')):
            with self.subTest(mode=mode):
                self.mode.write_text(mode)
                result, plan, out = self.launch(execute=True)
                self.assertEqual(result.returncode, 3, result.stderr)
                first, *later = plan
                self.assertEqual(first['stages']['behavior_status'], 'SUCCESS')
                self.assertEqual(first['cleanup_receipt_status'], receipt)
                self.assertEqual(first['cleanup_error'], error)
                self.assertEqual(first['cleanup_status'], 'UNKNOWN')
                self.assertEqual(first['target_process_cleanup_status'], 'NOT_VERIFIED')
                self.assertEqual(first['status'], 'UNKNOWN')
                self.assertTrue(any(evidence in (out / path).read_text() for path in first['cleanup_evidence']))
                self.assertTrue(all(row['status'] == 'NOT_EXECUTED' and 'attempt_id' not in row for row in later))

    def test_cleanup_interrupt_stops_matrix_and_keeps_evidence(self):
        self.mode.write_text('cleanup-interrupt')
        result, plan, out = self.launch(execute=True)
        pid = int((self.root / 'child.pid').read_text())
        self.addCleanup(stop_fixture, pid)
        self.assertFalse(process_is_live(pid))
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertEqual(plan[0]['cleanup_error'], 'interrupted')
        self.assertEqual(plan[0]['cleanup_receipt_status'], 'UNCONFIRMED')
        self.assertEqual(plan[0]['cleanup_local_process_group_status'], 'VERIFIED')
        self.assertEqual(sum('attempt_id' in row for row in plan), 1)
        self.assertTrue(any('cleanup had partial output' in (out / path).read_text()
                            for path in plan[0]['cleanup_evidence']))


class BoundedProcessTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.marker = self.root / 'pid'
        self.tools = Tools(self.root, DEFAULTS)

    def start_child_then(self, tail):
        return [sys.executable, '-c', textwrap.dedent('''
            import os, subprocess, sys, time
            from pathlib import Path
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            Path(sys.argv[1]).write_text(str(child.pid))
        ''') + tail, str(self.marker)]

    def assert_reaped(self, pid):
        self.addCleanup(stop_fixture, pid)
        self.assertFalse(process_is_live(pid))

    def test_child_reaped_on_success_or_abnormal_controller_exit(self):
        for tail, code in (('raise SystemExit(0)', 0), ('os.kill(os.getpid(), 15)', -15)):
            with self.subTest(code=code):
                result = self.tools.run(self.start_child_then(tail), max_capture_bytes=4096, timeout=4)
                self.assert_reaped(int(self.marker.read_text()))
                self.assertEqual(result['returncode'], code)
                self.assertEqual(result['local_process_group_status'], 'VERIFIED')

    def test_combined_evidence_limit_reaps_group(self):
        for stream in (1, 2):
            with self.subTest(fd=stream):
                cmd = self.start_child_then(f'os.write({stream}, b"x" * 100000); time.sleep(30)')
                result = self.tools.run(cmd, max_capture_bytes=4096, timeout=4)
                self.assert_reaped(int(self.marker.read_text()))
                self.assertEqual(result['error'], 'adapter output limit exceeded')
                self.assertEqual(result['local_process_group_status'], 'VERIFIED')
                size = sum((self.root / result[f'{name}_evidence']).stat().st_size for name in ('stdout', 'stderr'))
                self.assertEqual(size, 4096)

    def test_interrupt_before_popen_returns_still_reaps_new_process(self):
        popen = subprocess.Popen
        processes = []

        def interrupt_after_fork(*args, **kwargs):
            proc = popen(*args, **kwargs)
            processes.append(proc)
            os.kill(os.getpid(), signal.SIGINT)
            return proc

        with patch('compat.core.subprocess.Popen', side_effect=interrupt_after_fork):
            result = self.tools.run([sys.executable, '-c', 'import time; time.sleep(30)'],
                                    max_capture_bytes=4096, timeout=4, keep_interrupt=True)
        self.assert_reaped(processes[0].pid)
        self.assertEqual(result['error'], 'interrupted')
        self.assertEqual(result['local_process_group_status'], 'VERIFIED')

    def test_interrupt_during_local_reaping_does_not_skip_verification(self):
        stop = Tools.stop_bounded_group

        def interrupt_while_reaping(proc):
            os.kill(os.getpid(), signal.SIGINT)
            return stop(proc)

        with patch.object(Tools, 'stop_bounded_group', side_effect=interrupt_while_reaping):
            result = self.tools.run(self.start_child_then('print("reap")'), max_capture_bytes=4096,
                                    timeout=4, keep_interrupt=True)
        self.assert_reaped(int(self.marker.read_text()))
        self.assertEqual(result['error'], 'interrupted')
        self.assertEqual(result['stdout'], 'reap\n')
        self.assertEqual(result['local_process_group_status'], 'VERIFIED')
