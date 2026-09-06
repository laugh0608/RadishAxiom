#!/usr/bin/env python3
"""Check rejection boundaries of the read-only Linux builder inventory."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).with_name("inspect-linux-builder.py")
SPEC = importlib.util.spec_from_file_location("linux_builder_inventory", SOURCE)
assert SPEC is not None and SPEC.loader is not None
INVENTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVENTORY)


class InventoryBoundaryTests(unittest.TestCase):
    def test_multiarch_and_source_identity_are_preserved(self) -> None:
        rows = INVENTORY.parse_packages(
            "libc6:amd64\t2.36-1\tamd64\tinstalled\tglibc\t2.36-1\n"
            "libc6:arm64\t2.36-1\tarm64\tinstalled\tglibc\t2.36-1\n"
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["source"], "glibc")

    def test_noninstalled_package_is_not_relabelled(self) -> None:
        rows = INVENTORY.parse_packages(
            "old-tool\t1.0\tarm64\tconfig-files\told-tool\t1.0\n"
        )
        self.assertEqual(rows[0]["status"], "config-files")

    def test_bad_package_rows_are_rejected(self) -> None:
        row = "gcc\t12.2\tarm64\tinstalled\tgcc-defaults\t1.0\n"
        for text in ("", row + row, "gcc\t12.2\tarm64\n", row.replace("12.2", "")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                INVENTORY.parse_packages(text)

    def test_other_host_is_not_treated_as_linux(self) -> None:
        with patch.object(INVENTORY.sys, "platform", "darwin"):
            with self.assertRaisesRegex(ValueError, "Linux is required"):
                INVENTORY.inventory()

    def test_package_query_failure_is_not_an_empty_success(self) -> None:
        with (
            patch.object(INVENTORY.sys, "platform", "linux"),
            patch.object(INVENTORY, "os_release", return_value={"ID": "debian"}),
            patch.object(INVENTORY.shutil, "which", return_value="/usr/bin/dpkg-query"),
            patch.object(INVENTORY, "run", return_value={
                "exit_code": "2", "stdout": "", "stderr": "database unavailable",
            }),
        ):
            with self.assertRaisesRegex(ValueError, "database unavailable"):
                INVENTORY.inventory()

    def test_timed_out_probe_does_not_produce_valid_inventory(self) -> None:
        with patch.object(
            INVENTORY.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(["/bin/probe"], 3),
        ):
            with self.assertRaisesRegex(ValueError, "timed out"):
                INVENTORY.run(["/bin/probe"])


if __name__ == "__main__":
    unittest.main()
