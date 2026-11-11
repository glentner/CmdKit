"""Gate: every decision the cycle adds to src/cmdkit/config.py is pinned by tests/test_config.py.

    python -I mutants.py --tree DIR --diff FILE --log FILE

Run inside the profile's environment for DIR, an export of the index installed editable. FILE is
`git diff --cached -U0 <merge-base> -- src/cmdkit/config.py`; its hunks give the lines the cycle
adds or changes. Every node inside a function body (docstrings and annotations aside), or inside
a module-level assignment, whose span touches one of those lines is mutated in turn (a compound
statement counts by its first line, an expression by every line it spans), one mutant per run:

  - the test of an `if`, `while`, conditional expression, `assert` or comprehension filter is
    negated;
  - an `and`/`or` swaps its operator, and loses each operand in turn;
  - a comparison swaps its operator (`in`/`not in`, `==`/`!=`, `is`/`is not`, `<`/`>=`, `>`/`<=`);
  - a `not` is dropped;
  - a statement becomes `pass` (except a function's closing `return False` or `return None`,
    whose deletion returns None, which only a test of identity tells apart; its `False` is still
    mutated);
  - a string holding `_env` or `_eval` swaps the one for the other; an integer moves by one either
    way; `True` and `False` swap;
  - `any` and `all` swap; `break` and `continue` swap; `reversed(x)` becomes `list(x)`;
  - a slice bound moves by one either way;
  - a call to a private helper (a name starting with `_`) swaps its first two positional
    arguments.

Each mutant is written over DIR/src/cmdkit/config.py and `python -m pytest -x -q -p no:cacheprovider
tests/test_config.py` runs in DIR, in a process group of its own, with a 120 s cap. A mutant
survives when that run passes; any survivor fails the gate. The unmutated source, put through the
same `ast.unparse`, must pass first, and the original file is restored at the end.

Footprint: one pytest process at a time, under 150 MB; about a second per mutant.
"""

# type annotations
from __future__ import annotations

# standard libs
import argparse
import ast
import copy
import os
import re
import signal
import subprocess
import sys
import time

TARGET = os.path.join('src', 'cmdkit', 'config.py')
TESTS = os.path.join('tests', 'test_config.py')
HUNK = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')
SWAP = {ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
        ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.Lt: ast.GtE, ast.GtE: ast.Lt,
        ast.Gt: ast.LtE, ast.LtE: ast.Gt}
BODIES = ('body', 'orelse', 'finalbody')


def added_lines(path: str) -> set:
    lines = set()
    with open(path) as stream:
        for line in stream:
            m = HUNK.match(line)
            if m:
                start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
                lines.update(range(start, start + count))
    return lines


def function_nodes(tree: ast.Module) -> set:
    """The ids of nodes inside function bodies (docstrings excluded) and module-level assignments."""
    inside = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            for node in ast.walk(stmt):
                inside.add(id(node))
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = fn.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]
        for stmt in body:
            for node in ast.walk(stmt):
                inside.add(id(node))
    return inside


def negate(test: ast.expr) -> ast.expr:
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return test.operand
    return ast.UnaryOp(op=ast.Not(), operand=test)


