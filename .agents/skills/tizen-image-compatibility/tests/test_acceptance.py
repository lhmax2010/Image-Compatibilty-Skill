"""Missing v1.2 acceptance checks against production entry points."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from test_framework import Environment
from test_correctness import obj, symbol
from test_v12 import installed, inventory
from compat.core import read_manifest, InputError, finding, write_json, hash_file
from compat.compare import compare_elf, finalize
from compat.linker import dependency_checks
from compat.package_analysis import Ownership, package_id
from compat.report import build_results, generate
from compat.images import Image
from compat.testing import run_matrix
from compat.coverage import check
from compat.matrix_manifest import reconcile
from tizen_compat import main
sys.path.insert(0, str(Path(__file__).parent / 'review'))
from benchmark_v12 import fixture, verify_reports, budget_failures


class AcceptanceTests(Environment):
    def test_count_reconciliation_rejects_mismatch_and_preserves_unknown(self):
        m=inventory(self.blank(),[installed('a',['/a'])]);m['schema_version']='1.2'
        path=self.base/'manifest.json';write_json(path,m)
        self.assertEqual(read_manifest(path)['package_inventory']['installed_count'],1)
        m['package_inventory']['installed_count']=2;write_json(path,m)
        with self.assertRaises(InputError):read_manifest(path)
        owner=Ownership(m)
        self.assertFalse(owner.reconciliation['consistent']);self.assertEqual(owner.inventory['status'],'PARTIAL')
        self.assertIsNone(owner.inventory['installed_count']);self.assertEqual(owner.lookup('/a')['status'],'UNKNOWN')
        m['package_inventory']={'status':'UNKNOWN','installed_count':None}
        self.assertIsNone(Ownership(m).reconciliation['consistent'])

    def test_rename_split_removed_added_and_architecture_are_distinct_clues(self):
        a=inventory(self.blank(),[installed('original',['/lib/a.so','/lib/b.so'])])
        a['elf_objects']=[obj('/lib/a.so',type='DYN'),obj('/lib/b.so',type='DYN')]
        for names,expected in [(['renamed'],'possible_rename_or_replacement'),(['part-a','part-b'],'possible_split'),([],None)]:
            ps=[installed(names[0],['/lib/a.so','/lib/b.so'])] if len(names)==1 else [installed(n,[p]) for n,p in zip(names,['/lib/a.so','/lib/b.so'])]
            b=inventory(self.blank(),ps+[installed('addition',['/extra'])]);b['elf_objects']=copy.deepcopy(a['elf_objects'])
            result=build_results(a,b,[],[],[],self.config);row=result['package_results'][0];inv=result['package_inventory']
            self.assertEqual(row['match_status'],'baseline_only');self.assertEqual(row['availability']['status'],'UNKNOWN')
            self.assertEqual(row['replacement_hint']['kind'] if row['replacement_hint'] else None,expected)
            self.assertEqual(len(inv['candidate_assessments']),len(ps)+1)
            self.assertTrue(all(r['match_status']=='candidate_only' for r in inv['candidate_assessments']))
            if row['replacement_hint']:self.assertEqual(row['replacement_hint']['status'],'UNKNOWN')
        b=inventory(self.blank(),[installed('original',['/lib/a.so'],arch='aarch64')])
        result=build_results(a,b,[],[],[],self.config)
        self.assertFalse(result['package_inventory']['matched_packages']);self.assertIsNone(result['package_results'][0]['replacement_hint'])

    def test_sdk_elf_does_not_borrow_same_path_runtime_abi_evidence(self):
        a=inventory(self.blank(),[installed('runtime',['/lib/a.so'])]);b=copy.deepcopy(a)
        a['elf_objects']=[obj('/lib/a.so',type='DYN')];b['elf_objects']=copy.deepcopy(a['elf_objects'])
        sdk=inventory(self.blank(),[installed('sdk-devel',['/lib/a.so'])]);sdk['elf_objects']=[obj('/lib/a.so',type='DYN',exports=[symbol('sdk_only')])]
        a['sdk_package_manifest']=sdk;b['sdk_package_manifest']=copy.deepcopy(sdk)
        fs=[finding('abi','/lib/a.so','DWARF type/layout ABI','same','same','COMPATIBLE')]
        self.config['analysis']['modes']=['abi']
        rows=build_results(a,b,fs,[],[],self.config)['package_results']
        self.assertEqual(next(r for r in rows if r['scope']=='runtime')['abi']['status'],'COMPATIBLE')
        self.assertEqual(next(r for r in rows if r['scope']=='sdk')['abi']['status'],'UNKNOWN')

    def test_data_only_overall_is_not_a_compatibility_pass(self):
        a=inventory(self.blank(),[installed('data',['/usr/share/data'])]);b=copy.deepcopy(a)
        row=build_results(a,b,[],[],[],self.config)['package_results'][0]
        self.assertEqual((row['overall'],row['verification']),('NOT_APPLICABLE','NOT_APPLICABLE'))
        a['collection_complete']=False
        self.assertEqual(build_results(a,b,[],[],[],self.config)['package_results'][0]['abi']['status'],'UNKNOWN')

    def test_runtime_only_break_keeps_api_unknown(self):
        a=inventory(self.blank(),[installed('library',['/lib/a.so'])]);b=copy.deepcopy(a)
        a['elf_objects']=[obj('/lib/a.so',type='DYN',exports=[symbol('removed')])]
        b['elf_objects']=[obj('/lib/a.so',type='DYN')]
        fs=finalize(compare_elf(a,b),self.config);result=build_results(a,b,fs,[],[],self.config)
        row=result['package_results'][0]
        self.assertEqual((row['abi']['status'],row['api']['status'],row['overall']),('INCOMPATIBLE','UNKNOWN','INCOMPATIBLE'))
        self.assertEqual(row['verification'],'PARTIAL');self.assertEqual(result['status'],'INCOMPATIBLE')

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'),'Needs real synthetic ELF tools')
    def test_real_missing_public_library_package_and_direction(self):
        from compat.elf import collect_elf
        src=self.base/'lib.c';src.write_text('int api(void){return 1;}')
        lib=self.base/'libpublic.so'
        subprocess.run(['gcc','-shared','-fPIC',str(src),'-o',str(lib)],check=True)
        elf=collect_elf(lib,'/lib/libpublic.so',self.tools,'static')
        a=inventory(self.blank(),[installed('public',['/lib/libpublic.so'])]);b=inventory(self.blank(),[])
        a['elf_objects']=[elf];before=hash_file(lib)
        fs=finalize(compare_elf(a,b),self.config);result=build_results(a,b,fs,[],[],self.config)
        # Path removal alone can be a relocation/replacement; retain its owning package and gap.
        self.assertEqual(result['package_results'][0]['abi']['status'],'UNKNOWN')
        self.assertEqual(result['package_results'][0]['availability']['status'],'UNKNOWN')
        present=build_results(a,a,finalize(compare_elf(a,a),self.config),[],[],self.config)
        self.assertEqual(present['package_results'][0]['availability']['status'],'COMPATIBLE')
        b['loader_environment']=dict(model='glibc',environment_complete=True,cache_complete=True,default_dirs=['/lib'],symbol_scope='startup',namespace='base')
        consumer=obj('/bin/consumer',type='EXEC',needed=['libpublic.so'])
        self.assertTrue(any(f['status']=='INCOMPATIBLE' for f in dependency_checks(b,'baseline consumers on candidate',[consumer])))
        self.assertTrue(result['package_results'][0]['missing_interfaces']);self.assertEqual(hash_file(lib),before)
        reverse=compare_elf(b,a)
        self.assertFalse(any(f['status']=='INCOMPATIBLE' for f in reverse))

    def test_two_root_consumers_share_one_transitive_finding(self):
        a=inventory(self.blank(),[installed('app-a',['/bin/a']),installed('app-b',['/bin/b']),installed('middle',['/lib/m.so'])]);b=copy.deepcopy(a)
        a['elf_objects']=[obj(p,type='EXEC',needed=['m.so']) for p in ('/bin/a','/bin/b')]
        b['elf_objects']=[obj('/lib/m.so',type='DYN',needed=['missing.so'])]
        b['loader_environment']=dict(model='glibc',environment_complete=True,cache_complete=True,default_dirs=['/lib'],symbol_scope='startup',namespace='base')
        fs=finalize(dependency_checks(b,'baseline consumers on candidate',a['elf_objects']),self.config)
        broken=[f for f in fs if f['component']=='/lib/m.so' and f['status']=='INCOMPATIBLE']
        row, = broken
        self.assertEqual(row['roots'], {'count':2, 'examples':['/bin/a','/bin/b']})
        result=build_results(a,b,fs,[],[],self.config)
        for p in result['package_results']:
            if p['name'].startswith('app-'):
                self.assertEqual(p['linking']['status'],'INCOMPATIBLE')
                self.assertIn(row['id'], p['linking']['finding_ids'])
        edges=result['package_inventory']['provider_consumers']
        provider=package_id(b['packages'][2])
        self.assertEqual({e['consumer_package'] for e in edges if e['provider_package']==provider}, {package_id(p) for p in a['packages'][:2]})

    def test_duplicate_findings_are_audited_and_conflicts_rejected(self):
        f=finding('abi','/lib/a','x',1,None,'INCOMPATIBLE')
        fs=finalize([f,copy.deepcopy(f)],self.config)
        self.assertEqual(len(fs),1);self.assertEqual(fs[0]['occurrences'],2)
        result=build_results(self.blank(),self.blank(),fs,[],[],self.config)
        self.assertEqual(result['finding_integrity']['source_occurrences'],2)
        with self.assertRaises(ValueError):finalize([f,dict(f,status='COMPATIBLE')],self.config)
        with self.assertRaises(ValueError):build_results(self.blank(),self.blank(),[f,f],[],[],self.config)

    def test_v12_manifest_without_expected_metadata_cannot_reuse_pass(self):
        a,b=self.blank(),self.blank()
        for m in (a,b):m['schema_version']='1.2'
        a['test_results']=[dict(id='old',compiler='gcc',image='baseline',kind='runtime',status='COMPATIBLE')]
        a['cross_matrix']=[dict(compiler='gcc',image='baseline',header_status='COMPATIBLE',runtime_status='COMPATIBLE',status='COMPATIBLE',required_checks=[check('old','COMPATIBLE')])]
        left,right=self.base/'a.json',self.base/'b.json';write_json(left,a);write_json(right,b)
        out=self.base/'reuse'
        code=main(['--baseline-manifest',str(left),'--candidate-manifest',str(right),'--output',str(out),'--strict'])
        self.assertEqual(code,1)
        result=json.loads((out/'results.json').read_text())
        self.assertEqual(result['matrix'][0]['status'],'UNKNOWN');self.assertEqual(result['tests'][0]['status'],'UNKNOWN')
        self.assertEqual(result['coverage']['runtime']['completely_verified'],0)
        self.assertIsNone(result['package_inventory']['baseline_package_count'])

    def test_unexpected_failure_and_legacy_matrix_failure_remain_visible(self):
        cell=dict(compiler='gcc',image='candidate',status='COMPATIBLE')
        test=dict(id='unplanned',compiler='gcc',image='candidate',kind='runtime',status='INCOMPATIBLE',evidence=[])
        reconcile([], [test], [cell])
        self.assertEqual((cell['status'],cell['verification']),('INCOMPATIBLE','PARTIAL'))
        cell=dict(compiler='gcc',image='candidate',status='INCOMPATIBLE')
        reconcile([], [], [cell])
        self.assertEqual((cell['status'],cell['verification']),('INCOMPATIBLE','PARTIAL'))

    def test_obligation_failure_without_finding_controls_global_status_and_gate(self):
        a,b=self.blank(),self.blank();self.config['analysis']['modes']=['runtime']
        cell=dict(compiler='gcc',image='candidate',status='INCOMPATIBLE',required_checks=[check('broken stage','INCOMPATIBLE')])
        result=build_results(a,b,[],[],[cell],self.config)
        self.assertEqual(result['status'],'INCOMPATIBLE');self.assertEqual(result['quality_gate']['compatibility_status'],'FAIL')
        self.assertTrue(result['quality_gate']['compatibility_obligation_failures'])
        self.config['ci']['fail_on']='CRITICAL'
        result=build_results(a,b,[],[],[cell],self.config)
        self.assertEqual(result['status'],'INCOMPATIBLE');self.assertEqual(result['quality_gate']['compatibility_status'],'PASS')

    def test_cross_format_exact_records_and_corruption_detection(self):
        a,b,fs,config=fixture(12,3)
        result=build_results(a,b,fs,[],[],config);generate(self.output,a,b,result,config)
        checks=verify_reports(self.output,[f['id'] for f in fs],12)
        self.assertTrue(checks['no_lost_findings']);self.assertEqual(checks['provider_consumer_edges'],12)
        csv=self.output/'findings.csv';lines=csv.read_text().splitlines(True);csv.write_text(''.join(lines[:-1]))
        with self.assertRaises(AssertionError):verify_reports(self.output,[f['id'] for f in fs],12)

    def test_benchmark_budget_rejects_time_memory_and_reference_regressions(self):
        metrics=dict(fixture_version=2,packages_per_image=10,exports_per_package=2,wall_seconds=1,peak_rss_mib=10)
        self.assertFalse(budget_failures(metrics,2,20,metrics,2))
        self.assertEqual(len(budget_failures(metrics,.5,5)),2)
        self.assertEqual(len(budget_failures(dict(metrics,wall_seconds=3,peak_rss_mib=30),10,100,metrics,2)),2)
        with self.assertRaises(ValueError):budget_failures(metrics,reference=dict(metrics,packages_per_image=11))

    def test_indexing_and_aggregation_are_deterministic_under_inventory_permutation(self):
        a,b,fs,config=fixture(12,3);first=build_results(a,b,fs,[],[],config)
        for m in (a,b):
            for key in ('packages','elf_objects','filesystem','public_headers'):m[key].reverse()
        second=build_results(a,b,fs,[],[],config)
        self.assertEqual(first['package_results'],second['package_results'])
        self.assertEqual(first['package_inventory']['provider_consumers'],second['package_inventory']['provider_consumers'])

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'),'Needs real compiler')
    def test_sdk_and_rootfs_remain_readonly_during_real_compile_probes(self):
        roots=[];sdks={}
        for label in ('baseline','candidate'):
            root=self.base/label;root.mkdir();(root/'marker').write_text('unchanged')
            roots.append(Image(root,self.workspace,self.tools,label))
            sdk=self.base/(label+'-sdk');(sdk/'usr/include').mkdir(parents=True)
            (sdk/'usr/include/api.h').write_text('int api(void);');sdks[label]=str(sdk)
        self.config['cross_compilation'].update(cpp_tests=False,sysroots=sdks,compilers={'gcc':{'c':shutil.which('gcc')}},target_abis={label:dict(machine='Advanced Micro Devices X86-64',**{'class':'ELF64'},endianness="2's complement, little endian",provenance='synthetic-host-fixture') for label in sdks})
        def snapshot():return {str(p):hash_file(p) for base in [r.root for r in roots]+[Path(s) for s in sdks.values()] for p in base.rglob('*') if p.is_file()}
        before=snapshot();tests,_,_=run_matrix((self.blank(),self.blank()),tuple(roots),self.tools,'full')
        self.assertTrue(any(t.get('name')=='header:/usr/include/api.h' and t.get('success') for t in tests))
        self.assertEqual(before,snapshot())

if __name__=='__main__':unittest.main()
