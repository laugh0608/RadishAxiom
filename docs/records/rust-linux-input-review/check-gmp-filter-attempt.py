#!/usr/bin/env python3
"""Synthetic checks for the offline failure diagnosis; no Docker or GnuPG."""
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


review = load('inspect-gmp-filter-attempt.py')
synthetic = load('check-gmp-verification.py')


class FailureChecks(unittest.TestCase):
    def setUp(self):
        for name, value in [('PRIMARY', synthetic.PRIMARY), ('SUBKEY', synthetic.SUBKEY)]:
            handle = patch.object(review.run.profile, name, value)
            handle.start()
            self.addCleanup(handle.stop)
        self.status = (f'[GNUPG:] KEYEXPIRED {review.run.profile.EXPIRES["pub"]}\n'
                       '[GNUPG:] IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n').encode()
        self.raw = synthetic.raw_key()

    def test_original_rejection_and_unknown_crypto_remain(self):
        row = review.filter_output(self.status, self.raw, self.raw)
        self.assertEqual(row['original_profile_failure_reproduced'], review.FAILURE)
        self.assertFalse(row['self_certifications_checked'])
        self.assertFalse(row['detached_signature_checked'])
        self.assertEqual(row['source_acceptance'], 'not-assessed')

    def test_packet_framing_change_is_distinct_from_body_change(self):
        reframed = b''.join(bytes([0x80 | tag << 2 | 2]) + len(body).to_bytes(4, 'big') + body
                           for tag, body, _ in review.run.profile.keys.packets(self.raw))
        row = review.filter_output(self.status, self.raw, reframed)
        self.assertFalse(row['packet_encoding_equal'])
        self.assertTrue(row['public_and_self_signature_bodies_equal'])

    def test_wrong_missing_duplicate_expiry_and_import_count_rejected(self):
        for changed in (self.status.replace(b'1736961163', b'1736961679'), self.status.split(b'\n', 1)[1],
                        self.status + self.status, self.status.replace(b'IMPORT_RES 1', b'IMPORT_RES 2')):
            with self.assertRaises(ValueError):
                review.filter_output(changed, self.raw, self.raw)

    def test_additional_error_or_success_is_not_same_failure(self):
        for extra in (b'[GNUPG:] FAILURE import 1\n', b'[GNUPG:] GOODSIG synthetic\n'):
            with self.assertRaises(ValueError):
                review.filter_output(self.status + extra, self.raw, self.raw)

    def test_changed_or_dropped_self_material_is_rejected(self):
        for changed in (self.raw[:-1] + b'X', self.raw[:-1], self.raw.replace(synthetic.UID, b'Changed UID')):
            with self.assertRaises(ValueError):
                review.filter_output(self.status, self.raw, changed)

    def test_silent_profile_relaxation_prevents_historical_replay(self):
        with patch.object(review.run.base, 'IMPORT_ALLOWED', review.run.base.IMPORT_ALLOWED | {'KEYEXPIRED'}):
            with self.assertRaisesRegex(ValueError, 'no longer rejects'):
                review.filter_output(self.status, self.raw, self.raw)


if __name__ == '__main__':
    unittest.main()
