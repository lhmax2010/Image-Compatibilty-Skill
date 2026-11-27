"""Synthetic RPM payload end-to-end coverage. The package scriptlets are never run."""
import copy
from collections import Counter
import csv
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from compat import erofs, repository
from compat.core import DEFAULTS, Tools
from compat.rpm_payload import scan_cpio


def newc(members):
    data = bytearray()
    for index,(path,mode,raw,links,ino) in enumerate([*members,('TRAILER!!!',0,b'',1,0)],1):
        name = path.encode()+b'\0'
        fields = [ino or index,mode,0,0,links,0,len(raw),0,0,0,0,len(name),0]
        data += b'070701'+''.join(f'{x:08x}' for x in fields).encode()+name
        data += bytes((-len(data))%4)+raw
        data += bytes((-len(data))%4)
    return bytes(data)


class CpioTests(unittest.TestCase):
    def scan(self, members):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            return scan_cpio(io.BytesIO(newc(members)),output,Tools(output,copy.deepcopy(DEFAULTS)),
                             'static',False,time.monotonic()+10)

    def test_reject_escape_duplicate_and_descendant_of_link(self):
        file = stat.S_IFREG|0o644
        link = stat.S_IFLNK|0o777
        for items in (
            [('../escape',file,b'x',1,0)], [('/absolute',file,b'x',1,0)],
            [('usr/link',link,b'../../escape',1,0)],
            [('usr/link/child',file,b'x',1,0),('usr/link',link,b'elsewhere',1,0)],
            [('same',file,b'x',1,0),('same',file,b'y',1,0)],
            [('unpaired',file,b'x',2,55)]):
            with self.subTest(items=items),self.assertRaises(ValueError):
                self.scan(items)

    def test_hardlinks_are_metadata_and_absolute_targets_stay_virtual(self):
        file = stat.S_IFREG|0o4755
        rows,objects,_ = self.scan([('./usr/bin/a',file,b'',2,12),('./usr/bin/b',file,b'bytes',2,12),
                                  ('./usr/bin/link',stat.S_IFLNK|0o777,b'/usr/bin/b',1,0),
                                  ('./dev/mock',stat.S_IFCHR|0o600,b'',1,0)])
        by_path = {r['path']:r for r in rows}
        self.assertEqual(by_path['/usr/bin/a']['sha256'],hashlib.sha256(b'bytes').hexdigest())
        self.assertEqual(by_path['/usr/bin/link']['virtual_target'],'/usr/bin/b')
        self.assertEqual(by_path['/dev/mock']['type'],'special-metadata-only')
        self.assertEqual(objects,[])

    def test_nevra_architecture_and_soname_ambiguity(self):
        def archive(arch,version,checksum):
            return {'package':{'name':'one','arch':arch,'epoch':'0','version':version,'release':'1'},
                    'sha256':checksum,'metadata_status':'COMPLETE'}
        side = {'archives':[archive('armv7l','1','a'),archive('aarch64','1','b'),archive('noarch','2','c')]}
        self.assertEqual(set(repository.group_archives(side)),{('one','armv7l'),('one','aarch64'),('one','noarch')})
        groups = repository.group_archives({'archives':[archive('armv7l','1','a'),archive('armv7l','2','b')]})
        target = repository.group_archives({'archives':[archive('armv7l','3','c')]})
        key=('one','armv7l')
        self.assertEqual(list(repository.group_matches(groups[key],target[key],(True,True)))[0][0],
                         'AMBIGUOUS_MULTIPLE_VERSIONS')
        unknown = list(repository.group_matches(groups[key],{},(True,False)))
        self.assertTrue(all(row[0]=='INVENTORY_INCOMPLETE' for row in unknown))
        def obj(path):
            return dict(package_path=path,soname='one.so',complete=True,machine='ARM',size=4)
        peers = list(repository.object_pairs([obj('/old/a')],[obj('/usr/a'),obj('/usr/b')]))
        self.assertEqual(peers[0][0],'BASELINE_ONLY_OR_UNRESOLVED')

    def test_lookup_identity_default_demotion_and_incomplete_inventory(self):
        def symbol(name):
            return {'name':name,'type':'FUNC','size':4,'binding':'GLOBAL','visibility':'DEFAULT'}

        def obj(*names, complete=True):
            return {'exports':[symbol(name) for name in names],'export_inventory_complete':complete}

        old = obj('example@@ONE','same','absent')
        candidate = obj('example@ONE','example@@TWO','same')
        self.assertEqual(repository.symbol_counts([old,candidate]),{
            'export_unique_symbol_names':3,'export_lookup_identities':8,
            'import_unique_symbol_names':0,'import_lookup_identities':0})
        pair = {'package_id':'rpm-test','component':'example'}
        findings = {'example:default lookup':[{'status':'UNKNOWN','id':'default-lookup'}]}
        rows = list(repository.symbol_rows(pair,old,candidate,findings))
        by_old = {row['baseline']['name']:row for row in rows if row['baseline']}
        default = by_old['example@@ONE']
        self.assertEqual(default['candidate']['name'],'example@ONE')
        self.assertEqual(default['details'],['DEFAULT_LOOKUP_CHANGED'])
        self.assertEqual(default['finding_ids'],['default-lookup'])
        self.assertEqual(by_old['absent']['change'],'MISSING')
        observed = list(repository.symbol_rows(pair,old,candidate | {'export_inventory_complete':False},{}))
        self.assertEqual(next(row['change'] for row in observed if row['baseline']==symbol('absent')),'BASELINE_OBSERVED')
        self.assertEqual(next(row['change'] for row in observed if row['candidate']==symbol('example@@TWO')),
                         'CANDIDATE_OBSERVED')
        self.assertEqual(next(row['change'] for row in observed if row['baseline']==symbol('example@@ONE')),
                         'BASELINE_OBSERVED')

    def test_completed_digest_duplicate_is_preferred_and_others_remain_observed(self):
        bad = {'id':'before-sort','extraction_status':'FAILED','objects':[]}
        successful = {'id':'after-sort','extraction_status':'COMPLETE','objects':['/a']}
        duplicate = {'id':'last-sort','extraction_status':'COMPLETE','objects':['/b']}
        candidate = {'id':'candidate','extraction_status':'COMPLETE','objects':['/c']}
        left = [bad,successful,duplicate]
        self.assertIs(repository.preferred_archive(left),successful)
        a,b,c = ({'path':'/'+x,'package_path':'/example'} for x in 'abc')
        self.assertEqual(list(repository.package_objects((left,[candidate]),(successful,candidate),
                         ({'/a':a,'/b':b},{'/c':c}),True)),[
            ('PATH',a,c,''),('UNPAIRED_ARCHIVE_OBSERVATION',b,None,'/baseline/b')])


