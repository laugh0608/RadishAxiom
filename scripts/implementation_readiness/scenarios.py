"""Build the versioned readiness requirements and scenario matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    BENCHMARK_ROOT,
    PLATFORMS,
    PROFILE,
    REPO_ROOT,
    STAGE_IDS,
    bound_file,
    load_json,
    raw_digest,
)


BINDING_PATHS = (
    ("adr-0007", Path("docs/adr/0007-first-verification-first-compilation-pipeline.md")),
    ("adr-0008", Path("docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md")),
    ("axiom-evidence-v0.1", Path("docs/evidence/axiom-evidence-v0.md")),
    ("axiom-ir-v0.1", Path("docs/ir/axiom-ir-v0.md")),
    ("benchmark-corpus-v0.1", Path("benchmarks/keyed-finite-table-v0.1/corpus.json")),
    ("independent-check-v0.1", Path("contracts/independent-check-v0.1/contract.json")),
    ("keyed-finite-table-semantics", Path("docs/semantics/keyed-finite-table-semantics.md")),
    ("pipeline-artifacts-v0.1", Path("contracts/pipeline-artifacts-v0.1/contract.json")),
    ("toolchain-adapters-v0.1", Path("contracts/toolchain-adapters-v0.1/registry.json")),
)

ADR7_REQUIREMENTS = (
    "acceptance-1",
    "acceptance-2",
    "acceptance-3",
    "acceptance-4",
    "acceptance-5",
    "acceptance-6",
    "acceptance-7",
    "acceptance-8",
    "cache-integrity",
    "gate-bypass",
    "host-mismatch",
    "new-attempt",
    "operational-failure",
    "partial-receipt",
    "recovery",
)
ADR8_CHECKS = (
    "CHK-BUNDLE-01",
    "CHK-BUNDLE-02",
    "CHK-CAN-01",
    "CHK-CONCLUSION-01",
    "CHK-CONCRETE-01",
    "CHK-COUNTEREXAMPLE-01",
    "CHK-DIGEST-01",
    "CHK-IR-01",
    "CHK-ISOLATION-01",
    "CHK-OBLIGATION-01",
    "CHK-PLATFORM-01",
    "CHK-PROCESS-01",
    "CHK-PROOF-01",
    "CHK-PROOF-02",
    "CHK-RESOURCE-01",
    "CHK-STATUS-01",
)
ADR8_ACCEPTANCE = tuple(f"acceptance-{index}" for index in range(1, 9))


def bindings() -> list[dict[str, str]]:
    result = []
    for name, path in BINDING_PATHS:
        item = {"name": name, **bound_file(path)}
        value = load_json(REPO_ROOT / path) if path.suffix == ".json" else {}
        for key in ("registry_digest", "task_digest"):
            if isinstance(value.get(key), str):
                item[key] = value[key]
        result.append(item)
    return sorted(result, key=lambda item: item["name"])


def _requirement(requirement_id: str, binding: str, locator: str) -> dict[str, str]:
    return {"binding": binding, "id": requirement_id, "locator": locator}


def requirements() -> list[dict[str, str]]:
    result = [
        _requirement(f"adr-0007:{name}", "adr-0007", name)
        for name in ADR7_REQUIREMENTS
    ]
    result.extend(
        _requirement(f"adr-0008:{name}", "adr-0008", name)
        for name in (*ADR8_CHECKS, *ADR8_ACCEPTANCE)
    )
    corpus = load_json(BENCHMARK_ROOT / "corpus.json")
    for task_ref in corpus["tasks"]:
        task = load_json(BENCHMARK_ROOT / task_ref["path"])
        for scenario in task["scenarios"]:
            name = f"benchmark:{task['benchmark_id']}:{scenario['name']}"
            result.append(
                _requirement(
                    name,
                    "benchmark-corpus-v0.1",
                    f"{task_ref['path']}#{scenario['name']}",
                )
            )
    return sorted(result, key=lambda item: item["id"])


def _stages(
    default: str = "completed", overrides: dict[str, str] | None = None
) -> list[dict[str, str]]:
    values = {stage_id: default for stage_id in STAGE_IDS}
    values.update(overrides or {})
    return [{"id": stage_id, "result": values[stage_id]} for stage_id in STAGE_IDS]


def _not_applicable_input(name: str) -> dict[str, Any]:
    return {
        "candidate": {"materialization": "not-applicable"},
        "fixtures": [
            {"materialization": "specified-not-materialized", "name": name}
        ],
        "scenario_assertion": {"materialization": "specified-not-materialized"},
    }


def _scenario(
    *,
    scenario_id: str,
    kind: str,
    source_refs: list[str],
    stages: list[dict[str, str]],
    gate: str,
    gate_basis: list[str],
    must_roles: list[str],
    forbidden_roles: list[str],
    receipt_availability: str,
    receipt_outcome: str,
    receipt_codes: list[str],
    evidence_availability: str,
    evidence_conclusion: str,
    required_results: list[dict[str, str]] | None = None,
    remaining_trust: list[str] | None = None,
    uncovered: list[str] | None = None,
    independent_process: str = "not-run",
    independent_process_codes: list[str] | None = None,
    independent_outcome: str = "not-applicable",
    independent_codes: list[str] | None = None,
    bundle: str = "not-applicable",
    cache_decision: str = "not-applicable",
    cache_identity: str = "not-applicable",
    input_value: dict[str, Any] | None = None,
    platforms: tuple[str, ...] = PLATFORMS,
) -> dict[str, Any]:
    return {
        "artifact_roles": {
            "forbidden": sorted(forbidden_roles),
            "must_appear": sorted(must_roles),
        },
        "bundle": bundle,
        "cache": {"decision": cache_decision, "identity": cache_identity},
        "evidence": {
            "availability": evidence_availability,
            "conclusion": evidence_conclusion,
            "required_results": sorted(
                required_results or [],
                key=lambda item: (item["kind"], item["status"]),
            ),
            "remaining_trust": sorted(remaining_trust or []),
            "uncovered": sorted(uncovered or []),
        },
        "gate": {"basis": sorted(gate_basis), "decision": gate},
        "id": scenario_id,
        "independent": {
            "codes": sorted(independent_codes or []),
            "outcome": independent_outcome,
            "process": independent_process,
            "process_codes": sorted(independent_process_codes or []),
        },
        "input": input_value or _not_applicable_input(scenario_id.lower()),
        "kind": kind,
        "level": "specified",
        "platforms": list(platforms),
        "profile": PROFILE,
        "receipt": {
            "availability": receipt_availability,
            "codes": sorted(receipt_codes),
            "outcome": receipt_outcome,
        },
        "source_refs": sorted(source_refs),
        "stages": stages,
    }


def _fixture_descriptor(
    task: dict[str, Any], fixture_name: str
) -> dict[str, Any]:
    fixture = next(item for item in task["fixtures"] if item["name"] == fixture_name)
    value: dict[str, Any] = {
        "input": {
            "materialization": "bound-artifact",
            "path": f"benchmarks/keyed-finite-table-v0.1/{fixture['input']['path']}",
            "sha256": fixture["input"]["sha256"],
        },
        "kind": fixture["kind"],
        "materialization": "bound-fixture",
        "name": fixture_name,
    }
    if "golden" in fixture:
        value["golden"] = {
            "materialization": "bound-artifact",
            "path": f"benchmarks/keyed-finite-table-v0.1/{fixture['golden']['path']}",
            "sha256": fixture["golden"]["sha256"],
        }
    else:
        value["golden"] = {"materialization": "not-applicable"}
    return value


def _benchmark_scenarios() -> list[dict[str, Any]]:
    result = []
    corpus = load_json(BENCHMARK_ROOT / "corpus.json")
    for task_ref in corpus["tasks"]:
        task_path = BENCHMARK_ROOT / task_ref["path"]
        task_bytes = task_path.read_bytes()
        if raw_digest(task_bytes) != task_ref["sha256"]:
            raise ValueError(f"benchmark task digest drifted: {task_ref['path']}")
        task = load_json(task_path)
        candidates = {item["name"]: item for item in task["candidates"]}
        for scenario_ref in task["scenarios"]:
            expected_path = BENCHMARK_ROOT / scenario_ref["path"]
            expected_bytes = expected_path.read_bytes()
            if raw_digest(expected_bytes) != scenario_ref["sha256"]:
                raise ValueError(
                    f"benchmark scenario digest drifted: {scenario_ref['path']}"
                )
            expected = load_json(expected_path)
            candidate = candidates[expected["candidate"]]
            scenario_name = scenario_ref["name"]
            scenario_id = f"{task['benchmark_id']}-{scenario_name.upper()}"
            source_refs = [
                f"benchmark:{task['benchmark_id']}:{scenario_name}",
                "adr-0007:acceptance-3",
                "adr-0008:acceptance-4",
            ]
            correct = scenario_name == "correct"
            timeout = scenario_name == "backend-timeout"
            invalid = scenario_name == "invalid-input"
            if not correct:
                source_refs.append("adr-0007:acceptance-4")
            if timeout:
                source_refs.append("adr-0007:partial-receipt")
            if scenario_id == "AX-B01-CORRECT":
                source_refs.extend(
                    ["adr-0007:acceptance-1", "adr-0007:acceptance-2"]
                )

            stage_overrides: dict[str, str] = {}
            if not correct:
                stage_overrides.update({"P6": "not-run", "P7": "not-run", "P8": "not-run"})
            if timeout:
                stage_overrides["P4"] = "timeout"
            if invalid:
                stage_overrides["P5"] = "invalid"

            target_roles = ["execute-host", "host-output", "target-module"]
            must_roles = [
                "axiom-evidence",
                "canonical-ir",
                "candidate",
                "host-input",
                "independent-check-result",
                "obligation-set",
                "pipeline-receipt",
            ]
            forbidden_roles: list[str] = []
            if correct:
                must_roles.extend(target_roles)
            else:
                forbidden_roles.extend(target_roles)
            if timeout:
                receipt_outcome = "partial"
            elif correct:
                receipt_outcome = "completed"
            else:
                receipt_outcome = "blocked"

            input_value = {
                "candidate": {
                    "document_digest": candidate["document_digest"],
                    "materialization": "bound-artifact",
                    "name": candidate["name"],
                    "path": (
                        "benchmarks/keyed-finite-table-v0.1/"
                        + candidate["canonical"]["path"]
                    ),
                    "sha256": candidate["canonical"]["sha256"],
                },
                "fixtures": [
                    _fixture_descriptor(task, name) for name in expected["fixtures"]
                ],
                "scenario_assertion": {
                    "materialization": "bound-artifact",
                    "path": (
                        "benchmarks/keyed-finite-table-v0.1/"
                        + scenario_ref["path"]
                    ),
                    "sha256": scenario_ref["sha256"],
                },
            }
            result.append(
                _scenario(
                    scenario_id=scenario_id,
                    kind="benchmark",
                    source_refs=source_refs,
                    stages=_stages(overrides=stage_overrides),
                    gate="opened" if correct else "closed",
                    gate_basis=[
                        "all-prove-proved" if correct else (
                            "input-invalid" if invalid else (
                                "prove-unknown" if timeout else "prove-failed"
                            )
                        )
                    ],
                    must_roles=must_roles,
                    forbidden_roles=forbidden_roles,
                    receipt_availability="required",
                    receipt_outcome=receipt_outcome,
                    receipt_codes=["backend-wall-clock"] if timeout else [],
                    evidence_availability="required",
                    evidence_conclusion=expected["expected_conclusion"],
                    required_results=expected["required_results"],
                    remaining_trust=expected["required_trust"],
                    uncovered=expected["required_uncovered"],
                    independent_process="completed",
                    independent_outcome=expected["expected_independent_result"],
                    bundle="specified-not-materialized",
                    cache_decision="miss",
                    cache_identity="exact",
                    input_value=input_value,
                )
            )
    return result


CHECKER_CASES: dict[str, dict[str, Any]] = {
    "CHK-BUNDLE-01": {"outcome": "incomplete", "codes": ["artifact-missing"], "bundle": "missing"},
    "CHK-BUNDLE-02": {"outcome": "rejected", "codes": ["manifest-coverage"], "bundle": "invalid"},
    "CHK-CAN-01": {
        "outcome": "rejected",
        "codes": ["duplicate-member", "invalid-utf8", "noncanonical-json", "noncanonical-order"],
        "bundle": "invalid",
    },
    "CHK-CONCLUSION-01": {"outcome": "rejected", "codes": ["conclusion-mismatch"], "bundle": "complete"},
    "CHK-CONCRETE-01": {
        "outcome": "accepted-with-trust",
        "codes": ["host-output-mismatch"],
        "bundle": "complete",
        "cross_contract": True,
        "evidence": "implementation_inconsistent",
        "trust": ["host-runtime", "production-generator"],
    },
    "CHK-COUNTEREXAMPLE-01": {"outcome": "rejected", "codes": ["counterexample-invalid"], "bundle": "complete"},
    "CHK-DIGEST-01": {"outcome": "rejected", "codes": ["digest-mismatch"], "bundle": "invalid"},
    "CHK-IR-01": {"outcome": "rejected", "codes": ["invalid-ir"], "bundle": "complete"},
    "CHK-ISOLATION-01": {
        "outcome": "not-produced",
        "codes": [],
        "bundle": "complete",
        "process": "failed",
        "process_codes": ["isolation-boundary-violation"],
    },
    "CHK-OBLIGATION-01": {"outcome": "rejected", "codes": ["obligation-mismatch"], "bundle": "complete"},
    "CHK-PLATFORM-01": {
        "outcome": "accepted-with-trust",
        "codes": [],
        "bundle": "complete",
        "trust": ["checker-binary-platform"],
    },
    "CHK-PROCESS-01": {
        "outcome": "not-produced",
        "codes": [],
        "bundle": "complete",
        "process": "failed",
        "process_codes": ["checker-process-failure"],
    },
    "CHK-PROOF-01": {"outcome": "incomplete", "codes": ["certificate-incomplete"], "bundle": "complete"},
    "CHK-PROOF-02": {
        "outcome": "accepted-with-trust",
        "codes": [],
        "bundle": "complete",
        "trust": ["proof-backend"],
    },
    "CHK-RESOURCE-01": {
        "outcome": "incomplete",
        "codes": [],
        "bundle": "complete",
        "uncovered": ["resource-performance"],
    },
    "CHK-STATUS-01": {"outcome": "rejected", "codes": ["invalid-state-support"], "bundle": "complete"},
}


def _checker_scenarios() -> list[dict[str, Any]]:
    result = []
    acceptance_refs = {
        "CHK-CAN-01": ["adr-0008:acceptance-1"],
        "CHK-ISOLATION-01": ["adr-0008:acceptance-3", "adr-0008:acceptance-5"],
        "CHK-IR-01": ["adr-0008:acceptance-5"],
        "CHK-OBLIGATION-01": ["adr-0008:acceptance-5"],
        "CHK-CONCRETE-01": [
            "adr-0007:host-mismatch",
            "adr-0008:acceptance-4",
            "adr-0008:acceptance-5",
        ],
        "CHK-PLATFORM-01": ["adr-0007:acceptance-5", "adr-0008:acceptance-6"],
        "CHK-RESOURCE-01": ["adr-0008:acceptance-6"],
        "CHK-PROOF-01": ["adr-0008:acceptance-7"],
        "CHK-PROOF-02": ["adr-0008:acceptance-7"],
        "CHK-CONCLUSION-01": ["adr-0007:acceptance-7"],
    }
    for scenario_id in ADR8_CHECKS:
        case = CHECKER_CASES[scenario_id]
        cross_contract = case.get("cross_contract") is True
        if cross_contract:
            stages = _stages()
            gate = "opened"
            receipt_availability = "required"
            receipt_outcome = "completed"
            evidence_availability = "required"
            must_roles = [
                "axiom-evidence",
                "execute-host",
                "host-output",
                "independent-check-result",
                "pipeline-receipt",
                "target-module",
            ]
        else:
            stages = _stages(default="not-applicable")
            gate = "not-applicable"
            receipt_availability = "not-applicable"
            receipt_outcome = "not-applicable"
            evidence_availability = "input-only"
            must_roles = ["independent-check-request"]
            forbidden_roles = []
            if case["outcome"] != "not-produced":
                must_roles.append("independent-check-result")
            else:
                forbidden_roles.append("independent-check-result")
        result.append(
            _scenario(
                scenario_id=scenario_id,
                kind="cross-contract" if cross_contract else "independent-check",
                source_refs=[
                    f"adr-0008:{scenario_id}",
                    *acceptance_refs.get(scenario_id, []),
                ],
                stages=stages,
                gate=gate,
                gate_basis=["host-mismatch"] if cross_contract else ["not-applicable"],
                must_roles=must_roles,
                forbidden_roles=[] if cross_contract else forbidden_roles,
                receipt_availability=receipt_availability,
                receipt_outcome=receipt_outcome,
                receipt_codes=[],
                evidence_availability=evidence_availability,
                evidence_conclusion=case.get("evidence", "not-applicable"),
                remaining_trust=case.get("trust", []),
                uncovered=case.get("uncovered", []),
                independent_process=case.get("process", "completed"),
                independent_process_codes=case.get("process_codes", []),
                independent_outcome=case["outcome"],
                independent_codes=case["codes"],
                bundle=case["bundle"],
                input_value=_not_applicable_input(scenario_id.lower()),
            )
        )
    return result


def _pipeline_scenarios() -> list[dict[str, Any]]:
    all_completed = _stages()
    target_roles = ["execute-host", "host-output", "target-module"]
    cases = [
        _scenario(
            scenario_id="PIPE-CACHE-FORGED-HIT-01",
            kind="pipeline-rejection",
            source_refs=["adr-0007:acceptance-4", "adr-0007:cache-integrity"],
            stages=_stages(overrides={"P6": "not-run", "P7": "not-run", "P8": "not-run"}),
            gate="closed",
            gate_basis=["cache-identity-mismatch"],
            must_roles=["pipeline-receipt"],
            forbidden_roles=target_roles,
            receipt_availability="invalid-input",
            receipt_outcome="rejected",
            receipt_codes=["cache-key-mismatch"],
            evidence_availability="forbidden",
            evidence_conclusion="not-produced",
            cache_decision="hit",
            cache_identity="mismatch",
        ),
        _scenario(
            scenario_id="PIPE-CACHE-REUSE-01",
            kind="pipeline",
            source_refs=["adr-0007:acceptance-6", "adr-0007:cache-integrity"],
            stages=all_completed,
            gate="opened",
            gate_basis=["all-prove-proved", "cache-identity-exact"],
            must_roles=["axiom-evidence", "pipeline-receipt", *target_roles],
            forbidden_roles=[],
            receipt_availability="required",
            receipt_outcome="completed",
            receipt_codes=[],
            evidence_availability="required",
            evidence_conclusion="satisfied",
            cache_decision="hit",
            cache_identity="exact",
        ),
        _scenario(
            scenario_id="PIPE-EMITTER-FAILURE-01",
            kind="pipeline",
            source_refs=["adr-0007:operational-failure"],
            stages=_stages(overrides={"P6": "error", "P7": "not-run", "P8": "not-run"}),
            gate="opened",
            gate_basis=["all-prove-proved"],
            must_roles=["axiom-evidence", "pipeline-receipt"],
            forbidden_roles=target_roles,
            receipt_availability="required",
            receipt_outcome="error",
            receipt_codes=["emitter-error"],
            evidence_availability="required",
            evidence_conclusion="satisfied",
        ),
        _scenario(
            scenario_id="PIPE-GATE-BYPASS-01",
            kind="pipeline-rejection",
            source_refs=["adr-0007:acceptance-4", "adr-0007:gate-bypass"],
            stages=_stages(overrides={"P6": "not-run", "P7": "not-run", "P8": "not-run"}),
            gate="closed",
            gate_basis=["tampered-opened-decision-rejected"],
            must_roles=["pipeline-receipt"],
            forbidden_roles=target_roles,
            receipt_availability="invalid-input",
            receipt_outcome="rejected",
            receipt_codes=["gate-decision-mismatch"],
            evidence_availability="forbidden",
            evidence_conclusion="not-produced",
        ),
        _scenario(
            scenario_id="PIPE-HOST-PROCESS-FAILURE-01",
            kind="pipeline",
            source_refs=["adr-0007:operational-failure"],
            stages=_stages(overrides={"P7": "error", "P8": "not-run"}),
            gate="opened",
            gate_basis=["all-prove-proved"],
            must_roles=["axiom-evidence", "execute-host", "pipeline-receipt", "target-module"],
            forbidden_roles=["host-output"],
            receipt_availability="required",
            receipt_outcome="error",
            receipt_codes=["host-process-error"],
            evidence_availability="required",
            evidence_conclusion="inconclusive",
        ),
        _scenario(
            scenario_id="PIPE-NEW-ATTEMPT-01",
            kind="pipeline",
            source_refs=["adr-0007:acceptance-6", "adr-0007:new-attempt"],
            stages=all_completed,
            gate="opened",
            gate_basis=["new-attempt-completed", "old-attempt-preserved"],
            must_roles=["axiom-evidence", "pipeline-receipt", *target_roles],
            forbidden_roles=[],
            receipt_availability="required",
            receipt_outcome="completed",
            receipt_codes=[],
            evidence_availability="required",
            evidence_conclusion="satisfied",
            cache_decision="miss",
            cache_identity="exact",
        ),
        _scenario(
            scenario_id="PIPE-P9-ASSEMBLY-FAILURE-01",
            kind="pipeline",
            source_refs=["adr-0007:operational-failure"],
            stages=_stages(overrides={"P9": "error"}),
            gate="opened",
            gate_basis=["all-prove-proved"],
            must_roles=["pipeline-receipt", *target_roles],
            forbidden_roles=["axiom-evidence"],
            receipt_availability="required",
            receipt_outcome="error",
            receipt_codes=["assembly-error"],
            evidence_availability="forbidden",
            evidence_conclusion="not-produced",
        ),
        _scenario(
            scenario_id="PIPE-RECOVERY-01",
            kind="pipeline",
            source_refs=["adr-0007:acceptance-6", "adr-0007:recovery"],
            stages=all_completed,
            gate="opened",
            gate_basis=["missing-stages-completed", "old-failure-preserved"],
            must_roles=["axiom-evidence", "pipeline-receipt", *target_roles],
            forbidden_roles=[],
            receipt_availability="required",
            receipt_outcome="completed",
            receipt_codes=[],
            evidence_availability="required",
            evidence_conclusion="satisfied",
            cache_decision="hit",
            cache_identity="exact",
        ),
        _scenario(
            scenario_id="PIPE-TOOLCHAIN-NOT-ACCEPTED-01",
            kind="readiness-stop",
            source_refs=["adr-0007:acceptance-8", "adr-0008:acceptance-2"],
            stages=_stages(default="not-run", overrides={"P0": "unavailable"}),
            gate="closed",
            gate_basis=["tool-payload-not-accepted"],
            must_roles=["pipeline-receipt"],
            forbidden_roles=["axiom-evidence", *target_roles],
            receipt_availability="required",
            receipt_outcome="error",
            receipt_codes=["tool-payload-not-accepted"],
            evidence_availability="forbidden",
            evidence_conclusion="not-produced",
            uncovered=["supply-chain-payload-and-license-review"],
        ),
        _scenario(
            scenario_id="READY-IMPLEMENTATION-AUTHORIZATION-01",
            kind="readiness-stop",
            source_refs=["adr-0008:acceptance-8"],
            stages=_stages(default="not-applicable"),
            gate="not-applicable",
            gate_basis=["owner-authorization-required"],
            must_roles=[],
            forbidden_roles=["checker-binary", "production-binary"],
            receipt_availability="not-applicable",
            receipt_outcome="not-applicable",
            receipt_codes=[],
            evidence_availability="not-applicable",
            evidence_conclusion="not-applicable",
            uncovered=["implementation-authorization"],
        ),
    ]
    return cases


def build_scenarios() -> list[dict[str, Any]]:
    scenarios = [
        *_benchmark_scenarios(),
        *_checker_scenarios(),
        *_pipeline_scenarios(),
    ]
    return sorted(scenarios, key=lambda item: item["id"])


def build_coverage(
    requirement_values: list[dict[str, str]],
    scenario_values: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_requirement = {item["id"]: [] for item in requirement_values}
    for scenario in scenario_values:
        for source_ref in scenario["source_refs"]:
            if source_ref not in by_requirement:
                raise ValueError(
                    f"scenario {scenario['id']} references unknown requirement {source_ref}"
                )
            by_requirement[source_ref].append(scenario["id"])
    missing = sorted(key for key, values in by_requirement.items() if not values)
    if missing:
        raise ValueError(f"requirements without scenarios: {', '.join(missing)}")
    return [
        {"requirement": key, "scenarios": sorted(values)}
        for key, values in sorted(by_requirement.items())
    ]
