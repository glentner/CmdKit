"""Gate: what the cycle changed, read from commits (R1, R6, the non-goals, the deferral ledger).

    python -I change_set.py [--base REV] [--rev REV]

REV defaults to HEAD, and the base to `git merge-base origin/develop REV`. Checks:

1. Files. Since the latest plan commit (the latest whose subject is `[fix] Plan
   tests-use-tmp-path: ...`; the shaping commits before it mark this cycle's own seed adopted), the
   cycle changes `tests/test_config.py` and `AGENTS.md`, both, and otherwise only
   `spec/tests-use-tmp-path/`, plus an `issues/<slug>.md` it adds and `ROADMAP.md` when check 5
   needs them. Nothing under `src/`, no build file, no other test file, and nothing under `spec/`
   that pytest would load from its rootdir walk (`conftest.py`, `test_*.py`, `*_test.py`,
   `__init__.py`, `pytest.ini`, `tox.ini`, `setup.cfg`, `pyproject.toml`).
2. No `/tmp` literal. `git grep -nE "['\"]/tmp" REV -- tests/` finds nothing (How it is shown, 4).
3. The profile's `verify` row (R6). The only line of `AGENTS.md` that changes is the Profile
   table's `| verify |` row, and it changes by exactly the deletion of its sentence " Until
   `issues/tests-use-tmp-path.md` lands, ... allow that path": the rest of the row, command
   included, stays byte for byte. At REV it no longer names `/tmp`, a sandbox, or this seed.
4. One commit (R6). Walking base..REV oldest first, the first commit whose `tests/test_config.py`
   holds no quoted `/tmp` literal is the first commit whose single `verify` row names none of
   `/tmp`, a sandbox or this seed. A commit without the file, or with no single row, counts as
   not yet there.
5. Deferral ledger. Every prose or list line of a `## Phase` section of
   `spec/tests-use-tmp-path/TECH.md` (headings skipped) that defers work names an
   `issues/<slug>.md` that exists at REV and that `ROADMAP.md` points at with a `**Seed:**` line.

Footprint: git only; under a second.
"""

# type annotations
from __future__ import annotations

# standard libs
import argparse
import re
import subprocess
import sys

CONFIG = 'tests/test_config.py'
TECH = 'spec/tests-use-tmp-path/TECH.md'
TMP_LITERAL = re.compile(r'[\'"]/tmp')
DEFER = re.compile(r'not fixed here|do not fix|known limitation|follow-?up|deferred|defer\b|'
                   r'left (?:as|for) |out of scope|later cycle|not this cycle', re.IGNORECASE)
ISSUE = re.compile(r'issues/([a-z0-9][a-z0-9-]*)\.md')
SENTENCE = (' Until `issues/tests-use-tmp-path.md` lands, the suite writes to `/tmp/cmdkit/config`, '
            'so a sandboxed run must allow that path')
ROW_WORDS = ('/tmp', 'sandbox', 'tests-use-tmp-path')
PYTEST_LOADS = re.compile(r'(^|/)(conftest\.py|test_[^/]*\.py|[^/]*_test\.py|__init__\.py|pytest\.ini|'
                          r'tox\.ini|setup\.cfg|pyproject\.toml)$')
FAILURES: list = []


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=check).stdout


def fail(msg: str) -> None:
    FAILURES.append(msg)


def verify_row(text: str) -> tuple[int, str]:
    rows = [(i, line) for i, line in enumerate(text.splitlines()) if line.startswith('| verify |')]
    if len(rows) != 1:
        return -1, ''
    return rows[0]


def command(row: str) -> str:
    m = re.search(r'`([^`]+)`', row)
    return m.group(1) if m else ''


def row_done(rev: str, commit: str) -> bool:
    if not exists(commit, 'AGENTS.md'):
        return False
    i, row = verify_row(git('show', f'{commit}:AGENTS.md'))
    return i >= 0 and not any(word in row for word in ROW_WORDS)


def seeds(rev: str) -> set:
    text = git('show', f'{rev}:ROADMAP.md')
    return {m.group(1) for line in text.splitlines() if '**Seed:**' in line for m in ISSUE.finditer(line)}


def exists(rev: str, name: str) -> bool:
    return subprocess.run(['git', 'cat-file', '-e', f'{rev}:{name}'], capture_output=True).returncode == 0


