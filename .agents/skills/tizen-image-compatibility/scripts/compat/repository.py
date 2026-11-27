"""Directional comparison of available RPM archives and their isolated ELF objects."""
from collections import Counter, defaultdict

from .compare import compare_elf, finalize
from .core import canonical, digest, finding, write_json
from .elf import duplicate_dynsym_names, dynamic_exports, symbol_identity, symbol_multimap
from .profile import comparison_profile, runtime_object
from .report_io import csv_rows
from .report_symbols import size_difference
from .repository_pairing import reconcile
from .rpm_payload import FIELDS


def bucket(row):
    package = row['package']
    return package['name'],package['arch']


def nevra(row):
    if not row:
        return None
    p = row['package']
    return f"{p['name']}-{p['epoch']}:{p['version']}-{p['release']}.{p['arch']}"


def group_archives(repo):
    groups = defaultdict(lambda:defaultdict(list))
    for row in repo['archives']:
        if row['metadata_status'] == 'COMPLETE':
            groups[bucket(row)][tuple(row['package'][key] for key in FIELDS)].append(row)
    return groups


def group_matches(left,right,complete):
    for key in sorted(left.keys() & right.keys()):
        a,b = left[key],right[key]
        if len({x['sha256'] for x in a}) == len({x['sha256'] for x in b}) == 1:
            yield 'COMMON',a,b
        else:
            yield 'AMBIGUOUS_IDENTICAL_NEVRA',a,b
    a = [row for key in sorted(left.keys()-right.keys()) for row in left[key]]
    b = [row for key in sorted(right.keys()-left.keys()) for row in right[key]]
    if a and b:
        if len({nevra(x) for x in a}) == len({nevra(x) for x in b}) == 1 and len(
                {x['sha256'] for x in a}) == len({x['sha256'] for x in b}) == 1:
            yield 'VERSION_CHANGED',a,b
        else:
            yield 'AMBIGUOUS_MULTIPLE_VERSIONS',a,b
    else:
        state = 'MISSING' if a and complete[1] else 'ADDED' if b and complete[0] else 'INVENTORY_INCOMPLETE'
        for key in sorted(left.keys()-right.keys()):
            yield state,left[key],[]
        for key in sorted(right.keys()-left.keys()):
            yield state,[],right[key]


def object_pairs(left,right):
    left,right = ({o['package_path']:o for o in group} for group in (left,right))
    same = left.keys() & right.keys()
    for path in sorted(same):
        yield 'PATH',left[path],right[path]
    old,new = ({k:v for k,v in side.items() if k not in same} for side in (left,right))
    # A SONAME fallback requires a one-to-one complete ABI identity inside this package pair.
    def signature(o):
        if o.get('soname') and o.get('complete') and o.get('elf_runtime_role') != 'DEBUG_ONLY':
            return tuple(o.get(k) for k in ('soname','machine','class','endianness'))
        return None
    signatures = [defaultdict(list),defaultdict(list)]
    for group, by in zip((left,right),signatures):
        for o in group.values():
            if (key := signature(o)) is not None:
                by[key].append(o)
    used = set()
    for path,o in sorted(old.items()):
        key = signature(o)
        match = signatures[1].get(key,[])
        other = match[0] if len(match)==len(signatures[0].get(key,[]))==1 and match[0]['package_path'] in new else None
        if other:
            used.add(other['package_path'])
        yield ('VERIFIED_UNIQUE_SONAME' if other else 'BASELINE_ONLY_OR_UNRESOLVED'),o,other
    for path,o in sorted(new.items()):
        if path not in used:
            yield 'CANDIDATE_ONLY',None,o


def replacements(left,right):
    names = {p['package']['name'] for p in left}
    return sorted({(p['package']['name'],cap['name'],kind) for p in right for kind in ('provides','obsoletes')
                   for cap in p['package'][kind] if cap['name'] in names and cap['name'] != p['package']['name']})


def preferred_archive(rows):
    if rows:
        return min(rows, key=lambda row: (row['extraction_status'] != 'COMPLETE', row['id']))
    return None


