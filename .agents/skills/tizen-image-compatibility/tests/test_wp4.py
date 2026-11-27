"""WP-4 static policy, report and scratch behavior controls."""
from collections import Counter, namedtuple
from contextlib import redirect_stdout
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
from unittest.mock import patch

from test_framework import Environment
from test_report_enhancement import FixtureGuard
from test_static_fixes import elf, symbol
from test_wp3 import LOADER
from compat import erofs
from compat.compare import compare_elf, compare_static, finalize
from compat.core import Tools, read_manifest
from compat.elf import collect_elf, parse_readelf, symbol_identity
from compat.flash import PreparationError
from compat.linker import dependency_checks
from compat.linking_details import LinkingDetails
from compat.report import build_results, generate
from compat.report_enhance import build
from compat.report_io import evidence_path, open_payload
from compat.requirements import Providers, check_available_set, classify, obligations
from compat.repository import symbol_differences
from compat.repository_pairing import abi_key
from compat.symbol_references import resolve_findings
from compat.symbol_rules import classify_symbol_change
from compat.weak_review import Review, PENDING, TITLE
from tizen_compat import main


class Policies(Environment):
    def test_copy_relocation_from_real_nonpie_elf_and_provider_size(self):
        source = self.base / 'copy.c'
        source.write_text('extern int optind; int main(void) { return optind; }\n')
        binary = self.base / 'copy'
        subprocess.run(['gcc', '-no-pie', '-fno-pic', str(source), '-o', str(binary)], check=True)
        target = collect_elf(binary, '/bin/copy', self.tools, 'static')
        self.assertEqual(target['export_inventory_status'], 'COMPLETE')
        (copy,) = target['copy_relocations']
        self.assertEqual(copy['name'], 'optind')
        self.assertNotIn(copy['name'], {s['name'] for s in target['exports']})
        raw = (self.output / target['evidence'][0]).read_text()
        relocation = (self.output / target['evidence'][-2]).read_text()
        self.assertRegex(raw, r'optind@\S+ \(\d+\)')
        self.assertRegex(relocation, r'R_\w+_COPY.*optind@')
        self.assertEqual(parse_readelf(raw, '')['copy_relocations'], [])
        self.assertEqual(parse_readelf(raw.split('Version needs section', 1)[0], relocation)['copy_relocations'], [])
        decorated = copy['name']+'@'+copy['version']
        self.assertEqual(symbol_identity(decorated+' (3)'), symbol_identity(decorated))

        (req,) = [r for r in obligations(target) if r[0] == 'COPY_RELOCATION']
        self.assertEqual(req[4], copy['size'])
        version = copy['version']
        provider = target | {'path':'/lib/provider','soname':copy['provider_soname'], 'elf_runtime_role':'RUNTIME',
                             'type':'DYN', 'version_definitions':[{'name':version,'index':2,'flags':'none'}]}
        def evaluate(size, provider_version=version):
            record = provider | {'exports':[symbol('optind@@'+provider_version) |
                                              {'type':'OBJECT','size':size}]}
            return Providers([record]).evaluate(abi_key(target), [], req)
        same = evaluate(copy['size'])
        changed = evaluate(copy['size']+4)
        self.assertEqual(same, 'SATISFIED')
        self.assertIsNone(classify(req, same, same, True))
        self.assertEqual(classify(req, same, changed, True), ('INCOMPATIBLE','HIGH','COPY_RELOC_SIZE_CHANGED'))
        self.assertEqual(classify(req, same, evaluate(copy['size'],'WRONG'), True)[2], 'VERSIONED_SYMBOL_UNAVAILABLE')

    def test_legacy_exports_compare_canonical_version_name(self):
        base = elf('/lib/provider',exports=[symbol('api@@WP4_1 (2)')])
        peer = base | {'exports':[symbol('api@@WP4_1')]}
        findings = compare_elf({'elf_objects':[base]}, {'elf_objects':[peer]})
        self.assertFalse(any(f['interface'].startswith('api') for f in findings))

    def test_compact_rows_keep_data_and_count_code_and_satisfied_requirements(self):
        a = elf('/lib/provider', type='DYN', soname='lib.so',
                exports=[symbol('code'), symbol('data',kind='OBJECT')])
        b = a | {'exports':[symbol('code',size=16), symbol('data',kind='OBJECT',size=16)]}
        pair = dict(package_id='fixture',component=a['path'],baseline_object=a['path'],candidate_object=b['path'])
        result = dict(findings=[],repository={'elf_pairs':[pair]})
        catalog = [{x['path']:x} for x in (a,b)]
        only_relevant = list(symbol_differences(result,catalog,'changes'))
        self.assertEqual([row['details'] for row in only_relevant],[['DATA_SIZE_CHANGED']])
        self.assertEqual(result['repository']['symbol_differences']['omitted_by_detail'], {'CODE_SIZE_CHANGED':1})
        self.assertEqual(len(list(symbol_differences(result,catalog,'all'))),2)
        app = elf('/bin/consumer',needed=['lib.so'])
        for obj in (a,b,app):
            obj['elf_runtime_role'] = 'RUNTIME'
        catalogs = [{obj['path']:obj for obj in (provider,app)} for provider in (a,b)]
        owners = {obj['path']:('fixture','fixture-0:1-1.x86_64') for obj in (a,app)}
        components = {path:path for path in owners}
        for requested in (False,True):
            counts, findings = check_available_set(catalogs,owners,components,[True,True],self.output,
                                                   include_satisfied=requested)
            self.assertEqual(counts['by_kind']['DT_NEEDED']['satisfied'],1)
            self.assertEqual(counts['satisfied_rows_written'],int(requested))
            self.assertEqual(findings,[])
            with (self.output/'requirement-findings.csv').open() as stream:
                self.assertEqual([r['reason_code'] for r in csv.DictReader(stream)],
                                 ['REQUIREMENT_SATISFIED'] if requested else [])

    def test_rootfs_copy_requires_proven_scope_and_expected_size(self):
        version = {'name':'MARK_1','index':2,'flags':'none'}
        app = elf('/bin/copy', needed=['libcopy.so'],
                  copy_relocations=[dict(name='optind@MARK_1',version='MARK_1',size=4,provider_soname='libcopy.so')],
                  version_requirements=[version | {'file':'libcopy.so'}])
        def check(size, complete=True):
            provider = elf('/lib/libcopy.so',type='DYN',soname='libcopy.so',version_definitions=[version],
                           exports=[symbol('optind@@MARK_1',kind='OBJECT',size=size)])
            return next(r for r in dependency_checks(
                {'elf_objects':[provider], 'loader_environment':LOADER | {'environment_complete':complete},
                 'filesystem_path_inventory_complete':True}, 'test', [app])
                if r['check_id'].startswith('copy relocation:'))
        self.assertEqual(check(4)['status'],'COMPATIBLE')
        self.assertEqual((check(8)['status'],check(8)['reason_code']),('INCOMPATIBLE','COPY_RELOC_SIZE_CHANGED'))
        self.assertEqual(check(8,False)['status'],'UNKNOWN')

    def test_binding_policy_and_configured_loader(self):
        cases = [('GLOBAL','WEAK',False,('COMPATIBLE','INFO','SYMBOL_BINDING_WEAKENED')),
                 ('WEAK','GLOBAL',False,('COMPATIBLE','INFO','SYMBOL_BINDING_STRENGTHENED')),
                 ('UNIQUE','WEAK',False,('UNKNOWN','MEDIUM','GNU_UNIQUE_DROPPED')),
                 ('GLOBAL','WEAK',True,('UNKNOWN','MEDIUM','DYNAMIC_WEAK_SEMANTICS'))]
        for before, after, alternate, expected in cases:
            self.assertEqual(classify_symbol_change('binding', before, after, dynamic_weak=alternate), expected)
            a, b = [self.blank() | {'elf_objects':[elf('/lib/lib.so',exports=[symbol('value') | {'binding':binding}])]}
                    for binding in (before,after)]
            self.config['loader']['environments']['candidate'] = LOADER | {'ld_dynamic_weak':alternate}
            matches = [f for f in compare_static(a,b,self.config) if f['interface']=='value:binding']
            (row,) = matches
            self.assertEqual((row['status'],row['severity'],row['reason_code']),expected)

    def weak_inputs(self):
        names = ('_Z5templIiEvv','_ZTV4Test','_Z3runv','_Z4usedv','_Z6strongv','ordinary_c')
        exports = [symbol(name) | {'binding':'GLOBAL' if name == '_Z6strongv' else 'WEAK'} for name in names]
        left = elf('/lib/a.so', exports=exports)
        right = elf('/lib/a.so', exports=[])
        importer = elf('/bin/importer', imports=[symbol('_Z4usedv')])
        return (self.blank() | {'elf_objects':[left, importer]},
                self.blank() | {'elf_objects':[right, importer]})

    def test_weak_review_table_and_legacy_grading(self):
        a,b = self.weak_inputs()
        review = Review()
        rows = finalize(compare_static(a,b,self.config,review=review),self.config)
        by_reason = Counter((r['status'],r['reason_code']) for r in rows if 'removal_context' in r)
        self.assertEqual(by_reason, {('INCOMPATIBLE','EXPORT_REMOVED'):3, ('UNKNOWN',PENDING):3})
        result = build_results(a,b,rows,[],[],self.config)
        result.update(scope='RUNTIME_ROOTFS', review=review.summary(rows))
        generate(self.output,a,b,result,self.config,tools=self.tools)
        with (self.output/'weak-export-review.csv').open() as stream:
            table = list(csv.DictReader(stream))
        self.assertEqual({r['symbol'] for r in table}, {'_Z5templIiEvv','_ZTV4Test','_Z3runv'})
        if shutil.which('c++filt'):
            self.assertTrue(any('vtable for Test' == r['demangled'] for r in table))
        for leaf in ('index.html','summary.md'):
            self.assertIn(TITLE, (self.output/leaf).read_text())
        self.config['policy']['weak_cxx_export_removal'] = 'incompatible'
        old = compare_static(a,b,self.config)
        self.assertEqual(Counter((r['status'],r['reason_code']) for r in old if 'removal_context' in r),
                         {('INCOMPATIBLE','EXPORT_REMOVED'):6})
        compact = json.loads((self.output/'results.json').read_text())
        self.assertTrue(any('$symbol' in (f['baseline'] or {}) for f in compact['findings']
                            if isinstance(f['baseline'],dict)))
        self.assertEqual(resolve_findings(self.output, compact),result['findings'])
        index = self.base/'index'
        build(self.output,index,FixtureGuard)
        self.assertEqual(json.loads((index/'validation.json').read_text())['status'],'PASS')

    def test_review_gate_headline_and_exit_code(self):
        left = self.blank() | {'schema_version':'1.2','elf_objects':[elf('/lib/a.so',exports=[symbol('_Z3runv',binding='WEAK')])]}
        right = self.blank() | {'schema_version':'1.2','elf_objects':[elf('/lib/a.so')]}
        for side, data in (('old', left), ('new', right)):
            (self.base/(side+'.json')).write_text(json.dumps(data))
        def run(tag, candidate, *args):
            output = self.base/tag
            with redirect_stdout(io.StringIO()) as console:
                code = main(['--baseline-manifest',str(self.base/'old.json'),'--candidate-manifest',
                             str(self.base/(candidate+'.json')),'--output',str(output),*args])
            self.assertEqual(code,0)
            handoff = json.loads((output/'run-summary.json').read_text())
            self.assertEqual(handoff['ci_gate_status'],'PASS')
            return output, console.getvalue(), handoff

        output,line,handoff = run('pending','new')
        notice = 'Owner review: 1 weak C++ export removals pending (see weak-export-review.csv).'
        self.assertEqual(handoff['review_gate'],'PENDING')
        self.assertIn(notice,line)
        markdown = (output/'summary.md').read_text()
        html = (output/'index.html').read_text()
        self.assertIn(notice,markdown.split('## ',1)[0])
        self.assertIn(notice,html.split('Collector execution',1)[0])
        self.assertIn('| cxx_other | 1 |',markdown)
        self.assertIn('<th>C++ class</th><th>Count</th>',html)

        with (output/'weak-export-review.csv').open() as stream:
            row = next(csv.DictReader(stream))
        decision = self.base/'accept.csv'
        decision.write_text('review_id,review_decision,reviewer,review_note\n'
                            +row['review_id']+',ACCEPT,Owner,Verified\n')
        for expected, candidate, args in (('NONE','old',()),
                                           ('COMPLETE','new',('--review-decisions',str(decision)))):
            with self.subTest(expected=expected):
                output,line,handoff = run(expected,candidate,*args)
                self.assertEqual(handoff['review_gate'],expected)
                self.assertNotIn('Owner review:',line)
                for leaf in ('summary.md','index.html'):
                    self.assertNotIn('Owner review:', (output/leaf).read_text())

    def test_review_decisions_scope_and_receipt(self):
        a,b = self.weak_inputs()
        base = [r for r in compare_static(a,b,self.config) if 'review' in r]
        file = self.base/'decisions.csv'
        with file.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['review_id','review_decision','reviewer','review_note'])
            for item, decision in zip(base, ('ACCEPT','REJECT','')):
                writer.writerow([item['review']['review_id'],decision,'Owner','Reviewed'])
            writer.writerow(['WEAK-unmatched','ACCEPT','Owner','No matching entry'])
        before = file.read_bytes()
        decision = Review(file)
        findings = finalize(compare_static(a,b,self.config,review=decision),self.config)
        summary = decision.summary(findings)
        self.assertEqual([summary[k] for k in ('required','accepted','rejected','pending','unmatched','status')],
                         [3,1,1,1,1,'PENDING'])
        for value in ('ACCEPTED','REJECTED'):
            (row,) = [r for r in findings if r.get('review_state') == value]
            self.assertEqual(row['review']['reviewer'],'Owner')
            self.assertEqual(row['reason_code'], 'WEAK_CXX_EXPORT_REMOVAL_'+value)
        self.assertTrue(all('review' not in r for r in findings if r.get('reason_code') == 'EXPORT_REMOVED'))
        self.assertEqual(file.read_bytes(),before)
        self.assertEqual(summary['decisions_sha256'],hashlib.sha256(before).hexdigest())
        result = build_results(a,b,findings,[],[],self.config)
        result.update(scope='RUNTIME_ROOTFS', review=summary)
        generate(self.output,a,b,result,self.config)
        receipt = json.loads((self.output/'results.json').read_text())['run_summary']['review']
        self.assertEqual(receipt['decisions_sha256'],summary['decisions_sha256'])
        self.assertEqual(receipt['unmatched'],1)

    def test_dt_needed_aggregates_keep_missing_individual(self):
        app = elf('/bin/a',needed=['a.so','b.so','absent.so'])
        providers = [elf('/lib/'+name,type='DYN') | {'soname':name} for name in ('a.so','b.so')]
        objects = [app,*providers]
        files = [dict(path=obj['path'],type='file',**obj['execution_metadata']) for obj in objects]
        manifest = {'elf_objects':objects,'loader_environment':LOADER,
                    'filesystem_path_inventory_complete':True,'filesystem':files}
        with LinkingDetails(self.base/'stage') as details:
            results = dependency_checks(manifest,'candidate',details=details)
            results += details.finish(self.output/'linking-details.csv')
        with (self.output/'linking-details.csv').open() as stream:
            records = list(csv.DictReader(stream))
        required = [r for r in records if r['check_id'].startswith('DT_NEEDED:')]
        self.assertEqual(len(required),3)
        broken = next(r for r in required if r['check_id']=='DT_NEEDED:absent.so')
        self.assertEqual(broken['id'],broken['anchor_finding_id'])
        self.assertTrue(any(r['id']==broken['id'] and r['status']=='INCOMPATIBLE' for r in results))
        self.assertTrue(all(r['anchor_finding_id']!=r['id'] for r in required if r is not broken))

    def test_compressed_manifest_reuse_and_raw_evidence(self):
        tool = Tools(self.output, self.config, compress_evidence=True)
        raw = b'fixture evidence\x00\n'
        sha = hashlib.sha256(raw).hexdigest()
        ref = tool.store_evidence(io.BytesIO(raw), sha)
        path = evidence_path(self.output, ref)
        self.assertEqual(path.name,sha+'.txt.gz')
        with open_payload(path) as stream:
            self.assertEqual(hashlib.sha256(stream.read()).hexdigest(),sha)
        a,b = self.blank(),self.blank()
        result = build_results(a,b,[],[],[],self.config)
        generate(self.output,a,b,result | {'scope':'RUNTIME_ROOTFS'},self.config)
        self.assertEqual(read_manifest(self.output/'baseline-manifest.json')['image'],a['image'])
        reused = self.base / 'reused'
        rc = main(['--reuse',str(self.output),'--output',str(reused)])
        self.assertIn(rc,(0,1))
        with open_payload(evidence_path(reused, ref)) as stream:
            self.assertEqual(stream.read(),raw)
        with self.assertRaises(ValueError):
            evidence_path(reused, 'evidence/../results.json')

    def test_erofs_old_bwrap_scratch_and_storage_gate(self):
        image = self.base/'image.erofs'
        data = bytearray(4096)
        data[1024:1028] = b'\xe2\xe1\xf5\xe0'
        data[1036] = 12
        struct.pack_into('<I',data,1060,1)
        image.write_bytes(data)
        fsck = self.base/'fixture-fsck'
        fsck.write_text('#!/bin/sh\ncase "$1" in --version) echo fixture;; --help) echo "--extract --no-preserve";; esac\n')
        fsck.chmod(0o700)
        wrap = self.base/'fixture-bwrap'
        wrap.write_text('#!/bin/sh\necho "bwrap: Unknown option --size" >&2\nexit 1\n')
        wrap.chmod(0o700)
        self.config['tools'].update({'fsck.erofs':str(fsck), 'bwrap':str(wrap)})
        info = erofs.superblock(image)
        for state in ('success','failure','storage'):
            with self.subTest(state=state):
                work = self.output/state
                work.mkdir()
                record = {'layers':[]}
                tool = Tools(self.output,self.config)
                def capture(argv, env, stdout, stderr, *args, **kwargs):
                    scratch = Path(argv[argv.index('--bind')+1])
                    self.assertEqual(scratch.parent,work)
                    self.assertTrue(scratch.is_dir())
                    self.assertNotIn('--size',argv)
                    (scratch/'control').write_bytes(b'control')
                    self.assertTrue(kwargs['keep_running']())
                    return (0 if state=='success' else 1, '', 'VERIFIED')
                cap = Tools.capture_bounded
                def dispatch(argv, *args, **kwargs):
                    return capture(argv,*args,**kwargs) if '--bind' in argv else cap(argv,*args,**kwargs)
                with patch.object(Tools,'capture_bounded',side_effect=dispatch):
                    if state == 'storage':
                        usage = namedtuple('Usage', 'free')(64*1024**2+image.stat().st_size)
                        with patch.object(erofs.shutil,'disk_usage',return_value=usage), self.assertRaisesRegex(
                                PreparationError,'EROFS_STORAGE_LIMIT'):
                            erofs.extract(image.resolve(),work,tool,record,info)
                    elif state == 'failure':
                        with self.assertRaisesRegex(PreparationError,'EROFS_EXTRACTION_FAILED'):
                            erofs.extract(image.resolve(),work,tool,record,info)
                    else:
                        erofs.extract(image.resolve(),work,tool,record,info)
                        self.assertEqual(record['extractor']['scratch'],'DISK')
                self.assertEqual(list(work.glob('erofs-scratch-*')),[])
                self.assertEqual(image.read_bytes(),data)
