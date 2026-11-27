"""Reversible, host-only admission. Privileged commands are narrow and never execute ARM."""
import argparse
from datetime import datetime, timezone
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tempfile
import uuid

from preflight import CASES, LIVE_LIMITS, qualify


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[4]
STATE = WORKSPACE / '.local-backups/arm-smoke-admission'
ACCOUNT = 'tizen-smoke'
SLICE = 'tizensmoke.slice'
ANCHOR = 'tizen-smoke-preflight.service'
UNITS = (ANCHOR,) + tuple(f'tizen-smoke-preflight-{mode}.service' for mode in CASES)
CGROUP = Path('/sys/fs/cgroup')
COMMANDS = '/usr/bin:/usr/sbin'
SHELL = '/usr/sbin/nologin'
STAGED = {
    'probe': ('.local-backups/phase8e/artifacts/vd/A-C.elf', '8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc', '0550'),
    'qemu-arm-static': ('/usr/bin/qemu-arm-static', 'cdfc34eccbfd6d46bca8983713845aa04bfb9c5505abb6e6ae6ea85bed6ef22e', '0440'),
    'ld-linux.so.3': ('.local-backups/phase8g/projection/lib/ld-linux.so.3', '0b1fe895ab844a3dfb04a2ab034a6fca9aeadb570abd49b36bf4be16a676f4df', '0440'),
    'libc.so.6': ('.local-backups/phase8g/projection/lib/libc.so.6', 'f5a377a3121928d31111fa3a556a5ffe16014dc75254620bf2257d5ab7c1e4d4', '0440'),
}
ORDER = ('stop owned services', 'prove empty cgroup and idle account', 'stop owned slice',
         'remove staged files and input directory', 'remove dedicated user and group', 'retain ledger and evidence')
RESOURCE_CONTRACT = {'cgroup_files': LIVE_LIMITS, 'wall_seconds': 15, 'termination_grace_seconds': 2,
                     'tmpfs_bytes': 16777216, 'combined_capture_bytes': 1048576, 'file_limit_bytes': 1048576}


class Blocked(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Blocked(message)


def command(argv, admin=False, check=True):
    if admin:
        argv = ['/usr/bin/sudo', '-n', '--', *argv]
    env = dict(os.environ, PATH=COMMANDS, LC_ALL='C', SYSTEMD_COLORS='0')
    result = subprocess.run(argv, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
    if check and result.returncode:
        raise Blocked(f'{argv[-1] if len(argv) == 1 else argv[0]}: {result.stderr.strip() or result.stdout.strip()}')
    return result


def properties(unit):
    argv = ['/usr/bin/systemctl', '--system', 'show', unit]
    for key in ('LoadState', 'ActiveState', 'FragmentPath', 'DropInPaths', 'ControlGroup', 'Transient',
                'Description', 'InvocationID', 'MainPID', 'User', 'Result', 'ExecMainCode', 'ExecMainStatus'):
        argv += ['-p', key]
    result = command(argv, check=False)
    require(not result.stderr.strip(), f'Cannot query systemd for {unit}: {result.stderr.strip()}')
    values = dict(x.split('=', 1) for x in result.stdout.splitlines() if '=' in x)
    require('LoadState' in values and 'ActiveState' in values, f'No reliable systemd state for {unit}')
    return values


def occupied(values):
    # systemd supplies an implicit placeholder for a never-started slice.
    return (values['ActiveState'] != 'inactive' or values['LoadState'] not in ('not-found', 'loaded')
            or any(values.get(key) for key in ('FragmentPath', 'DropInPaths', 'ControlGroup'))
            or values.get('Transient') == 'yes')


def get_user():
    try:
        return pwd.getpwnam(ACCOUNT)
    except KeyError:
        return None


def get_group():
    try:
        return grp.getgrnam(ACCOUNT)
    except KeyError:
        return None


def digest(path):
    with path.open('rb') as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
        return digest.hexdigest()


def file_id(path):
    info = path.stat(follow_symlinks=False)
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)]


