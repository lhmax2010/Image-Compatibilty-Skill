"""Reconcile package-local pairs with unique repository-wide observations."""
from collections import Counter, defaultdict

from .profile import runtime_object


def abi_key(obj):
    return tuple(obj.get(key) for key in ('class', 'machine', 'endianness'))


def indices(objects):
    by_path, by_soname = defaultdict(list), defaultdict(list)
    for obj in objects:
        if not runtime_object(obj) or not obj.get('complete'):
            continue
        abi = abi_key(obj)
        if all(abi[:2]):
            by_path[(obj['package_path'], *abi[:2])].append(obj['path'])
        if obj.get('soname') and all(abi):
            by_soname[(obj['soname'], *abi)].append(obj['path'])
    return by_path, by_soname


def reconcile(pairs, dictionaries):
    """Pair globally only when both sides uniquely identify one another."""
    baseline, candidate = dictionaries
    by_path, by_soname = indices(candidate.values())
    used = {pair['candidate_object'] for pair in pairs if pair['baseline_object'] and pair['candidate_object']}
    candidate_rows = {pair['candidate_object']: pair for pair in pairs if pair['candidate_object']}
    pending = {pair['baseline_object']: pair for pair in pairs if pair['baseline_object'] and not pair['candidate_object']}
    consumed, ambiguous = set(), {}
    for matching, catalog, key_for in (
            ('CROSS_PACKAGE_PATH', by_path, lambda o: (o['package_path'], *abi_key(o)[:2])),
            ('CROSS_PACKAGE_SONAME', by_soname, lambda o: (o.get('soname'), *abi_key(o)))):
        proposals = {}
        for path, pair in pending.items():
            if path in ambiguous:
                continue
            obj = baseline[path]
            if not runtime_object(obj) or not obj.get('complete'):
                continue
            entries = catalog.get(key_for(obj), ())
            if entries:
                proposals[path] = entries
        claimed = Counter(group[0] for group in proposals.values() if len(group) == 1)
        for path, matches in proposals.items():
            if (len(matches) == 1 and matches[0] not in used and claimed[matches[0]] == 1
                    and pending[path]['baseline_package_id'] != candidate_rows[matches[0]]['candidate_package_id']):
                name = matches[0]
                pending.pop(path).update(candidate_object=name, match=matching, safe_pair=True,
                                         candidate_package_id=candidate_rows[name]['candidate_package_id'])
                consumed.add(name)
                used.add(name)
                ambiguous.pop(path, None)
            else:
                ambiguous[path] = sorted(set(ambiguous.get(path, [])) | set(matches))
    return [pair for pair in pairs if pair['baseline_object'] or pair['candidate_object'] not in consumed], ambiguous
