"""Prepare an auditable, bounded image input without mounting or booting it."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import tempfile

from .core import InfrastructureError, InputError, canonical, hash_file, write_json
from .flash import PROBE_BYTES, PreparationError, copy_partition, decompress_xz, gpt_partitions, identify, vdfs_signature


MANIFEST = 'extraction-manifest.json'
METADATA = 'rootfs-metadata.json'
SCHEMA = 'tizen-image-preparation/1'
SCOPES = {'rootfs': 'runtime-rootfs', 'rpm-repository': 'package-inventory', 'rootstrap': 'sdk'}
ROOTS = {'runtime-rootfs': 'rootfs', 'package-inventory': 'rpms', 'sdk': 'rootstrap'}
FLASH_FORMATS = ('gpt', 'vdfs', 'xz', 'ext', 'erofs', 'squashfs')


def file_format(path):
    with path.open('rb') as source:
        return identify(source.read(PROBE_BYTES))


def is_tar_container(path):
    try:
        with tarfile.open(path) as archive:
            return archive.next() is not None
    except (OSError, EOFError, tarfile.TarError):
        return False


def has_regular_file(root):
    return any(not path.is_symlink() and path.is_file() for path in root.rglob('*'))


def looks_like_root(path):
    def directory(name):
        item = path / name
        return not item.is_symlink() and item.is_dir()
    return directory('etc') or (directory('usr') and any(directory(name) for name in ('bin', 'lib', 'var', 'usr/bin')))


def tar_payload(image, layer=None):
    """A recognized embedded format, not a suffix, distinguishes a flash TAR."""
    if looks_like_root(image.root):
        return None
    candidates, platform_seen = [], False
    for virtual, meta in image.metadata.items():
        if meta['type'] != 'file' or virtual.count('/') > 2:
            continue
        path = image.root / virtual.lstrip('/')
        if not path.is_symlink() and path.is_file():
            platform_seen |= path.name == 'platform.img'
            kind = file_format(path)
            if kind in FLASH_FORMATS:
                candidates.append((path, kind))
    if layer is not None:
        layer['recognized_members'] = [{'path': p.relative_to(image.root).as_posix(), 'format': kind, 'bytes': p.stat().st_size}
                                       for p, kind in candidates[:256]]
        layer['recognized_member_count'] = len(candidates)
    if not candidates:
        if platform_seen:
            raise PreparationError('FLASH_PAYLOAD_UNRECOGNIZED', 'platform.img has no supported container or filesystem signature')
        return None
    # platform.img is a role hint only after a byte signature has been observed.
    for choices in ([p for p in candidates if p[0].name == 'platform.img'],
                    [p for p in candidates if p[1] == 'gpt'], candidates):
        if len(choices) == 1:
            return choices[0]
        if choices:
            raise PreparationError('FLASH_PAYLOAD_AMBIGUOUS', 'Several recognized disk payloads; provide a verified replacement')
    return None


def _stamp(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def identity(path, config):
    """Hash file bytes or a tree's paths, types, permissions, link targets and bytes."""
    limit = config['analysis']['max_extract_bytes']
    if path.is_file():
        before = _stamp(path)
        checksum = hash_file(path)
        if before != _stamp(path):
            raise PreparationError('INPUT_CHANGED', 'File changed during SHA256 verification')
        return {'kind': 'file', 'bytes': before[2], 'sha256': checksum}
    if not path.is_dir():
        raise PreparationError('INPUT_UNAVAILABLE', 'Expected regular file or directory')
    checksum, size, count = hashlib.sha256(), 0, 0
    def unreadable(error):
        raise error
    for directory, dirs, files in os.walk(path, followlinks=False, onerror=unreadable):
        dirs.sort()
        for name in sorted(dirs + files):
            item = Path(directory) / name
            mode = item.lstat().st_mode
            content = None
            if stat.S_ISLNK(mode):
                content = os.readlink(item)
            elif stat.S_ISREG(mode):
                before = _stamp(item)
                size += before[2]
                if size > limit:
                    raise PreparationError('TREE_LIMIT', 'Rootfs size exceeds the extraction limit')
                content = hash_file(item)
                if before != _stamp(item):
                    raise PreparationError('INPUT_CHANGED', 'Tree entry changed during SHA256 verification')
            elif not stat.S_ISDIR(mode):
                raise PreparationError('TREE_ENTRY_UNSAFE', 'A physical special file cannot be prepared')
            count += 1
            if count > config['analysis']['max_extract_files']:
                raise PreparationError('TREE_LIMIT', 'Rootfs entry count exceeds the extraction limit')
            checksum.update((canonical([item.relative_to(path).as_posix(), mode, content]) + '\n').encode('utf-8', 'surrogateescape'))
    return {'kind': 'tree-v1', 'entries': count, 'bytes': size, 'sha256': checksum.hexdigest()}


