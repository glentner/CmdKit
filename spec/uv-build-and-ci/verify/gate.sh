#!/bin/sh
# Gate dispatcher for the uv-build-and-ci cycle. POSIX sh; run from the repository root:
#
#     sh spec/uv-build-and-ci/verify/gate.sh MODE
#
# Modes (each phase's verify names one):
#   P1        package: build config, the wheel surface against 2.7.7, src untouched, the
#             release recipe, and the profile's verify (suite on 3.9 and 3.14) on an export.
#   P2        publish workflow: static checks and its run lines on an export (dry-run upload).
#   P3        Read the Docs and dependabot config, Poetry gone, the docs build (R7 + RTD emulation).
#   P4pre     tests workflow and AGENTS.md, static; the CI command on 3.9 and 3.14 on an export;
#             the collected-test count against the base; the CI-evidence checker's self-test.
#             The check before P4's push.
#   P4        P4pre, then the CI evidence of the pushed commit (Linux graded, others recorded),
#             written to spec/uv-build-and-ci/ci/P4.json.
#   P5pre     every phase's own checks (P1, P2, P3, P4pre) plus the ledger. The check before P5's push.
#   P5        P5pre, then the CI evidence with every job graded, written to ci/P5.json.
#   P5phase   the ledger and the all-jobs CI evidence only (P5's own checks, for a fail-once mutation).
#   evidence  the ledger and the all-jobs CI evidence again, writing nothing: the re-grade of R5
#             and R11 at a later head (after a review fix, and before landing).
#
# Every mode first checks the gate itself: verify/ has no uncommitted change and is the copy the
# latest plan commit (subject `[build] Plan uv-build-and-ci: ...`) froze.
#
# Needs: git, uv, gh (P4, P5, evidence); network to pypi.org, files.pythonhosted.org, github.com
# and api.github.com; the sandbox off (the suite writes /tmp/cmdkit/config, sphinx extensions
# write user caches, gh reads its credentials).
# Footprint: strictly sequential, one build, suite or sphinx process at a time; peak about
# 1 GB (sphinx); P5pre about half a minute warm (measured on the prototype), a few minutes cold.
# No background processes are started.

set -eu

mode=${1:?usage: gate.sh P1|P2|P3|P4pre|P4|P5pre|P5|P5phase|evidence}
here=$(cd "$(dirname "$0")" && pwd)
spec=$(dirname "$here")
root=$(git rev-parse --show-toplevel)
cd "$root"
rel=spec/uv-build-and-ci/verify

py() {
    # Gate Python: isolated, never the project environment, never this directory on sys.path.
    uv run --isolated --no-project --python 3.14 "$@"
}

say() { printf '%s\n' "== $*"; }

frozen() {
    plan=$(git log -1 --format=%H --grep='^\[build\] Plan uv-build-and-ci' HEAD)
    [ -n "$plan" ] || { echo "FAIL: no plan commit ([build] Plan uv-build-and-ci) in HEAD's history"; exit 1; }
    git diff --quiet HEAD -- "$rel" || { echo "FAIL: $rel has uncommitted changes"; exit 1; }
    [ -z "$(git ls-files --others --exclude-standard -- "$rel")" ] || { echo "FAIL: untracked files in $rel"; exit 1; }
    git diff --quiet "$plan" HEAD -- "$rel" || { echo "FAIL: $rel changed since the plan commit ${plan%"${plan#?????????}"}"; exit 1; }
}

p1() {
    say "P1: build configuration, wheel surface, src, release recipe, profile verify"
    py --with packaging python -I "$here/build_config.py" package src
    py --with packaging python -I "$here/wheel_surface.py"
    py --with pyyaml --with check-jsonschema --with actionlint-py python -I "$here/workflow_config.py" recipe
    py --with pyyaml python -I "$here/ci_command.py" profile 3.9 3.14
}

p2() {
    say "P2: publish workflow"
    py --with pyyaml --with check-jsonschema --with actionlint-py python -I "$here/workflow_config.py" publish publishrun
}

p3() {
    say "P3: Read the Docs, dependabot, no Poetry, docs build"
    py --with pyyaml --with check-jsonschema --with actionlint-py python -I "$here/workflow_config.py" rtd dependabot
    py --with packaging python -I "$here/build_config.py" package nopoetry
    py --with pyyaml python -I "$here/docs_build.py"
}

p4pre() {
    say "P4 pre-push: tests workflow, AGENTS.md, the CI command locally, the test count"
    py --with pyyaml --with check-jsonschema --with actionlint-py python -I "$here/workflow_config.py" tests agents
    py --with packaging python -I "$here/build_config.py" nopoetry src
    py --with pyyaml python -I "$here/ci_command.py" ci 3.9 3.14
    py --with pyyaml python -I "$here/ci_command.py" collect
    py python -I "$here/ci_evidence_selftest.py"
}

count() {
    # tests collected at HEAD (never fewer than at the base); the last line is the number
    py --with pyyaml python -I "$here/ci_command.py" collect | tail -n 1
}

evidence() {
    n=$(count)
    case "$n" in ''|*[!0-9]*) echo "FAIL: no test count ($n)"; exit 1 ;; esac
    say "CI evidence: require $1, $n tests per graded job"
    if [ -n "${2:-}" ]; then
        mkdir -p "$spec/ci"
        py python -I "$here/ci_evidence.py" --require "$1" --expect-count "$n" --out "$spec/ci/$2.json"
    else
        py python -I "$here/ci_evidence.py" --require "$1" --expect-count "$n"
    fi
}

ledger() { py python -I "$here/ledger.py" --seeds; }

frozen
case "$mode" in
    P1) p1 ;;
    P2) p2 ;;
    P3) p3 ;;
    P4pre) p4pre ;;
    P4) p4pre; evidence linux P4 ;;
    P5pre) p1; p2; p3; p4pre; ledger ;;
    P5) p1; p2; p3; p4pre; ledger; evidence all P5 ;;
    P5phase) ledger; evidence all P5 ;;
    evidence) ledger; evidence all ;;
    *) echo "unknown mode: $mode"; exit 2 ;;
esac
printf '%s\n' "ok gate $mode"
