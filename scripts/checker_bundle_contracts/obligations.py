"""Reconstruct the complete v0.1 obligation set from canonical benchmark IR."""

from __future__ import annotations

from typing import Any, Iterator

from .common import SEMANTICS_NAME, SEMANTICS_SHA256, entry, sorted_entries


PROVE_KINDS = {
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
CHECK_KINDS = {
    "host-conformance",
    "input-conformance",
    "ir-structure",
    "output-conformance",
}


def obligation(kind: str, subject: dict[str, Any]) -> dict[str, Any]:
    if kind in PROVE_KINDS:
        expectation = "prove"
    elif kind in CHECK_KINDS:
        expectation = "check"
    elif kind == "trust-boundary":
        expectation = "trust"
    else:
        raise ValueError(f"unknown obligation kind: {kind}")
    return entry(
        "axiom-evidence-v0.1:obligation",
        {"expectation": expectation, "kind": kind, "subject": subject},
    )


def _paths(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], dict[str, Any]]]:
    if isinstance(value, dict):
        yield path, value
        for key, item in value.items():
            yield from _paths(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _paths(item, (*path, str(index)))


def _record_fields(ir: dict[str, Any], table_type_id: str) -> list[str]:
    table_types = {item["id"]: item["definition"] for item in ir["table_types"]}
    record_types = {item["id"]: item["definition"] for item in ir["record_types"]}
    record_id = table_types[table_type_id]["record_type"]
    return [field["name"] for field in record_types[record_id]["fields"]]


def build_obligations(
    ir: dict[str, Any],
    ir_document_digest: str,
    input_artifacts: list[str],
    golden_artifacts: list[str],
    actual_output_artifacts: list[str],
    trust_entries: list[dict[str, Any]],
    *,
    profile: str,
) -> list[dict[str, Any]]:
    values = [
        obligation(
            "ir-structure",
            {"ir_document_digest": ir_document_digest, "kind": "document"},
        ),
        obligation(
            "effect-empty",
            {"ir_document_digest": ir_document_digest, "kind": "program"},
        ),
    ]

    nodes = {item["id"]: item["definition"] for item in ir["nodes"]}
    for node_id, definition in nodes.items():
        node_kind = definition["kind"]
        if node_kind != "input":
            anchor = {"id": node_id, "kind": "node"}
            values.extend(
                [obligation("totality", anchor), obligation("key-cardinality", anchor)]
            )
        if node_kind in {"filter", "lookup_join", "map"}:
            values.append(obligation("row-coverage", {"id": node_id, "kind": "node"}))
        if node_kind == "group":
            values.append(
                obligation("group-conservation", {"id": node_id, "kind": "node"})
            )
            values.append(
                obligation("row-coverage", {"id": node_id, "kind": "node"})
            )
        for path, expression in _paths(definition):
            if expression.get("op") in {
                "fixed_add",
                "fixed_sub",
                "int_add",
                "int_sub",
                "count_where",
                "sum_where",
            } or expression.get("kind") in {"count", "sum"}:
                values.append(
                    obligation(
                        "numeric-range",
                        {"id": node_id, "kind": "node-path", "path": list(path)},
                    )
                )

    for item in ir["contracts"]:
        contract_id = item["id"]
        definition = item["definition"]
        if definition["kind"] == "noninterference":
            values.append(
                obligation(
                    "noninterference", {"id": contract_id, "kind": "contract"}
                )
            )
        elif definition.get("role") == "guarantee":
            values.append(
                obligation(
                    "contract-guarantee", {"id": contract_id, "kind": "contract"}
                )
            )
        for path, expression in _paths(definition):
            if expression.get("op") in {
                "fixed_add",
                "fixed_sub",
                "int_add",
                "int_sub",
                "count_where",
                "sum_where",
            }:
                values.append(
                    obligation(
                        "numeric-range",
                        {
                            "id": contract_id,
                            "kind": "contract-path",
                            "path": list(path),
                        },
                    )
                )

    for output in ir["outputs"]:
        definition = nodes[output["node"]]
        for field_name in _record_fields(ir, definition["table_type"]):
            values.append(
                obligation(
                    "field-origin",
                    {
                        "direction": "output",
                        "interface": output["name"],
                        "kind": "field",
                        "name": field_name,
                    },
                )
            )

    if profile == "keyed-finite-table-benchmark":
        input_ports = sorted(
            item["definition"]["port"]
            for item in ir["nodes"]
            if item["definition"]["kind"] == "input"
        )
        for port in input_ports:
            values.append(
                obligation(
                    "input-conformance",
                    {"direction": "input", "kind": "interface", "name": port},
                )
            )
        for artifact in sorted(set(input_artifacts)):
            values.append(
                obligation(
                    "input-conformance", {"artifact": artifact, "kind": "artifact"}
                )
            )
        for artifact in sorted(set(actual_output_artifacts)):
            values.append(
                obligation(
                    "host-conformance", {"artifact": artifact, "kind": "artifact"}
                )
            )
        if golden_artifacts:
            for output in ir["outputs"]:
                values.append(
                    obligation(
                        "output-conformance",
                        {
                            "direction": "output",
                            "kind": "interface",
                            "name": output["name"],
                        },
                    )
                )
        for artifact in sorted(set(golden_artifacts)):
            values.append(
                obligation(
                    "output-conformance", {"artifact": artifact, "kind": "artifact"}
                )
            )

    for trust in trust_entries:
        definition = trust["definition"]
        values.append(
            obligation(
                "trust-boundary",
                {
                    "category": definition["category"],
                    "kind": "trust",
                    "scope": trust["id"],
                },
            )
        )

    encoded_definitions: set[bytes] = set()
    unique: list[dict[str, Any]] = []
    from .common import canonical_bytes

    for item in values:
        encoded = canonical_bytes(item["definition"])
        if encoded in encoded_definitions:
            continue
        encoded_definitions.add(encoded)
        unique.append(item)
    return sorted_entries(unique)


def build_obligation_set(
    ir_artifact: str,
    ir_document_digest: str,
    obligations: list[dict[str, Any]],
    *,
    profile: str,
) -> dict[str, Any]:
    return {
        "format": "axiom-obligation-set",
        "format_version": "0.1",
        "ir_artifact": ir_artifact,
        "ir_document_digest": ir_document_digest,
        "obligation_profile": {"name": profile, "version": "0.1"},
        "obligations": obligations,
        "semantics": {"name": SEMANTICS_NAME, "sha256": SEMANTICS_SHA256},
    }
