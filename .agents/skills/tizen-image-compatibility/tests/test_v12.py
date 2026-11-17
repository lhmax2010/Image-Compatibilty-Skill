"""v1.2 synthetic correctness, ownership, stage and native-loader regressions."""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
from test_framework import Environment
from test_correctness import obj, symbol
from compat.core import finding, validate_config, InputError, hash_file, read_manifest, validate_package_context
from compat.linker import dependency_checks
from compat.coverage import check, obligation, summarize, coverage_report
from compat.elf import verify_compile_target, collect_elf
from compat.matrix_manifest import plan_expected, reconcile, prepare_sdks
from compat.testing import ASSETS, run_matrix
from compat.images import Image
from compat.packages import collect_package_inventory
from compat.package_analysis import analyze_packages, package_id, Ownership
from compat.report import build_results, generate


def installed(name, files, version='1', arch='armv7l'):
    return dict(name=name,epoch='0',version=version,release='1',arch=arch,files=files,provides=[],requires=[],conflicts=[],obsoletes=[],
                collection_status='COMPLETE',provenance={'kind':'installed_rpmdb','source':'synthetic-test-db'},evidence=[])


def inventory(manifest, packages):
    manifest.update(packages=packages,package_inventory={'status':'COMPLETE','installed_count':len(packages),'source_kind':'installed_rpmdb'},collection_complete=True)
    manifest['filesystem']=[dict(path=p,type='file') for package in packages for p in package['files']]
    return manifest


