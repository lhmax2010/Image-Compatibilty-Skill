"""Observed instrumentation in repository ELF contracts."""
from collections import Counter


NEEDED = {'ASAN': ('libasan', 'libclang_rt.asan'), 'UBSAN': ('libubsan',), 'TSAN': ('libtsan',)}
IMPORTS = {'ASAN': ('__asan_',), 'HWASAN': ('__hwasan_',), 'UBSAN': ('__ubsan_',),
           'TSAN': ('__tsan_',), 'COVERAGE': ('__gcov_', '__llvm_gcov', '__llvm_profile_', '__sanitizer_cov')}
INSTRUMENTATION_EXPORTS = ('__odr_asan', '___asan_gen', '__asan_', '__sancov')


def instrumentation(obj):
    observed = {kind for kind, prefixes in NEEDED.items()
                if any(name.startswith(prefixes) for name in obj.get('needed', []))}
    observed.update(kind for kind, prefixes in IMPORTS.items()
                    if any(sym['name'].startswith(prefixes) for sym in obj.get('imports', [])))
    return sorted(observed)


def runtime_object(obj):
    return (obj.get('elf_runtime_role') != 'DEBUG_ONLY'
            and obj.get('type', '').split(' ', 1)[0] in ('DYN', 'EXEC'))


def build_profile(objects):
    applicable = [obj for obj in objects if runtime_object(obj)]
    counts = Counter(kind for obj in applicable for kind in instrumentation(obj))
    return {kind: counts[kind] / len(applicable) if applicable else 0 for kind in sorted(IMPORTS)}


def comparison_profile(left, right):
    a, b = map(build_profile, (left, right))
    confounders = [{'kind': kind, 'baseline_share': a[kind], 'candidate_share': b[kind]} for kind in a
                   if max(a[kind], b[kind]) >= 0.20 and min(a[kind], b[kind]) <= 0.02]
    return {'comparison_validity': 'CONFOUNDED' if confounders else 'COMPARABLE',
            'confounders': confounders, 'build_profile': {'baseline': a, 'candidate': b}}
