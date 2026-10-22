#!/usr/bin/env python3
"""静态依赖观察的合成边界测试；不执行 solver 或上游代码。"""
import hashlib
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

M = runpy.run_path(str(Path(__file__).with_name("inspect-cvc5-cli-dependencies.py")))


def elf():
    data = bytearray(400)
    struct.pack_into("<16sHHIQQQIHHHHHH", data, 0, b"\x7fELF\x02\x01\x01" + b"\0" * 9,
                     2, 183, 1, 0x400078, 64, 128, 0, 64, 56, 1, 64, 3, 1)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0x400000, 0, 400, 400, 4096)
    names = b"\0.shstrtab\0.comment\0"
    data[320:320 + len(names)] = names
    data[352:356] = b"GCC\0"
    struct.pack_into("<IIQQQQIIQQ", data, 192, 1, 3, 0, 0, 320, len(names), 0, 0, 1, 0)
    struct.pack_into("<IIQQQQIIQQ", data, 256, 11, 1, 0, 0, 352, 4, 0, 0, 1, 0)
    return data


class DependencyObservationTests(unittest.TestCase):
    def test_static_sections_do_not_invent_symbols(self):
        result = M["sections"](elf())
        self.assertEqual(result[-1]["strings"], ["GCC"])
        self.assertFalse(any(s["type"] == 2 for s in result))

    def test_section_header_and_data_bounds(self):
        for offset, fmt, value in [(40, "Q", 399), (58, "H", 0), (62, "H", 3),
                                   (256, "I", 999), (288, "Q", 1000)]:
            data = elf()
            struct.pack_into("<" + fmt, data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                M["sections"](data)

    def test_source_identity_and_unique_pattern(self):
        raw = b"synthetic pinned text\n"
        entry = {"file": "source.txt", "bytes": len(raw), "raw_digest": M["digest"](raw),
                 "git_blob_sha1": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}
        with tempfile.TemporaryDirectory(prefix="cvc5-dependency-observation-") as directory:
            p = Path(directory)
            (p / entry["file"]).write_bytes(raw)
            self.assertEqual(M["check_source"](p, entry), raw)
            for bad in [dict(entry, file="../source.txt"), dict(entry, bytes=1),
                        dict(entry, raw_digest="sha256:" + "0" * 64), dict(entry, git_blob_sha1="0" * 40)]:
                with self.assertRaises(ValueError):
                    M["check_source"](p, bad)
        self.assertEqual(M["one"]("pin=123", r"pin=(\d+)"), "123")
        for text in ["missing", "pin=123 pin=456"]:
            with self.assertRaises(ValueError):
                M["one"](text, r"pin=(\d+)")


if __name__ == "__main__":
    unittest.main()
