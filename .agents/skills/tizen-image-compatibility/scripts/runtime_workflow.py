#!/usr/bin/env python3
"""Build reviewed probes, run a pinned plan, or render a unified Tizen report."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from compat.core import DEFAULTS, InputError, Tools, hash_file, write_json
from compat import probe_bundle, runtime_build, runtime_plan, runtime_summary
from compat.sdb_runtime import PHASE8E_MANIFEST_SHA256, SdbTransport, handle, validate_enrollment
from frozen_runtime import load_bundle, overlaps
from tizen_compat import main as static_main


def input_paths(config):
    for field in ('sources', 'build_reports', 'runtime_reports'):
        yield from config.get(field, [])
    for field in ('expected_runtime_plan', 'reviewed_runtime_attempts'):
        if field in config:
            yield config[field]['path']
    for sdk in config.get('sdk', {}).values():
        for field in ('host', 'sysroot', 'startfiles', 'lock'):
            yield sdk[field]
    for group in config.get('runs', []):
        for field in ('manifest', 'bundle', 'enrollment'):
            yield group[field]
    if config.get('static_report'):
        yield config['static_report']['directory']
    if config.get('static_analysis'):
        for field, value in config['static_analysis'].items():
            if field in ('baseline', 'candidate', 'baseline_manifest', 'candidate_manifest'):
                yield value


def prepare(config):
    schedule = []
    for group in config['runs']:
        manifest = Path(group['manifest']).resolve()
        supplied_bundle = Path(group['bundle'])
        bundle = supplied_bundle.resolve()
        enrollment = json.loads(Path(group['enrollment']).read_text())
        pin = group.get('manifest_sha256', PHASE8E_MANIFEST_SHA256)
        if pin != PHASE8E_MANIFEST_SHA256 and supplied_bundle.is_symlink():
            raise InputError('Bundle root cannot be a symbolic link')
        artifacts = (load_bundle(manifest, pin, bundle)[1] if pin == PHASE8E_MANIFEST_SHA256 else
                     probe_bundle.load(manifest, pin, bundle))
        target = {key:enrollment[key] for key in ('scope', 'build_id')}
        target.update(profile=target['build_id'].rsplit('_', 1)[-1], target_sha256=probe_bundle.target_pin(enrollment),
                      environment_id=group.get('environment_id'))
        for entry in group['artifacts']:
            selection = {'artifact_id':entry} if isinstance(entry, str) else entry
            artifact = artifacts[selection['artifact_id']] | {'manifest_sha256':pin}
            # The legacy entry must keep legacy authorization semantics.
            executable_artifact = artifacts[selection['artifact_id']]
            required, skip = selection.get('required', True), selection.get('skip_reason')
            validate_enrollment(enrollment, executable_artifact, False)
            repetitions = selection.get('repetitions', 1)
            if type(repetitions) is not int or not 1 <= repetitions <= 100:
                raise InputError('Expected between 1 and 100 Runtime repetitions')
            for iteration in range(1, repetitions+1):
                test = runtime_plan.expected_case(artifact, target, iteration, repetitions, required, skip)
                schedule.append((test, enrollment, executable_artifact, bundle))
    if not schedule:
        raise InputError('Select at least one probe')
    plan = {'schema':runtime_plan.PLAN, 'tests':[item[0] for item in schedule]}
    runtime_plan.validate_plan(plan)
    return plan, schedule


def run(config, output, *, admit, execute):
    if 'expected_runtime_plan' in config:
        raise InputError('Run generates its expected plan; use report to import a pinned plan')
    plan, schedule = prepare(config)
    write_json(output/'runtime-expected-plan.json', plan)
    output_config = config.copy()
    receipts = list(config.get('runtime_reports', []))
    live = {}
    exit_code = 0
    boots = {}
    if execute:
        try:
            for test, enrollment, artifact, _ in schedule:
                if not test['skip_reason']:
                    validate_enrollment(enrollment, artifact, True)
        except InputError as error:
            output_config['runtime_run_note'] = f'Execution preflight blocked {test["test_id"]}: {error}'
            exit_code = 3
    if not exit_code and config.get('static_analysis'):
        if config.get('static_report'):
            raise InputError('Choose existing static report or fresh static analysis')
        static = config['static_analysis']
        flags = ('baseline_manifest','candidate_manifest') if 'baseline_manifest' in static else ('baseline','candidate')
        static_out = output/'static-analysis'
        argv = [item for key in flags for item in ('--'+key.replace('_','-'),static[key])]
        status = static_main([*argv,'--mode','static','--output',str(static_out)])
        write_json(output/'static-execution.json',{'exit_code':status,'scope':static['scope']})
        if status not in (0,1) or not (static_out/'results.json').is_file():
            exit_code = 3
            output_config['runtime_run_note'] = 'Static collection did not produce a usable report'
        else:
            output_config['static_report'] = {'directory':str(static_out),'scope':static['scope']}
    executable = shutil.which('sdb') if admit or execute else None
    if not exit_code and (admit or execute) and not executable:
        exit_code = 3
        output_config['runtime_run_note'] = 'SDB is unavailable'
    if not exit_code:
        try:
            for index, (test, enrollment, artifact, bundle) in enumerate(schedule, 1):
                if test['skip_reason']:
                    continue
                target = output/f'{index:02}-{artifact["artifact_id"]}'
                target.mkdir(mode=0o700)
                tools = Tools(target,DEFAULTS)
                try:
                    rc = handle(SdbTransport(tools,executable,enrollment['sdb_serial']),enrollment,artifact,
                                bundle/artifact['bundle_path'],target,read_device=admit,execute=execute,
                                expected_boot=boots.get(enrollment['sdb_serial']),
                                expected_environment=test['target']['environment_id'], test_id=test['test_id'])
                finally:
                    path = target/'runtime.json'
                    if path.is_file():
                        receipts.append(str(path))
                        live[hash_file(path)] = test['test_id']
                    tools.flush()
                record = json.loads(path.read_text())
                if record.get('boot_id'):
                    boots[enrollment['sdb_serial']] = record['boot_id']
                exit_code = exit_code or rc
                if rc and (not config.get('continue_after_verified_cleanup') or
                           record['target_cleanup_status'] != 'VERIFIED' or rc == 130):
                    output_config['runtime_run_note'] = 'Execution stopped after '+test['test_id']
                    if rc == 130:
                        exit_code = rc
                    break
        except KeyboardInterrupt:
            exit_code = 130
            output_config['runtime_run_note'] = 'Execution interrupted'
    runtime_summary.collect(output_config | {'runtime_reports':receipts},output,plan=plan,live_attempts=live)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('build','run','report'))
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute',action='store_true')
    mode.add_argument('--admit',action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        config = json.loads(args.config.read_text())
        if args.phase!='run' and (args.execute or args.admit):
            raise InputError('Device flags apply only to run')
        if any(overlaps(output, Path(path).resolve()) for path in (args.config, *input_paths(config))):
            raise InputError('Output must be separate from workflow inputs and existing evidence')
        output.mkdir(mode=0o700,parents=True,exist_ok=False)
        if args.phase == 'build':
            tools = Tools(output,DEFAULTS)
            try:
                manifest,pin,bundle = runtime_build.build_bundle(config,output,tools)
                write_json(output/'build-result.json',{'manifest':str(manifest),'sha256':pin,'bundle':str(bundle)})
                return 0
            finally:
                tools.flush()
        if args.phase == 'report':
            runtime_summary.collect(config,output)
            return 0
        return run(config, output, admit=args.admit, execute=args.execute)
    except (InputError,OSError,ValueError,KeyError,TypeError) as error:
        print(f'Tizen workflow error: {error}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
