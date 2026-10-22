#!/usr/bin/env python3
"""独立导出核对器的拒绝边界；只用自有内存合成材料。"""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("simulation_check", Path(__file__).with_name("check-solver-simulation-export.py"))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ExportCheckTests(unittest.TestCase):
    def test_canonical_subset_rejects_duplicate_null_number_and_spacing(self):
        self.assertEqual(checker.parse(b'{"a":"1","b":true}'), {"a": "1", "b": True})
        for data in [b'{"a":"1","a":"2"}', b'{"a":null}', b'{"a":1}', b'{ "a":"1"}', b'{"b":true,"a":"1"}']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                checker.parse(data)

    def test_prefix_cannot_be_claimed_as_complete_or_hide_extra_byte(self):
        prefix = {"raw_hex": "6162", "captured_bytes": "2", "complete": False, "exceeded": True,
                  "observed_bytes_lower_bound": "3", "prefix_raw_digest": checker.raw(b"ab"), "kind": "prefix"}
        self.assertEqual(checker.stream(prefix, 2), b"ab")
        for changes in [{"complete": True}, {"observed_bytes_lower_bound": "2"},
                        {"full_raw_digest": checker.raw(b"ab")}, {"captured_bytes": "1"},
                        {"prefix_raw_digest": checker.raw(b"ac")}, {"raw_hex": "ABCD"}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                checker.stream(prefix | changes, 2)

    def test_complete_and_incomplete_streams_use_distinct_digest_fields(self):
        complete = {"raw_hex": "6162", "captured_bytes": "2", "complete": True, "exceeded": False,
                    "observed_bytes_lower_bound": "2", "full_raw_digest": checker.raw(b"ab"), "kind": "complete"}
        self.assertEqual(checker.stream(complete, 2), b"ab")
        with self.assertRaises(ValueError):
            checker.stream(complete, 1)
        with self.assertRaises(ValueError):
            checker.stream(complete | {"complete": False, "kind": "prefix"}, 2)
        for value in ["01", "-1", "1.0", 1, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                checker.decimal(value)


if __name__ == "__main__":
    unittest.main()
