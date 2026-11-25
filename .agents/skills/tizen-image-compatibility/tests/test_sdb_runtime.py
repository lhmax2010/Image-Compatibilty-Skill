"""SDB adapter negatives run entirely on the host using a structured fake transport."""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from compat import sdb_protocol as wire
from compat import sdb_runtime as sdb

BOOT = '12345678-1234-1234-1234-123456789abc'
UID = '1000'
MANAGER = '/user.slice/user-1000.slice/user@1000.service'
BASE = '/opt/fixture/.cache'
DATA = b'safe host fixture'
SHA = hashlib.sha256(DATA).hexdigest()


class DeviceFixture:
    def __init__(self, mode):
        self.mode = mode
        self.released = threading.Event()
        self.calls = []
        self.next_number = 99
        self.lock = threading.Lock()
        self.pins = {name: sdb.digest(name.encode()) for name in sdb.PROVIDERS}

    def respond(self, rows, rc=0, stale=False):
        with self.lock:
            self.next_number += 1
            key = str(self.next_number)
        return sdb.Response(key, '\n'.join(rows)+'\n', rc, time.monotonic()-(30 if stale else 0), ('raw-'+key,))

    def push(self, path, destination):
        self.calls.append('push')
        assert Path(path).read_bytes() == DATA
        assert destination == self.directory+'/probe'
        return ['push.raw']

    def shell(self, operation, *args, timeout=4):
        self.calls.append(operation if operation in (wire.CREATE, wire.ADMIT, wire.ARM, wire.REMOVE) else operation[:12])
        session = [f'BOOT={BOOT}', f'UID={UID}']
        if operation == wire.ADMIT:
            if self.mode == 'profile':
                return self.respond(session, 1)
            return self.respond([*session,'DEVICE='+('a'*64),'BASE='+BASE,'MOUNT=rw,relatime','MANAGER='+MANAGER,
                *(f'FILE|{name}|/usr/lib/{name}|{checksum}' for name,checksum in self.pins.items())])
        if operation == wire.CREATE:
            self.attempt=args[-1]
            self.directory=f'{BASE}/tizen-compat-{self.attempt}-test'
            self.group=f'{MANAGER}/tizen-compat-{self.attempt}.scope'
            return self.respond([*session,'DIR='+self.directory,'DIR_ID=3:4:1000:700'])
        if operation == wire.DEPLOYED:
            return self.respond([*session,'ELF='+('0'*64 if self.mode=='digest' else SHA)])
        if operation.startswith('exec systemd-run '):
            assert '--user --scope' in operation and 'RuntimeMaxSec=10s' in operation
            if not self.released.wait(5):
                return self.respond([],143)
            if self.mode == 'disconnect':
                raise sdb.SdbRuntimeError('connection ended', 'SDB_DISCONNECTED')
            return self.respond([], {'nonzero':17,'timeout':143}.get(self.mode,0))
        if operation == wire.ARMED_IDENTITY:
            return self.respond([*session,'ATTEMPT='+self.attempt,'START=849','ELF='+SHA,'DIR_ID=3:4:1000:700',
                                 'CWD='+self.directory,'PROC_CGROUP='+self.group,
                                 'PROC_UIDS=1000:1000:1000:1000','CapEff=0000','CapPrm=0000'])
        if operation == wire.ARM:
            assert args[-4:] == (self.attempt,'55','849',self.group)
            self.released.set()
            return self.respond(session)
        if operation == wire.OBSERVE:
            phase=args[4]
            if self.mode=='disconnect' and phase=='ended':
                raise sdb.SdbRuntimeError('cannot query target', 'SDB_DISCONNECTED')
            base=[*session,'ATTEMPT='+self.attempt,'PHASE='+phase,
                  'OBSERVER_PID='+str({'before':12,'active':13,'ended':14,'removed':15}[phase])]
            if phase=='active':
                return self.respond([*base,'ActiveState=active','ControlGroup='+(
                    '/wrong' if self.mode=='cgroup' else self.group),
                    'RuntimeMaxUSec=10s','TimeoutStopUSec=1s','KillMode=control-group','Delegate=no',
                    'GROUP_ID=8:9','GROUP_WRITABLE=yes','GROUP_PIDS=55','ARMED=55',
                    'PROC|55|S|'+('12' if self.mode=='pid' else '55')+'|55|849'])
            if self.mode=='residue' and phase=='ended':
                return self.respond([*base,'ActiveState=inactive','ControlGroup=','GROUP_ABSENT=yes','PROC|55|S|55|55|849'])
            ok=[*base,'ActiveState=inactive','ControlGroup=','GROUP_ABSENT=yes',
                'Result='+('timeout' if self.mode=='timeout' and phase=='ended' else 'success')]
            if phase in ('ended','removed') and len(args)>5:
                ok.append('GONE|55')
            if phase=='removed' and self.mode!='missing-cleanup':
                ok.append('DIR_ABSENT=yes')
            return self.respond(ok,stale=self.mode=='stale' and phase=='removed')
        if operation == wire.CAPTURE:
            if self.mode=='output-limit':
                return self.respond(['OUTPUT_LIMIT=yes'],7)
            stdout = b'' if self.mode == 'timeout' else b'expected\n'
            files={'probe.stdout':stdout,'probe.stderr':b'', 'loader.55':(
                b'calling init: /lib/ld-linux.so.3\ncalling init: /lib/libc.so.6\n'
                b"checking for version `GLIBC_2.4' in file /lib/libc.so.6\n")}
            return self.respond([f'FILE|{name}|{len(data)}|{sdb.digest(data)}|'+base64.b64encode(data).decode()
                                 for name,data in files.items()])
        if operation == wire.PROVIDERS:
            return self.respond([f'FILE|{name}|/usr{name}|{self.pins[Path(name).name]}' for name in args[2:]])
        if operation in (wire.REMOVE, wire.RESET_TIMEOUT):
            return self.respond(session)
        raise AssertionError('Unrecognized operation')


