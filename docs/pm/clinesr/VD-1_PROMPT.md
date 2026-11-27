# ClineSR Task VD-1: VD RPM Sample Measurement (v1.5.1, measurement only)

**Machine:** the authorized VD workstation/server that already holds the two VD RPM repositories (about 5,880 RPMs each side).
**Requested by:** the project owner. Technical PM: Claude.
**Type:** measurement only. This is NOT an acceptance run, and no compatibility conclusions should be drawn from it.

## Purpose

Run the existing v1.5.1 tool on a small sample (about 150 packages per side) of the real VD RPM repositories, and report only counts, time, memory and disk. The PM needs the following numbers:

1. Real ARM throughput.
2. How many real ARM libraries the tool fails to read completely (a known v1.5.1 defect).
3. How many objects use ASan.
4. Whether the tool runs end-to-end on this machine.

## Hard rules (do not break any of these)

1. Do NOT modify, move, rename or delete anything in the RPM repository directories. Only read and copy from them.
2. Do NOT install software, use sudo, mount anything, or run any program found inside an RPM.
3. Write only inside the new work directory created in Step 2.
4. Do NOT upload, attach, push or send any RPM, ELF, report file, package list or package name anywhere. Report ONLY the summary block in Step 8.
5. Do NOT write your own analysis scripts. Do NOT change the tool's code or configuration. Use only the commands below.
6. If any step fails or does not match what is described, STOP and report the step number, the exact command and the last 30 lines of its output. Do not try alternative approaches.
7. Do not run the full repository. Only the sample.

## Step 1: Check prerequisites

Run:

```bash
command -v python3 rpm rpm2cpio readelf git; python3 --version; df -h "$HOME" | tail -1
```

STOP if any of `python3`, `rpm`, `rpm2cpio`, `readelf` or `git` is missing, if Python is older than 3.10, or if less than 30 GB is free. If the free space looks fine but you are unsure, report it and continue.

## Step 2: Set the input paths and create the work directory

Ask the user for the two repository paths if you do not know them. Then set:

```bash
BASE=/path/to/baseline-gcc-rpms        # TIZEN-ONEMAIN-KantSU2e-RELEASE_20261001.3 repository
CAND=/path/to/candidate-llvm-asan-rpms # TIZEN-ASAN-PUBLIC-KantSU2e-RELEASE_20261125.2 repository
WORK="$HOME/compat-vd1-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$WORK"/base "$WORK"/cand
ls "$BASE" >/dev/null && ls "$CAND" >/dev/null && echo "inputs ok: $WORK"
```

## Step 3: Get the exact v1.5.1 tool (read-only, no branch changes)

If the repository is not already cloned on this machine, clone it into the work directory. Then export the exact v1.5.1 commit without changing any branch:

```bash
cd "$WORK"
git clone --quiet https://github.com/lhmax2010/Image-Compatibilty-Skill.git repo
git -C repo cat-file -e 2d43c58b8753c53f58fae906cc4c821bd6227397^{commit} && echo "commit ok"
mkdir skill151 && git -C repo archive 2d43c58b8753c53f58fae906cc4c821bd6227397 .agents/skills/tizen-image-compatibility | tar -x -C skill151
SKILL="$WORK/skill151/.agents/skills/tizen-image-compatibility"
cat "$SKILL/VERSION"
```

Expected output: `commit ok` and `1.5.1`. Otherwise STOP.

## Step 4: Select about 150 package names that exist on both sides

This step only reads RPM headers and may take several minutes.

```bash
for side in BASE CAND; do d=${!side}
  find "$d" -name '*.rpm' ! -name '*debug*' -print0 |
    xargs -0 rpm -qp --qf '%{NAME}\t%{SIZE}\n' 2>/dev/null | sort -u > "$WORK/$side.names"
done
join -t$'\t' <(sort "$WORK/BASE.names") <(sort "$WORK/CAND.names") | sort -t$'\t' -k2,2nr |
  awk -F'\t' 'NR<=75 || /icu|webkit|chromium|efl|stdc\+\+|glibc|gcc|dbus|glib/' | head -150 | cut -f1 > "$WORK/sample.names"
wc -l "$WORK/BASE.names" "$WORK/CAND.names" "$WORK/sample.names"
```

