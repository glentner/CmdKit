"""Gate: what the cycle changed, read from the index and the commits since the plan.

    python -I change_set.py PHASE

PHASE is P1 or P2. The base is `git merge-base origin/develop HEAD`; the graded state is the index
(`git show :path`), which equals HEAD once the phase is committed. Checks:

1. Files. Since the plan commit (the latest whose subject is
   `[fix] Plan config-variant-collision: design + phased roadmap`), the cycle changes only
   `src/cmdkit/config.py`, `tests/test_config.py`, `docs/index.rst`, pages under `docs/api/` and
   `docs/tutorial/`, `AGENTS.md`, files under `spec/config-variant-collision/` other than `GOAL.md`,
   `PLAN.md` and `verify/`, plus an `issues/<slug>.md` it adds and `ROADMAP.md` when check 6 names
   a seed. Nothing under `spec/` is a file pytest's rootdir walk would load. The first four files
   named all change.
2. Blast radius. Every file under `src/` other than `src/cmdkit/config.py` is the base's, byte for
   byte (`namespace.py` above all: plain `Namespace` behaviour is a non-goal), and no file under
   `src/` is added or removed.
3. The rule line. `AGENTS.md` differs from the base's in exactly one line: the known-limitation line
   for the collision is replaced, in place, by the rule line quoted in RULE below.
4. The docs. `docs/index.rst` changes only inside the passage that introduces `_env` and `_eval`
   (from the line starting "The underlying" to the next row of dashes), and its added lines name
   ``_env``, ``_eval`` and a layer. The `Configuration` class docstring differs from the base's and
   names `_env` and `_eval`.
5. One commit. Walking the commits since the plan oldest first, then the staged index, the first
   state whose `src/cmdkit/config.py` code differs from the base's (its syntax tree with every
   docstring taken out, so a docstring-only commit is not the code's) is also the first that
   satisfies checks 3 and 4. At P2, the `Configuration.update` docstring differs from the base's
   and names `_env` and `_eval`. These checks find the docs; whether their words state the rule is
   the review's to grade.
6. No spec ids. No added line under `src/`, `tests/` or `docs/` names an R, C or P id.
7. Deferral ledger (P2 only). Every prose or list line of a `## Phase` section of `TECH.md`
   (headings skipped, and text inside double quotes or backticks not read as a deferral) that defers
   work names an `issues/<slug>.md` that exists in the index and that `ROADMAP.md` points at with a
   `**Seed:**` line.

Footprint: git and one Python process; under two seconds.
"""

# type annotations
from __future__ import annotations

# standard libs
import ast
import re
import subprocess
import sys

SLUG = 'config-variant-collision'
SPEC = f'spec/{SLUG}/'
TECH = f'{SPEC}TECH.md'
CONFIG = 'src/cmdkit/config.py'
TESTS = 'tests/test_config.py'
INDEX_RST = 'docs/index.rst'
PLAN_SUBJECT = f'[fix] Plan {SLUG}: design + phased roadmap'
OLD_LINE = ('- Known limitation (recorded, not fixed): `name`, `name_env` and `name_eval` from different '
            'layers collide → `issues/config-variant-collision.md`.')
RULE = ('- `name`, `name_env` and `name_eval` are one key across layers: the highest layer that sets any '
        'of them decides.')
PASSAGE_START = 'The underlying'
DEFER = re.compile(r'not fixed here|do not fix|known limitation|follow-?up|deferred|defer\b|'
                   r'left (?:as|for) |out of scope|later cycle|not this cycle', re.IGNORECASE)
ISSUE = re.compile(r'issues/([a-z0-9][a-z0-9-]*)\.md')
SPEC_ID = re.compile(r'\b[RCP][0-9]{1,2}\b')
PYTEST_LOADS = re.compile(r'(^|/)(conftest\.py|test_[^/]*\.py|[^/]*_test\.py|__init__\.py|pytest\.ini|'
                          r'tox\.ini|setup\.cfg|pyproject\.toml)$')
FAILURES: list = []


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=check).stdout


def fail(msg: str) -> None:
    FAILURES.append(msg)


