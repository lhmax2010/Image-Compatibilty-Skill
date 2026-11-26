"""Rootless, offline container adapter for explicitly enrolled test images."""
from pathlib import Path
from uuid import uuid4
import os

from .core import InputError, defer_console_interrupt, hash_file


GUEST_ENTRY = '''
target=$1
expected=$2
marker=$3
peer=$4
peer_hash=$5
shift 5
checksum=$(sha256sum "$target") || exit 125
[ "${checksum%% *}" = "$expected" ] || exit 125
[ -x "$target" ] || exit 125
if [ -n "$peer" ]; then
    checksum=$(sha256sum "$peer") || exit 125
    [ "${checksum%% *}" = "$peer_hash" ] || exit 125
fi
printf '%s\\n' "$marker" >&2
exec "$target" "$@"
'''


def podman_run(spec, source, target, is_artifact, arguments, tools, *, forbidden_root, companion=None):
    """Return actual target stages while retaining all CLI evidence via Tools."""
    stages = {'deployment_status': 'UNKNOWN', 'execution_status': 'UNKNOWN', 'behavior_status': 'UNKNOWN'}
    result = {'stages': stages, 'stdout': '', 'stderr': '', 'returncode': -1,
              'runtime_reason': 'Container prerequisites unavailable', 'runtime_evidence': []}
    if not tools.config['runtime']['authorized']:
        result['runtime_reason'] = 'Runtime authorization missing'
        return result
    controller = Path(spec['podman']).resolve()
    storage, run_root = (Path(spec[key]).resolve() for key in ('storage_root', 'run_root'))
    forbidden = Path(forbidden_root).resolve()
    if any(p.is_relative_to(forbidden) for p in (controller, storage, run_root)) or controller.is_relative_to(tools.output / 'build'):
        raise InputError('Container controller and storage must be outside input image and generated artifact paths')
    if not controller.is_file() or not os.access(controller, os.X_OK) or not all(p.is_dir() for p in (storage, run_root)):
        return result
    if storage == run_root or storage.is_relative_to(run_root) or run_root.is_relative_to(storage):
        raise InputError('Podman persistent and transient storage must be separate directories')
    base = [str(controller), '--remote=false', '--root', str(storage), '--runroot', str(run_root)]
    timeout = int(tools.config['runtime']['timeout_seconds'])
    def execute(argv, seconds):
        command = tools.run([*base, *argv], timeout=seconds, max_capture_bytes=1024 * 1024)
        result['runtime_evidence'] += [command['stdout_evidence'], command['stderr_evidence']]
        return command
    info = execute(['info', '--format', '{{.Host.Security.Rootless}}'], min(timeout, 15))
    if info['returncode'] != 0 or info['stdout'].strip() != 'true':
        result['runtime_reason'] = 'A local rootless Podman runtime is required'
        return result
    image = execute(['image', 'inspect', '--format', '{{.Id}}', spec['image']], min(timeout, 15))
    if image['returncode'] or image['stdout'].strip().removeprefix('sha256:') != spec['image'].removeprefix('sha256:'):
        result['runtime_reason'] = 'Pinned local container image identity could not be verified'
        return result
    if not source or not source.is_file():
        result['runtime_reason'] = 'Artifact or recorded target command absent'
        return result
    expected = hash_file(source)
    token = uuid4().hex
    name, marker = 'tizen-compat-' + token, 'tizen-compat-verified:' + token
    command = ['run', '--name', name, '--pull=never', '--network=none', '--read-only',
               '--read-only-tmpfs=false', '--image-volume=ignore', '--security-opt=no-new-privileges',
               '--cap-drop=all', '--http-proxy=false', '--systemd=false', '--pids-limit=64',
               '--memory=256m', '--user=65534:65534', '--ipc=private', '--pid=private',
               '--env=LC_ALL=C', '--env=TZ=UTC', '--env=TMPDIR=/tmp', '--env=HOME=/tmp',
               '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777',
               '--ulimit=fsize=1048576:1048576', '--timeout', str(timeout), '--entrypoint=/bin/sh']
    peer, peer_hash = '', ''
    if is_artifact:
        target = '/compat/probe'
        mounts = [(source, target)]
        if companion:
            peer = '/compat/' + companion.name
            peer_hash = hash_file(companion)
            mounts.append((companion, peer))
        for local, guest in mounts:
            if any(c in str(local) for c in ',\n\r'):
                raise InputError('Probe path is unsuitable for a Podman mount')
            command.extend(['--mount', f'type=bind,source={local},target={guest},ro'])
    try:
        runtime = execute([*command, spec['image'], '-ceu', GUEST_ENTRY, 'compat', target, expected, marker, peer, peer_hash,
                           *arguments], timeout + 5)
    finally:
        # Reap the exact named container even when the local CLI was interrupted.
        with defer_console_interrupt() as interrupted:
            cleanup = execute(['rm', '--force', '--time=0', name], 10)
        if interrupted():
            raise KeyboardInterrupt
    result.update(runtime_environment={'backend': 'podman-rootless', 'image_id': spec['image'], 'id': spec['id'],
                                       'isolation': 'container-with-host-kernel'},
                  expected_artifact_sha256=expected, stdout_evidence=runtime['stdout_evidence'], stderr_evidence=runtime['stderr_evidence'])
    if cleanup['returncode'] != 0:
        result['runtime_reason'] = 'Container cleanup could not be verified'
        return result
    prefix = marker + '\n'
    if (not runtime['stderr'].startswith(prefix) or hash_file(source) != expected
            or companion and hash_file(companion) != peer_hash):
        result['runtime_reason'] = 'Guest digest/startup marker is missing or artifact changed'
        return result
    stages['deployment_status'] = 'SUCCESS'
    code = runtime['returncode']
    if (runtime['error'] or runtime['stdout_truncated'] or runtime['stderr_truncated']
            or code in (-1, 124, 125, 126, 127, 137, 143)):
        result['runtime_reason'] = 'Target execution incomplete, unavailable, or forcibly terminated'
        return result
    stages['execution_status'] = 'SUCCESS'
    result.update(stdout=runtime['stdout'], stderr=runtime['stderr'][len(prefix):], returncode=code,
                  receipt_sha256=expected, companion_sha256=peer_hash or None, runtime_reason='',
                  crash={'exit_code': code, 'possible_signal': code - 128} if 128 < code < 193 else None)
    return result
