#!/bin/sh
# Checker for review cycle 1, F2 (the tests this cycle adds hold on every CI leg, Windows' text
# layer included). POSIX sh; run from anywhere in the repository:
#
#     sh spec/namespace-file-loading/remediation/F2-windows-text-layer.sh
#
# Exports the index under a fresh directory in $TMPDIR (left in place and printed), runs the whole
# suite on 3.9 and 3.14 in the profile's environment under F2-windows-text-layer.py's emulation of
# the Windows text layer, and checks the run (see the .py header). Grades the index: stage the work
# first. Needs git and uv; the caller sets UV_CACHE_DIR outside the repository and a writable TMPDIR.

set -eu

here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
cd "$root"
pythons='3.9 3.14'
git diff --quiet -- src tests docs || { echo "FAIL: unstaged changes under src/, tests/ or docs/: stage them first"; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/nfl-f2.XXXXXX")
work=$(cd "$work" && pwd -P)
printf '%s\n' "== F2 checker work files: $work"
git checkout-index -a --prefix="$work/head/"
for v in $pythons; do
    (unset PYTEST_ADDOPTS PYTEST_PLUGINS
     cd "$work/head" && PYTHONDONTWRITEBYTECODE=1 uv run --isolated --no-project --python "$v" \
        --with pytest --with hypothesis --with tomli --with tomli-w --with pyyaml --with-editable "$work/head" \
        python -I "$here/F2-windows-text-layer.py" run -p no:cacheprovider -rA -s tests) \
        > "$work/winsim-$v.out" 2>&1 || { tail -n 30 "$work/winsim-$v.out"; echo "FAIL: the suite failed under the Windows text layer on $v"; }
    tail -n 1 "$work/winsim-$v.out"
    uv run --isolated --no-project --python 3.14 python -I "$here/F2-windows-text-layer.py" check "$work/winsim-$v.out"
done
printf '%s\n' "ok F2 checker"
