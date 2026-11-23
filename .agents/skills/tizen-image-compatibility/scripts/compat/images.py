"""Read-only image access; archive links are resolved in the image namespace."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
from typing import Any, Iterator

from .core import InputError, InfrastructureError, Tools
from .flash import PROBE_BYTES, PreparationError, identify
from .preparation import MANIFEST, _stamp, prepare, prepared_input, tar_payload


class Image:
    def __init__(self, source: Path, workspace: Path, tools: Tools, label: str, *, prepare_input=True, sdk=False):
        self.source = source.resolve()
        self.root = self.source
        self.format = 'directory'
        self.metadata: dict[str, dict[str, Any]] = {}
        self.errors: list[OSError] = []
        self.extraction_manifest: Path | None = None
        if not self.source.exists():
            raise InputError(f'Image not found: {source}')
        if self.source.is_dir():
            if (self.source / 'oci-layout').exists():
                raise InputError('OCI layered layout is not a rootfs. Export/unpack it with an OCI-aware tool first (apply whiteouts), then pass the rootfs directory.')
            prepared = prepared_input(self.source, tools.config, sdk=sdk) if prepare_input else None
            if prepared:
                self.root, self.metadata, self.format, self.extraction_manifest = prepared
        elif not self.source.is_file():
            raise InputError('Image input must be a directory or regular file')
        elif tarfile.is_tarfile(self.source):
            self.format = 'tar'
            self.root = workspace / label
            self.root.mkdir()
            self.archive_stamp = _stamp(self.source)
            self._extract_tar(tools)
            if prepare_input:
                try:
                    flash = tar_payload(self)
                except PreparationError:
                    flash = True  # Let preparation record the ambiguous payload and fail.
                if flash:
                    self._prepare(workspace, tools, label, staged=self)
        else:
            with self.source.open('rb') as stream:
                prefix = stream.read(PROBE_BYTES)
            if prefix.startswith(b'hsqs'):
                self.format = 'squashfs'
                binary = tools.path('unsquashfs')
                if not binary:
                    raise InputError('SquashFS requires unsquashfs. Extract to a separate rootfs directory and retry.')
                self.root = workspace / label
                result = tools.run([binary, '-no-progress', '-no-xattrs', '-d', str(self.root), str(self.source)])
                if result['returncode']:
                    raise InfrastructureError(f'SquashFS extraction failed: {result["stderr"]}')
            elif prepare_input and identify(prefix) in ('gpt', 'xz', 'vdfs'):
                self._prepare(workspace, tools, label)
            elif prefix.startswith(b'\xed\xab\xee\xdb'):
                self.format = 'rpm-collection'
                self.root = workspace / label
                self.root.mkdir()
                name = self.source.name if self.source.suffix == '.rpm' else self.source.name + '.rpm'
                shutil.copyfile(self.source, self.root / name)
            else:
                raise InputError(f'Unsupported image format: {source}. For EXT4 use an isolated guest or read-only userspace extractor; for OCI export a merged rootfs. Supply the extracted directory or a rootfs TAR. No privileged mount is performed.')
        if self.root.is_dir() and any(self.root.glob('*.rpm')) and not (self.root / 'etc').exists():
            self.format = 'rpm-collection'
        tools.aliases[str(self.root)] = f'<{label}-rootfs>'

    def evidence_scope(self, declared=None):
        """Describe which source facts the current representation can retain."""
        fields = dict(paths='OBSERVABLE', file_contents='OBSERVABLE', uid_gid_mode='OBSERVABLE',
                      xattrs='OBSERVABLE', acl='OBSERVABLE', smack='OBSERVABLE',
                      file_capabilities='OBSERVABLE', hardlinks='OBSERVABLE',
                      ramdisk='UNKNOWN', special_files='OBSERVABLE')
        if self.format in ('tar', 'squashfs'):
            for key in ('xattrs', 'acl', 'smack', 'file_capabilities', 'hardlinks'):
                fields[key] = 'UNKNOWN'
            fields['uid_gid_mode'] = 'ARCHIVE_METADATA' if self.format == 'tar' else 'UNKNOWN'
            fields['special_files'] = 'ARCHIVE_METADATA' if self.format == 'tar' else 'UNKNOWN'
        if self.format == 'rpm-collection':
            fields = dict.fromkeys(fields, 'NOT_APPLICABLE')
        for key, value in (declared or {}).items():
            fields[key] = 'INCLUDED_DECLARED' if value else 'NOT_RESTORED'
        return fields

    def _prepare(self, workspace, tools, label, *, staged=None):
        bundle = workspace / (label + '-prepared')
        bundle.mkdir()
        report_marker = tools.output / (label + '-extraction-manifest.json')
        try:
            prepare(self.source, bundle, tools, staged=staged)
            self.root, self.metadata, self.format, _ = prepared_input(bundle, tools.config)
        finally:
            marker = bundle / MANIFEST
            if marker.is_file():
                shutil.copyfile(marker, report_marker)
                self.extraction_manifest = report_marker

    def _extract_tar(self, tools: Tools) -> None:
        total = count = 0
        links: list[tuple[Path, str, bool]] = []
        # Build only regular files/directories first. No archive-controlled parent symlinks.
        with tarfile.open(self.source, 'r|*') as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts:
                    raise InputError(f'Unsafe TAR path: {member.name}')
                if str(name) == '.':
                    continue
                count += 1
                total += max(member.size, 0)
                if count > tools.config['analysis']['max_extract_files'] or total > tools.config['analysis']['max_extract_bytes']:
                    raise InputError('Archive exceeds configured extraction limit')
                path = self.root.joinpath(*name.parts)
                if path.exists():
                    if not (member.isdir() and path.is_dir()):
                        raise InputError(f'Duplicate archive entry: {name}')
                kind = ('directory' if member.isdir() else 'file' if member.isfile() else
                        'symlink' if member.issym() else 'file' if member.islnk() else
                        'char' if member.ischr() else 'block' if member.isblk() else 'fifo')
                self.metadata['/' + str(name)] = dict(path='/' + str(name), type=kind,
                    mode=oct(member.mode), uid=member.uid, gid=member.gid,
                    target=member.linkname if member.issym() else None,
                    device=[member.devmajor, member.devminor] if member.isdev() else None)
                path.parent.mkdir(parents=True, exist_ok=True)
                if member.isdir():
                    path.mkdir(exist_ok=True)
                elif member.isfile():
                    source = archive.extractfile(member)
                    if source is None:
                        raise InputError(f'Unreadable archive entry: {name}')
                    with source, path.open('xb') as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                elif member.issym() or member.islnk():
                    links.append((path, member.linkname, member.islnk()))
                # Device nodes/FIFOs are recorded, never materialized/opened.
        for path, target, hard in links:
            if path.exists() or path.is_symlink():
                raise InputError(f'Archive link collides with entry: {path.name}')
            if hard:
                resolved = self.resolve('/' + target)
                if not resolved or not resolved.is_file():
                    raise InputError(f'Unsupported or unsafe TAR hardlink: {target}')
                shutil.copyfile(resolved, path)
            else:
                # Absolute links are left intact; resolve() never follows host roots.
                path.symlink_to(target)

    def resolve(self, virtual: str) -> Path | None:
        parts = list(PurePosixPath('/' + virtual.lstrip('/')).parts[1:])
        done: list[str] = []
        links = 0
        while parts:
            part = parts.pop(0)
            if part in ('', '.'):
                continue
            if part == '..':
                if not done:
                    return None
                done.pop()
                continue
            candidate = self.root.joinpath(*done, part)
            if candidate.is_symlink():
                links += 1
                if links > 40:
                    return None
                target = os.readlink(candidate)
                if target.startswith('/'):
                    done = []
                parts = list(PurePosixPath(target).parts) + parts
                if parts and parts[0] == '/':
                    parts.pop(0)
            else:
                done.append(part)
        path = self.root.joinpath(*done)
        return path if path.exists() else None

    def walk(self) -> Iterator[tuple[str, Path, dict[str, Any]]]:
        seen = set()
        for directory, dirs, files in os.walk(self.root, followlinks=False, onerror=self.errors.append):
            dirs[:] = sorted(d for d in dirs if not (Path(directory) == self.root and d in ('proc', 'sys', 'run')))
            for name in sorted(dirs + files):
                path = Path(directory) / name
                virtual = '/' + path.relative_to(self.root).as_posix()
                info = path.lstat()
                kind = ('symlink' if stat.S_ISLNK(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode)
                        else 'file' if stat.S_ISREG(info.st_mode) else 'socket' if stat.S_ISSOCK(info.st_mode)
                        else 'char' if stat.S_ISCHR(info.st_mode) else 'block' if stat.S_ISBLK(info.st_mode) else 'fifo')
                metadata = self.metadata.get(virtual, dict(path=virtual, type=kind, mode=oct(stat.S_IMODE(info.st_mode)),
                    uid=info.st_uid, gid=info.st_gid, target=os.readlink(path) if kind == 'symlink' else None,
                    device=[os.major(info.st_rdev), os.minor(info.st_rdev)] if kind in ('char', 'block') else None))
                seen.add(virtual)
                yield virtual, path, metadata
        for virtual in sorted(set(self.metadata) - seen):
            yield virtual, self.root / virtual.lstrip('/'), self.metadata[virtual]
