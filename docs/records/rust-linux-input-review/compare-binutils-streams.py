#!/usr/bin/env python3
"""Compare entire bounded gzip/XZ decompressed streams, without extracting or accepting source."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('content', HERE / 'inspect-binutils-content.py')
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)
require, identity = content.require, content.identity
BLOCK = 65536
LIMITS = {'compressed': 64 * 1024**2, 'expanded': 512 * 1024**2, 'xz_memory': 256 * 1024**2}


class XzReader:
    def __init__(self, raw):
        require(0 < len(raw) <= LIMITS['compressed'], 'compressed bound')
        self.source = io.BytesIO(raw)
        self.decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=LIMITS['xz_memory'])
        self.ended, self.total = False, 0

    def read(self, size):
        require(0 < size <= BLOCK, 'unbounded XZ read')
        output = bytearray()
        while len(output) < size and not self.ended:
            if self.decoder.eof:
                require(not self.decoder.unused_data and not self.source.read(1), 'trailing or concatenated XZ')
                self.ended = True
                break
            data = self.source.read(BLOCK) if self.decoder.needs_input else b''
            require(data or not self.decoder.needs_input, 'truncated XZ')
            part = self.decoder.decompress(data, max_length=size - len(output))
            self.total += len(part)
            require(self.total <= LIMITS['expanded'], 'expanded XZ bound')
            output.extend(part)
        return bytes(output)


def compare(gzip_raw, xz_raw):
    left, right = content.GzipReader(gzip_raw), XzReader(xz_raw)
    hashes, sizes = [hashlib.sha256(), hashlib.sha256()], [0, 0]
    equal, first_difference = True, None
    while True:
        a, b = left.read(BLOCK), right.read(BLOCK)
        if a != b:
            if first_difference is None:
                common = min(len(a), len(b))
                position = next((n for n in range(common) if a[n] != b[n]), common)
                first_difference = min(sizes) + position
            equal = False
        for n, data in enumerate((a, b)):
            hashes[n].update(data)
            sizes[n] += len(data)
        if not a and not b:
            break
    require(left.ended and right.ended, 'unconsumed compressed input')
    return {'gzip': identity(gzip_raw), 'xz': identity(xz_raw),
            'gzip_expanded': {'bytes': sizes[0], 'sha256': hashes[0].hexdigest()},
            'xz_expanded': {'bytes': sizes[1], 'sha256': hashes[1].hexdigest()},
            'all_expanded_bytes_equal': equal, 'first_differing_offset': first_difference,
            'compressed_bytes_equal': gzip_raw == xz_raw, 'source_acceptance': 'not-assessed',
            'archive_programs_executed': False}


def compare_members(xz_raw, gzip_report):
    """Diagnose why tar bytes differ; this does not establish full tar equivalence."""
    reader, rows = XzReader(xz_raw), {}
    with tarfile.open(fileobj=reader, mode='r|', bufsize=512) as archive:
        for member in archive:
            name = content.inputs.inputs.archive.path_name(member.name, content.TOP, member.isdir())
            require(name not in rows and len(rows) < content.LIMITS['members'], 'duplicate or member bound')
            require((member.isfile() or member.isdir()) and not member.issparse(), 'unsupported member')
            require(0 <= member.size <= content.LIMITS['member'], 'member size bound')
            require(not member.isdir() or member.size == 0, 'directory payload')
            row = {'path': name, 'kind': 'directory' if member.isdir() else 'file',
                   'mode': member.mode, 'uid': member.uid, 'gid': member.gid, 'bytes': member.size}
            if member.isfile():
                stream, digest, count = archive.extractfile(member), hashlib.sha256(), 0
                while block := stream.read(BLOCK):
                    count += len(block)
                    digest.update(block)
                require(count == member.size, 'truncated member')
                row['sha256'] = digest.hexdigest()
            rows[name] = row
    while block := reader.read(BLOCK):
        require(not any(block), 'nonzero tar tail')
    require(rows and reader.ended, 'empty or unconsumed archive')
    for name, row in rows.items():
        require(name != content.TOP or row['kind'] == 'directory', 'file at archive root')
        for parent in Path(name).parents:
            require(str(parent) not in rows or rows[str(parent)]['kind'] == 'directory', 'file ancestor')
    old = {r['path']: r for r in gzip_report['members'] if r['kind'] == 'file'}
    new = {name: row for name, row in rows.items() if row['kind'] == 'file'}
    common = old.keys() & new.keys()
    fields = Counter(k for name in common for k in old[name] if old[name][k] != new[name][k])
    changed = [{'path': name, 'gzip': old[name], 'xz': new[name]} for name in sorted(common)
               if any(old[name][k] != new[name][k] for k in ('bytes', 'sha256'))]
    return {'gzip_file_count': len(old), 'xz_file_count': len(new),
            'xz_explicit_directory_count': len(rows) - len(new),
            'only_in_gzip': sorted(old.keys() - new.keys()), 'only_in_xz': sorted(new.keys() - old.keys()),
            'changed_content_files': changed, 'matching_file_payload_count': len(common) - len(changed),
            'changed_field_counts': dict(sorted(fields.items())),
            'matching_file_count': sum(old[name] == new[name] for name in common),
            'gzip_file_owners': sorted({(r['uid'], r['gid']) for r in old.values()}),
            'xz_file_owners': sorted({(r['uid'], r['gid']) for r in new.values()}),
            'compared_file_fields': ['path', 'kind', 'bytes', 'sha256', 'mode', 'uid', 'gid'],
            'tar_header_order_timestamps_and_directory_metadata_equal': 'not-assessed',
            'source_acceptance': 'not-assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gzip', type=Path, required=True)
    parser.add_argument('--xz', type=Path, required=True)
    args = parser.parse_args()
    result = compare(content.inputs.read(args.gzip, LIMITS['compressed']),
                     content.inputs.read(args.xz, LIMITS['compressed']))
    print(json.dumps(result, sort_keys=True, indent=2))
