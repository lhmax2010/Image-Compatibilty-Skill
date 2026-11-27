"""Bounded, read-only RPM archive inspection and newc payload collection."""
import io
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
from xml.etree import ElementTree

from .core import Tools, canonical, digest, hash_file, limitation
from .elf import collect_elf, dynamic_exports
from .packages import parse_rpm_evidence
from .packed_rows import pack_symbol_inventory
from .report_io import evidence_path

FIELDS = ('name', 'epoch', 'version', 'release', 'arch')
CHUNK = 1024 * 1024
RESERVE = 64 * CHUNK


def inventory_paths(root, limit):
    if root.is_file():
        return [root]
    paths = []
    def fail(error):
        raise error
    for directory, folders, names in os.walk(root, followlinks=False, onerror=fail):
        folders.sort()
        for name in sorted(names):
            path = Path(directory)/name
            if path.suffix.lower() == '.rpm' and path.is_file() and not path.is_symlink():
                paths.append(path)
                if len(paths) > limit:
                    raise ValueError(f'RPM collection exceeds {limit} archives')
    return paths


def virtual_path(name):
    if name.startswith('./'):
        name = name[2:]
    if name in ('', '.'):
        return '/'
    if any(part in ('', '.', '..') for part in name.split('/')) or '\\' in name or any(ord(c) < 32 for c in name):
        raise ValueError('Unsafe CPIO pathname: '+repr(name))
    return '/'+name


def link_target(path, target):
    if not target or '\\' in target or any(ord(c) < 32 for c in target):
        raise ValueError('Unsafe CPIO symbolic link at '+path)
    # Absolute link names are virtual package paths. No filesystem link is created.
    parts = [] if target.startswith('/') else list(PurePosixPath(path).parent.parts[1:])
    for part in target.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if not parts:
                raise ValueError('CPIO symlink escapes package namespace at '+path)
            parts.pop()
        else:
            parts.append(part)
    return '/'+'/'.join(parts)


def exact(stream, size):
    data = stream.read(size)
    if len(data) != size:
        raise ValueError('Truncated CPIO record')
    return data


def file_content(stream, length, elf_path, tools, mode, path, scan_elf):
    checksum = hashlib.sha256()
    crc = 0
    prefix = exact(stream, min(length,4))
    checksum.update(prefix)
    crc += sum(prefix)
    remaining = length-len(prefix)
    is_elf = prefix == b'\x7fELF'
    result = None
    if is_elf and scan_elf:
        if length > tools.config['rpm_payload']['max_elf_bytes']:
            raise ValueError('ELF exceeds the per-file collection limit at '+path)
        if shutil.disk_usage(elf_path.parent).free < length+RESERVE:
            raise ValueError('Insufficient scratch space to collect ELF')
        target = elf_path.open('xb')
    else:
        target = None
    try:
        if target:
            target.write(prefix)
        while remaining:
            block = exact(stream,min(CHUNK,remaining))
            checksum.update(block)
            crc += sum(block)
            if target:
                target.write(block)
            remaining -= len(block)
        if target:
            target.close()
            result = collect_elf(elf_path,path,tools,mode,bounded=True)
            pack_symbol_inventory(result)
    finally:
        if target:
            target.close()
            elf_path.unlink()
    return checksum.hexdigest(), crc & 0xffffffff, result, is_elf


