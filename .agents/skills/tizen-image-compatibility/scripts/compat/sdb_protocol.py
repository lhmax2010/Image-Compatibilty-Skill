"""Fixed remote operations for the authorized SDB runtime runner."""

# Each operation executes in a new SDB shell. Only its positional data is substituted.
SESSION = r'''
set -eu
export LC_ALL=C
boot="$(cat /proc/sys/kernel/random/boot_id)"
uid="$(id -u)"
[ "$uid" -gt 0 ]
printf 'BOOT=%s\nUID=%s\n' "$boot" "$uid"
'''

BIND = SESSION + r'''
[ "$boot" = "$1" ] && [ "$uid" = "$2" ]
shift 2
'''

DIRECTORY = r'''
dir=$1; dir_id=$2; shift 2
[ -d "$dir" ] && [ ! -L "$dir" ] && [ "$dir" = "$(readlink -f -- "$dir")" ]
[ "$(stat -c '%d:%i:%u:%a' "$dir")" = "$dir_id" ]
'''

ADMIT = SESSION + r'''
[ "$(uname -m)" = armv7l ]
for release in /etc/os-release /etc/tizen-release; do
    grep -Fx "BUILD_ID=$1" "$release" >/dev/null
done
shift
serial="$(awk -F: '/^Serial[[:space:]]*:/ {gsub(/[[:space:]]/,"",$2); print $2; exit}' /proc/cpuinfo)"
[ -n "$serial" ]
finger="$(printf '%s' "$serial" | sha256sum)"
printf 'DEVICE=%s\n' "${finger%% *}"
base="$HOME/.cache"
[ -d "$base" ] && [ ! -L "$base" ] && [ "$base" = "$(readlink -f -- "$base")" ]
[ -w "$base" ] && [ -x "$base" ] && [ "$(stat -c '%u' "$base")" = "$uid" ]
printf 'BASE=%s\n' "$base"
mount="$(awk -v p="$base" '($5=="/" || $5==p || index(p,$5"/")==1) && length($5)>=n {n=length($5); opts=$6} END {print opts}' /proc/self/mountinfo)"
printf 'MOUNT=%s\n' "$mount"
manager="$(systemctl --user show -p ControlGroup --value)"
printf 'MANAGER=%s\n' "$manager"
[ -r "/sys/fs/cgroup/systemd$manager/cgroup.procs" ]
for name in systemd-run setsid sha256sum base64 head wc mktemp; do command -v "$name" >/dev/null; done
for name do
    path="$(readlink -f -- "/lib/$name")"
    [ -f "$path" ]
    sum="$(sha256sum "$path")"
    printf 'FILE|%s|%s|%s\n' "$name" "$path" "${sum%% *}"
done
'''

CREATE = BIND + r'''
umask 077
base=$1; attempt=$2
[ "$base" = "$HOME/.cache" ] && [ "$base" = "$(readlink -f -- "$base")" ] && [ ! -L "$base" ]
[ -w "$base" ] && [ -x "$base" ] && [ "$(stat -c '%u' "$base")" = "$uid" ]
dir="$(mktemp -d "$base/tizen-compat-$attempt-XXXXXXXX")"
printf 'DIR=%s\nDIR_ID=%s\n' "$dir" "$(stat -c '%d:%i:%u:%a' "$dir")"
'''

DEPLOYED = BIND + DIRECTORY + r'''
f="$dir/probe"
[ -f "$f" ] && [ ! -L "$f" ] && [ "$(stat -c '%u' "$f")" = "$uid" ]
chmod 0700 "$f"
x="$(sha256sum "$f")"
printf 'ELF=%s\n' "${x%% *}"
'''