def _json(path, limit=128 * 1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise PreparationError('PREPARATION_RECORD_INVALID', f'Expected a bounded regular JSON record: {path.name}')
    try:
        value = json.loads(path.read_text())
    except ValueError as exc:
        raise PreparationError('PREPARATION_RECORD_INVALID', f'Invalid JSON: {path.name}') from exc
    if not isinstance(value, dict):
        raise PreparationError('PREPARATION_RECORD_INVALID', f'Expected a JSON object: {path.name}')
    return value


def _set_coverage(record, scope, complete):
    record['coverage'] = {'scope': scope, 'complete': complete}


def _extract_adapter(source, work, tools, record, kind='vdfs', erofs_info=None):
    name = kind.upper()
    spec = tools.config['preparation'][kind+'_adapter']
    command = spec.get('command', [])
    executable = Path(command[0]).resolve() if command else None
    if not executable or not executable.is_file() or not os.access(executable, os.X_OK):
        raise PreparationError(name+'_EXTRACTOR_UNAVAILABLE', 'Configure an explicitly trusted host '+name+' extractor for this layout')
    origin = Path(record['source']['path'])
    if executable == origin or executable.is_relative_to(work.parent) or (origin.is_dir() and executable.is_relative_to(origin)):
        raise PreparationError(name+'_ADAPTER_INVALID', 'Extractor executable must be independent of image inputs and scratch output')
    if source == origin:
        copied = work / ('input.'+kind)
        copy_partition(source, copied, {'offset': 0, 'length': source.stat().st_size}, tools.config['analysis']['max_extract_bytes'])
        source = copied
    version = tools.run([str(executable), *spec.get('version_args', ['--version'])], cwd=work, max_capture_bytes=1024**2)
    if version['returncode'] != 0 or not version['stdout'].strip() or version.get('error'):
        raise PreparationError(name+'_ADAPTER_VERSION_FAILED', 'Extractor did not report a version')
    record['extractor'] = {'path': str(executable), 'sha256': hash_file(executable),
                           'version': version['stdout'].strip()[:4096], 'command_template': command}
    archive, receipt_file = work / (kind+'-rootfs.tar'), work / (kind+'-receipt.json')
    input_sha = hash_file(source)
    values = {'{input}': str(source), '{output}': str(archive), '{receipt}': str(receipt_file)}
    result = tools.run([str(executable), *(values.get(arg, arg) for arg in command[1:])],
                       cwd=work, timeout=tools.config['preparation']['adapter_timeout_seconds'], max_capture_bytes=1024**2)
    record['extractor'].update(exit_code=result['returncode'], evidence=[result['stdout_evidence'], result['stderr_evidence']])
    if (result['returncode'] != 0 or result.get('error') or archive.is_symlink() or not archive.is_file()
            or archive.stat().st_size > tools.config['analysis']['max_extract_bytes'] or hash_file(source) != input_sha):
        raise PreparationError(name+'_EXTRACTION_FAILED', 'Extractor failed, mutated the input copy, or returned an invalid TAR')
    if not tarfile.is_tarfile(archive):
        raise PreparationError(name+'_EXTRACTION_FAILED', 'Extractor output lacks TAR structure')
    receipt = _json(receipt_file)
    if (receipt.get('schema') != 'tizen-'+kind+'-receipt/1' or receipt.get('input_sha256') != input_sha
            or receipt.get('output_tar_sha256') != hash_file(archive)):
        raise PreparationError(name+'_RECEIPT_MISMATCH', 'Extractor receipt does not bind its input and output bytes')
    if erofs_info:
        for key, field in (('compat','feature_compat'),('incompat','feature_incompat'),
                           ('compression','compression_bitmap')):
            mask = receipt.get('supported_'+key+'_mask')
            flags = erofs_info[field] or 0
            if type(mask) is not int or not 0 <= mask <= 0xffffffff or flags & ~mask:
                raise PreparationError('EROFS_ADAPTER_FEATURE_UNVERIFIED','Adapter receipt does not account for detected '+key+' flags')
    record['extractor']['receipt'] = receipt
    record['layers'].append({'format': 'tar', 'role': 'adapter-output', 'sha256': receipt['output_tar_sha256']})
    rest = {part['guid'] for layer in record['layers'] if layer['format'] == 'gpt'
            for part in layer['partitions'] if part != layer.get('selected')}
    excluded = receipt.get('excluded_partitions', {})
    complete = (receipt.get('complete') is True and receipt.get('scope') == 'runtime-rootfs'
                and isinstance(excluded, dict) and set(excluded) == rest
                and all(isinstance(reason, str) and reason.strip() for reason in excluded.values()))
    _set_coverage(record, 'runtime-rootfs', complete)
    return archive


def _unpack_payload(path, kind, work, tools, record, inspect_only):
    limit = int(tools.config['analysis']['max_extract_bytes'])
    if kind == 'gpt':
        layer = gpt_partitions(path)
        record['layers'].append(layer)
        candidates = [p for p in layer['partitions'] if p['payload_format'] in ('xz', 'vdfs', 'squashfs', 'ext', 'erofs')]
        selected = [p for p in candidates if p['name'] == tools.config['preparation']['platform_partition']]
        choices = selected or candidates
        if len(choices) != 1:
            raise PreparationError('GPT_PARTITION_UNRESOLVED', 'No unique recognized partition payload; configure its GPT partition name')
        part = layer['selected'] = choices[0]
        target = work / 'partition.bin'
        part['sha256'] = copy_partition(path, target, part, limit)
        path, kind = target, part['payload_format']
    if kind == 'xz':
        target = work / 'decoded.bin'
        memlimit = tools.config['preparation']['xz_memory_mib'] * 1024**2
        record['layers'].append(decompress_xz(path, target, limit, memlimit))
        path, kind = target, file_format(target)
    if kind == 'vdfs':
        with path.open('rb') as stream:
            record['layers'].append(vdfs_signature(stream.read(PROBE_BYTES)))
        if inspect_only:
            spec = tools.config['preparation']['vdfs_adapter'].get('command', [])
            if not spec or not (Path(spec[0]).is_file() and os.access(spec[0], os.X_OK)):
                record['blocker'] = 'VDFS_EXTRACTOR_UNAVAILABLE'
            return None
        return _extract_adapter(path, work, tools, record)
    if kind == 'erofs':
        from .erofs import blocker, extract, superblock
        layer = superblock(path)
        record['layers'].append(layer)
        spec = tools.config['preparation']['erofs_adapter'].get('command')
        refused = blocker(layer,tools)
        if inspect_only:
            if refused:
                record['blocker'] = refused
            layer['external_adapter_configured'] = bool(spec)
            return None
        if spec and not layer['extra_devices']:
            return _extract_adapter(path,work,tools,record,'erofs',layer)
        archive = extract(path,work,tools,record,layer)
        _set_coverage(record,'runtime-rootfs',all(len(layer['partitions'])==1 for layer in record['layers'] if layer['format']=='gpt'))
        return archive
    record['layers'].append({'format': kind or 'unknown'})
    if not inspect_only:
        raise PreparationError('FLASH_FILESYSTEM_UNSUPPORTED', 'Supply a verified extracted Rootfs or same-build replacement for the identified payload')
    return None


def _replacement(path, kind, receipt_file, build_id, record, config):
    receipt = _json(receipt_file)
    observed = identity(path, config)
    if (not build_id or receipt.get('schema') != 'tizen-build-replacement/1' or receipt.get('build_id') != build_id
            or receipt.get('source_sha256') != record['source']['sha256']
            or receipt.get('replacement_sha256') != observed['sha256'] or receipt.get('kind') != kind):
        raise PreparationError('REPLACEMENT_IDENTITY_MISMATCH', 'Build ID, original bytes, replacement bytes or input kind do not match the trusted receipt')
    record['build_identity'] = {'id': build_id, 'basis': 'operator-supplied build receipt', 'receipt_sha256': hash_file(receipt_file)}
    record['replacement'] = {'path': str(path), 'kind': kind, 'identity': observed}
    _set_coverage(record, SCOPES[kind], receipt.get('complete') is True)


def prepare(source, output, tools, *, inspect_only=False, staged=None, replacement=None):
    """Prepare into a dedicated output; failed and partial manifests never grant eligibility."""
    from .images import Image

    source, output = source.resolve(), output.resolve()
    record = {'schema': SCHEMA, 'status': 'FAILED', 'source': {'path': str(source)}, 'layers': [],
              'tools': {'preparation': SCHEMA, 'python': sys.version.split()[0]},
              'coverage': {'scope': None, 'complete': False}}
    marker = output / MANIFEST
    protected = [source] + ([replacement[0], replacement[2]] if replacement else [])
    if any(output == p or (p.is_dir() and output.is_relative_to(p)) for p in protected):
        raise PreparationError('PREPARATION_OUTPUT_OVERLAP', 'Preparation output must be outside every input')
    if marker.exists() or marker.is_symlink():
        raise PreparationError('PREPARATION_OUTPUT_EXISTS', 'Preparation already has a manifest; choose another output')
    write_json(marker, {**record, 'status': 'PREPARING'})
    try:
        input_stamp = _stamp(source)
        record['source'].update(identity(source, tools.config))
        if staged is not None and staged.archive_stamp != input_stamp:
            raise PreparationError('INPUT_CHANGED', 'TAR changed after its initial extraction')
        with tempfile.TemporaryDirectory(prefix='.extract-', dir=output) as temp:
            work = Path(temp)
            legacy = staged
            if replacement:
                path, kind, receipt_file, build_id = replacement
                _replacement(path, kind, receipt_file, build_id, record, tools.config)
                record['layers'].append({'format': 'replacement', 'kind': kind})
                legacy = Image(path, work, tools, 'replacement', prepare_input=False)
            else:
                kind = file_format(source) if source.is_file() else None
                if kind == 'squashfs':
                    kind = None  # Standalone SquashFS remains on the existing path.
                payload = (source, kind) if kind in FLASH_FORMATS else None
                if staged is not None or (source.is_file() and is_tar_container(source)):
                    legacy = staged or Image(source, work, tools, 'tar', prepare_input=False)
                    with source.open('rb') as stream:
                        outer = stream.read(6)
                    signature = ((b'\x1f\x8b', 'gzip'), (b'\xfd7zXZ\0', 'xz'), (b'BZh', 'bzip2'))
                    outer_compression = next((name for prefix, name in signature if outer.startswith(prefix)), 'none')
                    record['layers'].append({'format': 'tar', 'members_seen': len(legacy.metadata), 'compression': outer_compression})
                    try:
                        payload = tar_payload(legacy, record['layers'][0])
                    except PreparationError as exc:
                        if not inspect_only:
                            raise
                        record['blocker'] = exc.code
                        payload = None
                    if payload:
                        member = payload[0]
                        record['layers'][0].update(selected_member=member.relative_to(legacy.root).as_posix(),
                                                  selected_bytes=member.stat().st_size, selected_sha256=hash_file(member))
                if payload:
                    archive = _unpack_payload(*payload, work, tools, record, inspect_only)
                    legacy = Image(archive, work, tools, 'extracted', prepare_input=False) if archive else None
                else:
                    if not record['layers']:
                        record['layers'].append({'format': 'directory' if source.is_dir() else file_format(source) or 'unrecognized'})
                    if not inspect_only:
                        legacy = legacy or Image(source, work, tools, 'native', prepare_input=False)
                        scope = 'package-inventory' if legacy.format == 'rpm-collection' else 'runtime-rootfs'
                        _set_coverage(record, scope, True)
            if inspect_only:
                record['status'] = 'INSPECTED'
            else:
                scope = record['coverage']['scope']
                if scope == 'package-inventory':
                    rpm = [legacy.root] if legacy.root.is_file() else [
                        p for p in legacy.root.rglob('*.rpm') if p.is_file() and not p.is_symlink()]
                    if not rpm or looks_like_root(legacy.root) or any(not _is_rpm(p) for p in rpm):
                        raise PreparationError('RPM_REPLACEMENT_INVALID', 'Expected a collection of raw RPM archives')
                if scope == 'runtime-rootfs' and ('extractor' in record or replacement) and not looks_like_root(legacy.root):
                    record['coverage']['complete'] = False
                if scope == 'runtime-rootfs' and not has_regular_file(legacy.root):
                    raise PreparationError('ROOTFS_EMPTY', 'Extracted rootfs has no regular files')
                if scope == 'sdk' and not any((include := legacy.resolve('/' + x)) and include.is_dir()
                                              for x in tools.config['cross_compilation']['include_dirs']):
                    record['coverage']['complete'] = False
                root = output / ROOTS[scope]
                if scope == 'package-inventory' and legacy.root.is_file():
                    if legacy.root.stat().st_size > tools.config['analysis']['max_extract_bytes']:
                        raise PreparationError('TREE_LIMIT','RPM exceeds the preparation byte limit')
                    root.mkdir()
                    shutil.copyfile(legacy.root,root/'input.rpm')
                elif legacy.root.is_relative_to(work):
                    legacy.root.rename(root)
                else:
                    # A pre-extracted input is copied; never move or edit its files.
                    identity(legacy.root, tools.config)  # Reject physical devices before copying.
                    shutil.copytree(legacy.root, root, symlinks=True)
                    if scope != 'package-inventory':
                        legacy.metadata = {name: meta for name, _, meta in legacy.walk()}
                        legacy.format = 'tar'  # A copied tree cannot independently re-establish original security metadata.
                write_json(output / METADATA, legacy.metadata)
                record['coverage']['evidence_scope'] = legacy.evidence_scope()
                if record.get('extractor', {}).get('implementation') == 'fsck.erofs':
                    record['coverage']['evidence_scope']['uid_gid_mode'] = 'NOT_RESTORED'
                record['output'] = {'root': ROOTS[scope], 'identity': identity(root, tools.config),
                                    'metadata_sha256': hash_file(output / METADATA), 'image_format': legacy.format}
                if replacement and identity(replacement[0], tools.config) != record['replacement']['identity']:
                    raise PreparationError('INPUT_CHANGED', 'Replacement changed during preparation')
                record['status'] = 'READY' if record['coverage']['complete'] else 'PARTIAL'
                if record['status'] == 'PARTIAL':
                    record['failure'] = {'code': 'ROOTFS_INCOMPLETE', 'message': 'Runtime coverage is not fully attested by the input or extractor receipt'}
        if _stamp(source) != input_stamp or source.is_dir() and identity(source, tools.config)['sha256'] != record['source']['sha256']:
            raise PreparationError('INPUT_CHANGED', 'Original image changed during preparation')
    except (OSError, ValueError, InfrastructureError, tarfile.TarError) as exc:
        record['status'] = 'FAILED'
        record['coverage']['complete'] = False
        record['failure'] = {'code': getattr(exc, 'code', 'PREPARATION_FAILED'), 'message': str(exc)}
        raise
    finally:
        pending = marker.with_suffix('.tmp')
        write_json(pending, record)
        pending.replace(marker)
    return record


def _is_rpm(path):
    with path.open('rb') as stream:
        return stream.read(4) == b'\xed\xab\xee\xdb'


def prepared_input(path, config, *, sdk=False):
    """Verify a prepared directory, including direct references to its payload root."""
    bundle = path.parent if path.name in ROOTS.values() and (path.parent / MANIFEST).is_file() else path
    marker = bundle / MANIFEST
    if not marker.exists() and not marker.is_symlink():
        return None
    record = _json(marker, 64 * 1024**2)
    coverage = record.get('coverage', {})
    if (record.get('schema') != SCHEMA or record.get('status') != 'READY' or not isinstance(coverage, dict)
            or coverage.get('complete') is not True):
        raise PreparationError('ROOTFS_INCOMPLETE', 'Prepared input is not eligible for compatibility analysis; see its extraction manifest')
    source = record.get('source')
    source_sha = source.get('sha256') if isinstance(source, dict) else None
    if (not isinstance(source_sha, str) or len(source_sha) != 64
            or any(char not in '0123456789abcdef' for char in source_sha)):
        raise PreparationError('PREPARATION_RECORD_INVALID', 'Prepared input has no valid source SHA256')
    scope = coverage.get('scope')
    if scope not in (('sdk',) if sdk else ('runtime-rootfs', 'package-inventory')):
        raise PreparationError('PREPARATION_SCOPE_MISMATCH', 'SDK and runtime inputs are separate; use a Rootstrap only as an SDK sysroot')
    info = record.get('output', {})
    root = bundle / ROOTS[scope]
    if (not isinstance(info, dict) or info.get('root') != root.name or root.is_symlink() or not root.is_dir()
            or info.get('image_format') not in ('directory', 'tar', 'squashfs', 'rpm-collection')
            or identity(root, config) != info.get('identity')):
        raise PreparationError('PREPARED_OUTPUT_MISMATCH', 'Prepared output no longer matches the extraction manifest')
    meta = _json(bundle / METADATA, 256 * 1024**2)
    if hash_file(bundle / METADATA) != info.get('metadata_sha256'):
        raise PreparationError('PREPARED_OUTPUT_MISMATCH', 'Prepared metadata no longer matches the extraction manifest')
    for name, entry in meta.items():
        p = PurePosixPath(name)
        if not p.is_absolute() or str(p) != name or '..' in p.parts or name.startswith('//') or not isinstance(entry, dict) or entry.get('path') != name:
            raise PreparationError('PREPARED_METADATA_INVALID', 'Unsafe virtual path in prepared metadata')
    return root, meta, 'rpm-collection' if scope == 'package-inventory' else info['image_format'], marker
