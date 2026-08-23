"""Shared canonical encoding, paths, and artifact helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = REPO_ROOT / "contracts/keyed-finite-table-checker-bundles-v0.1"
BENCHMARK_ROOT = REPO_ROOT / "benchmarks/keyed-finite-table-v0.1"
READINESS_PATH = REPO_ROOT / "contracts/implementation-readiness-v0.1/manifest.jcs"
FORMAT_VERSION = "0.1"
BUNDLE_SET_FORMAT = "keyed-finite-table-checker-bundle-set"
BUNDLE_SET_PROFILE = "keyed-finite-table-checker-bundles-v0.1"
SEMANTICS_NAME = "keyed-finite-table-semantics"
SEMANTICS_SHA256 = (
    "sha256:6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"
)
PLATFORMS = (
    "linux-amd64",
    "linux-arm64",
    "macos-amd64",
    "macos-arm64",
    "windows-amd64",
    "windows-arm64",
)
NORMATIVE_SPECS = (
    ("axiom-evidence-spec", Path("docs/evidence/axiom-evidence-v0.md"), "markdown", "0.1"),
    ("axiom-ir-spec", Path("docs/ir/axiom-ir-v0.md"), "markdown", "0.1"),
    (
        "checker-isolation-adr",
        Path("docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md"),
        "markdown",
        "0008",
    ),
    (
        "keyed-finite-table-semantics",
        Path("docs/semantics/keyed-finite-table-semantics.md"),
        "markdown",
        "0.1",
    ),
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
                raise ValueError(f"non-string object member at {path}")
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


def entry(domain: str, definition: dict[str, Any]) -> dict[str, Any]:
    return {"definition": definition, "id": content_id(domain, definition)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def artifact_descriptor(
    data: bytes, format_name: str, format_version: str
) -> dict[str, str]:
    return {
        "byte_length": str(len(data)),
        "content_digest": raw_digest(data),
        "format": format_name,
        "format_version": format_version,
    }


def file_ref(path: str, data: bytes) -> dict[str, str]:
    return {
        "byte_length": str(len(data)),
        "path": path,
        "sha256": raw_digest(data),
    }


def slug_for(scenario_id: str) -> str:
    return scenario_id.lower()


def digest_hex(digest: str) -> str:
    prefix = "sha256:"
    if not digest.startswith(prefix) or len(digest) != len(prefix) + 64:
        raise ValueError(f"invalid digest: {digest}")
    return digest.removeprefix(prefix)


def sorted_entries(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(values, key=lambda item: item["id"])


def read_bound(path_value: str, expected_digest: str) -> bytes:
    path = (REPO_ROOT / path_value).resolve()
    path.relative_to(REPO_ROOT)
    data = path.read_bytes()
    actual = raw_digest(data)
    if actual != expected_digest:
        raise ValueError(
            f"bound artifact digest drifted: {path_value}: {actual} != {expected_digest}"
        )
    return data
