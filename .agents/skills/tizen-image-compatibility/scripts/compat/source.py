"""Conservative C/C++ token normalization, without claiming a full C parser."""
from __future__ import annotations

import re
import posixpath
from typing import Any

LEX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|(?:[A-Za-z_]\w*)|(?:\d+(?:\.\d+)?)|(?:>>=|<<=|->\*|\.\.\.|##|::|->|\+\+|--|&&|\|\||==|!=|<=|>=|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^=|\.\*)|[^\s]', re.S)


def tokens(text: str) -> list[str]:
    return [m[0] for m in LEX.finditer(text) if not m[0].startswith(('/*', '//'))]


def normalize_text(text: str, build_paths: bool = True) -> str:
    lines = []
    for line in text.replace('\r\n', '\n').splitlines():
        if re.match(r'^\s*(#|;)\s*(Generated (on|at)|Build (date|time)|Timestamp):', line, re.I):
            continue
        if build_paths and re.match(r'^\s*#\s*(?:line\s+)?\d+\s+"', line):
            continue
        lines.append(line.rstrip())
    return '\n'.join(lines).strip()


def parse_header(text: str) -> dict[str, Any]:
    text = text.replace('\\\n', '')
    clean = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*',
                   lambda m: '\n' * m[0].count('\n') + ' ' if m[0].startswith(('/',)) else m[0], text, flags=re.S)
    macros, includes, conditions, directives = {}, [], [], []
    preprocessor_complete = True
    body = []
    for line in clean.splitlines():
        match = re.match(r'\s*#\s*define\s+(\w+)(.*)', line)
        if match:
            macros[match[1]] = {'kind': 'function' if match[2].startswith('(') else 'object',
                               'replacement': tokens(match[2])}
        match = re.match(r'\s*#\s*include\s*[<"]([^>"]+)', line)
        if match:
            includes.append(match[1])
        directive = re.fullmatch(r'\s*#\s*include\s*(?:"([^"\n]+)"|<([^>\n]+)>)\s*', line)
        if directive:
            directives.append({'name': directive[1] or directive[2], 'quoted': directive[1] is not None})
        elif re.match(r'\s*#', line):
            preprocessor_complete = False
        if re.match(r'\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b', line):
            conditions.append(tokens(line))
        if not re.match(r'\s*#', line):
            body.append(line)
    body_text = '\n'.join(body)
    declarations: dict[str, list[str]] = {}
    # Only unambiguous simple prototypes. All remaining types/inline/templates are
    # retained as tokens and conservatively classified when changed.
    for match in re.finditer(r'(?:^|[;}])\s*((?:[\w*]+\s+)+)([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;', body_text, re.M):
        declarations[match[2]] = tokens(match[1] + match[2] + '(' + match[3] + ')')
    reasons = []
    if re.search(r'__(GNUC|clang|llvm)', text):
        reasons.append('compiler-conditional')
    if re.search(r'__(aarch64|arm|x86_64|i386|LP64)|__SIZEOF_', text):
        reasons.append('architecture-conditional')
    if conditions:
        reasons.append('feature-conditional')
    if re.search(r'VERSION|API_LEVEL', text):
        reasons.append('SDK-version-macros')
    # Deliberately small proof language: plain built-in C prototypes only.
    # Typedefs, attributes, macros, C++ linkage, inline bodies etc. need a compiler.
    prototype = re.compile(r'\s*((?:[\w*]+\s+)+)([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;')
    primitive = {'void', 'char', 'short', 'int', 'long', 'float', 'double', 'signed', 'unsigned', 'const', 'volatile', '_Bool', '*'}
    def builtin_type(parts):
        base, _, pointer = ' '.join(parts).partition(' *')
        base = ' '.join(t for t in base.split() if t not in ('const', 'volatile'))
        return bool(re.fullmatch(r'(?:void|_Bool|float|double|long double|(?:(?:signed|unsigned) )?(?:char|short(?: int)?|int|long(?: long)?(?: int)?)|signed|unsigned)', base)
                    and all(t in ('*', 'const', 'volatile') for t in pointer.split()))
    remaining = prototype.sub('', body_text)
    simple = not tokens(remaining) and preprocessor_complete and not conditions and not macros
    seen_names = set()
    for match in prototype.finditer(body_text):
        simple &= match[2] not in seen_names
        seen_names.add(match[2])
        declarations[match[2]] = tokens(match[1] + match[2] + '(' + match[3] + ')')
        simple &= builtin_type(tokens(match[1]))
        parameter_names = set()
        for arg in match[3].split(','):
            parts = tokens(arg)
            named = False
            if parts and parts[-1] not in primitive and re.fullmatch(r'[A-Za-z_]\w*', parts[-1]):
                named = True
                simple &= parts[-1] not in parameter_names
                parameter_names.add(parts[-1])
                parts = parts[:-1]  # optional parameter name
            simple &= bool(parts) and builtin_type(parts) and not (parts == ['void'] and (named or ',' in match[3]))
    return {'tokens': tokens(clean), 'body_tokens': tokens(body_text), 'macros': macros,
            'includes': sorted(set(includes)), 'conditions': conditions,
            'include_directives': directives, 'simple_declarations_complete': bool(simple),
            'declarations': declarations, 'context_hints': reasons,
            'parser': 'conservative C/C++ lexical declarations; no preprocessing/type resolution'}


