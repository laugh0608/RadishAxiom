#!/usr/bin/env python3
"""只读检查已登记的 cvc5 Linux arm64 ZIP；不解包、加载或执行制品。"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "contracts/toolchain-adapters-v0.1/registry.json"
PREFIX = "cvc5-Linux-arm64-static"
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 96 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_MEMBERS = 128


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def validate_members(infos):
    require(0 < len(infos) <= MAX_MEMBERS, "member-count-limit")
    names = set()
    total = 0
    for info in infos:
        name = info.filename
        pieces = name.rstrip("/").split("/")
        require(name and len(name) <= 240 and "\\" not in name and "\x00" not in name,
                "invalid-member-name")
        require(not PurePosixPath(name).is_absolute()
                and all(part not in ("", ".", "..") and ":" not in part for part in pieces)
                and pieces[0] == PREFIX, "member-outside-root")
        normalized = "/".join(pieces)
        require(normalized not in names, "duplicate-member")
        names.add(normalized)
        mode = info.external_attr >> 16
        expected = stat.S_IFDIR if info.is_dir() else stat.S_IFREG
        require(stat.S_IFMT(mode) == expected, "link-or-special-member")
        require(not mode & (stat.S_ISUID | stat.S_ISGID), "privileged-member")
        require(not info.flag_bits & 1, "encrypted-member")
        require(info.compress_type in (0, 8), "unsupported-compression")
        require(0 <= info.file_size <= MAX_MEMBER, "member-size-limit")
        require(not info.is_dir() or info.file_size == 0, "nonempty-directory")
        total += info.file_size
        require(total <= MAX_TOTAL, "expanded-size-limit")
    for info in infos:
        parents = PurePosixPath(info.filename.rstrip("/")).parents
        for parent in parents:
            if str(parent) != ".":
                require(str(parent) + "/" in {i.filename for i in infos}, "missing-directory")
    return total


def inspect_elf(data):
    require(len(data) >= 64 and data[:7] == b"\x7fELF\x02\x01\x01", "not-elf64-little-endian")
    h = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    require(h[1] == 2 and h[2] == 183 and h[3] == 1, "not-aarch64-executable")
    require(h[8] == 64 and h[9] == 56 and 0 < h[10] <= 64, "invalid-program-header-shape")
    require(h[5] >= 64 and h[5] + h[9] * h[10] <= len(data), "program-header-bounds")
    headers = []
    for index in range(h[10]):
        kind, flags, offset, vaddr, _, size, memory, alignment = struct.unpack_from(
            "<IIQQQQQQ", data, h[5] + index * h[9])
        require(offset + size <= len(data), "segment-bounds")
        require(kind != 1 or size <= memory, "load-memory-size")
        headers.append({"type": kind, "flags": flags, "offset": offset,
                        "virtual_address": vaddr, "file_bytes": size,
                        "memory_bytes": memory, "alignment": alignment})
    require(any(p["type"] == 1 and p["flags"] & 1
                and p["virtual_address"] <= h[4] < p["virtual_address"] + p["memory_bytes"]
                for p in headers), "entry-outside-executable-load")
    require(not any(p["type"] in (2, 3) for p in headers), "dynamic-linkage-present")
    return {"class": "ELF64", "endian": "little", "type": "ET_EXEC", "machine": "AArch64",
            "entry": h[4], "program_headers": headers, "pt_interp": False, "pt_dynamic": False,
            "interpretation": "static-layout-only-not-runtime-compatibility"}


def inspect_archive(path):
    with ZipFile(path) as archive:
        infos = archive.infolist()
        total = validate_members(infos)
        members, texts, executable = [], {}, None
        for info in infos:
            if info.is_dir():
                members.append({"path": info.filename, "kind": "directory", "bytes": 0})
                continue
            h, size = hashlib.sha256(), 0
            with archive.open(info) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    size += len(block)
                    require(size <= info.file_size, "expanded-member-mismatch")
                    h.update(block)
            require(size == info.file_size, "expanded-member-mismatch")
            members.append({"path": info.filename, "kind": "file", "bytes": size,
                            "mode": oct((info.external_attr >> 16) & 0o7777),
                            "raw_digest": "sha256:" + h.hexdigest()})
            if info.filename == PREFIX + "/bin/cvc5":
                data = archive.read(info)
                executable = {"path": info.filename, "bytes": size,
                              "raw_digest": digest(data), "elf": inspect_elf(data)}
                # 字符串仅为静态线索，不认证运行版本或所链接组件的来源。
                clues = sorted(set(re.findall(rb"cadical-[A-Za-z0-9._-]+", data)))
                executable["unverified_build_strings"] = [s.decode("ascii") for s in clues]
            if info.filename.endswith(("/gmp.pc", "/gmpxx.pc", "/cvc5ConfigVersion.cmake")):
                require(size < 64 * 1024, "metadata-size-limit")
                texts[info.filename] = archive.read(info).decode("utf-8")
        require(executable is not None, "missing-cli")
        required = ["COPYING", "AUTHORS", "licenses/minisat-LICENSE", "licenses/lgpl-3.0.txt",
                    "licenses/gpl-3.0.txt", "licenses/GCC-exception-3.1.txt"]
        require(all(PREFIX + "/" + name in archive.namelist() for name in required),
                "missing-declared-license-file")
        return {"member_count": len(infos), "expanded_bytes": total,
                "members": sorted(members, key=lambda x: x["path"]), "cli": executable,
                "metadata_text": texts,
                "license_member_paths": sorted(i.filename for i in infos
                                               if not i.is_dir() and (
                                                   "/licenses/" in i.filename
                                                   or i.filename.endswith(("/COPYING", "/AUTHORS"))))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path, help="new JSON file, never overwritten")
    args = parser.parse_args()
    require(not args.output.exists(), "output-already-exists")
    require(args.archive.is_file() and args.archive.stat().st_size <= MAX_ARCHIVE, "archive-size-limit")
    registry = json.loads((ROOT / REGISTRY).read_bytes())
    tool = next(t for t in registry["tools"] if t["id"] == "cvc5-cli")
    require(tool["version"] == "1.3.4", "registry-version-drift")
    entry = next(a for a in tool["artifacts"] if a["platform"] == "linux-arm64")
    require(entry["filename"] == PREFIX + ".zip", "registry-filename-drift")
    with args.archive.open("rb") as source:
        archive_bytes = source.read(MAX_ARCHIVE + 1)
    require(len(archive_bytes) <= MAX_ARCHIVE, "archive-size-limit")
    raw = digest(archive_bytes)
    require(raw == "sha256:" + entry["digest"]["sha256"], "registered-digest-mismatch")
    result = {"format": "radishaxiom-cvc5-static-inspection", "version": "0.1",
              "scope": "registered-archive-bytes-layout-and-static-cli-only",
              "not_established": ["publisher-signature-verification", "binary-source-reproducibility",
                                  "complete-linked-dependency-and-license-acceptance", "installation",
                                  "execution", "runtime-isolation", "model-or-proof-support"],
              "registry_raw": file_digest(ROOT / REGISTRY),
              "inspector_raw": file_digest(Path(__file__)),
              "archive": {"filename": entry["filename"], "source_url": entry["source_url"],
                          "bytes": len(archive_bytes), "raw_digest": raw},
              "inspection": inspect_archive(io.BytesIO(archive_bytes))}
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print("static inspection passed; no installation or execution; license acceptance remains separate")


if __name__ == "__main__":
    main()
