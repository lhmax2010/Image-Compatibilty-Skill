"""Phase 8A execution receipts and DWARF identity regressions."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from test_framework import Environment
from compat.collect import collect
from compat.compare import finalize
from compat.core import Tools, canonical, digest, finding, read_manifest
from compat.debuginfo import advanced_abi
from compat.history import HistoryBrowser, build_history
from compat.images import Image
from compat.report import build_results, generate
from compat.report_io import evidence_path
from test_final_release import enhanced_report
from test_report_enhancement import FixtureGuard
from tizen_compat import main


class CollectorReceiptTests(Environment):
    def manifest(self, readelf=None, rpm=None):
        entries = {tool: {'status': status} if isinstance(status, str) else status
                   for tool, status in (('readelf', readelf), ('rpm', rpm)) if status is not None}
        return self.blank() | {'collector_execution': entries}

    def test_execution_slots_distinguish_missing_and_nonapplicable(self):
        self.config['analysis']['modes'] = ['abi', 'packages']
        complete = self.manifest('COMPLETE', 'COMPLETE')
        no_elf = {'status': 'NOT_EXECUTED', 'applicable': False, 'reason_code': 'NO_ELF_OBJECTS'}
        cases = [
            (complete, complete, 'COMPLETE'),
            (complete, self.manifest('FAILED', 'COMPLETE'), 'FAILED'),
            (complete, self.manifest('PARTIAL', 'COMPLETE'), 'PARTIAL'),
            (self.manifest(None, 'COMPLETE'), complete, 'PARTIAL'),
            (self.manifest('COMPLETE'), self.manifest(None, 'COMPLETE'), 'PARTIAL'),
            (self.manifest(), self.manifest(), 'UNKNOWN'),
            (self.blank(), self.blank(), 'UNKNOWN'),
            (self.blank(), complete, 'PARTIAL'),
            (self.manifest(no_elf, 'COMPLETE'), complete, 'COMPLETE'),
            (self.manifest(no_elf, 'NOT_EXECUTED'), self.manifest(no_elf, 'NOT_EXECUTED'), 'NOT_EXECUTED'),
            (self.manifest('COMPLETE', 'NOT_EXECUTED'), complete, 'PARTIAL'),
        ]
        for baseline, candidate, expected in cases:
            with self.subTest(expected=expected, baseline=baseline.get('collector_execution')):
                result = build_results(baseline, candidate, [], [], [], self.config)
                self.assertEqual(result['execution']['status'], expected)
                self.assertEqual(result['quality_gate']['execution_status'], 'FAIL' if expected == 'FAILED' else 'PASS')
                for side, manifest in (('baseline', baseline), ('candidate', candidate)):
                    slots = result['execution']['collectors'][side]
                    self.assertEqual(set(slots), {'readelf', 'rpm'})
                    for tool in slots.keys() - manifest.get('collector_execution', {}).keys():
                        self.assertEqual(slots[tool]['status'], 'UNKNOWN')
                        self.assertFalse(slots[tool]['recorded'])

    def test_collection_records_no_objects_missing_database_disabled_and_failure(self):
        root = self.base / 'image'
        root.mkdir()
        self.config['analysis']['modes'] = ['elf', 'packages']
        def receipts(image_format=None):
            img = Image(root, self.workspace, self.tools, 'baseline')
            if image_format:
                img.format = image_format
            return collect(img, 'baseline', 'baseline', 'static', self.tools, self.workspace, None)['collector_execution']
        plain = receipts()
        self.assertEqual(plain['readelf']['reason_code'], 'NO_ELF_OBJECTS')
        self.assertFalse(plain['readelf']['applicable'])
        self.assertEqual(plain['rpm']['reason_code'], 'RPM_DATABASE_NOT_FOUND')
        self.assertNotIn('applicable', plain['rpm'])
        self.assertFalse(receipts('rpm-collection')['rpm']['applicable'])
        db = root / 'var/lib/rpm'
        db.mkdir(parents=True)
        (db / 'Packages').write_text('fixture')
        binary = self.base / 'fail'
        binary.write_text('#!/bin/sh\nexit 17\n')
        binary.chmod(0o755)
        self.config['tools']['rpm'] = str(binary)
        self.assertEqual(receipts()['rpm']['status'], 'FAILED')
        self.config['tools'].update(readelf=False, rpm=False)
        self.assertTrue(all(s['status'] == 'NOT_EXECUTED' and s['reason_code'] == 'DISABLED'
                            for s in receipts().values()))
        self.config['analysis']['modes'] = ['filesystem']
        self.assertEqual(receipts(), {})

    def test_missing_receipt_renders_equally_in_json_markdown_and_html(self):
        self.config['analysis']['modes'] = ['elf', 'packages']
        a = self.manifest(None, 'COMPLETE')
        b = self.manifest('COMPLETE', 'COMPLETE')
        result = build_results(a, b, [], [], [], self.config)
        generate(self.output, a, b, result, self.config)
        decoded = json.loads((self.output / 'results.json').read_text())
        self.assertEqual(decoded['execution']['status'], 'PARTIAL')
        self.assertEqual(decoded['execution']['collectors']['baseline']['readelf']['status'], 'UNKNOWN')
        for name in ('summary.md', 'index.html'):
            body = (self.output / name).read_text()
            self.assertIn('PARTIAL', body)
            self.assertIn('No execution receipt for this collector and image', body)
        old = self.output / 'old.json'
        old.write_text(json.dumps(self.blank()))
        self.assertNotIn('collector_execution', read_manifest(old))

    def test_cli_collector_failure_and_policy_combinations(self):
        root = self.base / 'image'
        root.mkdir()
        (root / 'lib.so').write_bytes(b'\x7fELF' + bytes([2, 1]) + b'\x00' * 40)
        broken = self.base / 'readelf'
        broken.write_text('#!/bin/sh\nexit 17\n')
        broken.chmod(0o755)
        for idx, (fail, strict, minimum, expected) in enumerate([
            (True, False, {}, 3), (True, True, {'elf': 99}, 3),
            (False, False, {}, 0), (False, True, {}, 1), (False, False, {'elf': 99}, 1),
        ]):
            cfg = self.base / 'profile.json'
            cfg.write_text(json.dumps({'analysis': {'modes': ['elf']}, 'tools': {'readelf': str(broken)},
                                       'ci': {'fail_on_collector_failure': fail, 'strict': strict,
                                              'minimum_coverage': minimum}}))
            output = self.base / f'out-{idx}'
            with self.subTest(fail=fail, strict=strict, minimum=minimum):
                self.assertEqual(main(['--baseline', str(root), '--candidate', str(root),
                                       '--config', str(cfg), '--output', str(output), '--fail-on', 'CRITICAL']), expected)
                result = json.loads((output / 'results.json').read_text())
                self.assertEqual(result['execution']['status'], 'FAILED')
                self.assertEqual(result['status'], 'UNKNOWN')


class DwarfIdentityTests(Environment):
    def analyze(self, filename='/lib.so', report_text=None):
        with tempfile.TemporaryDirectory(prefix='tizen-compat-', dir=self.base) as d:
            stage = Path(d)
            tools = Tools(stage / 'report', copy.deepcopy(self.config))
            tools.config['tools']['abidiff'] = False
            roots = []
            for side in ('baseline', 'candidate'):
                root = stage / side
                (root / filename.lstrip('/')).parent.mkdir(parents=True)
                (root / filename.lstrip('/')).write_bytes(b'controlled input')
                roots.append(Image(root, stage, tools, side))
            obj = {'path': filename, 'debug_info': True}
            manifest = {'elf_objects': [obj]}
            if report_text is not None:
                binary = stage / 'abidiff'
                binary.write_text('#!/bin/sh\nfor arg in "$@"; do printf "%s\\n" "$arg"; done\n'
                                  'printf "%s\\n" ' + report_text + '\nexit 4\n')
                binary.chmod(0o755)
                tools.config['tools']['abidiff'] = str(binary)
            observation = advanced_abi(manifest, manifest, roots, tools)[0]
            for ref in observation['evidence']:
                self.assertTrue(evidence_path(tools.output, ref).is_file())
            return observation

    def test_dwarf_embedded_paths_are_stable_and_components_are_distinct(self):
        left, right = self.analyze(), self.analyze()
        self.assertEqual(left, right)
        self.assertEqual(left['debug_coverage']['baseline']['path'], '/lib.so')
        self.assertEqual(left['debug_coverage']['baseline']['location'], 'image')
        different = self.analyze('/other/lib.so')
        self.assertNotEqual(left['id'], different['id'])
        result = finalize([left, right, different], self.config)
        self.assertEqual(len(result), 2)
        self.assertEqual(next(x['occurrences'] for x in result if x['id'] == left['id']), 2)

    def test_dwarf_diagnostics_identity_preserves_raw_evidence(self):
        left, right = self.analyze(report_text='layout-A'), self.analyze(report_text='layout-A')
        self.assertEqual(left['id'], right['id'])
        self.assertNotEqual(left['evidence'][0], right['evidence'][0])
        self.assertEqual(left['candidate']['report'], right['candidate']['report'])
        self.assertNotEqual(left['id'], self.analyze(report_text='layout-B')['id'])

    def test_history_accepts_equal_fingerprints_with_distinct_raw_diagnostics(self):
        before_row = self.analyze(report_text='layout-A')
        after_row = self.analyze(report_text='layout-A')
        before, after = self.base / 'before', self.base / 'after'
        enhanced_report(before, [before_row])
        enhanced_report(after, [after_row])
        with patch('compat.history.ImpactGuard', FixtureGuard):
            build_history(before / 'enhanced', after / 'enhanced', self.base / 'history', 'fixture lineage')
        rows = HistoryBrowser(self.base / 'history').query('entries', {})['items']
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['before_id'], rows[0]['after_id'], rows[0]['match']),
                         (before_row['id'], after_row['id'], 'UNIQUE_DWARF_OBSERVATION'))

    def test_history_pairs_only_same_dwarf_observation_and_keeps_original_ids(self):
        current = self.analyze()
        old = copy.deepcopy(current)
        for side in ('baseline', 'candidate'):
            debug = old[side]['debug']
            debug.pop('location')
            debug['path'] = '/workspace/tizen-compat-original/' + side + '/lib.so'
        old['id'] = finding(old['dimension'], old['component'], old['interface'], old['baseline'], old['candidate'],
                            old['status'], old['severity'], old['detection_method'], old['evidence'],
                            old['potential_impact'])['id']
        self.assertNotEqual(old['id'], current['id'])
        other = self.analyze('/lib/different.so')
        changed = copy.deepcopy(other)
        changed['candidate']['report'] = 'different recorded diagnostics'
        changed['id'] = 'TC-' + digest(canonical(changed).encode())[:16]
        ordinary = [finding(d, '/a', 'ordinary test', 1, 2) for d in ('elf', 'abi', 'linking')]
        before, after = self.base / 'before', self.base / 'after'
        enhanced_report(before, [old, other, *ordinary])
        enhanced_report(after, [current, changed, *ordinary])
        with patch('compat.history.ImpactGuard', FixtureGuard):
            build_history(before / 'enhanced', after / 'enhanced', self.base / 'history', 'fixture lineage')
        rows = HistoryBrowser(self.base / 'history').query('entries', {})['items']
        row = next(r for r in rows if r['before_id'] == old['id'])
        self.assertEqual((row['after_id'], row['change'], row['match']),
                         (current['id'], 'PERSISTING_RISK', 'UNIQUE_DWARF_OBSERVATION'))
        self.assertEqual(next(r['after_id'] for r in rows if r['before_id'] == other['id']), None)
        self.assertEqual(next(r['before_id'] for r in rows if r['after_id'] == changed['id']), None)
        self.assertEqual({r['before_id'] for r in rows if r['match'] == 'EXACT_ID_AND_PAYLOAD'},
                         {r['id'] for r in ordinary})
