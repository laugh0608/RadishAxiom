#!/usr/bin/env python3
"""Synthetic primary/subkey, opaque signature and identity-item diagnostics; no network or cryptography."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m', HERE / 'inspect-gcc-key-inputs.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def packet(tag, body):
    return bytes([0xc0 | tag, 255]) + len(body).to_bytes(4, 'big') + body


def sig(issuer, kind=24, embedded=b''):
    hashed = b'\x05\x02\x00\x00\x00\x01'
    unhashed = b'\x09\x10' + bytes.fromhex(issuer[-16:])
    if embedded:
        unhashed += bytes([len(embedded) + 1, 32]) + embedded
    return b'\x04' + bytes([kind, 1, 2]) + len(hashed).to_bytes(2, 'big') + hashed + \
        len(unhashed).to_bytes(2, 'big') + unhashed + b'\x00\x00\x00\x01\x01'


class KeyTests(unittest.TestCase):
    def setUp(self):
        self.primary_body = b'\x04\x00\x00\x00\x01\x01synthetic primary'
        self.sub_body = b'\x04\x00\x00\x00\x02\x01synthetic subkey'
        self.primary, self.signer = map(m.keys.fingerprint, (self.primary_body, self.sub_body))
        self.prefix = packet(6, self.primary_body) + packet(13, b'Synthetic user')
        self.binding = sig(self.primary, embedded=sig(self.signer, 25))
        self.raw = self.prefix + packet(14, self.sub_body) + packet(2, self.binding)

    def inventory(self, raw):
        return m.inventory(raw, self.primary, self.signer)

    def test_subkey_binding_and_cross_signature_remain_declarations(self):
        report = self.inventory(self.raw)
        self.assertFalse(report['effective_validity_verified'])
        self.assertFalse(report['cryptography_executed'])
        self.assertEqual(report['declared_v4_self_digest_counts'], {'2': 1})
        self.assertEqual(report['signer_binding_declarations'][0]['embedded'][0]['declaration']['class'], 25)

    def test_primary_is_not_signer_subkey(self):
        with self.assertRaisesRegex(ValueError, 'subkey missing'):
            m.inventory(self.raw, self.primary, self.primary)

    def test_other_primary_duplicate_or_absent_subkey(self):
        for raw in (packet(6, self.sub_body) + self.raw,
                    self.raw + packet(14, self.sub_body), self.prefix):
            with self.assertRaises(ValueError):
                self.inventory(raw)

    def test_third_party_cannot_supply_primary_binding(self):
        for body in (sig(self.signer), sig(self.primary, 19)):
            with self.assertRaisesRegex(ValueError, 'binding declaration missing'):
                self.inventory(self.prefix + packet(14, self.sub_body) + packet(2, body))

    def test_opaque_version_does_not_become_valid_or_complete(self):
        report = self.inventory(self.raw + packet(2, b'\x03opaque'))
        self.assertFalse(report['complete_signature_semantics_inspected'])
        self.assertFalse(report['opaque_signatures'][0]['semantics_inspected'])
        self.assertEqual(report['declared_v4_self_digest_counts'], {'2': 1})

    def test_revocation_preserved_and_malformed_v4_rejected(self):
        report = self.inventory(self.raw + packet(2, sig(self.primary, 40)))
        self.assertEqual(report['declared_v4_revocations'][0]['class'], 40)
        with self.assertRaises(ValueError):
            self.inventory(self.raw + packet(2, b'\x04truncated'))

    def test_identity_requires_one_complete_matching_item(self):
        text = (b'2048R/FC26A641 2005-09-13 Richard Guenther &lt;richard.guenther@gmail.com&gt; '
                b'Key fingerprint = 7F74 F97C 1034 68EE 5D75 0B58 3AB0 0996 FC26 A641')
        raw = b'<li>' + text + b'</li>'
        self.assertFalse(m.identity_statement(raw)['identity_accepted'])
        for changed in (raw + raw, raw.replace(b'A641', b'A642'), raw.replace(b'Key fingerprint', b'</li><li>Key fingerprint'),
                        b'x' * 262145, b'\xff'):
            with self.assertRaises((ValueError, UnicodeError)):
                m.identity_statement(changed)


if __name__ == '__main__':
    unittest.main()
