"""Gate: the `tests` workflow ran on the cycle's PR for the pushed commit, with every job.

Reads GitHub only (no writes): the open PR from the cycle branch into develop, the `tests`
run of event pull_request for the pushed head, its jobs, and each job's log.

Checks:
- the evidence commit SHA (default: the remote-tracking ref of the cycle branch) is the PR's
  head, is an ancestor of HEAD, and nothing outside spec/ changed between it and HEAD;
- the run's head is that SHA and it completed; it has exactly the ten jobs named
  `<os> / py<python>` (ubuntu-latest x 3.9-3.14, macos-latest and windows-latest x 3.9, 3.14);
- each graded job concluded success, its log shows pytest on that platform and Python
  (`platform <linux|darwin|win32> -- Python <python>.`), its final summary shows only passed and
  xfailed tests, it ran exactly `--expect-count` tests (the number collected locally at the
  commit), and it shows xfailed only on a platform an xfail decorator in tests/ names;
- `--require linux` grades the six Linux jobs and records the others without judging them;
  `--require all` grades all ten.

`--out FILE` writes the per-job record as JSON (the phase commits it as evidence).
`--fixture DIR` reads pr.json, runs.json, run.json, xfail.json and log-<job id>.txt from DIR instead of
GitHub; it exists for the gate's self-test and is honoured only together with `--sha`.

Run from the repository root, with the sandbox off (gh):
    uv run --isolated --no-project --python 3.14 python -I spec/uv-build-and-ci/verify/ci_evidence.py --require linux|all --expect-count N [--sha SHA] [--out FILE]

Network: api.github.com (gh). Footprint: one gh call at a time; seconds.
"""

# standard libs
import argparse
import json
import os
import re
import subprocess
import sys

REPO = 'glentner/cmdkit'
BRANCH = 'feature/uv-build-and-ci'
LINUX = ['3.9', '3.10', '3.11', '3.12', '3.13', '3.14']
JOBS = [('ubuntu-latest', v) for v in LINUX] + [
    (o, v) for o in ('macos-latest', 'windows-latest') for v in ('3.9', '3.14')]
PLATFORM = {'ubuntu-latest': 'linux', 'macos-latest': 'darwin', 'windows-latest': 'win32'}
SUMMARY = re.compile(r'=+ (?P<body>(?:\d+ \w+(?:, )?)+) in [\d.]+s(?: \([^)]*\))? =+\s*$')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def gh(fixture: str | None, name: str, *args: str) -> str:
    if fixture:
        with open(os.path.join(fixture, name)) as fh:
            return fh.read()
    return subprocess.run(['gh', *args], capture_output=True, text=True, check=True).stdout


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout.strip()


def xfail_targets(sha: str) -> set[str]:
    """Platforms named by `sys.platform == '...'` in xfail decorators under tests/ at `sha`."""
    import ast
    out = set()
    for name in git('ls-tree', '-r', '--name-only', sha, '--', 'tests/').split():
        if not name.endswith('.py'):
            continue
        for node in ast.walk(ast.parse(git('show', f'{sha}:{name}'))):
            for d in getattr(node, 'decorator_list', []):
                if isinstance(d, ast.Call) and ast.unparse(d.func) == 'pytest.mark.xfail' and d.args:
                    c = d.args[0]
                    if isinstance(c, ast.Compare) and ast.unparse(c.left) == 'sys.platform' \
                            and isinstance(c.comparators[0], ast.Constant):
                        out.add(c.comparators[0].value)
    return out


