#!/usr/bin/env python3
"""合成负例只测试离线观察边界，不执行任何下载内容。"""
import json
import copy
import os
from pathlib import Path
import runpy
import tempfile
import unittest

M = runpy.run_path(str(Path(__file__).with_name("check-cvc5-provenance-followup.py")))


class Boundaries(unittest.TestCase):
    def test_artifact_count_conflict(self):
        with self.assertRaisesRegex(ValueError, "artifact-count-body"):
            M["classify"]("run-artifacts.json", b'{"total_count":1,"artifacts":[]}', {})

    def test_artifact_hidden_page(self):
        with self.assertRaisesRegex(ValueError, "pagination"):
            M["classify"]("run-artifacts.json", b'{"total_count":0,"artifacts":[]}', {"link": '<x>; rel="next"'})

    def test_error_status_and_body_are_distinct(self):
        with self.assertRaisesRegex(ValueError, "attestation-error-body"):
            M["classify"]("cli-attestations.json", b'{"status":"200","message":"Not Found"}', {})

    def test_unsafe_or_alien_path(self):
        with self.assertRaisesRegex(ValueError, "source-file-name"):
            M["read_source"](Path("."), {"file": "../run-artifacts.json"})

    def test_hash_and_http_status(self):
        name = "run-artifacts.json"
        url, status = M["EXPECTED"][name]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / name
            path.write_bytes(b'{}')
            row = {"file": name, "url": url, "http_status": status, "bytes": 2, "raw_digest": M["digest"](b'[]')}
            with self.assertRaisesRegex(ValueError, "digest-mismatch"):
                M["read_source"](Path(directory), row)
            row["raw_digest"] = M["digest"](b'{}')
            row["http_status"] = 403
            with self.assertRaisesRegex(ValueError, "request-mismatch"):
                M["read_source"](Path(directory), row)

    def test_size_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(b'12345')
            with self.assertRaisesRegex(ValueError, "size-limit"):
                M["read_bounded"](path, 4)
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "symlink"):
                M["read_bounded"](link)

    def test_non_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fifo"
            os.mkfifo(path)
            with self.assertRaisesRegex(ValueError, "not-regular-file"):
                M["read_bounded"](path)

    def test_recipe_identity_and_not_obtained_state(self):
        manifest = json.loads((M["RECORD"] / "source-inputs.json").read_bytes())
        prior = json.loads((M["PRIOR"] / "dependency-observation.json").read_bytes())
        recipes = prior["declared_fallback_recipes_not_proven_binary_inputs"]
        for field, value in [("recipe_url", "https://example.invalid/source"),
                             ("archive_sha256", "0" * 64), ("status", "obtained"),
                             ("recomputed_archive_digest", "sha256:" + "0" * 64),
                             ("actual_binary_link", "recipe-is-not-binary-proof")]:
            with self.subTest(field=field):
                download = copy.deepcopy(manifest["archive_download"])
                download["archives"][0][field] = value
                with self.assertRaisesRegex(ValueError, "archive-recipe-observation"):
                    M["check_archives"](download, recipes)


if __name__ == "__main__":
    unittest.main()
