"""Gate: what the cycle changed, read from the index and the commits since the plan.

    python -I change_set.py PHASE

PHASE is P1 or P2. The base is `git merge-base origin/develop HEAD`; the graded state is the index
(`git show :path`), which equals HEAD once the phase is committed. Checks:

1. Files. Since the plan commit (the latest whose subject is
   `[fix] Plan namespace-file-loading: design + phased roadmap`), the cycle changes only
   `src/cmdkit/namespace.py`, `src/cmdkit/config.py`, `tests/test_config.py`, pages under
   `docs/api/` and `docs/tutorial/`, files under `spec/namespace-file-loading/` other than
   `GOAL.md`, `PLAN.md` and `verify/`, plus an `issues/<slug>.md` it adds and `ROADMAP.md` when
   check 6 names a seed. Nothing under `spec/` is a file pytest's rootdir walk would load. The
   three source and test files named all change.
2. Blast radius. Every file under `src/` other than those two is the base's, byte for byte, and no
   file under `src/` is added or removed. `src/cmdkit/config.py` differs from the base's only in
   `Configuration.from_local`'s annotations and docstring, and in imports it adds (every base
   import is kept; an added one imports `os` or from `typing`).
3. The docstrings (R8). Each of `from_local`, `to_local`, `from_toml`, `from_yaml`, `from_json`,
   `to_toml`, `to_yaml` and `to_json` on `Namespace`, and `Configuration.from_local`, has a
   docstring that names `os.PathLike`. At P2, `Namespace.from_toml`'s names `TOMLDecodeError` and
   `Namespace.from_json`'s names `JSONDecodeError`. These checks find the docs; whether their words
   say what GOAL asks is the review's to grade.
4. One commit. Walking the commits since the plan oldest first, then the staged index, the first
   state whose `src/cmdkit/namespace.py` code differs from the base's (its syntax tree with every
   docstring taken out) is also the first whose check 3 (the P1 part) holds, and the first that
   changes any page under `docs/` the cycle changes. At P2, the first
   state where `from_toml` or `from_json` holds an `except` clause naming a decode error is also
   the first where their docstrings name it.
5. No spec ids. No added line under `src/`, `tests/` or `docs/` names an R, C or P id.
6. Deferral ledger (P2 only). Every prose or list line of a `## Phase` section of `TECH.md`
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

SLUG = 'namespace-file-loading'
SPEC = f'spec/{SLUG}/'
TECH = f'{SPEC}TECH.md'
NAMESPACE = 'src/cmdkit/namespace.py'
CONFIG = 'src/cmdkit/config.py'
TESTS = 'tests/test_config.py'
PLAN_SUBJECT = f'[fix] Plan {SLUG}: design + phased roadmap'
PATH_METHODS = ('from_local', 'to_local', 'from_toml', 'from_yaml', 'from_json', 'to_toml', 'to_yaml', 'to_json')
DECODE_DOCS = {'from_toml': 'TOMLDecodeError', 'from_json': 'JSONDecodeError'}
PATHLIKE = 'os.PathLike'
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


def strip_docstring(node: ast.AST) -> None:
    body = getattr(node, 'body', None)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        node.body = body[1:] or [ast.Pass()]


def code_of(source: str | None) -> str:
    """The module's syntax tree with every docstring taken out."""
    if source is None:
        return ''
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            strip_docstring(node)
    return ast.dump(tree)


def method(source: str | None, cls: str, name: str) -> ast.FunctionDef | None:
    if source is None:
        return None
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == name:
                    return member
    return None


def docstring(source: str | None, cls: str, name: str) -> str:
    fn = method(source, cls, name)
    return (ast.get_docstring(fn) or '') if fn is not None else ''