def show(state: str, name: str) -> str | None:
    """A file's text at a commit, or in the index when `state` is ''."""
    done = subprocess.run(['git', 'show', f'{state}:{name}'], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else None


def code_of(source: str | None) -> str:
    """The module's syntax tree with every docstring taken out."""
    if source is None:
        return ''
    tree = ast.parse(source)
    for node in ast.walk(tree):
        body = getattr(node, 'body', None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body \
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)


def method_docstring(source: str | None, name: str) -> str:
    if source is None:
        return ''
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == 'Configuration':
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == name:
                    return ast.get_docstring(member) or ''
    return ''


def class_docstring(source: str | None) -> str:
    if source is None:
        return ''
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == 'Configuration':
            return ast.get_docstring(node) or ''
    return ''


def passage(lines: list) -> tuple:
    """The line range of the passage that introduces `_env` and `_eval`."""
    start = next((i for i, line in enumerate(lines) if line.startswith(PASSAGE_START)), -1)
    if start < 0:
        return -1, -1
    end = next((i for i in range(start, len(lines)) if set(lines[i]) == {'-'}), len(lines))
    return start, end


def rule_line(base: str, text: str | None) -> bool:
    """Check 3 for one state."""
    if text is None:
        return False
    old, new = base.splitlines(), text.splitlines()
    if len(old) != len(new) or OLD_LINE not in old:
        return False
    i = old.index(OLD_LINE)
    return new[i] == RULE and old[:i] + old[i + 1:] == new[:i] + new[i + 1:]


def docs_ok(base_rst: str, rst: str | None, base_cfg: str, cfg: str | None) -> list:
    """Check 4 for one state: the reasons it fails, or none."""
    why = []
    if rst is None:
        return ['docs/index.rst is missing']
    old, new = base_rst.splitlines(), rst.splitlines()
    (a, b), (c, d) = passage(old), passage(new)
    if a < 0 or c < 0:
        why.append('docs/index.rst lost the passage that introduces _env and _eval')
    else:
        if old[:a] != new[:c] or old[b:] != new[d:]:
            why.append('docs/index.rst changes outside the passage that introduces _env and _eval')
        added = '\n'.join(line for line in new[c:d] if line not in old[a:b])
        for word in ('``_env``', '``_eval``', 'layer'):
            if word not in added and word.strip('`') not in added:
                why.append(f'the docs/index.rst passage adds nothing naming {word}')
    doc, base_doc = class_docstring(cfg), class_docstring(base_cfg)
    if doc == base_doc:
        why.append('the Configuration docstring is unchanged')
    elif '_env' not in doc or '_eval' not in doc:
        why.append('the Configuration docstring does not name _env and _eval')
    return why


def ledger() -> set:
    """Check 7: the seeds the TECH.md phase bodies name for their deferrals."""
    named = set()
    text = show('', TECH)
    if text is None:
        fail(f'{TECH} is not in the index')
        return named
    body = text.split('\n---\n', 1)[-1] if text.startswith('---\n') else text
    roadmap_text = show('', 'ROADMAP.md') or ''
    roadmap = {m.group(1) for line in roadmap_text.splitlines() if '**Seed:**' in line
               for m in ISSUE.finditer(line)}
    in_phase = False
    for line in body.splitlines():
        if line.startswith('## '):
            in_phase = line.startswith('## Phase ')
            continue
        bare = re.sub(r'"[^"]*"|`[^`]*`', '', line)
        if not in_phase or line.lstrip().startswith('#') or not DEFER.search(bare):
            continue
        slugs = ISSUE.findall(line)
        if not slugs:
            fail(f'{TECH} phase line defers without naming an issues/ seed: {line.strip()[:100]}')
        for slug in slugs:
            named.add(slug)
            if show('', f'issues/{slug}.md') is None:
                fail(f'{TECH} names issues/{slug}.md, which is not in the index')
            elif slug not in roadmap:
                fail(f'issues/{slug}.md has no ROADMAP.md **Seed:** entry')
    return named


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else ''
    if phase not in ('P1', 'P2'):
        print('usage: change_set.py P1|P2')
        sys.exit(2)
    base = git('merge-base', 'origin/develop', 'HEAD').strip()
    plan = ''
    for line in git('log', '--format=%H %s', 'HEAD').splitlines():
        sha, _, subject = line.partition(' ')
        if subject == PLAN_SUBJECT:
            plan = sha
            break
    if not plan:
        print(f'FAIL: no plan commit ({PLAN_SUBJECT})')
        sys.exit(1)

    named = ledger() if phase == 'P2' else set()

    # 1
    names = set()
    for line in git('diff', '--cached', '--name-status', plan).splitlines():
        status, *paths = line.split('\t')
        for name in paths:
            names.add(name)
            if name.startswith('spec/') and PYTEST_LOADS.search(name):
                fail(f'a file pytest would load, under spec/: {status} {name}')
                continue
            if name in (CONFIG, TESTS, INDEX_RST, 'AGENTS.md'):
                continue
            if re.fullmatch(r'docs/(api|tutorial)/[^/]+\.rst', name):
                continue
            if name.startswith(SPEC):
                if name in (f'{SPEC}GOAL.md', f'{SPEC}PLAN.md') or name.startswith(f'{SPEC}verify/'):
                    fail(f'a frozen spec file changed since the plan: {status} {name}')
                continue
            m = ISSUE.fullmatch(name)
            if m and status == 'A' and m.group(1) in named:
                continue
            if name == 'ROADMAP.md' and named:
                continue
            fail(f'changed outside the cycle\'s files: {status} {name}')
    for name in (CONFIG, TESTS, INDEX_RST, 'AGENTS.md'):
        if name not in names:
            fail(f'{name} is not changed since the plan')

    # 2
    for line in git('diff', '--cached', '--name-status', base, '--', 'src/').splitlines():
        status, *paths = line.split('\t')
        if paths != [CONFIG] or status != 'M':
            fail(f'src/ changes outside {CONFIG}: {status} {" ".join(paths)}')

    # 3, 4
    base_agents, base_rst, base_cfg = show(base, 'AGENTS.md'), show(base, INDEX_RST), show(base, CONFIG)
    if OLD_LINE not in base_agents.splitlines():
        fail('the base AGENTS.md lacks the known-limitation line this cycle replaces')
    if not rule_line(base_agents, show('', 'AGENTS.md')):
        fail('AGENTS.md: the known-limitation line is not replaced, in place and alone, by the rule line')
    for why in docs_ok(base_rst, show('', INDEX_RST), base_cfg, show('', CONFIG)):
        fail(why)

    # 5
    states = git('rev-list', '--reverse', f'{plan}..HEAD').split()
    if git('diff', '--cached', '--name-only', 'HEAD').strip():
        states.append('')
    first_code = first_docs = None
    base_code = code_of(base_cfg)
    for state in states:
        label = state[:9] or 'the index'
        if first_code is None and code_of(show(state, CONFIG)) != base_code:
            first_code = label
        if first_docs is None and rule_line(base_agents, show(state, 'AGENTS.md')) \
                and not docs_ok(base_rst, show(state, INDEX_RST), base_cfg, show(state, CONFIG)):
            first_docs = label
    if first_code != first_docs:
        fail(f'the code changes in {first_code}, the docs and the rule line in {first_docs}: '
             f'they land in the same commit')

    if phase == 'P2':
        doc, base_doc = method_docstring(show('', CONFIG), 'update'), method_docstring(base_cfg, 'update')
        if doc == base_doc or '_env' not in doc or '_eval' not in doc:
            fail('the Configuration.update docstring does not gain a statement naming _env and _eval')

    # 6
    for line in git('diff', '--cached', '-U0', base, '--', 'src/', 'tests/', 'docs/').splitlines():
        if line.startswith('+') and not line.startswith('+++') and SPEC_ID.search(line):
            fail(f'a spec id in an added line: {line[:100]}')

    for msg in FAILURES:
        print('FAIL:', msg)
    if FAILURES:
        sys.exit(1)
    print(f'ok change set {phase}: {len(names)} files since the plan, code and docs in {first_code}, '
          f'{len(named)} deferral seeds')


if __name__ == '__main__':
    main()
