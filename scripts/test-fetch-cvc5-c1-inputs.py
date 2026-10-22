#!/usr/bin/env python3
"""Synthetic network-free checks for the authorized first-error-stop fetcher."""
import hashlib
import importlib.util
import io
from email.message import Message
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fetch', ROOT / 'scripts/fetch-cvc5-c1-inputs.py')
FETCH = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FETCH)


class Response(io.BytesIO):
    def __init__(self, body, url, **fields):
        super().__init__(body)
        self.status, self.url, self.headers = 200, url, Message()
        for key, value in fields.items():
            self.headers[key.replace('_', '-')] = str(value)

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response):
        self.response, self.calls = response, 0

    def open(self, *args, **kwargs):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-fetch-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.raw = b'synthetic-download\n'
        self.row = {'url': FETCH.PREP.BASE + 'pool/main/s/synthetic/input.deb',
                    'relative_path': 'inputs/pool/main/s/synthetic/input.deb',
                    'declared_bytes': len(self.raw), 'declared_sha256': hashlib.sha256(self.raw).hexdigest()}
        self.observation = {'requested_url': self.row['url'], 'redirects': [], 'bytes': 0}
        self.budget = {'received': 0, 'limit': 1000}
        self.events = []

    def run_one(self, response):
        opener = Opener(response)
        with patch.object(FETCH.urllib.request, 'build_opener', return_value=opener):
            FETCH.fetch_one(self.row, self.root, self.observation, self.budget, self.events.append, 10)
        return opener

    def test_exact_bytes(self):
        self.run_one(Response(self.raw, self.row['url'], Content_Length=len(self.raw)))
        self.assertEqual((self.root / self.row['relative_path']).read_bytes(), self.raw)
        self.assertEqual(self.observation['sha256'], self.row['declared_sha256'])

    def test_no_content_length(self):
        self.run_one(Response(self.raw, self.row['url']))
        self.assertEqual(self.observation['bytes'], len(self.raw))

    def test_exact_total_limit(self):
        self.budget['limit'] = len(self.raw)
        self.run_one(Response(self.raw, self.row['url'], Content_Length=len(self.raw)))
        self.assertEqual(self.budget['received'], len(self.raw))

    def test_truncated_preserved(self):
        with self.assertRaisesRegex(ValueError, 'size-mismatch'):
            self.run_one(Response(self.raw[:-1], self.row['url'], Content_Length=len(self.raw)))
        self.assertEqual((self.root / self.row['relative_path']).read_bytes(), self.raw[:-1])

    def test_overflow_stops_and_preserves(self):
        with self.assertRaisesRegex(ValueError, 'size-overflow'):
            self.run_one(Response(self.raw + b'extra', self.row['url']))
        self.assertEqual(self.observation['bytes'], len(self.raw) + 1)

    def test_total_ceiling_never_reads_extra_byte(self):
        self.budget['limit'] = len(self.raw)
        with self.assertRaisesRegex(ValueError, 'body-budget-before-established-eof'):
            self.run_one(Response(self.raw + b'extra', self.row['url']))
        self.assertEqual(self.budget['received'], len(self.raw))

    def test_same_length_corruption(self):
        with self.assertRaisesRegex(ValueError, 'sha256-mismatch'):
            self.run_one(Response(b'x' * len(self.raw), self.row['url']))

    def test_wrong_content_length_before_file_write(self):
        with self.assertRaisesRegex(ValueError, 'content-length-mismatch'):
            self.run_one(Response(self.raw, self.row['url'], Content_Length=len(self.raw) + 1))
        self.assertFalse((self.root / self.row['relative_path']).exists())

    def test_compressed_response_rejected(self):
        with self.assertRaisesRegex(ValueError, 'content-encoding'):
            self.run_one(Response(self.raw, self.row['url'], Content_Encoding='gzip'))

    def test_duplicate_header_rejected(self):
        response = Response(self.raw, self.row['url'], Content_Length=len(self.raw))
        response.headers['Content-Length'] = str(len(self.raw))
        with self.assertRaisesRegex(ValueError, 'duplicate-response-header'):
            self.run_one(response)

    def test_overwrite_rejected(self):
        path = self.root / self.row['relative_path']
        path.parent.mkdir(parents=True)
        path.write_bytes(b'prior')
        with self.assertRaisesRegex(ValueError, 'already-exists'):
            self.run_one(Response(self.raw, self.row['url']))
        self.assertEqual(path.read_bytes(), b'prior')

    def test_first_network_error_no_later_requests(self):
        opener = Opener(urllib.error.URLError(OSError(1, 'synthetic forbidden')))
        journal = FETCH.Journal(self.root / 'events.jsonl', 1024 * 1024)
        self.addCleanup(journal.close)
        plan = {'entries': [self.row, dict(self.row, relative_path='inputs/second')],
                'transport_policy': {'batch_deadline_seconds': 30, 'per_item_deadline_seconds': 10,
                                     'response_body_byte_limit': 1000}}
        result = {'observations': [], 'matched_files': 0, 'matched_bytes': 0, 'download_complete': False}
        with patch.object(FETCH.urllib.request, 'build_opener', return_value=opener):
            with patch.object(FETCH.signal, 'setitimer'):
                with patch('builtins.print'):
                    FETCH.fetch_rows(plan, self.root, journal, result)
        self.assertEqual(opener.calls, 1)
        self.assertEqual(len(result['observations']), 1)
        self.assertEqual(result['matched_files'], 0)
        self.assertEqual(result['failure']['index'], 1)
        self.assertFalse(result['download_complete'])

    def test_error_details_do_not_echo_proxy_credentials(self):
        error = urllib.error.URLError('https://user:secret@example.invalid')
        self.assertNotIn('secret', str(FETCH.error_info(error)))


