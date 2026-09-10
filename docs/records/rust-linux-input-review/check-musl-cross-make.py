#!/usr/bin/env python3
"""Synthetic archive rejection checks; does not run upstream build tools."""
import gzip
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('musl_source', HERE / 'inspect-musl-cross-make.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def fixture(entries, comment=source.COMMIT, tail=False):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w', format=tarfile.PAX_FORMAT,
                      pax_headers={'comment': comment}) as tar:
        for name, kind in entries:
            member = tarfile.TarInfo(source.TOP + '/' + name)
            member.type = kind
            data = b'synthetic\n' if kind == tarfile.REGTYPE else b''
            member.size = len(data)
            if kind == tarfile.SYMTYPE:
                member.linkname = '/outside'
            tar.addfile(member, io.BytesIO(data))
    raw = out.getvalue()
    if tail:
        raw = raw[:-1] + b'X'
    return gzip.compress(raw, mtime=0)


class ArchiveChecks(unittest.TestCase):
    def inspect(self, data, digest=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.tar.gz'
            path.write_bytes(data)
            return source.inspect(path, digest or hashlib.sha256(data).hexdigest())

    def test_observation_does_not_authenticate_commit(self):
        result = self.inspect(fixture([('Makefile', tarfile.REGTYPE)]))
        self.assertEqual(result['commit_authentication'], 'not-assessed')
        self.assertEqual(result['acceptance'], 'not-assessed')
        self.assertEqual(result['files'][0]['bytes'], 10)

    def test_path_escape(self):
        with self.assertRaisesRegex(ValueError, 'noncanonical'):
            self.inspect(fixture([('../outside', tarfile.REGTYPE)]))

    def test_link(self):
        with self.assertRaisesRegex(ValueError, 'linked'):
            self.inspect(fixture([('link', tarfile.SYMTYPE)]))

    def test_duplicate(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.inspect(fixture([('x', tarfile.REGTYPE)] * 2))

    def test_hash_before_decompression(self):
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.inspect(b'not gzip', '0' * 64)

    def test_decompression_limit(self):
        with patch.dict(source.LIMITS, {'tar': 64}):
            with self.assertRaisesRegex(ValueError, 'tar size limit'):
                self.inspect(fixture([('x', tarfile.REGTYPE)]))

    def test_commit_comment(self):
        with self.assertRaisesRegex(ValueError, 'commit comment mismatch'):
            self.inspect(fixture([('x', tarfile.REGTYPE)], comment='0' * 40))

    def test_nonzero_tail(self):
        with self.assertRaisesRegex(ValueError, 'nonzero tar tail'):
            self.inspect(fixture([('x', tarfile.REGTYPE)], tail=True))


if __name__ == '__main__':
    unittest.main()
