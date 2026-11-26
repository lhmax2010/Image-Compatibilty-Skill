"""Report-only acceptance: source observations survive indexing and presentation."""
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compat.core import finding
from compat.compare import finalize
from compat.report import build_results, generate
from compat.report_enhance import build
from compat.report_io import ReportStream, ResourceGuard, ResourceLimit
from compat.report_browser import ReportBrowser
from compat.report_store import unpack

spec = importlib.util.spec_from_file_location('enhancement_benchmark', Path(__file__).parent / 'review' / 'benchmark_v12.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class FixtureGuard:
    """Small unit fixtures should run on hosts with less than the experiment's 100 GiB disk."""
    def __init__(self, output): self.peak_tree_rss = 0; self.last_snapshot = {}
    def check(self, force=False): pass


def symbol(name, kind='FUNC', **kwargs):
    return dict(name=name, type=kind, binding=kwargs.get('binding', 'GLOBAL'),
                visibility=kwargs.get('visibility', 'DEFAULT'), size=kwargs.get('size', 4))


def fixture():
    a, b, _, config = benchmark.fixture(2, 1)
    a['image']['name'] = '<img src=x onerror=alert(1)> & "image"'
    a['public_headers'] = []; b['public_headers'] = []
    a['packages'][0]['name'] = '<img src=x onerror=alert(1)> & "owner"'
    b['packages'][0]['name'] = a['packages'][0]['name']
    exports = [symbol('missing'), symbol('match'), symbol('ver@@V1'), symbol('kind'),
               symbol('size'), symbol('visible'), symbol('binding'), symbol('resolver', 'IFUNC'),
               symbol('data', 'OBJECT'), symbol('thread', 'TLS'), symbol('weak', binding='WEAK')]
    a['elf_objects'][0]['exports'] = exports
    b['elf_objects'][0]['exports'] = [symbol('added'), symbol('match'), symbol('ver@@V2'),
        symbol('kind', 'OBJECT'), symbol('size', size=8), symbol('visible', visibility='PROTECTED'),
        symbol('binding', binding='WEAK'), *copy.deepcopy(exports[7:])]
    for m in (a, b):
        original = m['elf_objects'][0]
        alias = copy.deepcopy(original); alias['path'] = '/usr/lib/alias.so'
        second = copy.deepcopy(original); second['path'] = '/usr/lib/second.so'; second['exports'] = [symbol('second')]
        m['elf_objects'] += [alias, second]
        m['filesystem'] += [dict(path=alias['path'], type='symlink', target='libsynthetic0.so'), dict(path=second['path'], type='file')]
        m['packages'][0]['files'] += [alias['path'], second['path']]
        # Deliberately shared ownership: never choose one owner silently.
        m['packages'][1]['files'].append(second['path'])
    extra = copy.deepcopy(b['packages'][1]); extra['name'] = 'new-only'; extra['files'] = []
    b['packages'].append(extra); b['package_inventory']['installed_count'] += 1
    path = a['elf_objects'][0]['path']
    fs = [finding('abi', path, 'missing', exports[0], None, 'INCOMPATIBLE', 'HIGH')]
    for root in ('/bin/root-a', '/bin/root-b'):
        f = finding('linking', path, 'import:missing', 'missing', None, 'UNKNOWN')
        f.update(consumer_image='baseline', consumer_path=path, root_consumer=root,
                 root_consumer_image='baseline', resolution='unknown_symbol_scope', check_id='import:missing')
        f['id'] += '-' + root.rsplit('/', 1)[1]
        fs.append(f)
    distinct = copy.deepcopy(fs[-1]); distinct['baseline'] = 'different requirement'; distinct['id'] += '-different'; fs.append(distinct)
    fs.append(finding('api', '/unassigned', 'SDK unavailable', None, None, 'UNKNOWN'))
    return a, b, finalize(fs, config), config


class EnhancementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name); cls.source = cls.base / 'source'; cls.source.mkdir()
        a, b, fs, config = fixture()
        cls.result = build_results(a, b, fs, [], [], config)
        generate(cls.source, a, b, cls.result, config)
        cls.output = cls.base / 'enhanced'
        cls.before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.source.iterdir() if p.is_file()}
        with patch('json.load', side_effect=AssertionError('Whole JSON loading prohibited')):
            cls.metrics = build(cls.source, cls.output, FixtureGuard)
        cls.browser = ReportBrowser(cls.output)
        cls.db = sqlite3.connect(cls.output / 'report-index.sqlite'); cls.db.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls): cls.db.close(); cls.temp.cleanup()

    def test_multiple_elf_and_alias_dedup(self):
        raw = self.db.execute("SELECT count(*) FROM raw_elf WHERE side='baseline'").fetchone()[0]
        canonical = self.db.execute("SELECT count(*) FROM elf WHERE side='baseline'").fetchone()[0]
        self.assertEqual((raw, canonical), (4, 3))
        package = self.browser.query('packages', {'q': ['owner'], 'side': ['baseline']})['rows'][0]
        self.assertEqual(package['observed_owned_elf_count'], 2)
        self.assertIsNone(package['owned_elf_count'])
        self.assertEqual(package['observed_counts']['exports'], 12)

    def test_unknown_install_count_preserves_observed_assessments(self):
        for has_records in (False, True):
            with self.subTest(has_records=has_records), tempfile.TemporaryDirectory() as directory:
                source = Path(directory)/'source'
                source.mkdir()
                output = Path(directory)/'enhanced'
                a, b, fs, config = fixture()
                a['package_inventory'].update(status='PARTIAL' if has_records else 'UNKNOWN', installed_count=None)
                if not has_records:
                    a['packages'] = []
                result = build_results(a, b, fs, [], [], config)
                generate(source, a, b, result, config)
                self.assertEqual(build(source, output, FixtureGuard)['status'], 'PASS')
                overview = ReportBrowser(output).query('overview', {})
                self.assertIsNone(overview['images']['baseline']['inventory']['installed_count'])
                self.assertEqual(overview['images']['baseline']['package_rows'], 2 if has_records else 0)
                self.assertEqual(overview['finding_count'], len(fs))

    def test_contradictory_known_install_count_still_fails_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source'
            source.mkdir()
            a, b, fs, config = fixture()
            result = build_results(a, b, fs, [], [], config)
            result['package_inventory']['baseline_package_count'] += 1
            generate(source, a, b, result, config)
            with self.assertRaisesRegex(ValueError, 'baseline_package_count'):
                build(source, Path(directory)/'enhanced', FixtureGuard)

    def test_export_types_and_version_counts(self):
        row = self.db.execute("SELECT counts FROM elf WHERE side='baseline' AND path='/usr/lib/libsynthetic0.so'").fetchone()
        counts = json.loads(row[0])
        self.assertEqual([counts[k] for k in ('exports', 'func', 'ifunc', 'object', 'tls', 'weak', 'versioned')], [11, 8, 1, 1, 1, 1, 1])

    def test_all_difference_categories_and_original_status(self):
        kinds = {r[0] for r in self.db.execute('SELECT DISTINCT difference_type FROM differences')}
        self.assertTrue({'MISSING', 'ADDED', 'TYPE_CHANGED', 'CODE_SIZE_CHANGED', 'VISIBILITY_CHANGED', 'BINDING_CHANGED', 'VERSION_CHANGED', 'MATCHED'} <= kinds)
        rows = [json.loads(r[0]) for r in self.db.execute("SELECT row_json FROM differences WHERE difference_type='MATCHED'")]
        self.assertTrue(all(r['compatibility_status'] == 'UNKNOWN' for r in rows))
        missing = json.loads(self.db.execute("SELECT row_json FROM differences WHERE name='missing' AND difference_type='MISSING'").fetchone()[0])
        self.assertEqual(missing['compatibility_status'], 'INCOMPATIBLE')
        version = json.loads(self.db.execute("SELECT row_json FROM differences WHERE difference_type='VERSION_CHANGED'").fetchone()[0])
        self.assertEqual((version['gcc_symbol_name'], version['llvm_symbol_name']), ('ver@@V1', 'ver@@V2'))

    def test_ambiguous_ownership_is_not_complete(self):
        packages = self.browser.query('packages', {'side': ['baseline']})['rows']
        self.assertTrue(all(p['shared_owned_elf_count'] == 1 for p in packages))
        self.assertTrue(all(p['counts']['func'] is None for p in packages))
        self.assertTrue(all(p['ownership_completeness'] == 'UNKNOWN' for p in packages))

    def test_candidate_only_and_unknown_api_linking(self):
        p = self.browser.query('packages', {'q': ['new-only']})['rows'][0]
        self.assertEqual(p['overall'], 'UNKNOWN'); self.assertIsNone(p['differences']['missing'])
        for p in self.browser.query('packages', {})['rows']:
            self.assertEqual(p['api'], 'UNKNOWN'); self.assertEqual(p['linking'], 'UNKNOWN')

    def test_no_sdk_debug_information_is_unknown(self):
        for p in self.browser.query('packages', {})['rows']:
            self.assertIsNone(p['header_count'])
        self.assertNotIn('type_layout_verified', (self.output / 'overview.json').read_text())

    def test_grouping_preserves_consumers_and_requirements(self):
        groups = self.browser.query('groups', {})['rows']
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(g['raw_finding_count'] for g in groups), [1, 2])
        group = next(g for g in groups if g['raw_finding_count'] == 2)
        self.assertEqual(group['affected_root_consumer_count'], 2)
        members = self.browser.query('findings', {'group': [group['group_id']]})['rows']
        self.assertEqual({r['root_path'] for r in members}, {'/bin/root-a', '/bin/root-b'})
        self.assertEqual(sum(g['raw_finding_count'] for g in groups), 3)

    def test_exact_original_payloads_ids_and_source_immutability(self):
        for finding in self.result['findings']:
            self.assertEqual(self.browser.query('finding', {'id': [finding['id']]}), finding)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir() if p.is_file()}
        self.assertEqual(self.before, after)
        self.assertEqual(self.metrics['status'], 'PASS')

    def test_package_status_coverage_preserved(self):
        for p in self.result['package_results']:
            data = self.browser.query('package', {'side': ['baseline'], 'id': [p['id']]})
            for key in ('abi', 'api', 'linking', 'overall', 'verification', 'coverage', 'confidence', 'limitations'):
                self.assertEqual(data['original_assessment'][key], p[key])

    def test_original_global_outcome_and_verification(self):
        overview = self.browser.query('overview', {})
        self.assertEqual(overview['original_overall'], self.result['status'])
        self.assertEqual(overview['original_verification'], self.result['verification'])

    def test_list_pages_defer_heavy_metadata_to_exact_details(self):
        package = self.browser.query('packages', {})['rows'][0]
        self.assertNotIn('coverage', package); self.assertNotIn('limitations', package)
        detail = self.browser.query('package', {'side': [package['side']], 'id': [package['package_id']]})
        self.assertIn('coverage', detail['summary']); self.assertIn('limitations', detail['summary'])
        group = self.browser.query('groups', {})['rows'][0]
        self.assertNotIn('group_key', group); self.assertNotIn('evidence_references', group)
        detail = self.browser.query('group', {'id': [group['group_id']]})
        self.assertIn('group_key', detail); self.assertIn('evidence_references', detail)

    def test_group_pagination_uses_covering_sort_before_payloads(self):
        plan = ' '.join(r[3] for r in self.db.execute('EXPLAIN QUERY PLAN SELECT id FROM groups WHERE interface LIKE ? ORDER BY raw_count DESC,id LIMIT 50', ('%missing%',)))
        self.assertIn('COVERING INDEX', plan)
        self.assertNotIn('TEMP B-TREE', plan)
        groups = self.browser.query('groups', {'q': ['missing'], 'limit': ['1']})
        self.assertEqual(groups['total'], 2)
        self.assertEqual(len(groups['rows']), 1)
        self.assertEqual(groups['rows'][0]['raw_finding_count'], 2)

    def test_html_escape_and_no_inline_data_script(self):
        text = (self.output / 'index.html').read_text()
        self.assertNotIn('<img src=x', text)
        self.assertIn('&lt;img src=x', text)
        js = (self.output / 'enhanced-report.js').read_text()
        self.assertNotIn('innerHTML', js); self.assertIn('textContent', js)
        self.assertIn('file://', text); self.assertIn('127.0.0.1', (self.output / 'README.md').read_text())
        self.assertLess(len(text), 100000)

    def test_pagination_and_parameterized_filters(self):
        self.assertEqual(len(self.browser.query('findings', {'limit': ['1']})['rows']), 1)
        self.assertEqual(self.browser.query('packages', {'q': ["' OR 1=1 --"]})['total'], 0)
        self.assertEqual(self.browser.query('packages', {'sort': ['DROP TABLE findings']})['total'], 5)
        with self.assertRaises(ValueError): self.browser.query('symbols', {})
        rows = self.browser.query('packages', {'sort': ['missing']})['rows']
        counts = [r['observed_differences']['missing'] for r in rows]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_read_only_server_paths(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), self.browser.handler())
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with urlopen(base + '/api/packages?limit=1') as response:
                self.assertEqual(len(json.loads(response.read())['rows']), 1)
            for path, expected in (('/evidence?ref=../results.json', 403), ('/report-index.sqlite', 404), ('/../../etc/passwd', 404)):
                with self.assertRaises(HTTPError) as caught: urlopen(base + path)
                self.assertEqual(caught.exception.code, expected)
            with self.assertRaises(HTTPError) as caught: urlopen(Request(base + '/api/packages', data=b'x'))
            self.assertEqual(caught.exception.code, 501)
        finally:
            server.shutdown(); worker.join(); server.server_close()

    def test_occupied_report_port_produces_actionable_cli_error(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/enhance_report.py'
        with ThreadingHTTPServer(('127.0.0.1', 0), self.browser.handler()) as incumbent:
            args = [sys.executable, str(script), 'serve', '--report', str(self.output),
                    '--port', str(incumbent.server_port)]
            result = subprocess.run(args, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('already in use', result.stderr)
            self.assertIn('--port 0', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(incumbent.socket.getsockname()[1], incumbent.server_port)

    def test_output_cannot_overwrite_source_or_existing_output(self):
        with self.assertRaises(ValueError): build(self.source, self.source / 'child', FixtureGuard)
        with self.assertRaises(FileExistsError): build(self.source, self.output, FixtureGuard)


class StreamTests(unittest.TestCase):
    def test_incomplete_collection_never_supplies_complete_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'; source.mkdir()
            a, b, fs, config = benchmark.fixture(1, 1)
            for m in (a, b):
                m['collection_complete'] = False
                m['elf_objects'] = []
                m['public_headers'] = []
            generate(source, a, b, build_results(a, b, fs, [], [], config), config)
            output = Path(tmp) / 'out'; build(source, output, FixtureGuard)
            for p in ReportBrowser(output).query('packages', {})['rows']:
                self.assertEqual(p['observed_counts']['func'], 0)
                self.assertEqual(p['observed_owned_elf_count'], 0)
                self.assertIsNone(p['counts']['func'])
                self.assertIsNone(p['owned_elf_count'])
                self.assertIsNone(p['shared_library_count'])
                self.assertIsNone(p['differences']['missing'])

    def test_large_stream_unicode_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'large.json'
            with path.open('w') as f:
                f.write('{"rows":[')
                for n in range(20000):
                    if n: f.write(',')
                    f.write(json.dumps({'n': n, 'text': '导出<&>' * 8}, ensure_ascii=False))
                f.write('],"tail":123456789}')
            seen = []
            result, sha = ReportStream(path, {('rows',)}, set(), lambda p, x: seen.append(x['n']), chunk_chars=31).read()
            self.assertEqual(seen, list(range(20000))); self.assertEqual(result['tail'], 123456789)
            self.assertEqual(sha, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_truncated_and_oversized_records_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            for contents in ('{"rows":[{"x":', '{"x":"' + 'a' * 1000 + '"}'):
                path.write_text(contents)
                with self.assertRaises(ValueError): ReportStream(path, {('rows',)}, set(), lambda p, x: None, chunk_chars=8, max_record_chars=64).read()

    def test_incomplete_symbol_metadata_and_missing_elf_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'; source.mkdir()
            a, b, fs, config = benchmark.fixture(1, 1)
            del a['elf_objects'][0]['exports'][0]['binding']
            b['elf_objects'][0]['path'] = '/renamed-without-soname.so'
            b['packages'][0]['files'] = ['/renamed-without-soname.so']
            b['filesystem'] = [dict(path='/renamed-without-soname.so', type='file')]
            generate(source, a, b, build_results(a, b, fs, [], [], config), config)
            output = Path(tmp) / 'out'; build(source, output, FixtureGuard)
            browser = ReportBrowser(output)
            package = browser.query('packages', {'side': ['baseline']})['rows'][0]
            self.assertIsNone(package['counts']['func']); self.assertIsNone(package['differences']['missing'])
            db = sqlite3.connect(output / 'report-index.sqlite')
            self.assertEqual(set(r[0] for r in db.execute('SELECT difference_type FROM differences')), {'UNKNOWN'})
            db.close()

    def test_resource_guard_enforces_disk_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = ResourceGuard(Path(tmp))
            class Disk: f_bavail = 1; f_frsize = 4096
            with patch('os.statvfs', return_value=Disk()):
                with self.assertRaisesRegex(ResourceLimit, 'disk'): guard.check(force=True)


if __name__ == '__main__': unittest.main()
