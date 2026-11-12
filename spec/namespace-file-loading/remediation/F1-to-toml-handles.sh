#!/bin/sh
# Checker for review cycle 1, F1 (to_toml writes to a handle by the type it takes, whatever its
# class). POSIX sh; run from anywhere in the repository:
#
#     sh spec/namespace-file-loading/remediation/F1-to-toml-handles.sh
#
# Exports the index and the merge-base with origin/develop under a fresh directory in $TMPDIR (left
# in place and printed), runs F1-to-toml-handles.py on each tree on 3.9 and 3.14 in the profile's
# environment, and compares the two (see the .py header for what each corpus holds and asserts).
# Grades the index, like the frozen gate: stage the work first. Needs git, tar and uv; the caller
# sets UV_CACHE_DIR outside the repository and a writable TMPDIR.

set -eu

here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
cd "$root"
pythons='3.9 3.14'
git diff --quiet -- src tests docs || { echo "FAIL: unstaged changes under src/, tests/ or docs/: stage them first"; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/nfl-f1.XXXXXX")
work=$(cd "$work" && pwd -P)
printf '%s\n' "== F1 checker work files: $work"
git checkout-index -a --prefix="$work/head/"
mkdir "$work/base"
git archive --format=tar "$(git merge-base origin/develop HEAD)" | (cd "$work/base" && tar -xf -)
for v in $pythons; do
    for side in base head; do
        (unset PYTEST_ADDOPTS PYTEST_PLUGINS
         cd "$work/$side" && PYTHONDONTWRITEBYTECODE=1 uv run --isolated --no-project --python "$v" \
            --with tomli --with tomli-w --with-editable "$work/$side" \
            python -I "$here/F1-to-toml-handles.py" run) > "$work/$side-$v.json" 2> "$work/$side-$v.err" || {
            tail -n 20 "$work/$side-$v.err"; echo "FAIL: the F1 checker crashed on the $side tree, $v"; exit 1; }
    done
    uv run --isolated --no-project --python 3.14 python -I "$here/F1-to-toml-handles.py" compare \
        "$work/base-$v.json" "$work/head-$v.json"
done
printf '%s\n' "ok F1 checker"
