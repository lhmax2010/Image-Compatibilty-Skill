"""Build and independently reconcile a report projection without running analysis."""
import csv
from collections import Counter
import html
import json
import os
from pathlib import Path
import resource
import shlex
import time

from .report_io import ResourceGuard, canonical, csv_rows, digest, hash_file, write_json
from .report_store import Store, COUNTS, unpack
from .report_symbols import build_pairs, compare_symbols, summarize_packages
from .report_groups import build_groups


def flatten(value, prefix=''):
    result = {}
    for key, item in value.items():
        name = prefix + key
        if isinstance(item, dict):
            result.update(flatten(item, name + '.'))
        else:
            result[name] = item
    return result


def export(store):
    db, output, check = store.db, store.output, store.check
    counts = {}
    specs = {
        'package-symbol-summary.csv': 'SELECT summary FROM packages ORDER BY side,name,id',
        'elf-symbol-summary.csv': 'SELECT summary FROM pairs ORDER BY id',
        'symbol-differences.csv': ('SELECT row_json FROM differences WHERE difference_type <> \'MATCHED\' ORDER BY n'
                                  if store.metadata.get('symbol_differences_mode') == 'changes'
                                  else 'SELECT row_json FROM differences ORDER BY n'),
        'linking-findings-groups.csv': 'SELECT summary FROM groups ORDER BY id',
    }
    for filename, query in specs.items():
        transform = (lambda x: x) if filename in ('symbol-differences.csv', 'linking-findings-groups.csv') else flatten
        # Determine the complete union of columns, including absent-side statistics.
        # Package/pair records are small; symbol and group fields have a fixed shape.
        columns = set()
        for index, row in enumerate(db.execute(query)):
            columns.update(transform(json.loads(row[0])))
            check()
            if filename in ('symbol-differences.csv', 'linking-findings-groups.csv'):
                break
        def rows():
            n = 0
            for row in db.execute(query):
                n += 1
                yield transform(json.loads(row[0]))
            counts[filename] = n
        csv_rows(output / filename, sorted(columns) or ['no_records'], rows(), check)
    simple = {
        'finding-index.csv': ('SELECT id,status,dimension,n,payload_hash,group_id FROM findings ORDER BY n',
                              ['id', 'status', 'dimension', 'n', 'payload_hash', 'group_id']),
        'linking-group-members.csv': ('SELECT group_id,id,consumer_image,consumer_path,root_image,root_path,provider_path FROM findings WHERE group_id IS NOT NULL ORDER BY group_id,id',
                                      ['group_id', 'id', 'consumer_image', 'consumer_path', 'root_image', 'root_path', 'provider_path']),
        'unassigned-findings.csv': ('SELECT id FROM unassigned ORDER BY id', ['id']),
    }
    for filename, (query, columns) in simple.items():
        csv_rows(output / filename, columns, (dict(r) for r in db.execute(query)), check)
        counts[filename] = db.execute('SELECT count(*) FROM (' + query + ')').fetchone()[0]
    return counts


