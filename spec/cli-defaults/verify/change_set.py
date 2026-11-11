# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Static checks on the cycle's change set, read from the git index against a base commit.

    python -I change_set.py P1|P2 BASE

P1 and P2:
    - every changed path is one the cycle may touch, and the source, test, docs and AGENTS.md
      files are among them;
    - AGENTS.md loses exactly the § Invariants 3 line about dropped argument errors, and nothing
      else in it changes;
    - no spec ids (R1, P2, ...) or spec paths in added lines under src/ or tests/;
    - every test function the base has in tests/test_app.py is still there, unchanged
      (test_app_group_usage among them).
P2 also:
    - the ALLOW_NOARGS paragraph of docs/api/app.rst no longer claims exit_status.success for a
      bare run, and names exit_status.usage;
    - the one commit since BASE that changes AGENTS.md also changes src/cmdkit/app.py;
    - the deferral ledger: every phase-body line in TECH.md that defers work names an
      issues/*.md file present in the index and listed in ROADMAP.md.

Footprint: a handful of git processes, one at a time.
"""

# standard libs
import re
import ast
import sys
import subprocess

ALLOWED = {
    'src/cmdkit/app.py', 'tests/test_app.py', 'docs/api/app.rst', 'AGENTS.md', 'ROADMAP.md',
}
ALLOWED_PREFIXES = ('spec/cli-defaults/', 'issues/')
REQUIRED = {'src/cmdkit/app.py', 'tests/test_app.py', 'docs/api/app.rst', 'AGENTS.md'}
DROPPED_LINE = ('- Known limitation (recorded, not fixed): with no logging configured, '
                '`ArgumentError` messages are dropped → `issues/cli-defaults.md`.')
SPEC_ID = re.compile(r'\b[RP][0-9]+\b|spec/cli-defaults')
OLD_NOARGS = 'is printed to ``sys.stdout`` and ``exit_status.success``'
DEFERRAL = re.compile(r'do not fix here|known limitation|left as a follow-up|follow-up|deferred|'
                      r'not fixed|out of scope', re.IGNORECASE)

FAILURES = []


def git(*args: str) -> str:
    return subprocess.run(['git', *args], check=True, stdout=subprocess.PIPE).stdout.decode()


def check(name: str, ok: bool, detail: str = '') -> None:
    print(('ok    ' if ok else 'FAIL  ') + name + ('' if ok or not detail else ': ' + detail))
    if not ok:
        FAILURES.append(name)


def diff_lines(base: str, path: str) -> tuple:
    """Added and removed lines of `path`, index against `base`."""
    added, removed = [], []
    for line in git('diff', '--cached', '-U0', base, '--', path).splitlines():
        if line.startswith('+++') or line.startswith('---'):
            continue
        if line.startswith('+'):
            added.append(line[1:])
        elif line.startswith('-'):
            removed.append(line[1:])
    return added, removed


def test_functions(source: str) -> dict:
    tree = ast.parse(source)
    return {node.name: ast.get_source_segment(source, node) for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')}


def common(base: str) -> None:
    changed = set(git('diff', '--cached', '--name-only', base).split())
    stray = sorted(p for p in changed if p not in ALLOWED and not p.startswith(ALLOWED_PREFIXES))
    check('only the cycle\'s files change', not stray, f'also changed: {stray}')
    missing = sorted(REQUIRED - changed)
    check('source, tests, docs and AGENTS.md all change', not missing, f'unchanged: {missing}')

    added, removed = diff_lines(base, 'AGENTS.md')
    check('AGENTS.md loses exactly the dropped-messages line, nothing else',
          added == [] and removed == [DROPPED_LINE], f'added={added} removed={removed}')
    agents = git('show', ':AGENTS.md')
    check('AGENTS.md keeps § Invariants 3', '### 3. Command line' in agents)

    leaks = []
    for path in sorted(changed):
        if path.startswith(('src/', 'tests/')):
            leaks += [f'{path}: {line.strip()}' for line in diff_lines(base, path)[0] if SPEC_ID.search(line)]
    check('no spec ids in added source or test lines', not leaks, '; '.join(leaks))

    before = test_functions(git('show', f'{base}:tests/test_app.py'))
    after = test_functions(git('show', ':tests/test_app.py'))
    edited = sorted(name for name, src in before.items() if after.get(name) != src)
    check('every existing test in tests/test_app.py is unchanged', not edited, f'changed or gone: {edited}')
    check('tests/test_app.py gains tests', len(after) > len(before), f'{len(before)} -> {len(after)}')


def phase_two(base: str) -> None:
    docs = git('show', ':docs/api/app.rst')
    check('the ALLOW_NOARGS paragraph no longer claims exit_status.success for a bare run',
          OLD_NOARGS not in docs)
    check('docs/api/app.rst names exit_status.usage', 'exit_status.usage' in docs)

    commits = git('log', '--format=%H', f'{base}..HEAD', '--', 'AGENTS.md').split()
    together = len(commits) == 1 and 'src/cmdkit/app.py' in git(
        'show', '--name-only', '--format=', commits[0]).split()
    check('the AGENTS.md line goes in the commit that changes src/cmdkit/app.py', together,
          f'commits touching AGENTS.md since base: {commits}')

    tech = git('show', ':spec/cli-defaults/TECH.md').split('\n')
    body = tech[tech.index('---', 1) + 1:]
    roadmap = git('show', ':ROADMAP.md')
    indexed = set(git('ls-files', '--cached', 'issues/').split())
    unrecorded, in_phase = [], False
    for line in body:
        if line.startswith('## '):
            in_phase = line.startswith('## Phase ')
            continue
        if not in_phase or line.startswith('#') or not DEFERRAL.search(line):
            continue
        seeds = re.findall(r'issues/[A-Za-z0-9._-]+\.md', line)
        if not seeds or any(s not in indexed or s not in roadmap for s in seeds):
            unrecorded.append(line.strip())
    check('deferral ledger: every deferral in a phase body has its seed and ROADMAP entry',
          not unrecorded, '; '.join(unrecorded))


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ('P1', 'P2'):
        print('usage: change_set.py P1|P2 BASE')
        return 2
    phase, base = sys.argv[1], sys.argv[2]
    common(base)
    if phase == 'P2':
        phase_two(base)
    if FAILURES:
        print(f'FAIL: {len(FAILURES)} check(s) failed')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
