"""Release-stabilization review cases; real synthetic compilation, no Tizen execution."""
import copy
import csv
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
from test_framework import Environment
from test_correctness import obj,symbol
from test_v12 import installed,inventory
from compat.core import finding,read_manifest,write_json,InputError,hash_file
from compat.elf import verify_compile_target,collect_elf
from compat.linker import dependency_checks
from compat.images import Image
from compat.testing import run_matrix
from compat.report import build_results,generate


class ReleaseReviewTests(Environment):
    def arm(self,arch='v7',pcs='soft'):
        return dict(path='/probe.o',complete=True,type='REL',machine='ARM',**{'class':'ELF32'},endianness="2's complement, little endian",arm_abi={'eabi':5,'float':pcs,'cpu_arch':arch})
    def configure_arm(self):
        self.config['cross_compilation']['target_abis']['baseline']=dict(machine='ARM',**{'class':'ELF32'},endianness="2's complement, little endian",eabi=5,float='soft',cpu_arch='v7',provenance='synthetic SDK')
    def test_arm_different_arch_is_unknown_not_calling_convention_break(self):
        self.configure_arm()
        for arch in ('v6','v8','v7E-M',None):
            r=verify_compile_target(self.arm(arch),self.blank(),self.config,'baseline')
            self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(r['abi_status'],'COMPATIBLE')
            self.assertFalse(r['conflicts']);self.assertEqual(r['hardware_assessment']['status'],'UNKNOWN')
        r=verify_compile_target(self.arm(),self.blank(),self.config,'baseline')
        self.assertEqual(r['status'],'COMPATIBLE');self.assertEqual(r['isa_assessment']['status'],'COMPATIBLE')
        self.assertEqual(r['hardware_assessment']['status'],'UNKNOWN')
    def test_arm_abi_conflict_survives_isa_uncertainty(self):
        self.configure_arm()
        for change in ('float','eabi','endianness'):
            e=self.arm('v6')
            if change=='float':e['arm_abi']['float']='hard'
            elif change=='eabi':e['arm_abi']['eabi']=4
            else:e['endianness']='big'
            r=verify_compile_target(e,self.blank(),self.config,'baseline')
            self.assertEqual(r['status'],'INCOMPATIBLE');self.assertEqual(r['abi_status'],'INCOMPATIBLE')
    @unittest.skipUnless(os.environ.get('COMPAT_TEST_CLANG'),'Needs actual Clang ARM compiler')
    def test_real_arm_v6_v7_and_vfp_fixtures(self):
        self.configure_arm();source=self.base/'probe.c';source.write_text('double probe(double x){return x+1.;}')
        for arch,pcs,expected in [('armv6','soft','UNKNOWN'),('armv7','soft','COMPATIBLE'),('armv7','hard','INCOMPATIBLE')]:
            flags=['--target='+arch+'-linux-gnueabi','-mfpu=vfpv3','-mfloat-abi='+pcs]
            out=self.base/(arch+pcs+'.o');compiler=os.environ['COMPAT_TEST_CLANG']
            subprocess.run([compiler,*flags,'-c',str(source),'-o',str(out)],check=True,capture_output=True)
            e=collect_elf(out,'/probe.o',self.tools,'quick')
            macros=subprocess.run([compiler,*flags,'-dM','-E',str(source)],check=True,capture_output=True,text=True).stdout
            if e['arm_abi']['float'] is None:
                self.assertIn('#define __ARM_PCS ',macros);e['arm_abi']['float']='soft'
            self.assertEqual(verify_compile_target(e,self.blank(),self.config,'baseline')['status'],expected)

    def custom_setup(self,missing_compiler=False):
        roots=[];sysroots={}
        for label in ('baseline','candidate'):
            root=self.base/label;root.mkdir();(root/'marker').write_text('read only')
            roots.append(Image(root,self.workspace,self.tools,label));sysroots[label]=str(root)
        specs=[]
        for language,ext in [('c','c'),('cpp','cpp')]:
            source=self.base/('probe.'+ext);source.write_text(('extern "C" ' if language=='cpp' else '')+'int entry(void){return 0;}')
            specs.append(dict(name='explicit-'+language,language=language,source=str(source),flags=['-nostdlib','-Wl,-e,entry']))
        self.config['cross_compilation'].update(c_tests=False,cpp_tests=False,sysroots=sysroots,
            compilers={'gcc':{'c':shutil.which('gcc'),'cpp':'/unavailable/compiler' if missing_compiler else shutil.which('g++')}},
            builds={'gcc':dict(sdk='baseline',reference_image='baseline',provenance='synthetic native SDK')},probes=specs)
        a,b=self.blank(),self.blank()
        for m in (a,b):m['elf_objects']=[obj('/lib/native.so',type='DYN')]
        return (a,b),tuple(roots)
    @unittest.skipUnless(shutil.which('gcc') and shutil.which('g++'),'Needs native C/C++ synthetic compilers')
    def test_explicit_c_and_cpp_schedule_with_builtin_toggles_disabled(self):
        manifests,roots=self.custom_setup()
        sources=[r.root/'marker' for r in roots]+[Path(p['source']) for p in self.config['cross_compilation']['probes']]
        before={str(p):hash_file(p) for p in sources}
        tests,matrix,_=run_matrix(manifests,roots,self.tools,'full')
        builds=[t for t in tests if t.get('success')]
        expected=[e for m in manifests for e in m['expected_tests'] if e['compiler']=='gcc' and e['kind']=='build']
        self.assertEqual({t['id'] for t in builds},{e['id'] for e in expected});self.assertEqual(len(builds),2)
        self.assertFalse(any('behavior' in t.get('name','') for t in tests))
        self.assertFalse(manifests[0]['test_manifest_audit']['duplicates']);self.assertFalse(manifests[0]['test_manifest_audit']['unexpected'])
        self.assertTrue(all(c['status']=='UNKNOWN' for c in matrix)) # no authorized runtime
        self.assertEqual(before,{str(p):hash_file(p) for p in sources})
    @unittest.skipUnless(shutil.which('gcc') and shutil.which('g++'),'Needs native synthetic compilers')
    def test_missing_custom_compiler_and_disabled_execution_keep_expected_ids(self):
        manifests,roots=self.custom_setup(True)
        tests,_,_=run_matrix(manifests,roots,self.tools,'full')
        cpp=next(e for m in manifests for e in m['expected_tests'] if e['compiler']=='gcc' and e['kind']=='build' and e['language']=='cpp')
        self.assertIn(cpp['id'],manifests[0]['test_manifest_audit']['missing']);self.assertEqual(cpp['status'],'UNKNOWN')
        self.assertTrue(any(t.get('name')=='explicit-c' and t.get('success') for t in tests))

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('g++') and os.environ.get('COMPAT_TEST_CLANG'),'Needs real GCC/Clang compile tools')
    def test_explicit_probes_exact_matrix_ids_with_simulated_receipts(self):
        manifests,roots=self.custom_setup()
        cc=self.config['cross_compilation'];clang=os.environ['COMPAT_TEST_CLANG']
        cc['compilers']['clang']={'c':clang,'cpp':clang}
        cc['builds']['clang']=dict(sdk='candidate',reference_image='candidate',provenance='synthetic Clang build')
        self.config['runtime'].update(enabled=True,authorized=True,environments={k:dict(id=k,runner=['SIMULATED-only','{binary}']) for k in ('baseline','candidate')})
        def receipt(env,binary,args,label,image,tools):
            return dict(returncode=0,stdout='synthetic-observation',stderr='',receipt_sha256=hash_file(binary),stdout_evidence='simulated',stderr_evidence='simulated',stages=dict(deployment_status='SUCCESS',execution_status='SUCCESS',behavior_status='UNKNOWN'))
        # Real compilation; harness-only receipts. No artifact or target is executed.
        with patch('compat.testing.run_target',side_effect=receipt):tests,matrix,_=run_matrix(manifests,roots,self.tools,'full')
        expected=[e for m in manifests for e in m['expected_tests']]
        self.assertEqual(len(expected),12);self.assertEqual({e['id'] for e in expected},{t['id'] for t in tests})
        self.assertEqual(manifests[0]['test_manifest_audit'],dict(missing=[],duplicates=[],unexpected=[]))
        self.assertTrue(all(c['status']=='COMPATIBLE' and c['verification']=='COMPLETE' for c in matrix))

    def lookup(self):
        c=obj('/app',type='EXEC',needed=['a.so'],imports=[symbol('f')]);p=obj('/lib/a.so',type='DYN',exports=[symbol('f')])
        m=self.blank();m.update(elf_objects=[p],collection_complete=True,loader_environment=dict(model='glibc',environment_complete=True,cache_complete=True,symbol_scope='startup',namespace='base',default_dirs=['/lib']))
        return c,p,m
    def imported(self,c,m):return next(f for f in dependency_checks(m,'baseline consumers on candidate',[c]) if f['check_id']=='import:f')
    def test_resolution_marker_required_on_consumer_and_provider(self):
        for side in ('consumer','provider'):
            for value in (None,False,'true',1):
                c,p,m=self.lookup();o=c if side=='consumer' else p
                if value is None:o.pop('resolution_metadata_complete')
                else:o['resolution_metadata_complete']=value
                self.assertEqual(self.imported(c,m)['status'],'UNKNOWN')
        c,p,m=self.lookup();self.assertEqual(self.imported(c,m)['status'],'COMPATIBLE')
        p['exports']=[];self.assertEqual(self.imported(c,m)['status'],'INCOMPATIBLE')
    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'),'Needs real synthetic ELF collection')
    def test_collector_establishes_resolution_evidence_and_rejects_partial_output(self):
        src=self.base/'lib.c';src.write_text('int exported(void){return 1;}');lib=self.base/'a.so'
        subprocess.run(['gcc','-shared','-fPIC',str(src),'-o',str(lib)],check=True)
        good=collect_elf(lib,'/lib/a.so',self.tools,'static')
        self.assertTrue(good['resolution_metadata_complete']);self.assertTrue(good['resolution_metadata_evidence'])
        real_run=self.tools.run
        for mode in ('truncated','warning','missing_dynamic','short_symbols'):
            def damaged(*args,**kwargs):
                r=real_run(*args,**kwargs)
                if mode=='truncated':r['stdout_truncated']=True
                elif mode=='warning':r['stderr']='readelf: malformed symbol metadata'
                elif mode=='missing_dynamic':r['stdout']=r['stdout'].replace('Dynamic section at offset','missing section at offset')
                else:r['stdout']=re.sub(r"(Symbol table '\.dynsym' contains )\d+",r'\g<1>999',r['stdout'])
                return r
            with patch.object(self.tools,'run',side_effect=damaged):bad=collect_elf(lib,'/lib/a.so',self.tools,'static')
            self.assertFalse(bad['resolution_metadata_complete'],mode)
        self.config['tools']['readelf']=False
        self.assertFalse(collect_elf(lib,'/lib/a.so',self.tools,'static')['resolution_metadata_complete'])
    def test_old_and_incomplete_manifest_never_invents_resolution_marker(self):
        c,p,m=self.lookup();m['schema_version']='1.2';p.pop('resolution_metadata_complete')
        path=self.base/'manifest.json';write_json(path,m);loaded=read_manifest(path)
        self.assertEqual(self.imported(c,loaded)['status'],'UNKNOWN')
        p['resolution_metadata_complete']='yes';write_json(path,m)
        with self.assertRaises(InputError):read_manifest(path)
        p['resolution_metadata_complete']=True;m['schema_version']='1.1';write_json(path,m)
        self.assertFalse(read_manifest(path)['elf_objects'][0]['resolution_metadata_complete'])

    def test_candidate_addition_is_inventory_added_with_unknown_compatibility(self):
        a=inventory(self.blank(),[]);b=inventory(self.blank(),[installed('new',['/new'])])
        r=build_results(a,b,[],[],[],self.config);addition=r['package_inventory']['candidate_additions'][0]
        self.assertEqual(addition['inventory_status'],'ADDED');self.assertEqual(addition['status'],'UNKNOWN')
        self.assertEqual(r['package_inventory']['candidate_assessments'][0]['status'],'UNKNOWN')
        self.assertFalse(build_results(b,b,[],[],[],self.config)['package_inventory']['candidate_additions'])
    def test_missing_preview_filters_before_limit_and_keeps_machine_data(self):
        fs=[finding('abi','/present/'+str(i),'present',1,1,'UNKNOWN') for i in range(1000)]
        absent=[finding('abi','/missing/'+str(i),'removed',1,None,'INCOMPATIBLE') for i in range(1002)]
        fs+=absent;result=build_results(self.blank(),self.blank(),fs,[],[],self.config)
        generate(self.output,self.blank(),self.blank(),result,self.config)
        section=(self.output/'index.html').read_text().split('<h2>Missing interfaces',1)[1].split('<h2>',1)[0]
        self.assertIn('Total: 1002; shown: 1000; hidden: 2',section)
        self.assertIn(absent[0]['id'],section);self.assertIn(absent[999]['id'],section);self.assertNotIn(absent[1000]['id'],section)
        data=json.loads((self.output/'results.json').read_text());self.assertEqual(len(data['findings']),2002)
        with (self.output/'findings.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual([r['id'] for r in rows],[f['id'] for f in fs]);self.assertEqual(len(data['missing_interfaces']),1002)
        self.assertFalse(any(f['id'] in section for f in fs[:1000]))

if __name__=='__main__':unittest.main()
