"""Assemble, validate, write, and check the checker bundle contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .common import (
    BUNDLE_SET_FORMAT,
    BUNDLE_SET_PROFILE,
    CONTRACT_ROOT,
    FORMAT_VERSION,
    PLATFORMS,
    READINESS_PATH,
    REPO_ROOT,
    canonical_bytes,
    content_id,
    file_ref,
    load_json,
    pretty_bytes,
    raw_digest,
)
from .protocol import independent_contract
from .scenarios import (
    CROSS_SCENARIOS,
    NEGATIVE_SCENARIOS,
    BuiltScenario,
    build_benchmark_scenario,
    build_cross_scenario,
    build_negative_scenario,
)


SOURCE_BINDINGS = (
    ("benchmark-corpus-v0.1", Path("benchmarks/keyed-finite-table-v0.1/corpus.json")),
    ("implementation-readiness-v0.1", Path("contracts/implementation-readiness-v0.1/manifest.jcs")),
    ("independent-check-v0.1", Path("contracts/independent-check-v0.1/contract.json")),
    ("pipeline-artifacts-v0.1", Path("contracts/pipeline-artifacts-v0.1/contract.json")),
    ("axiom-evidence-v0.1", Path("docs/evidence/axiom-evidence-v0.md")),
    ("axiom-ir-v0.1", Path("docs/ir/axiom-ir-v0.md")),
    ("checker-isolation-adr", Path("docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md")),
    ("keyed-finite-table-semantics", Path("docs/semantics/keyed-finite-table-semantics.md")),
)
GENERATOR_SOURCES = (
    Path("scripts/generate-checker-bundle-contracts.py"),
    Path("scripts/checker_bundle_contracts/__init__.py"),
    Path("scripts/checker_bundle_contracts/common.py"),
    Path("scripts/checker_bundle_contracts/evidence.py"),
    Path("scripts/checker_bundle_contracts/generator.py"),
    Path("scripts/checker_bundle_contracts/obligations.py"),
    Path("scripts/checker_bundle_contracts/pipeline.py"),
    Path("scripts/checker_bundle_contracts/protocol.py"),
    Path("scripts/checker_bundle_contracts/scenarios.py"),
)


def _bindings() -> list[dict[str, str]]:
    return [
        {"name": name, "path": path.as_posix(), "sha256": raw_digest((REPO_ROOT / path).read_bytes())}
        for name, path in sorted(SOURCE_BINDINGS)
    ]


def _schema() -> dict[str, Any]:
    digest = {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"}
    binding = {
        "additionalProperties": False,
        "properties": {
            "name": {"minLength": 1, "type": "string"},
            "path": {"minLength": 1, "type": "string"},
            "sha256": digest,
        },
        "required": ["name", "path", "sha256"],
        "type": "object",
    }
    expected_properties = {
        "check_id": digest,
        "codes": {"items": {"type": "string"}, "type": "array", "uniqueItems": True},
        "content_digest": digest,
        "document_digest": digest,
        "kind": {"enum": ["independent-result", "process-failure"]},
        "outcome": {
            "enum": [
                "accepted",
                "accepted-with-trust",
                "incomplete",
                "not-produced",
                "rejected",
            ]
        },
        "process": {"enum": ["completed", "failed"]},
        "process_codes": {"items": {"type": "string"}, "type": "array", "uniqueItems": True},
    }
    scenario = {
        "additionalProperties": False,
        "properties": {
            "bundle": {
                "additionalProperties": False,
                "properties": {
                    "manifest_content_digest": digest,
                    "manifest_document_digest": digest,
                    "materialization": {
                        "enum": [
                            "complete",
                            "missing",
                            "omitted-obligation",
                            "tampered",
                        ]
                    },
                    "path": {"minLength": 1, "type": "string"},
                },
                "required": [
                    "manifest_content_digest",
                    "manifest_document_digest",
                    "materialization",
                    "path",
                ],
                "type": "object",
            },
            "evidence": {
                "additionalProperties": False,
                "properties": {
                    "conclusion": {
                        "enum": [
                            "implementation_inconsistent",
                            "inconclusive",
                            "input_rejected",
                            "satisfied",
                            "violated",
                        ]
                    },
                    "content_digest": digest,
                    "document_digest": digest,
                },
                "required": ["conclusion", "content_digest", "document_digest"],
                "type": "object",
            },
            "expected": {
                "additionalProperties": False,
                "properties": expected_properties,
                "required": [
                    "codes",
                    "content_digest",
                    "document_digest",
                    "kind",
                    "outcome",
                    "process",
                    "process_codes",
                ],
                "type": "object",
            },
            "kind": {"enum": ["benchmark", "cross-contract", "independent-check"]},
            "level": {"const": "specified"},
            "readiness_scenario_id": {"pattern": "^[A-Z0-9-]+$", "type": "string"},
            "request": {
                "additionalProperties": False,
                "properties": {
                    "content_digest": digest,
                    "document_digest": digest,
                },
                "required": ["content_digest", "document_digest"],
                "type": "object",
            },
        },
        "required": [
            "bundle",
            "evidence",
            "expected",
            "kind",
            "level",
            "readiness_scenario_id",
            "request",
        ],
        "type": "object",
    }
    return {
        "$id": "urn:radishaxiom:schema:keyed-finite-table-checker-bundle-set:0.1",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "properties": {
            "bindings": {"items": binding, "minItems": 1, "type": "array", "uniqueItems": True},
            "counts": {
                "additionalProperties": False,
                "properties": {
                    "benchmark": {"pattern": "^[1-9][0-9]*$", "type": "string"},
                    "cross_contract": {"pattern": "^[1-9][0-9]*$", "type": "string"},
                    "negative": {"pattern": "^[1-9][0-9]*$", "type": "string"},
                    "total": {"pattern": "^[1-9][0-9]*$", "type": "string"},
                },
                "required": ["benchmark", "cross_contract", "negative", "total"],
                "type": "object",
            },
            "format": {"const": BUNDLE_SET_FORMAT},
            "format_version": {"const": FORMAT_VERSION},
            "level": {"const": "specified"},
            "platforms": {
                "items": {"enum": list(PLATFORMS)},
                "maxItems": len(PLATFORMS),
                "minItems": len(PLATFORMS),
                "type": "array",
                "uniqueItems": True,
            },
            "profile": {"const": BUNDLE_SET_PROFILE},
            "scenarios": {"items": scenario, "minItems": 1, "type": "array", "uniqueItems": True},
        },
        "required": [
            "bindings",
            "counts",
            "format",
            "format_version",
            "level",
            "platforms",
            "profile",
            "scenarios",
        ],
        "title": "Keyed Finite Table Checker Bundle Set v0.1",
        "type": "object",
    }


def _verify_readiness_benchmark(
    readiness: dict[str, Any], built: BuiltScenario
) -> None:
    evidence = built.evidence
    if evidence["conclusion"]["kind"] != readiness["evidence"]["conclusion"]:
        raise ValueError(f"Evidence conclusion drifted: {readiness['id']}")
    actual_trust = sorted(item["definition"]["category"] for item in evidence["trust"])
    if actual_trust != readiness["evidence"]["remaining_trust"]:
        raise ValueError(f"Evidence trust drifted: {readiness['id']}")
    actual_uncovered = sorted(
        item["definition"]["category"] for item in evidence["uncovered"]
    )
    if actual_uncovered != readiness["evidence"]["uncovered"]:
        raise ValueError(f"Evidence uncovered drifted: {readiness['id']}")
    states = [
        {
            "kind": item["definition"]["kind"],
            "status": item["result"]["kind"],
            **(
                {"reason": item["result"]["reason"]}
                if item["result"]["kind"] == "unknown"
                else {}
            ),
        }
        for item in evidence["obligations"]
    ]
    for required in readiness["evidence"]["required_results"]:
        if required not in states:
            raise ValueError(
                f"Evidence required result missing: {readiness['id']}:{required}"
            )


def _validate_bundle(built: BuiltScenario, readiness: dict[str, Any]) -> None:
    module = independent_contract()
    if canonical_bytes(built.manifest) != built.manifest_bytes:
        raise ValueError(f"manifest is not canonical: {built.scenario_id}")
    if canonical_bytes(built.request) != built.request_bytes:
        raise ValueError(f"request is not canonical: {built.scenario_id}")
    if canonical_bytes(built.evidence) != built.evidence_bytes:
        raise ValueError(f"Evidence is not canonical: {built.scenario_id}")
    module.validate_manifest(built.manifest)
    module.validate_request(built.request)
    if built.request["bundle_manifest"] != raw_digest(built.manifest_bytes):
        raise ValueError(f"request/manifest binding drifted: {built.scenario_id}")
    if built.request["evidence"] != raw_digest(built.evidence_bytes):
        raise ValueError(f"request/Evidence binding drifted: {built.scenario_id}")
    descriptor_by_digest = {
        item["content_digest"]: item for item in built.manifest["artifacts"]
    }
    if set(descriptor_by_digest) != set(built.materials):
        raise ValueError(f"manifest/material coverage drifted: {built.scenario_id}")
    root = f"s/{built.scenario_id.lower()}"
    blob_prefix = root + "/bundle/blobs/sha256/"
    blobs = {
        "sha256:" + path.removeprefix(blob_prefix): data
        for path, data in built.files.items()
        if path.startswith(blob_prefix)
    }
    materialization = built.index["bundle"]["materialization"]
    missing = sorted(set(descriptor_by_digest) - set(blobs))
    extra = sorted(set(blobs) - set(descriptor_by_digest))
    mismatched = []
    for digest, data in blobs.items():
        descriptor = descriptor_by_digest[digest]
        if raw_digest(data) != digest or str(len(data)) != descriptor["byte_length"]:
            mismatched.append(digest)
    if extra:
        raise ValueError(f"unlisted bundle blobs: {built.scenario_id}:{extra}")
    if materialization == "missing":
        if len(missing) != 1 or mismatched:
            raise ValueError(f"missing bundle negative drifted: {built.scenario_id}")
    elif materialization == "tampered":
        if missing or len(mismatched) != 1:
            raise ValueError(f"tampered bundle negative drifted: {built.scenario_id}")
    elif missing or mismatched:
        raise ValueError(f"complete bundle bytes drifted: {built.scenario_id}")
    limits = {item["name"]: int(item["value"]) for item in built.request["limits"]}
    if any(int(item["byte_length"]) > limits["artifact-bytes"] for item in built.manifest["artifacts"]):
        raise ValueError(f"artifact exceeds request limit: {built.scenario_id}")
    if sum(int(item["byte_length"]) for item in built.manifest["artifacts"]) > limits["bundle-bytes"]:
        raise ValueError(f"bundle exceeds request limit: {built.scenario_id}")
    if readiness["kind"] == "benchmark":
        _verify_readiness_benchmark(readiness, built)
    elif readiness["evidence"]["availability"] == "required":
        if built.evidence["conclusion"]["kind"] != readiness["evidence"]["conclusion"]:
            raise ValueError(f"cross-contract conclusion drifted: {built.scenario_id}")
        actual_trust = sorted(
            item["definition"]["category"] for item in built.evidence["trust"]
        )
        if actual_trust != readiness["evidence"]["remaining_trust"]:
            raise ValueError(f"cross-contract trust drifted: {built.scenario_id}")
    expected_path = next(
        path for path in built.files if path.startswith(root + "/expected-")
    )
    expected = load_json_bytes(built.files[expected_path])
    if readiness["independent"]["outcome"] == "not-produced":
        if expected["result"] != "not-produced":
            raise ValueError(f"process failure produced a result: {built.scenario_id}")
        if expected["code"] not in readiness["independent"]["process_codes"]:
            raise ValueError(f"process failure code drifted: {built.scenario_id}")
    else:
        module.validate_result(expected)
        if expected["result"]["kind"] != readiness["independent"]["outcome"]:
            raise ValueError(f"independent outcome drifted: {built.scenario_id}")
        actual_codes = {
            code for check in expected["checks"] for code in check["definition"]["codes"]
        }
        if not set(readiness["independent"]["codes"]).issubset(actual_codes):
            raise ValueError(f"independent codes drifted: {built.scenario_id}")


def load_json_bytes(data: bytes) -> dict[str, Any]:
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def build_generated_files() -> dict[str, bytes]:
    readiness_manifest = load_json(READINESS_PATH)
    readiness_by_id = {item["id"]: item for item in readiness_manifest["scenarios"]}
    benchmark_readiness = sorted(
        (item for item in readiness_manifest["scenarios"] if item["kind"] == "benchmark"),
        key=lambda item: item["id"],
    )
    if len(benchmark_readiness) != 20:
        raise ValueError("bundle contract requires exactly 20 benchmark scenarios")

    built_values: list[BuiltScenario] = []
    for readiness in benchmark_readiness:
        built = build_benchmark_scenario(readiness)
        _validate_bundle(built, readiness)
        built_values.append(built)
    base = next(item for item in built_values if item.scenario_id == "AX-B01-CORRECT")
    for scenario_id in CROSS_SCENARIOS:
        built = build_cross_scenario(readiness_by_id[scenario_id])
        _validate_bundle(built, readiness_by_id[scenario_id])
        built_values.append(built)
    for scenario_id in NEGATIVE_SCENARIOS:
        built = build_negative_scenario(readiness_by_id[scenario_id], base)
        _validate_bundle(built, readiness_by_id[scenario_id])
        built_values.append(built)

    ids = [item.scenario_id for item in built_values]
    if len(ids) != len(set(ids)) or set(ids) != {
        *(item["id"] for item in benchmark_readiness),
        *CROSS_SCENARIOS,
        *NEGATIVE_SCENARIOS,
    }:
        raise ValueError("materialized scenario set drifted")

    generated: dict[str, bytes] = {}
    for built in built_values:
        overlap = set(generated) & set(built.files)
        if overlap:
            raise ValueError(f"duplicate generated bundle paths: {sorted(overlap)}")
        generated.update(built.files)
    index = {
        "bindings": _bindings(),
        "counts": {
            "benchmark": "20",
            "cross_contract": str(len(CROSS_SCENARIOS)),
            "negative": str(len(NEGATIVE_SCENARIOS)),
            "total": str(len(built_values)),
        },
        "format": BUNDLE_SET_FORMAT,
        "format_version": FORMAT_VERSION,
        "level": "specified",
        "platforms": list(PLATFORMS),
        "profile": BUNDLE_SET_PROFILE,
        "scenarios": sorted(
            (item.index for item in built_values),
            key=lambda item: item["readiness_scenario_id"],
        ),
    }
    generated["bundle-set.jcs"] = canonical_bytes(index)
    generated["schemas/keyed-finite-table-checker-bundle-set.schema.json"] = pretty_bytes(
        _schema()
    )
    contract = {
        "bundle_set": {
            "content_digest": raw_digest(generated["bundle-set.jcs"]),
            "document_digest": content_id(
                "keyed-finite-table-checker-bundle-set-v0.1:document", index
            ),
            "path": "bundle-set.jcs",
        },
        "contract_version": FORMAT_VERSION,
        "files": [file_ref(path, data) for path, data in sorted(generated.items())],
        "format": "keyed-finite-table-checker-bundle-contract",
        "generator_sources": [
            {
                "path": path.as_posix(),
                "sha256": raw_digest((REPO_ROOT / path).read_bytes()),
            }
            for path in GENERATOR_SOURCES
        ],
        "scenario_count": str(len(built_values)),
        "sources": _bindings(),
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
    for path in sorted(expected_paths & actual_paths):
        actual = (CONTRACT_ROOT / path).read_bytes()
        if actual != expected[path]:
            errors.append(f"generated file drifted: {path}")
    for path in CONTRACT_ROOT.rglob("*") if CONTRACT_ROOT.exists() else []:
        if path.is_symlink():
            errors.append(f"symlink forbidden in checker bundle contract: {path}")
    return errors


def write_generated(expected: dict[str, bytes]) -> None:
    CONTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    for path in sorted(actual_generated_paths() - set(expected)):
        (CONTRACT_ROOT / path).unlink()
    for directory in sorted(
        (path for path in CONTRACT_ROOT.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass
    for path, data in expected.items():
        destination = CONTRACT_ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generated = build_generated_files()
        if args.write:
            write_generated(generated)
            print(
                "wrote keyed finite table checker bundle contract: "
                f"{len(generated)} files"
            )
            return 0
        errors = check_generated(generated)
    except (OSError, ValueError, KeyError, IndexError) as exc:
        print(f"checker bundle contract error: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        "keyed finite table checker bundle contract passed: "
        f"{len(generated)} files"
    )
    return 0
