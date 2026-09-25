#!/usr/bin/env python3
"""Synthetic GNU keyring selection boundaries; no network or cryptography."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('refresh', HERE / 'inspect-binutils-key-refresh.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def packet(tag, body):
    return bytes([192 | tag, 255]) + len(body).to_bytes(4, 'big') + body


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.body = b'\x04\x00\x00\x00\x01\x01synthetic'
        self.primary = m.keys.fingerprint(self.body)
        self.key = packet(6, self.body)

    def test_exact_selected_bytes_exclude_local_trust(self):
        uid = packet(13, b'synthetic UID')
        raw = packet(6, b'\x03legacy') + packet(12, b'local') + self.key + packet(12, b'local') + uid
        selected, report = m.select(raw, self.primary)
        self.assertEqual(selected, self.key + uid)
        self.assertEqual(report['primary_count'], 2)
        self.assertEqual(report['packet_counts'], {'6': 2, '12': 2, '13': 1})
        self.assertEqual(sum(row['excluded_local_trust'] for row in report['selected_packets']), 1)
        for row in report['selected_packets']:
            self.assertEqual(m.identity(raw[row['offset']:row['offset'] + row['bytes']]), row['packet'])
        self.assertFalse(report['unrelated_key_semantics_checked'])

    def test_old_format_header(self):
        raw = bytes([128 | (6 << 2), len(self.body)]) + self.body
        self.assertEqual(m.select(raw, self.primary)[0], raw)
        comparison = m.compare_public_material(raw, self.key)
        self.assertTrue(comparison['public_packet_bodies_equal_to_previous'])
        self.assertFalse(comparison['public_packet_encoding_equal_to_previous'])

    def test_changed_body_tag_or_order_rejected(self):
        uid = packet(13, b'synthetic')
        original = self.key + uid
        for changed in (self.key + packet(13, b'changed'), self.key + packet(2, b'synthetic'),
                        uid + self.key, original + uid, self.key):
            with self.assertRaisesRegex(ValueError, 'bodies differ'):
                m.compare_public_material(changed, original)

    def test_exact_encoding_comparison(self):
        self.assertTrue(m.compare_public_material(self.key, self.key)['public_packet_encoding_equal_to_previous'])

    def test_absent_or_duplicate(self):
        for raw, primary in ((self.key, '0' * 40), (self.key + self.key, self.primary)):
            with self.assertRaises(ValueError):
                m.select(raw, primary)

    def test_truncated_empty_invalid_or_preprimary(self):
        for raw in (b'', b'x', self.key[:-1], b'\xc6\xff\x00', packet(6, b''), packet(12, b'x')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                m.select(raw, self.primary)

    def test_secret_unknown_and_partial_packets(self):
        for tail in (packet(5, b'secret'), packet(7, b'secret'), packet(63, b'x'), b'\xc2\xe0', b'\x8b'):
            with self.assertRaises(ValueError):
                m.select(self.key + tail, self.primary)

    def test_input_and_packet_count_bounds(self):
        with patch.object(m, 'LIMIT', len(self.key) - 1), self.assertRaises(ValueError):
            m.select(self.key, self.primary)
        with patch.object(m, 'PACKETS', 1), self.assertRaises(ValueError):
            m.select(self.key + packet(12, b'x'), self.primary)

    def test_selected_profile_remains_strict(self):
        with self.assertRaisesRegex(ValueError, 'unexpected or secret'):
            m.select(self.key + packet(17, b'attribute'), self.primary)

    def test_next_key_not_included(self):
        other = packet(6, self.body + b'other') + packet(13, b'other UID')
        selected, report = m.select(self.key + other, self.primary)
        self.assertEqual(selected, self.key)
        self.assertEqual(len(report['selected_packets']), 1)


if __name__ == '__main__':
    unittest.main()
