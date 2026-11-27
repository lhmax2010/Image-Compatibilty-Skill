"""Audit unique ELF targets in the host shared-library directory without executing them."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compat.core import DEFAULTS, Tools
from compat.elf import collect_elf

source = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=False)
entries = set()
excluded = []
for path in source.glob('*.so*'):
    if not path.is_file():
        continue
    target = path.resolve()
    with target.open('rb') as stream:
        if stream.read(4)!=b'\x7fELF':
            excluded.append(path.name)
            continue
    entries.add(target)

HEX_SIZE = re.compile(rb'^\s*\d+:\s+[0-9a-fA-F]+\s+0[xX][0-9a-fA-F]+\s+')


def scan(path):
    with tempfile.TemporaryDirectory(dir=output) as temp:
        work = Path(temp)
        tools = Tools(work,DEFAULTS)
        obj = collect_elf(path,path.name,tools,'static')
        log = tools.records[0]
        raw_evidence = work/log['stdout_evidence']
        with raw_evidence.open('rb') as raw:
            hex_size = any(HEX_SIZE.match(line) for line in raw)
        warning = (work/log['stderr_evidence']).read_text(errors='replace').strip()[:600]
        return {'object':str(path),'hex_size_row':hex_size,'header_complete':obj['complete'],
                'complete':obj['export_inventory_complete'],'status':obj['export_inventory_status'],
                'reason':obj.get('export_inventory_reason'),'code':obj.get('export_inventory_reason_code'),
                'error':log['error'],'warning':warning,'captured_bytes':raw_evidence.stat().st_size,
                'exports':len(obj.get('exports',[]))}


with ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(scan,sorted(entries)))
summary = {'directory':str(source),'unique_elf_objects':len(rows),'headers_complete':sum(r['header_complete'] for r in rows),
           'exports_complete':sum(r['complete'] for r in rows),'any_hex_size':sum(r['hex_size_row'] for r in rows),
           'hex_incomplete':sum(r['hex_size_row'] and not r['complete'] for r in rows),
           'output_limit':sum(r['code']=='OUTPUT_LIMIT' for r in rows),
           'incomplete':[r for r in rows if not r['complete']], 'excluded_non_elf':sorted(excluded)}
(output/'host-scan.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='incomplete'},indent=2))
for row in summary['incomplete']:
    print(row['object'],row['code'] or row['warning'] or row['error'] or row['reason'],sep='\t')
