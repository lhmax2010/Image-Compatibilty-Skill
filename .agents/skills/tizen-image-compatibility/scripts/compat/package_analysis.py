"""Indexed installed-RPM ownership and directional per-package contracts.
Archive availability, installed ownership and SDK ownership are distinct datasets.
"""
from collections import defaultdict
from .core import canonical, digest
from .coverage import check, obligation, summarize, combined, finding_check
from .linker import alias


def package_id(record, scope='runtime'):
    identity = [record.get(k, '') for k in ('name', 'epoch', 'version', 'release', 'arch')]
    return scope + ':' + digest(canonical(identity).encode())[:24]


class Ownership:
    def __init__(self, manifest, scope='runtime'):
        self.manifest = manifest
        self.inventory = manifest.get('package_inventory', {'status': 'UNKNOWN', 'installed_count': None, 'reason': 'No v1.2 installed RPM inventory'})
        self.files = {f['path']: f for f in manifest.get('filesystem', [])}
        self.lookup_cache = {}
        self.records = {}; self.by_path = defaultdict(set); self.by_canonical = defaultdict(set)
        instances = defaultdict(int)
        for record in sorted(manifest.get('packages', []), key=canonical):
            if record.get('provenance', {}).get('kind') != 'installed_rpmdb': continue
            ident = package_id(record, scope)
            instances[ident] += 1
            if ident in self.records:
                self.inventory = dict(self.inventory, status='PARTIAL', reason='Duplicate installed package identity')
                ident += ':instance:' + str(instances[ident])
            self.records[ident] = record
            for path in record.get('files', []):
                self.by_path[path].add(ident)
                if self.files.get(path, {}).get('type') != 'symlink':
                    resolved = alias(path, self.files)
                    if resolved: self.by_canonical[resolved].add(ident)
        declared = self.inventory.get('installed_count')
        discovered = len(manifest.get('packages', []))
        self.reconciliation = {'declared_installed_count': declared, 'discovered_records': discovered,
                               'assessed_records': len(self.records), 'unverified_records': discovered - len(self.records),
                               'consistent': declared == discovered == len(self.records) if declared is not None else None}
        if self.inventory.get('status') == 'COMPLETE' and not self.reconciliation['consistent']:
            self.inventory = dict(self.inventory, status='PARTIAL', installed_count=None, reason='Installed inventory count/provenance does not reconcile')
    def lookup(self, path):
        if path in self.lookup_cache: return self.lookup_cache[path]
        resolved = alias(path, self.files) if path else None
        direct = self.by_path.get(path, set())
        owners = direct or self.by_canonical.get(resolved, set())
        status = 'COMPLETE' if len(owners) == 1 and self.inventory.get('status') == 'COMPLETE' else 'UNKNOWN'
        result = {'path': path, 'resolved_path': resolved, 'owners': sorted(owners), 'status': status,
                'target_owners': sorted(self.by_canonical.get(resolved, set())),
                'reason': '' if status == 'COMPLETE' else 'Missing, multiple, or incomplete installed RPM ownership'}
        self.lookup_cache[path] = result
        return result


def version(record):
    return None if record is None else ':'.join([record.get('epoch', '0') or '0', record.get('version', '')]) + '-' + record.get('release', '') + '.' + record.get('arch', '')


