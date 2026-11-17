"""Independent PR #2 regressions; synthetic reports only, no target execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_report_enhancement import fixture, symbol, FixtureGuard
from compat.core import finding
from compat.report import build_results, generate
from compat.report_enhance import build
from compat.report_store import Store, unpack
from compat.report_groups import build_groups
from compat.report_browser import ReportBrowser


class ReviewTests(unittest.TestCase):
    def test_size_type_uncertainty_and_type_changes_are_observations(self):
        from compat.report_symbols import size_difference
        for old, new in ((None, None), ('NOTYPE', 'NOTYPE'), ('FUNC', 'OBJECT'), ('FUNC', 'IFUNC')):
            self.assertEqual(size_difference({'type': old}, {'type': new}), 'SIZE_CHANGED_UNKNOWN')
        self.assertEqual(size_difference({'type': 'TLS'}, {'type': 'TLS'}), 'DATA_SIZE_CHANGED')

    def test_symbol_sizes_preserve_source_and_separate_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source'; source.mkdir()
            a, b, fs, config = fixture()
            exports = [symbol('code'), symbol('resolver', 'IFUNC'), symbol('data@@V1', 'OBJECT'),
                       symbol('tls', 'TLS'), symbol('unknown', 'NOTYPE'), symbol('multi')]
            a['elf_objects'][0]['exports'] = exports
            b['elf_objects'][0]['exports'] = copy.deepcopy(exports)
            for item in b['elf_objects'][0]['exports']:
                item['size'] = 8
            exports = [symbol('code'), symbol('resolver', 'IFUNC'), symbol('data@@V1', 'OBJECT'),
                       symbol('tls', 'TLS'), symbol('unknown', 'NOTYPE'), symbol('multi')]
            for m in (a, b):
                m['elf_objects'][0]['exports'] = copy.deepcopy(exports)
            for s in b['elf_objects'][0]['exports']: s['size'] = 8
            b['elf_objects'][0]['exports'][-1]['binding'] = 'WEAK'
            b['elf_objects'][0]['exports'][-1]['visibility'] = 'PROTECTED'
            for manifest in (a, b):
                next(e for e in manifest['elf_objects'] if e['path'] == '/usr/lib/alias.so')['exports'] = copy.deepcopy(manifest['elf_objects'][0]['exports'])
            path = a['elf_objects'][0]['path']
            original = finding('abi', path, 'data@@V1:size', 4, 8, 'INCOMPATIBLE', 'HIGH')
            original['evidence'] = ['evidence/data.txt']
            results = build_results(a, b, [original], [], [], config)
            generate(source, a, b, results, config)
            (source / 'evidence').mkdir(exist_ok=True)
            (source / 'evidence/data.txt').write_text('synthetic evidence')
            build(source, root / 'out', FixtureGuard)
            browser = ReportBrowser(root / 'out')
            import sqlite3
            with sqlite3.connect(root / 'out/report-index.sqlite') as db:
                rows = [json.loads(r[0]) for r in db.execute('SELECT row_json FROM differences')]
            expected = {'code': 'CODE_SIZE_CHANGED', 'resolver': 'CODE_SIZE_CHANGED',
                        'data': 'DATA_SIZE_CHANGED', 'tls': 'DATA_SIZE_CHANGED',
                        'unknown': 'SIZE_CHANGED_UNKNOWN', 'multi': 'CODE_SIZE_CHANGED'}
            for name, kind in expected.items():
                row = next(r for r in rows if r['symbol_name'] == name and 'SIZE_CHANGED' in r['difference_type'])
                self.assertEqual(row['difference_type'], kind)
                self.assertEqual([row[s + '_symbol_attributes']['size'] for s in ('gcc', 'llvm')], [4, 8])
                self.assertEqual(row['compatibility_status'], 'INCOMPATIBLE' if name == 'data' else 'UNKNOWN')
            data = next(r for r in rows if r['symbol_name'] == 'data')
            self.assertEqual(data['symbol_version'], 'V1')
            self.assertEqual(data['finding_ids'], [original['id']])
            self.assertIn('evidence/data.txt', data['evidence'])
            self.assertEqual({r['difference_type'] for r in rows if r['symbol_name'] == 'multi'},
                             {'CODE_SIZE_CHANGED', 'BINDING_CHANGED', 'VISIBILITY_CHANGED'})
            with sqlite3.connect(root / 'out/report-index.sqlite') as db:
                summary = json.loads(db.execute("SELECT summary FROM pairs WHERE baseline IS NOT NULL ORDER BY id").fetchall()[0][0])
                summaries = [json.loads(r[0]) for r in db.execute('SELECT summary FROM pairs')]
                changed = next(r for r in summaries if r['gcc_path'] == path)['observed_differences']
                self.assertEqual(changed['code_size_changes'], 3)
                self.assertEqual(changed['data_size_changes'], 2)
                self.assertEqual(changed['unknown_size_changes'], 1)
                self.assertEqual(changed['potential_abi_attribute_changes'], 3)
                if name == 'data':
                    self.assertEqual(row['compatibility_status'], 'INCOMPATIBLE')
                    self.assertEqual(row['finding_ids'], [original['id']])
                    self.assertIn('evidence/data.txt', row['evidence'])
                    self.assertEqual(row['symbol_version'], 'V1')
                else: self.assertEqual(row['compatibility_status'], 'UNKNOWN')
            multi = [r['difference_type'] for r in rows if r['symbol_name'] == 'multi']
            self.assertEqual(set(multi), {'CODE_SIZE_CHANGED', 'BINDING_CHANGED', 'VISIBILITY_CHANGED'})
            package = next(r for r in browser.query('packages', {'side': ['baseline']})['rows'] if r['observed_owned_elf_count'] == 2)
            stats = package['observed_differences']
            self.assertEqual(stats['code_size_changes'], 3)
            self.assertEqual(stats['data_size_changes'], 2)
            self.assertEqual(stats['unknown_size_changes'], 1)
            self.assertEqual(stats['potential_abi_attribute_changes'], 3)

    def group_fixture(self, root, paths, complete=True):
        store = Store(root, root, lambda: None)
        for i, path in enumerate(paths):
            f = finding('linking', '/lib/lib.so', 'import:f', 'f', None, 'UNKNOWN')
            f.update(id='fixture-' + str(i), consumer_path=path, consumer_image='baseline',
                     root_consumer='/bin/root', root_consumer_image='baseline', provider_path='/lib/provider.so')
            f['package_ownership'] = {
                'consumer_image': 'baseline',
                'consumer': {'status': 'COMPLETE' if complete else 'UNKNOWN', 'owners': ['same']},
                'root_consumer': {'status': 'COMPLETE', 'owners': ['same']},
                'candidate_provider': {'status': 'COMPLETE', 'owners': ['same']}}
            store._finding(f)
        build_groups(store)
        return store, json.loads(store.db.execute('SELECT summary FROM groups').fetchone()[0])

    def test_package_roles_are_image_qualified_and_non_additive(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, row = self.group_fixture(Path(tmp), ['/bin/app'])
            try:
                self.assertEqual(row['associated_package_count'], 2)
                self.assertEqual(row['affected_consumer_package_count'], 1)
                self.assertEqual(row['affected_root_package_count'], 1)
                self.assertEqual(row['provider_package_count'], 1)
                self.assertEqual(row['affected_package_count'], 2)  # legacy union preserved
                self.assertEqual(store.db.execute('SELECT count(*) FROM roles').fetchone()[0], 3)
                from compat.report_enhance import export
                import csv
                export(store)
                with (Path(tmp) / 'linking-findings-groups.csv').open() as stream:
                    exported = next(csv.DictReader(stream))
                for field in ('associated_package_count', 'affected_consumer_package_count',
                              'affected_root_package_count', 'provider_package_count'):
                    self.assertEqual(int(exported[field]), row[field])
            finally: store.db.close()

    def test_unknown_ownership_retains_observed_roles_without_credit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, row = self.group_fixture(Path(tmp), ['/bin/app'], False)
            try:
                self.assertIsNone(row['associated_package_count'])
                self.assertIsNone(row['affected_consumer_package_count'])
                self.assertEqual(row['observed_associated_package_count'], 2)
                self.assertEqual(row['observed_affected_consumer_package_count'], 1)
            finally: store.db.close()

    def test_invalid_consumer_paths_remain_unknown(self):
        for path in (None, '', 'relative', '/', '//bin/app', '/bin/../app', '/bin/app\x00x'):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as tmp:
                store, row = self.group_fixture(Path(tmp), [path, '/bin/app'])
                try:
                    self.assertIsNone(row['affected_elf_count'])
                    self.assertEqual(row['observed_direct_consumer_count'], 1)
                    self.assertEqual(row['direct_consumer_not_recorded_count'], 1)
                    self.assertEqual(store.db.execute('SELECT count(*) FROM findings').fetchone()[0], 2)
                finally: store.db.close()

    def test_evidence_collector_and_server_agree_on_symlink_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'evidence').mkdir()
            (root / 'outside.txt').write_text('outside evidence subtree')
            (root / 'evidence/safe.txt').write_text('safe')
            (root / 'evidence/escape').symlink_to('../outside.txt')
            store = Store(root, root, lambda: None)
            try:
                self.assertTrue(store.evidence_exists('evidence/safe.txt'))
                for ref in ('evidence/../outside.txt', 'evidence/escape', 'outside.txt'):
                    self.assertFalse(store.evidence_exists(ref), ref)
                from compat.report_io import evidence_path
                self.assertEqual(evidence_path(root, 'evidence/safe.txt'), root / 'evidence/safe.txt')
                for ref in ('evidence/escape', 'evidence/../outside.txt', '../outside.txt'):
                    with self.assertRaises(ValueError): evidence_path(root, ref)
            finally: store.db.close()
