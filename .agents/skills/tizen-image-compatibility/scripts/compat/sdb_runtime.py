"""Bounded, profile-scoped SDB observations with an independent lifecycle verifier."""
from __future__ import annotations

import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import ipaddress
from pathlib import Path
import re
import shlex
import time
from uuid import uuid4

from . import probe_bundle, runtime_binding, runtime_plan
from . import sdb_protocol as wire
from .core import InputError, canonical, digest, hash_file, write_json

HEADED = 'SR_HEADED_RUNTIME'
HEADLESS = 'SR_RUNTIME'
PHASE8E_MANIFEST_SHA256 = 'fe59f50a2501d0c165b5e7a3b037e969b418e06bbb8951e917412a4a06713c32'
PROVIDERS = {'ld-linux.so.3', 'libc.so.6', 'libgcc_s.so.1', 'libm.so.6', 'libstdc++.so.6'}
OPTIONAL_PROVIDERS = {'libpthread.so.0', 'libdl.so.2', 'librt.so.1', 'libatomic.so.1', 'libunwind.so.8'}
CAPTURE_LIMIT = 640 * 1024
REMOTE_FILE_LIMIT = 128 * 1024
MAX_OBSERVER_AGE = 3.0
SAFE_PATH = re.compile(r'/[A-Za-z0-9_.+@/-]+')
HASH = re.compile(r'[0-9a-f]{64}')


class SdbRuntimeError(InputError):
    def __init__(self, message, code='NOT_VERIFIED'):
        super().__init__(message)
        self.code = code


def require(condition, message, code='NOT_VERIFIED'):
    if not condition:
        raise SdbRuntimeError(message, code)


def safe_path(path):
    return isinstance(path, str) and SAFE_PATH.fullmatch(path) and all(
        p not in ('', '.', '..') for p in path[1:].split('/'))


def section_values(text):
    values = {}
    for line in text.splitlines():
        if re.fullmatch(r'[A-Za-z][A-Za-z_0-9]*=.*', line):
            key, value = line.split('=', 1)
            require(key not in values, f'Duplicate protocol value {key}')
            values[key] = value
    return values


def validate_enrollment(spec, artifact, execute):
    serial = spec['sdb_serial']
    host, sep, port = serial.rpartition(':')
    require(sep and port.isascii() and port.isdigit() and 0 < int(port) <= 65535
            and str(ipaddress.IPv4Address(host)) == host, 'Expected a single explicit IPv4 SDB endpoint')
    scope, family = spec['scope'], spec['image_family']
    require(scope in (HEADLESS, HEADED) and family in ('vd', 'llvm'), 'Unknown profile scope or image family')
    profile = 'headed' if scope == HEADED else 'headless'
    train = 'dev' if family == 'vd' else 'toolchain'
    require(re.fullmatch(rf'tizen-unified-{train}_[0-9]{{8}}\.[0-9]{{6}}_tizen-{profile}-armv7l',
                         spec['build_id']), 'Build ID must specify the selected family and profile')
    providers = spec['provider_sha256']
    require(PROVIDERS <= providers.keys() <= (PROVIDERS | OPTIONAL_PROVIDERS)
            and all(HASH.fullmatch(s) for s in providers.values())
            and HASH.fullmatch(spec['cpu_serial_sha256']), 'Incomplete identity pins')
    auth = spec.get('authorization', {})
    allowed = auth.get('artifact_sha256', {})
    if execute:
        require(scope == HEADED, 'Headless execution is managed by the existing formal entry', 'UNAUTHORIZED')
        require(spec.get('authorization', {}).get('execute') is True
                and allowed.get(artifact['artifact_id']) == artifact['sha256'],
                'Explicit authorization and exact artifact digest are required', 'UNAUTHORIZED')
        if 'manifest_sha256' in artifact:
            require(auth.get('manifest_sha256') == artifact['manifest_sha256']
                    and auth.get('target_sha256') == probe_bundle.target_pin(spec),
                    'New bundles require independent manifest and target authorization pins', 'UNAUTHORIZED')


@dataclass(frozen=True)
class Response:
    challenge: str
    text: str
    returncode: int
    received: float
    evidence: tuple[str, ...]


