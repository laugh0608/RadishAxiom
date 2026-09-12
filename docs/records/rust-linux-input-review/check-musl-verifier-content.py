#!/usr/bin/env python3
"""Synthetic archive and in-memory link boundary checks; no package execution."""
import importlib.util
import io
import lzma
from pathlib import Path
import tarfile
import unittest

spec = importlib.util.spec_from_file_location('content',
    Path(__file__).with_name('inspect-musl-verifier-content.py'))
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)


def archive(names=('file',), kind=tarfile.REGTYPE):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name in names:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = 3
                tar.addfile(member, io.BytesIO(b'abc'))
            elif kind == tarfile.SYMTYPE:
                member.linkname = '../escape'
                tar.addfile(member)
            else:
                tar.addfile(member)
    return stream.getvalue()


class Boundaries(unittest.TestCase):
    def test_regular_bytes(self):
        rows, files = content.read_tar(lzma.compress(archive()), 65536)
        self.assertEqual(files, {'file': b'abc'})
        self.assertEqual(rows['members'][0]['bytes'], 3)

    def test_compression_boundaries(self):
        packed = lzma.compress(archive())
        for data, limit in [(packed[:-1], 65536), (packed + packed, 65536),
                            (packed, 100), (packed + b'x', 65536)]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                content.read_tar(data, limit)

    def test_paths_duplicates_and_special_files(self):
        for raw in [archive(('../outside',)), archive(('/absolute',)),
                    archive(('file', 'file')), archive(kind=tarfile.FIFOTYPE),
                    archive(kind=tarfile.SYMTYPE), archive(('file', 'file/child'))]:
            with self.subTest(raw=raw[:100]), self.assertRaises(ValueError):
                content.read_tar(lzma.compress(raw), 65536)

    def test_tar_trailing_content(self):
        raw = archive()
        for changed in [raw + b'X' * 512, raw[:1024] + bytes(512)]:
            with self.assertRaises(ValueError):
                content.read_tar(lzma.compress(changed), 65536)

    def test_link_target_containment(self):
        self.assertEqual(content.link_destination('usr/lib/a', '../lib/b'), 'usr/lib/b')
        self.assertEqual(content.link_destination('usr/lib/a', '/usr/lib/b'), 'usr/lib/b')
        self.assertEqual(content.link_destination('usr/lib/a', 'usr/lib/b', True), 'usr/lib/b')
        for target in ['../../../escape', '', '/../../escape']:
            with self.assertRaises(ValueError):
                content.link_destination('usr/lib/a', target)

    def test_cross_package_directory_link(self):
        index = {'usr': {'type': 'directory'}, 'usr/share': {'type': 'directory'},
                 'usr/share/base': {'type': 'directory'},
                 'usr/share/base/copyright': {'type': 'file', 'packages': ['base'], 'bytes': 3},
                 'usr/share/tool': {'type': 'symlink', 'destination': 'usr/share/base'}}
        self.assertEqual(content.resolve(index, 'usr/share/tool/copyright')['path'],
                         'usr/share/base/copyright')
        self.assertEqual(content.resolve(index, '/lib/loader')['missing_component'], 'lib')

    def test_cycle_and_non_directory_rejected(self):
        with self.assertRaises(ValueError):
            content.resolve({'a': {'type': 'symlink', 'destination': 'b'},
                             'b': {'type': 'symlink', 'destination': 'a'}}, 'a')
        with self.assertRaises(ValueError):
            content.resolve({'a': {'type': 'file'}}, 'a/b')

    def test_static_candidate_reports_unresolved(self):
        rows = [{'path': name, 'bytes': 1, 'sha256': 'a' * 64, 'packages': ['test'],
                 'library_path_candidates': {'libmissing': {'status': 'missing'}}}
                for name in ['usr/bin/gpg', 'usr/bin/gpgconf']]
        result = content.root_candidates(rows)
        self.assertEqual(result['file_count'], 2)
        self.assertEqual(len(result['unresolved_needed']), 2)
        self.assertFalse(result['loader_resolution_assessed'])


if __name__ == '__main__':
    unittest.main()
