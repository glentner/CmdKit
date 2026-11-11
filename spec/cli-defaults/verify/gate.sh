#!/bin/sh
# Gate for the cli-defaults cycle. POSIX sh; run from anywhere in the repository:
#
#     sh spec/cli-defaults/verify/gate.sh MODE
#
# Modes:
#   frozen     verify/ is as the latest plan commit left it: no staged, unstaged or untracked
#              change, and no commit since that plan commit touches it; and every plan commit
#              touches only spec/cli-defaults/, issues/ and ROADMAP.md (a build commit can't
#              carry the subject and re-freeze verify/ beside its code).
#   static P1  change_set.py P1, graded from the cycle's first plan commit (the tree the build
#              started from, so a revised plan does not move it): the files changed; the § Invariants 3 line
#              gone, and nothing else in AGENTS.md changed; docs/api/app.rst changed; no spec ids
#              in added source or test lines; test_app_group_usage unchanged.
#   static P2  change_set.py P2: all of P1's checks, plus the deferral ledger over TECH.md.
#   errors     drive_main.py errors, on 3.9 and 3.14: argument errors in fresh interpreters.
#   noargs     drive_main.py noargs, on 3.9 and 3.14: bare groups and bare applications.
#   tests      tests/test_app.py on 3.9 and 3.14 (the profile's verify, narrowed to the slice),
#              with --hypothesis-seed=0: unseeded, an existing test fails about 1 run in 40 on
#              develop (issues/test-invalid-options-help-prefix.md); seed 0 does not hit it.
#   mutants P1 mutants.py P1 on 3.9 and 3.14 (review cycle 1, finding F5): every decision in the
#              argument-error report, each mutant killed by tests/test_app.py alone; the anchors
#              are PLAN.md § 2's lines, and a missing one is red.
#   mutants P2 mutants.py P2: P1's mutants and the bare group's decisions.
#   P1         frozen, static P1, errors, tests, mutants P1: the phase's verify.
#   P2         frozen, static P2, errors, noargs, tests, mutants P2: the phase's verify.
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
# P2 takes about 90 s warm.
#
# Dry runs only: CLI_DEFAULTS_GATE_DRYRUN=1 skips `frozen` (there is no plan commit yet) and grades
# the change set from CLI_DEFAULTS_GATE_BASE instead of the first plan commit. A build never sets it.

set -eu

mode=${1:?usage: gate.sh frozen|static P1|static P2|errors|noargs|tests|mutants P1|mutants P2|P1|P2}
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
cd "$root"
rel=spec/cli-defaults/verify
pythons='3.9 3.14'

say() { printf '%s\n' "== $*"; }

plan_commits() {
    # the plan commits by their subject line only (a body that quotes one doesn't count), newest first
    git log --format='%H %s' HEAD | awk '$2 == "[fix]" && $3 == "Plan" && $4 == "cli-defaults:" { print $1 }'
}

plan_commit() {
    # the latest plan commit: what verify/ is frozen at
    plan_commits | head -n 1
}

base() {
    # the first plan commit: what the change set is graded from
    if [ "${CLI_DEFAULTS_GATE_DRYRUN:-}" = 1 ]; then
        printf '%s\n' "${CLI_DEFAULTS_GATE_BASE:?dry run needs CLI_DEFAULTS_GATE_BASE}"
    else
        b=$(plan_commits | tail -n 1)
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
    plan=$(plan_commit)
    [ -n "$plan" ] || { echo "FAIL: no plan commit ([fix] Plan cli-defaults: ...) in HEAD's history"; exit 1; }
    git diff --quiet HEAD -- "$rel" || { echo "FAIL: $rel has unstaged changes"; exit 1; }
    git diff --cached --quiet HEAD -- "$rel" || { echo "FAIL: $rel has staged changes"; exit 1; }
    [ -z "$(git ls-files --others --exclude-standard -- "$rel")" ] || { echo "FAIL: untracked files in $rel"; exit 1; }
    [ -z "$(git log --format=%h "$plan..HEAD" -- "$rel")" ] || {
        echo "FAIL: a commit since the plan commit touches $rel"; exit 1; }
    for c in $(plan_commits); do
        stray=$(git show --name-only --format= "$c" | grep -v -e '^spec/cli-defaults/' -e '^issues/' -e '^ROADMAP\.md$' || true)
        [ -z "$stray" ] || { echo "FAIL: plan commit $c touches more than the plan's files: $stray"; exit 1; }
    done
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

mutants() {
    for v in $pythons; do
        inenv "$v" python -I "$here/mutants.py" "$exp" "${1:?mutants needs P1 or P2}"
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
    mutants) export_index; mutants "${2:-}" ;;
    P1) frozen; static P1; export_index; drive errors; tests; mutants P1 ;;
    P2) frozen; static P2; export_index; drive errors; drive noargs; tests; mutants P2 ;;
    *) echo "usage: gate.sh frozen|static P1|static P2|errors|noargs|tests|mutants P1|mutants P2|P1|P2"; exit 2 ;;
esac
say "gate $mode: ok"
