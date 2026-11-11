"""Self-test for ci_evidence.py: fixture runs it must pass, and broken ones it must fail.

Each case writes GitHub-shaped fixtures (pr.json, runs.json, run.json, log-<id>.txt, in the
shapes `gh` returns them) into a fresh temporary directory and runs ci_evidence.py with
`--fixture DIR --sha SHA`. No network, no git writes.

    uv run --isolated --no-project --python 3.14 python -I spec/uv-build-and-ci/verify/ci_evidence_selftest.py

Footprint: one python process at a time; seconds.
"""

# standard libs
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHA = 'a' * 40
LINUX = ['3.9', '3.10', '3.11', '3.12', '3.13', '3.14']
JOBS = [('ubuntu-latest', v) for v in LINUX] + [
    (o, v) for o in ('macos-latest', 'windows-latest') for v in ('3.9', '3.14')]
PLAT = {'ubuntu-latest': 'linux', 'macos-latest': 'darwin', 'windows-latest': 'win32'}


def log(name: str, plat: str, py: str, summary: str) -> str:
    return (f'{name}\tTest with pytest\t2026-11-11T01:47:45.86Z platform {plat} -- Python {py}.7, pytest-7.4.4\n'
            f'{name}\tTest with pytest\t2026-11-11T01:47:46.50Z \x1b[32m===== {summary} in 1.30s =====\x1b[0m\n')


def base():
    jobs, logs = [], {}
    for i, (o, v) in enumerate(JOBS):
        name = f'{o} / py{v}'
        jobs.append({'name': name, 'conclusion': 'success', 'databaseId': 100 + i})
        logs[100 + i] = log(name, PLAT[o], v, '75 passed')
    return {
        'pr': [{'number': 30, 'headRefOid': SHA, 'baseRefName': 'develop', 'isDraft': True}],
        'runs': [{'databaseId': 9, 'headSha': SHA, 'status': 'completed', 'conclusion': 'success',
                  'event': 'pull_request', 'attempt': 1, 'createdAt': '2026-11-11T01:47:32Z'}],
        'run': {'jobs': jobs, 'headSha': SHA, 'conclusion': 'success', 'attempt': 1},
        'logs': logs,
        'xfail': [],
    }


def mutate(fn):
    d = base()
    fn(d)
    return d


def job(d, name):
    return next(j for j in d['run']['jobs'] if j['name'] == name)


def set_log(d, name, text):
    d['logs'][job(d, name)['databaseId']] = text


