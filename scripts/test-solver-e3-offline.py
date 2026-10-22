#!/usr/bin/env python3
"""Adversarial tests of the separate offline E3 checker (no OS probes)."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('e3check', Path(__file__).with_name('check-solver-e3-offline.py'))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def frame(kind=2, body=bytes(44), sequence=0, binding=bytes(160)):
    return struct.pack('>4sBBBB4sQI', b'RAXB', 0, 1, 1, kind,
                       bytes(4), sequence, 160+len(body)) + binding + body


class IndependentCheckerTests(unittest.TestCase):
    def test_allow_all_is_not_accepted_as_worker_policy(self):
        program = struct.pack('<HBBI', 6, 0, 0, check.ALLOW)
        with self.assertRaises(AssertionError):
            check.check_worker(program)

    def test_malformed_program_fails_boundedly(self):
        for program in (b'x', struct.pack('<HBBI', 5, 0, 0, 100),
                        struct.pack('<HBBI', 0x20, 0, 0, 64),
                        struct.pack('<HBBI', 0xFF, 0, 0, 0)):
            with self.assertRaises(AssertionError):
                check.evaluate(program, 63)

    def test_supervisor_rejects_allow_all_and_deny_all(self):
        for action in (check.ALLOW, check.KILL):
            with self.assertRaises(AssertionError):
                check.check_supervisor(struct.pack('<HBBI', 6, 0, 0, action))

    def test_header_binding_sequence_and_truncation_rejected(self):
        valid = frame()
        parsed, control = check.read_frames(valid, 1, bytes(160))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(control, 228)
        for position in (0, 4, 5, 6, 7, 8, 19, 20, 24, 56, 88, 120, 152):
            corrupted = bytearray(valid); corrupted[position] ^= 0x80
            with self.assertRaises(AssertionError):
                check.read_frames(corrupted, 1, bytes(160))
        for size in (1, 23, 24, 100, len(valid)-1):
            with self.assertRaises(AssertionError):
                check.read_frames(valid[:size], 1, bytes(160))

    def test_duplicate_and_after_eof_are_rejected(self):
        with self.assertRaises(AssertionError):
            check.read_frames(frame()+frame(sequence=1), 1, bytes(160))
        after_eof = frame(4, b'') + frame(3, b'x', 1)
        with self.assertRaises(AssertionError):
            check.read_frames(after_eof, 1, bytes(160))

    def test_control_budget_is_not_reset_between_frames(self):
        many = b''.join(frame(3, b'x', i) for i in range(179))
        with self.assertRaises(AssertionError):
            check.read_frames(many, 1, bytes(160))


if __name__ == '__main__':
    unittest.main()
