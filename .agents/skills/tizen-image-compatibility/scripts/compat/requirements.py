"""Bounded evidence for requirements against RPM available sets."""
from collections import Counter, defaultdict, deque

from .core import canonical, finding
from .elf import duplicate_dynsym_names, dynamic_exports, normalize_version, symbol_identity, version_nodes
from .profile import runtime_object
from .report_io import csv_rows
from .repository_pairing import abi_key


EXAMPLE_LIMIT = 1000
DEPTH_LIMIT = 32
CSV_COLUMNS = ('id','scope','consumer','package_id','package_nevra','kind','soname','version','symbol',
               'status','severity','reason_code','baseline','candidate','evidence','potential_impact',
               'suppressed_by','suppressed_dependents','copy_size')
REASONS = {'DT_NEEDED':'NEEDED_SONAME_UNAVAILABLE', 'VERSION_NODE':'VERSION_NODE_UNAVAILABLE',
           'VERSIONED_IMPORT':'VERSIONED_SYMBOL_UNAVAILABLE', 'UNVERSIONED_IMPORT':'UNVERSIONED_SYMBOL_NOT_IN_CLOSURE', 'COPY_RELOCATION':'VERSIONED_SYMBOL_UNAVAILABLE'}


class Providers:
    """Index observed primary objects and the number offering each contract."""
    def __init__(self, objects):
        self.total, self.complete = Counter(), Counter()
        self.nodes, self.qualified = Counter(), Counter()
        self.fallback = Counter()
        self.copy_sizes = Counter()
        self.copy_objects = Counter()
        self.ambiguous_copy_objects = set()
        self.default_by_provider = defaultdict(Counter)
        self.edges = defaultdict(set)
        self.closures = {}
        seen = set()
        for obj in objects:
            if not runtime_object(obj) or not obj.get('complete') or not obj.get('soname') or not all(abi_key(obj)):
                continue
            key = (abi_key(obj), obj['soname'])
            unique = (key, obj.get('sha256') or obj['path'])
            if unique in seen:
                continue
            seen.add(unique)
            self.total[key] += 1
            self.edges[key].update(obj.get('needed', []))
            if obj.get('export_inventory_complete') is not True or duplicate_dynsym_names(obj):
                continue
            self.complete[key] += 1
            nodes = version_nodes(obj)
            self.nodes.update((key, node) for node in nodes)
            identities = [symbol_identity(s['name']) for s in dynamic_exports(obj)]
            if nodes:
                self.qualified.update({(key, s['base_name'], s['version']) for s in identities if s['version']})
            else:
                self.fallback.update({(key,s['base_name']) for s in identities})
            sizes = defaultdict(list)
            for row, sym in zip(dynamic_exports(obj), identities):
                if row.get('type') == 'OBJECT' and sym['version']:
                    sizes[key, sym['base_name'], sym['version']].append(row.get('size'))
            for identity, size_values in sizes.items():
                if len(size_values) != 1:
                    self.ambiguous_copy_objects.add(identity)
                else:
                    self.copy_sizes[(*identity, size_values[0])] += 1
                    self.copy_objects[identity] += 1
            self.default_by_provider[key].update({s['base_name'] for s in identities
                                                  if not s['version'] or s['default_version']})

    def closure(self, abi, needed):
        key = abi, tuple(sorted(set(needed)))
        if key not in self.closures:
            seen, guaranteed, partial = set(), set(), set()
            queue = deque((name,1) for name in key[1])
            incomplete = False
            while queue:
                name, depth = queue.popleft()
                if name in seen:
                    continue
                if depth > DEPTH_LIMIT:
                    incomplete = True
                    continue
                seen.add(name)
                bucket = abi, name
                total = self.total[bucket]
                incomplete |= self.complete[bucket] != total or total == 0
                for symbol, present in self.default_by_provider[bucket].items():
                    (guaranteed if present==total else partial).add(symbol)
                queue.extend((child,depth+1) for child in sorted(self.edges[bucket]) if child not in seen)
            self.closures[key] = guaranteed, partial, incomplete
        return self.closures[key]

    def evaluate(self, abi, needed, requirement):
        kind, soname, version, name, criterion = requirement
        bucket = abi, soname
        total = self.total[bucket]
        if kind == 'DT_NEEDED':
            return 'SATISFIED' if total else 'MISSING'
        if kind == 'UNVERSIONED_IMPORT':
            definite, partial, incomplete = self.closure(abi, needed)
            return ('SATISFIED' if name in definite else 'AMBIGUOUS' if name in partial else
                    'INCOMPLETE' if incomplete else 'MISSING')
        if kind == 'VERSION_NODE':
            if not total:
                return 'NO_PROVIDER'
            present = self.nodes[bucket,version]
        elif kind == 'COPY_RELOCATION':
            if (bucket,name,version) in self.ambiguous_copy_objects:
                return 'AMBIGUOUS'
            present = self.copy_sizes[bucket,name,version,criterion]
            if (total and total == self.complete[bucket] == self.copy_objects[bucket,name,version]
                    and not present):
                return 'SIZE_MISMATCH'
            if self.copy_objects[bucket,name,version] > present:
                return 'AMBIGUOUS'
        else:
            present = self.qualified[bucket,name,version] + self.fallback[bucket,name]
        return ('SATISFIED' if total and present == total else 'AMBIGUOUS' if present else
                'INCOMPLETE' if self.complete[bucket] != total else 'MISSING')


