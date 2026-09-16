#!/usr/bin/env python3
"""Synthetic key inventory boundaries; deliberately no cryptographic verification."""
import base64
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('review', HERE / 'inspect-mpc-mpfr-key-inputs.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def packet(tag, body):
    return bytes([0xc0 | tag, 255]) + len(body).to_bytes(4, 'big') + body


def armored(data):
    crc = 0xB704CE
    for byte in data:
        crc ^= byte << 16
        for _ in range(8):
            crc = (crc << 1) ^ (0x1864CFB if crc & 0x800000 else 0)
    return (b'-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n' + base64.b64encode(data) + b'\n=' +
            base64.b64encode((crc & 0xffffff).to_bytes(3, 'big')) + b'\n-----END PGP PUBLIC KEY BLOCK-----\n')


def fixture(digest=8, expiry=100, seed=1):
    # The public-key and signature values are synthetic, not mathematically valid.
    body = bytes([4, 0, 0, 0, seed, 17]) + b'synthetic'
    fpr = review.keys.fingerprint(body)
    hashed = b'\x05\x02\x00\x00\x00\x02' + b'\x05\x09' + expiry.to_bytes(4, 'big')
    issuer = b'\x09\x10' + bytes.fromhex(fpr[-16:])
    sig = bytes([4, 19, 17, digest]) + len(hashed).to_bytes(2, 'big') + hashed
    sig += len(issuer).to_bytes(2, 'big') + issuer + b'\x00\x00\x00\x01\x01'
    return packet(6, body) + packet(13, b'Synthetic user') + packet(2, sig), fpr, sig


class KeyInventoryTests(unittest.TestCase):
    def test_two_keys_are_separate(self):
        old, _, _ = fixture(digest=2, seed=1)
        new, expected, _ = fixture(seed=2)
        result = review.inventory(armored(old + new), expected)
        self.assertEqual([b['selected'] for b in result['blocks']], [False, True])
        self.assertEqual(result['blocks'][0]['declared_self_digest_counts'], {'2': 1})
        self.assertEqual(result['blocks'][1]['declared_self_digest_counts'], {'8': 1})
        self.assertFalse(result['cryptography_executed'])
        self.assertFalse(result['public_key_identity_accepted'])

    def test_expiry_is_only_a_hint(self):
        data, expected, _ = fixture()
        hint = review.inventory(armored(data), expected)['blocks'][0]['latest_uid_expiry_hints'][0]
        self.assertEqual(hint['declared_key_expiry_utc'], '1970-01-01T00:01:41+00:00')
        self.assertFalse(hint['effective_validity_verified'])

    def test_zero_expiry_is_no_declared_limit(self):
        data, expected, _ = fixture(expiry=0)
        hint = review.inventory(armored(data), expected)['blocks'][0]['latest_uid_expiry_hints'][0]
        self.assertIsNone(hint['declared_key_expiry_utc'])

    def test_missing_expected_primary(self):
        data, _, _ = fixture()
        with self.assertRaisesRegex(ValueError, 'expected primary'):
            review.inventory(armored(data), '0' * 40)

    def test_bad_crc(self):
        data, _, _ = fixture()
        raw = armored(data).replace(b'\n=', b'\n=AAAA')
        with self.assertRaises(ValueError):
            review.armor(raw)

    def test_secret_packet(self):
        _, expected, _ = fixture()
        with self.assertRaises(ValueError):
            review.inventory(armored(packet(5, b'synthetic secret')), expected)

    def test_truncated_packet(self):
        data, expected, _ = fixture()
        with self.assertRaises(ValueError):
            review.inventory(armored(data[:-1]), expected)

    def test_unsupported_signature_version(self):
        _, _, sig = fixture()
        with self.assertRaises(ValueError):
            review.signature_fields(bytes([3]) + sig[1:])

    def test_weak_digest_is_reported_not_accepted(self):
        _, _, sig = fixture(digest=2)
        result = review.signature_fields(sig)
        self.assertEqual(result['digest_algorithm'], 2)
        self.assertFalse(result['cryptography_executed'])


if __name__ == '__main__':
    unittest.main()
