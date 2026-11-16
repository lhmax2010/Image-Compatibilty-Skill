#!/usr/bin/env python3
"""Offline-first Tizen image compatibility CLI. See --help and SKILL.md."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

from compat.collect import collect
from compat.compare import advanced_abi, compare_static, finalize
from compat.core import (DIMENSIONS, SEVERITIES, InfrastructureError, InputError, Tools,
                         finding, load_config, read_manifest)
from compat.images import Image
from compat.report import build_results, generate
from compat.testing import run_matrix


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, help='Baseline rootfs, TAR, SquashFS or RPM collection')
    p.add_argument('--candidate', type=Path, help='Candidate rootfs, TAR, SquashFS or RPM collection')
    p.add_argument('--baseline-manifest', type=Path, help='Reuse collected baseline JSON')
    p.add_argument('--candidate-manifest', type=Path, help='Reuse collected candidate JSON')
    p.add_argument('--mode', choices=('quick', 'static', 'runtime', 'full'), default='static')
    p.add_argument('--output', type=Path, default=Path('compat-report'))
    p.add_argument('--config', type=Path)
    p.add_argument('--cache', type=Path, help='Optional incremental ELF cache outside source images')
    p.add_argument('--strict', action='store_true', help='Also fail on UNKNOWN checks, irrespective of severity')
    p.add_argument('--fail-on', choices=SEVERITIES)
    p.add_argument('--exclude', default='', help='Comma-separated dimensions')
    p.add_argument('--baseline-sysroot', type=Path)
    p.add_argument('--candidate-sysroot', type=Path)
    p.add_argument('--gcc', type=Path, help='Explicit GCC C compiler')
    p.add_argument('--gxx', type=Path, help='Explicit GCC C++ compiler')
    p.add_argument('--clang', type=Path, help='Explicit Clang C compiler')
    p.add_argument('--clangxx', type=Path, help='Explicit Clang C++ compiler')
    p.add_argument('--list-tools', action='store_true', help='Discover tools without requiring images')
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    tools = None
    try:
        config = load_config(args.config)
        excluded = {x.strip() for x in args.exclude.split(',') if x.strip()}
        if excluded - set(DIMENSIONS):
            raise InputError('Unknown excluded dimensions: ' + ','.join(sorted(excluded - set(DIMENSIONS))))
        config['analysis']['modes'] = [x for x in config['analysis']['modes'] if x not in excluded]
        config['ci']['strict'] |= args.strict
        if args.fail_on:
            config['ci']['fail_on'] = args.fail_on
        for label in ('baseline', 'candidate'):
            root = getattr(args, label + '_sysroot')
            if root:
                config['cross_compilation']['sysroots'][label] = str(root.resolve())
        for flag, family, language in (('gcc', 'gcc', 'c'), ('gxx', 'gcc', 'cpp'), ('clang', 'clang', 'c'), ('clangxx', 'clang', 'cpp')):
            path = getattr(args, flag)
            if path:
                config['cross_compilation']['compilers'].setdefault(family, {})[language] = str(path.resolve())
        paths = [p.resolve() for p in (args.baseline, args.candidate, args.baseline_sysroot, args.candidate_sysroot) if p]
        paths += [Path(p).resolve() for p in config['cross_compilation']['sysroots'].values()]
        output = args.output.resolve()
        for writable in [output] + ([args.cache.resolve()] if args.cache else []):
            for source in paths:
                if writable == source or (source.is_dir() and writable.is_relative_to(source)):
                    raise InputError('Output/cache must be outside all source images and SDK sysroots')
        # Report overwrites must not destroy a reused manifest or its evidence directory.
        for manifest in (args.baseline_manifest, args.candidate_manifest):
            if manifest and output == manifest.resolve().parent:
                raise InputError('Write reused comparisons to a new output directory')
        if not args.list_tools and not ((args.baseline and args.candidate) or (args.baseline_manifest and args.candidate_manifest)):
            raise InputError('Supply both --baseline/--candidate, or both --baseline-manifest/--candidate-manifest')
        if (args.baseline or args.candidate) and (args.baseline_manifest or args.candidate_manifest):
            raise InputError('Choose image inputs or manifest inputs, not both')
        if output.exists() and any(output.iterdir()):
            raise InputError('Output directory must be empty; use a new report directory (cache can be reused).')
        output.mkdir(parents=True, exist_ok=True)
        tools = Tools(output, config)
        tools.discover()
        if args.list_tools:
            print(json.dumps(tools.versions, indent=2))
            return 0
        with tempfile.TemporaryDirectory(prefix='tizen-compat-') as temporary:
            workspace = Path(temporary)
            tools.aliases[str(workspace)] = '<workspace>'
            roots = None
            if args.baseline_manifest:
                a, b = read_manifest(args.baseline_manifest), read_manifest(args.candidate_manifest)
                for manifest_path in (args.baseline_manifest, args.candidate_manifest):
                    original = manifest_path.parent / 'evidence'
                    if original.is_dir():
                        for item in original.glob('*.txt'):
                            if item.is_file() and not item.is_symlink():
                                shutil.copyfile(item, tools.raw / item.name)
            else:
                roots = (Image(args.baseline, workspace, tools, 'baseline'), Image(args.candidate, workspace, tools, 'candidate'))
                a, b = (collect(image, config['comparison'][label + '_name'], label, args.mode, tools, workspace, args.cache)
                        for image, label in zip(roots, ('baseline', 'candidate')))
            findings = compare_static(a, b, config)
            if roots and args.mode != 'quick' and 'abi' in config['analysis']['modes']:
                findings += advanced_abi(a, b, roots, tools)
            if not roots:
                # Preserve earlier executable results; do not claim to rerun target tests.
                tests = a['test_results'] + b['test_results']
                matrix = a.get('cross_matrix') or [{'compiler': compiler, 'image': image, 'header_status': 'UNKNOWN', 'runtime_status': 'UNKNOWN',
                           'status': 'UNKNOWN', 'reason': 'Manifest-only comparison; no new executions.'}
                          for compiler in ('gcc', 'clang') for image in ('baseline', 'candidate')]
                for test in tests:
                    if test['status'] == 'INCOMPATIBLE':
                        findings.append(finding(test.get('dimension', 'runtime' if test['kind'] == 'runtime' else 'headers'),
                            test.get('name', test['id']), 'recorded test:' + test['image'], None, test,
                            'INCOMPATIBLE', 'HIGH', 'reused test evidence; not rerun', test.get('evidence')))
                findings.append(finding('runtime', '*', 'manifest reuse', None, 'No tests rerun; original test results retained.', 'UNKNOWN', 'INFO'))
            elif set(config['analysis']['modes']) & {'headers', 'runtime'}:
                tests, matrix, test_findings = run_matrix((a, b), roots, tools, args.mode)
                findings += test_findings
            else:
                tests, matrix = [], []
            for cell in matrix:
                if cell['status'] == 'UNKNOWN':
                    findings.append(finding('runtime', cell['image'], cell['compiler'] + ':cross-compatibility coverage', None,
                        cell.get('runtime_reason', cell.get('reason', 'Incomplete matrix')), 'UNKNOWN', 'INFO'))
            findings = finalize(findings, config)
            a['cross_matrix'] = b['cross_matrix'] = matrix
            result = build_results(a, b, findings, tests, matrix, config)
            generate(output, a, b, result, config)
            print(f"{result['status']}: {len(findings)} findings; report {output / 'index.html'}")
            threshold = SEVERITIES.index(config['ci']['fail_on'])
            fail = any(f['status'] == 'INCOMPATIBLE' and SEVERITIES.index(f['severity']) <= threshold for f in findings)
            fail |= config['ci']['strict'] and any(f['status'] == 'UNKNOWN' for f in findings)
            return 1 if fail else 0
    except (InputError, ValueError) as exc:
        print(f'Input error: {exc}', file=sys.stderr)
        return 2
    except (OSError, InfrastructureError) as exc:
        print(f'Infrastructure error: {exc}', file=sys.stderr)
        return 3
    finally:
        if tools:
            tools.flush()


if __name__ == '__main__':
    raise SystemExit(main())
