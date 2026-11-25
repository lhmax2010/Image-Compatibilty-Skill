#!/usr/bin/env python3
"""Build reviewed probes, run a pinned plan, or render a unified Tizen report."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from compat.core import DEFAULTS, InputError, Tools, write_json
from compat import probe_bundle, runtime_build, runtime_summary
from compat.sdb_runtime import PHASE8E_MANIFEST_SHA256, SdbTransport, handle, validate_enrollment
from frozen_runtime import load_bundle, overlaps
from tizen_compat import main as static_main


def input_paths(config):
    for field in ('sources', 'build_reports', 'runtime_reports'):
        yield from config.get(field, [])
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('build','run','report'))
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--execute',action='store_true')
    mode.add_argument('--admit',action='store_true')
    args=parser.parse_args()
    output=args.output.resolve()
    tools=None
    try:
        config=json.loads(args.config.read_text())
        if args.phase!='run' and (args.execute or args.admit):
            raise InputError('Device flags apply only to run')
        if any(overlaps(output, Path(path).resolve()) for path in (args.config, *input_paths(config))):
            raise InputError('Output must be separate from workflow inputs and existing evidence')
        output.mkdir(mode=0o700,parents=True,exist_ok=False)
        if args.phase=='build':
            tools=Tools(output,DEFAULTS)
            manifest,pin,bundle=runtime_build.build_bundle(config,output,tools)
            write_json(output/'build-result.json',{'manifest':str(manifest),'sha256':pin,'bundle':str(bundle)})
            return 0
        if args.phase=='run' and config.get('static_analysis'):
            if config.get('static_report'):
                raise InputError('Choose existing static report or fresh static analysis')
            static=config['static_analysis']
            flags=('baseline_manifest','candidate_manifest') if 'baseline_manifest' in static else ('baseline','candidate')
            static_out=output/'static-analysis'
            argv=[item for key in flags for item in ('--'+key.replace('_','-'),static[key])]
            status=static_main([*argv,'--mode','static','--output',str(static_out)])
            write_json(output/'static-execution.json',{'exit_code':status,'scope':static['scope']})
            if status not in (0,1) or not (static_out/'results.json').is_file():
                raise InputError('Static collection did not produce a usable report')
            config['static_report']={'directory':str(static_out),'scope':static['scope']}
        if args.phase=='report':
            runtime_summary.collect(config,output)
            return 0

        plans=[]
        for group in config['runs']:
            manifest=Path(group['manifest']).resolve()
            supplied_bundle=Path(group['bundle'])
            bundle=supplied_bundle.resolve()
            if overlaps(output,bundle):
                raise InputError('Runtime output overlaps a frozen input')
            enrollment=json.loads(Path(group['enrollment']).read_text())
            pin=group.get('manifest_sha256',PHASE8E_MANIFEST_SHA256)
            if pin!=PHASE8E_MANIFEST_SHA256 and supplied_bundle.is_symlink():
                raise InputError('Bundle root cannot be a symbolic link')
            artifacts=(load_bundle(manifest,pin,bundle)[1] if pin==PHASE8E_MANIFEST_SHA256 else
                       probe_bundle.load(manifest,pin,bundle))
            for ident in group['artifacts']:
                artifact=artifacts[ident]
                validate_enrollment(enrollment,artifact,args.execute)
                plans.append((enrollment,artifact,bundle))
        if not plans:
            raise InputError('Select at least one probe')
        executable=shutil.which('sdb') if args.admit or args.execute else None
        if (args.admit or args.execute) and not executable:
            raise InputError('SDB is unavailable')
        reports=[]
        exit_code=0
        boots={}
        for i,(enrollment,artifact,bundle) in enumerate(plans,1):
            target=output/f'{i:02}-{artifact["artifact_id"]}'
            target.mkdir(mode=0o700)
            tools=Tools(target,DEFAULTS)
            try:
                rc=handle(SdbTransport(tools,executable,enrollment['sdb_serial']),enrollment,artifact,
                          bundle/artifact['bundle_path'],target,read_device=args.admit,execute=args.execute,
                          expected_boot=boots.get(enrollment['sdb_serial']))
            finally:
                tools.flush()
                tools=None
            reports.append(str(target/'runtime.json'))
            record=json.loads((target/'runtime.json').read_text())
            if record.get('boot_id'):
                boots[enrollment['sdb_serial']]=record['boot_id']
            if rc and (not config.get('continue_after_verified_cleanup') or
                       record['target_cleanup_status']!='VERIFIED' or rc==130):
                exit_code=rc
                break
            exit_code=exit_code or rc
        runtime_summary.collect(config | {'runtime_reports':[ *config.get('runtime_reports',[]), *reports]},output)
        return exit_code
    except (InputError,OSError,ValueError,KeyError,TypeError) as error:
        print(f'Tizen workflow error: {error}',file=sys.stderr)
        return 2
    finally:
        if tools:
            tools.flush()


if __name__=='__main__':
    raise SystemExit(main())
