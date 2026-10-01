#!/usr/bin/env python3
"""Synthetic digest-binding boundaries; no network, GnuPG or upstream execution."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('binutils', HERE / 'inspect-binutils-inputs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.raw = b'synthetic archive bytes'
        self.digest = hashlib.sha256(self.raw).hexdigest()
        self.line = (self.digest + '  binutils-2.44.tar.gz\n').encode()
        self.page = b'<html><pre>\n' + self.line + b'</pre></html>'

    def test_exact_filename_among_variants(self):
        other = self.line.replace(b'binutils-2.44', b'binutils-with-gold-2.44')
        self.assertEqual(module.announcement_digest(b'<pre>\n' + other + self.line + b'</pre>'), self.digest)

    def test_missing_ambiguous_and_different_format(self):
        for raw in (b'<pre>empty</pre>', self.line * 2, self.line.replace(b'.tar.gz', b'.tar.xz'),
                    self.line.replace(b'.tar.gz', b'.tar.gz.sig')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                module.announcement_digest(raw)

    def test_announcement_bound_and_encoding(self):
        for raw in (b'x' * 262145, b'\xff', b''):
            with self.assertRaises((ValueError, UnicodeError)):
                module.announcement_digest(raw)

    def test_archive_binding_and_tampering(self):
        with patch.object(module, 'ARCHIVE', module.identity(self.raw)), \
                patch.object(module, 'RECIPE_SHA1', hashlib.sha1(self.raw).hexdigest()):
            self.assertEqual(module.archive_identity(self.raw, self.page), module.identity(self.raw))
            for raw in (self.raw[:-1], self.raw[:-1] + b'X'):
                with self.assertRaisesRegex(ValueError, 'archive'):
                    module.archive_identity(raw, self.page)
            with self.assertRaisesRegex(ValueError, 'announcement SHA-256'):
                module.archive_identity(self.raw, self.page.replace(self.digest.encode(), b'0' * 64))

    def test_recipe_disagreement(self):
        with patch.object(module, 'ARCHIVE', module.identity(self.raw)), \
                patch.object(module, 'RECIPE_SHA1', '0' * 40), self.assertRaisesRegex(ValueError, 'recipe SHA-1'):
            module.archive_identity(self.raw, self.page)


if __name__ == '__main__':
    unittest.main()
