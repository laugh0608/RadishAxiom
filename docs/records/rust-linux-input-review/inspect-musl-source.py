#!/usr/bin/env python3
"""Read-only musl source inventory; observed hashes do not authenticate origin."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import tarfile

TOP = 'musl-1.2.5'
SOURCE_BYTES = 1080786
SOURCE_SHA256 = 'a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4'
SOURCE_COMMIT_COMMENT = '0784374d561435f7c787a555aeab8ede699ed298'
MAX_COMPRESSED = 4 * 1024**2
MAX_TAR = 32 * 1024**2
MAX_MEMBER = 8 * 1024**2
MAX_MEMBERS = 10000
REFERENCE_SHA1 = '36210d3423172a40ddcf83c762207c5f760b60a6'
ARCHIVE_METHOD = Path(__file__).resolve().parent / 'inspect-archives.py'
spec = importlib.util.spec_from_file_location('retained_archive', ARCHIVE_METHOD)
archive_method = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_method)
TERMS = ('copyright', 'license', 'permission', 'public domain', 'spdx-')


def inspect(path, include_text=False):
    with path.open('rb') as stream:
        compressed = stream.read(MAX_COMPRESSED + 1)
    if len(compressed) > MAX_COMPRESSED:
        raise ValueError('compressed size limit')
    if len(compressed) != SOURCE_BYTES or hashlib.sha256(compressed).hexdigest() != SOURCE_SHA256:
        raise ValueError('pinned source archive size or SHA-256 mismatch')
    sha1 = hashlib.sha1(compressed).hexdigest()
    if sha1 != REFERENCE_SHA1:
        raise ValueError('archive differs from retained upstream recipe SHA-1')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(MAX_TAR + 1)
    if len(raw) > MAX_TAR:
        raise ValueError('tar expansion limit')
    seen, rows = set(), []
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
        for member in tar:
            name = archive_method.path_name(member.name, TOP, member.isdir())
            if name in seen or len(seen) >= MAX_MEMBERS:
                raise ValueError('duplicate name or member count limit')
            seen.add(name)
            if member.size < 0 or member.size > MAX_MEMBER:
                raise ValueError('member size limit')
            if not (member.isdir() or member.isfile()):
                raise ValueError('linked or special source member')
            if member.isdir():
                if member.size:
                    raise ValueError('nonempty directory')
                continue
            data = tar.extractfile(member).read()
            if len(data) != member.size:
                raise ValueError('truncated member')
            text = data.decode('utf-8')
            relative = name[len(TOP)+1:]
            if relative == 'VERSION' and text != '1.2.5\n':
                raise ValueError('source version mismatch')
            row = {'path': relative, 'bytes': len(data),
                   'sha256': hashlib.sha256(data).hexdigest(),
                   'git_blob_sha1': hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),
                   'license_term_lines': [i for i,l in enumerate(text.splitlines(),1)
                                          if any(term in l.lower() for term in TERMS)]}
            if include_text:
                row['text'] = text
            rows.append(row)
        if any(raw[tar.offset:]):
            raise ValueError('nonzero tar tail')
        pax = tar.pax_headers
    if pax.get('comment') != SOURCE_COMMIT_COMMENT or len(seen) != 2933:
        raise ValueError('source archive comment or inventory count mismatch')
    if not {'COPYRIGHT', 'VERSION', 'Makefile', 'src/locale/iconv.c', 'src/stdlib/qsort.c'}.issubset(r['path'] for r in rows):
        raise ValueError('missing required source files')
    return {'kind': 'diagnostic-observation', 'acceptance': 'not-assessed',
            'python': platform.python_version(),
            'archive': {'file': path.name, 'bytes': len(compressed),
                        'sha256': hashlib.sha256(compressed).hexdigest(),
                        'recipe_sha1': sha1, 'tar_bytes': len(raw),
                        'tar_sha256': hashlib.sha256(raw).hexdigest(),
                        'member_count': len(seen), 'pax_headers': pax},
            'limits': {'compressed': MAX_COMPRESSED, 'tar': MAX_TAR,
                       'member': MAX_MEMBER, 'members': MAX_MEMBERS},
            'methods': {Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        ARCHIVE_METHOD.name: hashlib.sha256(ARCHIVE_METHOD.read_bytes()).hexdigest()},
            'files': sorted(rows, key=lambda r:r['path'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--include-text', action='store_true')
    args = parser.parse_args()
    print(json.dumps(inspect(args.archive, args.include_text), sort_keys=True, indent=2))
