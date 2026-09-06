#!/usr/bin/env python3
"""Synthetic rejection and compatibility checks for the source-only inspector."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import lzma
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("inspect-source-tar-v1.py")
SPEC = importlib.util.spec_from_file_location("source_tar_inventory", SCRIPT)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
TOP = MOD.TOP


def member(name: str, data: bytes = b"", kind: bytes = tarfile.REGTYPE, target: str = "", mode: int | None = None):
    info = tarfile.TarInfo(name)
    info.type = kind
    info.mode = mode if mode is not None else (0o777 if kind == tarfile.SYMTYPE else 0o755 if kind == tarfile.DIRTYPE else 0o644)
    info.linkname = target
    info.size = len(data)
    return info, data


def base_members():
    directories = {TOP}
    files = []
    for relative in sorted(MOD.REQUIRED):
        name = f"{TOP}/{relative}"
        parts = name.split("/")
        directories.update("/".join(parts[:i]) for i in range(1, len(parts)))
        data = b"synthetic fixture\n"
        if relative == "Makefile":
            data = b"VERSION = 6\nPATCHLEVEL = 18\nSUBLEVEL = 49\nEXTRAVERSION =\n"
        files.append(member(name, data))
    return [member(name, kind=tarfile.DIRTYPE) for name in sorted(directories)] + files


def archive(extra=(), *, members=None, global_fields=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT,
                      pax_headers={"comment": "1" * 40} if global_fields is None else global_fields) as stream:
        for info, data in (base_members() if members is None else members) + list(extra):
            stream.addfile(info, io.BytesIO(data))
    return output.getvalue()


def inspect(data):
    stream = io.BytesIO(data)
    return MOD.inspect_tar(MOD.TarReader(iter(lambda: stream.read(4096), b"")), TOP)


class SourceInventoryTests(unittest.TestCase):
    def test_valid_inventory_binds_content_tar_and_links(self):
        data = archive([member(f"{TOP}/data", b"SPDX-License-Identifier: MIT\n"),
                        member(f"{TOP}/link", kind=tarfile.SYMTYPE, target="data"),
                        member(f"{TOP}/hard", kind=tarfile.LNKTYPE, target=f"{TOP}/data")])
        result = inspect(data)
        self.assertEqual(result["tar"], {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.assertEqual(len(result["links"]), 2)
        self.assertEqual(result["spdx_prefix_scan"]["declarations"][0]["raw_declaration"], "MIT")

    def test_paths_cannot_escape_or_alias(self):
        for name in ("/outside", f"{TOP}/../outside", f"{TOP}//alias", f"{TOP}/./alias", f"{TOP}/bad\\name", f"{TOP}/bad\nname"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect(archive([member(name)]))

    def test_duplicate_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            inspect(archive([member(f"{TOP}/COPYING")]))

    def test_repeated_directory_suffix_is_not_normalized_away(self):
        with self.assertRaisesRegex(ValueError, "noncanonical"):
            inspect(archive([member(f"{TOP}/alias//", kind=tarfile.DIRTYPE)]))

    def test_ancestor_cannot_be_a_link(self):
        with self.assertRaisesRegex(ValueError, "ancestor"):
            inspect(archive([member(f"{TOP}/alias", kind=tarfile.SYMTYPE, target="LICENSES"),
                             member(f"{TOP}/alias/file")]))

    def test_link_escape_dangling_and_cycle_rejected(self):
        for target in ("/etc/passwd", "../outside", "missing", "loop"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                inspect(archive([member(f"{TOP}/loop", kind=tarfile.SYMTYPE, target=target)]))

    def test_nested_symlink_escape_is_not_lexically_collapsed(self):
        rows = [member(f"{TOP}/LICENSES/up", kind=tarfile.SYMTYPE, target=".."),
                member(f"{TOP}/bad", kind=tarfile.SYMTYPE, target="LICENSES/up/../COPYING")]
        with self.assertRaisesRegex(ValueError, "escapes"):
            inspect(archive(rows))

    def test_hardlink_requires_direct_regular_target(self):
        with self.assertRaisesRegex(ValueError, "hardlink"):
            inspect(archive([member(f"{TOP}/bad", kind=tarfile.LNKTYPE, target=f"{TOP}/LICENSES")]))

    def test_devices_permissions_and_ownership_rejected(self):
        cases = [member(f"{TOP}/device", kind=tarfile.CHRTYPE),
                 member(f"{TOP}/suid", mode=0o4644), member(f"{TOP}/writable", mode=0o666)]
        owner = member(f"{TOP}/owner"); owner[0].uid = 1000; cases.append(owner)
        for row in cases:
            with self.subTest(name=row[0].name), self.assertRaises(ValueError):
                inspect(archive([row]))

    def test_git_archive_group_write_modes_are_recorded_without_extraction(self):
        result = inspect(archive([member(f"{TOP}/group-write", b"input", mode=0o664)]))
        row = next(row for row in result["members"] if row["path"].endswith("/group-write"))
        self.assertEqual(row["mode"], "0664")

    def test_truncation_checksum_and_trailing_tar_rejected(self):
        data = archive()
        damaged = bytearray(data); damaged[0] ^= 1
        for value in (data[:600], bytes(damaged), data + b"x" * 512, data + b"\0"):
            with self.subTest(length=len(value)), self.assertRaises((ValueError, tarfile.HeaderError)):
                inspect(value)

    def test_unknown_pax_fields_and_duplicate_records_rejected(self):
        with self.assertRaisesRegex(ValueError, "global PAX"):
            inspect(archive(global_fields={"path": "outside"}))
        with self.assertRaisesRegex(ValueError, "duplicate PAX"):
            MOD.pax_fields(b"9 path=a\n9 path=b\n")
        with self.assertRaisesRegex(ValueError, "boundary"):
            MOD.pax_fields(b"99 path=a\n")

    def test_local_pax_long_path_is_checked(self):
        name = f"{TOP}/" + "x" * 180
        result = inspect(archive([member(name)]))
        self.assertIn(name, [row["path"] for row in result["members"]])
        info, data = member(f"{TOP}/ordinary")
        info.pax_headers = {"path": "../escape"}
        with self.assertRaises(ValueError):
            inspect(archive([(info, data)]))

    def test_resource_limits_fail_instead_of_truncating_inventory(self):
        data = archive()
        for key, value in (("entries", 1), ("tar_bytes", 512), ("member_bytes", 1), ("extension_bytes", 1)):
            with self.subTest(key=key), patch.dict(MOD.LIMITS, {key: value}), self.assertRaisesRegex(ValueError, "limit"):
                inspect(data)

    def test_missing_required_files_and_version_mismatch_rejected(self):
        rows = base_members()
        with self.assertRaisesRegex(ValueError, "missing"):
            inspect(archive(members=[row for row in rows if row[0].name != f"{TOP}/COPYING"]))
        rows = [member(info.name, b"VERSION = 5\n") if info.name == f"{TOP}/Makefile" else (info, data) for info, data in rows]
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            inspect(archive(members=rows))

    def test_xz_truncation_trailing_digest_and_memory_limits(self):
        data = lzma.compress(archive())
        self.assertTrue(b"".join(MOD.xz_chunks(io.BytesIO(data), MOD.digest(data))))
        for value, expected in ((data[:-8], MOD.digest(data[:-8])), (data + b"x", MOD.digest(data + b"x")),
                                (data + data, MOD.digest(data + data)), (data, "0" * 64)):
            with self.subTest(length=len(value)), self.assertRaises((ValueError, lzma.LZMAError)):
                b"".join(MOD.xz_chunks(io.BytesIO(value), expected))
        with patch.dict(MOD.LIMITS, {"xz_decoder_bytes": 1}), self.assertRaises(lzma.LZMAError):
            b"".join(MOD.xz_chunks(io.BytesIO(data), MOD.digest(data)))

    def test_cli_rejects_other_profiles_and_no_partial_success_on_bad_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.tar.xz"
            path.write_bytes(lzma.compress(archive()))
            for profile in ("go1.26.7-source", MOD.PROFILE):
                result = subprocess.run([sys.executable, str(SCRIPT), "--profile", profile, str(path)], capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
