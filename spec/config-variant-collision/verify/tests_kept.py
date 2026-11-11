"""Gate: every base test is kept, the one changed test says what GOAL says, the named tests exist.

    python -I tests_kept.py ast PHASE
        Reads the index and the merge-base with origin/develop. Every file under tests/ other than
        tests/test_config.py is the base's, byte for byte, and none is added or removed. In
        tests/test_config.py every module-level statement of the base is still there with the same
        syntax tree (functions and classes by name, anything else by its tree), and every member of
        every base class too, except TestConfiguration.test_attribute_expand_multiple_variants.
        That test's body, its docstring aside, is exactly CHANGED below. Nothing is added to a base
        class, and the module gains only imports, plain assignments to new names (no call, lambda
        or attribute target) and the class TestVariantCollision (no base, no decorator), whose
        members are test functions decorated at most with pytest.mark.parametrize: no fixture,
        autouse or otherwise, can reach a base test. No added line names inspect, getsource,
        __file__, __code__, hashlib, importlib or sys.modules, or monkeypatches a cmdkit name, so
        no test pins the source text. TestVariantCollision holds every test the phase names (NAMED).

    python -I tests_kept.py basefile OUT
        Writes to OUT the base's tests/test_config.py with the one changed test's body replaced by
        CHANGED (through ast.unparse). The gate runs it against the index's src/ on each Python:
        R7's "every base test still passes unchanged", literally.

    python -I tests_kept.py passed PHASE OUTPUT [OUTPUT ...]
        Each OUTPUT is the console output of a whole-suite run with -rA. Its short test summary
        reports PASSED for every line of base-nodeids.txt (collected at the merge-base), for every
        named test of the phase, and for six cases of test_pairs; and nothing FAILED, ERROR,
        SKIPPED, XFAIL or XPASS.

Footprint: git and one Python process; under a second.
"""

# type annotations
from __future__ import annotations

# standard libs
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = 'tests/test_config.py'
CHANGED_TEST = ('TestConfiguration', 'test_attribute_expand_multiple_variants')
CHANGED = """\
cfg = Configuration(a=Namespace({'nested': {'test': 'foo', 'a': 1}}),
                    b=Namespace({'nested': {'test_eval': 'echo bar', 'b': 2}}),
                    c=Namespace({'other': {'secret_eval': 'echo baz'}}))
assert cfg.nested.a == 1
assert cfg.nested.b == 2
assert cfg.other.secret == 'baz'
assert cfg.nested.test == 'bar'
"""
CLASS = 'TestVariantCollision'
NAMED = {
    'P1': ['test_pairs', 'test_top_level', 'test_deep', 'test_suffix_alone', 'test_mapping_values',
           'test_deciding_layer_ambiguous', 'test_namespace_update_unchanged', 'test_no_expansion',
           'test_non_string_keys', 'test_double_suffix', 'test_which_unchanged',
           'test_which_displaced_through_scalar', 'test_which_restored', 'test_which_through_scalars',
           'test_extend_and_from_local'],
}
NAMED['P2'] = NAMED['P1'] + ['test_update', 'test_successive_updates', 'test_attribute_assignment',
                             'test_attribute_assignment_unchanged']
PAIRS = 6
FAILURES: list = []


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout


def fail(msg: str) -> None:
    FAILURES.append(msg)


def dump(node: ast.AST) -> str:
    return ast.dump(node)


def body_without_docstring(fn: ast.FunctionDef) -> list:
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return body


def named_members(tree: ast.Module) -> dict:
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out[node.name] = node
    return out


PINNING = re.compile(r'\binspect\b|getsource|__file__|__code__|hashlib|importlib|sys\.modules|'
                     r'monkeypatch\.setattr\(\s*(cmdkit|Configuration|Namespace|NSCoreMixin|Environ)\b')
PARAMETRIZE = 'Attribute(value=Attribute(value=Name(id=\'pytest\', ctx=Load()), attr=\'mark\', ctx=Load()), attr=\'parametrize\', ctx=Load())'


