#!/usr/bin/env python3
"""Inventory a pinned Linux source tar.xz; never extract, execute, or accept it.

This diagnostic format is separate from the frozen toolchain-tar v0.1 method.
Only regular files, directories, and contained links are supported. Physical
headers and extension records are checked before their payload is interpreted.
"""

from __future__ import annotations

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


PROFILE = "linux-6.18.49-source"
TOP = "linux-6.18.49"
SOURCE_SHA256 = "ae826f33111fea6f1d279dde7299d7463c8dfd204aeb75a8fb5432bc60a28191"
LIMITS = {
    "compressed_bytes": 256 * 1024 * 1024,
    "tar_bytes": 2 * 1024 * 1024 * 1024,
    "member_bytes": 32 * 1024 * 1024,
    "entries": 200000,
    "extension_bytes": 16384,
    "path_bytes": 4096,
    "xz_decoder_bytes": 128 * 1024 * 1024,
    "link_hops": 40,
}
BLOCK = 1024 * 1024
REQUIRED = {
    "COPYING", "Makefile", "LICENSES/preferred/GPL-2.0",
    "LICENSES/exceptions/Linux-syscall-note", "scripts/min-tool-version.sh",
    "Documentation/process/changes.rst",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def xz_chunks(source, expected: str):
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=LIMITS["xz_decoder_bytes"])
    compressed_hash = hashlib.sha256()
    compressed_bytes = 0
    while not decoder.eof:
        data = source.read(65536) if decoder.needs_input else b""
        if decoder.needs_input and not data:
            raise ValueError("truncated xz stream")
        compressed_hash.update(data)
        compressed_bytes += len(data)
        if compressed_bytes > LIMITS["compressed_bytes"]:
            raise ValueError("compressed byte limit exceeded")
        block = decoder.decompress(data, max_length=BLOCK)
        if block:
            yield block
    if decoder.unused_data or source.read(1):
        raise ValueError("trailing or concatenated xz data")
    if compressed_hash.hexdigest() != expected:
        raise ValueError("compressed SHA-256 changed or mismatched during inspection")


class TarReader:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.buffer = b""
        self.bytes = 0
        self.sha256 = hashlib.sha256()

    def read(self, size: int) -> bytes:
        if size < 0 or size > BLOCK:
            raise ValueError("unbounded tar read")
        result = bytearray()
        while len(result) < size:
            if not self.buffer:
                self.buffer = next(self.chunks, b"")
                if not self.buffer:
                    break
                self.bytes += len(self.buffer)
                if self.bytes > LIMITS["tar_bytes"]:
                    raise ValueError("uncompressed tar byte limit exceeded")
                self.sha256.update(self.buffer)
            take = min(size - len(result), len(self.buffer))
            result.extend(self.buffer[:take])
            self.buffer = self.buffer[take:]
        return bytes(result)

    def exact(self, size: int) -> bytes:
        result = self.read(size)
        if len(result) != size:
            raise ValueError("truncated tar payload or header")
        return result

    def padding(self, size: int) -> None:
        if any(self.exact((-size) % 512)):
            raise ValueError("nonzero member padding")


def safe_text(value: str) -> None:
    if not value or len(value.encode("utf-8")) > LIMITS["path_bytes"]:
        raise ValueError("empty or oversized archive path/link")
    if "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("control character or backslash in archive path/link")


def path_name(value: str, top: str) -> str:
    safe_text(value)
    parts = value.split("/")
    if parts[0] != top or any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"noncanonical or escaping archive path: {value!r}")
    return value


def pax_fields(data: bytes) -> dict[str, str]:
    fields = {}
    while data:
        prefix, separator, _ = data.partition(b" ")
        if not separator or not re.fullmatch(rb"[1-9][0-9]*", prefix):
            raise ValueError("malformed PAX record length")
        length = int(prefix)
        if length > len(data) or length <= len(prefix) + 2 or data[length - 1:length] != b"\n":
            raise ValueError("invalid PAX record boundary")
        key, equals, value = data[len(prefix) + 1:length - 1].partition(b"=")
        if not equals:
            raise ValueError("malformed PAX field")
        name = key.decode("ascii")
        if name in fields:
            raise ValueError("duplicate PAX field")
        fields[name] = value.decode("utf-8")
        data = data[length:]
    return fields


