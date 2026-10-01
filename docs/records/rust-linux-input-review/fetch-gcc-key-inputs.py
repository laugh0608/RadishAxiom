#!/usr/bin/env python3
"""Fixed GCC identity page and full-fingerprint public key requests; explicit execution only."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fetch', HERE / 'fetch-mpc-mpfr-inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
DIRECTORY = HERE.parents[2] / '.tmp/gcc-key-content-50ef87c-20260925'
PRIMARY = '7F74F97C103468EE5D750B583AB00996FC26A641'
TARGETS = {
    'identity': {'url': 'https://gcc.gnu.org/mirrors.html', 'suffix': 'html', 'limit': 262144},
    'public-key': {'url': 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x' + PRIMARY,
                   'suffix': 'asc', 'limit': 262144},
}


def plan():
    return {'directory': str(DIRECTORY), 'targets': TARGETS, 'expected_primary': PRIMARY,
            'method': fetch.identity((HERE / 'fetch-mpc-mpfr-inputs.py').read_bytes()),
            'routing_method': fetch.identity(Path(__file__).read_bytes()), 'executed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if not args.execute_authorized:
        print(json.dumps(plan(), sort_keys=True, indent=2))
    else:
        if json.loads((DIRECTORY / 'fetch-plan.json').read_bytes()) != plan():
            raise ValueError('reviewed fetch plan drift')
        fetch.DIRECTORY, fetch.TARGETS = DIRECTORY, TARGETS
        results = [fetch.fetch(name, 1) for name in TARGETS]
        raise SystemExit(max(results))
