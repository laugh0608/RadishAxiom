#!/usr/bin/env python3
"""Inspect selected host components' ELF dependencies; never load or execute ELF.

This diagnostic reuses the retained archive reader and ELF observer. Name matches
are inventory candidates, not dynamic-loader resolution or source acceptance.
"""

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import tarfile


HERE = Path(__file__).resolve().parent
INVENTORY_SHA = "53ab99369b0cc344bd732feb749873d0c2d1b2ec59a591ece983bc67f41f2a7f"
TOP = "rust-1.97.1-aarch64-unknown-linux-gnu"
COMPONENTS = {"rustc", "cargo", "rust-std-aarch64-unknown-linux-gnu"}
MAX_ELF = 192 * 1024**2


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive_method = load("retained_rust_archive", "inspect-archives.py")
elf_method = load("retained_rust_elf", "inspect-selected-inputs.py")


def inventory():
    compressed = (HERE / "archive-inventory.json.gz").read_bytes()
    if hashlib.sha256(compressed).hexdigest() != INVENTORY_SHA:
        raise ValueError("retained inventory hash mismatch")
    # The compressed bytes are pinned before decoding; this is not a public reader.
    result = json.loads(gzip.decompress(compressed))
    host = next(a for a in result["archives"] if a["file"] == TOP + ".tar.xz")
    selected = {r["path"]: r for r in host["members"]
                if r.get("elf_header") and r["path"].split("/")[1] in COMPONENTS}
    if not selected:
        raise ValueError("no selected ELF inputs")
    return host, selected


def inspect_member(content, expected):
    if len(content) != expected["bytes"] or len(content) > MAX_ELF:
        raise ValueError("selected ELF size mismatch or limit")
    if hashlib.sha256(content).hexdigest() != expected["sha256"]:
        raise ValueError("selected ELF hash mismatch")
    elf = elf_method.elf_dependencies(content)
    if elf["machine"] != 183:
        raise ValueError("selected ELF is not AArch64")
    return {"path": expected["path"], "bytes": len(content),
            "sha256": expected["sha256"], "elf": elf}


def dependency_names(rows):
    names = {}
    for row in rows:
        name = row["path"].rsplit("/", 1)[-1]
        names.setdefault(name, []).append(row["path"])
    edges, external = [], set()
    for row in rows:
        for needed in row["elf"]["needed"]:
            candidates = sorted(names.get(needed, []))
            edges.append({"from": row["path"], "needed": needed,
                          "bundled_name_candidates": candidates,
                          "loader_resolution": "not-assessed"})
            if not candidates:
                external.add(needed)
    return {"edges": edges, "external_needed_names": sorted(external),
            "interpreters": sorted({r["elf"]["interpreter"] for r in rows
                                    if r["elf"]["interpreter"]}),
            "system_library_bytes": "not-inspected",
            "symbol_versions": "not-inspected",
            "dlopen_and_subprocess_dependencies": "not-inspected"}


def inspect(path):
    host, selected = inventory()
    rows, seen = [], set()
    with path.open("rb") as source:
        # Hash before parsing; XzReader also hashes the bytes actually consumed.
        if hashlib.file_digest(source, "sha256").hexdigest() != host["sha256"]:
            raise ValueError("pinned host archive mismatch")
        source.seek(0)
        reader = archive_method.XzReader(source, host["sha256"])
        with tarfile.open(fileobj=reader, mode="r|", bufsize=512) as tar:
            for member in tar:
                if member.name not in selected:
                    continue
                if member.name in seen or not member.isfile() or member.size > MAX_ELF:
                    raise ValueError("duplicate, non-file or oversized ELF")
                if member.size != selected[member.name]["bytes"]:
                    raise ValueError("ELF header size differs from inventory")
                seen.add(member.name)
                rows.append(inspect_member(tar.extractfile(member).read(), selected[member.name]))
        while data := reader.read(archive_method.BLOCK):
            if any(data):
                raise ValueError("nonzero tar tail")
        if seen != set(selected):
            raise ValueError("missing selected ELF")
        if reader.tar_bytes != host["tar_bytes"] or reader.tar_hash.hexdigest() != host["tar_sha256"]:
            raise ValueError("tar bytes differ from retained inventory")
    rows.sort(key=lambda r: r["path"])
    methods = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
               for name in (Path(__file__).name, "inspect-archives.py", "inspect-selected-inputs.py")}
    return {"kind": "diagnostic-observation", "acceptance": "not-assessed",
            "python": platform.python_version(), "methods": methods,
            "inventory_sha256": INVENTORY_SHA,
            "archive": {k: host[k] for k in ("file", "bytes", "sha256", "tar_bytes", "tar_sha256")},
            "selected_components": sorted(COMPONENTS), "elf_files": rows,
            "dependencies": dependency_names(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host_archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.host_archive), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
