#!/usr/bin/env python3
"""Create clearly synthetic root filesystems; never pretend these are Tizen results."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

FIXTURES = Path(__file__).resolve().parents[1] / 'assets' / 'synthetic-fixture'


def create(destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Fixture destination must be empty')
    compiler = shutil.which('gcc') or shutil.which('cc')
    if not compiler:
        raise ValueError('A host C compiler is needed ONLY to build synthetic fixture data')
    for label in ('baseline', 'candidate'):
        root = destination / label
        for directory in ('usr/lib', 'usr/include', 'usr/bin', 'etc', 'usr/lib/systemd/system', 'usr/share/dbus-1/interfaces'):
            (root / directory).mkdir(parents=True, exist_ok=True)
        subprocess.run([compiler, '-shared', '-fPIC', '-g', '-nostdlib', str(FIXTURES / (label + '.c')),
            '-Wl,-soname,libsynthetic.so.1', '-Wl,--version-script=' + str(FIXTURES / 'exports.map'),
            '-o', str(root / 'usr/lib/libsynthetic.so.1')], check=True, timeout=60)
        (root / 'usr/lib/libsynthetic.so').symlink_to('libsynthetic.so.1')
        header = 'int public_add(int a, int b);\n' + ('int public_removed(void);\n' if label == 'baseline' else 'int public_added(void);\n')
        (root / 'usr/include/synthetic.h').write_text(header)
        (root / 'etc/os-release').write_text('NAME="SYNTHETIC FIXTURE - NOT TIZEN"\nVERSION_ID="1"\n')
        (root / 'etc/synthetic.conf').write_text('[feature]\nenabled=' + ('yes' if label == 'baseline' else 'no') + '\n')
        (root / 'usr/lib/systemd/system/synthetic.service').write_text('[Service]\nExecStart=/usr/bin/synthetic\nUser=' + ('root' if label == 'baseline' else 'nobody') + '\n')
        (root / 'usr/share/dbus-1/interfaces/synthetic.xml').write_text('<node name="/test"><interface name="org.synthetic.Test"><method name="Call"><arg type="' + ('s' if label == 'baseline' else 'i') + '" direction="in"/></method></interface></node>')
        if label == 'baseline':
            command = root / 'usr/bin/synthetic'
            command.write_text('#!/bin/sh\n# Fixture only; never executed\n')
            command.chmod(0o755)
    print(f'Synthetic fixture written to {destination}; NOT a real Tizen compatibility result.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        create(args.destination)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
