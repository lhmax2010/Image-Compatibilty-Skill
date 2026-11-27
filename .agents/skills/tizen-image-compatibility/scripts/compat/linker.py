"""Read-only glibc search model. A verified result is conditional on the recorded
operator-supplied loader environment, not a claim of successful target execution.
Unknown environment/cache, unsupported tokens and shared-library caller scopes stay UNKNOWN.
"""
from collections import OrderedDict, deque
import posixpath
from .core import finding, canonical, digest
from .elf import copy_relocation_check, dynamic_exports, normalize_version, runtime_metadata_complete, symbol_identity, target_abi_matches, version_nodes


NEXT_ACTIONS = {
    'COPY_RELOC_SIZE_CHANGED': 'Restore the consumed data size or rebuild the executable.',
    'LOADER_ENV_MISSING': 'Configure loader.environments for the affected image.',
    'UNKNOWN_SEARCH_ENVIRONMENT': 'Supply the loader search, preload, mode and capability evidence for the consumer.',
    'UNKNOWN_LOADER_ABI': 'Record the target interpreter and its complete ELF ABI inventory.',
    'UNKNOWN_LOADER_FEATURE': 'Validate the loader flags with the matching target loader.',
    'UNKNOWN_SYMBOL_SEMANTICS': 'Validate the actual binding with the correct provider and loader scope.',
    'UNKNOWN_SYMBOL_SCOPE': 'Record the complete startup symbol scope or validate on the authorized target.',
    'UNKNOWN_VERSION_REQUIREMENT': 'Record the provider and its complete GNU version definitions.',
    'UNKNOWN_COLLECTION': 'Repeat collection with complete ELF and filesystem evidence.',
}


def loader_missing(side):
    return finding('linking', side, 'loader environment', None, None, 'UNKNOWN', 'MEDIUM',
                   'offline glibc dependency closure', impact='Linking checks were not executed for this side.',
                   action=NEXT_ACTIONS['LOADER_ENV_MISSING'], reason_code='LOADER_ENV_MISSING')


def summarize_unknowns(findings):
    summary = {}
    for item in findings:
        if item['dimension'] == 'linking' and item['status'] == 'UNKNOWN':
            code = item.get('reason_code', 'LINKING_STATIC_DIFFERENCE')
            group = summary.setdefault(code, {'count': 0, 'check_count': 0, 'example_finding_ids': [],
                'next_action': NEXT_ACTIONS.get(code, item['recommended_action'])})
            group['count'] += 1
            group['check_count'] += item.get('aggregated_checks', 1)
            if len(group['example_finding_ids']) < 20:
                group['example_finding_ids'].append(item['id'])
    return summary


def alias(path, files):
    for _ in range(40):
        parts = path.split('/')
        for n in range(len(parts), 1, -1):
            prefix = '/'.join(parts[:n])
            entry = files.get(prefix, {})
            if entry.get('type') == 'symlink':
                if not entry.get('resolved'):
                    return None
                path = posixpath.normpath(entry['resolved'] + '/' + '/'.join(parts[n:]))
                break
        else:
            return path
    return None


def expand(value, origin):
    value = value.replace('${ORIGIN}', origin).replace('$ORIGIN', origin)
    if '$' in value or not value.startswith('/'):
        return None
    return posixpath.normpath(value)


