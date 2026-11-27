"""Loopback-only, bounded, read-only report queries and evidence access."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import sqlite3
import time
from urllib.parse import parse_qs, unquote, urlsplit

from .report_store import unpack
from .report_io import evidence_path, open_payload


class ReportBrowser:
    def __init__(self, output, impact=None, history=None):
        self.output = Path(output).resolve()
        self.overview = json.loads((self.output / 'overview.json').read_text())
        self.source = Path(self.overview['source_directory']).resolve()
        self.impact = None
        self.history = None
        if impact is not None:
            from .impact_browser import ImpactBrowser
            self.impact = ImpactBrowser(self.output, impact)
        if history is not None:
            from .history import HistoryBrowser
            self.history = HistoryBrowser(history)

    def query(self, route, params):
        if route.startswith('history/'):
            if self.history is None:
                raise KeyError('History report not mounted')
            return self.history.query(route.removeprefix('history/'), params)
        if route.startswith('impact/'):
            if self.impact is None:
                raise KeyError('Impact sidecar not mounted')
            return self.impact.query(route.removeprefix('impact/'), params)
        db = sqlite3.connect((self.output / 'report-index.sqlite').as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        deadline = time.monotonic() + 20
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        try:
            return self._query(db, route, params)
        finally:
            db.close()

    def _query(self, db, route, params):
        def p(key, default=''):
            value = params.get(key, [default])[0]
            if len(value) > 4096:
                raise ValueError('Query value too long')
            return value
        limit = min(100, max(1, int(p('limit', '50'))))
        offset = max(0, int(p('offset', '0')))
        if offset > 100000000:
            raise ValueError('Offset too large')
        if route == 'overview':
            return self.overview
        if route == 'finding':
            row = db.execute('SELECT payload FROM findings WHERE id=?', (p('id'),)).fetchone()
            if row is None:
                raise KeyError('Finding not found')
            return unpack(row[0])
        if route == 'package':
            row = db.execute('SELECT summary,assessment FROM packages WHERE side=? AND id=?', (p('side'), p('id'))).fetchone()
            if row is None:
                raise KeyError('Package not found')
            return {'summary': json.loads(row[0]), 'original_assessment': unpack(row[1])}
        if route == 'elf':
            row = db.execute('SELECT summary FROM pairs WHERE id=?', (p('id'),)).fetchone()
            if row is None:
                raise KeyError('ELF pair not found')
            return json.loads(row[0])
        if route == 'group':
            row = db.execute('SELECT summary FROM groups WHERE id=?', (p('id'),)).fetchone()
            if row is None:
                raise KeyError('Group not found')
            return json.loads(row[0])
        where, args = [], []
        def equal(column, key):
            if p(key):
                where.append(column + '=?')
                args.append(p(key))
        def search(column):
            if p('q'):
                where.append(column + " LIKE ? ESCAPE '\\'")
                args.append('%' + p('q').replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        if route == 'packages':
            table, selection = 'packages', 'summary'
            search('name')
            for key in ('side', 'abi', 'api', 'linking', 'overall'):
                equal(key, key)
            order = {'name': 'name,id', 'func': 'func DESC,name,id', 'missing': 'missing DESC,name,id',
                     'findings': 'finding_count DESC,name,id', 'unknown': 'unknown_count DESC,name,id'}.get(p('sort'), 'name,id')
        elif route == 'elfs':
            table, selection, order = 'pairs', 'summary', 'id'
            if p('package'):
                where.append('(baseline IN (SELECT elf_id FROM ownership WHERE side=? AND package_id=?) OR candidate IN (SELECT elf_id FROM ownership WHERE side=? AND package_id=?))')
                args += [p('side'), p('package'), p('side'), p('package')]
        elif route == 'symbols':
            if not p('pair'):
                raise ValueError('Select an ELF pair before browsing symbols')
            table, selection, order = 'differences', 'row_json', 'n'
            equal('pair_id', 'pair')
            equal('difference_type', 'type')
            search('name')
        elif route == 'groups':
            # Sort/filter the narrow covering index before reading large evidence.
            table, selection, order = 'groups', 'id', 'raw_count DESC,id'
            equal('reason', 'reason')
            equal('status', 'status')
            search('interface')
        elif route == 'findings':
            table = 'findings'
            selection = 'id,status,dimension,component,interface,consumer_image,consumer_path,root_image,root_path,provider_path,group_id,evidence'
            order = 'n'
            for column, key in (('id', 'id'), ('status', 'status'), ('dimension', 'dimension'), ('group_id', 'group'), ('consumer_path', 'consumer'), ('root_path', 'root'), ('provider_path', 'provider')):
                equal(column, key)
            if p('group'):
                order = 'id'
            if p('package'):
                where.append('id IN (SELECT finding_id FROM package_refs WHERE side=? AND package_id=?)')
                args += [p('side'), p('package')]
            if p('elf'):
                where.append('id IN (SELECT finding_id FROM elf_refs WHERE elf_id IN (SELECT id FROM elf WHERE pair_id=?))')
                args.append(p('elf'))
        elif route == 'tests':
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='probe_observations'").fetchone():
                return {'total': 0, 'offset': 0, 'limit': limit, 'rows': [], 'available': False}
            table, selection, order = 'probe_observations', 'summary', 'n'
            for key in ('compiler', 'image', 'kind', 'status'):
                equal(key, key)
        else:
            raise KeyError('Unknown API route')
        clause = ' WHERE ' + ' AND '.join(where) if where else ''
        # SQLite may choose the huge UNIQUE full-group-key index for COUNT(*).
        # The immutable overview already reconciles the unfiltered group total.
        total = (self.overview['linking']['groups'] if route == 'groups' and not where else
                 db.execute('SELECT count(*) FROM ' + table + clause, args).fetchone()[0])
        rows = db.execute('SELECT ' + selection + ' FROM ' + table + clause + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', [*args, limit, offset])
        values = []
        for row in rows:
            if route == 'groups':
                value = json.loads(db.execute('SELECT summary FROM groups WHERE id=?', (row[0],)).fetchone()[0])
            else:
                value = dict(row) if route == 'findings' else json.loads(row[0])
            # Full source coverage/limitations and group evidence can be megabytes.
            # Keep them in detail endpoints and machine outputs, not every list page.
            omitted = {'coverage', 'limitations'} if route == 'packages' else {'group_key', 'evidence_references'} if route == 'groups' else set()
            values.append({k: v for k, v in value.items() if k not in omitted})
        return {'total': total, 'offset': offset, 'limit': limit, 'rows': values}

    def handler(self):
        browser = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                host = self.headers.get('Host', '').split(':')[0]
                if host not in ('127.0.0.1', 'localhost'):
                    self.send_error(403, 'Loopback host required')
                    return
                parsed = urlsplit(self.path)
                route = unquote(parsed.path)
                try:
                    if route.startswith('/api/'):
                        body = json.dumps(browser.query(route[5:], parse_qs(parsed.query)), ensure_ascii=False).encode()
                        self.send_response(200)
                        self.headers_for('application/json; charset=utf-8', len(body))
                        self.wfile.write(body)
                        return
                    if route == '/evidence':
                        ref = parse_qs(parsed.query).get('ref', [''])[0]
                        try:
                            path = evidence_path(browser.source, ref)
                        except (ValueError, OSError, RuntimeError):
                            self.send_error(403)
                            return
                        content_type = 'text/plain; charset=utf-8'
                    elif browser.impact is not None and route in ('/impact', '/impact.js'):
                        assets = Path(__file__).resolve().parents[2] / 'assets'
                        path = assets / ('impact-report.html' if route == '/impact' else 'impact-report.js')
                        content_type = 'text/html; charset=utf-8' if route == '/impact' else 'text/javascript; charset=utf-8'
                    elif browser.history is not None and route in ('/history', '/history.js'):
                        assets = Path(__file__).resolve().parents[2] / 'assets'
                        path = assets / ('history-report.html' if route == '/history' else 'history-report.js')
                        content_type = 'text/html; charset=utf-8' if route == '/history' else 'text/javascript; charset=utf-8'
                    else:
                        name = 'index.html' if route == '/' else route.lstrip('/')
                        allowed = {'index.html', 'enhanced-report.js', 'enhanced-report.css', 'overview.json', 'README.md'} | {p.name for p in browser.output.glob('*.csv')}
                        if name not in allowed:
                            self.send_error(404)
                            return
                        path = (browser.output / name).resolve()
                        if not path.is_relative_to(browser.output):
                            self.send_error(403)
                            return
                        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
                    with open_payload(path) as stream:
                        self.send_response(200)
                        self.headers_for(content_type, None if path.suffix == '.gz' else path.stat().st_size)
                        while True:
                            block = stream.read(65536)
                            if not block:
                                break
                            self.wfile.write(block)
                except (ValueError, sqlite3.Error) as error:
                    self.send_error(400, str(error))
                except (KeyError, FileNotFoundError):
                    self.send_error(404)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def headers_for(self, content_type, size):
                self.send_header('Content-Type', content_type)
                if size is not None:
                    self.send_header('Content-Length', str(size))
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
                self.end_headers()
        return Handler


def serve(output, port=8765, impact=None, history=None):
    if (Path(output)/'repository-index.sqlite').is_file():
        from .repository_browser import RepositoryBrowser
        if impact is not None or history is not None:
            raise ValueError('RPM repository indexes do not accept installed-image Impact or History sidecars')
        browser = RepositoryBrowser(output)
    else:
        browser = ReportBrowser(output, impact, history)
    server = ThreadingHTTPServer(('127.0.0.1', port), browser.handler())
    print('Read-only report: http://127.0.0.1:' + str(server.server_port) + '/', flush=True)
    if impact is not None:
        print('Impact analysis: http://127.0.0.1:' + str(server.server_port) + '/impact', flush=True)
    if history is not None:
        print('Historical regression: http://127.0.0.1:' + str(server.server_port) + '/history', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
