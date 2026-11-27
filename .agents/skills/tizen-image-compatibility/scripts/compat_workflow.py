#!/usr/bin/env python3
"""Configuration-driven offline workflow for users and AI agents."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sys

from compat.core import InputError, load_config
from compat.flash import PROBE_BYTES, identify
from compat.preparation import looks_like_root
from compat.report_io import manifest_path
from compat.run_summary import OBJECTIVES, SCHEMA, blocked_summary, save
import tizen_compat


PATHS = ('baseline', 'candidate', 'baseline_manifest', 'candidate_manifest', 'output', 'engine_config',
         'cache', 'baseline_rpm_fallback', 'candidate_rpm_fallback', 'index_output')
KEYS = set(PATHS) | {'objective', 'rpm_mode', 'mode', 'same_build_confirmed'}
TOOLS = ('readelf', 'rpm', 'rpm2cpio', 'fsck.erofs', 'mkfs.erofs', 'bwrap', 'tar', 'unsquashfs')
MAX_JSON = 256 * 1024


def object_keys(pairs):
    data = dict(pairs)
    if len(pairs) != len(data):
        raise InputError('Duplicate configuration or summary key')
    return data


def read_json(path):
    if not path.is_file():
        raise InputError(f'File is missing or not regular: {path}')
    with path.open('rb') as stream:
        data = stream.read(MAX_JSON+1)
    if len(data) > MAX_JSON:
        raise InputError('Workflow configuration or summary exceeds 256 KiB')
    value = json.loads(data, object_pairs_hook=object_keys)
    if not isinstance(value, dict):
        raise InputError('Expected a JSON object')
    return value


def options(path):
    path = path.absolute()
    data = read_json(path)
    if unknown := set(data)-KEYS:
        raise InputError('Unknown workflow fields: '+', '.join(sorted(unknown)))
    for name in PATHS:
        if name in data:
            value = data[name]
            if not isinstance(value, str) or not value.strip() or '\0' in value:
                raise InputError(f'{name} must be a non-empty local path')
            data[name] = path.parent/Path(value).expanduser()
    if 'output' not in data:
        raise InputError('Set output to a new directory')
    image = {'baseline','candidate'}
    manifests = {'baseline_manifest','candidate_manifest'}
    sources = set(data)&(image|manifests)
    if sources not in (image,manifests):
        raise InputError('Supply a baseline/candidate pair or a baseline_manifest/candidate_manifest pair')
    fallbacks = set(data)&{'baseline_rpm_fallback','candidate_rpm_fallback'}
    confirmation = data.get('same_build_confirmed',False)
    if type(confirmation) is not bool:
        raise InputError('same_build_confirmed must be a boolean')
    if (fallbacks and (len(fallbacks)!=2 or sources!=image or not confirmation)) or (confirmation and not fallbacks):
        raise InputError('Supply both RPM fallback paths and same_build_confirmed=true after verifying the build identities')
    data.setdefault('objective','EXPORT_SYMBOLS')
    data.setdefault('rpm_mode','payload')
    data.setdefault('mode','static')
    if data['objective'] not in OBJECTIVES or data['rpm_mode'] not in ('payload','metadata'):
        raise InputError('Invalid objective or rpm_mode. See workflow --help and the configuration guide.')
    if data['mode'] not in ('quick','static'):
        raise InputError('The offline workflow supports quick/static. Use the explicit SDK or authorized Runtime CLI for other stages.')
    if data['objective']=='EXPORT_SYMBOLS' and data['rpm_mode']=='metadata':
        raise InputError('EXPORT_SYMBOLS needs rpm_mode=payload. Use PACKAGE_INVENTORY for metadata-only runs.')
    destinations = [data[k].resolve() for k in ('output','cache','index_output') if k in data]
    for pos, dest in enumerate(destinations):
        if any(dest.is_relative_to(other) or other.is_relative_to(dest) for other in destinations[:pos]):
            raise InputError('Report, cache and optional index must use separate, non-overlapping directories')
        for key in sources|fallbacks|({'engine_config'}&set(data)):
            source = data[key].resolve()
            if dest==source or (source.is_dir() and dest.is_relative_to(source)):
                raise InputError('Report, cache and index must be outside every source input')
            if key.endswith('_manifest') and dest.is_relative_to(source.parent):
                raise InputError('A reused manifest needs output/cache/index outside its historical report directory')
    return data


@contextmanager
def engine_directory(data):
    original = Path.cwd()
    try:
        if path := data.get('engine_config'):
            os.chdir(path.parent)
        yield
    finally:
        os.chdir(original)


def tool_state(config):
    return {name: bool(override and shutil.which(override)) for name in TOOLS
            if (override := config['tools'].get(name,name)) is not None}


def identify_input(path, manifest=False):
    if manifest:
        path = manifest_path(path)
    if not path.exists():
        return 'MISSING'
    if manifest:
        return 'MANIFEST' if path.is_file() else 'UNSUPPORTED'
    if path.is_file():
        with path.open('rb') as stream:
            prefix = stream.read(PROBE_BYTES)
        if prefix.startswith(b'\xed\xab\xee\xdb') or path.suffix.lower()=='.rpm':
            return 'RPM_ARCHIVE'
        if kind := identify(prefix):
            return kind.upper()
        if prefix.startswith(b'\x1f\x8b') or prefix[257:262]==b'ustar':
            return 'TAR_CANDIDATE'
        return 'FILE_PENDING_FORMAT_CHECK'
    if path.is_dir():
        if (path/'extraction-manifest.json').is_file():
            return 'PREPARED_INPUT_PENDING_VERIFICATION'
        if looks_like_root(path):
            return 'ROOTFS_DIRECTORY'
        visited = 0
        for _, dirs, files in os.walk(path,followlinks=False):
            visited += len(dirs)+len(files)+1
            if any(name.lower().endswith('.rpm') for name in files):
                return 'RPM_REPOSITORY'
            if visited>8192:
                break
        return 'DIRECTORY_PENDING_FORMAT_CHECK'
    return 'UNSUPPORTED'


def plan(data, tools):
    inputs = {name:identify_input(data[name],name.endswith('_manifest')) for name in PATHS
              if name in data and name not in ('cache','output','index_output','engine_config')}
    missing = [name for name,kind in inputs.items() if kind in ('MISSING','UNSUPPORTED')]
    rpm = any(kind.startswith('RPM_') for kind in inputs.values())
    checks = ['readelf'] if data['objective']=='EXPORT_SYMBOLS' else []
    if rpm:
        checks += ['rpm']+(['rpm2cpio'] if data['rpm_mode']=='payload' else [])
    output = data['output']
    parent = next(p for p in (output,*output.parents) if p.is_dir())
    return {'schema':'tizen-compat-plan/1','status':'BLOCKED' if missing else 'READY_TO_ATTEMPT',
            'requested_objective':data['objective'],'mode':data['mode'],'rpm_mode':data['rpm_mode'],
            'inputs':inputs,'missing_inputs':missing,'tools':tools,'missing_expected_tools':[t for t in checks if not tools[t]],
            'output':str(output),'available_output_bytes':shutil.disk_usage(parent).free,
            'offline':True,'target_execution':False,
            'optional_stages':{'enhanced_index':'REQUESTED' if data.get('index_output') else 'NOT_REQUESTED'}}


def run(data):
    names = [name for name in PATHS if name in data and name!='index_output']
    argv = [value for name in names for value in ('--'+('config' if name=='engine_config' else name.replace('_','-')),str(data[name]))]
    argv += ['--mode',data['mode'],'--rpm-mode',data['rpm_mode'],'--objective',data['objective']]
    with engine_directory(data):
        code = tizen_compat.main(argv)
    output = data['output']
    receipt = output/'run-summary.json'
    if code not in (0,1):
        return code
    summary = read_json(receipt)
    if index := data.get('index_output'):
        try:
            if (output/'rpm-repository.json').is_file():
                from compat.repository_browser import build
            else:
                from compat.report_enhance import build
            build(output,index)
            stage = {'status':'COMPLETE','output':str(index)}
        except Exception as exc:
            stage = {'status':'FAILED','reason':str(exc)[:600]}
        except KeyboardInterrupt:
            stage = {'status':'INTERRUPTED','reason':'Optional index interrupted by operator.'}
        summary['optional_stages'] = {'enhanced_index': stage}
        save(output,summary)
    # The legacy entrypoint preserves its CI policy. The workflow also gates the requested objective.
    return 3 if summary['objective_completion']!='COMPLETE' else code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    for name in ('doctor','plan','run'):
        sub.add_parser(name).add_argument('--config',type=Path,required=name!='doctor')
    for name in ('status','summary'):
        sub.add_parser(name).add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ('status','summary'):
            value = read_json(args.output/'run-summary.json')
            if value.get('schema')!=SCHEMA:
                raise InputError('Unsupported run summary schema')
            if args.command=='status':
                keys = ('scope','requested_objective','objective_completion','execution_status','compatibility_status','coverage_status')
                value = {key:value[key] for key in keys}
        elif args.config is None:
            value = {'schema':'tizen-compat-doctor/1','tools':tool_state(load_config(None)),'offline':True}
        else:
            data = options(args.config)
            with engine_directory(data):
                config = load_config(data.get('engine_config'))
                tools = tool_state(config)
            if args.command=='run':
                if not all(config['report'][name] for name in ('html','json','csv','markdown')):
                    raise InputError('The workflow requires all standard report outputs. Use the legacy CLI for selective outputs.')
                return run(data)
            value = plan(data,tools)
            if args.command=='doctor':
                value['schema']='tizen-compat-doctor/1'
        print(json.dumps(value,ensure_ascii=False,indent=2))
        return 2 if value.get('status')=='BLOCKED' else 0
    except (OSError,ValueError,KeyError,RuntimeError) as exc:
        print(json.dumps(blocked_summary(None,'FAILED',exc),ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
