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
    - no added test line reads the module's source or bytecode (inspect, __file__, __spec__,
      __loader__, importlib other than importlib.reload, open(, a '.py' path, hashes and the like)
      or sets pytestmark: a test
      that pins the text kills every mutant without pinning any behaviour (adversarial reviews);
    - every top-level def, class and constant the base test module has is unchanged, decorators
      included;
    - every test function the base has in tests/test_app.py is still there, unchanged
      (test_app_group_usage among them);
    - src/cmdkit/__init__.py changes for the mark on cmdkit's own NullHandler only (review cycle
      2, F3; GOAL C9): exactly the one addHandler line removed, and exactly PLAN.md § 2's four
      lines added, in order (comment lines aside).
P2 also, and P1 too since review cycle 3 reopened it on the final tree (GOAL C9: the bare-group
help left the cycle):
    - src/cmdkit/app.py, docstrings aside, is the base's but for `import sys`, the helper and the
      report's `if` in the ArgumentError branch, whose body is exactly the guarded write (GOAL
      C10): ApplicationGroup and the rest of
      Application.main as in 2.7.7 (adversarial review of the C9 revision);
    - ApplicationGroup in src/cmdkit/app.py defines no main of its own, as in 2.7.7;
    - the ApplicationGroup section of docs/api/app.rst documents no ALLOW_NOARGS, as in 2.7.7;
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
    'src/cmdkit/app.py', 'src/cmdkit/__init__.py', 'tests/test_app.py', 'docs/api/app.rst', 'AGENTS.md', 'ROADMAP.md',
}
ALLOWED_PREFIXES = ('spec/cli-defaults/', 'issues/')
REQUIRED = {'src/cmdkit/app.py', 'src/cmdkit/__init__.py', 'tests/test_app.py', 'docs/api/app.rst', 'AGENTS.md'}
MARK_REMOVED = ['Logger.with_name(__name__).addHandler(NullHandler())']
MARK_ADDED = [
    '_null_handler = NullHandler()',
    '_null_handler._cmdkit_library_handler = True',
    'Logger.with_name(__name__).addHandler(_null_handler)',
    'del _null_handler',
]
DROPPED_LINE = ('- Known limitation (recorded, not fixed): with no logging configured, '
                '`ArgumentError` messages are dropped → `issues/cli-defaults.md`.')
SPEC_ID = re.compile(r'\b[RP][0-9]+\b|spec/cli-defaults')
SOURCE_READ = re.compile(r'\binspect\b|getsource|__file__|__spec__|__loader__|get_data|find_spec|'
                         r'importlib\.(?!reload\()|from importlib|'
                         r'pkgutil|hashlib|zlib|crc32|co_code|linecache|__code__|\bopen\(|read_text|read_bytes|'
                         r'\.py[\'"]|pytestmark')
HELPER_NAME = '_hidden_by_null_handler'
# GOAL C10 (review cycle 3, CR-F1): the write is skipped without a stderr, and its failure swallowed
GUARDED_WRITE = ast.unparse(ast.parse('''
if sys.stderr is not None:
    try:
        print(error, file=sys.stderr)
    except (OSError, ValueError):
        pass
'''))
REPORT_TEST = ('cls.log_critical == log.critical and '
               '_hidden_by_null_handler(log, logging.CRITICAL, error)')
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


def top_level(source: str) -> dict:
    """Every top-level def, class and assignment, by name, with its decorators (adversarial review)."""
    lines = source.splitlines()
    out = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        else:
            continue
        first = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
        for name in names:
            out[name] = '\n'.join(lines[first - 1:node.end_lineno])
    return out


def test_functions(source: str) -> dict:
    return {name: src for name, src in top_level(source).items() if name.startswith('test_')}


def strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], 'value', None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return tree


def app_module_rest(base: str) -> tuple:
    """src/cmdkit/app.py at base and staged, docstrings aside, with the report's three additions taken out."""
    old = strip_docstrings(ast.parse(git('show', f'{base}:src/cmdkit/app.py')))
    new = strip_docstrings(ast.parse(git('show', ':src/cmdkit/app.py')))
    removed = []
    keep = []
    for node in new.body:
        if isinstance(node, ast.Import) and [a.name for a in node.names] == ['sys']:
            removed.append('import sys')
            continue
        if isinstance(node, ast.FunctionDef) and node.name == HELPER_NAME:
            removed.append(HELPER_NAME)
            continue
        keep.append(node)
    new.body = keep
    for node in ast.walk(new):
        if isinstance(node, ast.ExceptHandler) and node.type is not None and ast.unparse(node.type) == 'ArgumentError':
            body = [stmt for stmt in node.body
                    if not (isinstance(stmt, ast.If) and ast.unparse(stmt.test) == REPORT_TEST
                            and [ast.unparse(b) for b in stmt.body] == [GUARDED_WRITE]
                            and not stmt.orelse)]
            if len(body) != len(node.body):
                removed.append('the report')
            node.body = body
    return ast.dump(old), ast.dump(new), removed


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
    readers = [line.strip() for line in diff_lines(base, 'tests/test_app.py')[0] if SOURCE_READ.search(line)]
    check('no added test line reads the module source', not readers, '; '.join(readers))

    added, removed = diff_lines(base, 'src/cmdkit/__init__.py')
    code = [line for line in added if line.strip() and not line.lstrip().startswith('#')]
    check('src/cmdkit/__init__.py changes for the mark only',
          code == MARK_ADDED and removed == MARK_REMOVED, f'added={added} removed={removed}')

    base_tests, staged_tests = git('show', f'{base}:tests/test_app.py'), git('show', ':tests/test_app.py')
    before_all, after_all = top_level(base_tests), top_level(staged_tests)
    moved = sorted(name for name, src in before_all.items() if after_all.get(name) != src)
    check('every top-level def, class and constant of the base test module is unchanged, decorators included',
          not moved, f'changed or gone: {moved}')
    before = test_functions(base_tests)
    after = test_functions(staged_tests)
    edited = sorted(name for name, src in before.items() if after.get(name) != src)
    check('every existing test in tests/test_app.py is unchanged', not edited, f'changed or gone: {edited}')
    check('tests/test_app.py gains tests', len(after) > len(before), f'{len(before)} -> {len(after)}')


def phase_two(base: str) -> None:
    old, new, removed = app_module_rest(base)
    check('src/cmdkit/app.py is 2.7.7\'s apart from import sys, the helper and the report (docstrings aside)',
          old == new and sorted(removed) == sorted(['import sys', HELPER_NAME, 'the report']),
          f'taken out: {removed}; the rest {"matches" if old == new else "differs"}')
    source = git('show', ':src/cmdkit/app.py')
    group = [node for node in ast.parse(source).body
             if isinstance(node, ast.ClassDef) and node.name == 'ApplicationGroup']
    own = [item.name for node in group for item in node.body
           if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    check('ApplicationGroup defines no main of its own, as in 2.7.7', len(group) == 1 and 'main' not in own,
          f'methods: {own}')
    docs_all = git('show', ':docs/api/app.rst')
    section = docs_all[docs_all.find('.. autoclass:: ApplicationGroup'):]
    check('the ApplicationGroup docs document no ALLOW_NOARGS, as in 2.7.7',
          '.. autoclass:: ApplicationGroup' in docs_all and 'ALLOW_NOARGS' not in section)
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
    phase_two(base)  # since review cycle 3, P1 is reopened on the final tree: both phases grade it all
    if FAILURES:
        print(f'FAIL: {len(FAILURES)} check(s) failed')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
