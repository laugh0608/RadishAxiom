#!/usr/bin/env python3
"""Read build recipes from pinned Rust source without extracting or executing it.

The output is a source diagnostic, not proof of how the published binary was
built. Use --include-text only for local review; retain the original source tar.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import tarfile


HERE = Path(__file__).resolve().parent
TOP = "rustc-1.97.1-src"
SOURCE_BYTES = 242787896
SOURCE_SHA = "0ed06fdaffd4722a7702e0b4eebfafc897ab8f513e8e1b247cdd7e5c6df6ded2"
COMMIT = "8bab26f4f68e0e26f0bb7960be334d5b520ea452"
IDENTITIES = {"git-commit-hash": COMMIT,
              "version": "1.97.1 (8bab26f4f 2026-07-14)"}
FIXED = {
    *IDENTITIES, "COPYRIGHT", "LICENSE-MIT", "LICENSE-APACHE", "license-metadata.json",
    "compiler/rustc_target/src/spec/targets/aarch64_unknown_linux_musl.rs",
    "compiler/rustc_target/src/spec/base/linux_musl.rs",
    "compiler/rustc_target/src/spec/crt_objects.rs",
    "src/bootstrap/src/lib.rs",
    "src/bootstrap/src/core/build_steps/compile.rs",
    "src/bootstrap/src/core/build_steps/llvm.rs",
    "library/unwind/build.rs", "library/unwind/Cargo.toml",
    "src/llvm-project/libunwind/LICENSE.TXT", "src/llvm-project/libunwind/CMakeLists.txt",
    "src/llvm-project/compiler-rt/LICENSE.TXT", "src/llvm-project/compiler-rt/CMakeLists.txt",
    "src/llvm-project/compiler-rt/lib/builtins/crtbegin.c",
    "src/llvm-project/compiler-rt/lib/builtins/crtend.c",
    "src/llvm-project/compiler-rt/lib/builtins/CMakeLists.txt",
}
TERMS = ("musl", "unwind", "crt", "crosstool", "sha256", "compiler_builtins", "compiler-builtins")
MAX_TEXT = 4 * 1024**2
MAX_TEXT_TOTAL = 16 * 1024**2

spec = importlib.util.spec_from_file_location("retained_rust_archive", HERE / "inspect-archives.py")
archive_method = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_method)


def selected(path):
    return path in FIXED or path.startswith(("src/ci/docker/", "src/bootstrap/src/core/config/",
        "src/llvm-project/libunwind/src/", "src/llvm-project/libunwind/include/")) or (
        path.startswith("library/compiler-builtins/") and
        Path(path).name in {"Cargo.toml", "build.rs", "LICENSE.txt", "LICENSE", "README.md"})


def describe(path, content, include_text):
    if len(content) > MAX_TEXT:
        raise ValueError("selected source text limit")
    text = content.decode("utf-8")
    if path in IDENTITIES and text.strip() != IDENTITIES[path]:
        raise ValueError("source identity mismatch")
    matches = []
    for number, line in enumerate(text.splitlines(), 1):
        terms = [term for term in TERMS if term in line.lower()]
        if terms:
            matches.append({"line": number, "terms": terms})
    row = {"path": TOP + "/" + path, "bytes": len(content),
           "sha256": hashlib.sha256(content).hexdigest(), "matches": matches}
    if path in IDENTITIES:
        row["identity_text"] = text.strip()
    if include_text:
        row["text"] = text
    return row


def inspect(path, include_text):
    rows, seen = [], set()
    count = captured = 0
    with path.open("rb") as source:
        if path.stat().st_size != SOURCE_BYTES:
            raise ValueError("source archive size mismatch")
        if hashlib.file_digest(source, "sha256").hexdigest() != SOURCE_SHA:
            raise ValueError("source archive digest mismatch")
        source.seek(0)
        reader = archive_method.XzReader(source, SOURCE_SHA)
        with tarfile.open(fileobj=reader, mode="r|", bufsize=512) as tar:
            for member in tar:
                count += 1
                if count > 400000 or member.size > 64 * 1024**2 or member.size < 0:
                    raise ValueError("source member count or size limit")
                name = archive_method.path_name(member.name, TOP, member.isdir())
                relative = name[len(TOP) + 1:]
                if member.isdir() or not selected(relative):
                    continue
                if not member.isfile() or name in seen or member.size > MAX_TEXT:
                    raise ValueError("selected source is duplicate, linked, special or oversized")
                seen.add(name)
                captured += member.size
                if len(seen) > 2048 or captured > MAX_TEXT_TOTAL:
                    raise ValueError("selected source aggregate limit")
                content = tar.extractfile(member).read()
                if len(content) != member.size:
                    raise ValueError("truncated selected source")
                rows.append(describe(relative, content, include_text))
        while data := reader.read(archive_method.BLOCK):
            if any(data):
                raise ValueError("nonzero source tar tail")
    if count != 323914:
        raise ValueError("member count differs from accepted source inventory")
    if not {TOP + "/" + name for name in IDENTITIES}.issubset(seen):
        raise ValueError("missing source identities")
    return {"kind": "diagnostic-observation", "acceptance": "not-assessed",
            "python": platform.python_version(), "source_commit": COMMIT,
            "archive": {"file": path.name, "bytes": SOURCE_BYTES, "sha256": SOURCE_SHA,
                        "tar_bytes": reader.tar_bytes, "tar_sha256": reader.tar_hash.hexdigest(),
                        "member_count": count},
            "methods": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                        for name in (Path(__file__).name, "inspect-archives.py")},
            "selected_files": sorted(rows, key=lambda r: r["path"]),
            "unmatched_fixed_paths": sorted(FIXED - {r["path"][len(TOP) + 1:] for r in rows}),
            "limits": {"selected_file_bytes": MAX_TEXT, "selected_total_bytes": MAX_TEXT_TOTAL,
                       "selected_files": 2048, "members": 400000,
                       "xz_and_tar": archive_method.LIMITS},
            "published_binary_build_attestation": "not-assessed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_archive", type=Path)
    parser.add_argument("--include-text", action="store_true")
    args = parser.parse_args()
    print(json.dumps(inspect(args.source_archive, args.include_text), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
