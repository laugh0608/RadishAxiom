#!/usr/bin/env python3
"""Synthetic metadata transport/integrity rejection checks; no network traffic."""
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
import urllib.request

spec = importlib.util.spec_from_file_location('c0_metadata', Path(__file__).with_name('cvc5-c0-sdk-metadata.py'))
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.directory_patch = patch.object(metadata, 'RETAINED', self.directory)
        self.directory_patch.start()
        self.root_patch = patch.object(metadata, 'ROOT', self.directory.parent)
        self.root_patch.start()
        packages = lzma.compress(b'Package: synthetic\nArchitecture: arm64\n\n')
        sources = lzma.compress(b'Package: synthetic\nVersion: 1\n\n')
        release = ('Origin: Debian\nCodename: bookworm\nArchitectures: arm64 all\nComponents: main\nSHA256:\n'
                   + ''.join(' ' + hashlib.sha256(raw).hexdigest() + ' ' + str(len(raw)) + ' ' + relative + '\n'
                             for relative, raw in zip(metadata.TARGETS[2:], (packages, sources)))).encode()
        signed = b'-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n\n' + release + b'-----BEGIN PGP SIGNATURE-----\nsynthetic\n-----END PGP SIGNATURE-----\n'
        self.manifest = {'format': 'radishaxiom-private-cvc5-c0-sdk-metadata', 'version': '0.1',
                         'complete': True, 'base_url': metadata.BASE, 'max_total_bytes': metadata.MAX_BYTES,
                         'timeout_seconds_per_item': 180, 'retries': 0, 'fallback_sources': 0,
                         'signature_authentication': 'not-established', 'observations': [],
                         'total_response_body_bytes': sum(map(len, (release, signed, packages, sources)))}
        for relative, raw in zip(metadata.TARGETS, (release, signed, packages, sources)):
            filename = relative.replace('/', '__')
            (self.directory / filename).write_bytes(raw)
            url = metadata.BASE + 'dists/bookworm/' + relative
            self.manifest['observations'].append({'relative_path': relative, 'retained_file': filename,
                'requested_url': url, 'final_url': url, 'redirects': [], 'status': 'obtained', 'http_status': 200,
                'response_headers': {'Content-Length': str(len(raw)), 'Content-Type': 'application/octet-stream'},
                'bytes': len(raw), 'raw_digest': metadata.digest(raw), 'elapsed_seconds': 0.001})
        self.write_manifest()

    def tearDown(self):
        self.directory_patch.stop()
        self.root_patch.stop()
        self.temp.cleanup()

    def write_manifest(self):
        (self.directory / 'fetch-observations.json').write_text(json.dumps(self.manifest))

    def assert_manifest_rejected(self, change):
        change(self.manifest)
        self.write_manifest()
        with self.assertRaises(ValueError):
            metadata.read_verified_metadata()

    def test_complete_integrity_is_not_signature_authentication(self):
        observations, packages, sources = metadata.read_verified_metadata()
        self.assertFalse(observations['signature_verified'])
        self.assertTrue(observations['inrelease_body_equals_release'])
        self.assertTrue(packages.startswith(b'Package:'))
        self.assertTrue(sources.startswith(b'Package:'))

    def test_incomplete_manifest(self):
        self.assert_manifest_rejected(lambda value: value.update(complete=False))

    def test_policy_drift(self):
        self.assert_manifest_rejected(lambda value: value.update(retries=1))

    def test_boolean_byte_count(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0].update(bytes=True))

    def test_duplicate_manifest_json_key(self):
        raw = json.dumps(self.manifest)
        (self.directory / 'fetch-observations.json').write_text(raw[:-1] + ', "complete": true}')
        with self.assertRaisesRegex(ValueError, 'duplicate-json-key'):
            metadata.read_verified_metadata()

    def test_initial_source_drift(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0].update(requested_url='https://deb.debian.org/Release'))

    def test_final_source_drift(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0].update(final_url='https://deb.debian.org/Release'))

    def test_http_status(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0].update(http_status=404))

    def test_content_length(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0]['response_headers'].update({'Content-Length': '1'}))

    def test_content_encoding(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0]['response_headers'].update({'Content-Encoding': 'gzip'}))

    def test_cookie_header_not_exported(self):
        self.manifest['observations'][0]['response_headers']['Set-Cookie'] = 'synthetic'
        self.write_manifest()
        observations, _, _ = metadata.read_verified_metadata()
        self.assertNotIn('synthetic', json.dumps(observations))

    def test_final_url_not_chain_end(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0].update(redirects=[{'from_url': value['observations'][0]['requested_url'], 'to_url': 'https://snapshot.debian.org/file/' + 'a' * 40 + '/Release', 'status': 302}]))

    def test_disconnected_redirect_chain(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0].update(redirects=[{'from_url': 'https://snapshot.debian.org/unrelated', 'to_url': value['observations'][0]['final_url'], 'status': 302}]))

    def test_raw_digest(self):
        self.assert_manifest_rejected(lambda value: value['observations'][0].update(raw_digest='sha256:' + '0' * 64))

    def test_package_xz_must_match_release_declaration(self):
        raw = lzma.compress(b'Package: modified\n\n')
        (self.directory / metadata.TARGETS[2].replace('/', '__')).write_bytes(raw)
        row = self.manifest['observations'][2]
        self.manifest['total_response_body_bytes'] += len(raw) - row['bytes']
        row.update(bytes=len(raw), raw_digest=metadata.digest(raw))
        row['response_headers']['Content-Length'] = str(len(raw))
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'release-index-hash-or-size-mismatch'):
            metadata.read_verified_metadata()

    def test_signature_body_mismatch(self):
        path = self.directory / 'InRelease'
        raw = path.read_bytes().replace(b'Codename: bookworm', b'Codename: bullseye')
        path.write_bytes(raw)
        self.manifest['observations'][1]['raw_digest'] = metadata.digest(raw)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'body-release-mismatch'):
            metadata.read_verified_metadata()

    def test_decompression_budget(self):
        with patch.object(metadata, 'MAX_DECOMPRESSED', 3):
            with self.assertRaisesRegex(ValueError, 'decompressed-index-budget'):
                metadata.decompress(lzma.compress(b'1234'))

    def test_truncated_xz(self):
        with self.assertRaises(ValueError):
            metadata.decompress(lzma.compress(b'1234')[:-1])

    def test_trailing_xz(self):
        with self.assertRaises(ValueError):
            metadata.decompress(lzma.compress(b'1234') + b'extra')

    def test_multiple_xz_streams(self):
        with self.assertRaises(ValueError):
            metadata.decompress(lzma.compress(b'1234') + lzma.compress(b'5678'))

    def test_duplicate_release_field(self):
        with self.assertRaises(ValueError):
            metadata.deb822(b'SHA256: a\nSHA256: b\n')

    def test_multiple_release_stanzas(self):
        with self.assertRaisesRegex(ValueError, 'multiple-stanzas'):
            metadata.release_hashes(b'Codename: bookworm\n\nCodename: bullseye\n')

    def test_valid_content_address_redirect(self):
        metadata.validate_redirect('Release', 'https://snapshot.debian.org/file/' + 'a' * 40 + '/Release')

    def test_index_content_address_requires_release_digest(self):
        url = 'https://snapshot.debian.org/file/' + 'a' * 40 + '/' + 'b' * 64
        with self.assertRaises(ValueError):
            metadata.validate_redirect(metadata.TARGETS[2], url)
        with self.assertRaises(ValueError):
            metadata.validate_redirect(metadata.TARGETS[2], url, 'c' * 64)
        metadata.validate_redirect(metadata.TARGETS[2], url, 'b' * 64)

    def test_package_download_path_never_allowed(self):
        with self.assertRaises(ValueError):
            metadata.validate_redirect('pool/main/a/example/example_1_arm64.deb', metadata.BASE + 'pool/main/a/example/example_1_arm64.deb')

    def test_existing_evidence_blocks_fetch_without_network(self):
        with patch.object(metadata.urllib.request, 'build_opener') as opener:
            with self.assertRaisesRegex(ValueError, 'retention-directory-exists-no-retry'):
                metadata.fetch()
            opener.assert_not_called()

    def test_fetch_refuses_declared_over_budget_without_reading(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.url = metadata.BASE + 'dists/bookworm/Release'
        response.status = 200
        response.headers = {'Content-Length': '5'}
        opener = MagicMock()
        opener.open.return_value = response
        destination = self.directory / 'fresh'
        with patch.object(metadata, 'RETAINED', destination), patch.object(metadata, 'MAX_BYTES', 4), \
                patch.object(metadata.urllib.request, 'build_opener', return_value=opener), patch('builtins.print'):
            with self.assertRaisesRegex(ValueError, 'content-length-exceeds-total-budget'):
                metadata.fetch()
        response.read.assert_not_called()
        observed = json.loads((destination / 'fetch-observations.json').read_text())
        self.assertFalse(observed['complete'])
        self.assertEqual(observed['total_response_body_bytes'], 0)

    def test_fetch_never_reads_over_remaining_bytes(self):
        first, second = MagicMock(), MagicMock()
        for response, relative in ((first, 'Release'), (second, 'InRelease')):
            response.__enter__.return_value = response
            response.url = metadata.BASE + 'dists/bookworm/' + relative
            response.status = 200
        first.headers = {'Content-Length': '4'}
        first.read.return_value = b'1234'
        second.headers = {'Content-Length': '1'}
        opener = MagicMock()
        opener.open.side_effect = [first, second]
        destination = self.directory / 'fresh'
        with patch.object(metadata, 'RETAINED', destination), patch.object(metadata, 'MAX_BYTES', 4), \
                patch.object(metadata.urllib.request, 'build_opener', return_value=opener), patch('builtins.print'):
            with self.assertRaisesRegex(ValueError, 'content-length-exceeds-total-budget'):
                metadata.fetch()
        first.read.assert_called_once_with(4)
        second.read.assert_not_called()
        self.assertEqual((destination / 'Release').read_bytes(), b'1234')

    def test_fetch_timeout_does_not_retry(self):
        opener = MagicMock()
        opener.open.side_effect = TimeoutError('synthetic timeout')
        destination = self.directory / 'fresh'
        with patch.object(metadata, 'RETAINED', destination), \
                patch.object(metadata.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(TimeoutError):
                metadata.fetch()
        self.assertEqual(opener.open.call_count, 1)
        observed = json.loads((destination / 'fetch-observations.json').read_text())
        self.assertEqual(observed['observations'][0]['error_type'], 'TimeoutError')
        self.assertEqual(observed['total_response_body_bytes'], 0)

    def test_redirect_rejections(self):
        for url in ('https://example.com/file/' + 'a' * 40 + '/Release',
                    'https://snapshot.debian.org/file/' + 'a' * 40 + '/Sources.xz',
                    'https://snapshot.debian.org/file/' + 'g' * 40 + '/Release',
                    'https://snapshot.debian.org/file/' + 'a' * 40 + '/../Release',
                    'https://snapshot.debian.org/file/' + 'a' * 40 + '/Release?q=1',
                    metadata.BASE.replace('20230612', '20230613') + 'dists/bookworm/Release'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                metadata.validate_redirect('Release', url)

    def test_redirect_loop(self):
        url = metadata.BASE + 'dists/bookworm/Release'
        handler = metadata.MetadataRedirect('Release', [])
        with self.assertRaisesRegex(ValueError, 'loop'):
            handler.redirect_request(urllib.request.Request(url), None, 302, '', {}, url)

    def test_maximum_redirects(self):
        handler = metadata.MetadataRedirect('Release', [{'from_url': 'synthetic'}] * 5)
        with self.assertRaisesRegex(ValueError, 'limit'):
            handler.redirect_request(urllib.request.Request(metadata.BASE + 'dists/bookworm/Release'), None, 302, '', {}, 'https://snapshot.debian.org/file/' + 'a' * 40 + '/Release')


if __name__ == '__main__':
    unittest.main()
