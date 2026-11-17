"""Read-only glibc search model. A verified result is conditional on the recorded
operator-supplied loader environment, not a claim of successful target execution.
Unknown environment/cache, unsupported tokens and shared-library caller scopes stay UNKNOWN.
"""
from collections import deque
import posixpath
from .core import finding, canonical, digest
from .elf import symbol_identity, target_abi_matches


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


def dependency_checks(manifest, label, consumers=None):
    objects = {o['path']: o for o in manifest['elf_objects']}
    files = {f['path']: f for f in manifest.get('filesystem', [])}
    env = manifest.get('loader_environment', {})
    known = (env.get('model') == 'glibc' and env.get('environment_complete') is True
             and env.get('cache_complete') is True)
    inventory = manifest.get('collection_complete') is True and all(o.get('complete') for o in objects.values())
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
        if not root.get('complete'):
            emit(root, 'collection', None, None, 'unknown_collection')
            continue
        root_scope = bool(root.get('interpreter')) or root.get('type', '').startswith('EXEC')
        loader = root.get('interpreter')
        loader_obj = objects.get(alias(loader, files)) if loader else None
        local_known = known and env.get('namespace', 'base') == 'base'
        preload = next((x.get('normalized', '') for x in manifest.get('configurations', []) if x['path'] == '/etc/ld.so.preload'), '')
        mode = int(files.get(root['path'], {}).get('mode', '0'), 8)
        if any(line.split('#')[0].strip() for line in preload.splitlines()) or mode & 0o6000:
            local_known = False
            emit(root, 'loader context', None, 'preload or secure-execution semantics not modeled', 'unknown_search_environment')
        scope_known = local_known and inventory
        symbol_scope_known = root.get('resolution_metadata_complete', True) and root_scope and env.get('symbol_scope') == 'startup' and env.get('namespace', 'base') == 'base'
        if loader:
            valid = bool(loader_obj and loader_obj.get('complete') and target_abi_matches(root, loader_obj))
            emit(root, 'dynamic loader', loader, loader_obj.get('path') if loader_obj else None,
                 'verified' if valid and local_known else 'missing_provider' if not loader_obj else 'unknown_loader_abi',
                 'INCOMPATIBLE' if not loader_obj and inventory and local_known else None, 'CRITICAL')
            scope_known &= valid
        queue = deque([(root, [])])
        seen = set()
        closure = []
        edges = {}
        loaded = {}
        while queue:
            obj, inherited = queue.popleft()
            if obj['path'] in seen:
                continue
            seen.add(obj['path']); closure.append(obj)
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
                for path in ([] if provider else paths):
                    if path is None:
                        ambiguous = True
                        continue
                    actual = alias(path, files)
                    hit = objects.get(actual)
                    if hit:
                        if not hit.get('complete') or (hit.get('type') and not hit['type'].startswith('DYN')) or not target_abi_matches(obj, hit):
                            ambiguous = True
                            continue
                        provider = hit
                        break
                    if actual in files and files[actual].get('type') == 'file':
                        ambiguous = True  # present but unparsed/not a usable ELF
                verified = local_known and inventory and not ambiguous and provider is not None
                if provider:
                    state = 'verified' if verified else 'unknown_search_environment'
                    loaded.setdefault(needed, provider)
                    edges[(obj['path'], needed)] = provider
                    queue.append((provider, inherited_next))
                else:
                    state = 'unresolvable_provider' if needed in global_names else 'missing_provider'
                    if not local_known or ambiguous or not inventory:
                        state = 'unknown_search_environment'
                emit(obj, 'DT_NEEDED:' + needed, needed, provider['path'] if provider else None, state,
                     'INCOMPATIBLE' if state in ('missing_provider', 'unresolvable_provider') else None)
                scope_known &= verified
        export_scope = {}
        for provider in closure:
            for exported in provider.get('exports', []):
                exp = symbol_identity(exported['name'])
                if not (exported.get('value') == 0 and exported.get('section') != 'ABS' and exported.get('type') != 'TLS') and exported.get('binding') in ('GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE') and exported.get('visibility') in ('DEFAULT', 'PROTECTED') and exported.get('section') != 'UND' and exported.get('type') in ('NOTYPE', 'OBJECT', 'FUNC', 'COMMON', 'TLS', 'IFUNC', 'GNU_IFUNC'):
                    export_scope.setdefault(exp['base_name'], []).append((provider, exported, exp))
        # Requirements refer to a particular dependency, in addition to symbol lookup scope.
        for obj in closure:
            failed_requirements = set()
            for req in obj.get('version_requirements', []):
                provider = edges.get((obj['path'], req['file'])) or loaded.get(req['file'])
                names = {v['name'] for v in (provider or {}).get('version_definitions', [])}
                present = req['name'] in names
                if not present:
                    failed_requirements.add((req['file'], req['name']))
                weak = 'WEAK' in req.get('flags', '').upper()
                state = 'verified' if present and scope_known else 'missing_version' if scope_known and provider and not weak else 'unknown_version_requirement'
                emit(obj, 'version:' + str(req['file']) + ':' + req['name'], req, provider['path'] if provider else None, state,
                     'INCOMPATIBLE' if state == 'missing_version' else None)
            for symbol in obj.get('imports', []):
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
