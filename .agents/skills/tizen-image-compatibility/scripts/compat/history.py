"""Read-only comparison of two directed compatibility report snapshots."""
from collections import Counter
from contextlib import closing
import csv
import os
from pathlib import Path
import sqlite3
import time

from .impact_source import Source, connection, file_version, read_json, readonly_uri, unpack_limited, virtual_path
from .impact_store import ImpactGuard
from .report_io import canonical, digest, hash_file, write_json

SCHEMA = 'tizen-compat-history/1'
INDEX = 'history.sqlite'
SUCCESS = {'IDENTICAL', 'COMPATIBLE'}
FIELDS = ('dimension', 'component', 'interface', 'check_id', 'consumer_image', 'consumer_path', 'root_image', 'root_path')
DDL = '''
CREATE TABLE entries(n INTEGER PRIMARY KEY, before_id TEXT UNIQUE, after_id TEXT UNIQUE,
    dimension TEXT NOT NULL, component TEXT NOT NULL, interface TEXT NOT NULL,
    before_status TEXT, after_status TEXT, before_evidence TEXT, after_evidence TEXT,
    change TEXT NOT NULL, evidence_change TEXT NOT NULL, match TEXT NOT NULL, contract TEXT,
    CHECK(before_id IS NOT NULL OR after_id IS NOT NULL));
CREATE INDEX change_page ON entries(change,n);
CREATE INDEX dimension_page ON entries(dimension,n);
'''


def contract_key(dimension, component, interface, check, consumer_side, consumer, root_side, root):
    """Only exact startup Linking requirements have a status-independent shape."""
    if dimension != 'linking' or not check or not check.startswith(('DT_NEEDED:', 'import:', 'version:')):
        return None
    if not (virtual_path(root) and virtual_path(consumer) and virtual_path(component)):
        return None
    if (consumer_side, root_side) not in (('baseline', 'baseline'), ('candidate', 'baseline'), ('candidate', 'candidate')):
        return None
    expected = 'candidate' if root_side == 'candidate' else 'baseline consumers on candidate'
    if interface != expected + ':' + check:
        return None
    return digest([dimension, component, interface, check, consumer_side, consumer, root_side, root])


def change(before, after):
    if before == after:
        return 'PERSISTING_RISK' if before in ('UNKNOWN', 'INCOMPATIBLE') else 'UNCHANGED'
    if before is None:
        return 'NEW_UNPAIRED_RISK' if after in ('UNKNOWN', 'INCOMPATIBLE') else 'ADDED_OBSERVATION'
    if after is None:
        return 'DISAPPEARED_UNVERIFIED'
    if before == 'INCOMPATIBLE' and after in SUCCESS:
        return 'FIXED_WITH_EVIDENCE'
    if before in SUCCESS and after == 'INCOMPATIBLE':
        return 'INTRODUCED'
    return 'STATUS_CHANGED'


def evidence_change(before, after):
    if before == after:
        return 'UNCHANGED'
    if before is None or after is None:
        return 'UNPAIRED'
    if before == 'REFERENCED_FILES_EXIST':
        return 'DEGRADED'
    if after == 'REFERENCED_FILES_EXIST':
        return 'IMPROVED'
    return 'CHANGED'


def architectures(source):
    images = source.overview.get('images', {})
    return [images.get(side, {}).get('image', {}).get('architecture') for side in ('baseline', 'candidate')]


def requirement(db, alias, ident):
    row = db.execute(f'SELECT payload,payload_hash FROM {alias}.findings WHERE id=?', (ident,)).fetchone()
    data = unpack_limited(row[0])
    if digest(data) != row[1]:
        raise ValueError(f'Original Finding payload hash mismatch for {ident}')
    return (data.get('baseline'), data.get('detection_method')), data.get('resolution')


