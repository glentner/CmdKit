#!/bin/sh
# Gate for the config-variant-collision cycle. POSIX sh; run from anywhere in the repository:
#
#     sh spec/config-variant-collision/verify/gate.sh MODE [PHASE]
#
# PHASE is P1 or P2 (default P2, the whole cycle). Modes:
#   static    change_set.py PHASE (the files changed, src/ outside config.py untouched, the
#             AGENTS.md rule line, the docs, code and docs in one commit, no spec ids in code or
#             docs, and at P2 the deferral ledger) and tests_kept.py ast PHASE (every base test
#             kept, the one changed test as written in TECH.md, the phase's named tests present).
#   suite     the profile's verify on 3.9 and 3.14 with -rA, then tests_kept.py passed PHASE: every
#             base node ID and every named test of the phase PASSED, nothing else failed; then the
#             base's own tests/test_config.py (its one changed test rewritten as GOAL words it) run
#             against the index's src/ on both Pythons, every test passing.
#   drive     drive.py on 3.9 and 3.14, each case in a fresh interpreter: the base and the staged
#             tree run the same non-collision corpus and must print the same thing; the staged
#             tree runs the collision corpus against an independent model of the rule.
#   mutants   mutants.py on 3.14: every decision on a line the cycle adds to src/cmdkit/config.py
#             is mutated in turn, and tests/test_config.py must fail for each mutant.
#   P1, P2    the phase's verify: static, suite, drive and mutants for that phase.
#   prepush   static P2 and suite P2: the cheap part, for before a push.
#
# Every mode first checks the gate itself (frozen): verify/ and PLAN.md have no uncommitted change
# and no commit since the plan commit (the latest whose subject is
# `[fix] Plan config-variant-collision: design + phased roadmap`) touches them; no commit between
# the merge-base and the plan commit changes anything outside spec/, issues/ and ROADMAP.md (so a
# plan commit made after build work is refused, whatever the build commits are called); and
# verify/'s tree at HEAD is the tree PLAN.md records. The plan commit and the tree id are also
# reported outside the repository, for the review to check against.
#
# Graded state is the index, not the working copy: stage the phase first (unstaged changes under
# src/, tests/, docs/ or AGENTS.md fail the gate). Suite, drive and mutant runs use an export of the
# index (git checkout-index) and an export of the merge-base with origin/develop, made under a fresh
# directory in $TMPDIR that is left in place for inspection and printed.
#
# Needs: git, tar, uv; network to pypi.org and files.pythonhosted.org, or a warm uv cache; the
# caller sets UV_CACHE_DIR outside the repository and a writable TMPDIR.
# Footprint: one Python process at a time, plus uv; each under 150 MB. Measured on the plan's
# prototype: static under 2 s, suite about 6 s, drive about 20 s, mutants about 90 s.

set -eu

mode=${1:?usage: gate.sh static|suite|drive|mutants|P1|P2|prepush [P1|P2]}
phase=${2:-P2}
case "$mode" in P1|P2) phase=$mode ;; esac
case "$phase" in P1|P2) ;; *) echo "unknown phase: $phase"; exit 2 ;; esac
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
cd "$root"
slug=config-variant-collision
rel=spec/$slug/verify
plan_subject="[fix] Plan $slug: design + phased roadmap"
pythons='3.9 3.14'

say() { printf '%s\n' "== $*"; }

gatepy() {
    # Gate Python: isolated, never the project environment, never this directory on sys.path.
    uv run --isolated --no-project --python 3.14 python -I "$@"
}

inenv() {
    # The profile's verify environment for one Python and one tree; the rest is the command.
    v=$1; tree=$2; shift 2
    (unset PYTEST_ADDOPTS PYTEST_PLUGINS PYTEST_DEBUG_TEMPROOT
     cd "$tree" && PYTHONDONTWRITEBYTECODE=1 uv run --isolated --no-project --python "$v" \
        --with pytest --with hypothesis --with tomli --with tomli-w --with pyyaml \
        --with-editable "$tree" "$@")
}

