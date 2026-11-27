"""Small, deterministic handoff for operators and automation."""
from itertools import islice
import json

from .core import atomic_output
from .elf import dynamic_exports


OBJECTIVES = ('EXPORT_SYMBOLS', 'PACKAGE_INVENTORY', 'STATIC_REPORT')
SCHEMA = 'tizen-compat-summary/1'


def save(output, summary):
    with atomic_output(output/'run-summary.json', 'w', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def rootfs_counts(manifest):
    objects = [obj for obj in manifest['elf_objects']
               if obj.get('elf_runtime_role') != 'DEBUG_ONLY']
    applicable = [obj for obj in objects if obj.get('export_inventory_status') != 'NOT_APPLICABLE']
    completed = sum(obj.get('export_inventory_complete') is True for obj in applicable)
    inventory = manifest.get('package_inventory', {})
    return {'installed_rpm_count': inventory.get('installed_count'), 'rpm_inventory_status': inventory.get('status'),
            'elf_observed': len(objects), 'elf_collected': sum(obj.get('complete') is True for obj in objects),
            'export_objects_applicable': len(applicable), 'export_inventories_complete': completed,
            'exports': sum(sum(1 for _ in dynamic_exports(obj)) for obj in objects),
            'path_inventory_complete': manifest.get('filesystem_path_inventory_complete') is True,
            'export_coverage_percent': round(100*completed/len(applicable), 2) if applicable else None}


def make_summary(a, b, result, config, objective=None, reused=False):
    repo = result.get('repository')
    scope = result['scope']
    objective = objective or ('PACKAGE_INVENTORY' if scope == 'RPM_REPOSITORY_METADATA' else 'STATIC_REPORT')
    execution = result['execution']['status']
    coverage = result['verification']
    stats = {side: repo[side] if repo else rootfs_counts(manifest)
             for side, manifest in (('baseline', a), ('candidate', b))}
    errors = []
    for side, collectors in result['execution']['collectors'].items():
        for name, receipt in collectors.items():
            if receipt.get('applicable') is False or receipt['status'] == 'COMPLETE':
                continue
            errors.append({'side': side, 'collector': name, 'status': receipt['status'],
                           'reason': str(receipt.get('reason') or receipt.get('reason_code') or '')[:300],
                           'error_count': len(receipt.get('errors', []))})
    completion = 'COMPLETE'
    if objective == 'EXPORT_SYMBOLS':
        if a['image'].get('fallback_reason') or b['image'].get('fallback_reason'):
            errors.append({'reason': 'Used explicitly supplied RPM fallback for blocked EROFS preparation.'})
        verified = sum(s['export_inventories_complete'] for s in stats.values())
        ready = all((s.get('export_analysis_status') == 'COMPLETE' or
                     (verified > 0 and s.get('payload_inventory_complete'))) if repo else
                    s['path_inventory_complete'] and s['export_inventories_complete'] > 0
                    and s['export_inventories_complete'] == s['export_objects_applicable'] for s in stats.values())
        if 'abi' not in config['analysis']['modes']:
            completion = 'NOT_EXECUTED'
            errors.append({'reason': 'ABI analysis is disabled; no export comparison was requested from the engine.'})
        elif not ready:
            completion = 'PARTIAL' if verified else 'NOT_EXECUTED'
            errors.append({'reason': 'The objective requires complete applicable export inventories on both sides.'})
        if repo and repo.get('inventory_states'):
            unresolved = sum(n for state, n in repo['inventory_states'].items() if state.startswith('AMBIGUOUS'))
            if unresolved:
                if completion == 'COMPLETE':
                    completion = 'PARTIAL'
                errors.append({'reason': 'Some RPM identities could not be paired unambiguously.', 'count': unresolved})
        unavailable = sum(f['interface'] in ('ELF availability','Repository ELF path availability')
                          and f['status']=='UNKNOWN' for f in result['findings'] if f['dimension']=='abi')
        if unavailable:
            if completion == 'COMPLETE':
                completion = 'PARTIAL'
            errors.append({'reason':'Some baseline ELF contracts have no verified candidate object.','count':unavailable})
    elif objective == 'PACKAGE_INVENTORY':
        ready = all(s.get('metadata_complete') == s.get('rpm_total') and s.get('rpm_total', 0) > 0 if repo
                    else s['rpm_inventory_status'] == 'COMPLETE' for s in stats.values())
        observed = any(s.get('metadata_complete') if repo else s['installed_rpm_count'] is not None for s in stats.values())
        if not ready:
            completion = 'PARTIAL' if observed else 'NOT_EXECUTED'
            errors.append({'reason': 'The objective requires complete package inventories on both sides.'})
    elif execution != 'COMPLETE' or coverage != 'COMPLETE':
        completion = 'NOT_EXECUTED' if execution == 'NOT_EXECUTED' else 'PARTIAL'
        errors.append({'reason': 'One or more applicable static checks lack complete evidence.'})
    if repo and repo.get('symbol_differences') is not None:
        stats['symbol_differences'] = repo['symbol_differences']
        if repo.get('requirements') is not None:
            stats['requirements'] = repo['requirements']
        stats['instrumentation_downgrades'] = repo['instrumentation_downgrades']
    if detail := result.get('rootfs_symbol_detail'):
        for side in ('baseline','candidate'):
            stats[side].update(detail[side])
        stats['symbol_differences'] = detail['symbol_differences']
    high = islice((f for f in result['findings'] if f['severity'] in ('CRITICAL','HIGH') and
                   f['status'] in ('INCOMPATIBLE','UNKNOWN')), 12)
    paths = {name: name for option, name in (('json','results.json'),('markdown','summary.md'),('html','index.html'),
                                             ('csv','findings.csv'),('csv','packages.csv')) if config['report'][option]}
    if repo and config['report']['csv']:
        paths.update({name: name for name in ('package-symbol-summary.csv','elf-symbol-summary.csv',
                                               'symbol-differences.csv','extraction-errors.csv')})
        if repo.get('requirements') is not None:
            paths['requirement-findings.csv'] = 'requirement-findings.csv'
    if detail:
        paths.update({name:name for name in ('elf-symbol-summary.csv','symbol-differences.csv')})
    paths.update({'run-summary.json':'run-summary.json','evidence':'evidence/'})
    summary = {'schema':SCHEMA, 'scope':scope, 'requested_objective':objective, 'objective_completion':completion,
            'execution_status':execution, 'compatibility_status':result['status'], 'coverage_status':coverage,
            'ci_gate_status':result['quality_gate']['status'], 'source_evidence': 'MANIFEST_REUSE' if reused else 'COLLECTED',
            'statistics':stats, 'finding_counts':result['summary']['by_status'], 'errors':errors,
            'high_risk_findings':[{key: str(f[key])[:240] for key in ('id','dimension','component','interface','status','severity')}
                                  for f in high], 'report_paths':paths,
            'next_step': ('Review symbol or Finding evidence for the requested objective.' if completion == 'COMPLETE' else
                          'Review the recorded collection gaps, then repeat with complete inputs and tools.')}
    if repo:
        summary.update(comparison_validity=repo['comparison_validity'],confounders=repo['confounders'])
    return summary


def blocked_summary(objective, phase, reason):
    return {'schema':SCHEMA, 'scope':None, 'requested_objective':objective, 'objective_completion':'BLOCKED',
            'execution_status':phase, 'compatibility_status':'UNKNOWN', 'coverage_status':'NOT_EXECUTED',
            'statistics':{}, 'high_risk_findings':[], 'errors':[{'reason':str(reason)[:600]}], 'report_paths':{},
            'next_step':'Resolve the reported blocker and use a new output directory.'}
