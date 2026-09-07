#!/usr/bin/env python3
"""Synthetic boundaries for this record's diagnostic methods, not crypto tests."""

import importlib.util
import io
import lzma
from pathlib import Path
import struct
import tarfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive = load("archive_diagnostic", "inspect-archives.py")
signature = load("signature_diagnostic", "verify-signatures.py")
selected = load("selected_diagnostic", "inspect-selected-inputs.py")


def fixture(extra=(), manifest="file:bin/tool\n"):
    stream = io.BytesIO()
    entries = [("root", None), ("root/tool", None), ("root/tool/bin", None),
               ("root/components", b"tool\n"), ("root/tool/manifest.in", manifest.encode()),
               ("root/tool/bin/tool", b"synthetic bytes"), *extra]
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in entries:
            member = tarfile.TarInfo(name)
            member.type = tarfile.DIRTYPE if data is None else tarfile.REGTYPE
            member.mode = 0o755 if data is None else 0o644
            member.size = 0 if data is None else len(data)
            tar.addfile(member, None if data is None else io.BytesIO(data))
    return stream.getvalue()


def inspect(data):
    compressed = lzma.compress(data)
    reader = archive.XzReader(io.BytesIO(compressed), archive.sha256(compressed))
    return archive.inspect_members(reader, "root")


class Diagnostics(unittest.TestCase):
    def test_elf_dependency_observation(self):
        data = bytearray(512)
        data[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", data, 18, 183)
        struct.pack_into("<Q", data, 32, 64)
        struct.pack_into("<HH", data, 54, 56, 3)
        struct.pack_into("<IIQQQQQQ", data, 64, 1, 0, 0, 0, 0, 512, 512, 1)
        struct.pack_into("<IIQQQQQQ", data, 120, 2, 0, 320, 320, 320, 64, 64, 1)
        struct.pack_into("<IIQQQQQQ", data, 176, 3, 0, 240, 240, 240, 4, 4, 1)
        data[240:244] = b"/ld\0"
        data[256:264] = b"libc.so\0"
        for offset, tag, value in [(320, 5, 256), (336, 10, 8), (352, 1, 0), (368, 0, 0)]:
            struct.pack_into("<qQ", data, offset, tag, value)
        self.assertEqual(selected.elf_dependencies(data)["needed"], ["libc.so"])
        self.assertEqual(selected.elf_dependencies(data)["interpreter"], "/ld")
        for offset, value in [(32, 900), (328, 900), (344, 900), (360, 900)]:
            broken = bytearray(data)
            struct.pack_into("<Q", broken, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                selected.elf_dependencies(broken)

    def test_positive_hashes_and_claims(self):
        result = inspect(fixture())
        self.assertEqual(result["type_counts"], {"directory": 3, "file": 3})
        row = result["members"][-1]
        self.assertEqual(row["sha256"], archive.sha256(b"synthetic bytes"))
        self.assertEqual(result["component_claims"][0]["path"], "bin/tool")

    def test_paths_duplicates_and_ancestors(self):
        for name in ["root/../escape", "/root/escape", "root//escape", "root/./escape",
                     "root/components", "root/missing/tool", "root/with\\slash"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect(fixture([(name, b"data")]))

    def test_manifest_claims(self):
        for manifest in ["file:absent\n", "dir:bin/tool\n", "file:bin/tool\nfile:bin/tool\n",
                         "unknown:bin/tool\n", "file:../../outside\n"]:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                inspect(fixture(manifest=manifest))

    def test_links_and_permissions(self):
        for kind, mode in [(tarfile.SYMTYPE, 0o777), (tarfile.CHRTYPE, 0o644), (tarfile.REGTYPE, 0o4755)]:
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w") as tar:
                member = tarfile.TarInfo("root")
                member.type, member.mode, member.linkname = kind, mode, "target" if kind == tarfile.SYMTYPE else ""
                tar.addfile(member)
            with self.assertRaises(ValueError):
                inspect(stream.getvalue())

    def test_limits(self):
        for key, value in [("entries", 2), ("member", 1), ("tar", 512), ("compressed", 1), ("xz_memory", 1024)]:
            with self.subTest(key=key), patch.dict(archive.LIMITS, {key: value}):
                with self.assertRaises((ValueError, lzma.LZMAError)):
                    inspect(fixture())

    def test_xz_and_tar_failures(self):
        data = lzma.compress(fixture())
        for broken, expected in [(data[:-1], archive.sha256(data[:-1])),
                                 (data + b"x", archive.sha256(data + b"x")),
                                 (data + data, archive.sha256(data + data)), (data, "0" * 64)]:
            with self.assertRaises((ValueError, lzma.LZMAError)):
                reader = archive.XzReader(io.BytesIO(broken), expected)
                archive.inspect_members(reader, "root")
        with self.assertRaises(ValueError):
            inspect(fixture() + b"hidden bytes")

    def test_signature_status_is_not_crypto(self):
        # Synthetic GnuPG text only exercises the status gate.
        valid = f"[GNUPG:] VALIDSIG {signature.FINGERPRINT} 2026-07-16 1784203793 0 4 0 1 10 00 {signature.FINGERPRINT}\n"
        self.assertTrue(signature.valid_status(valid))
        for bad in ["", valid + valid, valid.replace(" 10 00 ", " 2 00 "),
                    valid.replace(signature.FINGERPRINT, "0" * 40), valid + "[GNUPG:] BADSIG unknown\n",
                    valid + "[GNUPG:] EXPKEYSIG unknown\n"]:
            self.assertFalse(signature.valid_status(bad))


if __name__ == "__main__":
    unittest.main()
