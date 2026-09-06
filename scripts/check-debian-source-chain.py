#!/usr/bin/env python3
"""Synthetic boundary checks; mock GnuPG reports do not test cryptography."""

from datetime import datetime, timezone
import importlib.util
import json
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("debian_chain", Path(__file__).with_name("inspect-debian-source-chain.py"))
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def signature_report(body):
    envelope = ("-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n\n" + body +
                "-----BEGIN PGP SIGNATURE-----\nsynthetic, not a signature\n").encode()
    status = "".join(f"[GNUPG:] VALIDSIG {key} 2026-07-11 1 0 4 0 1 8 01 {key}\n"
                     for key in [MOD.BOOKWORM_ARCHIVE, MOD.BOOKWORM_RELEASE])
    return envelope, {"exit_code": 0, "status": status, "inrelease_sha256": MOD.sha256(envelope), "verified_text": body}


def fixture(directory, *, valid_until=""):
    binary, source = b"synthetic binary", b"synthetic source"
    binary_name, source_name = "flex_1_arm64.deb", "flex_1.dsc"
    pool = "pool/main/f/flex/"
    packages = f"Package: flex\nVersion: 1\nArchitecture: arm64\nFilename: {pool}{binary_name}\nSize: {len(binary)}\nSHA256: {MOD.sha256(binary)}\n\n"
    sources = f"Package: flex\nVersion: 1\nDirectory: {pool[:-1]}\nChecksums-Sha256:\n {MOD.sha256(source)} {len(source)} {source_name}\n\n"
    indexes = {"Packages.xz": lzma.compress(packages.encode()), "Sources.xz": lzma.compress(sources.encode())}
    body = "Origin: Debian\nLabel: Debian\nSuite: oldstable\nCodename: bookworm\nVersion: 12.15\nDate: Sat, 11 Jul 2026 10:16:37 UTC\n"
    if valid_until:
        body += "Valid-Until: " + valid_until + "\n"
    body += "SHA256:\n" + "".join(f" {MOD.sha256(data)} {len(data)} {MOD.INDEX_PATHS[name]}\n" for name, data in indexes.items())
    envelope, report = signature_report(body)
    (directory / "InRelease").write_bytes(envelope)
    (directory / "release-verification.json").write_text(json.dumps(report))
    for name, data in {**indexes, binary_name: binary, source_name: source}.items():
        (directory / name).write_bytes(data)
    candidate = {"package": "flex", "version": "1", "source_package": "flex", "source_version": "1", "filename": binary_name,
                 "url": "https://deb.debian.org/debian/" + pool + binary_name,
                 "publisher_bytes": len(binary), "publisher_sha256": MOD.sha256(binary)}
    path = directory / "candidates.json"
    path.write_text(json.dumps({"packages": [candidate]}))
    return path


class DebianChainTests(unittest.TestCase):
    def test_deb822_continuations_and_source_epoch_preserved(self):
        rows = list(MOD.stanzas("Package: bison\nVersion: 2:3.8.2+dfsg-1\nChecksums-Sha256:\n abc\n\n".splitlines(keepends=True)))
        self.assertEqual(rows[0]["version"], "2:3.8.2+dfsg-1")
        self.assertEqual(rows[0]["checksums-sha256"], "\nabc")

    def test_duplicate_fields_orphan_and_incomplete_lines_rejected(self):
        for value in ("Package: a\npackage: b\n", " orphan\n", "Package: a", "Package: a\r\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                list(MOD.stanzas(value.splitlines(keepends=True)))

    def test_checksums_require_sha256_unique_contained_paths(self):
        row = "0" * 64 + " 1 pool/file\n"
        for value in ("f" * 32 + " 1 file\n", row + row, "0" * 64 + " 1 ../escape\n", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MOD.checksums(value)

    def test_required_signers_and_digest_binding(self):
        envelope, report = signature_report("Origin: Debian\n")
        self.assertEqual(len(MOD.signature_observation(report, envelope)), 2)
        for override in ({"exit_code": 2}, {"inrelease_sha256": "0" * 64}, {"verified_text": "other\n"},
                         {"status": report["status"].splitlines(keepends=True)[0]},
                         {"status": report["status"] + "[GNUPG:] BADSIG bad\n"},
                         {"status": report["status"] + report["status"]}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                MOD.signature_observation({**report, **override}, envelope)

    def test_selected_package_cannot_drift_or_repeat(self):
        good = {"package": "flex", "version": "1", "architecture": "arm64"}
        for rows in ([], [good, good], [{**good, "version": "2"}], [{**good, "architecture": "amd64"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                MOD.unique_selection(rows, {"flex": "1"}, binary=True)

    def test_signed_index_digest_and_decode_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.xz"; data = lzma.compress(b"Package: flex\n\n"); path.write_bytes(data)
            expected = {"bytes": len(data), "sha256": MOD.sha256(data)}
            self.assertEqual(list(MOD.index_stanzas(path, expected))[0]["package"], "flex")
            with self.assertRaises(ValueError):
                list(MOD.index_stanzas(path, {**expected, "sha256": "0" * 64}))
            with patch.object(MOD, "MAX_DECODED_BYTES", 1), self.assertRaises(ValueError):
                list(MOD.index_stanzas(path, expected))
            with patch.object(MOD, "MAX_STANZA_BYTES", 1), self.assertRaises(ValueError):
                list(MOD.index_stanzas(path, expected))

    def test_index_truncation_and_concatenation_rejected(self):
        data = lzma.compress(b"Package: flex\n\n")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.xz"
            for value in (data[:-3], data + data, lzma.compress(b"Package: flex")):
                path.write_bytes(value)
                with self.subTest(length=len(value)), self.assertRaises((ValueError, lzma.LZMAError)):
                    list(MOD.index_stanzas(path, {"bytes": len(value), "sha256": MOD.sha256(value)}))

    def test_payload_changes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "payload"; path.write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                MOD.hash_file(path, {"bytes": 3, "sha256": MOD.sha256(b"yes")})

    def test_metadata_only_is_distinct_from_verified_payloads(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); candidates = fixture(directory)
            with patch.object(MOD, "CANDIDATES", candidates):
                now = datetime(2026, 9, 6, tzinfo=timezone.utc)
                self.assertEqual(MOD.inspect(directory, False, now)["payload_verification"], "not-performed")
                result = MOD.inspect(directory, True, now)
                self.assertEqual(result["payload_verification"], "all-lengths-and-sha256-match")
                self.assertEqual(result["acceptance"], "not-assessed")
                self.assertIn("no-publisher-expiry", result["freshness"])
                (directory / "flex_1.dsc").write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    MOD.inspect(directory, True, now)

    def test_release_expiry_or_future_date_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); candidates = fixture(directory, valid_until="Sat, 01 Aug 2026 00:00:00 UTC")
            with patch.object(MOD, "CANDIDATES", candidates):
                for now in (datetime(2026, 9, 6, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)):
                    with self.subTest(now=now), self.assertRaises(ValueError):
                        MOD.inspect(directory, False, now)


if __name__ == "__main__":
    unittest.main()
