#!/usr/bin/env bash
# FOR CLINESR ONLY. Fetch the assigned commit separately. Never commit or push.
# Usage from the ClineSR Git clone: bash .local-work/run_suite.sh <full origin/main commit> [tag]
# Only forward this script's bounded output. Private logs stay under .local-work.
set -euo pipefail
umask 077
export LC_ALL=C
fail() { printf '%s\n' 'SUITE FAILED'; exit 1; }
exec 3>&1
exec >/dev/null 2>&1
trap 'printf "%s\n" "SUITE FAILED" >&3' ERR

commit=${1:-}
tag=${2:-${commit:0:12}}
[[ $# -le 2 && $commit =~ ^[0-9a-f]{40}$ && $tag =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}$ ]] || { fail >&3; }
root=$(git rev-parse --show-toplevel)
root=$(cd -P -- "$root" && pwd -P)
local_work="$root/.local-work"
suite="$local_work/suite-$tag"
[[ ${WORK:-$suite} == "$suite" && ! -L $local_work && ! -L $local_work/tmp ]] || { fail >&3; }
git -C "$root" merge-base --is-ancestor "$commit" refs/remotes/origin/main
[[ $(git -C "$root" cat-file -t "$commit") == commit ]] || { fail >&3; }
mkdir -p -- "$local_work/tmp"
[[ $(cd -P -- "$local_work/tmp" && pwd -P) == "$local_work/tmp" ]] || { fail >&3; }
export TMPDIR="$local_work/tmp" TMP="$local_work/tmp" TEMP="$local_work/tmp"
# Refuse pre-existing scratch paths and logs, including dangling links.
mkdir -- "$suite"
mkdir -- "$suite/source"
log="$suite/suite.private.log"
git -C "$root" archive "$commit" | tar -xf - -C "$suite/source"
cd -- "$suite/source"
python3 -B -c 'import sys; print("Python " + ".".join(str(n) for n in sys.version_info[:3]))' >&3
rc=0
python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests >"$suite/stdout.private.log" 2>"$log" || rc=$?

trap - ERR
python3 -B - "$rc" "$log" >&3 <<'PY'
import re
import sys

exit_code, log = int(sys.argv[1]), sys.argv[2]
run = None
outcome = None
failures = []
with open(log, encoding='utf-8', errors='replace') as stream:
    for line in stream:
        match = re.fullmatch(r'Ran (\d+) tests? in [\d.]+s\s*', line)
        if match:
            run = int(match[1])
            outcome = None
        label = re.fullmatch(r'(OK|FAILED)(?: \(([^()]+)\))?\s*', line)
        if label:
            outcome = label.groups()
        problem = re.fullmatch(
            r'(?:FAIL|ERROR): ((?:test_[A-Za-z0-9_]+|setUpClass|tearDownClass|setUpModule|tearDownModule)) '
            r'\(((?:test_[A-Za-z0-9_]+|unittest\.loader\._FailedTest)(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\)\s*', line)
        if problem:
            method, qualified = problem.groups()
            failures.append(qualified if qualified.endswith('.' + method) else qualified + '.' + method)

counts = {}
valid = run is not None and outcome is not None
if valid and outcome[1]:
    for field in outcome[1].split(', '):
        match = re.fullmatch(r'(failures|errors|skipped|expected failures|unexpected successes)=(\d+)', field)
        if match:
            counts[match[1]] = int(match[2])
        else:
            valid = False
print('run={} failures={} errors={} skips={}'.format(
    run if run is not None else 0, counts.get('failures', 0), counts.get('errors', 0), counts.get('skipped', 0)))
for ident in sorted(set(failures)):
    print('test_id=' + ident)
ok = valid and run > 0 and exit_code == 0 and outcome[0] == 'OK'
print('SUITE OK' if ok else 'SUITE FAILED')
sys.exit(0 if ok else 1)
PY
