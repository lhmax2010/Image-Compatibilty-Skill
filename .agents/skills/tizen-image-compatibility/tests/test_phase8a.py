"""Regression tests for the real SR static acceptance findings."""
import copy
import json
import shutil
import subprocess
import unittest
from unittest.mock import patch

from test_framework import Environment
from compat.collect import collect
from compat.compare import compare_elf
from compat.core import finding
from compat.elf import collect_elf
from compat.images import Image
from compat.linker import dependency_checks
from compat.report import build_results
from compat.report_io import ResourceGuard, ResourceLimit
from test_static_fixes import elf, symbol
from tizen_compat import main


def node(name, index):
    return dict(name=name, index=index, flags='none', parents=[])


class VersionTests(Environment):
    def compare(self, before, after):
        return compare_elf(self.blank() | {'elf_objects': [before]}, self.blank() | {'elf_objects': [after]})

    def test_gnu_marker_change_with_retained_node_and_ordinary_abs(self):
        marker = dict(symbol('V1', kind='OBJECT', size=0), section='ABS', value=0)
        ordinary = dict(marker, name='ordinary_absolute')
        library = elf('/lib/demo.so', type='DYN', version_definitions=[node('V1', 2)])
        versioned = symbol('api@@V1')
        before = library | {'exports': [marker, ordinary, versioned]}
        after = library | {'exports': [ordinary, versioned]}
        self.assertFalse(any(f['status'] == 'INCOMPATIBLE' for f in self.compare(before, after)))
        after['exports'].remove(ordinary)
        changes = self.compare(before, after)
        self.assertEqual([f['interface'] for f in changes if f['status'] == 'INCOMPATIBLE'], ['ordinary_absolute'])

    def test_removed_version_uses_verdef_and_requires_complete_collection(self):
        before = elf('/lib/demo.so', type='DYN', version_definitions=[node('V1', 2)], exports=[symbol()])
        after = before | {'version_definitions': []}
        for complete, expected in [(True, 'INCOMPATIBLE'), (False, 'UNKNOWN')]:
            changes = self.compare(before, after | {'export_inventory_complete': complete})
            self.assertIn(('version definition:V1', expected), [(f['interface'], f['status']) for f in changes])

    def test_retained_node_does_not_hide_a_removed_function(self):
        before = elf('/lib/demo.so', type='DYN', version_definitions=[node('V1', 2)], exports=[symbol('api@@V1')])
        changes = self.compare(before, before | {'exports': []})
        self.assertTrue(any(f['interface'] == 'api@@V1' and f['status'] == 'INCOMPATIBLE' for f in changes))
        self.assertFalse(any(f['interface'] == 'version definition:V1' for f in changes))

    def test_readelf_keeps_marker_evidence_and_checks_version_requirement_index(self):
        sample = self.base / 'elf'
        sample.write_bytes(b'fixture')
        text = """ELF Header:
  Class: ELF64
  Data: 2's complement, little endian
  Type: DYN (Shared object file)
  Machine: Advanced Micro Devices X86-64
Dynamic section at offset 0x100 contains 1 entries:
Symbol table '.dynsym' contains 4 entries:
 Num: Value Size Type Bind Vis Ndx Name
 0: 0000000000000000 0 NOTYPE LOCAL DEFAULT UND
 1: 0000000000000000 0 OBJECT GLOBAL DEFAULT ABS V1
 2: 0000000000001000 4 FUNC GLOBAL DEFAULT 12 api@@V1
 3: 0000000000000000 0 FUNC GLOBAL DEFAULT UND used@V2 (3)

Version definition section '.gnu.version_d' contains 1 entry:
  0x001c: Rev: 1 Flags: none Index: 2 Cnt: 1 Name: V1

Version needs section '.gnu.version_r' contains 1 entry:
  000000: Version: 1 File: libc.so Cnt: 1
  0x0010: Name: V2 Flags: none Version: 3

"""
        response = dict(returncode=0, stdout_truncated=False, stderr='', error=None,
                        stdout_evidence='evidence/fixture.txt', stderr_evidence='evidence/empty.txt')
        for contents, complete in [(text, True), (text.replace(' (3)', ' (7)'), False)]:
            with patch.object(self.tools, 'path', return_value='/fixture/readelf'), \
                    patch.object(self.tools, 'run', return_value=response | {'stdout': contents}):
                result = collect_elf(sample, '/fixture', self.tools, 'static')
            self.assertEqual(result['export_inventory_complete'], complete)
            if complete:
                self.assertEqual([s['name'] for s in result['exports']], ['api@@V1'])
                self.assertEqual([s['name'] for s in result['version_node_markers']], ['V1'])
                self.assertEqual(result['imports'][0]['version_file'], 'libc.so')

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Needs native GCC/binutils')
    def test_real_readelf_distinguishes_full_symbol_names_from_first_token(self):
        objects = []
        for index,name in enumerate(('sample name (4)','sample')):
            source = self.base/f'{index}.S'
            source.write_text(f'.data\n.globl "{name}"\n.type "{name}",%object\n'
                              f'"{name}":\n.long 1\n.size "{name}",4\n')
            library = source.with_suffix('.so')
            subprocess.run(['gcc','-nostdlib','-shared',str(source),'-o',str(library)],
                           check=True,capture_output=True,timeout=20)
            collected = collect_elf(library,'/lib/fixture.so',self.tools,'static')
            self.assertTrue(collected['export_inventory_complete'])
            self.assertEqual([(item['name'],item['version_index']) for item in collected['exports']],[(name,None)])
            objects.append(collected)
        self.assertIn(('sample name (4)','INCOMPATIBLE'),
                      {(f['interface'],f['status']) for f in self.compare(*objects)})

    def test_bounded_linking_scope_and_required_version(self):
        consumer = elf(needed=['a.so'], version_requirements=[dict(file='a.so', name='V1', flags='none')],
                       imports=[dict(symbol('api@V1'), version_file='a.so')])
        provider = elf('/lib/a.so', type='DYN', version_definitions=[node('V1', 2)], exports=[symbol('api@@V1')])
        unrelated = elf('/other/unrelated.so', complete=False)
        manifest = self.blank() | dict(elf_objects=[provider, unrelated], collection_complete=False,
            filesystem_path_inventory_complete=True, loader_environment=dict(model='glibc',
                environment_complete=True, cache_complete=True, default_dirs=['/lib'], symbol_scope='startup'))
        def version_status():
            return next(f['resolution'] for f in dependency_checks(manifest, 'test', [consumer])
                        if f['check_id'] == 'version:a.so:V1')
        self.assertEqual(version_status(), 'verified')
        provider['version_definitions'] = [node('V2', 2)]
        self.assertEqual(version_status(), 'missing_version')
        manifest['filesystem_path_inventory_complete'] = False
        self.assertEqual(version_status(), 'unknown_version_requirement')
        manifest['filesystem_path_inventory_complete'] = True
        manifest['loader_environment']['namespace'] = 'plugin'
        self.assertEqual(version_status(), 'unknown_version_requirement')


