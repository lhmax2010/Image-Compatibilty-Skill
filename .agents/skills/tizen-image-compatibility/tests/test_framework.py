from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from compat.core import DEFAULTS, InputError, Tools, finding, load_config, read_manifest, validate_config
from compat.collect import collect, parse_dbus
from compat.compare import compare_api, compare_elf, compare_packages, dependency_checks, finalize
from compat.elf import collect_elf
from compat.images import Image
from compat.packages import parse_rpm_xml
from compat.report import build_results, generate
from compat.source import normalize_text, parse_header
from compat.testing import run_matrix
from make_synthetic_fixture import create
from tizen_compat import main


class Environment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.config = copy.deepcopy(DEFAULTS)
        self.output = self.base / 'report'
        self.output.mkdir()
        self.tools = Tools(self.output, self.config)
        self.workspace = self.base / 'workspace'
        self.workspace.mkdir()

    def blank(self):
        return dict(schema_version='1.0', image={'name': 'synthetic'}, elf_objects=[], public_headers=[],
            packages=[], limitations=[], test_results=[], filesystem=[], capabilities=[])


class SourceTests(Environment):
    def test_comments_preserve_strings_and_tokens(self):
        a = parse_header('/*comment*/ int f(int x);\n#define NAME "a // b"')
        b = parse_header('int  f ( int x ) ;\n#define NAME "a // b"')
        self.assertEqual(a['tokens'], b['tokens'])
        self.assertIn('f', a['declarations'])
        self.assertEqual(a['macros']['NAME']['replacement'], ['"a // b"'])
        self.assertNotEqual(parse_header('int f(intx);')['tokens'], a['tokens'])

    def test_function_macro_spacing_matters(self):
        # f(x) replacement vs f (x) object-like definition have different semantics.
        a = parse_header('#define f(x) x')
        b = parse_header('#define f (x) x')
        self.assertNotEqual(a, b)

    def test_normalization(self):
        self.assertEqual(normalize_text('# Generated at: yesterday\nkey=value  \n'), 'key=value')
        self.assertEqual(normalize_text('#line 3 "/build/path"\nint x;'), 'int x;')
        self.assertNotEqual(normalize_text('default=1'), normalize_text('default=2'))

    def test_header_comparison(self):
        a, b = self.blank(), self.blank()
        a['public_headers'] = [{'path': '/usr/include/a.h', 'sha256': 'a', **parse_header('int old(void);')}]
        b['public_headers'] = [{'path': '/usr/include/a.h', 'sha256': 'b', **parse_header('int next(void);')}]
        self.assertTrue(any(f['status'] == 'INCOMPATIBLE' and f['interface'] == 'old' for f in compare_api(a, b)))
        b['public_headers'] = []
        self.assertEqual(compare_api(a, b)[0]['status'], 'INCOMPATIBLE')

    def test_comment_only_header_is_lexically_equal_but_semantics_unknown(self):
        a, b = self.blank(), self.blank()
        a['public_headers'] = [{'path': '/usr/include/a.h', 'sha256': 'a', **parse_header('int old(void);')}]
        b['public_headers'] = [{'path': '/usr/include/a.h', 'sha256': 'b', **parse_header('/* note */ int old(void);')}]
        self.assertEqual(compare_api(a, b)[0]['status'], 'UNKNOWN')

    def test_dbus_argument_names_are_not_wire_contract(self):
        a = parse_dbus('<node><interface name="org.Test"><method name="M"><arg type="s" name="before"/></method></interface></node>')
        b = parse_dbus('<node><interface name="org.Test"><method name="M"><arg type="s" name="after" direction="in"/></method></interface></node>')
        self.assertEqual(a, b)

    def test_dbus_nested_paths(self):
        result = parse_dbus('<node name="/root"><node name="child"><interface name="org.Test"><method name="M"><arg type="s"/></method></interface></node></node>')
        self.assertEqual(result[0]['name'], '/root/child:org.Test:method:M')


