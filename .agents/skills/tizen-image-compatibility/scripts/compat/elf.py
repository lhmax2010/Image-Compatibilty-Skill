"""ELF extraction using binutils; raw readelf output remains authoritative."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from .core import Tools

HEADER_KEYS = {'Class': 'class', 'Data': 'endianness', 'OS/ABI': 'osabi',
               'ABI Version': 'abi_version', 'Type': 'type', 'Machine': 'machine'}


def parse_readelf(text: str) -> dict[str, Any]:
    obj: dict[str, Any] = {'exports': [], 'imports': [], 'needed': [], 'soname': None,
        'rpath': [], 'runpath': [], 'interpreter': None, 'versions': [], 'sections': [], 'tls': []}
    in_dynamic = False
    for line in text.splitlines():
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
                symbol = dict(name=name, size=int(size), type=kind, binding=binding, visibility=visibility)
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
    for key in ('needed', 'versions', 'sections'):
        obj[key] = sorted(set(obj[key]))
    obj['cxx'] = {name: sorted(s['name'] for s in obj['exports'] if s['name'].startswith(prefix))
                  for name, prefix in [('mangled', '_Z'), ('rtti', '_ZTI'), ('vtables', '_ZTV')]}
    obj['unwind_sections'] = [s for s in obj['sections'] if s in ('.eh_frame', '.eh_frame_hdr', '.gcc_except_table', '.ARM.exidx', '.ARM.extab')]
    obj['debug_info'] = '.debug_info' in obj['sections']
    return obj


def collect_elf(path: Path, virtual: str, tools: Tools, mode: str) -> dict[str, Any]:
    obj: dict[str, Any] = {'path': virtual, 'size': path.stat().st_size, 'complete': False}
    tool = tools.path('readelf')
    if tool:
        flags = ['-W', '-h', '-l', '-d', '--dyn-syms', '-V', '-S']
        if mode != 'quick':
            flags += ['-r', '-n']
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
