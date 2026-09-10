#!/usr/bin/env python3
"""Bounded read-only inventory; a requested commit is not Git authentication."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import platform
from pathlib import Path
import tarfile

COMMIT = '3635262e4524c991552789af6f36211a335a77b3'
TOP = 'musl-cross-make-' + COMMIT
SOURCE_BYTES = 213688
SOURCE_SHA = '60bed670d689d5c2164020960df36b80189dc5617e9763e023672f98a99d567e'
HERE = Path(__file__).resolve().parent
LIMITS = {'compressed': 4 * 1024**2, 'tar': 32 * 1024**2,
          'member': 8 * 1024**2, 'members': 4096}
method = HERE / 'inspect-archives.py'
spec = importlib.util.spec_from_file_location('retained_archive', method)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def inspect(path, expected_sha, include_text=False):
    with path.open('rb') as stream:
        compressed = stream.read(LIMITS['compressed'] + 1)
    if len(compressed) > LIMITS['compressed']:
        raise ValueError('compressed size limit')
    digest = hashlib.sha256(compressed).hexdigest()
    if digest != expected_sha:
        raise ValueError('archive digest mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(LIMITS['tar'] + 1)
    if len(raw) > LIMITS['tar']:
        raise ValueError('tar size limit')
    rows, seen = [], set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
        for member in tar:
            name = archive.path_name(member.name, TOP, member.isdir())
            if name in seen or len(seen) >= LIMITS['members']:
                raise ValueError('duplicate path or member limit')
            seen.add(name)
            if not (member.isfile() or member.isdir()):
                raise ValueError('linked or special member')
            if member.size < 0 or member.size > LIMITS['member']:
                raise ValueError('member size limit')
            if member.isdir():
                continue
            content = tar.extractfile(member).read()
            if len(content) != member.size:
                raise ValueError('truncated member')
            row = {'path': name[len(TOP)+1:], 'bytes': len(content),
                   'sha256': hashlib.sha256(content).hexdigest()}
            if include_text:
                row['text'] = content.decode('utf-8')
            rows.append(row)
        if any(raw[tar.offset:]):
            raise ValueError('nonzero tar tail')
        pax = tar.pax_headers
    if pax.get('comment') != COMMIT:
        raise ValueError('archive commit comment mismatch')
    return {'kind': 'diagnostic-observation', 'acceptance': 'not-assessed',
            'python': platform.python_version(), 'requested_commit': COMMIT, 'commit_authentication': 'not-assessed',
            'archive': {'file': path.name, 'bytes': len(compressed), 'sha256': digest,
                        'tar_bytes': len(raw), 'tar_sha256': hashlib.sha256(raw).hexdigest(),
                        'member_count': len(seen), 'pax_headers': pax},
            'limits': LIMITS, 'files': sorted(rows, key=lambda x: x['path']),
            'methods': {Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        method.name: hashlib.sha256(method.read_bytes()).hexdigest()}}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--include-text', action='store_true')
    args = parser.parse_args()
    if args.archive.stat().st_size != SOURCE_BYTES:
        raise ValueError('pinned archive size mismatch')
    print(json.dumps(inspect(args.archive, SOURCE_SHA, args.include_text), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