def build_history(before, after, output, scope):
    before, after, output = (Path(path).resolve() for path in (before, after, output))
    if not isinstance(scope, str) or not scope.strip() or len(scope) > 300 or any(ord(c) < 32 for c in scope):
        raise ValueError('A comparison scope declaring like-for-like direction and lineage is required')
    if any(output == p or output.is_relative_to(p) or p.is_relative_to(output) for p in (before, after)):
        raise ValueError('History output must be separate from both reports')
    for path in (before, after):
        original = Path(read_json(path / 'overview.json')['source_directory']).resolve()
        if output == original or output.is_relative_to(original) or original.is_relative_to(output):
            raise ValueError('History output overlaps an original compatibility report')
    output.mkdir(parents=True, exist_ok=False)
    temp = output / 'tmp'
    temp.mkdir()
    old_temp = os.environ.get('SQLITE_TMPDIR')
    os.environ['SQLITE_TMPDIR'] = str(temp)
    work = output / (INDEX + '.building')
    guard = ImpactGuard(output)
    started = time.monotonic()
    stage = 'input identity'
    try:
        older = Source(before, guard.check)
        newer = older if before == after else Source(after, guard.check)
        arch = architectures(older)
        if arch != architectures(newer) or any(not isinstance(a, list) or not a for a in arch):
            raise ValueError('Both snapshots must have matching, recorded architectures for both sides')
        stage = 'reconciliation'
        with closing(sqlite3.connect(work, uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA trusted_schema=OFF')
            db.execute('PRAGMA cache_size=-49152')
            # Keep temporary tables in the publication database so the guard accounts for them.
            db.set_progress_handler(guard.check, 100000)
            db.executescript(DDL)
            for alias, source in (('old_report', older), ('new_report', newer)):
                db.execute(f'ATTACH DATABASE ? AS {alias}', (readonly_uri(source.index),))
                db.execute(f'PRAGMA {alias}.cache_size=-24576')
            # Functions used only by explicit INSERT SELECT statements, never by input schemas.
            db.create_function('match_key', len(FIELDS), contract_key, deterministic=True)
            db.create_function('classify_change', 2, change, deterministic=True)
            db.create_function('evidence_change', 2, evidence_change, deterministic=True)
            for side, alias, source in (('older', 'old_report', older), ('newer', 'new_report', newer)):
                if side == 'newer' and before == after:
                    db.execute('CREATE TABLE newer AS SELECT * FROM older ORDER BY rowid')
                else:
                    db.execute(f'''CREATE TABLE {side} AS SELECT id,status,dimension,component,interface,
                        evidence_state AS evidence,payload_hash AS hash,match_key({','.join(FIELDS)}) AS contract
                        FROM {alias}.findings NOT INDEXED ORDER BY rowid''')
                db.execute(f'CREATE UNIQUE INDEX {side}_id ON {side}(id)')
                db.execute(f'CREATE INDEX {side}_contract ON {side}(contract,id) WHERE contract IS NOT NULL')
                if db.execute(f'SELECT count(*) FROM {side}').fetchone()[0] != source.count:
                    raise ValueError('History source Finding count mismatch')
            db.execute('''INSERT INTO entries SELECT NULL,o.id,n.id,o.dimension,o.component,o.interface,
                o.status,n.status,o.evidence,n.evidence,classify_change(o.status,n.status),
                evidence_change(o.evidence,n.evidence),'EXACT_ID_AND_PAYLOAD',o.contract
                FROM older o JOIN newer n ON n.id=o.id AND n.hash=o.hash AND n.status=o.status
                AND n.dimension=o.dimension AND n.component=o.component AND n.interface=o.interface
                AND n.contract IS o.contract ORDER BY o.rowid''')
            db.execute('''CREATE TABLE unique_contract AS SELECT o.contract
                FROM (SELECT contract FROM older WHERE contract IS NOT NULL GROUP BY contract HAVING count(*)=1) o
                INNER JOIN (SELECT contract FROM newer WHERE contract IS NOT NULL GROUP BY contract HAVING count(*)=1) n
                ON n.contract=o.contract''')
            possible = db.execute('''SELECT o.id,n.id,o.dimension,o.component,o.interface,o.status,n.status,
                 o.evidence,n.evidence,o.contract FROM unique_contract k JOIN older o USING(contract)
                 JOIN newer n USING(contract) WHERE o.id<>n.id
                 AND NOT EXISTS(SELECT 1 FROM entries e WHERE e.before_id=o.id)
                 AND NOT EXISTS(SELECT 1 FROM entries e WHERE e.after_id=n.id) ORDER BY o.id''')
            for row in possible:
                old_id, new_id, dimension, component, interface, left, right, left_ev, right_ev, key = tuple(row)
                prior, old_resolution = requirement(db, 'old_report', old_id)
                next_requirement, new_resolution = requirement(db, 'new_report', new_id)
                if prior[0] is None or not prior[1] or prior != next_requirement:
                    continue
                outcome = change(left, right)
                if ((outcome == 'FIXED_WITH_EVIDENCE' and new_resolution != 'verified')
                        or (outcome == 'INTRODUCED' and old_resolution != 'verified')):
                    outcome = 'STATUS_CHANGED_UNVERIFIED'
                db.execute('''INSERT INTO entries(before_id,after_id,dimension,component,interface,
                    before_status,after_status,before_evidence,after_evidence,change,evidence_change,match,contract)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                           (old_id, new_id, dimension, component, interface, left, right, left_ev, right_ev,
                            outcome, evidence_change(left_ev, right_ev), 'UNIQUE_LINKER_CONTRACT', key))
            for side, column in (('older', 'before_id'), ('newer', 'after_id')):
                left = side == 'older'
                fields = ('s.id,NULL', 's.status,NULL', 's.evidence,NULL') if left else ('NULL,s.id','NULL,s.status','NULL,s.evidence')
                statuses = fields[1]
                db.execute(f'''INSERT INTO entries SELECT NULL,{fields[0]},s.dimension,s.component,s.interface,
                    {statuses},{fields[2]},classify_change({statuses}),'UNPAIRED',
                    CASE WHEN EXISTS(SELECT 1 FROM {'newer' if left else 'older'} peer WHERE peer.id=s.id)
                             THEN 'ID_CONTEXT_OR_PAYLOAD_MISMATCH'
                         WHEN s.contract IS NOT NULL THEN 'AMBIGUOUS_OR_UNPROVEN_CONTRACT'
                         ELSE 'NO_STABLE_MATCH' END,s.contract
                    FROM {side} s WHERE NOT EXISTS(SELECT 1 FROM entries e WHERE e.{column}=s.id) ORDER BY s.rowid''')
            counts = tuple(db.execute('SELECT count(before_id),count(after_id) FROM entries').fetchone())
            if counts != (older.count, newer.count) or db.execute('PRAGMA main.quick_check(1)').fetchone()[0] != 'ok':
                raise ValueError('History index reconciliation failed')
            summary = {key: dict(db.execute(f'SELECT {key},count(*) FROM entries GROUP BY {key}'))
                       for key in ('change', 'match', 'evidence_change')}
            with (output / 'changes.csv').open('x', newline='') as stream:
                writer = csv.writer(stream)
                cursor = db.execute('SELECT * FROM entries ORDER BY n')
                writer.writerow([field[0] for field in cursor.description])
                for index, row in enumerate(cursor):
                    if index % 4096 == 0:
                        guard.check()
                    writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in row])
            for table in ('older', 'newer', 'unique_contract'):
                db.execute(f'DROP TABLE {table}')
            db.commit()
        older.assert_unchanged()
        newer.assert_unchanged()
        stage = 'publication'
        identity = {'before': older.hashes, 'after': newer.hashes, 'scope': scope,
                    'direction': 'baseline consumers on candidate', 'architecture': arch, 'schema': SCHEMA}
        info = identity | {'projection_id': digest(identity), 'state': 'COMPLETE', 'before_count': older.count,
                           'after_count': newer.count, 'summary': summary,
                           'before_coverage': older.overview.get('original_coverage'),
                           'after_coverage': newer.overview.get('original_coverage'),
                           'index_sha256': hash_file(work, guard.check),
                           'csv_sha256': hash_file(output / 'changes.csv', guard.check), 'wall_seconds': time.monotonic() - started}
        guard.check(force=True)
        write_json(output / 'run.pending.json', info)
        os.replace(work, output / INDEX)
        os.replace(output / 'run.pending.json', output / 'run.json')
        return info
    except BaseException as exc:
        write_json(output / 'failure.json', {'state': 'FAILED', 'stage': stage, 'error': str(exc)})
        raise
    finally:
        if old_temp is None:
            os.environ.pop('SQLITE_TMPDIR', None)
        else:
            os.environ['SQLITE_TMPDIR'] = old_temp


class HistoryBrowser:
    def __init__(self, folder):
        folder = Path(folder).resolve()
        self.index, self.marker = folder / INDEX, folder / 'run.json'
        self.versions = {p:file_version(p) for p in (self.index, self.marker)}
        self.info = read_json(self.marker)
        if (self.info.get('state') != 'COMPLETE' or self.info.get('schema') != SCHEMA
                or self.info.get('index_sha256') != hash_file(self.index)):
            raise ValueError('History report is unpublished, incompatible or changed')

    def query(self, route, params):
        if any(file_version(p) != version for p, version in self.versions.items()):
            raise ValueError('History report changed during service')
        if route == 'overview':
            return self.info
        if route != 'entries':
            raise KeyError('Unknown history route')
        limit = min(100, max(1, int(params.get('limit', ['50'])[0])))
        after = int(params.get('after', ['0'])[0])
        classification = params.get('change', [''])[0]
        if after < 0 or after > 2_000_000 or len(classification) > 64:
            raise ValueError('Invalid history cursor or classification')
        clause = ' AND change=?' if classification else ''
        values = (after, classification, limit + 1) if classification else (after, limit + 1)
        with closing(connection(self.index)) as db:
            rows = [dict(row) for row in db.execute(f'''SELECT n,before_id,after_id,dimension,
                substr(component,1,4096) AS component,substr(interface,1,4096) AS interface,
                before_status,after_status,before_evidence,after_evidence,change,evidence_change,match,contract
                FROM entries WHERE n>?{clause} ORDER BY n LIMIT ?''', values)]
        return {'items': rows[:limit], 'next_cursor': rows[limit-1]['n'] if len(rows) > limit else None}
