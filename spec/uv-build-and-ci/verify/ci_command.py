"""Gate: the suite as CI and the profile run it, on fresh exports of the committed tree.

Modes:
  ci PY...       tests.yml's own run line (it must be `uv run --locked python -m pytest -v`) at the
                 root of `git archive <rev>`, for each Python, with the job's environment
                 (`UV_PYTHON=<py>`, `UV_PYTHON_PREFERENCE=only-managed`, as setup-uv's
                 `python-version` input sets it on the runner).
  profile PY...  the profile's `verify` command (an editable install of the export, unlocked
                 test dependencies) for each Python.
  collect        the number of tests pytest collects at <rev> and at the cycle's base (the
                 merge-base with origin/develop); fails if <rev> collects fewer, else prints the
                 number alone on its last line. The CI evidence requires every graded job to
                 report exactly this many.

Every run's pytest summary may show only passed and xfailed tests (the ledger governs any xfail).

Run from the repository root, with the sandbox off (the suite writes /tmp/cmdkit/config):
    uv run --isolated --no-project --python 3.14 --with pyyaml python -I spec/uv-build-and-ci/verify/ci_command.py MODE [PY...] [--rev REV] [--base REV]

Network: pypi.org, files.pythonhosted.org, and uv's Python download hosts on first use.
Footprint: one pytest process at a time; under 300 MB; seconds per Python once cached.
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

# external libs
import yaml

EXPECTED = 'uv run --locked python -m pytest -v'
PROFILE = ['uv', 'run', '--isolated', '--no-project', '--python', '{py}', '--with', 'pytest', '--with', 'hypothesis',
           '--with', 'tomli', '--with', 'tomli-w', '--with', 'pyyaml', '--with-editable', '.', 'python', '-m', 'pytest']
SUMMARY = re.compile(r'^=*\s*(?P<body>(?:\d+ \w+(?:, )?)+) in [\d.]+s(?: \([^)]*\))?\s*=*\s*$')


def export(rev: str, dest: str) -> None:
    data = subprocess.run(['git', 'archive', '--format=tar', rev], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(dest, filter='data')


def clean_env() -> dict:
    env = dict(os.environ)  # a saved copy, never a cleared one
    for key in ('VIRTUAL_ENV', 'UV_PROJECT_ENVIRONMENT', 'UV_FROZEN', 'UV_NO_SYNC', 'UV_PYTHON',
                'UV_PYTHON_PREFERENCE', 'PYTEST_ADDOPTS', 'FORCE_COLOR'):
        env.pop(key, None)
    return env


def summary(out: str) -> dict:
    found = [m.group('body') for line in out.splitlines() if (m := SUMMARY.search(line))]
    if not found:
        return {}
    return {w: int(n) for n, w in (p.split(' ', 1) for p in found[-1].split(', '))}


def run_suite(cmd: list[str], cwd: str, env: dict, label: str, py: str) -> None:
    proc = subprocess.run(cmd + ['-p', 'no:cacheprovider'], cwd=cwd, env=env, capture_output=True, text=True)
    got = summary(proc.stdout)
    if proc.returncode != 0 or f'Python {py}.' not in proc.stdout or not got.get('passed') \
            or set(got) - {'passed', 'xfailed', 'warning', 'warnings'}:
        print((proc.stdout + proc.stderr)[-3000:])
        sys.exit(f'FAIL: {label} on Python {py}: exit {proc.returncode}, summary {got}')
    print(f'{label} Python {py}: {got}')


def collected(rev: str, env: dict) -> int:
    with tempfile.TemporaryDirectory(prefix='ci-collect-') as tmp:
        export(rev, tmp)
        cmd = [a.replace('{py}', '3.14') for a in PROFILE] + ['--collect-only', '-q', '-p', 'no:cacheprovider']
        proc = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True)
        m = re.search(r'^(\d+) tests? collected', proc.stdout, re.M)
        if proc.returncode != 0 or not m:
            print((proc.stdout + proc.stderr)[-2000:])
            sys.exit(f'FAIL: pytest --collect-only at {rev[:9]} exited {proc.returncode}')
        return int(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['ci', 'profile', 'collect'])
    ap.add_argument('pythons', nargs='*')
    ap.add_argument('--rev', default='HEAD')
    ap.add_argument('--base', default='origin/develop')
    args = ap.parse_args()
    env = clean_env()
    if args.mode == 'collect':
        base = subprocess.run(['git', 'merge-base', args.base, args.rev], capture_output=True, text=True,
                              check=True).stdout.strip()
        n_base, n_rev = collected(base, env), collected(args.rev, env)
        if n_rev < n_base:
            sys.exit(f'FAIL: {n_rev} tests collected at {args.rev}, fewer than {n_base} at the base')
        print(f'collected: base {n_base}, {args.rev} {n_rev}')
        print(n_rev)
        return 0
    if not args.pythons:
        sys.exit('FAIL: name at least one Python')
    if args.mode == 'ci':
        text = subprocess.run(['git', 'show', f'{args.rev}:.github/workflows/tests.yml'],
                              capture_output=True, text=True, check=True).stdout
        (job,) = yaml.safe_load(text)['jobs'].values()
        runs = [s['run'].strip() for s in job['steps'] if 'run' in s]
        if runs != [EXPECTED]:
            sys.exit(f'FAIL: tests.yml run lines are {runs}, expected [{EXPECTED!r}]')
    with tempfile.TemporaryDirectory(prefix='ci-command-') as tmp:
        export(args.rev, tmp)
        for v in args.pythons:
            if args.mode == 'ci':
                run_suite(EXPECTED.split(), tmp, dict(env, UV_PYTHON=v, UV_PYTHON_PREFERENCE='only-managed'), 'CI command', v)
            else:
                run_suite([a.replace('{py}', v) for a in PROFILE], tmp, env, 'profile verify', v)
    print(f'ok ci_command {args.mode}: {" ".join(args.pythons)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
