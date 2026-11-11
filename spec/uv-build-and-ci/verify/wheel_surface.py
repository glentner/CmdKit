"""Gate: the distributions `uv build` makes carry cmdkit 2.7.7's install surface.

Checks the requirements on the built distributions (one sdist and one py3-none-any wheel;
the wheel's METADATA compared field by field with the 2.7.7 wheel from PyPI, against the
GOAL's list of permitted differences; the files under cmdkit/; the licence text), on three
wheels: the one `uv build` makes at the root (built from its sdist), one built directly from
the tree with `uv build --wheel`, and one built from the sdist file by path; and the same field
comparison on the sdist's PKG-INFO, its licence files read from the sdist. Then installs the
root wheel into an isolated environment and checks `cmdkit.__version__`.

Reads committed state: the tree is `git archive <rev>` (default HEAD) unpacked into a fresh
temporary directory, never the working copy.

Run from the repository root:
    uv run --isolated --no-project --with packaging python -I spec/uv-build-and-ci/verify/wheel_surface.py [--rev REV]

Network: files.pythonhosted.org (the reference wheel, pinned by URL and sha256) and pypi.org
(the build backend and the install check).
Footprint: one process at a time (git, uv, python); peak under 300 MB; about 10-30 s warm.
Exit 0 and a final `ok` line on success; exit 1 with every failure listed otherwise.
"""

# standard libs
import argparse
import email.parser
import email.policy
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile

# external libs
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

REF_URL = ('https://files.pythonhosted.org/packages/23/62/'
           'c82680c31dc2dcfa55918a28720d2e5695cbb4e778b621416d12883203cd/'
           'cmdkit-2.7.7-py3-none-any.whl')
REF_SHA256 = '9dfb1ae63329d0ce1970886206ef14a9773d5ebcc15608c96df119bc82abf023'
REF_DISTINFO = 'cmdkit-2.7.7.dist-info'

PY_MINORS = [f'3.{n}' for n in range(9, 15)]  # every minor from 3.9 to 3.14
PY_CLASSIFIER = re.compile(r'^Programming Language :: Python :: 3\.\d+$')
AUTHOR_EMAIL = 'Geoffrey Lentner <glentner@purdue.edu>'
LICENSE_EXPRESSION = 'Apache-2.0'
LICENSE_CLASSIFIER = 'License :: OSI Approved :: Apache Software License'

# The exact install surface R1 names, independent of the reference wheel.
R1_REQUIRES_PYTHON = SpecifierSet('>=3.9,<4.0')
R1_EXTRAS = {'toml', 'yaml'}
R1_REQUIRES = {
    ('tomli', SpecifierSet('>=2.1.0,<3.0.0'), 'extra == "toml"'),
    ('tomli-w', SpecifierSet('>=1.1.0,<2.0.0'), 'extra == "toml"'),
    ('pyyaml', SpecifierSet('>=6.0.1,<7.0.0'), 'extra == "yaml"'),
}
R1_MODULES = {
    'cmdkit/__init__.py', 'cmdkit/ansi.py', 'cmdkit/app.py', 'cmdkit/cli.py',
    'cmdkit/config.py', 'cmdkit/contrib/__init__.py', 'cmdkit/contrib/builder.py',
    'cmdkit/logging.py', 'cmdkit/namespace.py', 'cmdkit/platform.py', 'cmdkit/py.typed',
}

# Fields whose difference R2 permits, each checked by its own rule below.
HANDLED = {'Metadata-Version', 'Version', 'Classifier', 'Home-page', 'Project-URL',
           'Author', 'Author-email', 'License', 'License-Expression', 'License-File',
           'Requires-Dist', 'Requires-Python', 'Provides-Extra'}

FAILURES: list[str] = []


def fail(where: str, msg: str) -> None:
    FAILURES.append(f'{where}: {msg}')


