"""Auditable export observations. These never change detector outcomes."""
from collections import Counter, defaultdict
import json

from .report_io import canonical, digest
from .report_store import COUNTS, source_status, symbol_name, unpack


def owners(store, elf_id):
    return [dict(row) for row in store.db.execute(
        'SELECT side,package_id,min(complete) AS complete FROM ownership WHERE elf_id=? GROUP BY side,package_id',
        (elf_id,))]


def build_pairs(store):
    db = store.db
    objects = {row['id']: dict(row) for row in db.execute('SELECT * FROM elf')}
    metadata = {key: json.loads(value['metadata']) for key, value in objects.items()}
    candidates = defaultdict(list)
    for ident, obj in objects.items():
        if obj['side'] == 'candidate' and metadata[ident].get('soname'):
            candidates[obj['scope'], metadata[ident]['soname']].append(ident)
    proposed, kinds = {}, {}
    for ident, obj in objects.items():
        if obj['side'] != 'baseline':
            continue
        associations = owners(store, ident)
        peers = [db.execute('SELECT peer FROM packages WHERE side=? AND id=?',
                            ('baseline', o['package_id'])).fetchone()[0] for o in associations]
        if not peers or any(p is None for p in peers):
            proposed[ident], kinds[ident] = None, 'UNKNOWN_PACKAGE_MATCH'
            continue
        placeholders = ','.join('?' for _ in peers)
        pool = {r[0] for r in db.execute('SELECT DISTINCT elf_id FROM ownership WHERE side=? AND package_id IN (' + placeholders + ')',
                                         ['candidate', *peers])}
        exact = [key for key in pool if objects[key]['scope'] == obj['scope'] and objects[key]['path'] == obj['path']]
        soname = candidates[obj['scope'], metadata[ident].get('soname')]
        if len(exact) == 1:
            proposed[ident], kinds[ident] = exact[0], 'PATH'
        elif len(soname) == 1 and soname[0] in pool:
            proposed[ident], kinds[ident] = soname[0], 'UNIQUE_CANONICAL_SONAME'
        else:
            proposed[ident], kinds[ident] = None, 'UNKNOWN_ELF_MATCH'
        store.check()
    reverse = Counter(x for x in proposed.values() if x)
    used = set()
    for baseline, candidate in proposed.items():
        if candidate and reverse[candidate] != 1:
            candidate, kinds[baseline] = None, 'AMBIGUOUS_MANY_TO_ONE'
        if candidate:
            used.add(candidate)
        pair = 'PAIR-' + digest([baseline, candidate])[:24]
        db.execute('INSERT INTO pairs VALUES(?,?,?,?,NULL)', (pair, baseline, candidate, kinds[baseline]))
        db.execute('UPDATE elf SET pair_id=? WHERE id=?', (pair, baseline))
        if candidate:
            db.execute('UPDATE elf SET pair_id=? WHERE id=?', (pair, candidate))
    for ident, obj in objects.items():
        if obj['side'] == 'candidate' and ident not in used:
            pair = 'PAIR-' + digest([None, ident])[:24]
            db.execute('INSERT INTO pairs VALUES(?,?,?,?,NULL)', (pair, None, ident, 'UNMATCHED_CANDIDATE'))
            db.execute('UPDATE elf SET pair_id=? WHERE id=?', (pair, ident))
    db.commit()


