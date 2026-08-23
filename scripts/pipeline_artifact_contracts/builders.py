"""Build canonical Pipeline Artifact Contract fixtures."""

from typing import Any

from .common import (
    CVC5_PROFILE,
    EVIDENCE_VERSION,
    FORMAT_VERSION,
    IR_DOCUMENT_DIGEST,
    IR_PATH,
    IR_VERSION,
    NODE_INVOCATION_PROFILE,
    NODE_TARGET_PROFILE,
    PIPELINE_PROFILE,
    REPO_ROOT,
    SEMANTICS_NAME,
    SEMANTICS_SHA256,
    STAGE_KINDS,
    content_id,
    entry,
    raw_digest,
)

def semantics() -> dict[str, str]:
    return {"name": SEMANTICS_NAME, "sha256": SEMANTICS_SHA256}


def build_obligation_set() -> dict[str, Any]:
    definitions = [
        {
            "expectation": "check",
            "kind": "ir-structure",
            "subject": {
                "ir_document_digest": IR_DOCUMENT_DIGEST,
                "kind": "document",
            },
        },
        {
            "expectation": "prove",
            "kind": "totality",
            "subject": {
                "ir_document_digest": IR_DOCUMENT_DIGEST,
                "kind": "program",
            },
        },
    ]
    obligations = sorted(
        (entry("axiom-evidence-v0.1:obligation", item) for item in definitions),
        key=lambda item: item["id"],
    )
    ir_bytes = (REPO_ROOT / IR_PATH).read_bytes()
    return {
        "format": "axiom-obligation-set",
        "format_version": FORMAT_VERSION,
        "ir_artifact": raw_digest(ir_bytes),
        "ir_document_digest": IR_DOCUMENT_DIGEST,
        "obligation_profile": {
            "name": "keyed-finite-table-benchmark",
            "version": "0.1",
        },
        "obligations": obligations,
        "semantics": semantics(),
    }
def build_host_data(role: str) -> dict[str, Any]:
    if role == "input":
        tables = [
            {
                "name": "orders",
                "rows": [
                    {
                        "discount_cents": "100",
                        "order_id": "O1",
                        "state": "settled",
                        "subtotal_cents": "1000",
                    }
                ],
            }
        ]
    elif role == "output":
        tables = [
            {
                "name": "net_orders",
                "rows": [{"net_cents": "900", "order_id": "O1"}],
            }
        ]
    else:
        raise ValueError(role)
    return {
        "format": "axiom-host-data",
        "format_version": FORMAT_VERSION,
        "ir_document_digest": IR_DOCUMENT_DIGEST,
        "role": role,
        "tables": tables,
    }


def build_query(obligation_id: str) -> bytes:
    symbol = "axiom_o_" + obligation_id.removeprefix("sha256:")[:16]
    return (
        f"(set-logic QF_UFLIA)\n"
        f"(declare-const {symbol} Int)\n"
        f"(assert (= {symbol} 0))\n"
        f"(assert (not (= {symbol} 0)))\n"
        f"(check-sat)\n"
    ).encode("ascii")


def build_target_module() -> bytes:
    return (
        'const axiomTargetProfile = "node-24-esm-keyed-finite-table-v0.1";\n'
        'if (axiomTargetProfile !== "node-24-esm-keyed-finite-table-v0.1") {\n'
        '  throw new Error("AXIOM_TARGET_PROFILE");\n'
        '}\n'
    ).encode("ascii")


def build_policy() -> dict[str, str]:
    return {
        "format": "axiom-assurance-policy",
        "format_version": "0.1",
        "proof_support": "backend-attestation",
    }


def build_options() -> dict[str, str]:
    return {
        "cvc5_profile": CVC5_PROFILE,
        "format": "axiom-pipeline-options",
        "format_version": "0.1",
        "node_invocation_profile": NODE_INVOCATION_PROFILE,
        "node_target_profile": NODE_TARGET_PROFILE,
        "pipeline_profile": PIPELINE_PROFILE,
    }


def artifact_descriptor(data: bytes, format_name: str, version: str) -> dict[str, str]:
    return {
        "byte_length": str(len(data)),
        "content_digest": raw_digest(data),
        "format": format_name,
        "format_version": version,
    }


def artifact_ref(role: str, digest: str) -> dict[str, str]:
    return {"artifact": digest, "role": role}


