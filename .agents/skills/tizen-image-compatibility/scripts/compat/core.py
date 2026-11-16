"""Shared schema, configuration and auditable, bounded tool execution."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
from typing import Any

VERSION = '1.0.0'
SCHEMA = '1.0'
DIMENSIONS = ('elf', 'abi', 'api', 'headers', 'linking', 'compiler_runtime', 'kernel',
              'ipc', 'commands', 'filesystem', 'packages', 'services', 'security',
              'runtime', 'hardware', 'network', 'performance')
SEVERITIES = ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')
STATUSES = ('IDENTICAL', 'COMPATIBLE', 'INCOMPATIBLE', 'UNKNOWN', 'NOT_APPLICABLE')
DEFAULTS: dict[str, Any] = {
    'comparison': {'baseline_name': 'baseline', 'candidate_name': 'candidate',
                   'baseline_toolchain': 'unknown', 'candidate_toolchain': 'unknown'},
    'analysis': {'modes': list(DIMENSIONS), 'ignore_build_ids': True,
                 'ignore_timestamps': True, 'normalize_build_paths': True,
                 'workers': 4, 'timeout_seconds': 60, 'max_text_bytes': 4194304,
                 'max_extract_bytes': 107374182400, 'max_extract_files': 2000000},
    'tools': {},
    'runtime': {'enabled': False, 'authorized': False, 'timeout_seconds': 60,
                'environments': {}, 'probes': []},
    'cross_compilation': {'enabled': True, 'c_tests': True, 'cpp_tests': True,
                          'sysroots': {}, 'compilers': {}, 'header_limit': 50,
                          'include_dirs': ['usr/include'], 'probes': []},
    'performance': {'enabled': False, 'tolerance_percent': 10},
    'report': {'html': True, 'json': True, 'markdown': True, 'csv': True},
    'ci': {'fail_on': 'HIGH', 'strict': False},
    'severity_overrides': {},
}


class InputError(ValueError):
    pass


class InfrastructureError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_config(path: Path | None) -> dict[str, Any]:
    conf = copy.deepcopy(DEFAULTS)
    if path:
        try:
            import yaml
        except ImportError as exc:
            raise InputError('YAML configuration needs PyYAML; omit --config for defaults.') from exc
        try:
            incoming = yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError) as exc:
            raise InputError(f'Cannot read configuration: {exc}') from exc
        if not isinstance(incoming, dict):
            raise InputError('Configuration must be a mapping')
        for section, values in incoming.items():
            if section not in conf or not isinstance(values, dict):
                raise InputError(f'Unknown section or invalid mapping: {section}')
            if section not in ('tools', 'severity_overrides'):
                unknown = set(values) - set(conf[section])
                if unknown:
                    raise InputError(f'Unknown {section} keys: {sorted(unknown)}')
            conf[section].update(values)
    validate_config(conf)
    return conf


def validate_config(c: dict[str, Any]) -> None:
    def require(ok: bool, message: str) -> None:
        if not ok:
            raise InputError(message)
    for section, defaults in DEFAULTS.items():
        for key, default in defaults.items():
            value = c[section][key]
            require(type(value) is type(default) or
                    (type(default) is int and type(value) is float), f'Invalid type: {section}.{key}')
            if type(default) is int:
                require(value >= (0 if key in ('header_limit', 'tolerance_percent') else 1),
                        f'Invalid range: {section}.{key}')
    require(all(x in DIMENSIONS for x in c['analysis']['modes']), 'Unknown analysis dimension')
    require(type(c['analysis']['workers']) is int and type(c['cross_compilation']['header_limit']) is int,
            'workers and header_limit must be integers')
    require(c['ci']['fail_on'] in SEVERITIES, 'Invalid fail_on severity')
    require(all(k in DIMENSIONS and v in SEVERITIES for k, v in c['severity_overrides'].items()),
            'severity_overrides must map dimension to severity')
    require(all(isinstance(v, str) or v is False for v in c['tools'].values()), 'Tool must be path or false')
    cc = c['cross_compilation']
    require(set(cc['sysroots']) <= {'baseline', 'candidate'}, 'Unknown sysroot image key')
    require(all(isinstance(v, str) for v in cc['sysroots'].values()), 'Sysroots must be paths')
    require(set(cc['compilers']) <= {'gcc', 'clang'}, 'Compiler keys must be gcc or clang')
    for name, spec in cc['compilers'].items():
        require(isinstance(spec, dict) and set(spec) <= {'c', 'cpp', 'flags', 'target'}, f'Invalid compiler {name}')
        require(all(isinstance(spec.get(k, ''), str) for k in ('c', 'cpp', 'target')), 'Compiler path/target must be string')
        require(isinstance(spec.get('flags', []), list) and all(isinstance(x, str) for x in spec.get('flags', [])), 'Compiler flags must be string array')
    require(all(isinstance(x, str) and not Path(x).is_absolute() and '..' not in Path(x).parts
                for x in cc['include_dirs']), 'include_dirs must be sysroot-relative')
    for env, spec in c['runtime']['environments'].items():
        require(env in ('baseline', 'candidate') and isinstance(spec, dict), 'Invalid runtime environment')
        require(set(spec) <= {'id', 'runner'}, 'Unknown runtime environment key')
        require(isinstance(spec.get('id'), str) and bool(spec['id']), 'Runtime environment needs id')
        runner = spec.get('runner')
        require(isinstance(runner, list) and bool(runner) and all(isinstance(x, str) for x in runner), 'runner must be argv array')
        require(any('{binary}' in x for x in runner), 'runner must reference {binary}')
    for probe in cc['probes']:
        require(isinstance(probe, dict) and set(probe) <= {'name', 'source', 'language', 'flags'}, 'Invalid compile probe')
        require(all(isinstance(probe.get(k), str) for k in ('name', 'source', 'language')) and probe['language'] in ('c', 'cpp'), 'Probe needs name, source and language')
        require(isinstance(probe.get('flags', []), list) and all(isinstance(x, str) for x in probe.get('flags', [])), 'Probe flags must be array')
    for probe in c['runtime']['probes']:
        require(isinstance(probe, dict) and set(probe) <= {'name', 'dimension', 'argv', 'expected_stdout', 'expected_exit'}, 'Invalid runtime probe')
        require(isinstance(probe.get('name'), str) and probe.get('dimension') in DIMENSIONS, 'Runtime probe needs name/dimension')
        require(isinstance(probe.get('argv'), list) and bool(probe['argv']) and all(isinstance(x, str) for x in probe['argv']), 'Runtime probe argv required')
        require(isinstance(probe.get('expected_exit', 0), int) and isinstance(probe.get('expected_stdout', ''), str), 'Invalid runtime expectation')


class Tools:
    """Never uses a shell. Tool output is persisted even on error or timeout."""
    def __init__(self, output: Path, config: dict[str, Any]):
        self.output = output
        self.raw = output / 'evidence'
        self.raw.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.lock = threading.Lock()
        self.records: list[dict[str, Any]] = []
        self.versions: dict[str, Any] = {}
        self.aliases: dict[str, str] = {}

    def path(self, name: str) -> str | None:
        override = self.config['tools'].get(name, name)
        return shutil.which(override) if override else None

    def normalize(self, text: str) -> str:
        for path, label in sorted(self.aliases.items(), key=lambda x: -len(x[0])):
            text = text.replace(path, label)
        return text

    def run(self, argv: list[str], timeout: float | None = None) -> dict[str, Any]:
        timeout = timeout or self.config['analysis']['timeout_seconds']
        env = os.environ.copy()
        env.update({'LC_ALL': 'C', 'TZ': 'UTC'})
        for key in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
            env.pop(key, None)
        error = ''
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
                try:
                    code = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    code, error = -1, 'timeout'
            except OSError as exc:
                code, error = -1, str(exc)
            result: dict[str, Any] = {'argv': [self.normalize(a) for a in argv], 'returncode': code, 'error': error}
            # Keep raw output in full on disk; parsing is bounded and marked incomplete.
            hashes = []
            for name, stream in (('stdout', stdout), ('stderr', stderr)):
                stream.seek(0)
                h = hashlib.sha256()
                temp = tempfile.NamedTemporaryFile(dir=self.raw, delete=False)
                with temp:
                    while block := stream.read(1024 * 1024):
                        h.update(block)
                        temp.write(block)
                raw_id = h.hexdigest()
                os.replace(temp.name, self.raw / f'{raw_id}.txt')
                stream.seek(0)
                data = stream.read(16 * 1024 * 1024 + 1)
                result[name] = self.normalize(data[:16 * 1024 * 1024].decode('utf-8', 'replace'))
                result[f'{name}_truncated'] = len(data) > 16 * 1024 * 1024
                result[f'{name}_evidence'] = f'evidence/{raw_id}.txt'
                hashes.append(raw_id)
            result['evidence_id'] = digest(canonical([result['argv'], code, hashes, error]).encode())
            with self.lock:
                self.records.append({k: v for k, v in result.items() if k not in ('stdout', 'stderr')})
            return result

    def discover(self) -> dict[str, Any]:
        for name in ('readelf', 'nm', 'objdump', 'abidiff', 'abi-dumper', 'abi-compliance-checker',
                     'pahole', 'rpm', 'unsquashfs', 'debugfs', 'clang', 'gcc'):
            path = self.path(name)
            record: dict[str, Any] = {'available': bool(path), 'path': path}
            if path:
                result = self.run([path, '--version'])
                record['version'] = (result['stdout'] or result['stderr']).splitlines()[:2]
            self.versions[name] = record
        return self.versions

    def flush(self) -> None:
        with (self.output / 'collection.log').open('w') as out:
            for record in sorted(self.records, key=canonical):
                out.write(canonical(record) + '\n')


def finding(dimension: str, component: str, interface: str, baseline: Any, candidate: Any,
            status: str = 'UNKNOWN', severity: str = 'MEDIUM', method: str = 'static comparison',
            evidence: Any = None, impact: str = '', action: str = '', confidence: str = 'medium') -> dict[str, Any]:
    item = dict(dimension=dimension, component=component, interface=interface,
                baseline=baseline, candidate=candidate, status=status, severity=severity,
                confidence=confidence, evidence=evidence or [], detection_method=method,
                potential_impact=impact or 'Review the observable contract before attributing this difference to a compiler.',
                recommended_action=action or 'Validate with the matching target SDK and representative consumer.')
    item['id'] = 'TC-' + digest(canonical(item).encode())[:16]
    return item


def limitation(dimension: str, reason: str, component: str = '*') -> dict[str, str]:
    return {'dimension': dimension, 'component': component, 'reason': reason}


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
        if data['schema_version'] != SCHEMA or not isinstance(data['image'], dict):
            raise ValueError('unsupported schema')
        if not isinstance(data['image'].get('name'), str):
            raise ValueError('image.name must be a string')
        for key in ('elf_objects', 'public_headers', 'packages', 'limitations', 'test_results'):
            if not isinstance(data[key], list):
                raise ValueError(f'invalid {key}')
        for key in ('elf_objects', 'public_headers', 'packages', 'limitations', 'test_results',
                    'filesystem', 'services', 'commands', 'configurations', 'security_interfaces',
                    'kernel', 'hardware', 'network', 'development', 'runtime_libraries', 'ipc', 'capabilities', 'cross_matrix'):
            if key in data and (not isinstance(data[key], list) or any(not isinstance(v, dict) for v in data[key])):
                raise ValueError(f'invalid {key} records')
        for obj in data['elf_objects']:
            if not isinstance(obj.get('path'), str) or type(obj.get('complete')) is not bool:
                raise ValueError('invalid ELF object')
            if obj['complete']:
                if not isinstance(obj.get('exports'), list):
                    raise ValueError('invalid ELF exports')
                for symbol in obj.get('exports', []):
                    if not isinstance(symbol, dict) or not all(k in symbol for k in ('name', 'type', 'binding', 'visibility', 'size')):
                        raise ValueError('invalid ELF symbol')
            if 'needed' in obj and (not isinstance(obj['needed'], list) or any(not isinstance(x, str) for x in obj['needed'])):
                raise ValueError('invalid ELF dependencies')
        for obj in data['public_headers']:
            if not all(k in obj for k in ('path', 'tokens', 'macros', 'conditions', 'includes', 'sha256', 'declarations', 'body_tokens', 'context_hints')):
                raise ValueError('invalid public header record')
            if not all(isinstance(obj[k], dict) for k in ('macros', 'declarations')) or not all(isinstance(obj[k], list) for k in ('tokens', 'conditions', 'includes', 'body_tokens', 'context_hints')):
                raise ValueError('invalid public header types')
        for section in ('filesystem', 'services', 'commands', 'configurations', 'security_interfaces',
                        'kernel', 'hardware', 'network', 'development', 'runtime_libraries'):
            if any(not isinstance(obj.get('path'), str) for obj in data.get(section, [])):
                raise ValueError(f'invalid {section} path')
        for obj in data.get('filesystem', []):
            if not isinstance(obj.get('type'), str):
                raise ValueError('invalid filesystem type')
        for obj in data.get('ipc', []):
            if not all(isinstance(obj.get(k), str) for k in ('path', 'name')):
                raise ValueError('invalid IPC record')
        for obj in data['packages']:
            if not all(isinstance(obj.get(k), str) for k in ('name', 'arch')):
                raise ValueError('invalid package identity')
        for obj in data['limitations']:
            if not all(isinstance(obj.get(k), str) for k in ('dimension', 'component', 'reason')):
                raise ValueError('invalid limitation')
        for obj in data['test_results']:
            if obj.get('status') not in STATUSES or not all(k in obj for k in ('id', 'kind', 'image')):
                raise ValueError('invalid test result')
        for obj in data.get('cross_matrix', []):
            if not all(obj.get(k) in STATUSES for k in ('header_status', 'runtime_status', 'status')) or not all(k in obj for k in ('compiler', 'image')):
                raise ValueError('invalid cross matrix')
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InputError(f'Invalid manifest {path}: {exc}') from exc
