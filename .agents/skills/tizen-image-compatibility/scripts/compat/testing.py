"""SDK-based compile matrix and opt-in target-adapter execution."""
from __future__ import annotations

from pathlib import Path
import re
import json
from typing import Any
from .core import Tools, finding, hash_file, InputError
from .images import Image
from .elf import collect_elf, target_abi_matches
from .semantic import semantic_probe, compare_semantics

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
    def record(test: dict[str, Any]) -> None:
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
            sdk = Image(sysroot_path, build_dir, tools, label + '-sdk')
            sdk_headers = []
            for directory in cc['include_dirs']:
                resolved = sdk.resolve('/' + directory)
                if resolved and resolved.is_dir():
                    for path in sorted(resolved.rglob('*')):
                        if path.suffix in ('.h', '.hpp', '.hh', '.hxx'):
                            virtual = '/' + directory.strip('/') + '/' + path.relative_to(resolved).as_posix()
                            hp = sdk.resolve(virtual)
                            if hp and hp.is_file():
                                sdk_headers.append({'path': virtual, 'origin': 'sdk', 'sdk': str(sysroot_path)})
            # Retain availability obligations for baseline image headers absent from the SDK.
            sdk_paths = {h['path'] for h in sdk_headers}
            sdk_headers += [dict(h, origin='sdk_missing') for h in manifest['public_headers'] if h['path'] not in sdk_paths]
            manifest['sdk_headers'] = sdk_headers
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
                if target['returncode'] == 0 and target_object.exists():
                    elf = collect_elf(target_object, target_object.name, tools, 'quick')
                    macro_result = tools.run([*base, '-dM', '-E', str(target_source)])
                    compiler_macros = macro_result['stdout']
                    if elf.get('machine') == 'ARM' and not elf.get('arm_abi', {}).get('float') and macro_result['returncode'] == 0:
                        if '#define __ARM_PCS_VFP ' in compiler_macros:
                            elf['arm_abi']['float'] = 'hard'
                        elif '#define __ARM_PCS ' in compiler_macros:
                            elf['arm_abi']['float'] = 'soft'
                    image_abis = [obj for obj in manifest['elf_objects'] if obj.get('complete') and not obj.get('type', '').startswith('REL')]
                    target_ok = bool(image_abis) and all(target_abi_matches(elf, obj) for obj in image_abis)
                if not target_ok:
                    record({'id': compiler + ':' + language + ':target', 'image': label, 'compiler': compiler,
                        'kind': 'compile', 'status': 'UNKNOWN', 'reason': 'Compiler target ABI could not be matched to image ELF metadata.',
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
                    artifact = build_dir / f'{compiler}-{label}-{language}-{number}.bin'
                    argv = [*base, *include_flags, '-UNDEBUG', '-std=c11' if language == 'c' else '-std=c++17',
                            str(source), *extra, '-o', str(artifact)] if link else [*base, *include_flags, '-fsyntax-only', str(source)]
                    result = tools.run(argv)
                    success = result['returncode'] == 0 and (not link or artifact.exists())
                    status = 'COMPATIBLE' if success else 'UNKNOWN'
                    test = {'id': compiler + ':' + language + ':' + name, 'name': name, 'language': language, 'image': label,
                        'compiler': compiler, 'kind': 'compile', 'status': status, 'success': success,
                        'compiler_version': version['stdout'].splitlines()[:1], 'argv': result['argv'],
                        'sdk': str(sysroot_path), 'header_origin': 'sdk', 'target_abi': elf,
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
    old = {t['id']: t for t in tests if t['image'] == 'baseline'}
    for test in list(tests):
        baseline = old.get(test['id'])
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
                'artifact_sha256': artifact['sha256'], 'compile_status': 'SUCCESS', **result['stages'], 'stdout': result['stdout'],
                'stderr': result['stderr'], 'environment_id': environment['id'],
                'evidence': [result['stdout_evidence'], result['stderr_evidence']]})
    if execution and roots:
        for label, image in zip(('baseline', 'candidate'), roots):
            env = rt['environments'].get(label)
            if env:
                for probe in rt['probes']:
                    result = run_target(env, Path(probe['argv'][0]), probe['argv'][1:], label, image, tools)
                    record({'id': 'custom:' + probe['name'], 'name': probe['name'], 'image': label, 'compiler': 'custom',
                        'kind': 'runtime', 'dimension': probe['dimension'], 'status': 'UNKNOWN', 'reference_image': 'baseline', **result['stages'],
                        'returncode': result['returncode'], 'stdout': result['stdout'], 'stderr': result['stderr'],
                        'expected_exit': probe.get('expected_exit', 0), 'expected_stdout': probe.get('expected_stdout'),
                        'evidence': [result['stdout_evidence'], result['stderr_evidence']]})
    reference_tests = {(t['id'], t['image']): t for t in tests if t['kind'] == 'runtime'}
    for test in tests:
        if test['kind'] != 'runtime':
            continue
        reference = reference_tests.get((test['id'], test.get('reference_image', 'baseline')))
        if not reference or any(t.get(k) != 'SUCCESS' for t in (reference, test) for k in ('deployment_status', 'execution_status')):
            continue
        if not reference or reference['returncode'] != reference.get('expected_exit', 0):
            continue
        if reference.get('expected_stdout') is not None and reference['stdout'] != reference['expected_stdout']:
            continue
        if test['returncode'] < 0 or test['returncode'] in (124, 125, 126, 127):
            test['status'] = 'UNKNOWN'
        else:
            test['status'] = 'COMPATIBLE' if all(test[k] == reference[k] for k in ('returncode', 'stdout', 'stderr')) else 'INCOMPATIBLE'
        test['behavior_status'] = test['status']
        findings.append(finding(test.get('dimension', 'runtime'), test['name'], test['compiler'] + ':' + test['image'],
            {k: reference[k] for k in ('returncode', 'stdout', 'stderr')}, {k: test[k] for k in ('returncode', 'stdout', 'stderr')},
            test['status'], 'HIGH' if test['status'] == 'INCOMPATIBLE' else 'INFO', 'authorized target adapter', test['evidence']))
    for cell in matrix:
        matched = [t for t in tests if t['kind'] == 'runtime' and t['image'] == cell['image'] and t['compiler'] == cell['compiler']]
        expected = sum(bool(cc[k + '_tests']) for k in ('c', 'cpp')) + len(cc['probes'])
        cell['compile_status'] = 'SUCCESS' if expected and sum(k[0] == cell['compiler'] for k in built) >= expected else 'UNKNOWN'
        if matched:
            for stage in ('deployment_status', 'execution_status'):
                cell[stage] = 'SUCCESS' if len(matched) >= expected and all(t.get(stage) == 'SUCCESS' for t in matched) else 'UNKNOWN'
            statuses = {t['status'] for t in matched}
            cell['runtime_status'] = 'INCOMPATIBLE' if 'INCOMPATIBLE' in statuses else 'COMPATIBLE' if statuses == {'COMPATIBLE'} and len(matched) >= expected else 'UNKNOWN'
        cell['behavior_status'] = cell['runtime_status']
        statuses = {cell['header_status'], cell['runtime_status']}
        cell['status'] = 'INCOMPATIBLE' if 'INCOMPATIBLE' in statuses else 'COMPATIBLE' if statuses == {'COMPATIBLE'} else 'UNKNOWN'
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