class RedirectTests(unittest.TestCase):
    def test_allowed_content_address(self):
        FETCH.allowed_redirect('https://snapshot.debian.org/file/' + 'a' * 40 + '/pkg_1+2_arm64.deb')

    def test_observed_encoded_plus_filename(self):
        FETCH.allowed_redirect('https://snapshot.debian.org/file/9daaa738e73c3098c4958feb6b2f3849f56b687f/bash_5.2.15-2%2Bb2_arm64.deb')

    def test_encoded_separator_and_double_encoding_rejected(self):
        for name in ('pkg%2Felse', '%2E%2E', 'pkg%252B1', 'pkg%00name', 'pkg%3Fq', 'pkg%23frag'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                FETCH.allowed_redirect('https://snapshot.debian.org/file/' + 'a' * 40 + '/' + name)

    def test_outside_scope(self):
        for url in ('http://snapshot.debian.org/file/' + 'a' * 40 + '/pkg',
                    'https://example.invalid/file/' + 'a' * 40 + '/pkg',
                    'https://snapshot.debian.org:443/file/' + 'a' * 40 + '/pkg',
                    'https://snapshot.debian.org/file/' + 'a' * 40 + '/../pkg',
                    'https://snapshot.debian.org/file/' + 'a' * 40 + '/pkg?q=1',
                    'https://snapshot.debian.org/archive/debian/20230612T000000Z/other'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                FETCH.allowed_redirect(url)

    def test_redirect_does_not_read_body(self):
        observation = {'requested_url': FETCH.PREP.BASE + 'pool/main/a/a/a.deb', 'redirects': []}
        redirect = FETCH.Redirect(observation, lambda _: None)
        target = 'https://snapshot.debian.org/file/' + 'a' * 40 + '/a.deb'
        opener = Opener('synthetic-next-response')
        redirect.add_parent(opener)
        body = io.BytesIO(b'body-is-not-read')
        req = urllib.request.Request(observation['requested_url'])
        req.timeout = 5
        hdrs = Message(); hdrs['Location'] = target
        self.assertEqual(redirect.http_error_302(req, body, 302, 'Found', hdrs), 'synthetic-next-response')
        self.assertTrue(body.closed)
        self.assertEqual(len(observation['redirects']), 1)

    def test_loop_and_limit(self):
        target = 'https://snapshot.debian.org/file/' + 'a' * 40 + '/a.deb'
        for chain in ([{'to_url': target}], [{'to_url': target + str(i)} for i in range(5)]):
            observation = {'requested_url': FETCH.PREP.BASE + 'pool/main/a/a/a.deb', 'redirects': chain}
            redirect = FETCH.Redirect(observation, lambda _: None)
            req = urllib.request.Request(observation['requested_url']); req.timeout = 5
            hdrs = Message(); hdrs['Location'] = target
            with self.assertRaises(ValueError):
                redirect.http_error_302(req, io.BytesIO(), 302, 'Found', hdrs)


if __name__ == '__main__':
    unittest.main()