CHECK_BUNDLE = BIND + DIRECTORY + r'''
for f do
    [ -f "$dir/$f" ] && [ ! -L "$dir/$f" ] && [ "$(stat -c '%u' "$dir/$f")" = "$uid" ]
    if [ "$f" = probe ]; then chmod 0700 "$dir/$f"; else chmod 0400 "$dir/$f"; fi
    sum="$(sha256sum "$dir/$f")"
    printf 'BUNDLE|%s|%s\n' "$f" "${sum%% *}"
done
n=0
for f in "$dir/"* "$dir/".*; do
    case "$f" in */.|*/..) continue;; esac
    if [ -e "$f" ] || [ -L "$f" ]; then n=$((n+1)); fi
done
printf 'COUNT=%s\n' "$n"
'''

# The actual exec replaces the independently observed shell and keeps its PID/starttime.
WORKER = r'''
set -eu
umask 077
cd -- "$1"
[ "$(id -u)" = "$3" ] && [ "$3" -gt 0 ] && [ "$(cat /proc/sys/kernel/random/boot_id)" = "$4" ]
[ -f probe ] && [ ! -L probe ] && [ "$(stat -c '%a:%u' probe)" = "700:$3" ]
printf '%s\n' "$$" > armed
while [ ! -f go ]; do /usr/bin/sleep 0.1; done
[ "$(cat go)" = "$5" ]
x="$(sha256sum probe)"
[ "${x%% *}" = "$2" ]
[ ! -e probe.stdout ] && [ ! -L probe.stdout ] && [ ! -e probe.stderr ] && [ ! -L probe.stderr ]
ulimit -c 0
ulimit -f 256
debug=libs,versions,files
[ "${6:-}" != bindings ] || debug=$debug,bindings
exec /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TMPDIR="$1" LD_DEBUG="$debug" LD_DEBUG_OUTPUT="$1/loader" "$1/probe" >probe.stdout 2>probe.stderr
'''

ARM = BIND + DIRECTORY + r'''
attempt=$1; pid=$2; start=$3; group=$4; shift 4
[ -f "$dir/armed" ] && [ ! -L "$dir/armed" ] && [ "$(cat "$dir/armed")" = "$pid" ]
[ "$(sed -n 's/^[0-9]*:name=systemd://p' "/proc/$pid/cgroup")" = "$group" ]
while [ "$#" -gt 0 ]; do
    file=$1; expected=$2; shift 2
    [ -f "$dir/$file" ] && [ ! -L "$dir/$file" ]
    x="$(sha256sum "$dir/$file")"
    [ "${x%% *}" = "$expected" ]
done
line="$(cat "/proc/$pid/stat")"
fields="${line##*) }"
set -- $fields
[ "${20}" = "$start" ]
[ ! -e "$dir/go" ] && [ ! -L "$dir/go" ]
set -C
printf '%s\n' "$attempt" > "$dir/go"
'''

# OBSERVE is called by the orchestrator, never by the worker or controller.
OBSERVE = BIND + r'''
attempt=$1; dir=$2; phase=$3
shift 3
unit="tizen-compat-$attempt.scope"
expected="/user.slice/user-$uid.slice/user@$uid.service/$unit"
printf 'ATTEMPT=%s\nPHASE=%s\nOBSERVER_PID=%s\n' "$attempt" "$phase" "$$"
systemctl --user --no-pager --full show "$unit" -p ActiveState -p ControlGroup -p RuntimeMaxUSec -p TimeoutStopUSec -p KillMode -p Result -p Delegate
group="/sys/fs/cgroup/systemd$expected"
members=''
if [ -d "$group" ]; then
    printf 'GROUP_ID=%s\n' "$(stat -c '%d:%i' "$group")"
    members="$(tr '\n' ' ' < "$group/cgroup.procs")"
    printf 'GROUP_PIDS=%s\n' "$members"
    printf 'GROUP_WRITABLE='
    if [ -w "$group/cgroup.procs" ]; then printf 'yes\n'; else printf 'no\n'; fi
    for child in "$group/"*; do
        if [ -d "$child" ]; then printf 'CHILD_GROUP=yes\n'; break; fi
    done
else
    printf 'GROUP_ABSENT=yes\n'
fi
if [ "$phase" = active ] && [ -f "$dir/armed" ] && [ ! -L "$dir/armed" ]; then
    pid="$(cat "$dir/armed")"
    case "$pid" in ''|*[!0-9]*) exit 3;; esac
    printf 'ARMED=%s\n' "$pid"

fi
if [ "$phase" = active ]; then
    set -- $members
fi
for pid do
    if line="$(cat "/proc/$pid/stat" 2>/dev/null)"; then
        fields="${line##*) }"
        set -- $fields
        [ "$#" -ge 20 ]
        printf 'PROC|%s|%s|%s|%s|%s\n' "$pid" "$1" "$3" "$4" "${20}"
    else
        [ ! -e "/proc/$pid" ] || exit 4
        printf 'GONE|%s\n' "$pid"
    fi
done
if [ ! -e "$dir" ] && [ ! -L "$dir" ]; then printf 'DIR_ABSENT=yes\n'; fi
'''