def run(cmd: list[str], cwd: str, env: dict) -> str:
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f'FAIL: {" ".join(cmd)} exited {proc.returncode}\n{proc.stdout}\n{proc.stderr}')
    return proc.stdout


def fetch_reference(dest: str) -> str:
    data, errors = b'', []
    for _ in range(3):  # a dropped connection is retried; the pinned digest decides
        try:
            data = urllib.request.urlopen(REF_URL, timeout=60).read()
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))
    else:
        sys.exit(f'FAIL: could not fetch the reference wheel: {errors}')
    digest = hashlib.sha256(data).hexdigest()
    if digest != REF_SHA256:
        sys.exit(f'FAIL: reference wheel sha256 {digest} != pinned {REF_SHA256}')
    out = os.path.join(dest, os.path.basename(REF_URL))
    with open(out, 'wb') as fh:
        fh.write(data)
    return out


def parse_metadata(raw: bytes):
    """Return (multimap of header -> list of values, description body)."""
    msg = email.parser.BytesParser(policy=email.policy.compat32).parsebytes(raw)
    fields: dict[str, list[str]] = {}
    for key, value in msg.items():
        fields.setdefault(key, []).append(str(value).strip())
    if 'Description' in fields:  # body carried as a header would dodge the body check
        fail('METADATA', 'carries a Description header')
    body = msg.get_payload()
    if not isinstance(body, str):
        sys.exit('FAIL: METADATA body is not a single text payload')
    return fields, body


def one(fields: dict, key: str, where: str):
    vals = fields.get(key, [])
    if len(vals) != 1:
        fail(where, f'{key} appears {len(vals)} times, expected once')
        return None
    return vals[0]


def requirements(values: list[str], where: str) -> set:
    out = set()
    for v in values:
        try:
            r = Requirement(v)
        except Exception as exc:  # noqa: BLE001
            fail(where, f'unparsable Requires-Dist {v!r}: {exc}')
            continue
        out.add((canonicalize_name(r.name), frozenset(r.extras), SpecifierSet(str(r.specifier)),
                 str(r.marker) if r.marker else '', r.url or ''))
    if len(out) != len(values):
        fail(where, f'Requires-Dist has duplicates: {values}')
    return out


def check_wheel(path: str, ref: dict, version: str, tree: str) -> None:
    where = os.path.basename(path) + f' [{os.path.basename(os.path.dirname(path))}]'
    if os.path.basename(path) != f'cmdkit-{version}-py3-none-any.whl':
        fail(where, f'wheel file name is not cmdkit-{version}-py3-none-any.whl')
    distinfo = f'cmdkit-{version}.dist-info'
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if not n.endswith('/')]
        if len(names) != len(set(names)):
            fail(where, 'duplicate archive members')
        files = {n: zf.read(n) for n in names}
    # --- the file list --------------------------------------------------------------------
    pkg = {n for n in files if n.startswith('cmdkit/')}
    if pkg != ref['pkg_files']:
        fail(where, f'files under cmdkit/ differ from 2.7.7: added {sorted(pkg - ref["pkg_files"])}, '
                    f'missing {sorted(ref["pkg_files"] - pkg)}')
    if pkg != R1_MODULES:
        fail(where, f'files under cmdkit/ are not the ten modules and py.typed: {sorted(pkg ^ R1_MODULES)}')
    for n in sorted(pkg & R1_MODULES):
        src = os.path.join(tree, 'src', *n.split('/'))
        if not os.path.isfile(src) or open(src, 'rb').read() != files[n]:
            fail(where, f'{n} is not byte-identical to src/{n}')
    other = {n for n in files if not n.startswith('cmdkit/') and not n.startswith(distinfo + '/')}
    if other:
        fail(where, f'files outside cmdkit/ and {distinfo}/: {sorted(other)}')
    meta_files = {n[len(distinfo) + 1:] for n in files if n.startswith(distinfo + '/')}
    lic_files = {n for n in meta_files if n.startswith('licenses/')}
    if meta_files - lic_files != {'METADATA', 'WHEEL', 'RECORD'}:
        fail(where, f'{distinfo}/ holds {sorted(meta_files - lic_files)}, expected METADATA, WHEEL, RECORD')
    wheel = files.get(f'{distinfo}/WHEEL', b'').decode()
    if 'Tag: py3-none-any' not in wheel.splitlines() or 'Root-Is-Purelib: true' not in wheel.splitlines():
        fail(where, 'WHEEL is not a pure py3-none-any wheel')
    if [l for l in wheel.splitlines() if l.startswith('Tag:')] != ['Tag: py3-none-any']:
        fail(where, 'WHEEL carries a tag other than py3-none-any')
    # --- METADATA, field by field -------------------------------------------------------
    check_metadata(files.get(f'{distinfo}/METADATA', b''), where, ref, version,
                   {n[len('licenses/'):]: files[f'{distinfo}/{n}'] for n in lic_files})


