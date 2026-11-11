#!/bin/sh
# Gate for the tests-use-tmp-path cycle. POSIX sh; run from anywhere in the repository:
#
#     sh spec/tests-use-tmp-path/verify/gate.sh MODE
#
# Modes:
#   static      change_set.py (the files changed, no quoted /tmp under tests/, the verify row,
#               one commit for both, the deferral ledger) and same_behaviour.py ast (R5's tree).
#   selftest    the write-audit hook against its canary suite, on 3.9 and 3.14.
#   audit       R1 and R5: the suite under the write-audit hook on 3.9 and 3.14, each run with
#               --basetemp at a fresh directory and TMPDIR at another; every write lies under the
#               basetemp or in the tool caches (C1); the tests write exactly the base's file
#               names; every base node ID passes.
#   concurrent  R4, and R3 in its portable form: the suite on 3.9 and 3.14 at once, from one
#               export, both under the hook, TMPDIR shared and fresh, pytest's default basetemp;
#               both pass, every write lies under that TMPDIR or in the caches, and no file a test
#               of one run wrote is read or written by a test of the other.
#   R2          needs a run where /tmp is writable (the sandbox off): /tmp/cmdkit must not exist
#               before (a host precondition: the gate fails closed and says so); the suite on 3.9
#               and 3.14 with --basetemp at a fresh directory passes; /tmp/cmdkit still doesn't exist.
#   tmpdenied   R3 in its native form, and R4 under it: needs a run where /tmp is not writable (a
#               sandbox that denies it). Probes that, then runs the profile's verify, as AGENTS.md
#               states it at HEAD, with TMPDIR at a fresh writable directory, then `concurrent`.
#   P1          static, selftest, audit, concurrent, R2: the phase's verify (sandbox off, for R2).
#
# Every mode first checks the gate itself: verify/ has no uncommitted change, and no commit since
# the latest plan commit (the latest whose subject is `[fix] Plan tests-use-tmp-path: ...`) touches
# it. Suite runs use an export of HEAD (git archive), never the working copy, with pytest's
# environment variables (PYTEST_ADDOPTS, PYTEST_PLUGINS, PYTEST_DEBUG_TEMPROOT) unset.
#
# Needs: git, tar, uv; network to pypi.org and files.pythonhosted.org (or a warm uv cache);
# UV_CACHE_DIR set by the caller to a directory outside the repository; a writable $TMPDIR (the
# work files go to a fresh directory under it, left in place for inspection and printed).
# Footprint: at most two suite processes at once (concurrent), under 100 MB each, plus uv; P1
# takes about 15 s warm. Background runs are always waited for, and each run's own process must be
# gone afterwards (kill -0 on the PID its log records).

set -eu

mode=${1:?usage: gate.sh static|selftest|audit|concurrent|R2|tmpdenied|P1}
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
cd "$root"
rel=spec/tests-use-tmp-path/verify
pythons='3.9 3.14'

say() { printf '%s\n' "== $*"; }

gatepy() {
    # Gate Python: isolated, never the project environment, never this directory on sys.path.
    uv run --isolated --no-project --python 3.14 python -I "$@"
}

suite() {
    # The profile's verify environment for one Python, from the export; the rest is the command.
    v=$1; shift
    (unset PYTEST_ADDOPTS PYTEST_PLUGINS PYTEST_DEBUG_TEMPROOT
     cd "$exp" && uv run --isolated --no-project --python "$v" --with pytest --with hypothesis \
        --with tomli --with tomli-w --with pyyaml --with-editable "$exp" "$@")
}

frozen() {
    # the plan commit by its subject line only (a body that quotes it doesn't count)
    plan=$(git log --format='%H %s' HEAD | awk '$2 == "[fix]" && $3 == "Plan" && $4 == "tests-use-tmp-path:" { print $1; exit }')
    [ -n "$plan" ] || { echo "FAIL: no plan commit ([fix] Plan tests-use-tmp-path: ...) in HEAD's history"; exit 1; }
    git diff --quiet HEAD -- "$rel" || { echo "FAIL: $rel has uncommitted changes"; exit 1; }
    [ -z "$(git ls-files --others --exclude-standard -- "$rel")" ] || { echo "FAIL: untracked files in $rel"; exit 1; }
    [ -z "$(git log --format=%h "$plan..HEAD" -- "$rel")" ] || {
        echo "FAIL: a commit since the plan commit touches $rel"; exit 1; }
}

workdir() {
    # an explicit template: macOS mktemp -d alone ignores $TMPDIR
    work=$(mktemp -d "${TMPDIR:-/tmp}/tests-use-tmp-path-gate.XXXXXX") || {
        echo "FAIL: mktemp needs a writable \$TMPDIR"; exit 1; }
    work=$(cd "$work" && pwd -P)
    say "work files: $work"
}

export_head() {
    exp="$work/export"
    mkdir "$exp"
    git archive --format=tar HEAD | (cd "$exp" && tar -xf -)
}

tmp_writable() {
    probe="/tmp/tests-use-tmp-path-probe-$$"
    if mkdir "$probe" 2> /dev/null; then
        rmdir "$probe"
        return 0
    fi
    return 1
}

static() {
    say "static: change set, verify row, one commit, ledger; the tests' syntax tree"
    gatepy "$here/change_set.py"
    gatepy "$here/same_behaviour.py" ast
}

selftest() {
    say "selftest: the write-audit hook against its canary suite"
    for v in $pythons; do
        suite "$v" python -I "$here/write_audit.py" selftest --work "$work/selftest-$v"
    done
}

