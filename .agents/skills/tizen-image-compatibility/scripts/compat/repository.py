"""Directional comparison of available RPM archives and their isolated ELF objects."""
from collections import Counter, defaultdict

from .compare import compare_elf, finalize
from .core import canonical, digest, finding, write_json
from .elf import dynamic_exports, symbol_identity
from .report_io import csv_rows
from .report_symbols import size_difference
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


def compare_repository(a,b,config):
    repos = (a['repository'],b['repository'])
    return_scope = ('RPM_REPOSITORY_PAYLOAD' if all(r['scope']=='RPM_REPOSITORY_PAYLOAD' for r in repos)
                    else 'RPM_REPOSITORY_METADATA')
    grouped = [group_archives(r) for r in repos]
    dictionaries = [{o['path']:o for o in m['elf_objects']} for m in (a,b)]
    names = set(grouped[0]) | set(grouped[1])
    complete = [r['inventory_complete'] for r in repos]
    out, packages, pairs = [], [], []
    candidate_caps = defaultdict(list)
    for p in repos[1]['archives']:
        if p['metadata_status']=='COMPLETE':
            for name in {cap['name'] for kind in ('provides','obsoletes') for cap in p['package'][kind]}:
                candidate_caps[name].append(p)
    for name in sorted(names):
        for state,left,right in group_matches(grouped[0].get(name,{}),grouped[1].get(name,{}),complete):
            pkg_a,pkg_b = (g[0] if g else None for g in (left,right))
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
            for matching,o,p in object_pairs(*[
                    [dictionaries[i][obj] for obj in pkg['objects']] if pkg and (pairable or len(g)==1) else []
                    for i,(pkg,g) in enumerate(zip((pkg_a,pkg_b),(left,right)))]):
                identity = (o or p)['package_path']
                component = '/@repository/'+package_id+identity
                elf_status = 'NOT_VERIFIED'
                comparisons = []
                if o and p and safe_pair:
                    comparisons = compare_elf({'elf_objects':[o | {'path':component}]},
                                              {'elf_objects':[p | {'path':component}]})
                    elf_status = ('INCOMPATIBLE' if any(x['status']=='INCOMPATIBLE' for x in comparisons) else
                                  'OBSERVED' if o.get('complete') and p.get('complete') else 'NOT_VERIFIED')
                elif o:
                    comparisons = [finding('abi',component,'Repository ELF path availability',identity,None,
                                   'UNKNOWN','INFO','scoped RPM payload matching',o.get('evidence'),
                                   'No unique verified ELF pair establishes interface continuity.')]
                findings.extend(comparisons)
                pairs.append({'package_id':package_id,'component':component,'match':matching,'status':elf_status,
                              'baseline_object':o['path'] if o else None,'candidate_object':p['path'] if p else None})
            active = finalize(findings,config)
            row['finding_ids'] = [f['id'] for f in active]
            row['status'] = 'INCOMPATIBLE' if any(f['status']=='INCOMPATIBLE' for f in active) else 'UNKNOWN'
            packages.append(row)
            out.extend(active)
    for side,repo in zip(('baseline','candidate'),repos):
        for error in repo['errors']:
            out.append(finding('packages',side+':'+error['archive'],'RPM '+error['stage']+' coverage',None,error['reason'],
                               'UNKNOWN','HIGH','repository collection',error['evidence']))
    out.append(finding('linking','repository','Installed loader coverage',None,None,'UNKNOWN','INFO',
                       impact='Repository comparisons establish ELF contracts only; the installed loader and provider set are unverified.'))
    return {'scope':return_scope,'baseline':repos[0]['counts'],'candidate':repos[1]['counts'],
            'packages':packages,'elf_pairs':pairs,'inventory_states':dict(Counter(p['inventory_status'] for p in packages)),
            'errors':[{'side':side,**e} for side,r in zip(('baseline','candidate'),repos) for e in r['errors']]},finalize(out,config)


def symbols(obj, role):
    entries = dynamic_exports(obj) if role=='EXPORT' else obj.get('imports',[])
    return {(s['name'],s.get('version_file') if role=='IMPORT' else None):s for s in entries}


