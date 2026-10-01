#!/usr/bin/env python3
"""Synthetic bounded archive and fixed-source request checks; no real network."""
import bz2
import importlib.util
import io
import json
import lzma
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m', HERE / 'inspect-gmp-tool-source.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name, kind, body in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(body)
            tar.addfile(member, io.BytesIO(body))
    return stream.getvalue()


class ArchiveChecks(unittest.TestCase):
    def setUp(self):
        self.raw = archive([('debian/test', tarfile.REGTYPE, b'synthetic\n')])

    def test_both_compressions_preserve_exact_text(self):
        for method, data in [('bz2', bz2.compress(self.raw)), ('xz', lzma.compress(self.raw))]:
            report, texts = m.inventory(data, method, 'debian')
            self.assertEqual(texts, {'test': 'synthetic\n'})
            self.assertEqual(report['tar'], m.identity(self.raw))

    def test_truncated_concatenated_and_trailing_streams(self):
        for method, data in [('bz2', bz2.compress(self.raw)), ('xz', lzma.compress(self.raw))]:
            for bad in [data[:-1], data + data, data + b'x']:
                with self.assertRaises(ValueError):
                    m.inventory(bad, method, 'debian')

    def test_paths_duplicates_links_and_specials_rejected(self):
        cases = [[('debian/../escape', tarfile.REGTYPE, b'x')],
                 [('/debian/absolute', tarfile.REGTYPE, b'x')],
                 [('debian/a', tarfile.REGTYPE, b'x')] * 2,
                 [('debian/a', tarfile.SYMTYPE, b'')],
                 [('debian/a', tarfile.LNKTYPE, b'')],
                 [('debian/a', tarfile.FIFOTYPE, b'')],
                 [('debian/a', tarfile.REGTYPE, b'x'), ('debian/a/b', tarfile.REGTYPE, b'y')]]
        for entries in cases:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                m.inventory(bz2.compress(archive(entries)), 'bz2', 'debian')

    def test_all_resource_limits(self):
        for key, value in [('compressed', 1), ('tar', 512), ('member', 1), ('members', 0)]:
            with patch.dict(m.LIMITS, {key: value}), self.assertRaises(ValueError):
                m.inventory(bz2.compress(self.raw), 'bz2', 'debian')

    def test_nonzero_tail_and_directory_payload(self):
        for raw in [self.raw + b'x' * 512, archive([('debian/a', tarfile.DIRTYPE, b'x')])]:
            with self.assertRaises(ValueError):
                m.inventory(bz2.compress(raw), 'bz2', 'debian')


class FetchChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve() / 'batch'
        handle = patch.object(m.route, 'DIRECTORY', self.directory)
        handle.start()
        self.addCleanup(handle.stop)
        self.rows = [{'name': str(i), 'url': 'https://example.invalid/' + str(i), **m.identity(b'fixed')}
                     for i in range(4)]
        handle = patch.object(m.route, 'plan', return_value={'targets': self.rows})
        handle.start()
        self.addCleanup(handle.stop)

    def fake(self, name, attempt, body=b'fixed', code=0):
        self.assertEqual(attempt, 1)
        stem = self.directory / (name + '-attempt-1')
        Path(str(stem) + '.json').write_text('{}')
        Path(str(stem) + '.body').write_bytes(body)
        return code

    def test_each_request_once_and_no_reentry(self):
        with patch.object(m.route.fetch, 'fetch', side_effect=self.fake) as fetch:
            self.assertEqual(m.route.execute(), 0)
            self.assertEqual([c.args for c in fetch.call_args_list], [(str(i), 1) for i in range(4)])
            with self.assertRaises(FileExistsError):
                m.route.execute()
            self.assertEqual(fetch.call_count, 4)

    def test_transport_failure_stops(self):
        with patch.object(m.route.fetch, 'fetch', side_effect=lambda n, a: self.fake(n, a, code=1)) as fetch:
            self.assertEqual(m.route.execute(), 1)
            self.assertEqual(fetch.call_count, 1)
        self.assertFalse(json.loads((self.directory / 'fetch-result.json').read_bytes())['passed'])

    def test_successful_transport_with_wrong_bytes_stops(self):
        with patch.object(m.route.fetch, 'fetch', side_effect=lambda n, a: self.fake(n, a, body=b'wrong')) as fetch:
            self.assertEqual(m.route.execute(), 1)
            self.assertEqual(fetch.call_count, 1)
        report = json.loads((self.directory / 'fetch-result.json').read_bytes())
        self.assertFalse(report['invocations'][0]['source_index_bytes_match'])


if __name__ == '__main__':
    unittest.main()
