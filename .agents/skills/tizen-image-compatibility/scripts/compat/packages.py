"""RPM queries use a temporary database copy, never an image's live RPM DB."""
from __future__ import annotations

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from typing import Any
from .core import Tools, limitation, canonical, digest
from .images import Image


def parse_rpm_header(package):
    tags = {tag.attrib['name'].lower(): [v.text or '' for v in tag] for tag in package}
    def first(key: str) -> str:
        return tags.get(key, [''])[0]
    record: dict[str, Any] = {key: first(key) for key in ('name', 'epoch', 'version', 'release', 'arch')}
    for field, prefix in (('provides', 'provide'), ('requires', 'require'), ('conflicts', 'conflict'), ('obsoletes', 'obsolete')):
        names = tags.get(prefix + 'name', [])
        flags = tags.get(prefix + 'flags', [])
        versions = tags.get(prefix + 'version', [])
        record[field] = sorted([{'name': name, 'flags': flags[i] if i < len(flags) else '',
            'version': versions[i] if i < len(versions) else ''} for i, name in enumerate(names)], key=lambda v: v['name'])
    dirs = tags.get('dirnames', [])
    indices = tags.get('dirindexes', [])
    bases = tags.get('basenames', [])
    if len(indices) != len(bases) or any(not 0 <= int(i) < len(dirs) for i in indices):
        raise ValueError('Incomplete RPM file ownership arrays')
    record['files'] = sorted(dirs[int(indices[i])] + name for i, name in enumerate(bases))
    record['epoch'] = record['epoch'] or '0'
    record['identity'] = canonical([record[k] for k in ('name', 'epoch', 'version', 'release', 'arch')])
    return record


def parse_rpm_xml(text: str) -> list[dict[str, Any]]:
    root = ET.fromstring('<packages>' + text + '</packages>')
    return [parse_rpm_header(package) for package in root.findall('rpmHeader')]


def parse_rpm_evidence(path: Path) -> list[dict[str, Any]]:
    """Read full raw RPM XML beyond the tool's bounded stdout preview."""
    parser = ET.XMLPullParser(events=('end',))
    parser.feed(b'<packages>')
    records = []
    with path.open('rb') as stream:
        while chunk := stream.read(64 * 1024):
            parser.feed(chunk)
            for _, element in parser.read_events():
                if element.tag == 'rpmHeader':
                    records.append(parse_rpm_header(element))
                    element.clear()
    parser.feed(b'</packages>')
    parser.close()  # A malformed/truncated raw document must not yield a complete inventory.
    return records


def collect_package_inventory(image: Image, tools: Tools, workspace: Path):
    rpm = tools.path('rpm')
    archives = ([image.root] if image.format == 'rpm-collection' and image.root.is_file() else
                sorted(p for p in image.root.rglob('*.rpm') if not p.is_symlink() and p.is_file()))
    db = next((image.resolve(v) for v in ('/usr/lib/sysimage/rpm', '/var/lib/rpm')
               if image.resolve(v) and image.resolve(v).is_dir()), None)
    inventory = {'status': 'UNKNOWN', 'installed_count': None, 'source_kind': 'installed_rpmdb',
                 'reason': 'RPM database unavailable', 'evidence': [], 'archive_status': 'NOT_APPLICABLE', 'archive_count': 0}
    records = []; available = []; limits = []
    commands = []
    database_present = db and any((db / name).is_file() and not (db / name).is_symlink()
                                  for name in ('rpmdb.sqlite', 'Packages', 'Packages.db', 'data.mdb'))
    if rpm:
        commands += [('rpm_archive', str(p), [rpm, '-qp', '--xml', str(p)]) for p in archives]
        if database_present:
            copy = workspace / ('rpmdb-' + digest(str(db).encode())[:16])
            copy.mkdir(exist_ok=True)
            try:
                for entry in db.iterdir():
                    if entry.is_file() and not entry.is_symlink(): shutil.copyfile(entry, copy / entry.name)
                commands.append(('installed_rpmdb', str(db), [rpm, '--dbpath', str(copy), '-qa', '--xml']))
            except OSError as exc:
                inventory.update(reason='RPM database snapshot failed: ' + str(exc), execution='FAILED')
        elif db:
            inventory['reason'] = 'RPM database directory has no recognized database; not an empty installed inventory'
    else:
        inventory['reason'] = 'rpm tool unavailable'
        if database_present:
            inventory['execution'] = 'FAILED'
    archive_failures = 0
    for kind, source, command in commands:
        result = tools.run(command)
        ev = [result['stdout_evidence'], result['stderr_evidence']]
        try:
            if result['returncode']:
                raise ValueError('query failed: ' + (result.get('error') or result['stderr'] or
                                                     f"exit {result['returncode']}"))
            raw = tools.output / result['stdout_evidence']
            if raw.is_file():
                parsed = parse_rpm_evidence(raw)
            elif result['stdout_truncated']:
                raise ValueError('Truncated query preview without full raw evidence')
            else:
                parsed = parse_rpm_xml(result['stdout'])
            for record in parsed:
                record.update(evidence=ev, collection_status='COMPLETE',
                              provenance={'kind': kind, 'source': source, 'query': result['argv']})
            if kind == 'installed_rpmdb':
                records.extend(parsed)
                inventory.update(status='COMPLETE', installed_count=len(parsed), reason='', evidence=ev,
                                 execution='COMPLETE')
            else: available.extend(parsed)
        except (ET.ParseError, ValueError, IndexError, KeyError, OSError) as exc:
            if kind == 'installed_rpmdb':
                inventory.update(reason='RPM installed inventory failed: ' + str(exc), evidence=ev, execution='FAILED')
            else: archive_failures += 1
            limits.append(limitation('packages', f'{kind} query/parse failed: {exc}', source))
    if inventory['status'] != 'COMPLETE': limits.append(limitation('packages', inventory['reason']))
    if archives:
        inventory.update(archive_status='PARTIAL' if archive_failures or not rpm else 'COMPLETE', archive_count=len(available))
    # Keep parallel installed versions/architectures and archive records separate; never overwrite by (name, arch).
    return sorted(records, key=lambda p: p['identity']), sorted(available, key=lambda p: p['identity']), inventory, limits


def collect_packages(image: Image, tools: Tools, workspace: Path):
    """Legacy collector API: records carry explicit provenance, including archive-only inputs."""
    installed, archives, inventory, limits = collect_package_inventory(image, tools, workspace)
    if image.format == 'rpm-collection':
        limits = [x for x in limits if x['reason'] != inventory['reason']]
        return archives, limits
    return installed, limits