Expected: `sample.names` contains between 100 and 150 lines. Do NOT print or report the names themselves.

## Step 5: Copy the sample RPMs (originals are only read)

```bash
for pair in "$BASE:base" "$CAND:cand"; do src=${pair%%:*}; dst=$WORK/${pair##*:}
  find "$src" -name '*.rpm' ! -name '*debug*' | while read -r f; do
    n=$(rpm -qp --qf '%{NAME}' "$f" 2>/dev/null)
    grep -qxF "$n" "$WORK/sample.names" && cp -p "$f" "$dst/"
  done
done
ls "$WORK/base" | wc -l; ls "$WORK/cand" | wc -l; du -sh "$WORK/base" "$WORK/cand"
```

## Step 6: Run the tool, measuring time and memory

This step may take a long time; do not interrupt it.

```bash
cd "$WORK"
python3 - "$SKILL" "$WORK" <<'EOF'
import resource, subprocess, sys, time
skill, work = sys.argv[1], sys.argv[2]
t = time.time()
rc = subprocess.call(['python3', f'{skill}/scripts/tizen_compat.py', '--baseline', f'{work}/base',
                      '--candidate', f'{work}/cand', '--rpm-mode', 'payload', '--mode', 'static',
                      '--output', f'{work}/report'],
                     stdout=open(f'{work}/run.stdout', 'w'), stderr=open(f'{work}/run.stderr', 'w'))
print('EXIT', rc, 'WALL_SECONDS', round(time.time() - t, 1),
      'PEAK_RSS_MB', round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1))
EOF
tail -1 "$WORK/run.stdout"; tail -5 "$WORK/run.stderr"; du -sh "$WORK/report"
```

An exit code of 0, 1 or 3 is acceptable for a measurement run. Exit 2 means an input error: STOP and report.

## Step 7: Compute the summary (counts only)

```bash
python3 - "$WORK/report" <<'EOF'
import collections, json, sys
r = sys.argv[1]
for side in ('baseline', 'candidate'):
    m = json.load(open(f'{r}/{side}-manifest.json'))
    o = m['elf_objects']; c = m['repository']['counts']
    print(f'## {side}')
    print('rpm_total', c['rpm_total'], 'metadata_complete', c['metadata_complete'],
          'extracted', c['extracted'], 'extraction_failed', c['extraction_failed'])
    print('elf_objects', len(o), 'elf_complete', c['elf_complete'],
          'export_inventories_complete', c['export_inventories_complete'])
    print('machines', dict(collections.Counter(x.get('machine') for x in o)))
    print('classes', dict(collections.Counter(x.get('class') for x in o)))
    print('elf_types', dict(collections.Counter((x.get('type') or '?').split()[0] for x in o)))
    print('export_status', dict(collections.Counter(x.get('export_inventory_status') for x in o)))
    print('incomplete_reasons', dict(collections.Counter(
        ('stdout>16MiB/limit' if 'limit' in str(x.get('error', '')) else
         'readelf-error' if x.get('error') else 'parse/size-format')
        for x in o if x.get('export_inventory_status') == 'UNKNOWN')))
    print('asan_objects', sum(any('asan' in n for n in x.get('needed', [])) for x in o))
    print('exports_total', c['exports'], 'imports_total', c['imports'])
res = json.load(open(f'{r}/results.json'))
print('## result')
print('status', res['status'], 'gate', res['quality_gate']['status'], 'findings', res['summary']['findings'])
print('by_status', res['summary']['by_status'])
print('inventory_states', res['repository']['inventory_states'])
EOF
```

## Step 8: Report back

Give the user ONLY this block, filled with the printed values. It must contain no package names, no file paths from inside the RPMs and no symbol names.

```
VD-1 RESULT (v1.5.1, sample)
date_utc:
tool_version: 1.5.1 (commit 2d43c58)
sample_packages: base=<n> cand=<n>   sample_size_on_disk: base=<..> cand=<..>
exit_code / wall_seconds / peak_rss_mb:
report_size_on_disk:
<paste the full output of Step 7 here>
last line of run.stdout:
any errors in run.stderr (last 5 lines):
notes (anything unexpected, or steps that needed a STOP):
```

Keep the work directory. Do not delete it until the PM asks you to.
