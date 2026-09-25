#!/usr/bin/env python3
"""Synthetic announcement/link scope checks; no key identity acceptance or network."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('review', HERE / 'inspect-binutils-key-inputs.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PageTests(unittest.TestCase):
    def setUp(self):
        self.old = (b'<p>GNU Binutils 2.43 Released Nick Clifton</p>'
                    b'<a href="binqltbMeQqcS.bin">OpenPGP key</a>')
        self.current = (b'<p>GNU Binutils 2.44 Released Nick Clifton</p>'
                        b'0cdd76777a0dfd3dd3a63f215f030208ddb91c2361d2bcc02acec0f1c16b6a2e')

    def test_link_resolution(self):
        m.pages_link_key(self.old, self.current)

    def test_changed_host_or_attachment(self):
        for link in (b'https://example.invalid/binqltbMeQqcS.bin', b'wrong.bin'):
            with self.assertRaisesRegex(ValueError, 'no longer linked'):
                m.pages_link_key(self.old.replace(b'binqltbMeQqcS.bin', link), self.current)

    def test_missing_identity_or_digest(self):
        for old, current in ((self.old.replace(b'Nick Clifton', b'unknown'), self.current),
                             (self.old, self.current.replace(b'2.44', b'2.45')),
                             (self.old, self.current[:-64])):
            with self.assertRaises(ValueError):
                m.pages_link_key(old, current)

    def test_bounds_and_encoding(self):
        for old in (b'', b'x' * 262145, b'\xff'):
            with self.assertRaises((ValueError, UnicodeError)):
                m.pages_link_key(old, self.current)


if __name__ == '__main__':
    unittest.main()
