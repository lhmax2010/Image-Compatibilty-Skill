"""Phase 7A policy regressions and controls. Never execute a Tizen artifact."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import csv
import hashlib
import sqlite3
from unittest.mock import patch

from test_framework import Environment
from compat.collect import collect
from compat.compare import compare_api, compare_elf, compare_static
from compat.core import read_manifest, write_json, InputError, finding
from compat.elf import collect_elf
from compat.images import Image
from compat.linker import dependency_checks
from compat.source import parse_header
from compat.coverage import coverage_report
from compat.report import build_results, generate
from compat.report_enhance import build
from compat.report_browser import ReportBrowser
from compat.report_store import unpack
from test_v12 import installed, inventory
from test_report_enhancement import FixtureGuard


def symbol(name='api', kind='FUNC', binding='GLOBAL', visibility='DEFAULT', size=4):
    return dict(name=name, type=kind, binding=binding, visibility=visibility,
                size=size, value=4096, section='12')


def elf(path='/bin/app', **kwargs):
    value = dict(path=path, complete=True, export_inventory_complete=True,
                 resolution_metadata_complete=True, type='EXEC', machine='Advanced Micro Devices X86-64',
                 **{'class': 'ELF64'}, endianness="2's complement, little endian", exports=[], imports=[], needed=[],
                 execution_metadata=dict(mode='0o755', security_metadata_complete=True, has_file_capabilities=False))
    return value | kwargs


def header(path, text):
    return dict(path=path, sha256='synthetic', evidence=['evidence/header.txt'], **parse_header(text))


class HeaderFixTests(Environment):
    def manifest(self, headers=(), complete=True):
        return self.blank() | dict(public_headers=list(headers), collection_complete=complete,
                                   header_inventory_complete=complete, header_include_roots=['/usr/include'])

    def test_fix01_incomplete_header_absence(self):
        a = self.manifest([header('/usr/include/api.h', 'int api(void);')])
        b = self.manifest(complete=False)
        b['limitations'] = [dict(dimension='filesystem', component='*', reason='Directory traversal failed')]
        self.assertEqual(compare_api(a, b)[0]['status'], 'UNKNOWN')

    def test_header_real_deletion_and_failed_collection_controls(self):
        a = self.manifest([header('/usr/include/api.h', 'int api(void);')])
        self.assertEqual(compare_api(a, self.manifest())[0]['status'], 'INCOMPATIBLE')
        for dim, path in [('api', '/usr/include/api.h'), ('filesystem', '*'), ('headers', '/usr/include/api.h')]:
            b = self.manifest(); b['limitations'] = [dict(dimension=dim, component=path, reason='tool failed')]
            self.assertEqual(compare_api(a, b)[0]['status'], 'UNKNOWN')
        b = self.manifest(); b.pop('header_inventory_complete')
        self.assertEqual(compare_api(a, b)[0]['status'], 'UNKNOWN')

    def test_fix02_unconditional_reexport(self):
        a = self.manifest([header('/usr/include/api.h', 'int api(void);')])
        b = self.manifest([header('/usr/include/api.h', '#include "detail.h"'), header('/usr/include/detail.h', 'int api(void);')])
        row = next(f for f in compare_api(a, b) if f['interface'] == 'api')
        self.assertEqual(row['status'], 'COMPATIBLE')
        self.assertEqual(row['declaration_reachability']['state'], 'PROVEN_PRESENT')

    def test_true_declaration_removal_and_changed_signature(self):
        a = self.manifest([header('/usr/include/api.h', 'int api(void);')])
        b = self.manifest([header('/usr/include/api.h', '')])
        row = next(f for f in compare_api(a, b) if f['interface'] == 'api')
        self.assertEqual((row['status'], row['declaration_reachability']['state']), ('INCOMPATIBLE', 'PROVEN_ABSENT'))
        b = self.manifest([header('/usr/include/api.h', '#include "detail.h"'), header('/usr/include/detail.h', 'double api(void);')])
        self.assertEqual(next(f for f in compare_api(a, b) if f['interface'] == 'api')['status'], 'UNKNOWN')

    def test_conditional_cycle_missing_parse_failure_and_unrelated_name(self):
        a = self.manifest([header('/usr/include/api.h', 'int api(void);')])
        cases = [
            [header('/usr/include/api.h', '#if FEATURE\n#include "detail.h"\n#endif'), header('/usr/include/detail.h', 'int api(void);')],
            [header('/usr/include/api.h', '#include "detail.h"'), header('/usr/include/detail.h', '#include "api.h"\nint api(void);')],
            [header('/usr/include/api.h', '#include "missing.h"')],
            [header('/usr/include/api.h', '#include "detail.h"'), header('/usr/include/detail.h', 'int api(void);\nmalformed(')],
            [header('/usr/include/api.h', ''), header('/usr/include/unrelated.h', 'int api(void);')],
            [header('/usr/include/api.h', '#include HEADER')],
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                row = next(f for f in compare_api(a, self.manifest(headers)) if f['interface'] == 'api')
                # A declaration in an unrelated file alone must not establish compatibility.
                self.assertNotEqual(row['status'], 'COMPATIBLE')
                if headers[0]['includes'] or headers[0]['conditions'] or 'HEADER' in headers[0]['tokens']:
                    self.assertEqual(row['status'], 'UNKNOWN')

    def test_collection_records_header_domain_failures(self):
        root = self.base / 'image'; (root / 'usr/include').mkdir(parents=True)
        (root / 'usr/include/a.h').write_text('int api(void);')
        image = Image(root, self.workspace, self.tools, 'baseline')
        good = collect(image, 'fixture', 'baseline', 'quick', self.tools, self.workspace)
        self.assertTrue(good['header_inventory_complete'])
        (root / 'usr/include/a.h').write_bytes(b'not a header\0')
        bad = collect(image, 'fixture', 'baseline', 'quick', self.tools, self.workspace)
        self.assertFalse(bad['header_inventory_complete'])

    def test_transitive_and_angle_include_require_recorded_roots(self):
        a = self.manifest([header('/usr/include/api.h', 'int api(void);')])
        b = self.manifest([header('/usr/include/api.h', '#include <detail.h>'),
                           header('/usr/include/detail.h', '#include "leaf.h"'),
                           header('/usr/include/leaf.h', 'int api(void);')])
        get = lambda: next(f for f in compare_api(a, b) if f['interface'] == 'api')
        self.assertEqual(get()['status'], 'COMPATIBLE')
        b['header_include_roots'] = []
        self.assertEqual(get()['declaration_reachability']['state'], 'POSSIBLE_MIGRATION')
        self.assertEqual(get()['status'], 'UNKNOWN')

    def test_incomplete_baseline_or_macros_never_prove_equivalence(self):
        a = self.manifest([header('/usr/include/api.h', '#include "types.h"\nint api(void);')])
        b = self.manifest([header('/usr/include/api.h', '#include "detail.h"'), header('/usr/include/detail.h', 'int api(void);')])
        self.assertEqual(next(f for f in compare_api(a, b) if f['interface'] == 'api')['status'], 'UNKNOWN')
        for text in ('#define api other\nint api(void);', 'typedef int T;\nT api(void);', 'int api(void);\n#define FLAG 1', 'int api(void);\nint api(int);'):
            b['public_headers'][1] = header('/usr/include/detail.h', text)
            self.assertEqual(next(f for f in compare_api(self.manifest([header('/usr/include/api.h', 'int api(void);')]), b) if f['interface'] == 'api')['status'], 'UNKNOWN')

    def test_unrelated_collection_error_does_not_mask_true_removal(self):
        a = self.manifest([header('/usr/include/api.h', 'int api(void);')]); b = self.manifest()
        b['limitations'] = [dict(dimension='security', component='/etc/policy', reason='unreadable')]
        self.assertEqual(compare_api(a, b)[0]['status'], 'INCOMPATIBLE')

    def test_oversize_decode_failure_and_broken_header_link(self):
        root = self.base / 'image'; (root / 'usr/include').mkdir(parents=True)
        path = root / 'usr/include/api.h'
        for value in (b'\xff int api(void);', b' ' * 20):
            path.write_bytes(value); self.config['analysis']['max_text_bytes'] = 16
            got = collect(Image(root, self.workspace, self.tools, 'baseline'), 'fixture', 'baseline', 'quick', self.tools, self.workspace)
            self.assertFalse(got['header_inventory_complete'])
        path.unlink(); path.symlink_to('absent.h')
        got = collect(Image(root, self.workspace, self.tools, 'baseline'), 'fixture', 'baseline', 'quick', self.tools, self.workspace)
        self.assertFalse(got['header_inventory_complete'])

    def test_unknown_xattrs_do_not_establish_normal_execution_context(self):
        root = self.base / 'image'; (root / 'bin').mkdir(parents=True)
        (root / 'bin/app').write_bytes(b'plain text fixture')
        with patch('compat.collect.os.listxattr', side_effect=OSError('unreadable')):
            m = collect(Image(root, self.workspace, self.tools, 'baseline'), 'fixture', 'baseline', 'quick', self.tools, self.workspace)
        record = next(f for f in m['filesystem'] if f['path'] == '/bin/app')
        self.assertFalse(record['security_metadata_complete'])
        self.assertNotIn('has_file_capabilities', record)


class ExportFixTests(Environment):
    def compare(self, old, new):
        return compare_elf(self.blank() | {'elf_objects': [old]}, self.blank() | {'elf_objects': [new]})

    def test_fix03_partial_exports_do_not_prove_absence(self):
        old = elf('/lib/a.so', type='DYN', exports=[symbol('api@@V1')])
        new = elf('/lib/a.so', type='DYN', export_inventory_complete=False)
        self.assertTrue(all(f['status'] != 'INCOMPATIBLE' for f in self.compare(old, new)))

    def test_complete_exports_keep_real_failures_and_observed_changes(self):
        for kind in ('FUNC', 'OBJECT', 'TLS'):
            for binding in ('GLOBAL', 'WEAK'):
                old = elf('/lib/a.so', type='DYN', exports=[symbol('api@@V1', kind, binding)])
                new = elf('/lib/a.so', type='DYN')
                self.assertTrue(any(f['status'] == 'INCOMPATIBLE' for f in self.compare(old, new)))
        old = elf('/lib/a.so', exports=[symbol(kind='OBJECT')])
        new = elf('/lib/a.so', export_inventory_complete=False, exports=[symbol(kind='OBJECT', size=8)])
        self.assertTrue(any(f['interface'] == 'api:size' and f['status'] == 'INCOMPATIBLE' for f in self.compare(old, new)))
        new['exports'][0]['visibility'] = 'PROTECTED'
        self.assertTrue(any(f['interface'] == 'api:visibility' and f['status'] == 'UNKNOWN' for f in self.compare(old, new)))

    def test_missing_export_marker_never_infers_inventory(self):
        old = elf('/lib/a.so', exports=[symbol()]); new = elf('/lib/a.so'); new.pop('export_inventory_complete')
        self.assertTrue(all(f['status'] != 'INCOMPATIBLE' for f in self.compare(old, new)))

    def test_readelf_advertised_rows_warning_failure_and_no_dynsym(self):
        file = self.base / 'dummy'; file.write_bytes(b'ELF fixture, never executed')
        text = """ELF Header:
  Class: ELF64
  Data: 2's complement, little endian
  Type: DYN (Shared object file)
  Machine: Advanced Micro Devices X86-64
