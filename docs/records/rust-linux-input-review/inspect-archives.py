#!/usr/bin/env python3
"""Read only the two pinned Rust Linux archives; never install or execute them.

This is a task diagnostic of logical tar members, not the frozen v0.1 archive
acceptance method, a physical-header validator, or a production extractor.
"""

import argparse
from collections import Counter
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
import tomllib


MANIFEST_SHA = "03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf"
SPECS = (
    ("rust", "aarch64-unknown-linux-gnu", "9a7a2c336b4787f1b72f6bab7c35d5b7af2fd03cbd39b4fc721466a70d402a7d"),
    ("rust-std", "aarch64-unknown-linux-musl", "49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31"),
)
LIMITS = {"compressed": 512 * 1024**2, "tar": 4 * 1024**3,
          "member": 512 * 1024**2, "entries": 200000, "text": 8 * 1024**2,
          "xz_memory": 256 * 1024**2, "path": 4096}
BLOCK = 1024**2


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def path_name(name, top, directory=False):
    if directory and name.endswith("/"):
        name = name[:-1]
    if (not name or len(name.encode()) > LIMITS["path"] or "\\" in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or name.split("/")[0] != top or any(p in {"", ".", ".."} for p in name.split("/"))):
        raise ValueError("noncanonical or escaping path")
    return name


class XzReader:
    def __init__(self, stream, expected):
        self.stream, self.expected = stream, expected
        self.decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=LIMITS["xz_memory"])
        self.compressed = hashlib.sha256()
        self.tar_hash = hashlib.sha256()
        self.compressed_bytes = self.tar_bytes = 0
        self.ended = False

    def read(self, size):
        if size < 0 or size > BLOCK:
            raise ValueError("unbounded read")
        result = bytearray()
        while len(result) < size and not self.ended:
            if self.decoder.eof:
                if self.decoder.unused_data or self.stream.read(1):
                    raise ValueError("trailing or concatenated XZ")
                if self.compressed.hexdigest() != self.expected:
                    raise ValueError("compressed hash changed during inspection")
                self.ended = True
                break
            data = self.stream.read(65536) if self.decoder.needs_input else b""
            if self.decoder.needs_input and not data:
                raise ValueError("truncated XZ")
            self.compressed.update(data)
            self.compressed_bytes += len(data)
            if self.compressed_bytes > LIMITS["compressed"]:
                raise ValueError("compressed limit")
            part = self.decoder.decompress(data, max_length=size - len(result))
            self.tar_bytes += len(part)
            if self.tar_bytes > LIMITS["tar"]:
                raise ValueError("tar byte limit")
            self.tar_hash.update(part)
            result.extend(part)
        return bytes(result)


