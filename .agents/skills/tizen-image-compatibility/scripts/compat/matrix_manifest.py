"""Deterministic expected tests planned before compiler/adapter execution."""
from collections import defaultdict
from pathlib import Path
from .core import canonical, digest, hash_file, read_manifest
from .coverage import check, obligation, combined
from .images import Image


def builtin_probes(config, language, assets):
    probes = [(language + '-behavior', assets / ('behavior.c' if language == 'c' else 'behavior.cpp'), ['-pthread', '-ldl', '-lm'])]
    if language == 'cpp' and config.get('extended_runtime_probes'):
        probes += [('cpp-cross-dso', assets / 'cross_dso.cpp', ['-pthread']),
                   ('cpp-cancel', assets / 'cancel.cpp', ['-pthread'])]
    return probes


def prepare_sdks(manifests, tools):
    cc = tools.config['cross_compilation']; sdks = {}
    for label, manifest in zip(('baseline', 'candidate'), manifests):
        path = cc['sysroots'].get(label)
        headers = []
        if path and Path(path).is_dir():
            sdk = Image(Path(path), tools.output / 'build', tools, label + '-sdk'); sdks[label] = sdk
            for directory in cc['include_dirs']:
                resolved = sdk.resolve('/' + directory)
                if resolved and resolved.is_dir():
                    for p in sorted(resolved.rglob('*')):
                        if p.suffix in ('.h', '.hpp', '.hh', '.hxx'):
                            virtual = '/' + directory.strip('/') + '/' + p.relative_to(resolved).as_posix()
                            hp = sdk.resolve(virtual)
                            if hp and hp.is_file(): headers.append({'path': virtual, 'origin': 'sdk', 'sdk': str(sdk.root), 'source_path': str(hp)})
            owned = cc['sdk_package_manifests'].get(label)
            if owned:
                inventory = read_manifest(Path(owned))
                if Path(inventory['image'].get('source', '')).resolve() == Path(path).resolve():
                    manifest['sdk_package_manifest'] = inventory
                else:
                    manifest['sdk_ownership_reason'] = 'Supplied package manifest source does not match SDK/sysroot'
        found = {h['path'] for h in headers}
        headers += [dict(h, origin='sdk_missing') for h in manifest['public_headers'] if h['path'] not in found]
        manifest['sdk_headers'] = sorted({h['path']: h for h in headers}.values(), key=lambda h: h['path'])
    candidate_paths = {h['path'] for h in manifests[1]['sdk_headers']}
    manifests[1]['sdk_headers'] += [dict(h, origin='sdk_missing', source_path=None, sdk=cc['sysroots'].get('candidate')) for h in manifests[0]['sdk_headers'] if h['path'] not in candidate_paths]
    manifests[1]['sdk_headers'].sort(key=lambda h: h['path'])
    return sdks


