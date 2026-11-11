"""Gate: the last phase's ledger: deferrals recorded, and every platform expected failure traced.

1. Deferral ledger. Every prose or list line of spec/uv-build-and-ci/TECH.md's phase bodies
   (Markdown headings are skipped) that defers work ("not fixed here", "known limitation",
   "follow-up", "deferred", "left as/for", "out of scope", "expected failure", "xfail") names an
   `issues/<slug>.md` (a line carrying the literal placeholder is the plan's R11 instruction)
   that exists at HEAD and that ROADMAP.md points at with a `**Seed:**` line.
2. R11 trace. Over the cycle's diff of tests/ (merge-base with origin/develop .. HEAD):
   - every added xfail is `pytest.mark.xfail(<platform condition>, reason=..., strict=True)`,
     its condition names exactly one of darwin or win32 (never Linux), and its reason names a
     seed `issues/<slug>.md` this cycle added, with status unshaped and a ROADMAP.md entry;
   - nothing else that hides a test is added: no skip, skipif, importorskip, pytest.skip,
     deselect, `--ignore`, or a change to pytest options in pyproject.toml; no test removed
     (the number of `def test_` functions never drops);
   - nothing outside tests/, issues/, ROADMAP.md and spec/ changed for it (src/ untouched is
     build_config.py's `src` mode).
   `--seeds` prints the seeds the PR body must name.

Reads committed state (`git show`, `git diff` between commits). Run from the repository root:
    uv run --isolated --no-project --python 3.14 python -I spec/uv-build-and-ci/verify/ledger.py [--rev REV] [--base REV] [--seeds]

Footprint: git only; under a second.
"""

# standard libs
import argparse
import ast
import re
import subprocess
import sys

TECH = 'spec/uv-build-and-ci/TECH.md'
DEFER = re.compile(r'not fixed here|do not fix|known limitation|follow-?up|deferred|defer\b|'
                   r'left (?:as|for) |out of scope|expected failure|xfail', re.IGNORECASE)
PLACEHOLDER = 'issues/<slug>.md'  # the plan's own R11 instructions, not a deferral
ISSUE = re.compile(r'issues/([a-z0-9][a-z0-9-]*)\.md')
HIDE = re.compile(r'\bskip(if)?\b|importorskip|pytest\.skip|deselect|--ignore|collect_ignore|'
                  r'pytestmark\s*=.*skip|__test__|pytest_ignore_collect|pytest_collection_modifyitems|'
                  r'pytest_generate_tests|pytest_runtest', re.IGNORECASE)
PLATFORM_BRANCH = re.compile(r'sys\.platform|os\.name|platform\.(system|platform|uname|win32|mac_ver)|'
                             r'getwindowsversion|\bwin32\b|\bdarwin\b|\bnt\b|windows', re.IGNORECASE)
XFAIL = re.compile(r'xfail', re.IGNORECASE)
FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout


def exists(rev: str, name: str) -> bool:
    return subprocess.run(['git', 'cat-file', '-e', f'{rev}:{name}'], capture_output=True).returncode == 0


def roadmap_seeds(rev: str) -> set[str]:
    text = git('show', f'{rev}:ROADMAP.md')
    return {m.group(1) for line in text.splitlines() if '**Seed:**' in line for m in ISSUE.finditer(line)}


def check_deferrals(rev: str) -> None:
    if not exists(rev, TECH):
        fail(f'{TECH} is not committed')
        return
    text = git('show', f'{rev}:{TECH}')
    body = text.split('\n---\n', 2)[-1] if text.startswith('---\n') else text
    seeds = roadmap_seeds(rev)
    in_phase = False
    for n, line in enumerate(body.splitlines(), 1):
        if line.startswith('## '):
            in_phase = line.startswith('## Phase ')
            continue
        if line.lstrip().startswith('#') or not in_phase or not DEFER.search(line):
            continue
        if PLACEHOLDER in line:
            continue
        named = ISSUE.findall(line)
        if not named:
            fail(f'TECH.md body line {n} defers without naming an issues/ seed: {line.strip()[:100]}')
        for slug in named:
            if not exists(rev, f'issues/{slug}.md'):
                fail(f'TECH.md body line {n} names issues/{slug}.md, which does not exist')
            elif slug not in seeds:
                fail(f'issues/{slug}.md has no ROADMAP.md **Seed:** entry')


