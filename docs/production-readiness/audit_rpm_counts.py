#!/usr/bin/env python3
"""Independently reconcile the known v1.5.1 synthetic RPM fixture."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re


def export_totals(manifest):
    raw = count = 0
    names = set()
    for obj in manifest['elf_objects']:
        lookup = set()
        for row in obj['exports']:
            if row in obj.get('version_node_markers', []):
                continue
            parts = re.split(r'(@@?)', row['name'], maxsplit=1)
            name = parts[0]
            names.add(name)
            lookup.add((name, parts[2] if len(parts)==3 else None))
            if len(parts)==3 and parts[1]=='@@':
                lookup.add((name,None))
            raw += 1
        count += len(lookup)
    return {'raw_exports':raw,'unique_export_base_names':len(names),'per_elf_lookup_identities':count}


def audit(report):
    value = {side:export_totals(json.loads((report/(side+'-manifest.json')).read_text())) for side in ('baseline','candidate')}
    with (report/'symbol-differences.csv').open(newline='') as stream:
        records = list(csv.DictReader(stream))
    value.update(rows=len(records),changes=dict(Counter(row['change'] for row in records)),
                 roles=dict(Counter(row['role'] for row in records)))
    assert value['baseline']=={'raw_exports':18,'unique_export_base_names':9,'per_elf_lookup_identities':36}
    assert value['candidate']=={'raw_exports':18,'unique_export_base_names':10,'per_elf_lookup_identities':36}
    assert value['rows']==25 and value['changes']==dict(MATCHED=16,ADDED=5,CHANGED=3,MISSING=1)
    receipt = json.loads((report/'run-summary.json').read_text())
    for side in ('baseline','candidate'):
        observed = receipt['statistics'][side]
        assert [observed[key] for key in ('exports','export_unique_symbol_names','export_lookup_identities')]==list(value[side].values())
    assert receipt['statistics']['symbol_differences']['by_change']==value['changes']
    value.update(objective_completion=receipt['objective_completion'],status='PASS')
    return value


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    print(json.dumps(audit(parser.parse_args().report),indent=2))
