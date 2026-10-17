#!/usr/bin/env python3
"""Finite synthetic checks for the independent AXBCMD01 input checker."""
import copy
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

M = runpy.run_path(str(Path(__file__).with_name("check-solver-bootstrap-command.py")))
B = M["BASE"]


def encode(tokens=M["TOKENS"]):
    return b"AXBCMD01" + struct.pack(">I", len(tokens)) + b"".join(
        struct.pack(">I", len(token)) + token.encode("ascii") for token in tokens)


class Boundaries(unittest.TestCase):
    def test_exact_and_all_truncations(self):
        raw = encode()
        self.assertEqual(M["decode_command"](raw), list(M["TOKENS"]))
        for size in range(len(raw)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                M["decode_command"](raw[:size])

    def test_version_count_lengths_and_tail(self):
        raw = encode()
        for altered in (b"AXBCMD02" + raw[8:], raw[:8] + struct.pack(">I", 11) + raw[12:],
                        raw[:12] + struct.pack(">I", 129) + raw[16:],
                        raw[:12] + struct.pack(">I", 0) + raw[16:], raw + b"x",
                        raw + b"x" * 4096):
            with self.assertRaises(ValueError):
                M["decode_command"](altered)

    def test_encoding_and_rehashed_fixed_argument_drift(self):
        for replacement in ("--tlimit-per=6000", "--foo=bar", "--nul=\x00", "--a b", "x"):
            tokens = list(M["TOKENS"])
            tokens[-1] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                M["decode_command"](encode(tokens))

    def fixture(self, root):
        rows = []
        for name in M["SOURCES"]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = (name + "\n").encode()
            path.write_bytes(raw)
            rows.append({"path": name, "bytes": len(raw), "digest": B["digest"](raw)})
        command = encode()
        manifest = {"format": "solver-bootstrap-command-input-v0.1",
                    "scope": "offline-command-inputs-only", "generator": M["SOURCES"][-1],
                    "source_inventory_digest": B["digest"](B["canonical"](rows)),
                    "sources": rows, "command": {"file": "command.bin", "bytes": len(command),
                                                   "digest": B["digest"](command)},
                    "native_build": "not-accepted"}
        return manifest, command

    def test_scope_source_and_artifact_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, command = self.fixture(root)
            M["check_manifest"](manifest, command, root)
            for key, value in (("native_build", "accepted"), ("scope", "accepted"),
                               ("generator", "other.rs"), ("extra", 1)):
                altered = copy.deepcopy(manifest)
                altered[key] = value
                with self.assertRaises(ValueError):
                    M["check_manifest"](altered, command, root)
            altered = copy.deepcopy(manifest)
            altered["sources"][0]["path"] = "../Cargo.toml"
            with self.assertRaises(ValueError):
                M["check_manifest"](altered, command, root)
            with self.assertRaises(ValueError):
                M["check_manifest"](manifest, command[:-1] + b"1", root)
            (root / M["SOURCES"][0]).write_bytes(b"changed")
            with self.assertRaises(ValueError):
                M["check_manifest"](manifest, command, root)

    def test_export_exact_files_and_rehashed_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, command = self.fixture(root)
            output = root / "export"
            output.mkdir()
            (output / "command.bin").write_bytes(command)
            (output / "manifest.json").write_bytes(B["canonical"](manifest))
            self.assertEqual(M["check_exports"](output, root)["argument_count"], 12)
            altered = command.replace(b"--tlimit-per=5000", b"--tlimit-per=6000")
            manifest["command"]["digest"] = B["digest"](altered)
            (output / "command.bin").write_bytes(altered)
            (output / "manifest.json").write_bytes(B["canonical"](manifest))
            with self.assertRaisesRegex(ValueError, "fixed-command-drift"):
                M["check_exports"](output, root)
            (output / "extra").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "export-file-set"):
                M["check_exports"](output, root)


if __name__ == "__main__":
    unittest.main()
