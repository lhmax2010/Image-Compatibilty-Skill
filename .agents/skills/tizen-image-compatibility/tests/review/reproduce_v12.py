"""Run with COMPAT_SCRIPTS pointing at reviewed 1.1 to reproduce its gaps."""
import copy, os, sys
from pathlib import Path
sys.path.insert(0, os.environ.get('COMPAT_SCRIPTS', str(Path(__file__).resolve().parents[2] / 'scripts')))
from compat.core import DEFAULTS, finding
from compat.linker import dependency_checks
from compat.coverage import coverage_report
from compat.elf import target_abi_matches
s=dict(name='f',type='FUNC',binding='GLOBAL',visibility='DEFAULT',size=0)
def elf(path, **kw):
    return dict(path=path,complete=True,machine='ARM',endianness='little',exports=[],imports=[],needed=[],**{'class':'ELF32'},arm_abi={'eabi':5,'float':'hard'},**kw)
c=elf('/app',type='EXEC'); c.update(needed=['a.so','b.so'],imports=[s])
a,b=elf('/lib/a.so'),elf('/lib/b.so'); a['exports']=b['exports']=[s]
m=dict(image={'name':'synthetic'},elf_objects=[a,b],filesystem=[],public_headers=[],packages=[],limitations=[],
       collection_complete=True,loader_environment=dict(model='glibc',environment_complete=True,cache_complete=True,default_dirs=['/lib'],symbol_scope='startup'))
print('M1 two eligible providers:', [(f['interface'],f['status']) for f in dependency_checks(m,'baseline consumers on candidate',[c]) if 'import:' in f['interface']])
base=dict(m,elf_objects=[c]); fs=[finding('linking','/app','baseline consumers on candidate:DT_NEEDED:missing',1,None,'INCOMPATIBLE'),finding('linking','/app','baseline consumers on candidate:import:unverified',None,None,'UNKNOWN')]
coverage,_=coverage_report(base,m,fs,[],[],copy.deepcopy(DEFAULTS))
print('M2 failure plus unknown:', {k:coverage['linking'][k] for k in ('applicable','verified','incompatible','coverage_percent')})
partial=elf('/unrelated'); partial['arm_abi']={}
print('M4 all-rootfs ABI prerequisite:', all(target_abi_matches(c,x) for x in [a,partial]))

try:
    from compat.elf import verify_compile_target
except ImportError:
    pass
else:
    config=copy.deepcopy(DEFAULTS)
    probe=dict(c,type='REL',arm_abi={'eabi':5,'float':'hard','cpu_arch':'v7'})
    config['cross_compilation']['target_abis']['baseline']=dict(machine='ARM',**{'class':'ELF32'},endianness='little',eabi=5,float='hard',cpu_arch='v7',provenance='synthetic SDK')
    print('M4 primary configured ABI:',verify_compile_target(probe,dict(m,elf_objects=[a,partial]),config,'baseline')['status'])
