"""ELF extraction using binutils; raw readelf output remains authoritative."""
from __future__ import annotations

from collections import Counter
import re
from pathlib import Path
from typing import Any
from .core import Tools

HEADER_KEYS = {'Class': 'class', 'Data': 'endianness', 'OS/ABI': 'osabi',
               'ABI Version': 'abi_version', 'Type': 'type', 'Machine': 'machine', 'Flags': 'flags'}
ELF_INVENTORY_REVISION = 4
DYNAMIC_SYMBOL_ROW = re.compile(r'^[ \t]*(\d+):[ \t]+([0-9a-fA-F]+)[ \t]+(\d+)[ \t]+(\S+)[ \t]+(\S+)'
                                r'[ \t]+(\S+)[ \t]+(\S+)(?:[ \t](.*))?$')


def elf_runtime_role(text: str, size: int, stderr: str = '') -> str:
    """Use file-backed sections and load segments, never the filename."""
    section_count = re.search(r'^\s*Number of section headers:\s*(\d+)\s*$', text, re.M)
    program_count = re.search(r'^\s*Number of program headers:\s*(\d+)\s*$', text, re.M)
    if not (section_count and program_count and re.search(r'^\s*Type:\s+(?:DYN|EXEC)\b', text, re.M)):
        return 'UNKNOWN'
    section_rows = re.findall(
        r'^ *\[ *(\d+)\] +(?:(\S+) +)?(\S+) +([0-9a-f]+) +([0-9a-f]+) +([0-9a-f]+) +'
        r'[0-9a-f]+ +(?:([A-Za-z]+) +)?\d+ +\d+ +\d+ *$', text, re.M)
    program_rows = re.findall(
        r'^ +(\S+) +(0x[0-9a-f]+) +(0x[0-9a-f]+) +0x[0-9a-f]+ +(0x[0-9a-f]+) +'
        r'0x[0-9a-f]+ +([RWE ]*) +(?:0x[0-9a-f]+|0) *$', text, re.M)
    if (len(section_rows) != int(section_count[1]) or len(program_rows) != int(program_count[1])
            or any(int(row[0]) != index for index, row in enumerate(section_rows))):
        return 'UNKNOWN'
    sections = [(name, kind, int(addr, 16), int(offset, 16), int(length, 16), flags)
                for _, name, kind, addr, offset, length, flags in section_rows]
    loads = [(int(offset, 16), int(addr, 16), int(length, 16), flags)
             for kind, offset, addr, length, flags in program_rows if kind == 'LOAD']
    if not loads:
        return 'UNKNOWN'
    dwarf = any(name in ('.debug_info', '.zdebug_info') and kind == 'PROGBITS' and 'A' not in flags and length
                and offset + length <= size for name, kind, _, offset, length, flags in sections)
    alloc = [(kind, addr, offset, length, flags) for _, kind, addr, offset, length, flags in sections
             if 'A' in flags and length]
    missing_debug_interp = (stderr.strip() == 'readelf: Error: Unable to find program interpreter name'
                            and any(name == '.interp' and kind == 'NOBITS' for name, kind, *_ in sections))
    if ((not stderr.strip() or missing_debug_interp) and dwarf and any('E' in flags for _, _, _, flags in loads)
            and any(kind == 'NOBITS' and 'X' in flags for kind, _, _, _, flags in alloc)
            and all(kind in ('NOBITS', 'NOTE') for kind, *_ in alloc)):
        return 'DEBUG_ONLY'
    if stderr.strip():
        return 'UNKNOWN'
    for kind, addr, offset, length, flags in alloc:
        if kind not in ('PROGBITS', 'DYNAMIC') or ('X' not in flags and kind != 'DYNAMIC'):
            continue
        if offset + length <= size and any(
                base <= offset and offset + length <= base + extent and addr - va == offset - base
                and ('X' not in flags or 'E' in permissions) for base, va, extent, permissions in loads):
            return 'RUNTIME_WITH_DEBUG' if dwarf else 'RUNTIME'
    return 'UNKNOWN'


def runtime_metadata_complete(obj):
    """Legacy manifests retain the existing evidence gate."""
    return (obj.get('resolution_metadata_complete') is True
            and obj.get('elf_runtime_role', 'RUNTIME') in ('RUNTIME', 'RUNTIME_WITH_DEBUG'))


