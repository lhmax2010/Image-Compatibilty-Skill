"""Match direct observations against the existing Phase 7A resolver."""
from collections import Counter
import time

from .core import VERSION, read_manifest
from .impact_source import virtual_path
from .linker import dependency_checks
from .report_io import canonical, digest, ResourceLimit

LABEL = 'baseline consumers on candidate'
REQUIREMENTS = ('DT_NEEDED:', 'import:', 'version:')
FAILURES = {'missing_provider', 'unresolvable_provider', 'missing_version',
            'missing_symbol', 'symbol_type_mismatch'}


class ReplayLimit(Exception):
    pass


def indexed_checks(rows, root):
    direct = [row for row in rows if row.get('consumer_image') == 'baseline'
              and row.get('root_consumer_image') == 'baseline'
              and row.get('consumer_path') == row.get('root_consumer') == root]
    counts = Counter(row['check_id'] for row in direct)
    if any(row['check_id'] == 'dynamic loader' and row['resolution'] != 'verified' for row in direct):
        return {}
    return {row['check_id']: row for row in direct if counts[row['check_id']] == 1
            and row['check_id'].startswith(REQUIREMENTS)}


def compare_observation(original, current):
    fields = ('id', 'dimension', 'interface', 'component', 'status', 'check_id',
              'consumer_path', 'consumer_image', 'root_consumer', 'root_consumer_image',
              'provider_path', 'baseline', 'candidate', 'resolution', 'detection_method')
    return all(original.get(key) == current.get(key) for key in fields)


def observations(paths, roots, check):
    left, right = [read_manifest(path) for path in paths]
    if any(m.get('collector_version') != VERSION for m in (left, right)):
        raise ValueError('Replay requires matching Phase 7A collector provenance on both sides')
    for manifest in (left, right):
        for section in ('elf_objects', 'filesystem'):
            paths_in_image = {item['path'] for item in manifest.get(section, [])}
            if len(paths_in_image) != len(manifest.get(section, [])):
                raise ValueError(f'Duplicate replay path in {section}')
    objects = {obj['path']: obj for obj in left['elf_objects']}
    replay_started = time.monotonic()
    for path in roots:
        if path not in objects or not virtual_path(path):
            raise ValueError(f'Replay root is not a recorded baseline ELF: {path}')
        if time.monotonic() - replay_started > 600:
            raise ResourceLimit('Replay exceeded 10 minute budget')
        root = objects[path]
        started = time.monotonic()
        steps = 0

        def checkpoint():
            nonlocal steps
            steps += 1
            if steps > 100_000 or time.monotonic() - started > 5:
                raise ReplayLimit()
            if steps % 256 == 0:
                check()

        try:
            before = indexed_checks(dependency_checks(left, 'baseline-control', [root],
                                                       consumer_manifest=left, checkpoint=checkpoint), path)
            after = indexed_checks(dependency_checks(right, LABEL, [root],
                                                      consumer_manifest=left, checkpoint=checkpoint), path)
        except ReplayLimit:
            yield path, None
            continue
        yield path, (before, after)


def qualified(before, after):
    if not before or before['resolution'] != 'verified' or before['status'] != 'COMPATIBLE':
        return None
    if before['baseline'] != after['baseline'] or not virtual_path(before.get('provider_path')):
        return None
    if after['status'] == 'INCOMPATIBLE' and after['resolution'] in FAILURES:
        return 'CONFIRMED_CONTRACT_IMPACT'
    if after['status'] == 'COMPATIBLE' and after['resolution'] == 'verified' and virtual_path(after.get('provider_path')):
        return 'NO_BREAK_OBSERVED'
    return None


def replay_proof(before, after):
    # Keep the replay identity and resolution details separate from original Finding IDs.
    keys = ('check_id', 'consumer_path', 'root_consumer', 'provider_path', 'resolution', 'status')
    return canonical({
        'policy': VERSION, 'scope': 'same baseline root under each recorded loader environment',
        'baseline': {k: before[k] for k in keys} | {'observation_sha256': digest(before)},
        'candidate': {k: after[k] for k in keys} | {'finding_id': after['id']},
        'requirement': before['baseline'],
    })