def inspect_members(reader, top):
    rows, texts = {}, {}
    with tarfile.open(fileobj=reader, mode="r|", bufsize=512) as archive:
        for member in archive:
            if len(rows) >= LIMITS["entries"] or member.size > LIMITS["member"] or member.size < 0:
                raise ValueError("member count or size limit")
            if not member.isfile() and not member.isdir():
                raise ValueError("links and special members require separate review")
            name = path_name(member.name, top, member.isdir())
            if name in rows:
                raise ValueError("duplicate path")
            if member.mode not in {0o644, 0o755} or member.uid != 0 or member.gid != 0:
                raise ValueError("unexpected owner or permissions")
            if member.isdir() and member.size != 0:
                raise ValueError("directory payload")
            relative = name[len(top) + 1:]
            row = {"path": name, "kind": "directory" if member.isdir() else "file",
                   "bytes": member.size, "mode": format(member.mode, "04o"),
                   "uid": member.uid, "gid": member.gid, "mtime": member.mtime,
                   "pax_headers": member.pax_headers}
            if member.isfile():
                stream = archive.extractfile(member)
                digest, count, prefix = hashlib.sha256(), 0, b""
                basename = name.rsplit("/", 1)[-1]
                capture = basename in {"components", "version", "git-commit-hash", "rust-installer-version", "manifest.in"}
                if capture and member.size > LIMITS["text"]:
                    raise ValueError("metadata text limit")
                captured = bytearray()
                while data := stream.read(BLOCK):
                    digest.update(data)
                    count += len(data)
                    prefix += data[:max(0, 64 - len(prefix))]
                    if capture:
                        captured.extend(data)
                if count != member.size:
                    raise ValueError("file size mismatch")
                row["sha256"] = digest.hexdigest()
                if prefix.startswith(b"\x7fELF"):
                    row["elf_header"] = {"class": prefix[4], "byte_order": prefix[5],
                                         "type": int.from_bytes(prefix[16:18], "little"),
                                         "machine": int.from_bytes(prefix[18:20], "little")}
                elif prefix.startswith(b"!<arch>\n"):
                    row["ar_magic"] = True
                if capture:
                    texts[relative] = captured.decode("utf-8")
            rows[name] = row
    # tarfile stops after its zero header. Consume and reject hidden tail data.
    while data := reader.read(BLOCK):
        if any(data):
            raise ValueError("nonzero data after tar end")
    for name in rows:
        parent = name.rpartition("/")[0]
        if name != top and rows.get(parent, {}).get("kind") != "directory":
            raise ValueError("missing or non-directory ancestor")
    if rows.get(top, {}).get("kind") != "directory":
        raise ValueError("missing archive root")
    components = texts.get("components", "").splitlines()
    if not components or len(components) != len(set(components)):
        raise ValueError("missing or duplicate components")
    claims = []
    for component in components:
        if not re.fullmatch(r"[a-z0-9-]+", component):
            raise ValueError("invalid component")
        manifest = texts.get(component + "/manifest.in")
        if manifest is None:
            raise ValueError("missing component manifest")
        seen = set()
        for line in manifest.splitlines():
            kind, sep, relative = line.partition(":")
            if not sep or kind not in {"file", "dir"} or relative in seen:
                raise ValueError("invalid or duplicate manifest claim")
            seen.add(relative)
            name = path_name(top + "/" + component + "/" + relative, top)
            if rows.get(name, {}).get("kind") != {"file": "file", "dir": "directory"}[kind]:
                raise ValueError("component claim missing or type mismatched")
            claims.append({"component": component, "kind": kind, "path": relative})
    return {"members": list(rows.values()), "components": components,
            "component_claims": claims, "metadata": {k: v for k, v in texts.items() if not k.endswith("manifest.in")},
            "type_counts": dict(Counter(row["kind"] for row in rows.values())),
            "licenses": [row for row in rows.values() if row["kind"] == "file"
                         and re.match(r"^(LICENSE|COPYRIGHT|NOTICE)([._-]|$)", row["path"].rsplit("/", 1)[-1])],
            "static_inputs": [row for row in rows.values() if "/self-contained/" in row["path"]
                              or row["path"].endswith("/rust-lld")]}


def inspect(path, expected):
    with path.open("rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > LIMITS["compressed"]:
            raise ValueError("not a bounded regular archive")
        if hashlib.file_digest(source, "sha256").hexdigest() != expected:
            raise ValueError("publisher hash mismatch before parsing")
        source.seek(0)
        reader = XzReader(source, expected)
        result = inspect_members(reader, path.name.removesuffix(".tar.xz"))
        after = os.fstat(source.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("input changed")
    return {"file": path.name, "bytes": before.st_size, "sha256": expected,
            "tar_bytes": reader.tar_bytes, "tar_sha256": reader.tar_hash.hexdigest(), **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    args = parser.parse_args()
    manifest = (args.inputs / "channel-rust-1.97.1.toml").read_bytes()
    if sha256(manifest) != MANIFEST_SHA:
        raise ValueError("fixed channel manifest hash mismatch")
    parsed = tomllib.loads(manifest.decode())
    results = []
    for package, target, expected in SPECS:
        name = f"{package}-1.97.1-{target}.tar.xz"
        entry = parsed["pkg"][package]["target"][target]
        if (entry["available"] is not True or entry["xz_hash"] != expected
                or entry["xz_url"] != "https://static.rust-lang.org/dist/2026-07-16/" + name):
            raise ValueError("manifest selection changed")
        results.append(inspect(args.inputs / name, expected))
    print(json.dumps({"kind": "diagnostic-observation", "acceptance": "not-assessed",
                      "method_sha256": sha256(Path(__file__).read_bytes()), "python": sys.version,
                      "limits": LIMITS, "manifest_sha256": MANIFEST_SHA, "archives": results}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
