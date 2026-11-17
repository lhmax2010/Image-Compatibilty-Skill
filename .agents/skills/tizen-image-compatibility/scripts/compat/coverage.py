"""Coverage of baseline contract obligations, never a ratio of finding rows.
One component can emit thousands of findings but cannot multiply its coverage credit.
"""
from .core import DIMENSIONS

SECTIONS = {'elf': 'elf_objects', 'abi': 'elf_objects', 'linking': 'elf_objects', 'api': 'public_headers',
            'headers': 'public_headers', 'compiler_runtime': 'runtime_libraries', 'kernel': 'kernel',
            'ipc': 'ipc', 'commands': 'commands', 'filesystem': 'filesystem', 'packages': 'packages',
            'services': 'services', 'security': 'security_interfaces', 'hardware': 'hardware',
            'network': 'network', 'performance': 'elf_objects'}


def combined(statuses):
    if 'INCOMPATIBLE' in statuses:
        return 'INCOMPATIBLE'
    if not statuses or 'UNKNOWN' in statuses:
        return 'UNKNOWN'
    return 'COMPATIBLE' if all(s in ('COMPATIBLE', 'IDENTICAL') for s in statuses) else 'UNKNOWN'


def coverage_report(a, b, findings, tests, matrix, config):
    output = {}
    for dim in DIMENSIONS:
        if dim not in config['analysis']['modes']:
            output[dim] = {'excluded': True, 'applicable': 0, 'verified': 0, 'compatible': 0,
                           'incompatible': 0, 'unknown': 0, 'coverage_percent': None, 'compatibility_percent': None, 'units': []}
            continue
        units = {}
        for obj in a.get(SECTIONS.get(dim, ''), []):
            key = obj.get('path') or (obj['name'] + ':' + obj['arch'] if dim == 'packages' else obj.get('name'))
            if dim == 'abi':
                units[key + ':exports'] = []
                units[key + ':type-layout'] = []
            else:
                units[key] = []
        if dim == 'runtime':
            units = {c['compiler'] + ':' + c['image']: [c['runtime_status']] for c in matrix}
            for probe in config['runtime']['probes']:
                for label in ('baseline', 'candidate'):
                    matches = [t['status'] for t in tests if t['id'] == 'custom:' + probe['name'] and t['image'] == label and t['kind'] == 'runtime']
                    units['custom:' + probe['name'] + ':' + label] = matches
        if dim == 'headers':
            # Header availability/probing is separate from runtime-image API inventory.
            for m in (a, b):
                for header in m.get('sdk_headers', []):
                    units.setdefault(header['path'], [])
            for path in units:
                matched = [t for t in tests if t.get('name') == 'header:' + path and t.get('image') == 'candidate']
                units[path] += [t['status'] for t in matched]
                expected = sum(config['cross_compilation'][k + '_tests'] for k in ('c', 'cpp') if k != 'c' or path.endswith('.h')) * 2
                if len(matched) < expected:
                    units[path].append('UNKNOWN')
        for f in findings:
            if f['dimension'] != dim:
                continue
            key = f['component']
            if dim == 'abi':
                key += ':type-layout' if f['interface'] == 'DWARF type/layout ABI' else ':exports'
            if key in units and dim not in ('headers', 'runtime'):
                units[key].append(f['status'])
        # A dimension with no inventory isn't proven inapplicable. Explicitly keep a discovery obligation.
        if not units:
            units['inventory/assessment unavailable'] = []
        states = [{'interface': k, 'status': combined(v)} for k, v in sorted(units.items())]
        compatible = sum(u['status'] == 'COMPATIBLE' for u in states)
        incompatible = sum(u['status'] == 'INCOMPATIBLE' for u in states)
        verified = compatible + incompatible
        total = len(states)
        output[dim] = {'excluded': False, 'applicable': total, 'verified': verified,
                       'compatible': compatible, 'incompatible': incompatible, 'unknown': total - verified,
                       'coverage_percent': round(100 * verified / total, 2),
                       'compatibility_percent': round(100 * compatible / total, 2), 'units': states}
    failures = []
    for dim, minimum in config['ci']['minimum_coverage'].items():
        actual = output[dim]['coverage_percent']
        if actual is None or actual < minimum:
            failures.append({'dimension': dim, 'minimum_percent': minimum, 'actual_percent': actual})
    gate = {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
            'thresholds': config['ci']['minimum_coverage']}
    return output, gate
