#!/usr/bin/env python3
"""Prepare two fixed Git metadata requests; execute only with explicit current-task authorization."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('candidate', HERE / 'fetch-linux-headers-candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
fetch = candidate.route.fetch
DIRECTORY = HERE.parents[2] / '.tmp/linux-headers-git-metadata-84bd6f8-20260929'
BASE = 'https://api.github.com/repos/sabotage-linux/kernel-headers/git/'
TARGETS = {
    'tag-ref': {'url': BASE + 'ref/tags/v4.19.88', 'suffix': 'json.body', 'limit': 65536},
    'commit': {'url': BASE + 'commits/' + candidate.COMMIT, 'suffix': 'json.body', 'limit': 262144},
}


def plan():
    return {'kind': 'diagnostic-linux-headers-git-metadata-plan-v1', 'directory': str(DIRECTORY),
            'targets': TARGETS, 'commit': candidate.COMMIT, 'tag': 'v4.19.88',
            'previous_tags_input': candidate.TAGS,
            'method': fetch.identity((HERE / 'fetch-mpc-mpfr-inputs.py').read_bytes()),
            'routing_method': fetch.identity(Path(__file__).read_bytes()),
            'executed': False, 'requests': 2, 'attempts_per_target': 1,
            'curl_timeout_seconds': 60, 'parent_timeout_seconds_per_request': 65,
            'redirects': False, 'automatic_retry': False, 'credentials': False,
            'scope': 'GitHub ref/commit declarations only; returned URLs are never followed; no signature verification'}


def execute():
    if DIRECTORY.resolve() != DIRECTORY.absolute() or not DIRECTORY.is_dir():
        raise ValueError('missing or symlink task directory')
    if json.loads((DIRECTORY / 'fetch-plan.json').read_bytes()) != plan():
        raise ValueError('reviewed metadata plan drift')
    fetch.DIRECTORY, fetch.TARGETS = DIRECTORY, TARGETS
    return max(fetch.fetch(name, 1) for name in TARGETS)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized:
        raise SystemExit(execute())
    print(json.dumps(plan(), sort_keys=True, indent=2))
