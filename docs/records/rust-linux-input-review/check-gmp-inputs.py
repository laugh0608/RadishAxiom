#!/usr/bin/env python3
"""Synthetic GMP page, byte binding and fetch-scope checks; no network or upstream execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m', HERE / 'inspect-gmp-inputs.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.home = (b'<a href="download/gmp/gmp-6.3.0.tar.xz">archive</a> 2094196 bytes '
                     b'Fingerprint: 343C 2FF0 FBEE 5EC2 EDBE F399 F359 9FF8 28C6 7298')
        self.announcement = (b'<a href="https://gmplib.org/download/gmp/gmp-6.3.0.tar.xz">archive</a>'
                             b'<a href="https://gmplib.org/download/gmp/gmp-6.3.0.tar.xz.sig">signature</a>')

    def test_exact_page_links_and_declaration(self):
        self.assertEqual(set(m.pages(self.home, self.announcement)), {'identity', 'announcement'})

    def test_wrong_release_host_or_missing_signature(self):
        for bad in (self.announcement.replace(b'6.3.0', b'6.2.1'),
                    self.announcement.replace(b'gmplib.org', b'example.invalid'),
                    self.announcement.replace(b'.xz.sig', b'.xz')):
            with self.assertRaises(ValueError):
                m.pages(self.home, bad)

    def test_wrong_identity_size_encoding_or_bound(self):
        for bad in (self.home.replace(b'7298', b'7299'), self.home.replace(b'2094196', b'1870556'),
                    b'\xff', b'x' * 262145):
            with self.assertRaises((ValueError, UnicodeError)):
                m.pages(bad, self.announcement)

    def test_archive_identity_recipe_and_tamper(self):
        raw = b'synthetic archive'
        with patch.object(m, 'ARCHIVE', m.identity(raw)), \
                patch.object(m, 'RECIPE_SHA1', hashlib.sha1(raw).hexdigest()):
            self.assertTrue(m.archive_binding(raw)['strong_digest_is_local_observation_not_authentication'])
            with self.assertRaisesRegex(ValueError, 'archive changed'):
                m.archive_binding(raw + b'x')
        with patch.object(m, 'ARCHIVE', m.identity(raw)), self.assertRaisesRegex(ValueError, 'SHA-1'):
            m.archive_binding(raw)


class FetchScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        p = patch.object(m.route, 'DIRECTORY', self.directory)
        p.start()
        self.addCleanup(p.stop)
        (self.directory / 'fetch-plan.json').write_text(json.dumps(m.route.plan()))

    def test_reviewed_scope_exact_order_and_single_attempt(self):
        with patch.object(m.route.fetch, 'fetch', return_value=0) as fetch:
            self.assertEqual(m.route.execute(), 0)
        self.assertEqual([call.args for call in fetch.call_args_list], [(name, 1) for name in m.route.TARGETS])

    def test_first_failure_stops_without_fallback(self):
        with patch.object(m.route.fetch, 'fetch', side_effect=[0, 1]) as fetch:
            self.assertEqual(m.route.execute(), 1)
        self.assertEqual(fetch.call_count, 2)

    def test_plan_change_refused_before_request(self):
        (self.directory / 'fetch-plan.json').write_text('{}')
        with patch.object(m.route.fetch, 'fetch') as fetch, self.assertRaises(ValueError):
            m.route.execute()
        fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
