"""Independent compatibility outcome and explicit required-check completeness (1.2)."""
from collections import defaultdict
from .core import DIMENSIONS, SEVERITIES
from .elf import dynamic_exports, symbol_identity

SECTIONS = {'elf': 'elf_objects', 'abi': 'elf_objects', 'linking': 'elf_objects', 'api': 'public_headers',
            'headers': 'public_headers', 'compiler_runtime': 'runtime_libraries', 'kernel': 'kernel',
            'ipc': 'ipc', 'commands': 'commands', 'filesystem': 'filesystem', 'packages': 'packages',
            'services': 'services', 'security': 'security_interfaces', 'hardware': 'hardware',
            'network': 'network', 'performance': 'elf_objects'}


def combined(statuses):
    statuses = list(statuses)
    if 'INCOMPATIBLE' in statuses: return 'INCOMPATIBLE'
    active = [s for s in statuses if s != 'NOT_APPLICABLE']
    if statuses and not active: return 'NOT_APPLICABLE'
    if not active or 'UNKNOWN' in active: return 'UNKNOWN'
    if all(s == 'IDENTICAL' for s in active): return 'IDENTICAL'
    return 'COMPATIBLE' if all(s in ('COMPATIBLE', 'IDENTICAL') for s in active) else 'UNKNOWN'


def check(name, status='UNKNOWN', evidence=(), reason='', executed=False):
    return {'id': name, 'status': status, 'verification': 'NOT_APPLICABLE' if status == 'NOT_APPLICABLE' else
            'COMPLETE' if status in ('IDENTICAL', 'COMPATIBLE', 'INCOMPATIBLE') else 'PARTIAL' if executed or evidence else 'NOT_EXECUTED',
            'evidence': sorted(set(evidence)), 'reason': reason}


def obligation(name, checks, findings=()):
    """Only unique mandatory checks determine completeness; failures never erase gaps."""
    checks = list(checks)
    if len({c['id'] for c in checks}) != len(checks):
        raise ValueError('Duplicate required check ID in ' + name)
    active = [c for c in checks if c['verification'] != 'NOT_APPLICABLE']
    outcome = combined([c['status'] for c in checks] + [f['status'] for f in findings])
    verification = ('NOT_APPLICABLE' if checks and not active else 'COMPLETE' if active and all(c['verification'] == 'COMPLETE' for c in active)
                    else 'PARTIAL' if any(c['verification'] in ('COMPLETE', 'PARTIAL') for c in active) else 'NOT_EXECUTED')
    if verification == 'COMPLETE' and any(f['status'] == 'UNKNOWN' for f in findings): verification = 'PARTIAL'
    if verification == 'NOT_APPLICABLE' and outcome != 'NOT_APPLICABLE': verification = 'PARTIAL'
    if outcome in ('COMPATIBLE', 'IDENTICAL') and verification not in ('COMPLETE', 'NOT_APPLICABLE'): outcome = 'UNKNOWN'
    return {'interface': name, 'status': outcome, 'compatibility': outcome, 'verification': verification,
            'required_checks': checks, 'finding_ids': sorted({f['id'] for f in findings}),
            'evidence': sorted({e for c in checks for e in c['evidence']} | {e for f in findings for e in f.get('evidence', [])}),
            'confidence': 'high' if verification == 'COMPLETE' else 'low',
            'limitations': [c['reason'] or c['id'] for c in active if c['verification'] != 'COMPLETE']}


