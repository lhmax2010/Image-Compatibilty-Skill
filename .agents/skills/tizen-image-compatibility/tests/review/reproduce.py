"""Print reproducible observations; use COMPAT_SCRIPTS to inspect an older checkout.
All ELFs are synthetic, built but never executed. Adapter only prints simulated results.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, os.environ.get('COMPAT_SCRIPTS', str(Path(__file__).resolve().parents[2] / 'scripts')))
from compat.core import DEFAULTS, Tools
from compat.elf import collect_elf
from compat.compare import dependency_checks, exports, advanced_abi, compare_api
from compat.source import parse_header
from compat.images import Image
from compat.testing import run_matrix
from compat.report import build_results

with tempfile.TemporaryDirectory() as td:
    p = Path(td); (p/'report').mkdir(); (p/'root/opt/hidden').mkdir(parents=True)
    c = copy.deepcopy(DEFAULTS); tools = Tools(p/'report', c)
    (p/'lib.c').write_text('int old_impl(void){return 1;} int new_impl(void){return 2;}\n__asm__(".symver old_impl,foo@V1");\n__asm__(".symver new_impl,foo@@V2");\n')
    (p/'versions').write_text('V1 {}; V2 {} V1;\n')
    lib = p/'root/opt/hidden/libv.so'
    subprocess.run(['gcc','-shared','-fPIC','-g','-nostdlib','-Wl,--build-id','-Wl,-soname,libv.so','-Wl,--version-script='+str(p/'versions'),str(p/'lib.c'),'-o',str(lib)],check=True)
    obj = collect_elf(lib,'/opt/hidden/libv.so',tools,'static')
    blank = dict(image={'name':'synthetic'}, elf_objects=[obj], filesystem=[], public_headers=[], packages=[],limitations=[],test_results=[])
    consumer = dict(obj, path='/bin/client', needed=['libv.so'], exports=[],imports=[{'name':'missing@V1','type':'FUNC','binding':'GLOBAL','visibility':'DEFAULT','size':0}])
    print('P0-1 hidden provider / unsatisfied import:', [(x['interface'],x['status']) for x in dependency_checks(blank,'synthetic',[consumer])])
    print('P0-2 parsed version relationships:', {k:obj.get(k) for k in ('version_definitions','version_requirements')})
    print('P0-2 raw exports vs lookup keys:', [s['name'] for s in obj['exports']], list(exports(obj)))
    image = Image(p/'root',p,tools,'fixture')
    stripped = copy.deepcopy(blank); stripped['elf_objects'][0]['debug_info']=False
    # A fake available abidiff isolates the skip bug; it does not claim real ABI execution.
    original_path=tools.path
    tools.path=lambda name: '/bin/true' if name=='abidiff' else original_path(name)
    print('P0-4 two no-DWARF libraries:', [(x['component'],x['interface']) for x in advanced_abi(dict(stripped,elf_objects=[dict(stripped['elf_objects'][0],path='/lib/a.so'),dict(stripped['elf_objects'][0],path='/lib/b.so')]),stripped,(image,image),tools)])
    tools.path=original_path
    a,b=copy.deepcopy(blank),copy.deepcopy(blank)
    for m,h,sha in ((a,'int f(void);','a'),(b,'/* comment */ int f(void);','b')):
        m['public_headers']=[dict(path='/usr/include/a.h',sha256=sha,**parse_header(h))]
    print('P1-1 token equality:', [x['status'] for x in compare_api(a,b)])
    result=build_results(a,b,[],[],[],c)
    print('P1-2 coverage fields:', result.get('coverage'),result.get('quality_gate'))
    adapter=p/'adapter.py'; adapter.write_text('import sys\nprint("simulated")\nsys.exit(0 if sys.argv[1]=="baseline" else 1)\n')
    c['cross_compilation'].update(cpp_tests=False,sysroots={'baseline':'/','candidate':'/'},compilers={'clang':{'c':'/usr/bin/gcc'}})
    c['runtime'].update(enabled=True,authorized=True,environments={label:{'id':'simulation-'+label,'runner':[sys.executable,str(adapter),'{image}','{binary}']} for label in ('baseline','candidate')})
    tests,matrix,_=run_matrix((copy.deepcopy(blank),copy.deepcopy(blank)),(image,image),tools,'full')
    print('P0-3 candidate-built artifact with own-image failure:', [(t['image'],t['status'],t.get('returncode')) for t in tests if t['kind']=='runtime'])