def ledger(rev: str) -> set:
    """The seeds the TECH.md phase bodies name for their deferrals."""
    named = set()
    if not exists(rev, TECH):
        fail(f'{TECH} is not committed at {rev}')
        return named
    text = git('show', f'{rev}:{TECH}')
    body = text.split('\n---\n', 2)[-1] if text.startswith('---\n') else text
    roadmap = seeds(rev)
    in_phase = False
    for n, line in enumerate(body.splitlines(), 1):
        if line.startswith('## '):
            in_phase = line.startswith('## Phase ')
            continue
        if not in_phase or line.lstrip().startswith('#') or not DEFER.search(line):
            continue
        slugs = ISSUE.findall(line)
        if not slugs:
            fail(f'{TECH} phase line defers without naming an issues/ seed: {line.strip()[:100]}')
        for slug in slugs:
            named.add(slug)
            if not exists(rev, f'issues/{slug}.md'):
                fail(f'{TECH} names issues/{slug}.md, which does not exist')
            elif slug not in roadmap:
                fail(f'issues/{slug}.md has no ROADMAP.md **Seed:** entry')
    return named


def main() -> None:
    parser = argparse.ArgumentParser(prog='change_set.py')
    parser.add_argument('--base', default='')
    parser.add_argument('--rev', default='HEAD')
    opts = parser.parse_args()
    rev = opts.rev
    base = opts.base or git('merge-base', 'origin/develop', rev).strip()

    # 5, first: the seeds it names widen check 1
    named = ledger(rev)

    # 1
    plan = ''
    for line in git('log', '--format=%H %s', rev).splitlines():
        sha, _, subject = line.partition(' ')
        if subject.startswith('[fix] Plan tests-use-tmp-path: '):
            plan = sha
            break
    if not plan:
        fail('no plan commit ([fix] Plan tests-use-tmp-path) in the history')
        plan = base
    changed = git('diff', '--name-status', plan, rev).splitlines()
    names = set()
    for line in changed:
        status, *paths = line.split('\t')
        for name in paths:
            names.add(name)
            if name.startswith('spec/') and PYTEST_LOADS.search(name):
                fail(f'a file pytest would load, under spec/: {status} {name}')
                continue
            if name in (CONFIG, 'AGENTS.md') or name.startswith('spec/tests-use-tmp-path/'):
                continue
            m = ISSUE.fullmatch(name)
            if m and status == 'A' and m.group(1) in named:
                continue
            if name == 'ROADMAP.md' and named:
                continue
            fail(f'changed outside the cycle\'s files: {status} {name}')
    for name in (CONFIG, 'AGENTS.md'):
        if name not in names:
            fail(f'{name} is not changed')

    # 2
    hits = git('grep', '-nE', '[\'"]/tmp', rev, '--', 'tests/', check=False).strip()
    if hits:
        fail(f'a quoted /tmp literal under tests/: {hits.splitlines()[0]}')

    # 3
    old, new = git('show', f'{base}:AGENTS.md'), git('show', f'{rev}:AGENTS.md')
    i, old_row = verify_row(old)
    j, new_row = verify_row(new)
    if i < 0 or j < 0:
        fail('AGENTS.md has no single `| verify |` row at the base or at REV')
    else:
        old_lines, new_lines = old.splitlines(), new.splitlines()
        if (old_lines[:i] + old_lines[i + 1:]) != (new_lines[:j] + new_lines[j + 1:]):
            fail('AGENTS.md changes outside the profile\'s verify row')
        for word in ROW_WORDS:
            if word in new_row:
                fail(f'the verify row still names {word!r}')
        if SENTENCE not in old_row:
            fail('the base verify row lacks the sentence this cycle deletes')
        elif new_row != old_row.replace(SENTENCE, '', 1):
            fail('the verify row changed beyond deleting its /tmp sentence')
        if not command(old_row) or command(old_row) != command(new_row):
            fail('the verify row\'s command changed')

    # 4
    commits = git('rev-list', '--reverse', f'{base}..{rev}').split()
    first_tests = first_row = ''
    for c in commits:
        if not first_tests and exists(c, CONFIG) and not TMP_LITERAL.search(git('show', f'{c}:{CONFIG}')):
            first_tests = c
        if not first_row and row_done(rev, c):
            first_row = c
    if not first_tests or first_tests != first_row:
        fail(f'the tests leave /tmp in {first_tests[:9] or "no commit"}, the verify row '
             f'in {first_row[:9] or "no commit"}: R6 needs one commit')

    for msg in FAILURES:
        print('FAIL:', msg)
    if FAILURES:
        sys.exit(1)
    print(f'ok change set: {len(names)} files, the verify row and the tests in {first_tests[:9]}, '
          f'{len(named)} deferral seeds')


if __name__ == '__main__':
    main()
