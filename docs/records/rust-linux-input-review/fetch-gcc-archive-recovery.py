#!/usr/bin/env python3
"""One separately authorized 180-second GCC archive recovery; preserve the failed first request."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fetch', HERE / 'fetch-mpc-mpfr-inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
DIRECTORY = HERE.parents[2] / '.tmp/gcc-inputs-dac0405-20260925'
TARGET = {'url': 'https://gcc.gnu.org/pub/gcc/releases/gcc-9.4.0/gcc-9.4.0.tar.xz',
          'limit': 100663296, 'suffix': 'tar.xz'}


def execute():
    if DIRECTORY.resolve() != DIRECTORY.absolute() or not DIRECTORY.is_dir():
        raise ValueError('missing or symlink task directory')
    first = json.loads((DIRECTORY / 'gcc-attempt-1.json').read_bytes())
    if (first['url'] != TARGET['url'] or first['exit_code'] != 28 or first['passed'] is not False or
            first['body']['file'] != 'gcc-attempt-1.tar.xz' or
            fetch.identity((DIRECTORY / first['body']['file']).read_bytes()) !=
            {k: first['body'][k] for k in ('bytes', 'sha256')}):
        raise ValueError('first timeout record or partial bytes changed')
    paths = {suffix: DIRECTORY / ('gcc-attempt-2.' + suffix) for suffix in ('json', 'stdout', 'stderr', 'tar.xz')}
    if any(p.exists() or p.is_symlink() for p in paths.values()):
        raise ValueError('refuse overwrite of recovery request')
    for suffix in ('json', 'tar.xz'):
        with paths[suffix].open('xb'):
            pass
    argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
            '--max-time', '180', '--max-filesize', str(TARGET['limit']), '--output', str(paths['tar.xz']),
            '--write-out', '%{http_code}\n', TARGET['url']]
    started, timeout = datetime.now(timezone.utc).isoformat(), False
    with paths['stdout'].open('xb') as out, paths['stderr'].open('xb') as err:
        try:
            code = subprocess.run(argv, stdout=out, stderr=err, timeout=185).returncode
        except subprocess.TimeoutExpired:
            code, timeout = None, True
    body, out, err = (paths[suffix].read_bytes() for suffix in ('tar.xz', 'stdout', 'stderr'))
    http = out.decode('ascii').strip()
    passed = code == 0 and not timeout and http == '200' and 0 < len(body) <= TARGET['limit']
    record = {'kind': 'diagnostic-gcc-archive-recovery-v1', 'target': 'gcc', 'attempt': 2,
              'url': TARGET['url'], 'argv': argv, 'started_at': started,
              'finished_at': datetime.now(timezone.utc).isoformat(),
              'method': fetch.identity(Path(__file__).read_bytes()),
              'curl': fetch.identity(Path('/usr/bin/curl').read_bytes()),
              'first_timeout_record': fetch.identity((DIRECTORY / 'gcc-attempt-1.json').read_bytes()),
              'exit_code': code, 'parent_timeout': timeout, 'http_code': http,
              'body': {'file': paths['tar.xz'].name, **fetch.identity(body)},
              'stdout': {**fetch.identity(out), 'text': out.decode('ascii')},
              'stderr': {**fetch.identity(err), 'text': err.decode('utf-8')},
              'passed': passed, 'transport_passed': passed, 'source_acceptance': 'not-assessed'}
    paths['json'].write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    print(json.dumps(record, sort_keys=True, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized:
        raise SystemExit(execute())
    print(json.dumps({'target': TARGET, 'directory': str(DIRECTORY), 'request_timeout': 180,
                      'parent_timeout': 185, 'executed': False}, sort_keys=True, indent=2))
