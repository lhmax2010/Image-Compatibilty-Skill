#!/usr/bin/env python3
"""Build and browse offline impact associations from a validated v1.3 report."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from compat.impact_browser import ImpactBrowser
from compat.impact_store import ENGINE, build
from compat.report_browser import serve
from compat.report_io import ResourceLimit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=ENGINE)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('build')
    create.add_argument('--input', type=Path, required=True, help='Validated enhanced v1.3 report')
    create.add_argument('--output', type=Path, required=True, help='New sidecar directory')
    create.add_argument('--scope-config', type=Path)
    create.add_argument('--replay-root', action='append', default=[],
                        help='Exact baseline ELF path to replay with existing Phase 7A manifests')
    for name in ('serve', 'query'):
        command = sub.add_parser(name)
        command.add_argument('--report', type=Path, required=True)
        command.add_argument('--impact', type=Path, required=True)
        if name == 'serve':
            command.add_argument('--port', type=int, default=8765)
        else:
            command.add_argument('route')
            command.add_argument('--param', action='append', default=[], metavar='KEY=VALUE')
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            result = build(args.input, args.output, args.scope_config, args.replay_root,
                           progress=lambda stage: print(stage, file=sys.stderr, flush=True))
        elif args.command == 'serve':
            serve(args.report, args.port, args.impact)
            return 0
        else:
            params = {}
            for pair in args.param:
                key, separator, value = pair.partition('=')
                if not separator:
                    raise ValueError('Query parameters must be KEY=VALUE')
                params[key] = [value]
            result = ImpactBrowser(args.report, args.impact).query(args.route, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, ResourceLimit) as exc:
        parser.exit(2, f'Impact error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
