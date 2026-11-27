"""WP-3b reason-code, removal context and compact linking contracts."""
import csv
import json
import sys
from unittest.mock import patch

from test_framework import Environment
from test_static_fixes import elf, symbol
from test_wp3 import LOADER
from compat.compare import compare_elf, compare_static, finalize
from compat.core import finding
from compat.elf import collect_elf
from compat.linking_details import LinkingDetails
from compat.report import build_results, generate
from tizen_compat import main


class ReasonTests(Environment):
    def test_missing_reason_mutation_is_detected(self):
        a, b = self.blank(), self.blank()
        record = finding('abi', '/lib/a', 'fixture', 'old', None, 'UNKNOWN')
        self.assertEqual(build_results(a, b, [record], [], [], self.config)['finding_integrity']['missing_reason_codes'], 0)
        record.pop('reason_code')
        self.assertEqual(build_results(a, b, [record], [], [], self.config)['finding_integrity']['missing_reason_codes'], 1)
        record['reason_code'] = 'not-a-code'
        self.assertEqual(build_results(a, b, [record], [], [], self.config)['finding_integrity']['missing_reason_codes'], 1)

    def test_export_incompleteness_explains_every_failed_condition(self):
        path = self.base/'fixture'
        path.write_bytes(b'ELF fixture')
        header = """Class: ELF64
Data: 2's complement, little endian
Type: DYN
Machine: Advanced Micro Devices X86-64
"""
        table = """Symbol table '.dynsym' contains 2 entries:
  0: 0000000000000000 0 NOTYPE LOCAL DEFAULT UND
  1: 0000000000001000 4 FUNC GLOBAL DEFAULT 12 foo
"""
        fixture = header + table
        returncode = dict(returncode=0, stdout_truncated=False, stderr_truncated=False, error='',
                          stdout_evidence='evidence/out.txt', stderr_evidence='evidence/err.txt')
        warning = 'readelf: Warning: /secret/path named package has a malformed symbol table'
        good = dict(stdout=fixture, stderr='', **returncode)
        cases = (
            ('READELF_DIAGNOSTIC', good | {'stderr':warning}),
            ('DYNSYM_ROWS_INCONSISTENT', good | {'stdout':fixture.replace('2 entries','3 entries')}),
            ('VERSION_RECORDS_INCONSISTENT', good | {'stdout':fixture.replace(' foo',' foo@@V0')}),
            ('HEADER_FIELDS_MISSING', good | {'stdout':fixture.replace('Class: ELF64\n','')}),
            ('OBJECT_INCOMPLETE', good | {'returncode':1}),
            ('TOOL_TIMEOUT', good | {'returncode':-1,'error':'timeout','reason_code':'TOOL_TIMEOUT'}),
            ('OUTPUT_LIMIT', good | {'returncode':-1,'error':'adapter output limit exceeded','reason_code':'OUTPUT_LIMIT'}),
        )
        for reason, reply in cases:
            with self.subTest(reason=reason), patch.object(self.tools,'path',return_value='readelf'), patch.object(self.tools,'run',return_value=reply):
                result = collect_elf(path,'/fixture',self.tools,'static')
                self.assertEqual(result['export_inventory_status'],'UNKNOWN')
                self.assertEqual(result['export_inventory_reason_code'],reason)
                self.assertIn(reason,result['export_inventory_diagnostics'])
                if reason == 'READELF_DIAGNOSTIC':
                    self.assertEqual(result['readelf_diagnostic_classes'],['SYMBOL_TABLE_DIAGNOSTIC'])
                    self.assertIn('OBJECT_INCOMPLETE',result['export_inventory_diagnostics'])
        source = self.blank() | {'elf_objects':[result]}
        result = build_results(source, self.blank(), [], [], [], self.config)
        self.assertEqual(result['export_incomplete_by_reason']['baseline'], {'OUTPUT_LIMIT':1})
        self.assertEqual(result['finding_integrity']['missing_reason_codes'], 0)
        generate(self.output, source, self.blank(), result | {'scope':'RUNTIME_ROOTFS'}, self.config)
        persisted = json.loads((self.output/'results.json').read_text())
        self.assertEqual(persisted['export_incomplete_by_reason']['baseline'], {'OUTPUT_LIMIT':1})
        self.assertEqual(persisted['finding_integrity']['missing_reason_codes'], 0)

    def test_removal_context_versions_classes_and_distinct_importers(self):
        provider = elf('/lib/a', type='DYN', exports=[symbol('wanted@@V1'),symbol('unused'),
                            symbol('_ZTV1A'),symbol('_ZTI1A')], imports=[symbol('wanted@V1')])
        importer = elf('/bin/client', imports=[symbol('wanted@V1'),symbol('wanted@V1'),symbol('unused@V2')])
        other_importer = elf('/bin/client', imports=[symbol('wanted@V2')])
        a = self.blank() | {'elf_objects':[provider,importer]}
        b = self.blank() | {'elf_objects':[provider | {'exports':[]},other_importer]}
        findings = compare_elf(a,b)
        context = {f['interface']:f['removal_context'] for f in findings if f.get('reason_code')=='EXPORT_REMOVED'}
        self.assertEqual(context['wanted@@V1']['observed_importers'], {'baseline':1,'candidate':0})
        self.assertEqual(context['unused']['observed_importers'], {'baseline':0,'candidate':0})
        self.assertEqual(context['wanted@@V1']['cxx_class'], 'c')
        self.assertEqual(context['_ZTV1A']['cxx_class'], 'vtable')
        self.assertEqual(context['_ZTI1A']['cxx_class'], 'typeinfo')
        result = build_results(a,b,findings,[],[],self.config)
        self.assertEqual(result['removed_exports']['findings'],4)
        self.assertEqual(result['finding_integrity']['missing_reason_codes'],0)
        b['elf_objects'][0]['export_inventory_complete'] = False
        incomplete = [f for f in compare_elf(a,b) if f.get('reason_code')=='EXPORT_NOT_OBSERVED']
        self.assertEqual(len(incomplete),4)
        self.assertTrue(all(f['status']=='UNKNOWN' and f.get('removal_context') for f in incomplete))


    def test_rpm_extractor_timeout_still_produces_a_reason_complete_report(self):
        root = self.base/'rpms'
        root.mkdir()
        (root/'one.rpm').write_bytes(b'\xed\xab\xee\xdb')
        rpm, extractor = self.base/'rpm', self.base/'rpm2cpio'
        xml = ('<rpmHeader><rpmTag name="Name"><string>demo</string></rpmTag>'
               '<rpmTag name="Version"><string>1</string></rpmTag>'
               '<rpmTag name="Release"><string>1</string></rpmTag>'
               '<rpmTag name="Arch"><string>noarch</string></rpmTag></rpmHeader>')
        rpm.write_text(f'#!{sys.executable}\nprint({xml!r})\n')
        extractor.write_text('#!/bin/sh\n[ "$1" = --version ] && exit 0\nsleep 30 &\nwait\n')
        for program in (rpm,extractor):
            program.chmod(0o700)
        config = self.base/'test.yaml'
        config.write_text(f'analysis: {{extract_timeout_seconds: 1}}\ntools: {{rpm: {rpm}, rpm2cpio: {extractor}}}\n')
        out = self.base/'timeout'
        self.assertEqual(main(['--baseline',str(root),'--candidate',str(root),'--config',str(config),'--output',str(out)]),3)
        report = json.loads((out/'results.json').read_text())
        self.assertEqual(report['finding_integrity']['missing_reason_codes'],0)
        self.assertEqual({item['reason_code'] for item in report['repository']['errors']},{'TOOL_TIMEOUT'})
        self.assertTrue(any(f['reason_code']=='TOOL_TIMEOUT' for f in report['findings']))


