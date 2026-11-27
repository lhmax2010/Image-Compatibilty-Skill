"""Identify an EROFS superblock and stage extraction with trusted host tools."""
from pathlib import Path
import re
import shutil
import struct
import tempfile

from .core import Tools, canonical, digest, hash_file
from .flash import PreparationError

OFFSET = 1024
COMPAT = {0x01:'SB_CHKSUM', 0x02:'MTIME', 0x04:'XATTR_FILTER'}
INCOMPAT = {
    0x01:'LZ4_0PADDING', 0x02:'COMPR_CFGS/BIG_PCLUSTER', 0x04:'CHUNKED_FILE',
    0x08:'DEVICE_TABLE/COMPR_HEAD2', 0x10:'ZTAILPACKING', 0x20:'FRAGMENTS/DEDUPE',
    0x40:'XATTR_PREFIXES',
}
ALGORITHMS = {0:'lz4',1:'lzma',2:'deflate',3:'zstd'}


def superblock(path):
    with path.open('rb') as stream:
        stream.seek(OFFSET)
        data = stream.read(128)
    if len(data)<96 or data[:4]!=b'\xe2\xe1\xf5\xe0':
        raise PreparationError('EROFS_SUPERBLOCK_INVALID','Missing or incomplete superblock')
    compat = struct.unpack_from('<I',data,8)[0]
    block_bits,slots = data[12:14]
    blocks = struct.unpack_from('<I',data,36)[0]
    incompatible,compression,device_count,device_slot = struct.unpack_from('<IHHH',data,80)
    unknown = incompatible & ~sum(INCOMPAT)
    block_size = 1 << block_bits if 9 <= block_bits <= 16 else 0
    # Unknown newer feature layouts can change geometry; preserve their raw flags
    # for a reviewed vendor adapter and enforce standard geometry only when known.
    if not block_size or not unknown and (not blocks or block_size*blocks > path.stat().st_size):
        raise PreparationError('EROFS_SUPERBLOCK_INVALID','Invalid block geometry or truncated image')
    algorithm_bits = compression if incompatible & 0x02 else None
    return {'format':'erofs','superblock_offset':OFFSET,'block_size':block_size,'blocks_low':blocks,
            'extension_slots':slots,'feature_compat':compat,'feature_incompat':incompatible,
            'known_compat_features':[label for flag,label in COMPAT.items() if flag & compat],
            'unknown_compat_mask':compat & ~sum(COMPAT),
            'known_incompat_features':[label for flag,label in INCOMPAT.items() if flag & incompatible],
            'unknown_incompat_mask':unknown,'extra_devices':device_count,'device_table_offset_slots':device_slot,
            'compression_bitmap':algorithm_bits,
            'compression_algorithms':(['implicit-lz4-if-compressed'] if algorithm_bits is None else
                                      [name for bit,name in ALGORITHMS.items() if algorithm_bits & (1<<bit)]),
            'unknown_compression_mask':0 if algorithm_bits is None else algorithm_bits & ~sum(1<<bit for bit in ALGORITHMS)}


def blocker(info,tools):
    if info['extra_devices']:
        return 'EROFS_EXTRA_DEVICES_REQUIRED'
    if info['unknown_compat_mask'] or info['unknown_incompat_mask'] or info['unknown_compression_mask']:
        return 'EROFS_FEATURE_UNSUPPORTED'
    if not all(tools.path(name) for name in ('fsck.erofs','bwrap','tar')):
        return 'EROFS_EXTRACTOR_UNAVAILABLE'
    return None


def extract(source,work,tools,record,info):
    blocked = blocker(info,tools)
    if blocked:
        raise PreparationError(blocked,'Use a reviewed EROFS adapter or a verified same-build input. See the EROFS layer for feature and device details')
    binary = Path(tools.path('fsck.erofs')).resolve()
    if binary == source or binary.is_relative_to(work.parent):
        raise PreparationError('EROFS_EXTRACTOR_INVALID','Host tool must be outside the image and scratch output')
    version = tools.run([str(binary),'--version'],max_capture_bytes=64*1024)
    help_result = tools.run([str(binary),'--help'],max_capture_bytes=64*1024)
    help_text = help_result['stdout']+help_result['stderr']
    record['extractor'] = {'path':str(binary),'sha256':hash_file(binary),'implementation':'fsck.erofs',
                           'version':(version['stdout'] or version['stderr']).strip()[:4096],
                           'evidence':[version['stdout_evidence'],version['stderr_evidence'],
                                       help_result['stdout_evidence'],help_result['stderr_evidence']]}
    if (version.get('error') or version['returncode'] or not record['extractor']['version'] or
            '--extract' not in help_text or not re.search(r'--(?:no-|\[no-\])preserve(?![-\w])',help_text)):
        raise PreparationError('EROFS_EXTRACTOR_UNAVAILABLE','fsck.erofs must support --extract and --no-preserve')
    archive = work/'erofs-rootfs.tar'
    reserve = 64*1024**2
    limit = min(tools.config['analysis']['max_extract_bytes'],shutil.disk_usage(work).free-reserve)
    if limit <= 0:
        raise PreparationError('EROFS_STORAGE_LIMIT','Insufficient space for staged TAR')
    size = min(tools.config['preparation']['erofs_scratch_mib']*1024**2,limit)
    # Use a fresh root with host tools/libraries and the selected image only.
    # Extraction writes to private tmpfs. The original image is never mounted.
    command = '"$1" --extract="$2" --no-preserve "$3" >&2 && "$4" -cf - -C "$2" .'
    argv = [tools.path('bwrap'),'--unshare-user','--unshare-net','--unshare-pid','--die-with-parent',
            '--ro-bind','/usr','/usr','--ro-bind-try','/bin','/bin','--ro-bind-try','/lib','/lib',
            '--ro-bind-try','/lib64','/lib64','--dev','/dev','--proc','/proc',
            '--ro-bind',str(binary),'/input/fsck.erofs','--ro-bind',str(source),'/input/image',
            '--ro-bind',tools.path('tar'),'/input/tar','--size',str(size),'--tmpfs','/work',
            '--chdir','/work','--','/bin/sh','-c',command,'erofs','/input/fsck.erofs','/work','/input/image','/input/tar']
    env = {'LC_ALL':'C','TZ':'UTC','TMPDIR':'/work','PATH':'/usr/bin:/bin'}
    with archive.open('x+b') as stdout,tempfile.TemporaryFile(dir=work) as stderr:
        code,error,cleanup = Tools.capture_bounded(argv,env,stdout,stderr,tools.config['analysis']['extract_timeout_seconds'],limit,work)
        stderr.seek(0)
        proof = canonical({'argv':argv,'exit_code':code,'reason':error,'cleanup':cleanup,'tar_bytes':stdout.tell()}).encode()+b'\n'+stderr.read(128*1024)
    name = digest(proof)+'.txt'
    (tools.raw/name).write_bytes(proof)
    record['extractor'].update(status='COMPLETE' if not (code or error) else 'FAILED',
                               exit_code=code,stderr_evidence='evidence/'+name)
    if error == 'interrupted':
        raise KeyboardInterrupt
    if error == 'timeout':
        record['extractor'].update(reason_code='TOOL_TIMEOUT', tool='fsck.erofs')
        raise PreparationError('TOOL_TIMEOUT', 'fsck.erofs')
    if code or error:
        raise PreparationError('EROFS_EXTRACTION_FAILED','fsck.erofs or the confined TAR stage failed. See stderr evidence')
    record['layers'].append({'format':'tar','role':'standard-erofs-output','sha256':hash_file(archive)})
    return archive
