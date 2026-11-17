#!/usr/bin/env python3
"""Five production-path reproductions, synthetic inputs only; no target execution."""
import copy
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_framework import Environment
from test_correctness import obj,symbol
from test_v12 import inventory,installed
from compat.elf import verify_compile_target
from compat.linker import dependency_checks
from compat.images import Image
from compat.testing import run_matrix
from compat.core import finding
from compat.report import build_results,generate


def observe():
    e=Environment();e.setUp()
    try:
        config=e.config
        arm=dict(path='/probe.o',complete=True,type='REL',machine='ARM',**{'class':'ELF32'},endianness='little',arm_abi={'eabi':5,'float':'soft','cpu_arch':'v6'})
        config['cross_compilation']['target_abis']['baseline']=dict(machine='ARM',**{'class':'ELF32'},endianness='little',eabi=5,float='soft',cpu_arch='v7',provenance='synthetic SDK')
        arm_result=verify_compile_target(arm,e.blank(),config,'baseline')
        config['cross_compilation']['target_abis']={}
        roots=[]
        for label in ('baseline','candidate'):
            root=e.base/label;root.mkdir();roots.append(Image(root,e.workspace,e.tools,label))
        source=e.base/'custom.c';source.write_text('int entry(void){return 0;}')
        config['cross_compilation'].update(c_tests=False,cpp_tests=False,sysroots={l:str(r.root) for l,r in zip(('baseline','candidate'),roots)},
            compilers={'gcc':{'c':shutil.which('gcc')}},builds={'gcc':{'sdk':'baseline','reference_image':'baseline','provenance':'synthetic'}},
            probes=[{'name':'explicit','language':'c','source':str(source),'flags':['-nostdlib','-Wl,-e,entry']}])
        a,b=e.blank(),e.blank()
        for m in (a,b):m['elf_objects']=[obj('/lib/native.so',type='DYN')]
        tests,_,_=run_matrix((a,b),tuple(roots),e.tools,'full')
        consumer=obj('/app',type='EXEC',needed=['a.so'],imports=[symbol('f')]);provider=obj('/lib/a.so',type='DYN',exports=[symbol('f')])
        consumer.pop('resolution_metadata_complete',None);provider.pop('resolution_metadata_complete',None)
        m=e.blank();m.update(elf_objects=[provider],collection_complete=True,loader_environment={'model':'glibc','environment_complete':True,'cache_complete':True,'symbol_scope':'startup','namespace':'base','default_dirs':['/lib']})
        imported=next(f for f in dependency_checks(m,'baseline consumers on candidate',[consumer]) if f['check_id']=='import:f')
        a=inventory(e.blank(),[]);b=inventory(e.blank(),[installed('new',['/new'])])
        added=build_results(a,b,[],[],[],config)['package_inventory']['candidate_additions'][0]
        fs=[finding('abi','/ordinary/'+str(i),'present','x','x','UNKNOWN') for i in range(1000)]
        missing=finding('abi','/late-missing.so','removed','x',None,'INCOMPATIBLE');fs.append(missing)
        result=build_results(a,b,fs,[],[],config);generate(e.output,a,b,result,config)
        section=(e.output/'index.html').read_text().split('<h2>Missing interfaces',1)[1].split('<h2>',1)[0]
        return {'major1':{'status':arm_result['status'],'conflicts':arm_result['conflicts']},
                'major2':{'explicit_builds':sum(t.get('name')=='explicit' and t.get('success',False) for t in tests)},
                'major3':{'missing_marker_import_status':imported['status']},
                'minor1':{'candidate_addition_status':added['status']},
                'minor2':{'late_missing_id_in_preview':missing['id'] in section,'machine_finding_count':len(result['findings'])}}
    finally:e.doCleanups()

if __name__=='__main__':print(json.dumps(observe(),indent=2))
