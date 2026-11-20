"""Bounded read-only queries over an impact sidecar and its original report."""
from contextlib import closing
import json
from pathlib import Path
import re
import threading
import time

from .impact_source import Source, attach_source, connection, file_version, read_json
from .impact_store import DB_NAME, ENGINE, SCHEMA
from .report_io import digest, evidence_path, hash_file

GROUP_ID = re.compile(r'IG-[a-f0-9]{64}')
NEXT_STEPS = {
    'REPLAYED_CONTRACT': 'Verify the exact recorded requirement with a matching target linker or loader trace.',
    'LINKING_OBSERVATIONS': 'Verify baseline binding and replay the same requirement under the target loader context.',
    'INTERFACE_OBSERVATION': 'Review the original contract. Use a matching SDK for header checks or matching debug information for ABI layout.',
    'RUNTIME_REVIEW': 'Validate the cross-library C++ runtime boundary, including RTTI, exceptions and unwinding where applicable.',
}


def page_rows(cursor, limit, key):
    rows = [dict(row) for row in cursor]
    return {'items': rows[:limit], 'next_cursor': key(rows[limit - 1]) if len(rows) > limit else None}


class ImpactBrowser:
    def __init__(self, report, sidecar):
        self.output = Path(sidecar).resolve()
        self.index = self.output / DB_NAME
        self.marker = self.output / 'run.json'
        self.versions = {p: file_version(p) for p in (self.index, self.marker)}
        self.data = read_json(self.marker, 1024 * 1024)
        if (self.data.get('schema') != SCHEMA or self.data.get('engine') != ENGINE
                or self.data.get('state') not in ('COMPLETE', 'PARTIAL')):
            raise ValueError('Unsupported or unpublished impact sidecar')
        self.source = Source(report, replay=bool(self.data['replay_roots']))
        if self.source.hashes != self.data.get('source_hashes'):
            raise ValueError('Stale impact sidecar: source identity changed')
        identity = {k: self.data[k] for k in ('schema', 'engine', 'source_hashes', 'config_sha256', 'replay_roots')}
        if digest(identity) != self.data.get('projection_id') or hash_file(self.index) != self.data.get('index_sha256'):
            raise ValueError('Impact sidecar content identity does not match publication')
        with closing(connection(self.index)) as db:
            row = db.execute("SELECT value FROM meta WHERE key='projection_id'").fetchone()
            if db.execute('PRAGMA user_version').fetchone()[0] != SCHEMA or not row or row[0] != self.data['projection_id']:
                raise ValueError('Impact SQLite version or projection mismatch')
        self.slots = threading.BoundedSemaphore(2)
        self.assert_unchanged()

    def assert_unchanged(self):
        self.source.assert_unchanged()
        if any(file_version(path) != version for path, version in self.versions.items()):
            raise ValueError('Published impact data changed; reopen the report')

    def query(self, route, params):
        if not self.slots.acquire(blocking=False):
            raise ValueError('Impact queries are busy; retry')
        try:
            self.assert_unchanged()
            with closing(connection(self.index)) as db:
                attach_source(db, self.source.index)
                db.execute('PRAGMA query_only=ON')
                db.execute('PRAGMA cache_size=-12288')
                db.execute('PRAGMA temp_store=MEMORY')
                stop = time.monotonic() + 2
                db.set_progress_handler(lambda: int(time.monotonic() >= stop), 10000)
                page = self._query(db, route, params)
            self.assert_unchanged()
            return {'projection_id': self.data['projection_id'], **page}
        finally:
            self.slots.release()

    def _query(self, db, route, params):
        def param(key, default=''):
            value = params.get(key, [default])[0]
            if len(value) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError('Invalid impact query parameter')
            return value

        limit = max(1, min(100, int(param('limit', '50'))))
        after = param('after')
        if after and param('projection') != self.data['projection_id']:
            raise ValueError('Cursor does not belong to this impact projection')
        if after and route in ('finding', 'members', 'consumers') and not re.fullmatch(r'[0-9]{1,9}', after):
            raise ValueError('Invalid numeric impact cursor')
        if route == 'overview':
            return {k: self.data[k] for k in ('schema', 'engine', 'mode', 'state', 'summary', 'replay_limits')}
        if route in ('groups', 'finding-groups', 'package-groups'):
            return self._groups(db, route, param, after, limit)
        if route == 'finding':
            row = db.execute("""SELECT f.id,f.status,f.dimension,f.interface,f.evidence,f.evidence_state,
                      coalesce(a.strength,'UNKNOWN') strength,coalesce(a.assessment,'UNASSESSED') assessment,
                      coalesce(a.reason,'NO_EXACT_LINKER_CHECK') reason,a.proof
                    FROM source.findings f LEFT JOIN association a ON a.n=f.n WHERE f.id=?""",
                             (param('finding'),)).fetchone()
            if not row:
                raise KeyError('Unknown Finding')
            result = dict(row)
            raw_evidence = result.pop('evidence')
            if not isinstance(raw_evidence, str) or len(raw_evidence) > 1024 * 1024:
                raise ValueError('Oversized or invalid Evidence reference list')
            result['interface'] = result['interface'][:4096]
            refs = json.loads(raw_evidence)
            if not isinstance(refs, list):
                raise ValueError('Invalid Evidence reference list')
            result['evidence'] = []
            start = max(0, int(after or '0'))
            for ref in refs[start:start + limit]:
                try:
                    available = isinstance(ref, str) and len(ref) <= 4096 and evidence_path(self.source.original, ref).is_file()
                except (ValueError, OSError, RuntimeError):
                    available = False
                result['evidence'].append({'reference': str(ref)[:4096], 'available': bool(available)})
            result['next_cursor'] = str(start + limit) if start + limit < len(refs) else None
            result['proof'] = json.loads(result['proof']) if result['proof'] else None
            return result
        ident = param('group')
        if not GROUP_ID.fullmatch(ident):
            raise ValueError('Invalid impact group ID')
        group = db.execute('SELECT * FROM impact_group WHERE id=?', (ident,)).fetchone()
        if not group:
            raise KeyError('Unknown impact group')
        g = group['g']
        if route == 'group':
            result = {k: group[k] for k in ('id', 'kind', 'subject', 'reason', 'scope', 'authority', 'rank', 'member_count')}
            result['recommendation'] = NEXT_STEPS[group['kind']]
            result['original_status_counts'] = dict(db.execute(
                'SELECT f.status,count(*) FROM group_finding m JOIN source_finding f ON f.n=m.n WHERE m.g=? GROUP BY f.status', (g,)))
            return result
        if route in ('members', 'consumers'):
            direct = "AND a.n IS NOT NULL" if route == 'consumers' else ''
            cursor = db.execute(f"""
                SELECT m.n,f.id,f.status,substr(f.interface,1,4096) interface,
                       CASE WHEN a.n IS NOT NULL THEN f.consumer_path END consumer_path,
                       CASE WHEN a.n IS NOT NULL THEN f.consumer_image END consumer_image,
                       CASE WHEN a.n IS NOT NULL THEN f.root_path END root_path,
                       CASE WHEN a.n IS NOT NULL THEN f.root_image END root_image,
                       CASE WHEN a.n IS NOT NULL THEN f.provider_path END observed_provider,
                       f.resolution,f.evidence_state,
                       coalesce(a.strength,'UNKNOWN') strength,coalesce(a.assessment,'UNASSESSED') assessment,
                       coalesce(a.reason,'NO_EXACT_LINKER_CHECK') reason
                FROM group_finding m JOIN source.findings f ON f.n=m.n
                LEFT JOIN association a ON a.n=m.n
                WHERE m.g=? AND m.n>? {direct} ORDER BY m.n LIMIT ?
            """, (g, int(after or '0'), limit + 1))
            return page_rows(cursor, limit, lambda row: str(row['n']))
        if route == 'packages':
            parts = after.split('|', 2) if after else ['', '', '']
            if len(parts) != 3:
                raise ValueError('Invalid package cursor')
            cursor = db.execute("""
                SELECT m.side,m.package_id,m.role,m.complete,m.confirmed,p.name,p.scope
                FROM package_group m JOIN source.packages p ON p.side=m.side AND p.id=m.package_id
                WHERE m.g=? AND (m.side,m.package_id,m.role)>(?,?,?)
                ORDER BY m.side,m.package_id,m.role LIMIT ?
            """, (g, *parts, limit + 1))
            return page_rows(cursor, limit, lambda row: '|'.join(row[k] for k in ('side','package_id','role')))
        raise KeyError('Unknown impact route')

    def _groups(self, db, route, param, after, limit):
        args = []
        wheres = []
        join = ''
        if route == 'finding-groups':
            join = 'JOIN group_finding m ON m.g=g.g JOIN source_finding f ON f.n=m.n'
            wheres.append('f.id=?')
            args.append(param('finding'))
        if route == 'package-groups':
            # The package-side and identity lead the materialized lookup index.
            join = '''JOIN (SELECT DISTINCT g FROM package_group
                       WHERE side=? AND package_id=?) p ON p.g=g.g'''
            args.extend((param('side'), param('package')))
        for key, column in (('kind', 'g.kind'), ('scope', 'g.scope'), ('rank', 'g.rank')):
            value = param(key)
            if value:
                wheres.append(column + '=?')
                args.append(value)
        if after:
            score, _, ident = after.partition('|')
            if score not in ('0', '1', '2') or not GROUP_ID.fullmatch(ident):
                raise ValueError('Invalid impact group cursor')
            wheres.append('(g.rank<? OR (g.rank=? AND g.id>?))')
            args.extend((int(score), int(score), ident))
        where = ' WHERE ' + ' AND '.join(wheres) if wheres else ''
        cursor = db.execute(f'''
            SELECT g.id,g.kind,g.subject,g.reason,g.scope,g.rank,g.member_count
            FROM impact_group g {join} {where} ORDER BY g.rank DESC,g.id LIMIT ?
        ''', (*args, limit + 1))
        return page_rows(cursor, limit, lambda row: str(row['rank']) + '|' + row['id'])
