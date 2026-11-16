"""Machine-readable and escaped, self-contained human reports."""
from __future__ import annotations

from collections import Counter
import csv
import html
import json
from pathlib import Path
from typing import Any
from .core import DIMENSIONS, SCHEMA, STATUSES, canonical, write_json


def build_results(a: dict[str, Any], b: dict[str, Any], findings: list[dict[str, Any]],
                  tests: list[dict[str, Any]], matrix: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(f['status'] for f in findings)
    test_counts = Counter(t['status'] for t in tests)
    status = 'INCOMPATIBLE' if counts['INCOMPATIBLE'] else 'UNKNOWN' if counts['UNKNOWN'] else 'COMPATIBLE' if findings else 'UNKNOWN'
    return {'schema_version': SCHEMA, 'direction': 'baseline consumers on candidate',
        'baseline': a['image'], 'candidate': b['image'], 'status': status,
        'summary': {'findings': len(findings), 'by_status': {s: counts[s] for s in STATUSES},
            'total_tests': len(tests), 'passed_tests': test_counts['COMPATIBLE'] + test_counts['IDENTICAL'],
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


def generate(output: Path, a: dict[str, Any], b: dict[str, Any], results: dict[str, Any], config: dict[str, Any]) -> None:
    write_json(output / 'baseline-manifest.json', a)
    write_json(output / 'candidate-manifest.json', b)
    report = config['report']
    if report['json']:
        write_json(output / 'results.json', results)
    if report['csv']:
        columns = ['id', 'dimension', 'component', 'interface', 'baseline', 'candidate', 'status', 'severity',
                   'confidence', 'evidence', 'detection_method', 'potential_impact', 'recommended_action']
        with (output / 'findings.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for finding in results['findings']:
                row = {k: canonical(finding[k]) if isinstance(finding[k], (dict, list)) else str(finding[k]) for k in columns}
                # Avoid spreadsheet formula injection from image-controlled paths and strings.
                writer.writerow({k: "'" + v if v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for k, v in row.items()})
    def esc(value: Any) -> str:
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True))
    def table(rows: list[list[Any]], headers: list[str]) -> str:
        return '<table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join(
            '<tr>' + ''.join('<td><pre>' + esc(x) + '</pre></td>' for x in row) + '</tr>' for row in rows) + '</tbody></table>'
    summary = results['summary']
    if report['markdown']:
        lines = ['# Tizen image compatibility', '', f"**Result: {results['status']}** — baseline consumers on candidate.", '',
            f"Baseline: {esc(a['image']['name'])}; candidate: {esc(b['image']['name'])}.", '',
            f"Tests: {summary['total_tests']}; passed: {summary['passed_tests']}; failed: {summary['failed_tests']}; unknown: {summary['unknown_tests']}.",
            f"Findings: {summary['findings']}; incompatible: {summary['by_status']['INCOMPATIBLE']}; unknown: {summary['by_status']['UNKNOWN']}.", '',
            'Static findings are not executable test counts. No runtime execution means no runtime pass.', '', '## Risks', '']
        for item in results['findings']:
            if item['status'] == 'INCOMPATIBLE':
                lines.append(f"- {item['severity']} `{esc(item['component'])}` / `{esc(item['interface'])}`: {esc(item['potential_impact'])} ({item['id']})")
        lines += ['', '## Cross-compatibility matrix', '', '| Compiler | Image | Headers | Runtime | Overall |', '|---|---|---|---|---|']
        for cell in results['matrix']:
            lines.append('| ' + ' | '.join(cell[k] for k in ('compiler', 'image', 'header_status', 'runtime_status', 'status')) + ' |')
        lines += ['', '## Limitations', '']
        for reason in sorted({x['reason'] for x in results['limitations']}):
            lines.append('- ' + esc(reason))
        lines += ['', 'Excluded dimensions: ' + ', '.join(results['excluded_dimensions']), '', 'See index.html, results.json and evidence/ for details.']
        (output / 'summary.md').write_text('\n'.join(lines) + '\n')
    if report['html']:
        content = '<h1>Tizen image compatibility</h1><h2>Executive summary</h2>'
        content += '<p class="status">' + esc(results['status']) + '</p>'
        content += table([[a['image'], b['image'], summary]], ['Baseline image', 'Candidate image', 'Tests and findings'])
        content += '<p>Direction: baseline consumers on candidate. UNKNOWN is not a pass. Static findings and executable tests are counted separately.</p>'
        content += '<h2>Compatibility overview</h2>' + table([[k, v] for k, v in results['dimensions'].items()], ['Dimension', 'Statuses'])
        content += '<h2>Cross-compatibility matrix</h2>' + table([[c.get(k, '') for k in ('compiler', 'image', 'header_status', 'runtime_status', 'status', 'reason', 'runtime_reason')] for c in results['matrix']],
            ['Compiler', 'Image', 'Headers', 'Runtime', 'Overall', 'Compile coverage', 'Runtime coverage'])
        content += '<h2>Detailed differences</h2><input id="filter" aria-label="Filter findings" placeholder="Filter findings…">'
        for item in results['findings']:
            content += '<details class="finding"><summary>' + esc(f"{item['severity']} · {item['status']} · {item['component']} · {item['interface']}") + '</summary>'
            content += table([[k, v] for k, v in item.items()], ['Field', 'Value'])
            content += '</details>'
        for title, key in [('Missing interfaces', 'missing_interfaces'), ('Normalized differences', 'normalized_differences')]:
            content += '<h2>' + title + '</h2>' + table([[f['id'], f['component'], f['interface'], f['potential_impact']] for f in results['findings'] if f['id'] in results[key]], ['ID', 'Component', 'Interface', 'Reason / impact'])
        content += '<h2>Normalization policy</h2><ul>' + ''.join('<li>' + esc(v) + '</li>' for v in results['normalization_policy']) + '</ul>'
        content += '<h2>Limitations</h2>' + table([[x['dimension'], x['component'], x['reason']] for x in results['limitations']], ['Dimension', 'Component', 'Reason'])
        content += '<p>Excluded dimensions: ' + esc(results['excluded_dimensions']) + '</p>'
        template = (Path(__file__).resolve().parents[2] / 'assets' / 'report_template.html').read_text()
        (output / 'index.html').write_text(template.replace('{{CONTENT}}', content))