def dependency_checks(manifest, label, consumers=None, consumer_manifest=None, checkpoint=None, *, details=None):
    debug_paths = {o['path'] for o in manifest['elf_objects'] if o.get('elf_runtime_role') == 'DEBUG_ONLY'}
    objects = {o['path']: o for o in manifest['elf_objects'] if o['path'] not in debug_paths}
    files = {f['path']: f for f in manifest.get('filesystem', [])}
    source_files = ({f['path']: f for f in consumer_manifest.get('filesystem', [])}
                    if consumer_manifest is not None else files if consumers is None else {})
    env = manifest.get('loader_environment', {})
    known = (env.get('model') == 'glibc' and env.get('environment_complete') is True
             and env.get('cache_complete') is True)
    inventory = manifest.get('filesystem_path_inventory_complete')
    if inventory is None:
        inventory = manifest.get('collection_complete') is True and all(o.get('complete') for o in objects.values())
    inventory = inventory is True
    global_names = {posixpath.basename(p) for p in objects} | {o.get('soname') for o in objects.values()}
    grouped = {}
    search_cache, requirement_cache, export_indexes, shared_scopes = {}, OrderedDict(), {}, OrderedDict()
    requirement_keys = OrderedDict()

    def cache_put(cache, key, value, limit):
        cache[key] = value
        if details is not None and len(cache) > limit:
            cache.popitem(last=False)

    def decision(key, resolve):
        if key not in requirement_cache:
            cache_put(requirement_cache, key, resolve(), 8192)
        requirement_cache.move_to_end(key)
        return requirement_cache[key]

    def requirement_key(data):
        key = id(data)
        if key not in requirement_keys:
            cache_put(requirement_keys, key, canonical(data), 16384)
        requirement_keys.move_to_end(key)
        return requirement_keys[key]

    def provider_identity(provider):
        if provider is None:
            return None
        # In a directional replay the baseline root itself can export symbols.
        # An identically named candidate object is a different scope member.
        return {'path': provider['path'], 'image': 'baseline' if consumers is not None and provider is root else 'candidate'}

    def emit(obj, interface, before, after, state, status=None, severity='HIGH', *, key=None, context=None):
        status = status or ('COMPATIBLE' if state == 'verified' else 'UNKNOWN')
        image = 'baseline' if consumers is not None and obj is root else 'candidate'
        key = (image, obj['path'], interface, key if key is not None else canonical([before, after, state]))
        symbolic = interface.startswith(('import:', 'version:', 'DT_NEEDED:', 'copy relocation:'))
        detail = details is not None and (symbolic or status == 'INCOMPATIBLE')
        aggregate = detail and symbolic and status != 'INCOMPATIBLE'
        token = label, key
        repeated = detail and details.repeat(token, root['path'])
        if repeated and aggregate:
            return
        entry = grouped.get(key)
        if entry is not None:
            if detail and not repeated:
                details.add(entry[0], root['path'], token, False)
            entry[1].add(root['path'])
            return
        item = finding('linking', obj['path'], label + ':' + interface, before, after, status,
                       'INFO' if status == 'COMPATIBLE' else severity, 'offline glibc dependency closure',
                       obj.get('evidence'), impact='Resolution state: ' + state + '. Conditional on recorded loader environment; runtime interposition/dlopen/IFUNC behavior is separate.',
                       reason_code=state.upper(), action=NEXT_ACTIONS.get(state.upper(), ''))
        item['resolution'] = state
        item['check_id'] = interface
        item['consumer_path'] = obj['path']
        item['consumer_image'] = image
        item['root_consumer_image'] = 'baseline' if consumers is not None else 'candidate'
        item['provider_path'] = after.get('provider') if isinstance(after, dict) else after if isinstance(after, str) and after.startswith('/') else None
        if context is not None:
            item['search_context'] = context() if callable(context) else context
        item['id'] = 'TC-' + digest(canonical({k: v for k, v in item.items() if k != 'id'}).encode())[:16]
        if detail:
            details.add(item, root['path'], token, aggregate)
        if not aggregate:
            grouped[key] = (item, {root['path']})

    def lookup(obj, paths, provider, proven, ambiguous):
        if provider and (not proven or not provider.get('complete') or not target_abi_matches(obj, provider)):
            ambiguous = True
        if provider:
            return provider, ambiguous
        for path in paths:
            actual = alias(path, files) if path is not None else None
            if actual is None or actual in debug_paths:
                ambiguous = True
                continue
            hit = objects.get(actual)
            if hit:
                if not hit.get('complete') or (hit.get('type') and not hit['type'].startswith('DYN')) or not target_abi_matches(obj, hit):
                    ambiguous = True
                    continue
                return hit, ambiguous
            if files.get(actual, {}).get('type') == 'file':
                ambiguous = True
        return None, ambiguous

    def provider_exports(provider):
        key = id(provider)
        if key not in export_indexes:
            index = {}
            for exported in dynamic_exports(provider):
                if checkpoint:
                    checkpoint()
                exp = symbol_identity(exported['name'])
                if not (exported.get('value') == 0 and exported.get('section') != 'ABS' and exported.get('type') != 'TLS') and exported.get('binding') in ('GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE') and exported.get('visibility') in ('DEFAULT', 'PROTECTED') and exported.get('section') != 'UND' and exported.get('type') in ('NOTYPE', 'OBJECT', 'FUNC', 'COMMON', 'TLS', 'IFUNC', 'GNU_IFUNC'):
                    index.setdefault(exp['base_name'], []).append((provider, exported, exp))
            export_indexes[key] = index
        return export_indexes[key]
    for root in consumers if consumers is not None else objects.values():
        if root.get('elf_runtime_role') == 'DEBUG_ONLY':
            continue
        if checkpoint:
            checkpoint()
        if not root.get('complete'):
            emit(root, 'collection', None, None, 'unknown_collection')
            continue
        root_scope = bool(root.get('interpreter')) or root.get('type', '').startswith('EXEC')
        loader = root.get('interpreter')
        loader_path = alias(loader, files) if loader else None
        loader_obj = objects.get(loader_path)
        local_known = (known and root_scope and env.get('namespace', 'base') == 'base'
                       and runtime_metadata_complete(root) and root.get('export_inventory_complete') is True)
        preload = next((x.get('normalized', '') for x in manifest.get('configurations', []) if x['path'] == '/etc/ld.so.preload'), '')
        # Root execution context belongs to the consumer image, providers/search
        # paths belong to the candidate. Never use candidate same-path mode for a
        # baseline executable. Explicit per-object metadata supports direct callers.
        actual_root = alias(root['path'], source_files)
        context = source_files.get(actual_root, {}) if actual_root in source_files else ({} if consumer_manifest is not None else root.get('execution_metadata', {}))
        try:
            mode = int(context['mode'], 8)
            mode_known = mode >= 0 and mode <= 0o177777
        except (KeyError, ValueError, TypeError):
            mode, mode_known = 0, False
        normal_context = mode_known and not mode & 0o6000 and context.get('security_metadata_complete') is True and context.get('has_file_capabilities') is False
        if any(line.split('#')[0].strip() for line in preload.splitlines()) or not normal_context:
            local_known = False
            emit(root, 'loader context', None, {'reason': 'preload or secure-execution context not proven normal',
                'metadata_image': 'baseline' if consumers is not None else 'candidate', 'metadata': context,
                'boundary': 'Mode/capability evidence cannot determine credentials, mount policy or AT_SECURE at runtime.'}, 'unknown_search_environment')
        scope_known = local_known and inventory
        symbol_scope_known = runtime_metadata_complete(root) and root_scope and env.get('symbol_scope') == 'startup' and env.get('namespace', 'base') == 'base'
        if loader:
            valid = bool(loader_obj and loader_obj.get('complete') and runtime_metadata_complete(loader_obj)
                         and loader_obj.get('export_inventory_complete') is True and target_abi_matches(root, loader_obj))
            missing = not loader_obj and loader_path not in debug_paths
            emit(root, 'dynamic loader', loader, loader_obj.get('path') if loader_obj else None,
                 'verified' if valid and local_known else 'missing_provider' if missing else 'unknown_loader_abi',
                 'INCOMPATIBLE' if missing and inventory and local_known else None, 'CRITICAL')
            scope_known &= valid
        queue = deque([(root, [])])
        seen = set()
        closure = []
        edges = {}
        loaded = {}
        loaded_proven = {}
        # The root and its validated interpreter precede dependency expansion.
        # An isolated DSO has no proven caller/load namespace and earns no credit.
        for initial in (root, loader_obj):
            if initial and initial.get('complete') and target_abi_matches(root, initial):
                names = [initial['path'], initial.get('soname')]
                for initial_name in filter(None, names):
                    loaded.setdefault(initial_name, initial)
                    loaded_proven.setdefault(initial_name, bool(local_known and inventory and runtime_metadata_complete(initial) and initial.get('export_inventory_complete') is True))
        while queue:
            if checkpoint:
                checkpoint()
            obj, inherited = queue.popleft()
            if obj['path'] in seen:
                continue
            seen.add(obj['path']); closure.append(obj)
            object_known = local_known and runtime_metadata_complete(obj) and obj.get('export_inventory_complete') is True
            scope_known &= object_known
            origin = posixpath.dirname(obj['path'])
            rpaths = [expand(v, origin) for v in obj.get('rpath', [])] if not obj.get('runpath') else []
            runpaths = [expand(v, origin) for v in obj.get('runpath', [])]
            inherited_next = rpaths + inherited
            unsupported = any(f.split(':', 1)[0] not in ('FLAGS', 'FLAGS_1') or any(word not in {'Flags:', 'NOW', 'BIND_NOW', 'PIE', 'NODEFLIB', 'STATIC_TLS'} for word in f.split(':', 1)[-1].split()) for f in obj.get('dynamic_flags', []))
            nodeflib = any('NODEFLIB' in f for f in obj.get('dynamic_flags', []))
            if unsupported:
                scope_known = False
                emit(obj, 'loader features', None, obj.get('dynamic_flags'), 'unknown_loader_feature')
            for needed in obj.get('needed', []):
                if checkpoint:
                    checkpoint()
                ambiguous = unsupported
                if '/' in needed or '$' in needed:
                    paths = [expand(needed, origin)]
                else:
                    dirs = ([] if obj.get('runpath') else rpaths + inherited) + [expand(v, origin) for v in env.get('library_path', [])] + runpaths
                    paths = [posixpath.join(d, needed) if d else None for d in dirs]
                    cache = env.get('cache', {}).get(needed, [])
                    if nodeflib:
                        cache = [v for v in cache if posixpath.dirname(v) not in env.get('default_dirs', [])]
                    paths += cache
                    if not nodeflib:
                        paths += [posixpath.join(d, needed) for d in env.get('default_dirs', [])]
                preloaded = loaded.get(needed)
                proven = bool(loaded_proven.get(needed))
                context = {'search_paths': paths, 'loaded': provider_identity(preloaded),
                           'loaded_proven': proven, 'collection_proven': object_known,
                           'unsupported_flags': ambiguous}
                key = (id(obj), needed, tuple(paths), id(preloaded), proven, ambiguous, object_known)
                if key not in search_cache:
                    provider, uncertain = lookup(obj, paths, preloaded, proven, ambiguous)
                    verified = (object_known and inventory and not uncertain and provider is not None
                                and runtime_metadata_complete(provider) and provider.get('export_inventory_complete') is True)
                    if provider or not object_known or uncertain or not inventory:
                        state = 'verified' if verified else 'unknown_search_environment'
                    else:
                        state = 'unresolvable_provider' if needed in global_names else 'missing_provider'
                    search_cache[key] = provider, verified, state
                provider, verified, state = search_cache[key]
                if provider:
                    loaded.setdefault(needed, provider)
                    loaded_proven.setdefault(needed, bool(verified))
                    # Only objects reached by this root's load order are reusable.
                    # Register SONAME after a real load, never by global-name scan.
                    soname = provider.get('soname')
                    if soname and '/' not in soname and '$' not in soname:
                        loaded.setdefault(soname, provider)
                        loaded_proven.setdefault(soname, bool(verified))
                    edges[(obj['path'], needed)] = provider
                    queue.append((provider, inherited_next))
                emit(obj, 'DT_NEEDED:' + needed, needed, provider['path'] if provider else None, state,
                     'INCOMPATIBLE' if state in ('missing_provider', 'unresolvable_provider') else None,
                     key=key, context=context)
                scope_known &= verified
        if loader_obj and loader_obj['path'] not in seen:
            closure.append(loader_obj)
            # Nonstandard interpreters with their own dependencies need a full
            # loader adapter; do not infer a closed symbol scope from this subset.
            scope_known &= not loader_obj.get('needed')
        # The non-root providers and their order can be identical across many roots.
        shared = [p for p in closure if p is not root]
        scope_key = tuple(map(id, shared))
        if scope_key not in shared_scopes:
            cache_put(shared_scopes, scope_key, {}, 32)
        shared_scopes.move_to_end(scope_key)
        export_scope = shared_scopes[scope_key]
        root_exports = provider_exports(root)
        # Requirements refer to a particular dependency, in addition to symbol lookup scope.
        for obj in closure:
            failed_requirements = set()
            for req in obj.get('version_requirements', []):
                if checkpoint:
                    checkpoint()
                version_name = normalize_version(req['name'])
                provider = edges.get((obj['path'], req['file'])) or loaded.get(req['file'])
                weak = 'WEAK' in req.get('flags', '').upper()
                key = (id(obj), requirement_key(req), id(provider), bool(scope_known))
                def check_version():
                    present = version_name in version_nodes(provider or {})
                    state = ('verified' if present and scope_known else 'missing_version'
                             if scope_known and provider and not weak else 'unknown_version_requirement')
                    return present, state
                present, state = decision(key, check_version)
                if not present:
                    failed_requirements.add((req['file'], version_name))
                emit(obj, 'version:' + str(req['file']) + ':' + req['name'], req, provider['path'] if provider else None, state,
                     'INCOMPATIBLE' if state == 'missing_version' else None, key=key,
                     context={'scope_proven': bool(scope_known), 'provider': provider_identity(provider)})
            for copy in obj.get('copy_relocations', []):
                file = copy.get('provider_soname')
                provider = edges.get((obj['path'], file)) or loaded.get(file)
                identity = symbol_identity(copy['name'])
                version = normalize_version(copy['version'])
                entries = [sym for _, sym, exp in provider_exports(provider).get(identity['base_name'], ())
                           if exp['version'] == version and sym.get('type') == 'OBJECT'] if provider else []
                other_entries = any(sym['version'] in (None, version)
                                    for other in closure if other is not provider and other is not obj
                                    for _, _, sym in provider_exports(other).get(identity['base_name'], ()))
                proven = bool(scope_known and symbol_scope_known and provider and not other_entries)
                state = ('unknown_symbol_scope' if not proven or len(entries) > 1 else 'missing_symbol' if not entries else
                         'copy_reloc_size_changed' if entries[0]['size'] != copy['size'] else 'verified')
                emit(obj, copy_relocation_check(copy), copy, {'provider': provider['path'], 'export': entries[0]}
                     if len(entries) == 1 else None, state,
                     'INCOMPATIBLE' if state in ('copy_reloc_size_changed', 'missing_symbol') else None,
                     context={'scope_proven':proven, 'provider':provider_identity(provider)})
            for symbol in obj.get('imports', []):
                if checkpoint:
                    checkpoint()
                identity = symbol_identity(symbol['name'])
                name = identity['base_name']
                if name not in export_scope:
                    export_scope[name] = tuple(entry for provider in shared for entry in
                                               provider_exports(provider).get(name, ()))
                entries = (*root_exports.get(name, ()), *export_scope[name])
                required_file = symbol.get('version_file')
                required_provider = edges.get((obj['path'], required_file)) or loaded.get(required_file)
                constraint_failed = (required_file, identity['version']) in failed_requirements
                constraint_unknown = bool(required_file and not required_provider)
                complete_scope = bool(scope_known and symbol_scope_known)
                key = (id(obj), requirement_key(symbol), tuple((id(p), id(e)) for p, e, _ in entries),
                       bool(scope_known), bool(symbol_scope_known), id(required_provider), constraint_failed)
                state, after = decision(key, lambda: check_import(symbol, identity, entries, complete_scope,
                                                                    constraint_failed, constraint_unknown))
                def context():
                    return {'scope_proven': bool(scope_known), 'startup_scope': bool(symbol_scope_known),
                           'required_provider': provider_identity(required_provider),
                           'version_constraint_failed': constraint_failed,
                           'symbol_scope': [provider_identity(p) | {'name': e['name'], 'type': e.get('type'),
                               'binding': e.get('binding'), 'visibility': e.get('visibility')}
                               for p, e, _ in entries]}
                emit(obj, 'import:' + symbol['name'], symbol, after, state,
                     'INCOMPATIBLE' if state in ('symbol_type_mismatch', 'missing_symbol') else None,
                     key=key, context=context)
    out = []
    for item, roots in grouped.values():
        paths = sorted(roots)
        item['root_consumer'] = item['consumer_path'] if item['consumer_path'] in roots else paths[0]
        item['roots'] = {'count': len(paths), 'examples': paths[:20]}
        item['_root_paths'] = paths
        out.append(item)
    return out


