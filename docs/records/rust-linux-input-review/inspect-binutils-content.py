#!/usr/bin/env python3
"""Bounded logical inventory of fixed Binutils gzip/tar bytes; never extract or execute."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inputs', HERE / 'inspect-binutils-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
require, identity = inputs.require, inputs.identity
TOP = 'binutils-2.44'
BLOCK = 65536
LIMITS = {'compressed': 64 * 1024**2, 'tar': 512 * 1024**2,
          'member': 32 * 1024**2, 'members': 100000, 'text': 2 * 1024**2}
SELECTED = {'README', 'COPYING', 'COPYING3', 'COPYING.LIB', 'COPYING3.LIB',
            'COPYING.LIBGLOSS', 'COPYING.NEWLIB', 'COPYING.RUNTIME',
            'bfd/version.m4', 'include/ansidecl.h', 'libiberty/COPYING.LIB',
            'gas/doc/as.texi', 'ld/ld.texi', 'binutils/doc/binutils.texi'}


class GzipReader:
    def __init__(self, raw):
        require(0 < len(raw) <= LIMITS['compressed'], 'compressed size bound')
        self.source = io.BytesIO(raw)
        self.decoder = zlib.decompressobj(31)
        self.pending = b''
        self.ended = False
        self.tar_bytes = 0
        self.tar_hash = hashlib.sha256()

    def read(self, size):
        require(0 <= size <= BLOCK, 'unbounded gzip read')
        output = bytearray()
        while len(output) < size and not self.ended:
            if self.decoder.eof:
                require(not self.decoder.unused_data and not self.pending and not self.source.read(1),
                        'trailing or concatenated gzip')
                self.ended = True
                break
            data = self.pending or self.source.read(BLOCK)
            require(data, 'truncated gzip')
            part = self.decoder.decompress(data, max_length=size - len(output))
            self.pending = self.decoder.unconsumed_tail
            self.tar_bytes += len(part)
            require(self.tar_bytes <= LIMITS['tar'], 'expanded tar bound')
            self.tar_hash.update(part)
            output.extend(part)
        return bytes(output)


def inventory(raw, expected):
    require(identity(raw) == expected, 'archive identity mismatch')
    reader, rows, texts = GzipReader(raw), {}, {}
    # 512-byte buffering avoids consuming unexamined data beyond the logical tar end.
    with tarfile.open(fileobj=reader, mode='r|', bufsize=512) as archive:
        for member in archive:
            name = inputs.inputs.archive.path_name(member.name, TOP, member.isdir())
            require(name not in rows and len(rows) < LIMITS['members'], 'duplicate path or member bound')
            require(member.isfile() or member.isdir(), 'linked or special member: ' + name)
            require(not member.issparse(), 'sparse member: ' + name)
            require(0 <= member.size <= LIMITS['member'], 'member size bound')
            require(not member.isdir() or member.size == 0, 'directory payload')
            row = {'path': name, 'kind': 'directory' if member.isdir() else 'file',
                   'bytes': member.size, 'mode': member.mode, 'uid': member.uid, 'gid': member.gid}
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
    require(reader.ended, 'gzip stream not exhausted')
    require(rows, 'empty archive')
    implicit_directories = set()
    for name in rows:
        require(name != TOP or rows[name]['kind'] == 'directory', 'file at archive root')
        # Logical tar archives need not carry directory headers. Missing ancestors
        # are recorded as implicit; an actual file used as an ancestor is rejected.
        for parent in Path(name).parents:
            if str(parent) == '.':
                continue
            if str(parent) in rows:
                require(rows[str(parent)]['kind'] == 'directory', 'file used as directory ancestor')
            else:
                implicit_directories.add(str(parent))
    return {'archive': expected, 'tar': {'bytes': reader.tar_bytes, 'sha256': reader.tar_hash.hexdigest()},
            'members': [rows[name] for name in sorted(rows)],
            'type_counts': dict(Counter(row['kind'] for row in rows.values())),
            'implicit_directories': sorted(implicit_directories),
            'selected_review_files': sorted(texts), 'physical_tar_profile_verified': False,
            'upstream_programs_executed': False, 'license_review_complete': False,
            'source_acceptance': 'not-assessed'}, texts


def inspect(path):
    report, texts = inventory(inputs.read(path, LIMITS['compressed']), inputs.ARCHIVE)
    require({'README', 'COPYING3', 'COPYING.LIB', 'bfd/version.m4'} <= texts.keys(), 'required review files missing')
    require('m4_define([BFD_VERSION], [2.44])' in texts['bfd/version.m4'], 'BFD version declaration drift')
    report.update(kind='diagnostic-binutils-content-v1', limits=LIMITS,
                  methods={name: identity(inputs.read(HERE / name)) for name in
                           ('inspect-binutils-content.py', 'inspect-binutils-inputs.py', 'inspect-archives.py')})
    return report, texts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=inputs.DEFAULT / 'binutils-attempt-1.tar.gz')
    parser.add_argument('--output', type=Path, required=True, help='new deterministic gzip JSON; never overwrite')
    args = parser.parse_args()
    report, _ = inspect(args.archive)
    raw = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    with args.output.open('xb') as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(json.dumps({'members': len(report['members']), 'type_counts': report['type_counts'],
                      'tar': report['tar'], 'output': identity(args.output.read_bytes())}, indent=2))
