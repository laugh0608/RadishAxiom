#!/usr/bin/env python3
"""Generate and validate toolchain payload acceptance records v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = REPO_ROOT / "contracts/toolchain-payload-acceptance-v0.1"
REGISTRY_PATH = REPO_ROOT / "contracts/toolchain-adapters-v0.1/registry.json"
INSPECTOR_PATH = REPO_ROOT / "scripts/inspect-toolchain-tar.py"
FORMAT = "radishaxiom-toolchain-payload-acceptance-record"
FORMAT_VERSION = "0.1"
RECORD_DIGEST_DOMAIN = "radishaxiom.toolchain-payload-acceptance-record.v0.1"
CONTRACT_FORMAT = "radishaxiom-toolchain-payload-acceptance-set"
CONTRACT_DIGEST_DOMAIN = "radishaxiom.toolchain-payload-acceptance-set.v0.1"
REVIEW_DATE = "2026-08-23"
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

ACCEPTED_SCOPE = [
    "archive-layout-and-metadata",
    "archive-license-and-vendor-inventory",
    "payload-byte-identity",
    "registered-future-isolated-build-input",
]
EXCLUDED_SCOPE = [
    "artifact-execution",
    "artifact-installation",
    "binary-source-reproducibility",
    "checker-implementation-correctness",
    "cross-platform-equivalence",
    "legal-compliance-for-any-specific-distribution",
    "publisher-signature-verification",
]

ARTIFACTS = (
    {
        "download_method": "https-curl-registry-url",
        "filename": "go1.26.7.darwin-arm64.tar.gz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "go1.26.7-darwin-arm64.inspection.json"
        ),
        "platform": "macos-arm64",
        "profile": "go1.26.7-darwin-arm64-host",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "go1.26.7-darwin-arm64.acceptance.json"
        ),
        "record_id": "go1.26.7-darwin-arm64-2026-08-23",
    },
    {
        "download_method": "https-curl-registry-url-range-reassembly",
        "filename": "go1.26.7.src.tar.gz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "go1.26.7-source.inspection.json"
        ),
        "platform": "source",
        "profile": "go1.26.7-source",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "go1.26.7-source.acceptance.json"
        ),
        "record_id": "go1.26.7-source-2026-08-23",
    },
    {
        "component": "cargo",
        "download_method": "https-curl-official-range-reassembly",
        "filename": "cargo-1.97.1-aarch64-apple-darwin.tar.xz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "cargo-1.97.1-aarch64-apple-darwin.inspection.json"
        ),
        "platform": "macos-arm64",
        "profile": "rust-1.97.1-cargo-aarch64-apple-darwin",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "cargo-1.97.1-aarch64-apple-darwin.acceptance.json"
        ),
        "record_id": "cargo-1.97.1-aarch64-apple-darwin-2026-08-30",
        "review_date": "2026-08-30",
        "tool": "rust-toolchain",
        "version": "1.97.1",
    },
    {
        "component": "clippy-preview",
        "download_method": "https-curl-official-range-reassembly",
        "filename": "clippy-1.97.1-aarch64-apple-darwin.tar.xz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "clippy-1.97.1-aarch64-apple-darwin.inspection.json"
        ),
        "platform": "macos-arm64",
        "profile": "rust-1.97.1-clippy-aarch64-apple-darwin",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "clippy-1.97.1-aarch64-apple-darwin.acceptance.json"
        ),
        "record_id": "clippy-1.97.1-aarch64-apple-darwin-2026-08-30",
        "review_date": "2026-08-30",
        "tool": "rust-toolchain",
        "version": "1.97.1",
    },
    {
        "component": "rust-std",
        "download_method": "https-curl-official-range-reassembly",
        "filename": "rust-std-1.97.1-aarch64-apple-darwin.tar.xz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "rust-std-1.97.1-aarch64-apple-darwin.inspection.json"
        ),
        "platform": "macos-arm64",
        "profile": "rust-1.97.1-rust-std-aarch64-apple-darwin",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "rust-std-1.97.1-aarch64-apple-darwin.acceptance.json"
        ),
        "record_id": "rust-std-1.97.1-aarch64-apple-darwin-2026-08-30",
        "review_date": "2026-08-30",
        "tool": "rust-toolchain",
        "version": "1.97.1",
    },
    {
        "component": "rustc",
        "download_method": "https-curl-official-range-reassembly",
        "filename": "rustc-1.97.1-aarch64-apple-darwin.tar.xz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "rustc-1.97.1-aarch64-apple-darwin.inspection.json"
        ),
        "platform": "macos-arm64",
        "profile": "rust-1.97.1-rustc-aarch64-apple-darwin",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "rustc-1.97.1-aarch64-apple-darwin.acceptance.json"
        ),
        "record_id": "rustc-1.97.1-aarch64-apple-darwin-2026-08-30",
        "review_date": "2026-08-30",
        "tool": "rust-toolchain",
        "version": "1.97.1",
    },
    {
        "download_method": "https-curl-official-range-reassembly",
        "filename": "rustc-1.97.1-src.tar.xz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "rustc-1.97.1-source.inspection.json"
        ),
        "platform": "source",
        "profile": "rust-1.97.1-source",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "rustc-1.97.1-source.acceptance.json"
        ),
        "record_id": "rustc-1.97.1-source-2026-08-30",
        "review_date": "2026-08-30",
        "tool": "rust-toolchain",
        "version": "1.97.1",
    },
    {
        "component": "rustfmt-preview",
        "download_method": "https-curl-official-range-reassembly",
        "filename": "rustfmt-1.97.1-aarch64-apple-darwin.tar.xz",
        "observation": (
            "contracts/toolchain-payload-acceptance-v0.1/observations/"
            "rustfmt-1.97.1-aarch64-apple-darwin.inspection.json"
        ),
        "platform": "macos-arm64",
        "profile": "rust-1.97.1-rustfmt-aarch64-apple-darwin",
        "record": (
            "contracts/toolchain-payload-acceptance-v0.1/records/"
            "rustfmt-1.97.1-aarch64-apple-darwin.acceptance.json"
        ),
        "record_id": "rustfmt-1.97.1-aarch64-apple-darwin-2026-08-30",
        "review_date": "2026-08-30",
        "tool": "rust-toolchain",
        "version": "1.97.1",
    },
)

LICENSE_CONCLUSIONS = {
    "sha256:154c946c17de61ca71d28e13673d76a5798e6e25995a7397fbae157afc8f62b4": {
        "components": ["BSD-3-Clause"],
        "conclusion": "BSD-3-Clause",
        "role": "license",
    },
    "sha256:2d36597f7117c38b006835ae7f537487207d8ec407aa9d9980794b2030cbc067": {
        "components": ["BSD-3-Clause"],
        "conclusion": "BSD-3-Clause",
        "role": "license",
    },
    "sha256:56210f826b8f0fbac3160dfe55c97f4019eb6cdda3963b5a0eab8a8bdb62360e": {
        "components": ["BSD-3-Clause", "ISC", "OpenSSL", "SSLeay-standalone"],
        "conclusion": "LicenseRef-Go-BoringCrypto-Bundle",
        "role": "composite-license-bundle",
    },
    "sha256:8cda009bd927676a95ee7ce2dae921442ac4d9584d041b56ecfcba6839032f0b": {
        "components": ["BSD-3-Clause"],
        "conclusion": "BSD-3-Clause",
        "role": "license",
    },
    "sha256:911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad": {
        "components": ["BSD-3-Clause"],
        "conclusion": "BSD-3-Clause",
        "role": "license",
    },
    "sha256:96f408bfae65bf137fc2525d3ecb030271c50c1e90799f87abf8846d8dd505cc": {
        "components": [],
        "conclusion": "PatentGrant-Go",
        "role": "patent-grant",
    },
    "sha256:b73277f7730993ef8e7f80aed83e5309762fed4d77eced982abb2c00657c074d": {
        "components": ["BSD-3-Clause"],
        "conclusion": "BSD-3-Clause",
        "role": "license",
    },
    "sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30": {
        "components": ["Apache-2.0"],
        "conclusion": "Apache-2.0",
        "role": "license",
    },
    "sha256:f99df8ae6da6de047ed002d9dbe8682d9a19c88e9a7473abdadf3ac206621a85": {
        "components": ["MIT"],
        "conclusion": "MIT",
        "role": "license",
    },
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    ).encode("ascii")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def domain_digest(domain: str, body: dict[str, Any]) -> str:
    return sha256_bytes(domain.encode("ascii") + b"\0" + canonical_bytes(body))


def reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text("ascii"), object_pairs_hook=reject_duplicate_members)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def require_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} members drifted")


def require_decimal(value: str, label: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise ValueError(f"{label} must be a canonical decimal string")
    return int(value)


def require_safe_relative_path(value: str, label: str) -> None:
    path = PurePosixPath(value)
    if not value or value.startswith("/") or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} is not a safe relative path: {value!r}")


def find_registry_artifact(
    registry: dict[str, Any], spec: dict[str, str]
) -> dict[str, Any]:
    tool_id = spec.get("tool", "go-toolchain")
    version = spec.get("version", "go1.26.7")
    tools = [item for item in registry["tools"] if item["id"] == tool_id]
    if len(tools) != 1 or tools[0]["version"] != version:
        raise ValueError(f"registry identity drifted: {tool_id} {version}")
    if "component" in spec:
        distribution = tools[0].get("rustup_distribution")
        if not isinstance(distribution, dict):
            raise ValueError("Rust rustup distribution is missing")
        artifacts = [
            item
            for item in distribution["components"]
            if item["filename"] == spec["filename"]
            and item["component"] == spec.get("registry_component", spec["component"])
        ]
    else:
        artifacts = [
            item for item in tools[0]["artifacts"] if item["filename"] == spec["filename"]
        ]
    if len(artifacts) != 1:
        raise ValueError(
            f"registered artifact missing or duplicated: {spec['filename']}"
        )
    return artifacts[0]


def validate_file_inventory(
    rows: list[dict[str, str]], count: str, digest: str, label: str
) -> None:
    if require_decimal(count, f"{label} count") != len(rows):
        raise ValueError(f"{label} count mismatch")
    paths = [row["path"] for row in rows]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError(f"{label} paths must be sorted and unique")
    for row in rows:
        require_keys(row, {"bytes", "path", "raw_sha256"}, f"{label} row")
        require_decimal(row["bytes"], f"{label} bytes")
        require_safe_relative_path(row["path"], f"{label} path")
        if not SHA256_PATTERN.fullmatch(row["raw_sha256"]):
            raise ValueError(f"{label} digest is invalid")
    if digest != sha256_bytes(canonical_bytes(rows)):
        raise ValueError(f"{label} inventory digest mismatch")


def validate_go_observation(
    observation: dict[str, Any], spec: dict[str, str], registry_artifact: dict[str, Any]
) -> None:
    require_keys(
        observation,
        {
            "archive",
            "artifact",
            "format",
            "format_version",
            "inspection_profile",
            "layout_assertions",
            "layout_validation",
            "license_inventory",
            "required_files",
            "vendor_inventory",
        },
        "inspection observation",
    )
    if observation["format"] != "radishaxiom-toolchain-tar-inspection":
        raise ValueError("inspection observation format drifted")
    if observation["format_version"] != "0.1":
        raise ValueError("inspection observation version drifted")
    if observation["inspection_profile"] != spec["profile"]:
        raise ValueError("inspection profile drifted")
    if observation["layout_validation"] != "passed":
        raise ValueError("archive layout was not accepted")

    artifact = observation["artifact"]
    require_keys(artifact, {"bytes", "filename", "raw_sha256"}, "observed artifact")
    if artifact["filename"] != spec["filename"]:
        raise ValueError("observed artifact filename drifted")
    require_decimal(artifact["bytes"], "observed artifact bytes")
    publisher_digest = "sha256:" + registry_artifact["digest"]["sha256"]
    if artifact["raw_sha256"] != publisher_digest:
        raise ValueError("observed digest does not match publisher digest")

    archive = observation["archive"]
    required_archive_keys = {
        "compression",
        "duplicate_path_validation",
        "gid_values",
        "gname_values",
        "link_inventory",
        "link_target_validation",
        "max_regular_file",
        "member_count",
        "member_inventory",
        "mode_values",
        "mtime",
        "path_validation",
        "permission_validation",
        "special_file_validation",
        "top_level",
        "total_regular_bytes",
        "type_counts",
        "uid_values",
        "uname_values",
    }
    require_keys(archive, required_archive_keys, "archive observation")
    for field in (
        "duplicate_path_validation",
        "link_target_validation",
        "path_validation",
        "permission_validation",
        "special_file_validation",
    ):
        if archive[field] != "passed":
            raise ValueError(f"archive {field} did not pass")
    if archive["compression"] != "gzip" or archive["top_level"] != "go":
        raise ValueError("archive envelope drifted")
    if archive["mode_values"] != ["0644", "0755"]:
        raise ValueError("archive permission modes drifted")
    if archive["uid_values"] != ["0"] or archive["gid_values"] != ["0"]:
        raise ValueError("archive owner ids drifted")
    if archive["uname_values"] != [""] or archive["gname_values"] != [""]:
        raise ValueError("archive owner names drifted")
    member_count = require_decimal(archive["member_count"], "archive member count")
    if require_decimal(archive["member_inventory"]["count"], "member inventory count") != member_count:
        raise ValueError("archive member inventory count mismatch")
    if not SHA256_PATTERN.fullmatch(archive["member_inventory"]["jcs_sha256"]):
        raise ValueError("archive member inventory digest is invalid")
    type_total = sum(
        require_decimal(value, f"archive type count {key}")
        for key, value in archive["type_counts"].items()
    )
    if type_total != member_count:
        raise ValueError("archive type counts do not sum to member count")
    if archive["type_counts"].get("hardlink") != "0" or archive["type_counts"].get("symlink") != "0":
        raise ValueError("accepted Go archives must not contain links")
    if archive["link_inventory"]["count"] != "0":
        raise ValueError("accepted Go archive link inventory must be empty")
    require_decimal(archive["total_regular_bytes"], "archive regular bytes")
    require_decimal(archive["max_regular_file"]["bytes"], "archive max file bytes")
    require_safe_relative_path(archive["max_regular_file"]["path"], "archive max file path")
    if archive["mtime"]["unique_count"] != "1":
        raise ValueError("accepted Go archive mtimes must be uniform")
    require_decimal(archive["mtime"]["minimum"], "archive minimum mtime")
    require_decimal(archive["mtime"]["maximum"], "archive maximum mtime")

    required = observation["required_files"]
    required_paths = [row["path"] for row in required]
    if required_paths != ["go/LICENSE", "go/PATENTS", "go/VERSION"]:
        raise ValueError("required Go file set drifted")
    for row in required:
        expected_keys = {"bytes", "path", "raw_sha256"}
        if row["path"] == "go/VERSION":
            expected_keys.add("utf8_text")
            if row["utf8_text"] != "go1.26.7\ntime 2026-08-18T21:44:21Z\n":
                raise ValueError("Go VERSION contents drifted")
        require_keys(row, expected_keys, f"required file {row['path']}")
        require_decimal(row["bytes"], f"required file {row['path']} bytes")
        if not SHA256_PATTERN.fullmatch(row["raw_sha256"]):
            raise ValueError(f"required file digest invalid: {row['path']}")

    licenses = observation["license_inventory"]
    require_keys(licenses, {"count", "files", "jcs_sha256"}, "license inventory")
    validate_file_inventory(
        licenses["files"], licenses["count"], licenses["jcs_sha256"], "license"
    )
    observed_license_digests = {row["raw_sha256"] for row in licenses["files"]}
    if observed_license_digests != set(LICENSE_CONCLUSIONS):
        raise ValueError("license text conclusion set is incomplete or stale")

    vendor = observation["vendor_inventory"]
    require_keys(
        vendor,
        {"manifest_count", "manifests", "module_count", "modules", "modules_jcs_sha256"},
        "vendor inventory",
    )
    validate_file_inventory(
        vendor["manifests"], vendor["manifest_count"],
        sha256_bytes(canonical_bytes(vendor["manifests"])), "vendor manifest"
    )
    module_rows = vendor["modules"]
    if require_decimal(vendor["module_count"], "vendor module count") != len(module_rows):
        raise ValueError("vendor module count mismatch")
    if module_rows != sorted(
        module_rows, key=lambda row: (row["manifest"], row["module"], row["version"])
    ):
        raise ValueError("vendor modules must be sorted")
    for row in module_rows:
        if set(row) not in ({"manifest", "module", "version"}, {"manifest", "module", "replacement", "version"}):
            raise ValueError("vendor module shape drifted")
        require_safe_relative_path(row["manifest"], "vendor module manifest")
    if vendor["modules_jcs_sha256"] != sha256_bytes(canonical_bytes(module_rows)):
        raise ValueError("vendor module inventory digest mismatch")

    layout = observation["layout_assertions"]
    if layout != sorted(layout, key=lambda row: (row["path"], row["expectation"])):
        raise ValueError("layout assertions must be sorted")
    for row in layout:
        require_keys(row, {"expectation", "path"}, "layout assertion")
        require_safe_relative_path(row["path"], "layout assertion path")
        if row["expectation"] not in {"absent", "present"}:
            raise ValueError("layout assertion expectation is invalid")


RUST_OBSERVATION_FACTS = {
    "rust-1.97.1-cargo-aarch64-apple-darwin": {
        "component": "cargo",
        "component_entries": "44",
        "component_entries_digest": "sha256:1d713b39c7223b149e0085fe09d1a52fb30f9b994527744221de38f4029138bd",
        "license_digest": "sha256:afb53053d6d49dfdf7569bc7ae2464ca3cafef70d6eaede271a553f5af6d479a",
        "licenses": "3",
        "member_digest": "sha256:98d89c727664d915b982feacaa8cc7f9e1856c6080d1eb52b7d33458f94b8245",
        "members": "68",
        "regular_bytes": "32496408",
    },
    "rust-1.97.1-clippy-aarch64-apple-darwin": {
        "component": "clippy-preview",
        "component_entries": "5",
        "component_entries_digest": "sha256:9dbe98df3a92dc82e1a3d71776b1664f542c4c6aa0fd13835681a4b1852bac90",
        "license_digest": "sha256:fdfd57325f7fadcd8fcf5bd19cea0f6937e1a4ec5e5c7841a8e2a58d4825d1b4",
        "licenses": "2",
        "member_digest": "sha256:b5dadfc53ccd1c5ea3eaea6d6aa95da85f55e30ead9319e237168015a68ff2fe",
        "members": "22",
        "regular_bytes": "16282904",
    },
    "rust-1.97.1-rust-std-aarch64-apple-darwin": {
        "component": "rust-std-aarch64-apple-darwin",
        "component_entries": "59",
        "component_entries_digest": "sha256:dea1a7b421446dcf433b59137294bdac531198fd20c65ba9f55f083b5ff56a9d",
        "license_digest": "sha256:1adeae8c6932213779cdccdd3c0fbf99e16c2e793b28d02952affce0d3c5c182",
        "licenses": "3",
        "member_digest": "sha256:36fc82c724ae07a134e12a0df9b5edb3e3af9a213443fcfa554413429df7c54d",
        "members": "78",
        "regular_bytes": "143434831",
    },
    "rust-1.97.1-rustc-aarch64-apple-darwin": {
        "component": "rustc",
        "component_entries": "43",
        "component_entries_digest": "sha256:e2cc0361ce4788cc12494e16b4365db9326bd8fbdd86b6c0cb0b3998b792dd13",
        "license_digest": "sha256:f62e987a606a36babd725647d5ba608cee0e73dece4b0a680067d2bb1c0468db",
        "licenses": "3",
        "member_digest": "sha256:276b98cfcda205521c6955159934c36e9bda9e3f182d55ba33747bc7345e14b4",
        "members": "72",
        "regular_bytes": "391144454",
    },
    "rust-1.97.1-rustfmt-aarch64-apple-darwin": {
        "component": "rustfmt-preview",
        "component_entries": "5",
        "component_entries_digest": "sha256:2b7df6f6c58ca78cb1a516a3c1b88d5ebfd3fdd84f29ad32965cac771bdc87c3",
        "license_digest": "sha256:838a379e1c9b0ac0d0a756c687321e70218bb41a21c9cca923d879609ae60abe",
        "licenses": "2",
        "member_digest": "sha256:b375fbbd1ca7685b25daff5bad5523e2179b70e10e9e0f4cbcf8b09430736606",
        "members": "22",
        "regular_bytes": "5795401",
    },
    "rust-1.97.1-source": {
        "component": "rust-source",
        "component_entries": "0",
        "component_entries_digest": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "license_digest": "sha256:7e218cd47b4dea984b9457dcf8087e726d0cfb9dfd15371f6dc27e675d7f72d1",
        "licenses": "17",
        "member_digest": "sha256:0814b0fbd4da65b86bb3362e76b8e9c9f24a0566b2d071e1dc9be7b4c4cedcac",
        "members": "323914",
        "regular_bytes": "3487143731",
    },
}


def validate_spdx_inventory(value: dict[str, Any], label: str) -> None:
    require_keys(
        value,
        {"expressions", "jcs_sha256", "occurrence_count", "unique_count"},
        label,
    )
    rows = value["expressions"]
    if require_decimal(value["unique_count"], f"{label} unique count") != len(rows):
        raise ValueError(f"{label} unique count mismatch")
    if rows != sorted(rows, key=lambda row: row["expression"]):
        raise ValueError(f"{label} expressions must be sorted")
    total = 0
    for row in rows:
        require_keys(row, {"expression", "occurrences"}, f"{label} expression")
        if not row["expression"]:
            raise ValueError(f"{label} expression is empty")
        total += require_decimal(row["occurrences"], f"{label} occurrences")
    if total != require_decimal(value["occurrence_count"], f"{label} occurrence count"):
        raise ValueError(f"{label} occurrence count mismatch")
    if value["jcs_sha256"] != sha256_bytes(canonical_bytes(rows)):
        raise ValueError(f"{label} inventory digest mismatch")


def validate_rust_observation(
    observation: dict[str, Any], spec: dict[str, str], registry_artifact: dict[str, Any]
) -> None:
    require_keys(
        observation,
        {
            "archive",
            "artifact",
            "format",
            "format_version",
            "inspection_profile",
            "layout_assertions",
            "layout_validation",
            "license_inventory",
            "required_files",
            "rust_inventory",
        },
        "Rust inspection observation",
    )
    if observation["format"] != "radishaxiom-toolchain-tar-inspection":
        raise ValueError("Rust inspection observation format drifted")
    if observation["format_version"] != "0.1":
        raise ValueError("Rust inspection observation version drifted")
    if observation["inspection_profile"] != spec["profile"]:
        raise ValueError("Rust inspection profile drifted")
    if observation["layout_validation"] != "passed":
        raise ValueError("Rust archive layout was not accepted")

    artifact_value = observation["artifact"]
    require_keys(artifact_value, {"bytes", "filename", "raw_sha256"}, "Rust artifact")
    if artifact_value["filename"] != spec["filename"]:
        raise ValueError("Rust observed artifact filename drifted")
    require_decimal(artifact_value["bytes"], "Rust artifact bytes")
    if artifact_value["raw_sha256"] != "sha256:" + registry_artifact["digest"]["sha256"]:
        raise ValueError("Rust observed digest does not match publisher digest")

    archive = observation["archive"]
    required_archive_keys = {
        "compression",
        "duplicate_path_validation",
        "gid_values",
        "gname_values",
        "link_inventory",
        "link_target_validation",
        "max_regular_file",
        "member_count",
        "member_inventory",
        "mode_values",
        "mtime",
        "path_validation",
        "permission_validation",
        "special_file_validation",
        "top_level",
        "total_regular_bytes",
        "type_counts",
        "uid_values",
        "uname_values",
    }
    require_keys(archive, required_archive_keys, "Rust archive observation")
    for field in (
        "duplicate_path_validation",
        "link_target_validation",
        "path_validation",
        "permission_validation",
        "special_file_validation",
    ):
        if archive[field] != "passed":
            raise ValueError(f"Rust archive {field} did not pass")
    top = spec["filename"].removesuffix(".tar.xz")
    if archive["compression"] != "xz" or archive["top_level"] != top:
        raise ValueError("Rust archive envelope drifted")
    if archive["mode_values"] != ["0644", "0755"]:
        raise ValueError("Rust archive modes drifted")
    if archive["uid_values"] != ["0"] or archive["gid_values"] != ["0"]:
        raise ValueError("Rust archive owner ids drifted")
    if archive["uname_values"] != [""] or archive["gname_values"] != [""]:
        raise ValueError("Rust archive owner names drifted")
    facts = RUST_OBSERVATION_FACTS[spec["profile"]]
    if archive["member_count"] != facts["members"]:
        raise ValueError("Rust archive member count drifted")
    if archive["total_regular_bytes"] != facts["regular_bytes"]:
        raise ValueError("Rust archive regular byte count drifted")
    if archive["member_inventory"]["count"] != archive["member_count"]:
        raise ValueError("Rust member inventory count mismatch")
    if archive["member_inventory"]["jcs_sha256"] != facts["member_digest"]:
        raise ValueError("Rust member inventory digest drifted")
    if sum(require_decimal(value, f"Rust type count {key}") for key, value in archive["type_counts"].items()) != require_decimal(archive["member_count"], "Rust member count"):
        raise ValueError("Rust archive type counts do not sum to member count")
    if archive["type_counts"].get("hardlink") != "0":
        raise ValueError("Rust archive contains hardlinks")
    expected_symlinks = "148" if spec["profile"] == "rust-1.97.1-source" else "0"
    if archive["type_counts"].get("symlink") != expected_symlinks:
        raise ValueError("Rust archive symlink count drifted")
    if archive["link_inventory"]["count"] != expected_symlinks:
        raise ValueError("Rust link inventory count drifted")
    expected_link_digest = (
        "sha256:8aab3c45eecb013f3c2e18d51ed4cfd7e1f176a0c0dde7ab6b325f97a1ce6170"
        if spec["profile"] == "rust-1.97.1-source"
        else "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    )
    if archive["link_inventory"]["jcs_sha256"] != expected_link_digest:
        raise ValueError("Rust link inventory digest drifted")
    if archive["mtime"]["unique_count"] != "2":
        raise ValueError("Rust archive mtime set drifted")

    required = observation["required_files"]
    paths = [row["path"] for row in required]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError("Rust required file paths must be sorted and unique")
    for row in required:
        expected_keys = {"bytes", "path", "raw_sha256"}
        if "utf8_text" in row:
            expected_keys.add("utf8_text")
        require_keys(row, expected_keys, f"Rust required file {row['path']}")
        require_decimal(row["bytes"], f"Rust required file {row['path']} bytes")
        require_safe_relative_path(row["path"], "Rust required file path")
        if not SHA256_PATTERN.fullmatch(row["raw_sha256"]):
            raise ValueError(f"Rust required file digest invalid: {row['path']}")

    licenses = observation["license_inventory"]
    require_keys(licenses, {"count", "files", "jcs_sha256"}, "Rust license inventory")
    validate_file_inventory(
        licenses["files"], licenses["count"], licenses["jcs_sha256"], "Rust license"
    )
    if licenses["count"] != facts["licenses"]:
        raise ValueError("Rust license inventory count drifted")
    if licenses["jcs_sha256"] != facts["license_digest"]:
        raise ValueError("Rust license inventory digest drifted")

    inventory = observation["rust_inventory"]
    require_keys(
        inventory,
        {
            "cargo_lock_count",
            "cargo_manifest_count",
            "component",
            "component_manifest_count",
            "component_manifest_entries",
            "component_manifests",
            "license_metadata_spdx",
            "reuse_spdx",
        },
        "Rust inventory",
    )
    if inventory["component"] != facts["component"]:
        raise ValueError("Rust component identity drifted")
    is_source = spec["profile"] == "rust-1.97.1-source"
    expected_counts = ("1977", "4613", "0") if is_source else ("0", "0", "1")
    actual_counts = (
        inventory["cargo_lock_count"],
        inventory["cargo_manifest_count"],
        inventory["component_manifest_count"],
    )
    if actual_counts != expected_counts:
        raise ValueError("Rust dependency inventory counts drifted")
    if require_decimal(inventory["component_manifest_count"], "component manifest count") != len(inventory["component_manifests"]):
        raise ValueError("Rust component manifest count mismatch")
    for row in inventory["component_manifests"]:
        require_keys(row, {"bytes", "path", "raw_sha256"}, "Rust component manifest")
    if inventory["component_manifest_entries"] != {
        "count": facts["component_entries"],
        "jcs_sha256": facts["component_entries_digest"],
    }:
        raise ValueError("Rust component manifest entry inventory drifted")
    validate_spdx_inventory(inventory["license_metadata_spdx"], "license metadata SPDX")
    validate_spdx_inventory(inventory["reuse_spdx"], "REUSE SPDX")
    if is_source:
        expected_spdx = (
            "22",
            "12",
            "sha256:0f9629ad80450125d2b32c2ba5b7d0a84a83dd369c452ed3a9c66f5f958c919c",
            "20",
            "12",
            "sha256:70f943dbbfc6fd6c8e2a9ec04a85c7f61980c518bbcd66ef26ddc5287e83137e",
        )
        actual_spdx = (
            inventory["license_metadata_spdx"]["occurrence_count"],
            inventory["license_metadata_spdx"]["unique_count"],
            inventory["license_metadata_spdx"]["jcs_sha256"],
            inventory["reuse_spdx"]["occurrence_count"],
            inventory["reuse_spdx"]["unique_count"],
            inventory["reuse_spdx"]["jcs_sha256"],
        )
        if actual_spdx != expected_spdx:
            raise ValueError("Rust source SPDX inventory drifted")
    elif inventory["license_metadata_spdx"]["unique_count"] != "0" or inventory["reuse_spdx"]["unique_count"] != "0":
        raise ValueError("Rust component archive overclaims source SPDX metadata")

    layout = observation["layout_assertions"]
    if layout != sorted(layout, key=lambda row: (row["path"], row["expectation"])):
        raise ValueError("Rust layout assertions must be sorted")
    for row in layout:
        require_keys(row, {"expectation", "path"}, "Rust layout assertion")
        require_safe_relative_path(row["path"], "Rust layout assertion path")
        if row["expectation"] != "present":
            raise ValueError("Rust layout assertion must require presence")


def license_conclusions(observation: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in observation["license_inventory"]["files"]:
        counts[row["raw_sha256"]] = counts.get(row["raw_sha256"], 0) + 1
    return [
        {
            **LICENSE_CONCLUSIONS[digest],
            "file_count": str(counts[digest]),
            "raw_sha256": digest,
        }
        for digest in sorted(counts)
    ]


def build_record(
    spec: dict[str, str], observation: dict[str, Any], registry_artifact: dict[str, Any]
) -> dict[str, Any]:
    inspector_binding = {
        "path": "scripts/inspect-toolchain-tar.py",
        "raw_sha256": raw_sha256(INSPECTOR_PATH),
    }
    observation_path = REPO_ROOT / spec["observation"]
    required = {row["path"]: row for row in observation["required_files"]}
    is_rust = spec.get("tool") == "rust-toolchain"
    artifact_value = {
        "bytes": observation["artifact"]["bytes"],
        "filename": spec["filename"],
        "platform": spec["platform"],
        "tool": spec.get("tool", "go-toolchain"),
        "version": spec.get("version", "go1.26.7"),
    }
    if "component" in spec:
        artifact_value["component"] = spec["component"]
    if is_rust:
        inventory = observation["rust_inventory"]
        dependency_inventory = {
            "cargo_lock_count": inventory["cargo_lock_count"],
            "cargo_manifest_count": inventory["cargo_manifest_count"],
            "component": inventory["component"],
            "component_manifest_count": inventory["component_manifest_count"],
            "component_manifest_entries": inventory["component_manifest_entries"],
            "component_manifests": inventory["component_manifests"],
            "scope": "archive-contained-rust-static-metadata",
            "status": "inventoried-not-executed",
        }
        main_license_files = [
            row
            for path, row in required.items()
            if PurePosixPath(path).name in {"LICENSE-APACHE", "LICENSE-MIT"}
        ]
        license_review = {
            "bundled_inventory_status": "recorded-not-a-legal-conclusion",
            "inventory_count": observation["license_inventory"]["count"],
            "inventory_jcs_sha256": observation["license_inventory"]["jcs_sha256"],
            "license_metadata_spdx": inventory["license_metadata_spdx"],
            "main_expression": "MIT OR Apache-2.0",
            "main_license_files": sorted(main_license_files, key=lambda row: row["path"]),
            "reuse_spdx": inventory["reuse_spdx"],
            "scope": "selected-root-license-files-and-publisher-license-metadata",
            "status": "archive-inventory-recorded",
        }
        accepted_scope = [
            "archive-layout-and-metadata",
            "archive-license-and-component-inventory",
            "payload-byte-identity",
            "registered-future-isolated-build-input",
        ]
    else:
        dependency_inventory = {
            "manifest_count": observation["vendor_inventory"]["manifest_count"],
            "manifests": observation["vendor_inventory"]["manifests"],
            "module_count": observation["vendor_inventory"]["module_count"],
            "modules": observation["vendor_inventory"]["modules"],
            "modules_jcs_sha256": observation["vendor_inventory"]["modules_jcs_sha256"],
            "scope": "archive-contained-go-vendor-manifests",
            "status": "inventoried",
        }
        license_review = {
            "conclusions": license_conclusions(observation),
            "inventory_count": observation["license_inventory"]["count"],
            "inventory_jcs_sha256": observation["license_inventory"]["jcs_sha256"],
            "main_expression": "BSD-3-Clause",
            "main_license": required["go/LICENSE"],
            "patent_grant": required["go/PATENTS"],
            "scope": "archive-contained-license-and-patent-files",
            "status": "archive-inventory-reviewed",
        }
        accepted_scope = ACCEPTED_SCOPE
    body = {
        "acceptance": {
            "accepted_scope": accepted_scope,
            "decision": "accepted-for-controlled-build-input",
            "excluded_scope": EXCLUDED_SCOPE,
            "review_date": spec.get("review_date", REVIEW_DATE),
        },
        "artifact": artifact_value,
        "dependency_inventory": dependency_inventory,
        "digest_domain": RECORD_DIGEST_DOMAIN,
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "id": spec["record_id"],
        "inspection": {
            "archive": observation["archive"],
            "layout_assertions": observation["layout_assertions"],
            "method": inspector_binding,
            "observation": {
                "path": spec["observation"],
                "raw_sha256": raw_sha256(observation_path),
            },
            "profile": spec["profile"],
            "result": "passed",
        },
        "license_review": license_review,
        "provenance": {
            "download_method": spec["download_method"],
            "download_url": registry_artifact["source_url"],
            "project_recomputation": {
                "raw_sha256": observation["artifact"]["raw_sha256"],
                "result": "matched",
            },
            "publisher_digest": {
                "kind": registry_artifact["digest"]["kind"],
                "raw_sha256": "sha256:" + registry_artifact["digest"]["sha256"],
                "source": registry_artifact["digest"]["source"],
            },
            "signature": {
                "reason": "no detached-signature input is recorded for this artifact in registry v0.1",
                "status": "not-verified-no-signature-input",
            },
        },
    }
    return {**body, "record_digest": domain_digest(RECORD_DIGEST_DOMAIN, body)}


def validate_record(value: dict[str, Any], expected: dict[str, Any]) -> None:
    if set(value) != set(expected):
        raise ValueError("acceptance record top-level members drifted")
    body = {key: item for key, item in value.items() if key != "record_digest"}
    if value.get("record_digest") != domain_digest(RECORD_DIGEST_DOMAIN, body):
        raise ValueError("acceptance record digest mismatch")
    if canonical_bytes(value) != canonical_bytes(expected):
        raise ValueError("acceptance record exceeds or drifts from observed policy")


def infer_schema(values: list[Any], key: str = "") -> dict[str, Any]:
    if values and all(isinstance(value, dict) for value in values):
        dictionaries = values
        all_keys = sorted(set().union(*(value.keys() for value in dictionaries)))
        required = sorted(set.intersection(*(set(value) for value in dictionaries)))
        return {
            "additionalProperties": False,
            "properties": {
                child: infer_schema(
                    [value[child] for value in dictionaries if child in value], child
                )
                for child in all_keys
            },
            "required": required,
            "type": "object",
        }
    if values and all(isinstance(value, list) for value in values):
        items = [item for value in values for item in value]
        result: dict[str, Any] = {"type": "array"}
        if items:
            result["items"] = infer_schema(items, key)
        return result
    if values and all(isinstance(value, str) for value in values):
        if values and all(SHA256_PATTERN.fullmatch(value) for value in values):
            return {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"}
        if values and all(re.fullmatch(r"0|[1-9][0-9]*", value) for value in values):
            return {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"}
        return {"type": "string"}
    if values and all(isinstance(value, bool) for value in values):
        return {"type": "boolean"}
    raise ValueError(f"cannot infer schema for {key}: mixed or unsupported values")


def record_schema(records: list[dict[str, Any]]) -> dict[str, Any]:
    result = infer_schema(records)
    result.update(
        {
            "$id": "https://radishaxiom.dev/schema/toolchain-payload-acceptance-record/0.1",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "RadishAxiom toolchain payload acceptance record v0.1",
        }
    )
    result["properties"]["format"] = {"const": FORMAT}
    result["properties"]["format_version"] = {"const": FORMAT_VERSION}
    result["properties"]["digest_domain"] = {"const": RECORD_DIGEST_DOMAIN}
    return result


def observation_schema(observations: list[dict[str, Any]]) -> dict[str, Any]:
    result = infer_schema(observations)
    result.update(
        {
            "$id": "https://radishaxiom.dev/schema/toolchain-tar-inspection/0.1",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "RadishAxiom toolchain tar inspection observation v0.1",
        }
    )
    result["properties"]["format"] = {
        "const": "radishaxiom-toolchain-tar-inspection"
    }
    result["properties"]["format_version"] = {"const": "0.1"}
    return result


def refreshed(value: dict[str, Any]) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key != "record_digest"}
    value["record_digest"] = domain_digest(RECORD_DIGEST_DOMAIN, body)
    return value


def negative_fixtures(record: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    result: list[tuple[str, str, dict[str, Any]]] = []

    value = copy.deepcopy(record)
    value["provenance"]["project_recomputation"]["raw_sha256"] = "sha256:" + "0" * 64
    result.append(("recomputed-digest-mismatch.invalid.json", "project digest differs from observation", refreshed(value)))

    value = copy.deepcopy(record)
    value["provenance"]["signature"]["status"] = "verified"
    result.append(("signature-overclaim.invalid.json", "signature verification is overclaimed", refreshed(value)))

    value = copy.deepcopy(record)
    value["inspection"]["result"] = "failed"
    result.append(("failed-inspection-accepted.invalid.json", "failed inspection cannot be accepted", refreshed(value)))

    value = copy.deepcopy(record)
    value["acceptance"]["excluded_scope"].remove("artifact-execution")
    result.append(("execution-exclusion-missing.invalid.json", "execution limitation is missing", refreshed(value)))

    value = copy.deepcopy(record)
    value["license_review"]["inventory_jcs_sha256"] = "sha256:" + "0" * 64
    result.append(("license-inventory-drift.invalid.json", "license inventory digest differs from observation", refreshed(value)))

    value = copy.deepcopy(record)
    value["dependency_inventory"]["module_count"] = "18"
    result.append(("vendor-module-count-drift.invalid.json", "vendor module count differs from observation", refreshed(value)))

    value = copy.deepcopy(record)
    value["unexpected"] = "member"
    result.append(("unknown-member.invalid.json", "closed record rejects unknown member", refreshed(value)))

    return result


def build_contract(records: list[tuple[dict[str, str], dict[str, Any]]], registry: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for spec, record in records:
        record_bytes = pretty_bytes(record)
        rows.append(
            {
                "artifact_filename": spec["filename"],
                "decision": record["acceptance"]["decision"],
                "id": record["id"],
                "path": spec["record"],
                "platform": spec["platform"],
                "raw_sha256": sha256_bytes(record_bytes),
                "record_digest": record["record_digest"],
            }
        )
    body = {
        "counts": {"accepted_records": str(len(rows)), "observations": str(len(rows))},
        "digest_domain": CONTRACT_DIGEST_DOMAIN,
        "format": CONTRACT_FORMAT,
        "format_version": FORMAT_VERSION,
        "inspection_method": {
            "path": "scripts/inspect-toolchain-tar.py",
            "raw_sha256": raw_sha256(INSPECTOR_PATH),
        },
        "records": rows,
        "registry_binding": {
            "path": "contracts/toolchain-adapters-v0.1/registry.json",
            "raw_sha256": raw_sha256(REGISTRY_PATH),
            "registry_digest": registry["registry_digest"],
        },
        "review_date": "2026-08-30",
    }
    return {**body, "contract_digest": domain_digest(CONTRACT_DIGEST_DOMAIN, body)}


def outputs() -> dict[Path, bytes]:
    registry = load_json(REGISTRY_PATH)
    built: list[tuple[dict[str, str], dict[str, Any]]] = []
    observations: list[dict[str, Any]] = []
    expected: dict[Path, bytes] = {}
    for spec in ARTIFACTS:
        registry_artifact = find_registry_artifact(registry, spec)
        if registry_artifact.get("acceptance_record") != spec["record"]:
            raise ValueError(f"registry acceptance record drifted: {spec['filename']}")
        expected_status = {
            "acceptance": "accepted-for-controlled-build-input",
            "archive_inspection": "passed-toolchain-tar-v0.1",
            "payload_verification": "sha256-matched-publisher-record",
        }
        for field, value in expected_status.items():
            if registry_artifact.get(field) != value:
                raise ValueError(
                    f"registry {field} does not authorize the accepted record: "
                    f"{spec['filename']}"
                )
        observation_path = REPO_ROOT / spec["observation"]
        observation = load_json(observation_path)
        if observation_path.read_bytes() != pretty_bytes(observation):
            raise ValueError(f"inspection observation encoding drifted: {spec['observation']}")
        if spec.get("tool") == "rust-toolchain":
            validate_rust_observation(observation, spec, registry_artifact)
        else:
            validate_go_observation(observation, spec, registry_artifact)
        record = build_record(spec, observation, registry_artifact)
        validate_record(record, record)
        expected[REPO_ROOT / spec["record"]] = pretty_bytes(record)
        built.append((spec, record))
        observations.append(observation)

    if observations[0]["required_files"] != observations[1]["required_files"]:
        raise ValueError("Go host/source required files differ")
    if observations[0]["license_inventory"] != observations[1]["license_inventory"]:
        raise ValueError("Go host/source license inventories differ")
    if observations[0]["vendor_inventory"] != observations[1]["vendor_inventory"]:
        raise ValueError("Go host/source vendor inventories differ")

    records = [record for _, record in built]
    expected[CONTRACT_ROOT / "contract.json"] = pretty_bytes(build_contract(built, registry))
    expected[
        CONTRACT_ROOT / "schemas/toolchain-payload-acceptance-record.schema.json"
    ] = pretty_bytes(record_schema(records))
    expected[
        CONTRACT_ROOT / "schemas/toolchain-tar-inspection-observation.schema.json"
    ] = pretty_bytes(observation_schema(observations))

    negative_rows = []
    for filename, reason, fixture in negative_fixtures(records[0]):
        try:
            validate_record(fixture, records[0])
        except ValueError:
            pass
        else:
            raise ValueError(f"negative fixture was accepted: {filename}")
        path = CONTRACT_ROOT / "fixtures/negative" / filename
        expected[path] = pretty_bytes(fixture)
        negative_rows.append({"file": filename, "reason": reason})
    expected[CONTRACT_ROOT / "fixtures/negative/expected.json"] = pretty_bytes(
        {"format": "radishaxiom-toolchain-payload-acceptance-negative-set", "format_version": "0.1", "fixtures": negative_rows}
    )
    return expected


def write_outputs(expected: dict[Path, bytes]) -> None:
    for path, data in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"wrote toolchain payload acceptance ({len(expected)} generated files)")


def check_outputs(expected: dict[Path, bytes]) -> int:
    errors: list[str] = []
    for path, data in expected.items():
        if not path.is_file():
            errors.append(f"missing generated file: {path.relative_to(REPO_ROOT)}")
        elif path.read_bytes() != data:
            errors.append(f"generated file drifted: {path.relative_to(REPO_ROOT)}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"toolchain payload acceptance passed ({len(expected)} generated files)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check generated files")
    mode.add_argument("--write", action="store_true", help="write generated files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        expected = outputs()
        if args.write:
            write_outputs(expected)
            return 0
        return check_outputs(expected)
    except (KeyError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(f"toolchain payload acceptance failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