def compare_symbols(store):
    db = store.db
    for pair in db.execute('SELECT * FROM pairs ORDER BY id').fetchall():
        objs = [db.execute('SELECT * FROM elf WHERE id=?', (pair[side],)).fetchone()
                if pair[side] else None for side in ('baseline', 'candidate')]
        metas = [json.loads(x['metadata']) if x else {} for x in objs]
        sets = [{row['name']: dict(row) for row in db.execute('SELECT * FROM symbols WHERE elf_id=?', (x['id'],))}
                if x else {} for x in objs]
        reliable = bool(all(objs) and all(x['complete'] for x in objs))
        related = defaultdict(list)
        aliases = json.loads(objs[0]['aliases']) if objs[0] else []
        for path in aliases:
            for finding in db.execute('SELECT id,interface,status,evidence FROM findings WHERE dimension=? AND component=?', ('abi', path)):
                related[finding['interface']].append(dict(finding))
        all_owners = {side: owners(store, obj['id']) if obj else []
                      for side, obj in zip(('baseline', 'candidate'), objs)}
        evidence = sorted({e for meta in metas for e in meta.get('evidence', [])})
        observed = Counter(missing=0, added=0, changed=0, version_changes=0, unknown=0, matched=0)
        left, right = sets
        work = []
        exact = set(left) & set(right)
        if reliable:
            work += [(name, name, False) for name in sorted(exact)]
            left_rest, right_rest = set(left) - exact, set(right) - exact
            lbase, rbase = defaultdict(list), defaultdict(list)
            for name in left_rest:
                lbase[left[name]['base']].append(name)
            for name in right_rest:
                rbase[right[name]['base']].append(name)
            for base in sorted(set(lbase) | set(rbase)):
                a, b = sorted(lbase[base]), sorted(rbase[base])
                if len(a) == len(b) == 1:
                    work.append((a[0], b[0], False))
                elif not b:
                    work += [(name, None, False) for name in a]
                elif not a:
                    work += [(None, name, False) for name in b]
                else:
                    work += [(name, None, True) for name in a] + [(None, name, True) for name in b]
        else:
            work = [(name if name in left else None, name if name in right else None, True)
                    for name in sorted(set(left) | set(right))]
        for old, new, uncertain in work:
            a = json.loads(left[old]['attrs']) if old else []
            b = json.loads(right[new]['attrs']) if new else []
            uncertain |= len(a) > 1 or len(b) > 1
            av, bv = a[0] if len(a) == 1 else {}, b[0] if len(b) == 1 else {}
            name = old or new
            base, version, _ = symbol_name(name)
            changes = []
            if uncertain:
                changes = [('UNKNOWN', [old, new])]
                observed['unknown'] += 1
            elif old is None:
                changes = [('ADDED', [new])]
                observed['added'] += 1
            elif new is None:
                changes = [('MISSING', [old, base + ':default lookup'])]
                observed['missing'] += 1
            else:
                if old != new:
                    changes.append(('VERSION_CHANGED', [old, new, base + ':default lookup', old + ':default symbol version']))
                    observed['version_changes'] += 1
                for attr, kind in (('type', 'TYPE_CHANGED'), ('size', 'SIZE_CHANGED'),
                                   ('visibility', 'VISIBILITY_CHANGED'), ('binding', 'BINDING_CHANGED')):
                    if av.get(attr) != bv.get(attr):
                        changes.append((kind, [old + ':' + attr]))
                if changes:
                    observed['changed'] += 1
                else:
                    changes = [('MATCHED', [old, base + ':default lookup'])]
                    observed['matched'] += 1
            for kind, keys in changes:
                refs = {f['id']: f for key in keys if key for f in related.get(key, [])}
                recorded = source_status(f['status'] for f in refs.values())
                status = recorded if not uncertain or recorded == 'INCOMPATIBLE' else 'UNKNOWN'
                row = {'pair_id': pair['id'], 'package_ids': all_owners,
                       'elf_path': objs[0]['path'] if objs[0] else objs[1]['path'],
                       'gcc_elf_id': pair['baseline'], 'llvm_elf_id': pair['candidate'],
                       'symbol_name': base, 'symbol_version': version, 'symbol_type': av.get('type', bv.get('type')),
                       'gcc_symbol_name': old, 'llvm_symbol_name': new,
                       'gcc_symbol_attributes': (a[0] if len(a) == 1 else a) if a else None,
                       'llvm_symbol_attributes': (b[0] if len(b) == 1 else b) if b else None,
                       'difference_type': kind, 'compatibility_status': status,
                       'source_compatibility_statuses': sorted({f['status'] for f in refs.values()}),
                       'finding_ids': sorted(refs),
                       'evidence': sorted(set(evidence) | {e for f in refs.values() for e in json.loads(f['evidence'])})}
                db.execute('INSERT INTO differences(pair_id,name,version,difference_type,status,row_json) VALUES(?,?,?,?,?,?)',
                           (pair['id'], base, version, kind, status, canonical(row)))
            store.check()
        elf_ids = [x['id'] for x in objs if x]
        placeholders = ','.join('?' for _ in elf_ids)
        finding_stats = db.execute('SELECT f.status,count(*) n FROM findings f WHERE f.id IN '
                                  '(SELECT finding_id FROM elf_refs WHERE elf_id IN (' + placeholders + ')) GROUP BY f.status', elf_ids).fetchall()
        statuses = {x['status']: x['n'] for x in finding_stats}
        abi_statuses = [f['status'] for fs in related.values() for f in fs]
        complete = reliable and not observed['unknown']
        summary = {'pair_id': pair['id'], 'package_ids': all_owners,
                   'gcc_elf_id': pair['baseline'], 'llvm_elf_id': pair['candidate'],
                   'gcc_path': objs[0]['path'] if objs[0] else None,
                   'llvm_path': objs[1]['path'] if objs[1] else None,
                   'canonical_identity': [x['id'] for x in objs if x],
                   'aliases': {side: json.loads(x['aliases']) if x else [] for side, x in zip(('baseline', 'candidate'), objs)},
                   'soname': [x.get('soname') for x in metas], 'elf_type': [x.get('type') for x in metas],
                   'match_status': pair['match_status'], 'comparison_complete': complete,
                   'gcc_counts': (json.loads(objs[0]['counts']) if objs[0]['complete'] else {k: None for k in COUNTS}) if objs[0] else None,
                   'llvm_counts': (json.loads(objs[1]['counts']) if objs[1]['complete'] else {k: None for k in COUNTS}) if objs[1] else None,
                   'gcc_observed_counts': json.loads(objs[0]['counts']) if objs[0] else None,
                   'llvm_observed_counts': json.loads(objs[1]['counts']) if objs[1] else None,
                   'observed_differences': dict(observed),
                   'differences': {k: v if complete else None for k, v in observed.items()},
                   'dt_needed_gcc': metas[0].get('needed') if objs[0] else None,
                   'dt_needed_llvm': metas[1].get('needed') if objs[1] else None,
                   'dt_needed_changed': metas[0]['needed'] != metas[1]['needed'] if reliable and all('needed' in m for m in metas) else None,
                   'abi_status': source_status(abi_statuses), 'source_abi_statuses': sorted(set(abi_statuses)),
                   'finding_count': sum(statuses.values()), 'unknown_count': statuses.get('UNKNOWN', 0),
                   'evidence': evidence}
        db.execute('UPDATE pairs SET summary=? WHERE id=?', (canonical(summary), pair['id']))
        store.check()
    db.executescript('CREATE INDEX difference_pair ON differences(pair_id,difference_type,n);')
    db.commit()


