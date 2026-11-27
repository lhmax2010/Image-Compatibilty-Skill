"""Navigation groups retain all original consumers, outcomes and finding IDs."""
from collections import Counter
import json
import posixpath

from .report_io import canonical


def valid_consumer_path(path):
    # Recorded normalized absolute file path, not evidence that the ELF executed.
    return (isinstance(path, str) and path.startswith('/') and not path.startswith('//')
            and path != '/' and not path.endswith('/') and posixpath.normpath(path) == path
            and not any(ord(char) < 32 or ord(char) == 127 for char in path))


def build_groups(store):
    db = store.db
    db.create_function('valid_consumer', 2, lambda image, path: int(image in ('baseline', 'candidate') and valid_consumer_path(path)))
    db.executescript('''
    CREATE TABLE group_counts AS
      SELECT group_id,count(*) raw_count,
        count(DISTINCT CASE WHEN valid_consumer(consumer_image,consumer_path) THEN consumer_image || char(0) || consumer_path END) direct_count,
        sum(NOT valid_consumer(consumer_image,consumer_path)) direct_not_recorded,
        min(ownership_complete) ownership_complete,
        sum(evidence_state='NO_REFERENCE') no_evidence,
        sum(evidence_state='MISSING_OR_UNSAFE_REFERENCE') missing_evidence
      FROM findings WHERE group_id IS NOT NULL GROUP BY group_id;
    CREATE UNIQUE INDEX group_count_id ON group_counts(group_id);
    CREATE TABLE group_root_counts AS
      SELECT group_id,
        count(DISTINCT CASE WHEN valid_consumer(side,path) THEN side || char(0) || path END) root_count,
        count(DISTINCT CASE WHEN truncated OR NOT valid_consumer(side,path) THEN finding_id END) root_not_recorded
      FROM finding_roots GROUP BY group_id;
    CREATE UNIQUE INDEX group_root_count_id ON group_root_counts(group_id);
    CREATE TABLE group_package_counts AS
      SELECT f.group_id,count(DISTINCT r.side || char(0) || r.package_id) package_count,
        count(DISTINCT CASE WHEN r.role='consumer' THEN r.side || char(0) || r.package_id END) consumer_count,
        count(DISTINCT CASE WHEN r.role='root' THEN r.side || char(0) || r.package_id END) root_count,
        count(DISTINCT CASE WHEN r.role='provider' THEN r.side || char(0) || r.package_id END) provider_count
      FROM findings f JOIN roles r ON r.finding_id=f.id
      WHERE f.group_id IS NOT NULL GROUP BY f.group_id;
    CREATE UNIQUE INDEX group_package_count_id ON group_package_counts(group_id);
    ''')
    current, evidence = None, set()

    def finish(ident, refs):
        if ident is None:
            return
        group = db.execute('SELECT * FROM groups WHERE id=?', (ident,)).fetchone()
        counts = db.execute('SELECT * FROM group_counts WHERE group_id=?', (ident,)).fetchone()
        roots = db.execute('SELECT * FROM group_root_counts WHERE group_id=?', (ident,)).fetchone()
        package_row = db.execute('SELECT * FROM group_package_counts WHERE group_id=?', (ident,)).fetchone()
        package_count = package_row['package_count'] if package_row else 0
        summary = {'group_id': ident, 'reason_category': group['reason'], 'status': group['status'],
                   'interface_or_dependency': group['interface'], 'provider': group['provider'],
                   'raw_finding_count': counts['raw_count'],
                   'affected_package_count': package_count if counts['ownership_complete'] else None,
                   'observed_affected_package_count': package_count,
                   'affected_package_count_definition': 'Legacy alias of associated_package_count (consumer/root/provider union); deprecated, not a consumer-impact count',
                   'package_role_note': 'Distinct (image, package identity) per role; roles overlap and must not be summed. Complete counts require complete ownership for all required roles.',
                   **{key: value for field, column in (
                       ('associated_package_count', 'package_count'),
                       ('affected_consumer_package_count', 'consumer_count'),
                       ('affected_root_package_count', 'root_count'),
                       ('provider_package_count', 'provider_count'))
                      for count in [package_row[column] if package_row else 0]
                      for key, value in ((field, count if counts['ownership_complete'] else None),
                                         ('observed_' + field, count))},
                   'ownership_complete': bool(counts['ownership_complete']),
                   'affected_elf_count': counts['direct_count'] if not counts['direct_not_recorded'] else None,
                   'observed_direct_consumer_count': counts['direct_count'],
                   'direct_consumer_not_recorded_count': counts['direct_not_recorded'],
                   'affected_root_consumer_count': roots['root_count'] if not roots['root_not_recorded'] else None,
                   'observed_root_consumer_count': roots['root_count'],
                   'root_consumer_not_recorded_count': roots['root_not_recorded'],
                   'no_evidence_reference_count': counts['no_evidence'],
                   'missing_evidence_reference_count': counts['missing_evidence'],
                   'evidence_references': sorted(refs),
                   'evidence_note': 'Reference presence only; not a claim of complete loader/environment verification',
                   'finding_index': 'report-index.sqlite:findings.group_id=' + ident,
                   'browser': '#/group/' + ident,
                   'group_key': json.loads(group['key']),
                   'interpretation': 'Navigation group of recorded observations; not a merged compatibility conclusion'}
        db.execute('UPDATE groups SET raw_count=?,summary=? WHERE id=?', (counts['raw_count'], canonical(summary), ident))
        store.check()

    for row in db.execute('SELECT group_id,evidence FROM findings WHERE group_id IS NOT NULL ORDER BY group_id'):
        if row['group_id'] != current:
            finish(current, evidence)
            current, evidence = row['group_id'], set()
        evidence.update(json.loads(row['evidence']))
    finish(current, evidence)
    db.executescript('''CREATE INDEX group_reason_order ON groups(reason,status,raw_count DESC,id);
        CREATE INDEX group_navigation ON groups(raw_count DESC,id,reason,status,interface);''')
    reasons = []
    for row in db.execute('SELECT reason,status,count(*) group_count,sum(raw_count) raw_count FROM groups GROUP BY reason,status'):
        reason, status = row['reason'], row['status']
        interfaces = db.execute('SELECT count(DISTINCT interface) FROM groups WHERE reason=? AND status=?', (reason, status)).fetchone()[0]
        reasons.append({'reason_category': reason, 'status': status, 'group_count': row['group_count'],
                        'raw_finding_count': row['raw_count'], 'distinct_recorded_interface_count': interfaces,
                        'reason_provenance': 'finding.resolution' if reason != 'NOT_RECORDED' else 'resolution field absent; cause not inferred'})
    db.commit()
    return reasons
