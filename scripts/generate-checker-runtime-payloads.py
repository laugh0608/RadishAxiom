#!/usr/bin/env python3
"""Generate and validate checker runtime payload registration records v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = REPO_ROOT / "contracts/checker-runtime-payloads-v0.1"
FORMAT = "radishaxiom-checker-runtime-payload-registration"
FORMAT_VERSION = "0.1"
RECORD_DOMAIN = "radishaxiom.checker-runtime-payload-registration.v0.1"
SET_FORMAT = "radishaxiom-checker-runtime-payload-registration-set"
SET_DOMAIN = "radishaxiom.checker-runtime-payload-registration-set.v0.1"
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

CURRENT_SOURCE = {
    "file_count": "695",
    "identity": "sha256:675f8ff470a621124ede081bcf8330b73910ab34e20b7b174356d57423e6ee74",
    "manifest_byte_length": "185571",
}
HISTORICAL_SOURCE = {
    "file_count": "682",
    "identity": "sha256:3b809ba6f062dbc1c543b64d9eb01f1fe46bdadf29f2d441b6d1c068200d90b4",
    "manifest_byte_length": "183203",
}
ACCEPTED_SCOPE = [
    "artifact-byte-reproducibility",
    "build-metadata",
    "runtime-self-identity",
    "scenario-behavior",
]
EXCLUDED_SCOPE = [
    "cross-platform-equivalence",
    "installation",
    "launcher-hard-isolation",
    "legal-compliance-for-distribution",
    "publication",
    "release-signing",
]

STORAGE_POLICY = {
    "active_runtime": {
        "provider": "not-selected",
        "requirements": [
            "independent-provider-readback",
            "immutable-asset-bytes",
            "no-latest-alias",
            "raw-byte-length-and-sha256",
            "revocation-and-replacement-policy",
            "separate-publication-authorization",
            "stable-exact-fetch",
        ],
        "status": "blocked-release-and-storage-governance-pending",
    },
    "candidate": {
        "expiration_effect": "candidate-becomes-unavailable",
        "fetch_resolution": "exact-artifact-id-only",
        "provider": "github-actions-artifact",
        "readback": "separate-job-provider-download-and-inner-archive-verification",
        "registration_effect": "candidate-only-never-active",
        "repository": "laugh0608/RadishAxiomChecker",
        "required_inner_bindings": [
            "archive-byte-length",
            "archive-raw-sha256",
            "retention-manifest-byte-length",
            "retention-manifest-raw-sha256",
        ],
        "required_provider_bindings": [
            "artifact-id",
            "created-at",
            "expires-at",
            "provider-archive-digest",
            "provider-archive-size",
            "workflow-head-sha",
            "workflow-run-id",
        ],
        "retention_days": "90",
        "status": "selected-not-materialized",
        "upload_object": "deterministic-inner-ustar",
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


def record(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "record_digest": domain_digest(RECORD_DOMAIN, body)}


def common(record_id: str, source: dict[str, str]) -> dict[str, Any]:
    return {
        "checker": {
            "implementation": "radishaxiom-independent-checker-go",
            "source": source,
            "toolchain": "go1.26.7",
            "version": "0.1-dev",
        },
        "digest_domain": RECORD_DOMAIN,
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "id": record_id,
        "target": {
            "executable_format": "macho-64-arm64",
            "goarch": "arm64",
            "goarm64": "v8.0",
            "goos": "darwin",
        },
    }


def historical_record() -> dict[str, Any]:
    body = {
        **common("checker-go0.1-dev-darwin-arm64-historical-2026-08-28", HISTORICAL_SOURCE),
        "acceptance": {
            "byte_length": "1580",
            "decision": "accepted-for-controlled-runtime-registration",
            "excluded_scope": EXCLUDED_SCOPE,
            "format": "radishaxiom-checker-payload-acceptance",
            "format_version": "0.1",
            "kind": "known-digest",
            "raw_sha256": "sha256:fb148d749622511ab6d13bcc2c35db10076a4cc9286e95d08443d3822ca1742a",
            "scenarios": [
                {
                    "byte_length": "7699",
                    "id": "ax-b01-correct",
                    "outcome": "accepted-with-trust",
                    "raw_sha256": "sha256:0f519d63ce293548c2988915ee0e9dd269ad3632e9c4f7a06c0ff3cb6332a97b",
                },
                {
                    "byte_length": "2254",
                    "id": "chk-digest-01",
                    "outcome": "rejected",
                    "raw_sha256": "sha256:97695d7a83bf2f3b46823037d2e7f2a44cde0754cd9d5727c39d9d7da1b72875",
                },
                {
                    "byte_length": "2935",
                    "id": "chk-resource-01",
                    "outcome": "incomplete",
                    "raw_sha256": "sha256:4b70570fcdf47be6d4cb329eb4da3de3739fb1557316a8a2630625f000879251",
                },
            ],
            "scope": ACCEPTED_SCOPE,
        },
        "artifact": {
            "byte_length": "4689378",
            "kind": "known-digest",
            "raw_sha256": "sha256:ef66c4d9098d058796e4f9d7e0f7713e73fc954e94c97a4001abd28acdbd99dc",
        },
        "build_provenance": {
            "byte_length": "1389",
            "format": "radishaxiom-checker-build-provenance",
            "format_version": "0.1",
            "kind": "known-digest",
            "raw_sha256": "sha256:7916666ae8f2883f5787a58307253416a653f8aca69e1cd1babc8f22639a38e0",
        },
        "registration": {
            "reasons": [
                "acceptance-bytes-not-retained",
                "artifact-bytes-not-retained",
                "checker-source-not-current",
                "provenance-bytes-not-retained",
            ],
            "status": "historical-ineligible",
        },
        "retention": {
            "acceptance_bytes": "not-retained",
            "artifact_bytes": "not-retained",
            "fetch": {
                "kind": "unavailable",
                "reason": "ephemeral build and acceptance outputs were deleted after identities were recorded",
            },
            "provenance_bytes": "not-retained",
        },
        "reverification": {
            "required_inputs": [
                "acceptance-bytes",
                "artifact-bytes",
                "current-source-match",
                "provenance-bytes",
            ],
            "status": "blocked-missing-bytes-and-source-mismatch",
        },
    }
    return record(body)


def pending_record() -> dict[str, Any]:
    body = {
        **common("checker-go0.1-dev-darwin-arm64-current-pending-2026-08-29", CURRENT_SOURCE),
        "acceptance": {"kind": "not-produced"},
        "artifact": {"kind": "not-produced"},
        "build_provenance": {"kind": "not-produced"},
        "registration": {
            "reasons": [
                "acceptance-not-produced",
                "artifact-not-produced",
                "candidate-archive-not-produced",
                "provenance-not-produced",
            ],
            "status": "awaiting-controlled-build-and-acceptance",
        },
        "retention": {
            "acceptance_bytes": "not-produced",
            "artifact_bytes": "not-produced",
            "candidate_archive_bytes": "not-produced",
            "fetch": {
                "kind": "unavailable",
                "reason": "no current-source candidate has been built or accepted",
            },
            "provenance_bytes": "not-produced",
        },
        "reverification": {
            "required_inputs": [
                "accepted-current-source-candidate",
                "retained-or-fetchable-acceptance-bytes",
                "retained-or-fetchable-artifact-bytes",
                "retained-or-fetchable-candidate-archive",
                "retained-or-fetchable-provenance-bytes",
            ],
            "status": "awaiting-controlled-build-and-acceptance",
        },
    }
    return record(body)


def require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{label} is not a sha256 identity")


def validate_record(value: dict[str, Any]) -> None:
    expected = historical_record() if value.get("id") == historical_record()["id"] else pending_record()
    if value.get("id") not in {historical_record()["id"], pending_record()["id"]}:
        raise ValueError("unknown runtime payload record id")
    if set(value) != set(expected):
        raise ValueError("runtime payload record members drifted")
    body = {key: item for key, item in value.items() if key != "record_digest"}
    if value.get("record_digest") != domain_digest(RECORD_DOMAIN, body):
        raise ValueError("runtime payload record digest mismatch")
    require_digest(value["checker"]["source"]["identity"], "checker source")
    if canonical_bytes(value) != canonical_bytes(expected):
        raise ValueError("runtime payload record exceeds or drifts from recorded facts")


def infer_schema(values: list[Any], key: str = "") -> dict[str, Any]:
    if values and all(isinstance(value, dict) for value in values):
        dictionaries = values
        all_keys = sorted(set().union(*(value.keys() for value in dictionaries)))
        required = sorted(set.intersection(*(set(value) for value in dictionaries)))
        return {
            "additionalProperties": False,
            "properties": {
                child: infer_schema([value[child] for value in dictionaries if child in value], child)
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
        if all(SHA256_PATTERN.fullmatch(value) for value in values):
            return {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"}
        if all(re.fullmatch(r"0|[1-9][0-9]*", value) for value in values):
            return {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"}
        return {"type": "string"}
    raise ValueError(f"cannot infer schema for {key}")


def schema(records: list[dict[str, Any]]) -> dict[str, Any]:
    variants = []
    for value in records:
        variant = infer_schema([value])
        variant["properties"]["format"] = {"const": FORMAT}
        variant["properties"]["format_version"] = {"const": FORMAT_VERSION}
        variant["properties"]["digest_domain"] = {"const": RECORD_DOMAIN}
        variant["properties"]["id"] = {"const": value["id"]}
        variant["properties"]["registration"]["properties"]["status"] = {
            "const": value["registration"]["status"]
        }
        variant["properties"]["artifact"]["properties"]["kind"] = {
            "const": value["artifact"]["kind"]
        }
        variant["properties"]["build_provenance"]["properties"]["kind"] = {
            "const": value["build_provenance"]["kind"]
        }
        variant["properties"]["acceptance"]["properties"]["kind"] = {
            "const": value["acceptance"]["kind"]
        }
        variants.append(variant)
    return {
        "$id": "https://radishaxiom.dev/schema/checker-runtime-payload-registration/0.1",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "oneOf": variants,
        "title": "RadishAxiom checker runtime payload registration v0.1",
    }


def refreshed(value: dict[str, Any]) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key != "record_digest"}
    value["record_digest"] = domain_digest(RECORD_DOMAIN, body)
    return value


def negative_fixtures(historical: dict[str, Any], pending: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    value = copy.deepcopy(historical)
    value["checker"]["source"] = copy.deepcopy(CURRENT_SOURCE)
    rows.append(("historical-artifact-current-source.invalid.json", "historical artifact cannot be rebound to current source", refreshed(value)))
    value = copy.deepcopy(historical)
    value["retention"]["artifact_bytes"] = "retained"
    rows.append(("missing-artifact-retention-overclaim.invalid.json", "deleted artifact bytes cannot be claimed as retained", refreshed(value)))
    value = copy.deepcopy(historical)
    value["registration"]["status"] = "registered"
    rows.append(("historical-payload-registered.invalid.json", "source-mismatched unavailable payload cannot be registered", refreshed(value)))
    value = copy.deepcopy(historical)
    value["acceptance"]["excluded_scope"].remove("installation")
    rows.append(("installation-exclusion-missing.invalid.json", "acceptance cannot be expanded to installation", refreshed(value)))
    value = copy.deepcopy(pending)
    value["artifact"] = copy.deepcopy(historical["artifact"])
    rows.append(("pending-artifact-without-provenance.invalid.json", "artifact digest alone cannot complete current-source registration", refreshed(value)))
    value = copy.deepcopy(pending)
    value["unexpected"] = "member"
    rows.append(("unknown-member.invalid.json", "closed registration rejects unknown members", refreshed(value)))
    return rows


def build_contract(records: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    rows = []
    for path, value in records:
        rows.append({
            "id": value["id"],
            "path": path,
            "raw_sha256": sha256_bytes(pretty_bytes(value)),
            "record_digest": value["record_digest"],
            "registration_status": value["registration"]["status"],
            "source": value["checker"]["source"]["identity"],
        })
    body = {
        "counts": {"active": "0", "historical_ineligible": "1", "pending": "1", "records": "2"},
        "current_checker_source": CURRENT_SOURCE,
        "digest_domain": SET_DOMAIN,
        "format": SET_FORMAT,
        "format_version": FORMAT_VERSION,
        "generator": {"path": "scripts/generate-checker-runtime-payloads.py", "raw_sha256": raw_sha256(Path(__file__))},
        "records": rows,
        "runtime_statement": "no-current-source-runtime-payload-is-registered",
        "storage_policy": STORAGE_POLICY,
    }
    return {**body, "contract_digest": domain_digest(SET_DOMAIN, body)}


def outputs() -> dict[Path, bytes]:
    historical = historical_record()
    pending = pending_record()
    records = [
        ("contracts/checker-runtime-payloads-v0.1/records/checker-go0.1-dev-darwin-arm64-historical.json", historical),
        ("contracts/checker-runtime-payloads-v0.1/records/checker-go0.1-dev-darwin-arm64-current-pending.json", pending),
    ]
    for _, value in records:
        validate_record(value)
    expected = {REPO_ROOT / path: pretty_bytes(value) for path, value in records}
    expected[CONTRACT_ROOT / "contract.json"] = pretty_bytes(build_contract(records))
    expected[CONTRACT_ROOT / "schemas/checker-runtime-payload-registration.schema.json"] = pretty_bytes(schema([historical, pending]))
    negative_rows = []
    for filename, reason, value in negative_fixtures(historical, pending):
        try:
            validate_record(value)
        except ValueError:
            pass
        else:
            raise ValueError(f"negative fixture was accepted: {filename}")
        expected[CONTRACT_ROOT / "fixtures/negative" / filename] = pretty_bytes(value)
        negative_rows.append({"file": filename, "reason": reason})
    expected[CONTRACT_ROOT / "fixtures/negative/expected.json"] = pretty_bytes({
        "fixtures": negative_rows,
        "format": "radishaxiom-checker-runtime-payload-negative-set",
        "format_version": FORMAT_VERSION,
    })
    return expected


def write_outputs(expected: dict[Path, bytes]) -> None:
    for path, data in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"wrote checker runtime payload registrations ({len(expected)} generated files)")


def check_outputs(expected: dict[Path, bytes]) -> int:
    errors = []
    for path, data in expected.items():
        if not path.is_file():
            errors.append(f"missing generated file: {path.relative_to(REPO_ROOT)}")
        elif path.read_bytes() != data:
            errors.append(f"generated file drifted: {path.relative_to(REPO_ROOT)}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"checker runtime payload registrations passed ({len(expected)} generated files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        expected = outputs()
        if args.write:
            write_outputs(expected)
            return 0
        return check_outputs(expected)
    except (KeyError, OSError, UnicodeError, ValueError) as error:
        print(f"checker runtime payload registration failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