def package_objects(groups, representatives, dictionaries, pairable):
    if pairable:
        yield from ((matching, old, new, '') for matching,old,new in object_pairs(*[
            [objects[key] for key in archive['objects']]
            for archive,objects in zip(representatives,dictionaries)]))
    for side, group, representative, objects in zip(('baseline','candidate'),groups,representatives,dictionaries):
        for archive in group:
            if pairable and archive is representative:
                continue
            for key in archive['objects']:
                obj = objects[key]
                identity = '' if len(group) == 1 and not (groups[0] and groups[1]) else f'/{side}{key}'
                yield ('UNPAIRED_ARCHIVE_OBSERVATION', obj if side=='baseline' else None,
                       obj if side=='candidate' else None, identity)


def complete_payload(repo, objects):
    return (repo['inventory_complete'] and all(row['extraction_status']=='COMPLETE' for row in repo['archives'])
            and repo['counts']['elf_observed']==len(objects)
            and all(obj.get('complete') and (obj.get('elf_runtime_role')=='DEBUG_ONLY'
                    or obj.get('export_inventory_status')=='NOT_APPLICABLE'
                    or obj.get('export_inventory_complete') is True) for obj in objects))


def unpaired_finding(obj, component, complete, alternatives, scope):
    if alternatives:
        code,status,severity = 'PROVIDER_AMBIGUOUS','UNKNOWN','MEDIUM'
    elif obj.get('type','').startswith('EXEC') or obj.get('interpreter'):
        code,status,severity = 'EXECUTABLE_NOT_FOUND','UNKNOWN','LOW'
    elif runtime_object(obj) and obj.get('soname'):
        code,status,severity = (('LIBRARY_REMOVED','INCOMPATIBLE','HIGH') if complete else
                                ('LIBRARY_NOT_FOUND_INCOMPLETE_INVENTORY','UNKNOWN','MEDIUM'))
    else:
        code,status,severity = 'OBJECT_UNPAIRED','UNKNOWN','INFO'
    return finding('abi',component,'Repository ELF path availability',obj['package_path'],alternatives or None,
                   status,severity,'repository-wide payload matching',obj.get('evidence'),
                   'Available RPM payload scope. A unique candidate object is required to continue the comparison.',
                   reason_code=code) | {'scope':scope}


