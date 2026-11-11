#!/bin/sh
# Gate for the cli-defaults cycle. POSIX sh; run from anywhere in the repository:
#
#     sh spec/cli-defaults/verify/gate.sh MODE
#
# Modes:
#   frozen     verify/ is as the plan commit left it: no staged, unstaged or untracked change,
#              and no commit since the plan commit touches it.
#   static P1  change_set.py P1: the files changed since the plan commit; the § Invariants 3 line
#              gone, and nothing else in AGENTS.md changed; docs/api/app.rst changed; no spec ids
#              in added source or test lines; test_app_group_usage unchanged.
#   static P2  change_set.py P2: all of P1's checks, plus the deferral ledger over TECH.md.
#   errors     drive_main.py errors, on 3.9 and 3.14: argument errors in fresh interpreters.
#   noargs     drive_main.py noargs, on 3.9 and 3.14: bare groups and bare applications.
#   tests      tests/test_app.py on 3.9 and 3.14 (the profile's verify, narrowed to the slice),
#              with --hypothesis-seed=0: unseeded, an existing test fails about 1 run in 40 on
#              develop (issues/test-invalid-options-help-prefix.md); seed 0 does not hit it.
#   P1         frozen, static P1, errors, tests: the phase's verify.
#   P2         frozen, static P2, errors, noargs, tests: the phase's verify.
#
# Every mode that installs or runs the tree uses an export of the index (git checkout-index), so a
# phase stages its work before this gate runs and the gate grades exactly what the commit will hold.
# The full suite is not run here: until the open tests-to-tmp_path change lands it writes outside
# the temporary directory; the profile's verify runs it before the push.
#
# Needs: git, uv; network to pypi.org and files.pythonhosted.org (or a warm uv cache); a writable
# $TMPDIR (the export goes to a fresh directory under it, left in place and printed). Set
# UV_CACHE_DIR to a directory outside the repository when sandboxed.
# Footprint: one interpreter at a time (uv, then pytest or one short-lived child), under 150 MB;
# P2 takes about 30 s warm.
#
# Dry runs only: CLI_DEFAULTS_GATE_DRYRUN=1 skips `frozen` (there is no plan commit yet) and grades
# the change set from CLI_DEFAULTS_GATE_BASE instead of the plan commit. A build never sets it.

set -eu

mode=${1:?usage: gate.sh frozen|static P1|static P2|errors|noargs|tests|P1|P2}
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
cd "$root"
rel=spec/cli-defaults/verify
pythons='3.9 3.14'

say() { printf '%s\n' "== $*"; }

plan_commit() {
    # the plan commit by its subject line only (a body that quotes it doesn't count)
    git log --format='%H %s' HEAD | awk '$2 == "[fix]" && $3 == "Plan" && $4 == "cli-defaults:" { print $1; exit }'
}

base() {
    if [ "${CLI_DEFAULTS_GATE_DRYRUN:-}" = 1 ]; then
        printf '%s\n' "${CLI_DEFAULTS_GATE_BASE:?dry run needs CLI_DEFAULTS_GATE_BASE}"
    else
        b=$(plan_commit)
        [ -n "$b" ] || { echo "FAIL: no plan commit ([fix] Plan cli-defaults: ...) in HEAD's history" >&2; exit 1; }
        printf '%s\n' "$b"
    fi
}

frozen() {
    if [ "${CLI_DEFAULTS_GATE_DRYRUN:-}" = 1 ]; then
        say "frozen: SKIPPED (dry run, no plan commit)"
        return 0
    fi
    say "frozen: $rel as the plan commit left it"
    plan=$(base)
    git diff --quiet HEAD -- "$rel" || { echo "FAIL: $rel has unstaged changes"; exit 1; }
    git diff --cached --quiet HEAD -- "$rel" || { echo "FAIL: $rel has staged changes"; exit 1; }
    [ -z "$(git ls-files --others --exclude-standard -- "$rel")" ] || { echo "FAIL: untracked files in $rel"; exit 1; }
    [ -z "$(git log --format=%h "$plan..HEAD" -- "$rel")" ] || {
        echo "FAIL: a commit since the plan commit touches $rel"; exit 1; }
}

export_index() {
    # an explicit template: macOS mktemp -d alone ignores $TMPDIR
    work=$(mktemp -d "${TMPDIR:-/tmp}/cli-defaults-gate.XXXXXX") || {
        echo "FAIL: mktemp needs a writable \$TMPDIR"; exit 1; }
    exp="$work/export"
    mkdir "$exp"
    git checkout-index -a --prefix="$exp/"
    say "export of the index: $exp"
}

inenv() {
    # one Python, the export installed editable, isolated from any project environment
    v=$1; shift
    (unset PYTEST_ADDOPTS PYTEST_PLUGINS
     cd "$exp" && uv run -q --isolated --no-project --python "$v" --with pytest --with hypothesis \
        --with-editable "$exp" "$@")
}

static() {
    phase=${1:?static needs P1 or P2}
    say "static $phase: change set since $(base | cut -c1-9)"
    uv run -q --isolated --no-project --python 3.14 python -I "$here/change_set.py" "$phase" "$(base)"
}

drive() {
    for v in $pythons; do
        inenv "$v" python -I "$here/drive_main.py" "$1"
    done
}

tests() {
    for v in $pythons; do
        say "tests: tests/test_app.py on $v"
        inenv "$v" python -m pytest -q -p no:cacheprovider --hypothesis-seed=0 tests/test_app.py
    done
}

case "$mode" in
    frozen) frozen ;;
    static) static "${2:-}" ;;
    errors) export_index; drive errors ;;
    noargs) export_index; drive noargs ;;
    tests) export_index; tests ;;
    P1) frozen; static P1; export_index; drive errors; tests ;;
    P2) frozen; static P2; export_index; drive errors; drive noargs; tests ;;
    *) echo "usage: gate.sh frozen|static P1|static P2|errors|noargs|tests|P1|P2"; exit 2 ;;
esac
say "gate $mode: ok"
