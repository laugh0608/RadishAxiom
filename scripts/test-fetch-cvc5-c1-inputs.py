#!/usr/bin/env python3
"""Synthetic network-free checks for the authorized first-error-stop fetcher."""
import hashlib
import copy
import importlib.util
import io
import json
from email.message import Message
from pathlib import Path
import tempfile
import time
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

    def test_continuation_skips_retained_and_stops_at_first_error(self):
        rows = [dict(self.row, relative_path='inputs/file' + str(i)) for i in range(8)]
        plan = {'entries': rows, 'transport_policy': {'batch_deadline_seconds': 30,
                'per_item_deadline_seconds': 10, 'response_body_byte_limit': len(self.raw) * 8}}
        journal = FETCH.Journal(self.root / 'events.jsonl', 1024 * 1024)
        self.addCleanup(journal.close)
        result = {'observations': [], 'matched_files': 6, 'matched_bytes': len(self.raw) * 6,
                  'download_complete': False}
        observed = 'https://snapshot.debian.org/file/' + 'a' * 40 + '/file6'
        with patch.object(FETCH, 'fetch_one', side_effect=ValueError('synthetic-failure')) as fetch:
            with patch.object(FETCH.signal, 'setitimer'), patch('builtins.print'):
                FETCH.fetch_rows(plan, self.root, journal, result, 7, observed)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args[0]['url'], observed)
        self.assertEqual(fetch.call_args.args[3]['limit'], len(self.raw) * 2)
        self.assertEqual(result['failure']['index'], 7)
        self.assertEqual(result['matched_files'], 6)
        self.assertEqual(rows[6]['url'], self.row['url'])
        self.assertEqual(result['observations'][0]['planned_url'], self.row['url'])

    def continuation_fixture(self):
        rows = [dict(self.row, relative_path='inputs/pool/main/s/synthetic/file' + str(i)) for i in range(8)]
        for row in rows[:6]:
            path = self.root / row['relative_path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.raw)
        failed = {'requested_url': rows[6]['url'], 'relative_path': rows[6]['relative_path'],
                  'bytes': 0, 'status': 'failed', 'rejected_redirect': {'status': 302,
                  'from_url': rows[6]['url'], 'location': '/file/' + 'a' * 40 + '/file6'}}
        prior = {'matched_files': 6, 'matched_bytes': 239168, 'failure': {'index': 7},
                 'observations': [{}] * 6 + [failed]}
        (self.root / 'result.json').write_text(json.dumps(prior))
        expected = {'result.json': hashlib.sha256((self.root / 'result.json').read_bytes()).hexdigest()}
        return {'entries': rows}, expected, prior

    def test_continuation_preflight_six_only(self):
        plan, expected, _ = self.continuation_fixture()
        with patch.object(FETCH, 'ORIGINAL_RECORDS', expected):
            target, record = FETCH.continuation_preflight(plan, self.root)
        self.assertTrue(target.endswith('/file6'))
        self.assertEqual(record['retained_readback']['matched_files'], 6)

    def test_continuation_rejects_original_record_drift(self):
        plan, expected, _ = self.continuation_fixture()
        with (self.root / 'result.json').open('a') as stream:
            stream.write(' ')
        with patch.object(FETCH, 'ORIGINAL_RECORDS', expected), self.assertRaisesRegex(ValueError, 'original-record-drift'):
            FETCH.continuation_preflight(plan, self.root)

    def test_continuation_rejects_existing_seventh_file(self):
        plan, expected, _ = self.continuation_fixture()
        (self.root / plan['entries'][6]['relative_path']).write_bytes(self.raw)
        with patch.object(FETCH, 'ORIGINAL_RECORDS', expected), self.assertRaisesRegex(ValueError, 'exact-six-retained'):
            FETCH.continuation_preflight(plan, self.root)

    def test_continuation_rejects_wrong_redirect_filename(self):
        plan, _, prior = self.continuation_fixture()
        prior['observations'][-1]['rejected_redirect']['location'] += '-other'
        raw = json.dumps(prior).encode()
        (self.root / 'result.json').write_bytes(raw)
        with patch.object(FETCH, 'ORIGINAL_RECORDS', {'result.json': hashlib.sha256(raw).hexdigest()}):
            with self.assertRaisesRegex(ValueError, 'filename-binding'):
                FETCH.continuation_preflight(plan, self.root)


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


class ContinuationClockTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch.object(FETCH.time, 'monotonic', return_value=0).start()
        self.addCleanup(patch.stopall)
        self.timer = patch.object(FETCH.signal, 'setitimer').start()
        self.deadlines = FETCH.ContinuationDeadlines(21600)
        self.deadlines.start_item(300)

    def test_headers_deadline(self):
        self.deadlines.start_headers()
        self.clock.return_value = 60
        with self.assertRaisesRegex(TimeoutError, '^headers-deadline$'):
            self.deadlines.arm()

    def test_body_idle_deadline(self):
        self.deadlines.start_headers()
        self.clock.return_value = 10
        self.deadlines.body_progress()
        self.clock.return_value = 70
        with self.assertRaisesRegex(TimeoutError, '^body-no-progress$'):
            self.deadlines.arm()

    def test_slow_progress_can_exceed_old_180_seconds(self):
        self.deadlines.start_headers()
        for value in (10, 60, 110, 160, 210, 260):
            self.clock.return_value = value
            self.deadlines.body_progress()
        self.assertEqual(self.deadlines.nearest(), (300, 'item-deadline'))
        self.clock.return_value = 300
        with self.assertRaisesRegex(TimeoutError, '^item-deadline$'):
            self.deadlines.arm()

    def test_late_data_cannot_reset_idle_timeout(self):
        self.deadlines.body_progress()
        self.clock.return_value = 61
        with self.assertRaisesRegex(TimeoutError, '^body-no-progress$'):
            self.deadlines.body_progress()

    def test_batch_bounds_preflight_and_final_audit(self):
        self.deadlines = FETCH.ContinuationDeadlines(20)
        self.clock.return_value = 20
        with self.assertRaisesRegex(TimeoutError, '^batch-deadline$'):
            self.deadlines.arm()

    def test_batch_wins_over_slow_item(self):
        self.clock.return_value = 21590
        self.deadlines.start_item(300)
        self.deadlines.start_headers()
        self.clock.return_value = 21600
        with self.assertRaisesRegex(TimeoutError, '^batch-deadline$'):
            self.deadlines.arm()

    def test_finish_does_not_reset_batch(self):
        self.clock.return_value = 200
        self.deadlines.finish_item()
        self.assertEqual(self.deadlines.nearest(), (21600, 'batch-deadline'))


class RangeResponse(Response):
    def __init__(self, body, url, **fields):
        super().__init__(body, url, **fields)
        self.status, self.read_calls = 206, 0

    def read1(self, size):
        self.read_calls += 1
        return super().read1(size)


class RangeFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-range-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.prefix, self.tail = b'synthetic-prefix-', b'and-tail\n'
        self.complete = self.prefix + self.tail
        self.source = self.root / 'old-partial.deb'
        self.source.write_bytes(self.prefix)
        self.partial = {'path': str(self.source.relative_to(ROOT)), 'bytes': len(self.prefix),
                        'sha256': hashlib.sha256(self.prefix).hexdigest()}
        self.path = self.root / 'new/inputs/pkg.deb'
        self.url = 'https://snapshot.debian.org/file/' + 'a' * 40 + '/pkg.deb'
        self.row = {'index': 41, 'request_url': self.url, 'planned_url': FETCH.PREP.BASE + 'pool/main/s/synthetic/pkg.deb',
                    'output_path': str(self.path.relative_to(ROOT)), 'request_headers': {'Accept-Encoding': 'identity',
                    'Range': f'bytes={len(self.prefix)}-{len(self.complete)-1}', 'If-Range': '"synthetic-etag"'},
                    'expected_status': 206, 'expected_content_range': f'bytes {len(self.prefix)}-{len(self.complete)-1}/{len(self.complete)}',
                    'network_body_bytes': len(self.tail), 'complete_bytes': len(self.complete),
                    'complete_sha256': hashlib.sha256(self.complete).hexdigest(), 'total_deadline_seconds': 300}
        self.observation = {'requested_url': self.url, 'redirects': [], 'range_request': True, 'bytes': 0, 'network_bytes': 0}
        self.budget = {'received': 0, 'limit': 1000}
        self.events = []
        self.timer = patch.object(FETCH.signal, 'setitimer')
        self.timer.start()
        self.addCleanup(self.timer.stop)
        self.deadlines = FETCH.ContinuationDeadlines(21600)
        self.deadlines.start_item(300)

    def response(self, body=None):
        return RangeResponse(self.tail if body is None else body, self.url, Content_Length=len(self.tail),
                             Content_Range=self.row['expected_content_range'], ETag='"synthetic-etag"')

    def run_one(self, response):
        opener = Opener(response)
        with patch.object(FETCH.urllib.request, 'build_opener', return_value=opener):
            FETCH.fetch_continuation_item(self.row, self.partial, self.observation, self.budget,
                                          self.events.append, self.deadlines)
        return opener

    def test_exact_range_assembles_without_touching_prefix(self):
        before = self.source.stat()
        response = self.response()
        self.run_one(response)
        self.assertEqual(self.path.read_bytes(), self.complete)
        self.assertEqual(self.source.read_bytes(), self.prefix)
        self.assertEqual(self.source.stat().st_ino, before.st_ino)
        self.assertEqual(self.source.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(self.budget['received'], len(self.tail))
        self.assertEqual(self.observation['sha256'], self.row['complete_sha256'])
        self.assertTrue(response.closed)

    def test_missing_etag_still_requires_complete_hash(self):
        response = self.response()
        del response.headers['ETag']
        self.run_one(response)
        self.assertEqual(self.path.read_bytes(), self.complete)

    def test_200_does_not_read_full_body_or_fallback(self):
        response = self.response(self.complete)
        response.status = 200
        with self.assertRaisesRegex(ValueError, 'unexpected-response-status'):
            self.run_one(response)
        self.assertEqual(response.read_calls, 0)
        self.assertEqual(self.path.read_bytes(), self.prefix)
        self.assertTrue(response.closed)

    def test_wrong_range_length_etag_encoding_or_framing_before_body(self):
        cases = [('Content-Range', 'bytes 0-8/26', 'content-range-mismatch'),
                 ('Content-Length', '999', 'content-length-mismatch'),
                 ('ETag', '"changed"', 'range-etag-mismatch'),
                 ('Content-Encoding', 'gzip', 'unexpected-content-encoding'),
                 ('Transfer-Encoding', 'chunked', 'conflicting-body-framing')]
        for index, (header, value, reason) in enumerate(cases):
            with self.subTest(header=header):
                self.row['output_path'] = str((self.root / f'new/inputs/case{index}').relative_to(ROOT))
                self.observation = dict(self.observation, bytes=0, network_bytes=0)
                response = self.response()
                del response.headers[header]
                response.headers[header] = value
                with self.assertRaisesRegex(ValueError, reason):
                    self.run_one(response)
                self.assertEqual(response.read_calls, 0)

    def test_duplicate_content_range_before_body(self):
        response = self.response()
        response.headers['Content-Range'] = self.row['expected_content_range']
        with self.assertRaisesRegex(ValueError, 'duplicate-response-header'):
            self.run_one(response)
        self.assertEqual(response.read_calls, 0)

    def test_range_requires_content_length(self):
        response = self.response()
        del response.headers['Content-Length']
        with self.assertRaisesRegex(ValueError, 'range-content-length-required'):
            self.run_one(response)
        self.assertEqual(response.read_calls, 0)

    def test_short_body_preserved_and_rejected(self):
        with self.assertRaisesRegex(ValueError, 'payload-size-mismatch'):
            self.run_one(self.response(self.tail[:-1]))
        self.assertEqual(self.path.read_bytes(), self.prefix + self.tail[:-1])

    def test_bad_full_digest_preserves_new_candidate(self):
        with self.assertRaisesRegex(ValueError, 'payload-sha256-mismatch'):
            self.run_one(self.response(b'x' * len(self.tail)))
        self.assertEqual(self.source.read_bytes(), self.prefix)

    def test_overflow_preserved_but_never_continued(self):
        with self.assertRaisesRegex(ValueError, 'payload-size-overflow'):
            self.run_one(self.response(self.tail + b'extra'))
        self.assertEqual(self.budget['received'], len(self.tail) + 1)

    def test_total_body_ceiling(self):
        self.budget['limit'] = len(self.tail)
        self.run_one(self.response())
        self.assertEqual(self.budget['received'], len(self.tail))

    def test_corrupted_prefix_fails_before_opener(self):
        self.source.write_bytes(b'x' * len(self.prefix))
        with patch.object(FETCH.urllib.request, 'build_opener') as opener:
            with self.assertRaisesRegex(ValueError, 'prefix-byte-mismatch'):
                FETCH.fetch_continuation_item(self.row, self.partial, self.observation, self.budget,
                                              self.events.append, self.deadlines)
        opener.assert_not_called()

    def test_existing_candidate_not_overwritten(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'old-candidate')
        with self.assertRaises(FileExistsError):
            self.run_one(self.response())
        self.assertEqual(self.path.read_bytes(), b'old-candidate')

    def test_range_redirect_closed_without_following(self):
        redirect = FETCH.Redirect(self.observation, self.events.append)
        opener = Opener('must-not-be-requested')
        redirect.add_parent(opener)
        req = urllib.request.Request(self.url); req.timeout = 60
        response = self.response()
        response.headers['Location'] = self.url + '-other'
        with self.assertRaisesRegex(ValueError, 'range-redirect-forbidden'):
            redirect.http_error_302(req, response, 302, 'Found', response.headers)
        self.assertEqual(opener.calls, 0)
        self.assertTrue(response.closed)

    def test_first_416_stops_no_request_42(self):
        second = dict(self.row, index=42)
        proposal = {'requests_detail': [self.row, second], 'retained_partial': self.partial,
                    'transport_policy': {'new_response_body_byte_limit': 1000}}
        result = {'observations': [], 'matched_files': 40, 'matched_bytes': 42872372, 'download_complete': False}
        journal = FETCH.Journal(self.root / 'events.jsonl', 1024 * 1024)
        self.addCleanup(journal.close)
        error = urllib.error.HTTPError(self.url, 416, 'synthetic', Message(), io.BytesIO(b'not-read'))
        opener = Opener(error)
        with patch.object(FETCH.urllib.request, 'build_opener', return_value=opener):
            FETCH.continuation2_rows(proposal, journal, result, self.deadlines)
        self.assertEqual(opener.calls, 1)
        self.assertEqual(result['failure']['index'], 41)
        self.assertEqual(result['failure']['http_status'], 416)
        self.assertEqual(result['matched_files'], 40)
        self.assertEqual([r['index'] for r in result['observations']], [41])
        self.assertTrue(error.closed)

    def test_first_digest_error_prevents_next_request(self):
        proposal = {'requests_detail': [self.row, dict(self.row, index=42)], 'retained_partial': self.partial,
                    'transport_policy': {'new_response_body_byte_limit': 1000}}
        result = {'observations': [], 'matched_files': 40, 'matched_bytes': 42872372, 'download_complete': False}
        journal = FETCH.Journal(self.root / 'events.jsonl', 1024 * 1024)
        self.addCleanup(journal.close)
        opener = Opener(self.response(b'x' * len(self.tail)))
        with patch.object(FETCH.urllib.request, 'build_opener', return_value=opener):
            FETCH.continuation2_rows(proposal, journal, result, self.deadlines)
        self.assertEqual(opener.calls, 1)
        self.assertEqual(result['failure']['reason'], 'payload-sha256-mismatch')

    def test_range_then_full_file_in_order_without_retained_requests(self):
        full = b'next-full-file\n'
        second = dict(self.row, index=42, request_url=self.row['planned_url'] + '-next',
                      planned_url=self.row['planned_url'] + '-next', expected_status=200,
                      output_path=str((self.path.parent / 'next.deb').relative_to(ROOT)),
                      request_headers={'Accept-Encoding': 'identity'}, expected_content_range=None,
                      network_body_bytes=len(full), complete_bytes=len(full),
                      complete_sha256=hashlib.sha256(full).hexdigest())
        responses = [self.response(), Response(full, second['request_url'], Content_Length=len(full))]
        seen = []
        def open_request(request, **kwargs):
            seen.append(request)
            return responses[len(seen) - 1]
        opener = Opener(None)
        opener.open = open_request
        proposal = {'requests_detail': [self.row, second], 'retained_partial': self.partial,
                    'transport_policy': {'new_response_body_byte_limit': len(self.tail) + len(full)}}
        result = {'observations': [], 'matched_files': 40, 'matched_bytes': 42872372,
                  'download_complete': False, 'failure': None}
        journal = FETCH.Journal(self.root / 'events.jsonl', 1024 * 1024)
        self.addCleanup(journal.close)
        with patch.object(FETCH.urllib.request, 'build_opener', return_value=opener), patch('builtins.print'):
            FETCH.continuation2_rows(proposal, journal, result, self.deadlines)
        self.assertEqual([req.full_url for req in seen], [self.url, second['request_url']])
        self.assertEqual(seen[0].get_header('Range'), self.row['request_headers']['Range'])
        self.assertEqual(seen[0].get_header('If-range'), '"synthetic-etag"')
        self.assertIsNone(seen[1].get_header('Range'))
        self.assertEqual(result['matched_files'], 42)
        self.assertEqual(result['response_body_bytes'], len(self.tail) + len(full))
        self.assertTrue(result['download_complete'])
        self.assertEqual((ROOT / second['output_path']).read_bytes(), full)
        self.assertEqual(self.source.read_bytes(), self.prefix)

    def test_progress_log_for_slow_data(self):
        clock = [0]
        response = self.response()
        read = response.read1
        def slow_read(size):
            clock[0] += 31
            return read(min(size, 3))
        response.read1 = slow_read
        with patch.object(FETCH.time, 'monotonic', side_effect=lambda: clock[0]):
            self.deadlines = FETCH.ContinuationDeadlines(21600)
            self.deadlines.start_item(300)
            self.run_one(response)
        progress = [e for e in self.events if e['event'] == 'body-progress']
        self.assertEqual(len(progress), 3)
        self.assertEqual(progress[-1]['network_bytes'], len(self.tail))

    def test_no_data_timeout_during_real_read_loop(self):
        clock = [0]
        response = self.response()
        def late_read(size):
            clock[0] = 61
            return b'x'
        response.read1 = late_read
        with patch.object(FETCH.time, 'monotonic', side_effect=lambda: clock[0]):
            self.deadlines = FETCH.ContinuationDeadlines(21600)
            self.deadlines.start_item(300)
            with self.assertRaisesRegex(TimeoutError, '^body-no-progress$'):
                self.run_one(response)
        self.assertEqual(self.source.read_bytes(), self.prefix)

    def test_journal_budget_is_enforced(self):
        journal = FETCH.Journal(self.root / 'small-journal.jsonl', 1)
        self.addCleanup(journal.close)
        with self.assertRaisesRegex(ValueError, 'journal-byte-budget'):
            journal.append({'event': 'body-progress'})
        self.assertEqual(journal.bytes, 0)


class ContinuationBindingTests(unittest.TestCase):
    def setUp(self):
        self.proposal = json.loads(FETCH.CONTINUATION_PLAN.read_bytes())
        self.plan = json.loads(FETCH.PREP.PLAN.read_bytes())

    def test_exact_proposal_bindings(self):
        FETCH.continuation2_bindings(self.proposal, self.plan)

    def test_duplicate_missing_or_reordered_indices(self):
        for kind in ('duplicate', 'missing', 'reorder'):
            p = copy.deepcopy(self.proposal)
            if kind == 'duplicate':
                p['requests_detail'][1]['index'] = 41
            elif kind == 'missing':
                p['requests_detail'].pop()
            else:
                p['requests_detail'][1:3] = reversed(p['requests_detail'][1:3])
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'request-index-binding'):
                FETCH.continuation2_bindings(p, self.plan)

    def test_output_cannot_replace_original_partial(self):
        self.proposal['requests_detail'][0]['output_path'] = self.proposal['retained_partial']['path']
        with self.assertRaisesRegex(ValueError, 'request-input-binding'):
            FETCH.continuation2_bindings(self.proposal, self.plan)

    def test_retained_complete_path_cannot_be_remapped(self):
        self.proposal['retained_complete_files'][0]['path'] = self.proposal['retained_partial']['path']
        with self.assertRaisesRegex(ValueError, 'retained-input-binding'):
            FETCH.continuation2_bindings(self.proposal, self.plan)

    def test_plan_bytes_must_match_before_any_network(self):
        with patch.object(FETCH, 'CONTINUATION_SHA256', '0' * 64):
            with patch.object(FETCH.urllib.request, 'build_opener') as opener:
                with self.assertRaisesRegex(ValueError, 'continuation-plan-sha256-drift'):
                    FETCH.continuation2_preflight()
        opener.assert_not_called()

    def test_existing_continuation_directory_refused_before_network(self):
        with tempfile.TemporaryDirectory(prefix='cvc5-existing-test-', dir=ROOT / '.tmp') as temp:
            root = Path(temp).resolve()
            (root / self.proposal['new_directory']).mkdir(parents=True)
            with patch.object(FETCH, 'ROOT', root), patch.object(FETCH, 'continuation2_retained', return_value={}):
                with patch.object(FETCH.urllib.request, 'build_opener') as opener:
                    with self.assertRaisesRegex(ValueError, 'continuation-already-exists'):
                        FETCH.continuation2_preflight()
                opener.assert_not_called()


class ContinuationSignalTests(unittest.TestCase):
    def test_real_timer_interrupts_wait_and_restores_handlers(self):
        previous = FETCH.signal.getsignal(FETCH.signal.SIGALRM)
        with self.assertRaisesRegex(TimeoutError, '^batch-deadline$'):
            with FETCH.ContinuationDeadlines(0.03):
                time.sleep(0.2)
        self.assertEqual(FETCH.signal.getsignal(FETCH.signal.SIGALRM), previous)
        self.assertEqual(FETCH.signal.getitimer(FETCH.signal.ITIMER_REAL), (0.0, 0.0))

    def test_expired_enter_restores_handlers(self):
        previous = FETCH.signal.getsignal(FETCH.signal.SIGALRM)
        with self.assertRaisesRegex(TimeoutError, '^batch-deadline$'):
            with FETCH.ContinuationDeadlines(0):
                self.fail('expired context entered')
        self.assertEqual(FETCH.signal.getsignal(FETCH.signal.SIGALRM), previous)


class SplitInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-split-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.new = self.base / 'continuation-2'
        self.prefix = b'P' * 12582912
        self.plan = {'retention_directory': str(self.base.relative_to(ROOT)), 'entries': [], 'summary': {}}
        self.proposal = {'new_directory': str(self.new.relative_to(ROOT)), 'retained_complete_files': [],
                         'prior_records': [], 'requests_detail': []}
        for index in range(1, 501):
            raw = self.prefix + b'T' if index == 41 else b'S'
            relative = f'inputs/pool/main/s/synthetic/file{index}'
            row = {'relative_path': relative, 'url': FETCH.PREP.BASE + relative.removeprefix('inputs/'),
                   'declared_bytes': len(raw), 'declared_sha256': hashlib.sha256(raw).hexdigest()}
            self.plan['entries'].append(row)
            target = (self.base if index <= 40 else self.new) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            if index <= 40:
                self.proposal['retained_complete_files'].append({'index': index, **FETCH.identity(target)})
            else:
                size = len(raw) - (len(self.prefix) if index == 41 else 0)
                self.proposal['requests_detail'].append({'index': index, 'planned_url': row['url'],
                    'output_path': str(target.relative_to(ROOT)), 'complete_bytes': len(raw),
                    'complete_sha256': row['declared_sha256'], 'network_body_bytes': size,
                    'total_deadline_seconds': max(300, 120 + (size + 32767) // 32768)})
        partial = self.base / self.plan['entries'][40]['relative_path']
        partial.write_bytes(self.prefix)
        self.proposal['retained_partial'] = {'index': 41, **FETCH.identity(partial)}
        self.plan['summary']['total_bytes'] = sum(r['declared_bytes'] for r in self.plan['entries'])

    def test_split_inventory_uses_new_complete_file_and_keeps_old_partial(self):
        result = FETCH.continuation2_readback(self.proposal, self.plan)
        self.assertEqual(result['matched_files'], 500)
        self.assertFalse(result['old_partial_is_complete_input'])
        self.assertEqual(result['inventory'][40]['path'], self.proposal['requests_detail'][0]['output_path'])
        self.assertEqual((ROOT / self.proposal['retained_partial']['path']).read_bytes(), self.prefix)
        self.assertEqual(len({r['path'] for r in result['inventory']}), 500)

    def test_corrupt_new_complete_file_rejected(self):
        target = ROOT / self.proposal['requests_detail'][1]['output_path']
        target.write_bytes(b'X')
        with self.assertRaisesRegex(ValueError, 'input-digest-mismatch'):
            FETCH.continuation2_readback(self.proposal, self.plan)

    def test_missing_new_file_rejected(self):
        (ROOT / self.proposal['requests_detail'][-1]['output_path']).unlink()
        with self.assertRaisesRegex(ValueError, 'new-inventory-incomplete'):
            FETCH.continuation2_readback(self.proposal, self.plan)

    def test_old_complete_file_drift_rejected(self):
        (ROOT / self.proposal['retained_complete_files'][0]['path']).write_bytes(b'X')
        with self.assertRaisesRegex(ValueError, 'input-digest-mismatch'):
            FETCH.continuation2_readback(self.proposal, self.plan)

    def test_old_partial_drift_rejected(self):
        (ROOT / self.proposal['retained_partial']['path']).write_bytes(b'wrong-prefix')
        with self.assertRaisesRegex(ValueError, 'input-size-mismatch'):
            FETCH.continuation2_readback(self.proposal, self.plan)

    def test_old_log_drift_rejected(self):
        log = self.base / 'old-events.jsonl'
        log.write_bytes(b'old-events\n')
        self.proposal['prior_records'].append(FETCH.identity(log))
        log.write_bytes(b'changed-events\n')
        with self.assertRaisesRegex(ValueError, 'prior-record-drift'):
            FETCH.continuation2_readback(self.proposal, self.plan)

    def test_extra_new_file_rejected(self):
        (self.new / 'inputs/pool/main/s/synthetic/extra').write_bytes(b'extra')
        with self.assertRaises(ValueError):
            FETCH.continuation2_readback(self.proposal, self.plan)


if __name__ == '__main__':
    unittest.main()
