"""Gate: the CI, publish, Read the Docs and dependabot configuration, and AGENTS.md § Factory.

Modes (one or more, run in order):
  publish     .github/workflows/publish.yml: on release creation, `uv build` then `uv publish`
              to PyPI with the PYPI_TOKEN secret, Actions at their current major.
  tests       .github/workflows/tests.yml: the ten (os, python) jobs, triggers, uv installs,
              the whole suite, Actions at their current major.
  rtd         .readthedocs.yaml: installs the docs group and cmdkit through uv (schema-checked).
  dependabot  .github/dependabot.yml: uv and github-actions, each targeting develop (schema-checked).
  publishrun  publish.yml's own run lines on a fresh export of <rev>, the upload as
              `uv publish --dry-run` with a placeholder token: both distributions are found.
  recipe      AGENTS.md: the release recipe reads project.version, locks with uv lock and
              bumps pyproject.toml and uv.lock; the high-blast-radius list names uv.lock.
  agents      recipe, plus: verify runs under uv's build backend, the gate and verify cover the
              tests.yml Linux matrix, § Factory names no Poetry, and § Invariants 4 drops the
              CI known limitation.

Reads committed state (`git show <rev>:<path>`, default HEAD). Workflows are also linted with
actionlint. "Current major" is the highest vN among the action repository's tags, read live
with `git ls-remote`; the pinned ref must be an existing tag of that major.

Run from the repository root:
    uv run --isolated --no-project --python 3.14 --with pyyaml --with check-jsonschema --with actionlint-py python -I spec/uv-build-and-ci/verify/workflow_config.py MODE... [--rev REV]

Network: github.com (tag listing). Footprint: one process at a time; under 200 MB; seconds.
"""

# standard libs
import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile

# external libs
import yaml

ACTIONS = {'actions/checkout', 'astral-sh/setup-uv'}
LINUX = ['3.9', '3.10', '3.11', '3.12', '3.13', '3.14']
JOBS = {('ubuntu-latest', v) for v in LINUX} | {
    (os_, v) for os_ in ('macos-latest', 'windows-latest') for v in ('3.9', '3.14')}
FAILURES: list[str] = []
_TAGS: dict[str, set[str]] = {}


def fail(msg: str) -> None:
    FAILURES.append(msg)


