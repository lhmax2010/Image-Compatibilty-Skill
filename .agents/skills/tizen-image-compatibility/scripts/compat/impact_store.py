"""Build a sparse, reproducible projection without changing the original report."""
from collections import Counter
from itertools import zip_longest
import os
from pathlib import Path
import resource
import re
import sqlite3
import time

from .impact_replay import compare_observation, observations, qualified, replay_proof
from .impact_source import Source, attach_source, group_rows, index_rows, read_json, scope_config, unpack_limited, virtual_path
from .report_io import ResourceGuard, ResourceLimit, canonical, digest, hash_file, write_json

SCHEMA = 1
ENGINE = 'v1.4-offline-compatibility-rc1'
DB_NAME = 'impact-index.sqlite'
TARGET_SECONDS = 720
GIB = 1024 ** 3
DDL = """
PRAGMA user_version=1;
PRAGMA foreign_keys=ON;
PRAGMA cache_size=-49152;
PRAGMA temp_store=FILE;
CREATE TABLE meta(key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE source_finding(
    n INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, status TEXT NOT NULL, payload_hash TEXT NOT NULL,
    dimension TEXT NOT NULL, old_group TEXT,
    CHECK(status IN ('INCOMPATIBLE','UNKNOWN','COMPATIBLE','IDENTICAL','NOT_APPLICABLE'))
);
CREATE TABLE impact_group(
    g INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
    source_key TEXT NOT NULL, subject TEXT NOT NULL, reason TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'UNDETERMINED', authority TEXT,
    rank INTEGER NOT NULL DEFAULT 0, member_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(kind,source_key)
);
CREATE TABLE group_finding(
    g INTEGER NOT NULL REFERENCES impact_group(g),
    n INTEGER NOT NULL REFERENCES source_finding(n),
    PRIMARY KEY(g,n)
) WITHOUT ROWID;
CREATE TABLE association(
    n INTEGER PRIMARY KEY REFERENCES source_finding(n),
    strength TEXT NOT NULL CHECK(strength IN ('DIRECT','INFERRED','UNKNOWN')),
    assessment TEXT NOT NULL CHECK(assessment IN (
        'CONFIRMED_CONTRACT_IMPACT','POSSIBLE_IMPACT','UNASSESSED','NO_BREAK_OBSERVED')),
    reason TEXT NOT NULL, proof TEXT,
    CHECK(assessment NOT IN ('CONFIRMED_CONTRACT_IMPACT','NO_BREAK_OBSERVED') OR
          (strength='DIRECT' AND proof IS NOT NULL))
);
CREATE TABLE package_group(
    side TEXT NOT NULL, package_id TEXT NOT NULL,
    g INTEGER NOT NULL REFERENCES impact_group(g),
    role TEXT NOT NULL CHECK(role IN ('consumer','provider','root')),
    complete INTEGER NOT NULL CHECK(complete IN (0,1)),
    confirmed INTEGER NOT NULL CHECK(confirmed IN (0,1)),
    CHECK(confirmed=0 OR (role='consumer' AND complete=1 AND side='baseline')),
    PRIMARY KEY(side,package_id,g,role)
) WITHOUT ROWID;
"""

RUNTIME = re.compile(r'(?<![\w+])(?:libstdc\+\+|libc\+\+abi|libc\+\+|libgcc_s|libunwind)\.so(?:\.[\w.]+)?'
                     r'|(?<![\w-])(?:libclang_rt[.\w-]*|compiler-rt)(?![\w-])')


def group_id(kind, key):
    return 'IG-' + digest([SCHEMA, kind, key])


def native_check(interface, check_id, image, root_image):
    if root_image == 'baseline' and image in ('baseline', 'candidate'):
        prefix = 'baseline consumers on candidate'
    elif root_image == image == 'candidate':
        prefix = 'candidate'
    else:
        return 0
    return int(isinstance(check_id, str) and interface == prefix + ':' + check_id
               and check_id.startswith(('DT_NEEDED:', 'import:', 'version:', 'dynamic loader')))


