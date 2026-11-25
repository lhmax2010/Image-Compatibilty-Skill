import hashlib
import json
import struct
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import runtime_workflow
from compat import probe_bundle, runtime_build, runtime_summary
from compat.core import InputError
from compat.sdb_runtime import validate_enrollment, verify_loaded


def elf(kind=2):
    raw=bytearray(52)
    raw[:7]=b'\x7fELF\x01\x01\x01'
    raw[16:20]=bytes([kind,0,40,0])
    raw[28:32]=(52).to_bytes(4,'little')
    struct.pack_into('<HH',raw,42,32,1)
    raw[36:40]=(0x5000200).to_bytes(4,'little')
    path=b'/lib/ld-linux.so.3\0' if kind==2 else b''
    raw+=struct.pack('<8I',3 if path else 1,84,0,0,len(path),len(path),0,0)+path
    return bytes(raw)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.bundle=self.root/'bundle'
        self.case=self.bundle/'demo'
        self.case.mkdir(parents=True)
        (self.case/'probe').write_bytes(elf())
        (self.case/'helper.so').write_bytes(elf(3))
        self.data={'artifact_id':'demo','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.case.iterdir()},
                   'build':{'records':[{}],'evidence_sha256':'a'*64},
                   'runtime_expectation':{'exit_code':0,'stdout':'','stderr':''},
                   'elf':{'interpreter':'/lib/ld-linux.so.3','needed':['libc.so.6']}}
        self.manifest=self.root/'manifest.json'

    def record(self):
        self.manifest.write_text(json.dumps({'schema':probe_bundle.SCHEMA,'probes':[self.data]}))
        return hashlib.sha256(self.manifest.read_bytes()).hexdigest()

    def test_exact_file_table_and_out_of_band_pin(self):
        digest=self.record()
        result=probe_bundle.load(self.manifest,digest,self.bundle)['demo']
        self.assertEqual(result['files'],self.data['files'])
        with self.assertRaisesRegex(InputError,'manifest SHA256'):
            probe_bundle.load(self.manifest,'0'*64,self.bundle)
        (self.case/'unlisted.so').write_bytes(elf(3))
        with self.assertRaisesRegex(InputError,'Unregistered'):
            probe_bundle.load(self.manifest,digest,self.bundle)

    def test_replaced_and_symlinked_bundle(self):
        digest=self.record()
        file=self.case/'helper.so'
        file.write_bytes(elf(2))
        with self.assertRaisesRegex(InputError,'SHA256'):
            probe_bundle.load(self.manifest,digest,self.bundle)
        file.unlink()
        private=self.root/'external.so'
        private.write_bytes(elf(3))
        file.symlink_to(private)
        with self.assertRaises(InputError):
            probe_bundle.load(self.manifest,digest,self.bundle)

    def test_path_traversal_and_hard_float(self):
        self.data['artifact_id']='../demo'
        with self.assertRaisesRegex(InputError,'Unsafe'):
            probe_bundle.load(self.manifest,self.record(),self.bundle)
        self.data['artifact_id']='demo'
        raw=bytearray(elf())
        raw[36:40]=(0x5000400).to_bytes(4,'little')
        (self.case/'probe').write_bytes(raw)
        self.data['files']['probe']=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(InputError,'hard-float'):
            probe_bundle.load(self.manifest,self.record(),self.bundle)

    def test_manifest_and_authorized_target_must_both_match(self):
        pin=self.record()
        artifact=probe_bundle.load(self.manifest,pin,self.bundle)['demo']
        spec={'scope':'SR_HEADED_RUNTIME','image_family':'llvm','sdb_serial':'192.0.2.2:26101',
              'build_id':'tizen-unified-toolchain_20261120.082536_tizen-headed-armv7l',
              'cpu_serial_sha256':'0'*64,'provider_sha256':dict.fromkeys(
                  ('ld-linux.so.3','libc.so.6','libgcc_s.so.1','libm.so.6','libstdc++.so.6'),'1'*64)}
        spec['authorization']={'execute':True,'manifest_sha256':pin,
                               'artifact_sha256':{'demo':artifact['sha256']}}
        spec['authorization']['target_sha256']=probe_bundle.target_pin(spec)
        validate_enrollment(spec,artifact,True)
        spec['sdb_serial']='192.0.2.3:26101'
        with self.assertRaisesRegex(InputError,'manifest and target'):
            validate_enrollment(spec,artifact,True)

    def test_unified_report_keeps_scope_and_escapes_outputs(self):
        static=self.root/'static'
        static.mkdir()
        (static/'findings.csv').write_text('dimension,status\nlinking,UNKNOWN\n')
        (static/'packages.csv').write_text('scope,abi,linking\ninstalled,INCOMPATIBLE,UNKNOWN\n')
        (static/'summary.md').write_text('Installed package counts: baseline=1; candidate=None.\n')
        runtime=self.root/'runtime.json'
        runtime.write_text(json.dumps({'schema':'tizen-compat-sdb-observation/v1',
            'scope':'SR_HEADED_RUNTIME','artifact_id':'demo','result':'OBSERVED_SUCCESS','behavior_match':True,
            'target_cleanup_status':'VERIFIED','formal_runtime_status':'NOT_VERIFIED',
            'receipt':{'stdout':'<script>alert(1)</script>'}}))
        output=self.root/'report'
        output.mkdir()
        report=runtime_summary.collect({'static_report':{'directory':str(static),'scope':'SR_HEADLESS_STATIC'},
                                        'runtime_reports':[str(runtime)]},output)
        self.assertEqual(report['formal_compatibility'],'UNKNOWN')
        self.assertEqual(report['static']['finding_counts'],[{'dimension':'linking','status':'UNKNOWN','count':1}])
        self.assertEqual(report['static']['installed_packages'],{'baseline':1,'candidate':None})
        self.assertEqual(report['static']['package_assessments'],[
            {'dimension':'abi','status':'INCOMPATIBLE','count':1},
            {'dimension':'linking','status':'UNKNOWN','count':1}])
        self.assertEqual(report['runtime'][0]['record']['scope'],'SR_HEADED_RUNTIME')
        self.assertNotIn('<script>',(output/'index.html').read_text())

    def test_output_cannot_be_created_inside_historical_report(self):
        source = self.root/'prior-report'
        source.mkdir()
        config = self.root/'report.json'
        config.write_text(json.dumps({'static_report':{'directory':str(source), 'scope':'SR_HEADLESS_STATIC'}}))
        output = source/'new'
        with patch.object(sys, 'argv', ['runtime_workflow.py','report','--config',str(config),'--output',str(output)]):
            self.assertEqual(runtime_workflow.main(), 2)
        self.assertFalse(output.exists())

    def test_version_check_does_not_substitute_for_symbol_binding(self):
        version = b"checking for version `SR_PROBE_1' in file ./provider.so\n"
        binding = b"binding file /probe [0] to ./provider.so [0]: normal symbol `sr_contract' [SR_PROBE_1]\n"
        artifact = {'binding_symbols':['sr_contract']}
        version_only = verify_loaded(None, None, artifact, version, startup_failure=True)
        both = verify_loaded(None, None, artifact, version+binding, startup_failure=True)
        self.assertEqual(version_only['versions'], [{'version':'SR_PROBE_1','path':'./provider.so'}])
        self.assertEqual(version_only['unobserved_binding_symbols'], ['sr_contract'])
        self.assertEqual(both['bindings'], [
            {'symbol':'sr_contract','consumer':'/probe','provider':'./provider.so','version':'SR_PROBE_1'}])

    def test_build_freezes_reviewed_steps_and_rejects_wrong_link_failure(self):
        host = self.root/'host'
        driver = host/'usr/bin/compiler'
        driver.parent.mkdir(parents=True)
        driver.write_bytes(b'test compiler identity')
        lock = self.root/'sdk.lock'
        lock.write_bytes(b'test SDK identity')
        source = self.root/'probe.c'
        source.write_bytes(b'int main(void) { return 0; }')
        config = {
            'sources':[str(source)],
            'sdk':{'sdk':{'host':str(host),'sysroot':str(host),'startfiles':str(host),
                          'lock':str(lock),'lock_sha256':hashlib.sha256(lock.read_bytes()).hexdigest(),
                          'label':'test SDK','compiler_sha256':{
                              '/usr/bin/compiler':hashlib.sha256(driver.read_bytes()).hexdigest()}}},
            'steps':[{'sdk':'sdk','driver':'/usr/bin/compiler','flags':['negative'],'out':'negative',
                      'expected_returncode':1,'stderr_contains':'undefined reference'},
                     {'sdk':'sdk','driver':'/usr/bin/compiler','flags':['/work/src/probe.c'],'out':'positive'}],
            'probes':[{'artifact_id':'compiled','files':{'probe':'positive'},
                       'runtime_expectation':{'exit_code':0,'stdout':'','stderr':''}}]}

        class CompilerFixture:
            def __init__(self, output, stderr):
                self.output = output
                self.stderr = stderr

            def run(self, argv, **limits):
                if argv[0] == '/usr/bin/readelf':
                    stdout = '[Requesting program interpreter: /lib/ld-linux.so.3]\n (NEEDED) [libc.so.6]\n'
                    return dict(returncode=0, error=None, stdout=stdout, stdout_evidence='elf.txt')
                self_test.assertIn('--unshare-net', argv)
                self_test.assertIn('--ro-bind', argv)
                failure = 'negative' in argv
                if not failure:
                    (self.output/'work/out/positive').write_bytes(elf())
                return dict(returncode=int(failure), error=None, stderr=self.stderr,
                            stdout_evidence='compile-out.txt', stderr_evidence='compile-err.txt')

        self_test = self
        good = self.root/'good'
        bad = self.root/'bad'
        good.mkdir()
        bad.mkdir()
        with patch.object(runtime_build.shutil, 'which', side_effect=lambda name:'/usr/bin/'+name):
            manifest, pin, output = runtime_build.build_bundle(config, good, CompilerFixture(good, 'undefined reference'))
            with self.assertRaisesRegex(InputError, 'specified failure'):
                runtime_build.build_bundle(config, bad, CompilerFixture(bad, 'unrelated compiler failure'))
        artifact = probe_bundle.load(manifest, pin, output)['compiled']
        self.assertEqual(artifact['elf']['needed'], ['libc.so.6'])
        build = json.loads((good/'build.json').read_text())
        self.assertEqual([step['returncode'] for step in build['steps']], [1,0])
        self.assertFalse((bad/'probe-manifest.json').exists())