class ImageTests(Environment):
    def test_symlink_stays_inside_image(self):
        root = self.base / 'image'; root.mkdir()
        (root / 'etc').mkdir(); (root / 'etc/file').write_text('inside')
        (root / 'absolute').symlink_to('/etc/file')
        (root / 'escape').symlink_to('../../etc/passwd')
        image = Image(root, self.workspace, self.tools, 'image')
        self.assertEqual(image.resolve('/absolute').read_text(), 'inside')
        self.assertIsNone(image.resolve('/escape'))

    def test_safe_tar_preserves_metadata(self):
        archive = self.base / 'root.tar'
        with tarfile.open(archive, 'w') as out:
            entry = tarfile.TarInfo('etc/file'); entry.size = 5; entry.uid = 123; entry.mode = 0o640
            out.addfile(entry, io.BytesIO(b'value'))
            link = tarfile.TarInfo('etc/link'); link.type = tarfile.SYMTYPE; link.linkname = '/etc/file'; out.addfile(link)
        image = Image(archive, self.workspace, self.tools, 'image')
        self.assertEqual(image.resolve('/etc/link').read_text(), 'value')
        self.assertEqual(image.metadata['/etc/file']['uid'], 123)
        self.assertEqual(image.metadata['/etc/file']['mode'], '0o640')

    def test_reject_tar_escape(self):
        archive = self.base / 'bad.tar'
        with tarfile.open(archive, 'w') as out:
            entry = tarfile.TarInfo('../escaped'); entry.size = 1; out.addfile(entry, io.BytesIO(b'x'))
        with self.assertRaises(InputError):
            Image(archive, self.workspace, self.tools, 'image')
        self.assertFalse((self.base / 'escaped').exists())

    def test_reject_tar_symlink_write(self):
        archive = self.base / 'bad.tar'
        with tarfile.open(archive, 'w') as out:
            link = tarfile.TarInfo('link'); link.type = tarfile.SYMTYPE; link.linkname = '/tmp'; out.addfile(link)
            entry = tarfile.TarInfo('link/escaped'); entry.size = 1; out.addfile(entry, io.BytesIO(b'x'))
        with self.assertRaises(InputError):
            Image(archive, self.workspace, self.tools, 'image')

    def test_unsupported_image(self):
        source = self.base / 'disk.img'; source.write_bytes(b'not ext4')
        with self.assertRaisesRegex(InputError, 'Unsupported image format'):
            Image(source, self.workspace, self.tools, 'image')

    def test_oci_layer_layout_rejected(self):
        source = self.base / 'oci'; source.mkdir(); (source / 'oci-layout').write_text('{}')
        with self.assertRaisesRegex(InputError, 'whiteouts'):
            Image(source, self.workspace, self.tools, 'image')