class ImpactGuard(ResourceGuard):
    def check(self, force=False):
        super().check(force)
        snapshot = self.last_snapshot
        if (max(snapshot['tree_rss_bytes'], snapshot['process_peak_rss_bytes']) > GIB
                or snapshot['allocated_bytes'] > 3 * GIB):
            raise ResourceLimit('Impact build exceeds 1 GiB RSS or 3 GiB output safety budget')
        if time.monotonic() - self.started > TARGET_SECONDS + 600:
            raise ResourceLimit('Impact build exceeded bounded build window')


FINDING_CSV = ('id','status','dimension','n','payload_hash','group_id')
LINKING_CSV = ('group_id','id','consumer_image','consumer_path','root_image','root_path','provider_path')


def ingest_exports(db, source, check):
    def ledger():
        for seq, row in enumerate(index_rows(source.path / 'finding-index.csv', FINDING_CSV, source.count, check), 1):
            ident, status, dim, n, payload_hash, old_group = row
            old_group = None if old_group in ('UNKNOWN', '') else old_group
            if (str(seq) != n or not re.fullmatch(r'TC-[\w.-]{1,124}', ident)
                    or not re.fullmatch(r'[a-f0-9]{64}', payload_hash)
                    or (dim == 'linking') != bool(old_group)):
                raise ValueError('Malformed Finding export identity or membership')
            yield seq, ident, status, payload_hash, dim, old_group

    db.executemany('INSERT INTO source_finding VALUES(?,?,?,?,?,?)', ledger())
    db.executescript("""
        CREATE INDEX ledger_by_group ON source_finding(old_group,n);
        CREATE TEMP TABLE linking_members(
          old_group TEXT NOT NULL,id TEXT PRIMARY KEY NOT NULL,
          image TEXT,consumer TEXT,root_image TEXT,root TEXT,provider TEXT
        ) WITHOUT ROWID;
        CREATE TEMP TABLE legacy_group(
          id TEXT PRIMARY KEY NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL,
          interface TEXT NOT NULL, provider TEXT, original_members INTEGER NOT NULL
        ) WITHOUT ROWID;
    """)
    db.executemany('INSERT INTO linking_members VALUES(?,?,?,?,?,?,?)',
                   index_rows(source.path / 'linking-group-members.csv', LINKING_CSV, source.count, check))
    db.executemany('INSERT INTO legacy_group VALUES(?,?,?,?,?,?)',
                   group_rows(source.path / 'linking-findings-groups.csv', source.count, check))
    invalid = db.execute("""
        SELECT 1 FROM linking_members m LEFT JOIN source_finding f ON f.id=m.id
        WHERE f.id IS NULL OR m.old_group IS NOT f.old_group LIMIT 1
    """).fetchone()
    expected = db.execute("SELECT count(*) FROM source_finding WHERE old_group IS NOT NULL").fetchone()[0]
    if invalid or db.execute("SELECT count(*) FROM linking_members").fetchone()[0] != expected:
        raise ValueError('v1.3 Finding and Linking member exports disagree')
    db.commit()


