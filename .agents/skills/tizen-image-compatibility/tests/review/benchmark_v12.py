#!/usr/bin/env python3
"""Production aggregation/report stress test with synthetic metadata, not Tizen validation."""
import argparse
from collections import Counter
import copy
import csv
import gc
from html.parser import HTMLParser
import json
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from compat.core import DEFAULTS, SCHEMA, finding, write_json, digest
from compat.compare import finalize
from compat.report import build_results, generate
from compat.source import parse_header


class ReportHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.packages = []; self.findings = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'details' and attrs.get('class') == 'package':
            self.packages.append((attrs['data-package-id'], attrs['data-status'], attrs['data-verification']))
        if tag == 'details' and attrs.get('class') == 'finding':
            self.findings.append((attrs['data-finding-id'], attrs['data-status']))


def fixture(packages=2000, symbols=10):
    """Ring of consumer/provider packages; ABI failures, API gaps and an unowned finding."""
    a = dict(schema_version=SCHEMA, image={'name': 'SYNTHETIC metadata baseline'}, elf_objects=[], public_headers=[], packages=[],
             limitations=[{'dimension': 'packages', 'component': 'fixture', 'reason': 'Generated metadata; not queried from RPM or a real Tizen image'}],
             test_results=[], filesystem=[], collection_complete=True,
             package_inventory={'status': 'COMPLETE', 'installed_count': packages, 'source_kind': 'installed_rpmdb', 'reason': 'SIMULATED ownership'})
    fs = []
    for i in range(packages):
        path = f'/usr/lib/libsynthetic{i}.so'; header = f'/usr/include/synthetic{i}.h'
        files = [path, header] if i % 10 == 0 else [path]
        a['packages'].append(dict(name=f'synthetic-{i}', epoch='0', version='1', release='1', arch='x86_64', files=files,
            provides=[], requires=[], conflicts=[], obsoletes=[], collection_status='COMPLETE', evidence=[],
            provenance={'kind': 'installed_rpmdb', 'source': 'SIMULATED metadata, not a queried DB'}))
        a['filesystem'] += [dict(path=p, type='file') for p in files]
        exports = [dict(name=f'public_{j}', type='FUNC', binding='GLOBAL', visibility='DEFAULT', size=0) for j in range(symbols)]
        a['elf_objects'].append(dict(path=path, type='DYN', complete=True, exports=exports, imports=[], needed=[]))
        fs += [finding('abi', path, s['name'], s, None, 'INCOMPATIBLE', 'HIGH') for s in exports]
        if i % 10 == 0:
            a['public_headers'].append(dict(path=header, sha256=digest(b'int api(void);'), origin='runtime_image', **parse_header('int api(void);')))
            fs.append(finding('api', header, 'semantic contract', 'declared', 'unverified', 'UNKNOWN'))
        provider = f'/usr/lib/libsynthetic{(i + 1) % packages}.so'
        f = finding('linking', path, 'baseline consumers on candidate:import:public_0', 'public_0', {'provider': provider}, 'INCOMPATIBLE', 'HIGH')
        f.update(consumer_path=path, consumer_image='baseline', root_consumer=path, root_consumer_image='baseline', provider_path=provider, check_id='import:public_0')
        fs.append(f)
    fs.append(finding('abi', '/opt/unowned.so', 'unowned', 'present', None, 'INCOMPATIBLE'))
    b = copy.deepcopy(a); b['image']['name'] = 'SYNTHETIC metadata candidate'
    for obj in b['elf_objects']: obj['exports'] = []
    config = copy.deepcopy(DEFAULTS); config['analysis']['modes'] = ['abi', 'api', 'linking', 'packages']; config['ci']['minimum_coverage'] = {'abi': 100}
    return a, b, finalize(fs, config), config


