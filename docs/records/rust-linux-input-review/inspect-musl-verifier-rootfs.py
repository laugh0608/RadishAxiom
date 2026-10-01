#!/usr/bin/env python3
"""Compare a diagnostic tar against its reviewed plan without importing the builder or extracting files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read_bounded(path, limit):
    require(path.absolute() == path.resolve() and path.is_file(), 'non-regular or symlink input')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'input limit exceeded')
    return raw


def inspect(raw, plan):
    require(1024 <= len(raw) <= 16 * 1024**2 and len(raw) % 512 == 0, 'invalid tar length')
    rows = plan['entries']
    expected = {row['path']: row for row in rows}
    require(len(expected) == len(rows) == plan['entry_count'] <= 512, 'invalid plan entry count')
    observed = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            path = member.name
            require(len(observed) < len(expected) and path in expected and path not in observed,
                    'extra, unexpected or duplicate entry: ' + path)
            row = expected[path]
            require(not member.pax_headers and raw[member.offset + 257:member.offset + 265] == b'ustar\x0000',
                    'non-USTAR entry: ' + path)
            kind = {tarfile.REGTYPE: 'file', tarfile.DIRTYPE: 'directory', tarfile.SYMTYPE: 'symlink'}.get(member.type)
            require(kind == row['type'], 'entry type mismatch: ' + path)
            require((member.mode, member.uid, member.gid) == (row['mode'], row['uid'], row['gid']),
                    'entry metadata mismatch: ' + path)
            require(member.mtime == 0 and member.uname == member.gname == '' and
                    member.devmajor == member.devminor == 0, 'unexpected header metadata: ' + path)
            if kind == 'file':
                require(member.size == row['bytes'], 'file size mismatch: ' + path)
                data = archive.extractfile(member).read()
                require(identity(data) == {key: row[key] for key in ('bytes', 'sha256')},
                        'file identity mismatch: ' + path)
                require(member.linkname == '', 'regular file has link target: ' + path)
            else:
                require(member.size == 0 and member.linkname == row.get('target', ''),
                        'non-file payload or link mismatch: ' + path)
            payload_end = member.offset_data + member.size
            padded_end = (payload_end + 511) // 512 * 512
            require(not any(raw[payload_end:padded_end]), 'nonzero file padding: ' + path)
            observed.append(path)
        require(len(raw) - archive.offset >= 1024 and not any(raw[archive.offset:]), 'invalid tar terminator')
    require(set(observed) == set(expected), 'missing entries')
    file_bytes = sum(row.get('bytes', 0) for row in rows)
    require(file_bytes == plan['file_bytes'], 'plan file byte count mismatch')
    return {'entry_count': len(observed), 'file_bytes': file_bytes, 'tar': identity(raw),
            'entry_types': {kind: sum(row['type'] == kind for row in rows)
                            for kind in ('file', 'directory', 'symlink')},
            'result': 'matched-reviewed-plan', 'programs_executed': False,
            'source_acceptance': 'not-assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--tar', type=Path, required=True)
    args = parser.parse_args()
    plan_raw = read_bounded(args.plan, 1024**2)
    result = inspect(read_bounded(args.tar, 16 * 1024**2), json.loads(plan_raw))
    result.update(kind='diagnostic-verifier-rootfs-readback-v1', plan=identity(plan_raw),
                  method=identity(Path(__file__).read_bytes()))
    print(json.dumps(result, sort_keys=True, indent=2))