class ExecutionTests(Environment):
    def test_default_failed_collector_exit_and_legacy_override(self):
        root = self.base / 'image'
        (root / 'etc').mkdir(parents=True)
        binary = root / 'elf'
        binary.write_bytes(b'\x7fELF\x02\x01' + b'\0' * 40)
        database = root / 'var/lib/rpm'
        database.mkdir(parents=True)
        (database / 'Packages').write_bytes(b'fixture')
        failed = self.base / 'failed'
        failed.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo fixture; exit 0; fi\nexit 19\n')
        failed.chmod(0o755)
        config = self.base / 'config.json'
        for i, (opt_in, strict, threshold, expected) in enumerate([
                (True, False, {}, 3), (False, False, {}, 0), (False, True, {}, 1), (False, False, {'abi': 1}, 1)]):
            with self.subTest(i=i):
                config.write_text(json.dumps({'tools': {'readelf': str(failed), 'rpm': str(failed)},
                    'ci': {'fail_on_collector_failure': opt_in, 'strict': strict, 'minimum_coverage': threshold}}))
                output = self.base / f'run-{i}'
                self.assertEqual(main(['--baseline', str(root), '--candidate', str(root), '--output', str(output),
                                      '--config', str(config), '--fail-on', 'CRITICAL']), expected)
                result = json.loads((output / 'results.json').read_text())
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertEqual(result['execution']['status'], 'FAILED')
                self.assertEqual(result['execution']['collectors']['baseline']['rpm']['status'], 'FAILED')
                self.assertIn('Collector execution', (output / 'index.html').read_text())
                self.assertIn('Collector execution', (output / 'summary.md').read_text())

    def test_partial_and_missing_optional_input_do_not_mask_compatibility_threshold(self):
        a = self.blank() | {'collector_execution': {'readelf': {'status': 'PARTIAL'}, 'rpm': {'status': 'NOT_EXECUTED'}}}
        row = finding('abi', 'a', 'change', 1, None, 'INCOMPATIBLE', 'HIGH')
        for threshold, expected in [('HIGH', 'FAIL'), ('CRITICAL', 'PASS')]:
            cfg = copy.deepcopy(self.config)
            cfg['ci']['fail_on'] = threshold
            report = build_results(a, a, [row], [], [], cfg)
            self.assertEqual(report['execution']['status'], 'PARTIAL')
            self.assertEqual(report['quality_gate']['compatibility_status'], expected)

    def test_input_scope_preserves_explicit_gaps(self):
        source = self.base / 'rootfs'
        (source / 'etc').mkdir(parents=True)
        (source / 'etc' / 'release').write_text('sample')
        self.config['analysis']['input_scope'] = {'baseline': {'paths': False, 'xattrs': False, 'ramdisk': False}}
        record = collect(Image(source, self.workspace, self.tools, 'baseline'), 'test', 'baseline',
                         'quick', self.tools, self.workspace, None)
        self.assertFalse(record['filesystem_path_inventory_complete'])
        self.assertFalse(record['header_inventory_complete'])
        self.assertEqual(record['image']['input_evidence_scope']['ramdisk'], 'NOT_RESTORED')
        self.assertEqual(record['image']['input_evidence_scope']['file_contents'], 'OBSERVABLE')

    def test_estimated_disk_budget_retains_free_space_reserve(self):
        gib = 1024**3
        guard = ResourceGuard(self.output, disk_budget=gib)
        with patch('os.statvfs', return_value=type('Disk', (), {'f_bavail': 2 * gib, 'f_frsize': 1})()):
            guard.check(force=True)
        self.assertEqual(guard.last_snapshot['disk_required_free_bytes'], 2 * gib)
        with patch('os.statvfs', return_value=type('Disk', (), {'f_bavail': 2 * gib - 65536, 'f_frsize': 1})()):
            with self.assertRaisesRegex(ResourceLimit, 'disk'):
                guard.check(force=True)
