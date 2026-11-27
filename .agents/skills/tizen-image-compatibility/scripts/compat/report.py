"""Machine-readable and escaped, self-contained human reports."""
from __future__ import annotations

from collections import Counter
from itertools import islice
import csv
import html
import json
from pathlib import Path
from typing import Any
from .coverage import coverage_report
from .package_analysis import analyze_packages
from .profile import comparison_profile
from .linker import summarize_unknowns
from .report_io import FINDING_DETAIL_COLUMNS, finding_cells
from .core import DIMENSIONS, SCHEMA, STATUSES, canonical, expected_collectors, write_json


def collector_execution(a, b, config):
    collectors = {}
    states = set()
    for side, manifest in (('baseline', a), ('candidate', b)):
        recorded = manifest.get('collector_execution', {})
        records = collectors[side] = {}
        expected = expected_collectors(config)
        if manifest.get('repository'):
            expected = sorted(set(expected) | {'rpm','rpm2cpio'})
        for tool in expected:
            entry = recorded.get(tool)
            if entry is None:
                entry = {'status': 'UNKNOWN', 'recorded': False, 'reason_code': 'MISSING_RECEIPT',
                         'reason': 'No execution receipt for this collector and image'}
            records[tool] = entry
            if entry.get('applicable') is not False:
                states.add(entry['status'])
    if 'FAILED' in states:
        status = 'FAILED'
    elif 'PARTIAL' in states or ('COMPLETE' in states and len(states) > 1):
        status = 'PARTIAL'
    elif 'UNKNOWN' in states:
        status = 'UNKNOWN'
    elif 'COMPLETE' in states:
        status = 'COMPLETE'
    else:
        status = 'NOT_EXECUTED'
    return {'status': status, 'collectors': collectors,
            'fail_on_collector_failure': config['ci'].get('fail_on_collector_failure', True)}