def observations_to_store(db, source, config, roots, check):
    db.create_function('impact_id', 2, group_id, deterministic=True)
    db.create_function('is_check', 4, native_check, deterministic=True)
    db.create_function('valid_path', 1, lambda p: int(virtual_path(p)), deterministic=True)
    db.create_function('runtime_hint', 2, lambda a, b: int(bool(RUNTIME.search((a or '') + ' ' + (b or '')))),
                       deterministic=True)
    db.executescript("""
        INSERT INTO impact_group(id,kind,source_key,subject,reason)
        SELECT impact_id('LINKING_OBSERVATIONS',id),'LINKING_OBSERVATIONS',id,
               substr(interface,1,4096),reason FROM legacy_group ORDER BY id;
        INSERT INTO impact_group(id,kind,source_key,subject,reason)
        SELECT impact_id('INTERFACE_OBSERVATION',id),'INTERFACE_OBSERVATION',id,dimension || ' · ' || id,dimension
        FROM source_finding WHERE dimension IN ('abi','api','headers','elf','compiler_runtime') AND old_group IS NULL
        ORDER BY id;
        INSERT INTO impact_group(id,kind,source_key,subject,reason)
        SELECT impact_id('RUNTIME_REVIEW',id),'RUNTIME_REVIEW',id,substr(interface,1,4096),
               'C++ runtime / unwinder boundary requires validation' FROM legacy_group
        WHERE runtime_hint(interface,provider) ORDER BY id;
        INSERT INTO group_finding
        SELECT g.g,f.n FROM impact_group g JOIN source_finding f ON f.old_group=g.source_key
        WHERE g.kind IN ('LINKING_OBSERVATIONS','RUNTIME_REVIEW') ORDER BY g.g,f.n;
        INSERT INTO group_finding
        SELECT g.g,f.n FROM impact_group g JOIN source_finding f ON f.id=g.source_key
        WHERE g.kind='INTERFACE_OBSERVATION' ORDER BY g.g,f.n;
        CREATE INDEX findings_to_groups ON group_finding(n,g);
        INSERT INTO association(n,strength,assessment,reason)
        SELECT f.n, 'INFERRED',
               CASE WHEN f.status IN ('UNKNOWN','INCOMPATIBLE') THEN 'POSSIBLE_IMPACT' ELSE 'UNASSESSED' END,
               CASE WHEN m.root_image='candidate' THEN 'CANDIDATE_NATIVE_ONLY'
                    WHEN g.reason LIKE 'unknown%' OR f.status='UNKNOWN' THEN 'LOADER_OR_SCOPE_UNPROVEN'
                    ELSE 'BASELINE_BINDING_UNPROVEN' END
        FROM source_finding f JOIN linking_members m ON m.id=f.id JOIN legacy_group g ON g.id=f.old_group
        WHERE is_check(g.interface,substr(g.interface,instr(g.interface,':')+1),m.image,m.root_image)
          AND valid_path(m.consumer) AND valid_path(m.root) ORDER BY f.n;
    """)
    if config['rules']:
        db.execute("""CREATE TEMP TABLE scope_rule(
          side TEXT,path TEXT,interface TEXT,classification TEXT,authority TEXT)""")
        db.executemany('INSERT INTO scope_rule VALUES(?,?,?,?,?)',
                       ((r['side'],r['path'],r['interface'],r['classification'],r['authority']) for r in config['rules']))
        # Scope is granted only if every member is covered by one consistent class.
        db.executescript("""
            CREATE TEMP TABLE scope_match AS
            SELECT m.g,count(DISTINCT m.n) matched,count(DISTINCT s.classification) classes,
                   min(s.classification) classification,count(DISTINCT s.authority) authorities,min(s.authority) authority
            FROM scope_rule s JOIN source.findings f
              ON f.interface=s.interface AND f.component=s.path
              AND f.consumer_image=s.side
            JOIN group_finding m ON m.n=f.n GROUP BY m.g;
            CREATE UNIQUE INDEX scope_match_group ON scope_match(g);
            UPDATE impact_group AS g SET scope=CASE WHEN (
              SELECT classes=1 AND matched=(SELECT count(*) FROM group_finding WHERE group_finding.g=g.g)
              FROM scope_match WHERE scope_match.g=g.g
            ) THEN (SELECT classification FROM scope_match WHERE scope_match.g=g.g) ELSE 'UNDETERMINED' END,
            authority=(SELECT CASE WHEN classes>1 THEN 'Conflicting classifications'
              WHEN authorities>1 THEN 'Multiple configured authorities' ELSE authority END FROM scope_match WHERE scope_match.g=g.g)
            WHERE g.g IN (SELECT g FROM scope_match);
        """)
    replay_limits = []
    if roots:
        for root, pair in observations(source.manifests, roots, check):
            if pair is None:
                replay_limits.append(root)
                continue
            before, after = pair
            for key, event in after.items():
                baseline = before.get(key)
                assessment = qualified(baseline, event)
                if not assessment:
                    continue
                row = db.execute('''SELECT f.n,f.payload,f.payload_hash,s.payload_hash exported_hash
                    FROM source.findings f JOIN source_finding s ON s.n=f.n AND s.id=f.id
                    WHERE f.id=?''', (event['id'],)).fetchone()
                if not row:
                    continue
                payload = unpack_limited(row['payload'])
                if digest(payload) != row['payload_hash'] or row['payload_hash'] != row['exported_hash']:
                    raise ValueError('Source Finding payload hash mismatch during replay')
                if not compare_observation(payload, event):
                    continue
                reason = 'DUAL_RESOLVER_MATCH'
                proof = replay_proof(baseline, event)
                if len(proof.encode()) > 131072:
                    raise ValueError('Replay proof exceeds supported size')
                db.execute('INSERT OR REPLACE INTO association VALUES(?,?,?,?,?)',
                           (row['n'], 'DIRECT', assessment, reason, proof))
                # Only an exact direct root check is represented in this context-specific group.
                # Core Finding IDs include the root, direction, requirement and recorded decision.
                source_key = event['id']
                created = db.execute('''INSERT INTO impact_group(id,kind,source_key,subject,reason)
                    VALUES(?,?,?,?,?) RETURNING g''',
                    (group_id('REPLAYED_CONTRACT', source_key), 'REPLAYED_CONTRACT', source_key,
                     event['interface'][:4096], reason)).fetchone()[0]
                db.execute('INSERT INTO group_finding VALUES(?,?)', (created, row['n']))
                matching = [r for r in config['rules'] if r['side']=='baseline' and r['path']==root and r['interface']==event['interface']]
                classes = {r['classification'] for r in matching}
                if classes:
                    authority = ', '.join(sorted({r['authority'] for r in matching}))
                    db.execute('UPDATE impact_group SET scope=?,authority=? WHERE g=?',
                               (next(iter(classes)) if len(classes)==1 else 'UNDETERMINED', authority[:4096], created))
    db.commit()
    return replay_limits


