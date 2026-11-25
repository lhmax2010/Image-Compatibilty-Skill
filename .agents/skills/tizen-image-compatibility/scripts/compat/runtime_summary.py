"""Render a sidecar report without rewriting static findings or runtime receipts."""
from collections import Counter
import csv
import html
import json
from pathlib import Path
import re

from .core import hash_file, write_json
from . import runtime_plan


def read(path):
    return json.loads(path.read_text())


def static_summary(spec):
    root = Path(spec['directory'])
    csv.field_size_limit(64*1024**2)
    with (root/'findings.csv').open(newline='') as f:
        counts = Counter((row['dimension'], row['status']) for row in csv.DictReader(f))
    package_assessments = Counter()
    with (root/'packages.csv').open(newline='') as f:
        packages = Counter()
        for row in csv.DictReader(f):
            packages[row['scope']] += 1
            for dimension in ('abi', 'api', 'linking', 'overall'):
                if row.get(dimension):
                    package_assessments[dimension, row[dimension]] += 1
    installed = {}
    summary_file = root/'summary.md'
    if summary_file.is_file():
        # The existing static Markdown reports inventories separately from assessment rows.
        with summary_file.open() as stream:
            for line in stream:
                field = re.match(r'^Installed package counts: baseline=(\d+|None); candidate=(\d+|None)\.', line)
                if field:
                    installed = dict(zip(('baseline', 'candidate'),
                                         (int(value) if value.isdecimal() else None for value in field.groups())))
                    break
    # Existing report puts the small baseline and candidate identity objects first.
    # Retain these independently of the operator-supplied scope label.
    identities = {}
    result = root/'results.json'
    if result.is_file():
        with result.open() as src:
            prefix = src.read(256*1024)
        decoder = json.JSONDecoder()
        for side in ('baseline','candidate'):
            match = prefix.find('"'+side+'"')
            if match >= 0:
                start = prefix.find('{',match)
                if start >= 0:
                    try:
                        data, _ = decoder.raw_decode(prefix[start:])
                    except ValueError:
                        continue
                    if 'os_version' in data:
                        identities[side] = data['os_version'].get('BUILD_ID', [])
    return {'scope':spec['scope'],'source':str(root),'published_build_ids':identities,
            'findings':sum(counts.values()),'package_rows':dict(packages),'installed_packages':installed,
            'package_assessments':[{'dimension':d,'status':s,'count':n}
                                   for (d,s),n in sorted(package_assessments.items())],
            'finding_counts':[{'dimension':dim,'status':status,'count':n} for (dim,status),n in sorted(counts.items())]}


def collect(config, output, *, plan=None, live_attempts=None):
    static = static_summary(config['static_report']) if config.get('static_report') else None
    builds = []
    for source in config.get('build_reports', []):
        path = Path(source)
        builds.append({'source':str(path),'sha256':hash_file(path),'record':read(path)})
    rows = runtime_plan.read_attempts(config.get('runtime_reports', []))
    if plan is None and config.get('expected_runtime_plan'):
        plan = runtime_plan.pinned_document(config['expected_runtime_plan'])
    plan = plan if plan is not None else {'schema':runtime_plan.PLAN, 'tests':[]}
    reconciled = runtime_plan.reconcile(config, plan, rows, live_attempts or {})
    results = {'schema':'tizen-compat-workflow-report/v1','static':static,'compile_link':builds,'runtime':rows,
               'runtime_status_counts':reconciled['counts'],'expected_runtime':reconciled,'formal_compatibility':'UNKNOWN',
               'runtime_run_note':config.get('runtime_run_note'),
               'limitations':['Runtime observations do not update static findings',
                              'Release and execution scopes are independently recorded',
                              'Formal target-process proof is not established by the SDB observation']}
    write_json(output/'results.json',results)
    md = ['# Tizen compatibility workflow','',
          'Formal compatibility: UNKNOWN','']
    if results['runtime_run_note']:
        md.extend([html.escape(results['runtime_run_note']),''])
    if static:
        md.extend(['## Static analysis','',f"Scope: {static['scope']}",f"Findings: {static['findings']:,}",
                   f"Package assessment rows: {sum(static['package_rows'].values()):,}",''])
        for side, count in static['installed_packages'].items():
            md.append(f"- Installed packages ({side}): {count if count is not None else 'UNKNOWN'}")
        md.append('')
    md.extend(['## Compile and link',''])
    for item in builds:
        md.append(f"- {len(item['record']['steps'])} recorded steps, evidence SHA256 {item['sha256']}")
    md.extend(['','## Raw Runtime receipts','',
               '| Scope | Artifact | Claimed result | Exit | Behavior match | Cleanup | Formal | Disposition |',
               '| --- | --- | --- | --- | --- | --- | --- | --- |'])
    incomplete = []
    for item in rows:
        r = item['record']
        if item.get('input_error'):
            continue
        if r['result'] in ('BLOCKED', 'OBSERVATION_INCOMPLETE', 'BEHAVIOR_MISMATCH', 'NOT_VERIFIED'):
            capture = r.get('captured_output') or r.get('receipt')
            stderr = capture.get('stderr', '') if isinstance(capture, dict) else ''
            reason = r.get('error') or ' '.join(str(stderr).split()) or 'Behavior or cleanup did not match the contract'
            incomplete.append(f"- {html.escape(r['artifact_id'])}: {html.escape(str(reason)[:300])}")
        cells=(r['scope'],r['artifact_id'],r['result'],r.get('target_returncode',''),r.get('behavior_match'),
               r.get('target_cleanup_status'),r.get('formal_runtime_status'),item['disposition'])
        md.append('| '+' | '.join(html.escape(str(v)).replace('|','\\|').replace('\n',' ') for v in cells)+' |')
    if incomplete:
        md.extend(['','## Incomplete observations','',*incomplete])
    md.extend(['','## Expected Runtime tests','',
               '| Test ID | Scope | Artifact | Repetition | Required | Status | Reason |',
               '| --- | --- | --- | --- | --- | --- | --- |'])
    for record in reconciled['tests']:
        test = record['test']
        cells = (test['test_id'], test['target']['scope'], test['artifact_id'],
                 f"{test['repetition']}/{test['repetitions']}", test['required'], record['status'], record['reason'])
        md.append('| '+' | '.join(html.escape(str(value)).replace('|','\\|').replace('\n',' ') for value in cells)+' |')
    if not reconciled['tests']:
        md.append('\nNo expected Runtime plan supplied. Imported observations remain unverified.')
    md.extend(['','Full build arguments, stdout/stderr hashes, Loader files, version checks, binding events,',
               'cleanup observations and source references are available in results.json.',''])
    summary='\n'.join(md)
    (output/'summary.md').write_text(summary)
    # Include the detailed sections in HTML. Escaping keeps untrusted tool output inert.
    sections=[('Overview',summary),('Expected Runtime tests and reconciliation',reconciled),
              ('Static finding and package counts',static),('Compile and link',builds),
              ('Runtime, Loader, behavior and cleanup',rows),('Coverage limitations',results['limitations'])]
    body=''.join('<details><summary>'+html.escape(title)+'</summary><pre>'+
                 html.escape(data if isinstance(data,str) else json.dumps(data,indent=2,ensure_ascii=False))+
                 '</pre></details>' for title,data in sections)
    (output/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
                                   '<title>Tizen compatibility workflow</title><h1>Tizen compatibility workflow</h1>'
                                   '<p><a href="results.json">JSON</a> · <a href="summary.md">Markdown</a></p>'+body)
    return results
