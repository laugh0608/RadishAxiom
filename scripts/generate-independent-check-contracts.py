#!/usr/bin/env python3
"""Generate the independent checker exchange contracts and fixtures.

This is a contract-specific fixture builder, not an Evidence checker, JSON Schema
implementation, or production artifact resolver.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = REPO_ROOT / "contracts/independent-check-v0.1"
CONTRACT_VERSION = "0.1"
PROFILE_NAME = "keyed-finite-table-independent-check"
PROFILE_VERSION = "0.1"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CANONICAL_UINT_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
POSITIVE_UINT_PATTERN = re.compile(r"^[1-9][0-9]*$")
STABLE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

TRUST_CATEGORIES = (
    "cryptographic-primitive",
    "decoder-normalizer",
    "host-runtime",
    "input-origin",
    "production-generator",
    "proof-backend",
    "sensitivity-classification",
    "specification-intent",
)

LIMITS = (
    ("artifact-bytes", "byte", "1048576"),
    ("bundle-bytes", "byte", "4194304"),
    ("collection-items", "item", "10000"),
    ("json-depth", "level", "128"),
    ("semantic-steps", "step", "1000000"),
    ("wall-clock", "millisecond", "5000"),
    ("working-memory", "byte", "67108864"),
)

CHECK_KINDS = (
    "conclusion-recompute",
    "concrete-check-replay",
    "counterexample-replay",
    "identity",
    "isolation-report",
    "obligation-reconstruction",
    "proof-support",
    "state-support",
    "strict-parse",
    "subject",
)

CHECK_OUTCOMES = ("incomplete", "passed", "rejected", "trusted")
REFERENCE_KINDS = (
    "artifact",
    "check",
    "evidence-entry",
    "obligation",
    "request",
    "tool",
    "trust",
)

TCB_CATEGORIES = (
    "canonicalization",
    "certificate-checker",
    "checker-core",
    "cryptographic-primitive",
    "rule-interpreter",
)

REQUIRED_TCB_CATEGORIES = (
    "canonicalization",
    "checker-core",
    "cryptographic-primitive",
    "rule-interpreter",
)

CHECK_CODE_REGISTRY = {
    "conclusion-recompute": (
        "conclusion-mismatch",
        "result-aggregation",
    ),
    "concrete-check-replay": (
        "concrete-check-mismatch",
        "host-output-mismatch",
    ),
    "counterexample-replay": (
        "counterexample-invalid",
        "minimality-unsupported",
    ),
    "identity": (
        "artifact-missing",
        "check-id-mismatch",
        "digest-mismatch",
        "duplicate-artifact",
        "evidence-cardinality",
        "length-mismatch",
        "manifest-coverage",
        "request-binding-mismatch",
    ),
    "isolation-report": (
        "checker-identity",
        "isolation-boundary-violation",
        "tcb-incomplete",
    ),
    "obligation-reconstruction": (
        "obligation-mismatch",
    ),
    "proof-support": (
        "attestation-not-allowed",
        "certificate-incomplete",
        "proof-support-mismatch",
        "proof-support-unsupported",
    ),
    "state-support": (
        "invalid-state-support",
        "trust-not-allowed",
    ),
    "strict-parse": (
        "duplicate-member",
        "evidence-missing-required-members",
        "invalid-json",
        "invalid-utf8",
        "json-number-or-null",
        "limit-set-mismatch",
        "missing-required-member",
        "noncanonical-json",
        "noncanonical-order",
        "unknown-member",
        "unknown-tag",
        "unsupported-version",
    ),
    "subject": (
        "invalid-ir",
        "subject-mismatch",
    ),
}

Json = dict[str, Any] | list[Any] | str | bool


class ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def validate_protocol_json(value: Json, path: str = "$") -> None:
    if type(value) is bool or isinstance(value, str):
        if isinstance(value, str) and not value.isascii():
            raise ContractError("invalid-utf8", f"fixture must stay ASCII: {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_protocol_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise ContractError("invalid-utf8", f"member must stay ASCII: {path}")
            validate_protocol_json(item, f"{path}.{key}")
        return
    raise ContractError("json-number-or-null", path)


def canonical_bytes(value: Json) -> bytes:
    validate_protocol_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_id(domain: str, value: Json) -> str:
    return raw_digest(domain.encode("utf-8") + b"\0" + canonical_bytes(value))


def file_ref(path: str, data: bytes) -> dict[str, str]:
    return {
        "byte_length": str(len(data)),
        "path": path,
        "sha256": raw_digest(data),
    }


def require_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("unknown-tag", "expected object")
    return value


def require_array(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError("unknown-tag", "expected array")
    return value


def require_keys(value: dict[str, Any], expected: set[str]) -> None:
    unknown = sorted(set(value) - expected)
    if unknown:
        raise ContractError("unknown-member", unknown[0])
    missing = sorted(expected - set(value))
    if missing:
        raise ContractError("missing-required-member", missing[0])


def require_digest(value: Any) -> str:
    if not isinstance(value, str) or not DIGEST_PATTERN.fullmatch(value):
        raise ContractError("digest-mismatch")
    return value


def require_sorted_unique(values: list[Any], code: str = "noncanonical-order") -> None:
    if values != sorted(values) or len(values) != len(set(values)):
        raise ContractError(code)


def no_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate-member", key)
        result[key] = value
    return result


def strict_parse(data: bytes) -> Json:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("invalid-utf8", str(exc)) from exc
    try:
        value = json.loads(text, object_pairs_hook=no_duplicate_members)
    except ContractError:
        raise
    except json.JSONDecodeError as exc:
        raise ContractError("invalid-json", str(exc)) from exc
    validate_protocol_json(value)
    if canonical_bytes(value) != data:
        raise ContractError("noncanonical-json")
    return value


def validate_request(value: Json) -> None:
    request = require_object(value)
    require_keys(
        request,
        {
            "assurance_policy",
            "bundle_manifest",
            "checker_profile",
            "evidence",
            "limits",
            "request_version",
        },
    )
    if request["request_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported-version")
    require_digest(request["bundle_manifest"])
    require_digest(request["evidence"])

    profile = require_object(request["checker_profile"])
    require_keys(profile, {"name", "version"})
    if profile != {"name": PROFILE_NAME, "version": PROFILE_VERSION}:
        raise ContractError("unsupported-version")

    policy = require_object(request["assurance_policy"])
    require_keys(policy, {"allowed_trust_categories", "proof_support"})
    if policy["proof_support"] not in {
        "attestation-allowed",
        "certificate-required",
    }:
        raise ContractError("unknown-tag")
    trust = require_array(policy["allowed_trust_categories"])
    if any(item not in TRUST_CATEGORIES for item in trust):
        raise ContractError("unknown-tag")
    require_sorted_unique(trust)

    limits = require_array(request["limits"])
    if len(limits) != len(LIMITS):
        raise ContractError("limit-set-mismatch")
    for actual, expected in zip(limits, LIMITS, strict=True):
        item = require_object(actual)
        require_keys(item, {"name", "unit", "value"})
        if (item["name"], item["unit"]) != expected[:2]:
            raise ContractError("limit-set-mismatch")
        if not isinstance(item["value"], str) or not POSITIVE_UINT_PATTERN.fullmatch(
            item["value"]
        ):
            raise ContractError("limit-set-mismatch")


def validate_manifest(value: Json) -> None:
    manifest = require_object(value)
    require_keys(manifest, {"artifacts", "bundle_version"})
    if manifest["bundle_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported-version")
    artifacts = require_array(manifest["artifacts"])
    if not artifacts:
        raise ContractError("evidence-cardinality")

    digests: list[str] = []
    evidence_count = 0
    for raw_item in artifacts:
        item = require_object(raw_item)
        require_keys(
            item,
            {"byte_length", "content_digest", "format", "format_version", "roles"},
        )
        if not isinstance(item["byte_length"], str) or not CANONICAL_UINT_PATTERN.fullmatch(
            item["byte_length"]
        ):
            raise ContractError("length-mismatch")
        digests.append(require_digest(item["content_digest"]))
        if not isinstance(item["format"], str) or not STABLE_CODE_PATTERN.fullmatch(
            item["format"]
        ):
            raise ContractError("unknown-tag")
        if not isinstance(item["format_version"], str) or not item["format_version"]:
            raise ContractError("unsupported-version")
        roles = require_array(item["roles"])
        if not roles or any(
            role
            not in {"evidence", "evidence-artifact", "normative-spec", "subject"}
            for role in roles
        ):
            raise ContractError("unknown-tag")
        require_sorted_unique(roles)
        evidence_count += roles.count("evidence")

    if len(digests) != len(set(digests)):
        raise ContractError("duplicate-artifact")
    if digests != sorted(digests):
        raise ContractError("noncanonical-order")
    if evidence_count != 1:
        raise ContractError("evidence-cardinality")


def validate_binding(value: Any) -> str:
    binding = require_object(value)
    require_keys(binding, {"content_digest", "document_digest"})
    require_digest(binding["content_digest"])
    document = require_object(binding["document_digest"])
    if document.get("kind") == "available":
        require_keys(document, {"kind", "value"})
        require_digest(document["value"])
        return "available"
    if document.get("kind") == "unavailable":
        require_keys(document, {"kind"})
        return "unavailable"
    raise ContractError("unknown-tag")


def validate_refs(value: Any) -> list[dict[str, str]]:
    refs = require_array(value)
    normalized: list[tuple[str, str]] = []
    for raw_ref in refs:
        ref = require_object(raw_ref)
        require_keys(ref, {"kind", "ref"})
        if ref["kind"] not in REFERENCE_KINDS:
            raise ContractError("unknown-tag")
        normalized.append((ref["kind"], require_digest(ref["ref"])))
    if normalized != sorted(normalized) or len(normalized) != len(set(normalized)):
        raise ContractError("noncanonical-order")
    return refs


def validate_result(value: Json) -> None:
    document = require_object(value)
    require_keys(
        document,
        {
            "checker",
            "checks",
            "evidence",
            "missing_artifacts",
            "remaining_trust",
            "request",
            "result",
            "result_version",
            "tcb",
        },
    )
    if document["result_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported-version")

    checker = require_object(document["checker"])
    require_keys(checker, {"artifact", "name", "source", "toolchain", "version"})
    require_digest(checker["artifact"])
    require_digest(checker["source"])
    if (
        checker["name"] != "radishaxiom-independent-checker-go"
        or checker["toolchain"] != "go1.26.7"
        or not isinstance(checker["version"], str)
        or not checker["version"]
        or checker["version"] == "latest"
    ):
        raise ContractError("checker-identity")

    evidence_availability = validate_binding(document["evidence"])
    request_availability = validate_binding(document["request"])

    missing = require_array(document["missing_artifacts"])
    for digest in missing:
        require_digest(digest)
    require_sorted_unique(missing)
    trust = require_array(document["remaining_trust"])
    for trust_id in trust:
        require_digest(trust_id)
    require_sorted_unique(trust)

    checks = require_array(document["checks"])
    if not checks:
        raise ContractError("missing-required-member", "checks")
    check_ids: list[str] = []
    check_outcomes: dict[str, str] = {}
    for raw_check in checks:
        check = require_object(raw_check)
        require_keys(check, {"definition", "id"})
        definition = require_object(check["definition"])
        require_keys(definition, {"codes", "kind", "outcome", "refs"})
        kind = definition["kind"]
        outcome = definition["outcome"]
        if kind not in CHECK_KINDS or outcome not in CHECK_OUTCOMES:
            raise ContractError("unknown-tag")
        codes = require_array(definition["codes"])
        if not codes or any(
            not isinstance(code, str)
            or code not in CHECK_CODE_REGISTRY[kind]
            for code in codes
        ):
            raise ContractError("unknown-tag")
        require_sorted_unique(codes)
        validate_refs(definition["refs"])
        expected_id = content_id("axiom-independent-check-v0.1:check", definition)
        if check["id"] != expected_id:
            raise ContractError("check-id-mismatch")
        check_ids.append(expected_id)
        check_outcomes[expected_id] = outcome
    require_sorted_unique(check_ids)

    tcb = require_array(document["tcb"])
    tcb_keys: list[tuple[str, str]] = []
    tcb_categories: set[str] = set()
    for raw_item in tcb:
        item = require_object(raw_item)
        require_keys(item, {"artifact", "category", "version"})
        if item["category"] not in TCB_CATEGORIES:
            raise ContractError("unknown-tag")
        artifact = require_digest(item["artifact"])
        if not isinstance(item["version"], str) or not item["version"]:
            raise ContractError("unsupported-version")
        tcb_keys.append((item["category"], artifact))
        tcb_categories.add(item["category"])
    if tcb_keys != sorted(tcb_keys) or len(tcb_keys) != len(set(tcb_keys)):
        raise ContractError("noncanonical-order")
    if not set(REQUIRED_TCB_CATEGORIES).issubset(tcb_categories):
        raise ContractError("tcb-incomplete")

    result = require_object(document["result"])
    kind = result.get("kind")
    if kind == "accepted":
        require_keys(result, {"kind"})
        result_refs: list[str] = []
    elif kind in {"accepted-with-trust", "incomplete", "rejected"}:
        require_keys(result, {"kind", "refs"})
        result_refs = require_array(result["refs"])
        if not result_refs:
            raise ContractError("result-aggregation")
        for ref in result_refs:
            require_digest(ref)
        require_sorted_unique(result_refs)
        if any(ref not in check_outcomes for ref in result_refs):
            raise ContractError("result-aggregation")
    else:
        raise ContractError("unknown-tag")

    if kind != "rejected" and (
        evidence_availability != "available" or request_availability != "available"
    ):
        raise ContractError("result-aggregation")
    if kind == "accepted" and (
        missing or trust or any(outcome != "passed" for outcome in check_outcomes.values())
    ):
        raise ContractError("result-aggregation")
    if kind == "accepted-with-trust" and (
        missing
        or not trust
        or any(outcome in {"incomplete", "rejected"} for outcome in check_outcomes.values())
    ):
        raise ContractError("result-aggregation")
    if kind == "incomplete" and not (
        missing or any(outcome == "incomplete" for outcome in check_outcomes.values())
    ):
        raise ContractError("result-aggregation")
    if kind == "rejected" and not any(
        check_outcomes.get(ref) == "rejected" for ref in result_refs
    ):
        raise ContractError("result-aggregation")


def digest_schema() -> dict[str, Any]:
    return {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"}


def closed_object(
    properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "additionalProperties": False,
        "properties": properties,
        "required": required or list(properties),
        "type": "object",
    }


def request_schema() -> dict[str, Any]:
    limit_items = []
    for name, unit, _ in LIMITS:
        limit_items.append(
            closed_object(
                {
                    "name": {"const": name},
                    "unit": {"const": unit},
                    "value": {"pattern": "^[1-9][0-9]*$", "type": "string"},
                }
            )
        )
    return {
        "$id": "urn:radishaxiom:schema:axiom-check-request:0.1",
        "$schema": SCHEMA_DIALECT,
        "additionalProperties": False,
        "properties": {
            "assurance_policy": closed_object(
                {
                    "allowed_trust_categories": {
                        "items": {"enum": list(TRUST_CATEGORIES)},
                        "type": "array",
                        "uniqueItems": True,
                    },
                    "proof_support": {
                        "enum": ["attestation-allowed", "certificate-required"]
                    },
                }
            ),
            "bundle_manifest": {"$ref": "#/$defs/digest"},
            "checker_profile": closed_object(
                {
                    "name": {"const": PROFILE_NAME},
                    "version": {"const": PROFILE_VERSION},
                }
            ),
            "evidence": {"$ref": "#/$defs/digest"},
            "limits": {
                "items": False,
                "maxItems": len(LIMITS),
                "minItems": len(LIMITS),
                "prefixItems": limit_items,
                "type": "array",
            },
            "request_version": {"const": CONTRACT_VERSION},
        },
        "required": [
            "assurance_policy",
            "bundle_manifest",
            "checker_profile",
            "evidence",
            "limits",
            "request_version",
        ],
        "title": "Axiom Check Request v0.1",
        "type": "object",
        "$defs": {"digest": digest_schema()},
    }


def manifest_schema() -> dict[str, Any]:
    descriptor = closed_object(
        {
            "byte_length": {
                "pattern": "^(0|[1-9][0-9]*)$",
                "type": "string",
            },
            "content_digest": {"$ref": "#/$defs/digest"},
            "format": {"pattern": "^[a-z][a-z0-9-]*$", "type": "string"},
            "format_version": {"minLength": 1, "type": "string"},
            "roles": {
                "items": {
                    "enum": [
                        "evidence",
                        "evidence-artifact",
                        "normative-spec",
                        "subject",
                    ]
                },
                "minItems": 1,
                "type": "array",
                "uniqueItems": True,
            },
        }
    )
    return {
        "$id": "urn:radishaxiom:schema:axiom-check-bundle-manifest:0.1",
        "$schema": SCHEMA_DIALECT,
        "$defs": {"digest": digest_schema()},
        "additionalProperties": False,
        "properties": {
            "artifacts": {
                "items": descriptor,
                "minItems": 1,
                "type": "array",
                "uniqueItems": True,
            },
            "bundle_version": {"const": CONTRACT_VERSION},
        },
        "required": ["artifacts", "bundle_version"],
        "title": "Axiom Check Bundle Manifest v0.1",
        "type": "object",
    }


def result_schema() -> dict[str, Any]:
    document_digest = {
        "oneOf": [
            closed_object(
                {
                    "kind": {"const": "available"},
                    "value": {"$ref": "#/$defs/digest"},
                }
            ),
            closed_object({"kind": {"const": "unavailable"}}),
        ]
    }
    binding = closed_object(
        {
            "content_digest": {"$ref": "#/$defs/digest"},
            "document_digest": document_digest,
        }
    )
    ref = closed_object(
        {
            "kind": {"enum": list(REFERENCE_KINDS)},
            "ref": {"$ref": "#/$defs/digest"},
        }
    )
    check_definition = closed_object(
        {
            "codes": {
                "items": {
                    "pattern": "^[a-z][a-z0-9-]*$",
                    "type": "string",
                },
                "minItems": 1,
                "type": "array",
                "uniqueItems": True,
            },
            "kind": {"enum": list(CHECK_KINDS)},
            "outcome": {"enum": list(CHECK_OUTCOMES)},
            "refs": {"items": ref, "type": "array", "uniqueItems": True},
        }
    )
    check = closed_object(
        {
            "definition": check_definition,
            "id": {"$ref": "#/$defs/digest"},
        }
    )
    result_variant = {
        "oneOf": [
            closed_object({"kind": {"const": "accepted"}}),
            *[
                closed_object(
                    {
                        "kind": {"const": kind},
                        "refs": {
                            "items": {"$ref": "#/$defs/digest"},
                            "minItems": 1,
                            "type": "array",
                            "uniqueItems": True,
                        },
                    }
                )
                for kind in ("accepted-with-trust", "incomplete", "rejected")
            ],
        ]
    }
    return {
        "$id": "urn:radishaxiom:schema:axiom-independent-check-result:0.1",
        "$schema": SCHEMA_DIALECT,
        "$defs": {"digest": digest_schema()},
        "additionalProperties": False,
        "properties": {
            "checker": closed_object(
                {
                    "artifact": {"$ref": "#/$defs/digest"},
                    "name": {"const": "radishaxiom-independent-checker-go"},
                    "source": {"$ref": "#/$defs/digest"},
                    "toolchain": {"const": "go1.26.7"},
                    "version": {"minLength": 1, "not": {"const": "latest"}, "type": "string"},
                }
            ),
            "checks": {
                "items": check,
                "minItems": 1,
                "type": "array",
                "uniqueItems": True,
            },
            "evidence": binding,
            "missing_artifacts": {
                "items": {"$ref": "#/$defs/digest"},
                "type": "array",
                "uniqueItems": True,
            },
            "remaining_trust": {
                "items": {"$ref": "#/$defs/digest"},
                "type": "array",
                "uniqueItems": True,
            },
            "request": binding,
            "result": result_variant,
            "result_version": {"const": CONTRACT_VERSION},
            "tcb": {
                "items": closed_object(
                    {
                        "artifact": {"$ref": "#/$defs/digest"},
                        "category": {"enum": list(TCB_CATEGORIES)},
                        "version": {"minLength": 1, "type": "string"},
                    }
                ),
                "minItems": len(REQUIRED_TCB_CATEGORIES),
                "type": "array",
                "uniqueItems": True,
            },
        },
        "required": [
            "checker",
            "checks",
            "evidence",
            "missing_artifacts",
            "remaining_trust",
            "request",
            "result",
            "result_version",
            "tcb",
        ],
        "title": "Axiom Independent Check Result v0.1",
        "type": "object",
    }


def base_request(evidence_digest: str, manifest_digest: str) -> dict[str, Any]:
    return {
        "assurance_policy": {
            "allowed_trust_categories": [],
            "proof_support": "certificate-required",
        },
        "bundle_manifest": manifest_digest,
        "checker_profile": {"name": PROFILE_NAME, "version": PROFILE_VERSION},
        "evidence": evidence_digest,
        "limits": [
            {"name": name, "unit": unit, "value": value}
            for name, unit, value in LIMITS
        ],
        "request_version": CONTRACT_VERSION,
    }


def build_rejection_fixture() -> tuple[dict[str, bytes], dict[str, Any]]:
    fixture_root = "fixtures/strict-evidence-rejection"
    evidence_bytes = b"{}"
    evidence_digest = raw_digest(evidence_bytes)
    blob_path = f"{fixture_root}/blobs/sha256/{evidence_digest.removeprefix('sha256:')}"

    manifest = {
        "artifacts": [
            {
                "byte_length": str(len(evidence_bytes)),
                "content_digest": evidence_digest,
                "format": "axiom-evidence",
                "format_version": "0.1",
                "roles": ["evidence"],
            }
        ],
        "bundle_version": CONTRACT_VERSION,
    }
    manifest_bytes = canonical_bytes(manifest)
    request = base_request(evidence_digest, raw_digest(manifest_bytes))
    request_bytes = canonical_bytes(request)

    check_definition = {
        "codes": ["evidence-missing-required-members"],
        "kind": "strict-parse",
        "outcome": "rejected",
        "refs": [{"kind": "artifact", "ref": evidence_digest}],
    }
    check_id = content_id("axiom-independent-check-v0.1:check", check_definition)
    checker_artifact = raw_digest(
        b"radishaxiom-independent-checker-go:synthetic-v0.0-test"
    )
    checker_source = raw_digest(
        b"radishaxiom-independent-checker-go:synthetic-source-v0.0-test"
    )
    result = {
        "checker": {
            "artifact": checker_artifact,
            "name": "radishaxiom-independent-checker-go",
            "source": checker_source,
            "toolchain": "go1.26.7",
            "version": "0.0-test",
        },
        "checks": [{"definition": check_definition, "id": check_id}],
        "evidence": {
            "content_digest": evidence_digest,
            "document_digest": {"kind": "unavailable"},
        },
        "missing_artifacts": [],
        "remaining_trust": [],
        "request": {
            "content_digest": raw_digest(request_bytes),
            "document_digest": {
                "kind": "available",
                "value": content_id(
                    "axiom-independent-check-v0.1:request", request
                ),
            },
        },
        "result": {"kind": "rejected", "refs": [check_id]},
        "result_version": CONTRACT_VERSION,
        "tcb": [
            {
                "artifact": checker_artifact,
                "category": category,
                "version": "0.0-test",
            }
            for category in REQUIRED_TCB_CATEGORIES
        ],
    }
    result_bytes = canonical_bytes(result)

    strict_request = strict_parse(request_bytes)
    strict_manifest = strict_parse(manifest_bytes)
    strict_result = strict_parse(result_bytes)
    validate_request(strict_request)
    validate_manifest(strict_manifest)
    validate_result(strict_result)
    if request["bundle_manifest"] != raw_digest(manifest_bytes):
        raise ValueError("request does not bind manifest bytes")
    if request["evidence"] != raw_digest(evidence_bytes):
        raise ValueError("request does not bind Evidence bytes")

    generated = {
        f"{fixture_root}/expected-result.jcs": result_bytes,
        f"{fixture_root}/manifest.jcs": manifest_bytes,
        f"{fixture_root}/request.jcs": request_bytes,
        blob_path: evidence_bytes,
    }
    metadata = {
        "evidence_content_digest": evidence_digest,
        "expected_check_id": check_id,
        "expected_result_document_digest": content_id(
            "axiom-independent-check-v0.1:result", result
        ),
        "files": [file_ref(path, data) for path, data in sorted(generated.items())],
        "fixture_id": "strict-evidence-rejection",
        "request_document_digest": content_id(
            "axiom-independent-check-v0.1:request", request
        ),
    }
    return generated, metadata


def validate_negative(
    data: bytes,
    validator: Callable[[Json], None],
    expected_code: str,
) -> None:
    try:
        value = strict_parse(data)
        validator(value)
    except ContractError as exc:
        if exc.code != expected_code:
            raise ValueError(
                f"negative fixture expected {expected_code}, got {exc.code}"
            ) from exc
        return
    raise ValueError(f"negative fixture unexpectedly accepted; wanted {expected_code}")


def build_negative_fixtures(
    request: dict[str, Any],
    manifest: dict[str, Any],
    result: dict[str, Any],
) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    cases: list[tuple[str, str, bytes, Callable[[Json], None], str]] = []

    def add(
        case_id: str,
        target: str,
        value: Json,
        validator: Callable[[Json], None],
        code: str,
    ) -> None:
        cases.append((case_id, target, canonical_bytes(value), validator, code))

    request_unknown = copy.deepcopy(request)
    request_unknown["unexpected"] = True
    add("request-unknown-member", "request", request_unknown, validate_request, "unknown-member")

    request_version = copy.deepcopy(request)
    request_version["request_version"] = "0.2"
    add("request-unknown-version", "request", request_version, validate_request, "unsupported-version")

    duplicate_request = canonical_bytes(request).replace(
        b'"request_version":"0.1"}',
        b'"request_version":"0.1","request_version":"0.1"}',
    )
    cases.append(
        (
            "request-duplicate-member",
            "request",
            duplicate_request,
            validate_request,
            "duplicate-member",
        )
    )
    cases.append(
        (
            "request-noncanonical-whitespace",
            "request",
            b" " + canonical_bytes(request),
            validate_request,
            "noncanonical-json",
        )
    )

    request_limits = copy.deepcopy(request)
    request_limits["limits"] = request_limits["limits"][:-1]
    add("request-missing-limit", "request", request_limits, validate_request, "limit-set-mismatch")

    request_proof = copy.deepcopy(request)
    request_proof["assurance_policy"]["proof_support"] = "automatic"
    add("request-unknown-proof-support", "request", request_proof, validate_request, "unknown-tag")

    request_trust = copy.deepcopy(request)
    request_trust["assurance_policy"]["allowed_trust_categories"] = [
        "proof-backend",
        "decoder-normalizer",
    ]
    add("request-unsorted-trust", "request", request_trust, validate_request, "noncanonical-order")

    manifest_duplicate = copy.deepcopy(manifest)
    manifest_duplicate["artifacts"].append(copy.deepcopy(manifest_duplicate["artifacts"][0]))
    add("manifest-duplicate-artifact", "bundle-manifest", manifest_duplicate, validate_manifest, "duplicate-artifact")

    manifest_role = copy.deepcopy(manifest)
    manifest_role["artifacts"][0]["roles"] = ["network-fallback"]
    add("manifest-unknown-role", "bundle-manifest", manifest_role, validate_manifest, "unknown-tag")

    second_artifact = {
        "byte_length": "1",
        "content_digest": raw_digest(b"x"),
        "format": "axiom-ir",
        "format_version": "0.1",
        "roles": ["subject"],
    }
    manifest_unsorted = copy.deepcopy(manifest)
    manifest_unsorted["artifacts"].append(second_artifact)
    manifest_unsorted["artifacts"] = list(
        reversed(
            sorted(
                manifest_unsorted["artifacts"],
                key=lambda item: item["content_digest"],
            )
        )
    )
    add("manifest-unsorted-artifacts", "bundle-manifest", manifest_unsorted, validate_manifest, "noncanonical-order")

    manifest_evidence = copy.deepcopy(manifest)
    second_evidence = copy.deepcopy(second_artifact)
    second_evidence["roles"] = ["evidence"]
    manifest_evidence["artifacts"].append(second_evidence)
    manifest_evidence["artifacts"] = sorted(
        manifest_evidence["artifacts"], key=lambda item: item["content_digest"]
    )
    add("manifest-two-evidence", "bundle-manifest", manifest_evidence, validate_manifest, "evidence-cardinality")

    result_trust = copy.deepcopy(result)
    result_trust["remaining_trust"] = [raw_digest(b"remaining-trust")]
    result_trust["result"] = {"kind": "accepted"}
    add("result-accepted-with-trust", "result", result_trust, validate_result, "result-aggregation")

    result_empty_trust = copy.deepcopy(result)
    result_empty_trust["result"] = {
        "kind": "accepted-with-trust",
        "refs": [result_empty_trust["checks"][0]["id"]],
    }
    add("result-trusted-without-trust", "result", result_empty_trust, validate_result, "result-aggregation")

    result_incomplete = copy.deepcopy(result)
    result_incomplete["result"] = {"kind": "incomplete", "refs": []}
    add("result-incomplete-without-refs", "result", result_incomplete, validate_result, "result-aggregation")

    result_unavailable = copy.deepcopy(result)
    result_unavailable["result"] = {"kind": "accepted"}
    add("result-accepted-unavailable-document", "result", result_unavailable, validate_result, "result-aggregation")

    result_check_id = copy.deepcopy(result)
    result_check_id["checks"][0]["id"] = raw_digest(b"wrong-check-id")
    result_check_id["result"]["refs"] = [result_check_id["checks"][0]["id"]]
    add("result-check-id-mismatch", "result", result_check_id, validate_result, "check-id-mismatch")

    result_checker = copy.deepcopy(result)
    result_checker["checker"]["name"] = "raxc"
    add("result-production-checker-name", "result", result_checker, validate_result, "checker-identity")

    result_tcb = copy.deepcopy(result)
    result_tcb["tcb"] = list(reversed(result_tcb["tcb"]))
    add("result-unsorted-tcb", "result", result_tcb, validate_result, "noncanonical-order")

    generated: dict[str, bytes] = {}
    expected: list[dict[str, str]] = []
    for case_id, target, data, validator, code in cases:
        validate_negative(data, validator, code)
        path = f"fixtures/negative/{case_id}.invalid.jcs"
        generated[path] = data
        expected.append(
            {
                "case_id": case_id,
                "expected_code": code,
                "expected_result": "rejected",
                "path": path,
                "raw_sha256": raw_digest(data),
                "target": target,
            }
        )
    expected.sort(key=lambda item: item["case_id"])
    registered_codes = {
        code for codes in CHECK_CODE_REGISTRY.values() for code in codes
    }
    unknown_codes = sorted(
        {item["expected_code"] for item in expected} - registered_codes
    )
    if unknown_codes:
        raise ValueError(
            f"negative fixtures use unregistered check codes: {unknown_codes}"
        )
    generated["fixtures/negative/expected.json"] = pretty_bytes(
        {
            "cases": expected,
            "fixture_set_version": CONTRACT_VERSION,
            "format": "axiom-independent-check-negative-fixtures",
        }
    )
    return generated, expected


def build_generated_files() -> dict[str, bytes]:
    generated: dict[str, bytes] = {
        "schemas/axiom-check-bundle-manifest.schema.json": pretty_bytes(
            manifest_schema()
        ),
        "schemas/axiom-check-request.schema.json": pretty_bytes(request_schema()),
        "schemas/axiom-independent-check-result.schema.json": pretty_bytes(
            result_schema()
        ),
    }

    fixture_files, fixture_metadata = build_rejection_fixture()
    generated.update(fixture_files)
    request = strict_parse(fixture_files["fixtures/strict-evidence-rejection/request.jcs"])
    manifest = strict_parse(fixture_files["fixtures/strict-evidence-rejection/manifest.jcs"])
    result = strict_parse(
        fixture_files["fixtures/strict-evidence-rejection/expected-result.jcs"]
    )
    if not isinstance(request, dict) or not isinstance(manifest, dict) or not isinstance(result, dict):
        raise ValueError("generated fixture documents must be objects")

    negative_files, negative_metadata = build_negative_fixtures(
        request, manifest, result
    )
    generated.update(negative_files)

    generator_path = Path(__file__).relative_to(REPO_ROOT).as_posix()
    bindings = []
    for name, path in (
        (
            "adr-0008",
            "docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md",
        ),
        ("axiom-evidence-v0.1", "docs/evidence/axiom-evidence-v0.md"),
        ("axiom-ir-v0.1", "docs/ir/axiom-ir-v0.md"),
    ):
        data = (REPO_ROOT / path).read_bytes()
        bindings.append({"name": name, "path": path, "raw_sha256": raw_digest(data)})

    schema_paths = sorted(path for path in generated if path.startswith("schemas/"))
    contract = {
        "bindings": bindings,
        "check_code_registry": [
            {"codes": list(CHECK_CODE_REGISTRY[kind]), "kind": kind}
            for kind in CHECK_KINDS
        ],
        "contract_version": CONTRACT_VERSION,
        "fixture": fixture_metadata,
        "format": "axiom-independent-check-contract",
        "generator": {
            "path": generator_path,
            "raw_sha256": raw_digest(Path(__file__).read_bytes()),
            "version": CONTRACT_VERSION,
        },
        "negative_fixtures": negative_metadata,
        "profile": {"name": PROFILE_NAME, "version": PROFILE_VERSION},
        "schema_dialect": SCHEMA_DIALECT,
        "schemas": [file_ref(path, generated[path]) for path in schema_paths],
    }
    generated["contract.json"] = pretty_bytes(contract)
    return generated


def actual_generated_paths() -> set[str]:
    if not CONTRACT_ROOT.exists():
        return set()
    return {
        path.relative_to(CONTRACT_ROOT).as_posix()
        for path in CONTRACT_ROOT.rglob("*")
        if path.is_file() and path.name != "README.md"
    }


def check_generated(expected: dict[str, bytes]) -> list[str]:
    errors = []
    expected_paths = set(expected)
    actual_paths = actual_generated_paths()
    for path in sorted(expected_paths - actual_paths):
        errors.append(f"missing generated file: {path}")
    for path in sorted(actual_paths - expected_paths):
        errors.append(f"unexpected generated file: {path}")
    for relative_path in sorted(expected_paths & actual_paths):
        actual = (CONTRACT_ROOT / relative_path).read_bytes()
        if actual != expected[relative_path]:
            errors.append(f"generated file differs: {relative_path}")
    return errors


def write_generated(expected: dict[str, bytes]) -> None:
    for relative_path, data in sorted(expected.items()):
        path = CONTRACT_ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="compare without writing")
    mode.add_argument("--write", action="store_true", help="write deterministic files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = build_generated_files()
    if args.write:
        write_generated(expected)
    errors = check_generated(expected)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"independent check contracts passed ({len(expected)} generated files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
