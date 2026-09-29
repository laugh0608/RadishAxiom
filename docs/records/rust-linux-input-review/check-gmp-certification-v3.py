#!/usr/bin/env python3
"""Synthetic joint-status/effective-expiry regression checks; no Docker or GnuPG."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v3 = load('inspect-gmp-certification-v3.py')
s = load('check-gmp-verification.py')


class JointChecks(unittest.TestCase):
    def setUp(self):
        for key, value in [('PRIMARY', s.PRIMARY), ('SUBKEY', s.SUBKEY)]:
            handle = patch.object(v3.p, key, value)
            handle.start()
            self.addCleanup(handle.stop)
        self.original = s.raw_key()
        self.listing = s.colons().replace(b'1736961679', b'1736961163')
        self.expired = b'[GNUPG:] KEYEXPIRED 1736961163\n'
        self.considered = f'[GNUPG:] KEY_CONSIDERED {s.PRIMARY} 0\n'.encode()
        self.status = self.expired + self.considered + self.expired * 2

    def assess(self, **changes):
        return v3.assess(s.result(self.status, stdout=self.listing, **changes),
                         self.original, self.original, s.NOW)

    def test_joint_positive_preserves_all_trust_boundaries(self):
        r = self.assess()
        self.assertEqual(r['packet_declared_expiry']['sub'], 1736961679)
        self.assertEqual(r['listed_effective_expiry']['sub'], 1736961163)
        self.assertEqual(r['key_expiry_status_records'], 3)
        self.assertEqual(r['source_acceptance'], 'not-assessed')
        self.assertEqual(r['historical_validity'], 'not-established')
        self.assertFalse(r['detached_signature_checked'])
        self.assertFalse(r['cryptography_executed_by_parser'])

    def test_old_parser_still_rejects_effective_expiry(self):
        with self.assertRaisesRegex(ValueError, 'exact expiry'):
            v3.p.certifications(self.listing, self.original, self.original, s.NOW)

    def test_status_cannot_be_deduplicated_reordered_or_extended(self):
        for status in [self.expired + self.considered, self.considered + self.expired * 3,
                       self.status + self.expired, self.status[:-1], self.status.replace(b'\n', b'\r\n'),
                       self.status + b'[GNUPG:] FAILURE synthetic 1\n',
                       self.status + b'[GNUPG:] REVKEYSIG synthetic\n']:
            with self.subTest(status=status), self.assertRaises(ValueError):
                v3.assess(s.result(status, stdout=self.listing), self.original, self.original, s.NOW)

    def test_status_wrong_primary_flags_or_expiry(self):
        for status in [self.status.replace(s.PRIMARY.encode(), b'A' * 40),
                       self.status.replace(b' 0\n', b' 2\n'),
                       self.status.replace(b'1736961163', b'1736961679')]:
            with self.assertRaises(ValueError):
                v3.assess(s.result(status, stdout=self.listing), self.original, self.original, s.NOW)

    def test_status_match_never_replaces_colon_checks(self):
        for listing in [b'', self.listing.replace(b'sig:!', b'sig:?'),
                        self.listing.replace(b'sub:e', b'sub:r'),
                        self.listing.replace(b'pub:e', b'pub:-'),
                        self.listing.replace(b':sc:', b':scD:'),
                        self.listing.replace(b':::8:', b':::2:'),
                        self.listing.replace(b':13x:', b':18x:'),
                        self.listing.replace(b'Synthetic', b'Other'),
                        self.listing + self.listing.splitlines(keepends=True)[3],
                        self.listing + b'rvk::::::::::::\n']:
            with self.subTest(listing=listing), self.assertRaises(ValueError):
                v3.assess(s.result(self.status, stdout=listing), self.original, self.original, s.NOW)

    def test_binding_expiry_or_nearby_value_not_effective_expiry(self):
        for expiry in [b'1736961679', b'1736961162', b'1736961164', b'0', b'']:
            lines = self.listing.splitlines(keepends=True)
            lines[4] = lines[4].replace(b'1736961163', expiry)
            with self.assertRaises(ValueError):
                v3.assess(s.result(self.status, stdout=b''.join(lines)), self.original, self.original, s.NOW)

    def test_no_normalization_of_packet_expiry_or_material(self):
        for raw in [self.original[:-1], self.original.replace(s.UID, b'Synthetic: changed'),
                    self.original.replace((1736961679 - v3.p.KEY_CREATED).to_bytes(4, 'big'),
                                          (1736961163 - v3.p.KEY_CREATED).to_bytes(4, 'big')),
                    s.raw_key(True)]:
            with self.assertRaises(ValueError):
                v3.assess(s.result(self.status, stdout=self.listing), self.original, raw, s.NOW)

    def test_key_or_self_signature_reassignment(self):
        lines = self.listing.splitlines(keepends=True)
        for listing in [self.listing.replace(s.SUBKEY.encode(), s.PRIMARY.encode()),
                        b''.join(lines[:3] + lines[4:] + lines[3:4])]:
            with self.assertRaises(ValueError):
                v3.assess(s.result(self.status, stdout=listing), self.original, self.original, s.NOW)

    def test_invocation_failure_exit_and_clock_rejected(self):
        for result in [s.result(self.status, code=1, stdout=self.listing),
                       s.result(self.status, code=False, stdout=self.listing),
                       s.result(self.status, failure='timeout', stdout=self.listing)]:
            with self.assertRaises(ValueError):
                v3.assess(result, self.original, self.original, s.NOW)
        for now in [False, v3.p.CREATED, 1736961163, 1736961679]:
            with self.assertRaises(ValueError):
                v3.assess(s.result(self.status, stdout=self.listing), self.original, self.original, now)

    def test_capture_and_parser_resource_bounds(self):
        base = s.result(self.status, stdout=self.listing)
        for key in ['stdout', 'stderr', 'status']:
            for value in [b'x' * (v3.p.keys.LIMIT + 1), 'wrong type']:
                with self.assertRaises(ValueError):
                    v3.assess({**base, key: value}, self.original, self.original, s.NOW)
        for listing in [self.listing + b'x' * 8193 + b'\n', self.listing[:-1]]:
            with self.assertRaises(ValueError):
                v3.assess({**base, 'stdout': listing}, self.original, self.original, s.NOW)


if __name__ == '__main__':
    unittest.main()
