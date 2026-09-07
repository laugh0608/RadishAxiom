"""Build scenario-specific pipeline artifacts and receipts."""

from __future__ import annotations

from typing import Any

from pipeline_artifact_contracts.builders import (
    artifact_ref,
    attempt_entry,
    build_options,
    build_policy,
    build_target_module,
    completed_result,
    failed_result,
    sorted_refs,
    stage,
)
from pipeline_artifact_contracts.common import (
    EVIDENCE_VERSION,
    FORMAT_VERSION,
    IR_VERSION,
    PIPELINE_PROFILE,
    STAGE_KINDS,
)
from pipeline_artifact_contracts.validation import validate_receipt_bytes

from .common import (
    SEMANTICS_NAME,
    SEMANTICS_SHA256,
    artifact_descriptor,
    canonical_bytes,
    entry,
    raw_digest,
)


TOOL_BYTES = b"radishaxiom-checker-bundle-production-fixture-tool-v0.1\n"


def production_tool() -> dict[str, Any]:
    return entry(
        "axiom-evidence-v0.1:tool",
        {
            "artifact": raw_digest(TOOL_BYTES),
            "name": "checker-bundle-production-fixture-tool",
            "roles": [
                "counterexample-replayer",
                "evidence-producer",
                "fixture-checker",
                "host-executor",
                "ir-normalizer",
                "obligation-generator",
                "output-comparator",
                "prover",
            ],
            "version": "0.1-specified",
        },
    )


def build_query(scenario_id: str, obligation_ids: list[str]) -> bytes:
    symbol = "axiom_s_" + raw_digest(scenario_id.encode("ascii"))[7:23]
    digest_marker = raw_digest("".join(obligation_ids).encode("ascii"))[7:23]
    return (
        "(set-logic QF_UFLIA)\n"
        f"(declare-const {symbol}_{digest_marker} Int)\n"
        f"(assert (= {symbol}_{digest_marker} 0))\n"
        f"(assert (not (= {symbol}_{digest_marker} 0)))\n"
        "(check-sat)\n"
    ).encode("ascii")


def build_response(kind: str) -> bytes:
    if kind not in {"sat", "unsat"}:
        raise ValueError(kind)
    return (kind + "\n").encode("ascii")


def _artifact_ref(role: str, digest: str) -> dict[str, str]:
    return artifact_ref(role, digest)


