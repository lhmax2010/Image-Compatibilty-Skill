#!/usr/bin/env python3
"""Inspect or safely prepare an offline Tizen image; never mount or boot it."""
import argparse
from pathlib import Path
import sys
import tarfile

from compat.core import InfrastructureError, Tools, load_config
from compat.flash import PreparationError
from compat.preparation import MANIFEST, SCOPES, identity, prepare


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path, help='Original image or already extracted Rootfs')
    parser.add_argument('--output', type=Path, help='New directory for normalized input and extraction manifest')
    parser.add_argument('--inspect', action='store_true', help='Identify and validate known layers without invoking a filesystem extractor')
    parser.add_argument('--identity-only', action='store_true', help='Print the SHA256 of a file or directory for a build receipt')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--replacement', type=Path, help='Explicitly provided same-build input')
    parser.add_argument('--replacement-kind', choices=SCOPES)
    parser.add_argument('--provenance', type=Path, help='Trusted build receipt binding original and replacement SHA256')
    parser.add_argument('--build-id', help='Expected build identity for replacement')
    args = parser.parse_args(argv)
    args.image = args.image.resolve()
    alternative = (args.replacement, args.replacement_kind, args.provenance, args.build_id)
    if any(alternative) and (not all(alternative) or args.inspect or args.identity_only):
        parser.error('Replacement needs path, kind, provenance and build ID, without inspection flags')
    if args.identity_only and (args.inspect or args.output):
        parser.error('--identity-only does not take --inspect or --output')
    if not args.identity_only and not args.output:
        parser.error('--output is required for preparation or inspection')
    tools = None
    try:
        config = load_config(args.config)
        if args.identity_only:
            print(identity(args.image, config)['sha256'])
            return 0
        output = args.output.resolve()
        inputs = [args.image] + [p.resolve() for p in (args.replacement, args.provenance) if p]
        if any(output == p or p.is_relative_to(output) or output.is_relative_to(p) for p in inputs):
            raise PreparationError('PREPARATION_OUTPUT_OVERLAP', 'Choose a new output outside each input')
        output.mkdir(parents=True, exist_ok=False)
        if all(alternative):
            alternative = (args.replacement.resolve(), args.replacement_kind, args.provenance.resolve(), args.build_id)
        tools = Tools(output, config)
        record = prepare(args.image, output, tools, inspect_only=args.inspect, replacement=alternative if all(alternative) else None)
        print(record['status'], record.get('blocker', ''), output / MANIFEST)
        return 2 if record['status'] == 'PARTIAL' else 0
    except (OSError, ValueError, InfrastructureError, tarfile.TarError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if tools:
            tools.flush()


if __name__ == '__main__':
    raise SystemExit(main())
