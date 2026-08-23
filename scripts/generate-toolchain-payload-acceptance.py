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


def find_go_artifact(registry: dict[str, Any], filename: str) -> dict[str, Any]:
    tools = [item for item in registry["tools"] if item["id"] == "go-toolchain"]
    if len(tools) != 1 or tools[0]["version"] != "go1.26.7":
        raise ValueError("Go registry identity drifted")
    artifacts = [item for item in tools[0]["artifacts"] if item["filename"] == filename]
    if len(artifacts) != 1:
        raise ValueError(f"registered Go artifact missing or duplicated: {filename}")
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


def validate_observation(
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
    body = {
        "acceptance": {
            "accepted_scope": ACCEPTED_SCOPE,
            "decision": "accepted-for-controlled-build-input",
            "excluded_scope": EXCLUDED_SCOPE,
            "review_date": REVIEW_DATE,
        },
        "artifact": {
            "bytes": observation["artifact"]["bytes"],
            "filename": spec["filename"],
            "platform": spec["platform"],
            "tool": "go-toolchain",
            "version": "go1.26.7",
        },
        "dependency_inventory": {
            "manifest_count": observation["vendor_inventory"]["manifest_count"],
            "manifests": observation["vendor_inventory"]["manifests"],
            "module_count": observation["vendor_inventory"]["module_count"],
            "modules": observation["vendor_inventory"]["modules"],
            "modules_jcs_sha256": observation["vendor_inventory"]["modules_jcs_sha256"],
            "scope": "archive-contained-go-vendor-manifests",
            "status": "inventoried",
        },
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
        "license_review": {
            "conclusions": license_conclusions(observation),
            "inventory_count": observation["license_inventory"]["count"],
            "inventory_jcs_sha256": observation["license_inventory"]["jcs_sha256"],
            "main_expression": "BSD-3-Clause",
            "main_license": required["go/LICENSE"],
            "patent_grant": required["go/PATENTS"],
            "scope": "archive-contained-license-and-patent-files",
            "status": "archive-inventory-reviewed",
        },
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
        "review_date": REVIEW_DATE,
    }
    return {**body, "contract_digest": domain_digest(CONTRACT_DIGEST_DOMAIN, body)}


def outputs() -> dict[Path, bytes]:
    registry = load_json(REGISTRY_PATH)
    built: list[tuple[dict[str, str], dict[str, Any]]] = []
    observations: list[dict[str, Any]] = []
    expected: dict[Path, bytes] = {}
    for spec in ARTIFACTS:
        registry_artifact = find_go_artifact(registry, spec["filename"])
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
        validate_observation(observation, spec, registry_artifact)
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
