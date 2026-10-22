#!/usr/bin/env python3
"""Independent read-only byte/tree reconciliation using stdlib tarfile parser.

Does not import the acquisition/parser implementation. This checks consistency
of retained evidence; unsigned manifests do not establish publisher identity.
"""
from __future__ import annotations
import bz2
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / 'docs/records/solver-cvc5-source-review-2026-10-17'
RETAINED = ROOT / '.tmp/cvc5-c0-acquisition-2026-10-17'


def digest(path):
    value, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('nonregular-retained-file')
        while chunk := stream.read(1024 * 1024):
            count += len(chunk)
            value.update(chunk)
    return count, value.hexdigest()


def check_identity(row):
    path = ROOT / row['path']
    actual = digest(path)
    if actual != (row['bytes'], row['raw_digest'].removeprefix('sha256:')):
        raise ValueError('identity-drift: ' + row['path'])
    return path


class BoundedDecompressed:
    def __init__(self, stream):
        self.stream, self.count = stream, 0

    def read(self, size):
        if not 0 <= size <= 128 * 1024 * 1024:
            raise ValueError('unbounded-independent-tar-read')
        result = self.stream.read(size)
        self.count += len(result)
        if self.count > 1024 * 1024 * 1024:
            raise ValueError('independent-expanded-tar-budget')
        return result


def verify_archive(archive, recorded):
    expected = {row['path']: row for row in recorded['entries']}
    seen, aliases, payload = set(), set(), 0
    with archive.open('rb') as raw:
        magic = raw.read(3)
        raw.seek(0)
        stream = bz2.BZ2File(raw, 'rb') if magic == b'BZh' else gzip.GzipFile(fileobj=raw)
        bounded = BoundedDecompressed(stream)
        with tarfile.open(fileobj=bounded, mode='r|') as tar:
            for info in tar:
                name = info.name.rstrip('/') if info.isdir() else info.name
                if name not in expected or name in seen or len(seen) >= 100000:
                    raise ValueError('independent-unexpected-duplicate-or-count')
                if name.startswith('/') or any(part in {'', '.', '..'} for part in name.split('/')) or '\\' in name:
                    raise ValueError('independent-path-escape')
                alias = unicodedata.normalize('NFC', name).casefold()
                if alias in aliases:
                    raise ValueError('independent-cross-platform-collision')
                seen.add(name)
                aliases.add(alias)
                row = expected[name]
                kind = 'file' if info.isfile() else 'directory' if info.isdir() else 'symlink' if info.issym() else 'hardlink' if info.islnk() else 'unsupported'
                if kind != row['kind'] or info.size != row['bytes'] or format(info.mode, '04o') != row['original_mode']:
                    raise ValueError('independent-metadata-type-size-mode-drift')
                if info.size > 128 * 1024 * 1024:
                    raise ValueError('independent-member-byte-budget')
                if kind == 'file':
                    payload += info.size
                    if payload > 1024 * 1024 * 1024:
                        raise ValueError('independent-payload-budget')
                    body = tar.extractfile(info)
                    value, count = hashlib.sha256(), 0
                    while chunk := body.read(65536):
                        value.update(chunk)
                        count += len(chunk)
                    if count != info.size or value.hexdigest() != row['sha256']:
                        raise ValueError('independent-tar-file-hash-drift')
                elif kind in {'symlink', 'hardlink'} and info.linkname != row['target']:
                    raise ValueError('independent-tar-link-drift')
            if tar.pax_headers != recorded['global_pax']:
                raise ValueError('independent-pax-global-comment-drift')
        stream.close()
    if seen != set(expected) or payload != recorded['payload_bytes']:
        raise ValueError('independent-missing-entry-or-payload-total')
    return expected