def compare_repository(a,b,config,output=None):
    repos = (a['repository'],b['repository'])
    return_scope = ('RPM_REPOSITORY_PAYLOAD' if all(r['scope']=='RPM_REPOSITORY_PAYLOAD' for r in repos)
                    else 'RPM_REPOSITORY_METADATA')
    grouped = [group_archives(r) for r in repos]
    dictionaries = [{o['path']:o for o in m['elf_objects']} for m in (a,b)]
    names = set(grouped[0]) | set(grouped[1])
    complete = [r['inventory_complete'] for r in repos]
    out, packages, pairs = [], [], []
    package_findings = defaultdict(list)
    owners = [{}, {}]
    candidate_caps = defaultdict(list)
    for p in repos[1]['archives']:
        if p['metadata_status']=='COMPLETE':
            for name in {cap['name'] for kind in ('provides','obsoletes') for cap in p['package'][kind]}:
                candidate_caps[name].append(p)
    for name in sorted(names):
        for state,left,right in group_matches(grouped[0].get(name,{}),grouped[1].get(name,{}),complete):
            pkg_a,pkg_b = (preferred_archive(g) for g in (left,right))
            pairable = state in ('COMMON','VERSION_CHANGED')
            package_id = 'RP-'+digest(canonical([name,[nevra(x) for x in left],[nevra(x) for x in right]]).encode())[:24]
            refs = sorted({e for row in left+right for e in row['evidence']})
            row = {'id':package_id,'name':name[0],'arch':name[1],'scope':return_scope,'inventory_status':state,
                   'baseline_nevra':nevra(pkg_a) if pairable or len(left)==1 else None,
                   'candidate_nevra':nevra(pkg_b) if pairable or len(right)==1 else None,
                   'baseline_archives':[x['id'] for x in left],'candidate_archives':[x['id'] for x in right],
                   'baseline_payload_status':pkg_a['extraction_status'] if pkg_a and pairable else None,
                   'candidate_payload_status':pkg_b['extraction_status'] if pkg_b and pairable else None,
                   'replacement_hints':replacements(left,candidate_caps[name[0]]) if state=='MISSING' else [],
                   'baseline_sha256':pkg_a['sha256'] if pairable or len(left)==1 else None,
                   'candidate_sha256':pkg_b['sha256'] if pairable or len(right)==1 else None,'evidence':refs}
            findings = []
            if state != 'COMMON':
                findings.append(finding('packages','/@repository/'+package_id,'RPM repository '+state,
                    sorted({nevra(x) for x in left}),sorted({nevra(x) for x in right}), 'UNKNOWN','INFO',
                    'available RPM inventory',refs, 'Availability or version changes do not establish installed compatibility.'))
            if pairable:
                for field in ('provides','requires'):
                    old,new = ({canonical(x):x for x in p['package'][field]} for p in (pkg_a,pkg_b))
                    diff = {'removed':[old[k] for k in sorted(old.keys()-new.keys())],
                            'added':[new[k] for k in sorted(new.keys()-old.keys())]}
                    row[field] = diff
                    if diff['removed'] or diff['added']:
                        findings.append(finding('packages','/@repository/'+package_id,field,
                            diff['removed'],diff['added'],'UNKNOWN','INFO','RPM metadata contract delta',refs))
            safe_pair = pairable and all(p['extraction_status']=='COMPLETE' for p in (pkg_a,pkg_b))
            for side, group in enumerate((left, right)):
                for archive in group:
                    for path in archive['objects']:
                        owners[side][path] = (package_id, nevra(archive))
            for matching,o,p,archive_identity in package_objects((left,right),(pkg_a,pkg_b),dictionaries,pairable):
                identity = (o or p)['package_path']
                component = '/@repository/'+package_id+(archive_identity or identity)
                pairs.append({'package_id':package_id,'component':component,'match':matching,'safe_pair':safe_pair,
                              'baseline_package_id':package_id if o else None,'candidate_package_id':package_id if p else None,
                              'baseline_object':o['path'] if o else None,'candidate_object':p['path'] if p else None})
            package_findings[package_id].extend(findings)
            packages.append(row)
    payload_complete = [complete_payload(repo, list(objects.values())) for repo,objects in zip(repos,dictionaries)]
    pairs, ambiguous = reconcile(pairs,dictionaries)
    downgrades = Counter()
    components = {}
    for pair in pairs:
        o,p = (dictionaries[i].get(pair[side+'_object']) for i,side in enumerate(('baseline','candidate')))
        component = pair['component']
        if o:
            components[o['path']] = component
        comparisons = []
        safe_pair = pair.pop('safe_pair')
        if o and ((p and safe_pair) or o.get('elf_runtime_role')=='DEBUG_ONLY'):
            comparisons = compare_elf({'elf_objects':[o | {'path':component}]},
                                      {'elf_objects':[p | {'path':component}] if p else []}, repository=True)
        elif o:
            comparisons = [unpaired_finding(o,component,all(payload_complete) and p is None and o.get('complete'),
                                            ambiguous.get(o['path'],[]),return_scope)]
            pair['availability_reason'] = comparisons[0]['reason_code']
        pair['status'] = ('INCOMPATIBLE' if any(f['status']=='INCOMPATIBLE' for f in comparisons) else
                          'OBSERVED' if o and p and safe_pair and o.get('complete') and p.get('complete') else 'NOT_VERIFIED')
        for f in comparisons:
            if f['dimension'] in config['analysis']['modes'] and f.get('reason_code') in ('INSTRUMENTATION_MISMATCH','INSTRUMENTATION_SYMBOL'):
                downgrades[f['reason_code']] += 1
        for owner in {pair['baseline_package_id'],pair['candidate_package_id']} - {None}:
            package_findings[owner].extend(comparisons)
    for row in packages:
        active = finalize(package_findings[row['id']],config)
        row['finding_ids'] = [f['id'] for f in active]
        row['status'] = 'INCOMPATIBLE' if any(f['status']=='INCOMPATIBLE' for f in active) else 'UNKNOWN'
    seen = {}
    for findings in package_findings.values():
        for f in findings:
            seen[f['id']] = f
    out.extend(seen.values())
    for side,repo in zip(('baseline','candidate'),repos):
        for error in repo['errors']:
            out.append(finding('packages',side+':'+error['archive'],'RPM '+error['stage']+' coverage',None,error['reason'],
                               'UNKNOWN','HIGH','repository collection',error['evidence']))
    out.append(finding('linking','repository','Installed loader coverage',None,None,'UNKNOWN','INFO',
                       impact='Repository comparisons establish ELF contracts only; the installed loader and provider set are unverified.'))
    requirements = None
    if return_scope=='RPM_REPOSITORY_PAYLOAD' and 'linking' in config['analysis']['modes']:
        from .requirements import check_available_set
        requirements, examples = check_available_set(dictionaries, owners[0], components, payload_complete,
                                                      output if config['report']['csv'] else None)
        out.extend(examples)
    stats = [r['counts'] | symbol_counts(m['elf_objects']) for m,r in zip((a,b),repos)]
    for counts, complete in zip(stats,payload_complete):
        counts['payload_inventory_complete'] = complete
    return {'scope':return_scope,'baseline':stats[0],'candidate':stats[1],
            'packages':packages,'elf_pairs':pairs,'inventory_states':dict(Counter(p['inventory_status'] for p in packages)),
            **comparison_profile(a['elf_objects'],b['elf_objects']),
            'instrumentation_downgrades':dict(downgrades), 'requirements':requirements,
            'errors':[{'side':side,**e} for side,r in zip(('baseline','candidate'),repos) for e in r['errors']]},finalize(out,config)


