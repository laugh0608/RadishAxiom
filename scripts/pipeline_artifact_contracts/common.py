"""Canonical encoding, identities, and shared protocol validation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = REPO_ROOT / "contracts/pipeline-artifacts-v0.1"
FORMAT_VERSION = "0.1"
PIPELINE_PROFILE = "raxc-keyed-finite-table-pipeline-v0.1"
CVC5_PROFILE = "cvc5-1.3.4-qf-uflia-v0.1"
NODE_TARGET_PROFILE = "node-24-esm-keyed-finite-table-v0.1"
NODE_INVOCATION_PROFILE = "node-24-esm-invocation-v0.1"
SEMANTICS_NAME = "keyed-finite-table-semantics"
SEMANTICS_SHA256 = "6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"
IR_VERSION = "0.1"
EVIDENCE_VERSION = "0.1"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

IR_PATH = Path("benchmarks/keyed-finite-table-v0.1/ax-b01/candidates/correct.ir.jcs")
IR_DOCUMENT_DIGEST = "sha256:1fa8846fb3ba15937e3e4b5848e74d84d89050711086d7462eb16175510b4154"
TOOL_REGISTRY_PATH = Path("contracts/toolchain-adapters-v0.1/registry.json")

DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CANONICAL_UINT_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
STABLE_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")

OBLIGATION_KINDS = (
    "contract-guarantee",
    "effect-empty",
    "field-origin",
    "group-conservation",
    "host-conformance",
    "input-conformance",
    "ir-structure",
    "key-cardinality",
    "noninterference",
    "numeric-range",
    "output-conformance",
    "row-coverage",
    "totality",
    "trust-boundary",
)

OBLIGATION_EXPECTATIONS = {
    "contract-guarantee": "prove",
    "effect-empty": "prove",
    "field-origin": "prove",
    "group-conservation": "prove",
    "host-conformance": "check",
    "input-conformance": "check",
    "ir-structure": "check",
    "key-cardinality": "prove",
    "noninterference": "prove",
    "numeric-range": "prove",
    "output-conformance": "check",
    "row-coverage": "prove",
    "totality": "prove",
    "trust-boundary": "trust",
}

STAGE_KINDS = {
    "P0": "capture-preflight",
    "P1": "normalize",
    "P2": "generate-obligations",
    "P3": "encode-query",
    "P4": "prove",
    "P5": "check-fixture",
    "P6": "generate-target",
    "P7": "execute-host",
    "P8": "compare-output",
    "P9": "assemble-results",
}

STAGE_RESULTS = (
    "completed",
    "error",
    "invalid",
    "not-run",
    "resource-exhausted",
    "timeout",
    "unavailable",
    "unsupported",
)

Json = dict[str, Any] | list[Any] | str | bool


class ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def validate_protocol_json(value: Any, path: str = "$") -> None:
    if type(value) is bool:
        return
    if isinstance(value, str):
        if not value.isascii():
            raise ContractError("non-ascii-fixture", path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_protocol_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise ContractError("non-ascii-fixture", path)
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
    ).encode("ascii")


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    ).encode("ascii")


def raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_id(domain: str, definition: Json) -> str:
    return raw_digest(domain.encode("ascii") + b"\0" + canonical_bytes(definition))


def entry(domain: str, definition: dict[str, Any]) -> dict[str, Any]:
    return {"definition": definition, "id": content_id(domain, definition)}


def parse_json_bytes(data: bytes) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("invalid-utf8", str(exc)) from exc
    duplicate: str | None = None

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal duplicate
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result and duplicate is None:
                duplicate = key
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_int=lambda value: (_ for _ in ()).throw(
                ContractError("json-number-or-null", value)
            ),
            parse_float=lambda value: (_ for _ in ()).throw(
                ContractError("json-number-or-null", value)
            ),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ContractError("json-number-or-null", value)
            ),
        )
    except ContractError:
        raise
    except json.JSONDecodeError as exc:
        raise ContractError("invalid-json", str(exc)) from exc
    if duplicate is not None:
        raise ContractError("duplicate-member", duplicate)
    validate_protocol_json(value)
    return value


def parse_canonical(data: bytes) -> Any:
    value = parse_json_bytes(data)
    if canonical_bytes(value) != data:
        raise ContractError("noncanonical-json")
    return value


def require_object(value: Any, code: str = "invalid-shape") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(code)
    return value


def require_array(value: Any, code: str = "invalid-shape") -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(code)
    return value


def require_members(value: dict[str, Any], members: set[str]) -> None:
    actual = set(value)
    unknown = sorted(actual - members)
    if unknown:
        raise ContractError("unknown-member", unknown[0])
    missing = sorted(members - actual)
    if missing:
        raise ContractError("missing-member", missing[0])


def require_digest(value: Any, code: str = "invalid-digest") -> str:
    if not isinstance(value, str) or not DIGEST_PATTERN.fullmatch(value):
        raise ContractError(code)
    return value


def require_sorted_unique(values: list[str], code: str) -> None:
    if values != sorted(values) or len(values) != len(set(values)):
        raise ContractError(code)
