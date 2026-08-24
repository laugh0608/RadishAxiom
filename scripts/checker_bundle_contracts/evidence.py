"""Build complete specified Axiom Evidence fixtures for checker bundles."""

from __future__ import annotations

import copy
from typing import Any

from .common import (
    SEMANTICS_NAME,
    SEMANTICS_SHA256,
    artifact_descriptor,
    canonical_bytes,
    content_id,
    entry,
    raw_digest,
    sorted_entries,
)
from .obligations import build_obligation_set, build_obligations


BACKEND_BYTES = b"cvc5-1.3.4-specified-fixture-identity\n"
UNCOVERED_STATEMENTS = {
    "host-fidelity-for-all-inputs": "Host fidelity beyond the listed finite fixtures is not covered.",
    "legal-regulatory-compliance": "Legal and regulatory compliance is not covered.",
    "long-term-archival-authenticity": "Long-term archival authenticity is not covered.",
    "real-world-intent": "The IR is not claimed to capture real-world intent.",
    "resource-performance": "Production resource and performance bounds are not covered.",
    "source-truth-completeness": "Source data truth and completeness are not covered.",
    "timing-memory-log-side-channel": "Timing, memory, and log side channels are not covered.",
}
TRUST_CLAIMS = {
    "cryptographic-primitive": "SHA-256 collision resistance is assumed for content identity.",
    "decoder-normalizer": "The production decoder and normalizer preserve the specified bytes.",
    "host-runtime": "The recorded host runtime execution is faithful to the generated target.",
    "input-origin": "The bound synthetic fixture is the intended concrete input.",
    "production-generator": "The production generator emitted the bound artifacts and receipt.",
    "proof-backend": "The bound proof backend response is sound for the bound query.",
    "sensitivity-classification": "The IR public and sensitive field labels are intended.",
    "specification-intent": "The bound contracts express the benchmark task intent.",
}


def _refs(role_digests: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"artifact": digest, "role": role}
        for role, digest in sorted(set(role_digests))
    ]


def _execution(
    *,
    kind: str,
    tool: str,
    inputs: list[tuple[str, str]],
    outputs: list[tuple[str, str]],
    result: dict[str, str],
) -> dict[str, Any]:
    return entry(
        "axiom-evidence-v0.1:execution",
        {
            "inputs": _refs(inputs),
            "kind": kind,
            "limits": [
                {"name": "wall-clock", "unit": "millisecond", "value": "5000"},
                {"name": "working-memory", "unit": "byte", "value": "67108864"},
            ],
            "outputs": _refs(outputs),
            "result": result,
            "tool": tool,
        },
    )


def _scope(ir_document_digest: str) -> dict[str, str]:
    return {"ir_document_digest": ir_document_digest, "kind": "program"}


def build_trust(
    categories: list[str],
    ir_document_digest: str,
    receipt_digest: str | None,
    production_tool_id: str,
    backend_tool_id: str,
) -> list[dict[str, Any]]:
    values = []
    for category in sorted(set(categories)):
        if category not in TRUST_CLAIMS:
            raise ValueError(f"unsupported trust category: {category}")
        if category == "proof-backend":
            scope: dict[str, str] = {"id": backend_tool_id, "kind": "tool"}
        elif category in {"decoder-normalizer", "host-runtime", "production-generator"}:
            scope = {"id": production_tool_id, "kind": "tool"}
        else:
            scope = _scope(ir_document_digest)
        mitigations: list[dict[str, str]] = []
        values.append(
            entry(
                "axiom-evidence-v0.1:trust",
                {
                    "category": category,
                    "claim": TRUST_CLAIMS[category],
                    "mitigations": mitigations,
                    "scope": scope,
                },
            )
        )
    return sorted_entries(values)


def build_uncovered(
    categories: list[str], ir_document_digest: str
) -> list[dict[str, Any]]:
    values = []
    for category in sorted(set(categories)):
        values.append(
            entry(
                "axiom-evidence-v0.1:uncovered",
                {
                    "category": category,
                    "scope": _scope(ir_document_digest),
                    "statement": UNCOVERED_STATEMENTS[category],
                },
            )
        )
    return sorted_entries(values)