class SdbTransport:
    """Uses an existing connection only. No discovery, reconnection or user command input."""

    def __init__(self, tools, executable, serial):
        self.tools = tools
        self.argv = [executable, '-s', serial]

    def _run(self, args, timeout):
        result = self.tools.run([*self.argv, *args], timeout=timeout, max_capture_bytes=CAPTURE_LIMIT,
                                keep_interrupt=True)
        error = result['error']
        if error:
            code = {'adapter output limit exceeded': 'OUTPUT_LIMIT', 'timeout': 'TRANSPORT_TIMEOUT',
                    'interrupted': 'INTERRUPTED'}.get(error, 'TRANSPORT_ERROR')
            raise SdbRuntimeError(error, code)
        protocol_limit = 'service name too long' in result['stderr']
        require(result['returncode'] == 0, 'SDB client failed',
                'SDB_PROTOCOL_REJECTED' if protocol_limit else 'SDB_DISCONNECTED')
        return result

    def shell(self, operation, *args, timeout=4):
        challenge = uuid4().hex
        prefix = f'__SR_{challenge}__'
        command = (f'( set -- {shlex.join([str(a) for a in args])}\n{operation}\n)'
                   f'\nrc=$?; printf "\\n{prefix}%s\\n" "$rc"')
        require(len(command.encode()) <= 1900, 'SDB shell request exceeds the legacy service length')
        result = self._run(['shell', command], timeout)
        text = result['stdout'].replace('\r\n', '\n')
        tail = re.search(rf'(?m)^\n?{prefix}([0-9]+)\n?\Z', text)
        require(tail is not None, 'Remote response has no fresh completion marker', 'SDB_DISCONNECTED')
        return Response(challenge, text[:tail.start()], int(tail[1]), time.monotonic(),
                        tuple(result[key] for key in ('stdout_evidence', 'stderr_evidence')))

    def push(self, artifact, destination):
        result = self._run(['push', str(artifact), destination], 10)
        return [result[key] for key in ('stdout_evidence', 'stderr_evidence')]


def good(response, label):
    require(response.returncode == 0, f'{label}: remote exit {response.returncode}',
            'OUTPUT_LIMIT' if 'OUTPUT_LIMIT=yes' in response.text.splitlines() else 'REMOTE_ERROR')
    return section_values(response.text)


def table(text, label, columns):
    return [line.split('|', columns)[1:] for line in text.splitlines()
            if line.startswith(label+'|') and len(line.split('|', columns)) == columns + 1]


@dataclass(frozen=True)
class Device:
    boot: str
    uid: str
    base: str
    manager: str
    providers: dict