def materialize_summary(db):
    db.executescript("""
        UPDATE impact_group SET member_count=(SELECT count(*) FROM group_finding m WHERE m.g=impact_group.g);
        UPDATE impact_group SET rank=coalesce((
            SELECT max(CASE WHEN a.assessment='CONFIRMED_CONTRACT_IMPACT' THEN 2
                            WHEN a.assessment='POSSIBLE_IMPACT' THEN 1 ELSE 0 END)
            FROM group_finding m JOIN association a ON a.n=m.n WHERE m.g=impact_group.g),0);
        CREATE INDEX group_order ON impact_group(rank DESC,id);
        CREATE INDEX group_filter ON impact_group(kind,scope,rank DESC,id);
        INSERT INTO package_group
        SELECT r.side,r.package_id,m.g,r.role,min(r.complete),
               CASE WHEN min(r.complete)=1 AND r.role='consumer' AND r.side='baseline'
                    THEN max(CASE WHEN a.assessment='CONFIRMED_CONTRACT_IMPACT' THEN 1 ELSE 0 END)
                    ELSE 0 END
        FROM source.roles r NOT INDEXED
        CROSS JOIN source_finding f ON f.id=r.finding_id
        CROSS JOIN group_finding m ON m.n=f.n
        CROSS JOIN source.packages p ON p.side=r.side AND p.id=r.package_id
        LEFT JOIN association a ON a.n=m.n GROUP BY r.side,r.package_id,m.g,r.role;
        CREATE INDEX groups_to_packages ON package_group(g,side,package_id,role);
    """)


