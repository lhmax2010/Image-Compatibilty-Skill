"""Final release controls. Native executions are of sources shipped in this repository."""
import copy
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from test_framework import Environment
from test_report_enhancement import FixtureGuard
from test_v12 import inventory
from compat.collect import collect
from compat.compare import compare_elf, compare_static, finalize
from compat.core import DEFAULTS, VERSION, Tools, finding, hash_file
from compat.elf import collect_elf
from compat.history import HistoryBrowser, build_history
from compat.images import Image
from compat.report import build_results, generate
from compat.report_browser import ReportBrowser
from compat.report_enhance import build as enhance
from compat.runtime_adapter import podman_run
from compat.testing import ASSETS, execute_target, run_matrix


def arm_object(path, hard):
    """Small ET_REL object conforming to AAELF32 with one TLS relocation."""
    strings = b'\x00value\x00'
    symbol = bytes(16) + struct.pack('<IIIBBH', 1, 0, 0, 0x16, 0, 0)
    attributes = bytes([6,10,7,65,8,1,9,2,24,1,25,1,28,int(hard)])
    file_tags = bytes([1]) + struct.pack('<I', 5 + len(attributes)) + attributes
    vendor = b'aeabi\x00' + file_tags
    sections = [('.text', 1, bytes(4), 0, 0, 0),
                ('.ARM.attributes', 0x70000003, b'A' + struct.pack('<I', 4 + len(vendor)) + vendor, 0, 0, 0),
                ('.ARM.exidx', 0x70000001, bytes(8), 1, 0, 8),
                ('.rel.text', 9, struct.pack('<II', 0, 0x16c), 6, 1, 8),
                ('.strtab', 3, strings, 0, 0, 0), ('.symtab', 2, symbol, 5, 1, 16)]
    names = b'\x00' + b''.join(name.encode() + b'\x00' for name,*_ in sections) + b'.shstrtab\x00'
    sections.append(('.shstrtab', 3, names, 0, 0, 0))
    data = bytearray(52)
    headers = bytes(40)
    for name, kind, payload, link, info, entry in sections:
        offset = len(data)
        data.extend(payload)
        data.extend(bytes((-len(data)) % 4))
        headers += struct.pack('<10I', names.index(name.encode()), kind, 0, 0, offset, len(payload), link, info, 4, entry)
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    data[:52] = ident + struct.pack('<HHIIIIIHHHHHH', 1, 40, 1, 0, 0, len(data),
                                   0x05000400 if hard else 0x05000200, 52, 0, 0, 40, len(sections)+1, 7)
    path.write_bytes(data + headers)


def linked(path, status, candidate, needed='libapi.so'):
    row = finding('linking', path, 'baseline consumers on candidate:DT_NEEDED:' + needed,
                  needed, candidate, status, 'HIGH', 'fixture startup check', ['evidence/input.txt'])
    return row | {'check_id': 'DT_NEEDED:' + needed, 'consumer_image': 'baseline', 'consumer_path': path,
                  'root_consumer_image': 'baseline', 'root_consumer': path,
                  'resolution': 'verified' if status == 'COMPATIBLE' else 'missing_provider'}


def enhanced_report(folder, observations, present=True):
    raw = folder/'raw'
    raw.mkdir(parents=True)
    (raw/'evidence').mkdir()
    if present:
        (raw/'evidence/input.txt').write_text('Controlled evidence\n')
    a, b = (Environment().blank() | {'schema_version':'1.2','collector_version':VERSION,
              'image': {'name':name, 'architecture':['ARM']}} for name in ('baseline', 'candidate'))
    for manifest in (a,b): inventory(manifest,[])
    config = copy.deepcopy(DEFAULTS)
    results = build_results(a,b,finalize(observations,config),[],[],config)
    generate(raw,a,b,results,config)
    enhance(raw, folder/'enhanced', FixtureGuard)


class FinalReleaseTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.config = copy.deepcopy(DEFAULTS)
        self.tools = Tools(self.root/'work', self.config)

    @unittest.skipUnless(shutil.which('readelf'), 'GNU readelf required for real ELF-byte fixture')
    def test_arm_object_pcs_and_tls_relocation(self):
        self.assertIsNotNone(self.tools.path('readelf'))
        hard, soft = (self.root/name for name in ('hard.o', 'soft.o'))
        arm_object(hard, True)
        arm_object(soft, False)
        a = collect_elf(hard, '/lib/probe.o', self.tools, 'static')
        b = collect_elf(soft, '/lib/probe.o', self.tools, 'static')
        inventory = a['arm_inventory']
        self.assertEqual((a['arm_abi']['pcs'], b['arm_abi']['pcs']), ('vfp', 'base'))
        self.assertEqual(inventory['tls_relocations'], ['R_ARM_TLS_LE32'])
        self.assertEqual(inventory['relocation_status'], 'COMPLETE')
        self.assertEqual(inventory['thumb_isa'], 'Thumb-2')
        self.assertIn('.ARM.exidx', inventory['unwind_sections'])
        self.assertEqual(inventory['hardware_assessment'], 'UNVERIFIED')
        def differences(peer):
            return compare_elf({'elf_objects':[a]}, {'elf_objects':[peer]})
        self.assertTrue(any(f['interface']=='ARM float' and f['status']=='INCOMPATIBLE' for f in differences(b)))
        self.assertFalse(any(f['status']=='INCOMPATIBLE' for f in differences(a)))
        quick = collect_elf(hard, '/lib/probe.o', self.tools, 'quick')
        self.assertEqual(quick['arm_inventory']['relocation_status'], 'NOT_EXECUTED')

    def test_dbus_valid_wire_change_and_incomplete_document(self):
        self.config['analysis']['modes'] = ['ipc','filesystem']
        rendered = '<node name="/svc"><interface name="local.Probe"><method name="Call"><arg type="{}"/></method></interface></node>'
        docs = []
        for name in ('previous','later'):
            root = self.root/name
            path = root/'usr/share/dbus-1/interfaces/local.Probe.xml'
            path.parent.mkdir(parents=True)
            docs.append((root,path))
        docs[0][1].write_text(rendered.format('s'))
        def manifest(side):
            label = ('baseline','candidate')[side]
            return collect(Image(docs[side][0], self.root, self.tools, label),label,label,'static',self.tools,self.root)
        a = manifest(0)
        for raw, expected in [(rendered.format('u'),'INCOMPATIBLE'), (rendered.format('s'),None),
                              ('<node broken','UNKNOWN'), ('<!DOCTYPE node [<!ENTITY x "x">]><node/>','UNKNOWN')]:
            docs[1][1].write_text(raw)
            values = [f['status'] for f in compare_static(a,manifest(1),self.config) if f['interface'].endswith(':method:Call')]
            self.assertEqual(values, [expected] if expected else [])
        docs[1][1].unlink()
        self.assertTrue(any(f['status']=='INCOMPATIBLE' and f['interface'].endswith(':method:Call')
                            for f in compare_static(a,manifest(1),self.config)))

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('g++'), 'Host GCC/G++ required for trusted probe-source controls')
    def test_representative_c_and_cxx_probes_positive_and_negative(self):
        env = os.environ | {'TMPDIR': str(self.root), 'LC_ALL':'C'}
        def compile_and_run(name, compiler, flags, code, text):
            output = self.root/name
            subprocess.run([compiler,*map(str,flags),'-o',str(output)], cwd=self.root, env=env, check=True, timeout=20)
            result = subprocess.run([str(output)], cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode,code,result.stderr)
            self.assertIn(text,result.stdout)
        compile_and_run('c', 'gcc', ['-std=c11',ASSETS/'behavior.c','-pthread','-ldl','-lm'],0,'c-behavior')
        compile_and_run('cancel', 'g++', ['-std=c++17',ASSETS/'cancel.cpp','-pthread'],0,'forced unwind ok')
        for negative in (False,True):
            peer = self.root/('negative.so' if negative else 'positive.so')
            flags = ['-DCOMPAT_PROBE_NEGATIVE'] if negative else []
            subprocess.run(['g++','-shared','-fPIC','-std=c++17',*flags,str(ASSETS/'cross_dso_lib.cpp'),
                            '-o',str(peer)], cwd=self.root, env=env, check=True, timeout=20)
            compile_and_run('cross-' + str(negative), 'g++', ['-std=c++17',ASSETS/'cross_dso.cpp',peer,'-pthread'],
                            14 if negative else 0,'' if negative else 'rtti lifetime string exception unwind tls ok')

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Host compiler required for build-only fixture')
    def test_compile_success_and_link_failure_are_disjoint(self):
        roots = []
        for side in ('baseline', 'candidate'):
            root = self.root/side
            root.mkdir()
            roots.append(Image(root,self.root,self.tools,side))
        sdk = self.root/'sdk'; sdk.mkdir()
        probe = self.root/'probe.c'; probe.write_text('int main(void) { return 0; }\n')
        self.config['cross_compilation'].update(c_tests=False,cpp_tests=False,compilers={'gcc':{'c':shutil.which('gcc')}},
            sysroots={'baseline':str(sdk),'candidate':str(sdk)},builds={'gcc':{'sdk':'baseline','reference_image':'baseline','provenance':'host fixture'}},
            probes=[{'language':'c','source':str(probe),'name':'link-fails','flags':['-lcompat_missing_8d7ab']}])
        object_file = self.root/'native.so'
        subprocess.run(['gcc','-shared',str(probe),'-o',str(object_file)],check=True,timeout=20)
        obj = collect_elf(object_file,'/lib/native.so',self.tools,'quick')
        manifests = tuple(Environment().blank() | {'elf_objects':[obj]} for _ in range(2))
        tests, _, _ = run_matrix(manifests,tuple(roots),self.tools,'full')
        result = next(t for t in tests if t.get('name')=='link-fails')
        self.assertEqual((result['compile_status'],result['link_status'],result['status']),('SUCCESS','FAILED','UNKNOWN'))
        planned = next(t for t in manifests[0]['expected_tests'] if t['kind']=='build')
        self.assertEqual((planned['actual_stage_results']['compilation'],planned['actual_stage_results']['linking']),('COMPATIBLE','UNKNOWN'))

    def test_adapter_capability_and_repeatability(self):
        self.config['runtime']['repetitions'] = 2
        env = {'id':'baseline','runner':['unused','{binary}']}
        with patch('compat.testing.run_target') as run:
            skipped = execute_target(env,Path('/probe'),[],'baseline',None,self.tools,required=['system-bus'])
            self.assertIn('system-bus',skipped['runtime_reason'])
            run.assert_not_called()
            run.side_effect = [{**{'returncode':0,'stderr':'','runtime_evidence':['a'],
                'stages':{'deployment_status':'SUCCESS','execution_status':'SUCCESS'}},'stdout':out} for out in ('yes','different')]
            result = execute_target(env,Path('/probe'),[],'baseline',None,self.tools)
        self.assertEqual(result['stages']['execution_status'],'UNKNOWN')
        self.assertEqual(len(result['attempts']),2)
        self.assertEqual(result['runtime_evidence'],['a'])

    def test_rootless_adapter_checks_pin_mounts_timeout_and_cleanup(self):
        self.config['runtime']['authorized'] = True
        storage, run_root, forbidden = (self.root/name for name in ('storage','run','image'))
        for path in (storage,run_root,forbidden): path.mkdir()
        probe, companion = self.root/'probe', self.root/'peer.so'
        probe.write_text('probe bytes'); companion.write_text('companion bytes')
        image_id = 'sha256:' + 'a'*64
        spec = dict(id='dedicated-test',podman=sys.executable,storage_root=str(storage),run_root=str(run_root),image=image_id)
        called = []
        def execute(argv, *, timeout, max_capture_bytes):
            called.append(argv)
            op = argv[6]
            self.assertGreater(max_capture_bytes,0)
            template = {'returncode':0,'stdout_evidence':'a','stderr_evidence':'b','error':'', 'stdout_truncated':False,'stderr_truncated':False,'stdout':'','stderr':''}
            if op == 'info': return template | {'stdout':'true\n'}
            if op == 'image': return template | {'stdout':image_id + '\n'}
            if op == 'rm': return template
            self.assertEqual(op,'run')
            self.assertIn('--network=none',argv)
            self.assertIn('--pull=never',argv)
            self.assertIn('--read-only',argv)
            self.assertIn('--cap-drop=all',argv)
            self.assertIn(hash_file(companion),argv)
            marker = next(s for s in argv if s.startswith('tizen-compat-verified:'))
            return template | {'stdout':'probe result\n','stderr':marker+'\n'}
        with patch.object(self.tools,'run',side_effect=execute):
            outcome = podman_run(spec,probe,'unused',True,[],self.tools,forbidden_root=forbidden,companion=companion)
        self.assertEqual([argv[6] for argv in called],['info','image','run','rm'])
        self.assertEqual(outcome['receipt_sha256'],hash_file(probe))
        self.assertEqual(outcome['stages']['execution_status'],'SUCCESS')
        self.assertEqual(outcome['companion_sha256'],hash_file(companion))

    def test_adapter_output_is_bounded(self):
        result = self.tools.run([sys.executable,'-c','print("x" * 100000)'], timeout=5, max_capture_bytes=1024)
        self.assertEqual(result['returncode'],-1)
        self.assertEqual(len(result['stdout']),1024)
        self.assertIn('limit',result['error'])

    def test_validated_target_signal_is_distinct_from_transport_failure(self):
        roots = []
        for side in ('baseline','candidate'):
            path = self.root/side
            path.mkdir()
            (path/'probe').write_bytes(b'controlled input')
            roots.append(Image(path,self.root,self.tools,side))
        self.config['runtime'].update(enabled=True,authorized=True,
            environments={s:{'id':s,'runner':['fixture','{binary}']} for s in ('baseline','candidate')},
            probes=[{'name':'sample','argv':['/probe'],'dimension':'runtime'}])
        def outcome(env,binary,args,label,image,tools):
            data = {'returncode':0 if label=='baseline' else -11,'stdout':'','stderr':'',
                    'stages':{'deployment_status':'SUCCESS','execution_status':'SUCCESS','behavior_status':'UNKNOWN'},
                    'expected_artifact_sha256':hash_file(image.root/'probe'), 'receipt_sha256':hash_file(image.root/'probe')}
            if label == 'candidate': data['crash'] = {'signal':11}
            return data
        with patch('compat.testing.run_target',side_effect=outcome):
            tests, _, _ = run_matrix((Environment().blank(),Environment().blank()),tuple(roots),self.tools,'runtime')
        self.assertEqual([r['status'] for r in tests],['COMPATIBLE','INCOMPATIBLE'])
        self.assertEqual(tests[1]['crash'],{'signal':11})

    def test_real_history_pipeline_fixed_new_ambiguous_and_disappeared(self):
        old = [linked('/bin/fixed','INCOMPATIBLE',None), linked('/bin/broken','COMPATIBLE','/lib/api.so'),
               linked('/bin/lost','INCOMPATIBLE',None), linked('/bin/ambiguous','INCOMPATIBLE',None),
               linked('/bin/persisting','UNKNOWN',None),linked('/bin/weak','INCOMPATIBLE',None)]
        new = [linked('/bin/fixed','COMPATIBLE','/lib/api.so'), linked('/bin/broken','INCOMPATIBLE',None),
               linked('/bin/ambiguous','COMPATIBLE','/lib/a.so'), linked('/bin/ambiguous','COMPATIBLE','/lib/b.so'),
               linked('/bin/persisting','UNKNOWN',None),linked('/bin/weak','COMPATIBLE','/lib/api.so') | {'resolution':'unknown'}]
        before = self.root/'before'; after = self.root/'after'
        enhanced_report(before,old,present=False)
        enhanced_report(after,new)
        output = self.root/'history'
        with patch('compat.history.ImpactGuard',FixtureGuard):
            result = build_history(before/'enhanced',after/'enhanced',output,'controlled matched architecture and lineage')
        self.assertEqual((result['before_count'],result['after_count']),(6,6))
        self.assertEqual(result['summary']['change']['FIXED_WITH_EVIDENCE'],1)
        self.assertEqual(result['summary']['change']['INTRODUCED'],1)
        self.assertEqual(result['summary']['change']['DISAPPEARED_UNVERIFIED'],2)
        self.assertEqual(result['summary']['change']['PERSISTING_RISK'],1)
        self.assertEqual(result['summary']['change']['STATUS_CHANGED_UNVERIFIED'],1)
        self.assertEqual(result['summary']['evidence_change']['IMPROVED'],4)
        history = HistoryBrowser(output)
        page = history.query('entries',{'limit':['1']})
        self.assertNotEqual(page['items'],history.query('entries',{'limit':['1'],'after':[str(page['next_cursor'])]})['items'])
        browser = ReportBrowser(after/'enhanced',history=output)
        server = ThreadingHTTPServer(('127.0.0.1',0),browser.handler())
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        url = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with urlopen(url+'/history',timeout=3) as response:
                self.assertIn(b'Historical regression',response.read())
            with urlopen(url+'/api/history/entries?change=INTRODUCED',timeout=3) as response:
                self.assertEqual(len(json.load(response)['items']),1)
            with self.assertRaises(HTTPError) as error: urlopen(url+'/history.sqlite',timeout=3)
            self.assertEqual(error.exception.code,404)
        finally:
            server.shutdown(); thread.join(); server.server_close()
