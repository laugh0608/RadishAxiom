#!/usr/bin/env python3
"""构建 patch 仅文本应用的合成边界；不执行第三方代码或构建工具。"""
from pathlib import Path
import runpy
import tempfile
import unittest

M = runpy.run_path(str(Path(__file__).with_name("check-cvc5-build-patch.py")))
PATCH = (b"diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
         b"@@ -1,2 +1,2 @@\n first\n-old\n+new\n")


class ExactPatch(unittest.TestCase):
    def apply(self, patch=PATCH, original=b"first\nold\n"):
        return M["apply_exact"](patch, {"a.txt": original}, {"a.txt"})

    def test_exact_success(self):
        self.assertEqual(self.apply(), {"a.txt": b"first\nnew\n"})

    def test_no_offset(self):
        with self.assertRaisesRegex(ValueError, "preimage-mismatch"):
            self.apply(original=b"extra\nfirst\nold\n")

    def test_no_fuzz(self):
        with self.assertRaisesRegex(ValueError, "preimage-mismatch"):
            self.apply(original=b"changed-context\nold\n")

    def test_truncated_hunk(self):
        with self.assertRaisesRegex(ValueError, "truncated-or-count"):
            self.apply(PATCH.removesuffix(b"+new\n"))

    def test_added_line_trailing_whitespace_rejected(self):
        for trailing in (b" ", b"\t"):
            with self.subTest(trailing=trailing), self.assertRaisesRegex(ValueError, "added-trailing-whitespace"):
                self.apply(PATCH.replace(b"+new\n", b"+new" + trailing + b"\n"))

    def test_truncated_header(self):
        with self.assertRaisesRegex(ValueError, "file-header"):
            self.apply(b"diff --git a/a.txt b/a.txt\n")

    def test_no_path_escape(self):
        for name in (b"../a.txt", b"/a.txt", b"a/../../x", b"a/./x", b".git/config", b"a\\x"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.apply(PATCH.replace(b"a.txt", name))

    def test_no_extra_file(self):
        with self.assertRaisesRegex(ValueError, "file-set"):
            self.apply(PATCH + PATCH.replace(b"a.txt", b"extra.txt"))

    def test_no_duplicate_file(self):
        with self.assertRaisesRegex(ValueError, "file-set"):
            self.apply(PATCH + PATCH)

    def test_no_bare_search_left_behind(self):
        for command in (b"find_path(X NAMES x)", b"FIND_LIBRARY (X x)", b"find_program(x sh)",
                        b"ExternalProject_Add(x)", b"pkg_check_modules(x y)", b"try_run(x)"):
            with self.subTest(command=command), self.assertRaisesRegex(ValueError, "fallback-left"):
                M["check_no_fallback"]({"cmake/FindGMP.cmake": command})

    def test_no_bare_link(self):
        for item in (b"set(X -ltinfo)", b"set(X bsd)", b"set(X md)", b"set(X tinfo)"):
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, "bare-link-left"):
                M["check_no_fallback"]({"cmake/FindEditline.cmake": item})

    def test_new_file(self):
        patch = (b"diff --git a/new b/new\nnew file mode 100644\n--- /dev/null\n+++ b/new\n"
                 b"@@ -0,0 +1,1 @@\n+content\n")
        self.assertEqual(M["apply_exact"](patch, {}, {"new"}), {"new": b"content\n"})

    def test_inventory_detects_extra_and_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").write_bytes(b"original")
            before = M["digest"](M["canonical"](M["inventory"](root)))
            (root / "extra").write_bytes(b"extra")
            self.assertNotEqual(before, M["digest"](M["canonical"](M["inventory"](root))))
            (root / "a").write_bytes(b"modified")
            self.assertNotEqual(before, M["digest"](M["canonical"](M["inventory"](root))))

    def test_inventory_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").write_bytes(b"original")
            (root / "link").symlink_to("a")
            with self.assertRaisesRegex(ValueError, "symlink"):
                M["inventory"](root)

    def test_wrong_upstream(self):
        record = {"format": "radishaxiom-cvc5-build-patch-review", "version": "0.1",
                  "upstream_commit": "0" * 40}
        with self.assertRaisesRegex(ValueError, "upstream-identity"):
            M["inspect"](Path("not-read"), Path("not-read"), record)

    def test_no_review_acceptance_overclaim(self):
        record = {"format": "radishaxiom-cvc5-build-patch-review", "version": "0.1",
                  "upstream_commit": M["COMMIT"], "build_ready": True, "acceptance": "accepted"}
        with self.assertRaisesRegex(ValueError, "acceptance-overclaim"):
            M["inspect"](Path("not-read"), Path("not-read"), record)

    def test_no_execution_overclaim(self):
        record = {"format": "radishaxiom-cvc5-build-patch-review", "version": "0.1",
                  "upstream_commit": M["COMMIT"], "build_ready": False, "acceptance": "not-accepted",
                  "scope": "static-text-review-only-not-configure-or-build", "actual_dependency_manifest": None,
                  "actual_sdk_archive_inputs": None, "patch_state": "prepared-static-candidate-not-executed",
                  "executed": ["CMake"], "not_executed": []}
        with self.assertRaisesRegex(ValueError, "execution-overclaim"):
            M["inspect"](Path("not-read"), Path("not-read"), record)


if __name__ == "__main__":
    unittest.main()