def sites(tree: ast.Module, lines: set) -> list:
    """(walk index, description, mutate) for every mutation the module admits."""
    inside = function_nodes(tree)
    out = []
    for index, node in enumerate(ast.walk(tree)):
        if id(node) not in inside and not isinstance(node, ast.FunctionDef):
            continue
        line = getattr(node, 'lineno', None)

        def touches(sub) -> bool:
            first = getattr(sub, 'lineno', None)
            if first is None:
                return False
            return any(n in lines for n in range(first, (getattr(sub, 'end_lineno', None) or first) + 1))

        def add(desc, fn, line=line):
            out.append((index, f'line {line}: {desc}', fn))

        if id(node) in inside:
            if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)) and touches(node.test):
                add(f'negate the {type(node).__name__} test',
                    lambda n: setattr(n, 'test', negate(n.test)))
            if isinstance(node, ast.comprehension):
                for i in range(len(node.ifs)):
                    if touches(node.ifs[i]):
                        add(f'negate comprehension filter {i}',
                            lambda n, i=i: n.ifs.__setitem__(i, negate(n.ifs[i])))
            if isinstance(node, ast.Slice) and touches(node):
                for bound in ('lower', 'upper'):
                    if getattr(node, bound) is not None:
                        for op in (ast.Add, ast.Sub):
                            add(f'slice {bound} {"+" if op is ast.Add else "-"} 1',
                                lambda n, bound=bound, op=op: setattr(n, bound, ast.BinOp(
                                    left=getattr(n, bound), op=op(), right=ast.Constant(value=1))))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and touches(node):
                if node.func.id == 'reversed':
                    add('reversed -> list', lambda n: setattr(n.func, 'id', 'list'))
                if node.func.id.startswith('_') and len(node.args) >= 2 \
                        and not any(isinstance(a, ast.Starred) for a in node.args[:2]):
                    add(f'swap the first two arguments of {node.func.id}',
                        lambda n: setattr(n, 'args', [n.args[1], n.args[0]] + n.args[2:]))
        if id(node) in inside and line is not None and touches(node):
            if isinstance(node, ast.BoolOp):
                other = ast.Or if isinstance(node.op, ast.And) else ast.And
                add(f'{type(node.op).__name__.lower()} -> {other.__name__.lower()}',
                    lambda n, other=other: setattr(n, 'op', other()))
                for i in range(len(node.values)):
                    add(f'drop operand {i} of {type(node.op).__name__.lower()}',
                        lambda n, i=i: setattr(n, 'values', n.values[:i] + n.values[i + 1:]))
            if isinstance(node, ast.Compare):
                for i, op in enumerate(node.ops):
                    if type(op) in SWAP:
                        add(f'{type(op).__name__} -> {SWAP[type(op)].__name__}',
                            lambda n, i=i: n.ops.__setitem__(i, SWAP[type(n.ops[i])]()))
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                add('drop not', lambda n: setattr(n, 'op', ast.UAdd()))
            if isinstance(node, ast.Constant):
                value = node.value
                if isinstance(value, bool):
                    add(f'{value} -> {not value}', lambda n: setattr(n, 'value', not n.value))
                elif isinstance(value, int):
                    add(f'{value} -> {value + 1}', lambda n: setattr(n, 'value', n.value + 1))
                    add(f'{value} -> {value - 1}', lambda n: setattr(n, 'value', n.value - 1))
                elif isinstance(value, str) and ('_env' in value or '_eval' in value):
                    swapped = value.replace('_eval', '\0').replace('_env', '_eval').replace('\0', '_env')
                    add(f'{value!r} -> {swapped!r}', lambda n, s=swapped: setattr(n, 'value', s))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('any', 'all'):
                other = 'all' if node.func.id == 'any' else 'any'
                add(f'{node.func.id} -> {other}', lambda n, other=other: setattr(n.func, 'id', other))
        # statements: each on an added line becomes `pass`; break and continue swap
        for field in BODIES:
            stmts = getattr(node, field, None)
            if not isinstance(stmts, list):
                continue
            for i, stmt in enumerate(stmts):
                if not isinstance(stmt, ast.stmt) or id(stmt) not in inside:
                    continue
                compound = isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try, ast.With,
                                             ast.FunctionDef, ast.ClassDef))
                span = range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1)
                if (stmt.lineno not in lines) if compound else not any(n in lines for n in span):
                    continue
                if isinstance(stmt, ast.Pass):
                    continue
                if isinstance(node, ast.FunctionDef) and field == 'body' and i == len(stmts) - 1 \
                        and isinstance(stmt, ast.Return) and (stmt.value is None or (
                            isinstance(stmt.value, ast.Constant) and stmt.value.value in (False, None))):
                    continue  # a closing `return False` or `return None`: deleting it returns None
                out.append((index, f'line {stmt.lineno}: {type(stmt).__name__} -> pass',
                            lambda n, field=field, i=i: getattr(n, field).__setitem__(i, ast.Pass())))
                if isinstance(stmt, (ast.Break, ast.Continue)):
                    other = ast.Continue if isinstance(stmt, ast.Break) else ast.Break
                    out.append((index, f'line {stmt.lineno}: {type(stmt).__name__} -> {other.__name__}',
                                lambda n, field=field, i=i, other=other: getattr(n, field).__setitem__(i, other())))
    return out