audit() {
    say "audit: R1 and R5, --basetemp at a fresh directory, TMPDIR at another"
    fails=0
    for v in $pythons; do
        mkdir "$work/tmp-$v"
        TMPDIR="$work/tmp-$v" suite "$v" python -I "$here/write_audit.py" run \
            --log "$work/audit-$v.json" --root "$exp" --token "$tok" -- \
            -rA --basetemp "$work/basetemp-$v" > "$work/audit-$v.out" 2>&1 || {
            tail -n 30 "$work/audit-$v.out"; echo "FAIL R1: the audited suite failed on $v"; fails=1; }
        # the verdict on the writes prints even when the suite failed
        gatepy "$here/write_audit.py" check "$work/audit-$v.json" --allow "$work/basetemp-$v" \
            --expect-names "$here/written-names.txt" || fails=1
    done
    [ "$fails" -eq 0 ] || exit 1
    gatepy "$here/same_behaviour.py" passed "$work/audit-3.9.out" "$work/audit-3.14.out"
}

concurrent() {
    say "concurrent: R4 and portable R3, both Pythons at once, shared fresh TMPDIR"
    mkdir "$work/shared-tmp" "$work/barrier"
    pids=''
    for v in $pythons; do
        TMPDIR="$work/shared-tmp" suite "$v" python -I "$here/write_audit.py" run \
            --log "$work/conc-$v.json" --root "$exp" --token "$tok" \
            --barrier "$work/barrier" --peers 2 -- -q -rA > "$work/conc-$v.out" 2>&1 &
        pids="$pids $!"
    done
    rc=0
    for p in $pids; do
        wait "$p" || rc=1
    done
    if [ "$rc" -ne 0 ]; then
        for v in $pythons; do tail -n 15 "$work/conc-$v.out"; done
        echo "FAIL R4: a concurrent run failed"
    fi
    for v in $pythons; do
        [ -f "$work/conc-$v.json" ] || { echo "FAIL R4: no audit log from $v"; exit 1; }
        pid=$(sed -n 's/^ "pid": \([0-9]*\),$/\1/p' "$work/conc-$v.json")
        [ -n "$pid" ] || { echo "FAIL: no PID in the $v log"; exit 1; }
        if kill -0 "$pid" 2> /dev/null; then
            echo "FAIL: the $v run (PID $pid) outlived the gate"; exit 1
        fi
        gatepy "$here/write_audit.py" check "$work/conc-$v.json" --allow "$work/shared-tmp" \
            --expect-names "$here/written-names.txt" || rc=1
    done
    gatepy "$here/write_audit.py" cross "$work/conc-3.9.json" "$work/conc-3.14.json" || rc=1
    [ "$rc" -eq 0 ] || exit 1
    gatepy "$here/same_behaviour.py" passed "$work/conc-3.9.out" "$work/conc-3.14.out"
}

r2() {
    say "R2: --basetemp at a fresh directory; /tmp/cmdkit absent before and after"
    if ! tmp_writable; then
        echo "FAIL R2: /tmp is not writable to this run, so its absence afterwards would prove"
        echo "         nothing. R2 needs a run where /tmp is writable (the sandbox off)."
        exit 1
    fi
    if [ -e /tmp/cmdkit ] || [ -L /tmp/cmdkit ]; then
        echo "FAIL R2: precondition: /tmp/cmdkit exists on this host (left by an earlier run of the"
        echo "         old suite). R2 needs a host where it doesn't; move it aside and run again."
        exit 1
    fi
    for v in $pythons; do
        suite "$v" python -m pytest -q --basetemp "$work/r2-$v" > "$work/r2-$v.out" 2>&1 || {
            tail -n 30 "$work/r2-$v.out"; echo "FAIL R2: the suite failed on $v"; exit 1; }
        if [ -e /tmp/cmdkit ] || [ -L /tmp/cmdkit ]; then
            echo "FAIL R2: /tmp/cmdkit exists after the run on $v"; exit 1
        fi
        tail -n 1 "$work/r2-$v.out"
    done
    echo "ok R2: both runs passed, /tmp/cmdkit absent"
}

tmpdenied() {
    say "tmpdenied: R3 where /tmp is not writable"
    if tmp_writable; then
        echo "FAIL R3: /tmp is writable to this run; tmpdenied needs a run that denies it (a sandbox)"
        exit 1
    fi
    mkdir "$work/tmp"
    cmd=$(sed -n 's/^| verify | `\([^`]*\)`.*/\1/p' "$exp/AGENTS.md")
    [ -n "$cmd" ] || { echo "FAIL R3: no command in AGENTS.md's verify row"; exit 1; }
    say "profile verify: $cmd"
    (unset PYTEST_ADDOPTS PYTEST_PLUGINS PYTEST_DEBUG_TEMPROOT
     cd "$exp" && TMPDIR="$work/tmp" sh -c "$cmd") > "$work/tmpdenied.out" 2>&1 || {
        tail -n 30 "$work/tmpdenied.out"; echo "FAIL R3: the profile's verify failed with /tmp denied"; exit 1; }
    grep -E ' passed' "$work/tmpdenied.out" | tail -n 2
    echo "ok R3: the profile's verify passed on both Pythons with /tmp denied"
}

frozen
tok="tests-use-tmp-path-gate-$$-$(date +%s)"
workdir
case "$mode" in
    static) static ;;
    selftest) export_head; selftest ;;
    audit) export_head; audit ;;
    concurrent) export_head; concurrent ;;
    R2) export_head; r2 ;;
    tmpdenied) export_head; tmpdenied; concurrent ;;
    P1) static; export_head; selftest; audit; concurrent; r2 ;;
    *) echo "unknown mode: $mode"; exit 2 ;;
esac
printf '%s\n' "ok gate $mode"