def check_metadata(raw: bytes, where: str, ref: dict, version: str, licences: dict) -> None:
    """R2's field-by-field comparison; `licences` maps each shipped licence file to its bytes."""
    new, body = parse_metadata(raw)
    old = ref['fields']
    # 1. Version
    if one(new, 'Version', where) != version:
        fail(where, f'Version is not {version}')
    # 2. Python version classifiers: every minor from 3.9 to 3.14, nothing else changed
    new_cls = set(new.get('Classifier', []))
    old_cls = set(old.get('Classifier', []))
    if len(new_cls) != len(new.get('Classifier', [])):
        fail(where, 'duplicate Classifier')
    py_new = {c for c in new_cls if PY_CLASSIFIER.match(c)}
    want_py = {f'Programming Language :: Python :: {m}' for m in PY_MINORS}
    if py_new != want_py:
        fail(where, f'Python minor classifiers differ from 3.9-3.14: {sorted(py_new ^ want_py)}')
    rest_new = new_cls - py_new
    rest_old = {c for c in old_cls if not PY_CLASSIFIER.match(c)}
    if rest_new != rest_old:
        # 5. the licence classifier may go only if the backend refuses it; uv_build does not
        fail(where, f'other classifiers differ: added {sorted(rest_new - rest_old)}, '
                    f'removed {sorted(rest_old - rest_new)}')
    # 3. Metadata-Version may change (encoding); it must be present once
    one(new, 'Metadata-Version', where)
    # 3. Home-page carried as a Project-URL instead
    home = one(old, 'Home-page', 'reference')
    if 'Home-page' in new:
        fail(where, 'carries Home-page; PEP 621 metadata moves it to Project-URL')
    old_urls = set(old.get('Project-URL', []))
    new_urls = new.get('Project-URL', [])
    if len(set(new_urls)) != len(new_urls):
        fail(where, 'duplicate Project-URL')
    added = set(new_urls) - old_urls
    if not old_urls <= set(new_urls):
        fail(where, f'Project-URL lost {sorted(old_urls - set(new_urls))}')
    if len(added) != 1 or not next(iter(added)).endswith(', ' + home) \
            or next(iter(added)).split(',', 1)[0].strip().lower().replace('-', '') not in {'homepage', 'home'}:
        fail(where, f'Project-URL additions must be exactly the home page {home!r}: {sorted(added)}')
    # 3. Author and Author-email combined into one Author-email
    if new.get('Author-email') != [AUTHOR_EMAIL]:
        fail(where, f'Author-email is {new.get("Author-email")}, expected [{AUTHOR_EMAIL!r}]')
    if 'Author' in new and new['Author'] != old.get('Author'):
        fail(where, f'Author {new["Author"]} differs from 2.7.7 {old.get("Author")}')
    for key in ('Maintainer', 'Maintainer-email'):
        if new.get(key) != old.get(key):
            fail(where, f'{key} differs')
    # 4. the licence, PEP 639 encoding
    if 'License' in new:
        fail(where, 'carries License beside the PEP 639 encoding')
    if one(old, 'License', 'reference') != LICENSE_EXPRESSION:
        fail('reference', 'License is not Apache-2.0')
    if new.get('License-Expression') != [LICENSE_EXPRESSION]:
        fail(where, f'License-Expression is {new.get("License-Expression")}, expected [{LICENSE_EXPRESSION!r}]')
    declared = set(new.get('License-File', []))
    if not declared or declared != set(licences):
        fail(where, f'License-File {sorted(declared)} does not match the licence files shipped {sorted(licences)}')
    for n, data in licences.items():
        if data != ref['license']:
            fail(where, f'{n} is not the 2.7.7 licence text')
    if not licences:
        fail(where, 'no licence text shipped')
    # Requirements and the Python floor
    new_req = requirements(new.get('Requires-Dist', []), where)
    if new_req != ref['requires']:
        fail(where, f'Requires-Dist differs from 2.7.7: {sorted(map(str, new_req ^ ref["requires"]))}')
    r1 = {(n, frozenset(), s, m, '') for n, s, m in R1_REQUIRES}
    if new_req != r1:
        fail(where, f'Requires-Dist is not R1\'s three extra-only requirements: {sorted(map(str, new_req ^ r1))}')
    rp = one(new, 'Requires-Python', where)
    if rp is not None and SpecifierSet(rp) != R1_REQUIRES_PYTHON:
        fail(where, f'Requires-Python {rp!r} is not >=3.9,<4.0')
    if SpecifierSet(one(old, 'Requires-Python', 'reference')) != R1_REQUIRES_PYTHON:
        fail('reference', 'Requires-Python is not >=3.9,<4.0')
    extras = {canonicalize_name(e) for e in new.get('Provides-Extra', [])}
    if extras != {canonicalize_name(e) for e in old.get('Provides-Extra', [])} or extras != R1_EXTRAS \
            or len(new.get('Provides-Extra', [])) != len(R1_EXTRAS):
        fail(where, f'Provides-Extra is {new.get("Provides-Extra")}, expected toml and yaml')
    # Every other field: the same value, repeated fields as sets
    for key in sorted((set(new) | set(old)) - HANDLED):
        if set(new.get(key, [])) != set(old.get(key, [])) or \
                len(new.get(key, [])) != len(set(new.get(key, []))):
            fail(where, f'{key} differs: 2.7.7 {old.get(key)} vs built {new.get(key)}')
    # The description: the same text; only the serializer's trailing newlines may differ
    if body.rstrip('\n') != ref['body'].rstrip('\n'):
        fail(where, 'description body differs from 2.7.7')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--rev', default='HEAD')
    args = ap.parse_args()
    root = run(['git', 'rev-parse', '--show-toplevel'], os.getcwd(), dict(os.environ)).strip()
    env = dict(os.environ)  # a saved copy, never a cleared one
    for key in ('UV_PROJECT_ENVIRONMENT', 'VIRTUAL_ENV', 'UV_PYTHON'):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='wheel-surface-') as tmp:
        tree = os.path.join(tmp, 'tree')
        os.mkdir(tree)
        archive = subprocess.run(['git', 'archive', '--format=tar', args.rev], cwd=root,
                                 capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            tf.extractall(tree, filter='data')
        with open(os.path.join(tree, 'pyproject.toml'), 'rb') as fh:
            version = tomllib.load(fh)['project']['version']
        Version(version)  # valid PEP 440
        # the reference
        ref_path = fetch_reference(tmp)
        with zipfile.ZipFile(ref_path) as zf:
            fields, body = parse_metadata(zf.read(f'{REF_DISTINFO}/METADATA'))
            ref = {
                'fields': fields, 'body': body,
                'pkg_files': {n for n in zf.namelist() if n.startswith('cmdkit/') and not n.endswith('/')},
                'license': zf.read(f'{REF_DISTINFO}/LICENSE'),
            }
        ref['requires'] = requirements(fields.get('Requires-Dist', []), 'reference')
        if ref['pkg_files'] != R1_MODULES:
            fail('reference', 'the 2.7.7 wheel does not hold the ten modules and py.typed')
        # R1: `uv build` at the root makes exactly one sdist and one wheel
        out_root = os.path.join(tmp, 'root')
        run(['uv', 'build', '--no-build-logs', '--out-dir', out_root], tree, env)
        # uv writes a .gitignore into the output directory; distributions are the rest
        built = sorted(f for f in os.listdir(out_root) if f != '.gitignore')
        sdists = [f for f in built if f.endswith('.tar.gz')]
        wheels = [f for f in built if f.endswith('.whl')]
        if sorted(sdists + wheels) != built or len(sdists) != 1 or len(wheels) != 1:
            fail('uv build', f'expected one sdist and one wheel, got {built}')
            print('\n'.join(f'FAIL: {f}' for f in FAILURES))
            return 1
        if sdists[0] != f'cmdkit-{version}.tar.gz':
            fail('uv build', f'sdist name {sdists[0]}')
        sdist = os.path.join(out_root, sdists[0])
        with tarfile.open(sdist) as tf:
            top = f'cmdkit-{version}/'
            members = {m.name: m for m in tf.getmembers() if m.isfile()}
            pkg_info = tf.extractfile(members[top + 'PKG-INFO']).read() if top + 'PKG-INFO' in members else b''
            meta = email.parser.BytesParser(policy=email.policy.compat32).parsebytes(pkg_info)
            licences = {f: tf.extractfile(members[top + f]).read() for f in meta.get_all('License-File') or []
                        if top + f in members}
        if not pkg_info:
            fail('sdist', 'no PKG-INFO')
        else:
            check_metadata(pkg_info, sdists[0] + ' PKG-INFO', ref, version, licences)
        # a wheel straight from the tree, and one from the sdist file by path
        out_tree = os.path.join(tmp, 'tree-wheel')
        run(['uv', 'build', '--no-build-logs', '--wheel', '--out-dir', out_tree], tree, env)
        out_sdist = os.path.join(tmp, 'sdist-wheel')
        run(['uv', 'build', '--no-build-logs', '--wheel', '--out-dir', out_sdist, sdist], tmp, env)
        for d in (out_root, out_tree, out_sdist):
            ws = [f for f in os.listdir(d) if f.endswith('.whl')]
            if len(ws) != 1:
                fail(d, f'expected one wheel, got {ws}')
                continue
            check_wheel(os.path.join(d, ws[0]), ref, version, tree)
        # R10: installed from the built wheel, __version__ is the pyproject version
        wheel = os.path.join(out_root, wheels[0])
        probe = ('import importlib, cmdkit; '
                 '[importlib.import_module(m) for m in ("cmdkit.ansi", "cmdkit.app", "cmdkit.cli", '
                 '"cmdkit.config", "cmdkit.logging", "cmdkit.namespace", "cmdkit.platform", '
                 '"cmdkit.contrib.builder")]; print(cmdkit.__version__, cmdkit.__file__)')
        out = run(['uv', 'run', '--isolated', '--no-project', '--with', wheel, 'python', '-I', '-c', probe],
                  tmp, env).split()
        if len(out) != 2 or out[0] != version:
            fail('install', f'cmdkit.__version__ is {out[:1]}, expected {version}')
        elif os.path.realpath(out[1]).startswith(os.path.realpath(tree)):
            fail('install', 'imported cmdkit from the source tree, not the wheel')
    if FAILURES:
        print('\n'.join(f'FAIL: {f}' for f in FAILURES))
        return 1
    print(f'ok wheel_surface: cmdkit {version}, 3 wheels and the sdist PKG-INFO match 2.7.7 within R2')
    return 0


if __name__ == '__main__':
    sys.exit(main())
