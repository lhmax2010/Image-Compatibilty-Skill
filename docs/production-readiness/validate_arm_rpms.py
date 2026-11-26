#!/usr/bin/env python3
"""Build and analyze two synthetic ARMv7 RPMs using authorized local SR SDKs."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2),b''):
            digest.update(chunk)
    return digest.hexdigest()


def command(argv, output, name, *, expected=0, env=None):
    result = subprocess.run(argv, capture_output=True, text=True, errors='replace', timeout=90, env=env)
    (output/(name+'.log')).write_text(result.stdout+result.stderr)
    if result.returncode!=expected:
        raise RuntimeError(f'{name} returned {result.returncode}. See its log.')
    return result.stdout


def package(output, sdk, label, compiler, version):
    work = output/label
    work.mkdir()
    source = 'int shared_symbol(void) { return 1; }\n'
    source += f'int {"arm_removed" if version==1 else "arm_added"}(void) {{ return {version}; }}\n'
    (work/'contract.c').write_text(source)
    (work/'versions.map').write_text('ARM_FIXTURE_1 { global: shared_symbol; arm_*; local: *; };\n')
    binary = work/'contract.payload'
    opts = ['--no-default-config','--target=armv7l-tizen-linux-gnueabi','-fuse-ld=lld'] if label=='candidate' else []
    boundary = ['bwrap','--unshare-user','--unshare-net','--unshare-pid','--die-with-parent','--ro-bind',str(sdk/'host'),'/','--ro-bind',str(sdk/'sysroot'),'/sysroot',
                '--bind',str(work),'/work','--dev','/dev','--proc','/proc','--chdir','/work','--clearenv','--setenv','PATH','/usr/bin',
                '--setenv','LC_ALL','C','--setenv','TMPDIR','/work','--','/usr/bin/'+compiler]
    cmd = ['--sysroot=/sysroot','-march=armv7-a','-mfloat-abi=softfp','-mfpu=neon','-mthumb','-fPIC','-nostdlib','-shared',
           '-Wl,--version-script=/work/versions.map','-Wl,-soname,libacceptance.so.1','/work/contract.c','-o','/work/contract.payload']
    compiler_version = command(boundary+opts+['--version'],work,'compiler-version').splitlines()[0]
    command(boundary+opts+cmd,work,'compile-link')
    descriptor = command(['readelf','-WhAdV','--dyn-syms',str(binary)],work,'readelf')
    if not all(pattern in descriptor for pattern in ('ELF32','Version5 EABI','Tag_CPU_arch: v7','ARM_FIXTURE_1')) or not re.search(r'Machine:\s+ARM\b',descriptor) or 'Tag_ABI_VFP_args: VFP registers' in descriptor:
        raise ValueError('Expected ARMv7/EABI5/Base PCS shared ELF')
    spec = work/'fixture.spec'
    spec.write_text(f'''Name: arm-payload-acceptance
Version: {version}
Release: 1
Summary: Synthetic ARMv7 ABI acceptance fixture
License: MIT
%description
Synthetic ARMv7 ABI acceptance fixture
%install
mkdir -p "%{{buildroot}}/usr/lib"
cp "{binary}" "%{{buildroot}}/usr/lib/contract.payload"
%files
/usr/lib/contract.payload
''')
    command(['rpmbuild','-bb','--target','armv7l-linux','--define','_topdir '+str(work),
             '--define','_tmppath '+str(work),'--define','__os_install_post %{nil}',str(spec)],work,'rpmbuild')
    (rpm,) = (work/'RPMS').rglob('*.rpm')
    provenance = {'rpm_sha256':sha(rpm),'elf_sha256':sha(binary),'compiler_version':compiler_version,
                  'compiler_sha256':sha((sdk/'host/usr/bin'/compiler).resolve()),'compiler_args':opts+cmd}
    return rpm, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gcc-sdk', type=Path, required=True)
    parser.add_argument('--llvm-sdk', type=Path, required=True)
    parser.add_argument('--skill', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    gcc, a = package(out,args.gcc_sdk.resolve(),'baseline','armv7l-tizen-linux-gnueabi-gcc',1)
    llvm, b = package(out,args.llvm_sdk.resolve(),'candidate','clang',2)
    report = out/'report'
    options = {'baseline':str(gcc),'candidate':str(llvm),'output':str(report),'objective':'EXPORT_SYMBOLS'}
    config = out/'run.json'
    config.write_text(json.dumps(options))
    command([sys.executable,str(args.skill.resolve()/'scripts/compat_workflow.py'),'run','--config',str(config)],out,'workflow',expected=1,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    summary = json.loads((report/'run-summary.json').read_text())
    if summary['objective_completion']!='COMPLETE' or summary['compatibility_status']!='INCOMPATIBLE':
        raise ValueError('ARM export objective failed to observe the controlled break')
    with (report/'symbol-differences.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    for side, expected, name, rpm, proof in (('baseline','MISSING','arm_removed',gcc,a),('candidate','ADDED','arm_added',llvm,b)):
        manifest = json.loads((report/(side+'-manifest.json')).read_text())
        (elf,) = manifest['elf_objects']
        (archive,) = manifest['repository']['archives']
        if elf['machine']!='ARM' or elf['sha256']!=proof['elf_sha256'] or archive['package']['arch']!='armv7l' or sha(rpm)!=proof['rpm_sha256']:
            raise ValueError('Wrong architecture or changed input identity')
        if not any(row['role']=='EXPORT' and row['change']==expected and name in row[side] for row in rows):
            raise ValueError('Expected ARM export observation is missing')
    (out/'validation.json').write_text(json.dumps({'status':'PASS','baseline':a,'candidate':b,'report':summary},indent=2)+'\n')
    print(out/'validation.json')


if __name__=='__main__':
    main()