def arm_inventory(obj, text, complete, relocations_requested):
    """Record observed ARM requirements without inferring hardware support."""
    attrs = obj['arm_attributes']
    stack = re.search(r'^\s*GNU_STACK\s+(?:0x[0-9a-fA-F]+\s+){5}([RWE ]+)\s+0x', text, re.M)
    relocations = Counter()
    advertised = 0
    for line in text.splitlines():
        header = re.match(r"Relocation section '.+' at offset .* contains (\d+) entr(?:y|ies):", line)
        if header:
            advertised += int(header[1])
        row = re.match(r'^\s*[a-fA-F0-9]+\s+[a-fA-F0-9]+\s+(R_ARM_[\w]+)\b', line)
        if row:
            relocations[row[1]] += 1
    count_verified = advertised == sum(relocations.values()) and (
        advertised > 0 or re.search(r'^There are no relocations in this file\.', text, re.M))
    return {'attributes': 'OBSERVED' if attrs else 'UNKNOWN',
            'arm_isa': attrs.get('Tag_ARM_ISA_use'), 'thumb_isa': attrs.get('Tag_THUMB_ISA_use'),
            'cpu_profile': attrs.get('Tag_CPU_arch_profile'),
            'stack_alignment_needed': attrs.get('Tag_ABI_align_needed'),
            'stack_alignment_preserved': attrs.get('Tag_ABI_align_preserved'),
            'gnu_stack_flags': ''.join(stack[1].split()) if stack else None,
            'unwind_sections': obj['unwind_sections'], 'tls_segments': obj['tls'],
            'tls_symbols_observed': sum(s['type'] == 'TLS' for s in obj['imports'] + obj['exports']),
            'relocations': dict(sorted(relocations.items())),
            'tls_relocations': sorted(r for r in relocations if '_TLS_' in r),
            'relocation_status': 'NOT_EXECUTED' if not relocations_requested else
            'COMPLETE' if complete and count_verified else 'UNKNOWN',
            'hardware_assessment': 'UNVERIFIED'}


def parse_readelf(text: str) -> dict[str, Any]:
    obj: dict[str, Any] = {'exports': [], 'imports': [], 'needed': [], 'soname': None,
        'rpath': [], 'runpath': [], 'interpreter': None, 'versions': [], 'sections': [], 'tls': [],
        'version_definitions': [], 'version_requirements': [], 'arm_attributes': {}, 'dynamic_flags': []}
    in_dynamic = False
    version_mode = None
    version_file = None
    for line in text.splitlines():
        if line.startswith("Symbol table '"):
            in_dynamic = line.startswith("Symbol table '.dynsym' ")
        elif not line.strip():
            in_dynamic = False
        if in_dynamic and (match := DYNAMIC_SYMBOL_ROW.match(line)):
            _,value,size,kind,binding,visibility,section,name = match.groups()
            if name:
                version_index = re.fullmatch(r'(.*@\S+) \((\d+)\)',name) if section=='UND' else None
                if version_index:
                    name = version_index[1]
                symbol = dict(name=name, value=int(value, 16), size=int(size), type=kind, binding=binding,
                              visibility=visibility, section=section, **symbol_identity(name))
                symbol['version_index'] = int(version_index[2]) if version_index else None
                if section == 'UND':
                    obj['imports'].append(symbol)
                elif binding in ('GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE') and visibility in ('DEFAULT', 'PROTECTED'):
                    obj['exports'].append(symbol)
            continue
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
    requirements = {(r['index'], r['name']): r for r in obj['version_requirements']}
    for symbol in obj['imports']:
        identity = symbol.get('version_index'), symbol['version']
        symbol['version_file'] = requirements.get(identity, {}).get('file')
    obj['arm_abi'] = arm_abi(obj)
    return obj