def plan_expected(manifests, tools, assets):
    cc = tools.config['cross_compilation']; expected = []
    compiler_hashes = {}; source_hashes = {}
    def add(compiler, language, name, kind, destination, sdk_label, source, legacy_id, stages):
        build = cc['builds'].get(compiler, {})
        binary = cc['compilers'].get(compiler, {}).get(language)
        if binary not in compiler_hashes:
            compiler_hashes[binary] = hash_file(Path(binary)) if binary and Path(binary).is_file() else None
        if source not in source_hashes: source_hashes[source] = hash_file(source) if source and source.is_file() else None
        src_hash = source_hashes[source]
        identity = {'compiler': compiler, 'language': language, 'name': name, 'kind': kind, 'destination_image': destination,
                    'compiler_identity': {'path': binary, 'sha256': compiler_hashes[binary], 'configuration': cc['compilers'].get(compiler, {})},
                    'probe_configuration': next((p for p in (tools.config['runtime']['probes'] if compiler == 'custom' else cc['probes']) if p['name'] == name), {}),
                    'sdk_identity': {'label': sdk_label, 'path': cc['sysroots'].get(sdk_label)},
                    'build_provenance': build.get('provenance'), 'source_identity': {'path': str(source) if source else name, 'sha256': src_hash},
                    'target_abi': cc['target_abis'].get(sdk_label), 'reference_image': build.get('reference_image', 'baseline')}
        if name == 'cpp-cross-dso':
            identity['companion_source_sha256'] = hash_file(assets / 'cross_dso_lib.cpp')
            identity['shared_header_sha256'] = hash_file(assets / 'cross_dso.hpp')
        if kind == 'runtime' and destination in tools.config['runtime']['environments']:
            environment = tools.config['runtime']['environments'][destination]
            identity['target_environment'] = {'id': environment['id'], 'backend': environment.get('backend', 'operator-adapter'),
                'image': environment.get('image'), 'configuration_sha256': digest(canonical(environment).encode()),
                'repetitions': tools.config['runtime'].get('repetitions', 1)}
        ident = 'ET-' + digest(canonical(identity).encode())[:24]
        artifact = 'build/probe-' + digest(canonical([compiler, language, name, sdk_label]).encode())[:24] + '.bin' if kind in ('build', 'runtime') and compiler != 'custom' else None
        expected.append(dict(identity, id=ident, legacy_id=legacy_id, image=destination, required_stages=stages,
                             expected_artifact=artifact, actual_stage_results={}, checks=[], evidence=[], reason='Not executed'))
    for compiler in ('gcc', 'clang'):
        build = cc['builds'].get(compiler, {}); sdk_label = build.get('sdk')
        for language in ('c', 'cpp'):
            language_enabled = cc[language + '_tests']
            if not language_enabled and not any(p['language'] == language for p in cc['probes']): continue
            if language_enabled and 'headers' in tools.config['analysis']['modes']:
                for label, m in zip(('baseline', 'candidate'), manifests):
                    if not m.get('sdk_headers'):
                        add(compiler, language, 'header inventory', 'header', label, label, None, compiler + ':' + language + ':header inventory', ['inventory'])
                    for h in m.get('sdk_headers', []):
                        if language == 'c' and not h['path'].endswith('.h'): continue
                        add(compiler, language, 'header:' + h['path'], 'header', label, label, Path(h['source_path']) if h.get('source_path') else None,
                            compiler + ':' + language + ':header:' + h['path'], ['target_abi', 'compilation', 'reference'])
            probes = builtin_probes(cc, language, assets) if language_enabled else []
            probes += [(p['name'], Path(p['source']), p.get('flags', [])) for p in cc['probes'] if p['language'] == language]
            for name, source, _ in probes:
                add(compiler, language, name, 'build', sdk_label, sdk_label, source, compiler + ':' + language + ':' + name,
                    ['target_abi', 'compilation', 'linking'])
                for label in ('baseline', 'candidate'):
                    add(compiler, language, name, 'runtime', label, sdk_label, source, compiler + ':' + name + ':execution',
                        ['compilation', 'linking', 'artifact', 'deployment', 'execution', 'native_reference', 'behavior'])
    for p in tools.config['runtime']['probes']:
        for label in ('baseline', 'candidate'):
            add('custom', '', p['name'], 'runtime', label, None, None, 'custom:' + p['name'],
                ['artifact', 'deployment', 'execution', 'native_reference', 'behavior'])
    ids = [e['id'] for e in expected]
    if len(ids) != len(set(ids)): raise ValueError('Duplicate expected test ID')
    return expected


