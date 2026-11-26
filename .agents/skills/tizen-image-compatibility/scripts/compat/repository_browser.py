"""Optional bounded index for the repository CSVs, independent of installed-RPM reports."""
import csv
import json
from pathlib import Path
import sqlite3
import time

from .core import canonical, write_json
from .report_browser import ReportBrowser
from .report_io import ResourceGuard, hash_file

TABLES = {'packages':'packages.csv','package-symbols':'package-symbol-summary.csv',
          'elf':'elf-symbol-summary.csv','symbols':'symbol-differences.csv','errors':'extraction-errors.csv'}


def build(source, output):
    source,output = Path(source).resolve(),Path(output).resolve()
    if source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Repository index output must be separate from the original report')
    marker = source/'rpm-repository.json'
    inputs = [source/name for name in TABLES.values()]
    if any(p.is_symlink() or not p.is_file() for p in [marker,*inputs]) or marker.stat().st_size>65536:
        raise ValueError('Expected a complete RPM repository report')
    overview = json.loads(marker.read_text())
    if overview['scope'] not in ('RPM_REPOSITORY_PAYLOAD','RPM_REPOSITORY_METADATA'):
        raise ValueError('Unknown RPM repository report scope')
    output.mkdir(parents=True,exist_ok=False)
    guard = ResourceGuard(output,disk_budget=2*sum(p.stat().st_size for p in inputs)+1024**3)
    started = time.monotonic()
    try:
        guard.check(force=True)
        before = {p.name:hash_file(p,guard.check) for p in [marker,*inputs]}
        rows = {}
        with sqlite3.connect(output/'repository-index.sqlite') as db:
            db.set_progress_handler(lambda: (guard.check(),0)[1],10000)
            db.execute('CREATE TABLE rows (kind TEXT,n INTEGER,package_id TEXT,component TEXT,payload TEXT,PRIMARY KEY(kind,n))')
            for key,name in TABLES.items():
                rows[key] = 0
                with (source/name).open(newline='') as stream:
                    for index,row in enumerate(csv.DictReader(stream),1):
                        payload = canonical(row)
                        if None in row or any(value is None for value in row.values()) or len(payload)>2*1024**2:
                            raise ValueError('Malformed or oversized repository CSV row: '+name)
                        db.execute('INSERT INTO rows VALUES(?,?,?,?,?)',(key,index,row.get('package_id',row.get('id','')),
                                                                        row.get('component',''),payload))
                        rows[key] = index
                        guard.check()
            db.execute('CREATE INDEX package_lookup ON rows(kind,package_id,n)')
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                raise ValueError('RPM repository index integrity check failed')
        if before != {p.name:hash_file(p,guard.check) for p in [marker,*inputs]}:
            raise ValueError('Repository report changed during indexing')
        overview.update(source_directory=str(source),rows=rows,index_scope='rpm-repository')
        write_json(output/'overview.json',overview)
        assets = Path(__file__).resolve().parents[2]/'assets'
        for leaf,original in [('index.html','repository-report.html'),('enhanced-report.js','repository-report.js')]:
            (output/leaf).write_bytes((assets/original).read_bytes())
        guard.check(force=True)
        write_json(output/'validation.json',{'status':'PASS','source_sha256':before,'rows':rows})
        write_json(output/'run.json',{'status':'PASS','elapsed_seconds':time.monotonic()-started,'resources':guard.last_snapshot})
    except BaseException as error:
        write_json(output/'run.json',{'status':'FAIL','error':str(error),'resources':guard.last_snapshot})
        raise


class RepositoryBrowser(ReportBrowser):
    def __init__(self,output):
        super().__init__(output)
        if json.loads((self.output/'run.json').read_text()).get('status')!='PASS':
            raise ValueError('RPM repository index is incomplete')

    def query(self,route,params):
        if route=='overview':
            return self.overview
        if route not in TABLES:
            raise KeyError(route)
        limit = min(20,max(1,int(params.get('limit',['20'])[0])))
        after = max(0,int(params.get('after',['0'])[0]))
        package = params.get('package',[''])[0]
        if len(package)>128:
            raise ValueError('Invalid package filter')
        sql = 'SELECT n,payload FROM rows WHERE kind=? AND n>?'
        args = [route,after]
        if package:
            sql += ' AND package_id=?'
            args.append(package)
        with sqlite3.connect((self.output/'repository-index.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            rows = db.execute(sql+' ORDER BY n LIMIT ?',(*args,limit+1)).fetchall()
        page = rows[:limit]
        return {'rows':[json.loads(payload) for _,payload in page],
                'next_after':page[-1][0] if len(rows)>limit else None}