def snapshot():
    user, group = get_user(), get_group()
    mount = command(['/usr/bin/findmnt', '-J', '-T', str(WORKSPACE)]).stdout
    fs = os.statvfs(WORKSPACE)
    unix = os.uname()
    return {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'machine_sha256': digest(Path('/etc/machine-id')), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'kernel': unix.release, 'arch': unix.machine, 'os_release': Path('/etc/os-release').read_text(),
        'uid': os.getuid(), 'gid': os.getgid(), 'groups': os.getgroups(),
        'account_existing': [user.pw_uid, user.pw_gid] if user else None,
        'group_existing': group.gr_gid if group else None,
        'units': {unit: properties(unit) for unit in (SLICE, *UNITS)},
        'cgroup_controllers': (CGROUP / 'cgroup.controllers').read_text().split(),
        'cgroup_mount': json.loads(command(['/usr/bin/findmnt', '-J', '-T', str(CGROUP)]).stdout),
        'current_cgroup': Path('/proc/self/cgroup').read_text(),
        'resources': {'cpu': len(os.sched_getaffinity(0)), 'meminfo': Path('/proc/meminfo').read_text(),
                      'available_bytes': fs.f_frsize * fs.f_bavail, 'available_inodes': fs.f_favail},
        'workspace': str(WORKSPACE), 'mount': json.loads(mount),
        'paths': {str(path): {'exists': os.path.lexists(path), 'symlink': path.is_symlink()}
                  for path in (STATE.parent, STATE, STATE / 'inputs', STATE / 'evidence', STATE / 'host-probe',
                               STATE / 'pre_setup_snapshot.json', STATE / 'resource-manifest.json')},
        'head': command(['/usr/bin/git', '-C', str(WORKSPACE), 'rev-parse', 'HEAD']).stdout.strip(),
        'git_status': command(['/usr/bin/git', '-C', str(WORKSPACE), 'status', '--porcelain=v1', '--branch']).stdout,
    }