frozen() {
    plan=$(git log --format='%H %s' HEAD | awk -v s="$plan_subject" 'substr($0, 42) == s { print $1; exit }')
    [ -n "$plan" ] || { echo "FAIL: no plan commit ($plan_subject) in HEAD's history"; exit 1; }
    mb=$(git merge-base origin/develop HEAD)
    early=$(git log --format=%h "$mb..$plan" -- . ':!spec' ':!issues' ':!ROADMAP.md' | head -n 1)
    [ -z "$early" ] || {
        echo "FAIL: commit $early, before the plan commit, changes files outside spec/, issues/ and ROADMAP.md:"
        echo "      a plan commit after build commits is refused, whatever their subjects"; exit 1; }
    for f in "$rel" "spec/$slug/PLAN.md"; do
        git diff --quiet HEAD -- "$f" || { echo "FAIL: $f has unstaged changes"; exit 1; }
        git diff --cached --quiet HEAD -- "$f" || { echo "FAIL: $f has staged changes"; exit 1; }
        [ -z "$(git log --format=%h "$plan..HEAD" -- "$f")" ] || {
            echo "FAIL: a commit since the plan commit touches $f"; exit 1; }
    done
    [ -z "$(git ls-files --others --exclude-standard -- "$rel")" ] || { echo "FAIL: untracked files in $rel"; exit 1; }
    want=$(sed -n 's/^Frozen gate tree: `\([0-9a-f]\{40\}\)`.*/\1/p' "spec/$slug/PLAN.md")
    have=$(git rev-parse "HEAD:$rel")
    [ -n "$want" ] && [ "$want" = "$have" ] || {
        echo "FAIL: $rel is tree $have at HEAD; PLAN.md records '${want:-none}'"; exit 1; }
    say "frozen: $rel is tree $have, plan commit $(git rev-parse --short "$plan")"
}

staged() {
    git diff --quiet -- src tests docs AGENTS.md || {
        echo "FAIL: unstaged changes under src/, tests/, docs/ or AGENTS.md: stage the phase first"; exit 1; }
}

workdir() {
    # an explicit template: macOS mktemp -d alone ignores $TMPDIR
    work=$(mktemp -d "${TMPDIR:-/tmp}/$slug-gate.XXXXXX") || { echo "FAIL: mktemp needs a writable \$TMPDIR"; exit 1; }
    work=$(cd "$work" && pwd -P)
    say "work files: $work"
}

exports() {
    [ -d "$work/head" ] && return 0
    git checkout-index -a --prefix="$work/head/"
    mkdir "$work/base"
    git archive --format=tar "$(git merge-base origin/develop HEAD)" | (cd "$work/base" && tar -xf -)
}

static() {
    say "static $phase: change set, docs, one commit, ledger; tests kept"
    gatepy "$here/change_set.py" "$phase"
    gatepy "$here/tests_kept.py" ast "$phase"
}

suite() {
    say "suite $phase: the profile's verify on $pythons, from the index"
    exports
    outs=''
    for v in $pythons; do
        inenv "$v" "$work/head" python -m pytest -p no:cacheprovider -rA > "$work/suite-$v.out" 2>&1 || {
            tail -n 30 "$work/suite-$v.out"; echo "FAIL: the suite failed on $v"; exit 1; }
        tail -n 1 "$work/suite-$v.out"
        outs="$outs $work/suite-$v.out"
    done
    gatepy "$here/tests_kept.py" passed "$phase" ${outs}
    say "suite: the base's tests/test_config.py, its one changed test as GOAL words it, on $pythons"
    gatepy "$here/tests_kept.py" basefile "$work/head/tests/test_config_base_kept.py"
    want=$(grep -c '^tests/test_config.py::' "$here/base-nodeids.txt")
    for v in $pythons; do
        inenv "$v" "$work/head" python -m pytest -p no:cacheprovider -q tests/test_config_base_kept.py \
            > "$work/basefile-$v.out" 2>&1 || {
            tail -n 30 "$work/basefile-$v.out"; echo "FAIL: a base test fails on $v"; exit 1; }
        last=$(tail -n 1 "$work/basefile-$v.out")
        case "$last" in
            "$want passed in "*) printf '%s\n' "ok base tests on $v: $last" ;;
            *) echo "FAIL: expected $want base tests to pass on $v, got: $last"; exit 1 ;;
        esac
    done
}

drive() {
    say "drive $phase: base against the index, fresh interpreters, on $pythons"
    exports
    for v in $pythons; do
        for side in base head; do
            inenv "$v" "$work/$side" python -I "$here/drive.py" run "$phase" > "$work/drive-$side-$v.json" 2> "$work/drive-$side-$v.err" || {
                tail -n 20 "$work/drive-$side-$v.err"; echo "FAIL: the drive crashed on the $side tree, $v"; exit 1; }
        done
        gatepy "$here/drive.py" compare "$phase" "$work/drive-base-$v.json" "$work/drive-head-$v.json"
    done
}

mutants() {
    say "mutants: decisions on the lines the cycle adds to src/cmdkit/config.py"
    exports
    base=$(git merge-base origin/develop HEAD)
    git diff --cached -U0 "$base" -- src/cmdkit/config.py > "$work/config.diff"
    inenv 3.14 "$work/head" python -I "$here/mutants.py" --tree "$work/head" --diff "$work/config.diff" \
        --log "$work/mutants.log"
}

frozen
case "$mode" in
    static|prepush|suite|drive|mutants|P1|P2) staged ;;
    *) echo "unknown mode: $mode"; exit 2 ;;
esac
workdir
case "$mode" in
    static) static ;;
    suite) suite ;;
    drive) drive ;;
    mutants) mutants ;;
    prepush) static; suite ;;
    P1|P2) static; suite; drive; mutants ;;
esac
printf '%s\n' "ok gate $mode $phase"
