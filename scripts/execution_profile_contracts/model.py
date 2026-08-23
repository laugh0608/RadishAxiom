"""Build the canonical execution profile contract value."""

from __future__ import annotations

from typing import Any

from .common import (
    CHECKER_PROFILE,
    CVC5_PROFILE,
    FORMAT,
    FORMAT_VERSION,
    NODE_PROFILE,
    NODE_TARGET_PROFILE,
    REPO_ROOT,
    SOURCE_PATHS,
    load_object,
    raw_digest,
)


def limit(name: str, unit: str, value: str, enforcement: str) -> dict[str, str]:
    return {
        "enforcement": enforcement,
        "name": name,
        "unit": unit,
        "value": value,
    }


def _limit_sets() -> list[dict[str, Any]]:
    values = [
        {
            "id": "cvc5-1.3.4-qf-uflia-internal-v0.1",
            "limits": [
                limit("semantic-steps", "step", "1000000", "cvc5-rlimit-per"),
                limit("wall-clock", "millisecond", "5000", "cvc5-tlimit-per"),
            ],
            "scope": "tool-internal",
        },
        {
            "id": "cvc5-1.3.4-qf-uflia-process-v0.1",
            "limits": [
                limit("stderr-bytes", "byte", "65536", "launcher-stream-cap"),
                limit("stdin-bytes", "byte", "1048576", "launcher-stream-cap"),
                limit("stdout-bytes", "byte", "4194304", "launcher-stream-cap"),
                limit("wall-clock", "millisecond", "6000", "launcher-hard-deadline"),
                limit("working-memory", "byte", "134217728", "launcher-os-hard-limit"),
            ],
            "scope": "process-outer",
        },
        {
            "id": "keyed-finite-table-independent-check-request-v0.1",
            "limits": [
                limit("artifact-bytes", "byte", "1048576", "checker-request"),
                limit("bundle-bytes", "byte", "4194304", "checker-request"),
                limit("collection-items", "item", "10000", "checker-request"),
                limit("json-depth", "level", "128", "checker-request"),
                limit("semantic-steps", "step", "1000000", "checker-request"),
                limit("wall-clock", "millisecond", "5000", "checker-request"),
                limit("working-memory", "byte", "67108864", "checker-request"),
            ],
            "scope": "request-internal",
        },
        {
            "id": "keyed-finite-table-independent-check-process-v0.1",
            "limits": [
                limit("stderr-bytes", "byte", "65536", "launcher-stream-cap"),
                limit("stdout-bytes", "byte", "1048576", "launcher-stream-cap"),
                limit("wall-clock", "millisecond", "6000", "launcher-hard-deadline"),
                limit("working-memory", "byte", "134217728", "launcher-os-hard-limit"),
            ],
            "scope": "process-outer",
        },
        {
            "id": "node-24-esm-invocation-process-v0.1",
            "limits": [
                limit("module-bytes", "byte", "1048576", "launcher-artifact-cap"),
                limit("stderr-bytes", "byte", "65536", "launcher-stream-cap"),
                limit("stdin-bytes", "byte", "1048576", "launcher-stream-cap"),
                limit("stdout-bytes", "byte", "1048576", "launcher-stream-cap"),
                limit("v8-old-space", "byte", "67108864", "node-cli-mebibyte-limit"),
                limit("wall-clock", "millisecond", "6000", "launcher-hard-deadline"),
                limit("working-memory", "byte", "134217728", "launcher-os-hard-limit"),
            ],
            "scope": "process-outer",
        },
    ]
    for item in values:
        item["limits"] = sorted(
            item["limits"], key=lambda entry: (entry["name"], entry["unit"])
        )
    return sorted(values, key=lambda item: item["id"])


def _environment() -> dict[str, Any]:
    return {
        "inherit": "none",
        "set": [],
    }


