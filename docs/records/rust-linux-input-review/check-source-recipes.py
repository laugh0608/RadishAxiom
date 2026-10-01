#!/usr/bin/env python3
"""Synthetic boundaries for the source recipe diagnostic; no source execution."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "source_recipes", Path(__file__).with_name("inspect-source-recipes.py"))
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


class SourceRecipes(unittest.TestCase):
    def test_exact_identity_required(self):
        for path, value in source.IDENTITIES.items():
            self.assertEqual(source.describe(path, value.encode(), False)["identity_text"], value)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                source.describe(path, (value + "-modified").encode(), False)

    def test_text_is_optional_and_lines_are_preserved(self):
        data = b"heading\nmusl source\n\nCRT and unwind\n"
        row = source.describe("src/ci/docker/scripts/synthetic.sh", data, False)
        self.assertNotIn("text", row)
        self.assertEqual(row["matches"], [
            {"line": 2, "terms": ["musl"]}, {"line": 4, "terms": ["unwind", "crt"]}])
        self.assertEqual(source.describe("synthetic", data, True)["text"], data.decode())

    def test_nontext_and_oversize_are_rejected(self):
        with self.assertRaises(UnicodeDecodeError):
            source.describe("synthetic", b"\xff", False)
        with patch.object(source, "MAX_TEXT", 3), self.assertRaisesRegex(ValueError, "text limit"):
            source.describe("synthetic", b"four", False)

    def test_selection_does_not_include_unrelated_vendored_code(self):
        self.assertTrue(source.selected("src/ci/docker/scripts/musl.sh"))
        self.assertTrue(source.selected("library/unwind/build.rs"))
        self.assertFalse(source.selected("vendor/unrelated/src/lib.rs"))

    def test_size_mismatch_precedes_tar_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.tar.xz"
            path.write_bytes(b"not a tar")
            with patch.object(source.tarfile, "open") as parser:
                with self.assertRaisesRegex(ValueError, "size mismatch"):
                    source.inspect(path, False)
                parser.assert_not_called()

    def test_hash_mismatch_precedes_tar_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.tar.xz"
            path.write_bytes(b"not a tar")
            with patch.object(source, "SOURCE_BYTES", 9), patch.object(source.tarfile, "open") as parser:
                with self.assertRaisesRegex(ValueError, "digest mismatch"):
                    source.inspect(path, False)
                parser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
