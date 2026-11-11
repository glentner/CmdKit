"""Gate: the tests do what they did at the base, and only where their files live changed (R5).

    python -I same_behaviour.py ast [--base REV] [--rev REV]
        Reads committed state. Every file under tests/ other than tests/test_config.py is byte for
        byte the base's, and no file is added or removed. tests/test_config.py parses to the
        base's syntax tree once the move is taken out of both:
          - from the base, the module's `TMPDIR = '/tmp/cmdkit/config'` and its
            `os.makedirs(TMPDIR, exist_ok=True)`;
          - from REV, a module-level `from pathlib import Path` the base lacks, and from each test
            function that gained a last parameter `tmp_path`, that parameter (and its annotation),
            with `tmp_path` read as `TMPDIR` in that function's body.
        So every call into cmdkit, every argument, every file name and extension, and every
        assertion is the base's. REV may not name `TMPDIR` anywhere else.
        REV defaults to HEAD, and the base to `git merge-base origin/develop REV`.

    python -I same_behaviour.py passed OUTPUT [OUTPUT ...]
        Each OUTPUT is the console output of a whole-suite run with `-rA`. Its short test summary
        reports PASSED for every line of base-nodeids.txt (collected at b9efaca), and nothing
        FAILED, ERROR, SKIPPED, XFAIL or XPASS. (No test is added: `ast` holds every file under
        tests/ to the merge-base's.)

Footprint: git and one Python process; under a second.
"""

# type annotations
from __future__ import annotations

# standard libs
import argparse
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = 'tests/test_config.py'


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout


def fail(msg: str) -> None:
    print('FAIL R5:', msg)
    sys.exit(1)


def is_tmpdir_assign(node: ast.stmt) -> bool:
    return (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'TMPDIR'
            and isinstance(node.value, ast.Constant) and node.value.value == '/tmp/cmdkit/config')


def is_makedirs(node: ast.stmt) -> bool:
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and ast.dump(node.value.func) == ast.dump(ast.parse('os.makedirs', mode='eval').body)
            and len(node.value.args) == 1 and isinstance(node.value.args[0], ast.Name)
            and node.value.args[0].id == 'TMPDIR'
            and [(k.arg, getattr(k.value, 'value', None)) for k in node.value.keywords] == [('exist_ok', True)])


def is_path_import(node: ast.stmt) -> bool:
    return (isinstance(node, ast.ImportFrom) and node.module == 'pathlib' and node.level == 0
            and [(a.name, a.asname) for a in node.names] == [('Path', None)])


class Rename(ast.NodeTransformer):

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id == 'tmp_path':
            node.id = 'TMPDIR'
        return node


def normalize_base(tree: ast.Module) -> ast.Module:
    body = tree.body
    found = [i for i, n in enumerate(body) if is_tmpdir_assign(n) or is_makedirs(n)]
    if len(found) != 2:
        fail(f'the base {CONFIG} does not carry the two module-level /tmp lines this gate expects')
    tree.body = [n for i, n in enumerate(body) if i not in found]
    return tree


def normalize_rev(tree: ast.Module, base_has_path: bool) -> tuple[ast.Module, list]:
    names = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == 'TMPDIR']
    if names:
        fail(f'{CONFIG} still names TMPDIR (line {names[0].lineno})')
    if not base_has_path:
        tree.body = [n for n in tree.body if not is_path_import(n)]
    moved = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = node.args.args
        if params and params[-1].arg == 'tmp_path':
            if node.args.defaults and len(node.args.defaults) >= 1:
                fail(f'{node.name}: tmp_path has a default')
            node.args.args = params[:-1]
            node.body = [Rename().visit(stmt) for stmt in node.body]
            moved.append(node.name)
        elif any(a.arg == 'tmp_path' for a in params + node.args.kwonlyargs):
            fail(f'{node.name}: tmp_path is not the last positional parameter')
    return tree, moved


def check_ast(opts: argparse.Namespace) -> None:
    rev = opts.rev
    base = opts.base or git('merge-base', 'origin/develop', rev).strip()
    files_base = set(git('ls-tree', '-r', '--name-only', base, '--', 'tests/').split())
    files_rev = set(git('ls-tree', '-r', '--name-only', rev, '--', 'tests/').split())
    if files_base != files_rev:
        fail(f'files under tests/ added {sorted(files_rev - files_base)}, '
             f'removed {sorted(files_base - files_rev)}')
    for name in sorted(files_base - {CONFIG}):
        if git('rev-parse', f'{base}:{name}') != git('rev-parse', f'{rev}:{name}'):
            fail(f'{name} changed; only {CONFIG} may')
    base_tree = ast.parse(git('show', f'{base}:{CONFIG}'))
    base_has_path = any(is_path_import(n) for n in base_tree.body)
    want = ast.dump(normalize_base(base_tree))
    got_tree, moved = normalize_rev(ast.parse(git('show', f'{rev}:{CONFIG}')), base_has_path)
    got = ast.dump(got_tree)
    if got != want:
        import difflib
        diff = difflib.unified_diff(ast.dump(normalize_base(ast.parse(git('show', f'{base}:{CONFIG}'))),
                                             indent=1).splitlines(),
                                    ast.dump(got_tree, indent=1).splitlines(), 'base', rev, n=2, lineterm='') \
            if sys.version_info >= (3, 9) else []
        print('\n'.join(list(diff)[:60]))
        fail(f'{CONFIG} differs from the base beyond moving its files to tmp_path')
    print(f'ok same behaviour: {CONFIG} is the base\'s but for tmp_path in {", ".join(moved)}; '
          f'the other {len(files_base) - 1} files under tests/ are unchanged')


def check_passed(opts: argparse.Namespace) -> None:
    with open(os.path.join(HERE, 'base-nodeids.txt')) as stream:
        want = {line.strip() for line in stream if line.strip()}
    for name in opts.outputs:
        with open(name) as stream:
            text = stream.read()
        mark = text.rfind('short test summary info')
        if mark < 0:
            fail(f'{name}: no short test summary (run with -rA)')
        text = text[mark:]  # captured logs above it carry their own "ERROR" lines
        passed = set(re.findall(r'^PASSED (\S+)', text, re.M))
        other = re.findall(r'^(FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b.*$', text, re.M)
        if other:
            fail(f'{name}: {len(other)} tests not passed, e.g. {other[0]}')
        if not want <= passed:
            fail(f'{name}: base node IDs not passed: {sorted(want - passed)[:5]}')
    print(f'ok node IDs: all {len(want)} of the base\'s tests collected and passed '
          f'({len(opts.outputs)} runs)')


def main() -> None:
    parser = argparse.ArgumentParser(prog='same_behaviour.py')
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('ast')
    p.add_argument('--base', default='')
    p.add_argument('--rev', default='HEAD')
    p = sub.add_parser('passed')
    p.add_argument('outputs', nargs='+')
    opts = parser.parse_args()
    check_ast(opts) if opts.mode == 'ast' else check_passed(opts)


if __name__ == '__main__':
    main()
