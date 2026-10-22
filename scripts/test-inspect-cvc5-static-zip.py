#!/usr/bin/env python3
"""合成 ZIP / ELF 拒绝检查；不读取或执行真实 solver。"""
import io
from pathlib import Path
import runpy
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

M = runpy.run_path(str(Path(__file__).with_name("inspect-cvc5-static-zip.py")))
PREFIX = M["PREFIX"]


def member(name, mode=stat.S_IFREG | 0o644, size=1):
    value = ZipInfo(name)
    value.external_attr = mode << 16
    value.file_size = size
    value.compress_type = ZIP_DEFLATED
    return value


def elf():
    data = bytearray(128)
    struct.pack_into("<16sHHIQQQIHHHHHH", data, 0, b"\x7fELF\x02\x01\x01" + b"\0" * 9,
                     2, 183, 1, 0x400078, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0x400000, 0, 128, 128, 4096)
    return data


class InspectionTests(unittest.TestCase):
    def test_cli_rejects_wrong_digest_and_existing_output(self):
        script = Path(__file__).with_name("inspect-cvc5-static-zip.py")
        with tempfile.TemporaryDirectory(prefix="cvc5-static-inspection-") as directory:
            archive = Path(directory) / "synthetic.zip"
            output = Path(directory) / "observation.json"
            archive.write_bytes(b"synthetic-unregistered-archive")
            result = subprocess.run([sys.executable, str(script), str(archive), str(output)],
                                    capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"registered-digest-mismatch", result.stderr)
            self.assertFalse(output.exists())
            output.write_bytes(b"keep-existing-observation")
            result = subprocess.run([sys.executable, str(script), str(archive), str(output)],
                                    capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"output-already-exists", result.stderr)
            self.assertEqual(output.read_bytes(), b"keep-existing-observation")

    def test_regular_members_and_real_zip_roundtrip(self):
        root = member(PREFIX + "/", stat.S_IFDIR | 0o755, 0)
        file = member(PREFIX + "/COPYING")
        output = io.BytesIO()
        with ZipFile(output, "w") as archive:
            archive.writestr(root, b"")
            archive.writestr(file, b"synthetic")
        with ZipFile(io.BytesIO(output.getvalue())) as archive:
            self.assertEqual(M["validate_members"](archive.infolist()), 9)

    def test_paths_duplicates_links_special_and_privileged(self):
        root = member(PREFIX + "/", stat.S_IFDIR | 0o755, 0)
        for name in ["/x", PREFIX + "/../x", PREFIX + "//x", PREFIX + "/./x", "other/x", PREFIX + "/x\\y"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                M["validate_members"]([root, member(name)])
        for mode in [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFREG | 0o4755]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                M["validate_members"]([root, member(PREFIX + "/x", mode)])
        with self.assertRaises(ValueError):
            M["validate_members"]([root, member(PREFIX + "/x"), member(PREFIX + "/x")])

    def test_archive_resource_limits_and_missing_parents(self):
        root = member(PREFIX + "/", stat.S_IFDIR | 0o755, 0)
        for entries in [[root, member(PREFIX + "/x", size=M["MAX_MEMBER"] + 1)],
                        [root] + [member(PREFIX + f"/{i}", size=M["MAX_MEMBER"]) for i in range(3)],
                        [root] + [member(PREFIX + f"/{i}") for i in range(M["MAX_MEMBERS"])],
                        [root, member(PREFIX + "/missing/x")]]:
            with self.assertRaises(ValueError):
                M["validate_members"](entries)

    def test_elf_static_shape(self):
        result = M["inspect_elf"](elf())
        self.assertEqual(result["machine"], "AArch64")
        self.assertFalse(result["pt_interp"])

    def test_elf_architecture_bounds_and_dynamic_linkage(self):
        for offset, fmt, value in [(18, "H", 62), (32, "Q", 125), (64, "I", 2),
                                   (64, "I", 3), (96, "Q", 1000), (24, "Q", 1)]:
            data = elf()
            struct.pack_into("<" + fmt, data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                M["inspect_elf"](data)
        with self.assertRaises(ValueError):
            M["inspect_elf"](elf()[:40])


if __name__ == "__main__":
    unittest.main()
