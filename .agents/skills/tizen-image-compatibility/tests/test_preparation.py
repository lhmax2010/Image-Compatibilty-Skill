"""Image preparation regression and byte-structured synthetic flash fixtures."""
import io
import json
import lzma
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import uuid
import zlib

from test_framework import Environment
from compat.compare import compare_static
from compat.core import Tools, hash_file, write_json
from compat.flash import PreparationError, decompress_xz, gpt_partitions
from compat.images import Image
from compat.preparation import MANIFEST, identity, prepare, prepared_input


def write_tar(path, members, compression=''):
    with tarfile.open(path, 'w' + compression) as archive:
        for name, payload in members.items():
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.uid = len(payload), 0o750, 123
            archive.addfile(item, io.BytesIO(payload))


def gpt(payload, sector=512, *, bad=''):
    entries = bytearray(2 * 128)
    partition_start = 6
    partition_end = partition_start + (len(payload) + sector - 1) // sector - 1
    disk_end = max(partition_end + 5, 30)
    disk = bytearray(sector * (disk_end + 1))
    disk[450] = 0xee
    disk[510:512] = b'\x55\xaa'
    disk[partition_start * sector:partition_start * sector + len(payload)] = payload
    for i in range(2 if bad == 'overlap' else 1):
        slot = i * 128
        entries[slot:slot + 16] = uuid.UUID(int=1).bytes_le
        entries[slot + 16:slot + 32] = uuid.UUID(int=2 + i).bytes_le
        struct.pack_into('<QQ', entries, slot + 32, partition_start, disk_end if bad == 'bounds' else partition_end)
        name = ('pltf_t.img' if i == 0 else 'other').encode('utf-16-le')
        entries[slot + 56:slot + 56 + len(name)] = name
    for lba, alternate, table in ((1, disk_end, 2), (disk_end, 1, disk_end - 1)):
        header = bytearray(92)
        struct.pack_into('<8sIIIIQQQQ16sQIII', header, 0, b'EFI PART', 0x10000, 92, 0, 0,
                         lba, alternate, 3, disk_end - 2, uuid.UUID(int=10).bytes_le,
                         table, 2, 128, zlib.crc32(entries))
        struct.pack_into('<I', header, 16, zlib.crc32(header))
        disk[lba * sector:lba * sector + len(header)] = header
        disk[table * sector:table * sector + len(entries)] = entries
    if bad == 'primary-crc':
        disk[sector + 16] ^= 1
    if bad == 'backup-crc':
        disk[disk_end * sector + 16] ^= 1
    if bad == 'array-crc':
        disk[sector * 2 + 32] ^= 1
    return bytes(disk)


