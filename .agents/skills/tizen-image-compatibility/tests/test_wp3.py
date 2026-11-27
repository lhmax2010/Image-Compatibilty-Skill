"""WP-3 report volume, context isolation and tool limits with offline fixtures."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
from unittest.mock import patch

from test_framework import Environment, SKILL
from test_static_fixes import elf, symbol
from test_report_enhancement import FixtureGuard
from test_wp2 import execute, prerequisite
from compat.collect import collect
from compat.compare import compare_static, finalize
from compat.core import InputError, finding, validate_config
from compat.images import Image
from compat.linker import check_import, dependency_checks
from compat.linking_details import LinkingDetails
from compat.report import build_results, generate
from compat.report_enhance import build
from compat.requirements import check_available_set
from tizen_compat import main


LOADER = {'model': 'glibc', 'cache_complete': True, 'environment_complete': True,
          'symbol_scope': 'startup', 'namespace': 'base', 'library_path': [],
          'default_dirs': ['/lib'], 'cache': {}}


class WP3Tests(Environment):
    def tool(self, name, env=None):
        binary = prerequisite(name, env)
        if binary:
            return binary
        if os.getenv('COMPAT_RELEASE_CI') == '1':
            self.fail(f'Missing required fixture tool {name}')
        self.skipTest(f'{name} unavailable')

    def scan(self, root, label='baseline'):
        return collect(Image(root, self.workspace, self.tools, label), label, label,
                       'static', self.tools, self.workspace)

    def test_t10_real_libc_and_loader_scale(self):
        gcc, readelf = self.tool('gcc'), self.tool('readelf')
        root = self.base / 'rootfs'
        (root/'bin').mkdir(parents=True)
        (root/'lib').mkdir()
        text = self.base/'main.c'
        text.write_text('extern int puts(const char *); void _start(void) { puts("fixture"); }\n')
        first = root/'bin/app-000'
        execute(gcc, '-nostdlib', '-no-pie', text, '-lc', '-o', first)
        interpreter = re.search(r'Requesting program interpreter: ([^\]]+)',
                                execute(readelf, '-lW', first).stdout)[1]
        target = root / interpreter.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(interpreter, target)
        libc = Path(execute(gcc, '-print-file-name=libc.so.6').stdout.strip())
        shutil.copyfile(libc, root/'lib/libc.so.6')
        for i in range(1, 500):
            os.link(first, root/f'bin/app-{i:03d}')
        self.config['analysis']['modes'] = ['linking']
        self.config['loader']['environments'] = {'baseline': LOADER, 'candidate': LOADER}
        source = self.scan(root)
        roots = [x for x in source['elf_objects'] if x['path'].startswith('/bin/app-')]
        shared = [x for x in source['elf_objects'] if x not in roots]
        self.assertEqual(len(roots), 500)
        self.assertTrue(all(x['execution_metadata']['security_metadata_complete'] is True for x in roots))
        self.assertEqual(source['security_interfaces'], [])
        prior = None
        if old := os.getenv('WP3_BASELINE_LINKER'):
            spec = importlib.util.spec_from_file_location('compat.wp3_prior_linker', old)
            prior = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(prior)
        counts = []
        for count in (5, 20, 80, 500):
            with self.subTest(count=count):
                image = source | {'elf_objects': roots[:count] + shared}
                with patch('compat.linker.check_import', wraps=check_import) as checks:
                    rows = dependency_checks(image, 'fixture', roots[:count], consumer_manifest=image)
                counts.append(len(rows))
                imports = [f for f in rows if f['consumer_path'] == '/lib/libc.so.6'
                           and f['check_id'].startswith('import:') and f['roots']['count'] == count]
                self.assertTrue(imports, 'No shared libc import relation found')
                self.assertTrue(all(len(f['roots']['examples']) == min(20, count) for f in imports))
                puts = [f for f in rows if f['component'].startswith('/bin/app-')
                        and f['check_id'].startswith('import:puts@')]
                self.assertEqual(len(puts), count)
                self.assertTrue(all(f['status'] == 'COMPATIBLE' and f['roots']['count'] == 1 for f in puts))
                # One evaluation per emitted import context, independent of relation size.
                self.assertEqual(checks.call_count, sum(f['check_id'].startswith('import:') for f in rows))
                detail_csv = self.base/f'linking-{count}.csv'
                with LinkingDetails(self.base/f'linking-{count}.sqlite') as details:
                    compact = dependency_checks(image, 'fixture', roots[:count], consumer_manifest=image, details=details)
                    compact.extend(details.finish(detail_csv))
                with detail_csv.open() as stream:
                    detail = list(csv.DictReader(stream))
                expected_rows = {f['id']:f for f in rows if f['check_id'].startswith(('import:', 'version:', 'DT_NEEDED:', 'copy relocation:'))
                                 or f['status']=='INCOMPATIBLE'}
                self.assertSetEqual({row['id'] for row in detail}, set(expected_rows))
                self.assertTrue(all(int(row['roots_count']) == expected_rows[row['id']]['roots']['count'] for row in detail))
                self.assertTrue({row['anchor_finding_id'] for row in detail} <= {f['id'] for f in compact})
                groups = [f for f in compact if f.get('aggregated_checks')]
                self.assertEqual(len(groups), len({(f['consumer_image'], f['consumer_path'], f['resolution'],
                                                    json.dumps(f['search_context'], sort_keys=True)) for f in groups}))
                self.assertTrue(all(f['status']=='COMPATIBLE' for f in compact if f.get('aggregated_checks')
                                    and f['consumer_path'].startswith('/bin/app-')))
                print(f'WP3B_LINKING_SCALE roots={count} before={len(rows)} after={len(compact)} detail={len(detail)}')
                old_count = len(prior.dependency_checks(image, 'fixture', roots[:count], consumer_manifest=image)) if prior else None
                print(f'WP3_LINKING_SCALE roots={count} old={old_count} new={len(rows)}')
        self.assertEqual(counts[3]-counts[2], 7*(counts[2]-counts[1]))
        self.assertEqual(counts[2]-counts[1], 4*(counts[1]-counts[0]))

    def test_t10b_context_split_and_cycle(self):
        base = elf('/bin/a', needed=['addon.so', 'bridge.so'], runpath=['/opt/a'])
        other = elf('/bin/b', needed=['addon.so', 'bridge.so'], runpath=['/opt/b'])
        bridge = elf('/lib/bridge.so', type='DYN', soname='bridge.so', needed=['addon.so'])
        addon = elf('/opt/a/addon.so', type='DYN', soname='addon.so', needed=['bridge.so'])
        image = self.blank() | {'elf_objects':[bridge, addon], 'loader_environment':LOADER,
                                'filesystem_path_inventory_complete':True}
        rows = dependency_checks(image, 'test', [base, other])
        affected = [f for f in rows if f['component'] == bridge['path'] and f['check_id'] == 'DT_NEEDED:addon.so']
        self.assertEqual({f['status'] for f in affected}, {'COMPATIBLE', 'INCOMPATIBLE'})
        self.assertEqual(len(affected), 2)
        self.assertNotEqual(affected[0]['search_context'], affected[1]['search_context'])
        self.assertEqual({tuple(f['roots']['examples']) for f in affected}, {('/bin/a',), ('/bin/b',)})
        self.assertEqual(len({f['id'] for f in rows}), len(rows))
        self.assertTrue(any(f['component'] == addon['path'] and f['status'] == 'COMPATIBLE' for f in rows))

    def test_t10c_missing_profile_is_not_executed(self):
        self.config['analysis']['modes'] = ['linking']
        a = self.blank() | {'elf_objects':[elf(needed=['lib.so'], imports=[symbol('f')])]}
        b = self.blank()
        records = finalize(compare_static(a, b, self.config), self.config)
        linking = [f for f in records if f['dimension']=='linking']
        self.assertEqual({f['component'] for f in linking}, {'baseline', 'candidate'})
        self.assertEqual(len(linking), 2)
        self.assertTrue(all(f['reason_code']=='LOADER_ENV_MISSING' for f in linking))
        result = build_results(a, b, records, [], [], self.config) | {'scope':'RUNTIME_ROOTFS'}
        self.assertEqual({u['verification'] for u in result['coverage']['linking']['units']}, {'NOT_EXECUTED'})
        self.assertEqual(result['finding_integrity']['missing_reason_codes'], 0)
        generate(self.output, a, b, result, self.config)
        run = result['run_summary']['linking_summary']['LOADER_ENV_MISSING']
        self.assertEqual(run['count'], 2)
        self.assertEqual(set(run['example_finding_ids']), {f['id'] for f in linking})
        self.assertIn('Configure loader.environments', (self.output/'summary.md').read_text())
        self.config['ci']['strict'] = True
        strict = build_results(a, b, records, [], [], self.config)
        self.assertEqual(strict['quality_gate']['strict_status'], 'FAIL')

    def test_same_provider_path_in_different_images_keeps_distinct_contexts(self):
        source = elf('/lib/source.so', type='DYN', soname='source.so', needed=['common.so'], exports=[symbol('f')])
        target = source | {'exports':[symbol('f')]}
        common = elf('/lib/common.so', type='DYN', soname='common.so', imports=[symbol('f')])
        client = elf('/bin/client', type='DYN', needed=['source.so'])
        image = self.blank() | {'elf_objects':[target, common], 'loader_environment':LOADER,
                                'filesystem_path_inventory_complete':True}
        rows = dependency_checks(image, 'baseline consumers on candidate', [source, client])
        matches = [f for f in rows if f['component'] == common['path'] and f['check_id'] == 'import:f']
        self.assertEqual(len(matches), 2)
        self.assertEqual(len({f['id'] for f in matches}), 2)
        self.assertEqual({f['search_context']['symbol_scope'][0]['image'] for f in matches},
                         {'baseline', 'candidate'})

    def test_t_req_missing_soname_aggregates_only_its_dependents(self):
        consumer = elf('/consumer', needed=['libmissing.so.1', 'libother.so.1'],
            version_requirements=[{'file':'libmissing.so.1','name':'X_1'}],
            imports=[symbol(f'f{i}@X_1') | {'version_file':'libmissing.so.1'} for i in range(30)])
        missing = elf('/a', type='DYN', soname='libmissing.so.1',
            version_definitions=[{'name':'X_1'}], exports=[symbol(f'f{i}@@X_1') for i in range(30)])
        other = elf('/other', type='DYN', soname='libother.so.1')
        dictionaries = ({'/consumer':consumer, '/other':other}, {})
        owner = {path:(path, path) for path in ('/consumer', '/other', '/a')}
        for existed in (False, True):
            if existed:
                dictionaries[0]['/a'] = missing
            summary, rows = check_available_set(dictionaries, owner, dict.fromkeys(owner, '/component'),
                                                (True, True), self.output)
            anchor = next(row for row in rows if row['soname'] == 'libmissing.so.1')
            self.assertEqual(anchor['suppressed_dependents'], 31)
            self.assertEqual(anchor['reason_code'], 'NEEDED_SONAME_UNAVAILABLE' if existed else 'ALSO_UNSATISFIED_IN_BASELINE')
            self.assertEqual(summary['finding_count'], 33)
            self.assertEqual(summary['emitted_count'], 2)
            self.assertTrue(any(row['soname']=='libother.so.1' and row['status']=='INCOMPATIBLE' for row in rows))
            with (self.output/'requirement-findings.csv').open(newline='') as stream:
                details = list(csv.DictReader(stream))
            self.assertEqual(len(details), 33)
            self.assertEqual(sum(row['suppressed_by']==anchor['id'] for row in details), 31)
            self.assertTrue(all(row['soname']=='libmissing.so.1' for row in details if row['suppressed_by']))

    def test_indexed_truncated_roots_keep_observed_paths_and_unknown_union(self):
        row = finding('linking', '/lib/consumer.so', 'loader context', None, None)
        examples = [f'/bin/app{i:02d}' for i in range(20)]
        row.update(consumer_path='/lib/consumer.so', root_consumer=examples[0], root_consumer_image='baseline',
                   roots={'count':21, 'examples':examples}, search_context={'scope_proven':False})
        a, b = self.blank(), self.blank()
        result = build_results(a, b, [row], [], [], self.config) | {'scope':'RUNTIME_ROOTFS'}
        generate(self.output, a, b, result, self.config)
        indexed = self.base/'index'
        build(self.output, indexed, FixtureGuard)
        with sqlite3.connect(indexed/'report-index.sqlite') as db:
            summary, = db.execute('SELECT summary FROM groups').fetchone()
        group = json.loads(summary)
        self.assertEqual(group['observed_root_consumer_count'], 20)
        self.assertEqual(group['root_consumer_not_recorded_count'], 1)
        self.assertIsNone(group['affected_root_consumer_count'])

    def test_t08r_real_asan_and_minority_case(self):
        gcc, clang = self.tool('gcc'), self.tool('clang', 'WP1_CLANG')
        self.config['analysis']['modes'] = ['abi', 'elf']
        root1, root2 = self.base/'a', self.base/'b'
        root1.mkdir(); root2.mkdir()
        source = self.base/'api.c'
        source.write_text('int table[10]={1}; int keep(void){return 1;}\n'
                          '#ifndef REMOVE\nint removed(void){return 2;}\n#endif\n')
        for root, compiler, flags in ((root1, gcc, []), (root2, clang, ['-fsanitize=address', '-DREMOVE'])):
            execute(compiler, '-fPIC', '-c', *flags, source, '-o', root/'api.o')
            execute(gcc, '-shared', '-nostdlib', root/'api.o', '-o', root/'api.so')
            (root/'api.o').unlink()
        a, b = self.scan(root1), self.scan(root2, 'candidate')
        for extra in (0, 5):
            manifests = [m | {'elf_objects':m['elf_objects'] + [elf(f'/plain{i}', type='DYN')
                          for i in range(extra)]} for m in (a,b)]
            findings = finalize(compare_static(*manifests, self.config), self.config)
            result = build_results(*manifests, findings, [], [], self.config)
            self.assertEqual(result['comparison_validity'], 'COMPARABLE' if extra else 'CONFOUNDED')
            self.assertTrue(any(f['interface']=='removed' and f['status']=='INCOMPATIBLE'
                                and f['reason_code']=='EXPORT_REMOVED' for f in findings))
            self.assertEqual(result['finding_integrity']['missing_reason_codes'], 0)
            self.assertTrue(any(f['interface']=='table:size' and
                        (f['status'], f['severity'], f['reason_code'])==('UNKNOWN','MEDIUM','INSTRUMENTATION_MISMATCH')
                        for f in findings))
            if not extra:
                generate(self.output, a, b, result | {'scope':'RUNTIME_ROOTFS'}, self.config)
                self.assertIn('Comparison confounded', (self.output/'index.html').read_text())

    def test_t_timeout_reports_cleanup_and_blocks_objective(self):
        image = self.base/'image.sqsh'
        image.write_bytes(b'hsqs' + bytes(64))
        tool = self.base/'fake-unsquashfs'
        tool.write_text('#!/bin/sh\ncase "$1" in --version) exit 0;; esac\nsleep 30 &\nwait\n')
        tool.chmod(0o700)
        config = self.base/'timeout.yaml'
        config.write_text(f'analysis: {{extract_timeout_seconds: 1}}\ntools: {{unsquashfs: "{tool}"}}\n')
        output = self.base/'timeout-output'
        code = main(['--baseline', str(image), '--candidate', str(image), '--config', str(config),
                     '--output', str(output)])
        self.assertEqual(code, 3)
        run = json.loads((output/'run-summary.json').read_text())
        self.assertEqual(run['objective_completion'], 'BLOCKED')
        self.assertEqual(run['errors'][0]['reason_code'], 'TOOL_TIMEOUT')
        self.assertEqual(run['errors'][0]['tool'], tool.name)
        log = (output/'collection.log').read_text()
        self.assertRegex(log, r'"local_process_group_status"\s*:\s*"VERIFIED"')
        self.assertIn('TOOL_TIMEOUT', log)

    def test_t_meta_cap_is_per_archive(self):
        self.tool('rpm')
        repo = self.base/'repo'
        repo.mkdir()
        for name in ('big.rpm', 'good.rpm'):
            (repo/name).write_bytes(b'\xed\xab\xee\xdb')
        tool = self.base/'fake-rpm'
        tool.write_text(f'#!{sys.executable}\nimport sys\n'
                        "if sys.argv[-1].endswith('big.rpm'):\n    print('x'*8192)\n"
                        "else:\n    print('<rpmHeader><rpmTag name=\"Name\"><string>good</string></rpmTag>"
                        "<rpmTag name=\"Version\"><string>1</string></rpmTag>"
                        "<rpmTag name=\"Release\"><string>1</string></rpmTag>"
                        "<rpmTag name=\"Arch\"><string>noarch</string></rpmTag></rpmHeader>')\n")
        tool.chmod(0o700)
        self.config['rpm_payload'].update(mode='metadata', max_metadata_bytes=1024)
        self.config['tools']['rpm'] = str(tool)
        manifest = self.scan(repo)
        self.assertEqual(manifest['repository']['counts']['rpm_total'], 2)
        self.assertEqual(manifest['repository']['counts']['metadata_complete'], 1)
        error, = manifest['repository']['errors']
        self.assertEqual((error['archive'], error['reason_code'], error['tool']), ('big.rpm', 'OUTPUT_LIMIT', tool.name))

    def test_invalid_timeout_and_metadata_cap(self):
        for section, key, value in (('analysis','extract_timeout_seconds',0),
                ('analysis','rpmdb_timeout_seconds',1.5), ('analysis','abi_timeout_seconds',True),
                ('rpm_payload','max_metadata_bytes',1024**3+1)):
            with self.subTest(key=key), patch.dict(self.config[section], {key:value}):
                with self.assertRaisesRegex(InputError, key):
                    validate_config(self.config)
