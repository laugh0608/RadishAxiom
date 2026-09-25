#!/usr/bin/env python3
"""Bounded logical inventory of fixed GCC XZ/tar bytes; never extract or execute."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive_tools = load('inspect-archives.py')
retention = load('retain-musl-verifier-inputs.py')
require, identity = retention.require, retention.identity
TOP, BLOCK = 'gcc-9.4.0', 65536
EXPECTED = {'bytes': 72411232, 'sha256': 'c95da32f440378d7751dd95533186f7fc05ceb4fb65eb5b85234e6299eb9838e'}
DEFAULT = HERE.parents[2] / '.tmp/gcc-inputs-dac0405-20260925/gcc-attempt-2.tar.xz'
LIMITS = {'compressed': 96 * 1024**2, 'tar': 1024**3, 'member': 32 * 1024**2,
          'members': 200000, 'text': 2 * 1024**2, 'xz_memory': 256 * 1024**2, 'path': 4096}
SELECTED = {'README', 'COPYING', 'COPYING3', 'COPYING.LIB', 'COPYING3.LIB', 'COPYING.RUNTIME',
            'gcc/BASE-VER', 'gcc/DATESTAMP', 'gcc/DEV-PHASE', 'gcc/version.c',
            'libgcc/Makefile.in', 'libgcc/libgcc2.c', 'libstdc++-v3/README',
            'libstdc++-v3/libsupc++/new', 'libatomic/libatomic_i.h', 'libgomp/libgomp.h',
            'libsanitizer/LICENSE.TXT', 'libgo/LICENSE', 'libquadmath/COPYING.LIB',
            'contrib/download_prerequisites'}


class XzReader(archive_tools.XzReader):
    def __init__(self, raw):
        require(0 < len(raw) <= LIMITS['compressed'], 'compressed bound')
        super().__init__(io.BytesIO(raw), identity(raw)['sha256'])

    def read(self, size):
        require(0 < size <= BLOCK, 'unbounded XZ read')
        part = super().read(size)
        require(self.tar_bytes <= LIMITS['tar'], 'expanded tar bound')
        return part


def inventory(raw, expected):
    require(identity(raw) == expected, 'archive identity mismatch')
    reader, rows, texts = XzReader(raw), {}, {}
    with tarfile.open(fileobj=reader, mode='r|', bufsize=512) as archive:
        for member in archive:
            name = archive_tools.path_name(member.name, TOP, member.isdir())
            require(name not in rows and len(rows) < LIMITS['members'], 'duplicate path or member bound')
            require((member.isfile() or member.isdir()) and not member.issparse(), 'linked, sparse or special member')
            require(0 <= member.size <= LIMITS['member'], 'member size bound')
            require(not member.isdir() or member.size == 0, 'directory payload')
            row = {'path': name, 'kind': 'directory' if member.isdir() else 'file', 'bytes': member.size,
                   'mode': member.mode, 'uid': member.uid, 'gid': member.gid}
            if member.isfile():
                relative = name[len(TOP) + 1:]
                capture = relative in SELECTED
                require(not capture or member.size <= LIMITS['text'], 'review text bound')
                stream, digest, count, captured = archive.extractfile(member), hashlib.sha256(), 0, bytearray()
                while data := stream.read(BLOCK):
                    count += len(data)
                    digest.update(data)
                    if capture:
                        captured.extend(data)
                require(count == member.size, 'truncated member')
                row['sha256'] = digest.hexdigest()
                if capture:
                    texts[relative] = captured.decode('utf-8')
            rows[name] = row
    while data := reader.read(BLOCK):
        require(not any(data), 'nonzero data after tar end')
    require(rows and reader.ended, 'empty or unconsumed archive')
    implicit = set()
    for name in rows:
        require(name != TOP or rows[name]['kind'] == 'directory', 'file at archive root')
        for parent in Path(name).parents:
            if str(parent) == '.':
                continue
            if str(parent) in rows:
                require(rows[str(parent)]['kind'] == 'directory', 'file ancestor')
            else:
                implicit.add(str(parent))
    return {'archive': expected, 'tar': {'bytes': reader.tar_bytes, 'sha256': reader.tar_hash.hexdigest()},
            'members': [rows[name] for name in sorted(rows)],
            'type_counts': dict(Counter(row['kind'] for row in rows.values())),
            'implicit_directories': sorted(implicit), 'selected_review_files': sorted(texts),
            'physical_tar_profile_verified': False, 'upstream_programs_executed': False,
            'license_review_complete': False, 'source_acceptance': 'not-assessed'}, texts


def inspect(path=DEFAULT):
    report, texts = inventory(retention.read_regular(path, LIMITS['compressed']), EXPECTED)
    require({'README', 'COPYING3', 'COPYING3.LIB', 'COPYING.RUNTIME', 'gcc/BASE-VER'} <= texts.keys(),
            'required review files missing')
    require(texts['gcc/BASE-VER'] == '9.4.0\n', 'GCC version declaration drift')
    report.update(kind='diagnostic-gcc-content-v1', limits=LIMITS,
                  methods={name: identity(retention.read_regular(HERE / name)) for name in
                           ('inspect-gcc-content.py', 'inspect-archives.py', 'retain-musl-verifier-inputs.py')})
    return report, texts


def summarize(report, texts):
    files = [row for row in report['members'] if row['kind'] == 'file']
    return {**{k: v for k, v in report.items() if k != 'members'},
            'member_count': len(report['members']),
            'max_file_bytes': max(row['bytes'] for row in files),
            'selected_file_identities': [row for row in files if row['path'][len(TOP) + 1:] in texts],
            'license_named_files_not_exhaustive': [row['path'] for row in files if
                any(word in row['path'].rsplit('/', 1)[-1].upper() for word in ('COPYING', 'LICENSE', 'COPYRIGHT'))],
            'version_declarations': {name: texts[name] for name in ('gcc/BASE-VER', 'gcc/DATESTAMP', 'gcc/DEV-PHASE')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    report, texts = inspect(args.archive)
    with args.output.open('xb') as stream:
        stream.write(gzip.compress((json.dumps(report, sort_keys=True, indent=2) + '\n').encode(), mtime=0))
    if args.summary is not None:
        with args.summary.open('x') as stream:
            stream.write(json.dumps(summarize(report, texts), sort_keys=True, indent=2) + '\n')
    print(json.dumps({'members': len(report['members']), 'type_counts': report['type_counts'],
                      'tar': report['tar'], 'output': identity(args.output.read_bytes())}, indent=2))
