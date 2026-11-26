#!/usr/bin/env python3
"""Package a checked Git tree's standalone Tizen skill deterministically."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

SKILL = '.agents/skills/tizen-image-compatibility'
NAME = 'tizen-image-compatibility'
TOP_LEVEL = {'SKILL.md', 'VERSION', 'config.yaml', 'requirements.txt'}
INCLUDED_DIRS = {'agents', 'assets', 'references', 'scripts', 'tests'}
EXAMPLES = {'examples/README.md', 'examples/synthetic-config.yaml', 'examples/runtime-workflow.json', 'examples/workflow.json'}
EXCLUDED = {'tests/test_arm_smoke_admission.py', 'scripts/arm_smoke_admission'}
REVIEW_TESTS = {'tests/review/benchmark_v12.py'}
PRIVATE = re.compile(
    rb'/(?:home|Users)/[a-zA-Z0-9_.-]+/|\.local-backups/|\b(?:192\.168|10)\.\d{1,3}\.\d{1,3}'
    rb'|\b172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}'
    rb'|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[a-zA-Z0-9]{30,}|\bgithub_pat_[a-zA-Z0-9_]{30,}'
)


def included(path):
    if path in EXCLUDED or path.startswith('scripts/arm_smoke_admission/'):
        return False
    if path.startswith('tests/review/'):
        return path in REVIEW_TESTS
    if path.startswith('examples/'):
        return path in EXAMPLES
    return path in TOP_LEVEL or path.partition('/')[0] in INCLUDED_DIRS


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def files_from_git(tree):
    data = subprocess.check_output(['git', 'archive', '--format=tar', tree, SKILL])
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as source:
        for entry in source:
            if entry.isdir():
                continue
            relative = str(PurePosixPath(entry.name).relative_to(SKILL))
            if not included(relative):
                continue
            if (not entry.isfile() or entry.size > 512 * 1024
                    or any(part.startswith('.') or part == '__pycache__' for part in PurePosixPath(relative).parts)
                    or relative.endswith(('.pyc', '.sqlite', '.elf', '.so', '.rpm'))):
                raise ValueError('Prohibited package entry: '+relative)
            payload = source.extractfile(entry).read()
            if b'\x00' in payload or PRIVATE.search(payload):
                raise ValueError('Release entry needs a content review: '+relative)
            yield relative, entry.mode, payload


def package(tree, destination):
    files = sorted(files_from_git(tree))
    entries = {path: data for path, _, data in files}
    if not TOP_LEVEL <= entries.keys():
        raise ValueError('Missing required Skill files')
    version = entries['VERSION'].decode('ascii').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION must be a semantic release version')
    destination.mkdir(parents=True, exist_ok=False)
    filename = f'{NAME}-v{version}.tar.gz'
    archive = destination/filename
    manifest = destination/'PACKAGE_FILES.txt'
    rows = ['SHA256  MODE  BYTES  PATH']
    with archive.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as output:
            for path, mode, payload in files:
                name = f'{NAME}/{path}'
                entry = tarfile.TarInfo(name)
                entry.mode = 0o755 if mode & 0o111 else 0o644
                entry.size = len(payload)
                output.addfile(entry, io.BytesIO(payload))
                rows.append(f'{sha256(payload)}  {entry.mode:o}  {len(payload)}  {name}')
    manifest.write_text('\n'.join(rows)+'\n', encoding='utf-8')
    checksums = destination/'SHA256SUMS'
    checksums.write_text(''.join(f'{sha256(path.read_bytes())}  {path.name}\n'
                                for path in (archive,manifest)), encoding='utf-8')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', default='HEAD', help='Commit or reviewed Git tree object')
    parser.add_argument('--output', required=True, type=Path, help='New output directory')
    args = parser.parse_args()
    print(package(args.tree, args.output))


if __name__ == '__main__':
    main()
