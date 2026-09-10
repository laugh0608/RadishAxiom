#!/usr/bin/env python3
"""Preflight the retained patch paths before any system patch invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import re

PATCHES = {
    '0001-cve-2025-26519-p1.diff': '89ec5af152afb9c0ba8e37ecdca63a7a7fd13b60247f1a2d8024a59baa18e7dc',
    '0002-cve-2025-26519-p2.diff': 'd5b88fe87f9554238bdd69235694b0d50bb909f38149a7be417a0240a490e813',
    '0003-cve-2026-6042.diff': '444fa70e52ca158fb7d4bad560637790bbf8f72e80b82fff840dd66fa83091e3',
    '0004-cve-2026-40200.diff': '1ee29f64f9ca8e8ad7c349779d661ff6b52126a27575d3586981357a52c406fb',
}
ALLOWED = {'src/locale/iconv.c', 'src/locale/gb18030utf.h', 'src/stdlib/qsort.c'}


def path_from_header(line):
    fields = line[4:].split()
    if len(fields) != 1:
        raise ValueError('unexpected patch path header fields')
    raw = fields[0]
    if raw == '/dev/null':
        return None
    parts = raw.split('/')
    if parts[0] not in {'a', 'b'} or any(p in {'', '.', '..'} for p in parts):
        raise ValueError('unsafe patch path')
    path = '/'.join(parts[1:])
    if path not in ALLOWED:
        raise ValueError('patch destination outside allowlist')
    return path


def inspect(data):
    if len(data) > 16384:
        raise ValueError('patch byte limit')
    text = data.decode('utf-8')
    paths, hunks = [], 0
    indexes, commits = [], []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if match := re.match(r'^>?From ([0-9a-f]{40}) ', line):
            commits.append(match[1])
        if match := re.match(r'^index ([0-9a-f]+)\.\.([0-9a-f]+)(?: |$)', line):
            indexes.append({'before': match[1], 'after': match[2]})
        if line.startswith('--- '):
            if i+1 >= len(lines) or not lines[i+1].startswith('+++ '):
                raise ValueError('unpaired patch headers')
            old, new = path_from_header(line), path_from_header(lines[i+1])
            if new is None or (old is not None and old != new):
                raise ValueError('unexpected deletion or rename')
            paths.append(new)
        if line.startswith('@@'):
            if not re.match(r'^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@', line):
                raise ValueError('invalid unified hunk header')
            hunks += 1
    if not paths or not hunks:
        raise ValueError('missing file diff or hunk')
    return {'destinations': sorted(set(paths)), 'file_diffs': len(paths), 'hunks': hunks,
            'embedded_commit_headers': commits, 'index_headers': indexes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    args = parser.parse_args()
    base = args.inputs
    result = []
    for name, expected in PATCHES.items():
        data = (base / 'patches' / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('retained patch digest mismatch')
        result.append({'file': name, 'sha256': expected, **inspect(data)})
    print(json.dumps(result, sort_keys=True, indent=2))