def validate(store, row_counts):
    db, check = store.db, store.check
    checks = {}
    def require(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise ValueError('Reconciliation failed: ' + name)
    csv.field_size_limit(64 * 1024 * 1024)
    n = 0
    with (store.source / 'findings.csv').open(newline='') as stream:
        indexed = iter(db.execute('SELECT id,status,csv_hash,payload,payload_hash FROM findings ORDER BY n'))
        for row in csv.DictReader(stream):
            stored = next(indexed, None)
            if stored is None or stored['id'] != row['id'] or stored['csv_hash'] != digest(row):
                raise ValueError('Original JSON/CSV disagreement at finding row ' + str(n + 1))
            payload = unpack(stored['payload'])
            if digest(payload) != stored['payload_hash'] or payload['id'] != row['id'] or payload['status'] != row['status']:
                raise ValueError('Lossless payload verification failed: ' + row['id'])
            n += 1
            check()
        require('original_csv_all_fields_and_payloads', next(indexed, None) is None and n == store.finding_count)
    require('status_histogram', dict(db.execute('SELECT status,count(*) FROM findings GROUP BY status')) == dict(store.histogram))
    inv = store.metadata['package_inventory']
    assessment_counts = {'baseline': store.metadata['package_results']['record_count'],
                         'candidate': inv['candidate_assessments']['record_count']}
    for side, assessed in assessment_counts.items():
        installed = inv[side + '_package_count']
        rows = dict(db.execute('SELECT scope,count(*) FROM packages WHERE side=? GROUP BY scope', (side,)))
        require(side + '_package_assessments', assessed == sum(rows.values()))
        # The installed inventory is a runtime total; source assessments may be
        # partial or include SDK records. Keep a null installed total as unknown.
        require(side + '_package_count', installed is None or
                type(installed) is int and installed == rows.get('runtime', 0))
    with (store.source / 'packages.csv').open(newline='') as stream:
        seen = set()
        for row in csv.DictReader(stream):
            package = db.execute('SELECT * FROM packages WHERE side=? AND id=?', ('baseline', row['id'])).fetchone()
            if package is None or row['id'] in seen:
                raise ValueError('Original package CSV identity mismatch')
            seen.add(row['id'])
            summary, original = json.loads(package['summary']), unpack(package['assessment'])
            for key in ('abi', 'api', 'linking', 'overall', 'verification'):
                if row[key] != str(summary[key]):
                    raise ValueError('Changed package assessment ' + row['id'] + ':' + key)
            for key in ('coverage', 'confidence', 'limitations'):
                if summary[key] != original.get(key):
                    raise ValueError('Changed original package field ' + key)
            check()
        require('all_original_package_statuses', len(seen) == assessment_counts['baseline'])
    for package in db.execute('SELECT * FROM packages'):
        summary = json.loads(package['summary'])
        totals = Counter({k: 0 for k in COUNTS})
        # Recompute directly from indexed export rows, independent of stored ELF counts.
        objects = db.execute('SELECT DISTINCT elf_id FROM ownership WHERE side=? AND package_id=?', (package['side'], package['id'])).fetchall()
        for obj in objects:
            for symbol in db.execute('SELECT * FROM symbols WHERE elf_id=?', (obj[0],)):
                attrs = json.loads(symbol['attrs'])
                totals['exports'] += 1
                totals['func'] += symbol['type'] == 'FUNC'
                totals['ifunc'] += symbol['type'] in ('IFUNC', 'GNU_IFUNC')
                totals['object'] += symbol['type'] == 'OBJECT'
                totals['tls'] += symbol['type'] == 'TLS'
                totals['weak'] += all(a.get('binding') == 'WEAK' for a in attrs)
                totals['versioned'] += symbol['version'] is not None
        if dict(totals) != summary['observed_counts'] or len(objects) != summary['observed_owned_elf_count']:
            raise ValueError('Package/ELF/symbol count disagreement: ' + package['id'])
        if package['side'] == 'candidate' and summary['overall'] != unpack(package['assessment']).get('status', 'UNKNOWN'):
            raise ValueError('Candidate inventory status changed')
        check()
    checks['independent_package_elf_symbol_recount'] = True
    checks['candidate_status_preserved'] = True
    require('unassigned_ids_preserved', db.execute('SELECT count(*) FROM unassigned').fetchone()[0] == inv['unassigned_finding_ids']['record_count'])
    require('no_dangling_references', not db.execute('SELECT id FROM unassigned EXCEPT SELECT id FROM findings').fetchone()
            and not db.execute('SELECT finding_id FROM package_refs EXCEPT SELECT id FROM findings').fetchone())
    require('all_findings_assigned_or_retained', not db.execute('SELECT id FROM findings WHERE id NOT IN (SELECT finding_id FROM package_refs) AND id NOT IN (SELECT id FROM unassigned)').fetchone())
    linking = db.execute("SELECT count(*) FROM findings WHERE dimension='linking'").fetchone()[0]
    require('all_linking_group_members', linking == db.execute('SELECT coalesce(sum(raw_count),0) FROM groups').fetchone()[0]
            == row_counts['linking-group-members.csv'])
    require('no_non_linking_group_members', not db.execute("SELECT id FROM findings WHERE (dimension='linking') != (group_id IS NOT NULL)").fetchone())
    require('finding_index_complete', row_counts['finding-index.csv'] == n)
    require('required_package_csv_complete', row_counts['package-symbol-summary.csv'] == sum(assessment_counts.values()))
    # Read back every generated CSV, including all symbol/group records.
    for filename, expected in row_counts.items():
        count = 0
        with (store.output / filename).open(newline='') as stream:
            for row in csv.DictReader(stream):
                if None in row:
                    raise ValueError('Malformed generated CSV: ' + filename)
                count += 1
                check()
        require('csv_rows:' + filename, count == expected)
    recorded_tests = store.metadata.get('summary', {}).get('total_tests')
    if type(recorded_tests) is int:
        require('probe_observation_count', recorded_tests == db.execute('SELECT count(*) FROM probe_observations').fetchone()[0])
    return {'status': 'PASS', 'checks': checks, 'findings': n, 'status_counts': dict(store.histogram),
            'unassigned_findings': inv['unassigned_finding_ids']['record_count'], 'csv_rows': row_counts}


def overview(store, reasons):
    db = store.db
    images = {}
    for side in ('baseline', 'candidate'):
        totals = Counter({k: 0 for k in COUNTS})
        for row in db.execute('SELECT counts FROM elf WHERE side=?', (side,)):
            totals.update(json.loads(row[0]))
        attributed = Counter({k: 0 for k in COUNTS})
        for row in db.execute('SELECT summary FROM packages WHERE side=?', (side,)):
            attributed.update(json.loads(row[0])['observed_counts'])
        images[side] = {'image': store.manifests[side].get('image'),
                        'inventory': store.manifests[side].get('package_inventory'),
                        'package_rows': db.execute('SELECT count(*) FROM packages WHERE side=?', (side,)).fetchone()[0],
                        'collected_elf_rows': db.execute('SELECT count(*) FROM raw_elf WHERE side=?', (side,)).fetchone()[0],
                        'canonical_elf_count': db.execute('SELECT count(*) FROM elf WHERE side=?', (side,)).fetchone()[0],
                        'incomplete_canonical_elf_count': db.execute('SELECT count(*) FROM elf WHERE side=? AND complete=0', (side,)).fetchone()[0],
                        'observed_unique_export_counts': dict(totals), 'observed_package_attributed_export_counts': dict(attributed)}
    linking = {'raw_findings': db.execute("SELECT count(*) FROM findings WHERE dimension='linking'").fetchone()[0],
               'groups': db.execute('SELECT count(*) FROM groups').fetchone()[0],
               'distinct_interfaces': db.execute('SELECT count(DISTINCT interface) FROM groups').fetchone()[0],
               'groups_with_multiple_observations': db.execute('SELECT count(*) FROM groups WHERE raw_count>1').fetchone()[0],
               'observations_in_multi_member_groups': db.execute('SELECT coalesce(sum(raw_count),0) FROM groups WHERE raw_count>1').fetchone()[0],
               'reason_status_distribution': reasons}
    return {'report_version': '1.3', 'source_schema_version': store.metadata['schema_version'],
            'source_directory': str(store.source), 'images': images, 'finding_count': store.finding_count,
            'status_counts': dict(store.histogram),
            'dimension_status_counts': [{'dimension': d, 'status': s, 'count': n} for (d, s), n in sorted(store.dimension_histogram.items())],
            'unassigned_finding_count': db.execute('SELECT count(*) FROM unassigned').fetchone()[0],
            'symbol_difference_rows': dict(db.execute('SELECT difference_type,count(*) FROM differences GROUP BY difference_type')),
            'linking': linking, 'original_coverage': store.metadata.get('coverage'),
            'original_verification': store.metadata.get('verification'), 'original_overall': store.metadata.get('status'),
            'original_probe_summary': store.metadata.get('summary'), 'original_matrix': store.metadata.get('matrix'),
            'original_quality_gate': store.metadata.get('quality_gate'),
            'notice': 'Display statistics only. Dynamic exports are not public API. Original compatibility, coverage and verification are unchanged. Counts marked UNKNOWN lack sufficient evidence; observed counts are partial. Groups retain distinct consumers and original outcomes.'}


def assets(output, data):
    asset_dir = Path(__file__).resolve().parents[2] / 'assets'
    for name in ('enhanced-report.js', 'enhanced-report.css'):
        (output / name).write_bytes((asset_dir / name).read_bytes())
    fragment = '<p>' + html.escape(data['notice']) + '</p><pre>' + html.escape(json.dumps({
        'original_overall': data['original_overall'], 'original_verification': data['original_verification'],
        'finding_count': data['finding_count'], 'status_counts': data['status_counts'],
        'images': data['images'], 'linking': data['linking']}, ensure_ascii=False, indent=2)) + '</pre>'
    template = (asset_dir / 'enhanced-report.html').read_text()
    command = shlex.join(['python3', str(Path(__file__).resolve().parents[1] / 'enhance_report.py'), 'serve', '--report', str(output)])
    (output / 'index.html').write_text(template.replace('<!--OVERVIEW-->', fragment).replace('<!--COMMAND-->', html.escape(command)))
    links = '\n'.join('- [' + p.name + '](' + p.name + ')' for p in sorted(output.glob('*.csv')))
    (output / 'README.md').write_text('# Report-only enhancement v1.3\n\n' + data['notice'] + '\n\n'
        'Open `index.html` for a static overview. Interactive search requires the loopback server (no Internet needed):\n\n'
        '```bash\n' + command + '\n```\n\nOpen http://127.0.0.1:8765/. `file://` does not support the interactive browser.\n\n'
        'All CSV rows and original finding payloads are retained in `report-index.sqlite`. Evidence is read from the unchanged source report at '
        + data['source_directory'] + '; keep that directory available. Evidence links indicate presence, not verification completeness.\n\n'
        + links + '\n\nSymbol counters deduplicate exact decorated names within virtual-symlink-canonical ELFs. Shared package owners overlap; image counts do not. '
        'Flattened CSV fields ending in `observed_counts`/`observed_differences` are observations, not complete inventories. '
        'Null values serialize as UNKNOWN. SQLite keeps nulls and exact original payloads. CSV values are spreadsheet-formula escaped.\n')


def build(source, output, guard_factory=ResourceGuard):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Output must be separate from the immutable source report')
    required = ('baseline-manifest.json', 'candidate-manifest.json', 'results.json', 'findings.csv', 'packages.csv')
    for name in required:
        if not (source / name).is_file():
            raise ValueError('Required source report missing: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    # A prior real report allocated 6.58 GiB for a report of this general scale.
    # Budget twice the indexed input bytes plus 1 GiB for indexes/journals, and
    # enforce an additional 1 GiB free-space reserve throughout the build.
    budget = 2 * sum((source / name).stat().st_size for name in required) + 1024**3
    guard = ResourceGuard(output, disk_budget=budget) if guard_factory is ResourceGuard else guard_factory(output)
    store = None
    stage = 'preflight'
    previous_tmp = os.environ.get('SQLITE_TMPDIR')
    (output / 'tmp').mkdir()
    os.environ['SQLITE_TMPDIR'] = str(output / 'tmp')
    try:
        guard.check(force=True)
        store = Store(output, source, guard.check)
        source_files = {p.name: {'bytes': p.stat().st_size, 'sha256': hash_file(p, guard.check)}
                        for p in source.iterdir() if p.is_file()}
        write_json(output / 'source-before.json', source_files)
        stages = []
        def run(name, action):
            nonlocal stage
            stage = name
            print(name, flush=True)
            tick = time.monotonic()
            result = action()
            stages.append({'stage': name, 'seconds': time.monotonic() - tick})
            write_json(output / 'stages.json', stages)
            return result
        run('baseline manifest', lambda: store.read_manifest('baseline'))
        run('candidate manifest', lambda: store.read_manifest('candidate'))
        run('original findings and assessments', store.read_results)
        run('canonical ELF matching', lambda: build_pairs(store))
        run('symbol observations', lambda: compare_symbols(store))
        reasons = run('linking navigation groups', lambda: build_groups(store))
        run('package statistics', lambda: summarize_packages(store))
        counts = run('CSV exports', lambda: export(store))
        unknown_reasons = [r for r in reasons if r['status'] == 'UNKNOWN']
        csv_rows(output / 'linking-unknown-reasons.csv', ['reason_category', 'status', 'group_count', 'raw_finding_count', 'distinct_recorded_interface_count', 'reason_provenance'], unknown_reasons, guard.check)
        counts['linking-unknown-reasons.csv'] = len(unknown_reasons)
        validation = run('independent reconciliation', lambda: validate(store, counts))
        data = overview(store, reasons)
        write_json(output / 'overview.json', data)
        assets(output, data)
        stage = 'source immutability'
        after = {p.name: {'bytes': p.stat().st_size, 'sha256': hash_file(p, guard.check)}
                 for p in source.iterdir() if p.is_file()}
        write_json(output / 'source-after.json', after)
        if source_files != after or any(source_files[n]['sha256'] != sha for n, sha in store.source_hashes.items()):
            raise ValueError('Source report changed during enhancement')
        validation['checks']['source_files_unchanged'] = True
        write_json(output / 'validation.json', validation)
        store.db.commit()
        store.db.close()
        store = None
        guard.check(force=True)
        metrics = {'status': 'PASS', 'wall_seconds': time.monotonic() - started,
                   'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                   'peak_tree_rss_bytes': guard.peak_tree_rss, 'resources': guard.last_snapshot,
                   'csv_rows': counts, 'files': {str(p.relative_to(output)): p.stat().st_size for p in output.rglob('*') if p.is_file()}}
        write_json(output / 'run.json', metrics)
        return metrics
    except BaseException as error:
        write_json(output / 'run.json', {'status': 'FAIL', 'stage': stage, 'error': str(error),
                   'error_type': type(error).__name__, 'wall_seconds': time.monotonic() - started,
                   'resources': guard.last_snapshot})
        raise
    finally:
        if store is not None:
            store.db.close()
        if previous_tmp is None:
            os.environ.pop('SQLITE_TMPDIR', None)
        else:
            os.environ['SQLITE_TMPDIR'] = previous_tmp
