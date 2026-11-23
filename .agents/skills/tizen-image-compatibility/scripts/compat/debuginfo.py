"""Build-ID verified split DWARF lookup; never installs a debuginfo RPM.
Extracted debuginfo RPM trees can be supplied as additional read-only roots.
"""
from pathlib import Path
import re
import shutil
from .core import canonical, finding, digest
from .elf import collect_elf
from .images import Image

DWARF_INTERFACE = 'DWARF type/layout ABI'
DWARF_METHOD = 'libabigail abidiff'


def debug_source(obj, image, additional_roots, tools):
    if obj.get('debug_info'):
        path = image.resolve(obj['path'])
        if path is not None:
            return {'kind': 'embedded', 'path': str(path),
                    'virtual_path': '/' + path.relative_to(image.root).as_posix(), 'location': 'image'}
        return None
    build_id = obj.get('build_id', '')
    if not re.fullmatch(r'[0-9a-fA-F]{8,128}', build_id):
        return None
    suffix = '/.build-id/' + build_id[:2] + '/' + build_id[2:] + '.debug'
    roots = [image]
    for root in additional_roots:
        if Path(root).is_dir():
            roots.append(Image(Path(root), tools.output, tools, 'debuginfo'))
    for root in roots:
        for virtual in ('/usr/lib/debug' + suffix, suffix, '/usr/lib/debug' + obj['path'] + '.debug'):
            path = root.resolve(virtual)
            if path and path.is_file():
                debug = collect_elf(path, virtual, tools, 'quick')
                if debug.get('complete') and debug.get('build_id') == build_id and debug.get('debug_info'):
                    return {'kind': 'split-build-id', 'path': str(path),
                            'virtual_path': '/' + path.relative_to(root.root).as_posix(),
                            'location': 'image' if root is image else 'debuginfo',
                            'build_id': build_id, 'evidence': debug.get('evidence', [])}
    return None


def report_source(source):
    if source is None:
        return None
    return {k: v for k, v in source.items() if k not in ('virtual_path', 'path')} | {'path': source['virtual_path']}


def advanced_abi(a, b, roots, tools):
    binary = tools.path('abidiff')
    stage_root = tools.output.resolve() / 'abi-inputs'
    tools.aliases[str(stage_root)] = '<abi-inputs>'
    right = {o['path']: o for o in b['elf_objects']}
    out = []
    for obj in a['elf_objects']:
        # ET_REL debug objects are not runtime providers.
        if obj.get('type', '').startswith('REL'):
            continue
        other = right.get(obj['path'])
        if not other and obj.get('soname'):
            matches = [x for x in right.values() if x.get('soname') == obj['soname']]
            other = matches[0] if len(matches) == 1 else None
        sources = []
        for label, current, image in zip(('baseline', 'candidate'), (obj, other), roots):
            sources.append(debug_source(current, image, tools.config['debuginfo']['roots'].get(label, []), tools) if current else None)
        reason = ('Candidate ELF unavailable' if other is None else 'abidiff unavailable' if not binary else
                  'Usable embedded DWARF or matching Build-ID debuginfo unavailable' if not all(sources) else '')
        status = 'UNKNOWN'; ev = []; output = reason; code = None
        fingerprint = None
        if not reason:
            inputs = []; flags = []
            for n, (current, image, source) in enumerate(zip((obj, other), roots, sources), 1):
                original = image.resolve(current['path'])
                if not original:
                    reason = 'ELF file unavailable'; break
                stage = stage_root / digest((obj['path'] + str(n)).encode())
                stage.mkdir(parents=True, exist_ok=True)
                local = stage / 'object.elf'
                shutil.copyfile(original, local)
                inputs.append(str(local))
                debugdir = stage / 'debug'; debugdir.mkdir(exist_ok=True)
                if source['kind'] == 'split-build-id':
                    bid = source['build_id']
                    target = debugdir / '.build-id' / bid[:2] / (bid[2:] + '.debug')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source['path'], target)
                flags += ['--debug-info-dir' + str(n), str(debugdir)]
            if not reason:
                result = tools.run([binary, '--no-default-suppression', '--fail-no-debug-info', *flags, *inputs])
                code = result['returncode']; output = tools.normalize(result['stdout'])
                ev = [result['stdout_evidence'], result['stderr_evidence']]
                status = 'UNKNOWN' if code < 0 or code & 3 or result['stdout_truncated'] else 'INCOMPATIBLE' if code & 8 else 'UNKNOWN' if code & 4 else 'COMPATIBLE' if code == 0 else 'UNKNOWN'
                if not result['stdout_truncated'] and not result.get('stderr_truncated'):
                    fingerprint = [digest(text.encode()) for text in
                                   (output, tools.normalize(result.get('stderr', '')), tools.normalize(result.get('error') or ''))]
            else:
                output = reason
        old_source, new_source = map(report_source, sources)
        item = finding('abi', obj['path'], DWARF_INTERFACE, {'debug': old_source},
                       {'debug': new_source, 'returncode': code, 'report': output},
                       status, 'HIGH' if status == 'INCOMPATIBLE' else 'INFO', DWARF_METHOD, ev,
                       impact='Coverage concerns externally reachable DWARF types, not every language/runtime behavior. Exit bit 4 alone is a difference, not a confirmed break.')
        if fingerprint:
            # Raw, content-addressed files may contain staging paths. Keep their
            # original references and derive identity from the complete normalized diagnostics.
            item['dwarf_evidence_fingerprint'] = fingerprint
            logical = {k: v for k, v in item.items() if k not in ('id', 'evidence')}
            item['id'] = 'TC-' + digest(canonical(logical).encode())[:16]
        item['coverage_unit'] = 'type-layout:' + obj['path']
        item['debug_coverage'] = {'baseline': old_source, 'candidate': new_source, 'reason': reason}
        out.append(item)
    return out
