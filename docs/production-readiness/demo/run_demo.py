#!/usr/bin/env python3
"""Run the offline HQ demo through the same workflow used by agents."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from generate_fixture import check_tools, generate, sha256

DEFAULT_SKILL = Path(__file__).resolve().parents[3]/'.agents/skills/tizen-image-compatibility'
FILES = ('index.html', 'summary.md', 'results.json', 'packages.csv', 'findings.csv',
         'package-symbol-summary.csv', 'elf-symbol-summary.csv', 'symbol-differences.csv',
         'extraction-errors.csv', 'run-summary.json')


def invoke(workflow, directory, expected_code, *argv):
    result = subprocess.run([sys.executable, str(workflow), *map(str,argv)], cwd=directory,
                            env=os.environ | {'PYTHONDONTWRITEBYTECODE':'1', 'TMPDIR':str(directory/'tmp')},
                            capture_output=True, text=True, timeout=120)
    command = str(argv[0])
    (directory/(command+'.stdout')).write_text(result.stdout, encoding='utf-8')
    (directory/(command+'.stderr')).write_text(result.stderr, encoding='utf-8')
    if result.returncode != expected_code:
        raise ValueError(f'{command} exited {result.returncode}; expected {expected_code}')
    return result


def check(condition, why):
    if not condition:
        raise ValueError('Unexpected fixture result: '+why)


def verify(fixture, report):
    check(all((report/file).is_file() for file in FILES), 'missing core report file(s)')
    summary = json.loads((report/'run-summary.json').read_text(encoding='utf-8'))
    check(summary['scope']=='RPM_REPOSITORY_PAYLOAD', 'wrong scope')
    check(summary['objective_completion']=='COMPLETE' and summary['execution_status']=='COMPLETE',
          'export goal or execution incomplete')
    check(summary['compatibility_status']=='INCOMPATIBLE', 'fixture contract break not detected')
    check(summary['coverage_status']=='PARTIAL', 'installed loader limitation disappeared from coverage')
    # The demo input is bounded to two tiny RPMs per side. General agents use
    # run-summary.json and CSV or bounded queries for real reports.
    results = json.loads((report/'results.json').read_text(encoding='utf-8'))
    check(all(results['repository'][side][key]==value for side in ('baseline','candidate')
              for key,value in {'rpm_total':2,'extracted':2,'elf_collected':2,
                                'export_inventories_complete':2,'exports':7,'imports':1}.items()),
          'RPM, ELF, export or import count')
    with (report/'symbol-differences.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    check(len(rows)==summary['statistics']['symbol_differences']['rows']==9, 'symbol detail row count')
    for side in ('baseline','candidate'):
        observed_exports = [json.loads(row[side]) for row in rows
                            if row['role']=='EXPORT' and row[side]!='UNKNOWN']
        names = {entry['base_name'] for entry in observed_exports}
        lookup = {entry['name'] for entry in observed_exports} | {
            entry['base_name'] for entry in observed_exports if entry['default_version']}
        check(len(names)==summary['statistics'][side]['export_unique_symbol_names']==7, 'unique export names')
        check(len(lookup)==summary['statistics'][side]['export_lookup_identities']==13, 'export lookup identities')
    expected = {
        ('EXPORT','MISSING','legacy_export',''): {'expected_detail':None},
        ('EXPORT','ADDED','', 'added_export'): {'expected_detail':None},
        ('EXPORT','CHANGED','version_contract','version_contract'): {'expected_detail':'VERSION_CHANGED'},
        ('EXPORT','CHANGED','data_contract','data_contract'): {'expected_detail':'DATA_SIZE_CHANGED'},
        ('EXPORT','CHANGED','stable_code','stable_code'): {'expected_detail':'CODE_SIZE_CHANGED'},
        ('IMPORT','MATCHED','legacy_export','legacy_export'): {'expected_detail':None},
    }
    observed = {}
    for row in rows:
        sides = [json.loads(row[key]) if row[key]!='UNKNOWN' else {} for key in ('baseline','candidate')]
        names = [side.get('base_name', side.get('name','').split('@',1)[0]) for side in sides]
        key = (row['role'],row['change'],*names)
        if key in expected:
            details = json.loads(row['details'])
            check(expected[key]['expected_detail'] is None or expected[key]['expected_detail'] in details,
                  'change detail for '+str(key))
            observed[key] = (row,sides)
    check(set(observed)==set(expected), 'expected symbol comparisons')
    provider,_ = observed['EXPORT','MISSING','legacy_export','']
    consumer,versions = observed['IMPORT','MATCHED','legacy_export','legacy_export']
    check(provider['status']=='INCOMPATIBLE', 'removed export status')
    check(provider['package_id']!=consumer['package_id'], 'consumer and provider package IDs must differ')
    check(all(x.get('version')=='DEMO_1' and x['version_file']=='libdemo-codec.so.1' for x in versions),
          'consumer versioned import and expected provider name')
    check(all((report/ref).is_file() and sha256(report/ref)==Path(ref).stem
              for row,_ in observed.values() for ref in json.loads(row['evidence'])), 'symbol Evidence digests')
    check(all(sha256(fixture/item['path'])==item['sha256']
              for item in json.loads((fixture/'fixture-manifest.json').read_text(encoding='utf-8'))['archives']),
          'input archive digest changed')
    with (report/'findings.csv').open(encoding='utf-8', newline='') as stream:
        findings = list(csv.DictReader(stream))
    check({row['id'] for row in findings}=={row['id'] for row in results['findings']}, 'JSON/CSV Finding IDs')
    check(any(x['dimension']=='linking' and x['status']=='UNKNOWN' for x in results['findings']),
          'installed loader scope is not identified as unknown')
    return {'status':'PASS','scope':'SYNTHETIC_RPM_DEMO','finding_count':len(findings),
            'symbol_rows':len(rows),'provider_component':provider['component'],
            'consumer_component':consumer['component'],'report':str(report),
            'engine_summary':str(report/'run-summary.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New demo output directory for fixtures and reports')
    parser.add_argument('--skill', type=Path, default=DEFAULT_SKILL, help='Installed directory containing SKILL.md')
    parser.add_argument('--preflight', action='store_true', help='Check local tools without creating fixtures')
    args = parser.parse_args()
    workflow = args.skill.resolve()/'scripts/compat_workflow.py'
    tools = check_tools()
    missing = [tool for tool,path in tools.items() if not path]
    ready = not missing and workflow.is_file() and sys.version_info >= (3,11)
    preflight = {'status':'READY' if ready else 'BLOCKED','python':sys.version.split()[0],
                 'workflow_available':workflow.is_file(),'tools':{tool:bool(path) for tool,path in tools.items()}}
    if args.preflight or not ready:
        print(json.dumps(preflight, indent=2))
        if not ready or args.preflight:
            return 0 if ready else 2
    if args.output is None:
        parser.error('--output is required unless --preflight is used')
    output = args.output.resolve()
    try:
        if any(char in str(output) for char in ('%', '\r', '\n')):
            raise ValueError('Output paths cannot contain RPM macro or line-break characters')
        if shutil.disk_usage(output.parent).free < 256*1024**2:
            raise ValueError('Demo needs at least 256 MiB available for tools and scratch files')
        output.mkdir(exist_ok=False)
        (output/'tmp').mkdir()
        fixture = output/'fixture'
        generate(fixture)
        config = output/'workflow.json'
        config.write_text(json.dumps({'baseline':'fixture/baseline','candidate':'fixture/candidate',
                                      'output':'report','objective':'EXPORT_SYMBOLS','rpm_mode':'payload'},
                                     indent=2)+'\n', encoding='utf-8')
        invoke(workflow, output, 0, 'doctor','--config',config)
        invoke(workflow, output, 0, 'plan','--config',config)
        invoke(workflow, output, 1, 'run','--config',config)
        report = output/'report'
        invoke(workflow, output, 0, 'status','--output',report)
        invoke(workflow, output, 0, 'summary','--output',report)
        proof = verify(fixture, report)
        (output/'demo-receipt.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(proof, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(f'Demo failed: {error}',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
