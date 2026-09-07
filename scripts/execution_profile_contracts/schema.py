"""Build the closed JSON Schema for the execution profile manifest."""

from __future__ import annotations

from typing import Any

from .common import FORMAT, FORMAT_VERSION, SCHEMA_DIALECT


def build_schema(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "$id": "urn:radishaxiom:schema:execution-profile-set:0.1",
        "$schema": SCHEMA_DIALECT,
        "additionalProperties": False,
        "properties": {
            "certificate_capabilities": {
                "const": manifest["certificate_capabilities"]
            },
            "counts": {"const": manifest["counts"]},
            "coverage": {"const": manifest["coverage"]},
            "format": {"const": FORMAT},
            "format_version": {"const": FORMAT_VERSION},
            "level": {"const": "specified"},
            "limit_sets": {"const": manifest["limit_sets"]},
            "profiles": {"const": manifest["profiles"]},
            "references": {"const": manifest["references"]},
            "source_bindings": {"const": manifest["source_bindings"]},
        },
        "required": [
            "certificate_capabilities",
            "counts",
            "coverage",
            "format",
            "format_version",
            "level",
            "limit_sets",
            "profiles",
            "references",
            "source_bindings",
        ],
        "title": "RadishAxiom Execution Profile Set v0.1",
        "type": "object",
    }