def config_shape(source: str) -> tuple:
    """config.py without imports, with Configuration.from_local's docstring and annotations out."""
    tree = ast.parse(source)
    imports = [ast.dump(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Configuration':
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == 'from_local':
                    strip_docstring(member)
                    member.returns = None
                    args = member.args
                    for arg in args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]:
                        if arg is not None:
                            arg.annotation = None
    return ast.dump(tree), imports


def import_ok(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names] == ['os'] and node.names[0].asname is None
    return isinstance(node, ast.ImportFrom) and node.module == 'typing' and node.level == 0


def path_docs_ok(namespace: str | None, config: str | None) -> list:
    """Check 3, the P1 part, for one state: the reasons it fails, or none."""
    why = []
    for name in PATH_METHODS:
        if PATHLIKE not in docstring(namespace, 'Namespace', name):
            why.append(f'the Namespace.{name} docstring does not name {PATHLIKE}')
    if PATHLIKE not in docstring(config, 'Configuration', 'from_local'):
        why.append(f'the Configuration.from_local docstring does not name {PATHLIKE}')
    return why


def decode_docs_ok(namespace: str | None) -> list:
    """Check 3, the P2 part, for one state."""
    return [f'the Namespace.{name} docstring does not name {word}'
            for name, word in DECODE_DOCS.items() if word not in docstring(namespace, 'Namespace', name)]


def has_decode_handler(namespace: str | None) -> bool:
    """from_toml or from_json holds an except clause naming a decode error."""
    def names_decode(node: ast.AST) -> bool:
        if isinstance(node, ast.Tuple):
            return any(names_decode(e) for e in node.elts)
        name = node.attr if isinstance(node, ast.Attribute) else getattr(node, 'id', '')
        return name.endswith('DecodeError') and name != 'UnicodeDecodeError'
    for name in DECODE_DOCS:
        fn = method(namespace, 'Namespace', name)
        if fn is not None and any(isinstance(n, ast.ExceptHandler) and n.type is not None and names_decode(n.type)
                                  for n in ast.walk(fn)):
            return True
    return False


def ledger() -> set:
    """Check 6: the seeds the TECH.md phase bodies name for their deferrals."""
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
            if name in (NAMESPACE, CONFIG, TESTS):
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
    for name in (NAMESPACE, CONFIG, TESTS):
        if name not in names:
            fail(f'{name} is not changed since the plan')

    # 2
    for line in git('diff', '--cached', '--name-status', base, '--', 'src/').splitlines():
        status, *paths = line.split('\t')
        if len(paths) != 1 or paths[0] not in (NAMESPACE, CONFIG) or status != 'M':
            fail(f'src/ changes outside {NAMESPACE} and {CONFIG}: {status} {" ".join(paths)}')
    base_cfg, cfg = show(base, CONFIG), show('', CONFIG)
    if cfg is not None:
        (old_shape, old_imports), (new_shape, new_imports) = config_shape(base_cfg), config_shape(cfg)
        if old_shape != new_shape:
            fail(f'{CONFIG} changes outside Configuration.from_local\'s annotations, docstring and imports')
        if any(i not in new_imports for i in old_imports):
            fail(f'{CONFIG} drops or changes an import')
        for node in ast.parse(cfg).body:
            if isinstance(node, (ast.Import, ast.ImportFrom)) and ast.dump(node) not in old_imports \
                    and not import_ok(node):
                fail(f'{CONFIG} adds an import other than os or from typing (line {node.lineno})')

    # 3
    base_ns, ns = show(base, NAMESPACE), show('', NAMESPACE)
    for why in path_docs_ok(ns, cfg):
        fail(why)
    if phase == 'P2':
        for why in decode_docs_ok(ns):
            fail(why)

    # 4
    states = git('rev-list', '--reverse', f'{plan}..HEAD').split()
    if git('diff', '--cached', '--name-only', 'HEAD').strip():
        states.append('')
    first_code = first_docs = first_handler = first_decode_docs = None
    base_code = code_of(base_ns)
    for state in states:
        label = state[:9] or 'the index'
        state_ns = show(state, NAMESPACE)
        if first_code is None and code_of(state_ns) != base_code:
            first_code = label
        if first_docs is None and not path_docs_ok(state_ns, show(state, CONFIG)):
            first_docs = label
        if first_handler is None and has_decode_handler(state_ns):
            first_handler = label
        if first_decode_docs is None and not decode_docs_ok(state_ns):
            first_decode_docs = label
    docs_changed = [name for name in names if re.fullmatch(r'docs/(api|tutorial)/[^/]+\.rst', name)]
    first_rst = None
    for state in states:
        if first_rst is None and any(show(state, name) != show(base, name) for name in docs_changed):
            first_rst = state[:9] or 'the index'
    if docs_changed and first_rst != first_code:
        fail(f'a docs/ page first changes in {first_rst}, the code in {first_code}: they land in the same commit')
    if first_code != first_docs:
        fail(f'the code changes in {first_code}, the os.PathLike docstrings in {first_docs}: '
             f'they land in the same commit')
    if phase == 'P2' and first_handler != first_decode_docs:
        fail(f'the decode-error handling lands in {first_handler}, its docstrings in {first_decode_docs}: '
             f'they land in the same commit')

    # 5
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