def _type_maps(ir: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    tables = {item["id"]: item["definition"] for item in ir["table_types"]}
    records = {item["id"]: item["definition"] for item in ir["record_types"]}
    return tables, records


def _tag_value(value: Any, type_value: dict[str, Any]) -> dict[str, Any]:
    kind = type_value["kind"]
    if kind == "bool":
        return {"kind": "bool", "value": value}
    if kind == "int":
        return {"kind": "int", "value": value}
    if kind == "fixed":
        return {
            "coefficient": value,
            "kind": "fixed",
            "scale": type_value["scale"],
        }
    if kind == "text":
        return {"kind": "text", "value": value}
    if kind == "enum":
        return {
            "enum_type": type_value["enum_type"],
            "kind": "enum",
            "member": value,
        }
    if kind == "option":
        if isinstance(value, dict) and value.get("kind") == "none":
            return {"kind": "none"}
        inner = value.get("value") if isinstance(value, dict) else value
        return {"kind": "some", "value": _tag_value(inner, type_value["value"])}
    raise ValueError(f"unsupported Evidence value kind: {kind}")


def _world(
    ir: dict[str, Any], fixture: dict[str, Any], required_keys: list[str]
) -> dict[str, Any]:
    tables, records = _type_maps(ir)
    input_types = {
        item["definition"]["port"]: item["definition"]["table_type"]
        for item in ir["nodes"]
        if item["definition"]["kind"] == "input"
    }
    required_by_table: dict[str, set[str]] = {}
    for value in required_keys:
        table_name, key = value.split(":", 1)
        required_by_table.setdefault(table_name, set()).add(key)

    result_tables = []
    for table in fixture["tables"]:
        table_name = table["name"]
        table_type = tables[input_types[table_name]]
        record_id = table_type["record_type"]
        record = records[record_id]
        fields = {field["name"]: field["type"] for field in record["fields"]}
        primary_key = table_type["primary_key"]
        rows = []
        for row in table["rows"]:
            key = ":".join(str(row[name]) for name in primary_key)
            if required_by_table and key not in required_by_table.get(table_name, set()):
                continue
            rows.append(
                {
                    "fields": [
                        {
                            "name": name,
                            "value": _tag_value(row[name], fields[name]),
                        }
                        for name in sorted(fields)
                    ],
                    "kind": "record",
                    "record_type": record_id,
                }
            )
        if rows:
            result_tables.append({"name": table_name, "rows": rows})
    return {"tables": result_tables}


def _counterexample(
    *,
    ir: dict[str, Any],
    fixture: dict[str, Any],
    assertion: dict[str, Any],
    obligation_id: str,
    ir_document_digest: str,
    input_rejected: bool,
) -> dict[str, Any]:
    expected = assertion["counterexample"]
    required_keys = expected.get("required_keys", [])
    first_world = _world(ir, fixture, required_keys)
    worlds = [first_world]
    if expected["kind"] == "paired-input":
        second_fixture = copy.deepcopy(fixture)
        first_row = second_fixture["tables"][0]["rows"][0]
        first_row["contact_email"] = "changed@example.test"
        worlds.append(_world(ir, second_fixture, required_keys))
    assume_ids = [] if input_rejected else sorted(
        item["id"]
        for item in ir["contracts"]
        if item["definition"].get("role") == "assume"
    )
    return {
        "kind": expected["kind"],
        "minimality": {
            "kind": expected["minimality"],
            "order": "axiom-witness-order-v0.1",
        },
        "observed": {
            "kind": "obligation-failure",
            "obligation": obligation_id,
            "required_fields": expected.get("required_fields", []),
            "required_keys": required_keys,
        },
        "preconditions": assume_ids,
        "trace": [
            {"kind": "document", "ref": ir_document_digest},
            {"kind": "obligation", "ref": obligation_id},
            {"kind": "observation", "value": "failed"},
        ],
        "worlds": worlds,
    }


def _choose_failed_obligation(
    obligations: list[dict[str, Any]], assertion: dict[str, Any]
) -> dict[str, Any]:
    required = next(
        item for item in assertion["required_results"] if item["status"] == "failed"
    )
    candidates = [
        item for item in obligations if item["definition"]["kind"] == required["kind"]
    ]
    required_fields = set(assertion["counterexample"].get("required_fields", []))
    for item in candidates:
        subject = item["definition"]["subject"]
        if subject.get("name") in required_fields:
            return item
    if required["kind"] == "row-coverage":
        for item in candidates:
            if item["definition"]["subject"]["kind"] == "node":
                return item
    if not candidates:
        raise ValueError(f"no failed obligation for {required['kind']}")
    return candidates[0]


def _checked_result(
    execution_id: str, artifacts: list[str], assumptions: list[str]
) -> dict[str, Any]:
    return {
        "artifacts": sorted(set(artifacts)),
        "assumptions": sorted(set(assumptions)),
        "execution": execution_id,
        "kind": "checked",
    }


def build_evidence(
    *,
    scenario_id: str,
    ir: dict[str, Any],
    ir_bytes: bytes,
    ir_document_digest: str,
    assertion: dict[str, Any],
    fixture_values: list[dict[str, Any]],
    input_digests: list[str],
    golden_digests: list[str],
    actual_output_digests: list[str],
    materials: dict[str, tuple[bytes, str, str]],
    receipt_bytes: bytes | None,
    pipeline_meta: dict[str, Any],
    trust_categories: list[str],
    uncovered_categories: list[str],
    profile: str,
    proof_mode: str,
    concrete_mismatch: bool = False,
) -> tuple[bytes, bytes, dict[str, tuple[bytes, str, str]], dict[str, Any]]:
    production_tool = pipeline_meta["tool"]
    backend_digest = raw_digest(BACKEND_BYTES)
    backend_tool = entry(
        "axiom-evidence-v0.1:tool",
        {
            "artifact": backend_digest,
            "name": "cvc5-specified-fixture-backend",
            "roles": ["prover"],
            "version": "1.3.4-specified",
        },
    )
    materials = dict(materials)
    materials[backend_digest] = (BACKEND_BYTES, "synthetic-contract-tool", "0.1")
    receipt_digest = None
    if receipt_bytes is not None:
        receipt_digest = raw_digest(receipt_bytes)
        materials[receipt_digest] = (receipt_bytes, "axiom-pipeline-receipt", "0.1")
    trust = build_trust(
        trust_categories,
        ir_document_digest,
        receipt_digest,
        production_tool["id"],
        backend_tool["id"],
    )
    trust_ids = [item["id"] for item in trust]
    trust_by_category = {
        item["definition"]["category"]: item["id"] for item in trust
    }

    preliminary = build_obligations(
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
        preliminary,
        profile=profile,
    )
    obligation_set_bytes = canonical_bytes(obligation_set)
    obligation_set_digest = raw_digest(obligation_set_bytes)
    existing_obligation_digest = next(
        (
            digest
            for digest, (_, format_name, _) in materials.items()
            if format_name == "axiom-obligation-set"
        ),
        None,
    )
    if existing_obligation_digest not in {None, obligation_set_digest}:
        raise ValueError(f"obligation set drifted for {scenario_id}")
    materials[obligation_set_digest] = (
        obligation_set_bytes,
        "axiom-obligation-set",
        "0.1",
    )

    query_digest = pipeline_meta["query"]
    response_digest = pipeline_meta.get("response")
    proof_result = {"kind": "completed"}
    if proof_mode == "timeout":
        proof_result = {"code": "backend-wall-clock", "kind": "timeout"}
    proof_execution = _execution(
        kind="prove",
        tool=backend_tool["id"],
        inputs=[("obligation-set", obligation_set_digest), ("query", query_digest)],
        outputs=[("response", response_digest)] if response_digest else [],
        result=proof_result,
    )
    structure_execution = _execution(
        kind="check-fixture",
        tool=production_tool["id"],
        inputs=[
            ("canonical-ir", raw_digest(ir_bytes)),
            *(
                [("pipeline-receipt", receipt_digest)]
                if receipt_digest is not None
                else []
            ),
        ],
        outputs=[],
        result={"kind": "completed"},
    )
    fixture_executions = [
        _execution(
            kind="check-fixture",
            tool=production_tool["id"],
            inputs=[("host-input", input_digest)],
            outputs=[],
            result={"kind": "completed"},
        )
        for input_digest in input_digests
    ]
    host_executions = [
        _execution(
            kind="execute-host",
            tool=production_tool["id"],
            inputs=[
                ("host-input", input_digests[index]),
                ("target-module", pipeline_meta["target"]),
            ],
            outputs=[("host-output", digest)],
            result={"kind": "completed"},
        )
        for index, digest in enumerate(actual_output_digests)
    ]
    if actual_output_digests:
        compare_executions = [
            _execution(
                kind="compare-output",
                tool=production_tool["id"],
                inputs=[
                    ("actual-output", actual_output_digests[index]),
                    ("golden-output", golden_digests[index]),
                ],
                outputs=[],
                result={"kind": "completed"},
            )
            for index in range(len(actual_output_digests))
        ]
    else:
        compare_executions = [
            _execution(
                kind="compare-output",
                tool=production_tool["id"],
                inputs=[("golden-output", digest)],
                outputs=[],
                result={"code": "verification-gate-closed", "kind": "unavailable"},
            )
            for digest in golden_digests
        ]

    failed_target = None
    if any(item["status"] == "failed" for item in assertion["required_results"]):
        failed_target = _choose_failed_obligation(preliminary, assertion)
    replay_execution = None
    if failed_target is not None:
        replay_execution = _execution(
            kind="replay-counterexample",
            tool=production_tool["id"],
            inputs=[
                ("canonical-ir", raw_digest(ir_bytes)),
                ("host-input", input_digests[0]),
            ],
            outputs=[],
            result={"kind": "completed"},
        )

    proof_kinds = {
        "contract-guarantee",
        "effect-empty",
        "field-origin",
        "group-conservation",
        "key-cardinality",
        "noninterference",
        "numeric-range",
        "row-coverage",
        "totality",
    }
    input_rejected = assertion["expected_conclusion"] == "input_rejected"
    failed_ids: list[str] = []
    unknown_ids: list[str] = []
    obligations: list[dict[str, Any]] = []
    for item in preliminary:
        definition = item["definition"]
        kind = definition["kind"]
        subject = definition["subject"]
        if kind == "ir-structure":
            result = _checked_result(
                structure_execution["id"],
                [
                    raw_digest(ir_bytes),
                    *([receipt_digest] if receipt_digest is not None else []),
                ],
                [],
            )
        elif kind in proof_kinds:
            if proof_mode == "timeout":
                result = {
                    "attempts": [proof_execution["id"]],
                    "kind": "unknown",
                    "reason": "timeout",
                }
                unknown_ids.append(item["id"])
            elif failed_target is not None and item["id"] == failed_target["id"]:
                assert replay_execution is not None
                result = {
                    "assumptions": [],
                    "counterexample": _counterexample(
                        ir=ir,
                        fixture=fixture_values[0],
                        assertion=assertion,
                        obligation_id=item["id"],
                        ir_document_digest=ir_document_digest,
                        input_rejected=False,
                    ),
                    "execution": replay_execution["id"],
                    "kind": "failed",
                }
                failed_ids.append(item["id"])
            elif proof_mode == "backend-attestation":
                proof_trust = trust_by_category["proof-backend"]
                result = {
                    "assumptions": [proof_trust],
                    "kind": "proved",
                    "support": {
                        "execution": proof_execution["id"],
                        "kind": "backend-attestation",
                        "query": query_digest,
                        "response": response_digest,
                        "trust": proof_trust,
                    },
                }
            else:
                result = {
                    "assumptions": [],
                    "kind": "proved",
                    "support": {
                        "execution": proof_execution["id"],
                        "kind": "kernel-replay",
                    },
                }
        elif kind == "input-conformance":
            artifact = subject.get("artifact")
            index = input_digests.index(artifact) if artifact in input_digests else 0
            execution = fixture_executions[index]
            if input_rejected:
                assert replay_execution is not None or failed_target is not None
                counterexample_execution = replay_execution
                if counterexample_execution is None:
                    counterexample_execution = _execution(
                        kind="replay-counterexample",
                        tool=production_tool["id"],
                        inputs=[("host-input", input_digests[0])],
                        outputs=[],
                        result={"kind": "completed"},
                    )
                    replay_execution = counterexample_execution
                result = {
                    "assumptions": [],
                    "counterexample": _counterexample(
                        ir=ir,
                        fixture=fixture_values[0],
                        assertion=assertion,
                        obligation_id=item["id"],
                        ir_document_digest=ir_document_digest,
                        input_rejected=True,
                    ),
                    "execution": counterexample_execution["id"],
                    "kind": "failed",
                }
                failed_ids.append(item["id"])
            else:
                result = _checked_result(execution["id"], [input_digests[index]], [])
        elif kind == "host-conformance":
            index = actual_output_digests.index(subject["artifact"])
            if concrete_mismatch:
                result = {
                    "assumptions": [],
                    "counterexample": {
                        "kind": "single-row",
                        "minimality": {
                            "kind": "reduced",
                            "order": "axiom-witness-order-v0.1",
                        },
                        "observed": {
                            "actual": actual_output_digests[index],
                            "expected": golden_digests[index],
                            "kind": "host-output-mismatch",
                        },
                        "preconditions": [],
                        "trace": [
                            {"kind": "obligation", "ref": item["id"]},
                            {"kind": "observation", "value": "failed"},
                        ],
                        "worlds": [_world(ir, fixture_values[index], [])],
                    },
                    "execution": compare_executions[index]["id"],
                    "kind": "failed",
                }
                failed_ids.append(item["id"])
            else:
                result = _checked_result(
                    host_executions[index]["id"],
                    [input_digests[index], actual_output_digests[index]],
                    [],
                )
        elif kind == "output-conformance":
            artifact = subject.get("artifact")
            index = golden_digests.index(artifact) if artifact in golden_digests else 0
            if not actual_output_digests:
                result = {
                    "attempts": [compare_executions[index]["id"]],
                    "kind": "unknown",
                    "reason": "backend-unavailable",
                }
                unknown_ids.append(item["id"])
            elif concrete_mismatch:
                result = {
                    "assumptions": [],
                    "counterexample": {
                        "kind": "single-row",
                        "minimality": {
                            "kind": "reduced",
                            "order": "axiom-witness-order-v0.1",
                        },
                        "observed": {
                            "actual": actual_output_digests[index],
                            "expected": golden_digests[index],
                            "kind": "host-output-mismatch",
                        },
                        "preconditions": [],
                        "trace": [
                            {"kind": "obligation", "ref": item["id"]},
                            {"kind": "observation", "value": "failed"},
                        ],
                        "worlds": [_world(ir, fixture_values[index], [])],
                    },
                    "execution": compare_executions[index]["id"],
                    "kind": "failed",
                }
                failed_ids.append(item["id"])
            else:
                result = _checked_result(
                    compare_executions[index]["id"],
                    [actual_output_digests[index], golden_digests[index]],
                    [],
                )
        elif kind == "trust-boundary":
            trust_id = subject["scope"]
            result = {"kind": "trusted", "trust": trust_id}
        else:
            raise ValueError(f"unhandled obligation kind: {kind}")
        obligations.append({**item, "result": result})

    conclusion_kind = assertion["expected_conclusion"]
    if conclusion_kind in {"input_rejected", "implementation_inconsistent", "violated"}:
        conclusion_refs = sorted(failed_ids)
    elif conclusion_kind == "inconclusive":
        conclusion_refs = sorted(unknown_ids)
    else:
        conclusion_refs = []

    execution_values = [
        structure_execution,
        proof_execution,
        *fixture_executions,
        *host_executions,
        *compare_executions,
    ]
    if replay_execution is not None:
        execution_values.append(replay_execution)
    executions = sorted_entries(
        list({item["id"]: item for item in execution_values}.values())
    )

    artifact_values = sorted(
        (
            artifact_descriptor(data, format_name, version)
            for data, format_name, version in materials.values()
        ),
        key=lambda item: item["content_digest"],
    )
    evidence = {
        "artifacts": artifact_values,
        "conclusion": {"kind": conclusion_kind, "refs": conclusion_refs},
        "digest_algorithm": "sha-256",
        "evidence_version": "0.1",
        "executions": executions,
        "format": "axiom-evidence",
        "obligation_profile": {"name": profile, "version": "0.1"},
        "obligations": sorted(obligations, key=lambda item: item["id"]),
        "producer": production_tool["id"],
        "subject": {
            "ir_artifact": raw_digest(ir_bytes),
            "ir_document_digest": ir_document_digest,
            "ir_version": "0.1",
            "kind": "axiom-ir",
            "semantics": {"name": SEMANTICS_NAME, "sha256": SEMANTICS_SHA256},
        },
        "tools": sorted_entries([production_tool, backend_tool]),
        "trust": trust,
        "uncovered": build_uncovered(uncovered_categories, ir_document_digest),
    }
    evidence_bytes = canonical_bytes(evidence)
    validate_evidence(evidence, materials)
    return evidence_bytes, obligation_set_bytes, materials, {
        "evidence_document_digest": content_id(
            "axiom-evidence-v0.1:document", evidence
        ),
        "obligations": obligations,
        "remaining_trust": trust_ids,
    }


def validate_evidence(
    evidence: dict[str, Any],
    materials: dict[str, tuple[bytes, str, str]],
) -> None:
    expected_members = {
        "artifacts",
        "conclusion",
        "digest_algorithm",
        "evidence_version",
        "executions",
        "format",
        "obligation_profile",
        "obligations",
        "producer",
        "subject",
        "tools",
        "trust",
        "uncovered",
    }
    if set(evidence) != expected_members:
        raise ValueError("Evidence top-level members drifted")
    if evidence["format"] != "axiom-evidence" or evidence["evidence_version"] != "0.1":
        raise ValueError("Evidence version drifted")
    artifact_digests = [item["content_digest"] for item in evidence["artifacts"]]
    if artifact_digests != sorted(set(artifact_digests)):
        raise ValueError("Evidence artifacts are not sorted and unique")
    if set(artifact_digests) != set(materials):
        raise ValueError("Evidence artifact coverage drifted")
    for descriptor in evidence["artifacts"]:
        data, format_name, version = materials[descriptor["content_digest"]]
        if descriptor != artifact_descriptor(data, format_name, version):
            raise ValueError("Evidence artifact descriptor drifted")
    for domain, member in (
        ("axiom-evidence-v0.1:tool", "tools"),
        ("axiom-evidence-v0.1:execution", "executions"),
        ("axiom-evidence-v0.1:trust", "trust"),
        ("axiom-evidence-v0.1:uncovered", "uncovered"),
    ):
        ids = [item["id"] for item in evidence[member]]
        if ids != sorted(set(ids)):
            raise ValueError(f"Evidence {member} are not sorted and unique")
        for item in evidence[member]:
            if item["id"] != content_id(domain, item["definition"]):
                raise ValueError(f"Evidence {member} ID drifted")
    obligation_ids = [item["id"] for item in evidence["obligations"]]
    if obligation_ids != sorted(set(obligation_ids)):
        raise ValueError("Evidence obligations are not sorted and unique")
    trust_ids = {item["id"] for item in evidence["trust"]}
    tools = {item["id"]: item["definition"] for item in evidence["tools"]}
    required_roles = {
        "check-certificate": "certificate-checker",
        "check-fixture": "fixture-checker",
        "compare-output": "output-comparator",
        "execute-host": "host-executor",
        "generate-obligations": "obligation-generator",
        "normalize": "ir-normalizer",
        "prove": "prover",
        "replay-counterexample": "counterexample-replayer",
    }
    for execution in evidence["executions"]:
        definition = execution["definition"]
        tool = tools.get(definition["tool"])
        required_role = required_roles.get(definition["kind"])
        if tool is None or required_role not in tool["roles"]:
            raise ValueError("Evidence execution tool role mismatch")
    for item in evidence["obligations"]:
        if item["id"] != content_id(
            "axiom-evidence-v0.1:obligation", item["definition"]
        ):
            raise ValueError("Evidence obligation ID drifted")
        expectation = item["definition"]["expectation"]
        result_kind = item["result"]["kind"]
        allowed = {
            "check": {"checked", "failed", "unknown"},
            "prove": {"proved", "failed", "unknown"},
            "trust": {"trusted", "unknown"},
        }
        if result_kind not in allowed[expectation]:
            raise ValueError("Evidence state/expectation mismatch")
        if result_kind == "trusted" and item["result"]["trust"] not in trust_ids:
            raise ValueError("Evidence trusted result has unknown trust")
    refs = evidence["conclusion"]["refs"]
    if refs != sorted(set(refs)) or any(ref not in obligation_ids for ref in refs):
        raise ValueError("Evidence conclusion refs drifted")