def reconcile(db, source):
    # Visit each FK in parent-key order. The generic SQLite sweep visits a child
    # table in primary-key order even when validating its other key, which turns
    # the large group -> Finding relationship into random seeks on a cold disk.
    relations = (
        ('group_finding INDEXED BY findings_to_groups', 'n', 'source_finding', 'n'),
        ('group_finding', 'g', 'impact_group', 'g'),
        ('association', 'n', 'source_finding', 'n'),
        ('package_group INDEXED BY groups_to_packages', 'g', 'impact_group', 'g'),
    )
    if any(db.execute(f'''SELECT 1 FROM (SELECT {child_key} FROM {child}) AS c
              LEFT JOIN {parent} AS p ON p.{parent_key}=c.{child_key}
              WHERE p.{parent_key} IS NULL LIMIT 1''').fetchone()
           for child, child_key, parent, parent_key in relations):
        raise ValueError('Impact index has missing foreign-key references')
    if db.execute('PRAGMA main.quick_check(1)').fetchone()[0] != 'ok':
        raise ValueError('Impact index integrity check failed')
    # Sort the narrow ledger sequentially. Walking either original covering index
    # with a lookup into the ledger for each row causes random reads on cold storage.
    ordinal = (
        'SELECT id,rowid,group_id FROM source.findings INDEXED BY finding_group_lookup ORDER BY id,group_id',
        'SELECT id,n,old_group FROM source_finding NOT INDEXED ORDER BY id,old_group',
    )
    classification = (
        'SELECT status,dimension,n FROM source.findings INDEXED BY finding_status ORDER BY status,dimension,n',
        'SELECT status,dimension,n FROM source_finding NOT INDEXED ORDER BY status,dimension,n',
    )
    for original, projected in (ordinal, classification):
        left, right = (map(tuple, db.execute(sql)) for sql in (original, projected))
        if any(a != b for a, b in zip_longest(left, right)):
            raise ValueError('Source Finding or Linking member reconciliation failed')
    missing_group = db.execute("""
      SELECT 1 FROM source_finding f INDEXED BY ledger_by_group
      LEFT JOIN impact_group g ON g.kind='LINKING_OBSERVATIONS' AND g.source_key=f.old_group
      LEFT JOIN group_finding m ON m.g=g.g AND m.n=f.n
      WHERE f.old_group IS NOT NULL AND m.n IS NULL LIMIT 1
    """).fetchone()
    missing_group_id = db.execute("""
      SELECT id FROM source.groups EXCEPT SELECT id FROM legacy_group LIMIT 1
    """).fetchone()
    invalid_group = db.execute("""
      SELECT 1 FROM legacy_group src LEFT JOIN source.groups original ON original.id=src.id
      LEFT JOIN impact_group g ON g.kind='LINKING_OBSERVATIONS' AND g.source_key=src.id
      WHERE original.id IS NULL OR g.member_count IS NOT src.original_members LIMIT 1
    """).fetchone()
    if (missing_group or missing_group_id or invalid_group
            or db.execute('SELECT count(*) FROM source_finding').fetchone()[0] != source.count):
        raise ValueError('Source Finding or Linking member reconciliation failed')
    empty = db.execute('SELECT 1 FROM impact_group WHERE member_count=0 LIMIT 1').fetchone()
    bad_roles = db.execute("""
      SELECT 1 FROM source.roles r NOT INDEXED
      LEFT JOIN source.packages p ON p.side=r.side AND p.id=r.package_id
      LEFT JOIN source_finding f ON f.id=r.finding_id
      WHERE p.id IS NULL OR f.id IS NULL OR r.role NOT IN ('root','consumer','provider') LIMIT 1
    """).fetchone()
    if empty or bad_roles:
        raise ValueError('Empty group or invalid role in source')
    states = Counter(dict(db.execute('SELECT assessment,count(*) FROM association GROUP BY assessment')))
    strengths = dict(db.execute('SELECT strength,count(*) FROM association GROUP BY strength'))
    reasons = dict(db.execute('SELECT reason,count(*) FROM association GROUP BY reason'))
    no_link = source.count - sum(states.values())
    strengths['UNKNOWN'] = no_link
    states['UNASSESSED'] += no_link
    reasons['NO_EXACT_LINKER_CHECK'] = no_link
    return {
        'source_findings': source.count,
        'original_status_counts': dict(db.execute('SELECT status,count(*) FROM source_finding GROUP BY status')),
        'groups': db.execute('SELECT count(*) FROM impact_group').fetchone()[0],
        'member_links': db.execute('SELECT count(*) FROM group_finding').fetchone()[0],
        'package_role_links': db.execute('SELECT count(*) FROM package_group').fetchone()[0],
        'grouped_findings': db.execute('SELECT count(DISTINCT n) FROM group_finding').fetchone()[0],
        'assessments': dict(states), 'strengths': strengths, 'reasons': reasons,
        'source_linking': db.execute("SELECT count(*) FROM source_finding WHERE dimension='linking'").fetchone()[0],
        'source_package_roles': db.execute('SELECT count(*) FROM source.roles').fetchone()[0],
        'source_unassigned': db.execute('SELECT count(*) FROM source.unassigned').fetchone()[0],
    }


