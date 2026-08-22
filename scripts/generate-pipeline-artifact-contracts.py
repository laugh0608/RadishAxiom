#!/usr/bin/env python3
"""Generate Pipeline Artifact Contract v0.1 schemas and fixtures.

This dependency-free generator validates contract fixtures. It is not a Rust
compiler, SMT parser, ECMAScript parser, solver adapter, Node launcher, Evidence
producer, or independent checker.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = REPO_ROOT / "contracts/pipeline-artifacts-v0.1"
FORMAT_VERSION = "0.1"
PIPELINE_PROFILE = "raxc-keyed-finite-table-pipeline-v0.1"
CVC5_PROFILE = "cvc5-1.3.4-qf-uflia-v0.1"
NODE_TARGET_PROFILE = "node-24-esm-keyed-finite-table-v0.1"
NODE_INVOCATION_PROFILE = "node-24-esm-invocation-v0.1"
SEMANTICS_NAME = "keyed-finite-table-semantics"
SEMANTICS_SHA256 = "6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"
IR_VERSION = "0.1"
EVIDENCE_VERSION = "0.1"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

IR_PATH = Path("benchmarks/keyed-finite-table-v0.1/ax-b01/candidates/correct.ir.jcs")
IR_DOCUMENT_DIGEST = "sha256:1fa8846fb3ba15937e3e4b5848e74d84d89050711086d7462eb16175510b4154"
TOOL_REGISTRY_PATH = Path("contracts/toolchain-adapters-v0.1/registry.json")

DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CANONICAL_UINT_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
STABLE_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")

OBLIGATION_KINDS = (
    "contract-guarantee",
    "effect-empty",
    "field-origin",
    "group-conservation",
    "host-conformance",
    "input-conformance",
    "ir-structure",
    "key-cardinality",
    "noninterference",
    "numeric-range",
    "output-conformance",
    "row-coverage",
    "totality",
    "trust-boundary",
)

OBLIGATION_EXPECTATIONS = {
    "contract-guarantee": "prove",
    "effect-empty": "prove",
    "field-origin": "prove",
    "group-conservation": "prove",
    "host-conformance": "check",
    "input-conformance": "check",
    "ir-structure": "check",
    "key-cardinality": "prove",
    "noninterference": "prove",
    "numeric-range": "prove",
    "output-conformance": "check",
    "row-coverage": "prove",
    "totality": "prove",
    "trust-boundary": "trust",
}

STAGE_KINDS = {
    "P0": "capture-preflight",
    "P1": "normalize",
    "P2": "generate-obligations",
    "P3": "encode-query",
    "P4": "prove",
    "P5": "check-fixture",
    "P6": "generate-target",
    "P7": "execute-host",
    "P8": "compare-output",
    "P9": "assemble-results",
}

STAGE_RESULTS = (
    "completed",
    "error",
    "invalid",
    "not-run",
    "resource-exhausted",
    "timeout",
    "unavailable",
    "unsupported",
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


def content_id(domain: str, definition: Json) -> str:
    return raw_digest(domain.encode("ascii") + b"\0" + canonical_bytes(definition))


def entry(domain: str, definition: dict[str, Any]) -> dict[str, Any]:
    return {"definition": definition, "id": content_id(domain, definition)}


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
    actual = set(value)
    unknown = sorted(actual - members)
    if unknown:
        raise ContractError("unknown-member", unknown[0])
    missing = sorted(members - actual)
    if missing:
        raise ContractError("missing-member", missing[0])


def require_digest(value: Any, code: str = "invalid-digest") -> str:
    if not isinstance(value, str) or not DIGEST_PATTERN.fullmatch(value):
        raise ContractError(code)
    return value


def require_sorted_unique(values: list[str], code: str) -> None:
    if values != sorted(values) or len(values) != len(set(values)):
        raise ContractError(code)


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


def validate_semantics(value: Any) -> None:
    item = require_object(value)
    require_members(item, {"name", "sha256"})
    if item != semantics():
        raise ContractError("semantics-mismatch")


def validate_subject(value: Any) -> None:
    item = require_object(value, "invalid-subject")
    kind = item.get("kind")
    if kind in {"document", "program"}:
        require_members(item, {"ir_document_digest", "kind"})
        require_digest(item["ir_document_digest"])
        return
    if kind in {"node", "contract"}:
        require_members(item, {"id", "kind"})
        require_digest(item["id"])
        return
    if kind in {"node-path", "contract-path"}:
        require_members(item, {"id", "kind", "path"})
        require_digest(item["id"])
        path = require_array(item["path"], "invalid-subject")
        if not path or not all(isinstance(part, str) and part for part in path):
            raise ContractError("invalid-subject")
        return
    if kind == "interface":
        require_members(item, {"direction", "kind", "name"})
        if item["direction"] not in {"input", "output"}:
            raise ContractError("invalid-subject")
        if not isinstance(item["name"], str) or not item["name"]:
            raise ContractError("invalid-subject")
        return
    if kind == "field":
        require_members(item, {"direction", "interface", "kind", "name"})
        if item["direction"] not in {"input", "output"}:
            raise ContractError("invalid-subject")
        if not all(isinstance(item[key], str) and item[key] for key in ("interface", "name")):
            raise ContractError("invalid-subject")
        return
    if kind == "artifact":
        require_members(item, {"artifact", "kind"})
        require_digest(item["artifact"])
        return
    if kind == "trust":
        require_members(item, {"category", "kind", "scope"})
        if not all(isinstance(item[key], str) and item[key] for key in ("category", "scope")):
            raise ContractError("invalid-subject")
        return
    raise ContractError("invalid-subject")


def validate_obligation_set_bytes(data: bytes) -> dict[str, Any]:
    root = require_object(parse_canonical(data))
    require_members(
        root,
        {
            "format",
            "format_version",
            "ir_artifact",
            "ir_document_digest",
            "obligation_profile",
            "obligations",
            "semantics",
        },
    )
    if root["format"] != "axiom-obligation-set":
        raise ContractError("unsupported-format")
    if root["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    require_digest(root["ir_artifact"])
    require_digest(root["ir_document_digest"])
    validate_semantics(root["semantics"])
    profile = require_object(root["obligation_profile"])
    require_members(profile, {"name", "version"})
    if profile not in (
        {"name": "keyed-finite-table-benchmark", "version": "0.1"},
        {"name": "keyed-finite-table-verification", "version": "0.1"},
    ):
        raise ContractError("unsupported-profile")
    obligations = require_array(root["obligations"])
    if not obligations:
        raise ContractError("empty-obligation-set")
    ids: list[str] = []
    definitions: set[bytes] = set()
    for value in obligations:
        item = require_object(value)
        require_members(item, {"definition", "id"})
        obligation_id = require_digest(item["id"])
        definition = require_object(item["definition"])
        require_members(definition, {"expectation", "kind", "subject"})
        kind = definition["kind"]
        if kind not in OBLIGATION_KINDS:
            raise ContractError("unknown-obligation-kind")
        if definition["expectation"] != OBLIGATION_EXPECTATIONS[kind]:
            raise ContractError("expectation-mismatch")
        validate_subject(definition["subject"])
        expected_id = content_id("axiom-evidence-v0.1:obligation", definition)
        if obligation_id != expected_id:
            raise ContractError("obligation-id-mismatch")
        encoded = canonical_bytes(definition)
        if encoded in definitions:
            raise ContractError("duplicate-obligation")
        definitions.add(encoded)
        ids.append(obligation_id)
    require_sorted_unique(ids, "obligations-not-sorted")
    return root


def validate_host_value(value: Any) -> None:
    if type(value) is bool or isinstance(value, str):
        return
    item = require_object(value, "invalid-host-value")
    kind = item.get("kind")
    if kind == "none":
        require_members(item, {"kind"})
        return
    if kind == "some":
        require_members(item, {"kind", "value"})
        validate_host_value(item["value"])
        return
    raise ContractError("invalid-host-value")


def validate_host_data_bytes(data: bytes) -> dict[str, Any]:
    root = require_object(parse_canonical(data))
    require_members(
        root,
        {"format", "format_version", "ir_document_digest", "role", "tables"},
    )
    if root["format"] != "axiom-host-data":
        raise ContractError("unsupported-format")
    if root["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    require_digest(root["ir_document_digest"])
    if root["role"] not in {"input", "output"}:
        raise ContractError("unknown-host-role")
    tables = require_array(root["tables"])
    table_names: list[str] = []
    for table_value in tables:
        table = require_object(table_value)
        require_members(table, {"name", "rows"})
        name = table["name"]
        if not isinstance(name, str) or not name:
            raise ContractError("invalid-table-name")
        table_names.append(name)
        rows = require_array(table["rows"])
        for row_value in rows:
            row = require_object(row_value, "invalid-row")
            if not row:
                raise ContractError("invalid-row")
            for field_name, field_value in row.items():
                if not field_name:
                    raise ContractError("invalid-field-name")
                validate_host_value(field_value)
    require_sorted_unique(table_names, "tables-not-sorted")
    return root


def validate_query_bytes(data: bytes) -> None:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ContractError("query-not-ascii", str(exc)) from exc
    if "\r" in text:
        raise ContractError("query-line-ending")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ContractError("query-final-lf")
    if ";" in text:
        raise ContractError("query-comment-forbidden")
    forbidden = (
        (r"\((?:forall|exists)\b", "query-quantifier-forbidden"),
        (r"\(set-option\b", "query-option-forbidden"),
        (r"\b(?:String|Real|Float16|Float32|Float64)\b", "query-theory-forbidden"),
        (r"(?<![A-Za-z0-9_])[0-9]+\.[0-9]+", "query-float-forbidden"),
        (r"(?:/Users/|/home/|[A-Za-z]:\\)", "query-path-forbidden"),
        (r"(?i)(?:random|seed|timestamp|hostname)", "query-nondeterminism-forbidden"),
    )
    for pattern, code in forbidden:
        if re.search(pattern, text):
            raise ContractError(code)
    lines = text.splitlines()
    if not lines or lines[0] != "(set-logic QF_UFLIA)":
        raise ContractError("query-logic-mismatch")
    if lines[-1] != "(check-sat)":
        raise ContractError("query-check-sat-missing")
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ContractError("query-parentheses")
    if depth != 0:
        raise ContractError("query-parentheses")


def validate_target_bytes(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("target-invalid-utf8", str(exc)) from exc
    if "\r" in text:
        raise ContractError("target-line-ending")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ContractError("target-final-lf")
    if NODE_TARGET_PROFILE not in text:
        raise ContractError("target-profile-missing")
    forbidden = (
        (r"\bimport\b|\brequire\s*\(", "target-import-forbidden"),
        (r"\beval\s*\(|\bFunction\s*\(", "target-dynamic-code-forbidden"),
        (r"\bNumber\s*\(", "target-number-forbidden"),
        (r"\bprocess\.env\b", "target-environment-forbidden"),
        (r"\b(?:fetch|WebSocket|WebAssembly|Worker)\b", "target-capability-forbidden"),
        (r"\b(?:Date|Intl)\b|Math\.random|\.localeCompare\s*\(|\.normalize\s*\(", "target-nondeterminism-forbidden"),
        (r"(?:/Users/|/home/|[A-Za-z]:\\)", "target-path-forbidden"),
        (r"//# sourceMappingURL|/\*|//", "target-comment-forbidden"),
    )
    for pattern, code in forbidden:
        if re.search(pattern, text):
            raise ContractError(code)


def validate_artifact_ref(value: Any, artifact_ids: set[str]) -> tuple[str, str]:
    item = require_object(value)
    require_members(item, {"artifact", "role"})
    digest = require_digest(item["artifact"])
    if digest not in artifact_ids:
        raise ContractError("artifact-reference-unknown")
    role = item["role"]
    if not isinstance(role, str) or not STABLE_ID_PATTERN.fullmatch(role):
        raise ContractError("invalid-artifact-role")
    return role, digest


def validate_result(value: Any, allow_not_run: bool) -> str:
    item = require_object(value)
    kind = item.get("kind")
    if kind not in STAGE_RESULTS:
        raise ContractError("unknown-stage-result")
    if kind == "completed":
        require_members(item, {"kind"})
    elif kind == "not-run":
        if not allow_not_run:
            raise ContractError("attempt-not-run-forbidden")
        require_members(item, {"blocked_by", "kind"})
        blocker = require_object(item["blocked_by"])
        require_members(blocker, {"id", "kind"})
        if blocker["kind"] not in {"gate", "stage"}:
            raise ContractError("not-run-blocker")
        if not isinstance(blocker["id"], str) or not blocker["id"]:
            raise ContractError("not-run-blocker")
    else:
        require_members(item, {"code", "kind"})
        if not isinstance(item["code"], str) or not STABLE_ID_PATTERN.fullmatch(item["code"]):
            raise ContractError("invalid-stage-code")
    return kind


def validate_receipt_bytes(data: bytes) -> dict[str, Any]:
    root = require_object(parse_canonical(data))
    require_members(
        root,
        {
            "artifacts",
            "assurance_policy",
            "evidence_version",
            "format",
            "format_version",
            "ir_version",
            "mode",
            "outcome",
            "pipeline_profile",
            "semantics",
            "stages",
            "tools",
            "verification_gate",
        },
    )
    if root["format"] != "axiom-pipeline-receipt":
        raise ContractError("unsupported-format")
    if root["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    if root["pipeline_profile"] != PIPELINE_PROFILE:
        raise ContractError("unsupported-profile")
    if root["mode"] not in {"benchmark-node24", "verification"}:
        raise ContractError("unsupported-mode")
    if root["ir_version"] != IR_VERSION or root["evidence_version"] != EVIDENCE_VERSION:
        raise ContractError("unsupported-version")
    if root["outcome"] not in {"blocked", "completed", "error", "partial"}:
        raise ContractError("unknown-receipt-outcome")
    validate_semantics(root["semantics"])
    policy_digest = require_digest(root["assurance_policy"])

    artifacts = require_array(root["artifacts"])
    artifact_ids: list[str] = []
    for value in artifacts:
        item = require_object(value)
        require_members(item, {"byte_length", "content_digest", "format", "format_version"})
        if not isinstance(item["byte_length"], str) or not CANONICAL_UINT_PATTERN.fullmatch(item["byte_length"]):
            raise ContractError("invalid-byte-length")
        artifact_ids.append(require_digest(item["content_digest"]))
        if not all(isinstance(item[key], str) and item[key] for key in ("format", "format_version")):
            raise ContractError("invalid-artifact-format")
    require_sorted_unique(artifact_ids, "artifacts-not-sorted")
    artifact_id_set = set(artifact_ids)
    if policy_digest not in artifact_id_set:
        raise ContractError("assurance-policy-missing")

    tools = require_array(root["tools"])
    tool_ids: list[str] = []
    for value in tools:
        item = require_object(value)
        require_members(item, {"definition", "id"})
        tool_id = require_digest(item["id"])
        definition = require_object(item["definition"])
        require_members(definition, {"artifact", "name", "roles", "version"})
        if require_digest(definition["artifact"]) not in artifact_id_set:
            raise ContractError("tool-artifact-missing")
        roles = require_array(definition["roles"])
        if not roles or not all(isinstance(role, str) and role for role in roles):
            raise ContractError("invalid-tool-role")
        require_sorted_unique(roles, "tool-roles-not-sorted")
        if not all(isinstance(definition[key], str) and definition[key] for key in ("name", "version")):
            raise ContractError("invalid-tool-identity")
        if tool_id != content_id("axiom-evidence-v0.1:tool", definition):
            raise ContractError("tool-id-mismatch")
        tool_ids.append(tool_id)
    require_sorted_unique(tool_ids, "tools-not-sorted")
    tool_id_set = set(tool_ids)

    stages = require_array(root["stages"])
    stage_ids = [require_object(item).get("id") for item in stages]
    if stage_ids != list(STAGE_KINDS):
        raise ContractError("stages-not-sorted")
    attempt_ids: set[str] = set()
    stage_results: dict[str, str] = {}
    stage_by_id: dict[str, dict[str, Any]] = {}
    for value in stages:
        item = require_object(value)
        require_members(item, {"attempts", "dependencies", "id", "kind", "result"})
        stage_id = item["id"]
        if item["kind"] != STAGE_KINDS.get(stage_id):
            raise ContractError("stage-kind-mismatch")
        dependencies = require_array(item["dependencies"])
        if dependencies != sorted(set(dependencies)):
            raise ContractError("dependencies-not-sorted")
        if any(dependency not in STAGE_KINDS for dependency in dependencies):
            raise ContractError("dependency-unknown")
        stage_result = validate_result(item["result"], allow_not_run=True)
        stage_results[stage_id] = stage_result
        stage_by_id[stage_id] = item
        attempts = require_array(item["attempts"])
        if stage_result == "not-run":
            if attempts:
                raise ContractError("not-run-has-attempt")
            continue
        if not attempts:
            raise ContractError("stage-attempt-missing")
        ordinals: list[str] = []
        final_attempt_result = ""
        for attempt_value in attempts:
            attempt = require_object(attempt_value)
            require_members(attempt, {"definition", "id"})
            attempt_id = require_digest(attempt["id"])
            definition = require_object(attempt["definition"])
            require_members(
                definition,
                {
                    "adapter_profile",
                    "cache",
                    "inputs",
                    "limits",
                    "options",
                    "ordinal",
                    "outputs",
                    "result",
                    "tool",
                },
            )
            if definition["tool"] not in tool_id_set:
                raise ContractError("tool-reference-unknown")
            ordinals.append(definition["ordinal"])
            if not CANONICAL_UINT_PATTERN.fullmatch(definition["ordinal"]):
                raise ContractError("invalid-attempt-ordinal")
            adapter = require_object(definition["adapter_profile"])
            adapter_kind = adapter.get("kind")
            if adapter_kind == "not-applicable":
                require_members(adapter, {"kind"})
            elif adapter_kind == "profile":
                require_members(adapter, {"kind", "value"})
                allowed_profiles = {CVC5_PROFILE, NODE_INVOCATION_PROFILE, NODE_TARGET_PROFILE}
                if adapter["value"] not in allowed_profiles:
                    raise ContractError("adapter-profile-unknown")
            else:
                raise ContractError("adapter-profile-unknown")
            input_values = require_array(definition["inputs"])
            input_keys = [validate_artifact_ref(ref, artifact_id_set) for ref in input_values]
            if input_keys != sorted(set(input_keys)):
                raise ContractError("artifact-refs-not-sorted")
            output_values = require_array(definition["outputs"])
            output_keys = [validate_artifact_ref(ref, artifact_id_set) for ref in output_values]
            if output_keys != sorted(set(output_keys)):
                raise ContractError("artifact-refs-not-sorted")
            limit_values = require_array(definition["limits"])
            limit_keys: list[tuple[str, str]] = []
            for limit_value in limit_values:
                limit = require_object(limit_value)
                require_members(limit, {"name", "unit", "value"})
                if not CANONICAL_UINT_PATTERN.fullmatch(limit["value"]):
                    raise ContractError("invalid-limit")
                limit_keys.append((limit["name"], limit["unit"]))
            if limit_keys != sorted(set(limit_keys)):
                raise ContractError("limits-not-sorted")
            options_digest = require_digest(definition["options"])
            if options_digest not in artifact_id_set:
                raise ContractError("options-artifact-missing")
            expected_cache = cache_key(
                adapter_profile=adapter,
                assurance_policy=policy_digest,
                inputs=input_values,
                limits_value=limit_values,
                options=options_digest,
                stage_id=stage_id,
                tool=definition["tool"],
            )
            cache = require_object(definition["cache"])
            require_members(cache, {"key", "kind"})
            if cache["key"] != expected_cache:
                raise ContractError("cache-key-mismatch")
            if cache["kind"] not in {"hit", "miss"}:
                raise ContractError("cache-kind-unknown")
            if cache["kind"] == "hit" and not output_values:
                raise ContractError("cache-hit-invalid")
            final_attempt_result = validate_result(definition["result"], allow_not_run=False)
            expected_attempt_id = content_id("axiom-pipeline-v0.1:attempt", definition)
            if attempt_id != expected_attempt_id:
                raise ContractError("attempt-id-mismatch")
            if attempt_id in attempt_ids:
                raise ContractError("duplicate-attempt")
            attempt_ids.add(attempt_id)
        expected_ordinals = [str(index) for index in range(len(ordinals))]
        if ordinals != expected_ordinals:
            raise ContractError("attempts-not-ordered")
        if final_attempt_result != stage_result:
            raise ContractError("stage-result-mismatch")

    gate = require_object(root["verification_gate"])
    require_members(gate, {"decision", "id", "requirements"})
    if gate["id"] != "verification-gate" or gate["decision"] not in {"closed", "opened"}:
        raise ContractError("gate-invalid")
    requirements = require_array(gate["requirements"])
    expected_requirement_kinds = [
        "all-prove-proved",
        "all-trust-declared",
        "assurance-policy-accepted",
        "input-checked",
        "ir-accepted",
    ]
    requirement_kinds = [require_object(value).get("kind") for value in requirements]
    if requirement_kinds != expected_requirement_kinds:
        raise ContractError("gate-requirements-not-sorted")
    obligation_ids = {
        item["id"] for item in build_obligation_set()["obligations"]
    }
    statuses: list[str] = []
    for value in requirements:
        requirement = require_object(value)
        require_members(requirement, {"kind", "refs", "status"})
        if requirement["status"] not in {"satisfied", "unsatisfied"}:
            raise ContractError("gate-status-unknown")
        statuses.append(requirement["status"])
        refs = require_array(requirement["refs"])
        ref_keys: list[tuple[str, str]] = []
        for ref_value in refs:
            ref = require_object(ref_value)
            require_members(ref, {"kind", "value"})
            ref_kind = ref["kind"]
            ref_id = require_digest(ref["value"])
            if ref_kind == "artifact" and ref_id not in artifact_id_set:
                raise ContractError("gate-reference-unknown")
            if ref_kind == "attempt" and ref_id not in attempt_ids:
                raise ContractError("gate-reference-unknown")
            if ref_kind == "obligation" and ref_id not in obligation_ids:
                raise ContractError("gate-reference-unknown")
            if ref_kind not in {"artifact", "attempt", "obligation"}:
                raise ContractError("gate-reference-unknown")
            ref_keys.append((ref_kind, ref_id))
        if ref_keys != sorted(set(ref_keys)):
            raise ContractError("gate-refs-not-sorted")
    expected_decision = "opened" if all(status == "satisfied" for status in statuses) else "closed"
    if gate["decision"] != expected_decision:
        raise ContractError("gate-decision-mismatch")
    if gate["decision"] == "opened":
        if any(stage_results[stage_id] != "completed" for stage_id in ("P1", "P2", "P3", "P4", "P5")):
            raise ContractError("gate-bypass")
        if any(stage_results[stage_id] != "completed" for stage_id in ("P6", "P7", "P8")):
            raise ContractError("gate-open-target-missing")
    else:
        if any(stage_results[stage_id] != "not-run" for stage_id in ("P6", "P7", "P8")):
            raise ContractError("gate-bypass")
    if root["outcome"] == "completed" and (
        gate["decision"] != "opened"
        or any(result != "completed" for result in stage_results.values())
    ):
        raise ContractError("receipt-outcome-mismatch")
    if root["outcome"] == "partial" and all(
        result == "completed" for result in stage_results.values()
    ):
        raise ContractError("receipt-outcome-mismatch")
    return root


def mutate(value: dict[str, Any], callback: Callable[[dict[str, Any]], None]) -> bytes:
    result = copy.deepcopy(value)
    callback(result)
    return canonical_bytes(result)


def negative_json_fixtures(
    obligation_set: dict[str, Any],
    host_input: dict[str, Any],
    completed_receipt: dict[str, Any],
    partial_receipt: dict[str, Any],
) -> dict[str, tuple[bytes, str, str]]:
    fixtures: dict[str, tuple[bytes, str, str]] = {}

    def add_obligation(name: str, callback: Callable[[dict[str, Any]], None], code: str) -> None:
        fixtures[f"obligation-{name}.invalid.jcs"] = (
            mutate(obligation_set, callback),
            code,
            "obligation-set",
        )

    add_obligation("unknown-member", lambda value: value.__setitem__("extra", "x"), "unknown-member")
    add_obligation("unknown-version", lambda value: value.__setitem__("format_version", "0.2"), "unsupported-version")
    add_obligation(
        "unknown-profile",
        lambda value: value.__setitem__("obligation_profile", {"name": "unknown", "version": "0.1"}),
        "unsupported-profile",
    )
    add_obligation("unsorted", lambda value: value["obligations"].reverse(), "obligations-not-sorted")
    add_obligation("duplicate", lambda value: value["obligations"].append(copy.deepcopy(value["obligations"][0])), "duplicate-obligation")
    add_obligation("id-mismatch", lambda value: value["obligations"][0].__setitem__("id", "sha256:" + "f" * 64), "obligation-id-mismatch")
    add_obligation("expectation-mismatch", lambda value: value["obligations"][0]["definition"].__setitem__("expectation", "trust"), "expectation-mismatch")
    add_obligation("unknown-subject", lambda value: value["obligations"][0]["definition"].__setitem__("subject", {"kind": "mystery"}), "invalid-subject")

    def add_host(name: str, callback: Callable[[dict[str, Any]], None], code: str) -> None:
        fixtures[f"host-{name}.invalid.jcs"] = (
            mutate(host_input, callback),
            code,
            "host-data",
        )

    add_host("unknown-member", lambda value: value.__setitem__("extra", "x"), "unknown-member")
    add_host("unknown-version", lambda value: value.__setitem__("format_version", "0.2"), "unsupported-version")
    add_host("unknown-role", lambda value: value.__setitem__("role", "golden-output"), "unknown-host-role")
    add_host(
        "unsorted-tables",
        lambda value: value["tables"].extend(
            [{"name": "accounts", "rows": [{"id": "A1"}]}]
        ),
        "tables-not-sorted",
    )
    add_host(
        "duplicate-table",
        lambda value: value["tables"].append(copy.deepcopy(value["tables"][0])),
        "tables-not-sorted",
    )
    add_host(
        "invalid-option",
        lambda value: value["tables"][0]["rows"][0].__setitem__(
            "discount_cents", {"kind": "unknown"}
        ),
        "invalid-host-value",
    )
    fixtures["host-json-number.invalid.jcs"] = (
        canonical_bytes(host_input).replace(b'"100"', b"100", 1),
        "json-number-or-null",
        "host-data",
    )
    fixtures["host-json-null.invalid.jcs"] = (
        canonical_bytes(host_input).replace(b'"100"', b"null", 1),
        "json-number-or-null",
        "host-data",
    )

    def add_receipt(
        name: str,
        source: dict[str, Any],
        callback: Callable[[dict[str, Any]], None],
        code: str,
    ) -> None:
        fixtures[f"receipt-{name}.invalid.jcs"] = (
            mutate(source, callback),
            code,
            "receipt",
        )

    add_receipt("unknown-member", completed_receipt, lambda value: value.__setitem__("extra", "x"), "unknown-member")
    add_receipt("unknown-version", completed_receipt, lambda value: value.__setitem__("format_version", "0.2"), "unsupported-version")
    add_receipt("unknown-profile", completed_receipt, lambda value: value.__setitem__("pipeline_profile", "latest"), "unsupported-profile")
    add_receipt(
        "unknown-tool",
        completed_receipt,
        lambda value: value["stages"][0]["attempts"][0]["definition"].__setitem__("tool", "sha256:" + "f" * 64),
        "tool-reference-unknown",
    )
    add_receipt("unsorted-stages", completed_receipt, lambda value: value["stages"].reverse(), "stages-not-sorted")
    add_receipt(
        "gate-bypass",
        partial_receipt,
        lambda value: value["verification_gate"].__setitem__("decision", "opened"),
        "gate-decision-mismatch",
    )
    add_receipt(
        "gate-reference",
        completed_receipt,
        lambda value: value["verification_gate"]["requirements"][0]["refs"][0].__setitem__("value", "sha256:" + "f" * 64),
        "gate-reference-unknown",
    )
    add_receipt(
        "cache-key",
        completed_receipt,
        lambda value: value["stages"][0]["attempts"][0]["definition"]["cache"].__setitem__("key", "sha256:" + "f" * 64),
        "cache-key-mismatch",
    )
    add_receipt(
        "not-run-blocker",
        partial_receipt,
        lambda value: value["stages"][6].__setitem__("result", {"kind": "not-run"}),
        "missing-member",
    )
    add_receipt(
        "cache-hit-without-output",
        completed_receipt,
        lambda value: (
            value["stages"][4]["attempts"][0]["definition"]["cache"].__setitem__("kind", "hit"),
            value["stages"][4]["attempts"][0]["definition"].__setitem__("outputs", []),
        ),
        "cache-hit-invalid",
    )
    return fixtures


def raw_negative_fixtures(query: bytes, target: bytes) -> dict[str, tuple[bytes, str, str]]:
    return {
        "query-comment.invalid.smt2": (
            query.replace(b"(check-sat)\n", b"; hidden\n(check-sat)\n"),
            "query-comment-forbidden",
            "query",
        ),
        "query-crlf.invalid.smt2": (
            query.replace(b"\n", b"\r\n"),
            "query-line-ending",
            "query",
        ),
        "query-extra-final-lf.invalid.smt2": (
            query + b"\n",
            "query-final-lf",
            "query",
        ),
        "query-missing-final-lf.invalid.smt2": (
            query[:-1],
            "query-final-lf",
            "query",
        ),
        "query-option.invalid.smt2": (
            query.replace(b"(set-logic", b"(set-option :produce-models true)\n(set-logic"),
            "query-option-forbidden",
            "query",
        ),
        "query-quantifier.invalid.smt2": (
            query.replace(b"(check-sat)\n", b"(assert (forall ((x Int)) (= x x)))\n(check-sat)\n"),
            "query-quantifier-forbidden",
            "query",
        ),
        "target-crlf.mjs.invalid": (
            target.replace(b"\n", b"\r\n"),
            "target-line-ending",
            "target",
        ),
        "target-environment.mjs.invalid": (
            target.replace(b"if (", b"const hidden = process.env.SECRET;\nif (", 1),
            "target-environment-forbidden",
            "target",
        ),
        "target-eval.mjs.invalid": (
            target.replace(b"if (", b'eval("0");\nif (', 1),
            "target-dynamic-code-forbidden",
            "target",
        ),
        "target-import.mjs.invalid": (
            b'import "node:fs";\n' + target,
            "target-import-forbidden",
            "target",
        ),
        "target-missing-final-lf.mjs.invalid": (
            target[:-1],
            "target-final-lf",
            "target",
        ),
        "target-number.mjs.invalid": (
            target.replace(b"if (", b"const lossy = Number(1n);\nif (", 1),
            "target-number-forbidden",
            "target",
        ),
    }


def schema_common_defs() -> dict[str, Any]:
    digest = {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"}
    semantics_schema = {
        "additionalProperties": False,
        "properties": {
            "name": {"const": SEMANTICS_NAME},
            "sha256": {"const": SEMANTICS_SHA256},
        },
        "required": ["name", "sha256"],
        "type": "object",
    }
    return {"digest": digest, "semantics": semantics_schema}


def obligation_schema() -> dict[str, Any]:
    defs = schema_common_defs()
    defs["subject"] = {
        "oneOf": [
            {
                "additionalProperties": False,
                "properties": {
                    "ir_document_digest": {"$ref": "#/$defs/digest"},
                    "kind": {"enum": ["document", "program"]},
                },
                "required": ["ir_document_digest", "kind"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "id": {"$ref": "#/$defs/digest"},
                    "kind": {"enum": ["contract", "node"]},
                },
                "required": ["id", "kind"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "id": {"$ref": "#/$defs/digest"},
                    "kind": {"enum": ["contract-path", "node-path"]},
                    "path": {"items": {"minLength": 1, "type": "string"}, "minItems": 1, "type": "array"},
                },
                "required": ["id", "kind", "path"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "direction": {"enum": ["input", "output"]},
                    "kind": {"const": "interface"},
                    "name": {"minLength": 1, "type": "string"},
                },
                "required": ["direction", "kind", "name"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "direction": {"enum": ["input", "output"]},
                    "interface": {"minLength": 1, "type": "string"},
                    "kind": {"const": "field"},
                    "name": {"minLength": 1, "type": "string"},
                },
                "required": ["direction", "interface", "kind", "name"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "artifact": {"$ref": "#/$defs/digest"},
                    "kind": {"const": "artifact"},
                },
                "required": ["artifact", "kind"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "category": {"minLength": 1, "type": "string"},
                    "kind": {"const": "trust"},
                    "scope": {"minLength": 1, "type": "string"},
                },
                "required": ["category", "kind", "scope"],
                "type": "object",
            },
        ]
    }
    defs["obligation"] = {
        "additionalProperties": False,
        "properties": {
            "definition": {
                "additionalProperties": False,
                "properties": {
                    "expectation": {"enum": ["check", "prove", "trust"]},
                    "kind": {"enum": list(OBLIGATION_KINDS)},
                    "subject": {"$ref": "#/$defs/subject"},
                },
                "required": ["expectation", "kind", "subject"],
                "type": "object",
            },
            "id": {"$ref": "#/$defs/digest"},
        },
        "required": ["definition", "id"],
        "type": "object",
    }
    return {
        "$defs": defs,
        "$id": "https://radishaxiom.dev/schema/pipeline-artifacts/axiom-obligation-set/0.1",
        "$schema": SCHEMA_DIALECT,
        "additionalProperties": False,
        "properties": {
            "format": {"const": "axiom-obligation-set"},
            "format_version": {"const": "0.1"},
            "ir_artifact": {"$ref": "#/$defs/digest"},
            "ir_document_digest": {"$ref": "#/$defs/digest"},
            "obligation_profile": {
                "additionalProperties": False,
                "properties": {
                    "name": {"enum": ["keyed-finite-table-benchmark", "keyed-finite-table-verification"]},
                    "version": {"const": "0.1"},
                },
                "required": ["name", "version"],
                "type": "object",
            },
            "obligations": {"items": {"$ref": "#/$defs/obligation"}, "minItems": 1, "type": "array"},
            "semantics": {"$ref": "#/$defs/semantics"},
        },
        "required": ["format", "format_version", "ir_artifact", "ir_document_digest", "obligation_profile", "obligations", "semantics"],
        "title": "Axiom obligation set v0.1",
        "type": "object",
    }


def host_data_schema() -> dict[str, Any]:
    defs = schema_common_defs()
    defs["option"] = {
        "oneOf": [
            {
                "additionalProperties": False,
                "properties": {"kind": {"const": "none"}},
                "required": ["kind"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "kind": {"const": "some"},
                    "value": {"$ref": "#/$defs/value"},
                },
                "required": ["kind", "value"],
                "type": "object",
            },
        ]
    }
    defs["value"] = {
        "oneOf": [
            {"type": "boolean"},
            {"type": "string"},
            {"$ref": "#/$defs/option"},
        ]
    }
    defs["row"] = {
        "additionalProperties": {"$ref": "#/$defs/value"},
        "minProperties": 1,
        "type": "object",
    }
    return {
        "$defs": defs,
        "$id": "https://radishaxiom.dev/schema/pipeline-artifacts/axiom-host-data/0.1",
        "$schema": SCHEMA_DIALECT,
        "additionalProperties": False,
        "properties": {
            "format": {"const": "axiom-host-data"},
            "format_version": {"const": "0.1"},
            "ir_document_digest": {"$ref": "#/$defs/digest"},
            "role": {"enum": ["input", "output"]},
            "tables": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "name": {"minLength": 1, "type": "string"},
                        "rows": {"items": {"$ref": "#/$defs/row"}, "type": "array"},
                    },
                    "required": ["name", "rows"],
                    "type": "object",
                },
                "type": "array",
            },
        },
        "required": ["format", "format_version", "ir_document_digest", "role", "tables"],
        "title": "Axiom host data v0.1",
        "type": "object",
    }


def receipt_schema() -> dict[str, Any]:
    defs = schema_common_defs()
    defs["artifactRef"] = {
        "additionalProperties": False,
        "properties": {
            "artifact": {"$ref": "#/$defs/digest"},
            "role": {"pattern": "^[A-Za-z][A-Za-z0-9._-]*$", "type": "string"},
        },
        "required": ["artifact", "role"],
        "type": "object",
    }
    defs["result"] = {
        "oneOf": [
            {
                "additionalProperties": False,
                "properties": {"kind": {"const": "completed"}},
                "required": ["kind"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "code": {"pattern": "^[A-Za-z][A-Za-z0-9._-]*$", "type": "string"},
                    "kind": {"enum": ["error", "invalid", "resource-exhausted", "timeout", "unavailable", "unsupported"]},
                },
                "required": ["code", "kind"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "blocked_by": {
                        "additionalProperties": False,
                        "properties": {
                            "id": {"minLength": 1, "type": "string"},
                            "kind": {"enum": ["gate", "stage"]},
                        },
                        "required": ["id", "kind"],
                        "type": "object",
                    },
                    "kind": {"const": "not-run"},
                },
                "required": ["blocked_by", "kind"],
                "type": "object",
            },
        ]
    }
    defs["attempt"] = {
        "additionalProperties": False,
        "properties": {
            "definition": {
                "additionalProperties": False,
                "properties": {
                    "adapter_profile": {
                        "oneOf": [
                            {
                                "additionalProperties": False,
                                "properties": {"kind": {"const": "not-applicable"}},
                                "required": ["kind"],
                                "type": "object",
                            },
                            {
                                "additionalProperties": False,
                                "properties": {
                                    "kind": {"const": "profile"},
                                    "value": {"enum": [CVC5_PROFILE, NODE_INVOCATION_PROFILE, NODE_TARGET_PROFILE]},
                                },
                                "required": ["kind", "value"],
                                "type": "object",
                            },
                        ]
                    },
                    "cache": {
                        "additionalProperties": False,
                        "properties": {
                            "key": {"$ref": "#/$defs/digest"},
                            "kind": {"enum": ["hit", "miss"]},
                        },
                        "required": ["key", "kind"],
                        "type": "object",
                    },
                    "inputs": {"items": {"$ref": "#/$defs/artifactRef"}, "type": "array"},
                    "limits": {
                        "items": {
                            "additionalProperties": False,
                            "properties": {
                                "name": {"minLength": 1, "type": "string"},
                                "unit": {"minLength": 1, "type": "string"},
                                "value": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
                            },
                            "required": ["name", "unit", "value"],
                            "type": "object",
                        },
                        "type": "array",
                    },
                    "options": {"$ref": "#/$defs/digest"},
                    "ordinal": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
                    "outputs": {"items": {"$ref": "#/$defs/artifactRef"}, "type": "array"},
                    "result": {"$ref": "#/$defs/result"},
                    "tool": {"$ref": "#/$defs/digest"},
                },
                "required": ["adapter_profile", "cache", "inputs", "limits", "options", "ordinal", "outputs", "result", "tool"],
                "type": "object",
            },
            "id": {"$ref": "#/$defs/digest"},
        },
        "required": ["definition", "id"],
        "type": "object",
    }
    return {
        "$defs": defs,
        "$id": "https://radishaxiom.dev/schema/pipeline-artifacts/axiom-pipeline-receipt/0.1",
        "$schema": SCHEMA_DIALECT,
        "additionalProperties": False,
        "properties": {
            "artifacts": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "byte_length": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
                        "content_digest": {"$ref": "#/$defs/digest"},
                        "format": {"minLength": 1, "type": "string"},
                        "format_version": {"minLength": 1, "type": "string"},
                    },
                    "required": ["byte_length", "content_digest", "format", "format_version"],
                    "type": "object",
                },
                "type": "array",
            },
            "assurance_policy": {"$ref": "#/$defs/digest"},
            "evidence_version": {"const": "0.1"},
            "format": {"const": "axiom-pipeline-receipt"},
            "format_version": {"const": "0.1"},
            "ir_version": {"const": "0.1"},
            "mode": {"enum": ["benchmark-node24", "verification"]},
            "outcome": {"enum": ["blocked", "completed", "error", "partial"]},
            "pipeline_profile": {"const": PIPELINE_PROFILE},
            "semantics": {"$ref": "#/$defs/semantics"},
            "stages": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "attempts": {"items": {"$ref": "#/$defs/attempt"}, "type": "array"},
                        "dependencies": {"items": {"enum": list(STAGE_KINDS)}, "type": "array"},
                        "id": {"enum": list(STAGE_KINDS)},
                        "kind": {"enum": list(STAGE_KINDS.values())},
                        "result": {"$ref": "#/$defs/result"},
                    },
                    "required": ["attempts", "dependencies", "id", "kind", "result"],
                    "type": "object",
                },
                "maxItems": 10,
                "minItems": 10,
                "type": "array",
            },
            "tools": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "definition": {
                            "additionalProperties": False,
                            "properties": {
                                "artifact": {"$ref": "#/$defs/digest"},
                                "name": {"minLength": 1, "type": "string"},
                                "roles": {"items": {"minLength": 1, "type": "string"}, "minItems": 1, "type": "array"},
                                "version": {"minLength": 1, "type": "string"},
                            },
                            "required": ["artifact", "name", "roles", "version"],
                            "type": "object",
                        },
                        "id": {"$ref": "#/$defs/digest"},
                    },
                    "required": ["definition", "id"],
                    "type": "object",
                },
                "minItems": 1,
                "type": "array",
            },
            "verification_gate": {
                "additionalProperties": False,
                "properties": {
                    "decision": {"enum": ["closed", "opened"]},
                    "id": {"const": "verification-gate"},
                    "requirements": {
                        "items": {
                            "additionalProperties": False,
                            "properties": {
                                "kind": {"enum": ["all-prove-proved", "all-trust-declared", "assurance-policy-accepted", "input-checked", "ir-accepted"]},
                                "refs": {
                                    "items": {
                                        "additionalProperties": False,
                                        "properties": {
                                            "kind": {"enum": ["artifact", "attempt", "obligation"]},
                                            "value": {"$ref": "#/$defs/digest"},
                                        },
                                        "required": ["kind", "value"],
                                        "type": "object",
                                    },
                                    "type": "array",
                                },
                                "status": {"enum": ["satisfied", "unsatisfied"]},
                            },
                            "required": ["kind", "refs", "status"],
                            "type": "object",
                        },
                        "maxItems": 5,
                        "minItems": 5,
                        "type": "array",
                    },
                },
                "required": ["decision", "id", "requirements"],
                "type": "object",
            },
        },
        "required": ["artifacts", "assurance_policy", "evidence_version", "format", "format_version", "ir_version", "mode", "outcome", "pipeline_profile", "semantics", "stages", "tools", "verification_gate"],
        "title": "Axiom pipeline receipt v0.1",
        "type": "object",
    }


def generated_contract(expected_files: dict[str, bytes], negatives: dict[str, tuple[bytes, str, str]]) -> dict[str, Any]:
    bindings = []
    for name, path in (
        ("adr-0007", Path("docs/adr/0007-first-verification-first-compilation-pipeline.md")),
        ("axiom-evidence-v0.1", Path("docs/evidence/axiom-evidence-v0.md")),
        ("axiom-ir-v0.1", Path("docs/ir/axiom-ir-v0.md")),
        ("keyed-finite-table-semantics", Path("docs/semantics/keyed-finite-table-semantics.md")),
        ("toolchain-adapter-identities-v0.1", TOOL_REGISTRY_PATH),
    ):
        data = (REPO_ROOT / path).read_bytes()
        binding: dict[str, str] = {
            "name": name,
            "path": path.as_posix(),
            "raw_sha256": raw_digest(data),
        }
        if path == TOOL_REGISTRY_PATH:
            registry = json.loads(data)
            binding["registry_digest"] = registry["registry_digest"]
        bindings.append(binding)
    bindings.sort(key=lambda item: item["name"])

    generated = [
        {
            "byte_length": str(len(data)),
            "path": path,
            "sha256": raw_digest(data),
        }
        for path, data in sorted(expected_files.items())
        if path != "contract.json"
    ]
    return {
        "bindings": bindings,
        "content_domains": {
            "attempt": "axiom-pipeline-v0.1:attempt",
            "cache_key": "axiom-pipeline-v0.1:cache-key",
            "obligation": "axiom-evidence-v0.1:obligation",
            "tool": "axiom-evidence-v0.1:tool",
        },
        "formats": [
            {"kind": "canonical-json", "name": "axiom-host-data", "schema": "schemas/axiom-host-data.schema.json", "version": "0.1"},
            {"kind": "canonical-json", "name": "axiom-obligation-set", "schema": "schemas/axiom-obligation-set.schema.json", "version": "0.1"},
            {"kind": "raw-utf8-lf", "name": "axiom-node-esm", "profile": NODE_TARGET_PROFILE, "version": NODE_TARGET_PROFILE},
            {"kind": "canonical-json", "name": "axiom-pipeline-receipt", "schema": "schemas/axiom-pipeline-receipt.schema.json", "version": "0.1"},
            {"kind": "raw-ascii-lf", "name": "axiom-smtlib2-qf-uflia-query", "profile": CVC5_PROFILE, "version": "0.1"},
        ],
        "generated_files": generated,
        "negative_fixture_count": str(len(negatives)),
        "pipeline_profile": PIPELINE_PROFILE,
        "raw_byte_profiles": {
            "axiom-node-esm": {
                "encoding": "UTF-8",
                "final_lf": "exactly-one",
                "line_endings": "LF",
                "validator_scope": "contract-fixture-subset-not-a-complete-ecmascript-parser",
            },
            "axiom-smtlib2-qf-uflia-query": {
                "encoding": "ASCII",
                "final_lf": "exactly-one",
                "line_endings": "LF",
                "validator_scope": "contract-fixture-subset-not-a-complete-smtlib-parser",
            },
        },
        "version": "0.1",
    }


def build_outputs() -> dict[Path, bytes]:
    obligation_set = build_obligation_set()
    host_input = build_host_data("input")
    host_output = build_host_data("output")
    totality_id = next(
        item["id"]
        for item in obligation_set["obligations"]
        if item["definition"]["kind"] == "totality"
    )
    fixture_bytes: dict[str, bytes] = {
        "fixtures/minimal/host-input.jcs": canonical_bytes(host_input),
        "fixtures/minimal/host-output.jcs": canonical_bytes(host_output),
        "fixtures/minimal/obligation-set.jcs": canonical_bytes(obligation_set),
        "fixtures/minimal/options.jcs": canonical_bytes(build_options()),
        "fixtures/minimal/policy.jcs": canonical_bytes(build_policy()),
        "fixtures/minimal/query.smt2": build_query(totality_id),
        "fixtures/minimal/target.mjs": build_target_module(),
        "fixtures/minimal/tool.txt": b"synthetic pipeline contract tool artifact; not executable\n",
    }
    completed_receipt = build_receipt(fixture_bytes, obligation_set, partial=False)
    partial_receipt = build_receipt(fixture_bytes, obligation_set, partial=True)
    fixture_bytes["fixtures/minimal/receipt.jcs"] = canonical_bytes(completed_receipt)
    fixture_bytes["fixtures/partial/backend-timeout.receipt.jcs"] = canonical_bytes(partial_receipt)

    negatives = negative_json_fixtures(
        obligation_set, host_input, completed_receipt, partial_receipt
    )
    negatives.update(
        raw_negative_fixtures(
            fixture_bytes["fixtures/minimal/query.smt2"],
            fixture_bytes["fixtures/minimal/target.mjs"],
        )
    )
    expected_index = {
        "negative": [
            {
                "expected_code": code,
                "kind": kind,
                "path": f"fixtures/negative/{name}",
                "sha256": raw_digest(data),
            }
            for name, (data, code, kind) in sorted(negatives.items())
        ],
        "positive": [
            {
                "byte_length": str(len(data)),
                "path": path,
                "sha256": raw_digest(data),
            }
            for path, data in sorted(fixture_bytes.items())
        ],
    }

    output_bytes: dict[str, bytes] = dict(fixture_bytes)
    for name, (data, _, _) in negatives.items():
        output_bytes[f"fixtures/negative/{name}"] = data
    output_bytes["fixtures/expected.json"] = pretty_bytes(expected_index)
    output_bytes["schemas/axiom-host-data.schema.json"] = pretty_bytes(host_data_schema())
    output_bytes["schemas/axiom-obligation-set.schema.json"] = pretty_bytes(obligation_schema())
    output_bytes["schemas/axiom-pipeline-receipt.schema.json"] = pretty_bytes(receipt_schema())
    contract = generated_contract(output_bytes, negatives)
    output_bytes["contract.json"] = pretty_bytes(contract)

    validate_obligation_set_bytes(fixture_bytes["fixtures/minimal/obligation-set.jcs"])
    validate_host_data_bytes(fixture_bytes["fixtures/minimal/host-input.jcs"])
    validate_host_data_bytes(fixture_bytes["fixtures/minimal/host-output.jcs"])
    validate_query_bytes(fixture_bytes["fixtures/minimal/query.smt2"])
    validate_target_bytes(fixture_bytes["fixtures/minimal/target.mjs"])
    validate_receipt_bytes(fixture_bytes["fixtures/minimal/receipt.jcs"])
    validate_receipt_bytes(fixture_bytes["fixtures/partial/backend-timeout.receipt.jcs"])
    for name, (data, expected_code, kind) in negatives.items():
        validator: Callable[[bytes], Any]
        if kind == "obligation-set":
            validator = validate_obligation_set_bytes
        elif kind == "host-data":
            validator = validate_host_data_bytes
        elif kind == "receipt":
            validator = validate_receipt_bytes
        elif kind == "query":
            validator = validate_query_bytes
        elif kind == "target":
            validator = validate_target_bytes
        else:
            raise AssertionError(kind)
        try:
            validator(data)
        except ContractError as exc:
            if exc.code != expected_code:
                raise ValueError(
                    f"negative fixture {name} returned {exc.code}, expected {expected_code}"
                ) from exc
        else:
            raise ValueError(f"negative fixture unexpectedly accepted: {name}")
    return {CONTRACT_ROOT / path: data for path, data in output_bytes.items()}


def write_outputs(expected: dict[Path, bytes]) -> None:
    for path, data in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"wrote pipeline artifact contracts ({len(expected)} generated files)")


def check_outputs(expected: dict[Path, bytes]) -> int:
    errors: list[str] = []
    for path, data in expected.items():
        if not path.is_file():
            errors.append(f"missing generated file: {path.relative_to(REPO_ROOT)}")
        elif path.read_bytes() != data:
            errors.append(f"generated file drifted: {path.relative_to(REPO_ROOT)}")
    generated_roots = {
        path.relative_to(CONTRACT_ROOT).as_posix() for path in expected
    }
    if CONTRACT_ROOT.is_dir():
        for path in CONTRACT_ROOT.rglob("*"):
            if not path.is_file() or path.name == "README.md":
                continue
            relative = path.relative_to(CONTRACT_ROOT).as_posix()
            if relative not in generated_roots:
                errors.append(f"unexpected generated file: {path.relative_to(REPO_ROOT)}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"pipeline artifact contracts passed ({len(expected)} generated files)")
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


if __name__ == "__main__":
    raise SystemExit(main())