def symbols(obj, role):
    entries = dynamic_exports(obj) if role=='EXPORT' else obj.get('imports',[])
    groups = symbol_multimap(entries,by_provider=role=='IMPORT')
    return groups if role=='IMPORT' else {(name,None):rows for name,rows in groups.items()}


def symbol_counts(objects):
    """Count base names per scope and qualified lookup identities per ELF."""
    stats = {}
    for role in ('EXPORT','IMPORT'):
        names, lookup_count = set(), 0
        for obj in objects:
            lookup = set()
            for (name,provider) in symbols(obj,role):
                identity = symbol_identity(name)
                base,version = identity['base_name'],identity['version']
                names.add(base)
                lookup.add((base,version,provider))
                if role=='EXPORT' and identity['default_version']:
                    lookup.add((base,None,None))
            lookup_count += len(lookup)
        stats[role.lower()+'_unique_symbol_names'] = len(names)
        stats[role.lower()+'_lookup_identities'] = lookup_count
    return stats


def symbol_rows(pair,o,p,findings):
    if (o or p).get('elf_runtime_role')=='DEBUG_ONLY':
        return
    candidate_duplicates = duplicate_dynsym_names(p)
    duplicates = duplicate_dynsym_names(o) | candidate_duplicates
    candidate_ids = [symbol_identity(s['name']) for s in dynamic_exports(p)]
    qualified = {(s['base_name'],s['version']) for s in candidate_ids}
    defaults = {s['base_name'] for s in candidate_ids if s['default_version'] or not s['version']}

    def satisfaction(symbol):
        if not symbol:
            return None
        if pair.get('availability_reason')=='LIBRARY_REMOVED':
            return 'false'
        identity = symbol_identity(symbol['name'])
        if symbol['name'] in duplicates or candidate_duplicates or p.get('export_inventory_complete') is not True:
            return 'unknown'
        found = ((identity['base_name'],identity['version']) in qualified if identity['version']
                 else identity['base_name'] in defaults)
        return 'true' if found else 'false'

    for role in ('EXPORT','IMPORT'):
        groups = [symbols(obj,role) for obj in (o,p)]
        ready = not duplicates and all(obj.get('export_inventory_complete') is True for obj in (o,p))
        for i,side in enumerate(('baseline','candidate')):
            for key,records in sorted(groups[i].items(),key=lambda item:canonical(item[0])):
                if key[0] not in duplicates:
                    continue
                for row in sorted(records,key=canonical):
                    yield {'package_id':pair['package_id'],'component':pair['component'],'role':role,
                           'change':side.upper()+'_OBSERVED','details':['DUPLICATE_DYNSYM_IDENTITY'],'status':'UNKNOWN',
                           'baseline_identity_satisfied':'unknown' if role=='EXPORT' and i==0 else None,
                           'baseline':row if i==0 else None,'candidate':row if i==1 else None,'finding_ids':[],
                           'baseline_sha256':o.get('sha256'),'candidate_sha256':p.get('sha256'),
                           'evidence':sorted(set(o.get('evidence',[])+p.get('evidence',[])))}
        old,new = ({key:rows[0] for key,rows in group.items() if key[0] not in duplicates} for group in groups)
        def unmatched(keys, qualified):
            grouped = defaultdict(list)
            for key in keys:
                identity = symbol_identity(key[0])
                group = (identity['base_name'],identity['version'],key[1]) if qualified else identity['base_name']
                grouped[group].append(key)
            return grouped

        def unique_pairs(old_keys,new_keys,qualified):
            lhs,rhs = unmatched(old_keys,qualified),unmatched(new_keys,qualified)
            return {keys[0]:rhs[name][0] for name,keys in lhs.items() if len(keys)==len(rhs[name])==1}

        version_pairs = {}
        if ready:
            removed,added = old.keys()-new.keys(),new.keys()-old.keys()
            version_pairs = unique_pairs(removed,added,True)
            version_pairs.update(unique_pairs(removed-version_pairs.keys(),added-set(version_pairs.values()),False))
        consumed = set(version_pairs.values())
        for key in sorted(old.keys() | new.keys(),key=canonical):
            x,y = old.get(key),new.get(key)
            if key in consumed:
                continue
            changed = []
            if key in version_pairs:
                y = new[version_pairs[key]]
                before,after = (symbol_identity(s['name']) for s in (x,y))
                if before['version'] != after['version']:
                    changed.append('VERSION_CHANGED')
                if before['default_version'] != after['default_version']:
                    changed.append('DEFAULT_LOOKUP_CHANGED')
                if role=='IMPORT' and x.get('version_file') != y.get('version_file'):
                    changed.append('REQUIRED_PROVIDER_CHANGED')
            if x and y:
                for attr in ('type','binding','visibility'):
                    if x.get(attr)!=y.get(attr):
                        changed.append(attr.upper()+'_CHANGED')
                if role=='EXPORT' and x.get('size')!=y.get('size'):
                    changed.append(size_difference(x,y))
            if x and y:
                change = 'CHANGED' if changed else 'MATCHED'
            else:
                change = ('MISSING' if x else 'ADDED') if ready else ('BASELINE_OBSERVED' if x else 'CANDIDATE_OBSERVED')
            names = {s['name'] for s in (x,y) if s}
            if role=='EXPORT':
                for name in tuple(names):
                    identity = symbol_identity(name)
                    if identity['default_version']:
                        names.add(identity['base_name']+':default lookup')
                    if identity['version'] is None:
                        names.add(identity['base_name']+':default symbol version')
            matches = [f for name in names for f in findings.get(name,[])] if role=='EXPORT' else []
            statuses = {f['status'] for f in matches}
            yield {'package_id':pair['package_id'],'component':pair['component'],'role':role,'change':change,
                   'baseline_identity_satisfied':satisfaction(x) if role=='EXPORT' else None,
                   'details':changed,'status':('INCOMPATIBLE' if 'INCOMPATIBLE' in statuses else
                                              'COMPATIBLE' if statuses=={'COMPATIBLE'} else 'UNKNOWN'),
                   'baseline':x,'candidate':y,'finding_ids':sorted({f['id'] for f in matches}),
                   'baseline_sha256':o.get('sha256'),'candidate_sha256':p.get('sha256'),
                   'evidence':sorted(set(o.get('evidence',[])+p.get('evidence',[])))}


