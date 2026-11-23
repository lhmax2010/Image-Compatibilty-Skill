"""Observe an independent cgroup while executing only a reviewed x86-64 fixture."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time


CASES = ('normal', 'nonzero', 'timeout', 'sigint', 'sigterm', 'closed', 'session', 'overflow', 'controller')
LIMIT = 1024 * 1024
BIND = '/mnt/tizen-smoke-input'
LIVE_LIMITS = {'memory.max': '268435456', 'memory.swap.max': '0', 'cpu.max': '100000 100000', 'pids.max': '32'}


def identity(path):
    info = path.stat()
    return [info.st_dev, info.st_ino]


def sample(path):
    events = dict(line.split() for line in (path/'cgroup.events').read_text().splitlines())
    procs = set()
    for member in path.rglob('cgroup.procs'):
        try:
            procs.update(map(int, member.read_text().split()))
        except FileNotFoundError:
            continue
    workers = []
    for pid in sorted(procs):
        try:
            process = Path(f'/proc/{pid}')
            fields = (process/'stat').read_bytes().rsplit(b') ', 1)[1].split()
            workers.append({'pid': pid, 'starttime': int(fields[19]),
                            'cgroup': (process/'cgroup').read_text().strip()})
        except (FileNotFoundError, ProcessLookupError):
            continue
    return {'identity': identity(path), 'populated': events['populated'], 'workers': workers,
            'limits': {name: (path/name).read_text().strip() for name in LIVE_LIMITS},
            'memory_current': (path/'memory.current').read_text().strip(),
            'pids_current': (path/'pids.current').read_text().strip(),
            'cpu_stat': (path/'cpu.stat').read_text().strip()}


def assert_empty(path, expected):
    deadline = time.monotonic() + 2
    while True:
        out = sample(path)
        if out['identity'] != expected:
            raise RuntimeError('Persistent slice inode changed')
        if out['populated'] == '0' and not out['workers'] and out['pids_current'] == '0':
            return out
        if time.monotonic() >= deadline:
            raise RuntimeError('Persistent slice still has live tasks')
        time.sleep(0.05)


def owned_unit(ledger, unit, values):
    return (values.get('Transient') == 'yes' and values.get('Description') == ledger.description(unit)
            and values.get('InvocationID') not in ('', None, '00000000000000000000000000000000'))


def fixture_argv(user, mode):
    argv = ['/usr/bin/prlimit', '--cpu=10', '--as=8589934592', '--nofile=64', '--fsize=1048576', '--core=0',
            '--', '/usr/bin/bwrap', '--unshare-all', '--unshare-user', '--disable-userns', '--die-with-parent',
            '--new-session', '--cap-drop', 'ALL', '--clearenv', '--proc', '/proc', '--perms', '1777',
            '--size', '16777216', '--tmpfs', '/tmp', '--dir', '/runner', '--dir', '/lib', '--dir', '/usr/lib']
    for name, location in (('host-probe', '/runner/host-only'), ('probe', '/runner/probe'),
                           ('qemu-arm-static', '/runner/qemu-arm-static'), ('ld-linux.so.3', '/lib/ld-linux.so.3'),
                           ('libc.so.6', '/lib/libc.so.6')):
        argv += ['--ro-bind', f'{BIND}/{name}', location]
    return [*argv, '--remount-ro', '/', '--chdir', '/tmp', '/runner/host-only', mode,
            str(user.pw_uid), str(user.pw_gid), *(os.readlink(f'/proc/self/ns/{ns}') for ns in ('net', 'pid', 'mnt'))]


def run_service(ledger, unit, mode, cgroup, user, command, properties):
    before = assert_empty(cgroup, ledger.created['slice']['identity'])
    invoked = before['identity']
    require_group = '/' + cgroup.name + '/' + unit
    stage = ledger.path.parent / 'inputs'
    argv = ['/usr/bin/sudo', '-n', '--', '/usr/bin/systemd-run', '--system', '--wait', '--pipe', '--quiet',
            '--service-type=exec', f'--unit={unit}', f'--slice={cgroup.name}', f'--description={ledger.description(unit)}',
            '--property=User=tizen-smoke', '--property=Group=tizen-smoke', '--property=NoNewPrivileges=yes',
            '--property=PrivateNetwork=yes', '--property=KillMode=control-group', '--property=RuntimeMaxSec=15s',
            '--property=TimeoutStopSec=2s', '--property=SendSIGKILL=yes', '--property=LimitCORE=0',
            '--property=MemoryMax=256M', '--property=MemorySwapMax=0', '--property=CPUQuota=100%',
            '--property=TasksMax=32', '--property=TemporaryFileSystem=/mnt:ro,nosuid,nodev',
            f'--property=BindReadOnlyPaths={stage}:{BIND}', '--', *fixture_argv(user, mode)]
    ledger.begin('start ' + unit)
    started = time.monotonic()
    data = {'before': before, 'live': [], 'after': None, 'runtime_limit': '15s', 'stop_grace': '2s'}
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    stop_requested = None
    proc = None
    evidence = ledger.path.parent / 'evidence'
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=dict(os.environ, LANG='C', LC_ALL='C', SYSTEMD_COLORS='0'), start_new_session=True)
        with selectors.DefaultSelector() as selector:
            for key in streams:
                selector.register(getattr(proc, key), selectors.EVENT_READ, key)
            next_sample = 0
            while selector.get_map() or proc.poll() is None:
                now = time.monotonic()
                if now - started > 23:
                    raise RuntimeError('Independent observation deadline exceeded')
                if now >= next_sample:
                    next_sample = now + 0.075
                    values = properties(unit)
                    if owned_unit(ledger, unit, values) and values.get('ControlGroup') == require_group:
                        live_path = cgroup / unit
                        try:
                            current = sample(live_path)
                        except FileNotFoundError:
                            current = None
                        if current and current['populated'] == '1' and current['workers']:
                            registered = ledger.created['units'].get(unit)
                            key = {'invocation_id': values['InvocationID'], 'cgroup': require_group,
                                   'identity': current['identity']}
                            if registered and registered != key:
                                raise RuntimeError('Live service identity changed')
                            if not registered:
                                ledger.created['units'][unit] = key
                                ledger.done()
                            if (current['limits'] != LIVE_LIMITS
                                    or any(worker['cgroup'] != '0::'+require_group for worker in current['workers'])):
                                raise RuntimeError('Effective service cgroup limits or process membership differ')
                            current['slice_populated'] = sample(cgroup)['populated']
                            data['live'].append(current)
                for ready, _ in selector.select(0.05):
                    block = os.read(ready.fd, 65536)
                    if not block:
                        selector.unregister(ready.fileobj)
                        continue
                    remaining = LIMIT - sum(map(len, streams.values()))
                    streams[ready.data].extend(block[:remaining])
                    if len(block) > remaining and stop_requested is None:
                        stop_requested = 'output-limit'
                        stop_service(ledger, unit, command, properties)
                if (mode == 'controller' and not stop_requested and b'HOST_CHILD_READY' in streams['stdout']
                        and any(len(item['workers']) >= 3 for item in data['live'])):
                    stop_requested = 'controller-exit'
                    proc.terminate()
                    # The shell's exit is irrelevant. Only the verified unit may be stopped.
                    stop_service(ledger, unit, command, properties)
        data['returncode'] = proc.wait(timeout=2)
        data['elapsed_seconds'] = round(time.monotonic() - started, 3)
        data['systemd_result'] = properties(unit)
        data['stop_requested'] = stop_requested
        data['after'] = assert_empty(cgroup, invoked)
        processes = command(['/usr/bin/ps', '-e', '-o', 'ruid=,euid=,suid=,pid='], admin=True).stdout.splitlines()
        data['remaining_dedicated_uid'] = [int(row[-1]) for line in processes
                                          if (row := line.split()) and str(user.pw_uid) in row[:3]]
        if data['remaining_dedicated_uid']:
            raise RuntimeError('Dedicated UID still has live processes outside the proven empty slice')
        if not data['live'] or not any(item['slice_populated'] == '1' for item in data['live']):
            raise RuntimeError('No live cgroup membership observation')
        if not b'HOST_X86_64_ISOLATION_OK' in streams['stdout']:
            raise RuntimeError('Host fixture did not complete its checks')
        if mode in ('closed', 'session', 'controller'):
            if b'HOST_CHILD_READY' not in streams['stdout'] or not any(len(i['workers']) >= 3 for i in data['live']):
                raise RuntimeError('No observed isolated child workload')
        code, result = data['returncode'], data['systemd_result']
        expected = {
            'normal': code == 0, 'nonzero': code == 17 and result.get('ExecMainStatus') == '17',
            'timeout': code != 0 and result.get('Result') == 'timeout' and data['elapsed_seconds'] >= 14,
            'sigint': code != 0 and result.get('ExecMainStatus') in ('2', '130'),
            'sigterm': code != 0 and result.get('ExecMainStatus') in ('15', '143'),
            'closed': code == 0, 'session': code == 0,
            'overflow': stop_requested == 'output-limit' and sum(map(len, streams.values())) == LIMIT,
            'controller': stop_requested == 'controller-exit',
        }
        if not expected[mode]:
            raise RuntimeError(f'Unexpected outcome of {mode}')
        data['status'] = 'VERIFIED'
    finally:
        try:
            if proc is not None:
                if ledger.created['units'].get(unit) and (proc.poll() is None or sample(cgroup)['populated'] != '0'):
                    stop_service(ledger, unit, command, properties)
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                proc.stdout.close()
                proc.stderr.close()
        finally:
            for key, raw in streams.items():
                (evidence / f'{mode}.{key}').write_bytes(raw)
            (evidence / f'{mode}.json').write_text(json.dumps(data, indent=2) + '\n')
            ledger.data['case_results'][mode] = data.get('status', 'NOT_VERIFIED')
            ledger.save()


def stop_service(ledger, unit, command, properties):
    values = properties(unit)
    if values.get('ActiveState') in ('inactive', 'failed'):
        return
    known = ledger.created['units'].get(unit)
    if not (known and owned_unit(ledger, unit, values) and known['invocation_id'] == values['InvocationID']):
        raise RuntimeError(f'Cannot stop a service outside the recorded invocation: {unit}')
    command(['/usr/bin/systemctl', '--system', 'stop', unit], admin=True)


def qualify(ledger, command, properties, occupied, verify_account):
    slice_name, anchor = 'tizensmoke.slice', 'tizen-smoke-preflight.service'
    cgroup = Path('/sys/fs/cgroup') / slice_name
    user = verify_account(ledger.created['account'])
    if occupied(properties(slice_name)) or cgroup.exists() or occupied(properties(anchor)):
        raise RuntimeError('Slice or anchor name was taken during setup')
    (ledger.path.parent/'evidence').mkdir(mode=0o700)
    ledger.begin('create ' + anchor + ' and ' + slice_name)
    # The exited oneshot keeps the slice identity observable between test services.
    command(['/usr/bin/systemd-run', '--system', f'--unit={anchor}', f'--slice={slice_name}', '--quiet',
             '--remain-after-exit', '--service-type=oneshot', f'--description={ledger.description(anchor)}',
             '--property=User=tizen-smoke', '--property=Group=tizen-smoke', '--property=NoNewPrivileges=yes',
             '--property=MemoryMax=256M', '--property=MemorySwapMax=0', '--property=CPUQuota=100%', '--property=TasksMax=32',
             '--property=PrivateNetwork=yes', '--', '/usr/bin/true'], admin=True)
    values = properties(anchor)
    if not owned_unit(ledger, anchor, values) or not cgroup.is_dir() or values.get('User') != 'tizen-smoke':
        raise RuntimeError('Could not establish the persistent slice/anchor identity')
    ledger.created['units'][anchor] = {'invocation_id': values['InvocationID']}
    ledger.created['slice'] = {'identity': identity(cgroup), 'path': str(cgroup)}
    ledger.done()
    for mode in CASES:
        unit = f'tizen-smoke-preflight-{mode}.service'
        if occupied(properties(unit)):
            raise RuntimeError(f'Preflight unit already exists: {unit}')
        run_service(ledger, unit, mode, cgroup, user, command, properties)
