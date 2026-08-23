"""Strict validation for execution profile fixtures."""

from __future__ import annotations

import json
import re
from typing import Any

from .common import (
    CHECKER_PROFILE,
    CVC5_PROFILE,
    FORMAT,
    FORMAT_VERSION,
    NODE_PROFILE,
    REPO_ROOT,
    canonical_bytes,
    raw_digest,
    validate_json,
)


POSITIVE_UINT = re.compile(r"^[1-9][0-9]*$")


class ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate-member", key)
        result[key] = value
    return result


def strict_parse(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("invalid-utf8") from exc
    try:
        value = json.loads(text, object_pairs_hook=_pairs)
    except ContractError:
        raise
    except json.JSONDecodeError as exc:
        raise ContractError("invalid-json") from exc
    try:
        validate_json(value)
    except ValueError as exc:
        raise ContractError("json-number-or-null") from exc
    if not isinstance(value, dict):
        raise ContractError("invalid-root")
    if canonical_bytes(value) != data:
        raise ContractError("noncanonical-json")
    return value


def _keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    unknown = sorted(set(value) - expected)
    if unknown:
        raise ContractError("unknown-member", f"{path}.{unknown[0]}")
    missing = sorted(expected - set(value))
    if missing:
        raise ContractError("missing-required-member", f"{path}.{missing[0]}")


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError("invalid-tag", path)
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("invalid-tag", path)
    return value


def _sorted_unique(values: list[str], code: str = "noncanonical-order") -> None:
    if values != sorted(values):
        raise ContractError(code)
    if len(values) != len(set(values)):
        raise ContractError("duplicate-entry")


def _validate_limit_sets(value: Any, expected: list[dict[str, Any]]) -> None:
    items = _array(value, "$.limit_sets")
    ids = [str(_object(item, "$.limit_sets[]").get("id", "")) for item in items]
    _sorted_unique(ids)
    expected_by_id = {item["id"]: item for item in expected}
    if set(ids) != set(expected_by_id):
        raise ContractError("limit-set-reference")
    for item in items:
        obj = _object(item, "$.limit_sets[]")
        _keys(obj, {"id", "limits", "scope"}, "$.limit_sets[]")
        limit_items = _array(obj["limits"], f"$.limit_sets[{obj['id']}].limits")
        pairs: list[tuple[str, str]] = []
        for entry in limit_items:
            limit_obj = _object(entry, "$.limit_sets[].limits[]")
            _keys(
                limit_obj,
                {"enforcement", "name", "unit", "value"},
                "$.limit_sets[].limits[]",
            )
            pair = (str(limit_obj["name"]), str(limit_obj["unit"]))
            pairs.append(pair)
            if not POSITIVE_UINT.fullmatch(str(limit_obj["value"])):
                raise ContractError("non-positive-limit", str(limit_obj["name"]))
        if pairs != sorted(pairs):
            raise ContractError("noncanonical-order", obj["id"])
        if len(pairs) != len(set(pairs)):
            raise ContractError("duplicate-limit", obj["id"])
        expected_item = expected_by_id[obj["id"]]
        if obj != expected_item:
            if obj["id"] == "keyed-finite-table-independent-check-request-v0.1":
                raise ContractError("checker-limit-set-mismatch")
            raise ContractError("limit-set-definition-mismatch", obj["id"])


def _validate_environment(profile: dict[str, Any]) -> None:
    environment = _object(profile.get("environment"), "$.profiles[].environment")
    if environment != {"inherit": "none", "set": []}:
        raise ContractError("environment-inheritance", profile.get("id", ""))


def _validate_cvc5(profile: dict[str, Any], expected: dict[str, Any]) -> None:
    _validate_environment(profile)
    invocation = _object(profile.get("invocation"), "$.profiles[].invocation")
    tokens = _array(invocation.get("argument_tokens"), "$.profiles[].argument_tokens")
    literal_values = [
        token.get("value", "")
        for token in tokens
        if isinstance(token, dict) and token.get("kind") == "literal"
    ]
    if any("seed" in str(value) for value in literal_values):
        raise ContractError("forbidden-cvc5-random-seed")
    if any(
        isinstance(token, dict) and token.get("kind") in {"artifact-path", "path"}
        for token in tokens
    ):
        raise ContractError("forbidden-cvc5-path-input")
    if "--strict-parsing" not in literal_values:
        raise ContractError("required-cvc5-option-missing")
    if tokens != expected["invocation"]["argument_tokens"]:
        raise ContractError("cvc5-options-mismatch")
    if profile != expected:
        raise ContractError("cvc5-profile-mismatch")


def _validate_node(profile: dict[str, Any], expected: dict[str, Any]) -> None:
    _validate_environment(profile)
    if profile.get("capability_boundary") != expected["capability_boundary"]:
        raise ContractError("node-capability-mismatch")
    if profile.get("codec") != expected["codec"]:
        raise ContractError("node-codec-mismatch")
    invocation = _object(profile.get("invocation"), "$.profiles[].invocation")
    if invocation.get("argument_tokens") != expected["invocation"]["argument_tokens"]:
        raise ContractError("node-options-mismatch")
    if profile != expected:
        raise ContractError("node-profile-mismatch")


def _validate_checker(profile: dict[str, Any], expected: dict[str, Any]) -> None:
    _validate_environment(profile)
    counters = _array(profile.get("resource_counters"), "$.profiles[].resource_counters")
    names = [str(_object(item, "$.profiles[].resource_counters[]").get("name", "")) for item in counters]
    expected_names = [item["name"] for item in expected["resource_counters"]]
    if names != expected_names:
        raise ContractError("checker-counter-order")
    if profile.get("result_boundary") != expected["result_boundary"]:
        raise ContractError("checker-result-boundary")
    if profile != expected:
        raise ContractError("checker-profile-mismatch")


def _validate_profiles(value: Any, expected: list[dict[str, Any]]) -> None:
    profiles = _array(value, "$.profiles")
    ids = [str(_object(item, "$.profiles[]").get("id", "")) for item in profiles]
    _sorted_unique(ids)
    expected_by_id = {item["id"]: item for item in expected}
    if set(ids) != set(expected_by_id):
        raise ContractError("profile-set-mismatch")
    for profile in profiles:
        obj = _object(profile, "$.profiles[]")
        profile_id = str(obj.get("id", ""))
        if profile_id == CVC5_PROFILE:
            _validate_cvc5(obj, expected_by_id[profile_id])
        elif profile_id == NODE_PROFILE:
            _validate_node(obj, expected_by_id[profile_id])
        elif profile_id == CHECKER_PROFILE:
            _validate_checker(obj, expected_by_id[profile_id])
        else:
            raise ContractError("unknown-profile", profile_id)


def _validate_certificate(value: Any, expected: dict[str, Any]) -> None:
    capability = _object(value, "$.certificate_capabilities")
    _keys(
        capability,
        {"authority", "candidate_formats", "policy_cases", "supported_profiles"},
        "$.certificate_capabilities",
    )
    if capability["supported_profiles"] != []:
        raise ContractError("certificate-profile-unaccepted")
    cases = _array(capability["policy_cases"], "$.certificate_capabilities.policy_cases")
    for case in cases:
        case_obj = _object(case, "$.certificate_capabilities.policy_cases[]")
        if set(case_obj) != {"evidence_support", "proof_support", "readiness_scenario"}:
            raise ContractError("certificate-boundary")
        if case_obj["evidence_support"] != "backend-attestation":
            raise ContractError("certificate-boundary")
    if capability != expected:
        raise ContractError("certificate-boundary")


def _validate_sources(value: Any, expected: list[dict[str, str]]) -> None:
    sources = _array(value, "$.source_bindings")
    names = [str(_object(item, "$.source_bindings[]").get("name", "")) for item in sources]
    _sorted_unique(names)
    if sources != expected:
        for source in sources:
            if not isinstance(source, dict):
                continue
            path = source.get("path")
            digest = source.get("sha256")
            if isinstance(path, str) and isinstance(digest, str):
                source_path = (REPO_ROOT / path).resolve()
                try:
                    source_path.relative_to(REPO_ROOT)
                except ValueError as exc:
                    raise ContractError("source-path-escape") from exc
                if source_path.is_file() and raw_digest(source_path.read_bytes()) != digest:
                    raise ContractError("source-digest-drift", path)
        raise ContractError("source-binding-mismatch")
    for source in sources:
        path = (REPO_ROOT / source["path"]).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise ContractError("source-path-escape") from exc
        if not path.is_file() or raw_digest(path.read_bytes()) != source["sha256"]:
            raise ContractError("source-digest-drift", source["path"])


def validate_manifest(value: dict[str, Any], expected: dict[str, Any]) -> None:
    _keys(
        value,
        {
            "certificate_capabilities",
            "counts",
            "coverage",
            "format",
            "format_version",
            "level",
            "limit_sets",
            "profiles",
            "references",
            "source_bindings",
        },
        "$",
    )
    if value["format"] != FORMAT:
        raise ContractError("unknown-format")
    if value["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    if value["level"] != "specified":
        raise ContractError("level-overclaim")
    _validate_limit_sets(value["limit_sets"], expected["limit_sets"])
    _validate_profiles(value["profiles"], expected["profiles"])
    _validate_certificate(
        value["certificate_capabilities"], expected["certificate_capabilities"]
    )
    _validate_sources(value["source_bindings"], expected["source_bindings"])
    if value["counts"] != expected["counts"]:
        raise ContractError("count-mismatch")
    if value["coverage"] != expected["coverage"]:
        raise ContractError("coverage-mismatch")
    if value["references"] != expected["references"]:
        raise ContractError("reference-mismatch")
    if value != expected:
        raise ContractError("manifest-mismatch")


def validate_bytes(data: bytes, expected: dict[str, Any]) -> dict[str, Any]:
    value = strict_parse(data)
    validate_manifest(value, expected)
    return value
