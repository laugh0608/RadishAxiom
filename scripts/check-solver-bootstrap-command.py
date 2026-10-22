#!/usr/bin/env python3
"""Independently check AXBCMD01 and source bindings; never certify native execution."""
import argparse
import json
from pathlib import Path
import runpy
import struct

BASE = runpy.run_path(str(Path(__file__).with_name("check-solver-bootstrap-inputs.py")))
ROOT = BASE["ROOT"]
require = BASE["require"]
SOURCES = (
    "Cargo.toml", "Cargo.lock", "rust-toolchain.toml",
    "crates/axiom-ir/src/solver.rs", "crates/digest/Cargo.toml",
    "crates/digest/src/lib.rs", "crates/solver-diagnostic-host/Cargo.toml",
    "crates/solver-diagnostic-host/src/lib.rs",
    "crates/solver-diagnostic-host/src/bootstrap_command.rs",
    "crates/solver-diagnostic-host/examples/solver_bootstrap_command.rs",
)
# Reviewed command contract; do not extract expectations from Rust or its export.
TOKENS = (
    "--safe-mode=safe", "--strict-parsing", "--force-logic=QF_UFLIA",
    "--lang=smt2", "--no-incremental", "--produce-models", "--dump-models",
    "--check-models", "--produce-proofs", "--check-proofs",
    "--rlimit-per=1000000", "--tlimit-per=5000",
)


def decode_command(raw):
    require(12 <= len(raw) <= 4096, "command-size")
    require(raw[:8] == b"AXBCMD01", "command-version")
    require(struct.unpack_from(">I", raw, 8)[0] == 12, "command-count")
    offset, tokens = 12, []
    for _ in range(12):
        require(offset + 4 <= len(raw), "command-truncated-length")
        size = struct.unpack_from(">I", raw, offset)[0]
        offset += 4
        require(1 <= size <= 128, "command-token-size")
        require(offset + size <= len(raw), "command-truncated-token")
        token = raw[offset:offset + size]
        offset += size
        require(token.startswith(b"--") and all(0x21 <= b <= 0x7e for b in token),
                "command-token-encoding")
        tokens.append(token.decode("ascii"))
    require(offset == len(raw), "command-trailing")
    require(tuple(tokens) == TOKENS, "fixed-command-drift")
    return tokens


def check_manifest(manifest, command, repository=ROOT):
    BASE["shape"](manifest, ("format", "scope", "generator", "source_inventory_digest",
                             "sources", "command", "native_build"))
    require(manifest["format"] == "solver-bootstrap-command-input-v0.1", "manifest-format")
    require(manifest["scope"] == "offline-command-inputs-only"
            and manifest["native_build"] == "not-accepted", "scope-escalation")
    require(manifest["generator"] == SOURCES[-1], "generator-entry")
    BASE["check_sources"](manifest["sources"], manifest["source_inventory_digest"],
                          repository, sources=SOURCES)
    BASE["check_artifact"](manifest["command"], "command.bin", command)
    decode_command(command)


def check_exports(directory, repository=ROOT):
    directory = Path(directory)
    require(not directory.is_symlink() and directory.is_dir(), "export-directory")
    require({p.name for p in directory.iterdir()} == {"manifest.json", "command.bin"},
            "export-file-set")
    manifest = BASE["read_bounded"](directory / "manifest.json", 65536)
    command = BASE["read_bounded"](directory / "command.bin", 4096)
    check_manifest(BASE["parse_json"](manifest), command, repository)
    return {"scope": "offline-command-inputs-only", "source_count": len(SOURCES),
            "manifest_digest": BASE["digest"](manifest), "command_bytes": len(command),
            "command_digest": BASE["digest"](command), "argument_count": len(TOKENS),
            "native_build": "not-accepted", "runtime_qualification": "not-established"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(check_exports(args.directory), indent=2, sort_keys=True))
