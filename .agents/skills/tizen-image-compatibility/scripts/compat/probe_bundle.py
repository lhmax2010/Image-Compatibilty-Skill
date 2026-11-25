"""Validate externally pinned, flat runtime probe bundles without following links."""
import json
from pathlib import Path
import re
import struct

from .core import InputError, canonical, digest, hash_file

SCHEMA = 'tizen-compat-probe-bundle/v1'
PIN = re.compile('[a-f0-9]{64}')
LEAF = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.+-]{0,63}')
SYSTEM_LIBRARIES = {'ld-linux.so.3', 'libc.so.6', 'libstdc++.so.6', 'libgcc_s.so.1', 'libm.so.6',
                    'libpthread.so.0', 'libdl.so.2', 'librt.so.1', 'libatomic.so.1',
                    'libc++.so.1', 'libc++abi.so.1', 'libunwind.so.8'}


def check(condition, message):
    if not condition:
        raise InputError(message)


def target_pin(spec):
    return digest(canonical({k: spec[k] for k in (
        'scope', 'sdb_serial', 'image_family', 'build_id', 'cpu_serial_sha256', 'provider_sha256')}).encode())


def interpreter(file, header):
    offset = int.from_bytes(header[28:32], 'little')
    width, count = struct.unpack_from('<HH', header, 42)
    check(width == 32 and 0 < count <= 256 and offset+32*count <= file.stat().st_size,
          'Malformed ELF program headers')
    with file.open('rb') as stream:
        stream.seek(offset)
        headers = list(struct.iter_unpack('<8I', stream.read(32*count)))
        entries = [entry for entry in headers if entry[0] == 3]
        check(len(entries) <= 1, 'Multiple ELF interpreters')
        if not entries:
            return None
        entry = entries[0]
        check(0 < entry[4] <= 128 and entry[1]+entry[4] <= file.stat().st_size, 'Malformed ELF interpreter')
        stream.seek(entry[1])
        return stream.read(entry[4])


def load(path, pin, root):
    check(isinstance(pin, str) and PIN.fullmatch(pin) and path.stat().st_size <= 1024**2,
          'A separate SHA256 pin and a bounded manifest are required')
    raw = path.read_bytes()
    check(digest(raw) == pin, 'Probe manifest SHA256 mismatch')
    manifest = json.loads(raw)
    check(manifest['schema'] == SCHEMA, 'Unsupported probe manifest')
    check(root.is_dir() and root.resolve() == root, 'Bundle must be a real directory')
    registered = set()
    artifacts = {}
    for case in manifest['probes']:
        name = case['artifact_id']
        check(LEAF.fullmatch(name) and name not in artifacts, 'Unsafe or repeated artifact ID')
        directory = root / name
        entries = case['files']
        check(1 <= len(entries) <= 8 and 'probe' in entries and directory.is_dir()
              and not directory.is_symlink(), 'Expected a real flat bundle containing probe')
        check({p.name for p in directory.iterdir()} == set(entries), 'Unregistered or missing bundle file')
        for leaf, checksum in entries.items():
            file = directory / leaf
            check((leaf == 'probe' or LEAF.fullmatch(leaf) and leaf not in SYSTEM_LIBRARIES
                   and re.search(r'\.so(?:\.[a-zA-Z0-9]+)*$', leaf))
                  and PIN.fullmatch(checksum) and file.is_file() and not file.is_symlink()
                  and file.stat().st_size <= 4*1024**2 and hash_file(file) == checksum,
                  'Invalid bundle file or SHA256 mismatch')
            with file.open('rb') as stream:
                header = stream.read(52)
            check(len(header) == 52 and header[:7] == b'\x7fELF\x01\x01\x01'
                  and int.from_bytes(header[18:20], 'little') == 40
                  and int.from_bytes(header[36:40], 'little') >> 24 == 5
                  and int.from_bytes(header[36:40], 'little') & 0x400 == 0
                  and int.from_bytes(header[16:18], 'little') in ((2, 3) if leaf == 'probe' else (3,)),
                  'Expected ELF32 little-endian ARM EABI5 without hard-float flag')
            check(interpreter(file, header) == (b'/lib/ld-linux.so.3\0' if leaf == 'probe' else None),
                  'Actual ELF interpreter does not match the pinned bundle contract')
        expect = case['runtime_expectation']
        check(expect.get('outcome', 'exit') in ('exit', 'loader-error', 'timeout')
              and type(expect['exit_code']) is int and 0 <= expect['exit_code'] <= 255
              and all(isinstance(expect[k], str) for k in ('stdout','stderr'))
              and (expect.get('outcome') != 'loader-error' or
                   isinstance(expect.get('stderr_contains'), str) and bool(expect['stderr_contains']) and expect['exit_code'] != 0),
              'Invalid executable behavior contract')
        binding = case.get('binding_symbols', [])
        check(isinstance(binding, list) and len(binding) <= 16 and len(set(binding)) == len(binding)
              and all(re.fullmatch(r'[A-Za-z0-9_.$]+', s) for s in binding), 'Invalid Loader diagnostic symbols')
        provenance = case['build']
        check(isinstance(provenance, dict) and isinstance(provenance['records'], list) and provenance['records']
              and PIN.fullmatch(provenance['evidence_sha256']), 'Missing build provenance')
        check(case['elf']['interpreter'] == '/lib/ld-linux.so.3' and isinstance(case['elf']['needed'], list)
              and all(LEAF.fullmatch(v) for v in case['elf']['needed']), 'Invalid ELF dependency contract')
        artifacts[name] = case | {'sha256': entries['probe'], 'bundle_path': name+'/probe', 'manifest_sha256': pin}
        registered.add(name)
    check(registered and {p.name for p in root.iterdir()} == registered, 'Unregistered bundle directory')
    return artifacts