def _cvc5_profile() -> dict[str, Any]:
    return {
        "capability_boundary": {
            "environment": "empty",
            "fallback": "forbidden",
            "filesystem": "forbidden",
            "network": "forbidden",
            "paths_from_request": "forbidden",
            "random_seed_option": "forbidden",
            "working_directory": "isolated-empty",
        },
        "environment": _environment(),
        "failure_mapping": [
            {"classification": "sat", "condition": "exit-zero-sat-complete-model"},
            {"classification": "unsat", "condition": "exit-zero-unsat"},
            {"classification": "unknown", "condition": "exit-zero-unknown"},
            {
                "classification": "timeout",
                "condition": "launcher-hard-deadline-terminated",
            },
            {
                "classification": "resource-exhausted",
                "condition": "launcher-memory-limit-terminated",
            },
            {
                "classification": "backend-unavailable",
                "condition": "registered-artifact-unavailable",
            },
            {
                "classification": "operational-error",
                "condition": "nonzero-exit-or-malformed-or-conflicting-output",
            },
        ],
        "id": CVC5_PROFILE,
        "internal_limit_set": "cvc5-1.3.4-qf-uflia-internal-v0.1",
        "invocation": {
            "argument_tokens": [
                {"kind": "literal", "value": "--safe-mode=safe"},
                {"kind": "literal", "value": "--strict-parsing"},
                {"kind": "literal", "value": "--force-logic=QF_UFLIA"},
                {"kind": "literal", "value": "--lang=smt2"},
                {"kind": "literal", "value": "--no-incremental"},
                {"kind": "literal", "value": "--produce-models"},
                {"kind": "literal", "value": "--dump-models"},
                {"kind": "literal", "value": "--check-models"},
                {"kind": "literal", "value": "--produce-proofs"},
                {"kind": "literal", "value": "--check-proofs"},
                {
                    "kind": "limit-option",
                    "limit": "semantic-steps",
                    "limit_set": "cvc5-1.3.4-qf-uflia-internal-v0.1",
                    "prefix": "--rlimit-per=",
                },
                {
                    "kind": "limit-option",
                    "limit": "wall-clock",
                    "limit_set": "cvc5-1.3.4-qf-uflia-internal-v0.1",
                    "prefix": "--tlimit-per=",
                },
            ],
            "executable": {
                "resolution": "registered-artifact-only",
                "tool": "cvc5-cli",
                "version": "1.3.4",
            },
            "stderr": "bounded-utf8-diagnostic-not-semantic-output",
            "stdin": "single-bound-smtlib-query-raw-bytes-then-eof",
            "stdout": "single-status-frame-plus-status-dependent-model-frame-then-eof",
        },
        "outer_limit_set": "cvc5-1.3.4-qf-uflia-process-v0.1",
        "registry_profile": CVC5_PROFILE,
        "role": "verification-adapter",
    }