def build_results(a: dict[str, Any], b: dict[str, Any], findings: list[dict[str, Any]],
                  tests: list[dict[str, Any]], matrix: list[dict[str, Any]], config: dict[str, Any], *,
                  repository=None) -> dict[str, Any]:
    if len({f['id'] for f in findings}) != len(findings):
        raise ValueError('Duplicate finding IDs: finalize findings before report aggregation')
    counts = Counter(f['status'] for f in findings)
    test_counts = Counter(t['status'] for t in tests)
    expected = a.get('expected_tests', []) + b.get('expected_tests', [])
    status = 'INCOMPATIBLE' if counts['INCOMPATIBLE'] else 'UNKNOWN' if counts['UNKNOWN'] else 'COMPATIBLE' if findings else 'UNKNOWN'
    views = [a,b]
    if repository:
        # Use the reconciled package-scoped pairs for coverage only. Source
        # manifests retain their original archive identities and paths.
        views = []
        for side, manifest in zip(('baseline','candidate'),(a,b)):
            names = {p[side+'_object']:p['component'] for p in repository['elf_pairs'] if p[side+'_object']}
            views.append(manifest | {'elf_objects':[obj | {'path':names.get(obj['path'],obj['path'])}
                                                     for obj in manifest['elf_objects']]})
    coverage, gate = coverage_report(*views, findings, tests, matrix, config)
    execution = collector_execution(a, b, config)
    execution_gate = 'FAIL' if execution['status'] == 'FAILED' and execution['fail_on_collector_failure'] else 'PASS'
    gate['execution_status'] = execution_gate
    if execution_gate == 'FAIL':
        gate['status'] = 'FAIL'
    if status == 'COMPATIBLE' and any(x['unknown'] for x in coverage.values()):
        status = 'UNKNOWN'
    package_inventory, package_results = analyze_packages(a, b, findings, coverage)
    for item in findings:
        item.pop('_root_paths', None)
    if (any(c['confirmed_incompatible'] for c in coverage.values()) or any(t['status'] == 'INCOMPATIBLE' for t in tests)
            or any(p['overall'] == 'INCOMPATIBLE' for p in package_results)):
        status = 'INCOMPATIBLE'
    profile = repository if repository is not None else comparison_profile(a['elf_objects'], b['elf_objects'])
    return {'package_inventory': package_inventory, 'package_results': package_results,
        **{key: profile[key] for key in ('comparison_validity', 'confounders', 'build_profile')},
        'execution': execution, 'linking_summary': summarize_unknowns(findings),
        'finding_integrity': {'unique_findings': len(findings), 'source_occurrences': sum(f.get('occurrences', 1) for f in findings),
                              'deduplicated': [{'id': f['id'], 'occurrences': f['occurrences']} for f in findings if f.get('occurrences', 1) > 1]},
        'expected_tests': a.get('expected_tests', []) + b.get('expected_tests', []),
        'coverage': coverage, 'quality_gate': gate,
        'coverage_policy': {'unit': 'baseline component contract; ABI has separate export and type-layout obligations',
                            'coverage_denominator': 'applicable', 'compatibility_denominator': 'applicable',
                            'verified': 'COMPLETE obligations only; outcomes are independent of completeness'}, 'schema_version': SCHEMA, 'direction': 'baseline consumers on candidate',
        'baseline': a['image'], 'candidate': b['image'], 'status': status,
        'verification': 'PARTIAL' if any(c['partially_verified'] for c in coverage.values()) or (any(c['verified'] for c in coverage.values()) and any(c['unexecuted'] for c in coverage.values())) else 'NOT_EXECUTED' if any(c['unexecuted'] for c in coverage.values()) else 'COMPLETE',
        'summary': {'findings': len(findings), 'by_status': {s: counts[s] for s in STATUSES},
            'total_expected_tests': len(expected), 'complete_expected_tests': sum(e.get('verification') == 'COMPLETE' for e in expected), 'total_tests': len(tests), 'passed_tests': test_counts['COMPATIBLE'] + test_counts['IDENTICAL'],
            'failed_tests': test_counts['INCOMPATIBLE'], 'unknown_tests': test_counts['UNKNOWN']},
        'dimensions': {d: dict(Counter(f['status'] for f in findings if f['dimension'] == d)) for d in DIMENSIONS},
        'findings': findings, 'tests': tests, 'matrix': matrix,
        'limitations': a['limitations'] + b['limitations'],
        'excluded_dimensions': sorted(set(DIMENSIONS) - set(config['analysis']['modes'])),
        'normalized_differences': [f['id'] for f in findings if f['status'] == 'COMPATIBLE'],
        'missing_interfaces': [f['id'] for f in findings if f['candidate'] is None and f['baseline'] is not None],
        'normalization_policy': ['ELF build IDs, debug paths, .comment and binary hashes are evidence, not interface comparisons.',
            'Filesystem timestamps are omitted; permissions, UID/GID, link targets are retained.',
            'RPM release-only changes are informational; version and capability changes need semantic verification.',
            'Header comments and token-separating whitespace are normalized; macro values and conditionals are retained.']}