def verify_reports(output, expected_ids, package_count):
    """Read serialized reports independently; exact IDs/associations, not just lengths."""
    with (output / 'results.json').open() as stream: result = json.load(stream)
    findings = result['findings']; packages = result['package_results']; inv = result['package_inventory']
    assert Counter(f['id'] for f in findings) == Counter(expected_ids), 'JSON dropped/duplicated findings'
    assert len(packages) == len({p['id'] for p in packages}) == package_count
    assert inv['baseline_package_count'] == inv['candidate_package_count'] == package_count
    assert len(inv['candidate_assessments']) == len(inv['matched_packages']) == package_count
    assert all(v['consistent'] for k, v in inv['count_reconciliation'].items() if k.endswith(':runtime'))
    ids = set(expected_ids)
    associations = set(inv['unassigned_finding_ids'])
    rows_by_id = {p['id']: p for p in packages}
    paths = {e['path']: p['id'] for p in packages for e in p['owned_interfaces']['elf']}
    for p in packages:
        associations.update(p['finding_ids']); associations.update(p['ambiguous_finding_ids'])
        assert p['overall'] == 'INCOMPATIBLE' and p['verification'] == 'PARTIAL'
    assert associations == ids, 'Missing or dangling package/global associations'
    for f in findings:
        if f['dimension'] == 'abi' and f['component'] in paths:
            assert f['id'] in rows_by_id[paths[f['component']]]['finding_ids'], 'ABI finding assigned to wrong owner'
        if f['dimension'] == 'api':
            owners = f['package_ownership']['consumer']['owners']; assert len(owners) == 1
            assert f['id'] in rows_by_id[owners[0]]['finding_ids']
        if f['dimension'] == 'linking':
            assert f['package_ownership']['consumer']['owners'] == [paths[f['consumer_path']]]
            assert f['package_ownership']['candidate_provider']['owners'] == [paths[f['provider_path']]]
    edges = inv['provider_consumers']; assert len(edges) == package_count
    assert {i for edge in edges for i in edge['finding_ids']} == {f['id'] for f in findings if f['dimension'] == 'linking'}
    with (output / 'packages.csv').open() as stream:
        csv_rows = list(csv.DictReader(stream))
    assert Counter(p['id'] for p in csv_rows) == Counter(rows_by_id.keys())
    for row in csv_rows:
        p = rows_by_id[row['id']]
        for field in ('abi', 'api', 'linking'): assert row[field] == p[field]['status']
        for field in ('overall', 'verification', 'baseline_version', 'candidate_version'): assert row[field] == str(p[field])
        assert json.loads(row['finding_ids']) == p['finding_ids']
        assert row['coverage_percent'] == str(p['coverage']['coverage_percent'])
    with (output / 'findings.csv').open() as stream:
        csv_findings = list(csv.DictReader(stream))
    assert Counter(f['id'] for f in csv_findings) == Counter(expected_ids), 'CSV finding loss/duplication'
    statuses = {f['id']: f['status'] for f in findings}
    assert all(f['status'] == statuses[f['id']] for f in csv_findings)
    parser = ReportHTML(); parser.feed((output / 'index.html').read_text())
    assert parser.packages == [(p['id'], p['overall'], p['verification']) for p in packages[:1000]]
    assert parser.findings == [(f['id'], f['status']) for f in findings[:1000]]
    markdown = (output / 'summary.md').read_text()
    for p in packages[:200]:
        assert '| runtime:' + p['name'] + ' | ' in markdown
    assert result['coverage']['abi']['coverage_percent'] == 50
    assert result['quality_gate']['status'] == 'FAIL'
    return {'json_csv_exact_ids': True, 'ownership_and_dependencies': True, 'no_lost_findings': True,
            'html_exact_preview': True, 'markdown_preview': True, 'package_csv_rows': len(csv_rows),
            'findings': len(findings), 'provider_consumer_edges': len(edges)}


def budget_failures(metrics, max_seconds=30, max_rss_mib=768, reference=None, factor=2):
    failures = []
    if metrics['wall_seconds'] > max_seconds: failures.append('wall_seconds exceeds configured budget')
    if metrics['peak_rss_mib'] > max_rss_mib: failures.append('peak_rss_mib exceeds configured budget')
    if reference:
        for key in ('fixture_version', 'packages_per_image', 'exports_per_package'):
            if metrics[key] != reference[key]: raise ValueError('Incomparable benchmark reference: ' + key)
        for key in ('wall_seconds', 'peak_rss_mib'):
            if metrics[key] > reference[key] * factor: failures.append(key + ' regressed beyond reference factor')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--packages', type=int, default=2000); parser.add_argument('--symbols', type=int, default=10)
    parser.add_argument('--max-seconds', type=float, default=30); parser.add_argument('--max-rss-mib', type=float, default=768)
    parser.add_argument('--reference', type=Path); parser.add_argument('--max-regression-factor', type=float, default=2)
    args = parser.parse_args()
    if min(args.packages, args.symbols, args.max_seconds, args.max_rss_mib, args.max_regression_factor) <= 0: parser.error('Counts/budgets must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter(); a, b, fs, config = fixture(args.packages, args.symbols)
    ids = [f['id'] for f in fs]
    assert len(ids) == args.packages * (args.symbols + 1) + (args.packages + 9) // 10 + 1
    result = build_results(a, b, fs, [], [], config); built = time.perf_counter()
    generate(args.output, a, b, result, config); rendered = time.perf_counter()
    del result, a, b, fs; gc.collect()  # Independent readback, without retaining redundant reports.
    checks = verify_reports(args.output, ids, args.packages); completed = time.perf_counter()
    metrics = {'fixture_version': 2, 'fixture': 'SYNTHETIC metadata only; no target execution',
        'packages_per_image': args.packages, 'exports_per_package': args.symbols,
        'build_seconds': round(built - started, 3), 'render_seconds': round(rendered - built, 3),
        'verification_seconds': round(completed - rendered, 3), 'wall_seconds': round(completed - started, 3),
        'peak_rss_mib': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        'checks': checks, 'bytes': {p.name: p.stat().st_size for p in sorted(args.output.iterdir()) if p.is_file()}}
    reference = json.loads(args.reference.read_text()) if args.reference else None
    metrics['budget_failures'] = budget_failures(metrics, args.max_seconds, args.max_rss_mib, reference, args.max_regression_factor)
    metrics['budgets'] = {'max_seconds': args.max_seconds, 'max_rss_mib': args.max_rss_mib, 'reference': str(args.reference) if args.reference else None, 'factor': args.max_regression_factor}
    metrics['exit_code'] = 1 if metrics['budget_failures'] else 0
    write_json(args.output / 'benchmark.json', metrics); print(json.dumps(metrics, indent=2))
    return metrics['exit_code']

if __name__ == '__main__': sys.exit(main())
