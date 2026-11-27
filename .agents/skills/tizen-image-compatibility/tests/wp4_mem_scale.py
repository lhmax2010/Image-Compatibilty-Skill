"""Build the two real-ELF RPM fixture sets without executing payloads."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
if not root.is_relative_to(Path.cwd().resolve()) or root == Path.cwd().resolve():
    raise SystemExit('Use a new output directory inside the workspace.')
root.mkdir()
(root/'tmp').mkdir()
os.environ.update({key:str(root/'tmp') for key in ('TMPDIR','TMP','TEMP')})

def run(argv, log):
    with (root/log).open('ab') as stream:
        subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, check=True)

def name(group, n):
    namespace = f'compatibility_fixture_group_{group:03}'
    symbol = f'configured_template_contract_with_long_mangled_signature_{n:03}'
    return f'_ZN{len(namespace)}{namespace}{len(symbol)}{symbol}IiEEvT_'

def source(group, count):
    return '.text\n' + ''.join(f'.globl {name(group,n)}\n.type {name(group,n)},@function\n'
       f'{name(group,n)}: ret\n.size {name(group,n)},.-{name(group,n)}\n' for n in range(count))

mapfile = root/'symbol.map'
mapfile.write_text('MEM_SCALE_1 { global: _Z*; local: *; };\n')
for group in (0,1):
    asm = root/f'provider{group}.s'
    asm.write_text(source(group,75))
    run(['gcc','-shared','-fPIC','-nostdlib',str(asm),f'-Wl,-soname,libmemprovider{group}.so.1,--version-script={mapfile}',
         '-o',str(root/f'libmemprovider{group}.so.1')], 'elf.log')
for i in range(24):
    baseline = source(i+2,100)
    trailing = '\n.data\n' + ''.join(f'.quad {name(group,n)}\n' for group in (0,1) for n in range(75))
    for side in ('base','cand'):
        asm=root/f'{side}-{i}.s'
        code = source(i+2,99) if side=='cand' and i==0 else baseline
        asm.write_text(code+trailing)
        run(['gcc','-shared','-fPIC','-nostdlib',str(asm), str(root/'libmemprovider0.so.1'),
             str(root/'libmemprovider1.so.1'),f'-Wl,-soname,libmemtest{i}.so.1,--version-script={mapfile}',
             '-o',str(root/f'{side}-{i}.so')], 'elf.log')
for side in ('base','cand'):
    top=root/side
    top.mkdir()
    provider='\n'.join(f'cp "{root}/libmemprovider{i}.so.1" "%{{buildroot}}/usr/lib/mem-scale/"' for i in (0,1))
    preamble = []
    install = ['mkdir -p "%{buildroot}/usr/lib/mem-scale"',provider]
    files = ['%files\n/usr/lib/mem-scale/libmemprovider*.so.1\n']
    for i in range(400):
        pkg=f'mem-scale-{i:04}'
        path=f'/usr/lib/mem-scale/{pkg}'
        preamble += [f'%package -n {pkg}\nSummary: Synthetic memory-scale object\n%description -n {pkg}\nMemory-scale fixture\n']
        install += [f'mkdir -p "%{{buildroot}}{path}"',f'cp "{root}/{side}-{i%24}.so" "%{{buildroot}}{path}/object.so"']
        if i%2==0:
            install += [f'cp "{root}/{side}-{(i+1)%24}.so" "%{{buildroot}}{path}/alternate.so"']
        files += [f'%files -n {pkg}\n{path}/\n']
    spec=top/'fixture.spec'
    spec.write_text('Name: mem-scale-providers\nVersion: 1\nRelease: 1\nSummary: Synthetic providers\n'
                    'License: MIT\n%description\nSynthetic fixture\n'+'\n'.join(preamble)+'\n%install\n'
                    +'\n'.join(install)+'\n\n'+'\n'.join(files))
    run(['rpmbuild','-bb','--define',f'_topdir {top}','--define',f'_tmppath {root}/tmp','--define','__os_install_post %{nil}',
         '--define','_binary_payload w3.gzdio',str(spec)],f'{side}-rpm.log')
    for n in (200,400):
        out=root/f'{side}-{n}'
        out.mkdir()
        archives=sorted((top/'RPMS').rglob('*.rpm'))
        assert len(archives)==401
        for rpm in archives:
            if rpm.name.startswith('mem-scale-providers') or int(rpm.name.split('-')[2])<n:
                os.link(rpm,out/rpm.name)
        assert len(list(out.iterdir()))==n+1
