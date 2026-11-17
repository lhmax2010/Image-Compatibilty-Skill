"""Navigation groups retain all original consumers, outcomes and finding IDs."""
from collections import Counter
import json

from .report_io import canonical


def build_groups(store):
    db = store.db
    db.executescript('''
    CREATE TABLE group_counts AS
      SELECT group_id,count(*) raw_count,
        count(DISTINCT consumer_image || char(0) || consumer_path) direct_count,
        count(DISTINCT root_image || char(0) || root_path) root_count,
        sum(root_path IS NULL) root_not_recorded,
        sum(consumer_path NOT LIKE '/%') direct_not_recorded,
        min(ownership_complete) ownership_complete,
        sum(evidence_state='NO_REFERENCE') no_evidence,
        sum(evidence_state='MISSING_OR_UNSAFE_REFERENCE') missing_evidence
      FROM findings WHERE group_id IS NOT NULL GROUP BY group_id;
    CREATE UNIQUE INDEX group_count_id ON group_counts(group_id);
    CREATE TABLE group_package_counts AS
      SELECT f.group_id,count(DISTINCT r.side || char(0) || r.package_id) package_count
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
        package_row = db.execute('SELECT package_count FROM group_package_counts WHERE group_id=?', (ident,)).fetchone()
        package_count = package_row[0] if package_row else 0
        summary = {'group_id': ident, 'reason_category': group['reason'], 'status': group['status'],
                   'interface_or_dependency': group['interface'], 'provider': group['provider'],
                   'raw_finding_count': counts['raw_count'],
                   'affected_package_count': package_count if counts['ownership_complete'] else None,
                   'observed_affected_package_count': package_count,
                   'ownership_complete': bool(counts['ownership_complete']),
                   'affected_elf_count': counts['direct_count'] if not counts['direct_not_recorded'] else None,
                   'observed_direct_consumer_count': counts['direct_count'],
                   'affected_root_consumer_count': counts['root_count'] if not counts['root_not_recorded'] else None,
                   'observed_root_consumer_count': counts['root_count'],
                   'root_consumer_not_recorded_count': counts['root_not_recorded'],
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
