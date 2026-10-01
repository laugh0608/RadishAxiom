#!/usr/bin/env python3
"""Synthetic regression checks for the second failure diagnosis; no external tools."""
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


review = load('inspect-gmp-certification-attempt.py')
synthetic = load('check-gmp-verification.py')


class FailureChecks(unittest.TestCase):
    def setUp(self):
        for name, value in [('PRIMARY', synthetic.PRIMARY), ('SUBKEY', synthetic.SUBKEY)]:
            handle = patch.object(review.run.profile, name, value)
            handle.start()
            self.addCleanup(handle.stop)
        p = review.run.profile
        self.raw = synthetic.raw_key()
        self.expired = f'[GNUPG:] KEYEXPIRED {p.EXPIRES["pub"]}\n'.encode()
        self.considered = f'[GNUPG:] KEY_CONSIDERED {p.PRIMARY} 0\n'.encode()
        self.status = self.expired + self.considered + self.expired * 2
        listing = synthetic.colons().replace(str(p.EXPIRES['sub']).encode(), str(p.EXPIRES['pub']).encode())
        self.invocation = synthetic.result(self.status, stdout=listing)

    def diagnose(self, **changes):
        return review.diagnose({**self.invocation, **changes}, self.raw, self.raw, synthetic.NOW)

    def test_both_rejections_reproduced_without_acceptance(self):
        row = self.diagnose()
        self.assertEqual(row['profile_failure_reproduced'], review.FAILURE)
        self.assertEqual(row['separate_colon_failure_reproduced'], review.COLON_FAILURE)
        self.assertEqual(row['expiry_difference_seconds'], 516)
        self.assertEqual(row['tool_sig_bang_records_observed'], 2)
        self.assertFalse(row['complete_certification_assessment_passed'])
        self.assertFalse(row['detached_signature_checked'])
        self.assertEqual(row['source_acceptance'], 'not-assessed')

    def test_no_normalization_of_extra_missing_or_reordered_status(self):
        for status in (self.status + self.expired, self.expired + self.considered,
                       self.considered + self.expired * 3, self.status.replace(b' 0\n', b' 1\n'),
                       self.status + b'[GNUPG:] REVKEYSIG synthetic\n', b'x' * 257):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.diagnose(status=status)

    def test_incomplete_invocation_is_not_the_same_failure(self):
        for changes in ({'returncode': False}, {'returncode': 1}, {'failure': 'timeout'}):
            with self.assertRaises(ValueError):
                self.diagnose(**changes)

    def test_unchanged_binding_expiry_is_a_different_case(self):
        with self.assertRaisesRegex(ValueError, 'no longer rejects'):
            self.diagnose(stdout=synthetic.colons())

    def test_other_colon_damage_is_not_misreported_as_expiry_difference(self):
        for listing in (b'', self.invocation['stdout'].replace(b'sig:!', b'sig:?'),
                        self.invocation['stdout'].replace(b'sub:e:', b'sub:r:')):
            with self.assertRaises(ValueError):
                self.diagnose(stdout=listing)

    def test_material_and_observation_binding_is_not_skipped(self):
        for raw, now in ((self.raw[:-1], synthetic.NOW), (self.raw, review.run.profile.CREATED)):
            with self.assertRaises(ValueError):
                review.diagnose(self.invocation, raw, raw, now)

    def test_profile_relaxation_cannot_rewrite_historical_failure(self):
        with patch.object(review.run, 'assess_output', return_value={}):
            with self.assertRaisesRegex(ValueError, 'no longer rejects'):
                self.diagnose()
        with patch.object(review.run.profile, 'certifications', return_value={}):
            with self.assertRaisesRegex(ValueError, 'no longer rejects'):
                self.diagnose()


if __name__ == '__main__':
    unittest.main()