class ComparisonTests(Environment):
    def obj(self, name='old@@V1'):
        return dict(path='/lib/libtest.so.1', complete=True, soname='libtest.so.1', needed=[], machine='A',
            exports=[dict(name=name, size=10, type='FUNC', binding='GLOBAL', visibility='DEFAULT')])

    def test_missing_versioned_symbol(self):
        a, b = self.blank(), self.blank()
        a['elf_objects'], b['elf_objects'] = [self.obj()], [self.obj('new@@V2')]
        result = compare_elf(a, b)
        self.assertTrue(any(f['interface'] == 'old@@V1' and f['status'] == 'INCOMPATIBLE' for f in result))

    def test_function_size_not_abi_failure(self):
        a, b = self.blank(), self.blank()
        a['elf_objects'], b['elf_objects'] = [self.obj()], [self.obj()]
        b['elf_objects'][0]['exports'][0]['size'] = 20
        self.assertFalse(any(f['status'] == 'INCOMPATIBLE' for f in compare_elf(a, b)))

    def test_soname_difference_and_needed(self):
        a, b = self.blank(), self.blank()
        a['elf_objects'], b['elf_objects'] = [self.obj()], [self.obj()]
        b['elf_objects'][0].update(soname='libtest.so.2', needed=['libmissing.so.1'])
        self.assertTrue(any(f['interface'] == 'soname' for f in compare_elf(a, b)))
        b['collection_complete'] = True
        b['loader_environment'] = {'model': 'glibc', 'environment_complete': True, 'cache_complete': True, 'default_dirs': ['/lib']}
        for elf in b['elf_objects']: elf['resolution_metadata_complete'] = True  # complete synthetic lookup evidence
        self.assertTrue(any(f['status'] == 'INCOMPATIBLE' for f in dependency_checks(b, 'candidate')))

    def test_missing_tool_no_false_removals(self):
        a, b = self.blank(), self.blank()
        a['elf_objects'], b['elf_objects'] = [self.obj()], [{'path': '/lib/libtest.so.1', 'complete': False}]
        self.assertFalse(any(f['status'] == 'INCOMPATIBLE' for f in compare_elf(a, b)))

    def test_weak_import_is_not_missing_export(self):
        a, b = self.blank(), self.blank()
        a['elf_objects'], b['elf_objects'] = [self.obj()], [self.obj()]
        a['elf_objects'][0]['imports'] = [{'name': 'optional', 'binding': 'WEAK'}]
        self.assertFalse(any(f['status'] == 'INCOMPATIBLE' for f in compare_elf(a, b)))

    def test_rpm_release_is_compatible(self):
        a, b = self.blank(), self.blank()
        a['packages'] = [dict(name='test', arch='aarch64', version='1', release='1')]
        b['packages'] = [dict(name='test', arch='aarch64', version='1', release='2')]
        self.assertEqual(compare_packages(a, b)[0]['status'], 'COMPATIBLE')
        b['packages'][0]['version'] = '2'
        self.assertTrue(any(f['status'] == 'UNKNOWN' for f in compare_packages(a, b)))

    def test_rpm_xml(self):
        xml = '<rpmHeader><rpmTag name="Name"><string>test</string></rpmTag><rpmTag name="Arch"><string>aarch64</string></rpmTag><rpmTag name="Providename"><string>libtest.so.1</string></rpmTag><rpmTag name="Provideversion"><string>1</string></rpmTag></rpmHeader>'
        record = parse_rpm_xml(xml)[0]
        self.assertEqual(record['provides'][0]['name'], 'libtest.so.1')
        self.assertEqual(record['arch'], 'aarch64')

    def test_severity_override_and_exclude(self):
        self.config['severity_overrides']['abi'] = 'CRITICAL'
        self.config['analysis']['modes'] = ['abi']
        result = finalize([finding('abi', 'x', 'x', 1, 2), finding('runtime', 'x', 'x', 1, 2)], self.config)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['severity'], 'CRITICAL')


