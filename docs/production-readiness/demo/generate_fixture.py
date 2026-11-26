#!/usr/bin/env python3
"""Build two local mini RPM repositories holding synthetic, versioned ELF objects."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TOOLS = ('gcc', 'g++', 'rpmbuild', 'rpm', 'rpm2cpio', 'readelf')

BASELINE = '''
extern "C" {
int data_contract[1] = { 1 };
int stable_code() { return 1; }
int stable_symbol() { return 42; }
int legacy_export() { return 7; }
int version_contract() { return 11; }
}
int demo_cpp(int value) { return value + 3; }
'''
CANDIDATE = '''
extern "C" {
int data_contract[2] = { 1, 2 };
int stable_code() {
    volatile int total = 0;
    for (int n = 0; n < 5; ++n) total = total + n;
    return total;
}
int stable_symbol() { return 42; }
int added_export() { return 8; }
int version_contract() { return 11; }
}
int demo_cpp(int value) { return value + 3; }
'''
CONSUMER = '''
extern int legacy_export(void);
int demo_consumer(void) { return legacy_export(); }
'''
BASELINE_MAP = '''
DEMO_1 { global: data_contract; stable_code; stable_symbol; legacy_export; _Z*; };
DEMO_2 { global: version_contract; local: *; } DEMO_1;
'''
CANDIDATE_MAP = '''
DEMO_1 { global: data_contract; stable_code; stable_symbol; added_export; _Z*; };
DEMO_3 { global: version_contract; local: *; } DEMO_1;
'''


def call(argv, directory, env):
    result = subprocess.run(argv, cwd=directory, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=60)
    with (directory/'fixture-build.log').open('a', encoding='utf-8') as log:
        log.write(json.dumps(argv, ensure_ascii=False)+'\n'+result.stdout)
    if result.returncode:
        raise ValueError(f'{Path(argv[0]).name} failed ({result.returncode}); see fixture-build.log')
    return result.stdout.strip()


def build_provider(side, is_candidate, directory, env):
    source = directory/f'{side}.cpp'
    versions = directory/f'{side}.map'
    binary = directory/f'{side}.elf'
    source.write_text(CANDIDATE if is_candidate else BASELINE, encoding='utf-8')
    versions.write_text(CANDIDATE_MAP if is_candidate else BASELINE_MAP, encoding='utf-8')
    call(['g++', '-O0', '-fPIC', '-shared', '-nostdlib', str(source), '-o', str(binary),
          '-Wl,-soname,libdemo-codec.so.1', '-Wl,--version-script='+str(versions)], directory, env)
    return binary


def build_rpm(name, version, artifact, library, relationship, output, work, env):
    spec = work/f'{name}.spec'
    buildroot = work/f'{name}-{version}-root'
    library_dir = buildroot/'usr/lib'
    library_dir.mkdir(parents=True)
    shutil.copyfile(artifact, library_dir/library)
    spec.write_text(f'''Name: {name}
Version: {version}
Release: 1
Summary: Synthetic headquarters demonstration fixture
License: MIT
AutoReqProv: no
{relationship}
%description
Synthetic, analysis-only fixture. Do not install this RPM.
%files
/usr/lib/{library}
''', encoding='utf-8')
    call(['rpmbuild', '-bb', '--noclean', '--buildroot', str(buildroot), '--define', '_topdir '+str(work/'rpm-build'),
          '--define', '_tmppath '+str(work/'tmp'), '--define', '__os_install_post %{nil}',
          '--define', '_build_id_links none',
          '--define', '_buildhost tizen-demo.invalid',
          '--define', 'use_source_date_epoch_as_buildtime 1',
          '--define', 'clamp_mtime_to_source_date_epoch 1', str(spec)],
         work, env)
    candidates = list((work/'rpm-build'/'RPMS').rglob(f'{name}-{version}-1.*.rpm'))
    if len(candidates) != 1:
        raise ValueError(f'Expected one newly built {name} RPM, found {len(candidates)}')
    built, = candidates
    target = output/built.name
    shutil.move(built, target)
    return target


def check_tools():
    return {tool:shutil.which(tool) for tool in TOOLS}


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def generate(output):
    missing = [tool for tool, path in check_tools().items() if path is None]
    if missing:
        raise ValueError('Missing fixture tools: '+', '.join(missing))
    output = output.resolve()
    if any(char in str(output) for char in ('%', '\r', '\n')):
        raise ValueError('Fixture paths cannot contain RPM macro or line-break characters')
    output.mkdir(exist_ok=False)
    work = output/'build'
    work.mkdir()
    (work/'tmp').mkdir()
    env = {key:value for key,value in os.environ.items()
           if key not in ('LD_PRELOAD','LD_LIBRARY_PATH','BASH_ENV','ENV')}
    env |= {'LC_ALL':'C', 'TZ':'UTC', 'SOURCE_DATE_EPOCH':'1704067200', 'TMPDIR':str(work/'tmp')}
    old, new = (build_provider(side, side=='candidate', work, env)
                for side in ('baseline','candidate'))
    consumer_source = work/'consumer.c'
    consumer_source.write_text(CONSUMER, encoding='utf-8')
    consumer = work/'consumer.elf'
    call(['gcc', '-O0', '-fPIC', '-shared', '-nostdlib', str(consumer_source), str(old),
          '-Wl,--no-undefined', '-Wl,-soname,libdemo-client.so.1', '-o', str(consumer)], work, env)
    records = []
    for side, version, binary in (('baseline','1',old),('candidate','2',new)):
        repository = output/side/'local'/'packages'
        repository.mkdir(parents=True)
        provider = build_rpm('demo-codec', version, binary, 'demo-codec.payload',
                             f'Provides: demo-codec-abi = {version}', repository, work, env)
        consumer_rpm = build_rpm('demo-client', version, consumer, 'demo-client.payload',
                                 'Requires: demo-codec-abi', repository, work, env)
        records.extend({'path':str(path.relative_to(output)), 'sha256':sha256(path)} for path in (provider,consumer_rpm))
    proof = {'scope':'SYNTHETIC_RPM_DEMO', 'compiler_target':call(['gcc','-dumpmachine'],work,env),
             'archives':records, 'consumer_elf_sha256':sha256(consumer)}
    (output/'fixture-manifest.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New output directory')
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args.output), indent=2))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f'Fixture generation failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