def spec_only_successor(sha: str, head: str, fixture: str | None) -> bool:
    """True when `head` descends from `sha`, is in HEAD's history, and changes only spec/."""
    if fixture:
        return False
    for a, b in ((sha, head), (head, 'HEAD')):
        if subprocess.run(['git', 'merge-base', '--is-ancestor', a, b], capture_output=True).returncode != 0:
            return False
    return not git('diff', '--name-only', sha, head, '--', '.', ':(exclude)spec').split()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--require', choices=['linux', 'all'], required=True)
    ap.add_argument('--sha')
    ap.add_argument('--out')
    ap.add_argument('--fixture')
    ap.add_argument('--expect-count', type=int, required=True,
                    help='tests collected at the commit (ci_command.py collect); every graded job must run exactly this many')
    args = ap.parse_args()
    if args.fixture and not args.sha:
        sys.exit('FAIL: --fixture is honoured only with --sha')
    failures = []
    if not args.sha:
        ref = subprocess.run(['git', 'rev-parse', '--verify', '--quiet', f'refs/remotes/origin/{BRANCH}'],
                             capture_output=True, text=True)
        if ref.returncode != 0:
            sys.exit(f'FAIL: no origin/{BRANCH}; push the branch and `git fetch origin {BRANCH}` first')
    sha = args.sha or ref.stdout.strip()
    if not args.fixture:
        if subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'HEAD']).returncode != 0:
            failures.append(f'{sha[:9]} is not an ancestor of HEAD')
        outside = git('diff', '--name-only', sha, 'HEAD', '--', '.', ':(exclude)spec').split()
        if outside:
            failures.append(f'files outside spec/ changed since {sha[:9]}: {outside}')
    xfail_platforms = (set(json.loads(gh(args.fixture, 'xfail.json'))) if args.fixture
                       else xfail_targets(sha))
    # the PR
    prs = json.loads(gh(args.fixture, 'pr.json', 'pr', 'list', '-R', REPO, '--head', BRANCH, '--base', 'develop',
                        '--state', 'open', '--json', 'number,headRefOid,baseRefName,isDraft'))
    if len(prs) != 1:
        failures.append(f'expected one open PR from {BRANCH} into develop, found {len(prs)}')
    elif prs[0]['headRefOid'] != sha and not spec_only_successor(sha, prs[0]['headRefOid'], args.fixture):
        failures.append(f'PR #{prs[0]["number"]} head is {prs[0]["headRefOid"][:9]}, neither {sha[:9]} nor a '
                        f'later commit of HEAD that changes only spec/')
    # the run
    runs = json.loads(gh(args.fixture, 'runs.json', 'run', 'list', '-R', REPO, '--workflow', 'tests.yml',
                         '--commit', sha, '--event', 'pull_request', '--limit', '20',
                         '--json', 'databaseId,headSha,status,conclusion,event,attempt,createdAt'))
    runs = [r for r in runs if r['headSha'] == sha and r['event'] == 'pull_request']
    if not runs:
        print('\n'.join(f'FAIL: {f}' for f in failures + [f'no pull_request tests run for {sha[:9]}']))
        return 1
    latest = max(runs, key=lambda r: r['createdAt'])
    if latest['status'] != 'completed':
        failures.append(f'run {latest["databaseId"]} is {latest["status"]}')
    run = json.loads(gh(args.fixture, 'run.json', 'run', 'view', str(latest['databaseId']), '-R', REPO,
                        '--json', 'jobs,headSha,conclusion,attempt'))
    if run['headSha'] != sha:
        failures.append(f'run head {run["headSha"][:9]} is not {sha[:9]}')
    jobs = {j['name']: j for j in run['jobs']}
    want = {f'{o} / py{v}': (o, v) for o, v in JOBS}
    if set(jobs) != set(want):
        failures.append(f'jobs differ: missing {sorted(set(want) - set(jobs))}, extra {sorted(set(jobs) - set(want))}')
    record, counts = {}, {}
    for name, (os_, py) in sorted(want.items()):
        job = jobs.get(name)
        if job is None:
            continue
        graded = args.require == 'all' or os_ == 'ubuntu-latest'
        log = ANSI.sub('', gh(args.fixture, f'log-{job["databaseId"]}.txt', 'run', 'view', '-R', REPO,
                              '--job', str(job['databaseId']), '--log'))
        plat = re.search(rf'platform {PLATFORM[os_]} -- Python {re.escape(py)}\.\d+', log)
        summaries = [m.group('body') for line in log.splitlines() if (m := SUMMARY.search(line))]
        outcome = {}
        if summaries:
            for part in summaries[-1].split(', '):
                n, word = part.split(' ', 1)
                outcome[word.rstrip('s') if word.endswith('s') and word != 'xpassed' else word] = int(n)
        record[name] = {'conclusion': job.get('conclusion'), 'python': bool(plat), 'summary': summaries[-1:] or None,
                        'graded': graded}
        if not graded:
            continue  # recorded only: graded in the all-jobs mode
        if not plat:
            failures.append(f'{name}: the log does not show pytest on {PLATFORM[os_]} Python {py}')
        if not summaries:
            failures.append(f'{name}: no pytest summary line in the log')
            continue
        total = sum(v for k, v in outcome.items() if k not in ('warning', 'deselected'))
        counts[name] = total
        if job.get('conclusion') != 'success':
            failures.append(f'{name}: concluded {job.get("conclusion")}')
        bad = {k: v for k, v in outcome.items() if k not in ('passed', 'xfailed', 'warning')}
        if bad:
            failures.append(f'{name}: pytest summary shows {bad}')
        if not outcome.get('passed'):
            failures.append(f'{name}: no test passed')
        if outcome.get('xfailed') and (os_ == 'ubuntu-latest' or PLATFORM[os_] not in xfail_platforms):
            failures.append(f'{name}: {outcome["xfailed"]} xfailed, but no xfail in tests/ targets {PLATFORM[os_]}')
        if total != args.expect_count:
            failures.append(f'{name}: {total} tests ran, expected the {args.expect_count} collected locally')
    if args.out:
        with open(args.out, 'w') as fh:
            json.dump({'sha': sha, 'run': latest['databaseId'], 'expect_count': args.expect_count,
                       'xfail_platforms': sorted(xfail_platforms), 'jobs': record, 'counts': counts}, fh, indent=2)
            fh.write('\n')
    for name, rec in sorted(record.items()):
        print(f'{name}: {rec["conclusion"]} {rec["summary"]}')
    if failures:
        print('\n'.join(f'FAIL: {f}' for f in failures))
        return 1
    print(f'ok ci_evidence: run {latest["databaseId"]} on {sha[:9]}, {len(record)} jobs, require {args.require}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
