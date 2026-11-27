"""Generate and analyze real synthetic RPM repositories without running the payloads."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess


def run(argv, log, expected=0):
    with log.open('w') as stream:
        completed = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if completed.returncode != expected:
        raise SystemExit(f'{argv[0]} returned {completed.returncode}. See {log}.')


def build_elf(root):
    version = root/'exports.map'
    version.write_text('SCALE_1 { global: wp2_*; local: *; };\n')
    for side,n in (('baseline',100),('candidate',99)):
        source = root/f'{side}.c'
        source.write_text(''.join(f'int wp2_{i}(void) {{ return {i}; }}\n' for i in range(n)))
        run(['gcc','-fPIC','-shared','-nostdlib',str(source),
             f'-Wl,-soname,libwp2-provider.so.1,--version-script={version}',
             '-o',str(root/f'{side}-provider')],root/f'{side}-elf.log')
    source = root/'consumer.s'
    source.write_text('.section .data\n.globl references\nreferences:\n'+
                      ''.join(f'.quad wp2_{i}\n' for i in range(100))+
                      '.section .note.GNU-stack,"",@progbits\n')
    run(['gcc','-shared','-nostdlib',str(source),str(root/'baseline-provider'),
         '-o',str(root/'consumer')],root/'consumer.log')


def package(root, side, count):
    top = root/side
    top.mkdir()
    tmp = top/'tmp'
    tmp.mkdir()
    provider = f'cp "{root}/{side}-provider" "%{{buildroot}}/usr/lib/wp2-scale/libwp2-provider.so.1"'
    install = ['mkdir -p "%{buildroot}/usr/lib/wp2-scale"',provider]
    preamble = []
    files = ['%files\n/usr/lib/wp2-scale/libwp2-provider.so.1\n']
    for i in range(count):
        name = f'wp2-scale-{i:04d}'
        relative = f'/usr/lib/wp2-scale/{name}'
        preamble.append(f'%package -n {name}\nSummary: Synthetic scale consumer\n%description -n {name}\nSynthetic fixture\n')
        install += [f'mkdir -p "%{{buildroot}}{relative}"',
                    f'cp "{root}/consumer" "%{{buildroot}}{relative}/consumer.so"']
        if i % 2 == 0:
            install.append(f'cp "{root}/consumer" "%{{buildroot}}{relative}/alternate.so"')
        files.append(f'%files -n {name}\n{relative}/\n')
    spec = top/'fixture.spec'
    spec.write_text('Name: wp2-scale-provider\nVersion: 1\nRelease: 1\nSummary: Synthetic scale provider\n'
                    'License: MIT\n%description\nSynthetic fixture\n'+'\n'.join(preamble)+
                    '\n%install\n'+'\n'.join(install)+'\n\n'+'\n'.join(files))
    run(['/usr/bin/time','-v','-o',str(top/'build.time'),'rpmbuild','-bb','--define',f'_topdir {top}',
         '--define',f'_tmppath {tmp}','--define','__os_install_post %{nil}',
         '--define','_binary_payload w3.gzdio',str(spec)],top/'build.log')
    return top/'RPMS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--packages', type=int, default=1000)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True)
    tmp = root/'tmp'
    tmp.mkdir()
    os.environ['TMPDIR'] = str(tmp)
    build_elf(root)
    a,b = (package(root, side, args.packages) for side in ('baseline','candidate'))
    skill = Path(__file__).resolve().parents[1]
    report = root/'report'
    config = root/'workflow.json'
    config.write_text(json.dumps({'baseline': str(a), 'candidate': str(b), 'output': str(report),
                                  'objective':'EXPORT_SYMBOLS','rpm_mode':'payload'}))
    run(['/usr/bin/time','-v','-o',str(root/'analysis.time'),'python3','-B',str(skill/'scripts/compat_workflow.py'),
         'run','--config',str(config)],root/'analysis.log',expected=1)
    summary=json.loads((report/'run-summary.json').read_text())
    requirements=summary['statistics']['requirements']
    with (report/'requirement-findings.csv').open(newline='') as stream:
        rows=sum(1 for _ in csv.DictReader(stream))
    assert summary['statistics']['baseline']['rpm_total']==args.packages+1
    assert summary['statistics']['candidate']['rpm_total']==args.packages+1
    assert rows==requirements['finding_count']==args.packages+(args.packages+1)//2
    assert requirements['stored_examples']==min(1000,rows)
    output={'summary':summary,'requirement_csv_rows':rows,
            'report_bytes':sum(p.stat().st_size for p in report.rglob('*') if p.is_file())}
    (root/'measurements.json').write_text(json.dumps(output,indent=2)+'\n')


if __name__ == '__main__':
    main()