def generate(output: Path, a: dict[str, Any], b: dict[str, Any], results: dict[str, Any], config: dict[str, Any],
             *, objective=None, reused=False) -> None:
    write_json(output / 'baseline-manifest.json', a, compact=True)
    write_json(output / 'candidate-manifest.json', b, compact=True)
    report = config['report']
    if report['csv']:
        with (output / 'findings.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=FINDING_DETAIL_COLUMNS)
            writer.writeheader()
            for finding in results['findings']:
                writer.writerow(finding_cells(finding, FINDING_DETAIL_COLUMNS))
        test_columns = ('id', 'logical_id', 'name', 'compiler', 'image', 'kind', 'status', 'compile_status',
                        'link_status', 'deployment_status', 'execution_status', 'behavior_status', 'reference_image',
                        'returncode', 'runtime_reason', 'evidence')
        with (output / 'test-results.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(test_columns)
            for test in results['tests']:
                values = [test.get(key, '') for key in test_columns]
                writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r'))
                                 else canonical(v) if isinstance(v, (dict, list)) else v for v in values])
        package_columns = ['id', 'name', 'scope', 'arch', 'baseline_version', 'candidate_version', 'abi', 'api', 'linking', 'overall', 'verification', 'coverage_percent', 'finding_ids', 'limitations']
        with (output / 'packages.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=package_columns); writer.writeheader()
            for package in results['package_results']:
                row = {k: package.get(k) for k in package_columns}
                for k in ('abi', 'api', 'linking'): row[k] = package[k]['status']
                row['coverage_percent'] = package['coverage']['coverage_percent']
                row = {k: canonical(v) if isinstance(v, (list, dict)) else str(v) for k, v in row.items()}
                writer.writerow({k: "'" + v if v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for k, v in row.items()})
        if results.get('repository'):
            from .repository import export_repository
            export_repository(output, a, b, results)
        elif objective == 'EXPORT_SYMBOLS':
            from .rootfs_symbols import export_rootfs_symbols
            export_rootfs_symbols(output, a, b, results)
    elif results.get('repository'):
        from .repository import count_symbol_differences
        count_symbol_differences(a, b, results)
    if results.get('scope'):
        from .run_summary import make_summary
        results['run_summary'] = make_summary(a, b, results, config, objective, reused)
    if report['json']:
        write_json(output / 'results.json', results, compact=True)
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True))
    def table(rows: list[list[Any]], headers: list[str]) -> str:
        return '<table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join(
            '<tr>' + ''.join('<td><pre>' + esc(x) + '</pre></td>' for x in row) + '</tr>' for row in rows) + '</tbody></table>'
    summary = results['summary']
    handoff = results.get('run_summary', {})
    banner = ''
    if results.get('comparison_validity') == 'CONFOUNDED':
        shares = ', '.join(f"{c['kind']} (baseline {c['baseline_share']:.1%}, candidate {c['candidate_share']:.1%})"
                           for c in results['confounders'])
        banner = f'Comparison confounded by instrumentation difference: {shares}. Size findings are downgraded.'
    headline = [('Input scope','scope'), ('Requested objective','requested_objective'),
                ('Objective completion','objective_completion'), ('Execution status','execution_status'),
                ('Compatibility status','compatibility_status'), ('Coverage status','coverage_status')]
    if report['markdown']:
        lines = ['# Tizen image compatibility', '', f"**Result: {results['status']}** — baseline consumers on candidate.", '',
            f"Baseline: {esc(a['image']['name'])}; candidate: {esc(b['image']['name'])}.", '',
            f"Tests: {summary['total_tests']}; passed: {summary['passed_tests']}; failed: {summary['failed_tests']}; unknown: {summary['unknown_tests']}.",
            f"Findings: {summary['findings']}; incompatible: {summary['by_status']['INCOMPATIBLE']}; unknown: {summary['by_status']['UNKNOWN']}.", '',
            'Static findings are not executable test counts. No runtime execution means no runtime pass.', '']
        if banner:
            lines[:0] = [banner, '']
        if handoff:
            lines += [f'- **{label}** {esc(handoff[key])}' for label, key in headline] + ['']
            lines += ['See `run-summary.json` for the compact machine-readable handoff.', '']
        linking = results.get('linking_summary', {})
        if linking:
            lines += ['## Linking UNKNOWN by reason', '',
                      '| Reason | Findings | Next action |', '| --- | ---: | --- |']
            lines += [f"| {esc(code)} | {entry['count']} | {esc(entry['next_action'])} |"
                      for code, entry in sorted(linking.items())] + ['']
        lines += ['## Collector execution', '', '**' + results['execution']['status'] + '**', '']
        for side, collectors in results['execution']['collectors'].items():
            for tool, entry in collectors.items():
                reasons = [e.get('path',e.get('archive','*')) + ' (' + e['reason'] + ')' for e in entry.get('errors', [])]
                lines.append('- ' + esc(side + ' ' + tool + ' ' + entry['status'] + ' ' +
                                        (entry.get('reason') or ', '.join(reasons[:10]))))
        lines += ['', '## Coverage', '', '| Dimension | Applicable | Complete | Partial | Unexecuted | Compatible | Incompatible | Unknown | Complete coverage % | Compatible / applicable % |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for dim, cov in results['coverage'].items():
            lines.append('| ' + ' | '.join(str(x) for x in [dim, *[cov[k] for k in ('applicable', 'verified', 'partially_verified', 'unexecuted', 'compatible', 'incompatible', 'unknown', 'coverage_percent', 'compatibility_percent')]]) + ' |')
        lines += ['', 'Quality gate: ' + results['quality_gate']['status'] + '; compatibility=' + results['quality_gate']['compatibility_status'] + '; coverage=' + results['quality_gate']['coverage_status'] + '; strict=' + results['quality_gate']['strict_status'] + '; execution=' + results['quality_gate']['execution_status'], '', '## Incompatible interfaces (first 200; full list in JSON/CSV)', '']
        for item in [f for f in results['findings'] if f['status'] == 'INCOMPATIBLE'][:200]:
            if item['status'] == 'INCOMPATIBLE':
                lines.append(f"- {item['severity']} `{esc(item['component'])}` / `{esc(item['interface'])}`: {esc(item['potential_impact'])} ({item['id']})")
        lines += ['', '## Package compatibility', '', 'Installed package counts: baseline=' + str(results['package_inventory']['baseline_package_count']) + '; candidate=' + str(results['package_inventory']['candidate_package_count']) + '. null means UNKNOWN, not zero.', '',
                  '| Package | GCC baseline version | LLVM candidate version | ABI | API | Linking | Complete coverage % | Overall |', '|---|---|---|---|---|---|---:|---|']
        for package in results['package_results'][:200]:
            lines.append('| ' + ' | '.join(esc(v) for v in [package['scope'] + ':' + package['name'], package['baseline_version'], package['candidate_version'], package['abi']['status'], package['api']['status'], package['linking']['status'], package['coverage']['coverage_percent'], package['overall']]) + ' |')
        lines += ['', 'First 200 packages shown; full records, ownership, findings and gaps are in results.json and packages.csv.']
        if repo := results.get('repository'):
            lines += ['', '## '+repo['scope'], '',
                      'Available RPMs and their payloads are separate from installed product inventories.',
                      'Baseline: '+canonical(repo['baseline']), 'Candidate: '+canonical(repo['candidate']),
                      'Package changes: '+canonical(repo['inventory_states']),
                      'See packages.csv, package-symbol-summary.csv, elf-symbol-summary.csv, symbol-differences.csv and extraction-errors.csv.']
            if repo.get('requirements'):
                lines += ['Available-set requirements: '+canonical(repo['requirements']),
                          'See requirement-findings.csv for all failed and unknown requirements when CSV is enabled.']
        lines += ['', '## Cross-compatibility matrix', '', '| Compiler | Image | Compile | Link | Deploy | Execute | Behavior | Overall |', '|---|---|---|---|---|---|---|---|']
        for cell in results['matrix']:
            lines.append('| ' + ' | '.join(esc(cell.get(k, 'UNKNOWN')) for k in ('compiler', 'image', 'compile_status', 'link_status',
                         'deployment_status', 'execution_status', 'behavior_status', 'status')) + ' |')
        lines += ['', '## Limitations', '']
        for reason in sorted({x['reason'] for x in results['limitations']}):
            lines.append('- ' + esc(reason))
        lines += ['', 'Excluded dimensions: ' + ', '.join(results['excluded_dimensions']), '', 'See index.html, results.json and evidence/ for details.']
        (output / 'summary.md').write_text('\n'.join(lines) + '\n')
    if report['html']:
        content = ('<p class="status">'+esc(banner)+'</p>' if banner else '')
        content += '<h1>Tizen image compatibility</h1><h2>Executive summary</h2>'
        content += '<p class="status">' + esc(results['status']) + '</p>'
        if handoff:
            content += table([[label,handoff[key]] for label,key in headline], ['Status field','Value'])
            content += '<p><a href="run-summary.json">Download the compact run summary</a></p>'
        if results.get('rootfs_symbol_detail'):
            content += '<p>Exact-path ELF detail: <a href="elf-symbol-summary.csv">libraries</a> · <a href="symbol-differences.csv">symbols</a>.</p>'
        content += table([[a['image'], b['image'], summary]], ['Baseline image', 'Candidate image', 'Tests and findings'])
        content += '<p>Direction: baseline consumers on candidate. UNKNOWN is not a pass. Static findings and executable tests are counted separately.</p>'
        content += '<h2>Collector execution</h2><p>' + esc(results['execution']['status']) + '</p>' + table(
            [[side, tool, {**entry, 'errors': entry.get('errors', [])[:10]}]
             for side, collectors in results['execution']['collectors'].items() for tool, entry in collectors.items()],
            ['Image', 'Collector', 'Recorded execution (first 10 errors)'])
        content += '<h2>Coverage and gate</h2>' + table([[d, {k: v for k, v in c.items() if k != 'units'}] for d, c in results['coverage'].items()], ['Dimension', 'Coverage'])
        content += '<p>Quality gate: ' + esc(results['quality_gate']) + '</p>'
        content += '<h2>Compatibility overview</h2>' + table([[k, v] for k, v in results['dimensions'].items()], ['Dimension', 'Statuses'])
        content += '<h2>Cross-compatibility matrix</h2>' + table([[c.get(k, 'UNKNOWN') for k in ('compiler', 'image', 'header_status', 'compile_status', 'link_status', 'deployment_status', 'execution_status', 'behavior_status', 'status')] for c in results['matrix']],
            ['Compiler', 'Image', 'Headers', 'Compile', 'Link', 'Deploy', 'Execute', 'Behavior', 'Overall'])
        content += '<h2>Compile and runtime observations</h2><p>First 100 tests. Full results in JSON and test-results.csv.</p>'
        content += table([[t.get(k, '') for k in ('id', 'name', 'compiler', 'image', 'status', 'compile_status', 'link_status', 'deployment_status', 'execution_status', 'behavior_status', 'runtime_reason', 'evidence')]
                          for t in results['tests'][:100]], ['ID', 'Test', 'Compiler', 'Image', 'Overall', 'Compile', 'Link', 'Deploy', 'Execute', 'Behavior', 'Reason', 'Evidence'])
        inventory = results['package_inventory']
        if repo := results.get('repository'):
            content += '<h2>'+esc(repo['scope'])+'</h2><p>Available RPM packages. Loaded product state and provider selection are unverified.</p>'
            content += table([[side,repo[side]] for side in ('baseline','candidate')],['Image','RPM, ELF, symbol and coverage counts'])
            content += '<p>Package relationships: '+esc(repo['inventory_states'])+'</p>'
            if repo.get('requirements'):
                content += '<p>Available-set requirements: '+esc(repo['requirements'])+'</p>'
                if report['csv']:
                    content += '<p><a href="requirement-findings.csv">Full available-set requirement findings</a></p>'
            content += '<p>Full tables: '+ ' · '.join('<a href="'+name+'">'+name+'</a>' for name in (
                'packages.csv','package-symbol-summary.csv','elf-symbol-summary.csv','symbol-differences.csv','extraction-errors.csv'))+'</p>'
            content += table([[p[k] for k in ('name','arch','inventory_status','baseline_nevra','candidate_nevra','status')]
                               for p in repo['packages'][:200]],['Package','Arch','Inventory','Baseline','Candidate','ABI result'])
            content += '<p>Package rows: '+str(len(repo['packages']))+'; preview: '+str(min(200,len(repo['packages'])))+'.</p>'
        content += '<h2>Package compatibility</h2><p>Installed package counts: baseline=' + esc(inventory['baseline_package_count']) + '; candidate=' + esc(inventory['candidate_package_count']) + '. null means UNKNOWN. First 1000 packages shown; full records in JSON/CSV.</p>'
        content += '<input id="package-filter" aria-label="Filter packages" placeholder="Filter packages…">'
        for package in results['package_results'][:1000]:
            content += '<details class="package" data-package-id="' + esc(package['id']) + '" data-status="' + esc(package['overall']) + '" data-verification="' + esc(package['verification']) + '"><summary>' + esc(package['scope'] + ':' + package['name'] + ' · ' + package['overall'] + ' · ' + package['verification']) + '</summary>'
            content += table([[package['baseline_version'], package['candidate_version'], package['abi']['status'], package['api']['status'], package['linking']['status'], package['coverage']['coverage_percent'], package['overall']]], ['GCC baseline version', 'LLVM candidate version', 'ABI', 'API', 'Linking', 'Complete coverage %', 'Overall'])
            # Full symbol sets remain in JSON; a bounded per-package preview avoids huge DOMs.
            preview = {k: package[k] for k in ('id', 'match_status', 'replacement_hint', 'finding_ids', 'missing_interfaces', 'limitations', 'evidence')}
            preview['owned ELF'] = [{k: e.get(k) for k in ('path', 'soname', 'type')} for e in package['owned_interfaces']['elf'][:100]]
            preview['headers'] = package['owned_interfaces']['headers'][:100]
            preview['public symbols (first 100)'] = list(islice((s['name'] for e in package['owned_interfaces']['elf'] for s in e['exports']), 100))
            preview = {k: v[:100] if isinstance(v, list) else v for k, v in preview.items()}
            content += table([[k, v] for k, v in preview.items()], ['Detail (bounded preview)', 'Value']) + '</details>'
        content += '<h3>Candidate-only inventory (first 1000)</h3>' + table([[p['package']['name'], p['package']['version'], p['reason']] for p in inventory['candidate_additions'][:1000]], ['Package', 'Version', 'Assessment boundary'])
        integrity = results['finding_integrity']
        content += '<p>Finding integrity: ' + esc({k:v for k,v in integrity.items() if k!='deduplicated'} |
                                                {'deduplicated_ids':len(integrity['deduplicated'])}) + '</p>'
        content += '<h2>Detailed differences</h2><input id="filter" aria-label="Filter findings" placeholder="Filter findings…">'
        content += '<p>First 1000 findings shown; complete details are in results.json and findings.csv.</p>'
        for item in results['findings'][:1000]:
            content += '<details class="finding" data-finding-id="' + esc(item['id']) + '" data-status="' + esc(item['status']) + '"><summary>' + esc(f"{item['severity']} · {item['status']} · {item['component']} · {item['interface']}") + '</summary>'
            content += table([[k, v] for k, v in item.items()], ['Field', 'Value'])
            content += '</details>'
        for title, key in [('Missing interfaces', 'missing_interfaces'), ('Normalized differences', 'normalized_differences')]:
            selected = set(results[key])
            preview = list(islice((f for f in results['findings'] if f['id'] in selected), 1000))
            content += '<h2>' + title + '</h2><p>Total: ' + str(len(selected)) + '; shown: ' + str(len(preview)) + '; hidden: ' + str(len(selected) - len(preview)) + '.</p>' + table([[f['id'], f['component'], f['interface'], f['potential_impact']] for f in preview], ['ID', 'Component', 'Interface', 'Reason / impact'])
        content += '<h2>Normalization policy</h2><ul>' + ''.join('<li>' + esc(v) + '</li>' for v in results['normalization_policy']) + '</ul>'
        content += '<h2>Limitations</h2>' + table([[x['dimension'], x['component'], x['reason']] for x in results['limitations']], ['Dimension', 'Component', 'Reason'])
        content += '<p>Excluded dimensions: ' + esc(results['excluded_dimensions']) + '</p>'
        template = (Path(__file__).resolve().parents[2] / 'assets' / 'report_template.html').read_text()
        (output / 'index.html').write_text(template.replace('{{CONTENT}}', content))
