#!/usr/bin/env python3
"""Inspect a registered Go or Rust tar payload without extracting or executing it."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import posixpath
import re
import stat
import tarfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any


FORMAT = "radishaxiom-toolchain-tar-inspection"
FORMAT_VERSION = "0.1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

RUST_COMPONENT_PROFILES = {
    "rust-1.97.1-cargo-aarch64-apple-darwin": {
        "component": "cargo",
        "filename": "cargo-1.97.1-aarch64-apple-darwin.tar.xz",
        "layout": ["cargo/bin/cargo"],
        "licenses": ["LICENSE-APACHE", "LICENSE-MIT", "LICENSE-THIRD-PARTY"],
        "version": "0.98.0 (c980f4866 2026-06-30)",
    },
    "rust-1.97.1-clippy-aarch64-apple-darwin": {
        "component": "clippy-preview",
        "filename": "clippy-1.97.1-aarch64-apple-darwin.tar.xz",
        "layout": [
            "clippy-preview/bin/cargo-clippy",
            "clippy-preview/bin/clippy-driver",
        ],
        "licenses": ["LICENSE-APACHE", "LICENSE-MIT"],
        "version": "0.1.97",
    },
    "rust-1.97.1-rust-std-aarch64-apple-darwin": {
        "component": "rust-std-aarch64-apple-darwin",
        "filename": "rust-std-1.97.1-aarch64-apple-darwin.tar.xz",
        "layout": [
            "rust-std-aarch64-apple-darwin/lib/rustlib/aarch64-apple-darwin/lib"
        ],
        "licenses": ["COPYRIGHT", "LICENSE-APACHE", "LICENSE-MIT"],
        "version": "1.97.1 (8bab26f4f 2026-07-14)",
    },
    "rust-1.97.1-rustc-aarch64-apple-darwin": {
        "component": "rustc",
        "filename": "rustc-1.97.1-aarch64-apple-darwin.tar.xz",
        "layout": ["rustc/bin/rustc", "rustc/bin/rustdoc"],
        "licenses": ["COPYRIGHT", "LICENSE-APACHE", "LICENSE-MIT"],
        "version": "1.97.1 (8bab26f4f 2026-07-14)",
    },
    "rust-1.97.1-rustfmt-aarch64-apple-darwin": {
        "component": "rustfmt-preview",
        "filename": "rustfmt-1.97.1-aarch64-apple-darwin.tar.xz",
        "layout": ["rustfmt-preview/bin/cargo-fmt", "rustfmt-preview/bin/rustfmt"],
        "licenses": ["LICENSE-APACHE", "LICENSE-MIT"],
        "version": "1.9.0",
    },
}
RUST_SOURCE_PROFILE = "rust-1.97.1-source"
RUST_COMMIT = "8bab26f4f68e0e26f0bb7960be334d5b520ea452"
RUST_COMMIT_INFO = (
    "8bab26f4f68e0e26f0bb7960be334d5b520ea452\n"
    "8bab26f4f\n"
    "2026-07-14\n"
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def inventory_digest(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_bytes(rows))


def archive_path(name: str, top_level: str = "go") -> PurePosixPath:
    if not name or "\0" in name or name.startswith("/"):
        raise ValueError(f"unsafe archive path: {name!r}")
    parts = PurePosixPath(name).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"non-canonical archive path: {name!r}")
    normalized = posixpath.normpath(name.rstrip("/"))
    if normalized != name.rstrip("/"):
        raise ValueError(f"non-normalized archive path: {name!r}")
    if parts[0] != top_level:
        raise ValueError(f"archive member escapes {top_level} top level: {name!r}")
    return PurePosixPath(normalized)


def resolved_link(member: tarfile.TarInfo, top_level: str = "go") -> str:
    target = member.linkname
    if not target or "\0" in target or target.startswith("/"):
        raise ValueError(f"unsafe link target: {member.name!r} -> {target!r}")
    if member.issym():
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), target))
    else:
        resolved = posixpath.normpath(target)
    parts = PurePosixPath(resolved).parts
    if not parts or parts[0] != top_level or ".." in parts:
        raise ValueError(
            f"link escapes {top_level} top level: {member.name!r} -> {target!r}"
        )
    return resolved


def member_kind(member: tarfile.TarInfo) -> str:
    if member.isfile():
        return "file"
    if member.isdir():
        return "directory"
    if member.issym():
        return "symlink"
    if member.islnk():
        return "hardlink"
    raise ValueError(f"unsupported archive member type: {member.name!r}")


def is_license_path(name: str) -> bool:
    basename = PurePosixPath(name).name.upper()
    return (
        basename in {"COPYING", "LICENSE", "NOTICE", "PATENTS"}
        or basename.startswith("COPYING.")
        or basename.startswith("LICENSE.")
        or basename.startswith("NOTICE.")
        or basename.startswith("PATENTS.")
    )


def file_record(archive: tarfile.TarFile, member: tarfile.TarInfo) -> dict[str, str]:
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"regular file could not be read: {member.name}")
    data = stream.read()
    if len(data) != member.size:
        raise ValueError(f"regular file length mismatch: {member.name}")
    return {
        "bytes": str(len(data)),
        "path": member.name,
        "raw_sha256": sha256_bytes(data),
    }


def vendor_modules(text: str, manifest_path: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("# ") or line.startswith("# => "):
            continue
        fields = line[2:].split()
        if len(fields) < 2 or fields[1] == "=>":
            continue
        row = {
            "manifest": manifest_path,
            "module": fields[0],
            "version": fields[1],
        }
        if "=>" in fields:
            marker = fields.index("=>")
            row["replacement"] = " ".join(fields[marker + 1 :])
        result.append(row)
    return result


def require_layout(names: set[str], profile: str) -> list[dict[str, str]]:
    common = ["go/LICENSE", "go/PATENTS", "go/VERSION", "go/src/make.bash"]
    host = [
        "go/bin/go",
        "go/bin/gofmt",
        "go/pkg/tool/darwin_arm64/compile",
        "go/pkg/tool/darwin_arm64/link",
    ]
    assertions: list[dict[str, str]] = []
    for name in common:
        if name not in names:
            raise ValueError(f"required archive member missing: {name}")
        assertions.append({"expectation": "present", "path": name})
    if profile == "go1.26.7-darwin-arm64-host":
        for name in host:
            if name not in names:
                raise ValueError(f"required host archive member missing: {name}")
            assertions.append({"expectation": "present", "path": name})
    elif profile == "go1.26.7-source":
        for name in host:
            if name in names:
                raise ValueError(f"source archive unexpectedly contains host binary: {name}")
            assertions.append({"expectation": "absent", "path": name})
    else:
        raise ValueError(f"unknown inspection profile: {profile}")
    return sorted(assertions, key=lambda row: (row["path"], row["expectation"]))


def inspect_go(args: argparse.Namespace) -> dict[str, Any]:
    path = args.archive.resolve()
    if not path.is_file():
        raise ValueError(f"archive is not a file: {path}")
    if path.name != args.filename:
        raise ValueError(f"archive filename mismatch: {path.name!r}")

    actual_sha256 = sha256_file(path)
    expected_sha256 = "sha256:" + args.expected_sha256
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"archive SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    counts = {"directory": 0, "file": 0, "hardlink": 0, "symlink": 0}
    names: set[str] = set()
    member_rows: list[dict[str, str]] = []
    link_rows: list[dict[str, str]] = []
    license_rows: list[dict[str, str]] = []
    module_manifest_rows: list[dict[str, str]] = []
    module_rows: list[dict[str, str]] = []
    mode_values: set[str] = set()
    uid_values: set[str] = set()
    gid_values: set[str] = set()
    uname_values: set[str] = set()
    gname_values: set[str] = set()
    mtime_values: set[str] = set()
    total_regular_bytes = 0
    max_regular = {"bytes": "0", "path": ""}
    required_members: dict[str, tarfile.TarInfo] = {}

    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("archive is empty")
        for member in members:
            normalized = str(archive_path(member.name))
            if normalized in names:
                raise ValueError(f"duplicate archive member: {normalized}")
            names.add(normalized)
            kind = member_kind(member)
            counts[kind] += 1
            if member.mode & (stat.S_ISUID | stat.S_ISGID):
                raise ValueError(f"setuid/setgid archive member: {member.name}")
            mode = format(member.mode, "04o")
            mode_values.add(mode)
            uid_values.add(str(member.uid))
            gid_values.add(str(member.gid))
            uname_values.add(member.uname)
            gname_values.add(member.gname)
            mtime_values.add(str(member.mtime))
            member_row = {
                "bytes": str(member.size),
                "gid": str(member.gid),
                "kind": kind,
                "mode": mode,
                "mtime": str(member.mtime),
                "path": normalized,
                "uid": str(member.uid),
            }
            if member.issym() or member.islnk():
                member_row["link_target"] = member.linkname
                link_rows.append(
                    {
                        "kind": kind,
                        "path": member.name,
                        "resolved_path": resolved_link(member),
                        "target": member.linkname,
                    }
                )
            member_rows.append(member_row)
            if member.isfile():
                total_regular_bytes += member.size
                if member.size > int(max_regular["bytes"]):
                    max_regular = {"bytes": str(member.size), "path": member.name}
                if member.name in {"go/LICENSE", "go/PATENTS", "go/VERSION"}:
                    required_members[member.name] = member
                if is_license_path(member.name):
                    license_rows.append(file_record(archive, member))
                if (
                    PurePosixPath(member.name).name == "modules.txt"
                    and "vendor" in PurePosixPath(member.name).parts
                ):
                    record = file_record(archive, member)
                    module_manifest_rows.append(record)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f"module manifest unreadable: {member.name}")
                    module_rows.extend(
                        vendor_modules(stream.read().decode("utf-8"), member.name)
                    )

        layout = require_layout(names, args.profile)
        required_rows = []
        version_text = ""
        for name in ("go/LICENSE", "go/PATENTS", "go/VERSION"):
            member = required_members.get(name)
            if member is None:
                raise ValueError(f"required regular file missing: {name}")
            record = file_record(archive, member)
            if name == "go/VERSION":
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("go/VERSION unreadable")
                version_text = stream.read().decode("utf-8")
                record["utf8_text"] = version_text
            required_rows.append(record)

    if not version_text.splitlines() or version_text.splitlines()[0] != "go1.26.7":
        raise ValueError(f"go/VERSION identity mismatch: {version_text!r}")
    license_rows.sort(key=lambda row: row["path"])
    module_manifest_rows.sort(key=lambda row: row["path"])
    module_rows.sort(key=lambda row: (row["manifest"], row["module"], row["version"]))
    link_rows.sort(key=lambda row: row["path"])
    member_rows.sort(key=lambda row: row["path"])
    required_rows.sort(key=lambda row: row["path"])

    return {
        "archive": {
            "compression": "gzip",
            "duplicate_path_validation": "passed",
            "gid_values": sorted(gid_values),
            "gname_values": sorted(gname_values),
            "link_inventory": {
                "count": str(len(link_rows)),
                "jcs_sha256": inventory_digest(link_rows),
            },
            "link_target_validation": "passed",
            "max_regular_file": max_regular,
            "member_count": str(sum(counts.values())),
            "member_inventory": {
                "count": str(len(member_rows)),
                "jcs_sha256": inventory_digest(member_rows),
            },
            "mode_values": sorted(mode_values),
            "mtime": {
                "maximum": max(mtime_values, key=int),
                "minimum": min(mtime_values, key=int),
                "unique_count": str(len(mtime_values)),
            },
            "path_validation": "passed",
            "permission_validation": "passed",
            "special_file_validation": "passed",
            "top_level": "go",
            "total_regular_bytes": str(total_regular_bytes),
            "type_counts": {key: str(value) for key, value in sorted(counts.items())},
            "uid_values": sorted(uid_values),
            "uname_values": sorted(uname_values),
        },
        "artifact": {
            "bytes": str(path.stat().st_size),
            "filename": args.filename,
            "raw_sha256": actual_sha256,
        },
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "inspection_profile": args.profile,
        "layout_assertions": layout,
        "layout_validation": "passed",
        "license_inventory": {
            "count": str(len(license_rows)),
            "files": license_rows,
            "jcs_sha256": inventory_digest(license_rows),
        },
        "required_files": required_rows,
        "vendor_inventory": {
            "manifest_count": str(len(module_manifest_rows)),
            "manifests": module_manifest_rows,
            "module_count": str(len(module_rows)),
            "modules": module_rows,
            "modules_jcs_sha256": inventory_digest(module_rows),
        },
    }


def rust_top_level(filename: str) -> str:
    if not filename.endswith(".tar.xz"):
        raise ValueError(f"Rust archive must use .tar.xz: {filename}")
    return filename.removesuffix(".tar.xz")


def read_utf8(
    archive: tarfile.TarFile, member: tarfile.TarInfo, label: str
) -> str:
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"{label} is unreadable: {member.name}")
    return stream.read().decode("utf-8")


def collect_spdx(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        license_value = value.get("license")
        if isinstance(license_value, dict) and isinstance(
            license_value.get("spdx"), str
        ):
            result.append(license_value["spdx"])
        spdx_value = value.get("SPDX-License-Identifier")
        if isinstance(spdx_value, str):
            result.append(spdx_value)
        for child in value.values():
            result.extend(collect_spdx(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(collect_spdx(child))
    return result


def spdx_inventory(expressions: list[str]) -> dict[str, Any]:
    counts = Counter(expressions)
    rows = [
        {"expression": expression, "occurrences": str(counts[expression])}
        for expression in sorted(counts)
    ]
    return {
        "occurrence_count": str(len(expressions)),
        "unique_count": str(len(rows)),
        "expressions": rows,
        "jcs_sha256": inventory_digest(rows),
    }


def rust_required_paths(profile: str, top: str) -> tuple[list[str], dict[str, Any]]:
    common = ["git-commit-hash", "git-commit-info", "version"]
    if profile == RUST_SOURCE_PROFILE:
        relative = common + [
            "COPYRIGHT",
            "Cargo.lock",
            "Cargo.toml",
            "LICENSE-APACHE",
            "LICENSE-MIT",
            "REUSE.toml",
            "compiler/rustc/Cargo.toml",
            "library/std/Cargo.toml",
            "license-metadata.json",
            "src/tools/cargo/Cargo.toml",
            "src/tools/clippy/Cargo.toml",
            "src/tools/rustfmt/Cargo.toml",
        ]
        return sorted(f"{top}/{item}" for item in relative), {
            "component": "rust-source",
            "layout": [
                "Cargo.lock",
                "Cargo.toml",
                "compiler/rustc/Cargo.toml",
                "library/std/Cargo.toml",
                "src/tools/cargo/Cargo.toml",
                "src/tools/clippy/Cargo.toml",
                "src/tools/rustfmt/Cargo.toml",
            ],
            "version": "1.97.1 (8bab26f4f 2026-07-14)",
        }
    spec = RUST_COMPONENT_PROFILES.get(profile)
    if spec is None:
        raise ValueError(f"unknown Rust inspection profile: {profile}")
    relative = common + [
        "components",
        "rust-installer-version",
        f"{spec['component']}/manifest.in",
        *spec["licenses"],
    ]
    return sorted(f"{top}/{item}" for item in relative), spec


def rust_license_paths(names: set[str], profile: str, top: str) -> list[str]:
    if profile == RUST_SOURCE_PROFILE:
        selected = {
            f"{top}/COPYRIGHT",
            f"{top}/LICENSE-APACHE",
            f"{top}/LICENSE-MIT",
            f"{top}/REUSE.toml",
            f"{top}/license-metadata.json",
        }
        selected.update(
            name
            for name in names
            if name.startswith(f"{top}/LICENSES/")
            and len(PurePosixPath(name).parts) == 3
        )
        return sorted(selected)
    spec = RUST_COMPONENT_PROFILES[profile]
    return sorted(f"{top}/{name}" for name in spec["licenses"])


def inspect_rust(args: argparse.Namespace) -> dict[str, Any]:
    path = args.archive.resolve()
    if not path.is_file():
        raise ValueError(f"archive is not a file: {path}")
    if path.name != args.filename:
        raise ValueError(f"archive filename mismatch: {path.name!r}")
    top = rust_top_level(args.filename)
    expected_paths, spec = rust_required_paths(args.profile, top)
    if args.profile != RUST_SOURCE_PROFILE and args.filename != spec["filename"]:
        raise ValueError("Rust component filename does not match inspection profile")
    if args.profile == RUST_SOURCE_PROFILE and args.filename != "rustc-1.97.1-src.tar.xz":
        raise ValueError("Rust source filename does not match inspection profile")

    actual_sha256 = sha256_file(path)
    expected_sha256 = "sha256:" + args.expected_sha256
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"archive SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    counts = {"directory": 0, "file": 0, "hardlink": 0, "symlink": 0}
    names: set[str] = set()
    members_by_name: dict[str, tarfile.TarInfo] = {}
    member_rows: list[dict[str, str]] = []
    link_rows: list[dict[str, str]] = []
    mode_values: set[str] = set()
    uid_values: set[str] = set()
    gid_values: set[str] = set()
    uname_values: set[str] = set()
    gname_values: set[str] = set()
    mtime_values: set[str] = set()
    total_regular_bytes = 0
    max_regular = {"bytes": "0", "path": ""}
    cargo_manifest_count = 0
    cargo_lock_count = 0

    with tarfile.open(path, mode="r:xz") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("archive is empty")
        for member in members:
            normalized = str(archive_path(member.name, top))
            if normalized in names:
                raise ValueError(f"duplicate archive member: {normalized}")
            names.add(normalized)
            members_by_name[normalized] = member
            kind = member_kind(member)
            counts[kind] += 1
            if member.mode & (stat.S_ISUID | stat.S_ISGID):
                raise ValueError(f"setuid/setgid archive member: {member.name}")
            mode = format(member.mode, "04o")
            mode_values.add(mode)
            uid_values.add(str(member.uid))
            gid_values.add(str(member.gid))
            uname_values.add(member.uname)
            gname_values.add(member.gname)
            mtime_values.add(str(member.mtime))
            row = {
                "bytes": str(member.size),
                "gid": str(member.gid),
                "kind": kind,
                "mode": mode,
                "mtime": str(member.mtime),
                "path": normalized,
                "uid": str(member.uid),
            }
            if member.issym() or member.islnk():
                row["link_target"] = member.linkname
                link_rows.append(
                    {
                        "kind": kind,
                        "path": normalized,
                        "resolved_path": resolved_link(member, top),
                        "target": member.linkname,
                    }
                )
            member_rows.append(row)
            if member.isfile():
                total_regular_bytes += member.size
                if member.size > int(max_regular["bytes"]):
                    max_regular = {"bytes": str(member.size), "path": normalized}
                basename = PurePosixPath(normalized).name
                cargo_manifest_count += int(basename == "Cargo.toml")
                cargo_lock_count += int(basename == "Cargo.lock")

        assertions: list[dict[str, str]] = []
        for relative in spec["layout"]:
            name = f"{top}/{relative}"
            if name not in names:
                raise ValueError(f"required Rust layout member missing: {name}")
            assertions.append({"expectation": "present", "path": name})
        for name in expected_paths:
            member = members_by_name.get(name)
            if member is None or not member.isfile():
                raise ValueError(f"required Rust regular file missing: {name}")

        required_rows: list[dict[str, str]] = []
        text_names = {
            f"{top}/components",
            f"{top}/git-commit-hash",
            f"{top}/git-commit-info",
            f"{top}/rust-installer-version",
            f"{top}/version",
        }
        text_values: dict[str, str] = {}
        for name in expected_paths:
            member = members_by_name[name]
            record = file_record(archive, member)
            if name in text_names:
                text = read_utf8(archive, member, "Rust metadata")
                record["utf8_text"] = text
                text_values[name] = text
            required_rows.append(record)

        if text_values[f"{top}/git-commit-hash"] != RUST_COMMIT:
            raise ValueError("Rust git-commit-hash drifted")
        if text_values[f"{top}/git-commit-info"] != RUST_COMMIT_INFO:
            raise ValueError("Rust git-commit-info drifted")
        if text_values[f"{top}/version"] != spec["version"]:
            raise ValueError("Rust version metadata drifted")
        if args.profile != RUST_SOURCE_PROFILE:
            if text_values[f"{top}/components"] != f"{spec['component']}\n":
                raise ValueError("Rust component identity drifted")
            if text_values[f"{top}/rust-installer-version"] != "3\n":
                raise ValueError("Rust installer format drifted")

        license_rows = [
            file_record(archive, members_by_name[name])
            for name in rust_license_paths(names, args.profile, top)
        ]
        component_manifest_names = []
        if args.profile != RUST_SOURCE_PROFILE:
            component_manifest_names = [f"{top}/{spec['component']}/manifest.in"]
        component_manifest_rows = [
            file_record(archive, members_by_name[name])
            for name in component_manifest_names
        ]
        component_manifest_lines: list[str] = []
        for name in component_manifest_names:
            component_manifest_lines.extend(
                read_utf8(archive, members_by_name[name], "component manifest").splitlines()
            )

        metadata_spdx: list[str] = []
        reuse_spdx: list[str] = []
        if args.profile == RUST_SOURCE_PROFILE:
            metadata_name = f"{top}/license-metadata.json"
            metadata_spdx = collect_spdx(
                json.loads(read_utf8(archive, members_by_name[metadata_name], metadata_name))
            )
            reuse_name = f"{top}/REUSE.toml"
            reuse_spdx = collect_spdx(
                tomllib.loads(read_utf8(archive, members_by_name[reuse_name], reuse_name))
            )

    member_rows.sort(key=lambda row: row["path"])
    link_rows.sort(key=lambda row: row["path"])
    required_rows.sort(key=lambda row: row["path"])
    license_rows.sort(key=lambda row: row["path"])
    component_manifest_rows.sort(key=lambda row: row["path"])
    assertions.sort(key=lambda row: (row["path"], row["expectation"]))
    if mode_values != {"0644", "0755"}:
        raise ValueError(f"Rust archive modes drifted: {sorted(mode_values)}")
    if uid_values != {"0"} or gid_values != {"0"}:
        raise ValueError("Rust archive owner ids drifted")
    if uname_values != {""} or gname_values != {""}:
        raise ValueError("Rust archive owner names drifted")
    if counts["hardlink"] != 0:
        raise ValueError("Rust archive unexpectedly contains hardlinks")
    if args.profile != RUST_SOURCE_PROFILE and counts["symlink"] != 0:
        raise ValueError("Rust component archive unexpectedly contains symlinks")

    return {
        "archive": {
            "compression": "xz",
            "duplicate_path_validation": "passed",
            "gid_values": sorted(gid_values),
            "gname_values": sorted(gname_values),
            "link_inventory": {
                "count": str(len(link_rows)),
                "jcs_sha256": inventory_digest(link_rows),
            },
            "link_target_validation": "passed",
            "max_regular_file": max_regular,
            "member_count": str(sum(counts.values())),
            "member_inventory": {
                "count": str(len(member_rows)),
                "jcs_sha256": inventory_digest(member_rows),
            },
            "mode_values": sorted(mode_values),
            "mtime": {
                "maximum": max(mtime_values, key=int),
                "minimum": min(mtime_values, key=int),
                "unique_count": str(len(mtime_values)),
            },
            "path_validation": "passed",
            "permission_validation": "passed",
            "special_file_validation": "passed",
            "top_level": top,
            "total_regular_bytes": str(total_regular_bytes),
            "type_counts": {key: str(value) for key, value in sorted(counts.items())},
            "uid_values": sorted(uid_values),
            "uname_values": sorted(uname_values),
        },
        "artifact": {
            "bytes": str(path.stat().st_size),
            "filename": args.filename,
            "raw_sha256": actual_sha256,
        },
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "inspection_profile": args.profile,
        "layout_assertions": assertions,
        "layout_validation": "passed",
        "license_inventory": {
            "count": str(len(license_rows)),
            "files": license_rows,
            "jcs_sha256": inventory_digest(license_rows),
        },
        "required_files": required_rows,
        "rust_inventory": {
            "cargo_lock_count": str(cargo_lock_count),
            "cargo_manifest_count": str(cargo_manifest_count),
            "component": spec["component"],
            "component_manifest_count": str(len(component_manifest_rows)),
            "component_manifest_entries": {
                "count": str(len(component_manifest_lines)),
                "jcs_sha256": inventory_digest(component_manifest_lines),
            },
            "component_manifests": component_manifest_rows,
            "license_metadata_spdx": spdx_inventory(metadata_spdx),
            "reuse_spdx": spdx_inventory(reuse_spdx),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument(
        "--profile",
        required=True,
        choices=(
            "go1.26.7-darwin-arm64-host",
            "go1.26.7-source",
            *sorted(RUST_COMPONENT_PROFILES),
            RUST_SOURCE_PROFILE,
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not SHA256_PATTERN.fullmatch(args.expected_sha256):
        parser.error("--expected-sha256 must be 64 lowercase hexadecimal characters")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.profile.startswith("go1.26.7-"):
            value = inspect_go(args)
        else:
            value = inspect_rust(args)
    except (OSError, tarfile.TarError, UnicodeDecodeError, ValueError) as error:
        raise SystemExit(f"inspection failed: {error}") from error
    data = (
        json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    ).encode("ascii")
    if args.output is None:
        print(data.decode("ascii"), end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
