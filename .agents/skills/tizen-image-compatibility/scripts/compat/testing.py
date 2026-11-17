"""SDK-based compile matrix and opt-in target-adapter execution."""
from __future__ import annotations

from pathlib import Path
import re
import json
from typing import Any
from .core import Tools, finding, hash_file, InputError, write_json, digest, canonical
from .images import Image
from .elf import collect_elf, target_abi_matches, verify_compile_target
from .semantic import semantic_probe, compare_semantics
from .matrix_manifest import prepare_sdks, plan_expected, reconcile

ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'probes'


def run_matrix(manifests: tuple[dict[str, Any], dict[str, Any]], roots: tuple[Any, Any],
               tools: Tools, mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    config = tools.config
    cc = config['cross_compilation']
    rt = config['runtime']
    tests: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    matrix = []
    built: dict[tuple[str, str], dict[str, Any]] = {}
    build_dir = tools.output / 'build'
    build_dir.mkdir(exist_ok=True)
    tools.aliases[str(build_dir)] = '<build>'
    sdks = prepare_sdks(manifests, tools)
    expected = plan_expected(manifests, tools, ASSETS)
    write_json(tools.output / 'expected-tests.json', expected)
    planned = {(e['legacy_id'], e['image'], 'runtime' if e['kind'] == 'runtime' else 'compile'): e for e in expected}
    def record(test: dict[str, Any]) -> None:
        test['logical_id'] = test['id']
        plan = planned.get((test['id'], test['image'], test['kind']))
        if plan:
            test['id'] = plan['id']
        elif test.get('name') is None:
            test['kind'] = 'diagnostic'
            test['id'] = 'DIAG-' + digest(canonical([test['id'], test['image']]).encode())[:24]
        else:
            test['id'] = 'UNEXPECTED-' + digest(canonical([test['id'], test['image']]).encode())[:24]
        tests.append(test)
        image_index = 0 if test['image'] == 'baseline' else 1
        manifests[image_index]['test_results'].append(test)
    for compiler in ('gcc', 'clang'):
        spec = cc['compilers'].get(compiler, {})
        build = cc['builds'].get(compiler, {})
        build_image = build.get('sdk')
        for image_idx, label in enumerate(('baseline', 'candidate')):
            manifest = manifests[image_idx]
            sysroot = cc['sysroots'].get(label)
            cell: dict[str, Any] = {'compiler': compiler, 'image': label, 'header_status': 'UNKNOWN', 'runtime_status': 'UNKNOWN', 'status': 'UNKNOWN'}
            cell.update(build_sdk=build_image, build_provenance=build.get('provenance'), reference_image=build.get('reference_image'),
                        compile_status='UNKNOWN', deployment_status='UNKNOWN', execution_status='UNKNOWN', behavior_status='UNKNOWN')
            matrix.append(cell)
            if mode not in ('full', 'runtime') or not cc['enabled'] or not sysroot or not roots:
                cell['reason'] = 'Compilation not requested, or explicit SDK/sysroot unavailable.'
                continue
            sysroot_path = Path(sysroot).resolve()
            if not sysroot_path.is_dir():
                cell['reason'] = 'Configured sysroot does not exist.'
                continue
            tools.aliases[str(sysroot_path)] = f'<{label}-sysroot>'
            sdk = sdks[label]
            sdk_headers = manifest['sdk_headers']
            headers = sdk_headers[:int(cc['header_limit'])] if 'headers' in config['analysis']['modes'] else []
            if len(headers) < len(sdk_headers):
                findings.append(finding('headers', label, compiler + ':header coverage', len(sdk_headers), len(headers),
                    'UNKNOWN', 'INFO', impact='Only configured header_limit headers were probed; increase it for full coverage.'))
            for language in ('c', 'cpp'):
                if not cc[language + '_tests']:
                    continue
                binary = spec.get(language)
                if not binary or not Path(binary).is_file():
                    record({'id': compiler + ':' + language + ':compiler', 'image': label, 'compiler': compiler, 'kind': 'compile',
                        'status': 'UNKNOWN', 'reason': 'Explicit compiler path unavailable; host default is not substituted.'})
                    continue
                version = tools.run([binary, '--version'])
                flags = list(spec.get('flags', []))
                if spec.get('target') and compiler == 'clang':
                    flags += ['--target=' + spec['target']]
                base = [binary, '--sysroot=' + str(sysroot_path), *flags]
                include_flags = []
                for directory in cc['include_dirs']:
                    inc = sdk.resolve('/' + directory)
                    if inc:
                        include_flags += ['-I', str(inc)]
                # Compile target object first; compare its ELF ABI with the actual image.
                extension = '.c' if language == 'c' else '.cpp'
                target_source = build_dir / f'{compiler}-{label}-{language}-target{extension}'
                target_source.write_text('double tizen_compat_target(double a) { return a + 1.0; }\n')
                target_object = target_source.with_suffix('.o')
                target = tools.run([*base, '-c', str(target_source), '-o', str(target_object)])
                target_ok = False
                target_verification = {'status': 'UNKNOWN', 'reason': 'Target compilation unavailable'}
                if target['returncode'] == 0 and target_object.exists():
                    elf = collect_elf(target_object, target_object.name, tools, 'quick')
                    macro_result = tools.run([*base, '-dM', '-E', str(target_source)])
                    compiler_macros = macro_result['stdout']
                    if elf.get('machine') == 'ARM' and not elf.get('arm_abi', {}).get('float') and macro_result['returncode'] == 0:
                        if '#define __ARM_PCS_VFP ' in compiler_macros:
                            elf['arm_abi']['float'] = 'hard'
                        elif '#define __ARM_PCS ' in compiler_macros:
                            elf['arm_abi']['float'] = 'soft'
                    if elf.get('machine') == 'ARM':
                        elf['arm_abi']['pcs'] = 'vfp' if elf['arm_abi'].get('float') == 'hard' else 'base' if elf['arm_abi'].get('float') == 'soft' else None
                        elf['arm_abi']['float_codegen'] = 'hard' if '#define __ARM_PCS_VFP ' in compiler_macros else 'soft' if '#define __SOFTFP__ ' in compiler_macros else 'softfp' if '#define __ARM_FP ' in compiler_macros else 'unknown'
                    target_verification = verify_compile_target(elf, manifest, config, label)
                    target_ok = target_verification['status'] == 'COMPATIBLE'
                    for mixed in target_verification['other_objects']:
                        findings.append(finding('elf', mixed['path'], 'mixed/missing target ABI', target_verification['source'], mixed,
                            mixed['status'], 'HIGH' if mixed['status'] == 'INCOMPATIBLE' else 'INFO', 'selected target ABI comparison'))
                if not target_ok:
                    record({'id': compiler + ':' + language + ':target', 'image': label, 'compiler': compiler,
                        'kind': 'compile', 'status': 'UNKNOWN', 'reason': 'Compiler target ABI could not be matched to authoritative evidence.', 'target_abi_verification': target_verification,
                        'evidence': [target['stdout_evidence'], target['stderr_evidence']]})
                    continue
                probes: list[tuple[str, Path, list[str], bool]] = []
                for i, header in enumerate(headers):
                    if language == 'c' and Path(header['path']).suffix != '.h':
                        continue
                    # Resolve in the virtual image namespace, never use a host-root symlink.
                    hp = sdk.resolve(header['path'])
                    if not hp:
                        record({'id': compiler + ':' + language + ':header:' + header['path'], 'name': 'header:' + header['path'],
                                'image': label, 'compiler': compiler, 'kind': 'compile', 'status': 'UNKNOWN', 'success': False,
                                'diagnostics': 'Header unavailable in the configured SDK', 'evidence': []})
                        continue
                    src = build_dir / f'{compiler}-{label}-{language}-header-{i}{extension}'
                    escaped = str(hp).replace('\\', '\\\\').replace('"', '\\"')
                    src.write_text(f'#include "{escaped}"\n')
                    probes.append(('header:' + header['path'], src, [], False))
                if label == build_image:
                    probes.append((language + '-behavior', ASSETS / ('behavior' + extension), ['-pthread', '-ldl', '-lm'], True))
                    for probe in cc['probes']:
                        if probe['language'] == language:
                            probes.append((probe['name'], Path(probe['source']).resolve(), probe.get('flags', []), True))
                for number, (name, source, extra, link) in enumerate(probes):
                    planned_test = planned.get((compiler + ':' + language + ':' + name, label, 'compile'))
                    artifact = tools.output / planned_test['expected_artifact'] if link and planned_test else build_dir / f'{compiler}-{label}-{language}-{number}.bin'
                    argv = [*base, *include_flags, '-UNDEBUG', '-std=c11' if language == 'c' else '-std=c++17',
                            str(source), *extra, '-o', str(artifact)] if link else [*base, *include_flags, '-fsyntax-only', str(source)]
                    result = tools.run(argv)
                    success = result['returncode'] == 0 and (not link or artifact.exists())
                    status = 'COMPATIBLE' if success else 'UNKNOWN'
                    test = {'id': compiler + ':' + language + ':' + name, 'name': name, 'language': language, 'image': label,
                        'compiler': compiler, 'kind': 'compile', 'status': status, 'success': success,
                        'compiler_version': version['stdout'].splitlines()[:1], 'argv': result['argv'],
                        'sdk': str(sysroot_path), 'header_origin': 'sdk', 'target_abi': elf,
                        'target_abi_verification': target_verification,
                        'artifact_path': str(artifact.relative_to(tools.output)) if link else None,
                        'artifact_sha256': hash_file(artifact) if success and link else None,
                        'compiler_macros_evidence': macro_result['stdout_evidence'],
                        'build_provenance': build.get('provenance'), 'reference_image': build.get('reference_image'),
                        'compile_status': 'SUCCESS' if success else 'FAILED',
                        'returncode': result['returncode'], 'diagnostics': result['stderr'],
                        'evidence': [result['stdout_evidence'], result['stderr_evidence']],
                        'reason': '' if success else 'Compile failure requires baseline/SDK context; not automatically a header incompatibility.'}
                    if success and not link and cc['semantic_headers'] and compiler == 'clang':
                        test['semantic'] = semantic_probe(base + include_flags, source, tools)
                    record(test)
                    if success and link and build.get('reference_image'):
                        built[(compiler, name)] = {'path': artifact, 'sha256': hash_file(artifact), 'sdk': label,
                                                  'reference_image': build['reference_image'], 'provenance': build['provenance']}
            header_tests = [t for t in tests if t['image'] == label and t['compiler'] == compiler and t.get('name', '').startswith('header:')]
            if len(headers) == len(sdk_headers) and header_tests and all(t['status'] == 'COMPATIBLE' for t in header_tests) and not any(t['status'] == 'UNKNOWN' for t in tests if t['image'] == label and t['compiler'] == compiler and t.get('name') is None):
                cell['header_status'] = 'COMPATIBLE'
            cell['reason'] = 'Header compilation is separate from binary execution.'
    # Only conclude regression when the exact compiler/probe succeeds on baseline headers.
    old = {t['logical_id']: t for t in tests if t['image'] == 'baseline'}
    for test in list(tests):
        baseline = old.get(test['logical_id'])
        if test.get('name', '').startswith('header:'):
            test['native_reference_valid'] = bool(baseline and baseline.get('success'))
        if test['image'] == 'candidate' and test.get('name', '').startswith('header:'):
            if not baseline or not baseline.get('success'):
                test['status'] = 'UNKNOWN'
                for cell in matrix:
                    if cell['compiler'] == test['compiler'] and cell['image'] == 'candidate':
                        cell['header_status'] = 'UNKNOWN'
            if test.get('semantic') and baseline and baseline.get('semantic'):
                findings.append(compare_semantics(baseline, test))
        if test['image'] == 'candidate' and test.get('name', '').startswith('header:') and baseline and baseline.get('success') and test.get('success') is False:
            findings.append(finding('headers', test['name'], test['compiler'], 'compiles', test['diagnostics'], 'INCOMPATIBLE', 'HIGH',
                'same-compiler cross-image header compilation', test['evidence'],
                'Baseline header probe passes while candidate probe fails under the configured SDKs; verify SDK equivalence before attributing cause.'))
            test['status'] = 'INCOMPATIBLE'
            for cell in matrix:
                if cell['compiler'] == test['compiler'] and cell['image'] == 'candidate':
                    cell['header_status'] = 'INCOMPATIBLE'
    execution = mode in ('full', 'runtime') and 'runtime' in config['analysis']['modes'] and rt['enabled'] and rt['authorized']
    for cell in matrix:
        compiler, label = cell['compiler'], cell['image']
        environment = rt['environments'].get(label)
        if not execution or not environment:
            cell['runtime_reason'] = 'Runtime environment missing or execution not explicitly enabled and authorized.'
            continue
        for (built_by, name), artifact in sorted(built.items()):
            if built_by != compiler:
                continue
            result = run_target(environment, artifact['path'], [], label, roots[0 if label == 'baseline' else 1], tools)
            record({'id': compiler + ':' + name + ':execution', 'name': name, 'image': label, 'compiler': compiler,
                'kind': 'runtime', 'status': 'UNKNOWN', 'returncode': result['returncode'],
                'reference_image': artifact['reference_image'], 'build_sdk': artifact['sdk'], 'build_provenance': artifact['provenance'],
                'artifact_sha256': artifact['sha256'], 'receipt_sha256': result.get('receipt_sha256'), 'compile_status': 'SUCCESS', **result['stages'], 'stdout': result['stdout'],
                'stderr': result['stderr'], 'environment_id': environment['id'],
                'evidence': [result['stdout_evidence'], result['stderr_evidence']]})
    if execution and roots:
        for label, image in zip(('baseline', 'candidate'), roots):
            env = rt['environments'].get(label)
            if env:
                for probe in rt['probes']:
                    result = run_target(env, Path(probe['argv'][0]), probe['argv'][1:], label, image, tools)
                    record({'id': 'custom:' + probe['name'], 'name': probe['name'], 'image': label, 'compiler': 'custom',
                        'kind': 'runtime', 'dimension': probe['dimension'], 'receipt_sha256': result.get('receipt_sha256'), 'expected_artifact_sha256': result.get('expected_artifact_sha256'), 'status': 'UNKNOWN', 'reference_image': 'baseline', **result['stages'],
                        'returncode': result['returncode'], 'stdout': result['stdout'], 'stderr': result['stderr'],
                        'expected_exit': probe.get('expected_exit', 0), 'expected_stdout': probe.get('expected_stdout'),
                        'evidence': [result['stdout_evidence'], result['stderr_evidence']]})
    reference_tests = {(t['logical_id'], t['image']): t for t in tests if t['kind'] == 'runtime'}
    for test in tests:
        if test['kind'] != 'runtime':
            continue
        reference = reference_tests.get((test['logical_id'], test.get('reference_image', 'baseline')))
        if not reference or any(t.get(k) != 'SUCCESS' for t in (reference, test) for k in ('deployment_status', 'execution_status')):
            continue
        if not reference or reference['returncode'] != reference.get('expected_exit', 0):
            continue
        if reference.get('expected_stdout') is not None and reference['stdout'] != reference['expected_stdout']:
            continue
        test['native_reference_valid'] = True
        if test['returncode'] < 0 or test['returncode'] in (124, 125, 126, 127):
            test['status'] = 'UNKNOWN'
        else:
            test['status'] = 'COMPATIBLE' if all(test[k] == reference[k] for k in ('returncode', 'stdout', 'stderr')) else 'INCOMPATIBLE'
        test['behavior_status'] = test['status']
        findings.append(finding(test.get('dimension', 'runtime'), test['name'], test['compiler'] + ':' + test['image'],
            {k: reference[k] for k in ('returncode', 'stdout', 'stderr')}, {k: test[k] for k in ('returncode', 'stdout', 'stderr')},
            test['status'], 'HIGH' if test['status'] == 'INCOMPATIBLE' else 'INFO', 'authorized target adapter', test['evidence']))
    audit = reconcile(expected, tests, matrix)
    for label, manifest in zip(('baseline', 'candidate'), manifests):
        manifest['expected_tests'] = [e for e in expected if e['image'] == label or (e['image'] is None and label == 'baseline')]
        manifest['test_manifest_audit'] = audit
    write_json(tools.output / 'expected-tests-results.json', expected)
    return tests, matrix, findings


def run_target(environment: dict[str, Any], binary: Path, args: list[str], label: str, image: Any, tools: Tools) -> dict[str, Any]:
    values = {'binary': str(binary), 'image': label, 'rootfs': str(image.root)}
    runner = [re.sub(r'\{(binary|image|rootfs)\}', lambda m: values[m[1]], token) for token in environment['runner']]
    executable = Path(runner[0]).resolve()
    if (executable == binary.resolve() or executable.is_relative_to(image.root.resolve())
            or executable.is_relative_to((tools.output / 'build').resolve())):
        raise InputError('Runtime runner must be an external isolation adapter; direct target execution is forbidden')
    result = tools.run([*runner, *args], timeout=tools.config['runtime']['timeout_seconds'])
    result['stages'] = {'deployment_status': 'UNKNOWN', 'execution_status': 'UNKNOWN', 'behavior_status': 'UNKNOWN'}
    # An adapter process exiting zero alone does not prove deployment or target execution.
    try:
        receipt = json.loads(result['stdout'])
        source = binary if binary.is_file() and binary.is_relative_to(tools.output) else image.resolve(str(binary))
        result['expected_artifact_sha256'] = hash_file(source) if source and source.is_file() else None
        result['receipt_sha256'] = receipt.get('binary_sha256') if isinstance(receipt, dict) else None
        valid = (result['returncode'] == 0 and not result['stdout_truncated'] and isinstance(receipt, dict)
                 and receipt.get('schema') == 'tizen-compat-runner/v1' and receipt.get('environment_id') == environment['id']
                 and source and source.is_file() and receipt.get('binary_sha256') == hash_file(source))
        if valid and receipt.get('deployment') == 'ok':
            result['stages']['deployment_status'] = 'SUCCESS'
            if (receipt.get('execution') == 'ok' and type(receipt.get('returncode')) is int
                    and isinstance(receipt.get('stdout'), str) and isinstance(receipt.get('stderr'), str)):
                result['stages']['execution_status'] = 'SUCCESS'
                result.update({k: receipt[k] for k in ('returncode', 'stdout', 'stderr')})
    except (ValueError, TypeError, OSError):
        pass
    return result
