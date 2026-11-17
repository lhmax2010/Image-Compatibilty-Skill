"""Optional configured Clang AST evidence. Equality is context-specific, not a
whole API/ABI proof; record layouts, templates and inline behavior remain UNKNOWN.
"""
import json
from .core import finding


def semantic_probe(base, source, tools):
    result = tools.run([*base, '-fsyntax-only', '-Xclang', '-ast-dump=json', str(source)])
    declarations = []
    complete = result['returncode'] == 0 and not result['stdout_truncated']
    if complete:
        try:
            pending = [json.loads(result['stdout'])]
            while pending:
                node = pending.pop()
                if node.get('kind') in ('FunctionDecl', 'CXXMethodDecl', 'TypedefDecl', 'TypeAliasDecl', 'VarDecl') and node.get('name'):
                    declarations.append({'kind': node['kind'], 'name': node['name'], 'type': node.get('type', {})})
                pending.extend(node.get('inner', []))
        except (ValueError, TypeError, AttributeError):
            complete = False
    return {'complete': complete, 'declarations': sorted(declarations, key=lambda x: (x['name'], x['kind'], str(x['type']))),
            'evidence': [result['stdout_evidence'], result['stderr_evidence']]}


def compare_semantics(before, after):
    a, b = before['semantic'], after['semantic']
    same = a['complete'] and b['complete'] and a['declarations'] == b['declarations']
    # The compiler context must be recorded even when two headers happen to yield the same AST.
    return finding('api', after['name'].removeprefix('header:'), 'Clang AST declarations',
                   {'declarations': a['declarations'], 'macros': before.get('compiler_macros_evidence'), 'sdk': before.get('sdk')},
                   {'declarations': b['declarations'], 'macros': after.get('compiler_macros_evidence'), 'sdk': after.get('sdk')},
                   'UNKNOWN', 'INFO' if same else 'HIGH', 'configured SDK Clang semantic evidence', a['evidence'] + b['evidence'],
                   impact=('AST declaration signatures match in recorded contexts. ' if same else 'AST declarations differ or analysis is incomplete. ')
                          + 'This does not prove complete semantic/API equivalence; layouts, inline behavior and other configurations remain unverified.')
