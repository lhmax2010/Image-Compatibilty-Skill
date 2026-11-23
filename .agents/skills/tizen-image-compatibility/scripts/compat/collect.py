"""Deterministic static manifests; collection never executes image binaries."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any

from .core import VERSION, SCHEMA, Tools, canonical, digest, hash_file, limitation, write_json
from .elf import ELF_INVENTORY_REVISION, collect_elf
from .images import Image
from .packages import collect_package_inventory
from .source import normalize_text, parse_header

RUNTIMES = re.compile(r'lib(c\+\+|stdc\+\+|gcc|clang_rt|unwind|omp|gomp|atomic|asan|tsan|ubsan|c\.|m\.|pthread|dl\.)')
HARDWARE = re.compile(r'(lib(EGL|GLES|GL\.|vulkan|drm|wayland|asound|avcodec|avformat|swscale|v4l|va\.)|gstreamer|camera|/dri/|/vulkan/|/alsa/)')
NETWORK = re.compile(r'(lib(ssl|crypto|gnutls|nss|curl|nghttp2)|/ssl/|/NetworkManager/|/connman/|/resolv\.conf$|/hosts$|/bluetooth/|/systemd/network/|/include/(net|netinet|arpa)/)')
SECURITY = re.compile(r'(selinux|smack|apparmor|seccomp|/security/|/polkit|/sudoers|/passwd$|/group$|/dbus-1/system.d/)')


def parse_keys(text: str) -> dict[str, list[str]]:
    section = ''
    result: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
        elif '=' in line:
            key, value = line.split('=', 1)
            result.setdefault(section + '.' + key.strip() if section else key.strip(), []).append(value.strip())
    return result


def parse_dbus(text: str) -> list[dict[str, Any]]:
    # Real introspection files may reference the standard external DTD. ElementTree
    # never fetches it. Declared entities and internal subsets are unnecessary here.
    if re.search(r'<!ENTITY\b|<!DOCTYPE[^>]*\[', text, re.IGNORECASE):
        raise ET.ParseError('D-Bus XML entity declarations are unsupported')
    root = ET.fromstring(text)
    if root.tag != 'node':
        raise ET.ParseError('D-Bus introspection requires a root node')
    result = []
    def visit(node: ET.Element, parent: str) -> None:
        name = node.get('name', '')
        path = name if name.startswith('/') else parent.rstrip('/') + '/' + name
        for interface in node.findall('interface'):
            for member in interface:
                if member.tag not in ('method', 'signal', 'property'):
                    continue
                result.append({'name': path + ':' + interface.get('name', '') + ':' + member.tag + ':' + member.get('name', ''),
                    'attributes': dict(sorted(member.attrib.items())),
                    'args': [{'type': arg.get('type', ''), 'direction': arg.get('direction', 'out' if member.tag == 'signal' else 'in')}
                             for arg in member if arg.tag == 'arg']})
        for child in node.findall('node'):
            visit(child, path)
    visit(root, '')
    if len({member['name'] for member in result}) != len(result):
        raise ET.ParseError('Ambiguous duplicate D-Bus members')
    return sorted(result, key=lambda x: x['name'])


def collect(image: Image, name: str, label: str, mode: str, tools: Tools,
            workspace: Path, cache: Path | None = None) -> dict[str, Any]:
    m: dict[str, Any] = {'schema_version': SCHEMA, 'collector_version': VERSION,
        'image': {'name': name, 'source': str(image.source), 'format': image.format,
                  'toolchain': tools.config['comparison'][label + '_toolchain'], 'architecture': [], 'os_version': '', 'kernel_version': ''},
        'tools': tools.versions, 'collection_mode': mode,
        'elf_objects': [], 'public_headers': [], 'packages': [], 'filesystem': [],
        'configurations': [], 'services': [], 'commands': [], 'ipc': [],
        'security_interfaces': [], 'kernel': [], 'hardware': [], 'network': [],
        'development': [], 'runtime_libraries': [], 'capabilities': [], 'test_results': [], 'limitations': [],
        'ipc_documents': {}}
    if getattr(image, 'extraction_manifest', None):
        m['image']['extraction_manifest'] = label + '-extraction-manifest.json'
    active = set(tools.config['analysis']['modes'])
    input_scope = image.evidence_scope(tools.config['analysis'].get('input_scope', {}).get(label))
    m['image']['input_evidence_scope'] = input_scope
    elf_jobs = []
    header_failures = []
    max_bytes = tools.config['analysis']['max_text_bytes']
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    m['limitations'] += [limitation('abi', 'Function/data type layouts, calling convention, padding and member offsets require usable debug info and libabigail; symbol equality alone is not ABI proof.'),
        limitation('api', 'Lexical declarations do not resolve conditional compilation, overloads or typedef-equivalent signatures. Use SDK compile probes for semantic confirmation.'),
        limitation('linking', 'Loader cache, namespaces, interposition, dlopen paths, weak-symbol behavior and full versioned symbol resolution require target execution.'),
        limitation('kernel', 'Offline files cannot prove syscall, ioctl, /proc, /sys or kernel feature behavior.'),
        limitation('security', 'Offline metadata cannot prove effective ACL/LSM/capability enforcement or access permissions.'),
        limitation('services', 'Unit files do not prove successful boot or service activation.'),
        limitation('commands', 'Command presence does not prove options, stdout/stderr or exit-code semantics.'),
        limitation('network', 'Network configuration/certificate inventory does not prove DNS/DHCP/TLS/IPv6 behavior.'),
        limitation('runtime', 'Runtime semantics require an explicitly authorized isolated environment.')]
    m['limitations'] += [limitation('ipc', 'Offline D-Bus XML does not prove bus accessibility, Unix socket/RPC semantics or activation.'),
        limitation('headers', 'Header compilation needs explicit compilers and matching SDK sysroots; lexical API collection is not a compile pass.'),
        limitation('compiler_runtime', 'Runtime-library inventory and ELF exports do not prove C++ ABI, builtin, sanitizer, atomic or OpenMP behavior.'),
        limitation('performance', 'Boot/load time, memory/CPU usage, throughput and stability benchmarks are not built in. Optional binary-size budget only.'),
        limitation('runtime', 'Built-in probes cover a representative subset. UTF-8 locales, futex/epoll, hardware and target-specific Tizen APIs need configured probes.')]
    if image.format in ('tar', 'squashfs'):
        m['limitations'].append(limitation('security', 'Archive extraction cannot recover all xattrs, ACLs and original ownership (TAR uid/gid/mode are retained separately).'))
    if image.format == 'rpm-collection':
        m['limitations'].append(limitation('filesystem', 'RPM collection inventories packages only; payloads are not installed or expanded. Supply an extracted rootfs for ELF/API analysis.'))
    for virtual, path, metadata in image.walk():
        if not tools.config['analysis']['ignore_timestamps'] and path.exists():
            metadata['mtime_ns'] = path.lstat().st_mtime_ns
        m['filesystem'].append(metadata)
        kind = metadata['type']
        is_ipc = '/dbus-1/interfaces/' in virtual and Path(virtual).suffix == '.xml' and kind in ('file', 'symlink')
        if is_ipc:
            m['ipc_documents'][virtual] = 'UNKNOWN'
        if kind in ('file', 'symlink') and re.match(r'^/(usr/)?s?bin/[^/]+$', virtual):
            if kind == 'symlink' or int(metadata['mode'], 8) & 0o111:
                m['commands'].append({'path': virtual, 'target': metadata.get('target')})
        if kind == 'symlink':
            metadata['resolved'] = '/' + image.resolve(virtual).relative_to(image.root).as_posix() if image.resolve(virtual) else None
            # File aliases expose their own public header/config installation paths.
            target = image.resolve(virtual)
            if target and target.is_file() and ('/include/' in virtual or virtual.startswith('/etc/') or '/systemd/' in virtual or is_ipc):
                path, kind = target, 'file'
            else:
                if '/include/' in virtual and Path(virtual).suffix in ('.h', '.hpp', '.hh', '.hxx'):
                    header_failures.append(virtual)
                    m['limitations'].append(limitation('api', 'Header symlink unresolved or unreadable', virtual))
                continue
        if kind != 'file' or not path.is_file():
            continue
        try:
            with path.open('rb') as stream:
                magic = stream.read(4)
            if magic == b'\x7fELF':
                elf_jobs.append((path, virtual))
            if HARDWARE.search(virtual):
                m['hardware'].append({'path': virtual})
            if NETWORK.search(virtual):
                m['network'].append({'path': virtual})
            is_header = Path(virtual).suffix in ('.h', '.hpp', '.hh', '.hxx') and '/include/' in virtual
            is_service = '/systemd/' in virtual and path.suffix in ('.service', '.socket', '.target', '.timer', '.mount', '.conf')
            is_development = path.suffix == '.pc' or path.name.endswith(('Config.cmake', '-config.cmake'))
            is_kernel = virtual.startswith('/boot/config') or '/include/linux/' in virtual or '/include/asm' in virtual
            is_config = virtual.startswith('/etc/') or is_service or is_development or is_kernel or '/dbus-1/' in virtual or '/tmpfiles.d/' in virtual or '/udev/' in virtual
            if kind == 'file' and ('security' in active):
                xattrs = {}
                metadata['security_metadata_complete'] = False
                try:
                    for attr in sorted(os.listxattr(path, follow_symlinks=False)):
                        if attr.startswith(('security.', 'system.posix_acl')):
                            xattrs[attr] = os.getxattr(path, attr, follow_symlinks=False).hex()
                    metadata['security_metadata_complete'] = all(input_scope[k] == 'OBSERVABLE' for k in
                        ('uid_gid_mode', 'xattrs', 'acl', 'smack', 'file_capabilities'))
                    metadata['has_file_capabilities'] = 'security.capability' in xattrs
                except OSError as exc:
                    m['limitations'].append(limitation('security', f'xattr unreadable: {exc.strerror}', virtual))
                if xattrs or int(metadata['mode'], 8) & 0o6000:
                    m['security_interfaces'].append({'path': virtual, 'mode': metadata['mode'], 'xattrs': xattrs})
            if not (is_header or is_config or SECURITY.search(virtual)):
                continue
            if path.stat().st_size > max_bytes:
                if is_header:
                    header_failures.append(virtual)
                m['limitations'].append(limitation('api' if is_header else 'filesystem', 'Text exceeds max_text_bytes', virtual))
                continue
            raw = path.read_bytes()
            if b'\x00' in raw:
                if is_header:
                    header_failures.append(virtual)
                    m['limitations'].append(limitation('api', 'Header contains NUL; not parsed', virtual))
                if SECURITY.search(virtual):
                    m['security_interfaces'].append({'path': virtual, 'policy_hash': digest(raw)})
                continue
            text = raw.decode('utf-8', 'replace')
            if is_header:
                try:
                    raw.decode('utf-8', 'strict')
                except UnicodeDecodeError:
                    header_failures.append(virtual)
                    m['limitations'].append(limitation('api', 'Header decode failed; replacement text is observation only', virtual))
            normalized = normalize_text(text, tools.config['analysis']['normalize_build_paths'])
            evidence = 'evidence/' + digest(raw) + '.txt'
            (tools.output / evidence).write_bytes(raw)
            if is_header:
                m['public_headers'].append({'origin': 'runtime_image', 'path': virtual, 'sha256': digest(raw), 'evidence': [evidence], **parse_header(normalized)})
            if is_config:
                entry = {'path': virtual, 'normalized': normalized, 'keys': parse_keys(normalized), 'evidence': [evidence]}
                m['configurations'].append(entry)
                if is_service:
                    m['services'].append(entry)
                if is_development:
                    m['development'].append(entry)
                if is_kernel:
                    m['kernel'].append(entry)
                if SECURITY.search(virtual):
                    m['security_interfaces'].append(entry)
                if is_ipc:
                    try:
                        m['ipc'] += [{'path': virtual, **x, 'evidence': [evidence]} for x in parse_dbus(raw.decode('utf-8'))]
                        m['ipc_documents'][virtual] = 'COMPLETE'
                    except (ET.ParseError, RecursionError, UnicodeError) as exc:
                        m['limitations'].append(limitation('ipc', f'Invalid D-Bus XML: {exc}', virtual))
        except OSError as exc:
            m['limitations'].append(limitation('filesystem', f'Unreadable: {exc.strerror}', virtual))
    for error in image.errors:
        m['limitations'].append(limitation('filesystem', f'Directory traversal failed: {error.strerror}', '*'))
    def elf_job(job: tuple[Path, str]) -> dict[str, Any]:
        path, virtual = job
        key = digest(canonical([VERSION, ELF_INVENTORY_REVISION, mode, virtual, hash_file(path), tools.versions.get('readelf'), tools.versions.get('nm')]).encode())
        cache_file = cache / (key + '.json') if cache else None
        if cache_file and cache_file.exists():
            try:
                stored = json.loads(cache_file.read_text())
                if not isinstance(stored, dict) or stored.get('path') != virtual or not stored.get('complete'):
                    raise ValueError('Invalid cache record')
                for ref in stored.get('evidence', []):
                    if not isinstance(ref, str) or not re.fullmatch(r'evidence/[a-f0-9]{64}\.txt', ref):
                        raise ValueError('Invalid cache evidence path')
                    source = cache / Path(ref).name
                    (tools.output / ref).write_bytes(source.read_bytes())
                return stored
            except (OSError, ValueError):
                pass
        obj = collect_elf(path, virtual, tools, mode)
        if cache_file and obj['complete']:
            for ref in obj.get('evidence', []):
                (cache / Path(ref).name).write_bytes((tools.output / ref).read_bytes())
            write_json(cache_file, obj)
        return obj
    if active & {'elf', 'abi', 'linking', 'compiler_runtime', 'performance'}:
        with ThreadPoolExecutor(max_workers=int(tools.config['analysis']['workers'])) as pool:
            m['elf_objects'] = sorted(pool.map(elf_job, elf_jobs), key=lambda x: x['path'])
    source_files = {f['path']: f for f in m['filesystem']}
    for obj in m['elf_objects']:
        # Content caches never establish permissions/capabilities: observe the source again.
        source_metadata = source_files.get(obj['path'], {})
        obj['execution_metadata'] = {k: source_metadata[k] for k in ('mode', 'security_metadata_complete', 'has_file_capabilities') if k in source_metadata}
        if not obj['complete']:
            m['limitations'].append(limitation('elf', obj.get('error', 'Incomplete ELF'), obj['path']))
        if RUNTIMES.search(Path(obj['path']).name):
            m['runtime_libraries'].append({'path': obj['path'], 'soname': obj.get('soname')})
    m['image']['architecture'] = sorted({obj.get('machine', str(obj.get('machine_id', 'unknown'))) for obj in m['elf_objects']})
    release = image.resolve('/etc/os-release')
    if release and release.is_file() and release.stat().st_size < max_bytes:
        m['image']['os_version'] = parse_keys(release.read_text(errors='replace'))
    m['image']['kernel_version'] = sorted({Path(x['path']).name.removeprefix('config-') for x in m['kernel'] if x['path'].startswith('/boot/config-')})
    if 'packages' in active:
        m['packages'], m['available_packages'], m['package_inventory'], limits = collect_package_inventory(image, tools, workspace)
        m['limitations'] += limits
    if not m['hardware']:
        m['capabilities'].append({'dimension': 'hardware', 'status': 'NOT_APPLICABLE', 'reason': 'No multimedia userspace interface detected; physical hardware presence is unknown.'})
    else:
        m['limitations'].append(limitation('hardware', 'Driver/codec inventory does not establish device behavior or hardware acceleration.'))
    m['loader_environment'] = tools.config['loader']['environments'].get(label, {})
    m['loader_configuration'] = [x for x in m['configurations'] if x['path'] == '/etc/ld.so.conf' or x['path'].startswith('/etc/ld.so.conf.d/')]
    scope_complete = all(input_scope[key] != 'NOT_RESTORED' for key in ('paths', 'file_contents'))
    m['filesystem_path_inventory_complete'] = (image.format != 'rpm-collection' and not image.errors
                                               and input_scope['paths'] != 'NOT_RESTORED')
    m['collection_complete'] = (m['filesystem_path_inventory_complete'] and scope_complete
                                and not any(x['dimension'] == 'filesystem' for x in m['limitations']))
    m['collector_execution'] = {}
    if elf_jobs and m['elf_objects']:
        failures = [o for o in m['elf_objects'] if not o['complete']]
        done = len(m['elf_objects']) - len(failures)
        m['collector_execution']['readelf'] = {
            'status': 'COMPLETE' if not failures else 'PARTIAL' if done else 'FAILED',
            'successful': done, 'attempted': len(m['elf_objects']),
            'errors': [{'path': obj['path'], 'reason': obj['error'], 'evidence': obj.get('evidence', [])}
                       for obj in failures]}
    if 'packages' in active:
        inventory = m['package_inventory']
        archive_failed = inventory['archive_status'] == 'PARTIAL'
        status = inventory.get('execution', 'NOT_EXECUTED')
        if archive_failed and status != 'FAILED':
            status = 'PARTIAL' if inventory['archive_count'] or status == 'COMPLETE' else 'FAILED'
        m['collector_execution']['rpm'] = {
            'status': status if status != 'NOT_EXECUTED' or not inventory['archive_count'] else 'COMPLETE',
            'reason': inventory['reason'] or ('RPM archive collection incomplete' if archive_failed else ''),
            'evidence': inventory.get('evidence', [])}
    m['header_inventory_complete'] = m['collection_complete'] and not header_failures
    m['header_inventory_scope'] = 'Readable installed .h/.hpp/.hh/.hxx paths under include directories; not SDK or semantic completeness'
    # Compiler include search roots are not inferred from filenames; quoted includes
    # resolve relative to their entry. SDK-specific angle paths need recorded roots.
    m['header_include_roots'] = []
    for key, value in m.items():
        if isinstance(value, list):
            value.sort(key=canonical)
    return m
