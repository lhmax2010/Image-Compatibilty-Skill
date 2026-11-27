#!/usr/bin/env bash
# VD-1 measurement kit (revision 7). FOR CLINESR ONLY. Measurement only, not acceptance.
#
# Usage, from the ClineSR workspace root:
#   bash .local-work/vd1_measure.sh check
#   BASE=<baseline rpm dir> CAND=<candidate rpm dir> bash .local-work/vd1_measure.sh prepare
#   bash .local-work/vd1_measure.sh run <WORK>
#   bash .local-work/vd1_measure.sh summary <WORK>
#   bash .local-work/vd1_measure.sh rerun <WORK> <40-hex commit on origin/main>   (revision 5)
#   bash .local-work/vd1_measure.sh detail <WORK> <7-hex tag>                     (revision 5)
#   Revision 6: summary skips tags not run in this WORK; detail adds object-shape and
#   extraction-error breakdowns and more fixed readelf diagnostic classes.
#   Revision 7: reads v1.5.3-rc1 reports (gzip manifests/evidence, symbol references in findings,
#   reason-code-based classification, owner-review and copy-relocation counts).
#
# Revision 5 adds 'rerun' (same sample, another published tool commit) and 'detail'
# (name-free breakdowns of one report). Existing WORK directories from revision 4.2 remain valid.
#
# Guarantees:
#   - Writes only under <workspace>/.local-work/, verified physically (symlinks resolved and rejected).
#   - Never modifies, moves or deletes RPM repositories. It only reads them and copies a sample.
#   - Never commits, pushes, pulls, merges or changes any branch. It only reads Git objects
#     already fetched into the workspace clone.
#   - Sets TMPDIR/TMP/TEMP to <workspace>/.local-work/tmp for itself and all children.
#   - Prints counts only: no package names, file paths from inside RPMs, or symbol names.
#     Raw diagnostics go to WORK/prepare.private.log and the run-*.private.stderr files, which stay local.
# Every failure prints a line starting with "STOP:" and exits non-zero.
set -euo pipefail
umask 077
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1

V151=2d43c58b8753c53f58fae906cc4c821bd6227397
FIX=323e0e1b416494a94eac40182970612b6b96d987
SAMPLE_MAX=${SAMPLE_MAX:-150}          # package names per side
SAMPLE_MAX_GB=${SAMPLE_MAX_GB:-5}      # RPM bytes copied per side
MIN_FREE_GB=${MIN_FREE_GB:-30}

stop() { echo "STOP: $*" >&2; exit 1; }
WS=$(git rev-parse --show-toplevel 2>/dev/null) || stop "run this from inside the workspace Git clone"
WS=$(cd -P "$WS" && pwd -P) || stop "cannot resolve workspace"
url=$(git -C "$WS" config --get remote.origin.url | tr "[:upper:]" "[:lower:]")
case "$url" in
  *lhmax2010/image-compatibilty-skill*) ;;
  *) stop "workspace origin is not lhmax2010/Image-Compatibilty-Skill" ;;
