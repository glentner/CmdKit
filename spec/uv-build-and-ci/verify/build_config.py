"""Gate: the repository's build configuration (Poetry gone, uv's backend, groups, lock, src).

Modes (one or more, run in order):
  package   pyproject.toml: PEP 621 metadata, uv's build backend, no Poetry table; the
            `dev` and `docs` dependency groups equal to the base's Poetry groups with carets
            translated (the docs group may add `setuptools<82` alone), no extra beyond `toml`
            and `yaml`;
            poetry.lock gone and uv.lock committed; `uv lock --check`; the three locked
            floors (idna 3.15, tornado 6.5.7, soupsieve 2.8.4).
  nopoetry  no Poetry in pyproject.toml, under .github/ or in .readthedocs.yaml.
  src       nothing under src/ changed since the cycle's base (merge-base with origin/develop),
            and no .gitattributes changed (the gates export trees with git archive).

Reads committed state: every file comes from `git show <rev>:<path>` or `git archive <rev>`
(default HEAD), never the working copy.

Run from the repository root:
    uv run --isolated --no-project --python 3.14 --with packaging python -I spec/uv-build-and-ci/verify/build_config.py package nopoetry src [--rev REV] [--base REV]

Network: pypi.org (`uv lock --check`). Footprint: one process at a time; under 200 MB; seconds.
"""

# standard libs
import argparse
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib

# external libs
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

FLOORS = {'idna': Version('3.15'), 'tornado': Version('6.5.7'), 'soupsieve': Version('2.8.4')}
EXTRAS = {'toml': {'tomli', 'tomli-w'}, 'yaml': {'pyyaml'}}
FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout


def tracked(rev: str) -> list[str]:
    return git('ls-tree', '-r', '--name-only', rev).splitlines()


def show(rev: str, name: str) -> str:
    return git('show', f'{rev}:{name}')


def caret(spec: str) -> str:
    """Poetry's caret, `^X.Y.Z`, as a PEP 440 range."""
    if not spec.startswith('^'):
        return spec
    parts = [int(p) for p in spec[1:].split('.')]
    parts += [0] * (3 - len(parts))
    if parts[0] > 0:
        upper = f'{parts[0] + 1}.0.0'
    elif parts[1] > 0:
        upper = f'0.{parts[1] + 1}.0'
    else:
        upper = f'0.0.{parts[2] + 1}'
    return f'>={".".join(map(str, parts))},<{upper}'


def poetry_groups(rev: str) -> dict:
    """The base's Poetry dev and docs groups, carets translated, as comparable tuples."""
    doc = tomllib.loads(show(rev, 'pyproject.toml'))
    out = {}
    for name, table in doc.get('tool', {}).get('poetry', {}).get('group', {}).items():
        items = set()
        for pkg, spec in table.get('dependencies', {}).items():
            extras = frozenset(spec.get('extras', [])) if isinstance(spec, dict) else frozenset()
            version = spec['version'] if isinstance(spec, dict) else spec
            items.add((canonicalize_name(pkg), extras, str(SpecifierSet(caret(version))), ''))
        out[name] = items
    if set(out) != {'dev', 'docs'}:
        sys.exit(f'FAIL: the base at {rev[:9]} has Poetry groups {sorted(out)}, expected dev and docs')
    return out