def collect_elf(path: Path, virtual: str, tools: Tools, mode: str, *, bounded=False) -> dict[str, Any]:
    obj: dict[str, Any] = {'path': virtual, 'size': path.stat().st_size, 'complete': False, 'resolution_metadata_complete': False,
                           'export_inventory_complete': False, 'export_inventory_status': 'UNKNOWN', 'elf_runtime_role': 'UNKNOWN'}
    tool = tools.path('readelf')
    if tool:
        flags = ['-W', '-h', '-l', '-d', '--dyn-syms', '-V', '-S', '-A', '-n']
        if mode != 'quick':
            flags += ['-r']
        result = tools.run([tool, *flags, str(path)], **({'max_capture_bytes':16*1024**2} if bounded else {}))
        obj.update(parse_readelf(result['stdout']))
        obj['evidence'] = [result['stdout_evidence'], result['stderr_evidence']]
        obj['complete'] = result['returncode'] == 0 and not result['stdout_truncated'] and 'machine' in obj
        if obj['complete'] and not result.get('error') and not result.get('stderr_truncated'):
            obj['elf_runtime_role'] = elf_runtime_role(result['stdout'], obj['size'], result['stderr'])
        # ELF-header success is independent of complete negative export evidence.
        symbols = re.search(r"Symbol table '\.dynsym' contains (\d+) entries:\n(.*?)(?:\n\n|\Z)", result['stdout'], re.S)
        rows = [match.groups() for line in symbols[2].splitlines() if (match := DYNAMIC_SYMBOL_ROW.match(line))] if symbols else []
        rows_valid = bool(symbols and result['stdout'].count("Symbol table '.dynsym' contains") == 1
            and int(symbols[1]) >= 1 and len(rows) == int(symbols[1])
            and all(int(index) == i and kind in ('NOTYPE', 'OBJECT', 'FUNC', 'SECTION', 'FILE', 'COMMON', 'TLS', 'IFUNC', 'GNU_IFUNC')
                    and binding in ('LOCAL', 'GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE')
                    and visibility in ('DEFAULT', 'INTERNAL', 'HIDDEN', 'PROTECTED')
                    and (i == 0 or (name and '[...]' not in name))
                    for i, (index,_,_,kind,binding,visibility,_,name) in enumerate(rows))
            and rows[0][3:7] == ('NOTYPE', 'LOCAL', 'DEFAULT', 'UND') and not (rows[0][7] or '').strip())
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
        version_valid &= all(not s['version'] or (s['version'] in requirements and
                             (s['version_index'] is None or s['version_file']))
                             for s in obj['imports'])
        obj['export_inventory_complete'] = bool(obj['complete'] and not result.get('error') and not result.get('stderr_truncated')
            and not result['stderr'].strip() and rows_valid and version_valid
            and all(obj.get(k) for k in ('class', 'endianness', 'type')))
        obj['export_inventory_status'] = ('COMPLETE' if obj['export_inventory_complete'] else
            'NOT_APPLICABLE' if not symbols and obj.get('type', '').startswith('REL') and obj['complete'] else 'UNKNOWN')
        obj['export_inventory_reason'] = ('All advertised dynsym rows and observed symbol versions reconciled.' if obj['export_inventory_complete'] else
            'No dynamic symbol table on ET_REL.' if obj['export_inventory_status'] == 'NOT_APPLICABLE' else
            'Tool failure/warning, truncated output, missing or unsupported dynsym/version records; absence unproven.')
        obj['export_inventory_evidence'] = obj['evidence']
        if obj['export_inventory_complete']:
            visible = list(dynamic_exports(obj))
            visible_rows = {id(symbol) for symbol in visible}
            obj['version_node_markers'] = [s for s in obj['exports'] if id(s) not in visible_rows]
            obj['exports'] = visible
        obj['resolution_metadata_complete'] = bool(obj['export_inventory_complete']
            and all(obj.get(k) for k in ('class', 'endianness', 'type'))
            and 'Dynamic section at offset' in result['stdout'])
        obj['resolution_metadata_evidence'] = obj['evidence'] if obj['resolution_metadata_complete'] else []
        if obj.get('machine') == 'ARM':
            obj['arm_inventory'] = arm_inventory(obj, result['stdout'], obj['complete'] and not result['stderr'].strip()
                                                  and not result.get('stderr_truncated'), mode != 'quick')
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
            result = tools.run([nm, '-D', '-P', str(path)], **({'max_capture_bytes':16*1024**2} if bounded else {}))
            obj['evidence'] = [result['stdout_evidence'], result['stderr_evidence']]
            obj['nm_symbols_raw'] = result['stdout']
    return obj


def version_nodes(obj):
    """The BASE record identifies the ELF itself, not a provided symbol version."""
    return {v['name']: v for v in obj.get('version_definitions', [])
            if v.get('index') != 1 and 'BASE' not in (v.get('flags') or '').upper().split()}


def dynamic_exports(obj):
    """Exclude demonstrated GNU ld node markers, including on legacy manifest replay."""
    nodes = version_nodes(obj) if obj.get('export_inventory_complete') is True and 'version_node_markers' not in obj else {}
    for sym in obj.get('exports', []):
        if (sym['name'] in nodes and type(nodes[sym['name']].get('index')) is int and nodes[sym['name']]['index'] > 1
                and sym.get('section') == 'ABS' and sym.get('type') == 'OBJECT'
                and sym.get('size') == sym.get('value') == 0 and sym.get('binding') == 'GLOBAL'
                and sym.get('visibility') == 'DEFAULT' and not sym.get('version')):
            continue
        yield sym


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
    conflict = bits & 0x600 == 0x600 or bool(float_abi and attr_float and float_abi != attr_float)
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
