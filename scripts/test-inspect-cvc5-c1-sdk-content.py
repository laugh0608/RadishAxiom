#!/usr/bin/env python3
"""Synthetic tests for archive-only C1 inspection, without network or payload execution."""
import bz2
import gzip
import importlib.util
import io
import lzma
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('review', ROOT / 'scripts/inspect-cvc5-c1-sdk-content.py')
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
DERIVED_SPEC = importlib.util.spec_from_file_location(
    'derived_review', ROOT / 'docs/records/solver-cvc5-c1-review-2026-10-23/derive-content-review.py')
DERIVED = importlib.util.module_from_spec(DERIVED_SPEC)
DERIVED_SPEC.loader.exec_module(DERIVED)


def tar(rows):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        for name, content in rows:
            entry = tarfile.TarInfo(name)
            if isinstance(content, tuple):
                entry.type, entry.linkname = content
                archive.addfile(entry)
            else:
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
    return output.getvalue()


def ar(rows):
    result = bytearray(b'!<arch>\n')
    for name, raw in rows:
        result.extend(f'{name:<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(raw):<10}`\n'.encode())
        result.extend(raw)
        if len(raw) % 2:
            result.extend(b'\n')
    return bytes(result)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.tmp', prefix='cvc5-content-test-')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name).resolve()
        (self.output / 'text').mkdir()
        self.budget = {'expanded': 0, 'selected': 0}

    def scan(self, rows, **kwargs):
        return REVIEW.scan_tar(lzma.compress(tar(rows)), 'input.tar.xz', 'test',
                               self.budget, self.output, **kwargs)

    def test_all_compressions_bounded_roundtrip(self):
        data = b'synthetic' * 100000
        for suffix, encode in [('gz', gzip.compress), ('xz', lzma.compress), ('bz2', bz2.compress)]:
            with self.subTest(suffix=suffix):
                chunks = list(REVIEW.expanded_chunks(encode(data), 'x.tar.' + suffix))
                self.assertEqual(b''.join(chunks), data)
                self.assertTrue(all(len(chunk) <= 65536 for chunk in chunks))

    def test_compressed_truncation_rejected(self):
        for suffix, encode in [('gz', gzip.compress), ('xz', lzma.compress), ('bz2', bz2.compress)]:
            with self.subTest(suffix=suffix), self.assertRaises((ValueError, EOFError, lzma.LZMAError)):
                list(REVIEW.expanded_chunks(encode(b'synthetic')[:-4], 'x.tar.' + suffix))

    def test_concatenation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'trailing-or-concatenated'):
            list(REVIEW.expanded_chunks(gzip.compress(b'a') + gzip.compress(b'b'), 'x.tar.gz'))

    def test_path_escape_rejected_before_writing(self):
        for name in ('../../escape', '/absolute', 'x/../escape', 'x//alias'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'path-escape-or-alias'):
                self.scan([(name, b'never written')])
        self.assertEqual(list((self.output / 'text').iterdir()), [])

    def test_duplicate_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate-or-entry-budget'):
            self.scan([('x', b'a'), ('./x', b'b')])

    def test_fifo_rejected(self):
        with self.assertRaisesRegex(ValueError, 'device-fifo'):
            self.scan([('pipe', (tarfile.FIFOTYPE, ''))])

    def test_links_recorded_without_filesystem_creation(self):
        result = self.scan([('usr/lib/libx.so', (tarfile.SYMTYPE, '/outside/or/inside'))])
        self.assertEqual(result['entries'][0]['target'], '/outside/or/inside')
        self.assertFalse((self.output / 'usr').exists())

    def test_selected_text_only_and_no_executable_modes(self):
        result = self.scan([('usr/bin/tool', b'not executed'), ('usr/share/doc/tool/copyright', b'MIT\n'),
                            ('usr/lib/pkgconfig/tool.pc', b'Libs: -ltool\n')])
        self.assertEqual(len(list((self.output / 'text').iterdir())), 2)
        self.assertNotIn('review_text_path', result['entries'][0])
        self.assertTrue(all(path.stat().st_mode & 0o111 == 0 for path in (self.output / 'text').iterdir()))

    def test_expanded_budget_stops(self):
        with patch.dict(REVIEW.LIMITS, total_expanded_bytes=1000), self.assertRaisesRegex(ValueError, 'expanded-byte-budget'):
            self.scan([('file', b'x' * 2000)])

    def test_selected_budget_stops(self):
        with patch.dict(REVIEW.LIMITS, total_selected_bytes=2), self.assertRaisesRegex(ValueError, 'total-selected-budget'):
            self.scan([('usr/share/doc/tool/copyright', b'MIT\n')])

    def test_individual_selected_budget_stops_before_write(self):
        with patch.dict(REVIEW.LIMITS, selected_text_bytes=2), self.assertRaisesRegex(ValueError, 'selected-text-budget'):
            self.scan([('pkg/debian/patches/fix.diff', b'patch')], source=True)
        self.assertEqual(list((self.output / 'text').iterdir()), [])

    def test_source_patch_and_copyright_selected(self):
        result = self.scan([('pkg/debian/copyright', b'copyright'), ('pkg/debian/patches/series', b'fix.patch\n'),
                            ('pkg/debian/patches/fix.patch', b'patch'), ('pkg/main.c', b'code')], source=True)
        self.assertEqual(sum('review_text_path' in row for row in result['entries']), 3)

    def test_ar_bad_padding_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ar-padding'):
            list(REVIEW.ar_members(ar([('file', b'x')])[:-1] + b'!'))

    def test_source_diff_is_text_not_tar_and_not_applied(self):
        raw = b'--- pkg.orig/file\n+++ pkg/file\n@@ -1 +1 @@\n-old\n+new\n'
        result = REVIEW.scan_diff(gzip.compress(raw), 'x.diff.gz', self.budget, self.output)
        self.assertFalse(result['patch_applied'])
        self.assertEqual((ROOT / result['review_text_path']).read_bytes(), raw)
        self.assertFalse((self.output / 'pkg').exists())

    def test_source_diff_invalid_or_over_budget_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source-diff-format'):
            REVIEW.scan_diff(gzip.compress(b'invalid'), 'x.diff.gz', self.budget, self.output)
        with patch.dict(REVIEW.LIMITS, selected_text_bytes=2), self.assertRaisesRegex(ValueError, 'selected-text-budget'):
            REVIEW.scan_diff(gzip.compress(b'--- large'), 'x.diff.gz', self.budget, self.output)
        self.assertEqual(list((self.output / 'text').iterdir()), [])

    def test_elf_header_and_static_members(self):
        header = b'\x7fELF\x02\x01\x01' + bytes(9) + b'\x01\x00\xb7\x00' + bytes(44)
        result = REVIEW.static_members(ar([('/', b'symbols'), ('obj.o/', header)]))
        self.assertEqual(result['elf_header_counts'], {'64:little:183:1': 1})
        self.assertEqual(result['non_elf_members'], [])

    def test_a_suffix_can_be_relocatable_elf_not_ar(self):
        header = b'\x7fELF\x02\x01\x01' + bytes(9) + b'\x01\x00\xb7\x00' + bytes(44)
        result = REVIEW.static_members(header)
        self.assertEqual(result['container'], 'elf-relocatable-with-a-suffix')
        self.assertEqual(result['elf_header_counts'], {'64:little:183:1': 1})

    def test_a_suffix_executable_and_unknown_bytes_rejected(self):
        header = b'\x7fELF\x02\x01\x01' + bytes(9) + b'\x02\x00\xb7\x00' + bytes(44)
        with self.assertRaisesRegex(ValueError, 'non-relocatable'):
            REVIEW.static_members(header)
        with self.assertRaisesRegex(ValueError, 'ar-magic'):
            REVIEW.static_members(b'unknown-format')

    def test_control_field_mismatch_stops(self):
        control = lzma.compress(tar([('control', b'Package: synthetic\nVersion: 1\nArchitecture: arm64\n')]))
        payload = lzma.compress(tar([('usr/share/doc/synthetic/copyright', b'MIT')]))
        package = ar([('debian-binary', b'2.0\n'), ('control.tar.xz', control), ('data.tar.xz', payload)])
        with self.assertRaisesRegex(ValueError, 'control-index-mismatch:Version'):
            REVIEW.deb(package, {'Package': 'synthetic', 'Version': '2', 'Architecture': 'arm64'}, self.budget, self.output)


