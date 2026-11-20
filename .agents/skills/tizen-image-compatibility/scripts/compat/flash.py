"""Bounded read-only identification and extraction of flash containers."""
from __future__ import annotations

import hashlib
import lzma
import struct
import uuid
import zlib

from .core import InputError


class PreparationError(InputError):
    def __init__(self, code: str, message: str):
        super().__init__(f'{code}: {message}')
        self.code = code


CHUNK = 1024 * 1024
XZ = b'\xfd7zXZ\0'
GPT = b'EFI PART'
SECTORS = (512, 4096)
PROBE_BYTES = max(SECTORS) + len(GPT)


def vdfs_signature(prefix):
    # The on-disk superblock used by Samsung-derived unpack.vdfs is at 0x400.
    layout = prefix[0x404:0x408]
    if prefix[0x400:0x404] == b'VDFS' and len(layout) == 4 and layout.isdigit():
        return {'format': 'vdfs', 'signature_offset': 0x400, 'magic': 'VDFS', 'layout_version': layout.decode('ascii')}
    return None


def identify(prefix):
    if any(prefix[n:n + len(GPT)] == GPT for n in SECTORS):
        return 'gpt'
    if prefix.startswith(XZ):
        return 'xz'
    if vdfs_signature(prefix):
        return 'vdfs'
    if (len(prefix) >= 1104 and prefix[1080:1082] == b'\x53\xef'
            and struct.unpack_from('<I', prefix, 1024)[0] > 0
            and struct.unpack_from('<I', prefix, 1048)[0] <= 6
            and struct.unpack_from('<I', prefix, 1056)[0] > 0
            and struct.unpack_from('<I', prefix, 1100)[0] <= 1):
        return 'ext'
    if prefix[1024:1028] == b'\xe2\xe1\xf5\xe0':
        return 'erofs'
    if prefix.startswith(b'hsqs'):
        return 'squashfs'
    return None


def _gpt_header(stream, sector, lba, sectors):
    stream.seek(sector * lba)
    block = stream.read(sector)
    if len(block) != sector or block[:8] != GPT:
        raise PreparationError('GPT_INVALID', 'Missing or truncated GPT header')
    revision, size, crc, zero = struct.unpack_from('<IIII', block, 8)
    if revision != 0x10000 or zero or not 92 <= size <= sector:
        raise PreparationError('GPT_INVALID', 'Invalid revision, reserved field, or header size')
    if zlib.crc32(block[:16] + bytes(4) + block[20:size]) != crc:
        raise PreparationError('GPT_INVALID', 'Header CRC32 mismatch')
    here, peer, first, last = struct.unpack_from('<QQQQ', block, 24)
    entries, count, width, entries_crc = struct.unpack_from('<QIII', block, 72)
    length = count * width
    table_end = entries + (length + sector - 1) // sector
    if (here != lba or peer != (sectors - 1 if lba == 1 else 1)
            or not 2 <= first <= last < sectors - 1 or not count or not 128 <= width <= 4096
            or width & (width - 1) or length > 4 * CHUNK):
        raise PreparationError('GPT_INVALID', 'Invalid GPT geometry or entry size')
    if not (2 <= entries < table_end <= first if lba == 1 else last < entries < table_end <= lba):
        raise PreparationError('GPT_INVALID', 'Entry table overlaps usable LBAs or metadata')
    stream.seek(sector * entries)
    array = stream.read(length)
    if len(array) != length or zlib.crc32(array) != entries_crc:
        raise PreparationError('GPT_INVALID', 'Partition entry array CRC32 mismatch')
    return first, last, block[56:72], width, array


