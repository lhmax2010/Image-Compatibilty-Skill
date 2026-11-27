"""Stable explanatory codes and bounded export-removal observations."""
from collections import Counter, defaultdict
import re

from .elf import normalize_version


COVERAGE_CODES = {
    'Installed loader coverage': 'DIMENSION_NOT_EXECUTED',
    'manifest reuse': 'DIMENSION_NOT_EXECUTED',
    'collection coverage': 'COVERAGE_LIMITATION',
    'dynamic export collection coverage': 'EXPORT_INVENTORY_INCOMPLETE',
    'DT_NEEDED': 'DT_NEEDED_CHANGED',
    'ELF availability': 'ELF_AVAILABILITY_UNVERIFIED',
}
REASON_CODE = re.compile(r'[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*\Z')


def valid_reason_code(value):
    return isinstance(value, str) and REASON_CODE.fullmatch(value) is not None


def observation_reason(interface, status):
    if interface == 'DWARF type/layout ABI':
        return 'DWARF_ABI_CHANGED' if status == 'INCOMPATIBLE' else 'DWARF_ABI_UNAVAILABLE'
    if interface in COVERAGE_CODES:
        return COVERAGE_CODES[interface]
    if interface.endswith(':cross-compatibility coverage'):
        return 'DIMENSION_NOT_EXECUTED'
    if interface.endswith(' coverage'):
        return 'COVERAGE_LIMITATION'
    if interface.startswith('version definition:'):
        return 'VERSION_DEFINITION_REMOVED' if status == 'INCOMPATIBLE' else 'VERSION_DEFINITION_NOT_OBSERVED'
    if interface.endswith(':default lookup'):
        # Losing the lookup and selecting a different default are separate observations.
        return 'DEFAULT_VERSION_LOOKUP_LOST'
    if interface.endswith(':default symbol version'):
        return 'DEFAULT_SYMBOL_VERSION_CHANGED'
    return 'CONTRACT_DIFFERENCE' if status == 'INCOMPATIBLE' else 'CONTRACT_UNVERIFIED'


def identity(symbol):
    # Preserve the version explicitly carried by the parsed symbol or display name.
    name = symbol['name']
    base, sep, version = name.partition('@')
    return symbol.get('base_name') or base, normalize_version(symbol.get('version') or (version.lstrip('@') if sep else None))


def cxx_class(name):
    if not name.startswith('_Z'):
        return 'c'
    for prefix, kind in (('_ZTV', 'vtable'), ('_ZTI', 'typeinfo'), ('_ZTS', 'typeinfo_name'),
                         ('_ZTT', 'vtt'), ('_ZGV', 'guard'), ('_ZTh', 'thunk'), ('_ZTv', 'thunk'),
                         ('_ZTc', 'thunk')):
        if name.startswith(prefix):
            return kind
    return 'cxx_template' if re.search(r'I.+E', name[2:]) else 'cxx_other'


class Importers:
    def __init__(self, baseline, candidate):
        self.sides = {}
        for side, objects in (('baseline', baseline), ('candidate', candidate)):
            index = defaultdict(set)
            for obj in objects:
                if obj.get('elf_runtime_role') != 'DEBUG_ONLY':
                    for symbol in (*obj.get('imports', []), *obj.get('copy_relocations', [])):
                        index[identity(symbol)].add(obj['path'])
            self.sides[side] = index

    def removal(self, symbol, baseline_path, candidate_path):
        key = identity(symbol)
        counts = {}
        for side, provider in (('baseline', baseline_path), ('candidate', candidate_path)):
            paths = self.sides[side].get(key, set())
            if key[1] is not None and '@@' in symbol['name']:
                paths = paths | self.sides[side].get((key[0], None), set())
            counts[side] = len(paths) - (provider in paths)
        return {'binding': symbol.get('binding'), 'type': symbol.get('type'), 'versioned': key[1] is not None,
                'cxx_class': cxx_class(key[0]), 'observed_importers': counts}


def removed_exports(findings):
    kinds, types, bindings, reasons = Counter(), Counter(), Counter(), Counter()
    observed = Counter({'baseline': 0, 'candidate': 0})
    associations = observed.copy()
    versioned = 0
    for item in findings:
        info = item.get('removal_context')
        if info is None:
            continue
        kinds[info['cxx_class']] += 1
        types[info['type'] or 'UNKNOWN'] += 1
        bindings[info['binding'] or 'UNKNOWN'] += 1
        reasons[item['reason_code']] += 1
        versioned += info['versioned']
        for side in observed:
            observed[side] += info['observed_importers'][side] > 0
            associations[side] += info['observed_importers'][side]
    return {'findings': sum(reasons.values()), 'by_reason': dict(reasons), 'by_cxx_class': dict(kinds),
            'by_type': dict(types), 'by_binding': dict(bindings), 'versioned': versioned,
            'exports_with_observed_importers': dict(observed), 'observed_importer_associations': dict(associations)}


def incomplete_exports(objects):
    return dict(Counter(o.get('export_inventory_reason_code') or 'OBJECT_INCOMPLETE'
                        for o in objects if o.get('export_inventory_status') == 'UNKNOWN'))