def symbol_rows(pair,o,p,findings):
    for role in ('EXPORT','IMPORT'):
        old,new = symbols(o,role),symbols(p,role)
        ready = all(obj.get('export_inventory_complete') for obj in (o,p))
        base = [{key:symbol_identity(s['name'])['base_name'] for key,s in group.items()} for group in (old,new)]
        unmatched_old,unmatched_new = defaultdict(list),defaultdict(list)
        for k in old.keys()-new.keys():
            unmatched_old[base[0][k]].append(k)
        for k in new.keys()-old.keys():
            unmatched_new[base[1][k]].append(k)
        version_pairs = {keys[0]:unmatched_new[name][0] for name,keys in unmatched_old.items()
                         if len(keys)==len(unmatched_new[name])==1}
        consumed = set(version_pairs.values())
        for key in sorted(old.keys() | new.keys(),key=canonical):
            x,y = old.get(key),new.get(key)
            if key in consumed:
                continue
            changed = []
            if key in version_pairs:
                y = new[version_pairs[key]]
                changed.append('VERSION_CHANGED' if x['name'] != y['name'] else 'REQUIRED_PROVIDER_CHANGED')
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
            matches = [f for name in names for f in findings.get(name,[])] if role=='EXPORT' else []
            yield {'package_id':pair['package_id'],'component':pair['component'],'role':role,'change':change,
                   'details':changed,'status':'INCOMPATIBLE' if any(f['status']=='INCOMPATIBLE' for f in matches) else 'UNKNOWN',
                   'baseline':x,'candidate':y,'finding_ids':sorted({f['id'] for f in matches}),
                   'baseline_sha256':o.get('sha256'),'candidate_sha256':p.get('sha256'),
                   'evidence':sorted(set(o.get('evidence',[])+p.get('evidence',[])))}


PACKAGE_COLUMNS = ('id','name','arch','scope','inventory_status','status','baseline_nevra','candidate_nevra',
    'baseline_archives','candidate_archives','baseline_sha256','candidate_sha256','baseline_payload_status',
    'candidate_payload_status','provides','requires','replacement_hints','finding_ids','evidence')


def export_repository(output,a,b,results):
    repo = results['repository']
    objects = [{o['path']:o for o in m['elf_objects']} for m in (a,b)]
    archives = [{r['id']:r for r in m['repository']['archives'] if 'id' in r} for m in (a,b)]
    by_component = defaultdict(lambda:defaultdict(list))
    for f in results['findings']:
        if f['dimension']=='abi':
            label = f['interface']
            for suffix in (':size',':type',':visibility',':binding',':default lookup',':default symbol version'):
                if label.endswith(suffix):
                    label=label[:-len(suffix)]
                    break
            by_component[f['component']][label].append(f)

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
            yield row
    csv_rows(output/'package-symbol-summary.csv',('id','name','arch','inventory_status','baseline_nevra','candidate_nevra',
        'baseline_elf','candidate_elf','baseline_export_complete','candidate_export_complete',
        'baseline_exports','candidate_exports','baseline_imports','candidate_imports'),package_stats())
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
            yield row
    csv_rows(output/'elf-symbol-summary.csv',('package_id','component','match','status')+
             tuple(side+'_'+f for side in ('baseline','candidate') for f in
                   ('path','sha256','soname','needed','exports','imports','export_status','arm_abi','asan','evidence')),elf_stats())
    def differences():
        for pair in repo['elf_pairs']:
            o,p = (objects[i].get(pair[side+'_object'],{}) for i,side in enumerate(('baseline','candidate')))
            yield from symbol_rows(pair,o,p,by_component[pair['component']])
    csv_rows(output/'symbol-differences.csv',('package_id','component','role','change','details','status',
             'baseline','candidate','finding_ids','baseline_sha256','candidate_sha256','evidence'),differences())
    csv_rows(output/'extraction-errors.csv',('side','archive','stage','path','reason','evidence'),repo['errors'])
    write_json(output/'rpm-repository.json',{k:repo[k] for k in ('scope','baseline','candidate','inventory_states')})