def mutate(tree: ast.Module, index: int, fn) -> str:
    clone = copy.deepcopy(tree)
    node = next(n for i, n in enumerate(ast.walk(clone)) if i == index)
    fn(node)
    ast.fix_missing_locations(clone)
    return ast.unparse(clone)


def run_tests(tree_dir: str) -> tuple:
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for name in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS'):
        env.pop(name, None)
    proc = subprocess.Popen([sys.executable, '-m', 'pytest', '-x', '-q', '-p', 'no:cacheprovider', TESTS],
                            cwd=tree_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=120)
        verdict = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        verdict = 'timeout'
    try:
        os.killpg(proc.pid, 0)
        os.killpg(proc.pid, signal.SIGKILL)
        leftover = True
    except ProcessLookupError:
        leftover = False
    return verdict, out.decode(errors='replace'), leftover


def main() -> None:
    parser = argparse.ArgumentParser(prog='mutants.py')
    parser.add_argument('--tree', required=True)
    parser.add_argument('--diff', required=True)
    parser.add_argument('--log', required=True)
    opts = parser.parse_args()
    target = os.path.join(opts.tree, TARGET)
    with open(target, 'rb') as stream:
        original = stream.read()
    tree = ast.parse(original)
    lines = added_lines(opts.diff)
    if not lines:
        print('FAIL: the diff adds no lines to src/cmdkit/config.py')
        sys.exit(1)
    plain = ast.unparse(tree)
    survivors, problems, seen, count = [], [], set(), 0
    started = time.time()
    try:
        with open(opts.log, 'w') as log:
            with open(target, 'w') as stream:
                stream.write(plain)
            verdict, out, leftover = run_tests(opts.tree)
            log.write(f'baseline: {verdict}\n')
            if verdict != 0 or leftover:
                print(out[-2000:])
                print('FAIL: the unmutated source (through ast.unparse) does not pass tests/test_config.py')
                sys.exit(1)
            for index, desc, fn in sites(tree, lines):
                source = mutate(tree, index, fn)
                if source == plain or source in seen:
                    continue
                seen.add(source)
                try:
                    compile(source, target, 'exec')
                except SyntaxError as exc:
                    problems.append(f'{desc}: does not compile ({exc})')
                    continue
                with open(target, 'w') as stream:
                    stream.write(source)
                verdict, out, leftover = run_tests(opts.tree)
                count += 1
                state = 'SURVIVED' if verdict == 0 else f'killed ({verdict})'
                log.write(f'{state}: {desc}\n')
                if verdict == 0:
                    survivors.append(desc)
                if verdict == 5:
                    problems.append(f'{desc}: pytest collected no tests')
                if leftover:
                    problems.append(f'{desc}: a process outlived its run')
    finally:
        with open(target, 'wb') as stream:
            stream.write(original)
    for desc in survivors:
        print(f'FAIL: mutant survived: {desc}')
    for desc in problems:
        print(f'FAIL: {desc}')
    if count == 0:
        print('FAIL: no mutants on the added lines')
    if survivors or problems or count == 0:
        sys.exit(1)
    print(f'ok mutants: {count} mutants on {len(lines)} added lines, all killed by {TESTS} '
          f'({time.time() - started:.0f} s)')


if __name__ == '__main__':
    main()