def build_pipeline_materials(
    *,
    scenario_id: str,
    ir_bytes: bytes,
    obligation_set_bytes: bytes,
    obligation_ids: list[str],
    input_digests: list[str],
    golden_digests: list[str],
    actual_output_digests: list[str],
    external_materials: dict[str, tuple[bytes, str, str]],
    stage_states: dict[str, str],
    gate_decision: str,
    receipt_outcome: str,
    proof_failed: bool,
) -> tuple[dict[str, tuple[bytes, str, str]], bytes, dict[str, Any]]:
    policy_bytes = canonical_bytes(build_policy())
    options_bytes = canonical_bytes(build_options())
    query_bytes = build_query(scenario_id, obligation_ids)
    response_bytes = build_response("sat" if proof_failed else "unsat")
    target_bytes = build_target_module()
    ir_digest = raw_digest(ir_bytes)
    obligation_digest = raw_digest(obligation_set_bytes)
    policy_digest = raw_digest(policy_bytes)
    options_digest = raw_digest(options_bytes)
    query_digest = raw_digest(query_bytes)
    response_digest = raw_digest(response_bytes)
    target_digest = raw_digest(target_bytes)
    tool_digest = raw_digest(TOOL_BYTES)

    materials: dict[str, tuple[bytes, str, str]] = {
        ir_digest: (ir_bytes, "axiom-ir", "0.1"),
        obligation_digest: (obligation_set_bytes, "axiom-obligation-set", "0.1"),
        options_digest: (options_bytes, "axiom-pipeline-options", "0.1"),
        policy_digest: (policy_bytes, "axiom-assurance-policy", "0.1"),
        query_digest: (query_bytes, "axiom-smtlib2-qf-uflia-query", "0.1"),
        tool_digest: (TOOL_BYTES, "synthetic-contract-tool", "0.1"),
    }
    if stage_states["P4"] == "completed":
        materials[response_digest] = (response_bytes, "cvc5-response", "1.3.4")
    materials.update(external_materials)
    if stage_states["P6"] == "completed":
        materials[target_digest] = (
            target_bytes,
            "axiom-node-esm",
            "node-24-esm-keyed-finite-table-v0.1",
        )

    descriptors = [
        artifact_descriptor(data, format_name, version)
        for data, format_name, version in materials.values()
    ]
    known_digests = {item["content_digest"] for item in descriptors}
    for digest in [*input_digests, *golden_digests, *actual_output_digests]:
        if digest not in known_digests:
            raise ValueError(f"pipeline material descriptor missing: {digest}")

    tool = production_tool()

    dependencies = {
        "P0": [],
        "P1": ["P0"],
        "P2": ["P1"],
        "P3": ["P2"],
        "P4": ["P3"],
        "P5": ["P1"],
        "P6": ["P2", "P4", "P5"],
        "P7": ["P6"],
        "P8": ["P7"],
        "P9": ["P0"],
    }
    ios: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]] = {
        "P0": (
            sorted_refs(
                [
                    _artifact_ref("candidate", ir_digest),
                    _artifact_ref("options", options_digest),
                    _artifact_ref("policy", policy_digest),
                ]
            ),
            [],
        ),
        "P1": (
            [_artifact_ref("candidate", ir_digest)],
            [_artifact_ref("canonical-ir", ir_digest)],
        ),
        "P2": (
            [_artifact_ref("canonical-ir", ir_digest)],
            [_artifact_ref("obligation-set", obligation_digest)],
        ),
        "P3": (
            [_artifact_ref("obligation-set", obligation_digest)],
            [_artifact_ref("query", query_digest)],
        ),
        "P4": (
            [_artifact_ref("query", query_digest)],
            [_artifact_ref("response", response_digest)]
            if stage_states["P4"] == "completed"
            else [],
        ),
        "P5": ([], []),
        "P6": (
            [_artifact_ref("canonical-ir", ir_digest)],
            [_artifact_ref("target-module", target_digest)]
            if stage_states["P6"] == "completed"
            else [],
        ),
        "P7": ([], []),
        "P8": ([], []),
        "P9": ([_artifact_ref("obligation-set", obligation_digest)], []),
    }

    stage_values: list[dict[str, Any]] = []
    attempts_by_stage: dict[str, list[dict[str, Any]]] = {}
    for stage_id in STAGE_KINDS:
        state = stage_states[stage_id]
        if state == "not-run":
            blocker = (
                {"id": "verification-gate", "kind": "gate"}
                if stage_id == "P6"
                else {"id": f"P{int(stage_id[1:]) - 1}", "kind": "stage"}
            )
            stage_values.append(
                stage(
                    stage_id,
                    dependencies[stage_id],
                    [],
                    {"blocked_by": blocker, "kind": "not-run"},
                )
            )
            attempts_by_stage[stage_id] = []
            continue

        stage_ios: list[tuple[list[dict[str, str]], list[dict[str, str]]]]
        if stage_id == "P5":
            stage_ios = []
            for index, input_digest in enumerate(input_digests):
                refs = [_artifact_ref("host-input", input_digest)]
                if index < len(golden_digests):
                    refs.append(_artifact_ref("golden-output", golden_digests[index]))
                stage_ios.append((sorted_refs(refs), []))
        elif stage_id == "P7":
            stage_ios = [
                (
                    sorted_refs(
                        [
                            _artifact_ref("host-input", input_digests[index]),
                            _artifact_ref("target-module", target_digest),
                        ]
                    ),
                    [_artifact_ref("host-output", digest)],
                )
                for index, digest in enumerate(actual_output_digests)
            ]
        elif stage_id == "P8":
            stage_ios = [
                (
                    sorted_refs(
                        [
                            _artifact_ref("actual-output", actual_output_digests[index]),
                            _artifact_ref("golden-output", golden_digests[index]),
                        ]
                    ),
                    [],
                )
                for index in range(len(actual_output_digests))
            ]
        else:
            stage_ios = [ios[stage_id]]

        if not stage_ios:
            raise ValueError(f"completed stage has no attempts: {scenario_id}:{stage_id}")
        attempt_values: list[dict[str, Any]] = []
        for ordinal, (inputs, outputs) in enumerate(stage_ios):
            if state == "completed":
                attempt_result = completed_result()
            elif state == "timeout":
                attempt_result = failed_result("timeout", "backend-wall-clock")
            elif state == "invalid":
                attempt_result = failed_result("invalid", "input-invalid")
            else:
                raise ValueError(f"unsupported materialized stage state: {state}")
            attempt_values.append(
                attempt_entry(
                    assurance_policy=policy_digest,
                    inputs=inputs,
                    options=options_digest,
                    ordinal=str(ordinal),
                    outputs=outputs,
                    result=attempt_result,
                    stage_id=stage_id,
                    tool=tool["id"],
                )
            )
        attempts_by_stage[stage_id] = attempt_values
        stage_values.append(
            stage(
                stage_id,
                dependencies[stage_id],
                attempt_values,
                attempt_values[-1]["definition"]["result"],
            )
        )

    prove_ok = gate_decision == "opened"
    input_ok = stage_states["P5"] == "completed"
    requirement_values = [
        {
            "kind": "all-prove-proved",
            "refs": [
                {"kind": "attempt", "value": attempts_by_stage["P4"][-1]["id"]}
            ],
            "status": "satisfied" if prove_ok else "unsatisfied",
        },
        {"kind": "all-trust-declared", "refs": [], "status": "satisfied"},
        {
            "kind": "assurance-policy-accepted",
            "refs": [{"kind": "artifact", "value": policy_digest}],
            "status": "satisfied",
        },
        {
            "kind": "input-checked",
            "refs": [
                {"kind": "attempt", "value": attempts_by_stage["P5"][-1]["id"]}
            ],
            "status": "satisfied" if input_ok else "unsatisfied",
        },
        {
            "kind": "ir-accepted",
            "refs": [
                {"kind": "attempt", "value": attempts_by_stage["P1"][-1]["id"]}
            ],
            "status": "satisfied",
        },
    ]
    receipt = {
        "artifacts": sorted(descriptors, key=lambda item: item["content_digest"]),
        "assurance_policy": policy_digest,
        "evidence_version": EVIDENCE_VERSION,
        "format": "axiom-pipeline-receipt",
        "format_version": FORMAT_VERSION,
        "ir_version": IR_VERSION,
        "mode": "benchmark-node24",
        "outcome": receipt_outcome,
        "pipeline_profile": PIPELINE_PROFILE,
        "semantics": {"name": SEMANTICS_NAME, "sha256": SEMANTICS_SHA256.removeprefix("sha256:")},
        "stages": stage_values,
        "tools": [tool],
        "verification_gate": {
            "decision": gate_decision,
            "id": "verification-gate",
            "requirements": requirement_values,
        },
    }
    receipt_bytes = canonical_bytes(receipt)
    validate_receipt_bytes(receipt_bytes)
    return materials, receipt_bytes, {
        "attempts": attempts_by_stage,
        "query": query_digest,
        "response": response_digest if stage_states["P4"] == "completed" else None,
        "target": target_digest,
        "tool": tool,
    }
