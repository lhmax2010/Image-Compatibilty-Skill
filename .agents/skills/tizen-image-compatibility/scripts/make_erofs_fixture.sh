#!/usr/bin/env bash
# Generate a pair of standard EROFS images containing only synthetic fixtures.
set -euo pipefail
umask 077
[[ $# == 1 ]] || { echo "Usage: $0 NEW_WORKSPACE_DIRECTORY" >&2; exit 2; }
workspace=$(pwd -P)
target=$(realpath -m -- "$1")
[[ $target == "$workspace/"* && ! -e $target && ! -L $target ]] || exit 2
for tool in python3 gcc mkfs.erofs sha256sum; do
    command -v "$tool" >/dev/null || { echo "Missing fixture tool $tool" >&2; exit 3; }
done
scripts=$(cd -P -- "$(dirname -- "$0")" && pwd -P)
mkdir -- "$target"
mkdir -- "$target/tmp"
export TMPDIR="$target/tmp" TMP="$target/tmp" TEMP="$target/tmp"
python3 -B "$scripts/make_synthetic_fixture.py" "$target/fixture"
for side in baseline candidate; do
    mkfs.erofs "$target/$side.erofs" "$target/fixture/$side"
done
(cd "$target" && sha256sum baseline.erofs candidate.erofs > SHA256SUMS)