def summarize(units, excluded=False):
    units = list(units)
    applicable = [u for u in units if u['verification'] != 'NOT_APPLICABLE']
    n = len(applicable)
    complete = sum(u['verification'] == 'COMPLETE' for u in applicable)
    compatible = sum(u['status'] in ('IDENTICAL', 'COMPATIBLE') for u in applicable)
    incompatible = sum(u['status'] == 'INCOMPATIBLE' for u in applicable)
    coverage = round(100 * complete / n, 2) if n and not excluded else None
    rate = round(100 * compatible / n, 2) if n and not excluded else None
    return {'excluded': excluded, 'applicable': n, 'verified': complete, 'completely_verified': complete,
            'partially_verified': sum(u['verification'] == 'PARTIAL' for u in applicable),
            'unexecuted': sum(u['verification'] == 'NOT_EXECUTED' for u in applicable),
            'not_applicable': len(units) - n, 'compatible': compatible, 'confirmed_compatible': compatible,
            'incompatible': incompatible, 'confirmed_incompatible': incompatible, 'unknown': n - compatible - incompatible,
            'coverage_percent': coverage, 'complete_verification_coverage_percent': coverage,
            'compatibility_percent': rate, 'units': units}


def finding_check(name, findings):
    fs = list({f['id']: f for f in findings}.values())
    result = check(name, combined(f['status'] for f in fs), [e for f in fs for e in f.get('evidence', [])],
                   'Missing/unsupported check' if not fs else '', bool(fs))
    # A confirmed failure alongside unknown evidence is still partially verified.
    if any(f['status'] == 'UNKNOWN' for f in fs): result['verification'] = 'PARTIAL'
    return result


