#!/usr/bin/env python3
"""Synthetic XZ/tar inventory boundaries; no upstream code or network execution."""
import lzma
import importlib.util
import io
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('content', HERE / 'inspect-gcc-content.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def archive(entries=(), tail=b'', root=True):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as tar:
        if root:
            directory = tarfile.TarInfo(m.TOP)
            directory.type = tarfile.DIRTYPE
            tar.addfile(directory)
        for path, raw, kind in entries:
            member = tarfile.TarInfo(m.TOP + '/' + path)
            member.type, member.size = kind, len(raw)
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                member.linkname = '/outside'
            tar.addfile(member, io.BytesIO(raw))
    return lzma.compress(output.getvalue() + tail)


class ContentTests(unittest.TestCase):
    def inspect(self, raw):
        return m.inventory(raw, m.identity(raw))

    def test_inventory_and_selected_text(self):
        raw = archive([('README', b'synthetic', tarfile.REGTYPE)])
        report, texts = self.inspect(raw)
        self.assertEqual(report['type_counts'], {'directory': 1, 'file': 1})
        self.assertEqual(texts, {'README': 'synthetic'})
        self.assertFalse(report['physical_tar_profile_verified'])
        self.assertFalse(report['license_review_complete'])
        self.assertEqual(report['source_acceptance'], 'not-assessed')

    def test_digest_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.inventory(archive(), {'bytes': 0, 'sha256': '0' * 64})

    def test_path_escape_and_duplicate(self):
        row = ('README', b'x', tarfile.REGTYPE)
        for entries in ([('../escape', b'x', tarfile.REGTYPE)], [row, row], [('a\\b', b'x', tarfile.REGTYPE)]):
            with self.assertRaises(ValueError):
                self.inspect(archive(entries))

    def test_link_and_special(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            with self.assertRaisesRegex(ValueError, 'linked, sparse or special'):
                self.inspect(archive([('bad', b'', kind)]))

    def test_directory_payload(self):
        with self.assertRaisesRegex(ValueError, 'directory payload'):
            self.inspect(archive([('bad', b'x', tarfile.DIRTYPE)]))

    def test_empty_or_file_ancestor(self):
        for raw in (archive(root=False), archive([('a', b'x', tarfile.REGTYPE), ('a/file', b'x', tarfile.REGTYPE)])):
            with self.assertRaises(ValueError):
                self.inspect(raw)

    def test_implicit_directories_are_recorded(self):
        report, _ = self.inspect(archive([('sub/file', b'x', tarfile.REGTYPE)], root=False))
        self.assertEqual(report['implicit_directories'], [m.TOP, m.TOP + '/sub'])
        self.assertEqual(report['type_counts'], {'file': 1})

    def test_member_and_count_bounds(self):
        raw = archive([('file', b'abc', tarfile.REGTYPE)])
        for bound, limit in [('member', 2), ('members', 1)]:
            with patch.dict(m.LIMITS, {bound: limit}), self.assertRaises(ValueError):
                self.inspect(raw)

    def test_text_bound_and_encoding(self):
        with patch.dict(m.LIMITS, {'text': 2}), self.assertRaisesRegex(ValueError, 'text bound'):
            self.inspect(archive([('README', b'abc', tarfile.REGTYPE)]))
        with self.assertRaises(UnicodeError):
            self.inspect(archive([('README', b'\xff', tarfile.REGTYPE)]))

    def test_xz_truncation_concatenation_crc(self):
        raw = archive()
        for changed in (raw[:-1], raw + raw, raw + b'x', raw[:-8] + b'\xff' * 8):
            with self.subTest(size=len(changed)), self.assertRaises((ValueError, lzma.LZMAError)):
                self.inspect(changed)

    def test_expansion_and_compression_bounds(self):
        raw = archive()
        for bound, limit in [('tar', 512), ('compressed', 2)]:
            with patch.dict(m.LIMITS, {bound: limit}), self.assertRaises(ValueError):
                self.inspect(raw)

    def test_hidden_tail(self):
        with self.assertRaisesRegex(ValueError, 'nonzero data'):
            self.inspect(archive(tail=b'X'))

    def test_bounded_small_reads(self):
        raw = b'x' * 200000
        reader = m.XzReader(lzma.compress(raw))
        output = bytearray()
        while chunk := reader.read(317):
            output.extend(chunk)
        self.assertEqual(bytes(output), raw)
        self.assertEqual(reader.tar_bytes, len(raw))
        with self.assertRaises(ValueError):
            reader.read(-1)


if __name__ == '__main__':
    unittest.main()
