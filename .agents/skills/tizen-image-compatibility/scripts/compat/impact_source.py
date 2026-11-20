"""Immutable inputs and bounded reads shared by the impact builder and browser."""
import csv
import json
from pathlib import Path
import re
import sqlite3
import zlib

from .report_io import digest, hash_file
from .report_groups import valid_consumer_path

MAX_TEXT = 32 * 1024 * 1024
SIDES = ('baseline', 'candidate')
INDEX_FILES = ('report-index.sqlite', 'overview.json', 'validation.json', 'source-after.json',
               'finding-index.csv', 'linking-group-members.csv', 'linking-findings-groups.csv')


def read_json(path, limit=MAX_TEXT):
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f'JSON exceeds input budget: {path.name}')
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError(f'Expected JSON object: {path.name}')
    return result


def unpack_limited(data):
    if not isinstance(data, bytes) or len(data) > MAX_TEXT:
        raise ValueError('Invalid source Finding payload')
    decoder = zlib.decompressobj()
    payload = decoder.decompress(data, MAX_TEXT + 1)
    if len(payload) > MAX_TEXT or not decoder.eof or decoder.unused_data:
        raise ValueError('Oversized or damaged source Finding payload')
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise ValueError('Invalid source Finding record')
    return result


def file_version(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Required regular file unavailable: {path}')
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def readonly_uri(path):
    file_version(path)
    for suffix in ('-wal', '-journal', '-shm'):
        if path.with_name(path.name + suffix).exists():
            raise ValueError('Expected a closed SQLite snapshot without journal side files')
    return path.as_uri() + '?mode=ro&immutable=1'


def connection(path):
    db = sqlite3.connect(readonly_uri(path), uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA trusted_schema=OFF')
    return db


def attach_source(db, path):
    db.execute('ATTACH DATABASE ? AS source', (readonly_uri(path),))
    db.execute('PRAGMA source.cache_size=-24576')


def virtual_path(value):
    return (isinstance(value, str) and len(value) <= 4096
            and valid_consumer_path(value) and value not in ('/.', '/..'))


def index_rows(path, fields, count, check):
    with path.open(newline='', encoding='utf-8') as stream:
        rows = csv.reader(stream)
        if tuple(next(rows, ())) != fields:
            raise ValueError(f'Unexpected v1.3 CSV schema: {path.name}')
        for n, row in enumerate(rows, 1):
            if n > count or len(row) != len(fields) or any(len(value) > 4096 for value in row):
                raise ValueError(f'Invalid v1.3 index record: {path.name}:{n + 1}')
            if n % 4096 == 0:
                check()
            yield row


def group_rows(path, count, check):
    needed = {'group_id', 'group_key', 'raw_finding_count'}
    previous_limit = csv.field_size_limit(MAX_TEXT)
    try:
        with path.open(newline='', encoding='utf-8') as stream:
            rows = csv.DictReader(stream)
            if rows.fieldnames == ['no_records'] and next(rows, None) is None:
                return
            if not needed <= set(rows.fieldnames or ()):
                raise ValueError('Invalid v1.3 Linking group export schema')
            for n, row in enumerate(rows, 1):
                if n > count or None in row:
                    raise ValueError('Invalid v1.3 Linking group export row')
                key = json.loads(row['group_key'])
                ident = row['group_id']
                count_for_group = int(row['raw_finding_count'])
                if 'LG-' + digest(key)[:32] != ident or not 1 <= count_for_group <= count:
                    raise ValueError('Linking group key or size does not match its export')
                if n % 4096 == 0:
                    check()
                yield ident, key.get('resolution') or 'NOT_RECORDED', key['status'], key['interface'], key.get('provider_path'), count_for_group
    finally:
        csv.field_size_limit(previous_limit)


class Source:
    def __init__(self, folder, check=lambda: None, replay=False):
        self.path = Path(folder).resolve()
        self.index = self.path / 'report-index.sqlite'
        self.files = [self.path / name for name in INDEX_FILES]
        self.versions = {p: file_version(p) for p in self.files}
        self.overview = read_json(self.path / 'overview.json')
        validation = read_json(self.path / 'validation.json')
        if (self.overview.get('report_version'), self.overview.get('source_schema_version')) != ('1.3', '1.2'):
            raise ValueError('Impact analysis requires the v1.3 index of a schema 1.2 report')
        self.count = self.overview.get('finding_count')
        required = ('original_csv_all_fields_and_payloads', 'all_linking_group_members',
                    'no_dangling_references', 'source_files_unchanged')
        if (type(self.count) is not int or not 0 <= self.count <= 1_000_000
                or validation.get('status') != 'PASS' or validation.get('findings') != self.count
                or not all(validation.get('checks', {}).get(k) is True for k in required)):
            raise ValueError('Source v1.3 index lacks complete built-in reconciliation')
        self.original = Path(self.overview['source_directory']).resolve()
        evidence_record = read_json(self.path / 'source-after.json')
        self.manifests = []
        if replay:
            for side in SIDES:
                name = side + '-manifest.json'
                path = self.original / name
                if file_version(path)[2] > 48 * 1024 * 1024:
                    raise ValueError('Replay manifest exceeds 48 MiB input budget')
                self.manifests.append(path)
        self.files.extend(self.manifests)
        self.versions.update({p: file_version(p) for p in self.manifests})
        readonly_uri(self.index)
        self.hashes = {p.name: hash_file(p, check) for p in self.files}
        for path in self.manifests:
            if evidence_record.get(path.name, {}).get('sha256') != self.hashes[path.name]:
                raise ValueError(f'Source manifest fails v1.3 provenance: {path.name}')
        self.assert_unchanged()

    def assert_unchanged(self):
        readonly_uri(self.index)
        if any(file_version(path) != version for path, version in self.versions.items()):
            raise ValueError('Source report changed or was replaced')

    @staticmethod
    def inspect(db, count):
        required = {
            'findings': {'n', 'id', 'status', 'dimension', 'component', 'group_id', 'payload_hash',
                         'interface', 'evidence', 'evidence_state', 'check_id', 'resolution', 'payload',
                         'consumer_image', 'consumer_path', 'root_image', 'root_path', 'provider_path'},
            'groups': {'id', 'reason', 'interface', 'status', 'provider'},
            'roles': {'finding_id', 'side', 'package_id', 'role', 'complete'},
            'packages': {'side', 'id', 'name', 'scope'},
        }
        for table, columns in required.items():
            kind = db.execute('SELECT type FROM source.sqlite_schema WHERE name=?', (table,)).fetchone()
            actual = {r[1] for r in db.execute(f'PRAGMA source.table_info({table})')}
            if not kind or kind[0] != 'table' or not columns <= actual:
                raise ValueError(f'Invalid v1.3 source table: {table}')
        if db.execute('SELECT count(*) FROM source.findings').fetchone()[0] != count:
            raise ValueError('Source index Finding count disagrees with reconciliation')


def scope_config(path):
    config = read_json(Path(path).resolve(), 1024 * 1024) if path else {'schema': 1, 'rules': []}
    if set(config) != {'schema', 'rules'} or type(config['schema']) is not int or config['schema'] != 1:
        raise ValueError('Unknown impact scope schema')
    rules = config['rules']
    if not isinstance(rules, list) or len(rules) > 2048:
        raise ValueError('Invalid or oversized scope rules')
    for rule in rules:
        keys = {'side', 'path', 'interface', 'classification', 'authority'}
        if (not isinstance(rule, dict) or set(rule) != keys
                or any(not isinstance(v, str) or not v or len(v) > 4096 for v in rule.values())
                or rule['side'] not in SIDES or not virtual_path(rule['path'])
                or rule['classification'] not in ('PUBLIC', 'INTERNAL')):
            raise ValueError('Scope rules require an exact side, path, interface and authority')
    return config
