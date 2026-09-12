#!/usr/bin/env python3
"""Copy a reviewed file manifest to local content-addressed storage, then restore offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

LIMIT = 16 * 1024**2
TOTAL_LIMIT = 128 * 1024**2
RECORDS = 'docs/records/rust-linux-input-review/'
CACHE = '.tmp/musl-verifier-d04b225-20260912/'


def identity(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def require(value, message):
    if not value:
        raise ValueError(message)


def safe_path(value):
    require(isinstance(value, str) and 0 < len(value) <= 180 and
            re.fullmatch(r'[A-Za-z0-9_.+/-]+', value) is not None and
            all(part not in {'', '.', '..', '.git'} for part in value.split('/')), 'unsafe relative path')
    return value


def read_regular(path, limit=LIMIT):
    require(path.absolute() == path.resolve(strict=True), 'symlink in input path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'input type or size outside profile')
        data = stream.read(limit + 1)
    require(len(data) == info.st_size and len(data) <= limit, 'input changed or exceeded limit')
    return data


def manifest_rows(raw):
    require(len(raw) <= 1024**2, 'manifest too large')
    manifest = json.loads(raw)
    require(manifest['kind'] == 'diagnostic-musl-retention-manifest-v1', 'wrong manifest kind')
    rows = manifest['files']
    require(isinstance(rows, list) and 0 < len(rows) <= 512, 'manifest file count')
    seen, total = set(), 0
    for row in rows:
        path = safe_path(row['path'])
        require(path not in seen and type(row['bytes']) is int and 0 <= row['bytes'] <= LIMIT and
                re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is not None, 'duplicate path or invalid identity')
        seen.add(path)
        total += row['bytes']
    for path in seen:
        require(not any(str(p) in seen for p in Path(path).parents), 'file is ancestor of another file')
    require(total <= TOTAL_LIMIT, 'manifest cumulative limit')
    return sorted(rows, key=lambda row: row['path'])


def write_new(path, data):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def new_directory(path):
    require(path.absolute() == path.resolve(), 'symlink in destination path')
    path.mkdir(parents=True, exist_ok=False)


def pack(root, raw, destination):
    rows = manifest_rows(raw)
    blobs = {}
    # Check all original bytes before creating a retention directory.
    for row in rows:
        data = read_regular(root / row['path'])
        require(identity(data) == {k: row[k] for k in ('bytes', 'sha256')}, 'original identity mismatch')
        blobs[row['sha256']] = data
    new_directory(destination)
    objects = destination / 'objects'
    objects.mkdir()
    for digest, data in sorted(blobs.items()):
        write_new(objects / digest, data)
    sync_directory(objects)
    write_new(destination / 'manifest.json', raw)
    sync_directory(destination)
    return {'file_count': len(rows), 'object_count': len(blobs), 'object_bytes': sum(map(len, blobs.values())),
            'manifest': identity(raw), 'source_acceptance': 'not-assessed', 'off_device_backup_verified': False}


def restore(store, expected_manifest, destination):
    raw = read_regular(store / 'manifest.json', 1024**2)
    require(raw == expected_manifest, 'retained manifest differs from reviewed manifest')
    rows = manifest_rows(raw)
    expected_objects = {row['sha256'] for row in rows}
    require({p.name for p in (store / 'objects').iterdir()} == expected_objects, 'unexpected/missing objects')
    blobs = {digest: read_regular(store / 'objects' / digest) for digest in expected_objects}
    for row in rows:
        require(identity(blobs[row['sha256']]) == {k: row[k] for k in ('bytes', 'sha256')},
                'retained object identity mismatch')
    new_directory(destination)
    for row in rows:
        path = destination / row['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        write_new(path, blobs[row['sha256']])
    for row in rows:
        require(identity(read_regular(destination / row['path'])) == {k: row[k] for k in ('bytes', 'sha256')},
                'restored identity mismatch')
    return {'file_count': len(rows), 'object_count': len(blobs), 'manifest': identity(raw),
            'restored_bytes_match': True, 'source_acceptance': 'not-assessed',
            'off_device_backup_verified': False}


def plan(root):
    """Curated current inputs and replay dependencies; never sweep an entire cache."""
    rows = {}

    def add(path, role, expected=None):
        safe_path(path)
        actual = identity(read_regular(root / path))
        require(expected is None or actual == {k: expected[k] for k in ('bytes', 'sha256')},
                'declared source identity mismatch: ' + path)
        row = {'path': path, 'role': role, **actual}
        require(path not in rows or rows[path] == row, 'conflicting retention entry')
        rows[path] = row

    def record(name):
        add(RECORDS + name, 'replay-method-or-record')
        return json.loads(read_regular(root / RECORDS / name))

    for name in (
        'inspect-musl-verifier-content.py', 'inspect-musl-trust-inputs.py', 'inspect-selected-inputs.py',
        'inspect-musl-verifier-packages.py', 'inspect-musl-verifier-sources.py', 'inspect-musl-key-status.py',
        'inspect-musl-verifier-layout.py', 'inspect-musl-verifier-licenses.py',
        'retain-musl-verifier-inputs.py', 'check-musl-retention.py',
        'check-musl-verifier-content.py', 'check-musl-verifier-layout.py', 'check-musl-verifier-licenses.py',
        'musl-verifier-packages-2026-09-12.json', 'musl-verifier-content-2026-09-12.json.gz',
        'musl-verifier-content-summary-2026-09-12.json', 'musl-verifier-layout-2026-09-12.json.gz',
        'musl-verifier-layout-summary-2026-09-12.json', 'musl-verifier-licenses-2026-09-12.json',
        'musl-key-status-2026-09-10.json', 'musl-debian-execution-2026-09-10.json',
        'debian-trixie-archive-2026-09-10.asc', 'debian-trixie-release-2026-09-10.asc',
        'musl-debian-InRelease-2026-09-10', 'musl-debian-fetch-2026-09-10.json',
        'musl-key-status-execution-2026-09-10.json'):
        add(RECORDS + name, 'replay-method-or-record')
    add('scripts/inspect-debian-source-chain.py', 'replay-method-or-record')
    for name, method in (
        ('musl-verifier-package-fetch-2026-09-12.json', 'fetch-musl-verifier-packages.py'),
        ('musl-verifier-index-fetch-2026-09-12.json', 'fetch-musl-verifier-index.py'),
        ('musl-verifier-licenses-fetch-2026-09-12.json', 'fetch-musl-verifier-licenses.py')):
        data = record(name)
        observations = data['invocations'] if isinstance(data, dict) else data
        for observation in observations:
            path = Path(CACHE + observation['body']['file'])
            for suffix, key in [(path.suffix, 'body'), ('.stdout', 'stdout'), ('.stderr', 'stderr')]:
                add(str(path.with_suffix(suffix)), 'original-fetch-bytes', observation[key])
            add(str(path.with_suffix('.json')), 'original-fetch-log')
            require(identity(read_regular(root / CACHE / method))['sha256'] == observation['method_sha256'],
                    'fetch method drift')
        add(CACHE + method, 'original-fetch-method')
    sources = {'bytes': 10527804, 'sha256': 'e8bbadd8389119e841494630998187f961d7de4d5b1dcbeed4f792a1d423299f'}
    add('.tmp/musl-auth-chain-0a66901/Sources.xz', 'original-source-index', sources)
    upstream = record('musl-source-fetch-2026-09-10.json')
    for row in upstream['files']:
        add('.tmp/musl-source-review-c7f7f60/' + row['file'], 'original-musl-input', row)
    for path, size, digest in (
        ('.tmp/musl-trust-bbbe083-20260910/keys-attempt-2.html', 10718,
         'b271f4c351a3b54f6a6be9667bb834809d12ee514055b903ccb06839d274e3e0'),
        ('.tmp/musl-trust-bbbe083-20260910/keyring-attempt-2.deb', 178572,
         'f699e2f88dca05212f2a452b58475f2993cb6993dfbafb1d0205a3291eb8b4b8'),
        ('.tmp/musl-key-status-ef02b43-20260910/announcement-attempt-2.html', 29691,
         '5384b92ed7ad6cf8ce31afff8b5edf88fc0e997ef641c7c43bffc0660d92615d'),
        ('.tmp/musl-key-status-ef02b43-20260910/archive-attempt-2.asc', 11861,
         '6f1d277429dd7ffedcc6f8688a7ad9a458859b1139ffa026d1eeaadcbffb0da7'),
        ('.tmp/musl-key-status-ef02b43-20260910/release-attempt-2.asc', 1384,
         '4d097bb93f83d731f475c5b92a0c2fcf108cfce1d4932792fca72d00b48d198b')):
        add(path, 'original-debian-identity-input', {'bytes': size, 'sha256': digest})
    return {'kind': 'diagnostic-musl-retention-manifest-v1', 'repository_base': '2fb2e70',
            'files': [rows[path] for path in sorted(rows)], 'source_acceptance': 'not-assessed',
            'scope': 'musl source/identity inputs, 18 verifier/license packages, and static replay dependencies',
            'complete_project_source_lock': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'pack', 'restore'))
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--source', type=Path, required=True, help='workspace for pack, retained directory for restore')
    parser.add_argument('--destination', type=Path, help='new directory; never overwritten')
    args = parser.parse_args()
    if args.mode == 'plan':
        require(args.manifest is None and args.destination is None, 'plan only accepts source')
        result = plan(args.source)
    else:
        require(args.manifest is not None and args.destination is not None, 'manifest and destination required')
        raw = read_regular(args.manifest, 1024**2)
        action = pack if args.mode == 'pack' else restore
        result = action(args.source, raw, args.destination)
    print(json.dumps(result, sort_keys=True, indent=2))