def added_lines(base: str, rev: str, *paths: str) -> list[tuple[str, str]]:
    out, current = [], ''
    for line in git('diff', '-U0', base, rev, '--', *paths).splitlines():
        if line.startswith('+++ '):
            current = line[6:] if line.startswith('+++ b/') else ''
        elif line.startswith('+') and not line.startswith('+++'):
            out.append((current, line[1:]))
    return out


def count_tests(rev: str) -> int:
    names = [f for f in git('ls-tree', '-r', '--name-only', rev, '--', 'tests/').split() if f.endswith('.py')]
    return sum(len(re.findall(r'^\s*def test_', git('show', f'{rev}:{f}'), re.M)) for f in names)


def xfail_decorators(src: str) -> list:
    """Every decorator, anywhere in the module, whose text names xfail."""
    if not src:
        return []
    out = []
    for node in ast.walk(ast.parse(src)):
        for d in getattr(node, 'decorator_list', []):
            if 'xfail' in ast.unparse(d):
                d.owner = getattr(node, 'name', '')
                out.append(d)
    return out


def judge_xfail(d) -> tuple[str, str]:
    """('' , slug) for `pytest.mark.xfail(sys.platform == 'darwin'|'win32', reason=..., strict=True)`."""
    if not (isinstance(d, ast.Call) and ast.unparse(d.func) == 'pytest.mark.xfail'):
        return 'not a pytest.mark.xfail(...) call', ''
    if len(d.args) != 1:
        return 'needs exactly one positional condition', ''
    c = d.args[0]
    if not (isinstance(c, ast.Compare) and ast.unparse(c.left) == 'sys.platform' and len(c.ops) == 1
            and isinstance(c.ops[0], ast.Eq) and isinstance(c.comparators[0], ast.Constant)
            and c.comparators[0].value in ('darwin', 'win32')):
        return "condition must be sys.platform == 'darwin' or 'win32'", ''
    kw = {k.arg: k.value for k in d.keywords}
    if set(kw) != {'reason', 'strict'}:
        return f'keywords must be reason and strict, got {sorted(map(str, kw))}', ''
    if not (isinstance(kw['strict'], ast.Constant) and kw['strict'].value is True):
        return 'strict must be True', ''
    if not (isinstance(kw['reason'], ast.Constant) and isinstance(kw['reason'].value, str)):
        return 'reason must be a string literal', ''
    slugs = ISSUE.findall(kw['reason'].value)
    if len(slugs) != 1:
        return 'reason must name one issues/<slug>.md seed', ''
    return '', slugs[0]