class LookupHardeningTests(Environment):
    def setup_lookup(self, exports_a=None, exports_b=None):
        c=obj('/bin/app',type='EXEC',needed=['a.so','b.so'],imports=[symbol('f')])
        a=obj('/lib/a.so',type='DYN',exports=exports_a or [symbol('f')]); b=obj('/lib/b.so',type='DYN',exports=exports_b or [symbol('f')])
        m=self.blank(); m.update(elf_objects=[a,b],collection_complete=True,
            loader_environment={'model':'glibc','environment_complete':True,'cache_complete':True,'default_dirs':['/lib'],'symbol_scope':'startup','namespace':'base'})
        return c,a,b,m
    def imported(self,c,m): return [f for f in dependency_checks(m,'baseline consumers on candidate',[c]) if ':import:' in f['interface']][-1]
    def test_multiple_providers_order_is_evidence_not_verification(self):
        c,a,b,m=self.setup_lookup(); f=self.imported(c,m)
        self.assertEqual(f['status'],'UNKNOWN')
        self.assertEqual([x['provider'] for x in f['candidate']['lookup_candidates']],['/lib/a.so','/lib/b.so'])
        c['needed'].reverse(); f=self.imported(c,m)
        self.assertEqual(f['candidate']['provider'],'/lib/b.so'); self.assertEqual(f['status'],'UNKNOWN')
    def test_distinct_versions_wrong_requirement_provider(self):
        c,a,b,m=self.setup_lookup([symbol('f@@V1')],[symbol('f@@V2')]); c['imports']=[dict(symbol('f@V2'),version_file='b.so')]
        b['version_definitions']=[dict(name='V2')]; c['version_requirements']=[dict(name='V2',file='b.so',flags='none')]
        self.assertEqual(self.imported(c,m)['status'],'COMPATIBLE')
        c['version_requirements'][0]['file']='a.so'; c['imports'][0]['version_file']='a.so'
        fs=dependency_checks(m,'baseline consumers on candidate',[c])
        self.assertTrue(any(f['resolution']=='missing_version' and f['status']=='INCOMPATIBLE' for f in fs))
        self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')
    def test_non_scope_and_unsupported_features(self):
        c,a,b,m=self.setup_lookup(); b['exports']=[]; c['needed']=['b.so']
        self.assertEqual(self.imported(c,m)['status'],'INCOMPATIBLE')  # a.so exists but is not loaded
        c['needed']=['a.so']; self.assertEqual(self.imported(c,m)['status'],'COMPATIBLE')
        for setting,value in [('symbol_scope','unknown'),('namespace','plugin-namespace'),('environment_complete',False)]:
            old=m['loader_environment'][setting];m['loader_environment'][setting]=value
            self.assertEqual(self.imported(c,m)['status'],'UNKNOWN');m['loader_environment'][setting]=old
        a['dynamic_flags']=['FLAGS_1:GROUP']; self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')
        a['dynamic_flags']=[];c['type']='DYN';self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')
    def test_weak_unique_ifunc_hidden_and_object_type(self):
        c,a,b,m=self.setup_lookup(); c['needed']=['a.so']
        for export in [symbol('f',kind='IFUNC'),symbol('f',binding='UNIQUE'),dict(symbol('f'),visibility='PROTECTED')]:
            a['exports']=[export]; self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')
        a['exports']=[symbol('f')];c['imports']=[symbol('f',binding='WEAK')]
        self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')
        c['imports']=[symbol('f')];a['exports']=[dict(symbol('f'),visibility='HIDDEN')]
        self.assertEqual(self.imported(c,m)['status'],'INCOMPATIBLE')
        a['type']='REL';self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')
    @unittest.skipUnless(shutil.which('gcc'),'Needs synthetic native compiler')
    def test_native_glibc_weak_first_and_dependency_order(self):
        # Authored native fixtures only. Clean process environment/cwd, not a Tizen image or an OS sandbox.
        for name,value,weak in [('a',11,True),('b',22,False)]:
            src=self.base/(name+'.c');src.write_text(('__attribute__((weak)) ' if weak else '')+f'int f(void){{return {value};}}')
            subprocess.run(['gcc','-shared','-fPIC','-nostdlib',str(src),'-Wl,-soname,'+name+'.so','-o',str(self.base/(name+'.so'))],check=True)
        source=self.base/'main.c';source.write_text('extern int f(void); int main(void){return f();}')
        for order,expected in [(('a','b'),11),(('b','a'),22)]:
            executable=self.base/('app-'+''.join(order))
            subprocess.run(['gcc',str(source),'-Wl,--no-as-needed',*[str(self.base/(n+'.so')) for n in order],'-Wl,-rpath,$ORIGIN','-o',str(executable)],check=True)
            elf=collect_elf(executable,'/app',self.tools,'static')
            if not elf.get('interpreter') or 'ld-linux' not in elf['interpreter']: self.skipTest('Native loader is not glibc ld-linux')
            result=subprocess.run([elf['interpreter'],str(executable)],cwd=self.base,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'},timeout=10,capture_output=True)
            self.assertEqual(result.returncode,expected,result.stderr)
            c,a,b,m=self.setup_lookup([symbol('f',binding='WEAK')],[symbol('f')]);c['needed']=[n+'.so' for n in order]
            self.assertEqual(self.imported(c,m)['candidate']['provider'],'/lib/'+order[0]+'.so')
            self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')


class CompletenessTests(Environment):
    def test_confirmed_failure_and_unknown_are_independent(self):
        u=obligation('component',[check('broken','INCOMPATIBLE'),check('not checked'),check('unsupported',executed=True)])
        self.assertEqual((u['status'],u['verification']),('INCOMPATIBLE','PARTIAL'))
        c=summarize([u]);self.assertEqual(c['confirmed_incompatible'],1);self.assertEqual(c['coverage_percent'],0)
        self.assertEqual(c['partially_verified'],1)
    def test_required_ids_deduplication_and_denominators(self):
        f=finding('abi','x','x',1,None,'INCOMPATIBLE')
        u=obligation('x',[check('required','COMPATIBLE')],[f]*100)
        self.assertEqual(len(u['finding_ids']),1)
        with self.assertRaises(ValueError): obligation('x',[check('x'),check('x')])
        na=obligation('not applicable',[check('applicability','NOT_APPLICABLE')])
        missing=obligation('unknown inventory',[check('inventory')])
        c=summarize([u,na,missing]);self.assertEqual((c['applicable'],c['not_applicable'],c['coverage_percent']),(2,1,50))
        self.assertIsNone(summarize([na])['coverage_percent'])
    def test_gate_reasons_separate_failure_and_partial_coverage(self):
        a,b=self.blank(),self.blank();a['elf_objects']=[obj('/app',needed=['x'],imports=[symbol('f')])]
        fs=[finding('linking','/app','baseline consumers on candidate:DT_NEEDED:x','x',None,'INCOMPATIBLE','HIGH')]
        fs[0].update(check_id='DT_NEEDED:x',root_consumer='/app')
        self.config['ci']['minimum_coverage']={'linking':100}
        cov,gate=coverage_report(a,b,fs,[],[],self.config)
        self.assertEqual(cov['linking']['confirmed_incompatible'],1)
        self.assertEqual(cov['linking']['completely_verified'],0)
        self.assertEqual(gate['compatibility_status'],'FAIL');self.assertEqual(gate['coverage_status'],'FAIL')


class ExpectedManifestTests(Environment):
    def sample(self):
        e=dict(id='E1',name='p',compiler='gcc',kind='runtime',destination_image='candidate',required_stages=['deployment','execution','native_reference','behavior'],expected_artifact=None)
        t=dict(id='E1',name='p',compiler='gcc',image='candidate',kind='runtime',status='COMPATIBLE',deployment_status='SUCCESS',execution_status='SUCCESS',native_reference_valid=True,behavior_status='COMPATIBLE',evidence=[])
        cell=dict(compiler='gcc',image='candidate')
        return e,t,cell
    def test_exact_sets_reject_duplicates_missing_and_unexpected(self):
        for change in ('none','missing','duplicate','unexpected'):
            e,t,c=self.sample();tests=[t]
            if change=='missing':tests=[]
            if change=='duplicate':tests=[t,t]
            if change=='unexpected':tests=[t,dict(t,id='UNRELATED')]
            audit=reconcile([e],tests,[c])
            self.assertEqual(c['status'],'COMPATIBLE' if change=='none' else 'UNKNOWN')
            if change!='none': self.assertTrue(any(audit.values()))
    def test_failure_survives_partial_receipt_and_reference(self):
        e,t,c=self.sample();t.update(execution_status='UNKNOWN',behavior_status='INCOMPATIBLE',status='INCOMPATIBLE')
        reconcile([e],[t],[c]);self.assertEqual((c['status'],c['verification']),('INCOMPATIBLE','PARTIAL'))
        e,t,c=self.sample();t['native_reference_valid']=False
        reconcile([e],[t],[c]);self.assertEqual(c['status'],'UNKNOWN')
    def test_artifact_hash_mismatch(self):
        e,t,c=self.sample();e.update(compiler='custom',required_stages=['artifact']);t.update(compiler='custom',expected_artifact_sha256='a',receipt_sha256='b');c['compiler']='custom'
        reconcile([e],[t],[c]);self.assertEqual(c['status'],'UNKNOWN')
        e,t,c=self.sample();e.update(compiler='custom',required_stages=['artifact']);t.update(compiler='custom',expected_artifact_sha256='a',receipt_sha256='a');c['compiler']='custom'
        reconcile([e],[t],[c]);self.assertEqual(c['status'],'COMPATIBLE')
    def test_build_target_abi_is_mandatory_on_both_destinations(self):
        build=dict(id='BUILD',compiler='gcc',name='p',kind='build',destination_image='baseline',required_stages=['target_abi','compilation','linking'],expected_artifact='build/p.bin')
        actual=dict(id='BUILD',compiler='gcc',name='p',image='baseline',kind='compile',success=True,status='COMPATIBLE',artifact_path='build/p.bin',artifact_sha256='frozen',target_abi_verification={'status':'COMPATIBLE'},evidence=[])
        e,t,cell=self.sample();e['required_stages']+=['compilation','linking','artifact'];e['expected_artifact']='build/p.bin';t['receipt_sha256']='frozen'
        reconcile([build,e],[actual,t],[cell]);self.assertEqual(cell['status'],'COMPATIBLE')
        actual['target_abi_verification']['status']='UNKNOWN'
        reconcile([build,e],[actual,t],[cell]);self.assertEqual(cell['status'],'UNKNOWN');self.assertEqual(cell['verification'],'PARTIAL')
    def test_plan_deterministic_and_declares_all_stages_before_execution(self):
        self.config['cross_compilation']['builds']={'gcc':dict(sdk='candidate',reference_image='candidate',provenance='swapped')}
        a,b=self.blank(),self.blank()
        first=plan_expected((a,b),self.tools,ASSETS); second=plan_expected((a,b),self.tools,ASSETS)
        self.assertEqual(first,second);self.assertEqual(len({e['id'] for e in first}),len(first))
        for e in first:
            if e['compiler']=='gcc':self.assertEqual(e['reference_image'],'candidate')
            if e['kind']=='runtime':self.assertTrue(set(('compilation','linking','artifact','native_reference','behavior')) <= set(e['required_stages']))
        self.assertFalse(self.tools.records)
    def test_static_run_keeps_missing_tests_and_writes_plan(self):
        roots=[]
        for label in ('baseline','candidate'):
            p=self.base/label;p.mkdir();roots.append(Image(p,self.workspace,self.tools,label))
        a,b=self.blank(),self.blank();tests,matrix,_=run_matrix((a,b),tuple(roots),self.tools,'static')
        self.assertFalse(tests);self.assertTrue((self.output/'expected-tests.json').is_file())
        self.assertTrue(all(c['missing_test_ids'] for c in matrix))
        self.assertTrue(all(c['verification']=='NOT_EXECUTED' for c in matrix))

    def test_missing_sdk_header_and_wrong_inventory_association(self):
        roots=[]
        for label in ('baseline','candidate'):
            root=self.base/label;(root/'usr/include').mkdir(parents=True);roots.append(root)
        (roots[0]/'usr/include/removed.h').write_text('int f(void);')
        self.config['cross_compilation']['sysroots']={k:str(v) for k,v in zip(('baseline','candidate'),roots)}
        wrong=inventory(self.blank(),[installed('devel',['/usr/include/removed.h'])]);wrong['image']['source']=str(self.base/'wrong')
        path=self.base/'wrong.json';path.write_text(json.dumps(wrong));self.config['cross_compilation']['sdk_package_manifests']['baseline']=str(path)
        a,b=self.blank(),self.blank();prepare_sdks((a,b),self.tools)
        self.assertNotIn('sdk_package_manifest',a);self.assertIn('does not match',a['sdk_ownership_reason'])
        expected=plan_expected((a,b),self.tools,ASSETS)
        candidate=[e for e in expected if e['name']=='header:/usr/include/removed.h' and e['destination_image']=='candidate']
        self.assertEqual(len(candidate),4);self.assertTrue(all(e['source_identity']['sha256'] is None for e in candidate))


class ManifestMigrationTests(Environment):
    def test_schema_11_success_downgraded_failure_preserved(self):
        m=self.blank();m['schema_version']='1.1';m['elf_objects']=[obj('/app')]
        m['test_results']=[dict(id='a',image='baseline',compiler='gcc',kind='runtime',status='COMPATIBLE'),dict(id='b',image='candidate',compiler='gcc',kind='runtime',status='INCOMPATIBLE')]
        p=self.base/'old.json';p.write_text(json.dumps(m));result=read_manifest(p)
        self.assertEqual([t['status'] for t in result['test_results']],['UNKNOWN','INCOMPATIBLE'])
        self.assertFalse(result['elf_objects'][0]['resolution_metadata_complete']);self.assertTrue(result['migration_notes'])
    def test_archive_cannot_claim_complete_installed_inventory(self):
        m=inventory(self.blank(),[installed('x',[])]);m['packages'][0]['provenance']['kind']='rpm_archive'
        with self.assertRaises(ValueError):validate_package_context(m)


class TargetAbiTests(Environment):
    def arm(self,path='/probe.o',pcs='hard',**kw):
        return dict(path=path,complete=True,machine='ARM',type='REL',**{'class':'ELF32'},endianness="2's complement, little endian",arm_abi=dict(eabi=5,float=pcs,cpu_arch='v7',**kw))
    def test_primary_config_ignores_unrelated_missing_attributes_but_reports_mixed(self):
        elf=self.arm();m=self.blank();m['elf_objects']=[dict(self.arm('/lib/loader'),type='DYN'),dict(self.arm('/unrelated'),type='DYN',arm_abi={}),dict(self.arm('/soft',pcs='soft'),type='DYN')]
        self.config['cross_compilation']['target_abis']['baseline']=dict(machine='ARM',**{'class':'ELF32'},endianness=elf['endianness'],eabi=5,float='hard',cpu_arch='v7',provenance='SDK toolchain')
        self.config['cross_compilation']['runtime_objects']['baseline']=['/lib/loader']
        result=verify_compile_target(elf,m,self.config,'baseline');self.assertEqual(result['status'],'COMPATIBLE')
        self.assertEqual({x['status'] for x in result['other_objects']},{'UNKNOWN','INCOMPATIBLE'})
        m['elf_objects'][0]['arm_abi']['float']='soft';self.assertEqual(verify_compile_target(elf,m,self.config,'baseline')['status'],'INCOMPATIBLE')
    def test_no_primary_unknown_wrong_object_and_aarch64(self):
        m=self.blank();self.assertEqual(verify_compile_target(self.arm(),m,self.config,'baseline')['status'],'UNKNOWN')
        a=obj('/loader',type='DYN');a['machine']='AArch64';m['elf_objects']=[a]
        probe=dict(a,type='REL');self.assertEqual(verify_compile_target(probe,m,self.config,'baseline')['status'],'COMPATIBLE')
        self.assertEqual(verify_compile_target(a,m,self.config,'baseline')['status'],'INCOMPATIBLE')
    @unittest.skipUnless(os.environ.get('COMPAT_TEST_CLANG'),'Needs real Clang')
    def test_real_hard_softfp_and_soft_pcs(self):
        source=self.base/'float.c';source.write_text('double f(double x){return x+1.;}')
        collected={}
        for mode in ('hard','softfp','soft'):
            out=self.base/(mode+'.o')
            r=self.tools.run([os.environ['COMPAT_TEST_CLANG'],'--target=armv7-linux-gnueabi','-mfpu=vfpv3','-mfloat-abi='+mode,'-c',str(source),'-o',str(out)])
            self.assertEqual(r['returncode'],0,r['stderr'])
            e=collect_elf(out,out.name,self.tools,'quick');macros=self.tools.run([os.environ['COMPAT_TEST_CLANG'],'--target=armv7-linux-gnueabi','-mfloat-abi='+mode,'-dM','-E',str(source)])['stdout']
            if not e['arm_abi']['float']:e['arm_abi']['float']='hard' if '#define __ARM_PCS_VFP ' in macros else 'soft' if '#define __ARM_PCS ' in macros else None
            collected[mode]=e['arm_abi']['float']
        self.assertEqual(collected,{'hard':'hard','softfp':'soft','soft':'soft'})


class PackageAnalysisTests(Environment):
    def result(self,a,b,fs=()):
        cov,_=coverage_report(a,b,list(fs),[],[],self.config)
        return analyze_packages(a,b,list(fs),cov)
    def test_missing_inventory_is_unknown_not_zero_and_archives_not_ownership(self):
        a,b=self.blank(),self.blank();a['packages']=[dict(installed('archive',['/lib/x.so']),provenance={'kind':'rpm_archive'})]
        summary,rows=self.result(a,b)
        self.assertIsNone(summary['baseline_package_count']);self.assertFalse(rows)
        self.assertFalse(Ownership(a).lookup('/lib/x.so')['owners'])
    def test_package_break_preserved_with_layout_and_api_gaps(self):
        a=inventory(self.blank(),[installed('libx',['/lib/x.so'])]);b=inventory(self.blank(),[installed('libx',['/lib/x.so'],version='2')])
        a['elf_objects']=[obj('/lib/x.so',type='DYN',exports=[symbol('removed')])];b['elf_objects']=[obj('/lib/x.so',type='DYN')]
        f=finding('abi','/lib/x.so','removed',symbol('removed'),None,'INCOMPATIBLE')
        summary,rows=self.result(a,b,[f]);row=rows[0]
        self.assertEqual(row['abi']['status'],'INCOMPATIBLE');self.assertEqual(row['abi']['verification'],'PARTIAL')
        self.assertEqual((row['overall'],row['verification']),('INCOMPATIBLE','PARTIAL'))
        self.assertEqual(row['api']['status'],'UNKNOWN');self.assertIn(f['id'],row['finding_ids'])
    def test_multiple_versions_unresolved_not_overwritten_and_additions(self):
        a=inventory(self.blank(),[installed('x',[],version='1'),installed('x',[],version='2')]);b=inventory(self.blank(),[installed('x',[],version='3'),installed('added',[])])
        summary,rows=self.result(a,b)
        self.assertEqual(len(rows),2);self.assertEqual(len(summary['unresolved_matches']),1)
        self.assertEqual(len(summary['candidate_only']),1)
        self.assertTrue(all(r['availability']['status']=='UNKNOWN' for r in rows))
    def test_missing_candidate_inventory_not_baseline_only(self):
        a=inventory(self.blank(),[installed('x',[])]);summary,_=self.result(a,self.blank())
        self.assertFalse(summary['baseline_only']);self.assertTrue(summary['unresolved_matches'])
    def test_usrmerge_symlink_and_multiple_owners(self):
        a=inventory(self.blank(),[installed('x',['/usr/lib/x.so']),installed('link',['/lib/alias.so'])])
        a['filesystem'] += [dict(path='/lib',type='symlink',resolved='/usr/lib'),dict(path='/lib/alias.so',type='symlink',resolved='/usr/lib/x.so')]
        ownership=Ownership(a)
        self.assertEqual(ownership.lookup('/lib/x.so')['owners'],[package_id(a['packages'][0])])
        self.assertEqual(ownership.lookup('/lib/alias.so')['owners'],[package_id(a['packages'][1])])
        self.assertEqual(ownership.lookup('/lib/alias.so')['target_owners'],[package_id(a['packages'][0])])
        a['packages'].append(installed('another',['/usr/lib/x.so']))
        self.assertEqual(Ownership(a).lookup('/usr/lib/x.so')['status'],'UNKNOWN')
    def test_consumer_provider_roles_and_unassigned_files(self):
        a=inventory(self.blank(),[installed('app',['/bin/app']),installed('lib',['/lib/x.so'])]);b=copy.deepcopy(a)
        a['elf_objects']=[obj('/bin/app',type='EXEC',needed=['x.so']),obj('/lib/x.so',type='DYN')];b['elf_objects']=copy.deepcopy(a['elf_objects'])
        f=finding('linking','/bin/app','baseline consumers on candidate:import:f','f',None,'INCOMPATIBLE');f.update(consumer_path='/bin/app',consumer_image='baseline',provider_path='/lib/x.so',root_consumer='/bin/app',check_id='import:f')
        unknown=finding('abi','/opt/unowned.so','export',1,None,'INCOMPATIBLE')
        summary,rows=self.result(a,b,[f,unknown]);by_name={r['name']:r for r in rows}
        self.assertEqual(f['package_ownership']['consumer']['owners'],[package_id(a['packages'][0])])
        self.assertEqual(f['package_ownership']['candidate_provider']['owners'],[package_id(b['packages'][1])])
        self.assertEqual(by_name['app']['linking']['status'],'INCOMPATIBLE');self.assertNotEqual(by_name['lib']['linking']['status'],'INCOMPATIBLE')
        self.assertIn(unknown['id'],summary['unassigned_finding_ids'])
    def test_transitive_break_reaches_root_package(self):
        a=inventory(self.blank(),[installed('app',['/bin/app']),installed('middle',['/lib/middle.so'])]);b=copy.deepcopy(a)
        a['elf_objects']=[obj('/bin/app',type='EXEC',needed=['middle.so'])]
        b['elf_objects']=[obj('/lib/middle.so',type='DYN',needed=['missing.so'])]
        b['loader_environment']=dict(model='glibc',environment_complete=True,cache_complete=True,default_dirs=['/lib'],symbol_scope='startup',namespace='base')
        fs=dependency_checks(b,'baseline consumers on candidate',a['elf_objects'])
        breaks=[f for f in fs if f['component']=='/lib/middle.so' and f['status']=='INCOMPATIBLE']
        self.assertTrue(breaks)
        summary,rows=self.result(a,b,fs)
        app=next(r for r in rows if r['name']=='app')
        self.assertEqual(app['linking']['status'],'INCOMPATIBLE')
        self.assertTrue(set(f['id'] for f in breaks)<=set(app['finding_ids']))
        self.assertEqual(breaks[0]['package_ownership']['root_consumer']['owners'],[package_id(a['packages'][0])])
    def test_data_only_applicability_and_runtime_api_unknown(self):
        a=inventory(self.blank(),[installed('data',['/usr/share/data'])]);b=copy.deepcopy(a)
        _,rows=self.result(a,b);self.assertEqual(rows[0]['abi']['status'],'NOT_APPLICABLE');self.assertEqual(rows[0]['api']['status'],'NOT_APPLICABLE')
        a['collection_complete']=False;_,rows=self.result(a,b);self.assertEqual(rows[0]['abi']['status'],'UNKNOWN')
    def test_sdk_unassigned_not_guessed_from_runtime_path(self):
        a=inventory(self.blank(),[installed('runtime',['/usr/include/a.h'])]);b=copy.deepcopy(a)
        a['sdk_headers']=[dict(path='/usr/include/a.h')]
        summary,_=self.result(a,b)
        self.assertTrue(any(x.get('scope')=='sdk' for x in summary['unassigned_interfaces']))
    def test_all_package_report_formats_and_escaping(self):
        a=inventory(self.blank(),[installed('=synthetic<script>',[]) ]);b=copy.deepcopy(a)
        result=build_results(a,b,[],[],[],self.config);generate(self.output,a,b,result,self.config)
        self.assertEqual(len(result['package_results']),1)
        with (self.output/'packages.csv').open() as stream:row=list(csv.DictReader(stream))[0]
        self.assertTrue(row['name'].startswith("'="))
        html=(self.output/'index.html').read_text();self.assertIn('package-filter',html);self.assertNotIn('=synthetic<script>',html)
        self.assertIn('Package compatibility',(self.output/'summary.md').read_text())
    def test_database_unavailable_not_empty_installed_inventory(self):
        root=self.base/'root';(root/'var/lib/rpm').mkdir(parents=True)
        image=Image(root,self.workspace,self.tools,'synthetic')
        packages,archives,meta,limits=collect_package_inventory(image,self.tools,self.workspace)
        self.assertFalse(packages);self.assertIsNone(meta['installed_count']);self.assertEqual(meta['status'],'UNKNOWN')
        self.assertTrue(limits)


class PackageIntegrationTests(Environment):
    @unittest.skipUnless(shutil.which('rpm') and shutil.which('rpmbuild'), 'Needs RPM tools')
    def test_actual_installed_db_and_archive_remain_separate(self):
        spec=self.base/'fixture.spec'; rpms=[]
        for ver in ('1','2'):
            spec.write_text(f"""Name: v12-synthetic-data
Version: {ver}
Release: 1
Summary: Own synthetic RPM fixture
License: MIT
BuildArch: noarch
%description
Synthetic package; never runs target payloads.
%install
mkdir -p %{{buildroot}}/usr/share/v12-test
printf data > %{{buildroot}}/usr/share/v12-test/data
%files
/usr/share/v12-test/data
""")
            r=subprocess.run(['rpmbuild','--define','_topdir '+str(self.base/'rpmbuild'),'-bb',str(spec)],capture_output=True,text=True,timeout=60)
            self.assertEqual(r.returncode,0,r.stderr)
            rpms.append(next((self.base/'rpmbuild/RPMS').rglob('*-'+ver+'-1.*.rpm')))
        root=self.base/'root';db=root/'var/lib/rpm';db.mkdir(parents=True)
        subprocess.run(['rpm','--dbpath',str(db),'--initdb'],check=True,capture_output=True)
        r=subprocess.run(['rpm','--dbpath',str(db),'-i','--justdb','--nodeps','--noscripts','--notriggers',str(rpms[0])],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        shutil.copyfile(rpms[1],root/'available.rpm')
        queried=subprocess.run(['rpm','--dbpath',str(db),'-qa','--qf','%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n'],check=True,capture_output=True,text=True).stdout.splitlines()
        owned_files=subprocess.run(['rpm','--dbpath',str(db),'-qal'],check=True,capture_output=True,text=True).stdout.splitlines()
        before={p.name:hash_file(p) for p in db.iterdir() if p.is_file()}
        image=Image(root,self.workspace,self.tools,'synthetic')
        records,archives,meta,limits=collect_package_inventory(image,self.tools,self.workspace)
        self.assertFalse(limits,limits);self.assertEqual(meta['installed_count'],1)
        self.assertEqual(meta['installed_count'],len(queried));self.assertEqual(len(records),len(queried))
        self.assertEqual([p['name']+'-'+p['version']+'-'+p['release']+'.'+p['arch'] for p in records],queried)
        self.assertEqual(records[0]['files'],sorted(owned_files))
        self.assertEqual(records[0]['version'],'1');self.assertEqual(archives[0]['version'],'2')
        self.assertEqual(records[0]['provenance']['kind'],'installed_rpmdb');self.assertEqual(archives[0]['provenance']['kind'],'rpm_archive')
        self.assertEqual(before,{p.name:hash_file(p) for p in db.iterdir() if p.is_file()})
    @unittest.skipUnless(shutil.which('rpm'), 'Needs RPM discovery')
    def test_full_rpm_evidence_beyond_stdout_preview(self):
        root=self.base/'root';db=root/'var/lib/rpm';db.mkdir(parents=True);(db/'rpmdb.sqlite').write_text('mock database')
        raw=self.output/'evidence/large-rpm.txt';raw.parent.mkdir(exist_ok=True)
        with raw.open('w') as stream:
            for i in range(1000):
                stream.write('<rpmHeader><rpmTag name="Name"><string>p'+str(i)+'</string></rpmTag><rpmTag name="Arch"><string>noarch</string></rpmTag><rpmTag name="Description"><string>'+('x'*18000)+'</string></rpmTag></rpmHeader>')
        self.assertGreater(raw.stat().st_size,16*1024*1024)
        response=dict(returncode=0,stdout='truncated preview',stdout_truncated=True,stderr='',stdout_evidence='evidence/large-rpm.txt',stderr_evidence='evidence/empty.txt',argv=['mock-rpm'])
        image=Image(root,self.workspace,self.tools,'synthetic')
        with patch.object(self.tools,'run',return_value=response):
            records,_,meta,limits=collect_package_inventory(image,self.tools,self.workspace)
        self.assertFalse(limits);self.assertEqual(len(records),1000);self.assertEqual(meta['installed_count'],1000)
        with raw.open('a') as stream:stream.write('<rpmHeader>')
        with patch.object(self.tools,'run',return_value=response):
            records,_,meta,limits=collect_package_inventory(image,self.tools,self.workspace)
        self.assertIsNone(meta['installed_count']);self.assertEqual(meta['status'],'UNKNOWN');self.assertTrue(limits)
    def test_explicit_sdk_package_ownership_retained(self):
        a,b=self.blank(),self.blank()
        sdk=inventory(self.blank(),[installed('api-devel',['/usr/include/api.h'])]);sdk['public_headers']=[dict(path='/usr/include/api.h')]
        a['sdk_package_manifest']=sdk;b['sdk_package_manifest']=copy.deepcopy(sdk)
        f=finding('headers','header:/usr/include/api.h','gcc','compiles','error','INCOMPATIBLE','HIGH')
        cov,_=coverage_report(a,b,[f],[],[],self.config)
        summary,rows=analyze_packages(a,b,[f],cov)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['scope'],'sdk')
        self.assertEqual(rows[0]['api']['status'],'INCOMPATIBLE')
        self.assertEqual(f['package_ownership']['consumer']['owners'],[package_id(sdk['packages'][0],'sdk')])
    def test_duplicate_exact_nevra_remains_ambiguous(self):
        record=installed('x',['/x'])
        a=inventory(self.blank(),[record,copy.deepcopy(record)]);b=inventory(self.blank(),[record])
        owner=Ownership(a);self.assertEqual(len(owner.records),2)
        self.assertEqual(owner.lookup('/x')['status'],'UNKNOWN')
        cov,_=coverage_report(a,b,[],[],[],self.config);summary,rows=analyze_packages(a,b,[],cov)
        self.assertEqual(len(rows),2);self.assertEqual(len(summary['unresolved_matches']),1)
    def test_indexed_many_packages_have_complete_machine_records(self):
        a,b=self.blank(),self.blank()
        packages=[installed('data-'+str(n),['/usr/share/data-'+str(n)]) for n in range(2000)]
        inventory(a,packages);inventory(b,copy.deepcopy(packages))
        result=build_results(a,b,[],[],[],self.config)
        self.assertEqual(len(result['package_results']),2000)
        self.assertEqual(len(result['package_inventory']['matched_packages']),2000)
        self.assertTrue(all(r['abi']['status']=='NOT_APPLICABLE' for r in result['package_results']))


if __name__=='__main__':unittest.main()
