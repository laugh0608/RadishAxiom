#!/usr/bin/env python3
"""Independent, bounded review of four offline bootstrap input files.

Checks current repository source bindings and hand-fixed resources / FD roles,
then uses the independent finite E3 interpreter. No native build, setup policy,
image, accepted payload, syscall execution or complete policy bundle is certified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import stat

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "Cargo.toml", "Cargo.lock", "rust-toolchain.toml",
    "crates/axiom-ir/src/solver.rs", "crates/digest/Cargo.toml",
    "crates/digest/src/lib.rs", "crates/solver-supervision-core/Cargo.toml",
    "crates/solver-supervision-core/src/lib.rs",
    "crates/solver-supervision-core/src/abi.rs",
    "crates/solver-supervision-core/src/bootstrap_start.rs",
    "crates/solver-supervision-core/src/handshake.rs",
    "crates/solver-supervision-core/src/policy.rs",
    "crates/solver-supervision-core/src/policy/supervisor.rs",
    "crates/solver-supervision-core/src/wire.rs",
    "crates/solver-supervision-core/src/cgroup.rs",
    "crates/solver-diagnostic-host/Cargo.toml",
    "crates/solver-diagnostic-host/src/lib.rs",
    "crates/solver-diagnostic-host/src/e3_cgroup.rs",
    "crates/solver-diagnostic-host/src/e3_wire.rs",
    "crates/solver-diagnostic-host/src/bootstrap_manifest.rs",
    "crates/solver-diagnostic-host/src/bootstrap_start.rs",
    "crates/solver-diagnostic-host/examples/solver_bootstrap_manifest.rs",
)
FILES = {"manifest.json": 65536, "inputs.json": 16384,
         "worker.cbpf.bin": 32768, "supervisor.cbpf.bin": 32768}
# Previously committed E3 offline-results: F1 must preserve policy bytes,
# in addition to passing the independent finite semantic cases.
POLICY_GOLDEN = {
    "worker.cbpf.bin": "sha256:2f5ff64bffb3b8cd438049d8f33d6ce86f9d3c72f4d61add5eba7da056a04e8f",
    "supervisor.cbpf.bin": "sha256:cf0ff9e3b57b8a0b3fa38414082a128922eb09ad9c14f9a5a227327a9572b57e",
}
MANIFEST_KEYS = ("format", "scope", "generator", "source_inventory_digest",
                 "sources", "inputs", "worker", "supervisor",
                 "outer_setup_policy", "native_build")
# Reviewed numeric contract; never extracted from Rust or its export.
EXPECTED_INPUTS = {
    "resources": {"stdin_bytes": 1048576, "stdout_bytes": 4194304,
                  "stderr_bytes": 65536, "wall_clock_ms": 6000,
                  "working_memory_bytes": 134217728, "swap_bytes": 0,
                  "pids_max": 2, "cgroup_file_bytes": 4096,
                  "semantic_steps": 1000000, "internal_wall_clock_ms": 5000},
    "wire": {"header_bytes": 24, "binding_bytes": 160,
             "payload_bytes": 65536, "chunk_bytes": 65376,
             "control_bytes": 65536, "direction_control_bytes": 32768,
             "pending_bytes": 131072},
    "supervisor_fd_roles": {"control_input": 0, "envelope_output": 1,
                            "diagnostic_output": 2, "child_stdin": 10,
                            "child_stdout": 11, "child_stderr": 12,
                            "timer": 13, "pidfd": 14, "listener": 15,
                            "cgroup": list(range(20, 32))},
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def parse_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, "duplicate-json-key")
            result[key] = value
        return result

    def reject_number(_):
        raise ValueError("non-integer-json-number")

    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs,
                           parse_float=reject_number, parse_constant=reject_number)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid-json") from error
    require(canonical(value) == raw, "noncanonical-json")
    return value


def shape(value, keys):
    require(type(value) is dict and tuple(value) == tuple(keys), "object-shape")


def check_fixed(value, expected):
    require(type(value) is type(expected), "fixed-value-type")
    if isinstance(expected, dict):
        shape(value, expected)
        for key in expected:
            check_fixed(value[key], expected[key])
    elif isinstance(expected, list):
        require(len(value) == len(expected), "fixed-list-length")
        for observed, wanted in zip(value, expected):
            check_fixed(observed, wanted)
    else:
        require(value == expected, "fixed-value-drift")


def read_bounded(path, limit):
    """Reject symlink components, FIFO/device input, oversized or growing files."""
    path = Path(os.path.abspath(path))
    for component in (*reversed(path.parents), path):
        require(not component.is_symlink(), "symlink-input")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), "not-regular-file")
        require(0 < before.st_size <= limit, "file-size-limit")
        parts, count = [], 0
        while count <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - count))
            if not chunk:
                break
            parts.append(chunk)
            count += len(chunk)
        after = os.fstat(fd)
        require(count == before.st_size and count <= limit, "file-size-changed")
        require((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size)
                == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size),
                "file-changed")
        return b"".join(parts)
    finally:
        os.close(fd)


def check_sources(rows, inventory_digest, repository=ROOT, sources=SOURCES):
    require(type(rows) is list and len(rows) == len(sources), "source-inventory-shape")
    for row, wanted in zip(rows, sources):
        shape(row, ("path", "bytes", "digest"))
        require(row["path"] == wanted, "source-path-set-or-order")
        raw = read_bounded(repository / wanted, 2 * 1024 * 1024)
        require(type(row["bytes"]) is int and row["bytes"] == len(raw), "source-length")
        require(row["digest"] == digest(raw), "source-digest")
    require(inventory_digest == digest(canonical(rows)), "source-inventory-digest")


def check_artifact(row, name, raw):
    shape(row, ("file", "bytes", "digest"))
    require(row["file"] == name, "artifact-name")
    require(type(row["bytes"]) is int and row["bytes"] == len(raw), "artifact-length")
    require(row["digest"] == digest(raw), "artifact-digest")


def check_manifest(manifest, blobs, repository=ROOT):
    shape(manifest, MANIFEST_KEYS)
    require(manifest["format"] == "solver-bootstrap-resource-policy-inputs-v0.1",
            "manifest-format")
    require(manifest["scope"] == "offline-pure-inputs-only"
            and manifest["outer_setup_policy"] == "not-established"
            and manifest["native_build"] == "not-accepted", "scope-escalation")
    require(manifest["generator"] == SOURCES[-1], "generator-entry")
    check_sources(manifest["sources"], manifest["source_inventory_digest"], repository)
    for key, name in (("inputs", "inputs.json"), ("worker", "worker.cbpf.bin"),
                      ("supervisor", "supervisor.cbpf.bin")):
        check_artifact(manifest[key], name, blobs[name])
    check_fixed(parse_json(blobs["inputs.json"]), EXPECTED_INPUTS)


def check_exports(directory, repository=ROOT):
    directory = Path(directory)
    require(not directory.is_symlink() and directory.is_dir(), "export-directory")
    require({path.name for path in directory.iterdir()} == set(FILES), "export-file-set")
    blobs = {name: read_bounded(directory / name, limit) for name, limit in FILES.items()}
    check_manifest(parse_json(blobs["manifest.json"]), blobs, repository)
    for name, wanted in POLICY_GOLDEN.items():
        require(digest(blobs[name]) == wanted, "fixed-policy-golden-drift")
    policy = runpy.run_path(str(ROOT / "scripts/check-solver-e3-offline.py"))
    worker_cases = policy["check_worker"](blobs["worker.cbpf.bin"])
    supervisor_cases = policy["check_supervisor"](blobs["supervisor.cbpf.bin"])
    return {"scope": "offline-pure-inputs-only", "source_count": len(SOURCES),
            "manifest_digest": digest(blobs["manifest.json"]),
            "inputs_digest": digest(blobs["inputs.json"]),
            "worker_digest": digest(blobs["worker.cbpf.bin"]),
            "supervisor_digest": digest(blobs["supervisor.cbpf.bin"]),
            "worker_finite_cases": worker_cases, "supervisor_finite_cases": supervisor_cases,
            "outer_setup_policy": "not-established", "native_build": "not-accepted",
            "complete_policy_bundle": "not-established", "runtime_qualification": "not-established"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(check_exports(args.directory), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
