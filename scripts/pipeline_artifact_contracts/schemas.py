"""Build JSON Schemas for Pipeline Artifact Contract formats."""

from typing import Any

from .common import (
    CVC5_PROFILE,
    NODE_INVOCATION_PROFILE,
    NODE_TARGET_PROFILE,
    OBLIGATION_KINDS,
    PIPELINE_PROFILE,
    SCHEMA_DIALECT,
    SEMANTICS_NAME,
    SEMANTICS_SHA256,
    STAGE_KINDS,
)

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