def verify_filesystem(base, expected):
    found = set()
    # os.walk does not descend into source symlinks.
    for current, dirs, files in os.walk(base, followlinks=False):
        for basename in dirs + files:
            path = Path(current) / basename
            name = str(path.relative_to(base))
            found.add(name)
            if name not in expected:
                raise ValueError('independent-extra-materialized-entry')
            row, observed = expected[name], path.lstat()
            if row['kind'] == 'directory':
                if not stat.S_ISDIR(observed.st_mode) or stat.S_IMODE(observed.st_mode) != 0o700:
                    raise ValueError('independent-directory-type-mode-drift')
            elif row['kind'] == 'symlink':
                if not stat.S_ISLNK(observed.st_mode) or os.readlink(path) != row['target']:
                    raise ValueError('independent-symlink-drift')
                resolved = path.resolve(strict=True)
                if resolved != base / row['resolved_path'] or not resolved.is_relative_to(base):
                    raise ValueError('independent-symlink-resolution-drift')
            else:
                if not stat.S_ISREG(observed.st_mode) or stat.S_IMODE(observed.st_mode) != 0o600:
                    raise ValueError('independent-file-type-mode-drift')
                wanted = expected[row['resolved_path']] if row['kind'] == 'hardlink' else row
                if digest(path) != (wanted['bytes'], wanted['sha256']):
                    raise ValueError('independent-materialized-content-drift')
                if row['kind'] == 'hardlink' and not os.path.samefile(path, base / row['resolved_path']):
                    raise ValueError('independent-hardlink-inode-drift')
    if found != set(expected):
        raise ValueError('independent-materialized-member-set-drift')


def main():
    source = json.loads((RECORDS / 'source-inputs.json').read_bytes())
    manifest = json.loads(check_identity(source['acquisition_manifest']).read_bytes())
    check_identity(source['fetch_helper'])
    check_identity(source['inspection_helper'])
    check_identity(source['retained_inspection_helper'])
    check_identity(source['download_selection'])
    check_identity(manifest['selection_input'])
    selected = json.loads((RETAINED / 'input-selection.json').read_bytes())
    expected_inputs = {row['id']: row for row in selected['source_archives']}
    if set(row['id'] for row in source['sources']) != {'cvc5', 'cadical', 'symfpu', 'libpoly', 'gmp'}:
        raise ValueError('independent-source-set-drift')
    total = 0
    for row in source['sources']:
        name = row['id']
        path = check_identity(row['archive'])
        total += row['archive']['bytes']
        expected_hash = expected_inputs[name]['expected_archive_sha256']
        if expected_hash is not None and row['archive']['raw_digest'] != 'sha256:' + expected_hash:
            raise ValueError('independent-expected-archive-hash-drift')
        if row['archive']['bytes'] > (64 if name == 'cvc5' else 32) * 1024 * 1024:
            raise ValueError('independent-archive-size-budget')
        recorded = json.loads(check_identity(row['tree_inventory']).read_bytes())
        commit = expected_inputs[name]['commit']
        if commit is not None and recorded['global_pax'].get('comment') != commit:
            raise ValueError('independent-selected-commit-comment-drift')
        check_identity(row['license_inventory'])
        entries = verify_archive(path, recorded)
        verify_filesystem((ROOT / row['source_root']).parent, entries)
        if name == 'cvc5':
            tree_path = check_identity(row['cvc5_retained_git_blob_check']['retained_git_tree'])
            git_tree = json.loads(tree_path.read_bytes())
            blobs = {blob['path']: blob for blob in git_tree['tree'] if blob['type'] == 'blob'}
            actual = {}
            for entry in entries.values():
                if entry['kind'] not in {'file', 'symlink'}:
                    continue
                relative = entry['path'].split('/', 1)[1]
                file = (ROOT / row['source_root']).parent / entry['path']
                raw = os.readlink(file).encode() if entry['kind'] == 'symlink' else file.read_bytes()
                value = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                actual[relative] = value
            if set(actual) != set(blobs) or any(value != blobs[name]['sha'] for name, value in actual.items()):
                raise ValueError('independent-cvc5-git-blob-drift')
    if total > 192 * 1024 * 1024:
        raise ValueError('independent-archive-total-budget')
    print(json.dumps({'status': 'checked', 'sources': len(source['sources']), 'archive_bytes': total,
                      'scope': 'independent-retained-byte-tree-consistency-only', 'signature_authentication': 'not-established',
                      'license_acceptance': 'not-accepted', 'build_ready': False}, indent=2))


if __name__ == '__main__':
    main()
