"""Keep split DWARF discoverable without treating it as executable content."""
import re
import shutil
import subprocess
from pathlib import Path

from test_framework import Environment
from test_static_fixes import elf
from compat.compare import compare_elf
from compat.coverage import coverage_report
from compat.debuginfo import debug_source
from compat.elf import collect_elf, elf_runtime_role
from compat.images import Image
from compat.linker import dependency_checks


class DebugElfTests(Environment):
    def test_real_elf_sections_and_split_build_id(self):
        if not all(shutil.which(tool) for tool in ('gcc', 'objcopy', 'readelf')):
            self.skipTest('GNU GCC, objcopy and readelf are required for the native ELF fixture')
        root = self.base / 'image'
        debug_dir = root / 'usr/lib/debug'
        debug_dir.mkdir(parents=True)
        source = self.base / 'fixture.c'
        source.write_text('int main(void) { return 0; }\n')
        embedded = debug_dir / 'app.debug'
        split = root / 'debug-without-suffix'
        runtime = root / 'app'
        subprocess.run(['gcc', '-g', '-Wl,--build-id', str(source), '-o', str(embedded)], check=True)
        subprocess.run(['objcopy', '--only-keep-debug', str(embedded), str(split)], check=True)
        subprocess.run(['objcopy', '--strip-debug', str(embedded), str(runtime)], check=True)
        full, debug, stripped = (collect_elf(p, '/' + p.relative_to(root).as_posix(), self.tools, 'static')
                                 for p in (embedded, split, runtime))
        self.assertEqual([o['elf_runtime_role'] for o in (full, debug, stripped)],
                         ['RUNTIME_WITH_DEBUG', 'DEBUG_ONLY', 'RUNTIME'])
        self.assertTrue(debug['debug_info'])
        self.assertEqual(full['build_id'], debug['build_id'])
        bid = debug['build_id']
        by_id = debug_dir / '.build-id' / bid[:2] / (bid[2:] + '.debug')
        by_id.parent.mkdir(parents=True)
        shutil.copyfile(split, by_id)
        image = Image(root, self.workspace, self.tools, 'baseline')
        self.assertEqual(debug_source(stripped, image, [], self.tools)['kind'], 'split-build-id')
        self.assertEqual(debug_source(full, image, [], self.tools)['kind'], 'embedded')
        result = subprocess.run(['readelf', '-WhlS', str(split)], text=True, errors='replace',
                                capture_output=True, check=True)
        size = split.stat().st_size
        truncated = result.stdout.split('Key to Flags:')[0]
        self.assertEqual(elf_runtime_role(truncated, size, result.stderr), 'UNKNOWN')
        self.assertEqual(elf_runtime_role(result.stdout, 0), 'UNKNOWN')
        self.assertEqual(elf_runtime_role(result.stdout, size, 'unrecognized diagnostics'), 'UNKNOWN')
        self.assertTrue(all((self.output / Path(ref)).is_file() for ref in debug['evidence']))
        runtime_headers = subprocess.check_output(['readelf', '-WhlS', str(embedded)], text=True)
        # GNU readelf can print an unaligned GNU_STACK as bare 0 on LLD output.
        unaligned_stack, changed = re.subn(r'^( +GNU_STACK .*? )0x[0-9a-f]+ *$', r'\g<1>0', runtime_headers, flags=re.M)
        self.assertEqual(changed, 1)
        self.assertEqual(elf_runtime_role(unaligned_stack, embedded.stat().st_size), 'RUNTIME_WITH_DEBUG')

    def loader_case(self, provider_role='RUNTIME'):
        root = elf('/bin/app', interpreter='/lib/ld.so', elf_runtime_role='RUNTIME_WITH_DEBUG',
                   needed=['libapi.so'])
        loader = elf('/lib/ld.so', type='DYN', elf_runtime_role='RUNTIME')
        provider = elf('/lib/libapi.so', type='DYN', soname='libapi.so', elf_runtime_role=provider_role)
        image = self.blank() | dict(elf_objects=[root, loader, provider], collection_complete=True,
            loader_environment=dict(model='glibc', cache_complete=True, environment_complete=True,
                namespace='base', symbol_scope='startup', default_dirs=['/lib']))
        return image, root, loader, provider

    def test_split_debug_never_becomes_consumer_or_provider(self):
        image, root, _, provider = self.loader_case('DEBUG_ONLY')
        provider.update(needed=['broken-needed.so'], interpreter='/broken-loader.so')
        rows = dependency_checks(image, 'test')
        self.assertTrue(rows)
        self.assertFalse(any(row['root_consumer'] == provider['path'] or row['provider_path'] == provider['path']
                             for row in rows))
        need = next(row for row in rows if row['root_consumer'] == root['path'] and row['check_id'] == 'DT_NEEDED:libapi.so')
        self.assertEqual(need['status'], 'UNKNOWN')
        image['elf_objects'].remove(provider)
        need = next(row for row in dependency_checks(image, 'test') if row['check_id'] == 'DT_NEEDED:libapi.so')
        self.assertEqual(need['status'], 'INCOMPATIBLE')

    def test_unclassified_elf_still_observed_without_verification_credit(self):
        for role, expected in [('RUNTIME_WITH_DEBUG', 'COMPATIBLE'), ('UNKNOWN', 'UNKNOWN')]:
            with self.subTest(role=role):
                image, root, _, provider = self.loader_case(role)
                observed = next(row for row in dependency_checks(image, 'test')
                                if row['check_id'] == 'DT_NEEDED:libapi.so')
                self.assertEqual((observed['status'], observed['provider_path']), (expected, provider['path']))
                provider['elf_runtime_role'] = 'RUNTIME'
                root['elf_runtime_role'] = role
                observed = next(row for row in dependency_checks(image, 'test')
                                if row['check_id'] == 'DT_NEEDED:libapi.so')
                self.assertEqual(observed['status'], expected)

    def test_split_debug_interpreter_and_coverage(self):
        image, root, loader, provider = self.loader_case('DEBUG_ONLY')
        loader['elf_runtime_role'] = 'DEBUG_ONLY'
        rows = dependency_checks(image, 'baseline consumers on candidate')
        interp = next(row for row in rows if row['check_id'] == 'dynamic loader')
        self.assertEqual((interp['status'], interp['resolution']), ('UNKNOWN', 'unknown_loader_abi'))
        after = image | {'elf_objects': [root, loader, provider | {'needed': ['libextra.so'], 'soname': 'different.so'}]}
        self.assertFalse(any(f['component'] == provider['path'] and f['dimension'] == 'linking'
                             for f in compare_elf(image, after)))
        coverage, _ = coverage_report(image, after, rows, [], [], self.config)
        unit = next(u for u in coverage['linking']['units'] if u['interface'] == provider['path'])
        self.assertEqual(unit['status'], 'NOT_APPLICABLE')
        self.assertTrue(any(u['interface'] == provider['path'] + ':type-layout' for u in coverage['abi']['units']))