def package_counts(store, package):
    db = store.db
    record = unpack(package['record'])
    assessment = unpack(package['assessment'])
    objects = db.execute('SELECT e.*,min(o.complete) AS ownership_complete FROM elf e JOIN ownership o ON o.elf_id=e.id '
                         'WHERE o.side=? AND o.package_id=? GROUP BY e.id', (package['side'], package['id'])).fetchall()
    count = Counter({k: 0 for k in COUNTS})
    shared = executable = 0
    for obj in objects:
        count.update(json.loads(obj['counts']))
        metadata = json.loads(obj['metadata'])
        typ = metadata.get('type', '')
        is_exec = typ.startswith('EXEC') or 'Position-Independent Executable' in typ or (
            (metadata.get('interpreter') or '').startswith('/') and not metadata.get('soname'))
        executable += is_exec
        shared += typ.startswith('DYN') and not is_exec
    files = store.files[package['side'], package['scope']]
    files_known = 'files' in record and all(p in files or store.resolve(package['side'], package['scope'], p) in files
                                          for p in record.get('files', []))
    inventory = store.manifests[package['side']]
    if package['scope'] == 'sdk':
        inventory = inventory.get('sdk_package_manifest', {})
    complete = (inventory.get('package_inventory', {}).get('status') == 'COMPLETE'
                and inventory.get('collection_complete') is True
                and record.get('collection_status') == 'COMPLETE' and files_known
                and all(x['complete'] and x['ownership_complete'] for x in objects))
    headers = assessment.get('collected_headers', [])
    header_count = len(headers) if complete and headers and all(x.get('ownership', {}).get('status') == 'COMPLETE' for x in headers) else None
    pairs = {x['pair_id'] for x in objects}
    differences = Counter(missing=0, added=0, changed=0, version_changes=0, unknown=0, matched=0)
    diff_complete = bool(package['peer']) and complete
    for pair in pairs:
        summary = json.loads(db.execute('SELECT summary FROM pairs WHERE id=?', (pair,)).fetchone()[0])
        differences.update(summary['observed_differences'])
        diff_complete &= summary['comparison_complete']
    return {'owned_elf_count': len(objects) if complete else None,
            'shared_library_count': shared if complete else None, 'executable_count': executable if complete else None,
            'observed_owned_elf_count': len(objects), 'observed_shared_library_count': shared, 'observed_executable_count': executable,
            'header_count': header_count, 'observed_header_count': len(headers),
            'ownership_completeness': 'COMPLETE' if all(x['ownership_complete'] for x in objects) and files_known else 'UNKNOWN',
            'symbol_inventory_complete': complete, 'observed_counts': dict(count),
            'counts': dict(count) if complete else {k: None for k in COUNTS},
            'shared_owned_elf_count': sum(len(owners(store, x['id'])) > 1 for x in objects),
            'observed_differences': dict(differences),
            'differences': dict(differences) if diff_complete else {k: None for k in differences}}