def sorted_refs(values: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(values, key=lambda item: (item["role"], item["artifact"]))


def limits() -> list[dict[str, str]]:
    return [
        {"name": "wall-clock", "unit": "millisecond", "value": "5000"},
        {"name": "working-memory", "unit": "byte", "value": "67108864"},
    ]


def profile_value(stage_id: str) -> dict[str, str]:
    if stage_id in {"P3", "P4"}:
        return {"kind": "profile", "value": CVC5_PROFILE}
    if stage_id == "P6":
        return {"kind": "profile", "value": NODE_TARGET_PROFILE}
    if stage_id == "P7":
        return {"kind": "profile", "value": NODE_INVOCATION_PROFILE}
    return {"kind": "not-applicable"}


def cache_key(
    *,
    adapter_profile: dict[str, str],
    assurance_policy: str,
    inputs: list[dict[str, str]],
    limits_value: list[dict[str, str]],
    options: str,
    stage_id: str,
    tool: str,
) -> str:
    definition: dict[str, Any] = {
        "adapter_profile": adapter_profile,
        "assurance_policy": assurance_policy,
        "evidence_version": EVIDENCE_VERSION,
        "inputs": inputs,
        "ir_version": IR_VERSION,
        "limits": limits_value,
        "options": options,
        "pipeline_profile": PIPELINE_PROFILE,
        "semantics": semantics(),
        "stage": stage_id,
        "tool": tool,
    }
    return content_id("axiom-pipeline-v0.1:cache-key", definition)


def attempt_entry(
    *,
    assurance_policy: str,
    inputs: list[dict[str, str]],
    options: str,
    ordinal: str,
    outputs: list[dict[str, str]],
    result: dict[str, str],
    stage_id: str,
    tool: str,
) -> dict[str, Any]:
    adapter = profile_value(stage_id)
    limit_values = limits()
    definition = {
        "adapter_profile": adapter,
        "cache": {
            "key": cache_key(
                adapter_profile=adapter,
                assurance_policy=assurance_policy,
                inputs=inputs,
                limits_value=limit_values,
                options=options,
                stage_id=stage_id,
                tool=tool,
            ),
            "kind": "miss",
        },
        "inputs": inputs,
        "limits": limit_values,
        "options": options,
        "ordinal": ordinal,
        "outputs": outputs,
        "result": result,
        "tool": tool,
    }
    return entry("axiom-pipeline-v0.1:attempt", definition)


def completed_result() -> dict[str, str]:
    return {"kind": "completed"}


def failed_result(kind: str, code: str) -> dict[str, str]:
    return {"code": code, "kind": kind}


def stage(
    stage_id: str,
    dependencies: list[str],
    attempts: list[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "attempts": attempts,
        "dependencies": dependencies,
        "id": stage_id,
        "kind": STAGE_KINDS[stage_id],
        "result": result,
    }


def gate_ref(kind: str, value: str) -> dict[str, str]:
    return {"kind": kind, "value": value}


def build_receipt(
    fixture_bytes: dict[str, bytes],
    obligation_set: dict[str, Any],
    partial: bool,
) -> dict[str, Any]:
    descriptors = {
        "host-input": artifact_descriptor(
            fixture_bytes["fixtures/minimal/host-input.jcs"], "axiom-host-data", "0.1"
        ),
        "host-output": artifact_descriptor(
            fixture_bytes["fixtures/minimal/host-output.jcs"], "axiom-host-data", "0.1"
        ),
        "ir": artifact_descriptor(
            (REPO_ROOT / IR_PATH).read_bytes(), "axiom-ir", "0.1"
        ),
        "obligations": artifact_descriptor(
            fixture_bytes["fixtures/minimal/obligation-set.jcs"],
            "axiom-obligation-set",
            "0.1",
        ),
        "options": artifact_descriptor(
            fixture_bytes["fixtures/minimal/options.jcs"],
            "axiom-pipeline-options",
            "0.1",
        ),
        "policy": artifact_descriptor(
            fixture_bytes["fixtures/minimal/policy.jcs"],
            "axiom-assurance-policy",
            "0.1",
        ),
        "query": artifact_descriptor(
            fixture_bytes["fixtures/minimal/query.smt2"],
            "axiom-smtlib2-qf-uflia-query",
            "0.1",
        ),
        "target": artifact_descriptor(
            fixture_bytes["fixtures/minimal/target.mjs"],
            "axiom-node-esm",
            NODE_TARGET_PROFILE,
        ),
        "tool": artifact_descriptor(
            fixture_bytes["fixtures/minimal/tool.txt"],
            "synthetic-contract-tool",
            "0.1",
        ),
    }
    artifact_by_name = {
        name: item["content_digest"] for name, item in descriptors.items()
    }
    artifacts = sorted(descriptors.values(), key=lambda item: item["content_digest"])

    tool_definition = {
        "artifact": artifact_by_name["tool"],
        "name": "pipeline-contract-fixture-generator",
        "roles": [
            "evidence-producer",
            "fixture-checker",
            "host-executor",
            "ir-normalizer",
            "obligation-generator",
            "output-comparator",
            "prover",
        ],
        "version": "0.1",
    }
    tool_value = entry("axiom-evidence-v0.1:tool", tool_definition)
    tool_id = tool_value["id"]
    policy_digest = artifact_by_name["policy"]
    options_digest = artifact_by_name["options"]

    stage_ios = {
        "P0": (
            sorted_refs(
                [
                    artifact_ref("candidate", artifact_by_name["ir"]),
                    artifact_ref("options", options_digest),
                    artifact_ref("policy", policy_digest),
                ]
            ),
            [],
        ),
        "P1": (
            [artifact_ref("candidate", artifact_by_name["ir"])],
            [artifact_ref("canonical-ir", artifact_by_name["ir"])],
        ),
        "P2": (
            [artifact_ref("canonical-ir", artifact_by_name["ir"])],
            [artifact_ref("obligation-set", artifact_by_name["obligations"])],
        ),
        "P3": (
            [artifact_ref("obligation-set", artifact_by_name["obligations"])],
            [artifact_ref("query", artifact_by_name["query"])],
        ),
        "P4": ([artifact_ref("query", artifact_by_name["query"])], []),
        "P5": (
            sorted_refs(
                [
                    artifact_ref("golden-output", artifact_by_name["host-output"]),
                    artifact_ref("host-input", artifact_by_name["host-input"]),
                ]
            ),
            [],
        ),
        "P6": (
            [artifact_ref("canonical-ir", artifact_by_name["ir"])],
            [artifact_ref("target-module", artifact_by_name["target"])],
        ),
        "P7": (
            sorted_refs(
                [
                    artifact_ref("host-input", artifact_by_name["host-input"]),
                    artifact_ref("target-module", artifact_by_name["target"]),
                ]
            ),
            [artifact_ref("host-output", artifact_by_name["host-output"])],
        ),
        "P8": (
            sorted_refs(
                [
                    artifact_ref("actual-output", artifact_by_name["host-output"]),
                    artifact_ref("golden-output", artifact_by_name["host-output"]),
                ]
            ),
            [],
        ),
        "P9": (
            [artifact_ref("obligation-set", artifact_by_name["obligations"])],
            [],
        ),
    }
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

    stages: list[dict[str, Any]] = []
    stage_attempts: dict[str, dict[str, Any]] = {}
    for stage_id in STAGE_KINDS:
        inputs, outputs = stage_ios[stage_id]
        if partial and stage_id == "P4":
            attempt_result = failed_result("timeout", "backend-wall-clock")
            attempt = attempt_entry(
                assurance_policy=policy_digest,
                inputs=inputs,
                options=options_digest,
                ordinal="0",
                outputs=outputs,
                result=attempt_result,
                stage_id=stage_id,
                tool=tool_id,
            )
            stage_attempts[stage_id] = attempt
            stages.append(stage(stage_id, dependencies[stage_id], [attempt], attempt_result))
            continue
        if partial and stage_id in {"P6", "P7", "P8"}:
            blocker = (
                {"id": "verification-gate", "kind": "gate"}
                if stage_id == "P6"
                else {"id": f"P{int(stage_id[1:]) - 1}", "kind": "stage"}
            )
            stages.append(
                stage(
                    stage_id,
                    dependencies[stage_id],
                    [],
                    {"blocked_by": blocker, "kind": "not-run"},
                )
            )
            continue
        attempt = attempt_entry(
            assurance_policy=policy_digest,
            inputs=inputs,
            options=options_digest,
            ordinal="0",
            outputs=outputs,
            result=completed_result(),
            stage_id=stage_id,
            tool=tool_id,
        )
        stage_attempts[stage_id] = attempt
        stages.append(
            stage(stage_id, dependencies[stage_id], [attempt], completed_result())
        )

    obligations = obligation_set["obligations"]
    structure_id = next(
        item["id"] for item in obligations if item["definition"]["kind"] == "ir-structure"
    )
    totality_id = next(
        item["id"] for item in obligations if item["definition"]["kind"] == "totality"
    )
    requirements = [
        {
            "kind": "all-prove-proved",
            "refs": [
                gate_ref("attempt", stage_attempts["P4"]["id"]),
                gate_ref("obligation", totality_id),
            ],
            "status": "unsatisfied" if partial else "satisfied",
        },
        {
            "kind": "all-trust-declared",
            "refs": [],
            "status": "satisfied",
        },
        {
            "kind": "assurance-policy-accepted",
            "refs": [gate_ref("artifact", policy_digest)],
            "status": "satisfied",
        },
        {
            "kind": "input-checked",
            "refs": [gate_ref("attempt", stage_attempts["P5"]["id"])],
            "status": "satisfied",
        },
        {
            "kind": "ir-accepted",
            "refs": [gate_ref("obligation", structure_id)],
            "status": "satisfied",
        },
    ]
    requirements.sort(key=lambda item: item["kind"])

    return {
        "artifacts": artifacts,
        "assurance_policy": policy_digest,
        "evidence_version": EVIDENCE_VERSION,
        "format": "axiom-pipeline-receipt",
        "format_version": FORMAT_VERSION,
        "ir_version": IR_VERSION,
        "mode": "benchmark-node24",
        "outcome": "partial" if partial else "completed",
        "pipeline_profile": PIPELINE_PROFILE,
        "semantics": semantics(),
        "stages": stages,
        "tools": [tool_value],
        "verification_gate": {
            "decision": "closed" if partial else "opened",
            "id": "verification-gate",
            "requirements": requirements,
        },
    }
