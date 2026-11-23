"""Read-only glibc search model. A verified result is conditional on the recorded
operator-supplied loader environment, not a claim of successful target execution.
Unknown environment/cache, unsupported tokens and shared-library caller scopes stay UNKNOWN.
"""
from collections import deque
import posixpath
from .core import finding, canonical, digest
from .elf import dynamic_exports, runtime_metadata_complete, symbol_identity, target_abi_matches, version_nodes


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


def dependency_checks(manifest, label, consumers=None, consumer_manifest=None, checkpoint=None):
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
    out = []
    def emit(obj, interface, before, after, state, status=None, severity='HIGH'):
        status = status or ('COMPATIBLE' if state == 'verified' else 'UNKNOWN')
        item = finding('linking', obj['path'], label + ':' + interface, before, after, status,
                       'INFO' if status == 'COMPATIBLE' else severity, 'offline glibc dependency closure',
                       obj.get('evidence'), impact='Resolution state: ' + state + '. Conditional on recorded loader environment; runtime interposition/dlopen/IFUNC behavior is separate.')
        item['resolution'] = state
        item['check_id'] = interface
        item['consumer_path'] = obj['path']
        item['consumer_image'] = 'baseline' if consumers is not None and obj is root else 'candidate'
        item['root_consumer'] = root['path']
        item['root_consumer_image'] = 'baseline' if consumers is not None else 'candidate'
        item['provider_path'] = after.get('provider') if isinstance(after, dict) else after if isinstance(after, str) and after.startswith('/') else None
        # A transitive failure reached from different entry points is distinct evidence.
        item['id'] = 'TC-' + digest(canonical({k: v for k, v in item.items() if k != 'id'}).encode())[:16]
        out.append(item)
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
                provider = loaded.get(needed)
                if provider and (not loaded_proven.get(needed) or not provider.get('complete') or not target_abi_matches(obj, provider)):
                    ambiguous = True
                for path in ([] if provider else paths):
                    if path is None:
                        ambiguous = True
                        continue
                    actual = alias(path, files)
                    if actual is None or actual in debug_paths:
                        ambiguous = True
                        continue
                    hit = objects.get(actual)
                    if hit:
                        if not hit.get('complete') or (hit.get('type') and not hit['type'].startswith('DYN')) or not target_abi_matches(obj, hit):
                            ambiguous = True
                            continue
                        provider = hit
                        break
                    if actual in files and files[actual].get('type') == 'file':
                        ambiguous = True  # present but unparsed/not a usable ELF
                verified = (object_known and inventory and not ambiguous and provider is not None
                            and runtime_metadata_complete(provider) and provider.get('export_inventory_complete') is True)
                if provider:
                    state = 'verified' if verified else 'unknown_search_environment'
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
                else:
                    state = 'unresolvable_provider' if needed in global_names else 'missing_provider'
                    if not object_known or ambiguous or not inventory:
                        state = 'unknown_search_environment'
                emit(obj, 'DT_NEEDED:' + needed, needed, provider['path'] if provider else None, state,
                     'INCOMPATIBLE' if state in ('missing_provider', 'unresolvable_provider') else None)
                scope_known &= verified
        if loader_obj and loader_obj['path'] not in seen:
            closure.append(loader_obj)
            # Nonstandard interpreters with their own dependencies need a full
            # loader adapter; do not infer a closed symbol scope from this subset.
            scope_known &= not loader_obj.get('needed')
        export_scope = {}
        for provider in closure:
            for exported in dynamic_exports(provider):
                if checkpoint:
                    checkpoint()
                exp = symbol_identity(exported['name'])
                if not (exported.get('value') == 0 and exported.get('section') != 'ABS' and exported.get('type') != 'TLS') and exported.get('binding') in ('GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE') and exported.get('visibility') in ('DEFAULT', 'PROTECTED') and exported.get('section') != 'UND' and exported.get('type') in ('NOTYPE', 'OBJECT', 'FUNC', 'COMMON', 'TLS', 'IFUNC', 'GNU_IFUNC'):
                    export_scope.setdefault(exp['base_name'], []).append((provider, exported, exp))
        # Requirements refer to a particular dependency, in addition to symbol lookup scope.
        for obj in closure:
            failed_requirements = set()
            for req in obj.get('version_requirements', []):
                if checkpoint:
                    checkpoint()
                provider = edges.get((obj['path'], req['file'])) or loaded.get(req['file'])
                names = version_nodes(provider or {})
                present = req['name'] in names
                if not present:
                    failed_requirements.add((req['file'], req['name']))
                weak = 'WEAK' in req.get('flags', '').upper()
                state = 'verified' if present and scope_known else 'missing_version' if scope_known and provider and not weak else 'unknown_version_requirement'
                emit(obj, 'version:' + str(req['file']) + ':' + req['name'], req, provider['path'] if provider else None, state,
                     'INCOMPATIBLE' if state == 'missing_version' else None)
            for symbol in obj.get('imports', []):
                if checkpoint:
                    checkpoint()
                identity = symbol_identity(symbol['name'])
                matches = []
                for provider, exported, exp in export_scope.get(identity['base_name'], []):
                    version_ok = (identity['version'] == exp['version'] if identity['version'] else (exp['version'] is None or exp['default_version']))
                    if version_ok:
                        matches.append((provider, exported))
                required_file = symbol.get('version_file')
                constraint_failed = (required_file, identity['version']) in failed_requirements
                constraint_unknown = bool(required_file and not (edges.get((obj['path'], required_file)) or loaded.get(required_file)))
                # Unversioned interposition and legacy non-default fallback are not modeled.
                fallback = any((identity['version'] and exp['version'] is None) or (identity['version'] is None and exp['version'] and not exp['default_version']) for _, _, exp in export_scope.get(identity['base_name'], []))
                if matches:
                    provider, exported = matches[0]
                    types_ok = symbol.get('type') in ('NOTYPE', exported.get('type'))
                    special = (any(x.get('type') in ('IFUNC', 'GNU_IFUNC') or x.get('binding') in ('UNIQUE', 'GNU_UNIQUE') or x.get('visibility') == 'PROTECTED' for _, x in matches)
                               or symbol.get('binding') == 'WEAK' or len(matches) > 1 or fallback or constraint_failed or constraint_unknown)
                    state = 'verified' if scope_known and symbol_scope_known and types_ok and not special else 'unknown_symbol_semantics'
                    if scope_known and symbol_scope_known and not types_ok and not special:
                        state = 'symbol_type_mismatch'
                    emit(obj, 'import:' + symbol['name'], symbol, {'provider': provider['path'], 'export': exported, 'lookup_candidates': [{'provider': p['path'], 'export': x} for p, x in matches], 'scope_proven': bool(symbol_scope_known and scope_known), 'required_provider': required_file}, state,
                         'INCOMPATIBLE' if state == 'symbol_type_mismatch' else None)
                else:
                    # A DSO can import from its executable/global namespace; weak absence is legal but behavior is unknown.
                    broken = scope_known and symbol_scope_known and not fallback and not constraint_unknown and symbol.get('binding') != 'WEAK'
                    emit(obj, 'import:' + symbol['name'], symbol, None, 'missing_symbol' if broken else 'unknown_symbol_scope',
                         'INCOMPATIBLE' if broken else None)
    return out
