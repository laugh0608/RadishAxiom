"""Shared paths and canonical encoding for execution profile contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = REPO_ROOT / "contracts/execution-profiles-v0.1"
FORMAT = "radishaxiom-execution-profile-set"
FORMAT_VERSION = "0.1"
DOCUMENT_DOMAIN = "radishaxiom-execution-profile-set-v0.1:document"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

CVC5_PROFILE = "cvc5-1.3.4-qf-uflia-v0.1"
NODE_PROFILE = "node-24-esm-invocation-v0.1"
NODE_TARGET_PROFILE = "node-24-esm-keyed-finite-table-v0.1"
CHECKER_PROFILE = "keyed-finite-table-independent-check-v0.1"

SOURCE_PATHS = (
    ("adr-0005", Path("docs/adr/0005-first-verification-backend.md")),
    ("adr-0006", Path("docs/adr/0006-first-target-runtime-and-execution-path.md")),
    (
        "adr-0008",
        Path("docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md"),
    ),
    (
        "implementation-readiness-v0.1",
        Path("contracts/implementation-readiness-v0.1/manifest.jcs"),
    ),
    ("independent-check-v0.1", Path("contracts/independent-check-v0.1/contract.json")),
    ("pipeline-artifacts-v0.1", Path("contracts/pipeline-artifacts-v0.1/contract.json")),
    ("toolchain-adapters-v0.1", Path("contracts/toolchain-adapters-v0.1/registry.json")),
)

GENERATOR_SOURCES = (
    Path("scripts/generate-execution-profile-contracts.py"),
    Path("scripts/execution_profile_contracts/__init__.py"),
    Path("scripts/execution_profile_contracts/common.py"),
    Path("scripts/execution_profile_contracts/model.py"),
    Path("scripts/execution_profile_contracts/schema.py"),
    Path("scripts/execution_profile_contracts/validator.py"),
    Path("scripts/execution_profile_contracts/generator.py"),
)

Json = dict[str, Any] | list[Any] | str | bool


def validate_json(value: Any, path: str = "$") -> None:
    if type(value) is bool or isinstance(value, str):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string member at {path}")
            validate_json(item, f"{path}.{key}")
        return
    raise ValueError(f"JSON number or null is forbidden at {path}")


def canonical_bytes(value: Json) -> bytes:
    validate_json(value)
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
    return raw_digest(domain.encode("ascii") + b"\0" + canonical_bytes(value))


def file_ref(path: str, data: bytes) -> dict[str, str]:
    return {
        "byte_length": str(len(data)),
        "path": path,
        "sha256": raw_digest(data),
    }


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value