class LinkingDetailTests(Environment):
    def test_individual_failures_and_coverage_from_staged_checks(self):
        app = elf('/bin/first', imports=[symbol('a'),symbol('b'),symbol('missing')],needed=['libapi.so'])
        provider = elf('/lib/libapi.so',type='DYN',exports=[symbol('a'),symbol('b')])
        files = [dict(path=obj['path'],type='file',**obj['execution_metadata']) for obj in (app,provider)]
        a = self.blank() | {'elf_objects':[app,provider], 'loader_environment':LOADER,
                           'filesystem_path_inventory_complete':True,'filesystem':files}
        self.config['analysis']['modes'] = ['linking']
        with LinkingDetails(self.base/'stage.sqlite') as details:
            findings = compare_static(a,a,self.config,linking_details=details)
            findings.extend(details.finish(self.output/'linking-details.csv'))
            result = build_results(a,a,finalize(findings,self.config),[],[],self.config,linking_details=details)
            self.assertEqual(details.counts['rows'], 8)
        with (self.output/'linking-details.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        broken = [f for f in result['findings'] if f.get('resolution')=='missing_symbol']
        self.assertEqual(len(broken),2)
        self.assertTrue(all(f['status']=='INCOMPATIBLE' and f['check_id']=='import:missing' for f in broken))
        self.assertTrue(all(row['id']==row['anchor_finding_id'] for row in rows if row['check_id']=='import:missing'))
        good = [f for f in result['findings'] if f.get('aggregated_checks')]
        self.assertEqual(sorted(f['aggregated_checks'] for f in good),[1,1,2,2])
        self.assertEqual({f['consumer_image'] for f in good},{'baseline','candidate'})
        unit = next(u for u in result['coverage']['linking']['units'] if u['interface']==app['path'])
        check = next(c for c in unit['required_checks'] if c['id']=='direct dependency and symbol requirements')
        self.assertEqual((check['status'],check['complete_count'],check['required_count']),('INCOMPATIBLE',4,4))
        self.assertEqual(result['finding_integrity']['missing_reason_codes'],0)
        generate(self.output,a,a,result | {'scope':'RUNTIME_ROOTFS'},self.config)
        run = json.loads((self.output/'results.json').read_text())['run_summary']
        self.assertEqual(run['linking_detail_counts']['rows'],8)

    def test_anchor_keeps_states_consumers_images_and_search_contexts_distinct(self):
        launch = {'consumer':'/lib/dso','image':'candidate','state':'unknown_symbol_semantics','path':'/lib/provider'}
        variants = [launch,launch | {'image':'baseline'},launch | {'consumer':'/lib/alternate'},
                    launch | {'state':'unknown_symbol_scope'},launch | {'path':'/opt/provider'}]
        with LinkingDetails(self.base/'groups.sqlite') as details:
            for i, variant in enumerate(variants):
                item = finding('linking',variant['consumer'],f'replay:import:s{i}',None,None,reason_code=variant['state'].upper())
                item.update(root_consumer_image='baseline',consumer_image=variant['image'],consumer_path=variant['consumer'],
                            check_id=f'import:s{i}', resolution=variant['state'],
                            search_context={'symbol_scope':[{'image':'candidate','path':variant['path'],'name':f's{i}'}]})
                details.add(item,'/bin/root',i,True)
            records = details.finish()
        self.assertEqual(len(records),len(variants))
        self.assertEqual({f['aggregated_checks'] for f in records},{1})
