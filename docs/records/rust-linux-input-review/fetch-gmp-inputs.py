#!/usr/bin/env python3
"""Five fixed GMP source-review requests; explicit authorization, no fallback or automatic retry."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fetch', HERE / 'fetch-mpc-mpfr-inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
DIRECTORY = HERE.parents[2] / '.tmp/gmp-inputs-50ef87c-20260925'
PRIMARY = '343C2FF0FBEE5EC2EDBEF399F3599FF828C67298'
BASE = 'https://gmplib.org/download/gmp/'
TARGETS = {
    'identity': {'url': 'https://gmplib.org/index', 'suffix': 'html', 'limit': 262144},
    'announcement': {'url': 'https://gmplib.org/list-archives/gmp-announce/2023-July/000050.html',
                     'suffix': 'html', 'limit': 262144},
    'gmp': {'url': BASE + 'gmp-6.3.0.tar.xz', 'suffix': 'tar.xz', 'limit': 2094196},
    'signature': {'url': BASE + 'gmp-6.3.0.tar.xz.sig', 'suffix': 'sig', 'limit': 65536},
    'public-key': {'url': 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x' + PRIMARY,
                   'suffix': 'asc', 'limit': 262144},
}


def plan():
    return {'directory': str(DIRECTORY), 'targets': TARGETS, 'declared_release_key': PRIMARY,
            'method': fetch.identity((HERE / 'fetch-mpc-mpfr-inputs.py').read_bytes()),
            'routing_method': fetch.identity(Path(__file__).read_bytes()), 'executed': False}


def execute():
    if json.loads((DIRECTORY / 'fetch-plan.json').read_bytes()) != plan():
        raise ValueError('reviewed fetch plan drift')
    fetch.DIRECTORY, fetch.TARGETS = DIRECTORY, TARGETS
    for name in TARGETS:
        result = fetch.fetch(name, 1)
        if result:
            return result
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized:
        raise SystemExit(execute())
    print(json.dumps(plan(), sort_keys=True, indent=2))