def check_import(symbol, identity, entries, scope_known, constraint_failed, constraint_unknown):
    matches = []
    for provider, exported, exp in entries:
        version_ok = (identity['version'] == exp['version'] if identity['version']
                      else exp['version'] is None or exp['default_version'])
        if version_ok:
            matches.append((provider, exported))
    # Unversioned interposition and legacy non-default fallback are not modeled.
    fallback = any((identity['version'] and exp['version'] is None) or
                   (identity['version'] is None and exp['version'] and not exp['default_version'])
                   for _, _, exp in entries)
    if not matches:
        broken = scope_known and not fallback and not constraint_unknown and symbol.get('binding') != 'WEAK'
        return ('missing_symbol' if broken else 'unknown_symbol_scope'), None
    provider, exported = matches[0]
    types_ok = symbol.get('type') in ('NOTYPE', exported.get('type'))
    special = (any(x.get('type') in ('IFUNC', 'GNU_IFUNC') or x.get('binding') in ('UNIQUE', 'GNU_UNIQUE')
                   or x.get('visibility') == 'PROTECTED' for _, x in matches)
               or symbol.get('binding') == 'WEAK' or len(matches) > 1 or fallback or constraint_failed or constraint_unknown)
    state = ('unknown_symbol_semantics' if not scope_known or special else
             'verified' if types_ok else 'symbol_type_mismatch')
    return state, {'provider': provider['path'], 'export': exported,
                   'lookup_candidates': [{'provider': p['path'], 'export': x} for p, x in matches],
                   'scope_proven': scope_known, 'required_provider': symbol.get('version_file')}
