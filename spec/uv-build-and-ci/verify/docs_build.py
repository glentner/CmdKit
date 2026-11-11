"""Gate: the documentation builds through uv, as the GOAL's command and as Read the Docs does.

1. The GOAL's command, `uv run --group docs sphinx-build docs docs/_build/html`, at the root of
   a fresh export of the committed tree (`git archive <rev>`, default HEAD): exit 0, an
   index.html, and the page carries the version from pyproject.toml (docs/conf.py reads it
   from the installed cmdkit, so the project itself was installed).
2. Read the Docs' uv install, emulated: an exact `uv sync --group docs` into a fresh
   environment on the Python that .readthedocs.yaml names (no implicit setuptools or pip),
   then Read the Docs' own sphinx invocation with that environment's interpreter.

Run from the repository root, with the sandbox off (sphinx extensions write user caches):
    uv run --isolated --no-project --python 3.14 --with pyyaml python -I spec/uv-build-and-ci/verify/docs_build.py [--rev REV]

Network: pypi.org, files.pythonhosted.org. Footprint: one sphinx build at a time; under 1 GB;
about 10-40 s warm.
"""

# standard libs
import argparse
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib

# external libs
import yaml


def run(cmd: list[str], cwd: str, env: dict, label: str) -> None:
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = '\n'.join((proc.stdout + proc.stderr).splitlines()[-25:])
        sys.exit(f'FAIL: {label}: {" ".join(cmd)} exited {proc.returncode}\n{tail}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--rev', default='HEAD')
    args = ap.parse_args()
    env = dict(os.environ)  # a saved copy, never a cleared one
    for key in ('UV_PROJECT_ENVIRONMENT', 'VIRTUAL_ENV', 'UV_PYTHON', 'UV_FROZEN', 'UV_LOCKED', 'UV_NO_SYNC'):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='docs-build-') as tmp:
        tree = os.path.join(tmp, 'tree')
        os.mkdir(tree)
        data = subprocess.run(['git', 'archive', '--format=tar', args.rev], capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(tree, filter='data')
        with open(os.path.join(tree, 'pyproject.toml'), 'rb') as fh:
            version = tomllib.load(fh)['project']['version']
        # 1. the GOAL's command, verbatim, at the root
        run(['uv', 'run', '--group', 'docs', 'sphinx-build', 'docs', 'docs/_build/html'], tree, env, 'R7 command')
        index = os.path.join(tree, 'docs', '_build', 'html', 'index.html')
        if not os.path.isfile(index):
            sys.exit('FAIL: R7 command made no index.html')
        if version not in open(index, encoding='utf-8').read():
            sys.exit(f'FAIL: the built docs do not carry version {version}')
        # 2. Read the Docs' uv install, emulated
        with open(os.path.join(tree, '.readthedocs.yaml')) as fh:
            rtd = yaml.safe_load(fh)
        install = rtd['python']['install']
        if install != [{'method': 'uv', 'command': 'sync', 'groups': ['docs']}]:
            sys.exit(f'FAIL: .readthedocs.yaml install is {install}; this emulation covers one uv sync of docs')
        py = str(rtd['build']['tools']['python'])
        venv = os.path.join(tmp, 'rtd-venv')
        rtd_env = dict(env, UV_PROJECT_ENVIRONMENT=venv, READTHEDOCS='True')
        run(['uv', 'sync', '--group', 'docs', '--python', py, '--managed-python'], tree, rtd_env, 'RTD install')
        exe = os.path.join(venv, 'Scripts' if os.name == 'nt' else 'bin', 'python')
        out = os.path.join(tmp, 'rtd-html')
        run([exe, '-m', 'sphinx', '-T', '-b', 'html', '-d', os.path.join(tmp, 'doctrees'),
             '-D', 'language=en', 'docs', out], tree, rtd_env, f'RTD build on Python {py}')
        if not os.path.isfile(os.path.join(out, 'index.html')):
            sys.exit('FAIL: RTD emulation made no index.html')
    print(f'ok docs_build: R7 command and the Read the Docs uv install (Python {py}) build cmdkit {version}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