def show(rev: str, name: str) -> str | None:
    proc = subprocess.run(['git', 'show', f'{rev}:{name}'], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def load(rev: str, name: str):
    text = show(rev, name)
    if text is None:
        fail(f'{name} is not committed')
        return None, None
    return yaml.safe_load(text), text


def tags(repo: str) -> set[str]:
    if repo not in _TAGS:
        out = subprocess.run(['git', 'ls-remote', '--tags', '--refs', f'https://github.com/{repo}'],
                             capture_output=True, text=True, check=True).stdout
        _TAGS[repo] = {line.split('refs/tags/', 1)[1] for line in out.splitlines() if 'refs/tags/' in line}
        if not _TAGS[repo]:
            sys.exit(f'FAIL: no tags listed for {repo}')
    return _TAGS[repo]


def check_uses(where: str, uses: str) -> str:
    """Fail unless `uses` is an allowed action at an existing tag of its current major."""
    repo, _, ref = uses.partition('@')
    if repo not in ACTIONS:
        fail(f'{where}: uses {uses}; only {sorted(ACTIONS)} are expected')
        return repo
    all_tags = tags(repo)
    majors = [int(m.group(1)) for t in all_tags if (m := re.fullmatch(r'v(\d+)(\.\d+){0,2}', t))]
    current = max(majors)
    if ref not in all_tags:
        fail(f'{where}: {uses} is not a published tag of {repo}')
    elif not re.fullmatch(rf'v{current}(\.\d+){{0,2}}', ref):
        fail(f'{where}: {uses} is not at the current major v{current}')
    return repo


def triggers(doc: dict):
    # YAML 1.1 reads the bare key `on` as True
    return doc.get('on', doc.get(True))


def steps_of(job: dict) -> list[dict]:
    return job.get('steps') or []


STEP_KEYS = {'name', 'uses', 'run', 'env', 'with'}


def shape(where: str, doc: dict, job: dict, job_keys: set) -> None:
    """The workflow and its job carry exactly the keys the design names, nothing that moves,
    gates, containerizes or re-scopes the job (defaults, environment, container, timeouts)."""
    top = {('on' if k is True else k) for k in doc}
    if top != {'name', 'on', 'permissions', 'jobs'}:
        fail(f'{where}: top-level keys {sorted(map(str, top))}, expected name, on, permissions, jobs')
    if doc.get('permissions') != {'contents': 'read'}:
        fail(f'{where}: permissions must be exactly contents: read')
    if set(job) != job_keys:
        fail(f'{where}: job keys {sorted(job)}, expected {sorted(job_keys)}')
    for st in steps_of(job):
        if set(st) - STEP_KEYS or ('uses' in st) == ('run' in st):
            fail(f'{where}: step {st.get("name") or st.get("uses") or st.get("run")!r} has keys {sorted(st)}')


def no_soft_failure(where: str, job: dict) -> None:
    if 'if' in job or job.get('continue-on-error'):
        fail(f'{where}: the job is conditional or allowed to fail')
    for s in steps_of(job):
        if 'if' in s or s.get('continue-on-error'):
            fail(f'{where}: step {s.get("name") or s.get("uses") or s.get("run")!r} is conditional or allowed to fail')
        if s.get('working-directory') or 'shell' in s:
            fail(f'{where}: step {s.get("name")!r} changes its directory or shell')
    if 'defaults' in job:
        fail(f'{where}: job-level defaults are not expected')


def actionlint(rev: str, name: str, text: str) -> None:
    with tempfile.TemporaryDirectory(prefix='actionlint-') as tmp:
        os.makedirs(os.path.join(tmp, '.github', 'workflows'))
        target = os.path.join(tmp, '.github', 'workflows', os.path.basename(name))
        with open(target, 'w') as fh:
            fh.write(text)
        proc = subprocess.run(['actionlint', '-no-color', target], cwd=tmp, capture_output=True, text=True)
        if proc.returncode != 0:
            fail(f'actionlint {name}: {proc.stdout.strip()} {proc.stderr.strip()}')


def schema(rev: str, name: str, text: str, builtin: str) -> None:
    with tempfile.TemporaryDirectory(prefix='schema-') as tmp:
        target = os.path.join(tmp, os.path.basename(name))
        with open(target, 'w') as fh:
            fh.write(text)
        proc = subprocess.run(['check-jsonschema', '--no-cache', '--builtin-schema', builtin, target],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            fail(f'{name} fails the {builtin} schema: {proc.stdout.strip()} {proc.stderr.strip()}')


def run_lines(job: dict) -> list[list[str]]:
    out = []
    for s in steps_of(job):
        if 'run' in s:
            for line in str(s['run']).splitlines():
                if line.strip():
                    out.append(shlex.split(line))
    return out


def check_publish(rev: str) -> None:
    name = '.github/workflows/publish.yml'
    doc, text = load(rev, name)
    if doc is None:
        return
    actionlint(rev, name, text)
    if triggers(doc) != {'release': {'types': ['created']}}:
        fail(f'{name}: triggers are {triggers(doc)}, expected release: types [created]')
    jobs = doc.get('jobs') or {}
    if len(jobs) != 1:
        fail(f'{name}: expected one job, got {sorted(jobs)}')
        return
    (jid, job), = jobs.items()
    shape(name, doc, job, {'runs-on', 'steps'})
    no_soft_failure(name, job)
    kinds = [('uses', st['uses'].partition('@')[0]) if 'uses' in st else ('run', str(st['run']).strip())
             for st in steps_of(job)]
    if kinds != [('uses', 'actions/checkout'), ('uses', 'astral-sh/setup-uv'), ('run', 'uv build'), ('run', 'uv publish')]:
        fail(f'{name}: steps are {kinds}, expected checkout, setup-uv, `uv build`, `uv publish` in that order')
    for st in steps_of(job):
        if 'with' in st:
            fail(f'{name}: step {st.get("name") or st.get("uses")!r} takes inputs {st["with"]}; none are expected '
                 f'(a pinned uv version would not be the uv the dry run exercised)')
        if 'env' in st and not str(st.get('run', '')).strip().startswith('uv publish'):
            fail(f'{name}: only the publish step takes an environment')
    if not str(job.get('runs-on', '')).startswith('ubuntu-'):
        fail(f'{name}: runs-on {job.get("runs-on")!r}')
    used = [check_uses(name, s['uses']) for s in steps_of(job) if 'uses' in s]
    if sorted(used) != sorted(ACTIONS):
        fail(f'{name}: uses {used}, expected checkout and setup-uv once each')
    lines = run_lines(job)
    builds = [i for i, l in enumerate(lines) if l[:2] == ['uv', 'build']]
    pubs = [i for i, l in enumerate(lines) if l[:2] == ['uv', 'publish']]
    if lines != [lines[i] for i in builds + pubs] or len(builds) != 1 or len(pubs) != 1 or builds[0] > pubs[0]:
        fail(f'{name}: run lines are {lines}, expected `uv build` then `uv publish`, nothing else')
    else:
        if lines[builds[0]] != ['uv', 'build']:
            fail(f'{name}: `uv build` takes no arguments here (dist/ is what uv publish reads): {lines[builds[0]]}')
        if lines[pubs[0]] != ['uv', 'publish']:
            fail(f'{name}: `uv publish` takes no arguments here (PyPI, dist/*): {lines[pubs[0]]}')
    env = {}
    for scope in [doc.get('env') or {}, job.get('env') or {}] + [s.get('env') or {} for s in steps_of(job)]:
        env.update(scope)
    pub_step = next((s for s in steps_of(job) if str(s.get('run', '')).strip().startswith('uv publish')), {})
    if (pub_step.get('env') or {}) != {'UV_PUBLISH_TOKEN': '${{ secrets.PYPI_TOKEN }}'}:
        fail(f'{name}: the publish step does not take UV_PUBLISH_TOKEN from secrets.PYPI_TOKEN')
    for key in env:
        if key.startswith('UV_') and key != 'UV_PUBLISH_TOKEN':
            fail(f'{name}: sets {key}, which can redirect or alter the upload')
    secrets = set(re.findall(r'secrets\.([A-Za-z0-9_]+)', text))
    if secrets != {'PYPI_TOKEN'}:
        fail(f'{name}: references secrets {sorted(secrets)}, expected PYPI_TOKEN only')


def check_tests(rev: str) -> None:
    name = '.github/workflows/tests.yml'
    doc, text = load(rev, name)
    if doc is None:
        return
    actionlint(rev, name, text)
    on = triggers(doc) or {}
    want = {'push': {'branches': {'master', 'develop'}}, 'pull_request': {'branches': {'develop'}}}
    got = {k: {kk: set(vv) if isinstance(vv, list) else vv for kk, vv in (v or {}).items()}
           for k, v in on.items()} if isinstance(on, dict) else on
    if got != want:
        fail(f'{name}: triggers are {on}, expected pushes to develop and master and PRs into develop')
    jobs = doc.get('jobs') or {}
    if len(jobs) != 1:
        fail(f'{name}: expected one matrix job, got {sorted(jobs)}')
        return
    (jid, job), = jobs.items()
    shape(name, doc, job, {'name', 'runs-on', 'strategy', 'env', 'steps'})
    no_soft_failure(name, job)
    kinds = [('uses', st['uses'].partition('@')[0]) if 'uses' in st else ('run',) for st in steps_of(job)]
    if kinds != [('uses', 'actions/checkout'), ('uses', 'astral-sh/setup-uv'), ('run',)]:
        fail(f'{name}: steps are {kinds}, expected checkout, setup-uv, then the one test step')
    strategy = job.get('strategy') or {}
    if strategy.get('fail-fast') is not False:
        fail(f'{name}: fail-fast must be false so every job reports')
    if set(strategy) != {'fail-fast', 'matrix'}:
        fail(f'{name}: strategy keys {sorted(strategy)}, expected fail-fast and matrix')
    matrix = strategy.get('matrix') or {}
    if set(matrix) - {'os', 'python', 'include'}:
        fail(f'{name}: matrix keys {sorted(matrix)}; expected os, python, include')
    combos = {(o, str(p)) for o in matrix.get('os', []) for p in matrix.get('python', [])}
    for inc in matrix.get('include', []) or []:
        if set(inc) != {'os', 'python'}:
            fail(f'{name}: include entry {inc} must set exactly os and python')
            continue
        combos.add((inc['os'], str(inc['python'])))
    if combos != JOBS:
        fail(f'{name}: matrix jobs differ: missing {sorted(JOBS - combos)}, extra {sorted(combos - JOBS)}')
    if job.get('runs-on') != '${{ matrix.os }}':
        fail(f'{name}: runs-on must be the matrix os')
    if job.get('name') != '${{ matrix.os }} / py${{ matrix.python }}':
        fail(f'{name}: job name must be `${{{{ matrix.os }}}} / py${{{{ matrix.python }}}}`')
    if (job.get('env') or {}).get('UV_PYTHON_PREFERENCE') != 'only-managed':
        fail(f'{name}: UV_PYTHON_PREFERENCE must be only-managed (Python installed by uv)')
    env_all = {**(doc.get('env') or {}), **(job.get('env') or {})}
    for s in steps_of(job):
        env_all.update(s.get('env') or {})
    for key in env_all:
        if key not in ('UV_PYTHON_PREFERENCE',):
            fail(f'{name}: sets {key}; no other environment is expected')
    used = []
    for s in steps_of(job):
        if 'uses' in s:
            repo = check_uses(name, s['uses'])
            used.append(repo)
            if repo == 'astral-sh/setup-uv' and (s.get('with') or {}) != {'python-version': '${{ matrix.python }}'}:
                fail(f'{name}: setup-uv must take python-version from the matrix and nothing else')
            if repo == 'actions/checkout' and s.get('with'):
                fail(f'{name}: checkout inputs {s["with"]} are not expected')
    if used != ['actions/checkout', 'astral-sh/setup-uv']:
        fail(f'{name}: uses {used}, expected checkout then setup-uv')
    lines = run_lines(job)
    if lines != [['uv', 'run', '--locked', 'python', '-m', 'pytest', '-v']]:
        fail(f'{name}: run lines are {lines}, expected exactly `uv run --locked python -m pytest -v`')


def check_rtd(rev: str) -> None:
    name = '.readthedocs.yaml'
    doc, text = load(rev, name)
    if doc is None:
        return
    schema(rev, name, text, 'vendor.readthedocs')
    build = doc.get('build') or {}
    if 'jobs' in build or 'commands' in build:
        fail(f'{name}: build.jobs/commands override the uv install; not expected')
    if not str(build.get('os', '')).startswith('ubuntu-'):
        fail(f'{name}: build.os is {build.get("os")!r}')
    if not re.fullmatch(r'3\.(9|1[0-4])', str((build.get('tools') or {}).get('python', ''))):
        fail(f'{name}: build.tools.python must be a supported 3.x from 3.9 to 3.14')
    install = (doc.get('python') or {}).get('install')
    if install != [{'method': 'uv', 'command': 'sync', 'groups': ['docs']}]:
        fail(f'{name}: python.install is {install}, expected one uv sync of the docs group')
    if (doc.get('sphinx') or {}).get('configuration') != 'docs/conf.py':
        fail(f'{name}: sphinx.configuration is not docs/conf.py')
    if re.search(r'\bpip\b|poetry', text, re.IGNORECASE):
        fail(f'{name}: names pip or Poetry')


def check_dependabot(rev: str) -> None:
    name = '.github/dependabot.yml'
    doc, text = load(rev, name)
    if doc is None:
        return
    schema(rev, name, text, 'vendor.dependabot')
    updates = doc.get('updates') or []
    eco = [u.get('package-ecosystem') for u in updates]
    if sorted(eco) != ['github-actions', 'uv']:
        fail(f'{name}: ecosystems are {eco}, expected uv and github-actions once each')
    for u in updates:
        if u.get('target-branch') != 'develop':
            fail(f'{name}: {u.get("package-ecosystem")} targets {u.get("target-branch")!r}, expected develop')
        if u.get('directory') != '/':
            fail(f'{name}: {u.get("package-ecosystem")} directory is {u.get("directory")!r}, expected /')


def check_publishrun(rev: str) -> None:
    """Run publish.yml's own run lines on a fresh export, the upload as a dry run."""
    import io, tarfile
    doc, _ = load(rev, '.github/workflows/publish.yml')
    if doc is None:
        return
    (job,) = (doc.get('jobs') or {}).values()
    env = dict(os.environ)  # a saved copy
    for key in list(env):
        if key.startswith('UV_') and key not in ('UV_CACHE_DIR', 'UV_TOOL_DIR'):
            env.pop(key)
    env.pop('VIRTUAL_ENV', None)
    with tempfile.TemporaryDirectory(prefix='publishrun-') as tmp:
        data = subprocess.run(['git', 'archive', '--format=tar', rev], capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(tmp, filter='data')
        for s in steps_of(job):
            if 'run' not in s:
                continue
            step_env = dict(env, **{k: ('pypi-dry-run-token' if 'secrets.' in str(v) else str(v))
                                    for k, v in (s.get('env') or {}).items()})
            for line in str(s['run']).splitlines():
                cmd = shlex.split(line)
                if cmd[:2] == ['uv', 'publish']:
                    cmd.append('--dry-run')
                proc = subprocess.run(cmd, cwd=tmp, env=step_env, capture_output=True, text=True)
                if proc.returncode != 0:
                    fail(f'publish.yml line {line!r} failed on the export: {proc.stderr.strip()[-400:]}')
                    return
                if cmd[:2] == ['uv', 'publish']:
                    checked = re.findall(r'^Checking (\S+\.(?:whl|tar\.gz)) ', proc.stderr + proc.stdout, re.M)
                    dist = sorted(f for f in os.listdir(os.path.join(tmp, 'dist')) if not f.startswith('.'))
                    if sorted(checked) != dist or len(dist) != 2:
                        fail(f'uv publish would upload {checked}; dist/ holds {dist}')


def section(text: str, start: str, stop: str) -> str:
    i = text.find(start)
    j = text.find(stop, i + 1)
    if i < 0 or j < 0:
        fail(f'AGENTS.md: cannot find the section between {start!r} and {stop!r}')
        return ''
    return text[i:j]


def gate_pythons(cmd: str) -> list[str] | None:
    m = re.match(r'\(for v in ([\d. ]+); do uv run --isolated --no-project --python \$v ', cmd)
    return m.group(1).split() if m else None


def agents_parts(rev: str):
    text = show(rev, 'AGENTS.md')
    if text is None:
        fail('AGENTS.md is not committed')
        return None, None, None
    factory = section(text, '## Factory', '## Invariants')
    recipe_src = re.search(r'```yaml\n(release:.*?)```', factory, re.S)
    if not recipe_src:
        fail('AGENTS.md: no release recipe block in § Factory')
        return None, None, None
    return text, factory, yaml.safe_load(recipe_src.group(1))['release']


def check_recipe(rev: str) -> None:
    text, factory, recipe = agents_parts(rev)
    if recipe is None:
        return
    if recipe['version']['source'] != 'pyproject.toml project.version':
        fail(f'release recipe version.source is {recipe["version"]["source"]!r}')
    if recipe['bump']['lock'] != 'uv lock':
        fail(f'release recipe bump.lock is {recipe["bump"]["lock"]!r}, expected uv lock')
    if recipe['bump']['files'] != ['pyproject.toml', 'uv.lock']:
        fail(f'release recipe bump.files is {recipe["bump"]["files"]}')
    recipe_text = re.search(r'```yaml\n(release:.*?)```', factory, re.S).group(1)
    if re.search(r'poetry', recipe_text, re.IGNORECASE):
        fail('the release recipe still names Poetry')
    hbr = section(text, '### High-blast-radius paths', '### 1.')
    if not re.search(r'^- .*`uv\.lock`', hbr, re.M):
        fail('the high-blast-radius list does not name uv.lock')
    if not re.search(r'^- .*`poetry\.lock`', hbr, re.M):
        fail('the high-blast-radius list dropped poetry.lock (the list only widens)')


def check_agents(rev: str) -> None:
    check_recipe(rev)
    text, factory, recipe = agents_parts(rev)
    if recipe is None:
        return
    tests = yaml.safe_load(show(rev, '.github/workflows/tests.yml') or '{}') or {}
    matrix = next(iter((tests.get('jobs') or {'': {}}).values())).get('strategy', {}).get('matrix', {})
    linux = sorted({str(p) for p in matrix.get('python', [])}
                   | {str(i['python']) for i in matrix.get('include', []) or [] if str(i.get('os', '')).startswith('ubuntu')}
                   if 'ubuntu-latest' in matrix.get('os', []) else set(), key=lambda v: tuple(map(int, v.split('.'))))
    if linux != LINUX:
        fail(f'tests.yml Linux pythons are {linux}, expected {LINUX}')
    gates = [g for g in recipe['gate'] if isinstance(g, str) and g.startswith('(for v in')]
    if len(gates) != 1 or gate_pythons(gates[0]) != linux:
        fail(f'release recipe gate pythons {[gate_pythons(g) for g in gates]} are not the Linux matrix {linux}')
    verify = re.search(r'^\| verify \| `([^`]*)`(.*)\|$', factory, re.M)
    if not verify:
        fail('AGENTS.md: no verify row in the profile')
    else:
        if gate_pythons(verify.group(1)) != [linux[0], linux[-1]]:
            fail(f'verify pythons {gate_pythons(verify.group(1))} are not the floor and newest {linux[0]}, {linux[-1]}')
        if "uv's build backend" not in verify.group(2):
            fail('verify row does not say it runs under uv\'s build backend')
    if re.search(r'poetry', factory, re.IGNORECASE):
        fail('AGENTS.md § Factory still names Poetry')
    inv4 = section(text, '### 4. Footprint', '### Conventions')
    flat = ' '.join(inv4.split())  # rewrapped lines read as one
    for item in re.split(r' - ', flat):
        if re.search(r'known limitation|not fixed', item, re.IGNORECASE) and \
                re.search(r'\bCI\b|tests\.yml|matrix|3\.10|3\.13|uv-build-and-ci', item, re.IGNORECASE):
            fail(f'§ Invariants 4 still records CI coverage as a known limitation: {item[:100]}')
    if not re.search(r'CI and the release gate cover every minor version from the floor to the newest', flat):
        fail('§ Invariants 4 lost its coverage rule')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('modes', nargs='+', choices=['publish', 'publishrun', 'tests', 'rtd', 'dependabot', 'recipe', 'agents'])
    ap.add_argument('--rev', default='HEAD')
    args = ap.parse_args()
    for mode in args.modes:
        globals()[f'check_{mode}'](args.rev)
    if FAILURES:
        print('\n'.join(f'FAIL: {f}' for f in FAILURES))
        return 1
    print(f'ok workflow_config: {" ".join(args.modes)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
