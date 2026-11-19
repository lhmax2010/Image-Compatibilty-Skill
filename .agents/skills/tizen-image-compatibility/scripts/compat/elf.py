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
            match = re.match(r'\s*\d+:\s+([0-9a-fA-F]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
            if match:
                value, size, kind, binding, visibility, section, name = match.groups()
                symbol = dict(name=name, value=int(value, 16), size=int(size), type=kind, binding=binding, visibility=visibility,
                              section=section, **symbol_identity(name))
                version_index = re.search(r'\((\d+)\)\s*$', line)
                symbol['version_index'] = int(version_index[1]) if version_index else None
                if section == 'UND':
                    obj['imports'].append(symbol)
                elif binding in ('GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE') and visibility in ('DEFAULT', 'PROTECTED'):
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
    obj: dict[str, Any] = {'path': virtual, 'size': path.stat().st_size, 'complete': False, 'resolution_metadata_complete': False,
                           'export_inventory_complete': False, 'export_inventory_status': 'UNKNOWN'}
    tool = tools.path('readelf')
    if tool:
        flags = ['-W', '-h', '-l', '-d', '--dyn-syms', '-V', '-S', '-A', '-n']
        if mode != 'quick':
            flags += ['-r']
        result = tools.run([tool, *flags, str(path)])
        obj.update(parse_readelf(result['stdout']))
        obj['evidence'] = [result['stdout_evidence'], result['stderr_evidence']]
        obj['complete'] = result['returncode'] == 0 and not result['stdout_truncated'] and 'machine' in obj
        # ELF-header success is independent of complete negative export evidence.
        symbols = re.search(r"Symbol table '\.dynsym' contains (\d+) entries:\n(.*?)(?:\n\n|\Z)", result['stdout'], re.S)
        rows = re.findall(r'^\s*(\d+):\s+[0-9a-fA-F]+\s+\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:[ \t]+(\S+))?[^\n]*$', symbols[2], re.M) if symbols else []
        rows_valid = bool(symbols and result['stdout'].count("Symbol table '.dynsym' contains") == 1
            and int(symbols[1]) >= 1 and len(rows) == int(symbols[1])
            and all(int(row[0]) == i and row[1] in ('NOTYPE', 'OBJECT', 'FUNC', 'SECTION', 'FILE', 'COMMON', 'TLS', 'IFUNC', 'GNU_IFUNC')
                    and row[2] in ('LOCAL', 'GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE')
                    and row[3] in ('DEFAULT', 'INTERNAL', 'HIDDEN', 'PROTECTED')
                    and (i == 0 or (row[5] and '[...]' not in row[5])) for i, row in enumerate(rows))
            and rows[0][1:5] == ('NOTYPE', 'LOCAL', 'DEFAULT', 'UND') and not rows[0][5])
        # Advertised version records and every observed versioned symbol must reconcile.
        version_valid = True
        for title, key in [('definition', 'version_definitions'), ('needs', 'version_requirements')]:
            section = re.search(r'Version ' + title + r' section .*? contains (\d+) entr(?:y|ies):\n(.*?)(?:\n\n|\Z)', result['stdout'], re.S)
            if section:
                count = len(obj[key]) if title == 'definition' else len(re.findall(r'File:\s*\S+', section[2]))
                version_valid &= count == int(section[1])
                if title == 'needs':
                    version_valid &= sum(int(n) for n in re.findall(r'Cnt:\s*(\d+)', section[2])) == len(obj[key])
        definitions = {v['name'] for v in obj['version_definitions']}
        requirements = {v['name'] for v in obj['version_requirements']}
        version_valid &= all(not s['version'] or s['version'] in definitions for s in obj['exports'])
        version_valid &= all(not s['version'] or s['version'] in requirements for s in obj['imports'])
        obj['export_inventory_complete'] = bool(obj['complete'] and not result.get('error') and not result.get('stderr_truncated')
            and not result['stderr'].strip() and rows_valid and version_valid
            and all(obj.get(k) for k in ('class', 'endianness', 'type')))
        obj['export_inventory_status'] = ('COMPLETE' if obj['export_inventory_complete'] else
            'NOT_APPLICABLE' if not symbols and obj.get('type', '').startswith('REL') and obj['complete'] else 'UNKNOWN')
        obj['export_inventory_reason'] = ('All advertised dynsym rows and observed symbol versions reconciled.' if obj['export_inventory_complete'] else
            'No dynamic symbol table on ET_REL.' if obj['export_inventory_status'] == 'NOT_APPLICABLE' else
            'Tool failure/warning, truncated output, missing or unsupported dynsym/version records; absence unproven.')
        obj['export_inventory_evidence'] = obj['evidence']
        obj['resolution_metadata_complete'] = bool(obj['export_inventory_complete']
            and all(obj.get(k) for k in ('class', 'endianness', 'type'))
            and 'Dynamic section at offset' in result['stdout'])
        obj['resolution_metadata_evidence'] = obj['evidence'] if obj['resolution_metadata_complete'] else []
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
            'vfp_args': vfp, 'cpu_arch': attrs.get('Tag_CPU_arch'), 'conflict': conflict, 'pcs': 'vfp' if (float_abi or attr_float) == 'hard' else 'base' if (float_abi or attr_float) == 'soft' else None,
            'fp_arch': attrs.get('Tag_FP_arch')}