def build(index, output, config_path=None, roots=(), progress=lambda stage: None):
    index, output = Path(index).resolve(), Path(output).resolve()
    if index == output or index in output.parents or output in index.parents:
        raise ValueError('Impact output must be separate from the v1.3 report')
    original = Path(read_json(index / 'overview.json')['source_directory']).resolve()
    if original == output or original in output.parents or output in original.parents:
        raise ValueError('Impact output must be separate from the original report')
    if len(roots) > 200 or not all(virtual_path(root) for root in roots):
        raise ValueError('Replay accepts up to 200 exact baseline ELF paths')
    roots = sorted(set(roots))
    config = scope_config(config_path)
    output.mkdir(parents=True, exist_ok=False)
    temp = output / 'tmp'
    temp.mkdir()
    old_tmp = os.environ.get('SQLITE_TMPDIR')
    os.environ['SQLITE_TMPDIR'] = str(temp)
    db = None
    guard = ImpactGuard(output)
    stages = {}
    stage = 'source'
    started = time.monotonic()

    def step(name, fn):
        nonlocal stage
        stage = name
        progress(stage)
        guard.check(force=True)
        tick = time.monotonic()
        result = fn()
        stages[name] = round(time.monotonic() - tick, 3)
        return result

    try:
        source = step('source', lambda: Source(index, guard.check, replay=bool(roots)))
        manifest = {'schema': SCHEMA, 'engine': ENGINE, 'source_hashes': source.hashes,
                    'config_sha256': digest(config), 'replay_roots': roots}
        identity = digest(manifest)
        work = output / 'impact-index.building.sqlite'
        db = sqlite3.connect(work, uri=True)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA trusted_schema=OFF')
        db.executescript(DDL)
        attach_source(db, source.index)
        db.set_progress_handler(guard.check, 100_000)
        step('source_integrity', lambda: Source.inspect(db, source.count))
        step('source_exports', lambda: ingest_exports(db, source, guard.check))
        limits = step('associations', lambda: observations_to_store(db, source, config, roots, guard.check))
        step('summary_indexes', lambda: materialize_summary(db))
        summary = step('reconcile', lambda: reconcile(db, source))
        db.executemany('INSERT INTO meta VALUES(?,?)',
                       (('projection_id', identity), ('engine', ENGINE)))
        db.commit()
        db.close()
        db = None
        if work.stat().st_size > int(1.5 * GIB):
            raise ResourceLimit('Published SQLite exceeds design target of 1.5 GiB')
        sha = step('publication_hash', lambda: hash_file(work, guard.check))
        source.assert_unchanged()
        guard.check(force=True)
        timing = time.monotonic() - started
        metrics = manifest | {
            'state': 'PARTIAL' if limits else 'COMPLETE', 'projection_id': identity,
            'source_directory': str(index), 'source_schema': '1.2', 'source_report_version': '1.3',
            'mode': 'REPLAYED' if roots else 'RECORDED', 'replay_limits': limits,
            'index_sha256': sha, 'index_bytes': work.stat().st_size, 'summary': summary,
            'stages_seconds': stages, 'wall_seconds': timing,
            'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            'peak_tree_rss_bytes': guard.peak_tree_rss, 'target_met': timing <= TARGET_SECONDS,
        }
        # Readers require run.json and verify its bound index identity. It is the last publication.
        write_json(output / 'run.pending.json', metrics)
        os.replace(work, output / DB_NAME)
        os.replace(output / 'run.pending.json', output / 'run.json')
        return metrics
    except BaseException as exc:
        write_json(output / 'failure.json', {'state': 'FAILED', 'stage': stage, 'error': str(exc),
                   'stages_seconds': stages, 'wall_seconds': time.monotonic() - started})
        raise
    finally:
        if db is not None:
            db.close()
        if old_tmp is None:
            os.environ.pop('SQLITE_TMPDIR', None)
        else:
            os.environ['SQLITE_TMPDIR'] = old_tmp
