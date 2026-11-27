"""Disk-backed detail rows for directional static linking checks."""
from collections import Counter, OrderedDict, defaultdict
import os
import posixpath
import sqlite3

from .core import canonical, digest, finding
from .report_io import csv_rows


COLUMNS = ('id', 'anchor_finding_id', 'image', 'consumer', 'check_id', 'state',
           'provider', 'roots_count', 'search_context_hash')


def group_context(context):
    """Share search inputs, leaving symbol-specific evidence on the detail row."""
    stable = {k: v for k, v in context.items() if k != 'symbol_scope'}
    if 'symbol_scope' in context:
        stable['scope_providers'] = list(dict.fromkeys((p['image'], p['path']) for p in context['symbol_scope']))
    return stable


class LinkingDetails:
    """Stage uniques and their root relations on disk and stream the CSV once."""
    def __init__(self, path):
        self.path = path
        self.tokens = OrderedDict()
        self.records = {}
        self.root_numbers = {}
        self.root_paths = []
        self.direct = {}
        self.counts = {}

    def __enter__(self):
        self.previous_temp = os.environ.get('SQLITE_TMPDIR')
        os.environ['SQLITE_TMPDIR'] = str(self.path.parent)
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA temp_store=FILE')
        # Disposable database. The report commits only after staging and CSV export.
        self.db.execute('PRAGMA journal_mode=OFF')
        self.db.execute('PRAGMA synchronous=OFF')
        self.db.execute('PRAGMA cache_size=-32768')
        self.db.executescript('''
            CREATE TABLE checks(
                n INTEGER PRIMARY KEY, id TEXT UNIQUE, anchor TEXT, image TEXT, consumer TEXT, check_id TEXT, state TEXT,
                provider TEXT, context TEXT, status TEXT, direction TEXT, direct INTEGER
            );
            CREATE TABLE roots(check_no INTEGER, root_no INTEGER);
        ''')
        return self

    def __exit__(self, *_):
        self.db.close()
        if self.previous_temp is None:
            os.environ.pop('SQLITE_TMPDIR', None)
        else:
            os.environ['SQLITE_TMPDIR'] = self.previous_temp

    def repeat(self, key, root):
        row = self.tokens.get(key)
        if row is None:
            return False
        self.tokens.move_to_end(key)
        self.record_root(row, root)
        return True

    def record_root(self, check_no, root):
        # Sequential writes avoid indexing repeated long root paths during resolution.
        if root not in self.root_numbers:
            self.root_numbers[root] = len(self.root_paths)
            self.root_paths.append(root)
        self.db.execute('INSERT INTO roots VALUES(?,?)', (check_no, self.root_numbers[root]))

    def add(self, item, root, key, aggregate):
        direction, image = item['root_consumer_image'], item['consumer_image']
        context = item.get('search_context', {})
        context_hash = digest(canonical(context).encode())
        entry_id = item['id']
        if aggregate:
            group = group_context(context)
            if item['check_id'].startswith('DT_NEEDED:'):
                needed = item['check_id'].split(':',1)[1]
                if '/' not in needed:
                    group['search_paths'] = [posixpath.dirname(p) if isinstance(p,str) and posixpath.basename(p)==needed
                                             else p for p in group.get('search_paths', [])]
            key_fields = [direction, image, item['component'], item['resolution'], group]
            anchor = 'TC-' + digest(canonical(['linking detail group', *key_fields]).encode())[:16]
            if anchor not in self.records:
                record = finding('linking', item['component'], item['interface'].split(':', 1)[0] +
                                 (':dependency checks' if item['check_id'].startswith('DT_NEEDED:') else ':symbol checks'),
                                 None, None, item['status'], item['severity'], item['detection_method'],
                                 item['evidence'], item['potential_impact'], item['recommended_action'],
                                 reason_code=item['reason_code'])
                record.update(id=anchor, check_id='dependency checks' if item['check_id'].startswith('DT_NEEDED:')
                              else 'symbol checks', consumer_path=item['consumer_path'],
                              consumer_image=image, root_consumer_image=direction, resolution=item['resolution'],
                              search_context=group, provider_path=None)
                self.records[anchor] = record
        else:
            anchor = entry_id
        added = self.db.execute('INSERT OR IGNORE INTO checks VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)',
                                (entry_id, anchor, image, item['consumer_path'], item['check_id'], item['resolution'],
                                 item.get('provider_path'), context_hash, item['status'], direction,
                                 int(root == item['consumer_path'] and direction == image)))
        check_no = added.lastrowid if added.rowcount else self.db.execute(
            'SELECT n FROM checks WHERE id=?', (entry_id,)).fetchone()[0]
        self.record_root(check_no, root)
        self.tokens[key] = check_no
        self.tokens.move_to_end(key)
        if len(self.tokens) > 8192:
            self.tokens.popitem(last=False)

    def finish(self, csv_path=None):
        self.tokens.clear()
        self.db.execute('CREATE INDEX by_anchor ON checks(anchor)')
        self.db.execute('CREATE INDEX by_check_root ON roots(check_no,root_no)')
        for anchor, count in self.db.execute('SELECT anchor, count(*) FROM checks GROUP BY anchor'):
            item = self.records.get(anchor)
            if item is None:
                continue
            item['aggregated_checks'] = count
            item['example_check_ids'] = [r[0] for r in self.db.execute(
                'SELECT DISTINCT check_id FROM checks WHERE anchor=? ORDER BY check_id LIMIT 20', (anchor,))]
            roots = sorted(self.root_paths[r[0]] for r in self.db.execute(
                'SELECT DISTINCT root_no FROM checks JOIN roots ON n=check_no WHERE anchor=?', (anchor,)))
            item['root_consumer'] = item['consumer_path'] if item['consumer_path'] in roots else roots[0]
            item['roots'] = {'count': len(roots), 'examples': roots[:20]}
            item['_root_paths'] = roots
        by_status = dict(self.db.execute('SELECT status,count(*) FROM checks GROUP BY status'))
        by_state = dict(self.db.execute('SELECT state,count(*) FROM checks GROUP BY state'))
        kinds = dict(self.db.execute("""
            SELECT CASE WHEN instr(check_id,':') THEN substr(check_id,1,instr(check_id,':')-1)
                        ELSE check_id END kind, count(*) FROM checks GROUP BY kind
        """))
        self.counts = {'rows': sum(by_status.values()), 'by_status': by_status, 'by_state': by_state,
                       'by_kind': kinds, 'aggregated_findings': len(self.records), 'csv_written': csv_path is not None}
        direct = defaultdict(Counter)
        for consumer, status, count in self.db.execute("""
            SELECT consumer, status, count(*) FROM (
                SELECT consumer, check_id, CASE
                    WHEN sum(status='INCOMPATIBLE') THEN 'INCOMPATIBLE'
                    WHEN sum(status='UNKNOWN') THEN 'UNKNOWN'
                    ELSE 'COMPATIBLE' END status
                FROM checks WHERE direction='baseline' AND image='baseline' AND direct
                    AND (check_id LIKE 'import:%' OR check_id LIKE 'version:%'
                         OR check_id LIKE 'DT_NEEDED:%' OR check_id LIKE 'copy relocation:%')
                GROUP BY consumer, check_id
            ) GROUP BY consumer, status
        """):
            direct[consumer][status] = count
        self.direct = direct
        if csv_path is not None:
            rows = self.db.execute("""
                SELECT id,anchor,image,consumer,check_id,state,provider,
                    (SELECT count(DISTINCT root_no) FROM roots WHERE check_no=checks.n),context
                FROM checks ORDER BY id
            """)
            csv_rows(csv_path, COLUMNS, (dict(zip(COLUMNS, row)) for row in rows))
        return list(self.records.values())
