"""Lossless, disk-backed projection of existing reports; no compatibility detection."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import posixpath
import sqlite3
import zlib

from .report_io import ReportStream, canonical, digest, evidence_path


def pack(value):
    return zlib.compress(canonical(value).encode(), 1)


def unpack(value):
    return json.loads(zlib.decompress(value))


def symbol_name(name):
    if '@@' in name:
        base, version = name.split('@@', 1)
        return base, version, True
    if '@' in name:
        base, version = name.split('@', 1)
        return base, version, False
    return name, None, False


def source_status(statuses):
    """Summarize recorded outcomes only. An absent observation remains UNKNOWN."""
    values = set(statuses)
    if 'INCOMPATIBLE' in values:
        return 'INCOMPATIBLE'
    if not values or 'UNKNOWN' in values:
        return 'UNKNOWN'
    if values <= {'COMPATIBLE', 'IDENTICAL'}:
        return 'IDENTICAL' if values == {'IDENTICAL'} else 'COMPATIBLE'
    return 'UNKNOWN'


COUNTS = ('exports', 'func', 'ifunc', 'object', 'tls', 'weak', 'versioned')


class Store:
    def __init__(self, output, source, check):
        self.output, self.source, self.check = Path(output), Path(source), check
        self.db = sqlite3.connect(self.output / 'report-index.sqlite')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA cache_size=-131072')
        self.db.execute('PRAGMA temp_store=FILE')
        self.db.set_progress_handler(self._progress, 50000)
        self.db.executescript('''
        CREATE TABLE raw_elf(side TEXT,scope TEXT,path TEXT,payload BLOB,fingerprint TEXT,
          PRIMARY KEY(side,scope,path));
        CREATE TABLE elf(id TEXT PRIMARY KEY,side TEXT,scope TEXT,path TEXT,aliases TEXT,
          metadata TEXT,counts TEXT,complete INTEGER,pair_id TEXT);
        CREATE TABLE aliases(side TEXT,scope TEXT,path TEXT,elf_id TEXT,
          PRIMARY KEY(side,scope,path));
        CREATE TABLE symbols(elf_id TEXT,name TEXT,base TEXT,version TEXT,default_version INTEGER,
          type TEXT,attrs TEXT,ambiguous INTEGER,PRIMARY KEY(elf_id,name));
        CREATE TABLE packages(side TEXT,id TEXT,name TEXT,scope TEXT,record BLOB,assessment BLOB,
          peer TEXT,match_status TEXT,summary TEXT,abi TEXT,api TEXT,linking TEXT,overall TEXT,
          func INTEGER,missing INTEGER,finding_count INTEGER,unknown_count INTEGER,
          PRIMARY KEY(side,id));
        CREATE TABLE ownership(side TEXT,package_id TEXT,elf_id TEXT,path TEXT,complete INTEGER,
          PRIMARY KEY(side,package_id,path));
        CREATE TABLE package_refs(side TEXT,package_id TEXT,finding_id TEXT,kind TEXT,
          PRIMARY KEY(side,package_id,finding_id,kind));
        CREATE TABLE roles(finding_id TEXT,side TEXT,package_id TEXT,role TEXT,complete INTEGER,
          PRIMARY KEY(finding_id,side,package_id,role));
        CREATE TABLE elf_refs(elf_id TEXT,finding_id TEXT,role TEXT,
          PRIMARY KEY(elf_id,finding_id,role));
        CREATE TABLE findings(id TEXT PRIMARY KEY,n INTEGER UNIQUE,status TEXT,dimension TEXT,
          component TEXT,interface TEXT,consumer_image TEXT,consumer_path TEXT,
          root_image TEXT,root_path TEXT,provider_path TEXT,resolution TEXT,check_id TEXT,
          evidence TEXT,payload BLOB,payload_hash TEXT,csv_hash TEXT,group_id TEXT,
          evidence_state TEXT,ownership_complete INTEGER);
        CREATE TABLE unassigned(id TEXT PRIMARY KEY);
        CREATE TABLE groups(id TEXT PRIMARY KEY,key TEXT UNIQUE,reason TEXT,status TEXT,
          interface TEXT,provider TEXT,raw_count INTEGER DEFAULT 0,summary TEXT);
        CREATE TABLE pairs(id TEXT PRIMARY KEY,baseline TEXT,candidate TEXT,match_status TEXT,
          summary TEXT);
        CREATE TABLE differences(n INTEGER PRIMARY KEY,pair_id TEXT,name TEXT,version TEXT,
          difference_type TEXT,status TEXT,row_json TEXT);
        CREATE TABLE probe_observations(n INTEGER PRIMARY KEY,id TEXT,compiler TEXT,image TEXT,kind TEXT,status TEXT,summary TEXT);
        ''')
        self.files = defaultdict(dict)
        self.manifests = {}
        self.source_hashes = {}
        self.finding_count = 0
        self.histogram = Counter()
        self.dimension_histogram = Counter()
        self.metadata = {}
        self.elf_lookup = {}
        self.evidence_cache = {}

    def evidence_exists(self, ref):
        if ref not in self.evidence_cache:
            try:
                self.evidence_cache[ref] = evidence_path(self.source, ref).is_file()
            except (ValueError, OSError, RuntimeError):
                self.evidence_cache[ref] = False
        return self.evidence_cache[ref]

    def _progress(self):
        self.check()
        return 0

    def resolve(self, side, scope, path):
        if not path or not path.startswith('/'):
            return None
        path = posixpath.normpath('/' + path.lstrip('/'))
        files = self.files[side, scope]
        for _ in range(40):
            parts = path.split('/')
            for index in range(1, len(parts)):
                prefix = '/'.join(parts[:index + 1])
                record = files.get(prefix, {})
                if record.get('type') == 'symlink':
                    target = record.get('target')
                    if target is None:
                        target = record.get('resolved')
                    if not target:
                        return None
                    if not target.startswith('/'):
                        target = posixpath.join(posixpath.dirname(prefix), target)
                    path = posixpath.normpath(posixpath.join(target, *parts[index + 1:]))
                    path = '/' + path.lstrip('/')
                    break
            else:
                return path
        return None

    def read_manifest(self, side):
        names = ('elf_objects', 'filesystem', 'packages', 'public_headers', 'configurations',
                 'commands', 'services', 'hardware', 'network', 'security_interfaces',
                 'available_packages', 'kernel', 'ipc', 'runtime_libraries', 'development',
                 'test_results', 'expected_tests', 'sdk_headers')
        arrays = {(name,) for name in names} | {('sdk_package_manifest', name) for name in names}
        def record(path, value):
            scope = 'sdk' if len(path) == 2 else 'runtime'
            if path[-1] == 'filesystem':
                self.files[side, scope][value['path']] = value
            elif path[-1] == 'elf_objects':
                fingerprint = digest({k: v for k, v in value.items()
                                      if k not in ('path', 'evidence', 'resolution_metadata_evidence')})
                self.db.execute('INSERT INTO raw_elf VALUES(?,?,?,?,?)',
                                (side, scope, value['path'], pack(value), fingerprint))
            self.check()
        path = self.source / (side + '-manifest.json')
        metadata, sha = ReportStream(path, arrays, {('sdk_package_manifest',)}, record, self.check).read()
        self.manifests[side] = metadata
        self.source_hashes[path.name] = sha
        for scope in ('runtime', 'sdk'):
            buckets = defaultdict(list)
            for row in self.db.execute('SELECT path,fingerprint FROM raw_elf WHERE side=? AND scope=?', (side, scope)):
                resolved = self.resolve(side, scope, row['path'])
                buckets[resolved or row['path']].append((row['path'], row['fingerprint'], resolved is not None))
            for path, aliases in buckets.items():
                preferred = next((a[0] for a in aliases if a[0] == path), sorted(a[0] for a in aliases)[0])
                obj = unpack(self.db.execute('SELECT payload FROM raw_elf WHERE side=? AND scope=? AND path=?',
                                            (side, scope, preferred)).fetchone()[0])
                ident = 'ELF-' + digest([side, scope, path])[:24]
                variants = defaultdict(dict)
                for symbol in obj.get('exports', []):
                    variants[symbol['name']][canonical(symbol)] = symbol
                counts = Counter({key: 0 for key in COUNTS})
                ambiguity = 0
                for name, entries in variants.items():
                    values = list(entries.values())
                    base, version, default = symbol_name(name)
                    kinds = {s.get('type') for s in values}
                    kind = next(iter(kinds)) if len(kinds) == 1 else 'UNKNOWN'
                    counts['exports'] += 1
                    counts['func'] += kind == 'FUNC'
                    counts['ifunc'] += kind in ('IFUNC', 'GNU_IFUNC')
                    counts['object'] += kind == 'OBJECT'
                    counts['tls'] += kind == 'TLS'
                    counts['weak'] += all(s.get('binding') == 'WEAK' for s in values)
                    counts['versioned'] += version is not None
                    ambiguity += len(values) != 1
                    self.db.execute('INSERT INTO symbols VALUES(?,?,?,?,?,?,?,?)',
                                    (ident, name, base, version, default, kind, canonical(values), len(values) != 1))
                same = len({a[1] for a in aliases}) == 1 and all(a[2] for a in aliases)
                required = ('name', 'type', 'binding', 'visibility', 'size')
                attrs_complete = all(all(key in s and s[key] is not None for key in required) for s in obj.get('exports', []))
                complete = (obj.get('complete') is True and 'exports' in obj and same and not ambiguity and attrs_complete
                            and obj.get('export_inventory_complete') is True)
                meta = {k: v for k, v in obj.items() if k not in ('exports', 'imports', 'cxx')}
                meta.update(alias_metadata_consistent=same, ambiguous_symbol_count=ambiguity,
                            identity_basis='image/scope/recorded virtual symlink resolution; hardlink identity unavailable')
                paths = sorted(a[0] for a in aliases)
                self.db.execute('INSERT INTO elf VALUES(?,?,?,?,?,?,?,?,NULL)',
                                (ident, side, scope, path, canonical(paths), canonical(meta), canonical(counts), complete))
                self.db.executemany('INSERT INTO aliases VALUES(?,?,?,?)', ((side, scope, a, ident) for a in paths))
                self.elf_lookup[side, scope, path] = ident
                for alias in paths:
                    self.elf_lookup[side, scope, alias] = ident
                self.check()
        self.db.commit()

    def _package(self, side, value):
        ident, scope = value['id'], value['scope']
        record = value['baseline_package'] if side == 'baseline' else value['package']
        keep = ('abi', 'api', 'linking', 'overall', 'status', 'verification', 'coverage', 'confidence',
                'limitations', 'availability', 'metadata', 'match_status', 'replacement_hint', 'reason')
        assessment = {key: value[key] for key in keep if key in value}
        owned = value.get('owned_interfaces', {})
        assessment['collected_headers'] = owned.get('headers', [])
        assessment['collected_development'] = owned.get('development', [])
        self.db.execute('INSERT INTO packages(side,id,name,scope,record,assessment,peer,match_status) VALUES(?,?,?,?,?,?,?,?)',
                        (side, ident, record['name'], scope, pack(record), pack(assessment),
                         value.get('baseline_assessment_id'), value.get('match_status', 'UNKNOWN')))
        for obj in owned.get('elf', []):
            row = self.db.execute('SELECT elf_id FROM aliases WHERE side=? AND scope=? AND path=?',
                                  (side, scope, obj['path'])).fetchone()
            if row is None:
                raise ValueError('Owned ELF absent from its source manifest: ' + obj['path'])
            self.db.execute('INSERT INTO ownership VALUES(?,?,?,?,?)',
                            (side, ident, row[0], obj['path'], obj.get('ownership', {}).get('status') == 'COMPLETE'))
        for field in ('finding_ids', 'ambiguous_finding_ids'):
            self.db.executemany('INSERT INTO package_refs VALUES(?,?,?,?)',
                                ((side, ident, fid, field) for fid in value.get(field, [])))

    def _finding(self, value):
        self.finding_count += 1
        self.histogram[value['status']] += 1
        self.dimension_histogram[value['dimension'], value['status']] += 1
        group_id = None
        if value['dimension'] == 'linking':
            key = {key: value.get(key) for key in ('status', 'resolution', 'interface', 'check_id',
                   'provider_path', 'consumer_image', 'root_consumer_image', 'baseline', 'candidate')}
            encoded = canonical(key)
            group_id = 'LG-' + digest(key)[:32]
            self.db.execute('INSERT OR IGNORE INTO groups(id,key,reason,status,interface,provider) VALUES(?,?,?,?,?,?)',
                            (group_id, encoded, value.get('resolution') or 'NOT_RECORDED', value['status'],
                             value['interface'], value.get('provider_path')))
            # Collision checks use the full key; the short ID is never trusted alone.
            if self.db.execute('SELECT key FROM groups WHERE id=?', (group_id,)).fetchone()[0] != encoded:
                raise ValueError('Linking group ID collision')
        columns = ('id', 'dimension', 'component', 'interface', 'baseline', 'candidate', 'status', 'severity',
                   'confidence', 'evidence', 'detection_method', 'potential_impact', 'recommended_action')
        def original_cell(v):
            text = canonical(v) if isinstance(v, (list, dict)) else str(v)
            return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text
        csv_hash = digest({k: original_cell(value[k]) for k in columns})
        ownership = value.get('package_ownership', {})
        required = [ownership.get('consumer', {})]
        if value.get('root_consumer'):
            required.append(ownership.get('root_consumer', {}))
        if value.get('provider_path'):
            required.append(ownership.get('candidate_provider', {}))
        refs = value.get('evidence', [])
        evidence_state = ('NO_REFERENCE' if not refs else 'REFERENCED_FILES_EXIST'
                          if all(self.evidence_exists(ref) for ref in refs) else 'MISSING_OR_UNSAFE_REFERENCE')
        self.db.execute('INSERT INTO findings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (value['id'], self.finding_count, value['status'], value['dimension'], value['component'],
                         value['interface'], value.get('consumer_image', 'baseline'),
                         value.get('consumer_path', value['component'].removeprefix('header:')),
                         value.get('root_consumer_image'), value.get('root_consumer'), value.get('provider_path'),
                         value.get('resolution'), value.get('check_id'), canonical(value.get('evidence', [])),
                         pack(value), digest(value), csv_hash, group_id, evidence_state,
                         all(x.get('status') == 'COMPLETE' for x in required)))
        associations = [(ownership.get('consumer_image', 'baseline'), 'consumer', ownership.get('consumer', {})),
                        ('candidate', 'provider', ownership.get('candidate_provider', {})),
                        (value.get('root_consumer_image', 'baseline'), 'root', ownership.get('root_consumer', {}))]
        for side, role, association in associations:
            for owner in association.get('owners', []):
                self.db.execute('INSERT OR IGNORE INTO roles VALUES(?,?,?,?,?)',
                                (value['id'], side, owner, role, association.get('status') == 'COMPLETE'))
        paths = [(value.get('consumer_image', 'baseline'), ownership.get('scope', 'runtime'),
                  value.get('consumer_path', value['component'].removeprefix('header:')), 'consumer'),
                 (value.get('root_consumer_image', 'baseline'), 'runtime', value.get('root_consumer'), 'root'),
                 ('candidate', 'runtime', value.get('provider_path'), 'provider')]
        for side, scope, path, role in paths:
            resolved = self.resolve(side, scope, path)
            elf_id = self.elf_lookup.get((side, scope, path)) or self.elf_lookup.get((side, scope, resolved))
            if elf_id:
                self.db.execute('INSERT OR IGNORE INTO elf_refs VALUES(?,?,?)', (elf_id, value['id'], role))

    def read_results(self):
        dims = ('elf', 'abi', 'api', 'headers', 'linking', 'compiler_runtime', 'kernel', 'ipc',
                'commands', 'filesystem', 'packages', 'services', 'security', 'hardware', 'network',
                'performance', 'runtime')
        inventory_arrays = ('candidate_assessments', 'unassigned_finding_ids', 'unassigned_interfaces',
                            'provider_consumers', 'interface_findings')
        arrays = {('findings',), ('package_results',), ('missing_interfaces',), ('normalized_differences',), ('tests',), ('expected_tests',)}
        arrays |= {('coverage', dim, 'units') for dim in dims}
        arrays |= {('package_inventory', key) for key in inventory_arrays}
        objects = {('coverage',), ('package_inventory',)} | {('coverage', dim) for dim in dims}
        def record(path, value):
            if path == ('findings',):
                self._finding(value)
            elif path == ('package_results',):
                self._package('baseline', value)
            elif path == ('package_inventory', 'candidate_assessments'):
                self._package('candidate', value)
            elif path == ('package_inventory', 'unassigned_finding_ids'):
                self.db.execute('INSERT INTO unassigned VALUES(?)', (value,))
            elif path == ('tests',):
                keys = ('id', 'name', 'compiler', 'image', 'kind', 'status', 'compile_status', 'link_status',
                        'deployment_status', 'execution_status', 'behavior_status', 'reason', 'runtime_reason',
                        'artifact_sha256', 'returncode', 'environment_id', 'evidence')
                summary = {k: value[k] for k in keys if k in value}
                self.db.execute('INSERT INTO probe_observations(id,compiler,image,kind,status,summary) VALUES(?,?,?,?,?,?)',
                                (*[summary.get(k) for k in ('id','compiler','image','kind','status')], canonical(summary)))
            self.check()
        metadata, sha = ReportStream(self.source / 'results.json', arrays, objects, record, self.check).read()
        self.metadata = metadata
        self.source_hashes['results.json'] = sha
        if metadata.get('schema_version') != '1.2':
            raise ValueError('Report enhancement requires the explicit schema-1.2 inventories and assessments')
        for match in metadata['package_inventory']['matched_packages']:
            self.db.execute('UPDATE packages SET peer=? WHERE side=? AND id=?',
                            (match['candidate'], 'baseline', match['baseline']))
            self.db.execute('UPDATE packages SET peer=? WHERE side=? AND id=?',
                            (match['baseline'], 'candidate', match['candidate']))
        self.db.executescript('''
        CREATE INDEX finding_component ON findings(dimension,component);
        CREATE INDEX finding_consumer ON findings(consumer_image,consumer_path);
        CREATE INDEX finding_group ON findings(group_id,id);
        CREATE INDEX finding_group_lookup ON findings(id,group_id);
        CREATE INDEX finding_group_evidence ON findings(group_id,evidence);
        CREATE INDEX finding_group_stats ON findings(group_id,consumer_image,consumer_path,root_image,root_path,evidence_state,ownership_complete);
        CREATE INDEX finding_status ON findings(status,dimension,n);
        CREATE INDEX package_ref_finding ON package_refs(finding_id);
        CREATE INDEX role_package ON roles(side,package_id,finding_id);
        CREATE INDEX ownership_elf ON ownership(elf_id,package_id);
        CREATE INDEX symbol_base ON symbols(elf_id,base);
        ''')
        self.db.commit()
