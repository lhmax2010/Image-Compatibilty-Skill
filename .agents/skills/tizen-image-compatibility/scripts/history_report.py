#!/usr/bin/env python3
"""Compare original Findings across two validated offline reports."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from compat.history import HistoryBrowser, build_history
from compat.report_io import ResourceLimit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build')
    for flag in ('before', 'after', 'output'):
        build.add_argument('--' + flag, required=True, type=Path)
    build.add_argument('--scope', required=True)
    build.add_argument('--fail-on', choices=('introduced', 'observed-risk'))
    query = commands.add_parser('query')
    query.add_argument('--report', type=Path, required=True)
    query.add_argument('route', choices=('overview', 'entries'))
    query.add_argument('--change', default='')
    query.add_argument('--limit', type=int, default=50)
    query.add_argument('--after', type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.command == 'query':
            info = HistoryBrowser(args.report).query(args.route, {'change': [args.change], 'limit': [args.limit], 'after': [args.after]})
        else:
            info = build_history(args.before, args.after, args.output, args.scope)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        if args.command == 'build' and args.fail_on:
            changes = info['summary']['change']
            return int(bool(changes.get('INTRODUCED') or args.fail_on == 'observed-risk' and changes.get('NEW_UNPAIRED_RISK')))
        return 0
    except (ValueError, KeyError) as error:
        print(f'Input error: {error}', file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, ResourceLimit) as error:
        print(f'Infrastructure error: {error}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
