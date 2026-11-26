#!/usr/bin/env python3
"""Offline report enhancement; never collects, analyzes or executes image contents."""
import argparse
from pathlib import Path
from compat.report_enhance import build
from compat.report_browser import serve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    render = sub.add_parser('build', help='Project an existing schema-1.2 report into a NEW directory')
    render.add_argument('--input', required=True, type=Path)
    render.add_argument('--output', required=True, type=Path)
    browse = sub.add_parser('serve', help='Read-only interactive browser; loopback only, no Internet')
    browse.add_argument('--report', required=True, type=Path)
    browse.add_argument('--port', type=int, default=8765)
    browse.add_argument('--impact', type=Path, help='Mount a validated v1.4 impact sidecar')
    browse.add_argument('--history', type=Path, help='Mount a completed historical regression report')
    args = parser.parse_args()
    if args.command == 'build':
        if (args.input/'rpm-repository.json').is_file():
            from compat.repository_browser import build as build_repository
            build_repository(args.input,args.output)
        else:
            build(args.input, args.output)
    else:
        serve(args.report, args.port, args.impact, args.history)


if __name__ == '__main__':
    main()
