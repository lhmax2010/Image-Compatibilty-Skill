#!/usr/bin/env bash
# VD-1 measurement kit (revision 5). FOR CLINESR ONLY. Measurement only, not acceptance.
#
# Usage, from the ClineSR workspace root:
#   bash .local-work/vd1_measure.sh check
#   BASE=<baseline rpm dir> CAND=<candidate rpm dir> bash .local-work/vd1_measure.sh prepare
#   bash .local-work/vd1_measure.sh run <WORK>
#   bash .local-work/vd1_measure.sh summary <WORK>
#   bash .local-work/vd1_measure.sh rerun <WORK> <40-hex commit on origin/main>   (revision 5)
#   bash .local-work/vd1_measure.sh detail <WORK> <7-hex tag>                     (revision 5)
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

cmd_summary() {
  need_work "${1:-}"
  local log
  log=$(mktemp "$W/summary.private.XXXXXXXX.log") || stop "could not create private summary log"
  shift
  local t; for t in "$@"; do [[ "$t" =~ ^[0-9a-f]{7}$ ]] || stop "tags must be 7 hex characters"; done
  python3 - "$W" "${V151:0:7}" "${FIX:0:7}" "$@" 2>"$log" <<'EOF' || stop "summary failed (see private summary log in WORK; do not share it)"
import collections, json, os, re, sys
w, *tags = sys.argv[1:]
def size(p):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
print('VD-1 RESULT (revision 5, sample, counts only)')
print('sample: base_rpms', len(os.listdir(f'{w}/base')), 'cand_rpms', len(os.listdir(f'{w}/cand')),
      'base_bytes', size(f'{w}/base'), 'cand_bytes', size(f'{w}/cand'))
for tag in tags:
    r = f'{w}/report-{tag}'
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
        m = json.load(open(f'{r}/{side}-manifest.json'))
        o = m['elf_objects']; c = m['repository']['counts']
        print(f'## {side}', 'rpm_total', c.get('rpm_total'), 'metadata_complete', c.get('metadata_complete'),
              'extracted', c.get('extracted'), 'extraction_failed', c.get('extraction_failed'))
        print('  elf_objects', len(o), 'elf_complete', c.get('elf_complete'),
              'export_inventories_complete', c.get('export_inventories_complete'))
        print('  machines', dict(collections.Counter(x.get('machine') for x in o)),
              'classes', dict(collections.Counter(x.get('class') for x in o)))
        print('  roles', dict(collections.Counter(x.get('elf_runtime_role') for x in o)))
        print('  export_status', dict(collections.Counter(x.get('export_inventory_status') for x in o)))
        print('  incomplete_reason_codes', dict(collections.Counter(
            x.get('export_inventory_reason_code') or ('limit' if 'limit' in str(x.get('error', '')) else 'other')
            for x in o if x.get('export_inventory_status') == 'UNKNOWN')))
        print('  asan_objects', sum(any('asan' in n for n in x.get('needed', [])) for x in o),
              'exports_total', c.get('exports'), 'imports_total', c.get('imports'))
    res = json.load(open(f'{r}/results.json'))
    rr = res.get('repository', {})
    print('## result status', res['status'], 'gate', res['quality_gate']['status'], 'findings', res['summary']['findings'])
    print('  by_status', res['summary']['by_status'])
    print('  inventory_states', rr.get('inventory_states'))
    print('  comparison_validity', rr.get('comparison_validity'), 'confounders', rr.get('confounders'))
    print('  instrumentation_downgrades', rr.get('instrumentation_downgrades'))
    req = rr.get('requirements') or {}
    print('  requirements_by_kind', req.get('by_kind'))
    print('  requirements_by_reason', req.get('by_reason'))
    sd = rr.get('symbol_differences') or {}
    print('  symbol_differences_by_role', {k: v.get('by_change') for k, v in (sd.get('by_role') or {}).items()})
    rc = collections.Counter(f.get('reason_code') for f in res['findings'] if f.get('reason_code'))
    print('  reason_codes', dict(rc.most_common(20)))
    inc = collections.Counter((f['dimension'], f.get('reason_code') or 'none') for f in res['findings']
                              if f['status'] == 'INCOMPATIBLE')
    print('  incompatible_by_dimension_reason', {f'{a}/{b}': n for (a, b), n in inc.most_common(15)})
    if os.path.exists(f'{r}/run-summary.json'):
        s = json.load(open(f'{r}/run-summary.json'))
        print('  run_summary', {k: s.get(k) for k in ('requested_objective', 'objective_completion',
              'execution_status', 'compatibility_status', 'coverage_status', 'ci_gate_status')})
print('END OF VD-1 RESULT')
EOF
}

