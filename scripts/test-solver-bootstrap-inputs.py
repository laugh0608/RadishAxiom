#!/usr/bin/env python3
"""Synthetic rejection checks for bootstrap input review; no Rust/native execution."""
import copy
import os
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

M = runpy.run_path(str(Path(__file__).with_name("check-solver-bootstrap-inputs.py")))
POLICY = runpy.run_path(str(Path(__file__).with_name("check-solver-e3-offline.py")))


class Boundaries(unittest.TestCase):
    def test_json_strictness(self):
        for raw in (b'{"x":1,"x":1}', b'{ "x":1}', b'{"x":1}\n',
                    b'{"x":1.0}', b'{"x":NaN}', b'{"x":"\\u0061"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                M["parse_json"](raw)
        self.assertEqual(M["parse_json"](b'{"x":1}'), {"x": 1})

    def test_numeric_type_and_resources(self):
        expected = M["EXPECTED_INPUTS"]
        for section, key, value in (("resources", "wall_clock_ms", 6001),
                                    ("resources", "swap_bytes", False),
                                    ("resources", "working_memory_bytes", 268435456),
                                    ("wire", "chunk_bytes", 65536),
                                    ("supervisor_fd_roles", "listener", 16)):
            drifted = copy.deepcopy(expected)
            drifted[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                M["check_fixed"](drifted, expected)
        extra = copy.deepcopy(expected)
        extra["supervisor_fd_roles"]["cgroup"][-1] = 20
        with self.assertRaises(ValueError):
            M["check_fixed"](extra, expected)

    def test_file_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "file"
            path.write_bytes(b"12345")
            self.assertEqual(M["read_bounded"](path, 5), b"12345")
            with self.assertRaisesRegex(ValueError, "size-limit"):
                M["read_bounded"](path, 4)
            (root / "link").symlink_to(path)
            with self.assertRaisesRegex(ValueError, "symlink"):
                M["read_bounded"](root / "link", 5)
            os.mkfifo(root / "fifo")
            with self.assertRaisesRegex(ValueError, "not-regular"):
                M["read_bounded"](root / "fifo", 5)
            with self.assertRaisesRegex(ValueError, "not-regular"):
                M["read_bounded"](root, 5)
            nested = root / "nested"
            nested.mkdir()
            (nested / "file").write_bytes(b"x")
            (root / "alias").symlink_to(nested, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                M["read_bounded"](root / "alias/file", 5)

    def fixture(self, directory):
        root = Path(directory).resolve()
        rows = []
        for name in M["SOURCES"]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = (name + "\n").encode()
            path.write_bytes(raw)
            rows.append({"path": name, "bytes": len(raw), "digest": M["digest"](raw)})
        blobs = {"inputs.json": M["canonical"](M["EXPECTED_INPUTS"]),
                 "worker.cbpf.bin": b"worker", "supervisor.cbpf.bin": b"supervisor"}
        manifest = {"format": "solver-bootstrap-resource-policy-inputs-v0.1",
                    "scope": "offline-pure-inputs-only", "generator": M["SOURCES"][-1],
                    "source_inventory_digest": M["digest"](M["canonical"](rows)),
                    "sources": rows}
        for key, name in (("inputs", "inputs.json"), ("worker", "worker.cbpf.bin"),
                          ("supervisor", "supervisor.cbpf.bin")):
            manifest[key] = {"file": name, "bytes": len(blobs[name]),
                             "digest": M["digest"](blobs[name])}
        manifest.update(outer_setup_policy="not-established", native_build="not-accepted")
        return root, rows, blobs, manifest

    def test_source_path_inventory_and_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rows, _, _ = self.fixture(directory)
            correct = M["digest"](M["canonical"](rows))
            M["check_sources"](rows, correct, root)
            for path in ("../Cargo.toml", "/Cargo.toml", "Cargo.lock", "./Cargo.toml"):
                changed = copy.deepcopy(rows)
                changed[0]["path"] = path
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "source-path"):
                    M["check_sources"](changed, M["digest"](M["canonical"](changed)), root)
            with self.assertRaisesRegex(ValueError, "inventory-digest"):
                M["check_sources"](rows, "sha256:" + "0" * 64, root)
            (root / M["SOURCES"][0]).write_bytes(b"altered source")
            with self.assertRaisesRegex(ValueError, "source-length|source-digest"):
                M["check_sources"](rows, correct, root)

    def test_manifest_scope_shape_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, blobs, manifest = self.fixture(directory)
            M["check_manifest"](manifest, blobs, root)
            for key, value in (("scope", "native-accepted"), ("outer_setup_policy", "accepted"),
                               ("native_build", "accepted"), ("generator", "other.rs"),
                               ("extra", 1)):
                changed = copy.deepcopy(manifest)
                changed[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    M["check_manifest"](changed, blobs, root)
            changed = copy.deepcopy(manifest)
            changed["worker"]["digest"] = M["digest"](b"different")
            with self.assertRaisesRegex(ValueError, "artifact-digest"):
                M["check_manifest"](changed, blobs, root)

    def test_rehashed_resource_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, blobs, manifest = self.fixture(directory)
            values = copy.deepcopy(M["EXPECTED_INPUTS"])
            values["resources"]["wall_clock_ms"] = 12000
            blobs["inputs.json"] = M["canonical"](values)
            manifest["inputs"]["bytes"] = len(blobs["inputs.json"])
            manifest["inputs"]["digest"] = M["digest"](blobs["inputs.json"])
            with self.assertRaisesRegex(ValueError, "fixed-value-drift"):
                M["check_manifest"](manifest, blobs, root)

    def test_all_allow_policy_rejected_independently(self):
        allow = struct.pack("<HBBI", 6, 0, 0, POLICY["ALLOW"])
        for name in ("check_worker", "check_supervisor"):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                POLICY[name](allow)

    def test_rehashed_all_allow_export_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, blobs, manifest = self.fixture(directory)
            allow = struct.pack("<HBBI", 6, 0, 0, POLICY["ALLOW"])
            for key, name in (("worker", "worker.cbpf.bin"),
                              ("supervisor", "supervisor.cbpf.bin")):
                blobs[name] = allow
                manifest[key] = {"file": name, "bytes": len(allow),
                                 "digest": M["digest"](allow)}
            export = root / "export"
            export.mkdir()
            for name, raw in blobs.items():
                (export / name).write_bytes(raw)
            (export / "manifest.json").write_bytes(M["canonical"](manifest))
            # All self-reported lengths and digests agree, but the reviewed
            # E3 bytes are immutable even if finite semantics could agree.
            M["check_manifest"](manifest, blobs, root)
            with self.assertRaisesRegex(ValueError, "fixed-policy-golden-drift"):
                M["check_exports"](export, root)

    def test_exact_export_files(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "export-file-set"):
                M["check_exports"](Path(directory))


if __name__ == "__main__":
    unittest.main()