class SdbRuntimeTests(unittest.TestCase):
    def run_fixture(self, mode='normal', execute=True, authorized=True, scope=sdb.HEADED, whitelist=True, read=True):
        self.fixture=DeviceFixture(mode)
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            source=root/'src'
            source.write_bytes(DATA)
            spec={'sdb_serial':'192.0.2.1:26101','scope':scope,'image_family':'llvm',
                  'build_id':'tizen-unified-toolchain_20261120.082536_tizen-'+
                             ('headed' if scope==sdb.HEADED else 'headless')+'-armv7l',
                  'cpu_serial_sha256':'a'*64,'provider_sha256':self.fixture.pins,
                  'authorization':{'execute':authorized,'artifact_sha256':{'llvm-A-C':SHA} if whitelist else {}}}
            artifact={'artifact_id':'llvm-A-C','sha256':SHA,
                      'elf':{'interpreter':'/lib/ld-linux.so.3','needed':['libc.so.6']},
                      'runtime_expectation':{'exit_code':0,'stdout':'expected\n','stderr':''}}
            code=sdb.handle(self.fixture,spec,artifact,source,root,read_device=read,execute=execute)
            return code,json.loads((root/'runtime.json').read_text())

    def test_normal_exit(self):
        code,r=self.run_fixture()
        self.assertEqual(code,0,r.get('error'))
        self.assertEqual((r['execution_status'],r['target_cleanup_status']),('EXITED','VERIFIED'))
        self.assertTrue(r['execution_success'] and r['behavior_match'])
        self.assertEqual(r['receipt']['binary_sha256'],SHA)
        self.assertEqual(r['receipt']['stdout'],'expected\n')
        self.assertEqual(r['loader']['status'],'VERIFIED')
        self.assertEqual(r['target_process_cleanup_status'],'NOT_VERIFIED')
        self.assertEqual(r['native_reference_status'],'NOT_VERIFIED')
        self.assertEqual(r['cross_image_compatibility'],'UNKNOWN')

    def test_nonzero_and_timeout(self):
        for mode,status,rc in [('nonzero','EXITED',17),('timeout','TIMEOUT',143)]:
            with self.subTest(mode=mode):
                code,r=self.run_fixture(mode)
                self.assertEqual(code,3)
                self.assertEqual((r['execution_status'],r['target_returncode']),(status,rc))
                self.assertEqual(r['target_cleanup_status'],'VERIFIED')
                self.assertIsNot(r['behavior_match'],True)

    def test_disconnect_and_output_limit(self):
        for mode,code_name,cleanup in [('disconnect','SDB_DISCONNECTED','NOT_VERIFIED'),
                                       ('output-limit','OUTPUT_LIMIT','VERIFIED')]:
            with self.subTest(mode=mode):
                code,r=self.run_fixture(mode)
                self.assertEqual(code,3)
                self.assertEqual(r['error_code'],code_name)
                self.assertEqual(r['target_cleanup_status'],cleanup)

    def test_identity_changes_block_the_grant(self):
        for mode in ('digest','profile','pid','cgroup'):
            with self.subTest(mode=mode):
                code,r=self.run_fixture(mode)
                self.assertEqual(code,3)
                self.assertNotIn(wire.ARM,self.fixture.calls)
                self.assertEqual(r['execution_status'],'NOT_EXECUTED')
                if mode=='profile':
                    self.assertNotIn(wire.CREATE,self.fixture.calls)

    def test_cleanup_missing_stale_or_residual(self):
        for mode in ('missing-cleanup','stale','residue'):
            with self.subTest(mode=mode):
                code,r=self.run_fixture(mode)
                self.assertEqual(code,3)
                self.assertEqual(r['target_cleanup_status'],'NOT_VERIFIED')
                if mode=='residue':
                    self.assertNotIn(wire.REMOVE,self.fixture.calls)

    def test_disallowed_execution_has_no_transport_calls(self):
        for kwargs in ({'authorized':False},{'whitelist':False},{'scope':sdb.HEADLESS}):
            with self.subTest(kwargs=kwargs):
                code,r=self.run_fixture(**kwargs)
                self.assertEqual(code,3)
                self.assertEqual(r['error_code'],'UNAUTHORIZED')
                self.assertEqual(self.fixture.calls,[])

    def test_default_plan_and_read_only(self):
        for read in (False,True):
            code,r=self.run_fixture(execute=False,read=read,authorized=False)
            self.assertEqual(code,0)
            self.assertEqual(self.fixture.calls,[wire.ADMIT] if read else [])
            self.assertEqual(r['execution_status'],'NOT_EXECUTED')

    def test_transport_marker_and_bound_service_size(self):
        tools=Mock()
        transport=sdb.SdbTransport(tools,'/trusted/sdb','192.0.2.1:26101')

        def reply(argv,**unused):
            marker=re.search(r'__SR_[a-f0-9]+__',argv[-1]).group()
            return {'returncode':0,'error':'','stdout':'answer\r\n'+marker+'17\r\n',
                    'stderr':'','stdout_evidence':'out','stderr_evidence':'err'}

        tools.run.side_effect=reply
        response=transport.shell('true')
        self.assertEqual(response.returncode,17)
        self.assertEqual(response.text,'answer\n')
        self.assertEqual(tools.run.call_args.args[0][:4],['/trusted/sdb','-s','192.0.2.1:26101','shell'])
        tools.reset_mock()
        with self.assertRaisesRegex(sdb.InputError,'legacy service length'):
            transport.shell(' '*2000)
        tools.run.assert_not_called()

    def test_legacy_request_rejection_differs_from_disconnection(self):
        tools=Mock()
        tools.run.return_value={'error':'','returncode':1,'stderr':'error: service name too long'}
        with self.assertRaises(sdb.SdbRuntimeError) as failure:
            sdb.SdbTransport(tools,'sdb','192.0.2.1:26101').shell('true')
        self.assertEqual(failure.exception.code,'SDB_PROTOCOL_REJECTED')

    def test_remote_fragments_parse(self):
        for script in (wire.ADMIT,wire.CREATE,wire.WORKER,wire.OBSERVE,wire.ARM,wire.ARMED_IDENTITY,wire.REMOVE,
                       wire.DEPLOYED,wire.CAPTURE,wire.PROVIDERS,wire.RESET_TIMEOUT):
            self.assertEqual(subprocess.run(['/bin/sh','-n'], input=script.encode(), capture_output=True).returncode,0)
