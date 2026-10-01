#!/usr/bin/env python3
"""Synthetic checks for dependency observations, not loader/crypto acceptance."""

import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest


spec = importlib.util.spec_from_file_location(
    "host_dependencies", Path(__file__).with_name("inspect-host-dependencies.py"))
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def elf(machine=183):
    data = bytearray(128)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, machine)
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 0, 0, 0, 0, 128, 128, 1)
    return bytes(data)


def expected(data):
    return {"path": "synthetic/bin/tool", "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def row(path, needed, interpreter=None):
    return {"path": path, "elf": {"needed": needed, "interpreter": interpreter}}


class HostDependencies(unittest.TestCase):
    def test_bound_aarch64(self):
        result = host.inspect_member(elf(), expected(elf()))
        self.assertEqual(result["elf"]["machine"], 183)
        self.assertEqual(result["elf"]["needed"], [])

    def test_modified_bytes_rejected(self):
        altered = bytearray(elf())
        altered[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            host.inspect_member(altered, expected(elf()))

    def test_size_and_architecture_rejected(self):
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            host.inspect_member(elf()[:-1], expected(elf()))
        with self.assertRaisesRegex(ValueError, "not AArch64"):
            host.inspect_member(elf(62), expected(elf(62)))

    def test_malformed_segment_rejected_after_valid_digest(self):
        data = bytearray(elf())
        struct.pack_into("<Q", data, 72, 900)
        with self.assertRaisesRegex(ValueError, "segment outside file"):
            host.inspect_member(data, expected(data))

    def test_transitive_external_names_remain_visible(self):
        graph = host.dependency_names([
            row("bin/tool", ["driver.so"], "/lib/loader.so"),
            row("lib/driver.so", ["LLVM.so"]),
            row("lib/LLVM.so", ["libz.so", "libc.so"]),
        ])
        self.assertEqual(graph["external_needed_names"], ["libc.so", "libz.so"])
        self.assertEqual(graph["interpreters"], ["/lib/loader.so"])
        self.assertTrue(all(e["loader_resolution"] == "not-assessed" for e in graph["edges"]))

    def test_ambiguous_basename_is_not_resolved(self):
        graph = host.dependency_names([
            row("bin/tool", ["driver.so"]), row("one/driver.so", []), row("two/driver.so", [])])
        self.assertEqual(graph["edges"][0]["bundled_name_candidates"],
                         ["one/driver.so", "two/driver.so"])
        self.assertEqual(graph["edges"][0]["loader_resolution"], "not-assessed")


if __name__ == "__main__":
    unittest.main()