def _node_profile() -> dict[str, Any]:
    return {
        "capability_boundary": {
            "addons": "forbidden",
            "child_process": "forbidden",
            "dynamic_code": "forbidden",
            "environment": "empty",
            "fallback": "forbidden",
            "filesystem_read": "resolved-target-module-only",
            "filesystem_write": "forbidden",
            "inspector": "forbidden",
            "network": "outer-isolation-forbidden",
            "npm": "forbidden",
            "wasi": "forbidden",
            "worker": "forbidden",
            "working_directory": "isolated-empty",
        },
        "codec": {
            "input": "one-canonical-axiom-host-data-envelope",
            "integer": "canonical-decimal-string-to-bigint-only",
            "json_number": "forbidden-for-semantic-values",
            "output": "one-canonical-axiom-host-data-envelope",
            "text": "well-formed-utf8-and-ecmascript-string-no-normalization-or-locale",
        },
        "environment": _environment(),
        "failure_mapping": [
            {
                "classification": "completed",
                "condition": "exit-zero-one-canonical-output-envelope",
            },
            {
                "classification": "execution-failure",
                "condition": "nonzero-exit-or-empty-malformed-conflicting-output",
            },
            {
                "classification": "timeout",
                "condition": "launcher-hard-deadline-terminated",
            },
            {
                "classification": "resource-exhausted",
                "condition": "launcher-memory-or-output-limit-terminated",
            },
            {
                "classification": "runtime-unavailable",
                "condition": "registered-artifact-unavailable",
            },
        ],
        "id": NODE_PROFILE,
        "invocation": {
            "argument_tokens": [
                {"kind": "literal", "value": "--permission"},
                {"kind": "literal", "value": "--disable-proto=throw"},
                {
                    "kind": "literal",
                    "value": "--disallow-code-generation-from-strings",
                },
                {"kind": "literal", "value": "--no-addons"},
                {"kind": "literal", "value": "--disable-sigusr1"},
                {"kind": "literal", "value": "--no-experimental-detect-module"},
                {"kind": "literal", "value": "--unhandled-rejections=strict"},
                {
                    "divisor": "1048576",
                    "kind": "limit-option-mebibytes",
                    "limit": "v8-old-space",
                    "limit_set": "node-24-esm-invocation-process-v0.1",
                    "prefix": "--max-old-space-size=",
                },
                {
                    "artifact_role": "target-module",
                    "kind": "artifact-read-grant",
                    "prefix": "--allow-fs-read=",
                    "resolution": "digest-selected-canonical-realpath",
                },
                {
                    "artifact_role": "target-module",
                    "kind": "artifact-path",
                    "resolution": "same-canonical-realpath-as-read-grant",
                },
            ],
            "executable": {
                "resolution": "registered-artifact-only",
                "tool": "node-runtime",
                "version": "24.19.0",
            },
            "stderr": "bounded-utf8-diagnostic-not-semantic-output",
            "stdin": "one-canonical-envelope-raw-bytes-then-eof",
            "stdout": "one-canonical-envelope-raw-bytes-then-eof",
        },
        "outer_limit_set": "node-24-esm-invocation-process-v0.1",
        "registry_profile": NODE_PROFILE,
        "role": "target-runtime-invocation",
        "target_profile": NODE_TARGET_PROFILE,
    }


def _checker_counters() -> list[dict[str, Any]]:
    return [
        {
            "checkpoints": [
                "manifest-declared-length-before-open-or-allocation",
                "streamed-raw-byte-count-before-parser",
            ],
            "measurement": "maximum-bytes-for-each-single-artifact",
            "name": "artifact-bytes",
        },
        {
            "checkpoints": [
                "sum-declared-lengths-before-any-blob-read",
                "cumulative-streamed-raw-byte-count",
            ],
            "measurement": "sum-of-unique-manifest-artifact-bytes",
            "name": "bundle-bytes",
        },
        {
            "checkpoints": [
                "one-per-json-object-member",
                "one-per-json-array-element",
                "one-per-domain-sequence-item-after-closed-decoding",
            ],
            "measurement": "cumulative-items-without-map-iteration",
            "name": "collection-items",
        },
        {
            "checkpoints": [
                "increment-before-opening-object-or-array",
                "decrement-after-matching-close-token",
            ],
            "measurement": "maximum-open-json-container-count-root-container-is-one",
            "name": "json-depth",
        },
        {
            "checkpoints": [
                "one-per-strict-json-token",
                "one-per-closed-member-validation",
                "one-per-64kib-digest-block",
                "one-per-ir-node-validation",
                "one-per-obligation-definition-or-comparison",
                "one-per-expression-evaluation",
                "one-per-row-or-world-visit",
                "one-per-key-comparison",
                "one-per-trace-step-replay",
                "one-per-certificate-rule-step",
            ],
            "measurement": "cumulative-profile-event-count-in-listed-phase-order",
            "name": "semantic-steps",
        },
        {
            "checkpoints": [
                "before-and-after-each-of-ten-check-kinds",
                "after-each-1024-semantic-steps",
                "before-result-encoding",
            ],
            "measurement": "monotonic-elapsed-milliseconds-from-first-request-byte",
            "name": "wall-clock",
        },
        {
            "checkpoints": [
                "charge-before-capacity-growth-or-domain-node-construction",
                "release-only-when-owned-budget-object-is-discarded",
            ],
            "measurement": "logical-owned-bytes-using-fixed-accounting-table",
            "name": "working-memory",
        },
    ]


