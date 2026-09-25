#!/usr/bin/env python3
"""One fixed upstream commit archive for comparison; not a substitute for the Rust mirror artifact."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('route', HERE / 'fetch-linux-headers-inputs.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)
COMMIT = 'fefadd9e4e093f776cd14ee3685a80eb4ca000f4'
TARGET = {'url': 'https://codeload.github.com/sabotage-linux/kernel-headers/tar.gz/' + COMMIT,
          'suffix': 'tar.gz', 'limit': 4194304}
TAGS = {'bytes': 9809, 'sha256': '188e3bc305d86b6d42db63ba0d2da1aa43b78f43494a40e0e5c01ece76b636bd'}


def plan():
    return {'directory': str(route.DIRECTORY), 'target': TARGET, 'commit': COMMIT, 'tag': 'v4.19.88',
            'tags_input': TAGS, 'method': route.plan()['method'],
            'routing_method': route.fetch.identity(Path(__file__).read_bytes()), 'executed': False}


def execute():
    raw = (route.DIRECTORY / 'tags-attempt-1.json.body').read_bytes()
    if route.fetch.identity(raw) != TAGS:
        raise ValueError('tag metadata drift')
    selected = [row for row in json.loads(raw) if row['name'] == 'v4.19.88']
    if len(selected) != 1 or selected[0]['commit']['sha'] != COMMIT:
        raise ValueError('exact tag-to-commit declaration drift')
    if json.loads((route.DIRECTORY / 'candidate-plan.json').read_bytes()) != plan():
        raise ValueError('reviewed candidate plan drift')
    route.fetch.DIRECTORY, route.fetch.TARGETS = route.DIRECTORY, {'candidate': TARGET}
    return route.fetch.fetch('candidate', 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized:
        raise SystemExit(execute())
    print(json.dumps(plan(), sort_keys=True, indent=2))
