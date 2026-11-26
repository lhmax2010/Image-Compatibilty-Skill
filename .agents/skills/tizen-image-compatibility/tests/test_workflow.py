"""Public workflow entrypoints exercised with real local synthetic ELF."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'


@unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Requires local GCC and readelf')
class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.root = Path(temp.name)
        cls.inputs = cls.root/'two inputs 图'
        subprocess.run([sys.executable,str(SCRIPTS/'make_synthetic_fixture.py'),str(cls.inputs)],
                       check=True,capture_output=True,timeout=30)
        cls.command = [sys.executable,str(SCRIPTS/'compat_workflow.py')]

    def setUp(self):
        self.job = self.root/self._testMethodName
        self.job.mkdir()

    def config(self, output='out', **kwargs):
        options = {'baseline':'../'+self.inputs.name+'/baseline','candidate':'../'+self.inputs.name+'/candidate',
                   'output':output,'objective':'EXPORT_SYMBOLS'}
        options.update(kwargs)
        path = self.job/(output.replace('/','-')+'.json')
        path.write_text(json.dumps(options))
        return path

    def invoke(self, *argv, expected=0):
        result = subprocess.run([*self.command,*map(str,argv)],cwd=self.root,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return result.stdout

    def test_rootfs_directory_and_manifest_use_same_export_contract(self):
        config = self.config()
        plan = json.loads(self.invoke('plan','--config',config))
        self.assertEqual(set(plan['inputs'].values()),{'ROOTFS_DIRECTORY'})
        self.assertFalse((self.job/'out').exists())
        self.invoke('run','--config',config,expected=1)
        report = self.job/'out'
        status = json.loads(self.invoke('status','--output',report))
        self.assertEqual(status['objective_completion'],'COMPLETE')
        self.assertEqual(status['compatibility_status'],'INCOMPATIBLE')
        with (report/'symbol-differences.csv').open(newline='') as stream:
            self.assertTrue(any(row['role']=='EXPORT' and row['change']=='MISSING' for row in csv.DictReader(stream)))
        self.assertIn('Objective completion',(report/'index.html').read_text())
        manifests = {'baseline_manifest':'out/baseline-manifest.json','candidate_manifest':'out/candidate-manifest.json',
                     'output':'reuse','objective':'EXPORT_SYMBOLS'}
        conf = self.job/'reuse.json'
        conf.write_text(json.dumps(manifests))
        self.invoke('run','--config',conf,expected=1)
        value = json.loads((self.job/'reuse/run-summary.json').read_text())
        self.assertEqual(value['source_evidence'],'MANIFEST_REUSE')
        self.assertEqual(value['objective_completion'],'COMPLETE')
        self.assertEqual(value['statistics']['symbol_differences'],
                         json.loads((report/'run-summary.json').read_text())['statistics']['symbol_differences'])

    def test_plain_and_compressed_tar_feed_real_elf_and_leave_inputs_unchanged(self):
        archives = []
        for side, extension, mode in (('baseline','.tar','w'),('candidate','.tar.gz','w:gz')):
            path = self.job/(side+extension)
            with tarfile.open(path,mode,dereference=False) as out:
                for item in (self.inputs/side).iterdir():
                    out.add(item,arcname=item.name)
            archives.append(path)
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in archives]
        cfg = self.config(baseline=archives[0].name,candidate=archives[1].name)
        self.invoke('run','--config',cfg,expected=1)
        data = json.loads((self.job/'out/run-summary.json').read_text())
        self.assertEqual(data['scope'],'RUNTIME_ROOTFS')
        self.assertEqual(data['objective_completion'],'COMPLETE')
        self.assertTrue(all(data['statistics'][s]['exports']>0 for s in ('baseline','candidate')))
        self.assertEqual(before,[hashlib.sha256(path.read_bytes()).hexdigest() for path in archives])

    def test_required_export_without_elf_is_not_success(self):
        (self.job/'empty/etc').mkdir(parents=True)
        cfg = self.config(baseline='empty',candidate='empty')
        self.invoke('run','--config',cfg,expected=3)
        state = json.loads(self.invoke('summary','--output',self.job/'out'))
        self.assertEqual(state['objective_completion'],'NOT_EXECUTED')
        self.assertEqual(state['statistics']['baseline']['exports'],0)
        self.assertIsNone(state['statistics']['baseline']['export_coverage_percent'])

    def test_broken_input_and_nonempty_output_keep_evidence(self):
        path = self.job/'broken'
        path.write_bytes(b'unsupported file')
        cfg = self.config(candidate=path.name)
        self.invoke('run','--config',cfg,expected=2)
        summary = self.job/'out/run-summary.json'
        before = summary.read_bytes()
        self.assertEqual(json.loads(before)['objective_completion'],'BLOCKED')
        self.invoke('run','--config',cfg,expected=2)
        self.assertEqual(summary.read_bytes(),before)
        self.assertEqual(path.read_bytes(),b'unsupported file')

    def test_invalid_config_and_unconfirmed_fallback(self):
        self.invoke('plan','--config',self.config(rpm_mode='metadata'),expected=2)
        self.invoke('plan','--config',self.config(extra_key='unexpected'),expected=2)
        self.invoke('plan','--config',self.config(baseline_rpm_fallback='a',candidate_rpm_fallback='b'),expected=2)
        self.invoke('plan','--config',self.config(mode='runtime'),expected=2)

    def test_simultaneous_same_output_has_one_owner(self):
        cfg = self.config()
        argv = [*self.command,'run','--config',str(cfg)]
        first = subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        second = subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for process in (first,second):
            process.communicate(timeout=45)
        self.assertEqual(sorted(p.returncode for p in (first,second)),[1,2])
        self.assertEqual(json.loads((self.job/'out/run-summary.json').read_text())['objective_completion'],'COMPLETE')

    def test_optional_index_failure_keeps_basic_report(self):
        (self.job/'already there').mkdir()
        cfg = self.config(index_output='already there')
        self.invoke('run','--config',cfg,expected=1)
        data = json.loads((self.job/'out/run-summary.json').read_text())
        self.assertEqual(data['objective_completion'],'COMPLETE')
        self.assertEqual(data['optional_stages']['enhanced_index']['status'],'FAILED')
        self.assertTrue((self.job/'out/elf-symbol-summary.csv').is_file())
