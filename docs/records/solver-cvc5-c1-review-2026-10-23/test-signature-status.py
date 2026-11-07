#!/usr/bin/env python3
"""Synthetic status records test role, time and failure rejection; no cryptography."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('status', Path(__file__).with_name('inspect-signature-status.py'))
STATUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATUS)
OBSERVED = 1792758000


def fixture(primaries=None):
    lines = ['[GNUPG:] PLAINTEXT 74 0 ']
    for primary in primaries if primaries is not None else STATUS.SIGNERS:
        signer, algorithm = STATUS.SIGNERS[primary]
        lines += ['[GNUPG:] NEWSIG', '[GNUPG:] KEY_CONSIDERED ' + primary + ' 0',
                  '[GNUPG:] SIG_ID synthetic 2023-06-10 1686387124',
                  '[GNUPG:] GOODSIG ' + signer[-16:] + ' Synthetic UID',
                  f'[GNUPG:] VALIDSIG {signer} 2023-06-10 1686387124 0 4 0 {algorithm} 8 01 {primary}',
                  '[GNUPG:] TRUST_UNDEFINED 0 pgp']
    return ('\n'.join(lines) + '\n').encode()


class Tests(unittest.TestCase):
    def verify(self, raw, **kw):
        return STATUS.verify(raw, exit_code=kw.get('exit_code', 0), observed_at=OBSERVED, failure=kw.get('failure'))

    def test_three_roles(self):
        self.assertEqual(set(self.verify(fixture())['signatures']), STATUS.REQUIRED)

    def test_missing_each_role(self):
        for primary in STATUS.REQUIRED:
            with self.subTest(primary=primary), self.assertRaises(ValueError):
                self.verify(fixture([p for p in STATUS.SIGNERS if p != primary]))

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            self.verify(fixture([STATUS.ARCHIVE, STATUS.ARCHIVE, STATUS.RELEASE]))

    def test_failure_statuses(self):
        for failure in STATUS.FAILURES:
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                self.verify(fixture() + ('[GNUPG:] ' + failure + ' synthetic\n').encode())

    def test_nonzero_or_incomplete_invocation(self):
        for kwargs in ({'exit_code': 2}, {'failure': 'deadline'}):
            with self.assertRaises(ValueError):
                self.verify(fixture(), **kwargs)

    def test_wrong_signer(self):
        with self.assertRaises(ValueError):
            self.verify(fixture().replace(STATUS.SIGNERS[STATUS.ARCHIVE][0].encode(), b'F' * 40))

    def test_signature_expiry_and_future(self):
        for raw in (fixture().replace(b'1686387124 0 4', b'1686387124 1700000000 4'),
                    fixture().replace(b'1686387124', b'1900000000')):
            with self.assertRaises(ValueError):
                self.verify(raw)

    def test_release_uid_annotation(self):
        raw = fixture([STATUS.LEGACY, STATUS.ARCHIVE, STATUS.RELEASE])
        raw = raw.rsplit(b'[GNUPG:] TRUST_UNDEFINED 0 pgp\n', 1)[0] + b'[GNUPG:] TRUST_UNDEFINED 0 pgp debian-release@lists.debian.org\n'
        self.verify(raw)
        with self.assertRaises(ValueError):
            self.verify(raw.replace(b'debian-release@lists.debian.org', b'unknown@example.test'))

    def test_unterminated_or_unknown(self):
        for raw in (fixture()[:-1], fixture()+b'[GNUPG:] UNKNOWN\n'):
            with self.assertRaises(ValueError):
                self.verify(raw)


if __name__ == '__main__':
    unittest.main()