def _checker_profile() -> dict[str, Any]:
    return {
        "capability_boundary": {
            "environment": "empty",
            "fallback": "forbidden",
            "filesystem": "resolved-readonly-bundle-only",
            "network": "forbidden",
            "production_tools": "forbidden",
            "working_directory": "isolated-empty",
        },
        "environment": _environment(),
        "id": CHECKER_PROFILE,
        "invocation": {
            "argument_tokens": [
                {"kind": "literal", "value": "check"},
                {
                    "artifact_role": "bundle-root",
                    "kind": "artifact-directory-option",
                    "prefix": "--bundle-root=",
                    "resolution": "caller-mounted-readonly-canonical-realpath",
                },
            ],
            "executable": {
                "artifact": "required-not-materialized",
                "name": "radishaxiom-independent-checker-go",
                "resolution": "future-registered-checker-artifact-only",
                "toolchain": "go1.26.7",
            },
            "stderr": "bounded-utf8-diagnostic-not-result",
            "stdin": "empty",
            "stdout": "one-canonical-independent-result-or-no-result",
        },
        "logical_memory_accounting": [
            {"charge": "requested-capacity", "kind": "raw-byte-buffer"},
            {"charge": "utf8-byte-length-plus-16", "kind": "utf8-string"},
            {"charge": "decimal-digit-count-plus-16", "kind": "big-integer"},
            {"charge": "32-plus-24-per-item", "kind": "json-container"},
            {"charge": "64-plus-owned-field-charges", "kind": "domain-node"},
            {"charge": "256", "kind": "sha256-state"},
        ],
        "outer_limit_set": "keyed-finite-table-independent-check-process-v0.1",
        "registry_profile": CHECKER_PROFILE,
        "request_limit_set": "keyed-finite-table-independent-check-request-v0.1",
        "resource_counters": _checker_counters(),
        "result_boundary": {
            "internal-budget-detected-before-encoding": "canonical-result-may-form",
            "outer-kill-crash-identity-failure-or-output-truncation": "process-failure-record-only",
            "process_failure_scenario": "CHK-PROCESS-01",
            "resource_scenario": "CHK-RESOURCE-01",
        },
        "role": "independent-checker",
    }


def _profiles() -> list[dict[str, Any]]:
    return sorted(
        [_checker_profile(), _cvc5_profile(), _node_profile()],
        key=lambda item: item["id"],
    )


def _certificate_capabilities() -> dict[str, Any]:
    return {
        "authority": {
            "policy_contract": "contracts/independent-check-v0.1/contract.json",
            "scenario_manifest": "contracts/implementation-readiness-v0.1/manifest.jcs",
        },
        "candidate_formats": [
            {
                "format": "alethe",
                "reason": "certificate-checker-and-complete-rule-coverage-not-accepted",
                "status": "candidate-not-accepted",
            },
            {
                "format": "cpc",
                "reason": "certificate-checker-and-complete-rule-coverage-not-accepted",
                "status": "candidate-not-accepted",
            },
        ],
        "policy_cases": [
            {
                "evidence_support": "backend-attestation",
                "proof_support": "attestation-allowed",
                "readiness_scenario": "CHK-PROOF-02",
            },
            {
                "evidence_support": "backend-attestation",
                "proof_support": "certificate-required",
                "readiness_scenario": "CHK-PROOF-01",
            },
        ],
        "supported_profiles": [],
    }