def check_tree(rows: list[dict], top: str) -> list[dict]:
    nodes = {row["path"]: row for row in rows}
    if nodes.get(top, {}).get("kind") != "directory":
        raise ValueError("top-level directory is missing")
    for name in nodes:
        parts = name.split("/")
        for end in range(1, len(parts)):
            if nodes.get("/".join(parts[:end]), {}).get("kind") != "directory":
                raise ValueError(f"missing or non-directory ancestor: {name}")
    links = []
    for row in rows:
        if row["kind"] not in {"symlink", "hardlink"}:
            continue
        target = row["target"]
        safe_text(target)
        if target.startswith("/"):
            raise ValueError("absolute link target")
        if row["kind"] == "hardlink":
            resolved = path_name(target, top)
            if nodes.get(resolved, {}).get("kind") != "file":
                raise ValueError("hardlink target must be an explicit regular file")
        else:
            parts = row["path"].split("/")[:-1]
            pending = target.split("/")
            hops = 0
            while pending:
                part = pending.pop(0)
                if part in {"", "."}:
                    continue
                if part == "..":
                    if len(parts) <= 1:
                        raise ValueError("symlink escapes archive root")
                    parts.pop()
                    continue
                candidate = "/".join([*parts, part])
                node = nodes.get(candidate)
                if node is None:
                    raise ValueError(f"dangling symlink target: {candidate}")
                if node["kind"] == "symlink":
                    hops += 1
                    if hops > LIMITS["link_hops"]:
                        raise ValueError("symlink cycle or hop limit exceeded")
                    safe_text(node["target"])
                    if node["target"].startswith("/"):
                        raise ValueError("absolute nested symlink target")
                    pending = node["target"].split("/") + pending
                else:
                    if pending and node["kind"] != "directory":
                        raise ValueError("symlink traverses a non-directory")
                    parts.append(part)
            resolved = "/".join(parts)
        links.append({"path": row["path"], "target": target, "resolved_path": resolved})
    return sorted(links, key=lambda row: row["path"])