def obligations(obj):
    rows = {('DT_NEEDED',soname,None,None,False) for soname in obj.get('needed', [])}
    rows.update(('VERSION_NODE',r['file'],normalize_version(r['name']),None,False) for r in obj.get('version_requirements', []))
    for sym in obj.get('imports', []):
        ident = symbol_identity(sym['name'])
        weak = sym.get('binding') == 'WEAK'
        if ident['version']:
            rows.add(('VERSIONED_IMPORT',sym.get('version_file'),ident['version'],ident['base_name'],weak))
        elif not weak:
            rows.add(('UNVERSIONED_IMPORT',None,None,ident['base_name'],False))
    rows.update(('COPY_RELOCATION', item.get('provider_soname'), normalize_version(item['version']),
                 symbol_identity(item['name'])['base_name'], item['size']) for item in obj.get('copy_relocations', []))
    # None values are valid for unqualified slots, so compare display keys.
    return sorted(rows, key=lambda row: tuple(str(value) for value in row))


def classify(requirement, before, after, candidate_complete):
    kind, _, _, _, weak = requirement
    if before != 'SATISFIED':
        return 'UNKNOWN','LOW','ALSO_UNSATISFIED_IN_BASELINE'
    if after == 'SATISFIED':
        return None
    if after == 'AMBIGUOUS':
        return 'UNKNOWN','MEDIUM','PROVIDER_AMBIGUOUS'
    if kind != 'COPY_RELOCATION' and weak:
        return 'UNKNOWN','LOW','WEAK_REFERENCE_UNSATISFIED'
    if kind == 'UNVERSIONED_IMPORT':
        return 'UNKNOWN','MEDIUM','UNVERSIONED_SYMBOL_NOT_IN_CLOSURE'
    if after == 'NO_PROVIDER':
        return 'UNKNOWN','MEDIUM','VERSION_PROVIDER_UNAVAILABLE'
    if after == 'INCOMPLETE' or not candidate_complete:
        return 'UNKNOWN','MEDIUM','REQUIREMENT_INVENTORY_INCOMPLETE'
    return 'INCOMPATIBLE','HIGH','COPY_RELOC_SIZE_CHANGED' if after == 'SIZE_MISMATCH' else REASONS[kind]


def aggregate_consumer(rows):
    """Keep the diagnostic rows and attach each suppressed row to its finding."""
    reason = 'ALSO_UNSATISFIED_IN_BASELINE'
    missing = {row['soname']: row for row in rows if row['kind'] == 'DT_NEEDED'
               and row['reason_code'] in (reason, 'NEEDED_SONAME_UNAVAILABLE')}
    baseline = dict(missing)
    for row in rows:
        if row['reason_code'] == reason:
            baseline.setdefault(row['soname'], row)
    for row in rows:
        anchor = missing.get(row['soname']) if row['kind'] in ('VERSION_NODE', 'VERSIONED_IMPORT', 'COPY_RELOCATION') else None
        if anchor is None and row['reason_code'] == reason:
            anchor = baseline[row['soname']]
        row['suppressed_by'] = ''
        if anchor is not None and anchor is not row:
            row['suppressed_by'] = anchor['id']
            anchor['suppressed_dependents'] = anchor.get('suppressed_dependents', 0) + 1


