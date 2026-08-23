"""Materialize benchmark, cross-contract, and negative checker bundles."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .common import (
    BENCHMARK_ROOT,
    REPO_ROOT,
    canonical_bytes,
    content_id,
    digest_hex,
    load_json,
    raw_digest,
    read_bound,
    slug_for,
)
from .evidence import BACKEND_BYTES, build_evidence, build_trust
from .obligations import build_obligation_set, build_obligations
from .pipeline import (
    TOOL_BYTES,
    build_pipeline_materials,
    build_query,
    build_response,
    production_tool,
)
from .protocol import (
    build_expected_result,
    build_manifest,
    build_process_failure,
    build_request,
)


CROSS_SCENARIOS = (
    "CHK-CONCRETE-01",
    "CHK-PROCESS-01",
    "CHK-PROOF-01",
    "CHK-PROOF-02",
    "CHK-RESOURCE-01",
)
NEGATIVE_SCENARIOS = (
    "CHK-BUNDLE-01",
    "CHK-DIGEST-01",
    "CHK-OBLIGATION-01",
)


@dataclass
class BuiltScenario:
    scenario_id: str
    files: dict[str, bytes]
    index: dict[str, Any]
    evidence: dict[str, Any]
    evidence_bytes: bytes
    manifest: dict[str, Any]
    manifest_bytes: bytes
    materials: dict[str, tuple[bytes, str, str]]
    request: dict[str, Any]
    request_bytes: bytes
    trust_ids: list[str]


def _backend_tool_id() -> str:
    from .common import entry

    return entry(
        "axiom-evidence-v0.1:tool",
        {
            "artifact": raw_digest(BACKEND_BYTES),
            "name": "cvc5-specified-fixture-backend",
            "roles": ["prover"],
            "version": "1.3.4-specified",
        },
    )["id"]


def _scenario_files(
    *,
    scenario_id: str,
    manifest_bytes: bytes,
    request_bytes: bytes,
    materials: dict[str, tuple[bytes, str, str]],
    expected_name: str,
    expected_bytes: bytes,
    omit_blob: str | None = None,
    replace_blob: tuple[str, bytes] | None = None,
) -> dict[str, bytes]:
    root = f"s/{slug_for(scenario_id)}"
    files = {
        f"{root}/bundle/manifest.jcs": manifest_bytes,
        f"{root}/bundle/request.jcs": request_bytes,
        f"{root}/{expected_name}": expected_bytes,
    }
    for digest, (data, _, _) in materials.items():
        if digest == omit_blob:
            continue
        if replace_blob is not None and digest == replace_blob[0]:
            data = replace_blob[1]
        files[f"{root}/bundle/blobs/sha256/{digest_hex(digest)}"] = data
    return files


def _index_entry(
    *,
    readiness: dict[str, Any],
    manifest_bytes: bytes,
    request: dict[str, Any],
    request_bytes: bytes,
    evidence: dict[str, Any],
    evidence_bytes: bytes,
    expected_kind: str,
    expected_bytes: bytes,
    expected_document_digest: str,
    expected_check_id: str | None,
    materialization: str,
) -> dict[str, Any]:
    expected = {
        "codes": readiness["independent"]["codes"],
        "content_digest": raw_digest(expected_bytes),
        "document_digest": expected_document_digest,
        "kind": expected_kind,
        "outcome": readiness["independent"]["outcome"],
        "process": readiness["independent"]["process"],
        "process_codes": readiness["independent"]["process_codes"],
    }
    if expected_check_id is not None:
        expected["check_id"] = expected_check_id
    return {
        "bundle": {
            "manifest_content_digest": raw_digest(manifest_bytes),
            "manifest_document_digest": content_id(
                "axiom-independent-check-v0.1:bundle-manifest",
                load_json_bytes(manifest_bytes),
            ),
            "materialization": materialization,
            "path": f"s/{slug_for(readiness['id'])}/bundle",
        },
        "evidence": {
            "conclusion": evidence["conclusion"]["kind"],
            "content_digest": raw_digest(evidence_bytes),
            "document_digest": content_id(
                "axiom-evidence-v0.1:document", evidence
            ),
        },
        "expected": expected,
        "kind": readiness["kind"],
        "level": "specified",
        "readiness_scenario_id": readiness["id"],
        "request": {
            "content_digest": raw_digest(request_bytes),
            "document_digest": content_id(
                "axiom-independent-check-v0.1:request", request
            ),
        },
    }


def load_json_bytes(data: bytes) -> dict[str, Any]:
    import json

    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _preliminary_obligation_set(
    *,
    ir: dict[str, Any],
    ir_bytes: bytes,
    ir_document_digest: str,
    input_digests: list[str],
    golden_digests: list[str],
    actual_output_digests: list[str],
    trust_categories: list[str],
    profile: str,
) -> tuple[list[dict[str, Any]], bytes]:
    trust = build_trust(
        trust_categories,
        ir_document_digest,
        None,
        production_tool()["id"],
        _backend_tool_id(),
    )
    obligations = build_obligations(
        ir,
        ir_document_digest,
        input_digests,
        golden_digests,
        actual_output_digests,
        trust,
        profile=profile,
    )
    obligation_set = build_obligation_set(
        raw_digest(ir_bytes),
        ir_document_digest,
        obligations,
        profile=profile,
    )
    return obligations, canonical_bytes(obligation_set)


def _fixture_materials(
    readiness: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[str],
    list[str],
    dict[str, tuple[bytes, str, str]],
]:
    fixture_values = []
    input_digests = []
    golden_digests = []
    materials: dict[str, tuple[bytes, str, str]] = {}
    for fixture in readiness["input"]["fixtures"]:
        input_binding = fixture["input"]
        input_bytes = read_bound(input_binding["path"], input_binding["sha256"])
        input_digest = raw_digest(input_bytes)
        fixture_values.append(load_json(REPO_ROOT / input_binding["path"]))
        input_digests.append(input_digest)
        materials[input_digest] = (input_bytes, "axiom-benchmark-data", "0.1")
        golden = fixture["golden"]
        if golden["materialization"] == "bound-artifact":
            golden_bytes = read_bound(golden["path"], golden["sha256"])
            golden_digest = raw_digest(golden_bytes)
            golden_digests.append(golden_digest)
            materials[golden_digest] = (
                golden_bytes,
                "axiom-benchmark-data",
                "0.1",
            )
    return fixture_values, input_digests, golden_digests, materials


def _materialize(
    *,
    readiness: dict[str, Any],
    ir: dict[str, Any],
    ir_bytes: bytes,
    ir_document_digest: str,
    assertion: dict[str, Any],
    fixture_values: list[dict[str, Any]],
    input_digests: list[str],
    golden_digests: list[str],
    actual_output_digests: list[str],
    external_materials: dict[str, tuple[bytes, str, str]],
    trust_categories: list[str],
    uncovered_categories: list[str],
    profile: str,
    proof_mode: str,
    proof_support: str,
    receipt_required: bool,
    concrete_mismatch: bool = False,
    semantic_steps: str = "1000000",
    result_special: tuple[str, str, str] | None = None,
    process_failure_code: str | None = None,
) -> BuiltScenario:
    obligations, obligation_set_bytes = _preliminary_obligation_set(
        ir=ir,
        ir_bytes=ir_bytes,
        ir_document_digest=ir_document_digest,
        input_digests=input_digests,
        golden_digests=golden_digests,
        actual_output_digests=actual_output_digests,
        trust_categories=trust_categories,
        profile=profile,
    )
    if receipt_required:
        stage_states = {item["id"]: item["result"] for item in readiness["stages"]}
        pipeline_materials, receipt_bytes, pipeline_meta = build_pipeline_materials(
            scenario_id=readiness["id"],
            ir_bytes=ir_bytes,
            obligation_set_bytes=obligation_set_bytes,
            obligation_ids=[item["id"] for item in obligations],
            input_digests=input_digests,
            golden_digests=golden_digests,
            actual_output_digests=actual_output_digests,
            external_materials=external_materials,
            stage_states=stage_states,
            gate_decision=readiness["gate"]["decision"],
            receipt_outcome=readiness["receipt"]["outcome"],
            proof_failed=assertion["expected_conclusion"] == "violated",
        )
    else:
        query_bytes = build_query(readiness["id"], [item["id"] for item in obligations])
        response_bytes = build_response("unsat")
        query_digest = raw_digest(query_bytes)
        response_digest = raw_digest(response_bytes)
        tool = production_tool()
        pipeline_materials = {
            raw_digest(ir_bytes): (ir_bytes, "axiom-ir", "0.1"),
            raw_digest(obligation_set_bytes): (
                obligation_set_bytes,
                "axiom-obligation-set",
                "0.1",
            ),
            query_digest: (query_bytes, "axiom-smtlib2-qf-uflia-query", "0.1"),
            response_digest: (response_bytes, "cvc5-response", "1.3.4"),
            raw_digest(TOOL_BYTES): (TOOL_BYTES, "synthetic-contract-tool", "0.1"),
            **external_materials,
        }
        receipt_bytes = None
        pipeline_meta = {
            "query": query_digest,
            "response": response_digest,
            "target": raw_digest(b"not-applicable-target"),
            "tool": tool,
        }

    evidence_bytes, rebuilt_obligations, materials, evidence_meta = build_evidence(
        scenario_id=readiness["id"],
        ir=ir,
        ir_bytes=ir_bytes,
        ir_document_digest=ir_document_digest,
        assertion=assertion,
        fixture_values=fixture_values,
        input_digests=input_digests,
        golden_digests=golden_digests,
        actual_output_digests=actual_output_digests,
        materials=pipeline_materials,
        receipt_bytes=receipt_bytes,
        pipeline_meta=pipeline_meta,
        trust_categories=trust_categories,
        uncovered_categories=uncovered_categories,
        profile=profile,
        proof_mode=proof_mode,
        concrete_mismatch=concrete_mismatch,
    )
    if rebuilt_obligations != obligation_set_bytes:
        raise ValueError(f"obligation set changed across receipt boundary: {readiness['id']}")
    evidence = load_json_bytes(evidence_bytes)
    manifest, bundle_materials, _ = build_manifest(
        evidence_bytes=evidence_bytes,
        ir_digest=raw_digest(ir_bytes),
        materials=materials,
    )
    manifest_bytes = canonical_bytes(manifest)
    request = build_request(
        evidence_digest=raw_digest(evidence_bytes),
        manifest_bytes=manifest_bytes,
        allowed_trust_categories=trust_categories,
        proof_support=proof_support,
        semantic_steps=semantic_steps,
    )
    request_bytes = canonical_bytes(request)

    if process_failure_code is None:
        special_kind = special_code = special_outcome = None
        if result_special is not None:
            special_kind, special_code, special_outcome = result_special
        result, result_meta = build_expected_result(
            request=request,
            request_bytes=request_bytes,
            evidence=evidence,
            evidence_bytes=evidence_bytes,
            outcome=readiness["independent"]["outcome"],
            remaining_trust=evidence_meta["remaining_trust"],
            special_kind=special_kind,
            special_code=special_code,
            special_outcome=special_outcome,
        )
        expected_bytes = canonical_bytes(result)
        expected_name = "expected-result.jcs"
        expected_kind = "independent-result"
        expected_document_digest = result_meta["document_digest"]
        expected_check_id = result_meta["check_id"]
    else:
        failure = build_process_failure(request, request_bytes, process_failure_code)
        expected_bytes = canonical_bytes(failure)
        expected_name = "expected-process-failure.jcs"
        expected_kind = "process-failure"
        expected_document_digest = content_id(
            "axiom-checker-bundle-v0.1:process-failure", failure
        )
        expected_check_id = None

    files = _scenario_files(
        scenario_id=readiness["id"],
        manifest_bytes=manifest_bytes,
        request_bytes=request_bytes,
        materials=bundle_materials,
        expected_name=expected_name,
        expected_bytes=expected_bytes,
    )
    index = _index_entry(
        readiness=readiness,
        manifest_bytes=manifest_bytes,
        request=request,
        request_bytes=request_bytes,
        evidence=evidence,
        evidence_bytes=evidence_bytes,
        expected_kind=expected_kind,
        expected_bytes=expected_bytes,
        expected_document_digest=expected_document_digest,
        expected_check_id=expected_check_id,
        materialization="complete",
    )
    return BuiltScenario(
        scenario_id=readiness["id"],
        files=files,
        index=index,
        evidence=evidence,
        evidence_bytes=evidence_bytes,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        materials=bundle_materials,
        request=request,
        request_bytes=request_bytes,
        trust_ids=evidence_meta["remaining_trust"],
    )


def build_benchmark_scenario(readiness: dict[str, Any]) -> BuiltScenario:
    candidate = readiness["input"]["candidate"]
    ir_bytes = read_bound(candidate["path"], candidate["sha256"])
    ir = load_json_bytes(ir_bytes)
    assertion_binding = readiness["input"]["scenario_assertion"]
    assertion = load_json(REPO_ROOT / assertion_binding["path"])
    if raw_digest((REPO_ROOT / assertion_binding["path"]).read_bytes()) != assertion_binding["sha256"]:
        raise ValueError(f"scenario assertion drifted: {readiness['id']}")
    fixture_values, input_digests, golden_digests, external = _fixture_materials(
        readiness
    )
    correct = assertion["expected_conclusion"] == "satisfied"
    actual_output_digests = list(golden_digests) if correct else []
    if assertion["expected_conclusion"] == "inconclusive":
        proof_mode = "timeout"
    elif correct:
        proof_mode = "backend-attestation"
    else:
        proof_mode = "kernel-replay"
    return _materialize(
        readiness=readiness,
        ir=ir,
        ir_bytes=ir_bytes,
        ir_document_digest=candidate["document_digest"],
        assertion=assertion,
        fixture_values=fixture_values,
        input_digests=input_digests,
        golden_digests=golden_digests,
        actual_output_digests=actual_output_digests,
        external_materials=external,
        trust_categories=readiness["evidence"]["remaining_trust"],
        uncovered_categories=readiness["evidence"]["uncovered"],
        profile="keyed-finite-table-benchmark",
        proof_mode=proof_mode,
        proof_support="attestation-allowed",
        receipt_required=True,
    )


def _base_ir() -> tuple[dict[str, Any], bytes, str]:
    path = BENCHMARK_ROOT / "ax-b01/candidates/correct.ir.jcs"
    ir_bytes = path.read_bytes()
    task = load_json(BENCHMARK_ROOT / "ax-b01/task.json")
    candidate = next(item for item in task["candidates"] if item["name"] == "correct")
    if raw_digest(ir_bytes) != candidate["canonical"]["sha256"]:
        raise ValueError("AX-B01 correct IR drifted")
    return load_json_bytes(ir_bytes), ir_bytes, candidate["document_digest"]


def build_cross_scenario(readiness: dict[str, Any]) -> BuiltScenario:
    scenario_id = readiness["id"]
    ir, ir_bytes, ir_document_digest = _base_ir()
    if scenario_id == "CHK-CONCRETE-01":
        task = load_json(BENCHMARK_ROOT / "ax-b01/task.json")
        fixture = next(item for item in task["fixtures"] if item["name"] == "base")
        input_bytes = (BENCHMARK_ROOT / fixture["input"]["path"]).read_bytes()
        golden_bytes = (BENCHMARK_ROOT / fixture["golden"]["path"]).read_bytes()
        input_digest = raw_digest(input_bytes)
        golden_digest = raw_digest(golden_bytes)
        actual_value = load_json_bytes(golden_bytes)
        actual_value["tables"][0]["rows"][0]["net_cents"] = "901"
        actual_bytes = canonical_bytes(actual_value)
        actual_digest = raw_digest(actual_bytes)
        external = {
            input_digest: (input_bytes, "axiom-benchmark-data", "0.1"),
            golden_digest: (golden_bytes, "axiom-benchmark-data", "0.1"),
            actual_digest: (actual_bytes, "axiom-benchmark-data", "0.1"),
        }
        assertion = {
            "counterexample": {"kind": "none"},
            "expected_conclusion": "implementation_inconsistent",
            "required_results": [],
        }
        return _materialize(
            readiness=readiness,
            ir=ir,
            ir_bytes=ir_bytes,
            ir_document_digest=ir_document_digest,
            assertion=assertion,
            fixture_values=[load_json_bytes(input_bytes)],
            input_digests=[input_digest],
            golden_digests=[golden_digest],
            actual_output_digests=[actual_digest],
            external_materials=external,
            trust_categories=readiness["evidence"]["remaining_trust"],
            uncovered_categories=[],
            profile="keyed-finite-table-benchmark",
            proof_mode="kernel-replay",
            proof_support="attestation-allowed",
            receipt_required=True,
            concrete_mismatch=True,
            result_special=("concrete-check-replay", "host-output-mismatch", "passed"),
        )

    trust_categories = (
        ["proof-backend"]
        if scenario_id in {"CHK-PROOF-01", "CHK-PROOF-02"}
        else []
    )
    assertion = {
        "counterexample": {"kind": "none"},
        "expected_conclusion": "satisfied",
        "required_results": [],
    }
    options: dict[str, Any] = {
        "proof_mode": "backend-attestation"
        if trust_categories
        else "kernel-replay",
        "proof_support": "certificate-required",
        "semantic_steps": "1000000",
        "result_special": None,
        "process_failure_code": None,
    }
    if scenario_id == "CHK-PROOF-01":
        options["result_special"] = (
            "proof-support",
            "certificate-incomplete",
            "incomplete",
        )
    elif scenario_id == "CHK-PROOF-02":
        options["proof_support"] = "attestation-allowed"
    elif scenario_id == "CHK-RESOURCE-01":
        options["semantic_steps"] = "1"
        options["result_special"] = (
            "obligation-reconstruction",
            "obligation-mismatch",
            "incomplete",
        )
    elif scenario_id == "CHK-PROCESS-01":
        options["process_failure_code"] = "checker-process-failure"
    else:
        raise ValueError(f"unsupported cross scenario: {scenario_id}")
    return _materialize(
        readiness=readiness,
        ir=ir,
        ir_bytes=ir_bytes,
        ir_document_digest=ir_document_digest,
        assertion=assertion,
        fixture_values=[],
        input_digests=[],
        golden_digests=[],
        actual_output_digests=[],
        external_materials={},
        trust_categories=trust_categories,
        uncovered_categories=readiness["evidence"]["uncovered"],
        profile="keyed-finite-table-verification",
        proof_mode=options["proof_mode"],
        proof_support=options["proof_support"],
        receipt_required=False,
        semantic_steps=options["semantic_steps"],
        result_special=options["result_special"],
        process_failure_code=options["process_failure_code"],
    )


def _negative_result(
    *,
    readiness: dict[str, Any],
    base: BuiltScenario,
    request: dict[str, Any],
    request_bytes: bytes,
    evidence: dict[str, Any],
    evidence_bytes: bytes,
    special_kind: str,
    special_code: str,
    special_outcome: str,
    missing_artifacts: list[str] | None = None,
) -> tuple[bytes, dict[str, str]]:
    result, meta = build_expected_result(
        request=request,
        request_bytes=request_bytes,
        evidence=evidence,
        evidence_bytes=evidence_bytes,
        outcome=readiness["independent"]["outcome"],
        remaining_trust=base.trust_ids,
        special_kind=special_kind,
        special_code=special_code,
        special_outcome=special_outcome,
        missing_artifacts=missing_artifacts,
    )
    return canonical_bytes(result), meta


def build_negative_scenario(
    readiness: dict[str, Any], base: BuiltScenario
) -> BuiltScenario:
    scenario_id = readiness["id"]
    request = base.request
    request_bytes = base.request_bytes
    manifest = base.manifest
    manifest_bytes = base.manifest_bytes
    evidence = base.evidence
    evidence_bytes = base.evidence_bytes
    materials = dict(base.materials)
    omit_blob = None
    replace_blob = None

    if scenario_id == "CHK-BUNDLE-01":
        omit_blob = next(
            item["content_digest"]
            for item in manifest["artifacts"]
            if item["format"] == "axiom-smtlib2-qf-uflia-query"
        )
        expected_bytes, meta = _negative_result(
            readiness=readiness,
            base=base,
            request=request,
            request_bytes=request_bytes,
            evidence=evidence,
            evidence_bytes=evidence_bytes,
            special_kind="identity",
            special_code="artifact-missing",
            special_outcome="incomplete",
            missing_artifacts=[omit_blob],
        )
        materialization = "missing"
    elif scenario_id == "CHK-DIGEST-01":
        target_digest = evidence["subject"]["ir_artifact"]
        original = materials[target_digest][0]
        replace_blob = (
            target_digest,
            bytes([original[0] ^ 1]) + original[1:],
        )
        expected_bytes, meta = _negative_result(
            readiness=readiness,
            base=base,
            request=request,
            request_bytes=request_bytes,
            evidence=evidence,
            evidence_bytes=evidence_bytes,
            special_kind="identity",
            special_code="digest-mismatch",
            special_outcome="rejected",
        )
        materialization = "tampered"
    elif scenario_id == "CHK-OBLIGATION-01":
        evidence = copy.deepcopy(base.evidence)
        omitted = next(
            item
            for item in evidence["obligations"]
            if item["definition"]["kind"] == "numeric-range"
        )
        evidence["obligations"] = [
            item for item in evidence["obligations"] if item["id"] != omitted["id"]
        ]
        evidence_bytes = canonical_bytes(evidence)
        manifest, materials, _ = build_manifest(
            evidence_bytes=evidence_bytes,
            ir_digest=evidence["subject"]["ir_artifact"],
            materials={
                digest: value
                for digest, value in base.materials.items()
                if value[1] != "axiom-evidence"
            },
        )
        manifest_bytes = canonical_bytes(manifest)
        request = build_request(
            evidence_digest=raw_digest(evidence_bytes),
            manifest_bytes=manifest_bytes,
            allowed_trust_categories=[
                item["definition"]["category"] for item in evidence["trust"]
            ],
            proof_support="attestation-allowed",
        )
        request_bytes = canonical_bytes(request)
        expected_bytes, meta = _negative_result(
            readiness=readiness,
            base=base,
            request=request,
            request_bytes=request_bytes,
            evidence=evidence,
            evidence_bytes=evidence_bytes,
            special_kind="obligation-reconstruction",
            special_code="obligation-mismatch",
            special_outcome="rejected",
        )
        materialization = "omitted-obligation"
    else:
        raise ValueError(f"unsupported negative scenario: {scenario_id}")

    files = _scenario_files(
        scenario_id=scenario_id,
        manifest_bytes=manifest_bytes,
        request_bytes=request_bytes,
        materials=materials,
        expected_name="expected-result.jcs",
        expected_bytes=expected_bytes,
        omit_blob=omit_blob,
        replace_blob=replace_blob,
    )
    index = _index_entry(
        readiness=readiness,
        manifest_bytes=manifest_bytes,
        request=request,
        request_bytes=request_bytes,
        evidence=evidence,
        evidence_bytes=evidence_bytes,
        expected_kind="independent-result",
        expected_bytes=expected_bytes,
        expected_document_digest=meta["document_digest"],
        expected_check_id=meta["check_id"],
        materialization=materialization,
    )
    return BuiltScenario(
        scenario_id=scenario_id,
        files=files,
        index=index,
        evidence=evidence,
        evidence_bytes=evidence_bytes,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        materials=materials,
        request=request,
        request_bytes=request_bytes,
        trust_ids=base.trust_ids,
    )