esac
LW="$WS/.local-work"
[ -L "$LW" ] && stop ".local-work must be a real directory, not a symlink"
mkdir -p "$LW"
[ -L "$LW" ] && stop ".local-work must be a real directory, not a symlink"
LW=$(cd -P "$LW" && pwd -P) || stop "cannot resolve .local-work"
case "$LW/" in "$WS"/*) ;; *) stop ".local-work resolves outside the workspace" ;; esac
# All temporary files of this script and of every child (sort, python, the tool) stay here.
[ -L "$LW/tmp" ] && stop ".local-work/tmp must not be a symlink"
mkdir -p "$LW/tmp"
export TMPDIR="$LW/tmp" TMP="$LW/tmp" TEMP="$LW/tmp"

# Physical confinement: the path must resolve (symlinks followed) inside $LW,
# and no component between $LW and the path may be a symlink.
inside_lw() {
  local p=$1 real
  real=$(cd -P "$p" 2>/dev/null && pwd -P) || return 1
  case "$real/" in "$LW"/*) ;; *) return 1 ;; esac
  [ "$p" = "$real" ]
}

need_work() {
  [ -n "${1:-}" ] || stop "give the WORK directory printed by 'prepare'"
  inside_lw "$1" || stop "WORK must be a real directory inside $LW (no symlinks)"
  W=$(cd -P "$1" && pwd -P)
  for d in base cand; do
    [ -d "$W/$d" ] && [ ! -L "$W/$d" ] || stop "WORK/$d missing or a symlink"
  done
}

cmd_check() {
  for t in python3 rpm rpm2cpio readelf git tar sha256sum; do
    command -v "$t" >/dev/null || stop "missing tool: $t"
  done
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || stop "Python 3.10+ required"
  for c in $V151 $FIX; do
    git -C "$WS" cat-file -e "$c^{commit}" 2>/dev/null || stop "commit $c not fetched; run: git -C \"$WS\" fetch origin main"
  done
  free=$(df -Pk "$LW" | awk 'NR==2{print int($4/1048576)}')
  [ "$free" -ge "$MIN_FREE_GB" ] || stop "only ${free} GB free in workspace filesystem (need ${MIN_FREE_GB})"
  echo "python: $(python3 --version 2>&1)  readelf: $(readelf --version | head -1)"
  echo "rpm: $(rpm --version)  free_gb: $free"
  echo "CHECK OK"
}

cmd_prepare() {
  cmd_check >/dev/null
  [ -n "${BASE:-}" ] && [ -d "$BASE" ] && [ -r "$BASE" ] || stop "set BASE to the readable baseline RPM directory"
  [ -n "${CAND:-}" ] && [ -d "$CAND" ] && [ -r "$CAND" ] || stop "set CAND to the readable candidate RPM directory"
  W="$LW/vd1r4-$(date -u +%Y%m%dT%H%M%SZ)"
  [ -e "$W" ] && stop "$W already exists; wait one second and retry"
  mkdir "$W" "$W/base" "$W/cand"
  inside_lw "$W" || stop "new WORK resolves outside $LW"
  # Raw diagnostics (may contain RPM file names) stay in this local log; never share it.
  LOG="$W/prepare.private.log"; : > "$LOG"
  for c in $V151 $FIX; do
    mkdir -p "$W/tool-${c:0:7}"
    git -C "$WS" archive "$c" .agents/skills/tizen-image-compatibility 2>>"$LOG" |
      tar -x -C "$W/tool-${c:0:7}" 2>>"$LOG" || stop "could not export tool ${c:0:7} (details in WORK/prepare.private.log)"
  done
  echo "tool versions: $(cat "$W/tool-${V151:0:7}/.agents/skills/tizen-image-compatibility/VERSION") / $(cat "$W/tool-${FIX:0:7}/.agents/skills/tizen-image-compatibility/VERSION")"
  for side in BASE CAND; do
    d=${!side}
    : > "$W/$side.skipped"
    { find "$d" -name '*.rpm' ! -name '*debug*' -type f -print0 2>>"$LOG" || true; } |
      while IFS= read -r -d '' f; do
        if n=$(rpm -qp --qf '%{NAME}' -- "$f" 2>>"$LOG") && sz=$(stat -c %s -- "$f" 2>>"$LOG"); then
          printf '%s\t%s\t%s\n' "$n" "$sz" "$f"
        else
          echo x >> "$W/$side.skipped"
        fi
      done | sort -T "$TMPDIR" -t$'\t' -k1,1 2>>"$LOG" > "$W/$side.map" || stop "header scan failed for $side (details in WORK/prepare.private.log)"
    [ -s "$W/$side.map" ] || stop "no readable RPMs found under $side"
    echo "scanned $side: rpms=$(wc -l < "$W/$side.map") unreadable_skipped=$(wc -l < "$W/$side.skipped") find_errors=$(grep -c '^find:' "$LOG" || true)"
  done
  python3 - "$W" "$SAMPLE_MAX" "$SAMPLE_MAX_GB" 2>>"$LOG" <<'EOF' || stop "sample selection failed (details in WORK/prepare.private.log; do not share it)"
import sys, collections
w, limit, budget = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) * 1024**3
def load(side):
    m = collections.defaultdict(list)
    for line in open(f'{w}/{side}.map', encoding='utf-8', errors='surrogateescape'):
        name, size, path = line.rstrip('\n').split('\t', 2)
        m[name].append((int(size), path))
    return m
b, c = load('BASE'), load('CAND')
common = sorted(set(b) & set(c))
if len(common) < 100:
    print(f'common_names {len(common)}  minimum_required 100')
    sys.exit(1)
def cost(n): return max(sum(s for s, _ in b[n]), sum(s for s, _ in c[n]))
targeted = [n for n in common if any(k in n.lower() for k in
            ('icu', 'webkit', 'chromium', 'efl', 'stdc++', 'glibc', 'gcc', 'dbus', 'glib', 'ecore', 'elementary'))]
ranked = sorted(common, key=lambda n: -cost(n))
step = max(1, len(ranked) // limit)
stratified = ranked[::step]
chosen, total = [], 0
for n in targeted + stratified:
    if n in chosen or len(chosen) >= limit:
        continue
    if total + cost(n) > budget:
        continue
    chosen.append(n); total += cost(n)
with open(f'{w}/sample.names', 'w') as out:
    out.write('\n'.join(sorted(chosen)) + '\n')
print(f'common_names {len(common)}  sample_names {len(chosen)}  targeted_in_sample {sum(n in chosen for n in targeted)}  sample_bytes_max_side {total}')
if len(chosen) < 50:
    sys.exit('STOP: fewer than 50 packages fit the byte budget; raise SAMPLE_MAX_GB')
EOF
  for pair in BASE:base CAND:cand; do
    side=${pair%%:*}; dst="$W/${pair##*:}"; fails=0
    join -t$'\t' -j1 "$W/sample.names" "$W/$side.map" 2>>"$LOG" | cut -f3 > "$W/$side.copylist" ||
      stop "sample join failed for $side (details in WORK/prepare.private.log)"
    grep -q '^join:' "$LOG" && stop "join reported unsorted input (details in WORK/prepare.private.log)"
    while IFS= read -r f; do
      cp -p -- "$f" "$dst/" 2>>"$LOG" || fails=$((fails+1))
    done < "$W/$side.copylist"
    [ "$fails" -eq 0 ] || stop "$fails RPM copies failed for $side (details in WORK/prepare.private.log; do not share it)"
  done
  local base_count cand_count base_size cand_size
  base_count=$(ls "$W/base" 2>>"$LOG" | wc -l) && cand_count=$(ls "$W/cand" 2>>"$LOG" | wc -l) &&
    base_size=$(du -sh "$W/base" 2>>"$LOG" | cut -f1) && cand_size=$(du -sh "$W/cand" 2>>"$LOG" | cut -f1) ||
    stop "could not count sampled files (details in WORK/prepare.private.log; do not share it)"
  echo "copied: base=$base_count cand=$cand_count  size: base=$base_size cand=$cand_size"
  echo "PREPARE OK WORK=$W"
}

run_tool() {
  local tag=$1 log
    [ -e "$W/report-$tag" ] || [ -L "$W/report-$tag" ] && stop "report-$tag already exists; use a new WORK from 'prepare'"
    for f in run-$tag.stdout run-$tag.stderr run-$tag.private.stdout run-$tag.private.stderr run-$tag.metrics; do
      [ -e "$W/$f" ] || [ -L "$W/$f" ] && stop "$f already exists; use a new WORK from 'prepare'"
    done
    local skill="$W/tool-$tag/.agents/skills/tizen-image-compatibility"
    inside_lw "$skill/scripts" && [ -f "$skill/scripts/tizen_compat.py" ] &&
      [ ! -L "$skill/scripts/tizen_compat.py" ] || stop "tool path is unavailable or outside WORK"
    log=$(mktemp "$W/run-$tag.private.XXXXXXXX.log") || stop "could not create private run log"
    python3 - "$skill" "$W" "$tag" 2>"$log" <<'EOF' || stop "run failed (see private run logs in WORK; do not share them)"
import resource, subprocess, sys, time
skill, w, tag = sys.argv[1:4]
t = time.time()
rc = subprocess.call(['python3', f'{skill}/scripts/tizen_compat.py', '--baseline', f'{w}/base',
                      '--candidate', f'{w}/cand', '--rpm-mode', 'payload', '--mode', 'static',
                      '--output', f'{w}/report-{tag}'],
                     stdout=open(f'{w}/run-{tag}.private.stdout', 'x'), stderr=open(f'{w}/run-{tag}.private.stderr', 'x'))
peak = round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1)
line = f'{tag} exit={rc} wall_seconds={round(time.time() - t, 1)} peak_rss_mb={peak}'
open(f'{w}/run-{tag}.metrics', 'x').write(line + '\n'); print(line)
if rc == 2:
    print('STOP: tool reported an input error (exit 2); see private run log in WORK', flush=True)
    sys.exit(2)
EOF
}

cmd_run() {
  need_work "${1:-}"
  for tag in ${V151:0:7} ${FIX:0:7}; do
    run_tool "$tag"
  done
  echo "RUN OK"
}

cmd_rerun() {
  need_work "${1:-}"
  local c=${2:-} tag
  [[ "$c" =~ ^[0-9a-f]{40}$ ]] || stop "give the full 40-character commit ID"
  git -C "$WS" cat-file -e "$c^{commit}" 2>/dev/null || stop "commit not fetched; run: git -C \"$WS\" fetch origin main"
  git -C "$WS" merge-base --is-ancestor "$c" origin/main 2>/dev/null || stop "commit is not on origin/main"
  tag=${c:0:7}
  [ -e "$W/tool-$tag" ] || [ -L "$W/tool-$tag" ] && stop "tool-$tag already exists in WORK"
  mkdir "$W/tool-$tag"
  LOG=$(mktemp "$W/rerun-$tag.private.XXXXXXXX.log") || stop "could not create private rerun log"
  git -C "$WS" archive "$c" .agents/skills/tizen-image-compatibility 2>>"$LOG" |
    tar -x -C "$W/tool-$tag" 2>>"$LOG" || stop "could not export tool $tag (details in private rerun log)"
  echo "tool version: $(cat "$W/tool-$tag/.agents/skills/tizen-image-compatibility/VERSION")"
  run_tool "$tag"
  echo "RERUN OK TAG=$tag"
}

report_safety() {
cat <<'PYTHON'
import gzip

STATES = set("COMPATIBLE INCOMPATIBLE IDENTICAL UNKNOWN NOT_APPLICABLE NOT_EXECUTED COMPLETE PARTIAL FAILED PASS FAIL PENDING NONE BLOCKED".split())
DIMENSIONS = set("elf abi api headers linking compiler_runtime kernel ipc commands filesystem packages services security runtime hardware network performance".split())
ROLES = {"RUNTIME", "RUNTIME_WITH_DEBUG", "DEBUG_ONLY", "UNKNOWN"}
CLASSES = {"ELF32", "ELF64"}
MACHINES = {"ARM", "AArch64", "Advanced Micro Devices X86-64", "Intel 80386", "RISC-V", "PowerPC", "PowerPC64", "MIPS R3000"}
TYPES = {"NONE", "REL", "EXEC", "DYN", "CORE"}
CXX = set("c cxx_template cxx_other vtable typeinfo typeinfo_name vtt guard thunk".split())
KINDS = set("DT_NEEDED VERSION_NODE VERSIONED_IMPORT UNVERSIONED_IMPORT COPY_RELOCATION CONSUMER_INVENTORY".split())
CHANGES = set("ADDED MISSING MATCHED CHANGED BASELINE_OBSERVED CANDIDATE_OBSERVED".split())
INVENTORY = set("COMMON VERSION_CHANGED BASELINE_ONLY CANDIDATE_ONLY BASELINE_ONLY_OR_UNRESOLVED AMBIGUOUS_MULTIPLE_VERSIONS AMBIGUOUS_IDENTICAL_NEVRA".split())
REASONS = set("""
    none EXPORT_REMOVED EXPORT_NOT_OBSERVED EXPORT_INVENTORY_INCOMPLETE DUPLICATE_DYNSYM_IDENTITY
    VERSION_DEFINITION_REMOVED VERSION_DEFINITION_NOT_OBSERVED DEFAULT_VERSION_LOOKUP_LOST
    DEFAULT_VERSION_CHANGED DEFAULT_SYMBOL_VERSION_CHANGED DT_NEEDED_CHANGED ELF_AVAILABILITY_UNVERIFIED
    EXECUTABLE_NOT_FOUND OBJECT_UNPAIRED LIBRARY_NOT_FOUND_INCOMPLETE_INVENTORY PROVIDER_AMBIGUOUS
    LIBRARY_REMOVED KIND_CHANGED TLS_KIND_CHANGED DATA_SIZE_DECREASED DATA_SIZE_INCREASED
    IFUNC_TRANSITION NOTYPE_ANNOTATION GNU_UNIQUE_DROPPED SYMBOL_BINDING_CHANGED SYMBOL_VISIBILITY_CHANGED
    INSTRUMENTATION_MISMATCH INSTRUMENTATION_SYMBOL DWARF_ABI_CHANGED DWARF_ABI_UNAVAILABLE
    DIMENSION_NOT_EXECUTED COVERAGE_LIMITATION LOADER_ENV_MISSING UNKNOWN_COLLECTION UNKNOWN_SEARCH_ENVIRONMENT
    UNKNOWN_LOADER_ABI UNKNOWN_LOADER_FEATURE UNKNOWN_VERSION_REQUIREMENT UNKNOWN_SYMBOL_SCOPE UNKNOWN_SYMBOL_SEMANTICS
    MISSING_PROVIDER UNRESOLVABLE_PROVIDER MISSING_VERSION MISSING_SYMBOL SYMBOL_TYPE_MISMATCH VERIFIED
    NEEDED_SONAME_UNAVAILABLE VERSION_NODE_UNAVAILABLE VERSIONED_SYMBOL_UNAVAILABLE ALSO_UNSATISFIED_IN_BASELINE
    UNVERSIONED_SYMBOL_NOT_IN_CLOSURE WEAK_REFERENCE_UNSATISFIED VERSION_PROVIDER_UNAVAILABLE
    REQUIREMENT_INVENTORY_INCOMPLETE CONSUMER_INVENTORY_INCOMPLETE TOOL_TIMEOUT OUTPUT_LIMIT TOOL_UNAVAILABLE
    CONTRACT_DIFFERENCE CONTRACT_UNVERIFIED LINKING_STATIC_DIFFERENCE READELF_DIAGNOSTIC DYNSYM_ROWS_INCONSISTENT
    VERSION_RECORDS_INCONSISTENT HEADER_FIELDS_MISSING OBJECT_INCOMPLETE COPY_RELOC_SIZE_CHANGED
    SYMBOL_BINDING_WEAKENED SYMBOL_BINDING_STRENGTHENED DYNAMIC_WEAK_SEMANTICS
    WEAK_CXX_EXPORT_REMOVED_UNREFERENCED WEAK_CXX_EXPORT_REMOVAL_ACCEPTED WEAK_CXX_EXPORT_REMOVAL_REJECTED
""".split())

def fixed(value, choices):
    return value if isinstance(value, str) and value in choices else 'OTHER'

def numeric(value):
    return value if type(value) in (int, float) else None

def counts(values, choices):
    result = {}
    for key, value in (values or {}).items():
        if type(value) is int:
            label = fixed(key, choices)
            result[label] = result.get(label, 0) + value
    return result

def reason(row):
    return fixed(row.get('reason_code') or 'none', REASONS)

def state(row):
    return fixed(row.get('status'), STATES)

def dimension(row):
    return fixed(row.get('dimension'), DIMENSIONS)
PYTHON
}

cmd_summary() {
  need_work "${1:-}"
  local log
  log=$(mktemp "$W/summary.private.XXXXXXXX.log") || stop "could not create private summary log"
  shift
  local t; for t in "$@"; do [[ "$t" =~ ^[0-9a-f]{7}$ ]] || stop "tags must be 7 hex characters"; done
  python3 -c "$(report_safety)
$(cat <<'EOF'
import collections, json, os, re, sys
w, *tags = sys.argv[1:]
def size(p):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
print('VD-1 RESULT (revision 7, sample, counts only)')
print('sample: base_rpms', len(os.listdir(f'{w}/base')), 'cand_rpms', len(os.listdir(f'{w}/cand')),
      'base_bytes', size(f'{w}/base'), 'cand_bytes', size(f'{w}/cand'))
for tag in tags:
    r = f'{w}/report-{tag}'
    if not os.path.isfile(f'{w}/run-{tag}.metrics'):
        print('===', tag, 'not run in this WORK'); continue
    metrics = open(f'{w}/run-{tag}.metrics').read().strip()
    if not re.fullmatch(rf'{tag} exit=-?\d+ wall_seconds=\d+\.\d+ peak_rss_mb=\d+\.\d+', metrics):
        sys.exit('invalid metrics record')
    print(f'=== {tag}', metrics, 'report_bytes', size(r))
    if not os.path.exists(f'{r}/results.json'):
        stderr = f'{w}/run-{tag}.private.stderr'
        if not os.path.isfile(stderr):
            stderr = f'{w}/run-{tag}.stderr'  # Existing revision 4.2 WORK.
        with open(stderr, errors='replace') as diagnostics:
            print('no results.json; stderr_lines', sum(1 for _ in diagnostics))
        continue
    for side in ('baseline', 'candidate'):
        m = json.load(open(f'{r}/{side}-manifest.json') if os.path.isfile(f'{r}/{side}-manifest.json') else __import__('gzip').open(f'{r}/{side}-manifest.json.gz', 'rt'))
        o = m['elf_objects']; c = m['repository']['counts']
        print(f'## {side}', 'rpm_total', numeric(c.get('rpm_total')), 'metadata_complete', numeric(c.get('metadata_complete')),
              'extracted', numeric(c.get('extracted')), 'extraction_failed', numeric(c.get('extraction_failed')))
        print('  elf_objects', len(o), 'elf_complete', numeric(c.get('elf_complete')),
              'export_inventories_complete', numeric(c.get('export_inventories_complete')))
        print('  machines', dict(collections.Counter(fixed(x.get('machine'), MACHINES) for x in o)),
              'classes', dict(collections.Counter(fixed(x.get('class'), CLASSES) for x in o)))
        print('  roles', dict(collections.Counter(fixed(x.get('elf_runtime_role'), ROLES) for x in o)))
        print('  export_status', dict(collections.Counter(fixed(x.get('export_inventory_status'), STATES) for x in o)))
        print('  incomplete_reason_codes', dict(collections.Counter(
            fixed(x.get('export_inventory_reason_code'), REASONS) if x.get('export_inventory_reason_code') else ('limit' if 'limit' in str(x.get('error', '')) else 'other')
            for x in o if x.get('export_inventory_status') == 'UNKNOWN')))
        print('  asan_objects', sum(any('asan' in n for n in x.get('needed', [])) for x in o),
              'exports_total', numeric(c.get('exports')), 'imports_total', numeric(c.get('imports')))
    res = json.load(open(f'{r}/results.json'))
    rr = res.get('repository', {})
    print('## result status', state(res), 'gate', state(res['quality_gate']), 'findings', numeric(res['summary']['findings']))
    print('  by_status', counts(res['summary']['by_status'], STATES))
    print('  inventory_states', counts(rr.get('inventory_states'), INVENTORY))
    print('  comparison_validity', fixed(rr.get('comparison_validity'), {'COMPARABLE','CONFOUNDED'}), 'confounder_count', len(rr.get('confounders') or []))
    print('  instrumentation_downgrades', counts(rr.get('instrumentation_downgrades'), REASONS))
    req = rr.get('requirements') or {}
    print('  requirements_by_kind', {k: counts(v, {'satisfied','failed','unknown'}) for k,v in (req.get('by_kind') or {}).items() if k in KINDS})
    print('  requirements_by_reason', counts(req.get('by_reason'), REASONS))
    sd = rr.get('symbol_differences') or {}
    print('  symbol_differences_by_role', {k: counts(v.get('by_change'), CHANGES) for k, v in (sd.get('by_role') or {}).items() if k in {'EXPORT','IMPORT'}})
    rc = collections.Counter(reason(f) for f in res['findings'] if f.get('reason_code'))
    print('  reason_codes', dict(rc.most_common(20)))
    inc = collections.Counter((dimension(f), reason(f)) for f in res['findings']
                              if f['status'] == 'INCOMPATIBLE')
    print('  incompatible_by_dimension_reason', {f'{a}/{b}': n for (a, b), n in inc.most_common(15)})
    if os.path.exists(f'{r}/run-summary.json'):
        s = json.load(open(f'{r}/run-summary.json'))
        print('  run_summary', {k: fixed(s.get(k), STATES | {'EXPORT_SYMBOLS','PACKAGE_INVENTORY','STATIC_REPORT'}) for k in ('requested_objective', 'objective_completion',
              'execution_status', 'compatibility_status', 'coverage_status', 'ci_gate_status')})
print('END OF VD-1 RESULT')
EOF
)" "$W" "${V151:0:7}" "${FIX:0:7}" "$@" 2>"$log" || stop "summary failed (see private summary log in WORK; do not share it)"
}

cmd_detail() {
  need_work "${1:-}"
  local tag=${2:-} log
  [[ "$tag" =~ ^[0-9a-f]{7}$ ]] || stop "tag must be 7 hex characters"
  [ -d "$W/report-$tag" ] && [ ! -L "$W/report-$tag" ] || stop "report-$tag missing; run 'run' or 'rerun' first"
  log=$(mktemp "$W/detail.private.XXXXXXXX.log") || stop "could not create private detail log"
  python3 -c "$(report_safety)
$(cat <<'EOF'
import collections, json, os, re, sys
w, tag = sys.argv[1:]
r = f'{w}/report-{tag}'
C = collections.Counter
def top(counter, n=15):
    return dict(counter.most_common(n))
print(f'VD-1 DETAIL (revision 7, tag {tag}, counts only)')
# Full repositories, from the header scan made by 'prepare' (no names printed).
maps = {}
for side in ('BASE', 'CAND'):
    names, total, rows = set(), 0, 0
    for line in open(f'{w}/{side}.map', encoding='utf-8', errors='surrogateescape'):
        name, size, _ = line.rstrip('\n').split('\t', 2)
        names.add(name); total += int(size); rows += 1
    maps[side] = names
    print(f'full_{side.lower()}: rpms {rows} bytes {total} names {len(names)}')
print('full_common_names', len(maps['BASE'] & maps['CAND']),
      'base_only_names', len(maps['BASE'] - maps['CAND']), 'cand_only_names', len(maps['CAND'] - maps['BASE']))
metrics = open(f'{w}/run-{tag}.metrics').read().strip()
if not re.fullmatch(rf'{tag} exit=-?\d+ wall_seconds=\d+\.\d+ peak_rss_mb=\d+\.\d+', metrics):
    sys.exit('invalid metrics record')
print(metrics)
# Report size by top-level entry; entry names are tool outputs, checked against an allowlist pattern.
known_entries = {
    '.compat-run', 'baseline-manifest.json', 'candidate-manifest.json', 'collection.log',
    'baseline-manifest.json.gz', 'candidate-manifest.json.gz', 'weak-export-review.csv',
    'expected-tests.json', 'expected-tests-results.json', 'build/',
    'elf-symbol-summary.csv', 'evidence/', 'extraction-errors.csv', 'findings.csv',
    'index.html', 'linking-details.csv', 'package-symbol-summary.csv', 'packages.csv',
    'requirement-findings.csv', 'results.json', 'rpm-repository.json', 'run-summary.json',
    'summary.md', 'symbol-differences.csv', 'test-results.csv',
}
sizes = C()
for entry in os.scandir(r):
    if entry.is_dir(follow_symlinks=False):
        b = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(entry.path) for f in fs)
        key = entry.name + '/'
    else:
        b, key = entry.stat(follow_symlinks=False).st_size, entry.name
    sizes[key if key in known_entries else 'other'] += b
print('report_bytes_by_entry', top(sizes, 15))
res = json.load(open(f'{r}/results.json'))
F = res['findings']
print('findings', len(F), 'by_dimension_status', top(C(f"{dimension(f)}/{state(f)}" for f in F), 20))
print('unknown_by_dimension_reason', top(C(f"{dimension(f)}/{reason(f)}" for f in F if f['status'] == 'UNKNOWN'), 20))
def kind(f):
    i, b, c = f.get('interface') or '', f.get('baseline'), f.get('candidate')
    if i.startswith('version definition:'): return 'VERSION_DEFINITION'
    if i.endswith(':default lookup'): return 'DEFAULT_LOOKUP'
    if i.endswith(':default symbol version'): return 'DEFAULT_SYMBOL_VERSION'
    rc = f.get('reason_code') or ''
    if rc in ('EXPORT_REMOVED', 'EXPORT_NOT_OBSERVED', 'WEAK_CXX_EXPORT_REMOVED_UNREFERENCED',
              'WEAK_CXX_EXPORT_REMOVAL_ACCEPTED', 'WEAK_CXX_EXPORT_REMOVAL_REJECTED') or f.get('removal_context'):
        return 'EXPORT_REMOVED'
    if isinstance(b, dict) and c is None and i == b.get('name'): return 'EXPORT_REMOVED'
    if b is None and isinstance(c, dict) and (i == c.get('name') or '$symbol' in c): return 'EXPORT_ADDED'
    field = i.rsplit(':', 1)[-1] if ':' in i else ''
    if field in ('type', 'binding', 'visibility', 'size') and not isinstance(b, dict): return 'FIELD_' + field.upper()
    if i in ('ELF availability', 'dynamic export collection coverage', 'dynamic export applicability',
             'dynamic interface surface', 'collection coverage', 'DWARF type/layout ABI',
             'duplicate dynamic symbol identities'):
        return 'META:' + i
    return 'OTHER'
abi = [f for f in F if f['dimension'] == 'abi']
print('abi_by_kind_status_reason', top(C(f"{kind(f)}/{state(f)}/{reason(f)}" for f in abi), 25))
elf_fields = {
    'FIELD_TYPE': {'NOTYPE', 'OBJECT', 'FUNC', 'SECTION', 'FILE', 'COMMON', 'TLS', 'IFUNC', 'GNU_IFUNC'},
    'FIELD_BINDING': {'LOCAL', 'GLOBAL', 'WEAK', 'UNIQUE', 'GNU_UNIQUE'},
    'FIELD_VISIBILITY': {'DEFAULT', 'INTERNAL', 'HIDDEN', 'PROTECTED'},
}
def elf_field(kind, value):
    return value if isinstance(value, str) and value in elf_fields[kind] else 'OTHER'
fields = collections.defaultdict(C)
for f in abi:
    k = kind(f)
    if k.startswith('FIELD_'):
        b, c = f.get('baseline'), f.get('candidate')
        if k == 'FIELD_SIZE':
            label = ('decrease' if (c or 0) < (b or 0) else 'increase') + '/' + state(f)
        else:
            label = f'{elf_field(k, b)}->{elf_field(k, c)}'
        fields[k][re.sub(r'[^A-Za-z_>/-]', '', label)[:40]] += 1
for k in sorted(fields):
    print(f'  {k.lower()}_pairs', top(fields[k], 12))
def manifest(side):
    import gzip
    p = f'{r}/{side}-manifest.json'
    return json.load(open(p) if os.path.isfile(p) else gzip.open(p + '.gz', 'rt'))['elf_objects']
objs = {side: manifest(side) for side in ('baseline', 'candidate')}
def base(n):
    return n.split('@', 1)[0]
imported = {side: C(s.get('base_name') or base(s['name']) for o in objs[side] for s in (o.get('imports') or []))
            for side in objs}
removed = [f for f in abi if kind(f) == 'EXPORT_REMOVED']
def cxx(n):
    if not n.startswith('_Z'): return 'c'
    for p, label in (('_ZTV', 'vtable'), ('_ZTI', 'typeinfo'), ('_ZTS', 'typeinfo_name'), ('_ZTT', 'vtt'),
                     ('_ZGV', 'guard'), ('_ZTh', 'thunk'), ('_ZTv', 'thunk'), ('_ZTc', 'thunk')):
        if n.startswith(p): return label
    return 'cxx_template' if 'I' in n[2:] and 'E' in n else 'cxx_other'
def rctx(f):
    x = f.get('removal_context') or {}
    b = f.get('baseline') if isinstance(f.get('baseline'), dict) and 'name' in f.get('baseline') else {}
    name = b.get('base_name') or base(b.get('name') or f.get('interface') or '')
    return {'binding': x.get('binding', b.get('binding')), 'type': x.get('type', b.get('type')),
            'versioned': x.get('versioned', '@' in (b.get('name') or '')),
            'cxx': x.get('cxx_class') or cxx(name), 'name': name,
            'imp_b': (x.get('observed_importers') or {}).get('baseline'),
            'imp_c': (x.get('observed_importers') or {}).get('candidate')}
R = [(f, rctx(f)) for f in removed]
print('removed_exports', len(removed), 'by_status_reason', top(C(f"{state(f)}/{reason(f)}" for f, _ in R), 10))
print('  by_binding_type', top(C(f"{elf_field('FIELD_BINDING', x['binding'])}/{elf_field('FIELD_TYPE', x['type'])}" for _, x in R), 12))
print('  versioned', sum(bool(x['versioned']) for _, x in R), 'by_cxx_class',
      top(C(fixed(x['cxx'], CXX) for _, x in R), 10))
ib = [(f, x) for f, x in R if (x['imp_b'] if x['imp_b'] is not None else imported['baseline'][x['name']])]
ic = [(f, x) for f, x in R if (x['imp_c'] if x['imp_c'] is not None else imported['candidate'][x['name']])]
print('  imported_by_some_baseline_object', len(ib), 'by_binding', dict(C(elf_field('FIELD_BINDING', x['binding']) for _, x in ib)),
      'imported_by_some_candidate_object', len(ic))
print('reason_by_status', top(C(f"{state(f)}/{reason(f)}" for f in F if f['status'] != 'COMPATIBLE'), 25))
print('compatible_reasons', top(C(reason(f) for f in F if f['status'] == 'COMPATIBLE'), 10))
try:
    rv = json.load(open(f'{r}/run-summary.json')).get('review')
    print('review', {k: numeric(rv.get(k)) for k in ('required', 'accepted', 'rejected', 'pending', 'unmatched')} | {'status': fixed(rv.get('status'), {'NONE','PENDING','COMPLETE'})} if isinstance(rv, dict) else None)
except Exception:
    print('review unreadable')
wr = f'{r}/weak-export-review.csv'
if os.path.isfile(wr):
    import csv
    rows = list(csv.DictReader(open(wr, newline='', errors='replace')))
    print('weak_review_rows', len(rows), 'by_cxx_class', top(C(fixed(x.get('cxx_class'), CXX) for x in rows), 10),
          'demangled_filled', sum(bool(x.get('demangled')) for x in rows))
# Export inventory incompleteness: name-free flags plus sanitized readelf diagnostic signatures.
def signature(line):
    # Emit a fixed template. Masking tokens cannot reliably identify short names.
    level = 'Warning' if line.lstrip().startswith('Warning:') else 'Error'
    for pattern, label in (
        (r'program interpreter', 'interpreter unavailable'),
        (r'version (?:index|information|symbol|definition|need)', 'version metadata diagnostic'),
        (r'(?:dynamic|symbol) table', 'symbol table diagnostic'),
        (r'section (?:header|name|size|offset)', 'section metadata diagnostic'),
        (r'(?:corrupt|invalid|truncat|extends past|out of range)', 'invalid or truncated ELF data'),
        (r'(?:NOBITS|has no data|not dumped|no data)', 'section without file data'),
        (r'(?:debuglink|debugaltlink|gnu_debug|separate debug)', 'debug link diagnostic'),
        (r'(?:DWARF|debug_|\.debug)', 'debug info diagnostic'),
        (r'(?:dynamic segment|PT_DYNAMIC|\.dynamic)', 'dynamic segment diagnostic'),
        (r'(?:reloc)', 'relocation diagnostic'),
        (r'(?:string table|strtab)', 'string table diagnostic'),
        (r'(?:\bnote\b|\.note)', 'note diagnostic'),
        (r'(?:unable to|could not|cannot|failed to|short read)', 'read failure'),
        (r'(?:unknown|unrecogni|unsupported|unhandled)', 'unsupported feature'),
    ):
        if re.search(pattern, line, re.IGNORECASE):
            return f'{level}: {label}'
    return f'{level}: other readelf diagnostic'
def path_class(p):
    p = p or ''
    if p.startswith('/usr/lib/debug/') or '/.debug/' in p: return 'debug_tree'
    if p.endswith('.debug'): return 'debug_suffix'
    if re.search(r'\.ko(\.[a-z]+)?$', p): return 'kernel_module'
    if p.endswith('.o') or p.endswith('.a'): return 'object_or_archive'
    if re.search(r'\.so(\.[0-9.]+)?$', p): return 'shared_library_name'
    if '/bin/' in p or '/sbin/' in p or '/libexec/' in p: return 'executable_dir'
    return 'other'
def elf_type(obj):
    return fixed(str(obj.get('type') or '').split(' ', 1)[0], TYPES)
for side in ('baseline', 'candidate'):
    allo = objs[side]
    print(f'copy_relocations_{side}', 'objects', sum(bool(o.get('copy_relocations')) for o in allo),
          'entries', sum(len(o.get('copy_relocations') or []) for o in allo))
    print(f'objects_{side}', len(allo), 'by_role_type', top(C(f"{fixed(o.get('elf_runtime_role'), ROLES)}/{elf_type(o)}" for o in allo), 10),
          'by_path_class', top(C(path_class(o.get('package_path') or o.get('path')) for o in allo), 10))
    bad = [o for o in objs[side] if o.get('export_inventory_status') == 'UNKNOWN']
    print(f'  export_incomplete_{side}_shape', top(C(f"{fixed(o.get('elf_runtime_role'), ROLES)}/{elf_type(o)}/{path_class(o.get('package_path') or o.get('path'))}/"
          + ('exports' if o.get('exports') else 'no_exports') + '/'
          + fixed(o.get('export_inventory_reason_code'), REASONS) for o in bad), 12))
    flags, sigs = C(), C()
    for o in bad:
        defs = {v.get('name') for v in o.get('version_definitions') or []}
        reqs = {v.get('name') for v in o.get('version_requirements') or []}
        f = set()
        if not o.get('complete'): f.add('object_incomplete')
        if not all(o.get(k) for k in ('class', 'endianness', 'type')): f.add('header_field_missing')
        if any(s.get('version') and s['version'] not in defs for s in o.get('exports') or []): f.add('export_version_undefined')
        if any(s.get('version') and s['version'] not in reqs for s in o.get('imports') or []): f.add('import_version_unrequired')
        if any(s.get('version') and s.get('version_index') is not None and not s.get('version_file') for s in o.get('imports') or []):
            f.add('import_version_file_missing')
        if o.get('export_inventory_reason_code'): f.add('code:' + fixed(o['export_inventory_reason_code'], REASONS))
        warned = False
        for ref in o.get('export_inventory_evidence') or []:
            if not re.fullmatch(r'evidence/[a-f0-9]{64}\.txt(\.gz)?', ref):
                continue
            p = os.path.join(r, ref)
            if not os.path.isfile(p) and os.path.isfile(p + '.gz'):
                p += '.gz'
            if os.path.commonpath((os.path.realpath(p), os.path.realpath(r))) != os.path.realpath(r):
                continue
            if not os.path.isfile(p) or os.path.getsize(p) > 1024 * 1024:
                continue
            reader = gzip.open if p.endswith('.gz') else open
            with reader(p, 'rb') as evidence:
                preview = evidence.read(1024 * 1024 + 1)
            if len(preview) > 1024 * 1024:
                continue
            for line in preview.decode('utf-8', 'replace').splitlines():
                diagnostic = re.match(r'^\S*readelf\S*: ((?:Warning|Error):.*)', line)
                if diagnostic:
                    warned = True; sigs[signature(diagnostic[1])] += 1
        if warned: f.add('readelf_diagnostic')
        for x in f or {'no_flag'}:
            flags[x] += 1
    print(f'export_incomplete_{side}', len(bad), 'flags', dict(flags))
    if sigs:
        print(f'  readelf_signatures_{side}', top(sigs, 8))
ee = f'{r}/extraction-errors.csv'
if os.path.isfile(ee):
    import csv
    rows = list(csv.DictReader(open(ee, newline='', errors='replace')))
    print('extraction_errors', len(rows), 'by_side_stage_code_tool',
          top(C(f"{fixed(x.get('side'), {'baseline','candidate'})}/{fixed(x.get('stage'), {'metadata','extraction','payload','elf','identity'})}/{fixed(x.get('reason_code'), REASONS)}/{fixed(x.get('tool'), {'rpm','rpm2cpio','readelf','llvm-readelf'})}" for x in rows), 12))
print('END OF VD-1 DETAIL')
EOF
)" "$W" "$tag" 2>"$log" || stop "detail failed (see private detail log in WORK; do not share it)"
}

case "${1:-}" in
  check) cmd_check ;;
  prepare) cmd_prepare ;;
  run) cmd_run "${2:-}" ;;
  summary) shift; cmd_summary "$@" ;;
  rerun) cmd_rerun "${2:-}" "${3:-}" ;;
  detail) cmd_detail "${2:-}" "${3:-}" ;;
  *) stop "usage: $0 check | prepare | run <WORK> | summary <WORK> [tag...] | rerun <WORK> <commit> | detail <WORK> <tag>" ;;
esac
