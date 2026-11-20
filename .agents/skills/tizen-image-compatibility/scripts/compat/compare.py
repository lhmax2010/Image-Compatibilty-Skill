"""Directional compatibility: can baseline consumers use candidate interfaces?"""
from __future__ import annotations

from pathlib import Path
from collections import defaultdict
from typing import Any
from .core import DIMENSIONS, SEVERITIES, Tools, canonical, digest, finding
from .elf import symbol_identity, target_abi_matches, arm_abi
from .linker import dependency_checks
from .debuginfo import advanced_abi
from .source import declaration_reachability, header_inventory_complete


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
    return {symbol['name']: symbol for symbol in obj.get('exports', [])}


def runtime_requirements(obj):
    runtimes = ('libstdc++.', 'libc++.', 'libc++abi.', 'libgcc_s.', 'libunwind.', 'libclang_rt.', 'compiler-rt')
    imports = ('__cxa_throw', '__cxa_begin_catch', '__cxa_thread_atexit', '__gxx_personality',
               '_Unwind_', '_ZTI', 'pthread_cancel', 'pthread_setcancelstate')
    return {'libraries': sorted(n for n in obj.get('needed', []) if n.startswith(runtimes)),
            'imports': sorted({s['name'] for s in obj.get('imports', []) if s['name'].startswith(imports)}),
            'unwind_sections': obj.get('unwind_sections', [])}


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
        if obj.get('machine') == other.get('machine') == 'ARM':
            old_arm, new_arm = obj.get('arm_abi') or arm_abi(obj), other.get('arm_abi') or arm_abi(other)
            contradictory = old_arm.get('conflict') or new_arm.get('conflict')
            for key in ('eabi', 'float'):
                if old_arm.get(key) and new_arm.get(key) and old_arm[key] != new_arm[key]:
                    findings.append(finding('elf', path, 'ARM ' + key, old_arm[key], new_arm[key],
                                            'UNKNOWN' if contradictory else 'INCOMPATIBLE', 'CRITICAL', evidence=ev))
            before, after = obj.get('arm_inventory'), other.get('arm_inventory')
            if before != after and (before or after):
                findings.append(finding('elf', path, 'ARM ISA, TLS, relocations and unwind', before, after,
                    'UNKNOWN', 'MEDIUM', 'ARM ELF requirement inventory', ev,
                    'Observed requirements differ or are incomplete. Verify interworking, relocation and unwind on the target.'))
        findings.append(finding('elf', path, 'target ABI metadata',
            {k: obj.get(k) for k in ('class', 'machine', 'endianness', 'arm_abi')},
            {k: other.get(k) for k in ('class', 'machine', 'endianness', 'arm_abi')},
            'COMPATIBLE' if target_abi_matches(obj, other) else 'UNKNOWN', 'INFO', 'ELF target ABI metadata only', ev))
        left, right = exports(obj), exports(other)
        old_exports_complete = obj.get('export_inventory_complete') is True
        new_exports_complete = other.get('export_inventory_complete') is True
        if not (old_exports_complete and new_exports_complete):
            findings.append(finding('abi', path, 'dynamic export collection coverage',
                obj.get('export_inventory_complete'), other.get('export_inventory_complete'), 'UNKNOWN', 'HIGH',
                'ELF dynamic export inventory completeness', ev,
                'Observed symbols remain usable evidence; an incomplete inventory cannot prove absence.'))
        versions = {}
        defaults = {}
        for exported in right.values():
            identity = symbol_identity(exported['name'])
            versions.setdefault((identity['base_name'], identity['version']), []).append(exported)
            if identity['default_version'] or identity['version'] is None:
                defaults.setdefault(identity['base_name'], []).append(exported)
        for name, symbol in left.items():
            identity = symbol_identity(name)
            # Explicit version imports accept either default or non-default definition.
            alternatives = versions.get((identity['base_name'], identity['version']), [])
            if identity['version'] is None and not alternatives:
                alternatives = defaults.get(identity['base_name'], [])
            next_symbol = right.get(name) or (alternatives[0] if alternatives else None)
            if identity['default_version']:
                default_candidates = defaults.get(identity['base_name'], [])
                if not default_candidates:
                    findings.append(finding('abi', path, identity['base_name'] + ':default lookup', name, None,
                        'INCOMPATIBLE' if new_exports_complete else 'UNKNOWN', 'HIGH', 'ELF default-version lookup', ev))
                elif default_candidates[0]['name'] != name:
                    findings.append(finding('abi', path, identity['base_name'] + ':default lookup', name, default_candidates[0]['name'],
                        'UNKNOWN', 'HIGH', 'ELF default-version lookup', ev))
            if next_symbol is None:
                findings.append(finding('abi', path, name, symbol, None, 'INCOMPATIBLE' if new_exports_complete else 'UNKNOWN', 'HIGH',
                    'ELF dynamic export/version comparison', ev, 'Previously linkable symbol or default symbol version is absent.' if new_exports_complete else 'Symbol not observed in an incomplete dynamic export inventory; absence is unproven.',
                    'Restore the exported ABI/version or rebuild and validate all affected consumers.', 'high'))
            else:
                if '@' not in name and symbol['name'] != next_symbol['name']:
                    findings.append(finding('abi', path, name + ':default symbol version', symbol['name'], next_symbol['name'],
                        'UNKNOWN', 'HIGH', evidence=ev, impact='Unversioned lookup now selects a different symbol version.'))
                keys = ('type', 'visibility', 'binding') + (('size',) if symbol['type'] in ('OBJECT', 'TLS') else ())
                for key in keys:
                    if symbol.get(key) != next_symbol.get(key):
                        findings.append(finding('abi', path, name + ':' + key, symbol.get(key), next_symbol.get(key),
                            'INCOMPATIBLE' if key in ('size', 'type') else 'UNKNOWN', 'HIGH', evidence=ev))
        for name in sorted(set(right) - set(left)):
            findings.append(finding('abi', path, name, None, right[name], 'COMPATIBLE' if old_exports_complete else 'UNKNOWN', 'INFO', evidence=ev,
                                    impact='Additional exported interface; existing exports are compared separately.'))
        if obj.get('needed') != other.get('needed'):
            findings.append(finding('linking', path, 'DT_NEEDED', obj.get('needed'), other.get('needed'), 'UNKNOWN', 'MEDIUM', evidence=ev,
                impact='Runtime implementation/dependency changed; dependency availability is checked separately.'))
        before_runtime, after_runtime = runtime_requirements(obj), runtime_requirements(other)
        if before_runtime != after_runtime and any(before_runtime[k] or after_runtime[k] for k in ('libraries', 'imports')):
            findings.append(finding('compiler_runtime', path, 'C++ runtime boundary requirements', before_runtime, after_runtime,
                'UNKNOWN', 'MEDIUM', 'ELF runtime requirement inventory', ev,
                'Runtime names, imports and unwind metadata describe observed requirements.',
                'Run cross-DSO exception, RTTI, object lifecycle, TLS and cancellation probes on the selected target.'))
        if old_exports_complete and new_exports_complete and all(obj.get(k) == other.get(k) for k in ('exports', 'needed', 'soname', 'machine', 'class')):
            findings.append(finding('abi', path, 'dynamic interface surface', 'collected ELF surface', 'same collected ELF surface',
                'IDENTICAL', 'INFO', evidence=ev, impact='Symbol-level surface matches; type/layout and behavioral coverage remain separate.'))
    return findings