def scan_cpio(stream, scratch, tools, mode, scan_elf, deadline):
    entries, objects, groups = {}, {}, {}
    limit = tools.config['rpm_payload']['max_files']
    count = elf_magic = 0
    while True:
        if time.monotonic() > deadline:
            raise ValueError('RPM inspection time limit exceeded')
        head = exact(stream,110)
        if head[:6] not in (b'070701',b'070702') or any(c not in b'0123456789abcdefABCDEF' for c in head[6:]):
            raise ValueError('Unsupported or malformed CPIO header')
        ino, mode_bits, uid, gid, links, _, size, major, minor, _, _, namesize, crc = (
            int(head[i:i+8],16) for i in range(6,110,8))
        if not 1 < namesize <= 4096:
            raise ValueError('Invalid CPIO path length')
        raw_name = exact(stream,namesize)
        if raw_name[-1:] != b'\0' or b'\0' in raw_name[:-1]:
            raise ValueError('Invalid CPIO pathname termination')
        name = raw_name[:-1].decode('utf-8','strict')
        exact(stream,(-stream.tell()) % 4)
        if name == 'TRAILER!!!':
            if size or any(any(block) for block in iter(lambda:stream.read(CHUNK),b'')):
                raise ValueError('Invalid CPIO trailer')
            break
        count += 1
        if count > limit:
            raise ValueError('RPM payload exceeds the file-count limit')
        path = virtual_path(name)
        if path in entries:
            raise ValueError('Duplicate CPIO pathname: '+path)
        kind = stat.S_IFMT(mode_bits)
        entry = {'path':path,'size':size,'mode':oct(stat.S_IMODE(mode_bits)),'uid':uid,'gid':gid}
        actual = 0
        if kind == stat.S_IFREG and path != '/':
            entry['type'] = 'file'
            sha, actual, elf, magic = file_content(stream,size,scratch/'elf',tools,mode,path,scan_elf)
            entry['sha256'] = sha
            if links > 1:
                groups.setdefault((major,minor,ino),[]).append((entry,links,elf,magic))
            else:
                elf_magic += magic
                if elf:
                    objects[path] = elf
        elif kind == stat.S_IFLNK and path != '/' and size <= 4096:
            raw = exact(stream,size)
            actual = sum(raw)
            target = raw.decode('utf-8','strict')
            entry.update(type='symlink',target=target,virtual_target=link_target(path,target),sha256=digest(raw))
        elif size == 0 and kind in (stat.S_IFDIR,stat.S_IFCHR,stat.S_IFBLK,stat.S_IFIFO,stat.S_IFSOCK):
            entry['type'] = 'directory' if kind == stat.S_IFDIR else 'special-metadata-only'
            if path == '/' and kind != stat.S_IFDIR:
                raise ValueError('Special root CPIO entry')
        else:
            raise ValueError('Unsafe or unsupported CPIO entry: '+path)
        if head[:6] == b'070702' and actual != crc:
            raise ValueError('CPIO checksum mismatch at '+path)
        exact(stream,(-stream.tell()) % 4)
        entries[path] = entry
    for path in entries:
        for parent in PurePosixPath(path).parents:
            row = entries.get(str(parent))
            if row and row['type'] != 'directory':
                raise ValueError('CPIO entries beneath a non-directory: '+path)
    for group in groups.values():
        populated = [item for item in group if item[0]['size']]
        if len(populated) > 1 or any(link_count != len(group) for _,link_count,_,_ in group):
            raise ValueError('Incomplete or ambiguous CPIO hardlink group')
        origin, _, elf, magic = (populated or group)[0]
        for row, _, _, _ in group:
            row.update(sha256=origin['sha256'],size=origin['size'],hardlink=origin['path'])
            elf_magic += magic
            if elf:
                objects[row['path']] = elf | {'path':row['path']}
    return sorted(entries.values(),key=lambda x:x['path']), [objects[k] for k in sorted(objects)], elf_magic


def extraction(rpm, record, tools, workspace, mode, scan_elf):
    program = tools.path('rpm2cpio')
    if not program:
        raise ValueError('rpm2cpio unavailable; use metadata mode or configure a trusted host rpm2cpio')
    spec = tools.config['rpm_payload']
    limit = min(spec['max_bytes'],tools.config['analysis']['max_extract_bytes'],shutil.disk_usage(workspace).free-RESERVE)
    if limit < 110:
        raise ValueError('Insufficient scratch storage for RPM payload')
    with tempfile.TemporaryDirectory(prefix='rpm-payload-',dir=workspace) as tmp:
        scratch = Path(tmp)
        output = scratch/'payload.cpio'
        argv = [program,str(rpm)]
        env = {key:val for key,val in os.environ.items() if key not in ('LD_PRELOAD','LD_LIBRARY_PATH','BASH_ENV','ENV')}
        env.update(LC_ALL='C',TZ='UTC',TMPDIR=str(scratch))
        # Retain an explicitly different legacy ceiling for existing configurations.
        legacy = spec['timeout_seconds']
        timeout = tools.config['analysis']['extract_timeout_seconds']
        if legacy != 3600:
            timeout = min(legacy, timeout)
        deadline = time.monotonic() + timeout
        with output.open('x+b') as stdout, tempfile.TemporaryFile(dir=scratch) as stderr:
            code,error,cleanup = Tools.capture_bounded(argv,env,stdout,stderr,timeout,limit,scratch)
            size = stdout.tell()
            stderr.seek(0)
            diagnostic = stderr.read(64*1024)
            proof = canonical({'argv':argv,'rpm_sha256':record['sha256'],'exit_code':code,
                               'reason':error,'cpio_bytes':size,'cleanup':cleanup}).encode()+b'\n'+diagnostic
            record['evidence'].append(tools.store_evidence(io.BytesIO(proof), digest(proof)))
            if error == 'interrupted':
                raise KeyboardInterrupt
            if error == 'timeout':
                record.update(reason_code='TOOL_TIMEOUT', tool=Path(program).name)
            if code or error:
                raise ValueError('rpm2cpio failed: '+(error or diagnostic.decode('utf-8','replace').strip()[:400] or str(code)))
            stdout.seek(0)
            return scan_cpio(stdout,scratch,tools,mode,scan_elf,deadline)


