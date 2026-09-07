"""Build the JSON Schema for the implementation-readiness manifest."""

from __future__ import annotations

from typing import Any

from .common import (
    FORMAT,
    FORMAT_VERSION,
    PLATFORMS,
    PROFILE,
    SCHEMA_DIALECT,
    STAGE_IDS,
    STAGE_RESULTS,
)


def manifest_schema() -> dict[str, Any]:
    digest = {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"}
    stable_id = {
        "pattern": "^[A-Za-z][A-Za-z0-9._:-]*$",
        "type": "string",
    }
    artifact_binding = {
        "additionalProperties": False,
        "properties": {
            "document_digest": digest,
            "materialization": {"const": "bound-artifact"},
            "name": {"minLength": 1, "type": "string"},
            "path": {"minLength": 1, "type": "string"},
            "sha256": digest,
        },
        "required": ["materialization", "path", "sha256"],
        "type": "object",
    }
    artifact = {
        "oneOf": [
            artifact_binding,
            {
                "additionalProperties": False,
                "properties": {"materialization": {"const": "not-applicable"}},
                "required": ["materialization"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "materialization": {"const": "specified-not-materialized"},
                    "name": {"minLength": 1, "type": "string"},
                },
                "required": ["materialization"],
                "type": "object",
            },
        ]
    }
    fixture = {
        "oneOf": [
            {
                "additionalProperties": False,
                "properties": {
                    "materialization": {"const": "specified-not-materialized"},
                    "name": {"minLength": 1, "type": "string"},
                },
                "required": ["materialization", "name"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "golden": artifact,
                    "input": artifact_binding,
                    "kind": {"enum": ["invalid", "valid"]},
                    "materialization": {"const": "bound-fixture"},
                    "name": {"minLength": 1, "type": "string"},
                },
                "required": ["golden", "input", "kind", "materialization", "name"],
                "type": "object",
            },
        ]
    }
    result_assertion = {
        "additionalProperties": False,
        "properties": {
            "kind": stable_id,
            "reason": stable_id,
            "status": {"enum": ["checked", "failed", "proved", "trusted", "unknown"]},
        },
        "required": ["kind", "status"],
        "type": "object",
    }
    scenario = {
        "additionalProperties": False,
        "properties": {
            "artifact_roles": {
                "additionalProperties": False,
                "properties": {
                    "forbidden": {"items": stable_id, "type": "array"},
                    "must_appear": {"items": stable_id, "type": "array"},
                },
                "required": ["forbidden", "must_appear"],
                "type": "object",
            },
            "bundle": {
                "enum": [
                    "complete",
                    "invalid",
                    "missing",
                    "not-applicable",
                    "specified-not-materialized",
                ]
            },
            "cache": {
                "additionalProperties": False,
                "properties": {
                    "decision": {"enum": ["hit", "miss", "not-applicable"]},
                    "identity": {"enum": ["exact", "mismatch", "not-applicable"]},
                },
                "required": ["decision", "identity"],
                "type": "object",
            },
            "evidence": {
                "additionalProperties": False,
                "properties": {
                    "availability": {
                        "enum": ["forbidden", "input-only", "not-applicable", "required"]
                    },
                    "conclusion": {
                        "enum": [
                            "implementation_inconsistent",
                            "inconclusive",
                            "input_rejected",
                            "not-applicable",
                            "not-produced",
                            "satisfied",
                            "violated",
                        ]
                    },
                    "remaining_trust": {"items": stable_id, "type": "array"},
                    "required_results": {"items": result_assertion, "type": "array"},
                    "uncovered": {"items": stable_id, "type": "array"},
                },
                "required": [
                    "availability",
                    "conclusion",
                    "remaining_trust",
                    "required_results",
                    "uncovered",
                ],
                "type": "object",
            },
            "gate": {
                "additionalProperties": False,
                "properties": {
                    "basis": {"items": stable_id, "minItems": 1, "type": "array"},
                    "decision": {"enum": ["closed", "not-applicable", "opened"]},
                },
                "required": ["basis", "decision"],
                "type": "object",
            },
            "id": stable_id,
            "independent": {
                "additionalProperties": False,
                "properties": {
                    "codes": {"items": stable_id, "type": "array"},
                    "outcome": {
                        "enum": [
                            "accepted",
                            "accepted-with-trust",
                            "incomplete",
                            "not-applicable",
                            "not-produced",
                            "rejected",
                        ]
                    },
                    "process": {"enum": ["completed", "failed", "not-run"]},
                    "process_codes": {"items": stable_id, "type": "array"},
                },
                "required": ["codes", "outcome", "process", "process_codes"],
                "type": "object",
            },
            "input": {
                "additionalProperties": False,
                "properties": {
                    "candidate": artifact,
                    "fixtures": {"items": fixture, "type": "array"},
                    "scenario_assertion": artifact,
                },
                "required": ["candidate", "fixtures", "scenario_assertion"],
                "type": "object",
            },
            "kind": {
                "enum": [
                    "benchmark",
                    "cross-contract",
                    "independent-check",
                    "pipeline",
                    "pipeline-rejection",
                    "readiness-stop",
                ]
            },
            "level": {"const": "specified"},
            "platforms": {"items": {"enum": list(PLATFORMS)}, "type": "array"},
            "profile": {"const": PROFILE},
            "receipt": {
                "additionalProperties": False,
                "properties": {
                    "availability": {
                        "enum": ["invalid-input", "not-applicable", "required"]
                    },
                    "codes": {"items": stable_id, "type": "array"},
                    "outcome": {
                        "enum": [
                            "blocked",
                            "completed",
                            "error",
                            "not-applicable",
                            "partial",
                            "rejected",
                        ]
                    },
                },
                "required": ["availability", "codes", "outcome"],
                "type": "object",
            },
            "source_refs": {"items": stable_id, "minItems": 1, "type": "array"},
            "stages": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "id": {"enum": list(STAGE_IDS)},
                        "result": {"enum": list(STAGE_RESULTS)},
                    },
                    "required": ["id", "result"],
                    "type": "object",
                },
                "maxItems": 10,
                "minItems": 10,
                "type": "array",
            },
        },
        "required": [
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
        ],
        "type": "object",
    }
    return {
        "$defs": {
            "digest": digest,
            "scenario": scenario,
            "stableId": stable_id,
        },
        "$id": "https://radishaxiom.dev/schema/implementation-readiness/manifest/0.1",
        "$schema": SCHEMA_DIALECT,
        "additionalProperties": False,
        "properties": {
            "bindings": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "name": stable_id,
                        "path": {"minLength": 1, "type": "string"},
                        "raw_sha256": digest,
                        "registry_digest": digest,
                        "task_digest": digest,
                    },
                    "required": ["name", "path", "raw_sha256"],
                    "type": "object",
                },
                "type": "array",
            },
            "coverage": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "requirement": stable_id,
                        "scenarios": {"items": stable_id, "minItems": 1, "type": "array"},
                    },
                    "required": ["requirement", "scenarios"],
                    "type": "object",
                },
                "type": "array",
            },
            "format": {"const": FORMAT},
            "format_version": {"const": FORMAT_VERSION},
            "observation": {
                "additionalProperties": False,
                "properties": {
                    "level": {"const": "specified"},
                    "observed_scenarios": {"const": "0"},
                },
                "required": ["level", "observed_scenarios"],
                "type": "object",
            },
            "platforms": {"items": {"enum": list(PLATFORMS)}, "type": "array"},
            "profile": {"const": PROFILE},
            "profiles": {"items": stable_id, "type": "array"},
            "requirement_count": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
            "requirements": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "binding": stable_id,
                        "id": stable_id,
                        "locator": {"minLength": 1, "type": "string"},
                    },
                    "required": ["binding", "id", "locator"],
                    "type": "object",
                },
                "type": "array",
            },
            "scenario_counts": {
                "additionalProperties": False,
                "properties": {
                    "benchmark": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
                    "checker": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
                    "pipeline_and_readiness": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
                    "total": {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"},
                },
                "required": ["benchmark", "checker", "pipeline_and_readiness", "total"],
                "type": "object",
            },
            "scenarios": {"items": {"$ref": "#/$defs/scenario"}, "type": "array"},
        },
        "required": [
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
        ],
        "title": "RadishAxiom Implementation Readiness Manifest v0.1",
        "type": "object",
    }