def write_json(path, data):
    # Only the operator's mode-0700 control directory holds mutable ledgers.
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix=path.name+'.', delete=False) as out:
        pending = Path(out.name)
        json.dump(data, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    pending.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Ledger:
    def __init__(self, pre=None):
        self.path = STATE / 'resource-manifest.json'
        if pre is not None:
            self.data = {
                'schema': 'tizen-arm-smoke-admission/v1', 'id': uuid.uuid4().hex,
                'created_utc': pre['timestamp_utc'], 'machine_sha256': pre['machine_sha256'],
                'boot_id': pre['boot_id'], 'owner_uid': pre['uid'], 'workspace': str(WORKSPACE),
                'account_name': ACCOUNT, 'slice_name': SLICE, 'status': 'SETUP',
                'created': {'account': None, 'input_dir': None, 'inputs': {}, 'units': {}, 'slice': None},
                'pending': None, 'input_sources': {}, 'cleanup_order': ORDER, 'case_results': {},
                'resource_contract': RESOURCE_CONTRACT,
                'evidence': {'snapshot': 'pre_setup_snapshot.json', 'cases': 'evidence/',
                             'operator_state': str(STATE), 'disposition': 'retain for audit'},
            }
            self.save()
        else:
            require(self.path.is_file() and not self.path.is_symlink() and self.path.stat().st_uid == os.getuid(),
                    'A verified project resource ledger is required')
            self.data = json.loads(self.path.read_text())
            require(self.data['schema'] == 'tizen-arm-smoke-admission/v1' and self.data['owner_uid'] == os.getuid()
                    and self.data['workspace'] == str(WORKSPACE) and self.data['account_name'] == ACCOUNT
                    and self.data['slice_name'] == SLICE
                    and self.data['machine_sha256'] == digest(Path('/etc/machine-id'))
                    and uuid.UUID(hex=self.data['id']).hex == self.data['id'], 'Ledger identity differs')
        self.created = self.data['created']

    def save(self):
        write_json(self.path, self.data)

    def begin(self, operation):
        require(self.data['pending'] is None, f'Unresolved operation: {self.data["pending"]}')
        self.data['pending'] = operation
        self.save()

    def done(self):
        self.data['pending'] = None
        self.save()

    def description(self, unit):
        return f'Tizen ARM admission {self.data["id"]} {unit}'


def verify_account(record):
    user, group = get_user(), get_group()
    require(user and group and user.pw_uid == record['uid'] > 0 and user.pw_gid == group.gr_gid == record['gid']
            and user.pw_gecos == record['marker'] and user.pw_shell == SHELL
            and not group.gr_mem and os.getgrouplist(ACCOUNT, user.pw_gid) == [user.pw_gid]
            and all(item.pw_name == ACCOUNT or item.pw_uid != user.pw_uid and item.pw_gid != group.gr_gid
                    for item in pwd.getpwall()), 'Dedicated account or group identity does not match')
    return user


def checked_state():
    require(STATE.resolve() == STATE and STATE.is_dir() and file_id(STATE)[2:] == [os.getuid(), os.getgid(), 0o700],
            'State directory path, owner or mode does not match')
    return STATE


def staged_sources(ledger):
    paths = {}
    for name, (source, checksum, mode) in STAGED.items():
        path = WORKSPACE / source
        require(path.resolve() == path and path.is_file() and digest(path) == checksum, f'Input identity mismatch: {name}')
        require(not path.stat().st_mode & (stat.S_ISUID | stat.S_ISGID)
                and 'security.capability' not in os.listxattr(path), f'Unexpected privileged input: {name}')
        paths[name] = (path, checksum, mode)
    ledger.data['input_sources'] = {k: {'source': str(p), 'sha256': checksum, 'mode': mode}
                                    for k, (p, checksum, mode) in paths.items()}
    ledger.save()
    return paths


def setup(ledger):
    require(not any(ledger.created.values()) and ledger.data['pending'] is None,
            'Existing or uncertain system resources require verified cleanup before re-creation')
    require(not get_user() and not get_group()
            and not any(occupied(properties(unit)) for unit in (SLICE, *UNITS)), 'Resource name conflict before setup')
    require(ledger.data['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'Host rebooted after the snapshot; archive the verified-empty state and take a fresh snapshot')
    ledger.data.setdefault('resource_contract', RESOURCE_CONTRACT)
    ledger.data.setdefault('evidence', {'snapshot': 'pre_setup_snapshot.json', 'cases': 'evidence/',
                                       'operator_state': str(STATE), 'disposition': 'retain for audit'})
    administrator = command(['/usr/bin/true'], admin=True, check=False)
    sources = staged_sources(ledger)
    require(administrator.returncode == 0,
            'sudo -n unavailable. In your system terminal run sudo -v, then rerun setup.sh --resume as the same user.')
    require(os.uname().machine == 'x86_64' and set(('cpu', 'memory', 'pids')) <= set((CGROUP/'cgroup.controllers').read_text().split()),
            'x86-64 and unified memory/CPU/pids controllers required')
    # Restrict compilation temporaries to the existing operator-owned state directory.
    source = HERE / 'host_probe.c'
    helper = STATE / 'host-probe'
    require(not os.path.lexists(helper), 'Local host probe already exists')
    command(['/usr/bin/env', f'TMPDIR={STATE}', '/usr/bin/gcc', '-static', '-O2', '-Wall', '-Wextra',
             '-Werror', str(source), '-o', str(helper)])
    header = helper.read_bytes()[:20]
    require(header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') == 62,
            'Only the reviewed x86-64 host fixture is accepted')
    sources['host-probe'] = (helper, digest(helper), '0550')
    ledger.data['input_sources']['host-probe'] = {'source': str(helper), 'sha256': sources['host-probe'][1], 'mode': '0550'}
    ledger.data['host_source_sha256'] = digest(source)
    ledger.save()

    marker = 'tizen-arm-admission-' + ledger.data['id']
    ledger.begin('create account and group')
    command(['/usr/sbin/useradd', '--system', '--user-group', '--no-create-home', '--shell', SHELL,
             '--comment', marker, ACCOUNT], admin=True)
    user, group = get_user(), get_group()
    require(user and group, 'Created account/group not found')
    ledger.created['account'] = {'uid': user.pw_uid, 'gid': group.gr_gid, 'marker': marker, 'created_here': True}
    ledger.done()
    verify_account(ledger.created['account'])
    sudo_policy = command(['/usr/bin/sudo', '-n', '-l', '-U', ACCOUNT], admin=True, check=False)
    require(sudo_policy.returncode == 1 and 'not allowed to run sudo' in sudo_policy.stdout + sudo_policy.stderr,
            'No independent evidence the dedicated account is denied sudo')

    inputs = STATE / 'inputs'
    require(not os.path.lexists(inputs), 'Input directory is occupied')
    ledger.begin('create inputs')
    command(['/usr/bin/install', '-d', '-o', 'root', '-g', ACCOUNT, '-m', '0750', str(inputs)], admin=True)
    ledger.created['input_dir'] = file_id(inputs)
    ledger.done()
    require(inputs.is_dir() and inputs.resolve() == inputs and ledger.created['input_dir'][2:] == [0, group.gr_gid, 0o750],
            'Input directory ownership or mode differs')
    for name, (path, checksum, mode) in sources.items():
        target = inputs / name
        require(not os.path.lexists(target), f'Input name conflict: {name}')
        ledger.begin('copy ' + name)
        command(['/usr/bin/install', '-o', 'root', '-g', ACCOUNT, '-m', mode, str(path), str(target)], admin=True)
        observed = command(['/usr/bin/sha256sum', str(target)], admin=True).stdout.split()[0]
        require(observed == checksum, f'Input copy mismatch: {name}')
        ident = root_input_id(target)
        require(ident[2:] == [0, group.gr_gid, int(mode, 8)], f'Input owner/mode mismatch: {name}')
        require(not command(['/usr/sbin/getcap', str(target)], admin=True).stdout.strip(),
                f'Privileged file capability on staged file {name}')
        ledger.created['inputs'][name] = {'identity': ident, 'sha256': checksum}
        ledger.done()
    qualify(ledger, command, properties, occupied, verify_account)
    ledger.data['status'] = 'ACTIVE / CLEANUP_AVAILABLE'
    ledger.save()


def root_input_id(path):
    result = command(['/usr/bin/stat', '-c', '%d %i %u %g %a %F', str(path)], admin=True).stdout.strip().split(maxsplit=5)
    require(len(result) == 6 and result[5] == 'regular file', f'Input is not a regular file: {path.name}')
    return [*map(int, result[:4]), int(result[4], 8)]


def live_account(uid, admin):
    rows = command(['/usr/bin/ps', '-e', '-o', 'ruid=,euid=,suid=,pid='], admin=admin).stdout.splitlines()
    return [int(row[-1]) for line in rows if (row := line.split()) and str(uid) in row[:3]]


def mount_targets():
    lines = Path('/proc/self/mountinfo').read_text().splitlines()
    # Kernel escapes whitespace and backslashes in mountpoint fields.
    return [Path(line.split()[4].replace(r'\040', ' ').replace(r'\011', '\t').replace(r'\134', '\\')) for line in lines]


def verify_units(ledger):
    active = []
    require(set(ledger.created['units']) <= set(UNITS), 'Unit names in ledger do not match the project')
    for unit in UNITS:
        values = properties(unit)
        if not occupied(values):
            continue
        registered = ledger.created['units'].get(unit)
        require(registered and values.get('Transient') == 'yes' and values.get('Description') == ledger.description(unit)
                and values.get('InvocationID') == registered['invocation_id'], f'Unowned or replaced service: {unit}')
        if unit != ANCHOR and values.get('ControlGroup'):
            path = CGROUP / SLICE / unit
            require(registered.get('cgroup') == '/' + SLICE + '/' + unit == values['ControlGroup']
                    and path.is_dir() and file_id(path)[:2] == registered.get('identity'),
                    f'Replaced service cgroup: {unit}')
        active.append(unit)
    values = properties(SLICE)
    if occupied(values):
        saved = ledger.created['slice']
        path = CGROUP / SLICE
        require(saved and ledger.data['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                and values.get('ControlGroup') == '/' + SLICE and not values.get('FragmentPath')
                and not values.get('DropInPaths')
                and file_id(path)[:2] == saved['identity'], 'Slice cgroup identity does not match')
        children = set(path.iterdir())
        require(all(not item.is_dir() or item.name in ledger.created['units'] for item in children),
                'Slice contains an unexpected child boundary')
    else:
        require(not active and not (CGROUP / SLICE).exists(),
                'An unverified service or kernel cgroup remains without the registered slice')
    return active, occupied(values)


def verify_input_tree(ledger, admin):
    inputs = STATE / 'inputs'
    expected = ledger.created['inputs']
    require(set(expected) <= {*STAGED, 'host-probe'}, 'Ledger contains unexpected input paths')
    if not os.path.lexists(inputs):
        return []
    require(ledger.created['input_dir'] and not inputs.is_symlink()
            and inputs.resolve() == inputs and file_id(inputs) == ledger.created['input_dir']
            and not any(target.is_relative_to(inputs) for target in mount_targets()), 'Input directory identity or mount differs')
    if not admin:
        return list(expected)
    names = command(['/usr/bin/ls', '-1A', '--', str(inputs)], admin=True).stdout.splitlines()
    require(set(names) <= set(expected), 'Unexpected entries in root-owned input tree')
    for name in names:
        path = inputs / name
        observed = command(['/usr/bin/sha256sum', str(path)], admin=True).stdout.split()[0] if (
            root_input_id(path) == expected[name]['identity']) else None
        require(observed == expected[name]['sha256'], f'Replaced input: {name}')
    return names


def pending_is_absent(pending):
    if pending == 'create account and group':
        return not get_user() and not get_group()
    if pending == 'create inputs':
        return not os.path.lexists(STATE / 'inputs')
    if pending.startswith('copy ') and (name := pending.removeprefix('copy ')) in {*STAGED, 'host-probe'}:
        directory = STATE / 'inputs'
        result = command(['/usr/bin/ls', '-1A', '--', str(directory)], admin=True)
        return name not in result.stdout.splitlines()
    if pending == f'create {ANCHOR} and {SLICE}':
        return not (CGROUP / SLICE).exists() and not any(occupied(properties(unit)) for unit in (ANCHOR, SLICE))
    if pending.startswith('start ') and (unit := pending.removeprefix('start ')) in UNITS:
        return not occupied(properties(unit)) and not (CGROUP / SLICE / unit).exists()
    return False


def rollback(ledger, apply):
    pending = ledger.data['pending']
    require(pending is None or pending_is_absent(pending),
            'A pending object exists or cannot be attributed safely; review the journal before rollback')
    inputs = STATE / 'inputs'
    services, slice_live = verify_units(ledger)
    record = ledger.created['account']
    user, group = get_user(), get_group()
    if user:
        require(record and record['created_here'], 'Account was not created by this ledger')
        verify_account(record)
    elif group:
        require(record and record['created_here'] and group.gr_gid == record['gid'] and not group.gr_mem
                and all(entry.pw_gid != group.gr_gid for entry in pwd.getpwall()), 'Unowned or replaced group')
    paths = verify_input_tree(ledger, os.path.lexists(inputs))
    print(json.dumps({'mode': 'apply' if apply else 'dry-run', 'services': services, 'slice': SLICE if slice_live else None,
                      'account': ACCOUNT if user else None, 'group': ACCOUNT if group else None,
                      'input_entries': paths, 'input_directory': str(inputs) if os.path.lexists(inputs) else None,
                      'retaining': ['pre_setup_snapshot.json', 'resource-manifest.json', 'workspace evidence']}, indent=2))
    if not apply:
        return
    if pending is not None:
        ledger.data['reconciled_absent_operation'] = pending
        ledger.done()
    ledger.data['status'] = 'ROLLBACK_IN_PROGRESS'
    ledger.save()
    for unit in (item for item in services if item != ANCHOR):
        command(['/usr/bin/systemctl', '--system', 'stop', unit], admin=True)
        if properties(unit).get('ActiveState') == 'failed':
            command(['/usr/bin/systemctl', '--system', 'reset-failed', unit], admin=True)
    if slice_live:
        path = CGROUP / SLICE
        require('populated 0' in (path / 'cgroup.events').read_text().splitlines(),
                'Slice still has tasks or its empty state is unobservable')
    if record:
        require(not live_account(record['uid'], admin=True), 'Dedicated UID still has live processes')
    if ANCHOR in services:
        command(['/usr/bin/systemctl', '--system', 'stop', ANCHOR], admin=True)
    if slice_live:
        if occupied(properties(SLICE)):
            command(['/usr/bin/systemctl', '--system', 'stop', SLICE], admin=True)
    require(not occupied(properties(SLICE)) and not (CGROUP / SLICE).exists(), 'Slice did not stop cleanly')
    require(not any(occupied(properties(unit)) for unit in UNITS), 'A dedicated service still exists or is active')
    for name in paths:
        command(['/usr/bin/rm', '--', str(inputs / name)], admin=True)
        ledger.data.setdefault('removed_inputs', []).append(name)
        ledger.save()
    if os.path.lexists(inputs):
        command(['/usr/bin/rmdir', '--', str(inputs)], admin=True)
    if user:
        verify_account(record)
        require(not live_account(record['uid'], admin=True), 'Dedicated UID still has live processes')
        command(['/usr/sbin/userdel', ACCOUNT], admin=True)
    group = get_group()
    if group:
        require(record and group.gr_gid == record['gid'] and not group.gr_mem
                and all(entry.pw_gid != group.gr_gid for entry in pwd.getpwall()), 'Dedicated group changed')
        command(['/usr/sbin/groupdel', ACCOUNT], admin=True)
    require(not get_user() and not get_group() and not os.path.lexists(inputs), 'Rollback incomplete')
    ledger.data['rollback_observation'] = {'dedicated_account': 'absent', 'dedicated_group': 'absent',
                                           'slice': 'absent', 'units': 'absent', 'input_directory': 'absent'}
    ledger.data['status'] = 'ROLLED_BACK'
    ledger.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('setup').add_argument('--resume', action='store_true')
    clean = sub.add_parser('cleanup').add_mutually_exclusive_group()
    clean.add_argument('--dry-run', action='store_true')
    clean.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    updating = args.action == 'setup' or args.apply
    try:
        require(os.getuid() == os.geteuid() != 0, 'Run as the workspace owner, using native sudo for narrow commands')
        require(STATE.parent.resolve() == STATE.parent and STATE.parent.is_dir(), 'Use the existing workspace-local backup directory')
        pre = None
        if args.action == 'setup' and not args.resume:
            require(not os.path.lexists(STATE), 'State directory already exists; inspect it before any resume')
            pre = snapshot()
            conflicts = [unit for unit, values in pre['units'].items() if occupied(values)]
            if pre['account_existing']:
                conflicts.append('account ' + ACCOUNT)
            if pre['group_existing'] is not None:
                conflicts.append('group ' + ACCOUNT)
            if (CGROUP / SLICE).exists():
                conflicts.append('cgroup ' + SLICE)
            require(not conflicts, 'Resource name conflicts: ' + ', '.join(conflicts))
            STATE.mkdir(mode=0o700)
        checked_state()
        with (STATE / '.lock').open('a' if updating else 'r') as lock:
            fcntl.flock(lock, (fcntl.LOCK_EX if updating else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            ledger = Ledger(pre)
            try:
                if pre is not None:
                    write_json(STATE / 'pre_setup_snapshot.json', pre)
                if args.action == 'setup':
                    setup(ledger)
                    print(ledger.data['status'])
                else:
                    rollback(ledger, args.apply)
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as e:
                if updating:
                    ledger.data['status'] = 'BLOCKED' if args.action == 'setup' else 'ROLLBACK_BLOCKED'
                    ledger.data['last_error'] = str(e) or 'Interrupted'
                    ledger.save()
                raise
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as e:
        reason = str(e) or 'Interrupted'
        print(f'Blocked: {reason}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