PACKAGE_COLUMNS = ('id','name','arch','scope','inventory_status','status','baseline_nevra','candidate_nevra',
    'baseline_archives','candidate_archives','baseline_sha256','candidate_sha256','baseline_payload_status',
    'candidate_payload_status','provides','requires','replacement_hints','finding_ids','evidence')


def symbol_differences(results, objects):
    by_component = defaultdict(lambda:defaultdict(list))
    for f in results['findings']:
        if f['dimension']=='abi':
            label = f['interface']
            symbol_record = any(isinstance(f.get(side), dict) and f[side].get('name')==label
                                for side in ('baseline','candidate'))
            if not symbol_record:
                for suffix in (':size',':type',':visibility',':binding'):
                    if label.endswith(suffix):
                        label=label[:-len(suffix)]
                        break
            by_component[f['component']][label].append(f)
    changes = Counter()
    roles = {'EXPORT':Counter(),'IMPORT':Counter()}
    unsatisfied = 0
    for pair in results['repository']['elf_pairs']:
        o,p = (objects[i].get(pair[side+'_object'],{}) for i,side in enumerate(('baseline','candidate')))
        for row in symbol_rows(pair,o,p,by_component[pair['component']]):
            changes[row['change']] += 1
            roles[row['role']][row['change']] += 1
            unsatisfied += row.get('baseline_identity_satisfied')=='false'
            yield row
    results['repository']['symbol_differences'] = {
        'rows':sum(changes.values()),'by_change':dict(sorted(changes.items())),
        'exports_baseline_unsatisfied':unsatisfied,
        'by_role':{role:{'rows':sum(counts.values()),'by_change':dict(sorted(counts.items()))}
                   for role,counts in roles.items()}}


