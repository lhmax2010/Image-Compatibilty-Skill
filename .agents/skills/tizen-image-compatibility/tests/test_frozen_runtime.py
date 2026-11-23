"""Host-only tests: the controller fabricates receipts and never runs fixture bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ENTRY = Path(__file__).resolve().parents[1] / 'scripts' / 'frozen_runtime.py'


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

    def launch(self, *, execute=False, enrollment=True, wrong_manifest_hash=False):
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
        result, plan, out = self.launch(execute=True)
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
                result, plan, _ = self.launch(execute=True)
                self.assertEqual(result.returncode, 3, result.stderr)
                native, cross = (row for row in plan if row['artifact_id'] == 'vd-A-C')
                self.assertEqual(native['status'], 'UNKNOWN')
                self.assertEqual(native['stages'][stage], status)
                self.assertEqual(cross['status'], 'NOT_EXECUTED')
                self.assertNotIn('attempt_id', cross)

    def test_cross_mismatch_and_unconfirmed_cleanup(self):
        self.mode.write_text('mismatch')
        result, plan, _ = self.launch(execute=True)
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
                self.assertEqual(plan[0]['cleanup_status'], 'SUCCESS')
                self.assertTrue(any('partial output' in (out / path).read_text()
                                    for path in plan[0]['runtime_evidence']))
                pid = int((self.root / 'child.pid').read_text())
                stat = Path(f'/proc/{pid}/stat')
                if stat.exists():
                    try:
                        self.assertEqual(stat.read_text().split(') ')[1].split()[0], 'Z')
                    except FileNotFoundError:
                        pass