def compare_api(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    left, right = index(a['public_headers']), index(b['public_headers'])
    for path, header in left.items():
        other = right.get(path)
        if not other:
            complete = header_inventory_complete(b, path)
            findings.append(finding('api', path, 'public header', path, None, 'INCOMPATIBLE' if complete else 'UNKNOWN', 'HIGH', evidence=header.get('evidence'),
                impact='Header path absent from a complete header inventory.' if complete else 'Header not observed; incomplete header inventory cannot prove removal.'))
            continue
        ev = evidence(header, other)
        if all(header[k] == other[k] for k in ('tokens', 'macros', 'conditions', 'includes')):
            findings.append(finding('api', path, 'normalized public declarations', 'same token sequence', 'same token sequence',
                'UNKNOWN', 'INFO', 'C/C++ token normalization (lexical evidence only)', ev,
                'Tokens match; SDK, macros, target ABI and included declarations have not been semantically verified.'))
            continue
        for name in sorted(set(header['declarations']) | set(other['declarations'])):
            old, new = header['declarations'].get(name), other['declarations'].get(name)
            if old != new:
                reach = declaration_reachability(b, path, name, old) if old is not None and new is None else None
                baseline_simple = old is not None and declaration_reachability(a, path, name, old)['state'] == 'PROVEN_PRESENT'
                status = ('COMPATIBLE' if reach and baseline_simple and reach['state'] == 'PROVEN_PRESENT' else
                          'INCOMPATIBLE' if reach and baseline_simple and reach['state'] == 'PROVEN_ABSENT' else 'UNKNOWN')
                closure_evidence = [ref for h in b['public_headers'] if reach and h['path'] in reach['visited'] for ref in h.get('evidence', [])]
                item = finding('api', path, name, old, new, status, 'HIGH',
                    'lexical function declaration comparison', ev,
                    'Declaration changed; literal include closure can establish only identical plain C prototype availability. Other contexts require SDK compilation.')
                if reach:
                    item['declaration_reachability'] = reach
                    item['evidence'] = sorted(set(item['evidence'] + closure_evidence))
                    item['id'] = 'TC-' + digest(canonical({k: v for k, v in item.items() if k != 'id'}).encode())[:16]
                findings.append(item)
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
    old = defaultdict(list); new = defaultdict(list)
    for record in a['packages']: old[(record['name'], record['arch'])].append(record)
    for record in b['packages']: new[(record['name'], record['arch'])].append(record)
    findings = []
    for key, packages in old.items():
        candidates = new.get(key, [])
        if len(packages) != 1 or len(candidates) > 1:
            findings.append(finding('packages', ':'.join(key), 'package identity', packages, candidates, 'UNKNOWN', 'HIGH', impact='Multiple installed NEVRAs require explicit identity resolution; none were overwritten.'))
            continue
        package = packages[0]
        other = candidates[0] if candidates else None
        if not other:
            findings.append(finding('packages', ':'.join(key), 'package availability', package['name'], None, 'UNKNOWN', 'HIGH',
                impact='Package may be renamed, split or replaced; check its provided interfaces and file consumers.'))
            continue
        ev = evidence(package, other)
        for field in ('epoch', 'version', 'release', 'provides', 'requires', 'conflicts', 'obsoletes', 'files'):
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
    out += dependency_checks(b, 'baseline consumers on candidate', a['elf_objects'], consumer_manifest=a)
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
                missing = b.get('collection_complete') is True and not any(
                    x['component'] in (path, '*') and x['dimension'] == 'filesystem' for x in b['limitations'])
                status = 'INCOMPATIBLE' if missing and dimension == 'commands' else 'UNKNOWN'
                out.append(finding(dimension, path, key + ' availability', path, None, status, 'HIGH', evidence=value.get('evidence')))
                continue
            left = {k: v for k, v in value.items() if k not in ('evidence', 'sha256')}
            right = {k: v for k, v in other.items() if k not in ('evidence', 'sha256')}
            if left != right:
                out.append(finding(dimension, path, key, left, right, 'UNKNOWN',
                    'HIGH' if dimension == 'security' else 'MEDIUM', evidence=evidence(value, other)))
    old, new = {}, {}
    for manifest, by_name in ((a, old), (b, new)):
        for member in manifest.get('ipc', []):
            by_name.setdefault(member['name'], []).append(member)
    documents = b.get('ipc_documents')
    for name, members in old.items():
        member = members[0]
        peers = new.get(name, [])
        other = peers[0] if len(peers) == 1 else None
        if other is None or any(member.get(k) != other.get(k) for k in ('args', 'attributes')):
            known_baseline = a.get('ipc_documents', {}).get(member['path']) == 'COMPLETE'
            known_candidate = isinstance(documents, dict) and (documents.get(other['path']) == 'COMPLETE' if other else
                b.get('collection_complete') is True and all(status == 'COMPLETE' for status in documents.values()))
            complete = known_baseline and known_candidate and len(members) == 1 and len(peers) <= 1
            out.append(finding('ipc', member['path'], name, member, other, 'INCOMPATIBLE' if complete else 'UNKNOWN', 'HIGH',
                               'D-Bus introspection contract comparison', evidence(member, other or {}),
                               confidence='high' if complete else 'low'))
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



def finalize(findings: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    active = set(config['analysis']['modes'])
    unique = {}
    payloads = {}
    for item in findings:
        if item['dimension'] in active:
            item = dict(item, severity=config['severity_overrides'].get(item['dimension'], item['severity']))
            ident = item['id']
            payload = canonical({k: v for k, v in item.items() if k != 'occurrences'})
            if ident in unique:
                if payloads[ident] != payload:
                    raise ValueError('Conflicting finding ID: ' + ident)
                unique[ident]['occurrences'] = unique[ident].get('occurrences', 1) + item.get('occurrences', 1)
            else:
                unique[ident] = item
                payloads[ident] = payload
    return sorted(unique.values(), key=lambda x: (SEVERITIES.index(x['severity']), x['dimension'], x['component'], x['id']))
