#!/usr/bin/env python3
"""Plan or submit Phase 8E's frozen SR artifacts to an enrolled external adapter."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
from types import SimpleNamespace
from uuid import uuid4

from compat.core import DEFAULTS, InputError, Tools, canonical, digest, hash_file
from compat.testing import execute_target


REFERENCES = {'vd': 'gcc', 'llvm': 'clang'}
PROBES = {'A-C', 'B-CPP'}
BUILD_IDS = {f'{side}-{probe}' for side in REFERENCES for probe in PROBES}
RESERVED_EXIT_CODES = {124, 125, 126, 127, 137, 143}


def require(condition, message):
    if not condition:
        raise InputError(message)


def sha256(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def read_json(path):
    return json.loads(path.read_bytes())


def load_bundle(manifest_path, manifest_sha, bundle):
    raw = manifest_path.read_bytes()
    require(sha256(manifest_sha) and digest(raw) == manifest_sha, 'Manifest SHA256 mismatch')
    manifest = json.loads(raw)
    require(manifest['schema'] == 'tizen-compat-frozen-artifacts/v1', 'Unsupported frozen manifest')
    images = manifest['reference_images']
    require(set(images) == set(REFERENCES), 'VD and LLVM reference images are required')
    for side, family in REFERENCES.items():
        image = images[side]
        require(image['tool_family'] == family and sha256(image['image']['published_sha256'])
                and image['target_triple'] == 'armv7l-tizen-linux-gnueabi'
                and sha256(image['sdk_package_lock_sha256'])
                and isinstance(image['sdk_base_snapshot'], str) and image['sdk_base_snapshot'],
                f'Invalid reference image for {side}')

    artifacts, paths = {}, set()
    for artifact in manifest['artifacts']:
        ident, name, side = (artifact[key] for key in ('artifact_id', 'bundle_path', 'native_reference'))
        relative = Path(name)
        path = bundle / relative
        require(side in REFERENCES and not relative.is_absolute() and relative.parts
                and '..' not in relative.parts and relative.as_posix() == name and path == path.resolve()
                and path.is_file() and name not in paths and ident not in artifacts,
                f'Invalid or duplicate frozen artifact {ident}')
        paths.add(name)
        require(type(artifact['bytes']) is int and artifact['bytes'] > 0
                and path.stat().st_size == artifact['bytes'] and sha256(artifact['sha256'])
                and hash_file(path) == artifact['sha256'], f'Artifact SHA256 or size mismatch for {ident}')
        build, elf = artifact['build'], artifact['elf']
        compiler = build['compile_argv'][0]
        require(build['link_argv'][0] == compiler and sha256(images[side]['host_binary_sha256'].get(compiler))
                and elf['machine'] == 'ARM' and elf['class'] == 'ELF32'
                and type(elf['eabi']) is int and elf['eabi'] == 5 and elf['pcs'] == 'base',
                f'Build and native reference do not agree for {ident}')
        artifacts[ident] = artifact
    selected = {ident: a for ident, a in artifacts.items() if a['purpose'] == 'four_quadrant_base'}
    require(set(selected) == BUILD_IDS, 'Expected the four VD/LLVM base C/C++ builds')
    for ident, a in selected.items():
        side, _, probe = ident.partition('-')
        compiler = a['build']['compile_argv'][0]
        role = 'exec' if side == 'vd' else 'pie'
        suffix = {'vd': ('gcc', 'g++'), 'llvm': ('clang', 'clang++')}[side][probe == 'B-CPP']
        expectation = a['runtime_expectation']
        require(a['native_reference'] == side and (Path(compiler).name == suffix or
                side == 'vd' and Path(compiler).name == f'armv7l-tizen-linux-gnueabi-{suffix}')
                and a['elf']['interpreter'] == '/lib/ld-linux.so.3' and a['elf']['role'] == role
                and expectation['argv'] == [] and type(expectation['exit_code']) is int
                and expectation['exit_code'] == 0 and isinstance(expectation['stdout'], str)
                and isinstance(expectation['stderr'], str), f'Invalid base probe contract for {ident}')

    plan, pairs, prior_ids = [], set(), set()
    for row in manifest['runtime_plan']:
        ident, side, prior = (row[key] for key in ('artifact_id', 'destination_image', 'phase8d_expected_id'))
        require(ident in selected and side in REFERENCES and (ident, side) not in pairs
                and isinstance(prior, str) and prior.startswith('ET-') and prior not in prior_ids
                and row['artifact_sha256'] == selected[ident]['sha256']
                and row['status'] == 'NOT_EXECUTED' and row['authorized_environment_id'] is None,
                'Invalid or duplicate historical plan row')
        pairs.add((ident, side))
        prior_ids.add(prior)
        plan.append({k: row[k] for k in ('artifact_id', 'destination_image', 'phase8d_expected_id', 'artifact_sha256')})
    require(len(pairs) == len(BUILD_IDS) * len(REFERENCES), 'Incomplete frozen runtime plan')
    return images, selected, plan


def overlaps(a, b):
    return a.is_relative_to(b) or b.is_relative_to(a)


def enroll(spec, images, bundle, output):
    require(spec['scope'] == 'SR_RUNTIME' and set(spec['targets']) == set(REFERENCES),
            'Separate SR Runtime enrollment is required for both images')
    timeout, targets = spec['timeout_seconds'], spec['targets']
    require(type(timeout) is int and 1 <= timeout <= 300, 'Timeout must be an integer from 1 to 300 seconds')
    roots = []
    for side, target in targets.items():
        root = Path(target['rootfs'])
        require(root.is_absolute() and root.is_dir() and not overlaps(root.resolve(), output)
                and not overlaps(root.resolve(), bundle), f'Invalid local reference root for {side}')
        roots.append(root.resolve())
        require(isinstance(target['id'], str) and re.fullmatch('[A-Za-z0-9_.-]{1,128}', target['id'])
                and sha256(target['target_identity_sha256'])
                and target['image_sha256'] == images[side]['image']['published_sha256'],
                f'Invalid enrolled image or environment identity for {side}')
    require(targets['vd']['id'] != targets['llvm']['id'] and not overlaps(*roots),
            'VD and LLVM require independent environments and reference roots')
    controller = Path(spec['controller'])
    require(controller.is_absolute() and controller.is_file() and os.access(controller, os.X_OK)
            and not any(overlaps(controller.resolve(), p) for p in (*roots, output, bundle))
            and sha256(spec['controller_sha256']) and hash_file(controller) == spec['controller_sha256'],
            'External adapter controller path or SHA256 is invalid')
    with controller.open('rb') as handle:
        header = handle.read(20)
    require(header.startswith(b'#!') or
            header[:4] == b'\x7fELF' and len(header) == 20 and
            int.from_bytes(header[18:20], 'little' if header[5] == 1 else 'big') not in (40, 183),
            'Adapter controller cannot be an ARM target executable')
    return controller.resolve(), timeout, targets


def snapshot(target):
    return {key: target[key] for key in ('id', 'image_sha256', 'target_identity_sha256')}


def write_report(output, report):
    pending = output / 'runtime.json.pending'
    pending.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    pending.replace(output / 'runtime.json')


def run_case(case, target, controller, binary, tools, timeout):
    run_id = uuid4().hex
    expected = case['artifact_sha256']
    binding = {'run_id': run_id, 'plan_id': case['plan_id'], 'target_identity_sha256': target['target_identity_sha256']}
    identity = ['--environment-id', target['id'], '--target-identity-sha256', target['target_identity_sha256'],
                '--image-sha256', target['image_sha256'], '--run-id', run_id, '--plan-id', case['plan_id']]
    adapter = {'id': target['id'], 'receipt_binding': binding,
               'runner': [str(controller), 'run', *identity, '--artifact', '{binary}', '--sha256', expected,
                          '--timeout-seconds', str(timeout)]}
    case.update(attempt_id=run_id, status='UNKNOWN', verification_status='NOT_VERIFIED',
                target_process_cleanup_status='NOT_VERIFIED')
    try:
        observed = execute_target(adapter, binary, [], case['destination_image'],
                                  SimpleNamespace(root=Path(target['rootfs'])), tools, expected=expected)
        case.update({key: observed[key] for key in ('stages', 'runtime_reason', 'runtime_evidence')})
        case['adapter_error'] = observed.get('adapter_error', '')
        case['adapter_returncode'] = observed.get('adapter_returncode')
        case['run_local_process_group_status'] = observed.get('local_process_group_status', 'NOT_VERIFIED')
        if case['stages']['execution_status'] == 'SUCCESS':
            case['observation'] = {'exit_code': observed['returncode'], 'stdout': observed['stdout'],
                                   'stderr': observed['stderr']}
    finally:
        cleanup = tools.run([str(controller), 'cleanup', *identity], timeout=min(15, timeout),
                            max_capture_bytes=1024 * 1024, keep_interrupt=True)
        case['cleanup_evidence'] = [cleanup[k] for k in ('stdout_evidence', 'stderr_evidence')]
        case['cleanup_error'] = cleanup['error']
        case['cleanup_local_process_group_status'] = cleanup['local_process_group_status']
        try:
            receipt = json.loads(cleanup['stdout'])
        except ValueError:
            receipt = {}
        accepted = (cleanup['returncode'] == 0 and not cleanup['error'] and not cleanup['stdout_truncated']
                    and isinstance(receipt, dict) and receipt.get('schema') == 'tizen-compat-runner-cleanup/v1'
                    and receipt.get('environment_id') == target['id'] and receipt.get('cleanup') == 'ok'
                    and all(receipt.get(key) == value for key, value in binding.items()))
        # Controller stdout acknowledges cleanup. Independent target proof has no enrolled source yet.
        case['cleanup_receipt_status'] = 'ACCEPTED' if accepted else 'UNCONFIRMED'
        case['cleanup_status'] = 'UNKNOWN'


def frozen_runtime(manifest, manifest_sha, bundle, output, *, enrollment=None, execute=False):
    bundle = bundle.resolve(strict=True)
    output = output.resolve()
    require(bundle.is_dir() and not overlaps(bundle, output) and not manifest.resolve().is_relative_to(output)
            and (enrollment is None or not enrollment.resolve().is_relative_to(output)),
            'Output must be a new directory separate from the frozen inputs')
    images, artifacts, plan = load_bundle(manifest, manifest_sha, bundle)
    spec = read_json(enrollment) if enrollment else None
    require(not execute or spec is not None and spec.get('enabled') is True and spec.get('authorized') is True,
            'Execution requires --execute and explicitly enabled and authorized enrollment')
    if spec is not None:
        controller, timeout, targets = enroll(spec, images, bundle, output)
    for row in plan:
        a = artifacts[row['artifact_id']]
        ref, side = a['native_reference'], row['destination_image']
        compiler = a['build']['compile_argv'][0]
        row.update(native_image=ref, status='NOT_EXECUTED', verification_status='NOT_EXECUTED',
                   plan_id=None, environment=None,
                   build_proof={'status': 'FROZEN_SHA256_VERIFIED', 'sdk': images[ref]['sdk_base_snapshot'],
                                'sdk_package_lock_sha256': images[ref]['sdk_package_lock_sha256'],
                                'native_image_sha256': images[ref]['image']['published_sha256'],
                                'compiler': compiler, 'compiler_sha256': images[ref]['host_binary_sha256'][compiler]})
        if spec is not None:
            row['environment'] = snapshot(targets[side])
            row['plan_id'] = 'FR-' + digest(canonical(['SR_RUNTIME', manifest_sha, row['artifact_id'],
                                                       row['artifact_sha256'], side, row['environment'],
                                                       snapshot(targets[ref]), spec['controller_sha256']]).encode())
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {'schema': 'tizen-compat-frozen-runtime/v1', 'scope': 'SR_RUNTIME',
              'manifest_sha256': manifest_sha, 'execution_requested': execute, 'cases': plan}
    write_report(output, report)
    if not execute:
        return 0

    stage = output / 'build'
    stage.mkdir()
    for ident, artifact in artifacts.items():
        binary = stage / ident
        shutil.copyfile(bundle / artifact['bundle_path'], binary)
        require(hash_file(binary) == artifact['sha256'], f'Staged artifact changed for {ident}')
        binary.chmod(0o444)
    config = deepcopy(DEFAULTS)
    config['runtime'].update(timeout_seconds=timeout, repetitions=1)
    tools = Tools(output, config)
    references = {}
    stop_reason = ''
    for case in sorted(plan, key=lambda row: row['destination_image'] != row['native_image']):
        ident, side = case['artifact_id'], case['destination_image']
        native = side == case['native_image']
        if stop_reason or (not native and ident not in references):
            case['runtime_reason'] = stop_reason or 'Successful native reference missing'
            continue
        require(hash_file(controller) == spec['controller_sha256'], 'Enrolled controller changed before execution')
        expectation = artifacts[ident]['runtime_expectation']
        expected = {k: expectation[k] for k in ('exit_code', 'stdout', 'stderr')} if native else references[ident]
        try:
            run_case(case, targets[side], controller, stage / ident, tools, timeout)
            observed = case.get('observation')
            behavior_observed = bool(observed and observed['exit_code'] not in RESERVED_EXIT_CODES)
            match = behavior_observed and observed == expected
            if behavior_observed:
                case['stages']['behavior_status'] = 'SUCCESS' if match else 'MISMATCH'
            local = (case['run_local_process_group_status'], case['cleanup_local_process_group_status'])
            if 'interrupted' in (case['adapter_error'], case['cleanup_error']):
                stop_reason = 'Execution interrupted'
            elif case['cleanup_receipt_status'] != 'ACCEPTED' or local != ('VERIFIED', 'VERIFIED'):
                stop_reason = 'Cleanup receipt or local process group could not be verified'
            elif case['target_process_cleanup_status'] != 'VERIFIED':
                stop_reason = 'Independent target process exit was not verified'
            else:
                case['cleanup_status'] = 'SUCCESS'
            if stop_reason:
                case['runtime_reason'] = stop_reason
            elif behavior_observed:
                case['status'] = 'COMPATIBLE' if match else ('UNKNOWN' if native else 'INCOMPATIBLE')
                case['verification_status'] = 'NOT_VERIFIED' if case['status'] == 'UNKNOWN' else 'VERIFIED'
                if native and match:
                    references[ident] = observed
                elif not match:
                    case['runtime_reason'] = 'Observed behavior differs from the ' + ('frozen expectation' if native else 'native reference')
            elif observed:
                case['runtime_reason'] = 'Reserved infrastructure exit code'
        finally:
            write_report(output, report)
            tools.flush()
    write_report(output, report)
    if stop_reason == 'Execution interrupted':
        return 130
    if any(row['status'] in ('UNKNOWN', 'NOT_EXECUTED') for row in plan):
        return 3
    return int(any(row['status'] == 'INCOMPATIBLE' for row in plan))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'bundle', 'output', 'enrollment'):
        parser.add_argument(f'--{key}', type=Path, required=key != 'enrollment')
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        return frozen_runtime(args.manifest, args.manifest_sha256, args.bundle, args.output,
                              enrollment=args.enrollment, execute=args.execute)
    except (InputError, OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        parser.exit(2, f'Frozen runtime input error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
