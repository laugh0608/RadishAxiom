"""Reuse and materialize the frozen Independent Check Contract v0.1 protocol."""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from .common import (
    NORMATIVE_SPECS,
    REPO_ROOT,
    artifact_descriptor,
    canonical_bytes,
    content_id,
    raw_digest,
)


CHECKER_BYTES = b"radishaxiom-independent-checker-go-specified-v0.1\n"
CHECKER_SOURCE_BYTES = b"radishaxiom-independent-checker-go-source-specified-v0.1\n"
DEFAULT_CODES = {
    "conclusion-recompute": "result-aggregation",
    "concrete-check-replay": "concrete-check-mismatch",
    "counterexample-replay": "minimality-unsupported",
    "identity": "manifest-coverage",
    "isolation-report": "isolation-boundary-violation",
    "obligation-reconstruction": "obligation-mismatch",
    "proof-support": "proof-support-mismatch",
    "state-support": "invalid-state-support",
    "strict-parse": "noncanonical-json",
    "subject": "subject-mismatch",
}


@lru_cache(maxsize=1)
def independent_contract() -> ModuleType:
    path = REPO_ROOT / "scripts/generate-independent-check-contracts.py"
    spec = importlib.util.spec_from_file_location(
        "radishaxiom_independent_check_contract_v0_1", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load independent contract generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_manifest(
    *,
    evidence_bytes: bytes,
    ir_digest: str,
    materials: dict[str, tuple[bytes, str, str]],
) -> tuple[dict[str, Any], dict[str, tuple[bytes, str, str]], dict[str, list[str]]]:
    all_materials = dict(materials)
    evidence_digest = raw_digest(evidence_bytes)
    all_materials[evidence_digest] = (evidence_bytes, "axiom-evidence", "0.1")
    roles: dict[str, set[str]] = {
        digest: {"evidence-artifact"} for digest in all_materials
    }
    roles[evidence_digest] = {"evidence"}
    roles.setdefault(ir_digest, set()).add("subject")

    for _, path, format_name, version in NORMATIVE_SPECS:
        data = (REPO_ROOT / path).read_bytes()
        digest = raw_digest(data)
        all_materials[digest] = (data, format_name, version)
        roles.setdefault(digest, set()).add("normative-spec")

    artifacts = []
    for digest, (data, format_name, version) in all_materials.items():
        descriptor = artifact_descriptor(data, format_name, version)
        descriptor["roles"] = sorted(roles[digest])
        artifacts.append(descriptor)
    manifest = {
        "artifacts": sorted(artifacts, key=lambda item: item["content_digest"]),
        "bundle_version": "0.1",
    }
    independent_contract().validate_manifest(manifest)
    return manifest, all_materials, {
        digest: sorted(value) for digest, value in roles.items()
    }


def build_request(
    *,
    evidence_digest: str,
    manifest_bytes: bytes,
    allowed_trust_categories: list[str],
    proof_support: str,
    semantic_steps: str = "1000000",
) -> dict[str, Any]:
    module = independent_contract()
    request = module.base_request(evidence_digest, raw_digest(manifest_bytes))
    request["assurance_policy"] = {
        "allowed_trust_categories": sorted(set(allowed_trust_categories)),
        "proof_support": proof_support,
    }
    for item in request["limits"]:
        if item["name"] == "semantic-steps":
            item["value"] = semantic_steps
    module.validate_request(request)
    return request


def _check(
    kind: str,
    outcome: str,
    code: str,
    refs: list[dict[str, str]],
) -> dict[str, Any]:
    definition = {
        "codes": [code],
        "kind": kind,
        "outcome": outcome,
        "refs": sorted(refs, key=lambda item: (item["kind"], item["ref"])),
    }
    return {
        "definition": definition,
        "id": content_id("axiom-independent-check-v0.1:check", definition),
    }


def build_expected_result(
    *,
    request: dict[str, Any],
    request_bytes: bytes,
    evidence: dict[str, Any],
    evidence_bytes: bytes,
    outcome: str,
    remaining_trust: list[str],
    special_kind: str | None = None,
    special_code: str | None = None,
    special_outcome: str | None = None,
    missing_artifacts: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    checks = []
    trust_refs = [{"kind": "trust", "ref": value} for value in remaining_trust]
    for kind in independent_contract().CHECK_KINDS:
        check_outcome = "passed"
        code = DEFAULT_CODES[kind]
        refs: list[dict[str, str]] = []
        if kind == "strict-parse":
            refs.append({"kind": "artifact", "ref": raw_digest(evidence_bytes)})
        elif kind == "identity":
            refs.append({"kind": "request", "ref": raw_digest(request_bytes)})
        elif kind == "subject":
            refs.append({"kind": "artifact", "ref": evidence["subject"]["ir_artifact"]})
        elif kind == "obligation-reconstruction":
            refs.extend(
                {"kind": "obligation", "ref": item["id"]}
                for item in evidence["obligations"]
            )
        elif kind == "state-support":
            refs.extend(trust_refs)
        elif kind == "proof-support":
            refs.extend(trust_refs)
            if "proof-backend" in {
                item["definition"]["category"] for item in evidence["trust"]
            } and outcome == "accepted-with-trust":
                check_outcome = "trusted"
        elif kind == "conclusion-recompute":
            refs.extend(
                {"kind": "obligation", "ref": value}
                for value in evidence["conclusion"]["refs"]
            )
        if kind == special_kind:
            check_outcome = special_outcome or check_outcome
            code = special_code or code
        checks.append(_check(kind, check_outcome, code, refs))
    checks.sort(key=lambda item: item["id"])
    check_by_kind = {item["definition"]["kind"]: item for item in checks}

    if outcome == "accepted":
        result_variant: dict[str, Any] = {"kind": "accepted"}
    else:
        ref_kind = special_kind
        if ref_kind is None:
            ref_kind = "proof-support" if remaining_trust else "state-support"
        result_variant = {"kind": outcome, "refs": [check_by_kind[ref_kind]["id"]]}

    checker_artifact = raw_digest(CHECKER_BYTES)
    result = {
        "checker": {
            "artifact": checker_artifact,
            "name": "radishaxiom-independent-checker-go",
            "source": raw_digest(CHECKER_SOURCE_BYTES),
            "toolchain": "go1.26.7",
            "version": "0.1-specified",
        },
        "checks": checks,
        "evidence": {
            "content_digest": raw_digest(evidence_bytes),
            "document_digest": {
                "kind": "available",
                "value": content_id("axiom-evidence-v0.1:document", evidence),
            },
        },
        "missing_artifacts": sorted(set(missing_artifacts or [])),
        "remaining_trust": sorted(set(remaining_trust)),
        "request": {
            "content_digest": raw_digest(request_bytes),
            "document_digest": {
                "kind": "available",
                "value": content_id(
                    "axiom-independent-check-v0.1:request", request
                ),
            },
        },
        "result": result_variant,
        "result_version": "0.1",
        "tcb": [
            {
                "artifact": checker_artifact,
                "category": category,
                "version": "0.1-specified",
            }
            for category in independent_contract().REQUIRED_TCB_CATEGORIES
        ],
    }
    independent_contract().validate_result(result)
    significant = check_by_kind[special_kind] if special_kind else check_by_kind[
        "proof-support" if remaining_trust else "state-support"
    ]
    return result, {
        "check_id": significant["id"],
        "document_digest": content_id(
            "axiom-independent-check-v0.1:result", result
        ),
    }


def build_process_failure(
    request: dict[str, Any], request_bytes: bytes, code: str
) -> dict[str, Any]:
    return {
        "code": code,
        "format": "axiom-checker-invocation-failure",
        "format_version": "0.1",
        "request": {
            "content_digest": raw_digest(request_bytes),
            "document_digest": content_id(
                "axiom-independent-check-v0.1:request", request
            ),
        },
        "result": "not-produced",
    }