def summarize_packages(store):
    db = store.db
    rows = db.execute('SELECT * FROM packages ORDER BY side,name,id').fetchall()
    counts = {(x['side'], x['id']): package_counts(store, x) for x in rows}
    for row in rows:
        record, assessment = unpack(row['record']), unpack(row['assessment'])
        own = counts[row['side'], row['id']]
        other = 'candidate' if row['side'] == 'baseline' else 'baseline'
        peer = counts.get((other, row['peer']))
        gcc, llvm = (own, peer) if row['side'] == 'baseline' else (peer, own)
        status_counts = {x['status']: x['n'] for x in db.execute(
            'SELECT f.status,count(*) n FROM findings f WHERE f.id IN '
            '(SELECT finding_id FROM package_refs WHERE side=? AND package_id=?) GROUP BY f.status',
            (row['side'], row['id']))}
        statuses = {key: assessment.get(key, {}).get('status', 'UNKNOWN') for key in ('abi', 'api', 'linking')}
        summary = {'side': row['side'], 'package_id': row['id'], 'name': record['name'], 'scope': row['scope'],
                   **{k: record.get(k) for k in ('epoch', 'version', 'release', 'arch')},
                   'match_status': row['match_status'], 'peer_package_id': row['peer'],
                   'gcc_installed': True if gcc else (False if row['match_status'] == 'candidate_only' else None),
                   'llvm_installed': True if llvm else (False if row['match_status'] == 'baseline_only' else None),
                   **own, 'gcc': gcc, 'llvm': llvm, **statuses,
                   'overall': assessment.get('overall', assessment.get('status', 'UNKNOWN')),
                   'verification': assessment.get('verification'), 'coverage': assessment.get('coverage'),
                   'confidence': assessment.get('confidence'), 'limitations': assessment.get('limitations'),
                   'finding_count': sum(status_counts.values()), 'unknown_count': status_counts.get('UNKNOWN', 0),
                   'status_counts': status_counts,
                   'direction': 'baseline consumers on candidate; candidate rows retain their original inventory-only status'}
        db.execute('UPDATE packages SET summary=?,abi=?,api=?,linking=?,overall=?,func=?,missing=?,finding_count=?,unknown_count=? '
                   'WHERE side=? AND id=?', (canonical(summary), statuses['abi'], statuses['api'], statuses['linking'], summary['overall'],
                    own['observed_counts']['func'], own['observed_differences']['missing'], summary['finding_count'], summary['unknown_count'],
                    row['side'], row['id']))
        store.check()
    db.commit()
