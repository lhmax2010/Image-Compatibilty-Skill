#!/usr/bin/env python3
"""Plan, admit or run a frozen SR probe over an existing authorized SDB connection."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from compat import probe_bundle
from compat.core import DEFAULTS, InputError, Tools
from compat.sdb_runtime import PHASE8E_MANIFEST_SHA256, SdbTransport, handle
from frozen_runtime import load_bundle, overlaps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'bundle', 'enrollment', 'output'):
        parser.add_argument(f'--{name}', required=True, type=Path)
    parser.add_argument('--artifact', required=True)
    parser.add_argument('--manifest-sha256', help='Independent digest for a versioned probe bundle')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--admit', action='store_true', help='Use the enrolled device for read-only admission')
    mode.add_argument('--execute', action='store_true', help='Execute exactly one explicitly authorized artifact')
    args = parser.parse_args()
    bundle, output = args.bundle.resolve(), args.output.resolve()
    try:
        if overlaps(bundle, output) or any(p.resolve().is_relative_to(output)
                                           for p in (args.manifest, args.enrollment)):
            raise InputError('Output must be a new directory separate from the frozen inputs')
        if args.manifest_sha256 and args.manifest_sha256 != PHASE8E_MANIFEST_SHA256:
            if args.bundle.is_symlink():
                raise InputError('Bundle root cannot be a symbolic link')
            artifacts = probe_bundle.load(args.manifest, args.manifest_sha256, bundle)
        else:
            _, artifacts, _ = load_bundle(args.manifest, PHASE8E_MANIFEST_SHA256, bundle)
        if args.artifact not in artifacts:
            raise InputError('Artifact is absent from the pinned manifest')
        artifact = artifacts[args.artifact]
        spec = json.loads(args.enrollment.read_bytes())
        if not isinstance(spec, dict):
            raise InputError('Enrollment must be a JSON object')
        sdb = shutil.which('sdb') if args.admit or args.execute else None
        if (args.admit or args.execute) and not sdb:
            raise InputError('SDB is unavailable')
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        tools = Tools(output, DEFAULTS)
        try:
            result = handle(SdbTransport(tools, sdb, spec.get('sdb_serial')), spec, artifact,
                            bundle/artifact['bundle_path'], output, read_device=args.admit, execute=args.execute)
        finally:
            tools.flush()
        print(output/'runtime.json')
        return result
    except (InputError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'SDB runtime input error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