def reconcile(expected, tests, matrix):
    actual = defaultdict(list)
    for t in tests:
        if t['kind'] != 'diagnostic': actual[t['id']].append(t)
    expected_ids = {e['id'] for e in expected}
    unexpected = sorted(set(actual) - expected_ids)
    builds = {(e['compiler'], e['name']): actual.get(e['id'], []) for e in expected if e['kind'] == 'build'}
    for e in expected:
        matches = actual.get(e['id'], []); t = matches[0] if len(matches) == 1 else {}
        ev = t.get('evidence', [])
        checks = []
        for stage in e['required_stages']:
            value = 'UNKNOWN'
            if t:
                build_tests = builds.get((e['compiler'], e['name']), [])
                build = build_tests[0] if len(build_tests) == 1 else {}
                if stage == 'target_abi': value = 'COMPATIBLE' if t.get('target_abi_verification', {}).get('status') == 'COMPATIBLE' else 'UNKNOWN'
                elif stage in ('compilation', 'linking'):
                    record = build if e['kind'] == 'runtime' else t
                    key = 'compile_status' if stage == 'compilation' else 'link_status'
                    if key in record:
                        value = 'COMPATIBLE' if record[key] == 'SUCCESS' and record.get('artifact_path') == e['expected_artifact'] else 'UNKNOWN'
                    else:
                        value = 'COMPATIBLE' if record.get('success') and record.get('artifact_path') == e['expected_artifact'] else 'UNKNOWN'
                    if e['kind'] == 'header': value = t['status'] if t.get('success') is not None else 'UNKNOWN'
                elif stage == 'artifact':
                    expected_hash = build.get('artifact_sha256') if e['compiler'] != 'custom' else t.get('expected_artifact_sha256')
                    value = 'COMPATIBLE' if expected_hash and t.get('receipt_sha256') == expected_hash else 'UNKNOWN'
                    if e.get('companion_source_sha256') and (not build.get('companion') or t.get('companion_sha256') != build['companion']['sha256']):
                        value = 'UNKNOWN'
                elif stage in ('deployment', 'execution'): value = 'COMPATIBLE' if t.get(stage + '_status') == 'SUCCESS' else 'UNKNOWN'
                elif stage in ('native_reference', 'reference'): value = 'COMPATIBLE' if t.get('native_reference_valid') else 'UNKNOWN'
                elif stage == 'behavior': value = t.get('behavior_status', 'UNKNOWN')
            checks.append(check(stage, value, ev, 'Missing, duplicate, failed or unverified stage: ' + stage if value == 'UNKNOWN' else '', bool(t)))
        if len(matches) != 1: checks.append(check('exact ID membership', reason='Missing expected ID' if not matches else 'Duplicate actual ID', executed=bool(matches)))
        u = obligation(e['id'], checks, matches)
        for record in matches:
            if record['status'] in ('COMPATIBLE', 'IDENTICAL') and u['verification'] != 'COMPLETE':
                record['observed_status'] = record['status']; record['status'] = 'UNKNOWN'
                record['reason'] = 'Expected mandatory stages or ID membership are incomplete'
        e.update(checks=checks, actual_stage_results={c['id']: c['status'] for c in checks}, observed_target_abi=t.get('target_abi_verification'), actual_artifact_sha256=t.get('artifact_sha256') or t.get('receipt_sha256'), status=u['status'],
                 verification=u['verification'], evidence=u['evidence'], reason='; '.join(u['limitations']))
    for ident in unexpected:
        for t in actual[ident]:
            if t['status'] in ('COMPATIBLE', 'IDENTICAL'):
                t['observed_status'] = t['status']; t['status'] = 'UNKNOWN'; t['reason'] = 'Unexpected test ID'
    for cell in matrix:
        # Both destinations depend on every mandatory build, including its target ABI.
        relevant = [e for e in expected if e['compiler'] == cell['compiler'] and (e['kind'] == 'build' or e['destination_image'] == cell['image'])]
        required = [check(e['id'], e['status'], e['evidence'], e['reason'], e['verification'] != 'NOT_EXECUTED') for e in relevant]
        for c, e in zip(required, relevant): c['verification'] = e['verification']
        bad = [ident for ident in unexpected if any(t.get('compiler') == cell['compiler'] and t.get('image') == cell['image'] for t in actual[ident])]
        if bad:
            c = check('unexpected IDs', combined(t['status'] for ident in bad for t in actual[ident]), reason=', '.join(bad), executed=True)
            c['verification'] = 'PARTIAL'
            required.append(c)
        if cell.get('status') == 'INCOMPATIBLE' and not relevant:
            c = check('recorded failure without expected plan', 'INCOMPATIBLE', reason='Prior failure retained; mandatory checks cannot be reconstructed')
            c['verification'] = 'PARTIAL'; required.append(c)
        if not required: required = [check('expected tests', reason='No mandatory tests identified')]
        u = obligation(cell['compiler'] + ':' + cell['image'], required)
        cell.update(status=u['status'], verification=u['verification'], required_checks=required,
                    expected_test_ids=[e['id'] for e in relevant], missing_test_ids=[e['id'] for e in relevant if not actual.get(e['id'], [])],
                    duplicate_test_ids=[e['id'] for e in relevant if len(actual.get(e['id'], [])) > 1], unexpected_test_ids=bad)
        for kind, field in (('header', 'header_status'), ('runtime', 'runtime_status')):
            group = [e for e in relevant if e['kind'] == kind]
            cell[field] = combined(e['status'] for e in group)
        cell['behavior_status'] = cell['runtime_status']
        for stage, field in (('compilation', 'compile_status'), ('linking', 'link_status'),
                             ('deployment', 'deployment_status'), ('execution', 'execution_status')):
            applicable = [e['actual_stage_results'].get(stage) for e in relevant if stage in e['required_stages']]
            cell[field] = 'SUCCESS' if applicable and all(v in ('COMPATIBLE', 'IDENTICAL') for v in applicable) else 'UNKNOWN'
    return {'missing': sorted(expected_ids - set(actual)), 'duplicates': sorted(i for i, ts in actual.items() if len(ts) > 1), 'unexpected': unexpected}
