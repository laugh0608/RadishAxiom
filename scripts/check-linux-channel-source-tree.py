#!/usr/bin/env python3
"""Independent bounded file-tree comparison; no production inspector imports or execution."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

MAX_ARCHIVE = 64 * 1024**2
MAX_TREE = 32 * 1024**2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, limit):
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    require(len(value) <= limit, 'input-size-limit')
    return value


def expanded(raw):
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        value = stream.read(MAX_TREE + 1)
    require(len(value) <= MAX_TREE, 'expanded-size-limit')
    return value


def tree(raw, dot_prefix):
    result, root = {}, None
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        require(not archive.pax_headers, 'source-pax')
        for member in archive:
            require(len(result) < 4096 and not member.pax_headers, 'tree-count-or-pax')
            name = member.name
            if dot_prefix and name == '.':
                require(root is None and member.isdir(), 'source-root-header')
                root = {'mode': member.mode, 'uid': member.uid, 'gid': member.gid}
                continue
            if dot_prefix:
                require(name.startswith('./'), 'source-relative-prefix')
                name = name[2:]
            require(name and len(name) <= 4096 and '\\' not in name
                    and all(p not in ('', '.', '..') for p in name.split('/'))
                    and all(ord(c) >= 32 and ord(c) != 127 for c in name), 'unsafe-tree-path')
            require(name not in result and (member.isfile() or member.isdir() or member.issym()),
                    'duplicate-or-special-member')
            row = {'kind': 'file' if member.isfile() else 'directory' if member.isdir() else 'symlink',
                   'mode': member.mode, 'uid': member.uid, 'gid': member.gid,
                   'bytes': member.size, 'link': member.linkname}
            if member.isfile():
                require(0 <= member.size <= MAX_TREE, 'file-size-limit')
                data = archive.extractfile(member).read(member.size + 1)
                require(len(data) == member.size, 'file-truncated')
                row['sha256'] = hashlib.sha256(data).hexdigest()
            result[name] = row
    require(bool(result) and (not dot_prefix or root is not None), 'missing-tree-or-root')
    return result, root


def compare(image, compressed_digest, diff_id, source, source_sha256, source_blob_sha1, sums):
    require(hashlib.sha256(source).hexdigest() == source_sha256, 'source-sha256')
    require(hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
            == source_blob_sha1, 'source-git-blob')
    expected = [line.split()[0] for line in sums.decode().splitlines()
                if len(line.split()) == 2
                and line.split()[1].lstrip('*') == 'aarch64/alpine-minirootfs-3.23.5-aarch64.tar.gz']
    require(expected == [hashlib.sha512(source).hexdigest()], 'source-sha512-list')
    with tarfile.open(fileobj=io.BytesIO(image), mode='r:') as archive:
        name = 'blobs/sha256/' + compressed_digest
        matches = [m for m in archive if m.name == name]
        require(len(matches) == 1 and matches[0].isfile()
                and matches[0].size <= MAX_ARCHIVE, 'image-layer-member')
        compressed = archive.extractfile(matches[0]).read(MAX_ARCHIVE + 1)
    require(hashlib.sha256(compressed).hexdigest() == compressed_digest, 'image-layer-digest')
    image_tar, source_tar = expanded(compressed), expanded(source)
    require(hashlib.sha256(image_tar).hexdigest() == diff_id, 'image-diff-id')
    a, source_root = tree(source_tar, True)
    b, _ = tree(image_tar, False)
    differences = [p for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)]
    return {'scope': 'relative-tree-comparison-only-not-runtime-root-equivalence',
            'source_archive_sha256': source_sha256, 'source_git_blob_sha1': source_blob_sha1,
            'source_sha512': expected[0], 'image_compressed_digest': compressed_digest,
            'image_diff_id': diff_id, 'source_tar_sha256': hashlib.sha256(source_tar).hexdigest(),
            'path_rule': 'source dot root retained separately; remove exactly one leading ./; reject collisions',
            'source_root_header_not_present_in_image_layer': source_root,
            'source_count': len(a), 'image_count': len(b), 'difference_paths': differences,
            'relative_trees_equal': not differences,
            'compared_fields': ['relative path', 'kind', 'mode', 'uid', 'gid', 'bytes', 'literal link', 'file SHA256'],
            'not_compared': ['runtime root directory metadata', 'mtime', 'uname', 'gname',
                             'tar header encoding/padding', 'runtime mounts/namespace'],
            'image_acceptance': 'not-accepted', 'execution_ready': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('image', 'source', 'checksums', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('image-sha256', 'layer-sha256', 'diff-id', 'source-sha256', 'source-blob-sha1'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        require(all(re.fullmatch('[0-9a-f]{64}', x) for x in (
            args.image_sha256, args.layer_sha256, args.diff_id, args.source_sha256))
                and re.fullmatch('[0-9a-f]{40}', args.source_blob_sha1), 'digest-shape')
        image = read(args.image, MAX_ARCHIVE)
        require(hashlib.sha256(image).hexdigest() == args.image_sha256, 'image-archive-digest')
        result = compare(image, args.layer_sha256, args.diff_id, read(args.source, MAX_ARCHIVE),
                         args.source_sha256, args.source_blob_sha1, read(args.checksums, 65536))
        result.update(method_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      image_archive_sha256=args.image_sha256)
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        print('independent relative tree comparison retained; no environment created')
        return 0 if result['relative_trees_equal'] else 2
    except (ValueError, OSError, UnicodeError, tarfile.TarError) as exc:
        reason = str(exc) if type(exc) is ValueError and re.fullmatch('[a-z0-9-]+', str(exc)) else type(exc).__name__
        print('source comparison failed: ' + reason)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
