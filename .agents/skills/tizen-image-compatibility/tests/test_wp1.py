"""WP-1 ELF and input acceptance. Fixture binaries are never executed."""
from collections import Counter
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from test_preparation import gpt, write_tar
from compat.compare import compare_elf
from compat.core import DEFAULTS, Tools, VERSION
from compat.elf import collect_elf
from compat.flash import gpt_partitions
from compat.preparation import is_tar_container
from compat.report_io import ResourceGuard
from compat.repository import symbol_rows, symbols
from compat.symbol_rules import classify_symbol_change
from tizen_compat import main


def invoke(argv, timeout=90):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise AssertionError(f'{argv[0]} exited {result.returncode}: {result.stderr}')
    return result.stdout


def independent_interface(path):
    """Compare GNU text columns with the Skill inventory without its regex/helpers."""
    text = invoke(['readelf','-W','--dyn-syms','-V','-d',str(path)])
    providers, definitions, requirements, needed = {}, set(), set(), []
    exports, imports = [], []
    in_symbols = False
    where = None
    provider = None
    for line in text.splitlines():
        if line.startswith('Version definition section'):
            where = 'definition'
        elif line.startswith('Version needs section'):
            where = 'needs'
        if where == 'definition' and 'Index:' in line and 'Name:' in line:
            definitions.add(line.split('Name:',1)[1].strip())
        if where == 'needs':
            if 'File:' in line:
                provider = line.split('File:',1)[1].split()[0]
            if 'Name:' in line and 'Version:' in line:
                name = line.split('Name:',1)[1].split()[0]
                index = int(line.split('Version:',1)[1].strip())
                providers[index] = provider
                requirements.add((provider,name,index))
        if '(NEEDED)' in line:
            needed.append(line.rsplit('[',1)[1].split(']',1)[0])
        if line.startswith("Symbol table '.dynsym' "):
            in_symbols = True
            continue
        if not line.strip():
            in_symbols = False
        fields = line.split(maxsplit=7)
        if not in_symbols or len(fields)!=8 or not fields[0].rstrip(':').isdigit():
            continue
        _,value,size,kind,binding,visibility,section,name = fields
        size = int(size,16) if size.startswith('0x') else int(size)
        if section=='UND':
            ending = re.fullmatch(r'(.*) \((\d+)\)',name) if '@' in name else None
            imports.append((ending[1] if ending else name,size,kind,binding,visibility,int(ending[2]) if ending else None))
        elif binding in ('GLOBAL','WEAK','UNIQUE','GNU_UNIQUE') and visibility in ('DEFAULT','PROTECTED'):
            exports.append((name,size,kind,binding,visibility,section,value))
    exports = [(name,size,kind,binding,visibility) for name,size,kind,binding,visibility,section,value in exports
               if not (name in definitions and size==0 and int(value,16)==0 and kind=='OBJECT' and
                       binding=='GLOBAL' and visibility=='DEFAULT' and section=='ABS')]
    return (Counter(exports), Counter(row[:5]+(providers.get(row[5]),) for row in imports),
            definitions, requirements, needed)


class WorkPackageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = copy.deepcopy(DEFAULTS)
        self.tools = Tools(self.root/'evidence-output',self.config)

    def require(self, tool, env=None):
        path = os.getenv(env,'') if env else ''
        path = path or shutil.which(tool)
        if not path or not os.access(path,os.X_OK):
            reason = f'BLOCKED: missing {tool}'+(f' ({env})' if env else '')
            if os.getenv('COMPAT_RELEASE_CI')=='1':
                self.fail(reason)
            self.skipTest(reason)
        return path

    def fixture(self, compiler, leaf, size, keep_bar, *, target=None):
        work = self.root/leaf
        work.mkdir()
        source = work/'contract.c'
        source.write_text(f'char big_table[{size}]; int foo(void) {{return 1;}}' +
                          (' int bar(void) {return 2;}' if keep_bar else '')+'\n')
        version = work/'exports.map'
        version.write_text('V1 { global: big_table; foo;' + (' bar;' if keep_bar else '') + ' local: *; };\n')
        output = work/'lib/libwp1.so'
        output.parent.mkdir()
        if target:
            invoke([compiler,str(source),str(version),str(output)])
        else:
            obj = work/'contract.o'
            invoke([compiler,'-fPIC','-c',str(source),'-o',str(obj)])
            invoke(['gcc','-shared',str(obj),f'-Wl,--version-script={version},-soname,libwp1.so',
                    '-o',str(output)])
        return work,output

    def independently_check(self, path, obj):
        def key(s):
            return tuple(s[k] for k in ('name','size','type','binding','visibility'))
        actual = (Counter(key(s) for s in obj['exports']),
                  Counter(key(s)+(s.get('version_file'),) for s in obj['imports']),
                  {v['name'] for v in obj['version_definitions']},
                  {(v['file'],v['name'],v['index']) for v in obj['version_requirements']},obj['needed'])
        self.assertEqual(actual,independent_interface(path))

    def check_transitions(self, compiler, label, *, target=False):
        old, a = self.fixture(compiler,label+'-a',200000,True,target=target)
        new, b = self.fixture(compiler,label+'-b',100,False,target=target)
        grow_old, c = self.fixture(compiler,label+'-c',100,True,target=target)
        grow_new, d = self.fixture(compiler,label+'-d',150000,False,target=target)
        for path in (a,b,c,d):
            for bounded in (False,True):
                obj = collect_elf(path,'/lib/libwp1.so',self.tools,'static',bounded=bounded)
                self.assertTrue(obj['export_inventory_complete'],obj.get('export_inventory_reason'))
                values = {s['name']:s['size'] for s in obj['exports']}
                self.assertEqual(values['big_table@@V1'],200000 if path==a else 150000 if path==d else 100)
                self.assertNotIn('V1',values)
                if target:
                    self.assertEqual(obj.get('machine'),'ARM')
                if not bounded:
                    self.independently_check(path,obj)
        for index,(left,right,reason) in enumerate(((old,new,'DATA_SIZE_DECREASED'),(grow_old,grow_new,'DATA_SIZE_INCREASED'))):
            report = self.root/(label+'-report-'+str(index))
            self.assertEqual(main(['--baseline',str(left),'--candidate',str(right),'--output',str(report)]),1)
            data = json.loads((report/'results.json').read_text())
            findings = {f['interface']:f for f in data['findings'] if f['dimension']=='abi' and f['component']=='/lib/libwp1.so'}
            self.assertEqual(findings['bar@@V1']['status'],'INCOMPATIBLE')
            self.assertEqual(findings['big_table@@V1:size']['status'],'INCOMPATIBLE')
            self.assertEqual(findings['big_table@@V1:size']['reason_code'],reason)
            self.assertTrue(all(not name.startswith('V1') for name in findings))

    def test_t01_t03_and_cli_gcc_x86(self):
        self.check_transitions(self.require('gcc'),'gcc')

    def test_t01_t03_and_cli_clang_x86(self):
        self.check_transitions(self.require('clang','WP1_CLANG'),'clang')

    def test_t01_t03_and_cli_sr_arm(self):
        for family in ('GCC','CLANG'):
            with self.subTest(family=family):
                compiler = self.require(f'SR ARM {family} fixture wrapper',f'WP1_ARM_{family}')
                self.check_transitions(compiler,'arm-'+family,target=True)

    def test_t02_large_dynamic_table(self):
        self.require('gcc')
        asm = self.root/'large.s'
        with asm.open('w') as out:
            print('.text',file=out)
            for i in range(50000):
                print(f'.globl fn_{i}\n.type fn_{i}, @function\nfn_{i}: ret',file=out)
            print('.data',file=out)
            for i in range(50000):
                print(f'.quad fn_{i}, fn_{i}, fn_{i}, fn_{i}',file=out)
            print('.section .note.GNU-stack,"",@progbits',file=out)
        elf = self.root/'large.so'
        invoke(['gcc','-shared','-nostdlib',str(asm),'-o',str(elf)])
        relocating = subprocess.run(['readelf','-Wr',str(elf)],check=True,capture_output=True,timeout=90).stdout
        self.assertGreaterEqual(sum(b' R_X86_64_64 ' in line for line in relocating.splitlines()),200000)
        self.assertGreater(len(relocating),16*1024**2)
        obj = collect_elf(elf,'/large.so',self.tools,'static',bounded=True)
        self.assertTrue(obj['export_inventory_complete'])
        self.assertEqual(len(obj['exports']),50000)
        self.independently_check(elf,obj)

    def test_t04_rules(self):
        for field,before,after,expected in (
            ('type','FUNC','IFUNC',('UNKNOWN','LOW','IFUNC_TRANSITION')),
            ('type','GNU_IFUNC','FUNC',('UNKNOWN','LOW','IFUNC_TRANSITION')),
            ('type','NOTYPE','OBJECT',('UNKNOWN','MEDIUM','NOTYPE_ANNOTATION')),
            ('type','FUNC','NOTYPE',('UNKNOWN','MEDIUM','NOTYPE_ANNOTATION')),
            ('type','OBJECT','IFUNC',('INCOMPATIBLE','HIGH','KIND_CHANGED')),
            ('type','TLS','FUNC',('INCOMPATIBLE','HIGH','TLS_KIND_CHANGED')),
            ('type','OBJECT','TLS',('INCOMPATIBLE','HIGH','TLS_KIND_CHANGED')),
            ('size',8,4,('INCOMPATIBLE','HIGH','DATA_SIZE_DECREASED')),
            ('size',4,8,('INCOMPATIBLE','HIGH','DATA_SIZE_INCREASED')),
            ('binding','UNIQUE','GLOBAL',('UNKNOWN','MEDIUM','GNU_UNIQUE_DROPPED')),
            ('binding','GNU_UNIQUE','GLOBAL',('UNKNOWN','MEDIUM','GNU_UNIQUE_DROPPED')),
            ('binding','GLOBAL','WEAK',('UNKNOWN','HIGH','SYMBOL_BINDING_CHANGED')),
            ('visibility','PROTECTED','DEFAULT',('UNKNOWN','HIGH','SYMBOL_VISIBILITY_CHANGED'))):
            with self.subTest(field=field,before=before,after=after):
                self.assertEqual(classify_symbol_change(field,before,after),expected)

    def test_k01_duplicate_orders_and_repository_rows(self):
        row = {'name':'foo','size':8,'binding':'GLOBAL','visibility':'DEFAULT','type':'OBJECT'}
        obj = {'path':'/sample.so','complete':True,'export_inventory_complete':True,'exports':[row]}
        forms = ([row,row|{'size':4}],[row|{'size':4},row])
        outcomes = []
        for rows in forms:
            altered = obj | {'exports':rows}
            findings = compare_elf({'elf_objects':[altered]},{'elf_objects':[obj]})
            abi = [f for f in findings if f['dimension']=='abi']
            self.assertTrue(abi and all(f['status']=='UNKNOWN' for f in abi))
            self.assertTrue(any(f.get('reason_code')=='DUPLICATE_DYNSYM_IDENTITY' for f in abi))
            self.assertEqual(len(symbols(altered,'EXPORT')[('foo',None)]),2)
            rendered = list(symbol_rows({'package_id':'sample','component':'/sample.so'},altered,obj,{}))
            self.assertEqual([r['status'] for r in rendered],['UNKNOWN']*3)
            outcomes.append((abi,rendered))
        self.assertEqual(*outcomes)

    def test_k03_zero_tar_valid_tar_and_gpt(self):
        zero=self.root/'zero'
        zero.write_bytes(bytes(1024))
        self.assertEqual(main(['--baseline',str(zero),'--candidate',str(zero),'--output',str(self.root/'invalid')]),2)
        valid=self.root/'valid.tar'
        write_tar(valid,{'etc/os-release':b'Synthetic\n'})
        self.assertTrue(is_tar_container(valid))
        empty_tree=self.root/'only-directories.tar'
        with tarfile.open(empty_tree,'w') as archive:
            entry=tarfile.TarInfo('etc')
            entry.type=tarfile.DIRTYPE
            archive.addfile(entry)
        self.assertEqual(main(['--baseline',str(empty_tree),'--candidate',str(empty_tree),
                               '--output',str(self.root/'invalid-tree')]),2)
        disk=self.root/'flash'
        disk.write_bytes(gpt(bytes(4096)))
        self.assertFalse(is_tar_container(disk))
        self.assertEqual(gpt_partitions(disk)['sector_size'],512)

    def test_k06_bounded_output_evidence_and_cleanup(self):
        with patch('compat.core.DEFAULT_CAPTURE_BYTES',8192):
            result=self.tools.run([sys.executable,'-c','import os,time; os.write(1,b"x"*16000); time.sleep(5)'])
        self.assertEqual(result['reason_code'],'OUTPUT_LIMIT')
        self.assertTrue(result['stdout_truncated'])
        self.assertEqual(result['local_process_group_status'],'VERIFIED')
        self.assertLessEqual(sum((self.tools.output/result[f'{side}_evidence']).stat().st_size
                                 for side in ('stdout','stderr')),8192)

    def test_k09_unreadable_psi_uses_memory_fallback(self):
        original=Path.read_text

        def read(path,*args,**kwargs):
            if str(path)=='/proc/pressure/memory':
                raise PermissionError('fixture')
            fake = {'/proc/self/cgroup':'0::/test\n','/sys/fs/cgroup/test/memory.current':'1024\n',
                    '/sys/fs/cgroup/test/memory.max':str(8*1024**3)}
            return fake[str(path)] if str(path) in fake else original(path,*args,**kwargs)

        with patch.object(Path,'read_text',read):
            guard=ResourceGuard(self.root,disk_budget=1)
            guard.check(force=True)
        self.assertEqual(guard.last_snapshot['memory_pressure'],'NOT_AVAILABLE')
        self.assertEqual(guard.last_snapshot['cgroup_memory_current_bytes'],1024)
        self.assertLessEqual(guard.last_snapshot['mem_available_bytes'],8*1024**3-1024)

    def test_negative_incomplete_inputs_warning_and_bad_size(self):
        _,path=self.fixture(self.require('gcc'),'negative',200000,True)
        truncated=self.root/'truncated'
        truncated.write_bytes(path.read_bytes()[:120])
        obj=collect_elf(truncated,'/lib/libwp1.so',self.tools,'static')
        self.assertFalse(obj['export_inventory_complete'])
        good=collect_elf(path,'/lib/libwp1.so',self.tools,'static')
        findings=compare_elf({'elf_objects':[obj]},{'elf_objects':[good]})
        self.assertTrue(findings and all(f['status']=='UNKNOWN' for f in findings))
        actual=self.tools.run(['readelf','-WhlSdAVn','--dyn-syms',str(path)])
        for change in ({'stderr':'warning fixture'},{'stdout':actual['stdout'].replace('0x30d40','0xZZ')},
                       {'stdout':actual['stdout'].replace('bar@@V1','foo@@V1')}):
            with patch.object(self.tools,'run',return_value=actual|change):
                observed=collect_elf(path,'/lib/libwp1.so',self.tools,'static')
            self.assertFalse(observed['export_inventory_complete'])
            if 'foo@@V1' in change.get('stdout','') and 'bar@@V1' not in change.get('stdout',''):
                self.assertEqual(observed.get('export_inventory_reason_code'),'DUPLICATE_DYNSYM_IDENTITY')

    def test_negative_llvm_marker_and_relocation_failure(self):
        llvm=self.require('llvm-readelf','WP1_LLVM_READELF')
        _,path=self.fixture(self.require('gcc'),'llvm',200000,True)
        self.config['tools']['readelf']=llvm
        obj=collect_elf(path,'/lib/libwp1.so',self.tools,'static')
        self.assertTrue(obj['export_inventory_complete'],obj.get('export_inventory_reason'))
        self.assertTrue(any(s['name']=='V1@@V1' for s in obj['version_node_markers']))
        self.assertEqual(next(s['size'] for s in obj['exports'] if s['name']=='big_table@@V1'),200000)
        self.independently_check(path,obj)
        _,arm=self.fixture(self.require('SR ARM GCC fixture wrapper','WP1_ARM_GCC'),'relocation',200000,True,target=True)
        self.config['tools']['readelf']='readelf'
        real=self.tools.run

        def fail_reloc(argv,**kwargs):
            if '-r' in argv:
                valid=real(argv,**kwargs)
                return valid|{'returncode':-1,'error':'timeout'}
            return real(argv,**kwargs)

        with patch.object(self.tools,'run',side_effect=fail_reloc):
            obj=collect_elf(arm,'/lib/libwp1.so',self.tools,'static')
        self.assertTrue(obj['export_inventory_complete'])
        self.assertEqual(obj['arm_inventory']['relocation_status'],'UNKNOWN')

    def test_f20_version(self):
        self.assertEqual(VERSION,(Path(__file__).parents[1]/'VERSION').read_text().strip())