def header_inventory_complete(manifest, path):
    """Explicit domain inventory evidence, independent of lexical/semantic coverage."""
    if manifest.get('header_inventory_complete') is not True:
        return False
    if manifest.get('collection_complete') is False:
        return False
    for limit in manifest.get('limitations', []):
        component = limit.get('component', '')
        relevant = component in (path, '*') or (component.startswith('/') and path.startswith(component.rstrip('/') + '/'))
        if relevant and limit.get('dimension') in ('filesystem', 'api', 'headers'):
            # Generic statements about lexical limits are not collection errors.
            if component != '*' or limit['dimension'] == 'filesystem' or re.search(r'fail|unread|invalid|truncat|exceed|incomplete', limit.get('reason', ''), re.I):
                return False
    return True


def declaration_reachability(manifest, entry, name, declaration):
    """Bounded literal-include closure; no invented include paths or preprocessing."""
    headers = {h['path']: h for h in manifest.get('public_headers', [])}
    visiting, visited, matches, reasons = set(), set(), [], []
    def visit(path):
        if path in visiting:
            reasons.append('include cycle: ' + path); return
        if path in visited:
            return
        if len(visited) >= 256 or len(visiting) >= 64:
            reasons.append('include traversal limit'); return
        header = headers.get(path)
        if header is None:
            reasons.append('missing include: ' + path); return
        visiting.add(path)
        if not header_inventory_complete(manifest, path) or header.get('simple_declarations_complete') is not True:
            reasons.append('incomplete/unsupported declaration context: ' + path)
        if name in header.get('declarations', {}):
            matches.append({'path': path, 'declaration': header['declarations'][name]})
        if 'include_directives' not in header:
            reasons.append('include metadata unavailable: ' + path)
        for include in header.get('include_directives', []):
            include_name = include['name']
            # Absolute includes and parent traversal depend on an SDK context.
            if include_name.startswith('/') or '..' in include_name.split('/'):
                reasons.append('unsupported include path: ' + include_name); continue
            roots = ([posixpath.dirname(path)] if include['quoted'] else []) + manifest.get('header_include_roots', [])
            resolved = next((posixpath.normpath(r + '/' + include_name) for r in roots
                             if posixpath.normpath(r + '/' + include_name) in headers), None)
            if resolved:
                visit(resolved)
            else:
                reasons.append('unresolved include: ' + include_name)
        visiting.remove(path); visited.add(path)
    visit(entry)
    exact = bool(matches) and all(m['declaration'] == declaration for m in matches)
    if not reasons and exact:
        state = 'PROVEN_PRESENT'
    elif not reasons and not matches:
        state = 'PROVEN_ABSENT'
    elif matches or any(name in h.get('declarations', {}) for h in headers.values()):
        state = 'POSSIBLE_MIGRATION'
    else:
        state = 'UNKNOWN'
    return {'state': state, 'entry': entry, 'visited': sorted(visited), 'matches': matches,
            'reasons': sorted(set(reasons)),
            'scope': 'literal include closure and identical built-in C prototype only; no full API/ABI proof'}