def inspect_tar(reader: TarReader, top: str) -> dict:
    rows, licenses, spdx = [], [], []
    names = set()
    global_pax, local_pax = {}, {}
    extension_count = 0
    required_text = {}
    while True:
        header = reader.exact(512)
        if header == bytes(512):
            if local_pax or reader.exact(512) != bytes(512):
                raise ValueError("dangling PAX record or missing second end block")
            while tail := reader.read(BLOCK):
                if any(tail):
                    raise ValueError("nonzero data after tar end marker")
            if reader.bytes % 512:
                raise ValueError("unaligned tar padding")
            break
        member = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
        if header[257:265] != b"ustar\x0000":
            raise ValueError("source profile requires POSIX USTAR/PAX headers")
        if member.size < 0:
            raise ValueError("negative member size")
        if member.type in {tarfile.XHDTYPE, tarfile.XGLTYPE}:
            extension_count += 1
            if extension_count > LIMITS["entries"] or member.size > LIMITS["extension_bytes"]:
                raise ValueError("PAX extension limit exceeded")
            fields = pax_fields(reader.exact(member.size))
            reader.padding(member.size)
            if member.type == tarfile.XGLTYPE:
                if global_pax or rows or local_pax or set(fields) != {"comment"}:
                    raise ValueError("unexpected global PAX fields or placement")
                if not re.fullmatch(r"[0-9a-f]{40}", fields["comment"]):
                    raise ValueError("invalid archive commit comment")
                global_pax = fields
            else:
                if local_pax or not fields or not set(fields) <= {"path", "linkpath"}:
                    raise ValueError("unsupported or stacked local PAX fields")
                local_pax = fields
            continue
        if len(rows) >= LIMITS["entries"] or member.size > LIMITS["member_bytes"]:
            raise ValueError("member count or size limit exceeded")
        kind = {tarfile.REGTYPE: "file", tarfile.AREGTYPE: "file", tarfile.DIRTYPE: "directory",
                tarfile.SYMTYPE: "symlink", tarfile.LNKTYPE: "hardlink"}.get(member.type)
        if kind is None:
            raise ValueError(f"unsupported tar member type: {member.type!r}")
        # TarInfo normalizes directory suffixes. Validate the physical spelling
        # first so repeated trailing slashes do not disappear before rejection.
        raw_name = header[:100].split(b"\0", 1)[0].decode("utf-8")
        prefix = header[345:500].split(b"\0", 1)[0].decode("utf-8")
        if prefix:
            raw_name = prefix + "/" + raw_name
        name = local_pax.get("path", raw_name)
        if kind == "directory":
            name = name.removesuffix("/")
        name = path_name(name, top)
        if name in names:
            raise ValueError(f"duplicate archive path: {name}")
        names.add(name)
        # git archive preserves group-write bits (tar.umask defaults to 0002).
        # Record these source modes; this tool never applies them to disk.
        allowed_modes = ({0o777} if kind == "symlink" else
                         {0o755, 0o775} if kind == "directory" else
                         {0o644, 0o664, 0o755, 0o775})
        if member.mode not in allowed_modes or member.uid != 0 or member.gid != 0:
            raise ValueError(f"unexpected source ownership or permissions: {name}")
        if kind != "file" and member.size != 0:
            raise ValueError("non-file member has a payload")
        if "linkpath" in local_pax and kind not in {"symlink", "hardlink"}:
            raise ValueError("linkpath on a non-link")
        row = {"path": name, "kind": kind, "bytes": member.size,
               "mode": format(member.mode, "04o"), "uid": member.uid, "gid": member.gid,
               "uname": member.uname, "gname": member.gname, "mtime": member.mtime}
        if kind in {"symlink", "hardlink"}:
            row["target"] = local_pax.get("linkpath", member.linkname)
        elif member.linkname:
            raise ValueError("unexpected link name on a non-link")
        local_pax = {}
        if kind == "file":
            file_hash = hashlib.sha256()
            remaining, prefix = member.size, b""
            while remaining:
                data = reader.exact(min(BLOCK, remaining))
                file_hash.update(data)
                prefix += data[:max(0, 8192 - len(prefix))]
                remaining -= len(data)
            reader.padding(member.size)
            row["sha256"] = file_hash.hexdigest()
            relative = name[len(top) + 1:]
            if relative in REQUIRED:
                required_text[relative] = prefix.decode("utf-8")
            basename = relative.rsplit("/", 1)[-1].upper()
            if relative.startswith("LICENSES/") or re.match(r"^(COPYING|LICENSE|NOTICE|PATENTS)([._-]|$)", basename):
                licenses.append({"path": name, "bytes": member.size, "sha256": row["sha256"]})
            # This is a reproducible text inventory, not an SPDX parser or a
            # legal conclusion; missing/ambiguous declarations stay visible.
            for match in re.finditer(rb"SPDX-License-Identifier:[ \t]*([^\r\n]+)", prefix):
                spdx.append({"path": name, "raw_declaration": match[1].decode("utf-8", "backslashreplace")})
        rows.append(row)
    missing = REQUIRED - required_text.keys()
    if missing:
        raise ValueError(f"required source files missing: {sorted(missing)}")
    for key, value in {"VERSION": "6", "PATCHLEVEL": "18", "SUBLEVEL": "49", "EXTRAVERSION": ""}.items():
        actual = re.findall(r"^" + key + r"[ \t]*=[ \t]*([^\n]*)$", required_text["Makefile"], re.MULTILINE)
        if actual != [value]:
            raise ValueError(f"Makefile version mismatch: {key}")
    if not global_pax:
        raise ValueError("missing source archive commit comment")
    rows.sort(key=lambda row: row["path"])
    return {"tar": {"bytes": reader.bytes, "sha256": reader.sha256.hexdigest()},
            "archive_commit_comment": global_pax["comment"],
            "type_counts": dict(sorted(Counter(row["kind"] for row in rows).items())),
            "extensions": extension_count, "members": rows, "links": check_tree(rows, top),
            "license_files": sorted(licenses, key=lambda row: row["path"]),
            "spdx_prefix_scan": {"bytes_per_file": 8192, "declarations": spdx}}


def inspect(path: Path, expected: str = SOURCE_SHA256) -> dict:
    with path.open("rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > LIMITS["compressed_bytes"]:
            raise ValueError("source is not a bounded regular file")
        sha = hashlib.sha256()
        read_bytes = 0
        while data := source.read(BLOCK):
            read_bytes += len(data)
            if read_bytes > LIMITS["compressed_bytes"]:
                raise ValueError("compressed byte limit exceeded before parsing")
            sha.update(data)
        if sha.hexdigest() != expected:
            raise ValueError("compressed SHA-256 mismatch before parsing")
        source.seek(0)
        result = inspect_tar(TarReader(xz_chunks(source, expected)), TOP)
        after = os.fstat(source.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("source changed during inspection")
    return {"format": "radishaxiom-source-tar-inventory", "format_version": "1",
            "kind": "diagnostic-observation", "acceptance": "not-assessed",
            "inspection_profile": PROFILE, "limits": LIMITS,
            "method": {"path": "scripts/inspect-source-tar-v1.py", "sha256": digest(Path(__file__).read_bytes()),
                       "python": sys.version},
            "source": {"filename": path.name, "bytes": before.st_size, "sha256": expected},
            **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=[PROFILE])
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        result = inspect(args.archive)
    except (OSError, ValueError, EOFError, lzma.LZMAError, tarfile.HeaderError) as error:
        print(f"source inventory failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