def gpt_partitions(path):
    size = path.stat().st_size
    with path.open('rb') as stream:
        prefix = stream.read(PROBE_BYTES)
        sizes = [n for n in SECTORS if prefix[n:n + len(GPT)] == GPT]
        if len(sizes) != 1 or size % sizes[0] or size < sizes[0] * 4:
            raise PreparationError('GPT_INVALID', 'Ambiguous sector size or non-aligned/truncated disk')
        sector = sizes[0]
        sectors = size // sector
        primary = _gpt_header(stream, sector, 1, sectors)
        backup = _gpt_header(stream, sector, sectors - 1, sectors)
        if primary != backup:
            raise PreparationError('GPT_INVALID', 'Primary and backup GPT disagree')
        first, last, disk_id, width, array = primary
        if not any(disk_id):
            raise PreparationError('GPT_INVALID', 'Missing disk GUID')
        partitions, identifiers = [], set()
        for pos in range(0, len(array), width):
            entry = array[pos:pos + width]
            if not any(entry[:16]):
                continue
            identifier = uuid.UUID(bytes_le=entry[16:32])
            begin, end = struct.unpack_from('<QQ', entry, 32)
            if not first <= begin <= end <= last or not identifier.int or identifier in identifiers:
                raise PreparationError('GPT_INVALID', 'Out-of-range partition or missing/duplicate partition GUID')
            identifiers.add(identifier)
            offset, length = begin * sector, (end - begin + 1) * sector
            partitions.append({'index': pos // width + 1, 'name': entry[56:128].decode('utf-16-le', 'replace').split('\0')[0],
                               'type_guid': str(uuid.UUID(bytes_le=entry[:16])), 'guid': str(identifier),
                               'start_lba': begin, 'end_lba': end, 'offset': offset, 'length': length})
        ordered = sorted(partitions, key=lambda p: p['start_lba'])
        if any(a['end_lba'] >= b['start_lba'] for a, b in zip(ordered, ordered[1:])):
            raise PreparationError('GPT_INVALID', 'Partition ranges overlap')
        for part in partitions:
            stream.seek(part['offset'])
            part['payload_format'] = identify(stream.read(min(PROBE_BYTES, part['length']))) or 'unknown'
    return {'format': 'gpt', 'sector_size': sector, 'disk_guid': str(uuid.UUID(bytes_le=disk_id)),
            'primary_crc_verified': True, 'backup_crc_verified': True,
            'protective_mbr_observed': prefix[510:512] == b'\x55\xaa' and any(prefix[n] == 0xEE for n in (450, 466, 482, 498)),
            'partitions': partitions}


def copy_partition(path, destination, part, limit):
    offset, length = part['offset'], part['length']
    if length > limit or offset < 0 or length < 1 or offset + length > path.stat().st_size:
        raise PreparationError('PARTITION_LIMIT', 'Partition range exceeds the file or extraction limit')
    digest = hashlib.sha256()
    with path.open('rb') as source, destination.open('xb') as output:
        source.seek(offset)
        remaining = length
        while remaining:
            data = source.read(min(remaining, CHUNK))
            if not data:
                raise PreparationError('GPT_INVALID', 'Partition ended before its declared length')
            output.write(data)
            digest.update(data)
            remaining -= len(data)
    return digest.hexdigest()


def decompress_xz(path, output, limit, memlimit):
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=memlimit)
    decoded, padding = 0, 0
    source_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    try:
        with path.open('rb') as source, output.open('xb') as target:
            for data in iter(lambda: source.read(CHUNK), b''):
                source_hash.update(data)
                if not decoder.eof:
                    while True:
                        block = decoder.decompress(data, max_length=min(CHUNK, limit - decoded + 1))
                        decoded += len(block)
                        if decoded > limit:
                            raise PreparationError('XZ_LIMIT', 'Uncompressed XZ size exceeds the extraction limit')
                        target.write(block)
                        output_hash.update(block)
                        if decoder.eof:
                            data = decoder.unused_data
                            break
                        if decoder.needs_input:
                            data = b''
                            break
                        data = b''
                if data.strip(b'\0'):
                    raise PreparationError('XZ_INVALID', 'Nonzero trailing data or concatenated XZ streams')
                padding += len(data)
    except lzma.LZMAError as exc:
        raise PreparationError('XZ_INVALID', f'XZ integrity or decoder memory check failed: {exc}') from exc
    if not decoder.eof or padding % 4:
        raise PreparationError('XZ_INVALID', 'Truncated XZ stream or invalid stream padding')
    return {'format': 'xz', 'compressed_bytes': path.stat().st_size - padding, 'padding_bytes': padding,
            'decoded_bytes': decoded, 'check_id': decoder.check, 'source_sha256': source_hash.hexdigest(),
            'decoded_sha256': output_hash.hexdigest()}