def check_r11(rev: str, base: str, show_seeds: bool) -> set:
    merge_base = git('merge-base', base, rev).strip()
    new_files = set(git('diff', '--name-only', '--diff-filter=A', merge_base, rev, '--', 'issues/').split())
    seeds = roadmap_seeds(rev)
    used = set()
    added = added_lines(merge_base, rev, 'tests/')
    if any(XFAIL.search(l) for n, l in added if not n.endswith('.py')):
        fail('xfail added in a non-Python file under tests/')
    for name, line in added:
        if HIDE.search(line):
            fail(f'{name}: adds a test-hiding construct: {line.strip()}')
    # every xfail added under tests/ must be one new, well-formed decorator (read by ast), and no
    # other added line may branch on the platform (a platform branch is the xfail route, not a fix)
    for name in sorted({n for n, l in added if n.endswith('.py')}):
        new_src = git('show', f'{rev}:{name}')
        old_src = git('show', f'{merge_base}:{name}') if exists(merge_base, name) else ''
        old_decos = {ast.unparse(d) for d in xfail_decorators(old_src)}
        new_decos = [d for d in xfail_decorators(new_src) if ast.unparse(d) not in old_decos]
        covered = set()
        for d in new_decos:
            covered.update(range(d.lineno, d.end_lineno + 1))
            problem, slug = judge_xfail(d)
            if problem:
                fail(f'{name}:{d.lineno}: {problem}: {ast.unparse(d)[:120]}')
                continue
            used.add(slug)
            if f'issues/{slug}.md' not in new_files:
                fail(f'{name}:{d.lineno}: xfail seed issues/{slug}.md is not new in this cycle')
                continue
            seed_text = git('show', f'{rev}:issues/{slug}.md')
            if not re.search(r'^status: unshaped$', seed_text, re.M):
                fail(f'issues/{slug}.md is not status: unshaped')
            if f'{name}::' not in seed_text or d.owner not in seed_text:
                fail(f'issues/{slug}.md does not name the failing test {name}::...{d.owner}')
            if not re.search(r'\b[0-9a-f]{7,40}\b', seed_text):
                fail(f'issues/{slug}.md does not name the base commit the failure was confirmed on')
            if slug not in seeds:
                fail(f'issues/{slug}.md has no ROADMAP.md **Seed:** entry')
        old_lines = set(old_src.splitlines())
        for n, line in enumerate(new_src.splitlines(), 1):
            if n in covered or line in old_lines:
                continue
            if XFAIL.search(line):
                fail(f'{name}:{n}: xfail outside a new @pytest.mark.xfail(...) decorator: {line.strip()[:100]}')
            if PLATFORM_BRANCH.search(line) and not line.lstrip().startswith(('import ', 'from ')):
                fail(f'{name}:{n}: an added line branches on the platform: {line.strip()[:100]}')
    stray = [n for n, l in added_lines(merge_base, rev, '.') if XFAIL.search(l) and not n.startswith(('tests/', 'spec/', 'issues/', 'ROADMAP.md'))]
    if stray:
        fail(f'xfail added outside tests/: {sorted(set(stray))}')
    old_toml = git('show', f'{merge_base}:pyproject.toml')
    new_toml = git('show', f'{rev}:pyproject.toml')
    pick = lambda t: re.search(r'^\[tool\.pytest\.ini_options\]\n(.*?)(?=^\[|\Z)', t, re.S | re.M)
    if (pick(old_toml) and pick(old_toml).group(1)) != (pick(new_toml) and pick(new_toml).group(1)):
        fail('pyproject.toml [tool.pytest.ini_options] changed')
    moved = git('diff', '--name-status', '--diff-filter=RD', merge_base, rev, '--', 'tests/').strip()
    if moved:
        fail(f'files under tests/ renamed or deleted: {moved.splitlines()}')
    for f in git('diff', '--name-only', merge_base, rev).split():
        if re.search(r'(^|/)(conftest\.py|pytest\.ini|tox\.ini|setup\.cfg)$', f):
            fail(f'{f} changed; pytest configuration is not part of this cycle')
    before, after = count_tests(merge_base), count_tests(rev)
    if after < before:
        fail(f'tests/ defines {after} test functions, fewer than {before} at the base')
    if show_seeds:
        print('seeds:', ' '.join(f'issues/{s}.md' for s in sorted(used)) or 'none')
        changed = git('diff', '--name-only', merge_base, rev, '--', 'tests/').split()
        print('tests changed (R11 small fixes and xfails, for the PR body):', ' '.join(changed) or 'none')
    return used


def check_pr_body(seeds: set) -> None:
    import json
    out = subprocess.run(['gh', 'pr', 'view', 'feature/uv-build-and-ci', '-R', 'glentner/cmdkit', '--json', 'body'],
                         capture_output=True, text=True, check=True).stdout
    body = json.loads(out)['body']
    for slug in sorted(seeds):
        if f'issues/{slug}.md' not in body:
            fail(f'the PR body does not name the seed issues/{slug}.md')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--rev', default='HEAD')
    ap.add_argument('--base', default='origin/develop')
    ap.add_argument('--seeds', action='store_true')
    ap.add_argument('--pr-body', action='store_true', help='also require the open PR body to name each seed (publish)')
    args = ap.parse_args()
    check_deferrals(args.rev)
    used = check_r11(args.rev, args.base, args.seeds or args.pr_body)
    if args.pr_body:
        check_pr_body(used)
    if FAILURES:
        print('\n'.join(f'FAIL: {f}' for f in FAILURES))
        return 1
    print('ok ledger: deferrals recorded, expected failures traced')
    return 0


if __name__ == '__main__':
    sys.exit(main())