class InfrastructureTests(Environment):
    def test_config_rejects_types_and_unknown_keys(self):
        bad = self.base / 'bad.yaml'; bad.write_text('runtime:\n  authorized: "yes"\n')
        with self.assertRaises(InputError): load_config(bad)
        bad.write_text('analysis:\n  workers: 0\n')
        with self.assertRaises(InputError): load_config(bad)
        bad.write_text('runtime:\n  mystery: true\n')
        with self.assertRaises(InputError): load_config(bad)

    def test_missing_tool(self):
        self.config['tools']['readelf'] = False
        self.config['tools']['nm'] = False
        elf = self.base / 'file'; elf.write_bytes(b'\x7fELF' + bytes([2, 1, 1, 0, 0]) + b'\0' * 9 + b'\x3e\x00')
        record = collect_elf(elf, '/file', self.tools, 'static')
        self.assertFalse(record['complete'])
        self.assertEqual(record['machine_id'], 62)

    def test_timeout_records_evidence(self):
        result = self.tools.run([sys.executable, '-c', 'import time; time.sleep(5)'], timeout=0.05)
        self.assertEqual(result['error'], 'timeout')
        self.assertTrue((self.output / result['stdout_evidence']).exists())

    def test_report_escaping_and_manifest(self):
        a, b = self.blank(), self.blank()
        records = [finding('api', '<script>alert(1)</script>', '=formula', 'x', None, 'INCOMPATIBLE', 'HIGH')]
        result = build_results(a, b, records, [], [], self.config)
        generate(self.output, a, b, result, self.config)
        self.assertEqual(read_manifest(self.output / 'baseline-manifest.json')['schema_version'], '1.0')
        html = (self.output / 'index.html').read_text()
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn("'=formula", (self.output / 'findings.csv').read_text())
        self.assertEqual(json.loads((self.output / 'results.json').read_text())['status'], 'INCOMPATIBLE')

    def test_no_runtime_means_unknown(self):
        a, b = self.blank(), self.blank()
        tests, matrix, findings = run_matrix((a, b), None, self.tools, 'full')
        self.assertEqual(len(matrix), 4)
        self.assertTrue(all(x['status'] == 'UNKNOWN' for x in matrix))
        self.assertFalse(tests)

    def test_source_output_guard(self):
        source = self.base / 'image'; source.mkdir()
        self.assertEqual(main(['--baseline', str(source), '--candidate', str(source), '--output', str(source / 'report')]), 2)
        self.assertFalse((source / 'report').exists())


@unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Synthetic ELF tests need GCC and readelf')
class EndToEndTests(Environment):
    def setUp(self):
        super().setUp()
        self.images = self.base / 'images'
        create(self.images)

    def snapshot(self):
        return {str(p.relative_to(self.images)): (p.lstat().st_mode, os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest())
                for p in self.images.rglob('*') if p.is_file() or p.is_symlink()}

    def test_elf_collection_and_cache(self):
        image = Image(self.images / 'baseline', self.workspace, self.tools, 'baseline')
        m = collect(image, 'synthetic', 'baseline', 'static', self.tools, self.workspace, self.base / 'cache')
        obj = m['elf_objects'][0]
        self.assertTrue(obj['complete'])
        self.assertIn('ELF', obj['class'])
        self.assertEqual(obj['soname'], 'libsynthetic.so.1')
        self.assertTrue(any(s['name'].startswith('public_removed@') for s in obj['exports']))
        count = len(self.tools.records)
        n = collect(image, 'synthetic', 'baseline', 'static', self.tools, self.workspace, self.base / 'cache')
        self.assertEqual(m, n)
        self.assertEqual(count, len(self.tools.records))

    def test_full_offline_cli_and_reuse(self):
        snapshot = self.snapshot()
        output = self.base / 'cli-report'
        code = main(['--baseline', str(self.images / 'baseline'), '--candidate', str(self.images / 'candidate'), '--mode', 'full', '--output', str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(snapshot, self.snapshot())
        result = json.loads((output / 'results.json').read_text())
        self.assertTrue(any(f['interface'].startswith('public_removed') and f['status'] == 'INCOMPATIBLE' for f in result['findings']))
        self.assertEqual(len(result['matrix']), 4)
        self.assertTrue(all(c['status'] == 'UNKNOWN' for c in result['matrix']))
        reused = self.base / 'reuse'
        self.assertEqual(main(['--baseline-manifest', str(output / 'baseline-manifest.json'), '--candidate-manifest', str(output / 'candidate-manifest.json'), '--output', str(reused)]), 1)
        self.assertTrue((reused / 'evidence').is_dir())

    def test_identical_strict_and_threshold(self):
        source = str(self.images / 'baseline')
        self.assertEqual(main(['--baseline', source, '--candidate', source, '--output', str(self.base / 'same')]), 0)
        self.assertEqual(main(['--baseline', source, '--candidate', source, '--strict', '--output', str(self.base / 'strict')]), 1)
        self.assertEqual(main(['--baseline', source, '--candidate', str(self.images / 'candidate'), '--fail-on', 'CRITICAL', '--output', str(self.base / 'critical')]), 0)


if __name__ == '__main__':
    unittest.main()