def stamp(path):
    st = path.stat()
    return st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns


def collect_repository(image, manifest, tools, workspace, mode, collectors):
    spec = tools.config['rpm_payload']
    payload = spec['mode'] == 'payload'
    scope = 'RPM_REPOSITORY_PAYLOAD' if payload else 'RPM_REPOSITORY_METADATA'
    manifest['image']['scope'] = scope
    manifest['limitations'] = [limitation('linking','Repository payloads establish object contracts and DT_NEEDED observations; the installed provider set, loader scope and runtime behavior are unverified.')]
    manifest['packages'] = []
    rows, errors = [], []
    scan_elf = 'readelf' in collectors
    try:
        paths = inventory_paths(image.root,spec['max_packages'])
    except (OSError,ValueError) as exc:
        paths = []
        errors.append({'archive':'*','stage':'inventory','reason':str(exc),'evidence':[]})
    rpm_tool = tools.path('rpm')
    for path in paths:
        relative = path.name if image.root.is_file() else path.relative_to(image.root).as_posix()
        row = {'archive':relative,'metadata_status':'UNKNOWN','extraction_status':'NOT_EXECUTED',
               'evidence':[],'payload_files':[],'elf_count':0,'objects':[]}
        rows.append(row)
        try:
            original = stamp(path)
            if original[2] > spec['max_bytes']:
                raise ValueError('RPM archive exceeds the per-package byte limit')
            if shutil.disk_usage(workspace).free < RESERVE+32*CHUNK:
                raise ValueError('Insufficient report and scratch storage')
            row['sha256'] = hash_file(path)
            row['archive_bytes'] = original[2]
            row['id'] = 'RPM-'+digest(canonical([relative,row['sha256']]).encode())[:24]
            if not rpm_tool:
                raise ValueError('rpm metadata tool unavailable')
            result = tools.run([rpm_tool,'-qp','--xml',str(path)],max_capture_bytes=tools.config['rpm_payload']['max_metadata_bytes'])
            row['evidence'] = [result['stdout_evidence'],result['stderr_evidence']]
            if result.get('reason_code'):
                row.update(reason_code=result['reason_code'], tool=result['tool'])
            if result['returncode'] or result['error']:
                raise ValueError('RPM metadata query failed: '+(result['error'] or result['stderr'].strip()[:400]))
            packages = parse_rpm_evidence(evidence_path(tools.output,result['stdout_evidence']))
            if len(packages) != 1 or not all(packages[0].get(k) for k in FIELDS):
                raise ValueError('Expected one complete RPM NEVRA')
            row['package'] = packages[0]
            row['metadata_status'] = 'COMPLETE'
            if payload:
                row['payload_files'],objects,row['elf_count'] = extraction(path,row,tools,workspace,mode,scan_elf)
                row['extraction_status'] = 'COMPLETE'
                checksums = {f['path']:f.get('sha256') for f in row['payload_files']}
                for obj in objects:
                    obj['package_path'] = obj['path']
                    obj['path'] = '/@rpm/'+row['id']+obj['path']
                    obj['rpm_archive_id'] = row['id']
                    obj['sha256'] = checksums[obj['package_path']]
                    row['objects'].append(obj['path'])
                if stamp(path) != original:
                    raise ValueError('RPM source changed during collection')
                manifest['elf_objects'].extend(objects)
                errors.extend({'archive':relative,'stage':'elf','reason':obj.get('error','Incomplete ELF collection'),
                               'path':obj['package_path'],'evidence':obj.get('evidence',[])} for obj in objects
                              if not obj.get('complete'))
            elif stamp(path) != original:
                raise ValueError('RPM source changed during metadata collection')
        except (OSError,ValueError,ElementTree.ParseError,KeyError,IndexError) as exc:
            stage = 'payload' if row['metadata_status'] == 'COMPLETE' and payload else 'metadata'
            row['extraction_status'] = 'FAILED' if stage == 'payload' else 'NOT_EXECUTED'
            if 'source changed' in str(exc):
                row.update(metadata_status='UNKNOWN',payload_files=[],objects=[],elf_count=0)
            error = {'archive':relative,'stage':stage,'reason':str(exc),'evidence':row['evidence']}
            if row.get('reason_code'):
                error.update(reason_code=row['reason_code'], tool=row['tool'])
            errors.append(error)
    meta_ok = sum(r['metadata_status']=='COMPLETE' for r in rows)
    extracted = sum(r['extraction_status']=='COMPLETE' for r in rows)
    objects = manifest['elf_objects']
    elf_ready = sum(bool(x.get('complete')) for x in objects)
    complete_exports = sum(bool(x.get('export_inventory_complete')) for x in objects)
    applicable_exports = sum(o.get('export_inventory_status')!='NOT_APPLICABLE' for o in objects)
    meta_complete = bool(rows) and meta_ok == len(rows) and not any(e['stage']=='inventory' for e in errors)
    manifest['package_inventory'] = {'status':'NOT_APPLICABLE','installed_count':None,'archive_count':len(rows),
                                   'archive_status':'COMPLETE' if meta_complete else 'PARTIAL','source_kind':'rpm_repository'}
    manifest['available_packages'] = [r['package'] | {'provenance':{'kind':'rpm_archive','archive':r['archive'],
                                      'sha256':r['sha256']},'evidence':r['evidence']} for r in rows if r['metadata_status']=='COMPLETE']
    manifest['repository'] = {'scope':scope,'archives':rows,'errors':errors,'inventory_complete':meta_complete,
        'counts':{'rpm_total':len(rows),'metadata_complete':meta_ok,'extracted':extracted,
                  'extraction_failed':sum(r['extraction_status']=='FAILED' for r in rows),
                  'payload_unscanned':len(rows)-extracted,'elf_observed':sum(r['elf_count'] for r in rows),
                  'elf_collected':len(objects),'elf_complete':elf_ready,'export_inventories_complete':complete_exports,
                  'exports':sum(len(list(dynamic_exports(o))) for o in objects),
                  'imports':sum(len(o.get('imports',[])) for o in objects),
                  'payload_coverage_percent':round(100*extracted/len(rows),2) if rows and payload else None,
                  'export_coverage_percent':round(100*complete_exports/applicable_exports,2) if applicable_exports else None,
                  'export_analysis_status':'NOT_EXECUTED' if not complete_exports else
                    'COMPLETE' if extracted==len(rows) and complete_exports==applicable_exports
                    and len(objects)==sum(r['elf_count'] for r in rows) else 'PARTIAL'}}
    manifest['image']['architecture'] = sorted({o['machine'] for o in objects if o.get('machine')})
    observed = bool(rows or errors)
    manifest.update(collection_complete=False,filesystem_path_inventory_complete=False,header_inventory_complete=False,
        collector_execution={
            'rpm':{'status':'NOT_EXECUTED' if not observed else
                            'COMPLETE' if meta_complete else 'PARTIAL' if meta_ok else 'FAILED',
                   'applicable':observed,'attempted':len(rows),
                   'successful':meta_ok,'errors':[e for e in errors if e['stage'] in ('metadata','inventory')]},
            'rpm2cpio':{'status':'NOT_EXECUTED' if not payload or not observed else
                        'COMPLETE' if meta_complete and extracted == len(rows) else 'PARTIAL' if extracted else 'FAILED',
                        'applicable':payload and observed,'attempted':meta_ok if payload else 0,'successful':extracted,
                        'errors':[e for e in errors if e['stage']=='payload']},
            'readelf':{'status':('COMPLETE' if elf_ready==len(objects) else 'PARTIAL' if elf_ready else 'FAILED')
                        if objects else 'NOT_EXECUTED',
                       'applicable':bool(objects),'attempted':len(objects),'successful':elf_ready,
                       'errors':[{'path':o['path'],'reason':o.get('error'),'evidence':o.get('evidence',[])}
                                 for o in objects if not o.get('complete')]}})
    return manifest