CASES = [
    ('all green, all graded', 'all', base(), 0),
    ('all green, linux graded', 'linux', base(), 0),
    ('windows xfails traced to a win32 decorator', 'all', mutate(lambda d: [d.update(xfail=['win32'])] + [set_log(d, f'windows-latest / py{v}', log(f'windows-latest / py{v}', 'win32', v, '73 passed, 2 xfailed')) for v in ('3.9', '3.14')]), 0),
    ('windows xfails with no win32 decorator', 'all', mutate(lambda d: [set_log(d, f'windows-latest / py{v}', log(f'windows-latest / py{v}', 'win32', v, '73 passed, 2 xfailed')) for v in ('3.9', '3.14')]), 1),
    ('linux xfail', 'all', mutate(lambda d: [d.update(xfail=['win32', 'linux'])] + [set_log(d, 'ubuntu-latest / py3.12', log('u', 'linux', '3.12', '74 passed, 1 xfailed'))]), 1),
    ('every job ran one test (uniform hiding)', 'all', mutate(lambda d: [set_log(d, f'{o} / py{v}', log(f'{o} / py{v}', PLAT[o], v, '1 passed')) for o, v in JOBS]), 1),
    ('mac collection error, linux graded', 'linux', mutate(lambda d: [job(d, 'macos-latest / py3.9').update(conclusion='failure'), set_log(d, 'macos-latest / py3.9', log('m', 'darwin', '3.9', '1 error'))]), 0),
    ('windows died before pytest, linux graded', 'linux', mutate(lambda d: [job(d, 'windows-latest / py3.14').update(conclusion='failure'), set_log(d, 'windows-latest / py3.14', 'error: uv failed\n')]), 0),
    ('windows died before pytest, all graded', 'all', mutate(lambda d: [job(d, 'windows-latest / py3.14').update(conclusion='failure'), set_log(d, 'windows-latest / py3.14', 'error: uv failed\n')]), 1),
    ('mac job failed, all graded', 'all', mutate(lambda d: job(d, 'macos-latest / py3.9').update(conclusion='failure')), 1),
    ('mac job failed, linux graded', 'linux', mutate(lambda d: job(d, 'macos-latest / py3.9').update(conclusion='failure')), 0),
    ('linux job failed, linux graded', 'linux', mutate(lambda d: job(d, 'ubuntu-latest / py3.12').update(conclusion='failure')), 1),
    ('a job missing', 'all', mutate(lambda d: d['run']['jobs'].pop()), 1),
    ('an extra job', 'all', mutate(lambda d: d['run']['jobs'].append({'name': 'ubuntu-latest / py3.15', 'conclusion': 'success', 'databaseId': 999}) or d['logs'].update({999: log('x', 'linux', '3.15', '75 passed')})), 1),
    ('log shows another python', 'all', mutate(lambda d: set_log(d, 'windows-latest / py3.9', log('w', 'win32', '3.14', '75 passed'))), 1),
    ('log shows another platform', 'all', mutate(lambda d: set_log(d, 'macos-latest / py3.14', log('m', 'linux', '3.14', '75 passed'))), 1),
    ('success but failures in summary', 'all', mutate(lambda d: set_log(d, 'ubuntu-latest / py3.9', log('u', 'linux', '3.9', '74 passed, 1 failed'))), 1),
    ('skips in summary', 'all', mutate(lambda d: set_log(d, 'windows-latest / py3.14', log('w', 'win32', '3.14', '70 passed, 5 skipped'))), 1),
    ('no summary line', 'all', mutate(lambda d: set_log(d, 'ubuntu-latest / py3.10', 'platform linux -- Python 3.10.1\n')), 1),
    ('fewer tests collected on one job', 'all', mutate(lambda d: set_log(d, 'ubuntu-latest / py3.11', log('u', 'linux', '3.11', '60 passed'))), 1),
    ('run still in progress', 'all', mutate(lambda d: d['runs'][0].update(status='in_progress')), 1),
    ('run on another commit', 'all', mutate(lambda d: d['run'].update(headSha='b' * 40)), 1),
    ('no run for the commit', 'all', mutate(lambda d: d['runs'][0].update(headSha='b' * 40)), 1),
    ('PR head is another commit', 'all', mutate(lambda d: d['pr'][0].update(headRefOid='b' * 40)), 1),
    ('no open PR', 'all', mutate(lambda d: d.update(pr=[])), 1),
    ('run from a push, not the PR', 'all', mutate(lambda d: d['runs'][0].update(event='push')), 1),
]


def main() -> int:
    bad = []
    for label, require, data, want in CASES:
        with tempfile.TemporaryDirectory(prefix='ci-evidence-selftest-') as tmp:
            for key in ('pr', 'runs', 'run', 'xfail'):
                with open(os.path.join(tmp, f'{key}.json'), 'w') as fh:
                    json.dump(data[key], fh)
            for jid, text in data['logs'].items():
                with open(os.path.join(tmp, f'log-{jid}.txt'), 'w') as fh:
                    fh.write(text)
            proc = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'ci_evidence.py'), '--require', require,
                                   '--sha', SHA, '--fixture', tmp, '--expect-count', '75'], capture_output=True, text=True)
        got = 0 if proc.returncode == 0 else 1
        print(f'{"ok  " if got == want else "BAD "} {label}: exit {proc.returncode}, expected {"pass" if want == 0 else "fail"}')
        if got != want or (proc.returncode not in (0, 1)):
            bad.append(label)
            print(proc.stdout[-800:], proc.stderr[-800:])
    if bad:
        print(f'FAIL: {len(bad)} self-test case(s): {bad}')
        return 1
    print(f'ok ci_evidence_selftest: {len(CASES)} cases')
    return 0


if __name__ == '__main__':
    sys.exit(main())
