"""Assemble, validate, write, and check implementation-readiness files."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

from .common import (
    CONTRACT_ROOT,
    FORMAT,
    FORMAT_VERSION,
    PLATFORMS,
    PROFILE,
    REPO_ROOT,
    STAGE_IDS,
    STAGE_RESULTS,
    ContractError,
    canonical_bytes,
    document_digest,
    parse_canonical,
    pretty_bytes,
    raw_digest,
    require_array,
    require_digest,
    require_members,
    require_object,
    require_stable_id,
)
from .schema import manifest_schema
from .scenarios import build_coverage, build_scenarios, bindings, requirements


MANIFEST_MEMBERS = {
    "bindings",
    "coverage",
    "format",
    "format_version",
    "observation",
    "platforms",
    "profile",
    "profiles",
    "requirement_count",
    "requirements",
    "scenario_counts",
    "scenarios",
}
SCENARIO_MEMBERS = {
    "artifact_roles",
    "bundle",
    "cache",
    "evidence",
    "gate",
    "id",
    "independent",
    "input",
    "kind",
    "level",
    "platforms",
    "profile",
    "receipt",
    "source_refs",
    "stages",
}
TARGET_ROLES = {"execute-host", "host-output", "target-module"}


def _profiles() -> list[str]:
    registry = json.loads(
        (REPO_ROOT / "contracts/toolchain-adapters-v0.1/registry.json").read_bytes()
    )
    return sorted(item["id"] for item in registry["profiles"])


def _independent_codes() -> set[str]:
    contract = json.loads(
        (REPO_ROOT / "contracts/independent-check-v0.1/contract.json").read_bytes()
    )
    return {
        code
        for group in contract["check_code_registry"]
        for code in group["codes"]
    }


def build_manifest() -> dict[str, Any]:
    requirement_values = requirements()
    scenario_values = build_scenarios()
    benchmark_count = sum(
        scenario["kind"] == "benchmark" for scenario in scenario_values
    )
    checker_count = sum(
        scenario["id"].startswith("CHK-") for scenario in scenario_values
    )
    if benchmark_count != 20 or checker_count != 16:
        raise ValueError(
            "readiness matrix must retain 20 benchmark and 16 CHK scenarios"
        )
    return {
        "bindings": bindings(),
        "coverage": build_coverage(requirement_values, scenario_values),
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "observation": {"level": "specified", "observed_scenarios": "0"},
        "platforms": list(PLATFORMS),
        "profile": PROFILE,
        "profiles": _profiles(),
        "requirement_count": str(len(requirement_values)),
        "requirements": requirement_values,
        "scenario_counts": {
            "benchmark": str(benchmark_count),
            "checker": str(checker_count),
            "pipeline_and_readiness": str(
                len(scenario_values) - benchmark_count - checker_count
            ),
            "total": str(len(scenario_values)),
        },
        "scenarios": scenario_values,
    }


def _require_sorted_unique(values: list[str], code: str) -> None:
    if len(values) != len(set(values)):
        raise ContractError("duplicate-" + code.removesuffix("s-not-sorted"))
    if values != sorted(values):
        raise ContractError(code)


def _verify_bound_artifacts(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _verify_bound_artifacts(item)
        return
    if not isinstance(value, dict):
        return
    if value.get("materialization") == "bound-artifact":
        path_value = value.get("path")
        digest_value = value.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest_value, str):
            raise ContractError("invalid-artifact-binding")
        path = (REPO_ROOT / path_value).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise ContractError("artifact-path-escape", path_value) from exc
        if not path.is_file():
            raise ContractError("artifact-missing", path_value)
        if raw_digest(path.read_bytes()) != digest_value:
            raise ContractError("artifact-digest-mismatch", path_value)
    for item in value.values():
        _verify_bound_artifacts(item)


def _validate_scenario(
    scenario: dict[str, Any],
    expected_by_id: dict[str, dict[str, Any]],
) -> None:
    require_members(scenario, SCENARIO_MEMBERS)
    scenario_id = require_stable_id(scenario["id"])
    if scenario["profile"] != PROFILE:
        raise ContractError("unsupported-profile", scenario_id)
    if scenario["level"] != "specified":
        raise ContractError("invalid-evidence-level", scenario_id)
    if scenario["platforms"] != list(PLATFORMS):
        raise ContractError("platform-set-mismatch", scenario_id)

    source_refs = require_array(scenario["source_refs"])
    if not all(isinstance(item, str) for item in source_refs):
        raise ContractError("invalid-source-ref", scenario_id)
    _require_sorted_unique(source_refs, "source-refs-not-sorted")

    stages = require_array(scenario["stages"])
    stage_ids = [require_object(item).get("id") for item in stages]
    if stage_ids != list(STAGE_IDS):
        raise ContractError("stages-not-sorted", scenario_id)
    stage_results: dict[str, str] = {}
    for stage in stages:
        require_members(stage, {"id", "result"})
        if stage["result"] not in STAGE_RESULTS:
            raise ContractError("unknown-stage-result", scenario_id)
        stage_results[stage["id"]] = stage["result"]

    roles = require_object(scenario["artifact_roles"])
    require_members(roles, {"forbidden", "must_appear"})
    forbidden = require_array(roles["forbidden"])
    required = require_array(roles["must_appear"])
    if not all(isinstance(item, str) for item in [*forbidden, *required]):
        raise ContractError("invalid-artifact-role", scenario_id)
    _require_sorted_unique(forbidden, "forbidden-roles-not-sorted")
    _require_sorted_unique(required, "required-roles-not-sorted")
    if set(forbidden) & set(required):
        raise ContractError("artifact-role-conflict", scenario_id)

    gate = require_object(scenario["gate"])
    require_members(gate, {"basis", "decision"})
    gate_decision = gate["decision"]
    if gate_decision == "closed":
        if not TARGET_ROLES.issubset(set(forbidden)):
            raise ContractError("gate-artifact-bypass", scenario_id)
        if any(stage_results[stage_id] == "completed" for stage_id in ("P6", "P7", "P8")):
            raise ContractError("gate-stage-bypass", scenario_id)
    elif gate_decision == "opened":
        if stage_results["P6"] == "not-run":
            raise ContractError("gate-stage-mismatch", scenario_id)
    elif gate_decision == "not-applicable":
        if any(result != "not-applicable" for result in stage_results.values()):
            raise ContractError("not-applicable-stage-mismatch", scenario_id)
    else:
        raise ContractError("unknown-gate-decision", scenario_id)

    cache = require_object(scenario["cache"])
    require_members(cache, {"decision", "identity"})
    if cache["decision"] == "hit" and cache["identity"] != "exact":
        receipt = require_object(scenario["receipt"])
        if receipt.get("outcome") != "rejected":
            raise ContractError("cache-identity-mismatch", scenario_id)

    evidence = require_object(scenario["evidence"])
    require_members(
        evidence,
        {
            "availability",
            "conclusion",
            "remaining_trust",
            "required_results",
            "uncovered",
        },
    )
    for field in ("remaining_trust", "uncovered"):
        values = require_array(evidence[field])
        if not all(isinstance(item, str) for item in values):
            raise ContractError("invalid-evidence-list", scenario_id)
        _require_sorted_unique(values, f"{field.replace('_', '-')}-not-sorted")
    required_results = require_array(evidence["required_results"])
    result_keys = []
    for result in required_results:
        item = require_object(result)
        allowed = {"kind", "status"}
        if "reason" in item:
            allowed.add("reason")
        require_members(item, allowed)
        result_keys.append((item["kind"], item["status"]))
    if result_keys != sorted(set(result_keys)):
        raise ContractError("obligation-results-not-sorted", scenario_id)

    independent = require_object(scenario["independent"])
    require_members(independent, {"codes", "outcome", "process", "process_codes"})
    codes = require_array(independent["codes"])
    if not all(isinstance(item, str) for item in codes):
        raise ContractError("invalid-independent-code", scenario_id)
    _require_sorted_unique(codes, "independent-codes-not-sorted")
    unknown_codes = sorted(set(codes) - _independent_codes())
    if unknown_codes:
        raise ContractError("independent-code-unknown", unknown_codes[0])
    process_codes = require_array(independent["process_codes"])
    if not all(isinstance(item, str) for item in process_codes):
        raise ContractError("invalid-process-code", scenario_id)
    _require_sorted_unique(process_codes, "process-codes-not-sorted")
    if independent["process"] == "failed" and independent["outcome"] != "not-produced":
        raise ContractError("process-outcome-mismatch", scenario_id)
    if independent["outcome"] == "not-produced" and codes:
        raise ContractError("not-produced-has-result-code", scenario_id)
    if independent["process"] == "failed" and not process_codes:
        raise ContractError("process-code-missing", scenario_id)
    if independent["process"] != "failed" and process_codes:
        raise ContractError("process-code-unexpected", scenario_id)
    if scenario["bundle"] == "missing" and independent["outcome"] in {
        "accepted",
        "accepted-with-trust",
    }:
        raise ContractError("bundle-outcome-mismatch", scenario_id)
    if independent["outcome"] == "accepted" and evidence["remaining_trust"]:
        raise ContractError("trust-outcome-mismatch", scenario_id)
    if (
        independent["outcome"] == "accepted-with-trust"
        and not evidence["remaining_trust"]
    ):
        raise ContractError("trust-outcome-mismatch", scenario_id)

    receipt = require_object(scenario["receipt"])
    require_members(receipt, {"availability", "codes", "outcome"})
    receipt_codes = require_array(receipt["codes"])
    if not all(isinstance(item, str) for item in receipt_codes):
        raise ContractError("invalid-receipt-code", scenario_id)
    _require_sorted_unique(receipt_codes, "receipt-codes-not-sorted")
    if receipt["availability"] == "invalid-input" and receipt["outcome"] != "rejected":
        raise ContractError("receipt-outcome-mismatch", scenario_id)

    _verify_bound_artifacts(scenario["input"])
    expected = expected_by_id.get(scenario_id)
    if expected is None:
        raise ContractError("unknown-scenario", scenario_id)
    expected_evidence = expected["evidence"]
    if len(required_results) < len(expected_evidence["required_results"]):
        raise ContractError("obligation-omission", scenario_id)
    if evidence["conclusion"] != expected_evidence["conclusion"]:
        raise ContractError("conclusion-aggregation", scenario_id)
    if scenario != expected:
        raise ContractError("scenario-definition-mismatch", scenario_id)


def validate_manifest_bytes(data: bytes, expected: dict[str, Any]) -> dict[str, Any]:
    root = require_object(parse_canonical(data))
    require_members(root, MANIFEST_MEMBERS)
    if root["format"] != FORMAT:
        raise ContractError("unsupported-format")
    if root["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    if root["profile"] != PROFILE:
        raise ContractError("unsupported-profile")
    if root["platforms"] != list(PLATFORMS):
        raise ContractError("platform-set-mismatch")
    if root["profiles"] != _profiles():
        raise ContractError("profile-set-mismatch")
    if root["observation"] != {"level": "specified", "observed_scenarios": "0"}:
        raise ContractError("observation-overclaim")

    binding_values = require_array(root["bindings"])
    binding_names = []
    for value in binding_values:
        binding = require_object(value)
        allowed = {"name", "path", "raw_sha256"}
        if "registry_digest" in binding:
            allowed.add("registry_digest")
        if "task_digest" in binding:
            allowed.add("task_digest")
        require_members(binding, allowed)
        binding_names.append(require_stable_id(binding["name"]))
        path = (REPO_ROOT / binding["path"]).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise ContractError("binding-path-escape", binding["name"]) from exc
        if not path.is_file():
            raise ContractError("binding-missing", binding["name"])
        if raw_digest(path.read_bytes()) != require_digest(binding["raw_sha256"]):
            raise ContractError("binding-digest-mismatch", binding["name"])
    _require_sorted_unique(binding_names, "bindings-not-sorted")

    requirement_values = require_array(root["requirements"])
    requirement_ids = []
    for value in requirement_values:
        requirement = require_object(value)
        require_members(requirement, {"binding", "id", "locator"})
        requirement_ids.append(require_stable_id(requirement["id"]))
        if requirement["binding"] not in binding_names:
            raise ContractError("requirement-binding-unknown", requirement["id"])
    _require_sorted_unique(requirement_ids, "requirements-not-sorted")
    if root["requirement_count"] != str(len(requirement_ids)):
        raise ContractError("requirement-count-mismatch")

    scenario_values = require_array(root["scenarios"])
    scenario_ids = [require_object(item).get("id") for item in scenario_values]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ContractError("duplicate-scenario")
    if scenario_ids != sorted(scenario_ids):
        raise ContractError("scenarios-not-sorted")
    expected_by_id = {item["id"]: item for item in expected["scenarios"]}
    for scenario in scenario_values:
        _validate_scenario(require_object(scenario), expected_by_id)

    coverage_values = require_array(root["coverage"])
    coverage_ids = []
    for value in coverage_values:
        coverage = require_object(value)
        require_members(coverage, {"requirement", "scenarios"})
        coverage_id = require_stable_id(coverage["requirement"])
        coverage_ids.append(coverage_id)
        covered = require_array(coverage["scenarios"])
        if not covered or any(item not in scenario_ids for item in covered):
            raise ContractError("coverage-scenario-unknown", coverage_id)
        _require_sorted_unique(covered, "coverage-scenarios-not-sorted")
    if coverage_ids != requirement_ids:
        raise ContractError("coverage-mismatch")

    if root["scenario_counts"] != expected["scenario_counts"]:
        raise ContractError("scenario-count-mismatch")
    if root != expected:
        raise ContractError("manifest-definition-mismatch")
    return root


def _mutate(
    manifest: dict[str, Any], callback: Callable[[dict[str, Any]], None]
) -> bytes:
    value = copy.deepcopy(manifest)
    callback(value)
    return canonical_bytes(value)


def _find_scenario(value: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    return next(item for item in value["scenarios"] if item["id"] == scenario_id)


def negative_fixtures(
    manifest: dict[str, Any],
) -> dict[str, tuple[bytes, str]]:
    values: dict[str, tuple[bytes, str]] = {}

    def add(
        name: str,
        callback: Callable[[dict[str, Any]], None],
        code: str,
    ) -> None:
        values[f"{name}.invalid.jcs"] = (_mutate(manifest, callback), code)

    add("unknown-member", lambda value: value.__setitem__("unexpected", True), "unknown-member")
    add("unknown-version", lambda value: value.__setitem__("format_version", "0.2"), "unsupported-version")
    add(
        "unknown-profile",
        lambda value: _find_scenario(value, "AX-B01-CORRECT").__setitem__(
            "profile", "latest"
        ),
        "unsupported-profile",
    )
    add(
        "gate-bypass",
        lambda value: _find_scenario(value, "AX-B01-BACKEND-TIMEOUT")[
            "gate"
        ].__setitem__("decision", "opened"),
        "gate-stage-mismatch",
    )
    add(
        "obligation-omission",
        lambda value: _find_scenario(value, "AX-B01-CORRECT")["evidence"][
            "required_results"
        ].pop(),
        "obligation-omission",
    )
    add(
        "artifact-tamper",
        lambda value: _find_scenario(value, "AX-B01-CORRECT")["input"][
            "candidate"
        ].__setitem__("sha256", "sha256:" + "f" * 64),
        "artifact-digest-mismatch",
    )
    add(
        "cache-forged-hit",
        lambda value: _find_scenario(value, "PIPE-CACHE-REUSE-01")[
            "cache"
        ].__setitem__("identity", "mismatch"),
        "cache-identity-mismatch",
    )
    add(
        "missing-bundle-accepted",
        lambda value: _find_scenario(value, "CHK-BUNDLE-01")[
            "independent"
        ].__setitem__("outcome", "accepted"),
        "bundle-outcome-mismatch",
    )
    add(
        "attestation-overreach",
        lambda value: _find_scenario(value, "CHK-PROOF-02")[
            "independent"
        ].__setitem__("outcome", "accepted"),
        "trust-outcome-mismatch",
    )
    add(
        "conclusion-aggregation",
        lambda value: _find_scenario(value, "AX-B01-WRONG-ADD")[
            "evidence"
        ].__setitem__("conclusion", "satisfied"),
        "conclusion-aggregation",
    )
    add(
        "process-failure-disguised",
        lambda value: _find_scenario(value, "CHK-PROCESS-01")[
            "independent"
        ].__setitem__("outcome", "rejected"),
        "process-outcome-mismatch",
    )
    add(
        "duplicate-scenario",
        lambda value: value["scenarios"].append(
            copy.deepcopy(value["scenarios"][-1])
        ),
        "duplicate-scenario",
    )
    add(
        "unsorted-scenarios",
        lambda value: value["scenarios"].reverse(),
        "scenarios-not-sorted",
    )
    return values


def generated_contract(
    output_bytes: dict[str, bytes],
    manifest: dict[str, Any],
    negatives: dict[str, tuple[bytes, str]],
) -> dict[str, Any]:
    generator_paths = [
        Path("scripts/generate-implementation-readiness.py"),
        *sorted((REPO_ROOT / "scripts/implementation_readiness").glob("*.py")),
    ]
    generator_files = []
    for path in generator_paths:
        relative = path if not path.is_absolute() else path.relative_to(REPO_ROOT)
        data = (REPO_ROOT / relative).read_bytes()
        generator_files.append(
            {"path": relative.as_posix(), "raw_sha256": raw_digest(data)}
        )
    return {
        "bindings": manifest["bindings"],
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "generated_files": [
            {
                "byte_length": str(len(data)),
                "path": path,
                "sha256": raw_digest(data),
            }
            for path, data in sorted(output_bytes.items())
        ],
        "generator_files": generator_files,
        "manifest_document_digest": document_digest(manifest),
        "manifest_raw_sha256": raw_digest(canonical_bytes(manifest)),
        "negative_fixture_count": str(len(negatives)),
        "observation_level": "specified",
        "profile": PROFILE,
        "scenario_counts": manifest["scenario_counts"],
    }


def build_outputs() -> dict[Path, bytes]:
    manifest = build_manifest()
    manifest_bytes = canonical_bytes(manifest)
    validate_manifest_bytes(manifest_bytes, manifest)
    negatives = negative_fixtures(manifest)
    for name, (data, expected_code) in negatives.items():
        try:
            validate_manifest_bytes(data, manifest)
        except ContractError as exc:
            if exc.code != expected_code:
                raise ValueError(
                    f"negative fixture {name} returned {exc.code}, expected {expected_code}"
                ) from exc
        else:
            raise ValueError(f"negative fixture unexpectedly accepted: {name}")

    expected_index = {
        "negative": [
            {
                "expected_code": code,
                "path": f"fixtures/negative/{name}",
                "sha256": raw_digest(data),
            }
            for name, (data, code) in sorted(negatives.items())
        ],
        "positive": {
            "document_digest": document_digest(manifest),
            "path": "manifest.jcs",
            "sha256": raw_digest(manifest_bytes),
        },
    }
    output_bytes: dict[str, bytes] = {
        "fixtures/negative/expected.json": pretty_bytes(expected_index),
        "manifest.jcs": manifest_bytes,
        "schemas/implementation-readiness-manifest.schema.json": pretty_bytes(
            manifest_schema()
        ),
    }
    for name, (data, _) in negatives.items():
        output_bytes[f"fixtures/negative/{name}"] = data
    contract = generated_contract(output_bytes, manifest, negatives)
    output_bytes["contract.json"] = pretty_bytes(contract)
    return {CONTRACT_ROOT / path: data for path, data in output_bytes.items()}


def write_outputs(expected: dict[Path, bytes]) -> None:
    for path, data in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(
        f"wrote implementation readiness contract ({len(expected)} generated files)"
    )


def check_outputs(expected: dict[Path, bytes]) -> int:
    errors = []
    for path, data in expected.items():
        if not path.is_file():
            errors.append(f"missing generated file: {path.relative_to(REPO_ROOT)}")
        elif path.read_bytes() != data:
            errors.append(f"generated file drifted: {path.relative_to(REPO_ROOT)}")
    expected_paths = {
        path.relative_to(CONTRACT_ROOT).as_posix() for path in expected
    }
    if CONTRACT_ROOT.is_dir():
        for path in CONTRACT_ROOT.rglob("*"):
            if not path.is_file() or path.name == "README.md":
                continue
            relative = path.relative_to(CONTRACT_ROOT).as_posix()
            if relative not in expected_paths:
                errors.append(
                    f"unexpected generated file: {path.relative_to(REPO_ROOT)}"
                )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        f"implementation readiness contract passed ({len(expected)} generated files)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = build_outputs()
    if args.write:
        write_outputs(expected)
        return 0
    return check_outputs(expected)
