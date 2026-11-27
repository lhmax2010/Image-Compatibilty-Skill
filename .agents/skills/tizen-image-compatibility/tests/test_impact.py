"""End-to-end impact acceptance against synthetic resolver records."""
from contextlib import closing
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from test_framework import Environment
from test_report_enhancement import FixtureGuard
from test_static_fixes import elf, symbol
from test_v12 import installed, inventory
from compat.compare import finalize
from compat.core import DEFAULTS, VERSION
from compat.report_io import manifest_path, open_payload
from compat.impact_browser import ImpactBrowser
from compat.impact_source import group_rows, unpack_limited
from compat.impact_store import DB_NAME, build
from compat.linker import dependency_checks
from compat.report import build_results, generate
from compat.report_browser import ReportBrowser
from compat.report_enhance import build as enhance
from compat.report_io import hash_file


def synthetic_report(directory, guard=FixtureGuard):
    source = directory / 'original'
    source.mkdir(parents=True)
    (source / 'evidence').mkdir()
    (source / 'evidence/review.txt').write_text('Synthetic metadata observation only\n')

    def app(name, needed, imports=()):
        return elf('/bin/' + name, needed=needed, imports=list(imports), evidence=['evidence/review.txt'])

    roots = [
        app('missing', ['gone.so']), app('versions', ['ver.so'], [symbol('api@V1')]),
        app('alias', ['alias.so', 'real.so']), app('partial', ['partial.so'], [symbol('api')]),
        app('secure', ['gone.so']), app('multi', ['one.so','two.so'], [symbol('api')]),
        app('runtime', ['libstdc++.so.6']), app('old-failure', ['never.so']),
        app('symbol', ['sym.so'], [symbol('remove_me')]),
        app('a/same', ['gone.so']), app('b/same', ['alias.so']),
    ]
    roots[1]['version_requirements'] = [{'file':'ver.so','name':'V1','flags':'none'}]
    roots[1]['imports'][0]['version_file'] = 'ver.so'
    roots[4]['evidence'].extend(['evidence/missing.txt', 'evidence/../results.json'])
    libs = [
        elf('/lib/gone.so', type='DYN', soname='gone.so'),
        elf('/lib/ver.so', type='DYN', exports=[symbol('api@@V1')], version_definitions=[{'name':'V1'}]),
        elf('/lib/alias.so', type='DYN', soname='real.so'),
        elf('/lib/partial.so', type='DYN', exports=[symbol('api')]),
        elf('/lib/one.so', type='DYN', exports=[symbol('api')]),
        elf('/lib/two.so', type='DYN', exports=[symbol('api')]),
        elf('/lib/libstdc++.so.6', type='DYN'),
        elf('/lib/sym.so', type='DYN', exports=[symbol('remove_me')]),
    ]

    def manifest(side, objects):
        m = Environment().blank() | dict(schema_version='1.2', collector_version=VERSION,
            image={'name': 'SYNTHETIC ' + side},
            elf_objects=objects,
            loader_environment={'model':'glibc','environment_complete':True,'cache_complete':True,
                'namespace':'base','symbol_scope':'startup','default_dirs':['/lib']})
        inventory(m, [installed('apps', [x['path'] for x in objects if x['path'].startswith('/bin/')]),
                      installed('libs', [x['path'] for x in objects if x['path'].startswith('/lib/')])])
        for row in m['filesystem']:
            row.update(mode='0o4755' if row['path']=='/bin/secure' and side=='baseline' else '0o755',
                       security_metadata_complete=True, has_file_capabilities=False)
        return m

    a = manifest('baseline', roots + libs)
    modified = copy.deepcopy(libs[1:])
    modified[0].update(exports=[symbol('api@@V2')], version_definitions=[{'name':'V2'}])
    modified[2].pop('export_inventory_complete')
    modified[2]['exports'] = []
    modified[-1]['exports'] = []
    b = manifest('candidate', copy.deepcopy(roots) + modified)
    findings = dependency_checks(b,'candidate') + dependency_checks(b,'baseline consumers on candidate',a['elf_objects'],consumer_manifest=a)
    config = copy.deepcopy(DEFAULTS)
    results = build_results(a,b,finalize(findings,config),[],[],config)
    generate(source,a,b,results,config)
    indexed = directory/'indexed'
    enhance(source,indexed,guard)
    return results, source, indexed, [x['path'] for x in roots]


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): hash_file(p) for p in folder.rglob('*') if p.is_file()}


class ImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.base = Path(temp.name)
        cls.results, cls.source, cls.indexed, cls.roots = synthetic_report(cls.base)
        cls.before = (snapshot(cls.source), snapshot(cls.indexed))
        cls.replay = cls.base/'replay'
        cls.recorded = cls.base/'recorded'
        with patch('compat.impact_store.ImpactGuard', FixtureGuard):
            cls.replayed = build(cls.indexed,cls.replay,roots=cls.roots)
            cls.historical = build(cls.indexed,cls.recorded)
        cls.browser = ImpactBrowser(cls.indexed,cls.replay)

    def original(self, consumer, check, direction='baseline'):
        return next(f for f in self.results['findings'] if f.get('check_id')==check
                    and f.get('consumer_path')==consumer and f.get('root_consumer')==consumer
                    and f.get('root_consumer_image')==direction)

    def result(self, path, check, direction='baseline'):
        f = self.original(path,check,direction)
        return self.browser.query('finding',{'finding':[f['id']]})

    def test_true_missing_provider_and_symbol_contracts(self):
        for path, check in [('/bin/missing','DT_NEEDED:gone.so'),('/bin/symbol','import:remove_me'),
                            ('/bin/versions','version:ver.so:V1')]:
            with self.subTest(check=check):
                result = self.result(path,check)
                self.assertEqual((result['status'],result['strength'],result['assessment']),
                                 ('INCOMPATIBLE','DIRECT','CONFIRMED_CONTRACT_IMPACT'))
                self.assertEqual(result['proof']['baseline']['status'],'COMPATIBLE')
                self.assertEqual(result['proof']['candidate']['finding_id'],result['id'])

    def test_reused_soname_remains_compatible(self):
        result = self.result('/bin/alias','DT_NEEDED:real.so')
        self.assertEqual((result['status'],result['assessment']),('COMPATIBLE','NO_BREAK_OBSERVED'))
        self.assertEqual(result['proof']['candidate']['provider_path'],'/lib/alias.so')

    def test_secure_scope_incomplete_dynsym_and_multiple_providers_remain_unknown(self):
        for path, check in [('/bin/secure','DT_NEEDED:gone.so'),('/bin/partial','import:api'),('/bin/multi','import:api')]:
            with self.subTest(check=check,path=path):
                result = self.result(path,check)
                self.assertEqual(result['status'],'UNKNOWN')
                self.assertEqual(result['assessment'],'POSSIBLE_IMPACT')
                self.assertIsNone(result['proof'])

    def test_existing_baseline_failure_and_candidate_native_do_not_confirm(self):
        for path, check, direction in [('/bin/old-failure','DT_NEEDED:never.so','baseline'),
                                       ('/bin/missing','DT_NEEDED:gone.so','candidate')]:
            result = self.result(path,check,direction)
            self.assertEqual((result['status'],result['assessment']),('INCOMPATIBLE','POSSIBLE_IMPACT'))

    def test_historical_source_does_not_gain_credit_and_assessment_counts_conserve(self):
        counts = self.historical['summary']
        self.assertEqual(counts['assessments'].get('CONFIRMED_CONTRACT_IMPACT',0),0)
        self.assertEqual(sum(counts['assessments'].values()),counts['source_findings'])
        self.assertNotIn('DIRECT',counts['strengths'])

    def test_missing_and_unsafe_evidence_are_retained_as_unavailable(self):
        result = self.result('/bin/secure','DT_NEEDED:gone.so')
        self.assertEqual({e['reference']:e['available'] for e in result['evidence']}, {
            'evidence/review.txt': True, 'evidence/missing.txt': False, 'evidence/../results.json': False})

    def test_csv_reconciliation_rejects_swapped_source_status(self):
        broken = self.base/'swapped-status'
        shutil.copytree(self.indexed, broken)
        table = broken/'finding-index.csv'
        text = table.read_text()
        self.assertIn(',INCOMPATIBLE,linking,', text)
        table.write_text(text.replace(',INCOMPATIBLE,linking,', ',UNKNOWN,linking,', 1))
        output = self.base/'swapped-output'
        with patch('compat.impact_store.ImpactGuard', FixtureGuard):
            with self.assertRaisesRegex(ValueError,'reconciliation'):
                build(broken,output)
        self.assertFalse((output/'run.json').exists())

    def test_same_basename_different_path_and_multi_membership(self):
        bad = self.result('/bin/a/same','DT_NEEDED:gone.so')
        good = self.result('/bin/b/same','DT_NEEDED:alias.so')
        self.assertNotEqual(bad['id'], good['id'])
        self.assertEqual(good['assessment'],'NO_BREAK_OBSERVED')
        f = self.original('/bin/runtime','DT_NEEDED:libstdc++.so.6')
        associated = self.browser.query('finding-groups',{'finding':[f['id']]})['items']
        self.assertEqual({r['kind'] for r in associated},{'REPLAYED_CONTRACT','RUNTIME_REVIEW','LINKING_OBSERVATIONS'})

    def test_all_source_ids_and_hashes_are_preserved_and_no_dangling(self):
        self.assertEqual(self.before,(snapshot(self.source),snapshot(self.indexed)))
        with closing(sqlite3.connect(self.indexed/'report-index.sqlite')) as old, closing(sqlite3.connect(self.replay/DB_NAME)) as new:
            self.assertEqual(old.execute('SELECT n,id,status,payload_hash FROM findings ORDER BY n').fetchall(),
                             new.execute('SELECT n,id,status,payload_hash FROM source_finding ORDER BY n').fetchall())
            self.assertEqual(new.execute('PRAGMA foreign_key_check').fetchall(),[])
            new.execute('PRAGMA foreign_keys=ON')
            with self.assertRaises(sqlite3.IntegrityError):
                new.execute('INSERT INTO group_finding VALUES(1,-999)')
            with self.assertRaises(sqlite3.IntegrityError):
                new.execute('INSERT INTO group_finding SELECT * FROM group_finding LIMIT 1')
            self.assertGreater(new.execute('SELECT count(*) FROM impact_group WHERE member_count>1').fetchone()[0],0)

    def test_package_roles_and_keyset_pages(self):
        confirmed = self.browser.query('groups',{'rank':['2'],'limit':['1']})
        gid = confirmed['items'][0]['id']
        second = self.browser.query('groups',{'rank':['2'],'limit':['1'],'after':[confirmed['next_cursor']],
                                             'projection':[confirmed['projection_id']]})
        self.assertNotEqual(gid,second['items'][0]['id'])
        with self.assertRaises(ValueError):
            self.browser.query('groups',{'after':[confirmed['next_cursor']],'projection':['different']})
        packages = self.browser.query('packages',{'group':[gid]})['items']
        self.assertTrue(any(r['role']=='consumer' and r['confirmed'] for r in packages))
        self.assertFalse(any(r['role']!='consumer' and r['confirmed'] for r in packages))
        for row in packages:
            groups = self.browser.query('package-groups',{'side':[row['side']],'package':[row['package_id']]})['items']
            self.assertIn(gid,{g['id'] for g in groups})

    def test_build_determinism_scope_and_refuse_overwrite(self):
        duplicate = self.base/'rebuild'
        with patch('compat.impact_store.ImpactGuard', FixtureGuard):
            result = build(self.indexed,duplicate,roots=list(reversed(self.roots)))
            with self.assertRaises(FileExistsError):
                build(self.indexed,duplicate)
            with self.assertRaises(ValueError):
                build(self.indexed,self.source/'child')
        self.assertEqual(result['projection_id'],self.replayed['projection_id'])
        self.assertEqual(result['index_sha256'],self.replayed['index_sha256'])
        self.assertEqual(result['summary'],self.replayed['summary'])

    def test_explicit_scope_and_conflict_do_not_affect_status(self):
        target=self.original('/bin/missing','DT_NEEDED:gone.so')
        rule={'side':'baseline','path':target['component'],'interface':target['interface'],
              'classification':'PUBLIC','authority':'Synthetic product contract'}
        config=self.base/'scope.json'
        for label,rules,scope in [('explicit',[rule],'PUBLIC'),
                                  ('conflicted',[rule,rule|{'classification':'INTERNAL'}],'UNDETERMINED')]:
            config.write_text(json.dumps({'schema':1,'rules':rules}))
            with patch('compat.impact_store.ImpactGuard', FixtureGuard):
                build(self.indexed,self.base/label,config,roots=['/bin/missing'])
            b=ImpactBrowser(self.indexed,self.base/label)
            group=next(g for g in b.query('finding-groups',{'finding':[target['id']]})['items']
                       if g['kind']=='REPLAYED_CONTRACT')
            self.assertEqual((group['scope'],group['rank']),(scope,2))

    def test_failure_after_partial_writes_never_publishes(self):
        output=self.base/'interrupted'
        with patch('compat.impact_store.ImpactGuard', FixtureGuard), patch('compat.impact_store.reconcile',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                build(self.indexed,output)
        self.assertTrue((output/'impact-index.building.sqlite').exists())
        self.assertFalse((output/'run.json').exists())
        self.assertEqual(json.loads((output/'failure.json').read_text())['state'],'FAILED')
        with self.assertRaises(ValueError):
            ImpactBrowser(self.indexed,output)

    def test_corrupt_database_stale_binding_and_unsupported_schema(self):
        bad=self.base/'corrupt'
        shutil.copytree(self.indexed,bad)
        db=bad/'report-index.sqlite'
        db.write_bytes(b'not sqlite')
        with patch('compat.impact_store.ImpactGuard', FixtureGuard):
            with self.assertRaises(sqlite3.DatabaseError):
                build(bad,self.base/'corrupt-output')
        with self.assertRaisesRegex(ValueError,'Stale'):
            ImpactBrowser(bad,self.replay)
        invalid=self.base/'wrong-schema'
        shutil.copytree(self.replay,invalid)
        marker=invalid/'run.json'
        marker.write_text(json.dumps(self.replayed|{'schema':2}))
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            ImpactBrowser(self.indexed,invalid)

    def test_evidence_and_loopback_http_original_remain_usable(self):
        b=ReportBrowser(self.indexed,self.replay)
        server=ThreadingHTTPServer(('127.0.0.1',0),b.handler())
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            for path in ('/impact','/impact.js','/api/impact/groups?limit=1','/api/overview','/evidence?ref=evidence/review.txt'):
                with urlopen(base+path,timeout=5) as response:
                    self.assertEqual(response.status,200)
                    self.assertTrue(response.read())
            for path,code in [('/evidence?ref=../results.json',403),('/impact-index.sqlite',404),
                              ('/api/impact/groups?after='+('q'*4100),400)]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base+path,timeout=5)
                self.assertEqual(error.exception.code,code)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_bounded_compressed_payload_and_checkpoint_equivalence(self):
        import zlib
        with self.assertRaises(ValueError):
            unpack_limited(zlib.compress(b'x'*(33*1024*1024)))
        def load(side):
            with open_payload(manifest_path(self.source/(side+'-manifest.json'))) as stream:
                return json.load(stream)
        a,b=[load(side) for side in ('baseline','candidate')]
        root=[obj for obj in a['elf_objects'] if obj['path']=='/bin/alias']
        ticks=[]
        plain=dependency_checks(b,'baseline consumers on candidate',root,consumer_manifest=a)
        observed=dependency_checks(b,'baseline consumers on candidate',root,consumer_manifest=a,checkpoint=lambda:ticks.append(1))
        self.assertEqual(plain,observed)
        self.assertGreater(len(ticks),0)

    def test_empty_navigation_export_uses_v13_no_records_header(self):
        path = self.base/'empty-groups.csv'
        path.write_text('no_records\n')
        self.assertEqual(list(group_rows(path, 1, lambda: None)), [])
        path.write_text('no_records\ninvalid\n')
        with self.assertRaises(ValueError):
            list(group_rows(path, 1, lambda: None))
