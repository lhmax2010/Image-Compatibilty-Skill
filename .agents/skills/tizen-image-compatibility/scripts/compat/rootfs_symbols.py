"""Optional exact-path ELF and symbol detail for rootfs export workflows."""
from collections import defaultdict

from .report_io import csv_rows
from .repository import symbol_counts, symbol_differences, symbols


def export_rootfs_symbols(output, a, b, result):
    objects = [{o['path']:o for o in manifest['elf_objects'] if o.get('elf_runtime_role')!='DEBUG_ONLY'}
               for manifest in (a,b)]
    owners = defaultdict(set)
    for package in result['package_results']:
        for field in ('owned_interfaces','candidate_interfaces'):
            for obj in (package.get(field) or {}).get('elf', []):
                owners[obj['path']].add(package['id'])
    pairs = [{'package_id':','.join(sorted(owners[path])) or 'UNKNOWN','component':path,
              'baseline_object':path if path in objects[0] else None,
              'candidate_object':path if path in objects[1] else None}
             for path in sorted(objects[0].keys()|objects[1].keys())]

    def library_rows():
        for pair in pairs:
            row = dict(pair)
            for side, catalog in zip(('baseline','candidate'),objects):
                obj = catalog.get(pair[side+'_object'])
                if obj:
                    row.update({side+'_'+key:obj.get(key) for key in ('soname','needed','export_inventory_status','evidence')})
                    row.update({side+'_'+role.lower()+'s':len(symbols(obj,role)) for role in ('EXPORT','IMPORT')})
                    row.update({side+'_'+key:value for key,value in symbol_counts([obj]).items()})
            yield row

    csv_rows(output/'elf-symbol-summary.csv',('package_id','component','baseline_object','candidate_object')+
             tuple(side+'_'+key for side in ('baseline','candidate') for key in
                   ('soname','needed','export_inventory_status','evidence','exports','imports','export_unique_symbol_names',
                    'export_lookup_identities','import_unique_symbol_names','import_lookup_identities')),library_rows())
    detail = {'elf_pairs':pairs}
    view = {'repository':detail,'findings':result['findings']}
    csv_rows(output/'symbol-differences.csv',('package_id','component','role','change','details','status',
             'baseline','candidate','finding_ids','baseline_sha256','candidate_sha256','evidence'),
             symbol_differences(view,objects,result['symbol_differences_mode']))
    result['rootfs_symbol_detail'] = {'matching':'EXACT_ROOTFS_PATH','symbol_differences':detail['symbol_differences'],
                                    'baseline':symbol_counts(objects[0].values()),'candidate':symbol_counts(objects[1].values())}
