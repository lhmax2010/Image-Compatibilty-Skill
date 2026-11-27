"""WP-2 real ELF/RPM scenarios and independently specified outcomes."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_rpm_payload import SCRIPTS
from compat.compare import compare_elf
from compat.profile import comparison_profile
from compat.repository_pairing import reconcile
from compat.requirements import Providers, check_available_set, classify


def execute(*args, expected=0):
    result = subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120)
    if result.returncode!=expected:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    return result


def prerequisite(tool, env=None):
    return (os.getenv(env) if env else None) or shutil.which(tool)


class RepositoryFixtures(unittest.TestCase):
    def setUp(self):
        for name in ('gcc','rpmbuild','rpm','rpm2cpio','readelf'):
            if not prerequisite(name):
                self.blocked(name)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.build = self.root/'build'
        self.build.mkdir()
        self.serial = 0

    def blocked(self, tool):
        reason = 'BLOCKED: missing '+tool
        if os.getenv('COMPAT_RELEASE_CI')=='1':
            self.fail(reason)
        self.skipTest(reason)

    def file(self, leaf, text):
        path = self.root/leaf
        path.write_text(text)
        return path

    def library(self, leaf, soname, text, *, version=None, clang=None, flags=(), deps=()):
        source = self.file(leaf+'.c',text)
        binary = self.root/leaf
        compiler = clang or 'gcc'
        obj = self.root/(leaf+'.o')
        execute(compiler,'-O0','-g','-fPIC','-c',*flags,source,'-o',obj)
        link = ['gcc','-shared','-nostdlib',obj,f'-Wl,-soname,{soname}',*deps,'-o',binary]
        if version:
            versions = self.file(leaf+'.map',version+' { global: *; };\n')
            link.append(f'-Wl,--version-script={versions}')
        execute(*link)
        return binary

    def rpm(self, repo, name, files, *, arch='x86_64', version='1'):
        repo.mkdir(parents=True,exist_ok=True)
        self.serial += 1
        top = self.build/str(self.serial)
        top.mkdir()
        install, paths = [], []
        for virtual,source in files.items():
            install.append(f'mkdir -p "%{{buildroot}}{Path(virtual).parent}"')
            install.append(f'cp "{source}" "%{{buildroot}}{virtual}"')
            paths.append(virtual)
        spec = top/'fixture.spec'
        spec.write_text(f'Name: {name}\nVersion: {version}\nRelease: 1\nSummary: Synthetic WP-2 fixture\n'
                        'License: MIT\n%description\nSynthetic fixture\n%install\n'+
                        '\n'.join(install)+'\n%files\n'+'\n'.join(paths)+'\n')
        execute('rpmbuild','-bb','--target',arch+'-linux','--define',f'_topdir {top}',
                '--define',f'_tmppath {top}','--define','__os_install_post %{nil}',spec)
        (binary,) = (top/'RPMS').rglob('*.rpm')
        shutil.copy2(binary,repo/binary.name)

    def run_case(self, a,b,label,*,expected=1,workflow=False):
        report = self.root/(label+'-report')
        if workflow:
            job = self.file(label+'-workflow.json',json.dumps(
                {'baseline':str(a),'candidate':str(b),'output':str(report),'objective':'EXPORT_SYMBOLS','rpm_mode':'payload'}))
            execute(sys.executable,SCRIPTS/'compat_workflow.py','run','--config',job,expected=expected)
        else:
            execute(sys.executable,SCRIPTS/'tizen_compat.py','--baseline',a,'--candidate',b,'--output',report,
                    expected=expected)
        result = json.loads((report/'results.json').read_text())
        summary = json.loads((report/'run-summary.json').read_text())
        if os.getenv('WP2_ACCEPTANCE_OUTPUT'):
            capture = Path(os.environ['WP2_ACCEPTANCE_OUTPUT'])
            def assessment(data):
                return {'library_and_symbol_findings':[{k:f.get(k) for k in ('interface','status','severity','reason_code')}
                    for f in data['findings'] if f['dimension']=='abi'],
                    'available_set': data['repository'].get('requirements')}
            record = {'exit':expected,'summary':summary,'assessment':assessment(result)}
            if old_cli := os.getenv('WP2_BASELINE_CLI'):
                old_report = self.root/(label+'-old-report')
                old = subprocess.run([sys.executable,old_cli,'--baseline',str(a),'--candidate',str(b),
                                      '--output',str(old_report)],capture_output=True,text=True,timeout=60)
                assert old.returncode in (0,1,3),old.stderr
                record['baseline'] = {'exit':old.returncode,
                                      **assessment(json.loads((old_report/'results.json').read_text()))}
            (capture/(label+'.json')).write_text(json.dumps(record,indent=2))
        return report,result,summary

    def test_t05_library_removed_and_incomplete_control(self):
        left,right = self.root/'a',self.root/'b'
        lib = self.library('bar','libbar.so.1','int bar(void){return 1;}')
        marker = self.file('contents','same package metadata\n')
        self.rpm(left,'foo',{'/usr/lib/libbar.so.1':lib})
        self.rpm(right,'foo',{'/usr/share/doc/foo':marker},version='2')
        _,result,status = self.run_case(left,right,'t05',workflow=True)
        (removed,) = [f for f in result['findings'] if f.get('reason_code')=='LIBRARY_REMOVED']
        self.assertEqual((removed['status'],removed['severity'],removed['scope']),
                         ('INCOMPATIBLE','HIGH','RPM_REPOSITORY_PAYLOAD'))
        self.assertEqual(status['objective_completion'],'COMPLETE')
        (right/'broken.rpm').write_bytes(b'broken RPM fixture')
        _,result,status = self.run_case(left,right,'t05-incomplete',workflow=True,expected=3)
        (unknown,) = [f for f in result['findings'] if f['interface']=='Repository ELF path availability']
        self.assertEqual((unknown['status'],unknown['severity'],unknown['reason_code']),
                         ('UNKNOWN','MEDIUM','LIBRARY_NOT_FOUND_INCOMPLETE_INVENTORY'))
        self.assertEqual(status['objective_completion'],'PARTIAL')

    def split_case(self, before, after, label, arch='x86_64'):
        left,right = self.root/(label+'-a'),self.root/(label+'-b')
        self.rpm(left,'baz',{'/usr/lib/old-lib.so.1':before},arch=arch)
        self.rpm(right,'baz-libs',{'/usr/lib/new-lib.so.1':after},arch=arch)
        _,result,status = self.run_case(left,right,label,workflow=True)
        (pair,) = result['repository']['elf_pairs']
        self.assertEqual(pair['match'],'CROSS_PACKAGE_SONAME')
        self.assertNotEqual(pair['baseline_package_id'],pair['candidate_package_id'])
        self.assertTrue(any(f['interface']=='b' and f['status']=='INCOMPATIBLE' for f in result['findings']))
        self.assertEqual(status['objective_completion'],'COMPLETE')

    def test_t06_package_split(self):
        a = self.library('a','libbaz.so.1','int a(void){return 1;} int b(void){return 2;}')
        b = self.library('b','libbaz.so.1','int a(void){return 1;}')
        self.split_case(a,b,'t06')
        left,right = self.root/'path-a',self.root/'path-b'
        self.rpm(left,'baz',{'/usr/lib/same-lib.so.1':a})
        self.rpm(right,'baz-libs',{'/usr/lib/same-lib.so.1':b})
        _,result,_ = self.run_case(left,right,'t06-path',workflow=True)
        self.assertEqual(result['repository']['elf_pairs'][0]['match'],'CROSS_PACKAGE_PATH')

    def test_t06_package_split_sr_arm(self):
        compiled=[]
        version=self.file('versions.map','V1 { global: a; b; local: *; };\n')
        for i,family in enumerate(('GCC','CLANG')):
            compiler=prerequisite('arm-'+family.lower(),'WP1_ARM_'+family)
            if not compiler:
                self.blocked('SR ARMv7 '+family+' fixture wrapper')
            source=self.file(f'arm-{i}.c','int a(void){return 1;}'+(' int b(void){return 2;}' if not i else ''))
            version.write_text('V1 { global: a;'+(' b;' if not i else '')+' local: *; };\n')
            out=self.root/f'arm-{i}.so'
            execute(compiler,source,version,out)
            compiled.append(out)
        # The fixture wrapper versions the exported names.
        left,right=self.root/'arm-a',self.root/'arm-b'
        self.rpm(left,'baz',{'/usr/lib/old-lib.so.1':compiled[0]},arch='armv7l')
        self.rpm(right,'baz-libs',{'/usr/lib/new-lib.so.1':compiled[1]},arch='armv7l')
        report,result,_=self.run_case(left,right,'t06-arm',workflow=True)
        self.assertEqual(result['repository']['elf_pairs'][0]['match'],'CROSS_PACKAGE_SONAME')
        self.assertTrue(any(f['interface']=='b@@V1' and f['status']=='INCOMPATIBLE' for f in result['findings']))
        for side in ('baseline','candidate'):
            (obj,)=json.loads((report/(side+'-manifest.json')).read_text())['elf_objects']
            self.assertEqual((obj['machine'],obj['class']),('ARM','ELF32'))

    def test_t06b_ambiguous_soname(self):
        a=self.root/'a'
        b=self.root/'b'
        for repo,pkg,leaf,n in ((a,'old','old',0),(b,'candidate-one','new-one',1),(b,'candidate-two','new-two',2)):
            binary=self.library(leaf,'libq.so.1',f'int q(void){{return {n};}}')
            self.rpm(repo,pkg,{f'/usr/lib/{leaf}.so.1':binary})
        _,result,status=self.run_case(a,b,'t06b',expected=3,workflow=True)
        (finding,)=[f for f in result['findings'] if f.get('reason_code')=='PROVIDER_AMBIGUOUS']
        self.assertEqual((finding['status'],finding['severity'],len(finding['candidate'])),('UNKNOWN','MEDIUM',2))
        self.assertEqual(status['objective_completion'],'PARTIAL')

    def test_t07_requirements_and_baseline_control(self):
        libx=self.library('libx-origin','libx.so.1','int f(void){return 1;} int g(void){return 2;}',version='X_1')
        libh=self.library('libh-origin','libh.so.1','int h(void){return 3;}')
        client=self.library('client','app.so','extern int f(void),g(void),h(void); int call(void){return f()+g()+h();}',
                            deps=(libx,libh))
        b=self.root/'baseline'
        self.rpm(b,'application',{'/usr/lib/app.so':client})
        self.rpm(b,'providers',{'/usr/lib/libx.so.1':libx,'/usr/lib/libh.so.1':libh})
        x2=self.library('libx-next','libx.so.1','int f(void){return 1;}',version='X_2')
        no_h=self.library('libh-no-h','libh.so.1','int other(void){return 3;}')

        def case(label,base,x,h,expected,wants):
            candidate=self.root/label
            self.rpm(candidate,'application',{'/usr/lib/app.so':client})
            files={'/usr/lib/libh.so.1':h}
            if x:
                files['/usr/lib/libx.so.1']=x
            self.rpm(candidate,'providers',files)
            report,result,status=self.run_case(base,candidate,label,expected=expected,workflow=True)
            with (report/'requirement-findings.csv').open(newline='') as stream:
                rows=list(csv.DictReader(stream))
            details={(r['reason_code'],r['symbol'],r['version']) for r in rows}
            self.assertEqual(details,wants)
            self.assertEqual(len(rows),result['repository']['requirements']['finding_count'])
            self.assertGreater(sum(c['satisfied'] for c in status['statistics']['requirements']['by_kind'].values()),0)
            if rows:
                self.assertTrue(all(r['scope']=='AVAILABLE_SET' and r['package_nevra'].startswith('application-') for r in rows))
            return rows

        case('t07-version',b,x2,libh,1,{('VERSION_NODE_UNAVAILABLE','UNKNOWN','X_1'),
              ('VERSIONED_SYMBOL_UNAVAILABLE','f','X_1'),('VERSIONED_SYMBOL_UNAVAILABLE','g','X_1')})
        case('t07-needed',b,None,libh,1,{('NEEDED_SONAME_UNAVAILABLE','UNKNOWN','UNKNOWN'),
              ('VERSION_PROVIDER_UNAVAILABLE','UNKNOWN','X_1'),('VERSIONED_SYMBOL_UNAVAILABLE','f','X_1'),
              ('VERSIONED_SYMBOL_UNAVAILABLE','g','X_1')})
        case('t07-unversioned',b,libx,no_h,1,{('UNVERSIONED_SYMBOL_NOT_IN_CLOSURE','h','UNKNOWN')})
        missing=self.root/'baseline-incomplete-set'
        self.rpm(missing,'application',{'/usr/lib/app.so':client})
        self.rpm(missing,'providers',{'/usr/lib/libh.so.1':libh})
        rows=case('t07-control-fail',missing,None,libh,0,{('ALSO_UNSATISFIED_IN_BASELINE','UNKNOWN','UNKNOWN'),
            ('ALSO_UNSATISFIED_IN_BASELINE','UNKNOWN','X_1'),('ALSO_UNSATISFIED_IN_BASELINE','f','X_1'),
            ('ALSO_UNSATISFIED_IN_BASELINE','g','X_1')})
        self.assertTrue(all(r['status']=='UNKNOWN' and r['severity']=='LOW' for r in rows))
        case('t07-satisfied',b,libx,libh,0,set())

    def test_t08_clang_asan_confound_and_plain_control(self):
        clang=prerequisite('clang','WP1_CLANG')
        if not clang:
            self.blocked('Clang')
        source=('int table[10] = {1}; int keep(void){return 1;}'
                '\n#ifndef REMOVE\nint removed(void){return 2;}\n#endif\n')
        plain=self.library('plain','libp.so.1',source)
        asan=self.library('asan','libp.so.1',source,clang=clang,flags=('-fsanitize=address','-DREMOVE'))
        control=self.library('control','libp.so.1',source.replace('table[10]','table[20]'),clang=clang)
        lhs=self.root/'a'
        self.rpm(lhs,'p',{'/usr/lib/libp.so.1':plain})
        for leaf,binary in (('t08-asan',asan),('t08-control',control)):
            rhs=self.root/leaf
            self.rpm(rhs,'p',{'/usr/lib/libp.so.1':binary})
            report,result,status=self.run_case(lhs,rhs,leaf)
            size=next(f for f in result['findings'] if f['interface']=='table:size')
            if binary==asan:
                self.assertEqual((size['status'],size['severity'],size['reason_code']),
                                 ('UNKNOWN','MEDIUM','INSTRUMENTATION_MISMATCH'))
                self.assertEqual(size['baseline'],40)
                self.assertGreater(size['candidate'],40)
                self.assertEqual(status['comparison_validity'],'CONFOUNDED')
                self.assertGreater(status['statistics']['instrumentation_downgrades']['INSTRUMENTATION_MISMATCH'],0)
                self.assertTrue(any(f['interface'].startswith('__odr_asan') and f['severity']=='INFO' and
                                    f.get('reason_code')=='INSTRUMENTATION_SYMBOL' for f in result['findings']))
                self.assertTrue(any(f['interface']=='removed' and f['status']=='INCOMPATIBLE' for f in result['findings']))
                self.assertTrue((report/'summary.md').read_text().startswith('Comparison confounded'))
                self.assertIn('Comparison confounded',(report/'index.html').read_text())
            else:
                self.assertEqual(status['comparison_validity'],'COMPARABLE')
                self.assertEqual((size['status'],size['reason_code']),('INCOMPATIBLE','DATA_SIZE_INCREASED'))

    def test_t12_split_debug_not_applicable(self):
        if not prerequisite('objcopy'):
            self.blocked('objcopy')
        original=self.library('original','libd.so.1','int d(void){return 4;}')
        split=self.root/'split.debug'
        execute('objcopy','--only-keep-debug',original,split)
        left,right=self.root/'a',self.root/'b'
        for repo in (left,right):
            self.rpm(repo,'debug-demo',{'/usr/lib/debug/demo.debug':split})
        report,result,_=self.run_case(left,right,'t12',expected=0)
        manifest=json.loads((report/'baseline-manifest.json').read_text())
        self.assertEqual(manifest['elf_objects'][0]['elf_runtime_role'],'DEBUG_ONLY')
        self.assertIsNone(result['repository']['baseline']['export_coverage_percent'])
        self.assertFalse(any(f['severity']=='HIGH' for f in result['findings']))
        self.assertEqual(next(u['verification'] for u in result['coverage']['abi']['units'] if
                              u['interface'].endswith(':exports')),'NOT_APPLICABLE')


def runtime(path, soname, *, needed=(), exports=(), **attrs):
    return {'path':path,'package_path':path,'class':'ELF64','machine':'X86','endianness':'little',
            'type':'DYN','complete':True,'export_inventory_complete':True,'resolution_metadata_complete':True,
            'soname':soname,'needed':list(needed),
            'exports':[{'name':name,'type':'OBJECT','size':size,'binding':'GLOBAL','visibility':'DEFAULT'}
                       for name,size in exports],**attrs}


class Boundaries(unittest.TestCase):
    def test_negative_no_cross_arch_or_candidate_reuse(self):
        old = runtime('/left','libx.so.1')
        reused_old = runtime('/paired','libx.so.1')
        shared = runtime('/paired','libx.so.1')
        arm = runtime('/arm','libx.so.1') | {'machine':'ARM','class':'ELF32'}
        pairs = [{'baseline_object':'/left','candidate_object':None,'baseline_package_id':'old','candidate_package_id':None},
                 {'baseline_object':'/paired','candidate_object':'/paired','baseline_package_id':'used','candidate_package_id':'used'},
                 {'baseline_object':None,'candidate_object':'/arm','baseline_package_id':None,'candidate_package_id':'arm'}]
        output,ambiguous=reconcile(pairs,[{'/left':old,'/paired':reused_old},{'/paired':shared,'/arm':arm}])
        self.assertIsNone(output[0]['candidate_object'])
        self.assertEqual(ambiguous,{'/left':['/paired']})

    def test_negative_cycle_provider_conflict_and_consumer_inventory(self):
        a=runtime('/a','a',needed=['b'],exports=[('f',4)])
        b=runtime('/b','b',needed=['a'],exports=[('g',4)])
        obj=runtime('/c',None) | {'resolution_metadata_complete':False}
        providers=Providers([a,b])
        self.assertEqual(providers.evaluate(('ELF64','X86','little'),['b'],('UNVERSIONED_IMPORT',None,None,'f',False)),
                         'SATISFIED')
        summary,rows=check_available_set([{'/c':obj},{}],{'/c':('pkg','pkg-0:1-1.x86_64')},
                                         {'/c':'/c'},[False,True])
        self.assertEqual(summary['finding_count'],1)
        self.assertEqual(rows[0]['reason_code'],'CONSUMER_INVENTORY_INCOMPLETE')
        variant=runtime('/other','a')
        providers=Providers([a,variant])
        key=('ELF64','X86','little')
        self.assertEqual(providers.evaluate(key,['a'],('VERSIONED_IMPORT','a','V1','f',False)),'AMBIGUOUS')
        self.assertEqual(Providers([a]).evaluate(key,['a'],('VERSIONED_IMPORT','a','V1','f',False)),'SATISFIED')
        self.assertEqual(classify(('VERSIONED_IMPORT','a','V1','f',True),'SATISFIED','MISSING',True),
                         ('UNKNOWN','LOW','WEAK_REFERENCE_UNSATISFIED'))
        self.assertEqual(classify(('DT_NEEDED','a',None,None,False),'SATISFIED','MISSING',False),
                         ('UNKNOWN','MEDIUM','REQUIREMENT_INVENTORY_INCOMPLETE'))

    def test_negative_single_pair_instrumentation_in_comparable_run(self):
        left=[runtime(f'/obj{i}',f'lib{i}',exports=[('table',4)]) for i in range(6)]
        right=[obj | {'exports':[obj['exports'][0] | {'size':8}]} for obj in left]
        right[0]=right[0] | {'imports':[{'name':'__asan_init'}]}
        self.assertEqual(comparison_profile(left,right)['comparison_validity'],'COMPARABLE')
        rows=compare_elf({'elf_objects':left},{'elf_objects':right})
        sizes={f['component']:f['reason_code'] for f in rows if f['interface']=='table:size'}
        self.assertEqual(sizes.pop('/obj0'),'INSTRUMENTATION_MISMATCH')
        self.assertEqual(list(sizes.values()),['DATA_SIZE_INCREASED']*5)
