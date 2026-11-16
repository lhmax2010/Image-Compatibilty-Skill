"""Conservative C/C++ token normalization, without claiming a full C parser."""
from __future__ import annotations

import re
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
    macros, includes, conditions = {}, [], []
    body = []
    for line in clean.splitlines():
        match = re.match(r'\s*#\s*define\s+(\w+)(.*)', line)
        if match:
            macros[match[1]] = {'kind': 'function' if match[2].startswith('(') else 'object',
                               'replacement': tokens(match[2])}
        match = re.match(r'\s*#\s*include\s*[<"]([^>"]+)', line)
        if match:
            includes.append(match[1])
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
    return {'tokens': tokens(clean), 'body_tokens': tokens(body_text), 'macros': macros,
            'includes': sorted(set(includes)), 'conditions': conditions,
            'declarations': declarations, 'context_hints': reasons,
            'parser': 'conservative C/C++ lexical declarations; no preprocessing/type resolution'}
