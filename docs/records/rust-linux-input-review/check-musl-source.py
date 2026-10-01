#!/usr/bin/env python3
"""Synthetic rejection checks for musl source, signature and patch diagnostics."""
import gzip
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


source = load('inspect-musl-source')
patches = load('inspect-musl-patches')
verify = load('verify-musl-source')


def status(fingerprint=verify.FINGERPRINT, digest='8'):
    return f'[GNUPG:] VALIDSIG {fingerprint} 2024-03-01 1709258940 0 4 0 1 {digest} 00 {fingerprint}\n'


class DiagnosticChecks(unittest.TestCase):
    def test_source_pin_before_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.gz'
            path.write_bytes(b'not gzip')
            with self.assertRaisesRegex(ValueError, 'pinned source archive'):
                source.inspect(path)

    def test_patch_path_escape(self):
        for line in ['+++ b/../../outside', '+++ /outside', '+++ b/src/locale/iconv.c extra',
                     '+++ b/src/unexpected.c']:
            with self.subTest(line=line), self.assertRaises(ValueError):
                patches.path_from_header(line)

    def test_patch_delete_and_rename(self):
        for target in ['/dev/null', 'b/src/stdlib/qsort.c']:
            data = f'--- a/src/locale/iconv.c\n+++ {target}\n@@ -1 +1 @@\n-x\n+y\n'.encode()
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'deletion or rename'):
                patches.inspect(data)

    def test_valid_signature_status(self):
        self.assertTrue(verify.valid_signature(status()))

    def test_bad_signature_status(self):
        cases = ['', status('0' * 40), status(digest='2'), status() + status(),
                 status() + '[GNUPG:] BADSIG rejected\n',
                 status() + '[GNUPG:] EXPKEYSIG expired\n',
                 '[GNUPG:] VALIDSIG incomplete\n']
        for value in cases:
            with self.subTest(value=value):
                self.assertFalse(verify.valid_signature(value))

    def test_original_source_body_binding(self):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w') as tar:
            member = tarfile.TarInfo('musl-1.2.5/src/locale/iconv.c')
            member.size = 7
            tar.addfile(member, io.BytesIO(b'altered'))
        with self.assertRaisesRegex(ValueError, 'selected source digest mismatch'):
            verify.original_files(gzip.compress(out.getvalue()))

    def test_unexpected_patch_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'unexpected').write_text('synthetic')
            with self.assertRaisesRegex(ValueError, 'unexpected patch result path'):
                verify.inventory(root)

    def test_linked_patch_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'link').symlink_to('/synthetic-outside')
            with self.assertRaisesRegex(ValueError, 'link in patch result'):
                verify.inventory(root)


if __name__ == '__main__':
    unittest.main()
