"""RPM queries use a temporary database copy, never an image's live RPM DB."""
from __future__ import annotations

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from typing import Any
from .core import Tools, limitation
from .images import Image


def parse_rpm_xml(text: str) -> list[dict[str, Any]]:
    root = ET.fromstring('<packages>' + text + '</packages>')
    records = []
    for package in root.findall('rpmHeader'):
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
        record['files'] = sorted(dirs[int(indices[i])] + name for i, name in enumerate(bases) if i < len(indices) and int(indices[i]) < len(dirs))
        records.append(record)
    return records


def collect_packages(image: Image, tools: Tools, workspace: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rpm = tools.path('rpm')
    sources = sorted(p for p in image.root.rglob('*.rpm') if not p.is_symlink() and p.is_file())
    # Path.resolve() on image symlinks is intentionally avoided.
    db = next((image.resolve(v) for v in ('/usr/lib/sysimage/rpm', '/var/lib/rpm')
               if image.resolve(v) and image.resolve(v).is_dir()), None)
    if not sources and not db:
        return [], [limitation('packages', 'No RPM database or RPM package collection found; package format not assumed.')]
    if not rpm:
        return [], [limitation('packages', 'rpm tool unavailable')]
    commands = [[rpm, '-qp', '--xml', str(p)] for p in sources]
    if db:
        copy = workspace / ('rpmdb-' + str(len(list(workspace.glob('rpmdb-*')))))
        copy.mkdir()
        for entry in db.iterdir():
            if entry.is_file() and not entry.is_symlink():
                shutil.copyfile(entry, copy / entry.name)
        commands.append([rpm, '--dbpath', str(copy), '-qa', '--xml'])
    records: dict[tuple[str, str], dict[str, Any]] = {}
    limits = []
    for command in commands:
        result = tools.run(command)
        if result['returncode'] or result['stdout_truncated']:
            limits.append(limitation('packages', 'RPM query failed: ' + result['stderr'], result['stdout_evidence']))
            continue
        try:
            for record in parse_rpm_xml(result['stdout']):
                record['evidence'] = [result['stdout_evidence'], result['stderr_evidence']]
                records[(record['name'], record['arch'])] = record
        except (ET.ParseError, ValueError, IndexError, KeyError) as exc:
            limits.append(limitation('packages', f'RPM XML parse failed: {exc}'))
    return sorted(records.values(), key=lambda x: (x['name'], x['arch'])), limits