def count_symbol_differences(a,b,results):
    objects = [{o['path']:o for o in m['elf_objects']} for m in (a,b)]
    for _ in symbol_differences(results,objects):
        pass


def export_repository(output,a,b,results):
    repo = results['repository']
    objects = [{o['path']:o for o in m['elf_objects']} for m in (a,b)]
    archives = [{r['id']:r for r in m['repository']['archives'] if 'id' in r} for m in (a,b)]
    csv_rows(output/'packages.csv',PACKAGE_COLUMNS,repo['packages'])
    def package_stats():
        for p in repo['packages']:
            row = {k:p[k] for k in ('id','name','arch','inventory_status','baseline_nevra','candidate_nevra')}
            for i,side in enumerate(('baseline','candidate')):
                selected = [archives[i][k] for k in p[side+'_archives']]
                found = {key for r in selected for key in r['objects']}
                row.update({side+'_elf':len(found),
                            side+'_export_complete':sum(objects[i][k].get('export_inventory_complete') is True for k in found),
                            side+'_exports':sum(len(symbols(objects[i][k],'EXPORT')) for k in found),
                            side+'_imports':sum(len(symbols(objects[i][k],'IMPORT')) for k in found)})
                row.update({side+'_'+key:value for key,value in symbol_counts([objects[i][k] for k in found]).items()})
            yield row
    csv_rows(output/'package-symbol-summary.csv',('id','name','arch','inventory_status','baseline_nevra','candidate_nevra',
        'baseline_elf','candidate_elf','baseline_export_complete','candidate_export_complete',
        'baseline_exports','candidate_exports','baseline_imports','candidate_imports')+
        tuple(side+'_'+role+'_'+unit for side in ('baseline','candidate') for role in ('export','import')
              for unit in ('unique_symbol_names','lookup_identities')),package_stats())
    def elf_stats():
        for pair in repo['elf_pairs']:
            row = dict(pair)
            for i,side in enumerate(('baseline','candidate')):
                o = objects[i].get(pair[side+'_object'])
                if o:
                    row.update({side+'_path':o['package_path'],side+'_sha256':o['sha256'],side+'_soname':o.get('soname'),
                                side+'_needed':o.get('needed',[]),side+'_exports':len(symbols(o,'EXPORT')),
                                side+'_imports':len(symbols(o,'IMPORT')),side+'_export_status':o.get('export_inventory_status'),
                                side+'_arm_abi':o.get('arm_abi') or o.get('arm_inventory'),
                                side+'_asan': [x for x in o.get('needed',[]) if 'asan' in x.lower()] +
                                              sorted({x['name'] for x in o.get('imports',[]) if x['name'].startswith('__asan_')}),
                                side+'_evidence':o.get('evidence',[])})
                    row.update({side+'_'+key:value for key,value in symbol_counts([o]).items()})
            yield row
    csv_rows(output/'elf-symbol-summary.csv',('package_id','component','match','status')+
             tuple(side+'_'+f for side in ('baseline','candidate') for f in
                   ('path','sha256','soname','needed','exports','imports','export_status','arm_abi','asan','evidence',
                    'export_unique_symbol_names','export_lookup_identities','import_unique_symbol_names','import_lookup_identities'))
             + ('baseline_package_id','candidate_package_id'),elf_stats())
    csv_rows(output/'symbol-differences.csv',('package_id','component','role','change','details','status',
             'baseline','candidate','finding_ids','baseline_sha256','candidate_sha256','evidence',
             'baseline_identity_satisfied'),symbol_differences(results,objects))
    csv_rows(output/'extraction-errors.csv',('side','archive','stage','path','reason','evidence'),repo['errors'])
    write_json(output/'rpm-repository.json',{k:repo[k] for k in ('scope','baseline','candidate','inventory_states','symbol_differences')})