def coverage_report(a, b, findings, tests, matrix, config):
    grouped = defaultdict(list); root_findings = defaultdict(list)
    for f in findings:
        grouped[(f['dimension'], f['component'])].append(f)
        if f['dimension'] == 'linking' and (f.get('root_consumer_image') == 'baseline' or 'baseline consumers on candidate' in f['interface']):
            root_findings[f.get('root_consumer', f['component'])].append(f)
    right = {key: {o.get('path', o.get('name')): o for o in b.get(key, [])} for key in set(SECTIONS.values())}
    output = {}
    for dim in DIMENSIONS:
        if dim not in config['analysis']['modes']:
            output[dim] = summarize([], True); continue
        units = []
        for obj in a.get(SECTIONS.get(dim, ''), []):
            path = obj.get('path') or (obj['name'] + ':' + obj['arch'] if dim == 'packages' else obj.get('name'))
            fs = grouped[(dim, path)]
            peer = right.get(SECTIONS.get(dim), {}).get(obj.get('path', obj.get('name')))
            if dim == 'abi':
                layout = [f for f in fs if f['interface'] == 'DWARF type/layout ABI']
                surface = [f for f in fs if f not in layout]
                complete = bool(peer and obj.get('complete') and peer.get('complete')
                                and obj.get('export_inventory_complete') is True and peer.get('export_inventory_complete') is True)
                checks = [check('collection', 'COMPATIBLE' if complete else 'UNKNOWN')]
                by_symbol = defaultdict(list)
                for f in surface: by_symbol[f['interface'].split(':', 1)[0]].append(f)
                versions = defaultdict(list)
                for s in dynamic_exports(peer or {}):
                    identity = symbol_identity(s['name']); versions[(identity['base_name'], identity['version'])].append(s)
                baseline_exports = list(dynamic_exports(obj))
                for s in baseline_exports:
                    identity = symbol_identity(s['name']); matches = versions[(identity['base_name'], identity['version'])]
                    relevant = by_symbol[s['name']] + (by_symbol[identity['base_name']] if identity['base_name'] != s['name'] else [])
                    if relevant:
                        c = finding_check('export:' + s['name'], relevant)
                    else:
                        keys = ('type', 'binding', 'visibility') + (('size',) if s['type'] in ('OBJECT', 'TLS') else ())
                        same = complete and any(all(s.get(k) == x.get(k) for k in keys) for x in matches)
                        c = check('export:' + s['name'], 'COMPATIBLE' if same else 'UNKNOWN')
                    checks.append(c)
                if not baseline_exports:
                    checks.append(check('export inventory', 'COMPATIBLE' if complete else 'UNKNOWN'))
                units.append(obligation(path + ':exports', checks, surface))
                units.append(obligation(path + ':type-layout', [finding_check('DWARF type/layout ABI', layout)], layout))
            elif dim == 'linking':
                applicable = [f for f in fs if f.get('root_consumer', path) == path and ('baseline consumers on candidate' in f['interface'])]
                slots = defaultdict(list)
                for f in applicable: slots[f.get('check_id', f['interface'])].append(f)
                required = {'DT_NEEDED:' + n for n in obj.get('needed', [])} | {'import:' + s['name'] for s in obj.get('imports', [])}
                required |= {'version:' + r['file'] + ':' + r['name'] for r in obj.get('version_requirements', [])}
                if obj.get('interpreter'): required.add('dynamic loader')
                required |= set(slots)
                checks = [finding_check(k, slots[k]) for k in sorted(required)]
                # Closure/context completeness is independent of a single failed dependency.
                closure_findings = root_findings[path]
                checks.append(finding_check('scope/closure', closure_findings))
                units.append(obligation(path, checks, closure_findings))
            elif dim == 'api':
                units.append(obligation(path, [check('header availability', 'COMPATIBLE' if peer else 'UNKNOWN'),
                    finding_check('semantic contract', fs)], fs))
            elif dim == 'headers':
                continue
            else:
                checks = [finding_check('observed contract', fs)]
                if dim in ('commands', 'compiler_runtime', 'kernel', 'filesystem', 'packages', 'services', 'security', 'hardware', 'network', 'ipc'):
                    checks.append(check('behavior/semantic verification', reason='Inventory or metadata comparison does not prove behavior'))
                units.append(obligation(path, checks, fs))
        if dim == 'headers':
            for m in (a, b):
                for e in m.get('expected_tests', []):
                    if e['kind'] == 'header': units.append(obligation(e['id'], e['checks'], []))
        if dim == 'runtime':
            for cell in matrix:
                checks = cell.get('required_checks') or [check('expected test manifest', reason='No v1.2 expected test manifest')]
                units.append(obligation(cell['compiler'] + ':' + cell['image'], checks))
            for m in (a, b):
                for e in m.get('expected_tests', []):
                    if e.get('compiler') == 'custom': units.append(obligation(e['id'], e['checks']))
        if not units: units = [obligation('inventory/assessment unavailable', [check('inventory', reason='Applicability unknown; no complete inventory/assessment')])]
        output[dim] = summarize(units)
    failures = []
    for dim, minimum in config['ci']['minimum_coverage'].items():
        actual = output[dim]['coverage_percent']
        if actual is None or actual < minimum: failures.append({'dimension': dim, 'minimum_percent': minimum, 'actual_percent': actual})
    threshold = SEVERITIES.index(config['ci']['fail_on'])
    incompatible = [f['id'] for f in findings if f['status'] == 'INCOMPATIBLE' and SEVERITIES.index(f['severity']) <= threshold]
    # Reused stage/obligation failures may have no surviving finding row. Treat these as HIGH.
    obligation_failures = [{'dimension': dim, 'interface': u['interface'], 'severity': 'HIGH'}
                          for dim, info in output.items() for u in info['units']
                          if u['status'] == 'INCOMPATIBLE' and not u['finding_ids'] and SEVERITIES.index('HIGH') <= threshold]
    strict = config['ci']['strict'] and any(c['partially_verified'] or c['unexecuted'] or c['unknown'] for c in output.values())
    gate = {'status': 'FAIL' if failures or incompatible or obligation_failures or strict else 'PASS',
            'coverage_status': 'FAIL' if failures else 'PASS', 'compatibility_status': 'FAIL' if incompatible or obligation_failures else 'PASS',
            'strict_status': 'FAIL' if strict else 'PASS', 'failures': failures,
            'compatibility_failures': incompatible, 'compatibility_obligation_failures': obligation_failures, 'thresholds': config['ci']['minimum_coverage']}
    return output, gate
