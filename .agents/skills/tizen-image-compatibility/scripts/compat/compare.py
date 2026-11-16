"""Directional compatibility: can baseline consumers use candidate interfaces?"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from .core import DIMENSIONS, SEVERITIES, Tools, canonical, finding


def index(items: list[dict[str, Any]], key: str = 'path') -> dict[str, dict[str, Any]]:
    return {str(x[key]): x for x in items}


def evidence(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    return sorted(set(a.get('evidence', []) + b.get('evidence', [])))


def virtual_alias(path: str, files: dict[str, dict[str, Any]]) -> str:
    for _ in range(40):
        if path in files and files[path].get('resolved'):
            path = files[path]['resolved']
            continue
        parts = Path(path).parts
        match = next((str(Path(*parts[:n])) for n in range(len(parts) - 1, 1, -1)
                      if files.get(str(Path(*parts[:n])), {}).get('resolved')), None)
        if not match:
            return path
        path = files[match]['resolved'].rstrip('/') + path[len(match):]
    return path


def exports(obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for symbol in obj.get('exports', []):
        name = symbol['name']
        result[name.replace('@@', '@')] = symbol
        if '@@' in name:
            result[name.split('@@')[0]] = symbol
    return result


def compare_elf(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    old, new = index(a['elf_objects']), index(b['elf_objects'])
    for path, obj in old.items():
        other = new.get(path)
        if not other and obj.get('soname'):
            matches = [x for x in new.values() if x.get('soname') == obj['soname']]
            if len(matches) == 1:
                other = matches[0]
        if other is None:
            findings.append(finding('abi', path, 'ELF availability', path, None, 'UNKNOWN', 'HIGH',
                impact='The baseline binary/library path is missing; aliases or replacement implementations need verification.'))
            continue
        ev = evidence(obj, other)
        if not obj.get('complete') or not other.get('complete'):
            findings.append(finding('abi', path, 'collection coverage', obj.get('complete'), other.get('complete'), evidence=ev))
            continue
        for key in ('class', 'endianness', 'machine', 'osabi', 'abi_version', 'type', 'soname', 'interpreter', 'rpath', 'runpath'):
            if obj.get(key) != other.get(key):
                incompatible = key in ('class', 'endianness', 'machine')
                findings.append(finding('elf' if key != 'soname' else 'linking', path, key, obj.get(key), other.get(key),
                    'INCOMPATIBLE' if incompatible else 'UNKNOWN', 'CRITICAL' if incompatible else 'HIGH', evidence=ev,
                    impact='Existing binary consumers may require a different ABI or dynamic loader.'))
        left, right = exports(obj), exports(other)
        for name, symbol in left.items():
            if name not in right:
                findings.append(finding('abi', path, name, symbol, None, 'INCOMPATIBLE', 'HIGH',
                    'ELF dynamic export/version comparison', ev, 'Previously linkable symbol or default symbol version is absent.',
                    'Restore the exported ABI/version or rebuild and validate all affected consumers.', 'high'))
            else:
                next_symbol = right[name]
                if '@' not in name and symbol['name'] != next_symbol['name']:
                    findings.append(finding('abi', path, name + ':default symbol version', symbol['name'], next_symbol['name'],
                        'UNKNOWN', 'HIGH', evidence=ev, impact='Unversioned lookup now selects a different symbol version.'))
                keys = ('type', 'visibility', 'binding') + (('size',) if symbol['type'] in ('OBJECT', 'TLS') else ())
                for key in keys:
                    if symbol.get(key) != next_symbol.get(key):
                        findings.append(finding('abi', path, name + ':' + key, symbol.get(key), next_symbol.get(key),
                            'INCOMPATIBLE' if key in ('size', 'type') else 'UNKNOWN', 'HIGH', evidence=ev))
        for name in sorted(set(right) - set(left)):
            findings.append(finding('abi', path, name, None, right[name], 'COMPATIBLE', 'INFO', evidence=ev,
                                    impact='Additional exported interface; existing exports are compared separately.'))
        if obj.get('needed') != other.get('needed'):
            findings.append(finding('linking', path, 'DT_NEEDED', obj.get('needed'), other.get('needed'), 'UNKNOWN', 'MEDIUM', evidence=ev,
                impact='Runtime implementation/dependency changed; dependency availability is checked separately.'))
        if all(obj.get(k) == other.get(k) for k in ('exports', 'needed', 'soname', 'machine', 'class')):
            findings.append(finding('abi', path, 'dynamic interface surface', 'collected ELF surface', 'same collected ELF surface',
                'IDENTICAL', 'INFO', evidence=ev, impact='Symbol-level surface matches; type/layout and behavioral coverage remain separate.'))
    return findings


def dependency_checks(manifest: dict[str, Any], label: str, consumers: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    objects = manifest['elf_objects']
    files = index(manifest.get('filesystem', []))
    names = {Path(obj['path']).name for obj in objects}
    names |= {obj['soname'] for obj in objects if obj.get('soname')}
    names |= {Path(p).name for p, entry in files.items() if entry['type'] == 'symlink' and entry.get('resolved')}
    complete = all(obj.get('complete') for obj in objects) and bool(objects)
    complete = complete and not any(x['dimension'] == 'filesystem' for x in manifest['limitations'])
    findings = []
    for obj in consumers if consumers is not None else objects:
        if not obj.get('complete'):
            continue
        needed = obj.get('needed', [])
        for lib in needed:
            if lib not in names:
                findings.append(finding('linking', obj['path'], label + ':DT_NEEDED:' + lib, lib, None,
                    'INCOMPATIBLE' if complete else 'UNKNOWN', 'HIGH', 'whole-rootfs provider inventory',
                    obj.get('evidence'), 'Required SONAME has no detected provider in this rootfs.',
                    'Supply the required runtime library or prove a loader-supported equivalent.', 'high' if complete else 'low'))
        loader = obj.get('interpreter')
        resolved_loader = virtual_alias(loader, files) if loader else None
        if loader and (resolved_loader not in files or (files[resolved_loader]['type'] == 'symlink' and not files[resolved_loader].get('resolved'))):
            findings.append(finding('linking', obj['path'], label + ':dynamic loader', loader, None,
                'INCOMPATIBLE' if complete else 'UNKNOWN', 'CRITICAL', evidence=obj.get('evidence')))
    # Detect cycles without recursion so large dependency graphs do not overflow Python's stack.
    graph = {o['soname']: set(o.get('needed', [])) for o in objects if o.get('soname')}
    for start in sorted(graph):
        pending = [(start, [start])]
        visited = set()
        while pending:
            node, chain = pending.pop()
            if node in visited:
                continue
            visited.add(node)
            for child in sorted(graph.get(node, [])):
                if child == start and len(chain) > 1:
                    findings.append(finding('linking', start, label + ':dependency cycle', None, chain + [start],
                        'UNKNOWN', 'LOW', impact='Dependency cycles can be legal; initializer order needs runtime validation.'))
                    pending = []
                    break
                if child not in visited:
                    pending.append((child, chain + [child]))
    return findings


def compare_api(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    left, right = index(a['public_headers']), index(b['public_headers'])
    for path, header in left.items():
        other = right.get(path)
        if not other:
            unreadable = any(x['component'] == path for x in b['limitations'])
            findings.append(finding('api', path, 'public header', path, None, 'UNKNOWN' if unreadable else 'INCOMPATIBLE', 'HIGH', evidence=header.get('evidence')))
            continue
        ev = evidence(header, other)
        if all(header[k] == other[k] for k in ('tokens', 'macros', 'conditions', 'includes')):
            findings.append(finding('api', path, 'normalized public declarations', 'same token sequence', 'same token sequence',
                'IDENTICAL' if header['sha256'] == other['sha256'] else 'COMPATIBLE', 'INFO', 'C/C++ token normalization', ev,
                'Comments and non-semantic whitespace do not change declarations.'))
            continue
        for name in sorted(set(header['declarations']) | set(other['declarations'])):
            old, new = header['declarations'].get(name), other['declarations'].get(name)
            if old != new:
                removed = old is not None and new is None and name not in other['tokens'] and not header['conditions'] and not other['conditions']
                findings.append(finding('api', path, name, old, new, 'INCOMPATIBLE' if removed else 'UNKNOWN', 'HIGH',
                    'lexical function declaration comparison', ev,
                    'Declaration changed; parameter names, typedefs and conditional context require SDK compilation to establish semantic impact.'))
        for name in sorted(set(header['macros']) | set(other['macros'])):
            old, new = header['macros'].get(name), other['macros'].get(name)
            if old != new:
                findings.append(finding('api', path, '#define ' + name, old, new, 'UNKNOWN', 'MEDIUM', evidence=ev,
                    impact='Macro change may affect compiler/architecture/feature/SDK configuration: ' + ', '.join(sorted(set(header['context_hints'] + other['context_hints'])))))
        findings.append(finding('api', path, 'types, inline bodies and conditional source',
            header['body_tokens'], other['body_tokens'], 'UNKNOWN', 'MEDIUM', 'token-level C/C++ surface comparison', ev,
            'Struct/union/enum/typedef/class/template/inline differences require matching preprocessor context and semantic verification.'))
    return findings


def compare_packages(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    old = {(x['name'], x['arch']): x for x in a['packages']}
    new = {(x['name'], x['arch']): x for x in b['packages']}
    findings = []
    for key, package in old.items():
        other = new.get(key)
        if not other:
            findings.append(finding('packages', ':'.join(key), 'package availability', package['name'], None, 'UNKNOWN', 'HIGH',
                impact='Package may be renamed, split or replaced; check its provided interfaces and file consumers.'))
            continue
        ev = evidence(package, other)
        for field in ('version', 'release', 'provides', 'requires', 'conflicts', 'obsoletes', 'files'):
            if package.get(field) != other.get(field):
                release = field == 'release'
                findings.append(finding('packages', ':'.join(key), field, package.get(field), other.get(field),
                    'COMPATIBLE' if release else 'UNKNOWN', 'INFO' if release else 'MEDIUM', evidence=ev,
                    impact='Release number alone is not an interface.' if release else 'RPM metadata changed; version/dependency constraints require a target package-solver check.'))
    return findings


def compare_static(a: dict[str, Any], b: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    out = compare_elf(a, b) + compare_api(a, b) + compare_packages(a, b)
    if not config['analysis']['ignore_build_ids']:
        other = index(b['elf_objects'])
        for obj in a['elf_objects']:
            peer = other.get(obj['path'], {})
            if obj.get('build_id') != peer.get('build_id'):
                out.append(finding('elf', obj['path'], 'build ID (non-interface metadata)', obj.get('build_id'), peer.get('build_id'),
                    'COMPATIBLE', 'INFO', impact='Build ID differences do not establish ABI differences.'))
    out += dependency_checks(b, 'candidate')
    out += dependency_checks(b, 'baseline consumers on candidate', a['elf_objects'])
    for dimension, key in [('filesystem', 'filesystem'), ('commands', 'commands'), ('services', 'services'),
        ('filesystem', 'configurations'), ('security', 'security_interfaces'), ('kernel', 'kernel'),
        ('hardware', 'hardware'), ('network', 'network'), ('packages', 'development'), ('compiler_runtime', 'runtime_libraries')]:
        old, new = index(a.get(key, [])), index(b.get(key, []))
        for path, value in old.items():
            other = new.get(path)
            if other is None:
                other = new.get(virtual_alias(path, index(b.get('filesystem', []))))
            if other is None:
                # Incomplete collection must not manufacture removals.
                missing = not any(x['component'] in (path, '*') and x['dimension'] == 'filesystem' for x in b['limitations'])
                status = 'INCOMPATIBLE' if missing and dimension == 'commands' else 'UNKNOWN'
                out.append(finding(dimension, path, key + ' availability', path, None, status, 'HIGH', evidence=value.get('evidence')))
                continue
            left = {k: v for k, v in value.items() if k not in ('evidence', 'sha256')}
            right = {k: v for k, v in other.items() if k not in ('evidence', 'sha256')}
            if left != right:
                out.append(finding(dimension, path, key, left, right, 'UNKNOWN',
                    'HIGH' if dimension == 'security' else 'MEDIUM', evidence=evidence(value, other)))
    old, new = index(a.get('ipc', []), 'name'), index(b.get('ipc', []), 'name')
    for name, member in old.items():
        other = new.get(name)
        if other is None or any(member.get(k) != other.get(k) for k in ('args', 'attributes')):
            incomplete = any(x['dimension'] in ('filesystem', 'ipc') and x['component'] in ('*', member['path'])
                             and ('failed' in x['reason'].lower() or 'invalid' in x['reason'].lower() or 'exceeds' in x['reason'].lower()) for x in b['limitations'])
            out.append(finding('ipc', member['path'], name, member, other, 'UNKNOWN' if incomplete else 'INCOMPATIBLE', 'HIGH',
                               'D-Bus introspection contract comparison', evidence(member, other or {}), confidence='high'))
    if a['image'].get('os_version') != b['image'].get('os_version'):
        out.append(finding('kernel', 'image', 'OS/SDK provenance', a['image'].get('os_version'), b['image'].get('os_version'), 'UNKNOWN', 'LOW',
            impact='Environment versions differ; do not attribute all findings to GCC versus LLVM.'))
    if config['performance']['enabled']:
        old, new = index(a['elf_objects']), index(b['elf_objects'])
        tolerance = config['performance']['tolerance_percent']
        for path in sorted(set(old) & set(new)):
            size = old[path]['size']
            if size:
                delta = (new[path]['size'] - size) / size * 100
                out.append(finding('performance', path, 'binary size', size, new[path]['size'],
                    'INCOMPATIBLE' if delta > tolerance else 'COMPATIBLE', 'LOW',
                    impact=f'Size delta {delta:.2f}%; configured budget {tolerance}%. This is a resource budget, not an ABI failure.'))
    for manifest, label in ((a, 'baseline'), (b, 'candidate')):
        for limit in manifest['limitations']:
            out.append(finding(limit['dimension'], label + ':' + limit['component'], 'coverage', None, limit['reason'], 'UNKNOWN', 'INFO',
                'capability/coverage assessment', impact=limit['reason'], action='Provide the required tool, debug information, SDK or authorized target environment.'))
        for cap in manifest.get('capabilities', []):
            out.append(finding(cap['dimension'], label, 'subsystem detection', None, cap['reason'], cap['status'], 'INFO'))
    return finalize(out, config)


def advanced_abi(a: dict[str, Any], b: dict[str, Any], roots: tuple[Any, Any], tools: Tools) -> list[dict[str, Any]]:
    binary = tools.path('abidiff')
    if not binary:
        return [finding('abi', '*', 'libabigail', None, 'abidiff unavailable', 'UNKNOWN', 'INFO')]
    out = []
    right = index(b['elf_objects'])
    for obj in a['elf_objects']:
        other = right.get(obj['path'])
        if not other or not obj.get('debug_info') or not other.get('debug_info'):
            continue
        before, after = roots[0].resolve(obj['path']), roots[1].resolve(obj['path'])
        if not before or not after:
            continue
        result = tools.run([binary, '--no-default-suppression', '--fail-no-debug-info', str(before), str(after)])
        code = result['returncode']
        status = 'UNKNOWN' if code < 0 or code & 3 else 'INCOMPATIBLE' if code & 8 else 'UNKNOWN' if code & 4 else 'COMPATIBLE'
        out.append(finding('abi', obj['path'], 'DWARF type/layout ABI', code if status == 'UNKNOWN' else 'DWARF ABI', result['stdout'],
            status, 'HIGH' if status == 'INCOMPATIBLE' else 'INFO', 'libabigail abidiff',
            [result['stdout_evidence'], result['stderr_evidence']], confidence='high' if status != 'UNKNOWN' else 'low'))
    return out or [finding('abi', '*', 'DWARF coverage', None, 'No matched ELF pair with embedded .debug_info; split debug files are not automatically located.', 'UNKNOWN', 'INFO')]


def finalize(findings: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    active = set(config['analysis']['modes'])
    unique = {}
    for item in findings:
        if item['dimension'] in active:
            item['severity'] = config['severity_overrides'].get(item['dimension'], item['severity'])
            unique[item['id']] = item
    return sorted(unique.values(), key=lambda x: (SEVERITIES.index(x['severity']), x['dimension'], x['component'], x['id']))
