"""Canonical encoding, strict parsing, and shared readiness identities."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = REPO_ROOT / "contracts/implementation-readiness-v0.1"
BENCHMARK_ROOT = REPO_ROOT / "benchmarks/keyed-finite-table-v0.1"
FORMAT = "radishaxiom-implementation-readiness"
FORMAT_VERSION = "0.1"
PROFILE = "keyed-finite-table-implementation-readiness-v0.1"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
STABLE_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]*$")
STAGE_IDS = tuple(f"P{index}" for index in range(10))
STAGE_RESULTS = (
    "completed",
    "error",
    "invalid",
    "not-applicable",
    "not-run",
    "resource-exhausted",
    "timeout",
    "unavailable",
    "unsupported",
)
PLATFORMS = (
    "linux-amd64",
    "linux-arm64",
    "macos-amd64",
    "macos-arm64",
    "windows-amd64",
    "windows-arm64",
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


def document_digest(value: Json) -> str:
    return raw_digest(
        b"radishaxiom.implementation-readiness.v0.1\0" + canonical_bytes(value)
    )


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
    unknown = sorted(set(value) - members)
    if unknown:
        raise ContractError("unknown-member", unknown[0])
    missing = sorted(members - set(value))
    if missing:
        raise ContractError("missing-member", missing[0])


def require_digest(value: Any) -> str:
    if not isinstance(value, str) or not DIGEST_PATTERN.fullmatch(value):
        raise ContractError("invalid-digest")
    return value


def require_stable_id(value: Any) -> str:
    if not isinstance(value, str) or not STABLE_ID_PATTERN.fullmatch(value):
        raise ContractError("invalid-stable-id")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def bound_file(path: Path) -> dict[str, str]:
    data = (REPO_ROOT / path).read_bytes()
    return {"path": path.as_posix(), "raw_sha256": raw_digest(data)}
