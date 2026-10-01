#!/usr/bin/env python3
"""Synthetic stream equivalence and decompressor boundaries; no upstream execution."""
import gzip
import importlib.util
import io
import lzma
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('streams', HERE / 'compare-binutils-streams.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def tar_bytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as tar:
        for path, data, owner, kind in entries:
            member = tarfile.TarInfo(m.content.TOP + '/' + path)
            member.size, member.uid, member.gid, member.type = len(data), owner, owner, kind
            tar.addfile(member, io.BytesIO(data))
    return output.getvalue()


class StreamTests(unittest.TestCase):
    def test_equal_multiple_blocks(self):
        raw = b'synthetic' * 30000
        result = m.compare(gzip.compress(raw), lzma.compress(raw))
        self.assertTrue(result['all_expanded_bytes_equal'])
        self.assertFalse(result['compressed_bytes_equal'])
        self.assertEqual(result['gzip_expanded'], m.identity(raw))
        self.assertEqual(result['xz_expanded'], m.identity(raw))
        self.assertIsNone(result['first_differing_offset'])
        self.assertEqual(result['source_acceptance'], 'not-assessed')

    def test_difference_and_full_tail_consumption(self):
        a = b'a' * 150000
        b = a[:70000] + b'b' + a[70001:]
        result = m.compare(gzip.compress(a), lzma.compress(b))
        self.assertFalse(result['all_expanded_bytes_equal'])
        self.assertEqual(result['first_differing_offset'], 70000)
        self.assertEqual(result['xz_expanded'], m.identity(b))

    def test_different_lengths(self):
        for a, b in ((b'a' * 70000, b'a' * 150000), (b'a' * 150000, b'a' * 70000)):
            result = m.compare(gzip.compress(a), lzma.compress(b))
            self.assertFalse(result['all_expanded_bytes_equal'])
            self.assertEqual(result['first_differing_offset'], 70000)

    def test_empty_streams(self):
        self.assertTrue(m.compare(gzip.compress(b''), lzma.compress(b''))['all_expanded_bytes_equal'])

    def test_corruption_truncation_concat_and_padding(self):
        raw = lzma.compress(b'synthetic')
        for changed in (raw[:-1], raw + raw, raw + b'\0' * 4, raw[:20] + b'\xff' * 8 + raw[28:]):
            with self.assertRaises((ValueError, lzma.LZMAError)):
                m.compare(gzip.compress(b'synthetic'), changed)

    def test_bounds_and_memory(self):
        raw = lzma.compress(b'a' * 100)
        for field, limit in [('compressed', 1), ('expanded', 1), ('xz_memory', 1)]:
            with patch.dict(m.LIMITS, {field: limit}), self.assertRaises((ValueError, lzma.LZMAError)):
                m.compare(gzip.compress(b'a' * 100), raw)
        with self.assertRaises(ValueError):
            m.XzReader(raw).read(-1)

    def test_small_reads(self):
        raw = bytes(range(256)) * 1000
        reader = m.XzReader(lzma.compress(raw))
        chunks = []
        while block := reader.read(317):
            chunks.append(block)
        self.assertEqual(b''.join(chunks), raw)
        self.assertEqual(reader.total, len(raw))

    def test_member_payload_and_metadata_differences(self):
        old = tar_bytes([('same', b'x', 0, tarfile.REGTYPE), ('changed', b'y', 0, tarfile.REGTYPE),
                         ('missing', b'z', 0, tarfile.REGTYPE)])
        gz = gzip.compress(old)
        report, _ = m.content.inventory(gz, m.identity(gz))
        new = tar_bytes([('same', b'x', 1000, tarfile.REGTYPE), ('changed', b'diff', 0, tarfile.REGTYPE),
                         ('added', b'new', 0, tarfile.REGTYPE)])
        result = m.compare_members(lzma.compress(new), report)
        self.assertEqual(result['only_in_gzip'], [m.content.TOP + '/missing'])
        self.assertEqual(result['only_in_xz'], [m.content.TOP + '/added'])
        self.assertEqual(result['matching_file_payload_count'], 1)
        self.assertEqual(result['matching_file_count'], 0)
        self.assertEqual(result['changed_field_counts'], {'bytes': 1, 'gid': 1, 'sha256': 1, 'uid': 1})
        self.assertEqual(result['changed_content_files'][0]['path'], m.content.TOP + '/changed')

    def test_invalid_members_and_tail_rejected(self):
        for entries, tail in [([('../escape', b'x', 0, tarfile.REGTYPE)], b''),
                              ([('a', b'x', 0, tarfile.REGTYPE), ('a/b', b'x', 0, tarfile.REGTYPE)], b''),
                              ([('a', b'', 0, tarfile.SYMTYPE)], b''),
                              ([('a', b'x', 0, tarfile.REGTYPE)], b'X')]:
            with self.assertRaises(ValueError):
                m.compare_members(lzma.compress(tar_bytes(entries) + tail), {'members': []})


if __name__ == '__main__':
    unittest.main()