class PreparationTests(Environment):
    def flash(self, *, geometry=512, bad=''):
        archive = self.base / 'flash-without-extension'
        vdfs = bytes(1024) + b'VDFS2007' + bytes(6000)
        write_tar(archive, {'platform.img': gpt(lzma.compress(vdfs), geometry, bad=bad)}, ':gz')
        return archive

    def separate(self, name):
        out = self.base / name
        out.mkdir()
        return out, Tools(out, self.tools.config)

    def test_rootfs_tar_and_targz_keep_legacy_metadata(self):
        for n, compression in enumerate(('', ':gz')):
            archive = self.base / f'ordinary-{n}.bin'
            write_tar(archive, {'etc/os-release': b'NAME=Tizen', 'usr/bin/program': b'payload'}, compression)
            before = hash_file(archive)
            image = Image(archive, self.workspace, self.tools, f'ordinary-{n}')
            self.assertEqual(image.resolve('/usr/bin/program').read_bytes(), b'payload')
            self.assertEqual(image.metadata['/usr/bin/program']['uid'], 123)
            self.assertIsNone(image.extraction_manifest)
            self.assertEqual(hash_file(archive), before)
            output, tools = self.separate(f'output-{n}')
            self.assertEqual(prepare(archive, output, tools)['status'], 'READY')
            verified = Image(output, self.workspace, self.tools, f'prepared-{n}')
            self.assertEqual(verified.metadata['/usr/bin/program']['mode'], '0o750')

    def test_signature_detection_and_missing_adapter_are_distinct(self):
        archive = self.flash(geometry=4096)
        before = hash_file(archive)
        out, tools = self.separate('inspection')
        record = prepare(archive, out, tools, inspect_only=True)
        self.assertEqual([p['format'] for p in record['layers']], ['tar', 'gpt', 'xz', 'vdfs'])
        gpt_layer, xz = record['layers'][1:3]
        self.assertEqual((gpt_layer['sector_size'], gpt_layer['selected']['offset']), (4096, 24576))
        self.assertTrue(gpt_layer['backup_crc_verified'])
        self.assertGreater(xz['padding_bytes'], 0)
        self.assertEqual(record['layers'][3]['layout_version'], '2007')
        self.assertEqual(record['blocker'], 'VDFS_EXTRACTOR_UNAVAILABLE')
        self.assertEqual(record['source']['sha256'], before)
        self.assertFalse((out / 'rootfs').exists())
        with self.assertRaisesRegex(PreparationError, 'VDFS_EXTRACTOR_UNAVAILABLE'):
            Image(archive, self.workspace, self.tools, 'flash')
        manifest = json.loads((self.tools.output/'flash-extraction-manifest.json').read_text())
        self.assertEqual(manifest['failure']['code'], 'VDFS_EXTRACTOR_UNAVAILABLE')
        self.assertEqual(hash_file(archive), before)

    def test_gpt_rejects_unchecked_ranges_headers_or_tables(self):
        for error in ('overlap', 'bounds', 'primary-crc', 'backup-crc', 'array-crc'):
            with self.subTest(error=error):
                path = self.base / error
                path.write_bytes(gpt(lzma.compress(bytes(8192)), bad=error))
                with self.assertRaisesRegex(PreparationError, 'GPT_INVALID'):
                    gpt_partitions(path)

    def test_truncated_concatenated_and_overbudget_xz(self):
        payload = lzma.compress(b'x'*20000)
        for label, data, limit, reason in [('truncated', payload[:-1], 40000, 'XZ_INVALID'),
                                           ('concatenated', payload+payload, 40000, 'XZ_INVALID'),
                                           ('limit', payload, 10000, 'XZ_LIMIT')]:
            p = self.base/label; p.write_bytes(data)
            with self.assertRaisesRegex(PreparationError, reason):
                decompress_xz(p, self.base/(label+'.out'), limit, 128 * 1024**2)

    def fake_adapter(self, complete, *, wrong_digest=False, traversal=False):
        fixtures = self.base/'adapter'; fixtures.mkdir(exist_ok=True)
        archive = fixtures/'fixture.tar'
        write_tar(archive, {'../escape' if traversal else 'etc/os-release': b'NAME=fixture'})
        script = fixtures/'adapter.py'
        script.write_text(f'''import hashlib,json,pathlib,shutil,sys
if sys.argv[1:] == ['--version']:
    print('synthetic adapter 1'); sys.exit(0)
source, output, receipt = map(pathlib.Path, sys.argv[1:])
shutil.copyfile({str(archive)!r}, output)
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
receipt.write_text(json.dumps(dict(schema='tizen-vdfs-receipt/1', input_sha256=digest(source),
    output_tar_sha256={'"not-matching"' if wrong_digest else 'digest(output)'}, scope='runtime-rootfs',
    excluded_partitions={{}}, complete={complete!r})))
''')
        self.tools.config['preparation']['vdfs_adapter'] = {
            'command': [sys.executable, str(script), '{input}', '{output}', '{receipt}'],
            'version_args': [str(script), '--version']}

    def test_adapter_attestation_and_tampered_bundle(self):
        source = self.flash()
        self.fake_adapter(True)
        output, tools = self.separate('adapted')
        record = prepare(source, output, tools)
        self.assertEqual(record['status'], 'READY')
        self.assertIn('synthetic adapter', record['extractor']['version'])
        direct = Image(source, self.workspace, self.tools, 'automatic')
        self.assertEqual(direct.resolve('/etc/os-release').read_bytes(), b'NAME=fixture')
        self.assertTrue(direct.extraction_manifest.is_file())
        self.assertEqual(Image(output, self.workspace, self.tools, 'valid').resolve('/etc/os-release').read_bytes(), b'NAME=fixture')
        (output/'rootfs/etc/os-release').write_text('changed')
        with self.assertRaisesRegex(PreparationError, 'PREPARED_OUTPUT_MISMATCH'):
            Image(output/'rootfs', self.workspace, self.tools, 'tampered')

    def test_partial_adapter_cannot_be_used_even_via_direct_root(self):
        source = self.flash()
        self.fake_adapter(False)
        output, tools = self.separate('partial')
        record = prepare(source, output, tools)
        self.assertEqual(record['status'], 'PARTIAL')
        for path in (output, output/'rootfs'):
            with self.assertRaisesRegex(PreparationError, 'ROOTFS_INCOMPLETE'):
                Image(path, self.workspace, self.tools, 'partial')

    def test_adapter_mismatch_and_unsafe_tar_never_publish_ready(self):
        source = self.flash()
        for label, options, match in [('mismatch', dict(wrong_digest=True), 'VDFS_RECEIPT_MISMATCH'),
                                      ('traversal', dict(traversal=True), 'Unsafe TAR path')]:
            self.fake_adapter(True, **options)
            output, tools = self.separate(label)
            with self.assertRaisesRegex(ValueError, match):
                prepare(source, output, tools)
            self.assertEqual(json.loads((output/MANIFEST).read_text())['status'], 'FAILED')
            self.assertFalse((output/'rootfs').exists())

    def test_same_build_replacement_keeps_sdk_and_rpm_scopes_separate(self):
        source = self.flash()
        for kind in ('rootfs', 'rpm-repository', 'rootstrap'):
            replacement = self.base / kind; replacement.mkdir()
            rel = {'rootfs':'etc/os-release', 'rpm-repository':'package.rpm', 'rootstrap':'usr/include/api.h'}[kind]
            member = replacement/rel; member.parent.mkdir(parents=True, exist_ok=True)
            member.write_bytes(bytes.fromhex('edabeedb') if kind == 'rpm-repository' else b'fixture')
            receipt = self.base/(kind+'.json')
            write_json(receipt, {'schema':'tizen-build-replacement/1', 'kind':kind, 'build_id':'fixture-1',
                                 'source_sha256':hash_file(source), 'replacement_sha256':identity(replacement,self.tools.config)['sha256'],
                                 'complete':True})
            output, tools = self.separate(kind+'-prepared')
            record = prepare(source, output, tools, replacement=(replacement,kind,receipt,'fixture-1'))
            self.assertEqual(record['status'], 'READY')
            if kind == 'rootstrap':
                self.assertEqual(prepared_input(output, self.tools.config, sdk=True)[0].name, 'rootstrap')
                with self.assertRaisesRegex(PreparationError, 'PREPARATION_SCOPE_MISMATCH'):
                    Image(output, self.workspace, self.tools, 'wrong-role')
                unrelated = self.base/'other-rootfs'; unrelated.mkdir()
                cli = Path(__file__).resolve().parents[1]/'scripts/tizen_compat.py'
                result = subprocess.run([sys.executable, str(cli), '--baseline', str(unrelated), '--candidate', str(unrelated),
                                         '--baseline-sysroot', str(output), '--mode', 'full', '--output', str(self.base/'wrong-sdk')],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('ROOTSTRAP_SOURCE_MISMATCH', result.stderr)
            else:
                image = Image(output, self.workspace, self.tools, kind)
                self.assertIsNotNone(image.resolve('/'+rel))
                self.assertEqual(image.format == 'rpm-collection', kind == 'rpm-repository')
            out, other = self.separate(kind+'-mismatch')
            with self.assertRaisesRegex(PreparationError, 'REPLACEMENT_IDENTITY_MISMATCH'):
                prepare(source, out, other, replacement=(replacement,kind,receipt,'different-build'))

    def test_cli_never_compares_unprepared_flash_and_absence_gate(self):
        source = self.flash()
        root = self.base/'root'; root.mkdir()
        report = self.base/'blocked-report'
        cli = Path(__file__).resolve().parents[1]/'scripts/tizen_compat.py'
        run = subprocess.run([sys.executable, str(cli), '--baseline', str(source), '--candidate', str(root),
                              '--output', str(report)], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertIn('VDFS_EXTRACTOR_UNAVAILABLE', run.stderr)
        self.assertFalse((report/'results.json').exists())
        a, b = self.blank(), self.blank()
        a['commands'] = [{'path':'/usr/bin/existing'}]
        for complete in (None, False, True):
            if complete is not None:
                b['collection_complete'] = complete
            absence = next(f for f in compare_static(a,b,self.tools.config) if f['dimension']=='commands')
            self.assertEqual(absence['status'], 'INCOMPATIBLE' if complete else 'UNKNOWN')
