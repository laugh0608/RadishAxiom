#!/usr/bin/env python3
"""Two separately reviewed headers inputs; one request each, no redirects, retry or execution."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fetch', HERE / 'fetch-mpc-mpfr-inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
DIRECTORY = HERE.parents[2] / '.tmp/linux-headers-inputs-38edae0-20260925'
TARGETS = {
    'headers': {'url': 'https://ci-mirrors.rust-lang.org/rustc/sabotage-linux-tarballs/linux-headers-4.19.88.tar.xz',
                'suffix': 'tar.xz', 'limit': 4194304},
    'tags': {'url': 'https://api.github.com/repos/sabotage-linux/kernel-headers/tags?per_page=100',
             'suffix': 'json.body', 'limit': 262144},
}


def plan():
    return {'directory': str(DIRECTORY), 'targets': TARGETS,
            'method': fetch.identity((HERE / 'fetch-mpc-mpfr-inputs.py').read_bytes()),
            'routing_method': fetch.identity(Path(__file__).read_bytes()), 'executed': False,
            'scope': 'fixed Rust mirror artifact and first page of upstream tag metadata; no tag authentication'}


def execute():
    if json.loads((DIRECTORY / 'fetch-plan.json').read_bytes()) != plan():
        raise ValueError('reviewed fetch plan drift')
    fetch.DIRECTORY, fetch.TARGETS = DIRECTORY, TARGETS
    # Independent artifact and metadata requests: preserve failures for both,
    # without deriving or following any URL returned by the remote API.
    return max(fetch.fetch(name, 1) for name in TARGETS)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized:
        raise SystemExit(execute())
    print(json.dumps(plan(), sort_keys=True, indent=2))
