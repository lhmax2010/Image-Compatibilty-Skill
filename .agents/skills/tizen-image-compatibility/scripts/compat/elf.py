"""ELF extraction using binutils; raw readelf output remains authoritative."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from .core import Tools

HEADER_KEYS = {'Class': 'class', 'Data': 'endianness', 'OS/ABI': 'osabi',
               'ABI Version': 'abi_version', 'Type': 'type', 'Machine': 'machine', 'Flags': 'flags'}


def parse_readelf(text: str) -> dict[str, Any]:
    obj: dict[str, Any] = {'exports': [], 'imports': [], 'needed': [], 'soname': None,
        'rpath': [], 'runpath': [], 'interpreter': None, 'versions': [], 'sections': [], 'tls': [],
        'version_definitions': [], 'version_requirements': [], 'arm_attributes': {}, 'dynamic_flags': []}
    in_dynamic = False
    version_mode = None
    version_file = None
    for line in text.splitlines():
        if line.startswith('Version definition section'):
            version_mode = 'definitions'
        elif line.startswith('Version needs section'):
            version_mode = 'requirements'
        elif line.startswith('Version symbols section'):
            version_mode = None
        if version_mode == 'definitions':
            match = re.search(r'Flags:\s*(.*?)\s+Index:\s*(\d+).*?Name:\s*(\S+)', line)
            if match:
                obj['version_definitions'].append(dict(name=match[3], index=int(match[2]), flags=match[1], parents=[]))
            parent = re.search(r'Parent \d+:\s*(\S+)', line)
            if parent and obj['version_definitions']:
                obj['version_definitions'][-1]['parents'].append(parent[1])
        if version_mode == 'requirements':
            file_match = re.search(r'File:\s*(\S+)', line)
            if file_match:
                version_file = file_match[1]
            match = re.search(r'Name:\s*(\S+)\s+Flags:\s*(.*?)\s+Version:\s*(\d+)', line)
            if match:
                obj['version_requirements'].append(dict(file=version_file, name=match[1], flags=match[2], index=int(match[3])))
        attr = re.match(r'\s*(Tag_\w+):\s*(.*)', line)
        if attr:
            obj['arm_attributes'][attr[1]] = attr[2]
        flag = re.search(r'\((FLAGS_1|FLAGS|FILTER|AUXILIARY|AUDIT|DEPAUDIT|SYMBOLIC)\)\s*(.*)', line)
        if flag:
            obj['dynamic_flags'].append(flag[1] + ':' + flag[2])
        for key, name in HEADER_KEYS.items():
            match = re.match(r'\s*' + re.escape(key) + r':\s*(.*)', line)
            if match:
                obj[name] = match[1].strip()
        if "Symbol table '" in line:
            in_dynamic = "'.dynsym'" in line
        if in_dynamic:
            match = re.match(r'\s*\d+:\s+[0-9a-fA-F]+\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
            if match:
                size, kind, binding, visibility, section, name = match.groups()
                symbol = dict(name=name, size=int(size), type=kind, binding=binding, visibility=visibility,
                              section=section, **symbol_identity(name))
                version_index = re.search(r'\((\d+)\)\s*$', line)
                symbol['version_index'] = int(version_index[1]) if version_index else None
                if section == 'UND':
                    obj['imports'].append(symbol)
                elif binding in ('GLOBAL', 'WEAK', 'UNIQUE') and visibility in ('DEFAULT', 'PROTECTED'):
                    obj['exports'].append(symbol)
        match = re.search(r'\((NEEDED|SONAME|RPATH|RUNPATH)\).*?\[(.*?)\]', line)
        if match:
            key, value = match.groups()
            if key == 'SONAME':
                obj['soname'] = value
            elif key == 'NEEDED':
                obj['needed'].append(value)
            else:
                obj[key.lower()] = value.split(':')
        match = re.search(r'Requesting program interpreter:\s*(.*?)\]', line)
        if match:
            obj['interpreter'] = match[1]
        if re.match(r'\s*TLS\s', line):
            obj['tls'].append(line.strip())
        match = re.search(r'\[\s*\d+\]\s+(\.[\w.]+)\s', line)
        if match:
            obj['sections'].append(match[1])
        match = re.search(r'Name:\s*(\S+)', line)
        if match:
            obj['versions'].append(match[1])
        match = re.search(r'Build ID:\s*(\S+)', line)
        if match:
            obj['build_id'] = match[1]
    for key in ('exports', 'imports'):
        obj[key].sort(key=lambda x: (x['name'], x['type']))
    for key in ('versions', 'sections'):
        obj[key] = sorted(set(obj[key]))
    obj['cxx'] = {name: sorted(s['name'] for s in obj['exports'] if s['name'].startswith(prefix))
                  for name, prefix in [('mangled', '_Z'), ('rtti', '_ZTI'), ('vtables', '_ZTV')]}
    obj['unwind_sections'] = [s for s in obj['sections'] if s in ('.eh_frame', '.eh_frame_hdr', '.gcc_except_table', '.ARM.exidx', '.ARM.extab')]
    obj['debug_info'] = any(x in obj['sections'] for x in ('.debug_info', '.zdebug_info'))
    requirements = {r['index']: r for r in obj['version_requirements']}
    for symbol in obj['imports']:
        symbol['version_file'] = requirements.get(symbol.get('version_index'), {}).get('file')
    obj['arm_abi'] = arm_abi(obj)
    return obj


def collect_elf(path: Path, virtual: str, tools: Tools, mode: str) -> dict[str, Any]:
    obj: dict[str, Any] = {'path': virtual, 'size': path.stat().st_size, 'complete': False}
    tool = tools.path('readelf')
    if tool:
        flags = ['-W', '-h', '-l', '-d', '--dyn-syms', '-V', '-S', '-A', '-n']
        if mode != 'quick':
            flags += ['-r']
        result = tools.run([tool, *flags, str(path)])
        obj.update(parse_readelf(result['stdout']))
        obj['evidence'] = [result['stdout_evidence'], result['stderr_evidence']]
        obj['complete'] = result['returncode'] == 0 and not result['stdout_truncated'] and 'machine' in obj
        if not obj['complete']:
            obj['error'] = result['error'] or result['stderr'] or 'Incomplete ELF parse'
    else:
        obj['error'] = 'readelf unavailable; ELF header fallback only, symbols unsupported'
        with path.open('rb') as stream:
            header = stream.read(20)
        if len(header) >= 20:
            endian = 'little' if header[5] == 1 else 'big'
            obj.update({'class': {1: 'ELF32', 2: 'ELF64'}.get(header[4], 'unknown'),
                        'endianness': endian, 'machine_id': int.from_bytes(header[18:20], endian),
                        'osabi_id': header[7], 'abi_version': str(header[8])})
        nm = tools.path('nm')
        if nm:
            result = tools.run([nm, '-D', '-P', str(path)])
            obj['evidence'] = [result['stdout_evidence'], result['stderr_evidence']]
            obj['nm_symbols_raw'] = result['stdout']
    return obj


def symbol_identity(name: str) -> dict[str, Any]:
    base, separator, version = name.partition('@@' if '@@' in name else '@')
    return {'base_name': base, 'version': version or None, 'default_version': separator == '@@'}


def arm_abi(obj: dict[str, Any]) -> dict[str, Any]:
    if obj.get('machine') != 'ARM':
        return {}
    flags = obj.get('flags', '')
    match = re.match(r'0x([0-9a-fA-F]+)', flags)
    bits = int(match[1], 16) if match else 0
    attrs = obj.get('arm_attributes', {})
    vfp = attrs.get('Tag_ABI_VFP_args')
    # Missing attributes do not prove the base PCS; hand assembly often omits them.
    float_abi = 'hard' if bits & 0x400 else 'soft' if bits & 0x200 else None
    attr_float = 'hard' if vfp == 'VFP registers' else 'soft' if vfp == 'Base AAPCS' else None
    conflict = bool(float_abi and attr_float and float_abi != attr_float)
    return {'eabi': (bits >> 24) or None, 'float': float_abi or attr_float,
            'vfp_args': vfp, 'cpu_arch': attrs.get('Tag_CPU_arch'), 'conflict': conflict}


def target_abi_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not all(left.get(k) is not None and left.get(k) == right.get(k) for k in ('class', 'endianness', 'machine')):
        return False
    if left.get('machine') == 'ARM':
        a, b = left.get('arm_abi') or arm_abi(left), right.get('arm_abi') or arm_abi(right)
        if a.get('conflict') or b.get('conflict'):
            return False
        return all(a.get(k) is not None and a.get(k) == b.get(k) for k in ('eabi', 'float'))
    return True