def admit(transport, spec):
    response = transport.shell(wire.ADMIT, spec['build_id'], *sorted(spec['provider_sha256']), timeout=8)
    require(response.returncode == 0, 'Target release/Profile or prerequisites did not match', 'IDENTITY_MISMATCH')
    vals = good(response, 'admission')
    require(vals.get('DEVICE') == spec['cpu_serial_sha256'], 'Pinned board identity differs', 'IDENTITY_MISMATCH')
    uid, boot = vals['UID'], vals['BOOT']
    base, manager = vals['BASE'], vals['MANAGER']
    require(re.fullmatch(r'[1-9][0-9]*', uid) and re.fullmatch(
        r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', boot), 'Invalid nonroot UID or boot ID')
    opts = set(vals['MOUNT'].split(','))
    require(safe_path(base) and base.endswith('/.cache') and 'rw' in opts and 'noexec' not in opts
            and manager == f'/user.slice/user-{uid}.slice/user@{uid}.service',
            'No accepted private staging base or observable user manager')
    rows = table(response.text, 'FILE', 3)
    providers = {name: {'path': path, 'sha256': sha} for name, path, sha in rows}
    require(len(rows) == len(spec['provider_sha256']) and all(safe_path(p['path']) for p in providers.values())
            and {k: v['sha256'] for k, v in providers.items()} == spec['provider_sha256'],
            'Pinned provider identity differs', 'IDENTITY_MISMATCH')
    return Device(boot, uid, base, manager, providers), response.evidence


@dataclass(frozen=True)
class Attempt:
    id: str
    device: Device
    artifact_sha: str
    directory: str
    directory_id: str

    @property
    def unit(self):
        return f'tizen-compat-{self.id}.scope'

    @property
    def cgroup(self):
        return f'{self.device.manager}/{self.unit}'

    @property
    def session(self):
        return self.device.boot, self.device.uid

    @property
    def stage(self):
        return *self.session, self.directory, self.directory_id


@dataclass(frozen=True)
class Observation:
    response: Response
    fields: dict
    processes: dict
    gone: frozenset

    @classmethod
    def parse(cls, response, attempt, phase):
        fields = good(response, phase)
        require(fields.get('ATTEMPT') == attempt.id and fields.get('PHASE') == phase
                and (fields.get('BOOT'), fields.get('UID')) == attempt.session
                and re.fullmatch(r'[1-9][0-9]*', fields.get('OBSERVER_PID', '')),
                'Observer returned the wrong attempt, stage or device boot')
        rows = table(response.text, 'PROC', 5)
        gone = [p for p, in table(response.text, 'GONE', 1)]
        processes = {pid: (state, pgid, sid, start) for pid, state, pgid, sid, start in rows}
        require(len(processes) == len(rows) and len(gone) == len(set(gone)) and not set(gone) & processes.keys()
                and all(p.isascii() and p.isdigit() and int(p) > 0 for p in (*processes, *gone))
                and all(re.fullmatch(r'[A-Za-z]', state) and all(re.fullmatch(r'[0-9]+', s) for s in (pgid, sid, start))
                        for state, pgid, sid, start in processes.values()), 'Malformed observer process records')
        return cls(response, fields, processes, frozenset(gone))

    def assert_running(self, attempt, now):
        f = self.fields
        pid = f.get('ARMED')
        members = f.get('GROUP_PIDS', '').split()
        require(0 <= now - self.response.received <= MAX_OBSERVER_AGE,
                'The live observation is stale')
        require(f.get('ActiveState') == 'active' and f.get('ControlGroup') == attempt.cgroup
                and f.get('RuntimeMaxUSec') == '10s' and f.get('TimeoutStopUSec') == '1s'
                and f.get('KillMode') == 'control-group' and f.get('Delegate') == 'no'
                and 'CHILD_GROUP' not in f and re.fullmatch(r'[0-9]+:[0-9]+', f.get('GROUP_ID', ''))
                and f.get('GROUP_WRITABLE') in ('yes', 'no')
                and pid in self.processes and len(set(members)) == len(members)
                and set(members) == self.processes.keys() | self.gone
                and f['OBSERVER_PID'] not in members
                and self.processes[pid][0] not in ('Z', 'X', 'x')
                and self.processes[pid][1:3] == (pid, pid), 'Active PID, session or cgroup identity mismatch')
        require(f.get('ELF') == attempt.artifact_sha and f.get('DIR_ID') == attempt.directory_id
                and f.get('CWD') == attempt.directory and f.get('PROC_CGROUP') == attempt.cgroup
                and f.get('PROC_UIDS') == ':'.join([attempt.device.uid]*4)
                and all(re.fullmatch('0+', f.get(k, '')) for k in ('CapEff', 'CapPrm')),
                'The armed process is not bound to the admitted nonroot artifact')
        return pid

    def assert_stopped(self, active):
        f = self.fields
        require(f.get('ActiveState') in ('inactive', 'failed') and not f.get('ControlGroup')
                and (f.get('GROUP_ABSENT') == 'yes' or active is not None
                     and f.get('GROUP_ID') == active.fields.get('GROUP_ID')
                     and f.get('GROUP_PIDS') == '' and 'CHILD_GROUP' not in f),
                'The target scope is still active or its kernel identity differs')
        if active is not None:
            require(self.processes.keys() | self.gone == active.processes.keys(),
                    'An original process has no post-run observation')
            for pid, current in self.processes.items():
                require(current[3] != active.processes[pid][3] or current[0] in ('Z', 'X', 'x'),
                        'An original target process is still alive')


def observe(transport, attempt, phase, *pids):
    response = transport.shell(wire.OBSERVE, *attempt.session, attempt.id, attempt.directory, phase, *pids)
    result = Observation.parse(response, attempt, phase)
    pid = result.fields.get('ARMED', '')
    if phase == 'active' and pid in result.processes:
        detail = transport.shell(wire.ARMED_IDENTITY, *attempt.stage, attempt.id, pid)
        fields = good(detail, 'armed identity')
        require((fields.pop('BOOT', None), fields.pop('UID', None)) == attempt.session
                and fields.pop('ATTEMPT', None) == attempt.id
                and fields.pop('START', None) == result.processes[pid][3]
                and not result.fields.keys() & fields.keys(), 'Armed PID was replaced during observation')
        evidence = replace(response, evidence=response.evidence + detail.evidence)
        result = replace(result, response=evidence, fields=result.fields | fields)
    return result


def verify_exit(attempt, active, ended, removed, released, now):
    active.assert_running(attempt, released)
    expected = ('active', 'ended', 'removed')
    observations = (active, ended, removed)
    require(tuple(o.fields['PHASE'] for o in observations) == expected
            and len({o.response.challenge for o in observations}) == 3
            and len({o.fields['OBSERVER_PID'] for o in observations}) == 3
            and all(o.response.evidence and o.fields['ATTEMPT'] == attempt.id
                    and (o.fields['BOOT'], o.fields['UID']) == attempt.session for o in observations)
            and released <= ended.response.received <= removed.response.received <= now
            and now - removed.response.received <= MAX_OBSERVER_AGE,
            'Independent exit observations missing, replayed or stale')
    ended.assert_stopped(active)
    removed.assert_stopped(active)
    require(removed.fields.get('DIR_ABSENT') == 'yes', 'The target private directory still exists')


def capture_files(transport, attempt, output, names):
    response = transport.shell(wire.CAPTURE, *attempt.stage, *names)
    good(response, 'capture')
    rows = table(response.text, 'FILE', 4)
    require(len(rows) == len(names) and {r[0] for r in rows} == set(names),
            'Target output files are incomplete')
    contents = {}
    for leaf, size, checksum, encoded in rows:
        try:
            raw = base64.b64decode(encoded, validate=True)
        except binascii.Error as error:
            raise SdbRuntimeError('Malformed binary capture') from error
        require(len(raw) <= REMOTE_FILE_LIMIT, 'Target output too large', 'OUTPUT_LIMIT')
        require(size == str(len(raw)) and checksum == digest(raw), 'Binary capture checksum differs')
        (output/leaf).write_bytes(raw)
        contents[leaf] = raw
    return contents, response.evidence


def verify_loaded(transport, attempt, artifact, log, *, startup_failure=False):
    initialized = list(dict.fromkeys(re.findall(rb'calling init:[ \t]+((?:/|\./)\S+)', log)))
    versions = re.findall(rb"checking for version `([^']+)' in file ((?:/|\./)\S+)", log)
    version_rows = [{'version': v.decode('ascii'), 'path': p.decode('ascii')} for v, p in versions]
    wanted = set(artifact.get('binding_symbols', []))
    contracts = artifact.get('binding_contracts', [])
    events = list(runtime_binding.events(log, wanted | {item['symbol'] for item in contracts}))
    bindings = [{key: row[key] for key in ('symbol', 'consumer', 'provider', 'version')} for row in events]
    base = {'versions': version_rows, 'bindings': bindings,
            'unobserved_binding_symbols': sorted(wanted - {row['symbol'] for row in bindings})}
    if startup_failure and not initialized:
        return base | {'status': 'STARTUP_REJECTED', 'files': [],
                       'exact_bindings': runtime_binding.exact_results(contracts, events, [], attempt, artifact)}
    require(initialized and versions, 'Loader diagnostics do not establish actual loading')
    paths = [p.decode('ascii') for p in initialized]
    companions = {name: sha for name, sha in artifact.get('files', {}).items() if name != 'probe'}
    private = {attempt.directory+'/'+name: sha for name, sha in companions.items()}
    paths = list(dict.fromkeys(attempt.directory+'/'+p[2:] if p.startswith('./') else p for p in paths))
    require(all(safe_path(p) and (p.startswith(('/lib/', '/usr/lib/')) or p in private) for p in paths),
            'Unexpected Loader path')
    response = transport.shell(wire.PROVIDERS, *attempt.session, *paths)
    good(response, 'loaded providers')
    rows = table(response.text, 'FILE', 3)
    expected = {Path(artifact['elf']['interpreter']).name, *artifact['elf']['needed']}
    pins = attempt.device.providers | {Path(p).name: {'path': p, 'sha256': sha} for p, sha in private.items()}
    found = {(path, sha) for _, path, sha in rows}
    require(expected <= pins.keys() and len(rows) == len(paths) and {asked for asked, _, _ in rows} == set(paths)
            and {(pins[name]['path'], pins[name]['sha256']) for name in expected} <= found
            and found <= {(p['path'], p['sha256']) for p in pins.values()}, 'Unpinned or missing actual Loader/provider')
    files = [{'requested': requested, 'path': path, 'sha256': checksum} for requested, path, checksum in rows]
    return base | {'status': 'VERIFIED', 'files': files, 'evidence': response.evidence,
                   'exact_bindings': runtime_binding.exact_results(contracts, events, files, attempt, artifact)}


def run_attempt(transport, device, artifact, source, output, report):
    aid = uuid4().hex[:16]
    boot, uid = device.boot, device.uid
    binary_sha = artifact['sha256']
    bundle = artifact.get('files', {'probe': binary_sha})
    copies = {}
    for leaf, checksum in bundle.items():
        original = source if leaf == 'probe' else source.parent/leaf
        require(original.is_file() and not original.is_symlink() and original.stat().st_size <= 4*1024**2,
                'Frozen bundle changed before staging')
        copy = output / ('frozen.elf' if leaf == 'probe' else leaf)
        with copy.open('xb') as out:
            out.write(original.read_bytes())
        copy.chmod(0o444)
        require(hash_file(copy) == checksum, 'Frozen bundle changed before staging')
        copies[leaf] = copy
    created = transport.shell(wire.CREATE, boot, uid, device.base, aid)
    values = good(created, 'private directory')
    directory, identity = values['DIR'], values['DIR_ID']
    require(re.fullmatch(re.escape(device.base)+rf'/tizen-compat-{aid}-[A-Za-z0-9]+', directory)
            and re.fullmatch(rf'[0-9]+:[0-9]+:{uid}:700', identity), 'Unexpected target directory identity')
    attempt = Attempt(aid, device, binary_sha, directory, identity)
    report.update(attempt_id=aid, target_directory=directory, directory_identity=identity,
                  scope_unit=attempt.unit, cgroup=attempt.cgroup, create_evidence=created.evidence)
    write_json(output/'runtime.json', report)

    active = None
    released = None
    launch_sent = False
    files = [*bundle, 'armed', 'go', 'probe.stdout', 'probe.stderr']
    remote_rc = None
    try:
        before = observe(transport, attempt, 'before')
        require(before.fields.get('GROUP_ABSENT') == 'yes' and before.fields.get('ActiveState') == 'inactive',
                'Attempt scope already exists')
        report['deployment_transport_evidence'] = {
            leaf: transport.push(copy, directory+'/'+leaf) for leaf, copy in copies.items()}
        if 'files' in artifact:
            deployed = transport.shell(wire.CHECK_BUNDLE, *attempt.stage, *bundle)
            values = good(deployed, 'bundle deployment')
            rows = table(deployed.text, 'BUNDLE', 2)
            require(len(rows) == len(bundle) and dict(rows) == bundle and values.get('COUNT') == str(len(bundle)),
                    'Deployment bundle SHA256 mismatch', 'DEPLOYMENT_MISMATCH')
        else:
            deployed = transport.shell(wire.DEPLOYED, *attempt.stage)
            require(good(deployed, 'deployment').get('ELF') == binary_sha,
                    'Deployment SHA256 mismatch', 'DEPLOYMENT_MISMATCH')
        report['deployed_sha256'] = bundle
        report['deployment_status'] = 'VERIFIED'
        report['deployment_evidence'] = deployed.evidence

        launcher = ['systemd-run','--user','--scope','--no-ask-password',f'--unit={attempt.unit}',
                    '-p','RuntimeMaxSec=10s','-p','TimeoutStopSec=1s','-p','KillMode=control-group',
                    '/usr/bin/setsid','-w','/bin/sh','-c',wire.WORKER,'worker',directory,binary_sha,uid,boot,aid]
        if artifact.get('binding_symbols') or artifact.get('binding_contracts'):
            launcher.append('bindings')
        started = time.monotonic()
        report['launch_requested'] = True
        write_json(output/'runtime.json', report)
        with ThreadPoolExecutor(max_workers=1) as pool:
            launch_sent = True
            launch = pool.submit(transport.shell, 'exec '+shlex.join(launcher), timeout=16)
            end = time.monotonic() + 4
            while time.monotonic() < end and not launch.done():
                candidate = observe(transport, attempt, 'active')
                if 'ARMED' in candidate.fields:
                    if time.monotonic() - candidate.response.received > MAX_OBSERVER_AGE:
                        # No grant was sent. A fresh sample within the existing lease can still admit it.
                        continue
                    pid = candidate.assert_running(attempt, time.monotonic())
                    active = candidate
                    break
                time.sleep(0.075)
            require(active is not None, 'Independent observer did not see an admitted process')
            report['active_observer_evidence'] = active.response.evidence
            files.append('loader.'+pid)
            report['execution_status'] = 'RELEASE_REQUESTED'
            released = time.monotonic()
            active.assert_running(attempt, released)
            pins = [v for leaf, checksum in bundle.items() if leaf != 'probe' for v in (leaf, checksum)]
            armed = transport.shell(wire.ARM, *attempt.stage, aid, pid, active.processes[pid][3], attempt.cgroup, *pins)
            good(armed, 'execution grant')
            report['execution_status'] = 'RELEASED'
            report['grant_evidence'] = armed.evidence
            finished = launch.result()
            report['controller_evidence'] = finished.evidence
            remote_rc = finished.returncode
            report['scope_wall_seconds'] = round(time.monotonic()-started, 6)
    except (InputError, OSError) as error:
        report['execution_error'] = str(error)
        raise
    finally:
        # A failed transport never implies a dead target. Re-observe using another SDB request.
        try:
            ended = observe(transport, attempt, 'ended', *(active.processes if active else ()))
            ended.assert_stopped(active)
            report['exit_observer'] = {'fields':ended.fields, 'processes':ended.processes,
                                       'gone':sorted(ended.gone),'evidence':ended.response.evidence}
            if released is not None and remote_rc is not None:
                classify_execution(transport, attempt, artifact, output, report, files, ended, remote_rc)
        finally:
            # Leave unexpected contents or still-running scopes untouched for authorized recovery.
            if 'exit_observer' in report:
                removed_cmd = transport.shell(wire.REMOVE, *attempt.stage, *files)
                good(removed_cmd, 'target file cleanup')
                if launch_sent and ended.fields.get('Result') == 'timeout' and ended.fields.get('GROUP_ABSENT') == 'yes':
                    good(transport.shell(wire.RESET_TIMEOUT, *attempt.session, attempt.unit, attempt.cgroup),
                         'clear the verified-empty transient timeout scope')
                removed = observe(transport, attempt, 'removed', *(active.processes if active else ()))
                report['directory_removed'] = removed.fields.get('DIR_ABSENT') == 'yes'
                if active is not None and released is not None:
                    verify_exit(attempt, active, ended, removed, released, time.monotonic())
                    report['target_cleanup_status'] = 'VERIFIED'
                    report['cleanup_observer'] = {'active':active.fields, 'processes':active.processes,
                        'active_evidence':active.response.evidence, 'after':removed.fields,
                        'gone':sorted(removed.gone), 'after_evidence':removed.response.evidence}


def classify_execution(transport, attempt, artifact, output, report, files, ended, remote_rc):
    report['target_returncode'] = remote_rc
    expected = artifact['runtime_expectation']
    kind = expected.get('outcome', 'exit')
    out, evidence = capture_files(transport, attempt, output, files[-3:])
    stdout, stderr = out['probe.stdout'], out['probe.stderr']
    report['output_evidence'] = evidence
    report['output_sha256'] = {leaf:digest(raw) for leaf,raw in out.items()}
    report['captured_output'] = {'stdout':stdout.decode('utf-8','replace'),
                                 'stderr':stderr.decode('utf-8','replace')}
    if ended.fields.get('Result') == 'timeout':
        report['execution_status'] = 'TIMEOUT'
        report['execution_success'] = False
        report['behavior_match'] = (kind == 'timeout' and remote_rc == expected['exit_code']
                                    and stdout == expected['stdout'].encode() and stderr == expected['stderr'].encode())
        return
    report['execution_status'] = 'EXITED'
    report['execution_success'] = remote_rc == 0
    loader_failure = (kind == 'loader-error' and expected['stderr_contains'].encode() in stderr
                      and remote_rc == expected['exit_code'] and not stdout)
    report['loader'] = verify_loaded(transport, attempt, artifact, out[files[-1]], startup_failure=loader_failure)
    report['behavior_match'] = loader_failure or (kind == 'exit' and remote_rc == expected['exit_code']
        and stdout == expected['stdout'].encode() and stderr == expected['stderr'].encode()
        and not report['loader']['unobserved_binding_symbols'])
    if re.search(rb"(?m)^glibc: dlopen blocked for object .+ attempting to load ", stderr):
        report['environment_limit'] = 'TARGET_LOADER_POLICY_BLOCKED'
    report['receipt'] = {'schema':'tizen-compat-runner/v1', 'environment_id':report['environment_id'],
                         'binary_sha256':attempt.artifact_sha, 'deployment':'ok', 'execution':'ok',
                         'returncode':remote_rc, 'stdout':stdout.decode('utf-8','replace'),
                         'stderr':stderr.decode('utf-8','replace'), 'run_id':attempt.id,
                         'plan_id': report['plan_id'], 'scope':report['scope']}


def handle(transport, spec, artifact, source, output, *, read_device, execute, expected_boot=None,
           expected_environment=None, test_id=None):
    report = dict(schema='tizen-compat-sdb-observation/v1', scope=spec['scope'],
                  artifact_id=artifact['artifact_id'], artifact_sha256=artifact['sha256'],
                  manifest_sha256=artifact.get('manifest_sha256', PHASE8E_MANIFEST_SHA256),
                  bundle_sha256=runtime_plan.bundle_digest(artifact), test_id=test_id,
                  deployment_status='NOT_EXECUTED', execution_status='NOT_EXECUTED',
                  execution_success=None, behavior_match=None, target_cleanup_status='NOT_VERIFIED',
                  native_reference_status='NOT_VERIFIED', cross_image_compatibility='UNKNOWN',
                  formal_runtime_status='NOT_VERIFIED', target_process_cleanup_status='NOT_VERIFIED', result='PLANNED')
    try:
        validate_enrollment(spec, artifact, execute)
        report.update(enrolled_target_sha256=probe_bundle.target_pin(spec), build_id=spec['build_id'],
                      profile=spec['build_id'].rsplit('_', 1)[1])
        if read_device or execute:
            device, evidence = admit(transport, spec)
            require(expected_boot is None or expected_boot == device.boot,
                    'Boot identity changed since the previous observation', 'IDENTITY_MISMATCH')
            target = [spec['scope'], spec['sdb_serial'], spec['cpu_serial_sha256'], spec['build_id'],
                      device.boot, device.uid, device.providers]
            environment = digest(canonical(target).encode())
            require(expected_environment is None or expected_environment == environment,
                    'Pinned Runtime environment identity differs', 'IDENTITY_MISMATCH')
            report.update(admission_status='VERIFIED', admission_evidence=evidence,
                          environment_id=environment, build_id=spec['build_id'],
                          boot_id=device.boot, providers=device.providers)
            report['plan_id'] = digest(canonical([target, report['manifest_sha256'], artifact['artifact_id'], artifact['sha256']]).encode())
        if execute:
            run_attempt(transport, device, artifact, source, output, report)
            incomplete_bindings = any(row['status'] != 'VERIFIED' for row in
                                      report.get('loader', {}).get('exact_bindings', []))
            if report['target_cleanup_status'] != 'VERIFIED' or incomplete_bindings:
                report['result'] = 'NOT_VERIFIED'
            elif report['behavior_match'] is True:
                report['result'] = 'OBSERVED_SUCCESS' if report['execution_success'] else 'OBSERVED_EXPECTED_FAILURE'
            else:
                report['result'] = 'BEHAVIOR_MISMATCH'
        return 0 if report['result'] in ('PLANNED', 'OBSERVED_SUCCESS', 'OBSERVED_EXPECTED_FAILURE') else 3
    except KeyboardInterrupt:
        report.update(result='BLOCKED', error='Interrupted', error_code='INTERRUPTED')
        return 130
    except (InputError, OSError, ValueError, KeyError, TypeError) as error:
        report.update(result='BLOCKED', error=str(error), error_code=getattr(error, 'code', 'NOT_VERIFIED'))
        return 3
    finally:
        write_json(output/'runtime.json', report)