ARMED_IDENTITY = BIND + DIRECTORY + r'''
attempt=$1; pid=$2
[ -f "$dir/probe" ] && [ ! -L "$dir/probe" ]
[ -f "$dir/armed" ] && [ ! -L "$dir/armed" ] && [ "$(cat "$dir/armed")" = "$pid" ]
sum="$(sha256sum "$dir/probe")"
line="$(cat "/proc/$pid/stat")"
fields="${line##*) }"
set -- $fields
printf 'ATTEMPT=%s\nSTART=%s\nELF=%s\nDIR_ID=%s\n' "$attempt" "${20}" "${sum%% *}" "$dir_id"
printf 'CWD=%s\n' "$(readlink -f "/proc/$pid/cwd")"
printf 'PROC_CGROUP=%s\n' "$(sed -n 's/^[0-9]*:name=systemd://p' "/proc/$pid/cgroup")"
awk '/^Uid:/{print "PROC_UIDS="$2":"$3":"$4":"$5}
     /^CapEff:/{print "CapEff="$2} /^CapPrm:/{print "CapPrm="$2}' "/proc/$pid/status"
'''

RESET_TIMEOUT = BIND + r'''
unit=$1; group=$2
[ ! -e "/sys/fs/cgroup/systemd$group" ]
[ "$(systemctl --user show "$unit" -p Transient --value)" = yes ]
[ "$(systemctl --user show "$unit" -p Result --value)" = timeout ]
systemctl --user reset-failed "$unit"
'''

CAPTURE = BIND + DIRECTORY + r'''
for leaf do
    f="$dir/$leaf"
    [ -f "$f" ] && [ ! -L "$f" ]
    size="$(wc -c < "$f" | tr -d ' ')"
    [ "$size" -le 131072 ] || { printf 'OUTPUT_LIMIT=yes\n'; exit 7; }
    hash="$(sha256sum "$f")"
    printf 'FILE|%s|%s|%s|' "$leaf" "$size" "${hash%% *}"
    head -c 131073 "$f" | base64 | tr -d '\r\n'
    printf '\n'
done
'''

PROVIDERS = BIND + r'''
for path do
    real="$(readlink -f -- "$path")"
    [ -f "$real" ]
    sum="$(sha256sum "$real")"
    printf 'FILE|%s|%s|%s\n' "$path" "$real" "${sum%% *}"
done
'''

REMOVE = BIND + DIRECTORY + r'''
for leaf do rm -f -- "$dir/$leaf"; done
# Fork/exec can emit additional Loader diagnostics under child PIDs.
for path in "$dir"/loader.*; do
    [ -e "$path" ] || continue
    leaf=${path##*/loader.}
    case "$leaf" in ''|*[!0-9]*) continue;; esac
    [ -f "$path" ] && [ ! -L "$path" ] && [ "$(stat -c %u "$path")" = "$uid" ]
    rm -- "$path"
done
rmdir -- "$dir"
'''