cmd_detail() {
  need_work "${1:-}"
  local tag=${2:-} log
  [[ "$tag" =~ ^[0-9a-f]{7}$ ]] || stop "tag must be 7 hex characters"
  [ -d "$W/report-$tag" ] && [ ! -L "$W/report-$tag" ] || stop "report-$tag missing; run 'run' or 'rerun' first"
  log=$(mktemp "$W/detail.private.XXXXXXXX.log") || stop "could not create private detail log"
  python3 - "$W" "$tag" 2>"$log" <<'EOF' || stop "detail failed (see private detail log in WORK; do not share it)"
import collections, json, os, re, sys
w, tag = sys.argv[1:]
r = f'{w}/report-{tag}'
C = collections.Counter
def top(counter, n=15):
    return dict(counter.most_common(n))
print(f'VD-1 DETAIL (revision 5, tag {tag}, counts only)')
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
print('findings', len(F), 'by_dimension_status', top(C(f"{f['dimension']}/{f['status']}" for f in F), 20))
print('unknown_by_dimension_reason', top(C(f"{f['dimension']}/{f.get('reason_code') or 'none'}" for f in F if f['status'] == 'UNKNOWN'), 20))
def kind(f):
    i, b, c = f.get('interface') or '', f.get('baseline'), f.get('candidate')
    if i.startswith('version definition:'): return 'VERSION_DEFINITION'
    if i.endswith(':default lookup'): return 'DEFAULT_LOOKUP'
    if i.endswith(':default symbol version'): return 'DEFAULT_SYMBOL_VERSION'
    if isinstance(b, dict) and c is None and i == b.get('name'): return 'EXPORT_REMOVED'
    if b is None and isinstance(c, dict) and i == c.get('name'): return 'EXPORT_ADDED'
    field = i.rsplit(':', 1)[-1] if ':' in i else ''
    if field in ('type', 'binding', 'visibility', 'size') and not isinstance(b, dict): return 'FIELD_' + field.upper()
    if i in ('ELF availability', 'dynamic export collection coverage', 'dynamic export applicability',
             'dynamic interface surface', 'collection coverage', 'DWARF type/layout ABI',
             'duplicate dynamic symbol identities'):
        return 'META:' + i
    return 'OTHER'
abi = [f for f in F if f['dimension'] == 'abi']
print('abi_by_kind_status_reason', top(C(f"{kind(f)}/{f['status']}/{f.get('reason_code') or 'none'}" for f in abi), 25))
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
            label = ('decrease' if (c or 0) < (b or 0) else 'increase') + '/' + str(f['status'])
        else:
            label = f'{elf_field(k, b)}->{elf_field(k, c)}'
        fields[k][re.sub(r'[^A-Za-z_>/-]', '', label)[:40]] += 1
for k in sorted(fields):
    print(f'  {k.lower()}_pairs', top(fields[k], 12))
def manifest(side):
    return json.load(open(f'{r}/{side}-manifest.json'))['elf_objects']
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
print('removed_exports', len(removed), 'by_status', dict(C(f['status'] for f in removed)))
print('  by_binding_type', top(C("/".join(elf_field(k, f['baseline'].get(field)) for k, field in (("FIELD_BINDING", "binding"), ("FIELD_TYPE", "type"))) for f in removed), 12))
print('  versioned', sum('@' in (f['baseline'].get('name') or '') for f in removed),
      'by_cxx_class', top(C(cxx(f['baseline'].get('base_name') or base(f['baseline'].get('name', ''))) for f in removed), 10))
ib = [f for f in removed if imported['baseline'][f['baseline'].get('base_name') or base(f['baseline']['name'])]]
ic = [f for f in removed if imported['candidate'][f['baseline'].get('base_name') or base(f['baseline']['name'])]]
print('  imported_by_some_baseline_object', len(ib), 'by_binding', dict(C(elf_field('FIELD_BINDING', f['baseline'].get('binding')) for f in ib)),
      'imported_by_some_candidate_object', len(ic))
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
    ):
        if re.search(pattern, line, re.IGNORECASE):
            return f'{level}: {label}'
    return f'{level}: other readelf diagnostic'
for side in ('baseline', 'candidate'):
    bad = [o for o in objs[side] if o.get('export_inventory_status') == 'UNKNOWN']
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
        if o.get('export_inventory_reason_code'): f.add('code:' + re.sub(r'[^A-Z_]', '', o['export_inventory_reason_code'])[:40])
        warned = False
        for ref in o.get('export_inventory_evidence') or []:
            if not re.fullmatch(r'evidence/[a-f0-9]{64}\.txt', ref):
                continue
            p = os.path.join(r, ref)
            if os.path.commonpath((os.path.realpath(p), os.path.realpath(r))) != os.path.realpath(r):
                continue
            if not os.path.isfile(p) or os.path.getsize(p) > 1024 * 1024:
                continue
            for line in open(p, errors='replace'):
                if re.match(r'^\S*readelf\S*: (Warning|Error)', line):
                    warned = True; sigs[signature(line.split(':', 1)[1])] += 1
        if warned: f.add('readelf_diagnostic')
        for x in f or {'no_flag'}:
            flags[x] += 1
    print(f'export_incomplete_{side}', len(bad), 'flags', dict(flags))
    if sigs:
        print(f'  readelf_signatures_{side}', top(sigs, 8))
print('END OF VD-1 DETAIL')
EOF
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