Dynamic section at offset 0x100 contains 1 entries:
Symbol table '.dynsym' contains 2 entries:
 Num: Value Size Type Bind Vis Ndx Name
 0: 0000000000000000 0 NOTYPE LOCAL DEFAULT UND
 1: 0000000000001000 4 FUNC GLOBAL DEFAULT 12 api@@V1

Version definition section '.gnu.version_d' contains 1 entry:
  0x001c: Rev: 1 Flags: none Index: 2 Cnt: 1 Name: V1

"""
        result = dict(returncode=0, stdout=text, stdout_truncated=False, stderr='', error='', stdout_evidence='evidence/rows.txt', stderr_evidence='evidence/errors.txt')
        for change, expected in [({}, True), ({'stdout': text.replace('2 entries:', '3 entries:')}, False),
                                 ({'stderr': 'warning'}, False), ({'returncode': 1}, False), ({'stdout_truncated': True}, False),
                                 ({'stderr_truncated': True}, False), ({'error': 'timeout'}, False),
                                 ({'stdout': text.replace("contains 1 entry:", "contains 2 entries:")}, False),
                                 ({'stdout': text.replace('Name: V1', 'Name: OTHER')}, False)]:
            with patch.object(self.tools, 'path', return_value='/synthetic/readelf'), patch.object(self.tools, 'run', return_value=result | change):
                got = collect_elf(file, '/lib/a.so', self.tools, 'static')
            self.assertEqual(got['export_inventory_complete'], expected)
            self.assertEqual(got['exports'][0]['name'], 'api@@V1')
        with patch.object(self.tools, 'path', return_value='/synthetic/readelf'), patch.object(self.tools, 'run', return_value=result | {'stdout': text.split('Dynamic section')[0].replace('DYN (Shared object file)', 'REL (Relocatable file)')}):
            got = collect_elf(file, '/rel.o', self.tools, 'static')
        self.assertFalse(got['export_inventory_complete'])
        self.assertEqual(got['export_inventory_status'], 'NOT_APPLICABLE')

    def test_inventory_gaps_cannot_earn_coverage_or_identical_credit(self):
        a = self.blank() | {'elf_objects': [elf('/lib/a.so', type='DYN')]}
        b = copy.deepcopy(a); b['elf_objects'][0]['export_inventory_complete'] = False
        fs = compare_elf(a, b)
        self.assertFalse(any(f['status'] == 'IDENTICAL' for f in fs))
        self.assertEqual(coverage_report(a, b, fs, [], [], self.config)[0]['abi']['verified'], 0)

    def test_new_fields_roundtrip_validate_and_old_fields_stay_unknown(self):
        manifest = self.blank() | dict(schema_version='1.2', elf_objects=[elf()], header_inventory_complete=True)
        path = self.base / 'manifest.json'
        write_json(path, manifest); self.assertTrue(read_manifest(path)['elf_objects'][0]['export_inventory_complete'])
        manifest['elf_objects'][0]['export_inventory_complete'] = 'yes'; write_json(path, manifest)
        with self.assertRaises(InputError): read_manifest(path)
        manifest['elf_objects'][0].pop('export_inventory_complete'); write_json(path, manifest)
        self.assertNotIn('export_inventory_complete', read_manifest(path)['elf_objects'][0])
        manifest['header_inventory_complete'] = 1; write_json(path, manifest)
        with self.assertRaises(InputError): read_manifest(path)

    @unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'Needs native GCC/binutils')
    def test_native_elf_types_versions_visibility_and_cache_context(self):
        root = self.base / 'root'; (root / 'lib').mkdir(parents=True)
        source = self.base / 'a.c'; source.write_text('int data=1; __thread int tls; __attribute__((weak)) int weak(void){return 1;} __attribute__((visibility("hidden"))) int hidden(void){return 1;} int api(void){return data;}')
        version = self.base / 'v.map'; version.write_text('V1 {global: api; data; tls; weak; local:*;};')
        lib = root / 'lib/a.so'
        subprocess.run(['gcc', '-shared', '-fPIC', str(source), '-Wl,--version-script=' + str(version), '-o', str(lib)], check=True, capture_output=True)
        got = collect_elf(lib, '/lib/a.so', self.tools, 'static')
        self.assertTrue(got['export_inventory_complete']); self.assertTrue(got['resolution_metadata_complete'])
        self.assertTrue({'FUNC', 'OBJECT', 'TLS'} <= {s['type'] for s in got['exports']})
        self.assertTrue(any(s['binding'] == 'WEAK' for s in got['exports']))
        self.assertFalse(any(s['name'] == 'hidden' for s in got['exports']))
        reloc = self.base / 'a.o'; subprocess.run(['gcc', '-c', str(source), '-o', str(reloc)], check=True, capture_output=True)
        self.assertEqual(collect_elf(reloc, '/a.o', self.tools, 'static')['export_inventory_status'], 'NOT_APPLICABLE')
        cache = self.base / 'cache'
        before = collect(Image(root, self.workspace, self.tools, 'baseline'), 'fixture', 'baseline', 'static', self.tools, self.workspace, cache)
        lib.chmod(0o4755)
        after = collect(Image(root, self.workspace, self.tools, 'baseline'), 'fixture', 'baseline', 'static', self.tools, self.workspace, cache)
        self.assertNotEqual(before['elf_objects'][0]['execution_metadata']['mode'], after['elf_objects'][0]['execution_metadata']['mode'])
        self.assertEqual(after['elf_objects'][0]['exports'], before['elf_objects'][0]['exports'])
        # Merely collecting the unexecuted executable's header does not establish dynsym.
        main = self.base / 'main.c'; main.write_text('int main(void){return 0;}')
        executable = self.base / 'app'; subprocess.run(['gcc', '-no-pie', str(main), '-o', str(executable)], check=True, capture_output=True)
        self.assertTrue(collect_elf(executable, '/app', self.tools, 'static')['export_inventory_complete'])

    def test_missing_readelf_keeps_inventory_unknown(self):
        path = self.base / 'elf'; path.write_bytes(b'\x7fELF' + bytes(20))
        with patch.object(self.tools, 'path', return_value=None):
            got = collect_elf(path, '/a', self.tools, 'static')
        self.assertFalse(got['export_inventory_complete']); self.assertFalse(got['resolution_metadata_complete'])


class LoaderFixTests(Environment):
    def manifest(self, objects=(), root=None, mode='0o755'):
        m = self.blank() | dict(elf_objects=list(objects), collection_complete=True,
            loader_environment=dict(model='glibc', cache_complete=True, environment_complete=True, symbol_scope='startup', namespace='base', default_dirs=['/lib'], library_path=[], cache={}))
        if root:
            m['filesystem'] = [dict(path=root['path'], type='file', mode=mode,
                                    security_metadata_complete=True, has_file_capabilities=False)]
        return m

    def needed(self, m, root, source=None):
        kwargs = {'consumer_manifest': source} if source is not None else {}
        return dependency_checks(m, 'baseline consumers on candidate', [root], **kwargs)

    def test_fix04_loaded_soname_reuse(self):
        root = elf(needed=['alias.so', 'real.so'])
        provider = elf('/lib/alias.so', type='DYN', soname='real.so')
        rows = self.needed(self.manifest([provider]), root)
        row = next(f for f in rows if f['check_id'] == 'DT_NEEDED:real.so')
        self.assertEqual(row['status'], 'COMPATIBLE')
        self.assertEqual(row['provider_path'], '/lib/alias.so')

    def test_reuse_is_per_root_namespace_and_reachable_provider_only(self):
        provider = elf('/private/alias.so', type='DYN', soname='real.so')
        root = elf(needed=['real.so'])
        self.assertTrue(any(f['status'] == 'INCOMPATIBLE' for f in self.needed(self.manifest([provider]), root)))
        root['needed'] = ['alias.so', 'real.so']; root['runpath'] = ['/private']
        m = self.manifest([provider]); m['loader_environment']['namespace'] = 'other'
        self.assertTrue(all(f['status'] != 'COMPATIBLE' for f in self.needed(m, root)))
        m = self.manifest([provider]); first = copy.deepcopy(root); second = elf('/bin/other', needed=['real.so'])
        rows = dependency_checks(m, 'baseline consumers on candidate', [first, second])
        self.assertTrue(any(f['root_consumer'] == '/bin/other' and f['status'] == 'INCOMPATIBLE' for f in rows))

    def test_reuse_cannot_grant_abi_or_incomplete_metadata_credit(self):
        root = elf(needed=['alias.so', 'real.so']); provider = elf('/lib/alias.so', type='DYN', soname='real.so')
        for changes in ({'machine': 'ARM'}, {'resolution_metadata_complete': False}, {'complete': False}, {'export_inventory_complete': False}):
            rows = self.needed(self.manifest([provider | changes]), root)
            self.assertTrue(all(f['status'] != 'COMPATIBLE' for f in rows))
        missing = self.needed(self.manifest(), elf(needed=['absent.so']))
        self.assertEqual(missing[0]['status'], 'INCOMPATIBLE')

    def test_missing_export_marker_cannot_prove_linker_symbol_absence(self):
        root = elf(needed=['a.so'], imports=[symbol('removed')])
        provider = elf('/lib/a.so', type='DYN'); provider.pop('export_inventory_complete')
        rows = self.needed(self.manifest([provider]), root)
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in rows))

    def test_fix05_source_mode_not_candidate_mode(self):
        root = elf(needed=['private.so']); provider = elf('/opt/private.so', type='DYN')
        source = self.manifest(root=root, mode='0o4755'); candidate = self.manifest([provider], root, '0o755')
        candidate['loader_environment']['library_path'] = ['/opt']
        source['elf_objects'] = [root]
        rows = [f for f in compare_static(source, candidate, self.config)
                if f['dimension'] == 'linking' and 'baseline consumers on candidate' in f['interface']]
        self.assertTrue(all(f['status'] != 'COMPATIBLE' for f in rows))

    def test_mode_missing_capabilities_setgid_and_reverse_context(self):
        root = elf(needed=['lib.so']); provider = elf('/lib/lib.so', type='DYN')
        candidate = self.manifest([provider], root, '0o4755')
        normal = self.manifest(root=root)
        self.assertTrue(all(f['status'] == 'COMPATIBLE' for f in self.needed(candidate, root, normal)))
        for changes in ({'mode': '0o2755'}, {'mode': None}, {'security_metadata_complete': False}, {'has_file_capabilities': True}):
            source = copy.deepcopy(normal); source['filesystem'][0].update(changes)
            self.assertTrue(all(f['status'] != 'COMPATIBLE' for f in self.needed(candidate, root, source)))
        unknown_root = copy.deepcopy(root); unknown_root.pop('execution_metadata')
        self.assertTrue(all(f['status'] != 'COMPATIBLE' for f in self.needed(candidate, unknown_root)))

    def test_compare_static_passes_baseline_context(self):
        root = elf(needed=['lib.so']); provider = elf('/lib/lib.so', type='DYN')
        a = self.manifest([root], root, '0o4755'); b = self.manifest([provider], root)
        fs = compare_static(a, b, self.config)
        self.assertFalse(any(f['dimension'] == 'linking' and 'baseline consumers' in f['interface'] and f['status'] == 'COMPATIBLE' for f in fs))

    def test_unknown_first_load_cannot_later_become_verified_alias(self):
        root = elf(needed=['alias.so', 'real.so'], runpath=['$UNKNOWN', '/lib'])
        rows = self.needed(self.manifest([elf('/lib/alias.so', type='DYN', soname='real.so')]), root)
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in rows))

    def test_absolute_needed_does_not_match_bare_soname(self):
        root = elf(needed=['alias.so', '/elsewhere/real.so'])
        rows = self.needed(self.manifest([elf('/lib/alias.so', type='DYN', soname='real.so')]), root)
        self.assertEqual(next(f for f in rows if f['check_id'] == 'DT_NEEDED:/elsewhere/real.so')['status'], 'INCOMPATIBLE')

    def test_isolated_dso_cannot_prove_missing_library_without_caller_scope(self):
        rows = self.needed(self.manifest(), elf('/lib/plugin.so', type='DYN', needed=['real.so']))
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in rows))

    def test_interpreter_soname_is_already_loaded_but_other_process_is_not(self):
        loader = elf('/special/ld.so', type='DYN', soname='ld.so', exports=[symbol('loader_api')])
        root = elf(interpreter=loader['path'], needed=['ld.so'], imports=[symbol('loader_api')])
        rows = self.needed(self.manifest([loader]), root)
        self.assertTrue(all(f['status'] == 'COMPATIBLE' for f in rows))

    def test_reused_provider_keeps_version_import_and_root_role_evidence(self):
        root = elf(needed=['alias.so', 'real.so'], imports=[symbol('api@V1')])
        provider = elf('/lib/alias.so', type='DYN', soname='real.so', exports=[symbol('api@@V1')], version_definitions=[dict(name='V1')])
        root['version_requirements'] = [dict(file='real.so', name='V1', flags='none')]
        rows = self.needed(self.manifest([provider]), root)
        self.assertTrue(all(f['status'] == 'COMPATIBLE' for f in rows))
        self.assertTrue(all(f['root_consumer_image'] == 'baseline' for f in rows))
        provider['exports'] = []; provider['version_definitions'] = []
        rows = self.needed(self.manifest([provider]), root)
        self.assertTrue(any(f['check_id'] == 'version:real.so:V1' and f['status'] == 'INCOMPATIBLE' for f in rows))
        self.assertTrue(any(f['check_id'] == 'import:api@V1' and f['status'] == 'INCOMPATIBLE' for f in rows))

    def test_native_candidate_uses_own_mode_and_metadata_unknown_is_explicit(self):
        root = elf(needed=['a.so']); provider = elf('/lib/a.so', type='DYN')
        normal = self.manifest([root, provider], root)
        self.assertTrue(all(f['status'] == 'COMPATIBLE' for f in dependency_checks(normal, 'candidate')))
        normal['filesystem'][0]['mode'] = '0o4755'
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in dependency_checks(normal, 'candidate') if f['root_consumer'] == root['path']))

    def test_source_symlink_and_missing_source_metadata_do_not_borrow_candidate(self):
        root = elf(needed=['a.so']); candidate = self.manifest([elf('/lib/a.so', type='DYN')], root)
        source = self.manifest(root=root, mode='0o4755')
        source['filesystem'][0]['path'] = '/real/app'
        source['filesystem'].append(dict(path='/bin/app', type='symlink', resolved='/real/app'))
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in self.needed(candidate, root, source)))
        self.assertTrue(all(f['status'] == 'UNKNOWN' for f in self.needed(candidate, root, self.manifest())))

    def test_duplicate_soname_obeys_proven_load_order(self):
        root = elf(needed=['a.so', 'b.so', 'shared.so'])
        providers = [elf('/lib/' + n + '.so', type='DYN', soname='shared.so') for n in ('a', 'b')]
        row = next(f for f in self.needed(self.manifest(providers), root) if f['check_id'] == 'DT_NEEDED:shared.so')
        self.assertEqual((row['status'], row['provider_path']), ('COMPATIBLE', '/lib/a.so'))
        root['needed'] = ['b.so', 'a.so', 'shared.so']
        row = next(f for f in self.needed(self.manifest(providers), root) if f['check_id'] == 'DT_NEEDED:shared.so')
        self.assertEqual(row['provider_path'], '/lib/b.so')


class PipelineFixTests(Environment):
    def test_fixed_findings_survive_frozen_report_contract(self):
        a = self.blank() | dict(schema_version='1.2', header_inventory_complete=True, header_include_roots=[])
        b = copy.deepcopy(a)
        a['public_headers'] = [header('/usr/include/api.h', 'int api(void);')]
        b['public_headers'] = [header('/usr/include/api.h', '#include "detail.h"'), header('/usr/include/detail.h', 'int api(void);')]
        a['elf_objects'] = [elf('/lib/lib.so', type='DYN', exports=[symbol('removed'), symbol('data', 'OBJECT')])]
        b['elf_objects'] = [elf('/lib/lib.so', type='DYN', export_inventory_complete=False, exports=[symbol('data', 'OBJECT', size=8)])]
        for m in (a, b):
            inventory(m, [installed('library', ['/lib/lib.so', '/usr/include/api.h', '/usr/include/detail.h'])])
        fs = compare_static(a, b, self.config)
        gap = finding('api', '/unassigned', 'SDK unavailable', None, None)
        fs.append(gap)
        result = build_results(a, b, fs, [], [], self.config)
        (self.output / 'evidence/header.txt').write_text('Synthetic header evidence; no target execution')
        generate(self.output, a, b, result, self.config)
        hashes = lambda: {str(p.relative_to(self.output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.output.rglob('*') if p.is_file()}
        before = hashes(); output = self.base / 'enhanced'
        metrics = build(self.output, output, FixtureGuard)
        browser = ReportBrowser(output)
        self.assertEqual(metrics['status'], 'PASS')
        self.assertEqual(before, hashes())
        db = sqlite3.connect(output / 'report-index.sqlite')
        self.addCleanup(db.close)
        stored = {r[0]: unpack(r[1]) for r in db.execute('SELECT id,payload FROM findings')}
        self.assertEqual(stored, {f['id']: f for f in result['findings']})
        with (output / 'finding-index.csv').open() as stream:
            self.assertEqual({r['id'] for r in csv.DictReader(stream)}, set(stored))
        row = browser.query('packages', {'q': ['library'], 'side': ['baseline'], 'limit': ['1'], 'sort': ['func']})
        self.assertEqual(row['total'], 1)
        package_id = row['rows'][0]['package_id']
        candidate_summary = browser.query('packages', {'side': ['candidate']})['rows'][0]
        self.assertFalse(candidate_summary['symbol_inventory_complete'])
        self.assertIsNone(candidate_summary['counts']['func'])
        self.assertEqual(candidate_summary['observed_counts']['object'], 1)
        self.assertTrue(browser.query('package', {'side': ['baseline'], 'id': [package_id]}))
        selected = browser.query('findings', {'package': [package_id], 'side': ['baseline'], 'status': ['INCOMPATIBLE']})
        self.assertTrue(any(r['interface'] == 'data:size' for r in selected['rows']))
        moved = next(f for f in result['findings'] if f['interface'] == 'api')
        self.assertEqual(browser.query('finding', {'id': [moved['id']]})['declaration_reachability']['state'], 'PROVEN_PRESENT')
        self.assertEqual(db.execute('SELECT count(*) FROM unassigned WHERE id=?', (gap['id'],)).fetchone()[0], 1)
        self.assertTrue((output / 'index.html').is_file())