def check_available_set(dictionaries, owners, components, complete, output=None, *, include_satisfied=False):
    left, right = (Providers(objects.values()) for objects in dictionaries)
    examples, by_reason, by_kind = [], Counter(), defaultdict(Counter)
    emitted_by_reason = Counter()
    satisfied_written = 0
    limitation = ('AVAILABLE_SET checks only objects present in the repository payloads. '
                  'Installed sets, loader scope and runtime resolution remain unverified.')

    def rows():
        nonlocal satisfied_written
        for path,obj in dictionaries[0].items():
            if not runtime_object(obj):
                continue
            package_id, nevra = owners[path]
            abi = abi_key(obj)
            usable = (obj.get('complete') and obj.get('resolution_metadata_complete') is True
                      and obj.get('export_inventory_complete') is True and isinstance(obj.get('imports'),list)
                      and all(abi) and not duplicate_dynsym_names(obj))
            requirements = obligations(obj) if usable else [('CONSUMER_INVENTORY',None,None,None,False)]
            details = []
            for req in requirements:
                kind, soname, version, symbol, criterion = req
                if usable:
                    needed = obj.get('needed', [])
                    before = left.evaluate(abi, needed, req)
                    after = right.evaluate(abi, needed, req)
                    outcome = classify(req,before,after,complete[1])
                else:
                    before = after = 'INCOMPLETE'
                    outcome = 'UNKNOWN','MEDIUM','CONSUMER_INVENTORY_INCOMPLETE'
                if outcome is None:
                    by_kind[kind]['satisfied'] += 1
                    if include_satisfied and output is not None:
                        satisfied_written += 1
                        identity = {'soname':soname,'version':version,'symbol':symbol}
                        if kind == 'COPY_RELOCATION':
                            identity['copy_size'] = criterion
                        item = finding('linking', components[path], 'AVAILABLE_SET '+kind+' '+canonical(list(identity.values())),
                                       before, after, 'COMPATIBLE','INFO','repository available-set requirement comparison',
                                       obj.get('evidence'),limitation,reason_code='REQUIREMENT_SATISFIED')
                        yield item | dict(scope='AVAILABLE_SET',consumer=path,package_id=package_id,
                                          package_nevra=nevra,kind=kind,**identity)
                    continue
                status, severity, code = outcome
                by_kind[kind]['failed' if status=='INCOMPATIBLE' else 'unknown'] += 1
                identity = {'soname':soname,'version':version,'symbol':symbol}
                if kind == 'COPY_RELOCATION':
                    identity['copy_size'] = criterion
                label = 'AVAILABLE_SET '+kind+' '+canonical(list(identity.values()))
                item = finding('linking',components[path],label,before,after,status,severity,
                               'repository available-set requirement comparison',obj.get('evidence'),limitation,
                               reason_code=code)
                item.update(scope='AVAILABLE_SET', consumer=path, package_id=package_id, package_nevra=nevra,
                            kind=kind, **identity)
                by_reason[code] += 1
                details.append(item)
            aggregate_consumer(details)
            for item in details:
                if not item['suppressed_by']:
                    code = item['reason_code']
                    emitted_by_reason[code] += 1
                    if emitted_by_reason[code] <= EXAMPLE_LIMIT:
                        examples.append(item)
                yield item

    if output is None:
        for _ in rows():
            pass
    else:
        csv_rows(output/'requirement-findings.csv',CSV_COLUMNS,rows())
    summary = {'scope':'AVAILABLE_SET','by_kind':{kind:{k:counts[k] for k in ('satisfied','failed','unknown')}
                                                  for kind,counts in sorted(by_kind.items())},
               'by_reason':dict(sorted(by_reason.items())), 'finding_count':sum(by_reason.values()),
               'emitted_count':sum(emitted_by_reason.values()),
               'satisfied_rows_written':satisfied_written, 'stored_examples':len(examples), 'example_limit_per_reason':EXAMPLE_LIMIT,
               'limitations':limitation}
    return summary, examples