def analyze_packages(a, b, findings, coverage):
    scopes = {}
    for label, manifest in (('baseline', a), ('candidate', b)):
        scopes[(label, 'runtime')] = Ownership(manifest)
        scopes[(label, 'sdk')] = Ownership(manifest.get('sdk_package_manifest', {}), 'sdk')
    baseline = {k: (r, scope) for scope in ('runtime', 'sdk') for k, r in scopes[('baseline', scope)].records.items()}
    candidate = {k: (r, scope) for scope in ('runtime', 'sdk') for k, r in scopes[('candidate', scope)].records.items()}
    left_groups = defaultdict(list); right_groups = defaultdict(list)
    for ident, (p, scope) in baseline.items(): left_groups[(p['name'], p['arch'], scope)].append(ident)
    for ident, (p, scope) in candidate.items(): right_groups[(p['name'], p['arch'], scope)].append(ident)
    matches = {}; unresolved = []; baseline_only = []; candidate_only = []
    for key in sorted(set(left_groups) | set(right_groups)):
        left, right = left_groups[key], right_groups[key]
        if len(left) == len(right) == 1: matches[left[0]] = right[0]
        elif not right and scopes[('candidate', key[2])].inventory.get('status') == 'COMPLETE': baseline_only.extend(left)
        elif not left and scopes[('baseline', key[2])].inventory.get('status') == 'COMPLETE': candidate_only.extend(right)
        else: unresolved.append({'name': key[0], 'arch': key[1], 'scope': key[2], 'baseline_ids': left, 'candidate_ids': right})
    reverse = {v: k for k, v in matches.items()}
    owned = defaultdict(lambda: {'elf': [], 'headers': [], 'development': [], 'ambiguous': []})
    unassigned = []
    for (label, scope), ownership in scopes.items():
        manifest = ownership.manifest
        for section, kind in (('elf_objects', 'elf'), ('public_headers', 'headers'), ('development', 'development')):
            for obj in manifest.get(section, []):
                association = ownership.lookup(obj['path'])
                item = {'path': obj['path'], 'ownership': association, 'evidence': obj.get('evidence', [])}
                if kind == 'elf': item.update(soname=obj.get('soname'), type=obj.get('type'), exports=obj.get('exports', []), needed=obj.get('needed', []))
                if not association['owners']: unassigned.append(dict(item, image=label, scope=scope, kind=kind))
                for ident in association['owners']:
                    owned[(label, ident)][kind].append(item)
                    if association['status'] != 'COMPLETE': owned[(label, ident)]['ambiguous'].append(obj['path'])
        # SDK compile evidence without an explicit installed SDK package manifest stays unassigned.
        if scope == 'runtime':
            sdk_owners = scopes[(label, 'sdk')]
            for header in (a if label == 'baseline' else b).get('sdk_headers', []):
                if not sdk_owners.lookup(header['path'])['owners']:
                    unassigned.append({'image': label, 'scope': 'sdk', 'kind': 'header', 'path': header['path'], 'reason': 'No reliable SDK package ownership'})
    related = defaultdict(list); uncertain = defaultdict(list); unassigned_findings = []
    candidate_findings = defaultdict(set)
    dependency_edges = defaultdict(set)
    path_findings = defaultdict(lambda: defaultdict(set))
    for f in findings:
        scope = 'sdk' if f['dimension'] == 'headers' or f['interface'] == 'Clang AST declarations' else 'runtime'
        path = f['component'].removeprefix('header:')
        consumer_label = f.get('consumer_image', 'baseline')
        path_findings[(consumer_label, scope, path)][f['dimension']].add(f['id'])
        consumer = scopes[(consumer_label, scope)].lookup(f.get('consumer_path', path))
        provider = scopes[('candidate', 'runtime')].lookup(f.get('provider_path'))
        f['package_ownership'] = {'scope': scope, 'consumer_image': consumer_label, 'consumer': consumer, 'candidate_provider': provider}
        associations = [(consumer_label, consumer)]
        if f.get('root_consumer'):
            root_label = f.get('root_consumer_image', 'baseline')
            root_owner = scopes[(root_label, 'runtime')].lookup(f['root_consumer'])
            f['package_ownership']['root_consumer'] = root_owner
            associations.append((root_label, root_owner))
        if f.get('provider_path'):
            for provider_id in provider['owners']:
                for label, association in associations:
                    for consumer_id in association['owners']:
                        dependency_edges[(provider_id, label, consumer_id, provider['status'], association['status'])].add(f['id'])
            associations.append(('candidate', provider))
        assigned = False
        for label, association in associations:
            for ident in association['owners']:
                if label == 'candidate': candidate_findings[ident].add(f['id'])
                key = ident if label == 'baseline' else reverse.get(ident)
                if key:
                    (related if association['status'] == 'COMPLETE' else uncertain)[key].append(f)
                    assigned = True
        if not assigned: unassigned_findings.append(f['id'])
    cov_index = {}
    for dim, info in coverage.items():
        for unit in info['units']: cov_index[(dim, unit['interface'])] = unit
    sdk_checks = defaultdict(list)
    for manifest in (a, b):
        for e in manifest.get('expected_tests', []):
            if e['kind'] == 'header': sdk_checks[e['name'].removeprefix('header:')].append(obligation(e['id'], e['checks']))
    # Candidate replacement hints use indexed shared files; never establish a rename/split as fact.
    replacement_hints = {}
    unmatched_candidates = set(candidate_only)
    for ident in baseline_only:
        record, scope = baseline[ident]
        overlaps = defaultdict(set)
        for path in record.get('files', []):
            if scopes[('baseline', scope)].files.get(path, {}).get('type') != 'file': continue
            for cid in scopes[('candidate', scope)].lookup(path)['owners']:
                if cid in unmatched_candidates and candidate[cid][0]['arch'] == record['arch']:
                    overlaps[cid].add(path)
        if overlaps:
            replacement_hints[ident] = {'kind': 'possible_split' if len(overlaps) > 1 else 'possible_rename_or_replacement',
                'status': 'UNKNOWN', 'candidates': [{'id': cid, 'shared_paths': sorted(paths)} for cid, paths in sorted(overlaps.items())],
                'reason': 'Shared owned paths are clues only; package lineage and interface equivalence are not established'}
    baseline_only_set = set(baseline_only)
    results = []
    for ident, (record, scope) in sorted(baseline.items(), key=lambda p: (p[1][0]['name'], p[0])):
        peer_id = matches.get(ident); peer = candidate.get(peer_id, (None, None))[0]
        owner = scopes[('baseline', scope)]; other_owner = scopes[('candidate', scope)]
        inventory_ok = owner.inventory.get('status') == other_owner.inventory.get('status') == 'COMPLETE'
        interfaces = owned[('baseline', ident)]; fs = list({f['id']: f for f in related[ident]}.values())
        availability = obligation('package availability', [check('identity', 'COMPATIBLE' if peer and inventory_ok else 'UNKNOWN', reason='' if peer and inventory_ok else 'Unmatched/ambiguous package; rename, split or replacement not proven')])
        meta_keys = ('epoch', 'version', 'release', 'arch', 'provides', 'requires', 'conflicts', 'obsoletes', 'files')
        metadata = obligation('package metadata', [check(k, 'IDENTICAL' if peer and record.get(k) == peer.get(k) and inventory_ok else 'UNKNOWN', record.get('evidence', []), 'Metadata equality/change only') for k in meta_keys])
        dimensions = {}
        for name, dims, paths in (
            ('abi', ('elf', 'abi'), [x['path'] for x in interfaces['elf']]),
            ('api', ('api', 'headers', 'packages'), [x['path'] for x in interfaces['headers'] + interfaces['development']]),
            ('linking', ('linking',), [x['path'] for x in interfaces['elf']])):
            paths = sorted(set(paths)); path_set = set(paths)
            check_list = []; associated = [f for f in fs if f['dimension'] in dims]
            for path in paths:
                source_units = [cov_index[(d, k)] for d in dims for k in (path, path + ':exports', path + ':type-layout') if (d, k) in cov_index]
                if scope == 'sdk':
                    # Identical virtual paths do not make SDK and runtime ELF evidence interchangeable.
                    source_units = sdk_checks[path] if name == 'api' else []
                if source_units:
                    for u in source_units:
                        c = check(u['interface'], u['status'], u['evidence'], '; '.join(u['limitations']))
                        c['verification'] = u['verification']; check_list.append(c)
                else: check_list.append(check(path, reason='Interface collected but required analysis unavailable'))
            # Development metadata is necessary, but never sufficient for semantic API proof.
            if name == 'api' and paths: check_list.append(check('complete API semantics', reason='Headers/AST probes do not prove every source-level contract'))
            if not check_list:
                manifest_complete = owner.manifest.get('collection_complete') is True and record.get('collection_status') == 'COMPLETE'
                files_known = all(p in owner.files for p in record.get('files', []))
                no_relevant = not interfaces['elf'] and not interfaces['headers'] and not interfaces['development']
                unsupported_files = any(p.endswith(('.a', '.h', '.hpp', '.hh', '.hxx', '.pc', '.cmake')) or '.so' in p for p in record.get('files', []))
                can_na = inventory_ok and manifest_complete and files_known and no_relevant and not unsupported_files and not interfaces['ambiguous']
                check_list = [check('applicability', 'NOT_APPLICABLE' if can_na else 'UNKNOWN', reason='' if can_na else 'Runtime/SDK interface evidence insufficient')]
            if interfaces['ambiguous'] or uncertain[ident]: check_list.append(check('ownership', reason='Multiple/incomplete owners; findings retained without definitive attribution'))
            # A provider finding is not the provider package's own dependency contract; retain its reference without transferring consumer failure.
            associated = [f for f in associated if f['component'].removeprefix('header:') in path_set or f.get('consumer_path') in path_set or (name == 'linking' and f.get('root_consumer') in path_set)]
            dimension = obligation(name, check_list, associated)
            dimension['coverage'] = summarize([obligation(c['id'], [c]) for c in check_list])
            dimensions[name] = dimension
        components = [availability, metadata, *dimensions.values()]
        overall_checks = []
        for u in components:
            c = check(u['interface'], u['status'], u['evidence'], '; '.join(u['limitations'])); c['verification'] = u['verification']; overall_checks.append(c)
        overall = obligation(ident, overall_checks)
        if all(d['status'] == 'NOT_APPLICABLE' for d in dimensions.values()) and overall['status'] in ('COMPATIBLE', 'IDENTICAL'):
            overall.update(status='NOT_APPLICABLE', verification='NOT_APPLICABLE')
        results.append({'match_status': 'matched' if peer else 'baseline_only' if ident in baseline_only_set else 'unresolved',
                        'replacement_hint': replacement_hints.get(ident), 'id': ident, 'name': record['name'], 'scope': scope, 'arch': record['arch'],
                        'baseline_version': version(record), 'candidate_version': version(peer),
                        'baseline_package': record, 'candidate_package': peer,
                        'availability': availability, 'metadata': metadata, **dimensions,
                        'overall': overall['status'], 'verification': overall['verification'], 'confidence': overall['confidence'],
                        'limitations': overall['limitations'], 'coverage': summarize(components),
                        'owned_interfaces': interfaces, 'candidate_interfaces': owned[('candidate', peer_id)] if peer_id else None,
                        'finding_ids': sorted({f['id'] for f in fs}), 'ambiguous_finding_ids': sorted({f['id'] for f in uncertain[ident]}),
                        'missing_interfaces': sorted({f['id'] for f in fs if f['candidate'] is None and f['baseline'] is not None}),
                        'evidence': sorted({e for f in fs for e in f.get('evidence', [])} | set(record.get('evidence', [])))})
    summary = {'baseline': scopes[('baseline', 'runtime')].inventory, 'candidate': scopes[('candidate', 'runtime')].inventory,
               'baseline_package_count': scopes[('baseline', 'runtime')].inventory.get('installed_count'),
               'candidate_package_count': scopes[('candidate', 'runtime')].inventory.get('installed_count'),
               'matched_packages': [{'baseline': k, 'candidate': v} for k, v in sorted(matches.items())],
               'baseline_only': baseline_only, 'candidate_only': candidate_only, 'unresolved_matches': unresolved,
               'candidate_additions': [{'id': i, 'package': candidate[i][0], 'inventory_status': 'ADDED', 'status': 'UNKNOWN', 'scope': candidate[i][1], 'reason': 'Inventory addition only; ABI/API compatibility unverified'} for i in candidate_only],
               'available_archives': {'baseline': a.get('available_packages', []), 'candidate': b.get('available_packages', [])},
               'count_reconciliation': {label + ':' + scope: owner.reconciliation for (label, scope), owner in scopes.items()},
               'unverified_package_records': [{'image': label, 'scope': scope, 'package': p, 'status': 'UNKNOWN'} for (label, scope), owner in scopes.items() for p in owner.manifest.get('packages', []) if p.get('provenance', {}).get('kind') != 'installed_rpmdb'],
               'candidate_assessments': [{'id': i, 'package': record, 'scope': scope,
                    'match_status': 'matched' if i in reverse else 'candidate_only' if i in unmatched_candidates else 'unresolved',
                    'baseline_assessment_id': reverse.get(i), 'status': 'UNKNOWN',
                    'reason': 'See directional baseline assessment; candidate inventory alone does not prove compatibility',
                    'owned_interfaces': owned[('candidate', i)], 'finding_ids': sorted(candidate_findings[i])} for i, (record, scope) in sorted(candidate.items())],
               'provider_consumers': [{'provider_image': 'candidate', 'provider_package': p, 'consumer_image': label, 'consumer_package': c,
                    'status': 'COMPLETE' if ps == cs == 'COMPLETE' else 'UNKNOWN', 'finding_ids': sorted(ids)}
                    for (p, label, c, ps, cs), ids in sorted(dependency_edges.items())],
               'interface_findings': [{'image': label, 'scope': scope, 'path': path, 'dimensions': {d: sorted(ids) for d, ids in sorted(dims.items())}}
                    for (label, scope, path), dims in sorted(path_findings.items())],
               'replacement_hints': replacement_hints,
               'sdk_inventories': {label: scopes[(label, 'sdk')].inventory for label in ('baseline', 'candidate')},
               'unassigned_interfaces': unassigned, 'unassigned_finding_ids': sorted(set(unassigned_findings))}
    return summary, results