def check_package(rev: str, base: str) -> None:
    files = tracked(rev)
    if 'poetry.lock' in files:
        fail('poetry.lock is still tracked')
    if 'uv.lock' not in files:
        fail('uv.lock is not committed')
        return
    text = show(rev, 'pyproject.toml')
    doc = tomllib.loads(text)
    if 'poetry' in doc.get('tool', {}):
        fail('pyproject.toml still has a [tool.poetry] table')
    backend = doc.get('build-system', {})
    if backend.get('build-backend') != 'uv_build':
        fail(f'build-backend is {backend.get("build-backend")!r}, expected uv_build')
    reqs = [Requirement(r) for r in backend.get('requires', [])]
    if [canonicalize_name(r.name) for r in reqs] != ['uv-build']:
        fail(f'build-system.requires is {backend.get("requires")}, expected uv_build alone')
    project = doc.get('project')
    if not isinstance(project, dict):
        fail('no PEP 621 [project] table')
        return
    for key in ('name', 'version', 'requires-python'):
        if key not in project:
            fail(f'[project] lacks {key}')
    if 'version' in project.get('dynamic', []):
        fail('the version is dynamic; it must be static in [project]')
    if project.get('dependencies'):
        fail(f'required runtime dependencies: {project["dependencies"]}')
    extras = project.get('optional-dependencies', {})
    got = {k: {canonicalize_name(Requirement(r).name) for r in v} for k, v in extras.items()}
    if got != EXTRAS:
        fail(f'extras are {got}, expected exactly {EXTRAS}')
    groups = doc.get('dependency-groups', {})
    if set(groups) != {'dev', 'docs'}:
        fail(f'dependency groups are {sorted(groups)}, expected dev and docs')
    if 'dev-dependencies' in doc.get('tool', {}).get('uv', {}):
        fail('[tool.uv] dev-dependencies is set; development dependencies live in [dependency-groups]')
    base_groups = poetry_groups(git('merge-base', base, rev).strip())
    for name, items in groups.items():
        got = set()
        for item in items:
            if isinstance(item, dict):
                fail(f'group {name} includes {item}; list requirements only')
                continue
            r = Requirement(item)
            got.add((canonicalize_name(r.name), frozenset(r.extras), str(SpecifierSet(str(r.specifier))), str(r.marker or '')))
        want = base_groups.get(name, set())
        extra = got - want
        allowed = {('setuptools', frozenset(), str(SpecifierSet('<82')), '')} if name == 'docs' else set()
        if want - got or extra - allowed:
            fail(f'group {name} differs from the Poetry group translated: missing {sorted(map(str, want - got))}, '
                 f'added {sorted(map(str, extra - allowed))}')
    # the lock covers both groups and is current
    lock = tomllib.loads(show(rev, 'uv.lock'))
    packages = lock.get('package', [])
    root = [p for p in packages if p.get('name') == 'cmdkit']
    if len(root) != 1:
        fail('uv.lock has no single cmdkit entry')
    elif set(root[0].get('dev-dependencies', {})) != {'dev', 'docs'}:
        fail(f'uv.lock locks groups {sorted(root[0].get("dev-dependencies", {}))}, expected dev and docs')
    seen = {}
    for p in packages:
        name = canonicalize_name(p.get('name', ''))
        if name in FLOORS:
            seen.setdefault(name, []).append(p['version'])
            if Version(p['version']) < FLOORS[name]:
                fail(f'uv.lock locks {name} {p["version"]}, below {FLOORS[name]}')
    print('locked:', ', '.join(f'{k} {sorted(v)}' for k, v in sorted(seen.items())) or 'none of the three')
    with tempfile.TemporaryDirectory(prefix='build-config-') as tmp:
        data = subprocess.run(['git', 'archive', '--format=tar', rev], capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(tmp, filter='data')
        env = dict(os.environ)
        for key in ('UV_PROJECT_ENVIRONMENT', 'VIRTUAL_ENV', 'UV_FROZEN', 'UV_LOCKED', 'UV_NO_SYNC'):
            env.pop(key, None)
        proc = subprocess.run(['uv', 'lock', '--check'], cwd=tmp, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            fail(f'uv lock --check failed: {proc.stderr.strip()}')


def check_nopoetry(rev: str) -> None:
    targets = [f for f in tracked(rev)
               if f in ('pyproject.toml', '.readthedocs.yaml') or f.startswith('.github/')]
    if 'pyproject.toml' not in targets:
        fail('pyproject.toml is not tracked')
    for name in targets:
        for n, line in enumerate(show(rev, name).splitlines(), 1):
            if re.search(r'poetry', line, re.IGNORECASE):
                fail(f'{name}:{n} names Poetry: {line.strip()}')


def check_src(rev: str, base: str) -> None:
    merge_base = git('merge-base', base, rev).strip()
    changed = git('diff', '--name-only', merge_base, rev, '--', 'src/').split()
    if changed:
        fail(f'src/ changed since {merge_base[:9]}: {changed}')
    # the gates materialise trees with `git archive`, which honours .gitattributes
    attrs = [f for f in git('diff', '--name-only', merge_base, rev).split() if f.endswith('.gitattributes')]
    if attrs:
        fail(f'.gitattributes changed in the cycle: {attrs}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('modes', nargs='+', choices=['package', 'nopoetry', 'src'])
    ap.add_argument('--rev', default='HEAD')
    ap.add_argument('--base', default='origin/develop')
    args = ap.parse_args()
    for mode in args.modes:
        if mode == 'package':
            check_package(args.rev, args.base)
        elif mode == 'nopoetry':
            check_nopoetry(args.rev)
        else:
            check_src(args.rev, args.base)
    if FAILURES:
        print('\n'.join(f'FAIL: {f}' for f in FAILURES))
        return 1
    print(f'ok build_config: {" ".join(args.modes)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