def bound_names(tree: ast.Module) -> set:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split('.')[0] for a in node.names)
        else:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
    return names


def check_added(old: ast.Module, new: ast.Module, base: str) -> None:
    """What the module gains: imports, plain new names, and the one new class."""
    old_dumps = {dump(n) for n in old.body}
    old_bound = bound_names(old)
    for node in new.body:
        if dump(node) in old_dumps or (isinstance(node, (ast.FunctionDef, ast.ClassDef))
                                       and node.name in old_bound):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not all(isinstance(t, ast.Name) and t.id not in old_bound for t in targets):
                fail(f'line {node.lineno}: an added assignment must bind a new plain name')
            if node.value is not None and any(isinstance(n, (ast.Call, ast.Lambda, ast.NamedExpr))
                                              for n in ast.walk(node.value)):
                fail(f'line {node.lineno}: an added assignment may not call or define a function')
            continue
        if isinstance(node, ast.ClassDef) and node.name == CLASS:
            if node.bases or node.keywords or node.decorator_list:
                fail(f'{CLASS} has a base, a keyword or a decorator')
            for i, member in enumerate(node.body):
                if i == 0 and isinstance(member, ast.Expr) and isinstance(member.value, ast.Constant):
                    continue
                if not isinstance(member, ast.FunctionDef) or not member.name.startswith('test_'):
                    fail(f'{CLASS}: line {member.lineno} is not a test function')
                    continue
                for deco in member.decorator_list:
                    if not (isinstance(deco, ast.Call) and dump(deco.func) == PARAMETRIZE):
                        fail(f'{CLASS}.{member.name}: a decorator other than pytest.mark.parametrize')
            continue
        fail(f'line {node.lineno}: a module-level {type(node).__name__} the base lacks')
    added = [line[1:] for line in git('diff', '--cached', '-U0', base, '--', CONFIG).splitlines()
             if line.startswith('+') and not line.startswith('+++')]
    for line in added:
        if PINNING.search(line):
            fail(f'an added test line reaches for the source or patches cmdkit: {line.strip()[:100]}')