def target_abi_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not all(left.get(k) is not None and left.get(k) == right.get(k) for k in ('class', 'endianness', 'machine')):
        return False
    if left.get('machine') == 'ARM':
        a, b = left.get('arm_abi') or arm_abi(left), right.get('arm_abi') or arm_abi(right)
        if a.get('conflict') or b.get('conflict'):
            return False
        return all(a.get(k) is not None and a.get(k) == b.get(k) for k in ('eabi', 'float'))
    return True


def abi_relation(left, right):
    """Tri-state metadata comparison; missing fields never imply agreement."""
    missing = []; conflicts = []
    for key in ('class', 'endianness', 'machine'):
        if not left.get(key) or not right.get(key): missing.append(key)
        elif left[key] != right[key]: conflicts.append(key)
    if left.get('machine') == right.get('machine') == 'ARM':
        a, b = left.get('arm_abi') or arm_abi(left), right.get('arm_abi') or arm_abi(right)
        if a.get('conflict') or b.get('conflict'): conflicts.append('conflicting ARM attributes')
        for key in ('eabi', 'float'):
            if not a.get(key) or not b.get(key): missing.append(key)
            elif a[key] != b[key]: conflicts.append(key)
    return {'status': 'INCOMPATIBLE' if conflicts else 'UNKNOWN' if missing else 'COMPATIBLE',
            'missing': missing, 'conflicts': conflicts}


def verify_compile_target(elf, manifest, config, label):
    """Configured SDK ABI is primary; selected loader/libc objects support it.
    Other rootfs objects are diagnosed independently, never universal prerequisites.
    """
    configured = config['cross_compilation']['target_abis'].get(label)
    objects = manifest.get('elf_objects', [])
    selected_paths = config['cross_compilation']['runtime_objects'].get(label)
    if selected_paths is None:
        selected_paths = sorted({o['interpreter'] for o in objects if o.get('interpreter')} |
                                {o['path'] for o in objects if o.get('soname') in ('libc.so.6', 'libc.so')})
    selected = [o for o in objects if o['path'] in selected_paths and o.get('complete') and o.get('type', '').startswith(('DYN', 'EXEC'))]
    if configured:
        primary = {k: configured[k] for k in ('machine', 'class', 'endianness')}
        primary['arm_abi'] = {k: configured.get(k) for k in ('eabi', 'float', 'cpu_arch')}
        source = 'configured SDK ABI: ' + configured['provenance']
    elif selected:
        primary = selected[0]; source = 'selected target runtime'
    else:
        # Non-ARM synthetic/native images have no optional PCS metadata requirement.
        native = [o for o in objects if o.get('complete') and o.get('machine') != 'ARM' and o.get('type', '').startswith(('DYN', 'EXEC'))]
        primary = native[0] if native else {}; source = 'native image metadata' if native else 'no authoritative target evidence'
    result = abi_relation(elf, primary)
    if not elf.get('type', '').startswith('REL'):
        result['conflicts'].append('compile target must be ET_REL'); result['status'] = 'INCOMPATIBLE'
    isa = {'status': 'NOT_APPLICABLE'}
    if elf.get('machine') == 'ARM':
        want = (primary.get('arm_abi') or arm_abi(primary)).get('cpu_arch')
        got = (elf.get('arm_abi') or arm_abi(elf)).get('cpu_arch')
        isa = {'status': 'COMPATIBLE' if want and got and want == got else 'UNKNOWN',
               'probe_cpu_arch': got, 'reference_cpu_arch': want,
               'reason': 'CPU attribute agreement only; not hardware/extension validation' if want and got and want == got
                         else 'ISA requirements differ or are missing; reference object/SDK is not a hardware capability inventory'}
        if not want or not got:
            result['missing'].append('cpu_arch')
            if result['status'] != 'INCOMPATIBLE': result['status'] = 'UNKNOWN'
        elif want != got:
            result['missing'].append('ISA compatibility / target hardware evidence')
            if result['status'] != 'INCOMPATIBLE': result['status'] = 'UNKNOWN'
    supporting = [{'path': p, 'status': 'UNKNOWN', 'missing': ['authoritative runtime object unavailable'], 'conflicts': []} for p in selected_paths if p not in {o['path'] for o in selected}]
    for o in selected:
        r = abi_relation(elf, o); supporting.append({'path': o['path'], **r})
        if r['status'] == 'INCOMPATIBLE':
            result['status'] = 'INCOMPATIBLE'; result['conflicts'].append(o['path'])
    mixed = [{'path': o['path'], **abi_relation(primary, o)} for o in objects if o.get('complete') and not o.get('type', '').startswith('REL')]
    abi_status = abi_relation(elf, primary)['status']
    if any(r['status'] == 'INCOMPATIBLE' for r in supporting): abi_status = 'INCOMPATIBLE'
    return {**result, 'abi_status': abi_status, 'isa_assessment': isa,
            'hardware_assessment': {'status': 'UNKNOWN', 'reason': 'No target hardware capability validation performed'},
            'source': source, 'selected_objects': supporting,
            'other_objects': [r for r in mixed if r['status'] != 'COMPATIBLE']}
