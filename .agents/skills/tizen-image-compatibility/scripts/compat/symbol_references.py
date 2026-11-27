"""Resolve compact ABI symbol references without changing a finding's payload."""
from functools import lru_cache

from .core import read_manifest


def compact_findings(a, b, results):
    objects = [{obj['path']:obj for obj in m['elf_objects']} for m in (a,b)]
    pairs = {p['component']:p for p in (results.get('repository') or {}).get('elf_pairs', [])}

    @lru_cache(maxsize=32)
    def symbols(side, path):
        rows = objects[side].get(path, {}).get('exports', [])
        return {row['name']:row for row in rows}

    compact = []
    for item in results['findings']:
        if item['dimension'] == 'abi':
            pair = pairs.get(item['component'], {})
            updates = {}
            for i, side in enumerate(('baseline', 'candidate')):
                value = item.get(side)
                path = pair.get(side+'_object', item['component'])
                if isinstance(value, dict) and 'name' in value and symbols(i, path).get(value['name']) == value:
                    updates[side] = {'$symbol':[path, value['name']]}
            if updates:
                item = item | updates
        compact.append(item)
    return compact


def resolve_finding(item, lookup):
    updates = {}
    for side in ('baseline', 'candidate'):
        value = item.get(side)
        if isinstance(value, dict) and '$symbol' in value:
            path, name = value['$symbol']
            symbol = lookup(side, path).get(name)
            if symbol is None:
                raise ValueError('Finding has an unresolved manifest symbol reference')
            updates[side] = symbol
    return item | updates if updates else item


def resolve_findings(source, results):
    """Return legacy-shaped findings from either results format."""
    @lru_cache(maxsize=2)
    def objects(side):
        manifest = read_manifest(source / (side+'-manifest.json'))
        return {obj['path']:obj['exports'] for obj in manifest['elf_objects'] if 'exports' in obj}

    @lru_cache(maxsize=32)
    def lookup(side, path):
        return {row['name']:row for row in objects(side).get(path, [])}

    return [resolve_finding(item, lookup) for item in results['findings']]
