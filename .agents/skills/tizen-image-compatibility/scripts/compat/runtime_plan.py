"""Expected SDB observations and reconciliation of immutable attempt evidence."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from .core import InputError, canonical, digest

PLAN = 'tizen-compat-runtime-expected-plan/v1'
REVIEW = 'tizen-compat-runtime-reviewed-attempts/v1'
LEGACY_MANIFEST = 'fe59f50a2501d0c165b5e7a3b037e969b418e06bbb8951e917412a4a06713c32'
SCOPES = {'SR_HEADED_RUNTIME', 'SR_RUNTIME'}
SHA = re.compile(r'[a-f0-9]{64}')
ATTEMPT = re.compile(r'[a-f0-9]{16}')
PERFORMED = {'EXITED', 'TIMEOUT'}


def sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def bundle_digest(artifact):
    files = artifact.get('files')
    return digest(canonical(files if files is not None else {'probe':artifact['sha256']}).encode())


def expected_case(artifact, target, iteration=1, repetitions=1, required=True, skip_reason=None):
    row = dict(artifact_id=artifact['artifact_id'], manifest_sha256=artifact['manifest_sha256'],
               artifact_sha256=artifact['sha256'], bundle_sha256=bundle_digest(artifact),
               bundle_files=artifact.get('files', {'probe':artifact['sha256']}),
               target=target, expected_behavior=artifact['runtime_expectation'],
               binding_contracts=artifact.get('binding_contracts', []),
               repetition=iteration, repetitions=repetitions, required=required, skip_reason=skip_reason)
    if artifact.get('binding_symbols'):
        row['binding_symbols'] = artifact['binding_symbols']
    return {'test_id':test_id(row), **row}


def test_id(row):
    return 'RT-'+digest(canonical({k:v for k,v in row.items() if k != 'test_id'}).encode())[:24]


def validate_plan(plan):
    if plan['schema'] != PLAN or not isinstance(plan['tests'], list) or len(plan['tests']) > 4096:
        raise InputError('Invalid Runtime Expected Plan')
    tests = {}
    repetitions = defaultdict(list)
    for row in plan['tests']:
        key, target = row['test_id'], row['target']
        skip = row['skip_reason']
        files = row['bundle_files']
        behavior = row['expected_behavior']
        if (key != test_id(row) or key in tests or not row['artifact_id']
                or not all(sha(row[field]) for field in ('manifest_sha256','artifact_sha256','bundle_sha256'))
                or not isinstance(files, dict) or files.get('probe') != row['artifact_sha256']
                or not all(sha(value) for value in files.values()) or row['bundle_sha256'] != digest(canonical(files).encode())
                or target['scope'] not in SCOPES or not sha(target['target_sha256'])
                or target['profile'] != target['build_id'].rsplit('_', 1)[-1]
                or target['profile'] != ('tizen-headed-armv7l' if target['scope'] == 'SR_HEADED_RUNTIME' else 'tizen-headless-armv7l')
                or target['environment_id'] is not None and not sha(target['environment_id'])
                or not isinstance(behavior, dict) or type(behavior.get('exit_code')) is not int
                or not 0 <= behavior['exit_code'] <= 255
                or behavior.get('outcome', 'exit') not in ('exit', 'timeout', 'loader-error')
                or any(not isinstance(behavior.get(field), str) for field in ('stdout','stderr'))
                or behavior.get('outcome') == 'loader-error' and (
                    not isinstance(behavior.get('stderr_contains'), str) or not behavior['stderr_contains'])
                or not isinstance(row['binding_contracts'], list)
                or not isinstance(row.get('binding_symbols', []), list)
                or type(row['required']) is not bool or skip is not None and (row['required'] or not isinstance(skip, str) or not skip)
                or type(row['repetition']) is not int or type(row['repetitions']) is not int
                or not 1 <= row['repetition'] <= row['repetitions'] <= 100):
            raise InputError('Invalid or duplicate expected Runtime Test ID or contract')
        tests[key] = row
        cohort = canonical({k:v for k,v in row.items() if k not in ('test_id','repetition')})
        repetitions[cohort].append(row['repetition'])
    if any(sorted(values) != list(range(1, json.loads(cohort)['repetitions']+1))
           for cohort, values in repetitions.items()):
        raise InputError('Runtime repetition schedule is incomplete')
    return tests


def pinned_document(spec, max_bytes=8*1024**2):
    path = Path(spec['path'])
    with path.open('rb') as stream:
        raw = stream.read(max_bytes+1)
    if len(raw) > max_bytes or not sha(spec['sha256']) or digest(raw) != spec['sha256']:
        raise InputError('Independent Runtime document pin differs: '+str(path))
    return json.loads(raw)


def reviewed_mapping(config, tests):
    spec = config.get('reviewed_runtime_attempts')
    if not spec:
        return {}
    review = pinned_document(spec)
    if review['schema'] != REVIEW or not isinstance(review['attempts'], dict):
        raise InputError('Invalid Runtime review ledger')
    for checksum, entry in review['attempts'].items():
        if (not sha(checksum) or entry['test_id'] not in tests
                or not isinstance(entry.get('review_basis'), str) or not entry['review_basis']
                or type(entry.get('legacy', False)) is not bool
                or type(entry.get('eligible', True)) is not bool):
            raise InputError('Invalid reviewed attempt mapping')
    return review['attempts']


def read_attempts(paths):
    rows = []
    for source in paths:
        entry = {'source':str(source), 'sha256':None, 'record':None}
        try:
            with Path(source).open('rb') as stream:
                raw = stream.read(2*1024**2+1)
            if len(raw) > 2*1024**2:
                raise ValueError('Runtime observation exceeds its size limit')
            entry['sha256'] = digest(raw)
            record = json.loads(raw)
            entry['record'] = record
            if (not isinstance(record, dict) or record.get('schema') != 'tizen-compat-sdb-observation/v1'
                    or record.get('scope') not in SCOPES or not isinstance(record.get('artifact_id'), str)
                    or not isinstance(record.get('result'), str)
                    or record.get('execution_status') is not None and not isinstance(record['execution_status'], str)
                    or record.get('attempt_id') is not None and (
                        not isinstance(record['attempt_id'], str) or not ATTEMPT.fullmatch(record['attempt_id']))):
                raise ValueError('Invalid SDB observation schema or identity')
        except (OSError, ValueError, TypeError) as error:
            entry['input_error'] = str(error)
        rows.append(entry)
    return rows


def identity_errors(row, test, legacy):
    if any(row.get(field) != test[field] for field in ('artifact_id','artifact_sha256')):
        return 'ARTIFACT_IDENTITY_MISMATCH'
    manifest = row.get('manifest_sha256')
    receipt = row.get('receipt') or {}
    if manifest is None and legacy and isinstance(receipt, dict) and receipt.get('binary_sha256') == test['artifact_sha256']:
        manifest = LEGACY_MANIFEST
    if manifest != test['manifest_sha256']:
        return 'MANIFEST_DIGEST_MISMATCH'
    bundle = row.get('bundle_sha256')
    if bundle is None and legacy:
        deployed = row.get('deployed_sha256')
        if deployed == test['bundle_files'] or (
                test['manifest_sha256'] == LEGACY_MANIFEST and set(test['bundle_files']) == {'probe'}):
            bundle = test['bundle_sha256']
    if bundle != test['bundle_sha256']:
        return 'BUNDLE_DIGEST_MISMATCH'
    if row.get('deployed_sha256') is not None and row['deployed_sha256'] != test['bundle_files']:
        return 'DEPLOYED_FILE_DIGEST_MISMATCH'
    target = test['target']
    profile = row.get('profile')
    if legacy and profile is None and isinstance(row.get('build_id'), str):
        profile = row['build_id'].rsplit('_', 1)[-1]
    if (row.get('scope') != target['scope'] or row.get('build_id') != target['build_id'] or profile != target['profile']
            or (not legacy or row.get('enrolled_target_sha256') is not None)
            and row.get('enrolled_target_sha256') != target['target_sha256']):
        return 'TARGET_IDENTITY_MISMATCH'
    if row.get('execution_status') in PERFORMED:
        environment = row.get('environment_id')
        if (not sha(environment) or target['environment_id'] and target['environment_id'] != environment
                or legacy and not target['environment_id']):
            return 'ENVIRONMENT_IDENTITY_MISMATCH'
    if row.get('test_id') != test['test_id'] and (not legacy or row.get('test_id') is not None):
        return 'TEST_ID_MISMATCH'
    return None


def outcome(row, test):
    if row['result'] == 'BLOCKED':
        return 'BLOCKED'
    if row.get('execution_status') not in PERFORMED:
        return 'NOT_EXECUTED' if row['result'] == 'PLANNED' else 'NOT_VERIFIED'
    if (not row.get('attempt_id') or row.get('admission_status') != 'VERIFIED'
            or row.get('deployment_status') != 'VERIFIED' or row.get('target_cleanup_status') != 'VERIFIED'
            or row.get('directory_removed') is not True):
        return 'NOT_VERIFIED'
    capture = row.get('captured_output') or row.get('receipt')
    if not isinstance(capture, dict) or not all(isinstance(capture.get(field), str) for field in ('stdout','stderr')):
        return 'NOT_VERIFIED'
    loader = row.get('loader') or {}
    if not isinstance(loader, dict):
        return 'NOT_VERIFIED'
    contracts = test['binding_contracts']
    if contracts:
        matched_contracts = []
        for item in loader.get('exact_bindings', []):
            event = item.get('matched_event') or {}
            contract = item['contract']
            provider = event.get('loaded_provider') or {}
            if (item['status'] == 'VERIFIED' and event.get('symbol') == contract['symbol']
                    and event.get('version') == contract['version'] and provider.get('sha256') == contract['provider_sha256']
                    and provider in loader.get('files', [])):
                matched_contracts.append(contract)
        if matched_contracts != contracts:
            return 'NOT_VERIFIED'
    if row.get('behavior_match') is False:
        return 'BEHAVIOR_MISMATCH'
    if row.get('behavior_match') is not True:
        return 'NOT_VERIFIED'
    labels = set(test.get('binding_symbols', []))
    if labels and (loader.get('unobserved_binding_symbols')
                   or not labels <= {binding['symbol'] for binding in loader.get('bindings', [])}):
        return 'NOT_VERIFIED'
    expected = test['expected_behavior']
    kind = expected.get('outcome', 'exit')
    if kind == 'loader-error':
        matched = (row['execution_status'] == 'EXITED' and loader.get('status') == 'STARTUP_REJECTED'
                   and not capture['stdout'] and expected['stderr_contains'] in capture['stderr'])
    else:
        matched = row['execution_status'] == ('TIMEOUT' if kind == 'timeout' else 'EXITED') and (
            capture['stdout'], capture['stderr']) == (expected['stdout'], expected['stderr'])
    if not matched or row.get('target_returncode') != expected['exit_code']:
        return 'BEHAVIOR_MISMATCH'
    return 'OBSERVED_SUCCESS' if kind == 'exit' and expected['exit_code'] == 0 else 'OBSERVED_EXPECTED_FAILURE'


def reconcile(config, plan, rows, live_attempts):
    tests = validate_plan(plan)
    reviewed = reviewed_mapping(config, tests)
    selected = config.get('final_attempts', {})
    if not isinstance(selected, dict) or any(k not in tests or not sha(v) for k,v in selected.items()):
        raise InputError('Invalid final Runtime attempt selection')
    by_sha, attempt_digests = {}, defaultdict(set)
    candidates, history = defaultdict(list), defaultdict(list)
    accepted_attempts = {}
    for index, entry in enumerate(rows):
        pin = entry['sha256']
        row = entry['record']
        if not entry.get('input_error') and row.get('attempt_id'):
            attempt_digests[row['attempt_id']].add(pin)
        if pin and pin in by_sha:
            entry.update(disposition='DUPLICATE_RECEIPT', duplicate_of=by_sha[pin])
        elif pin:
            by_sha[pin] = index

    for entry in rows:
        if entry.get('disposition'):
            continue
        row, pin = entry['record'], entry['sha256']
        if entry.get('input_error'):
            entry['disposition'] = 'INVALID_RECEIPT'
            continue
        review = reviewed.get(pin)
        live_id = live_attempts.get(pin)
        key = live_id if live_id else review['test_id'] if review else row.get('test_id')
        key = key if isinstance(key, str) else None
        entry['expected_test_id'] = key
        entry['provenance'] = ('LOCAL_RUN' if live_id else 'INDEPENDENT_REVIEW' if review else 'UNREVIEWED_IMPORT')
        if review:
            entry['review_basis'] = review['review_basis']
        if key not in tests:
            entry['disposition'] = 'UNPLANNED_RECEIPT'
            continue
        history[key].append(entry)
        if len(attempt_digests[row.get('attempt_id')]) > 1:
            entry['disposition'] = 'CONFLICTING_ATTEMPT_ID'
            continue
        if not (live_id or review):
            entry['disposition'] = 'UNVERIFIED_IMPORT'
            continue
        if review and not review.get('eligible', True):
            entry['disposition'] = 'HISTORICAL_ONLY'
            entry['identity_check'] = identity_errors(row, tests[key], review.get('legacy', False)) or 'MATCH'
            if row.get('attempt_id'):
                accepted_attempts[row['attempt_id']] = row.get('execution_status')
            continue
        mismatch = identity_errors(row, tests[key], bool(review and review.get('legacy')))
        if mismatch:
            entry['disposition'] = mismatch
            continue
        try:
            entry['observed_status'] = outcome(row, tests[key])
        except (KeyError, TypeError, AttributeError, ValueError):
            entry['disposition'] = 'INVALID_RECEIPT'
            continue
        entry['disposition'] = 'ELIGIBLE'
        candidates[key].append(entry)
        if row.get('attempt_id'):
            accepted_attempts[row['attempt_id']] = row.get('execution_status')

    final = []
    for key, test in tests.items():
        eligible = candidates[key]
        if key in selected:
            chosen = next((row for row in eligible if row['sha256'] == selected[key]), None)
            reason = 'EXPLICIT_FINAL_ATTEMPT' if chosen else 'INVALID_FINAL_SELECTION'
        else:
            substantive = [row for row in eligible if row['observed_status'] != 'NOT_EXECUTED']
            eligible = substantive or eligible
            if len(eligible) == 1:
                chosen, reason = eligible[0], 'ONLY_ELIGIBLE_RECEIPT'
            else:
                chosen, reason = None, 'MULTIPLE_ELIGIBLE_ATTEMPTS' if eligible else 'NO_ELIGIBLE_RECEIPT'
        if test['skip_reason']:
            status, reason, chosen = 'SKIP', test['skip_reason'], None
        elif chosen:
            status = chosen['observed_status']
        else:
            status = 'NOT_VERIFIED' if history[key] or key in selected else 'NOT_EXECUTED'
        observation = chosen['record'] if chosen else {}
        capture = observation.get('captured_output') or observation.get('receipt')
        stderr = capture.get('stderr', '') if isinstance(capture, dict) else ''
        limitation = observation.get('environment_limit')
        if not limitation and isinstance(stderr, str) and stderr.startswith('glibc: dlopen blocked for object '):
            limitation = 'TARGET_LOADER_POLICY_BLOCKED'
        final.append({'test':test, 'status':status, 'reason':reason, 'environment_limit':limitation,
                      'final_receipt_sha256':chosen['sha256'] if chosen else None,
                      'environment_id':observation.get('environment_id'),
                      'attempts':[row['sha256'] for row in history[key]],
                      'formal_runtime_status':'NOT_VERIFIED'})
    return {'tests':final, 'counts':dict(Counter(row['status'] for row in final)),
            'required_counts':dict(Counter(row['status'] for row in final if row['test']['required'])),
            'unique_attempts':len(accepted_attempts),
            'performed_attempts':sum(status in PERFORMED for status in accepted_attempts.values()),
            'reported_attempt_ids':len(attempt_digests) - (None in attempt_digests),
            'reported_performed_attempts':len({row['record']['attempt_id'] for row in rows
                if not row.get('input_error') and row['record'].get('attempt_id')
                and row['record'].get('execution_status') in PERFORMED}),
            'receipt_dispositions':dict(Counter(row['disposition'] for row in rows)),
            'invalid_final_selections':sum(row['reason'] == 'INVALID_FINAL_SELECTION' for row in final)}