@unittest.skipUnless(all(shutil.which(x) for x in ('g++','readelf','rpm','rpmbuild','rpm2cpio')), 'Requires local RPM tools and host g++')
class RealRpmPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.root = Path(temp.name)
        cls.populate()

    @classmethod
    def populate(cls):
        cls.spec = cls.root/'package.spec'
        cls.before,cls.after = cls.root/'baseline'/'nested',cls.root/'candidate'/'packages'
        for directory in (cls.before,cls.after):
            directory.mkdir(parents=True)
        old = cls.build_library('old',False)
        new = cls.build_library('new',True)
        for path,binary,version in [(cls.before,old,'1'),(cls.after,new,'2')]:
            cls.build_rpm(path,'security-network-codec',version,binary)
            cls.build_rpm(path,'independent-library',version,old)
            cls.build_rpm(path,'metadata-only',version,None)
            for arch in ('armv7l','aarch64'):
                cls.build_rpm(path,'architecture-marker',version,None,arch=arch)
        cls.build_rpm(cls.before,'multi-version','1',None)
        cls.build_rpm(cls.before,'multi-version','2',None)
        cls.build_rpm(cls.after,'multi-version','3',None)
        cls.build_rpm(cls.before,'replaced-package','1',None)
        cls.build_rpm(cls.after,'replacement-package','1',None,provides='replaced-package')
        cls.build_rpm(cls.before,'known-addition','1',None)
        cls.build_rpm(cls.after,'candidate-addition','1',None)
        (cls.after/'broken.rpm').write_bytes(b'\xed\xab\xee\xdb truncated')
        cls.output = cls.root/'report'
        cls.run_cli(cls.before.parent,cls.after.parent,cls.output,1)
        cls.results = json.loads((cls.output/'results.json').read_text())

    @classmethod
    def build_library(cls,name,changed):
        code = cls.root/(name+'.cpp')
        body='int sum=0; for(int i=0;i<6;i++) sum+=i; return sum;' if changed else 'return 1;'
        code.write_text(f'''extern "C" {{
int data_contract[{2 if changed else 1}] = {{1}};
int stable_code() {{{body}}}
int stable_symbol() {{ return 1; }}
__thread int tls_contract = 1;
static int impl() {{ return 5; }}
int (*resolve_contract(void))(void) {{ return impl; }}
int ifunc_contract(void) __attribute__((ifunc("resolve_contract")));
int version_switch() {{ return 1; }}
int {'added_symbol' if changed else 'removed_symbol'}() {{ return 1; }}
extern int external_contract();
int call_external() {{ return external_contract(); }}
}}
int mangled_contract(int x) {{ return x+1; }}
''')
        version = cls.root/(name+'.map')
        version.write_text('STABLE_1 { global: stable_*; call_external; data_contract; tls_contract; ifunc_contract; _Z*; };\n'
                           + ('NEXT_2' if changed else 'NEXT_1')+' { global: version_switch; '
                           + ('added_symbol' if changed else 'removed_symbol')+'; local: *; };\n')
        elf = cls.root/(name+'.bin')
        libasan = subprocess.check_output(['g++','-print-file-name=libasan.so'],text=True).strip()
        cls.asan_available = Path(libasan).is_file()
        flags = ['-fsanitize=address','-Wl,--no-as-needed','-lasan'] if changed and cls.asan_available else []
        subprocess.run(['g++','-shared','-nostdlib','-O0','-fPIC',str(code),*flags,
                        '-Wl,-soname,contract.so.1','-Wl,--version-script='+str(version),'-o',str(elf)],check=True,
                        capture_output=True,timeout=30)
        return elf

    @classmethod
    def build_rpm(cls,directory,name,version,binary,provides=None,arch=None):
        top = cls.root/'build'
        leaf = 'shared.payload' if binary else 'notes.txt'
        content = f'cp "{binary}" "%{{buildroot}}/usr/lib/{leaf}"' if binary else f'printf synthetic > "%{{buildroot}}/usr/lib/{leaf}"'
        cls.spec.write_text(f'''Name: {name}
Version: {version}
Release: 1
Summary: Release test synthetic package
License: MIT
{'' if binary or arch else 'BuildArch: noarch'}
{f'Provides: {provides}' if provides else ''}
%description
Synthetic RPM fixture
%install
mkdir -p "%{{buildroot}}/usr/lib"
{content}
%post
touch "{cls.root}/SCRIPTLET-RAN"
%files
/usr/lib/{leaf}
''')
        target = ['--target',arch+'-linux'] if arch else []
        result = subprocess.run(['rpmbuild','-bb',*target,'--define','_topdir '+str(top),
                                '--define','_tmppath '+str(cls.root),'--define','__os_install_post %{nil}',
                                str(cls.spec)],capture_output=True,text=True,timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)
        (built,) = list((top/'RPMS').rglob(f'{name}-{version}-1.*.rpm'))
        built.rename(directory/built.name)
        return directory/built.name

    @classmethod
    def run_cli(cls,before,after,output,code,*flags):
        p = subprocess.run([sys.executable,str(SCRIPTS/'tizen_compat.py'),'--baseline',str(before),'--candidate',str(after),
                            '--output',str(output),*flags],capture_output=True,text=True,timeout=90)
        if p.returncode!=code or 'Traceback' in p.stderr:
            raise AssertionError((p.returncode,p.stdout,p.stderr))

    def test_real_rpm_payload_reports_and_scope(self):
        result = self.results
        self.assertEqual(result['scope'],'RPM_REPOSITORY_PAYLOAD')
        self.assertNotIn('filesystem',{f['dimension'] for f in result['findings']})
        self.assertTrue({'security','network','hardware'}.isdisjoint(f['dimension'] for f in result['findings']))
        self.assertIsNone(result['package_inventory']['baseline_package_count'])
        self.assertGreaterEqual(result['repository']['baseline']['export_inventories_complete'],2)
        self.assertGreaterEqual(result['repository']['baseline']['exports'],10)
        self.assertEqual(result['repository']['candidate']['rpm_total'],9)
        self.assertTrue(any(Path(row['archive']).name=='broken.rpm' for row in result['repository']['errors']))
        baseline = json.loads((self.output/'baseline-manifest.json').read_text())
        objects = baseline['elf_objects']
        self.assertEqual({o['package_path'] for o in objects},{'/usr/lib/shared.payload'})
        self.assertEqual(len({o['path'] for o in objects}),2)
        for obj in objects:
            self.assertEqual(len(obj['sha256']),64)
        self.assertFalse((self.root/'SCRIPTLET-RAN').exists())
        self.assertTrue(any(p['inventory_status']=='AMBIGUOUS_MULTIPLE_VERSIONS' for p in result['repository']['packages']))
        self.assertEqual({p['arch'] for p in result['repository']['packages'] if p['name']=='architecture-marker'},
                         {'armv7l','aarch64'})
        for leaf in ('index.html','summary.md','results.json','packages.csv','findings.csv','package-symbol-summary.csv',
                     'elf-symbol-summary.csv','symbol-differences.csv','extraction-errors.csv'):
            self.assertTrue((self.output/leaf).is_file(),leaf)
        self.assertIn(result['scope'],(self.output/'index.html').read_text())

    def test_export_import_details_and_code_size_is_not_abi_failure(self):
        with (self.output/'symbol-differences.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        findings = [f for f in self.results['findings'] if f['status']=='INCOMPATIBLE']
        self.assertTrue(any(f['interface'].startswith('removed_symbol') for f in findings))
        (size,) = [f for f in self.results['findings'] if f['interface'].startswith('data_contract')
                   and f['interface'].endswith(':size')]
        self.assertEqual((size['status'],size['reason_code']),('UNKNOWN','INSTRUMENTATION_MISMATCH') if self.asan_available
                         else ('INCOMPATIBLE','DATA_SIZE_INCREASED'))
        self.assertFalse(any(f['interface'].startswith('stable_code') and f['interface'].endswith(':size') for f in findings))
        self.assertTrue(any('CODE_SIZE_CHANGED' in row['details'] for row in rows))
        self.assertTrue(any('DATA_SIZE_CHANGED' in row['details'] for row in rows))
        self.assertTrue(any('VERSION_CHANGED' in row['details'] for row in rows))
        self.assertTrue(any(row['change']=='ADDED' and row['status']=='COMPATIBLE' and 'added_symbol' in row['candidate']
                            for row in rows))
        self.assertTrue(any('_Z' in row['baseline'] for row in rows))
        self.assertTrue(any(row['role']=='IMPORT' and 'external_contract' in row['baseline'] for row in rows))
        exports = [json.loads(row['baseline']) for row in rows if row['role']=='EXPORT' and row['baseline']!='UNKNOWN']
        self.assertTrue(any(s['name'].startswith('tls_contract') and s['type']=='TLS' for s in exports))
        self.assertTrue(any(s['name'].startswith('ifunc_contract') and s['type'] in ('IFUNC','GNU_IFUNC') for s in exports))
        if self.asan_available:
            self.assertIn('libasan.so',(self.output/'elf-symbol-summary.csv').read_text())
        stats = self.results['repository']['symbol_differences']
        self.assertEqual(stats['exports_baseline_unsatisfied'],2)
        self.assertEqual({json.loads(row['baseline'])['name'] for row in rows if row['baseline_identity_satisfied']=='false'},
                         {'removed_symbol@@NEXT_1','version_switch@@NEXT_1'})
        changes = dict(Counter(r['change'] for r in rows))
        self.assertEqual(stats['by_change'],changes)
        for role,summary in stats['by_role'].items():
            self.assertEqual(summary['by_change'],dict(Counter(r['change'] for r in rows if r['role']==role)))
        if self.asan_available:
            self.assertEqual(changes,{'MATCHED':16,'ADDED':5,'CHANGED':3,'MISSING':1})
            self.assertEqual(stats['rows'],25)
        for side in ('baseline','candidate'):
            counts = self.results['repository'][side]
            self.assertEqual(counts['exports'],18)
            self.assertEqual(counts['export_unique_symbol_names'],9 if side=='baseline' else 10)
            self.assertEqual(counts['export_lookup_identities'],36)

    def test_ambiguous_versions_retain_every_real_elf_as_observed(self):
        root = self.root/'ambiguous-elf'
        baseline,candidate = root/'left',root/'right'
        for side in (baseline,candidate):
            side.mkdir(parents=True)
        first,second = (next(side.glob('security-network-codec*.rpm')) for side in (self.before,self.after))
        for rpm in (first,second):
            shutil.copyfile(rpm,baseline/rpm.name)
        self.build_rpm(candidate,'security-network-codec','3',self.root/'new.bin')
        output = root/'report'
        self.run_cli(baseline,candidate,output,0)
        result = json.loads((output/'results.json').read_text())['repository']
        self.assertEqual(result['packages'][0]['inventory_status'],'AMBIGUOUS_MULTIPLE_VERSIONS')
        pairs = result['elf_pairs']
        self.assertEqual(len({r['component'] for r in pairs}),3)
        self.assertTrue(all(r['match']=='UNPAIRED_ARCHIVE_OBSERVATION' for r in pairs))
        with (output/'symbol-differences.csv').open() as stream:
            exports = [r for r in csv.DictReader(stream) if r['role']=='EXPORT']
        self.assertEqual(Counter(r['change'] for r in exports),{'BASELINE_OBSERVED':18,'CANDIDATE_OBSERVED':9})

    def test_native_repository_manifest_replay_preserves_scope_and_rejects_dangling_objects(self):
        baseline = self.output/'baseline-manifest.json'
        candidate = self.output/'candidate-manifest.json'
        output = self.root/'replay-report'
        argv = [sys.executable,str(SCRIPTS/'tizen_compat.py'),'--baseline-manifest',str(baseline)]
        result = subprocess.run([*argv,'--candidate-manifest',str(candidate),'--output',str(output)],
                                capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,1,result.stderr)
        reused = json.loads((output/'results.json').read_text())
        self.assertEqual(reused['scope'],'RPM_REPOSITORY_PAYLOAD')
        self.assertEqual(reused['repository']['symbol_differences'],self.results['repository']['symbol_differences'])
        self.assertEqual({row['id'] for row in reused['findings']},{row['id'] for row in self.results['findings']})
        self.assertIn('broken.rpm',(output/'extraction-errors.csv').read_text())
        self.assertEqual((output/'symbol-differences.csv').read_bytes(),(self.output/'symbol-differences.csv').read_bytes())

        data = json.loads(candidate.read_text())
        data['repository']['archives'][0]['objects'].append('/no/such/ELF')
        malformed = self.root/'invalid-replay-manifest.json'
        malformed.write_text(json.dumps(data))
        result = subprocess.run([*argv,'--candidate-manifest',str(malformed),'--output',str(self.root/'invalid-replay')],
                                capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertIn('Invalid manifest',result.stderr)
        self.assertNotIn('Traceback',result.stderr)

    def test_complete_archive_inventory_identifies_missing_and_replacement_hints(self):
        before = next(self.before.glob('replaced-package*.rpm'))
        after = next(self.after.glob('replacement-package*.rpm'))
        output = self.root/'replacement-metadata'
        self.run_cli(before,after,output,0,'--rpm-mode','metadata')
        rows = json.loads((output/'results.json').read_text())['repository']['packages']
        self.assertEqual({r['inventory_status'] for r in rows},{'MISSING','ADDED'})
        self.assertEqual(next(r for r in rows if r['inventory_status']=='MISSING')['replacement_hints'],
                         [['replacement-package','replaced-package','provides']])

    def test_cli_rejects_untrusted_member_from_host_converter_fixture(self):
        root = self.root/'unsafe'
        root.mkdir()
        stream = root/'bad.cpio'
        stream.write_bytes(newc([('../escape',stat.S_IFREG|0o644,b'outside',1,0)]))
        converter = root/'fixture-rpm2cpio'
        converter.write_text('#!/bin/sh\nexec cat '+repr(str(stream))+'\n')
        converter.chmod(0o700)
        base = next(self.before.glob('security-network-codec*.rpm'))
        candidate = next(self.after.glob('security-network-codec*.rpm'))
        config = root/'config.json'
        if importlib.util.find_spec('yaml') is None:
            self.skipTest('Explicit fixture converter configuration requires PyYAML')
        config.write_text(json.dumps({'tools':{'rpm2cpio':str(converter)}}))
        output = root/'report'
        self.run_cli(base,candidate,output,3,'--config',str(config))
        result = json.loads((output/'results.json').read_text())
        self.assertEqual(result['repository']['baseline']['extracted'],0)
        self.assertEqual(result['repository']['baseline']['export_analysis_status'],'NOT_EXECUTED')
        self.assertTrue(all('Unsafe CPIO pathname' in error['reason'] and error['evidence']
                            for error in result['repository']['errors']))
        self.assertFalse((root/'escape').exists())

    def test_single_archive_metadata_mode_and_optional_browser(self):
        base = next(self.before.glob('security-network-codec*.rpm'))
        candidate = next(self.after.glob('security-network-codec*.rpm'))
        output = self.root/'metadata'
        self.run_cli(base,candidate,output,0,'--rpm-mode','metadata')
        result = json.loads((output/'results.json').read_text())
        self.assertEqual(result['scope'],'RPM_REPOSITORY_METADATA')
        self.assertEqual(result['repository']['baseline']['elf_collected'],0)
        self.assertIsNone(result['repository']['baseline']['export_coverage_percent'])
        summary = json.loads((output/'run-summary.json').read_text())
        self.assertEqual(summary['requested_objective'],'PACKAGE_INVENTORY')
        self.assertEqual(summary['objective_completion'],'COMPLETE')
        self.assertEqual(summary['statistics']['baseline']['export_analysis_status'],'NOT_EXECUTED')
        from compat.repository_browser import build,RepositoryBrowser
        indexed = self.root/'indexed'
        build(self.output,indexed)
        page = RepositoryBrowser(indexed).query('symbols',{'limit':['2']})
        self.assertEqual(len(page['rows']),2)
        self.assertIsNotNone(page['next_after'])

    def test_erofs_failure_can_switch_to_both_explicit_rpm_inputs(self):
        image = self.root/'unrecognized.erofs'
        blob = bytearray(4096)
        blob[1024:1028] = b'\xe2\xe1\xf5\xe0'
        blob[1036] = 12
        struct.pack_into('<I',blob,1060,1)
        struct.pack_into('<I',blob,1104,0x80000000)
        image.write_bytes(blob)
        before = next(self.before.glob('security-network-codec*.rpm'))
        after = next(self.after.glob('security-network-codec*.rpm'))
        output = self.root/'fallback'
        self.run_cli(image,image,output,1,'--baseline-rpm-fallback',str(before),
                     '--candidate-rpm-fallback',str(after))
        report = json.loads((output/'results.json').read_text())
        self.assertEqual(report['scope'],'RPM_REPOSITORY_PAYLOAD')
        receipt = json.loads((output/'baseline-extraction-manifest.json').read_text())
        self.assertEqual(receipt['failure']['code'],'EROFS_FEATURE_UNSUPPORTED')
        self.assertIn('EROFS_FEATURE_UNSUPPORTED',report['baseline']['fallback_reason'])
        self.assertEqual(image.read_bytes(),blob)
        workflow = self.root/'fallback-job.json'
        workflow.write_text(json.dumps({'baseline':str(image),'candidate':str(image),'output':'workflow-fallback',
            'baseline_rpm_fallback':str(before),'candidate_rpm_fallback':str(after),'same_build_confirmed':True}))
        run = subprocess.run([sys.executable,str(SCRIPTS/'compat_workflow.py'),'run','--config',str(workflow)],
                             capture_output=True,text=True,timeout=45)
        self.assertEqual(run.returncode,1,run.stdout+run.stderr)
        summary = json.loads((self.root/'workflow-fallback/run-summary.json').read_text())
        self.assertEqual(summary['scope'],'RPM_REPOSITORY_PAYLOAD')
        self.assertEqual(summary['objective_completion'],'COMPLETE')
        self.assertTrue(any('RPM fallback' in e['reason'] for e in summary['errors']))


class ErofsTests(unittest.TestCase):
    def test_identifies_features_algorithms_and_devices(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp)/'erofs'
            data = bytearray(8192)
            data[1024:1028]=b'\xe2\xe1\xf5\xe0'
            data[1036]=12
            struct.pack_into('<I',data,1060,2)
            struct.pack_into('<IHHH',data,1104,0x8a,0b1101,2,8)
            image.write_bytes(data)
            info=erofs.superblock(image)
            self.assertEqual(info['unknown_incompat_mask'],0x80)
            self.assertEqual(info['extra_devices'],2)
            self.assertEqual(info['compression_algorithms'],['lz4','deflate','zstd'])
            tools = Tools(Path(temp),copy.deepcopy(DEFAULTS))
            self.assertEqual(erofs.blocker(info,tools),'EROFS_EXTRA_DEVICES_REQUIRED')
            struct.pack_into('<I',data,1032,0x80000001)
            struct.pack_into('<IHHH',data,1104,0,0,0,0)
            image.write_bytes(data)
            info = erofs.superblock(image)
            self.assertEqual(info['known_compat_features'],['SB_CHKSUM'])
            self.assertEqual(info['unknown_compat_mask'],0x80000000)
            self.assertEqual(erofs.blocker(info,tools),'EROFS_FEATURE_UNSUPPORTED')

    @unittest.skipUnless(shutil.which('bwrap') and shutil.which('tar'), 'Requires bwrap and tar for command fixture')
    def test_confined_extractor_command_and_evidence_with_host_tool_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root/'synthetic.erofs'
            blob = bytearray(4096)
            blob[1024:1028] = b'\xe2\xe1\xf5\xe0'
            blob[1036] = 12
            struct.pack_into('<I',blob,1060,1)
            image.write_bytes(blob)
            tool = root/'synthetic-fsck'
            tool.write_text('#!/bin/sh\ncase "$1" in\n'
                            '--version) echo "synthetic host fixture";;\n'
                            '--help) echo "--extract --[no-]preserve";;\n'
                            '--extract=*) dest=${1#*=}; test "$2" = --no-preserve || exit 9; '
                            'test -r "$3" && test ! -w "$3" || exit 10; '
                            'test ! -e /home && test ! -e /etc/passwd || exit 11; '
                            'mkdir "$dest/etc"; echo fixture > "$dest/etc/os-release"; echo extraction-fixture >&2;;\n'
                            '*) exit 8;;\nesac\n')
            tool.chmod(0o700)
            output = root/'prepared'
            output.mkdir()
            config = copy.deepcopy(DEFAULTS)
            config['tools']['fsck.erofs'] = str(tool)
            from compat.preparation import prepare
            record = prepare(image,output,Tools(output,config))
            self.assertEqual(record['status'],'READY')
            self.assertIn('extraction-fixture',(output/record['extractor']['stderr_evidence']).read_text())
            self.assertEqual((output/'rootfs/etc/os-release').read_text(),'fixture\n')
            self.assertEqual(image.read_bytes(),blob)

    @unittest.skipUnless(all(shutil.which(x) for x in ('fsck.erofs','mkfs.erofs','bwrap','gcc','readelf')),
                         'Standard EROFS extraction requires local mkfs.erofs and fsck.erofs')
    def test_real_erofs_images_extract_and_collect_elf(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fixture=root/'fixture'
            subprocess.run([sys.executable,str(SCRIPTS/'make_synthetic_fixture.py'),str(fixture)],check=True,timeout=20)
            images=[]
            for side in ('baseline','candidate'):
                image=root/(side+'.erofs')
                subprocess.run(['mkfs.erofs',str(image),str(fixture/side)],check=True,capture_output=True,timeout=30)
                images.append(image)
            output=root/'report'
            RealRpmPayloadTests.run_cli(*images,output,1)
            result=json.loads((output/'results.json').read_text())
            self.assertEqual(result['scope'],'RUNTIME_ROOTFS')
            self.assertTrue(any(f['status']=='INCOMPATIBLE' and f['dimension']=='abi' for f in result['findings']))
            for side in ('baseline','candidate'):
                receipt=json.loads((output/(side+'-extraction-manifest.json')).read_text())
                self.assertEqual(receipt['status'],'READY')
                self.assertEqual(receipt['extractor']['status'],'COMPLETE')