class ResolutionTests(unittest.TestCase):
    def test_parent_link(self):
        index = {'doc/a': [{'kind': 'symlink', 'target': 'b', 'package': 'a'}],
                 'doc/b/copyright': [{'kind': 'file', 'package': 'b'}]}
        self.assertEqual(DERIVED.resolve(index, 'doc/a/copyright')['resolved_path'], 'doc/b/copyright')

    def test_absolute_virtual_link(self):
        index = {'x': [{'kind': 'symlink', 'target': '/y', 'package': 'a'}],
                 'y': [{'kind': 'file', 'package': 'b'}]}
        self.assertEqual(DERIVED.resolve(index, 'x')['status'], 'resolved')

    def test_hardlink_root_relative(self):
        index = {'a/x': [{'kind': 'hardlink', 'target': './b/y', 'package': 'a'}],
                 'b/y': [{'kind': 'file', 'package': 'b'}]}
        self.assertEqual(DERIVED.resolve(index, 'a/x')['resolved_path'], 'b/y')

    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            DERIVED.resolve({'x': [{'kind': 'symlink', 'target': 'x', 'package': 'a'}]}, 'x')

    def test_escape_rejected(self):
        with self.assertRaises(ValueError):
            DERIVED.resolve({'x': [{'kind': 'symlink', 'target': '../outside', 'package': 'a'}]}, 'x')

    def test_missing_is_not_success(self):
        self.assertEqual(DERIVED.resolve({}, 'missing')['status'], 'missing-or-not-file')


if __name__ == '__main__':
    unittest.main()