def check_ast(phase: str) -> None:
    base = git('merge-base', 'origin/develop', 'HEAD').strip()
    for line in git('diff', '--cached', '--name-status', base, '--', 'tests/').splitlines():
        status, *paths = line.split('\t')
        if paths != [CONFIG] or status != 'M':
            fail(f'tests/ changes outside {CONFIG}: {status} {" ".join(paths)}')
    old = ast.parse(git('show', f'{base}:{CONFIG}'))
    new = ast.parse(git('show', f':{CONFIG}'))
    old_named, new_named = named_members(old), named_members(new)
    new_other = [dump(n) for n in new.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    for node in old.body:
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if dump(node) not in new_other:
                fail(f'a module-level statement of the base is gone or changed (line {node.lineno})')
            continue
        if node.name not in new_named:
            fail(f'{node.name} is gone')
            continue
        if isinstance(node, ast.FunctionDef):
            if dump(node) != dump(new_named[node.name]):
                fail(f'{node.name} changed')
            continue
        mine = new_named[node.name]
        if not isinstance(mine, ast.ClassDef) or dump(ast.List(elts=node.bases)) != dump(ast.List(elts=mine.bases)):
            fail(f'class {node.name} changed its kind or bases')
            continue
        members = {getattr(m, 'name', None): m for m in mine.body if hasattr(m, 'name')}
        others = [dump(m) for m in mine.body if not hasattr(m, 'name')]
        base_members = {getattr(m, 'name', None) for m in node.body if hasattr(m, 'name')}
        if set(members) - base_members or len(others) != len([m for m in node.body if not hasattr(m, 'name')]):
            fail(f'class {node.name} gains members: {sorted(set(members) - base_members)}')
        for member in node.body:
            name = getattr(member, 'name', None)
            if name is None:
                if dump(member) not in others:
                    fail(f'a statement of class {node.name} is gone or changed (line {member.lineno})')
                continue
            if name not in members:
                fail(f'{node.name}.{name} is gone')
            elif (node.name, name) == CHANGED_TEST:
                fn = members[name]
                if dump(ast.Module(body=body_without_docstring(fn), type_ignores=[])) != \
                        dump(ast.parse(CHANGED)):
                    fail(f'{node.name}.{name}: its body is not the one TECH.md gives')
                if dump(fn.args) != dump(member.args) or fn.decorator_list != [] or member.decorator_list != []:
                    fail(f'{node.name}.{name}: its signature or decorators changed')
            elif dump(member) != dump(members[name]):
                fail(f'{node.name}.{name} changed')
    check_added(old, new, base)
    cls = new_named.get(CLASS)
    if not isinstance(cls, ast.ClassDef):
        fail(f'no class {CLASS} in {CONFIG}')
        return
    have = {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}
    for name in NAMED[phase]:
        if name not in have:
            fail(f'{CLASS}.{name} is missing ({phase} names it)')


SUMMARY = re.compile(r'^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (\S+)')


def check_passed(phase: str, outputs: list) -> None:
    with open(os.path.join(HERE, 'base-nodeids.txt')) as stream:
        base_ids = [line.strip() for line in stream if line.strip()]
    for path in outputs:
        passed, bad = set(), []
        with open(path) as stream:
            for line in stream:
                m = SUMMARY.match(line)
                if not m:
                    continue
                if m.group(1) == 'PASSED':
                    passed.add(m.group(2))
                else:
                    bad.append(line.strip())
        for line in bad:
            fail(f'{os.path.basename(path)}: {line[:120]}')
        for node in base_ids:
            if node not in passed:
                fail(f'{os.path.basename(path)}: base test not PASSED: {node}')
        for name in NAMED[phase]:
            if name == 'test_pairs':
                continue
            node = f'{CONFIG}::{CLASS}::{name}'
            if node not in passed:
                fail(f'{os.path.basename(path)}: named test not PASSED: {node}')
        pairs = [n for n in passed if n.startswith(f'{CONFIG}::{CLASS}::test_pairs[')]
        if len(pairs) != PAIRS:
            fail(f'{os.path.basename(path)}: {len(pairs)} test_pairs cases PASSED, not {PAIRS}')


def write_basefile(out: str) -> None:
    base = git('merge-base', 'origin/develop', 'HEAD').strip()
    tree = ast.parse(git('show', f'{base}:{CONFIG}'))
    done = 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == CHANGED_TEST[0]:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == CHANGED_TEST[1]:
                    head = member.body[:len(member.body) - len(body_without_docstring(member))]
                    member.body = head + ast.parse(CHANGED).body
                    done += 1
    if done != 1:
        fail(f'the base has no single {".".join(CHANGED_TEST)}')
        return
    with open(out, 'w') as stream:
        stream.write(ast.unparse(ast.fix_missing_locations(tree)) + '\n')


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == 'basefile':
        write_basefile(sys.argv[2])
        for msg in FAILURES:
            print('FAIL:', msg)
        sys.exit(1 if FAILURES else 0)
    if len(sys.argv) < 3 or sys.argv[1] not in ('ast', 'passed') or sys.argv[2] not in NAMED:
        print('usage: tests_kept.py ast P1|P2 | passed P1|P2 OUTPUT [OUTPUT ...] | basefile OUT')
        sys.exit(2)
    mode, phase = sys.argv[1], sys.argv[2]
    if mode == 'ast':
        check_ast(phase)
    else:
        if len(sys.argv) < 4:
            print('passed needs at least one OUTPUT')
            sys.exit(2)
        check_passed(phase, sys.argv[3:])
    for msg in FAILURES:
        print('FAIL:', msg)
    if FAILURES:
        sys.exit(1)
    print(f'ok tests kept ({mode} {phase})')


if __name__ == '__main__':
    main()
