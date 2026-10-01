#!/usr/bin/env python3
"""Fetch one of four explicitly authorized fixed source-review objects; never install or retry automatically."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
DIRECTORY = HERE.parents[2] / '.tmp/musl-remaining-source-fetch-aa13d7c-20260916'
TARGETS = {
    'mpc': {'url': 'https://www.multiprecision.org/downloads/mpc-1.3.1.tar.gz', 'limit': 773573,
            'suffix': 'tar.gz', 'sha256': 'ab642492f5cf882b74aa0cb730cd410a81edcdbec895183ce930e706c1c759b8',
            'recipe_sha1': 'bac1c1fa79f5602df1e29e4684e103ad55714e02'},
    'mpc-signature': {'url': 'https://www.multiprecision.org/downloads/mpc-1.3.1.tar.gz.sig',
                      'limit': 65536, 'suffix': 'sig'},
    'mpfr': {'url': 'https://www.mpfr.org/mpfr-4.2.2/mpfr-4.2.2.tar.xz', 'limit': 1505596,
             'suffix': 'tar.xz', 'sha256': 'b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01',
             'recipe_sha1': 'a63a264b273a652e27518443640e69567da498ce'},
    'mpfr-signature': {'url': 'https://www.mpfr.org/mpfr-4.2.2/mpfr-4.2.2.tar.xz.asc',
                       'limit': 65536, 'suffix': 'asc'},
}


def identity(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def fetch(name, attempt):
    if DIRECTORY.resolve() != DIRECTORY.absolute() or not DIRECTORY.is_dir():
        raise ValueError('missing or symlink task directory')
    target = TARGETS[name]
    stem = DIRECTORY / f'{name}-attempt-{attempt}'
    if attempt == 2:
        first = json.loads((DIRECTORY / f'{name}-attempt-1.json').read_bytes())
        if first['exit_code'] not in {5, 6, 7} or first['http_code'] != '000' or first['body']['bytes'] != 0:
            raise ValueError('second attempt only follows separately confirmed sandbox connection failure')
    paths = {suffix: Path(str(stem) + '.' + suffix) for suffix in ('json', 'stdout', 'stderr', target['suffix'])}
    if any(path.exists() or path.is_symlink() for path in paths.values()):
        raise ValueError('refuse overwrite of existing attempt')
    with paths['json'].open('x'):
        pass
    body = paths[target['suffix']]
    with body.open('xb'):
        pass
    argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https',
            '--tlsv1.2', '--max-time', '60', '--max-filesize', str(target['limit']),
            '--output', str(body), '--write-out', '%{http_code}\n', target['url']]
    started = datetime.now(timezone.utc).isoformat()
    timeout = False
    with paths['stdout'].open('xb') as stdout, paths['stderr'].open('xb') as stderr:
        try:
            result = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=65)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code, timeout = None, True
    content, out, err = body.read_bytes(), paths['stdout'].read_bytes(), paths['stderr'].read_bytes()
    http = out.decode('ascii', errors='strict').strip()
    transport = not timeout and code == 0 and http == '200' and 0 < len(content) <= target['limit']
    matches = None
    if 'sha256' in target:
        matches = (len(content) == target['limit'] and hashlib.sha256(content).hexdigest() == target['sha256']
                   and hashlib.sha1(content).hexdigest() == target['recipe_sha1'])
    observation = {'kind': 'diagnostic-mpc-mpfr-fetch-v1', 'target': name, 'attempt': attempt, 'argv': argv,
                   'url': target['url'], 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
                   'method': identity(Path(__file__).read_bytes()), 'curl': identity(Path('/usr/bin/curl').read_bytes()),
                   'exit_code': code, 'parent_timeout': timeout, 'http_code': http,
                   'body': {'file': body.name, **identity(content)},
                   'stdout': {**identity(out), 'text': out.decode('ascii')},
                   'stderr': {**identity(err), 'text': err.decode('utf-8', errors='strict')},
                   'transport_passed': transport, 'index_and_recipe_bytes_match': matches,
                   'passed': transport and matches is not False, 'source_acceptance': 'not-assessed'}
    paths['json'].write_text(json.dumps(observation, sort_keys=True, indent=2) + '\n')
    print(json.dumps({key: observation[key] for key in
                      ('target', 'attempt', 'exit_code', 'http_code', 'body', 'passed')}, indent=2))
    return 0 if observation['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=TARGETS)
    parser.add_argument('--attempt', type=int, choices=(1, 2), default=1)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized:
        if args.target is None:
            parser.error('--target is required for execution')
        raise SystemExit(fetch(args.target, args.attempt))
    print(json.dumps(TARGETS, sort_keys=True, indent=2))