def _references() -> list[dict[str, str]]:
    return sorted(
        [
            {
                "id": "cvc5-options-1.3.4",
                "scope": "cli-option-names-and-value-kinds",
                "url": "https://cvc5.github.io/docs/cvc5-1.3.4/options.html",
            },
            {
                "id": "node-cli-24.19.0",
                "scope": "node-cli-flags",
                "url": "https://nodejs.org/download/release/v24.19.0/docs/api/cli.html",
            },
            {
                "id": "node-permissions-24.19.0",
                "scope": "permission-model-boundary",
                "url": "https://nodejs.org/download/release/v24.19.0/docs/api/permissions.html",
            },
        ],
        key=lambda item: item["id"],
    )


def source_bindings() -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "path": path.as_posix(),
            "sha256": raw_digest((REPO_ROOT / path).read_bytes()),
        }
        for name, path in sorted(SOURCE_PATHS)
    ]


def _coverage(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    ids = {item["id"] for item in readiness["scenarios"]}
    benchmark = sorted(
        item["id"] for item in readiness["scenarios"] if item["kind"] == "benchmark"
    )
    checker_extra = [
        "CHK-BUNDLE-01",
        "CHK-CONCRETE-01",
        "CHK-DIGEST-01",
        "CHK-OBLIGATION-01",
        "CHK-PROCESS-01",
        "CHK-PROOF-01",
        "CHK-PROOF-02",
        "CHK-RESOURCE-01",
    ]
    required = set(benchmark) | set(checker_extra)
    missing = sorted(required - ids)
    if missing:
        raise ValueError(f"readiness scenarios missing: {missing}")
    return sorted(
        [
        {
            "profile": CHECKER_PROFILE,
            "readiness_scenarios": sorted(required),
        },
        {
            "profile": CVC5_PROFILE,
            "readiness_scenarios": benchmark,
        },
        {
            "profile": NODE_PROFILE,
            "readiness_scenarios": sorted(benchmark + ["CHK-CONCRETE-01"]),
        },
        ],
        key=lambda item: item["profile"],
    )


def _validate_registry() -> None:
    registry = load_object(REPO_ROOT / "contracts/toolchain-adapters-v0.1/registry.json")
    profiles = {item["id"]: item for item in registry["profiles"]}
    tools = {item["id"]: item for item in registry["tools"]}
    expected_profiles = {
        CHECKER_PROFILE: ("go-toolchain", "specified-not-materialized"),
        CVC5_PROFILE: ("cvc5-cli", "specified-not-materialized"),
        NODE_PROFILE: ("node-runtime", "specified-not-materialized"),
    }
    for profile_id, (tool, materialization) in expected_profiles.items():
        profile = profiles.get(profile_id)
        if profile is None or profile["tool"] != tool:
            raise ValueError(f"registry profile drifted: {profile_id}")
        if profile["materialization"] != materialization:
            raise ValueError(f"registry materialization drifted: {profile_id}")
    expected_tools = {
        "cvc5-cli": "1.3.4",
        "go-toolchain": "go1.26.7",
        "node-runtime": "24.19.0",
    }
    for tool_id, version in expected_tools.items():
        if tools.get(tool_id, {}).get("version") != version:
            raise ValueError(f"registry tool version drifted: {tool_id}")


def build_manifest() -> dict[str, Any]:
    _validate_registry()
    readiness = load_object(
        REPO_ROOT / "contracts/implementation-readiness-v0.1/manifest.jcs"
    )
    profiles = _profiles()
    limit_sets = _limit_sets()
    return {
        "certificate_capabilities": _certificate_capabilities(),
        "counts": {
            "certificate_profiles": "0",
            "limit_sets": str(len(limit_sets)),
            "profiles": str(len(profiles)),
        },
        "coverage": _coverage(readiness),
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "level": "specified",
        "limit_sets": limit_sets,
        "profiles": profiles,
        "references": _references(),
        "source_bindings": source_bindings(),
    }
