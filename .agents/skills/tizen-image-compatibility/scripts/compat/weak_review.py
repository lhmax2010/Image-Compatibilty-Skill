"""Owner decisions for complete, unreferenced weak C++ export observations."""
from collections import Counter, defaultdict
import csv
import io
import tempfile

from .core import InputError, canonical, digest
from .report_io import csv_rows


PENDING = 'WEAK_CXX_EXPORT_REMOVED_UNREFERENCED'
TITLE = 'Weak C++ symbols no longer exported — pending owner review'
RATIONALE = (
    'C++ template instantiations, inline functions, and the vtables, typeinfo and thunks of classes without a key '
    'function have *vague linkage*. Every object file that uses one emits its own weak copy, and the dynamic linker '
    'binds all users to one of the available copies. A program compiled against the same headers therefore normally '
    "carries its own copy and does not need this library to export it. Clang and GCC make different inlining, "
    'instantiation and visibility decisions, so a library built with Clang often exports fewer of these copies. '
    'No analyzed program or library imports any of the listed symbols. The remaining risk is a consumer outside the '
    "analyzed set that was built to import the library's copy instead of emitting its own, for example through "
    'extern template declarations or explicit instantiation in the library. That cannot be checked statically here, '
    'so each entry waits for owner review.'
)
COLUMNS = ('review_id', 'package', 'soname', 'path', 'symbol', 'demangled', 'cxx_class', 'binding', 'type', 'size', 'version',
           'observed_importers_baseline', 'observed_importers_candidate', 'rationale_code',
           'review_decision', 'reviewer', 'review_note')


def pending_headline(review):
    if review.get('status') == 'PENDING':
        return f"Owner review: {review['pending']} weak C++ export removals pending (see weak-export-review.csv)."
    return ''


class Review:
    def __init__(self, path=None):
        self.decisions = {}
        self.sha256 = None
        if path is None:
            return
        payload = path.read_bytes()
        self.sha256 = digest(payload)
        try:
            reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig'), newline=''))
            if not {'review_id', 'review_decision', 'reviewer', 'review_note'} <= set(reader.fieldnames or ()):
                raise InputError('Review CSV requires review_id, review_decision, reviewer and review_note')
            for row in reader:
                key = row['review_id']
                decision = (row['review_decision'] or '').strip().upper()
                if not key or decision not in ('', 'ACCEPT', 'REJECT'):
                    raise InputError('Review CSV contains an invalid ID or decision')
                value = (decision, row['reviewer'] or '', row['review_note'] or '')
                if key in self.decisions and self.decisions[key] != value:
                    raise InputError('Review CSV has conflicting decisions for one review ID')
                self.decisions[key] = value
        except (UnicodeError, csv.Error) as exc:
            raise InputError('Invalid review CSV') from exc

    def grade(self, item, obj, package):
        context = item['removal_context']
        if (item.get('reason_code') != 'EXPORT_REMOVED' or context['binding'] != 'WEAK'
                or context['cxx_class'] == 'c' or any(context['observed_importers'].values())):
            return
        symbol = item['baseline']
        path = obj.get('package_path', obj['path'])
        soname = obj.get('soname')
        ident = 'WEAK-' + digest(canonical([package, soname or path, symbol['name']]).encode())
        decision, reviewer, note = self.decisions.get(ident, ('', '', ''))
        grade = {'': ('UNKNOWN','LOW',PENDING,'PENDING_OWNER_REVIEW'),
                 'ACCEPT': ('COMPATIBLE','INFO','WEAK_CXX_EXPORT_REMOVAL_ACCEPTED','ACCEPTED'),
                 'REJECT': ('INCOMPATIBLE','HIGH','WEAK_CXX_EXPORT_REMOVAL_REJECTED','REJECTED')}
        item['status'], item['severity'], item['reason_code'], item['review_state'] = grade[decision]
        item['review'] = dict(review_id=ident, package=package, soname=soname, path=path, symbol=symbol['name'],
                              cxx_class=context['cxx_class'], rationale_code=PENDING, review_decision=decision,
                              reviewer=reviewer, review_note=note, **{k:symbol.get(k) for k in ('binding','type','size','version')},
                              **{'observed_importers_'+k:v for k,v in context['observed_importers'].items()})
        item['potential_impact'] = 'Weak C++ export removed with no observed importer. See the owner-review rationale.'
        item['recommended_action'] = 'Review consumers outside the analyzed set.'
        item['id'] = 'TC-' + digest(canonical({k:v for k,v in item.items() if k != 'id'}).encode())[:16]

    def summary(self, findings):
        records = [item['review'] for item in findings if 'review' in item]
        counts = Counter(item['review_decision'] for item in records)
        unmatched = sorted(self.decisions.keys() - {item['review_id'] for item in records})
        return dict(required=len(records), accepted=counts['ACCEPT'], rejected=counts['REJECT'],
                    pending=counts[''], unmatched=len(unmatched),
                    status='PENDING' if counts[''] else 'COMPLETE' if records else 'NONE',
                    decisions_sha256=self.sha256, review_unmatched=unmatched)


def export(output, findings, tools, write_csv=True):
    records = [item['review'] for item in findings if 'review' in item]
    groups = defaultdict(list)
    names = sorted({row['symbol'].partition('@')[0] for row in records
                    if '\n' not in row['symbol'] and '\r' not in row['symbol']})
    demangled = {}
    if tools and names:
        if binary := tools.path('c++filt'):
            with tempfile.TemporaryFile(dir=output) as stream:
                stream.write(('\n'.join(names)+'\n').encode())
                stream.seek(0)
                result = tools.run([binary], stdin=stream, max_capture_bytes=64*1024**2, full_output=True)
            lines = result['stdout'].splitlines()
            if not (result['returncode'] or result['stdout_truncated']) and len(lines) == len(names):
                demangled = dict(zip(names, lines))
        else:
            tools.records.append({'tool':'c++filt', 'reason_code':'TOOL_UNAVAILABLE'})
    for row in records:
        row['demangled'] = demangled.get(row['symbol'].partition('@')[0], '')
        if not row['review_decision']:
            groups[row['package'] or '', row['soname'] or row['path']].append(row)
    if write_csv:
        csv_rows(output/'weak-export-review.csv', COLUMNS, records)
    return groups
