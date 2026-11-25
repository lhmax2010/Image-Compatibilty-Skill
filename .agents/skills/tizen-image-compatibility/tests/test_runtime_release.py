import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from compat import runtime_binding, runtime_plan
from compat.core import InputError, hash_file
from compat.sdb_runtime import verify_loaded
import runtime_workflow


PROBE = '1'*64
LIB = '2'*64
PIN = '3'*64
ENV = '4'*64
TARGET = dict(scope='SR_HEADED_RUNTIME', build_id='tizen-unified-toolchain_20261120.082536_tizen-headed-armv7l',
              profile='tizen-headed-armv7l', target_sha256='5'*64, environment_id=ENV)


class ExactBindingTests(unittest.TestCase):
    def setUp(self):
        self.directory = '/opt/attempt-one'
        self.artifact = {'files':{'probe':PROBE,'test.so':LIB,'second.so':'6'*64},
                         'runtime_expectation':{'exit_code':0,'stdout':'','stderr':''}}
        self.contract = dict(consumer='bundle:probe', provider='bundle:test.so', symbol='sr_contract',
                             version='TEST_1', provider_sha256=LIB)
        self.event = dict(consumer=self.directory+'/probe', provider='./test.so', consumer_namespace=0,
                          provider_namespace=0, symbol='sr_contract', version='TEST_1')
        self.files = [{'requested':self.directory+'/'+leaf, 'path':self.directory+'/'+leaf, 'sha256':checksum}
                      for leaf, checksum in self.artifact['files'].items() if leaf != 'probe']
        self.attempt = SimpleNamespace(directory=self.directory)

    def check(self, events, files=None, contracts=None):
        return runtime_binding.exact_results(contracts or [self.contract], events, self.files if files is None else files,
                                             self.attempt, self.artifact)

    def test_exact_binding_from_raw_glibc_log_and_pinned_provider(self):
        log = b"binding file /opt/attempt-one/probe [0] to ./test.so [0]: normal symbol `sr_contract' [TEST_1]\n"
        selected = self.check(list(runtime_binding.events(log, {'sr_contract'})))[0]
        self.assertEqual(selected['status'],'VERIFIED')
        self.assertEqual(selected['matched_event']['loaded_provider']['sha256'],LIB)
        self.assertEqual(self.check([self.event],[])[0]['status'],'NOT_VERIFIED')
        bad_hash = [row | {'sha256':'f'*64} for row in self.files]
        self.assertEqual(self.check([self.event],bad_hash)[0]['status'],'NOT_VERIFIED')

    def test_same_name_wrong_version_provider_or_consumer(self):
        negatives = [('version','TEST_2'),('provider','./second.so'),('consumer','./second.so')]
        for field, wrong in negatives:
            with self.subTest(field=field):
                self.assertEqual(self.check([self.event | {field:wrong}])[0]['status'],'NOT_VERIFIED')

    def test_version_check_does_not_prove_lazy_binding(self):
        log = b"checking for version `TEST_1' in file ./test.so\n"
        observed = verify_loaded(None,self.attempt,self.artifact | {'binding_symbols':['sr_contract'],
                               'binding_contracts':[self.contract]},log,startup_failure=True)
        self.assertEqual(observed['versions'][0]['version'],'TEST_1')
        self.assertEqual(observed['unobserved_binding_symbols'],['sr_contract'])
        self.assertEqual(observed['exact_bindings'][0]['status'],'NOT_VERIFIED')

    def test_competing_provider_or_namespace_is_reported_as_ambiguous(self):
        for competing in (self.event | {'provider':'./second.so'}, self.event | {'consumer_namespace':1}):
            self.assertEqual(self.check([self.event,competing])[0]['reason'],'AMBIGUOUS_BINDINGS')
        self.assertEqual(self.check([self.event,self.event])[0]['status'],'VERIFIED')
        second = self.contract | {'consumer':'bundle:second.so'}
        output = self.check([self.event, self.event | {'consumer':'./second.so'}],contracts=[self.contract,second])
        self.assertEqual([r['status'] for r in output],['VERIFIED','VERIFIED'])

    def test_manifest_rejects_wrong_exact_provider_pin_or_duplicate_contract(self):
        runtime_binding.validate_contracts(self.artifact | {'binding_contracts':[self.contract]})
        with self.assertRaises(InputError):
            runtime_binding.validate_contracts(self.artifact | {'binding_contracts':[
                self.contract | {'provider_sha256':'f'*64}]})
        with self.assertRaises(InputError):
            runtime_binding.validate_contracts(self.artifact | {'binding_contracts':[self.contract,self.contract]})


class ExpectedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.artifact = dict(artifact_id='case', sha256=PROBE, manifest_sha256=PIN,
                             files={'probe':PROBE,'example.so':LIB},
                             runtime_expectation={'exit_code':0,'stdout':'ok\n','stderr':''})
        self.test = runtime_plan.expected_case(self.artifact,TARGET)
        self.plan = {'schema':runtime_plan.PLAN, 'tests':[self.test]}
        self.receipt = dict(schema='tizen-compat-sdb-observation/v1', result='OBSERVED_SUCCESS',
            test_id=self.test['test_id'], attempt_id='a'*16, artifact_id='case', scope=TARGET['scope'],
            build_id=TARGET['build_id'], profile=TARGET['profile'], environment_id=ENV,
            enrolled_target_sha256=TARGET['target_sha256'], manifest_sha256=PIN, artifact_sha256=PROBE,
            bundle_sha256=self.test['bundle_sha256'], execution_status='EXITED', target_returncode=0,
            admission_status='VERIFIED', deployment_status='VERIFIED', target_cleanup_status='VERIFIED',
            directory_removed=True, behavior_match=True, captured_output={'stdout':'ok\n','stderr':''})

    def file(self, name, data):
        file = self.root/name
        file.write_text(json.dumps(data))
        return file

    def report(self, records, config=None, trusted=True):
        rows = runtime_plan.read_attempts(records)
        live = {r['sha256']:r['record']['test_id'] for r in rows if not r.get('input_error')} if trusted else {}
        report = runtime_plan.reconcile(config or {}, self.plan, rows, live)
        return report, rows

    def test_duplicate_receipt_scored_once_and_external_hash_not_trust(self):
        path = self.file('receipt', self.receipt)
        trusted, rows = self.report([path,path])
        self.assertEqual(trusted['counts'],{'OBSERVED_SUCCESS':1})
        self.assertEqual(trusted['unique_attempts'],1)
        self.assertEqual(rows[1]['disposition'],'DUPLICATE_RECEIPT')
        external, _ = self.report([path],trusted=False)
        self.assertEqual(external['counts'],{'NOT_VERIFIED':1})
        self.assertEqual(external['unique_attempts'],0)
        self.assertEqual(external['reported_attempt_ids'],1)

    def test_attempt_history_explicit_selection_and_conflicting_same_id(self):
        first = self.file('first',self.receipt | {'behavior_match':False})
        second = self.file('second',self.receipt | {'attempt_id':'b'*16})
        both, _ = self.report([first,second])
        self.assertEqual(both['counts'],{'NOT_VERIFIED':1})
        chosen, _ = self.report([first,second],{'final_attempts':{self.test['test_id']:hash_file(second)}})
        self.assertEqual(chosen['counts'],{'OBSERVED_SUCCESS':1})
        self.assertEqual(len(chosen['tests'][0]['attempts']),2)
        conflict = self.file('conflict',self.receipt)
        disputed, rows = self.report([first,conflict])
        self.assertEqual(disputed['counts'],{'NOT_VERIFIED':1})
        self.assertTrue(all(r['disposition']=='CONFLICTING_ATTEMPT_ID' for r in rows))

    def test_mismatched_artifact_manifest_bundle_and_target_rejected(self):
        changes = {'artifact_sha256':'ARTIFACT_IDENTITY_MISMATCH','manifest_sha256':'MANIFEST_DIGEST_MISMATCH',
                   'bundle_sha256':'BUNDLE_DIGEST_MISMATCH','environment_id':'ENVIRONMENT_IDENTITY_MISMATCH',
                   'profile':'TARGET_IDENTITY_MISMATCH','enrolled_target_sha256':'TARGET_IDENTITY_MISMATCH'}
        for key, disposition in changes.items():
            with self.subTest(field=key):
                path = self.file('receipt',self.receipt | {key:'f'*64})
                result, rows = self.report([path])
                self.assertEqual(result['counts'],{'NOT_VERIFIED':1})
                self.assertEqual(rows[0]['disposition'],disposition)

    def test_missing_repetition_optional_skip_and_interruption(self):
        first = runtime_plan.expected_case(self.artifact,TARGET,1,2)
        second = runtime_plan.expected_case(self.artifact,TARGET,2,2)
        skip = runtime_plan.expected_case(self.artifact | {'artifact_id':'optional'},TARGET,
                                          required=False,skip_reason='Unavailable runtime component')
        self.plan['tests'] = [first,second,skip]
        interrupted = self.file('interrupted',self.receipt | {'test_id':first['test_id'],
                                  'result':'BLOCKED','execution_status':'NOT_EXECUTED','error_code':'INTERRUPTED'})
        result, _ = self.report([interrupted])
        self.assertEqual(result['counts'],{'BLOCKED':1,'NOT_EXECUTED':1,'SKIP':1})
        self.assertEqual(result['required_counts'],{'BLOCKED':1,'NOT_EXECUTED':1})
        self.plan['tests'].remove(second)
        with self.assertRaises(InputError):
            self.report([])

    def test_independent_review_pin_and_invalid_receipt_remain_auditable(self):
        path = self.file('receipt',self.receipt)
        malformed = self.root/'malformed'
        malformed.write_text('{')
        invalid_status = self.file('bad-execution-field',self.receipt | {'execution_status':['EXITED']})
        review = self.file('review',{'schema':runtime_plan.REVIEW,'attempts':{
            hash_file(path):{'test_id':self.test['test_id'],'review_basis':'synthetic review fixture'}}})
        config = {'reviewed_runtime_attempts':{'path':str(review),'sha256':hash_file(review)}}
        result, rows = self.report([path,malformed,invalid_status],config,trusted=False)
        self.assertEqual(rows[1]['disposition'],'INVALID_RECEIPT')
        self.assertEqual(rows[2]['disposition'],'INVALID_RECEIPT')
        self.assertEqual(result['counts'],{'OBSERVED_SUCCESS':1})
        review.write_text('changed')
        with self.assertRaises(InputError):
            self.report([path],config,trusted=False)

    def test_plan_is_on_disk_before_first_grant_and_failfast_survives(self):
        second_artifact = self.artifact | {'artifact_id':'next','bundle_path':'next/probe'}
        second = runtime_plan.expected_case(second_artifact,TARGET)
        self.plan['tests'].append(second)
        first_artifact = self.artifact | {'bundle_path':'case/probe'}
        enrollment = {'sdb_serial':'192.0.2.3:26101'}
        schedule = [(self.test,enrollment,first_artifact,self.root),(second,enrollment,second_artifact,self.root)]

        def blocked(transport,spec,artifact,source,output,**options):
            self.assertTrue((self.root/'runtime-expected-plan.json').is_file())
            (output/'runtime.json').write_text(json.dumps(self.receipt | {'result':'BLOCKED',
                'execution_status':'NOT_EXECUTED','target_cleanup_status':'NOT_VERIFIED'}))
            return 3
        with (patch.object(runtime_workflow,'prepare',return_value=(self.plan,schedule)),
              patch.object(runtime_workflow.shutil,'which',return_value='/sdb'),
              patch.object(runtime_workflow,'validate_enrollment'),
              patch.object(runtime_workflow,'handle',side_effect=blocked) as handler):
            self.assertEqual(runtime_workflow.run({},self.root,admit=False,execute=True),3)
            self.assertEqual(handler.call_count,1)
        results = json.loads((self.root/'results.json').read_text())
        self.assertEqual(results['runtime_status_counts'],{'BLOCKED':1,'NOT_EXECUTED':1})
        self.assertEqual(results['formal_compatibility'],'UNKNOWN')
