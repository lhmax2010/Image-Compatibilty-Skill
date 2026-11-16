"""SDK-based compile matrix and opt-in target-adapter execution."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from .core import Tools, finding
from .elf import collect_elf

ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'probes'


def run_matrix(manifests: tuple[dict[str, Any], dict[str, Any]], roots: tuple[Any, Any],
               tools: Tools, mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    config = tools.config
    cc = config['cross_compilation']
    rt = config['runtime']
    tests: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    matrix = []
    built: dict[tuple[str, str], Path] = {}
    build_dir = tools.output / 'build'
    build_dir.mkdir(exist_ok=True)
    tools.aliases[str(build_dir)] = '<build>'
    def record(test: dict[str, Any]) -> None:
        tests.append(test)
        image_index = 0 if test['image'] == 'baseline' else 1
        manifests[image_index]['test_results'].append(test)
    for compiler in ('gcc', 'clang'):
        spec = cc['compilers'].get(compiler, {})
        build_image = 'baseline' if compiler == 'gcc' else 'candidate'
        for image_idx, label in enumerate(('baseline', 'candidate')):
            manifest = manifests[image_idx]
            sysroot = cc['sysroots'].get(label)
            cell: dict[str, Any] = {'compiler': compiler, 'image': label, 'header_status': 'UNKNOWN', 'runtime_status': 'UNKNOWN', 'status': 'UNKNOWN'}
            matrix.append(cell)
            if mode not in ('full', 'runtime') or not cc['enabled'] or not sysroot or not roots:
                cell['reason'] = 'Compilation not requested, or explicit SDK/sysroot unavailable.'
                continue
            sysroot_path = Path(sysroot).resolve()
            if not sysroot_path.is_dir():
                cell['reason'] = 'Configured sysroot does not exist.'
                continue
            tools.aliases[str(sysroot_path)] = f'<{label}-sysroot>'
            headers = manifest['public_headers'][:int(cc['header_limit'])] if 'headers' in config['analysis']['modes'] else []
            if len(headers) < len(manifest['public_headers']):
                findings.append(finding('headers', label, compiler + ':header coverage', len(manifest['public_headers']), len(headers),
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
                    inc = roots[image_idx].resolve('/' + directory)
                    if inc:
                        include_flags += ['-I', str(inc)]
                # Compile target object first; compare its ELF ABI with the actual image.
                extension = '.c' if language == 'c' else '.cpp'
                target_source = build_dir / f'{compiler}-{label}-{language}-target{extension}'
                target_source.write_text('int tizen_compat_target;\n')
                target_object = target_source.with_suffix('.o')
                target = tools.run([*base, '-c', str(target_source), '-o', str(target_object)])
                target_ok = False
                if target['returncode'] == 0 and target_object.exists():
                    elf = collect_elf(target_object, target_object.name, tools, 'quick')
                    target_ok = bool(manifest['elf_objects']) and any(
                        all(elf.get(k) == obj.get(k) and elf.get(k) is not None for k in ('class', 'endianness', 'machine'))
                        for obj in manifest['elf_objects'])
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
                    hp = roots[image_idx].resolve(header['path'])
                    if not hp:
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
                        'returncode': result['returncode'], 'diagnostics': result['stderr'],
                        'evidence': [result['stdout_evidence'], result['stderr_evidence']],
                        'reason': '' if success else 'Compile failure requires baseline/SDK context; not automatically a header incompatibility.'}
                    record(test)
                    if success and link:
                        built[(compiler, name)] = artifact
            header_tests = [t for t in tests if t['image'] == label and t['compiler'] == compiler and t.get('name', '').startswith('header:')]
            if header_tests and all(t['status'] == 'COMPATIBLE' for t in header_tests):
                cell['header_status'] = 'COMPATIBLE'
            cell['reason'] = 'Header compilation is separate from binary execution.'
    # Only conclude regression when the exact compiler/probe succeeds on baseline headers.
    old = {t['id']: t for t in tests if t['image'] == 'baseline'}
    for test in list(tests):
        baseline = old.get(test['id'])
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
            result = run_target(environment, artifact, [], label, roots[0 if label == 'baseline' else 1], tools)
            record({'id': compiler + ':' + name + ':execution', 'name': name, 'image': label, 'compiler': compiler,
                'kind': 'runtime', 'status': 'UNKNOWN', 'returncode': result['returncode'], 'stdout': result['stdout'],
                'stderr': result['stderr'], 'environment_id': environment['id'],
                'evidence': [result['stdout_evidence'], result['stderr_evidence']]})
    if execution and roots:
        for label, image in zip(('baseline', 'candidate'), roots):
            env = rt['environments'].get(label)
            if env:
                for probe in rt['probes']:
                    result = run_target(env, Path(probe['argv'][0]), probe['argv'][1:], label, image, tools)
                    record({'id': 'custom:' + probe['name'], 'name': probe['name'], 'image': label, 'compiler': 'custom',
                        'kind': 'runtime', 'dimension': probe['dimension'], 'status': 'UNKNOWN',
                        'returncode': result['returncode'], 'stdout': result['stdout'], 'stderr': result['stderr'],
                        'expected_exit': probe.get('expected_exit', 0), 'expected_stdout': probe.get('expected_stdout'),
                        'evidence': [result['stdout_evidence'], result['stderr_evidence']]})
    baseline_tests = {t['id']: t for t in tests if t['image'] == 'baseline' and t['kind'] == 'runtime'}
    for test in tests:
        if test['kind'] != 'runtime':
            continue
        reference = baseline_tests.get(test['id'])
        if not reference or reference['returncode'] != reference.get('expected_exit', 0):
            continue
        if reference.get('expected_stdout') is not None and reference['stdout'] != reference['expected_stdout']:
            continue
        if test['returncode'] < 0 or test['returncode'] in (124, 125, 126, 127):
            test['status'] = 'UNKNOWN'
        else:
            test['status'] = 'COMPATIBLE' if all(test[k] == reference[k] for k in ('returncode', 'stdout', 'stderr')) else 'INCOMPATIBLE'
        findings.append(finding(test.get('dimension', 'runtime'), test['name'], test['compiler'] + ':' + test['image'],
            {k: reference[k] for k in ('returncode', 'stdout', 'stderr')}, {k: test[k] for k in ('returncode', 'stdout', 'stderr')},
            test['status'], 'HIGH' if test['status'] == 'INCOMPATIBLE' else 'INFO', 'authorized target adapter', test['evidence']))
    for cell in matrix:
        matched = [t for t in tests if t['kind'] == 'runtime' and t['image'] == cell['image'] and t['compiler'] == cell['compiler']]
        expected = sum(bool(cc[k + '_tests']) for k in ('c', 'cpp')) + len(cc['probes'])
        if matched:
            statuses = {t['status'] for t in matched}
            cell['runtime_status'] = 'INCOMPATIBLE' if 'INCOMPATIBLE' in statuses else 'COMPATIBLE' if statuses == {'COMPATIBLE'} and len(matched) >= expected else 'UNKNOWN'
        statuses = {cell['header_status'], cell['runtime_status']}
        cell['status'] = 'INCOMPATIBLE' if 'INCOMPATIBLE' in statuses else 'COMPATIBLE' if statuses == {'COMPATIBLE'} else 'UNKNOWN'
    return tests, matrix, findings


def run_target(environment: dict[str, Any], binary: Path, args: list[str], label: str, image: Any, tools: Tools) -> dict[str, Any]:
    values = {'binary': str(binary), 'image': label, 'rootfs': str(image.root)}
    runner = [re.sub(r'\{(binary|image|rootfs)\}', lambda m: values[m[1]], token) for token in environment['runner']]
    return tools.run([*runner, *args], timeout=tools.config['runtime']['timeout_seconds'])
