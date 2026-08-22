#!/usr/bin/env python3
"""Generate the deterministic keyed-finite-table v0.1 benchmark corpus.

This is a corpus-specific fixture builder, not a general Axiom IR implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "benchmarks/keyed-finite-table-v0.1"
CORPUS_VERSION = "0.1"
SEMANTICS_NAME = "keyed-finite-table-semantics"
SEMANTICS_SHA256 = "6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"
IR_VERSION = "0.1"
EVIDENCE_VERSION = "0.1"

Json = dict[str, Any] | list[Any] | str | bool


def validate_json(value: Json, path: str = "$") -> None:
    if type(value) is bool or isinstance(value, str):
        if isinstance(value, str) and not value.isascii():
            raise ValueError(f"corpus generator only accepts ASCII strings: {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise ValueError(f"non-ASCII JSON member: {path}")
            validate_json(item, f"{path}.{key}")
        return
    raise ValueError(f"JSON number/null or unsupported value at {path}: {value!r}")


def canonical_bytes(value: Json) -> bytes:
    validate_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def pretty_bytes(value: Json) -> bytes:
    validate_json(value)
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_id(domain: str, definition: Json) -> str:
    payload = domain.encode("utf-8") + b"\0" + canonical_bytes(definition)
    return raw_digest(payload)


def entry(domain: str, definition: dict[str, Any]) -> dict[str, Any]:
    return {"definition": definition, "id": content_id(domain, definition)}


def by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item["id"])


BOOL = {"kind": "bool"}
TEXT = {"kind": "text"}


def int_type(lower: int, upper: int) -> dict[str, str]:
    return {"kind": "int", "lower": str(lower), "upper": str(upper)}


def enum_ref(enum_id: str) -> dict[str, str]:
    return {"enum_type": enum_id, "kind": "enum"}


def enum_decl(name: str, members: list[str]) -> dict[str, Any]:
    return entry(
        "axiom-ir-v0.1:enum-type",
        {"members": members, "name": name},
    )


def record_decl(
    fields: list[tuple[str, dict[str, Any], str]],
) -> dict[str, Any]:
    definition = {
        "fields": sorted(
            (
                {"label": label, "name": name, "type": field_type}
                for name, field_type, label in fields
            ),
            key=lambda field: field["name"],
        )
    }
    return entry("axiom-ir-v0.1:record-type", definition)


def table_decl(
    record_id: str, primary_key: list[str], capacity: int = 100
) -> dict[str, Any]:
    return entry(
        "axiom-ir-v0.1:table-type",
        {
            "capacity": str(capacity),
            "primary_key": primary_key,
            "record_type": record_id,
        },
    )


def bound(index: int) -> dict[str, str]:
    return {"index": str(index), "op": "bound"}


def field(index: int, name: str) -> dict[str, Any]:
    return {"field": name, "op": "field", "record": bound(index)}


def literal_bool(value: bool) -> dict[str, Any]:
    return {"op": "literal_bool", "value": value}


def literal_int(field_type: dict[str, Any], value: int) -> dict[str, Any]:
    return {"op": "literal_int", "type": field_type, "value": str(value)}


def literal_text(value: str) -> dict[str, str]:
    return {"op": "literal_text", "value": value}


def literal_enum(enum_id: str, member: str) -> dict[str, str]:
    return {"enum_type": enum_id, "member": member, "op": "literal_enum"}


def eq(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    ordered = sorted((left, right), key=canonical_bytes)
    return {"left": ordered[0], "op": "eq", "right": ordered[1]}


def compare(
    op: str, left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    return {"left": left, "op": op, "right": right}


def not_(value: dict[str, Any]) -> dict[str, Any]:
    return {"op": "not", "value": value}


def and_(*values: dict[str, Any]) -> dict[str, Any]:
    flattened: list[dict[str, Any]] = []
    for value in values:
        if value.get("op") == "and":
            flattened.extend(value["values"])
        else:
            flattened.append(value)
    unique = {canonical_bytes(value): value for value in flattened}
    ordered = [unique[key] for key in sorted(unique)]
    if len(ordered) == 1:
        return ordered[0]
    return {"op": "and", "values": ordered}


def arithmetic(
    op: str,
    left: dict[str, Any],
    right: dict[str, Any],
    result_type: dict[str, Any],
) -> dict[str, Any]:
    if op == "int_add":
        values = sorted((left, right), key=canonical_bytes)
        return {"op": op, "result_type": result_type, "values": values}
    return {
        "left": left,
        "op": op,
        "result_type": result_type,
        "right": right,
    }


def if_(
    condition: dict[str, Any],
    then: dict[str, Any],
    else_: dict[str, Any],
    result_type: dict[str, Any],
) -> dict[str, Any]:
    return {
        "condition": condition,
        "else": else_,
        "op": "if",
        "result_type": result_type,
        "then": then,
    }


def table_ref(kind: str, name: str) -> dict[str, str]:
    return {"kind": kind, "name": name}


def lookup(kind: str, name: str, keys: list[dict[str, Any]]) -> dict[str, Any]:
    return {"keys": keys, "op": "lookup", "table": table_ref(kind, name)}


def match_option(
    subject: dict[str, Any],
    none: dict[str, Any],
    some: dict[str, Any],
    result_type: dict[str, Any] = BOOL,
) -> dict[str, Any]:
    return {
        "none": none,
        "op": "match_option",
        "result_type": result_type,
        "some": some,
        "subject": subject,
    }


def forall(kind: str, name: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"body": body, "op": "forall_rows", "table": table_ref(kind, name)}


def count_where(
    name: str, predicate: dict[str, Any], result_type: dict[str, Any]
) -> dict[str, Any]:
    return {
        "op": "count_where",
        "predicate": predicate,
        "result_type": result_type,
        "table": table_ref("input", name),
    }


def sum_where(
    name: str,
    predicate: dict[str, Any],
    value: dict[str, Any],
    result_type: dict[str, Any],
) -> dict[str, Any]:
    return {
        "op": "sum_where",
        "predicate": predicate,
        "result_type": result_type,
        "table": table_ref("input", name),
        "value": value,
    }


def node(definition: dict[str, Any]) -> dict[str, Any]:
    return entry("axiom-ir-v0.1:node", definition)


def contract(definition: dict[str, Any]) -> dict[str, Any]:
    return entry("axiom-ir-v0.1:contract", definition)


def input_node(port: str, table_id: str) -> dict[str, Any]:
    return node({"kind": "input", "port": port, "table_type": table_id})


def filter_node(
    source: str, table_id: str, predicate: dict[str, Any]
) -> dict[str, Any]:
    return node(
        {
            "kind": "filter",
            "predicate": predicate,
            "source": source,
            "table_type": table_id,
        }
    )


def map_node(
    source: str,
    table_id: str,
    fields: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    return node(
        {
            "fields": sorted(
                (
                    {"expression": expression, "name": name}
                    for name, expression in fields
                ),
                key=lambda item: item["name"],
            ),
            "kind": "map",
            "source": source,
            "table_type": table_id,
        }
    )


def join_node(
    left: str,
    right: str,
    table_id: str,
    pairs: list[tuple[str, str]],
    fields: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    return node(
        {
            "fields": sorted(
                (
                    {"expression": expression, "name": name}
                    for name, expression in fields
                ),
                key=lambda item: item["name"],
            ),
            "kind": "lookup_join",
            "left": left,
            "pairs": [
                {"left": left_name, "right": right_name}
                for left_name, right_name in sorted(pairs)
            ],
            "right": right,
            "table_type": table_id,
        }
    )


def group_node(
    source: str,
    table_id: str,
    keys: list[tuple[str, str]],
    aggregates: list[dict[str, str]],
) -> dict[str, Any]:
    return node(
        {
            "aggregates": sorted(aggregates, key=lambda item: item["name"]),
            "keys": [
                {"name": name, "source_field": source_field}
                for name, source_field in keys
            ],
            "kind": "group",
            "source": source,
            "table_type": table_id,
        }
    )


def ir_document(
    enum_types: list[dict[str, Any]],
    record_types: list[dict[str, Any]],
    table_types: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    output_name: str,
    output_node: str,
    contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "contracts": by_id(contracts),
        "digest_algorithm": "sha-256",
        "effects": [],
        "enum_types": by_id(enum_types),
        "format": "axiom-ir",
        "ir_version": IR_VERSION,
        "nodes": by_id(nodes),
        "outputs": [{"name": output_name, "node": output_node}],
        "record_types": by_id(record_types),
        "semantics": {"name": SEMANTICS_NAME, "sha256": SEMANTICS_SHA256},
        "table_types": by_id(table_types),
    }


def data_file(
    benchmark_id: str,
    role: str,
    tables: list[tuple[str, list[dict[str, Any]], list[str]]],
) -> dict[str, Any]:
    normalized_tables = []
    for name, rows, primary_key in tables:
        ordered_rows = sorted(
            rows,
            key=lambda row: tuple(canonical_bytes(row[field]) for field in primary_key),
        )
        normalized_tables.append({"name": name, "rows": ordered_rows})
    return {
        "benchmark_id": benchmark_id,
        "data_version": CORPUS_VERSION,
        "format": "axiom-benchmark-data",
        "role": role,
        "tables": sorted(normalized_tables, key=lambda table: table["name"]),
    }


BASE_TRUST = [
    "cryptographic-primitive",
    "decoder-normalizer",
    "input-origin",
    "production-generator",
    "specification-intent",
]
BASE_UNCOVERED = [
    "host-fidelity-for-all-inputs",
    "legal-regulatory-compliance",
    "long-term-archival-authenticity",
    "real-world-intent",
    "resource-performance",
    "source-truth-completeness",
    "timing-memory-log-side-channel",
]


def result(kind: str, status: str, reason: str | None = None) -> dict[str, str]:
    value = {"kind": kind, "status": status}
    if reason is not None:
        value["reason"] = reason
    return value


def expected_assertion(
    benchmark_id: str,
    candidate: str,
    fixtures: list[str],
    conclusion: str,
    required_results: list[dict[str, str]],
    counterexample: dict[str, Any],
    *,
    trust: list[str],
) -> dict[str, Any]:
    return {
        "assertion_version": CORPUS_VERSION,
        "benchmark_id": benchmark_id,
        "candidate": candidate,
        "counterexample": counterexample,
        "expected_conclusion": conclusion,
        "expected_independent_result": "accepted-with-trust",
        "fixtures": sorted(fixtures),
        "format": "axiom-expected-evidence",
        "required_results": sorted(
            required_results,
            key=lambda item: (item["kind"], item["status"], item.get("reason", "")),
        ),
        "required_trust": sorted(set(trust)),
        "required_uncovered": BASE_UNCOVERED,
    }


def witness(
    kind: str, required_keys: list[str], required_fields: list[str]
) -> dict[str, Any]:
    return {
        "kind": kind,
        "minimality": "reduced",
        "required_fields": sorted(required_fields),
        "required_keys": sorted(required_keys),
    }


def correct_results(extra_proved: list[str]) -> list[dict[str, str]]:
    proved = [
        "contract-guarantee",
        "effect-empty",
        "field-origin",
        "key-cardinality",
        "row-coverage",
        "totality",
        *extra_proved,
    ]
    return [
        result("host-conformance", "checked"),
        result("input-conformance", "checked"),
        result("ir-structure", "checked"),
        result("output-conformance", "checked"),
        *(result(kind, "proved") for kind in sorted(set(proved))),
        result("trust-boundary", "trusted"),
    ]


def make_task(
    *,
    benchmark_id: str,
    slug: str,
    enum_types: list[dict[str, Any]],
    record_types: list[dict[str, Any]],
    table_types: list[dict[str, Any]],
    input_nodes: list[dict[str, Any]],
    output_name: str,
    output_table_id: str,
    contracts: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    fixtures: dict[str, dict[str, Any]],
    scenarios: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    input_ports = sorted(
        (
            {
                "name": item["definition"]["port"],
                "table_type": item["definition"]["table_type"],
            }
            for item in input_nodes
        ),
        key=lambda item: item["name"],
    )
    task_identity = {
        "benchmark_id": benchmark_id,
        "contracts": sorted(item["id"] for item in contracts),
        "input_ports": input_ports,
        "output": {"name": output_name, "table_type": output_table_id},
        "semantics": {"name": SEMANTICS_NAME, "sha256": SEMANTICS_SHA256},
    }
    return {
        "benchmark_id": benchmark_id,
        "candidates": candidates,
        "contracts": contracts,
        "enum_types": enum_types,
        "fixtures": fixtures,
        "input_nodes": input_nodes,
        "input_ports": input_ports,
        "output": {"name": output_name, "table_type": output_table_id},
        "record_types": record_types,
        "scenarios": scenarios,
        "slug": slug,
        "table_types": table_types,
        "task_digest": content_id("axiom-benchmark-v0.1:task", task_identity),
    }


def build_b01() -> dict[str, Any]:
    benchmark_id = "AX-B01"
    money = int_type(0, 100000)
    state = enum_decl("OrderState", ["pending", "settled"])
    order_record = record_decl(
        [
            ("discount_cents", money, "public"),
            ("order_id", TEXT, "public"),
            ("state", enum_ref(state["id"]), "public"),
            ("subtotal_cents", money, "public"),
        ]
    )
    output_record = record_decl(
        [("net_cents", money, "public"), ("order_id", TEXT, "public")]
    )
    orders = table_decl(order_record["id"], ["order_id"])
    net_orders = table_decl(output_record["id"], ["order_id"])
    source = input_node("orders", orders["id"])

    assume = contract(
        {
            "expression": forall(
                "input",
                "orders",
                compare("le", field(0, "discount_cents"), field(0, "subtotal_cents")),
            ),
            "kind": "formula",
            "role": "assume",
        }
    )
    output_lookup = lookup("output", "net_orders", [field(0, "order_id")])
    settled_result = match_option(
        output_lookup,
        literal_bool(False),
        eq(
            field(0, "net_cents"),
            arithmetic(
                "int_sub",
                field(1, "subtotal_cents"),
                field(1, "discount_cents"),
                money,
            ),
        ),
    )
    pending_result = match_option(
        output_lookup, literal_bool(True), literal_bool(False)
    )
    guarantee = contract(
        {
            "expression": forall(
                "input",
                "orders",
                if_(
                    eq(field(0, "state"), literal_enum(state["id"], "settled")),
                    settled_result,
                    pending_result,
                    BOOL,
                ),
            ),
            "kind": "formula",
            "role": "guarantee",
        }
    )

    candidates: dict[str, dict[str, Any]] = {}
    for name, operation in (
        ("correct", "int_sub"),
        ("wrong-add", "int_add"),
        ("wrong-drop-zero", "int_sub"),
    ):
        settled = eq(field(0, "state"), literal_enum(state["id"], "settled"))
        if name == "wrong-drop-zero":
            settled = and_(
                settled,
                not_(eq(field(0, "subtotal_cents"), field(0, "discount_cents"))),
            )
        filtered = filter_node(source["id"], orders["id"], settled)
        mapped = map_node(
            filtered["id"],
            net_orders["id"],
            [
                (
                    "net_cents",
                    arithmetic(
                        operation,
                        field(0, "subtotal_cents"),
                        field(0, "discount_cents"),
                        money,
                    ),
                ),
                ("order_id", field(0, "order_id")),
            ],
        )
        candidates[name] = ir_document(
            [state],
            [order_record, output_record],
            [orders, net_orders],
            [source, filtered, mapped],
            "net_orders",
            mapped["id"],
            [assume, guarantee],
        )

    fixtures = {
        "base": {
            "input": data_file(
                benchmark_id,
                "input",
                [
                    (
                        "orders",
                        [
                            {
                                "discount_cents": "100",
                                "order_id": "O1",
                                "state": "settled",
                                "subtotal_cents": "1000",
                            },
                            {
                                "discount_cents": "0",
                                "order_id": "O2",
                                "state": "pending",
                                "subtotal_cents": "500",
                            },
                            {
                                "discount_cents": "750",
                                "order_id": "O3",
                                "state": "settled",
                                "subtotal_cents": "750",
                            },
                        ],
                        ["order_id"],
                    )
                ],
            ),
            "golden": data_file(
                benchmark_id,
                "golden-output",
                [
                    (
                        "net_orders",
                        [
                            {"net_cents": "900", "order_id": "O1"},
                            {"net_cents": "0", "order_id": "O3"},
                        ],
                        ["order_id"],
                    )
                ],
            ),
            "kind": "valid",
        },
        "boundary": {
            "input": data_file(
                benchmark_id,
                "input",
                [
                    (
                        "orders",
                        [
                            {
                                "discount_cents": "0",
                                "order_id": "O4",
                                "state": "settled",
                                "subtotal_cents": "100000",
                            }
                        ],
                        ["order_id"],
                    )
                ],
            ),
            "golden": data_file(
                benchmark_id,
                "golden-output",
                [("net_orders", [{"net_cents": "100000", "order_id": "O4"}], ["order_id"])],
            ),
            "kind": "valid",
        },
        "invalid": {
            "input": data_file(
                benchmark_id,
                "invalid-input",
                [
                    (
                        "orders",
                        [
                            {
                                "discount_cents": "101",
                                "order_id": "OX",
                                "state": "settled",
                                "subtotal_cents": "100",
                            }
                        ],
                        ["order_id"],
                    )
                ],
            ),
            "kind": "invalid",
        },
    }
    full_trust = BASE_TRUST + ["host-runtime", "proof-backend"]
    scenarios = {
        "correct": expected_assertion(
            benchmark_id,
            "correct",
            ["base", "boundary"],
            "satisfied",
            correct_results(["numeric-range"]),
            {"kind": "none"},
            trust=full_trust,
        ),
        "wrong-add": expected_assertion(
            benchmark_id,
            "wrong-add",
            ["base"],
            "violated",
            [result("contract-guarantee", "failed")],
            witness("single-row", ["orders:O1"], ["discount_cents", "net_cents", "subtotal_cents"]),
            trust=BASE_TRUST,
        ),
        "wrong-drop-zero": expected_assertion(
            benchmark_id,
            "wrong-drop-zero",
            ["base"],
            "violated",
            [result("row-coverage", "failed")],
            witness("single-row", ["orders:O3"], ["discount_cents", "subtotal_cents"]),
            trust=BASE_TRUST,
        ),
        "backend-timeout": expected_assertion(
            benchmark_id,
            "correct",
            ["base"],
            "inconclusive",
            [result("contract-guarantee", "unknown", "timeout")],
            {"kind": "none"},
            trust=BASE_TRUST + ["proof-backend"],
        ),
        "invalid-input": expected_assertion(
            benchmark_id,
            "correct",
            ["invalid"],
            "input_rejected",
            [result("input-conformance", "failed")],
            witness("single-row", ["orders:OX"], ["discount_cents", "subtotal_cents"]),
            trust=BASE_TRUST,
        ),
    }
    return make_task(
        benchmark_id=benchmark_id,
        slug="ax-b01",
        enum_types=[state],
        record_types=[order_record, output_record],
        table_types=[orders, net_orders],
        input_nodes=[source],
        output_name="net_orders",
        output_table_id=net_orders["id"],
        contracts=[assume, guarantee],
        candidates=candidates,
        fixtures=fixtures,
        scenarios=scenarios,
    )


def build_b02() -> dict[str, Any]:
    benchmark_id = "AX-B02"
    tier = enum_decl("CustomerTier", ["gold", "silver"])
    order_record = record_decl(
        [
            ("customer_id", TEXT, "public"),
            ("order_id", TEXT, "public"),
            ("region", TEXT, "public"),
        ]
    )
    customer_record = record_decl(
        [
            ("customer_id", TEXT, "public"),
            ("region", TEXT, "public"),
            ("tier", enum_ref(tier["id"]), "public"),
        ]
    )
    output_record = record_decl(
        [("order_id", TEXT, "public"), ("tier", enum_ref(tier["id"]), "public")]
    )
    orders = table_decl(order_record["id"], ["order_id"])
    customers = table_decl(customer_record["id"], ["customer_id"])
    output = table_decl(output_record["id"], ["order_id"])
    orders_node = input_node("orders", orders["id"])
    customers_node = input_node("customers", customers["id"])

    customer_lookup = lookup("input", "customers", [field(0, "customer_id")])
    assume = contract(
        {
            "expression": forall(
                "input",
                "orders",
                match_option(customer_lookup, literal_bool(False), literal_bool(True)),
            ),
            "kind": "formula",
            "role": "assume",
        }
    )
    nested_output = match_option(
        lookup("output", "order_tiers", [field(1, "order_id")]),
        literal_bool(False),
        eq(field(0, "tier"), field(1, "tier")),
    )
    guarantee = contract(
        {
            "expression": forall(
                "input",
                "orders",
                match_option(customer_lookup, literal_bool(False), nested_output),
            ),
            "kind": "formula",
            "role": "guarantee",
        }
    )

    candidates = {}
    for name, pairs, tier_expression in (
        ("correct", [("customer_id", "customer_id")], field(1, "tier")),
        ("wrong-region-join", [("region", "region")], field(1, "tier")),
        ("wrong-constant-tier", [("customer_id", "customer_id")], literal_enum(tier["id"], "silver")),
    ):
        joined = join_node(
            orders_node["id"],
            customers_node["id"],
            output["id"],
            pairs,
            [("order_id", field(0, "order_id")), ("tier", tier_expression)],
        )
        candidates[name] = ir_document(
            [tier],
            [order_record, customer_record, output_record],
            [orders, customers, output],
            [orders_node, customers_node, joined],
            "order_tiers",
            joined["id"],
            [assume, guarantee],
        )

    base_orders = [
        {"customer_id": "C1", "order_id": "O1", "region": "north"},
        {"customer_id": "C2", "order_id": "O2", "region": "north"},
    ]
    base_customers = [
        {"customer_id": "C1", "region": "north", "tier": "gold"},
        {"customer_id": "C2", "region": "north", "tier": "silver"},
    ]
    fixtures = {
        "base": {
            "input": data_file(
                benchmark_id,
                "input",
                [
                    ("customers", base_customers, ["customer_id"]),
                    ("orders", base_orders, ["order_id"]),
                ],
            ),
            "golden": data_file(
                benchmark_id,
                "golden-output",
                [
                    (
                        "order_tiers",
                        [
                            {"order_id": "O1", "tier": "gold"},
                            {"order_id": "O2", "tier": "silver"},
                        ],
                        ["order_id"],
                    )
                ],
            ),
            "kind": "valid",
        },
        "boundary": {
            "input": data_file(
                benchmark_id,
                "input",
                [
                    ("customers", [{"customer_id": "C3", "region": "south", "tier": "gold"}], ["customer_id"]),
                    ("orders", [{"customer_id": "C3", "order_id": "O3", "region": "south"}], ["order_id"]),
                ],
            ),
            "golden": data_file(
                benchmark_id,
                "golden-output",
                [("order_tiers", [{"order_id": "O3", "tier": "gold"}], ["order_id"])],
            ),
            "kind": "valid",
        },
        "invalid": {
            "input": data_file(
                benchmark_id,
                "invalid-input",
                [
                    ("customers", base_customers, ["customer_id"]),
                    ("orders", [{"customer_id": "C404", "order_id": "OX", "region": "north"}], ["order_id"]),
                ],
            ),
            "kind": "invalid",
        },
    }
    scenarios = {
        "correct": expected_assertion(
            benchmark_id,
            "correct",
            ["base", "boundary"],
            "satisfied",
            correct_results([]),
            {"kind": "none"},
            trust=BASE_TRUST + ["host-runtime", "proof-backend"],
        ),
        "wrong-region-join": expected_assertion(
            benchmark_id,
            "wrong-region-join",
            ["base"],
            "violated",
            [result("key-cardinality", "failed")],
            witness("row-pair", ["customers:C1", "customers:C2", "orders:O1"], ["region"]),
            trust=BASE_TRUST,
        ),
        "wrong-constant-tier": expected_assertion(
            benchmark_id,
            "wrong-constant-tier",
            ["base"],
            "violated",
            [result("field-origin", "failed")],
            witness("row-pair", ["customers:C1", "orders:O1"], ["tier"]),
            trust=BASE_TRUST,
        ),
        "backend-timeout": expected_assertion(
            benchmark_id,
            "correct",
            ["base"],
            "inconclusive",
            [result("key-cardinality", "unknown", "timeout")],
            {"kind": "none"},
            trust=BASE_TRUST + ["proof-backend"],
        ),
        "invalid-input": expected_assertion(
            benchmark_id,
            "correct",
            ["invalid"],
            "input_rejected",
            [result("input-conformance", "failed")],
            witness("missing-key", ["orders:OX"], ["customer_id"]),
            trust=BASE_TRUST,
        ),
    }
    return make_task(
        benchmark_id=benchmark_id,
        slug="ax-b02",
        enum_types=[tier],
        record_types=[order_record, customer_record, output_record],
        table_types=[orders, customers, output],
        input_nodes=[orders_node, customers_node],
        output_name="order_tiers",
        output_table_id=output["id"],
        contracts=[assume, guarantee],
        candidates=candidates,
        fixtures=fixtures,
        scenarios=scenarios,
    )


def build_b03() -> dict[str, Any]:
    benchmark_id = "AX-B03"
    units = int_type(0, 1000)
    count = int_type(0, 100)
    total = int_type(0, 100000)
    event_record = record_decl(
        [
            ("account_id", TEXT, "public"),
            ("event_id", TEXT, "public"),
            ("units", units, "public"),
        ]
    )
    output_record = record_decl(
        [
            ("account_id", TEXT, "public"),
            ("event_count", count, "public"),
            ("total_units", total, "public"),
        ]
    )
    events = table_decl(event_record["id"], ["event_id"])
    output = table_decl(output_record["id"], ["account_id"])
    source = input_node("usage_events", events["id"])

    group_predicate = eq(field(0, "account_id"), field(2, "account_id"))
    expected_count = count_where("usage_events", group_predicate, count)
    expected_total = sum_where(
        "usage_events", group_predicate, field(0, "units"), total
    )
    aggregate_match = match_option(
        lookup("output", "account_usage", [field(0, "account_id")]),
        literal_bool(False),
        and_(
            eq(field(0, "event_count"), expected_count),
            eq(field(0, "total_units"), expected_total),
        ),
    )
    guarantee = contract(
        {
            "expression": forall("input", "usage_events", aggregate_match),
            "kind": "formula",
            "role": "guarantee",
        }
    )

    candidates = {}
    correct_group = group_node(
        source["id"],
        output["id"],
        [("account_id", "account_id")],
        [
            {"kind": "count", "name": "event_count"},
            {"field": "units", "kind": "sum", "name": "total_units"},
        ],
    )
    candidates["correct"] = ir_document(
        [],
        [event_record, output_record],
        [events, output],
        [source, correct_group],
        "account_usage",
        correct_group["id"],
        [guarantee],
    )

    for name, account_expression, units_expression in (
        ("wrong-single-group", literal_text("ALL"), field(0, "units")),
        ("wrong-unit-sum", field(0, "account_id"), literal_int(units, 1)),
    ):
        mapped = map_node(
            source["id"],
            events["id"],
            [
                ("account_id", account_expression),
                ("event_id", field(0, "event_id")),
                ("units", units_expression),
            ],
        )
        grouped = group_node(
            mapped["id"],
            output["id"],
            [("account_id", "account_id")],
            [
                {"kind": "count", "name": "event_count"},
                {"field": "units", "kind": "sum", "name": "total_units"},
            ],
        )
        candidates[name] = ir_document(
            [],
            [event_record, output_record],
            [events, output],
            [source, mapped, grouped],
            "account_usage",
            grouped["id"],
            [guarantee],
        )

    base_rows = [
        {"account_id": "A1", "event_id": "E1", "units": "4"},
        {"account_id": "A1", "event_id": "E2", "units": "6"},
        {"account_id": "A2", "event_id": "E3", "units": "3"},
    ]
    fixtures = {
        "base": {
            "input": data_file(benchmark_id, "input", [("usage_events", base_rows, ["event_id"])]),
            "golden": data_file(
                benchmark_id,
                "golden-output",
                [
                    (
                        "account_usage",
                        [
                            {"account_id": "A1", "event_count": "2", "total_units": "10"},
                            {"account_id": "A2", "event_count": "1", "total_units": "3"},
                        ],
                        ["account_id"],
                    )
                ],
            ),
            "kind": "valid",
        },
        "boundary": {
            "input": data_file(benchmark_id, "input", [("usage_events", [], ["event_id"])]),
            "golden": data_file(benchmark_id, "golden-output", [("account_usage", [], ["account_id"])]),
            "kind": "valid",
        },
        "invalid": {
            "input": data_file(
                benchmark_id,
                "invalid-input",
                [
                    (
                        "usage_events",
                        [
                            {"account_id": "A1", "event_id": "EX", "units": "1"},
                            {"account_id": "A2", "event_id": "EX", "units": "2"},
                        ],
                        ["event_id"],
                    )
                ],
            ),
            "kind": "invalid",
        },
    }
    scenarios = {
        "correct": expected_assertion(
            benchmark_id,
            "correct",
            ["base", "boundary"],
            "satisfied",
            correct_results(["group-conservation", "numeric-range"]),
            {"kind": "none"},
            trust=BASE_TRUST + ["host-runtime", "proof-backend"],
        ),
        "wrong-single-group": expected_assertion(
            benchmark_id,
            "wrong-single-group",
            ["base"],
            "violated",
            [result("group-conservation", "failed")],
            witness("group", ["usage_events:E1", "usage_events:E3"], ["account_id"]),
            trust=BASE_TRUST,
        ),
        "wrong-unit-sum": expected_assertion(
            benchmark_id,
            "wrong-unit-sum",
            ["base"],
            "violated",
            [result("contract-guarantee", "failed")],
            witness("group", ["usage_events:E1", "usage_events:E2"], ["total_units", "units"]),
            trust=BASE_TRUST,
        ),
        "backend-timeout": expected_assertion(
            benchmark_id,
            "correct",
            ["base"],
            "inconclusive",
            [result("group-conservation", "unknown", "timeout")],
            {"kind": "none"},
            trust=BASE_TRUST + ["proof-backend"],
        ),
        "invalid-input": expected_assertion(
            benchmark_id,
            "correct",
            ["invalid"],
            "input_rejected",
            [result("input-conformance", "failed")],
            witness("row-pair", ["usage_events:EX"], ["event_id"]),
            trust=BASE_TRUST,
        ),
    }
    return make_task(
        benchmark_id=benchmark_id,
        slug="ax-b03",
        enum_types=[],
        record_types=[event_record, output_record],
        table_types=[events, output],
        input_nodes=[source],
        output_name="account_usage",
        output_table_id=output["id"],
        contracts=[guarantee],
        candidates=candidates,
        fixtures=fixtures,
        scenarios=scenarios,
    )


def build_b04() -> dict[str, Any]:
    benchmark_id = "AX-B04"
    category = enum_decl("TicketCategory", ["billing", "support"])
    priority = enum_decl("TicketPriority", ["high", "low"])
    ticket_record = record_decl(
        [
            ("category", enum_ref(category["id"]), "public"),
            ("contact_email", TEXT, "sensitive"),
            ("internal_note", TEXT, "sensitive"),
            ("priority", enum_ref(priority["id"]), "public"),
            ("ticket_id", TEXT, "public"),
        ]
    )
    output_record = record_decl(
        [
            ("category", enum_ref(category["id"]), "public"),
            ("priority", enum_ref(priority["id"]), "public"),
            ("ticket_id", TEXT, "public"),
        ]
    )
    tickets = table_decl(ticket_record["id"], ["ticket_id"])
    output = table_decl(output_record["id"], ["ticket_id"])
    source = input_node("tickets", tickets["id"])

    guarantee = contract(
        {
            "expression": forall(
                "input",
                "tickets",
                match_option(
                    lookup("output", "export", [field(0, "ticket_id")]),
                    literal_bool(False),
                    and_(
                        eq(field(0, "category"), field(1, "category")),
                        eq(field(0, "priority"), field(1, "priority")),
                        eq(field(0, "ticket_id"), field(1, "ticket_id")),
                    ),
                ),
            ),
            "kind": "formula",
            "role": "guarantee",
        }
    )
    noninterference = contract(
        {"inputs": ["tickets"], "kind": "noninterference", "outputs": ["export"]}
    )

    candidates = {}
    for name in ("correct", "wrong-sensitive-filter", "wrong-sensitive-priority"):
        nodes = [source]
        map_source = source
        if name == "wrong-sensitive-filter":
            map_source = filter_node(
                source["id"],
                tickets["id"],
                eq(field(0, "contact_email"), literal_text("a@example.test")),
            )
            nodes.append(map_source)
        priority_expression: dict[str, Any] = field(0, "priority")
        if name == "wrong-sensitive-priority":
            priority_expression = if_(
                eq(field(0, "contact_email"), literal_text("a@example.test")),
                literal_enum(priority["id"], "high"),
                literal_enum(priority["id"], "low"),
                enum_ref(priority["id"]),
            )
        mapped = map_node(
            map_source["id"],
            output["id"],
            [
                ("category", field(0, "category")),
                ("priority", priority_expression),
                ("ticket_id", field(0, "ticket_id")),
            ],
        )
        nodes.append(mapped)
        candidates[name] = ir_document(
            [category, priority],
            [ticket_record, output_record],
            [tickets, output],
            nodes,
            "export",
            mapped["id"],
            [guarantee, noninterference],
        )

    base_rows = [
        {
            "category": "billing",
            "contact_email": "a@example.test",
            "internal_note": "manual review",
            "priority": "high",
            "ticket_id": "T1",
        },
        {
            "category": "support",
            "contact_email": "b@example.test",
            "internal_note": "known issue",
            "priority": "low",
            "ticket_id": "T2",
        },
    ]
    variant_rows = [dict(row) for row in base_rows]
    variant_rows[0]["contact_email"] = "z@example.test"
    variant_rows[0]["internal_note"] = "different secret"
    golden_rows = [
        {"category": "billing", "priority": "high", "ticket_id": "T1"},
        {"category": "support", "priority": "low", "ticket_id": "T2"},
    ]
    fixtures = {
        "base": {
            "input": data_file(benchmark_id, "input", [("tickets", base_rows, ["ticket_id"])]),
            "golden": data_file(benchmark_id, "golden-output", [("export", golden_rows, ["ticket_id"])]),
            "kind": "valid",
        },
        "boundary": {
            "input": data_file(benchmark_id, "input", [("tickets", variant_rows, ["ticket_id"])]),
            "golden": data_file(benchmark_id, "golden-output", [("export", golden_rows, ["ticket_id"])]),
            "kind": "valid",
        },
        "invalid": {
            "input": data_file(
                benchmark_id,
                "invalid-input",
                [
                    (
                        "tickets",
                        [base_rows[0], {**base_rows[1], "ticket_id": "T1"}],
                        ["ticket_id"],
                    )
                ],
            ),
            "kind": "invalid",
        },
    }
    sensitive_trust = BASE_TRUST + ["sensitivity-classification"]
    scenarios = {
        "correct": expected_assertion(
            benchmark_id,
            "correct",
            ["base", "boundary"],
            "satisfied",
            correct_results(["noninterference"]),
            {"kind": "none"},
            trust=sensitive_trust + ["host-runtime", "proof-backend"],
        ),
        "wrong-sensitive-filter": expected_assertion(
            benchmark_id,
            "wrong-sensitive-filter",
            ["base", "boundary"],
            "violated",
            [result("noninterference", "failed")],
            witness("paired-input", ["tickets:T1"], ["contact_email"]),
            trust=sensitive_trust,
        ),
        "wrong-sensitive-priority": expected_assertion(
            benchmark_id,
            "wrong-sensitive-priority",
            ["base", "boundary"],
            "violated",
            [result("noninterference", "failed")],
            witness("paired-input", ["tickets:T1"], ["contact_email", "priority"]),
            trust=sensitive_trust,
        ),
        "backend-timeout": expected_assertion(
            benchmark_id,
            "correct",
            ["base"],
            "inconclusive",
            [result("noninterference", "unknown", "timeout")],
            {"kind": "none"},
            trust=sensitive_trust + ["proof-backend"],
        ),
        "invalid-input": expected_assertion(
            benchmark_id,
            "correct",
            ["invalid"],
            "input_rejected",
            [result("input-conformance", "failed")],
            witness("row-pair", ["tickets:T1"], ["ticket_id"]),
            trust=sensitive_trust,
        ),
    }
    return make_task(
        benchmark_id=benchmark_id,
        slug="ax-b04",
        enum_types=[category, priority],
        record_types=[ticket_record, output_record],
        table_types=[tickets, output],
        input_nodes=[source],
        output_name="export",
        output_table_id=output["id"],
        contracts=[guarantee, noninterference],
        candidates=candidates,
        fixtures=fixtures,
        scenarios=scenarios,
    )


def validate_candidate(task: dict[str, Any], document: dict[str, Any]) -> None:
    domains = {
        "contracts": "axiom-ir-v0.1:contract",
        "enum_types": "axiom-ir-v0.1:enum-type",
        "nodes": "axiom-ir-v0.1:node",
        "record_types": "axiom-ir-v0.1:record-type",
        "table_types": "axiom-ir-v0.1:table-type",
    }
    for member, domain in domains.items():
        entries = document[member]
        ids = [item["id"] for item in entries]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError(
                f"{task['benchmark_id']}: {member} IDs are unsorted or duplicated"
            )
        for item in entries:
            if item["id"] != content_id(domain, item["definition"]):
                raise ValueError(f"{task['benchmark_id']}: invalid {member} ID")
    contract_ids = [item["id"] for item in document["contracts"]]
    if contract_ids != sorted(item["id"] for item in task["contracts"]):
        raise ValueError(f"{task['benchmark_id']}: candidate changed task contracts")
    actual_inputs = sorted(
        (
            {
                "name": item["definition"]["port"],
                "table_type": item["definition"]["table_type"],
            }
            for item in document["nodes"]
            if item["definition"]["kind"] == "input"
        ),
        key=lambda item: item["name"],
    )
    if actual_inputs != task["input_ports"]:
        raise ValueError(f"{task['benchmark_id']}: candidate changed input interface")
    nodes = {item["id"]: item["definition"] for item in document["nodes"]}
    output_node = nodes[document["outputs"][0]["node"]]
    if output_node["table_type"] != task["output"]["table_type"]:
        raise ValueError(f"{task['benchmark_id']}: candidate changed output table type")
    referenced: set[str] = set()
    pending = [document["outputs"][0]["node"]]
    while pending:
        node_id = pending.pop()
        if node_id in referenced:
            continue
        if node_id not in nodes:
            raise ValueError(f"{task['benchmark_id']}: dangling node {node_id}")
        referenced.add(node_id)
        definition = nodes[node_id]
        for member in ("source", "left", "right"):
            if member in definition:
                pending.append(definition[member])
    if referenced != set(nodes):
        raise ValueError(f"{task['benchmark_id']}: candidate contains dead nodes")
    if canonical_bytes(json.loads(pretty_bytes(document))) != canonical_bytes(document):
        raise ValueError(f"{task['benchmark_id']}: pretty round-trip changed IR")


def file_ref(path: str, data: bytes) -> dict[str, str]:
    return {"path": path, "sha256": raw_digest(data)}


def build_generated_files() -> dict[str, bytes]:
    tasks = [build_b01(), build_b02(), build_b03(), build_b04()]
    generated: dict[str, bytes] = {}
    root_tasks = []

    for task in tasks:
        slug = task["slug"]
        candidate_entries = []
        for name, document in sorted(task["candidates"].items()):
            validate_candidate(task, document)
            canonical_path = f"{slug}/candidates/{name}.ir.jcs"
            pretty_path = f"{slug}/candidates/{name}.ir.json"
            canonical = canonical_bytes(document)
            pretty = pretty_bytes(document)
            generated[canonical_path] = canonical
            generated[pretty_path] = pretty
            candidate_entries.append(
                {
                    "canonical": file_ref(canonical_path, canonical),
                    "document_digest": content_id(
                        "axiom-ir-v0.1:document", document
                    ),
                    "name": name,
                    "pretty": file_ref(pretty_path, pretty),
                }
            )

        fixture_entries = []
        for name, fixture in sorted(task["fixtures"].items()):
            input_path = f"{slug}/fixtures/{name}.input.json"
            input_bytes = pretty_bytes(fixture["input"])
            generated[input_path] = input_bytes
            if fixture["kind"] == "valid":
                golden_path = f"{slug}/fixtures/{name}.golden.json"
                golden_bytes = pretty_bytes(fixture["golden"])
                generated[golden_path] = golden_bytes
                fixture_entries.append(
                    {
                        "golden": file_ref(golden_path, golden_bytes),
                        "input": file_ref(input_path, input_bytes),
                        "kind": "valid",
                        "name": name,
                    }
                )
            else:
                fixture_entries.append(
                    {
                        "input": file_ref(input_path, input_bytes),
                        "kind": "invalid",
                        "name": name,
                    }
                )

        scenario_entries = []
        for name, assertion in sorted(task["scenarios"].items()):
            path = f"{slug}/expected/{name}.json"
            data = pretty_bytes(assertion)
            generated[path] = data
            scenario_entries.append({"name": name, **file_ref(path, data)})

        task_manifest = {
            "benchmark_id": task["benchmark_id"],
            "candidates": candidate_entries,
            "corpus_version": CORPUS_VERSION,
            "fixtures": fixture_entries,
            "format": "axiom-benchmark-task",
            "input_ports": task["input_ports"],
            "output": task["output"],
            "scenarios": scenario_entries,
            "task_contract_ids": sorted(item["id"] for item in task["contracts"]),
            "task_digest": task["task_digest"],
            "task_version": CORPUS_VERSION,
        }
        task_path = f"{slug}/task.json"
        task_bytes = pretty_bytes(task_manifest)
        generated[task_path] = task_bytes
        root_tasks.append(
            {
                "benchmark_id": task["benchmark_id"],
                **file_ref(task_path, task_bytes),
            }
        )

    generator_path = Path(__file__).relative_to(REPO_ROOT).as_posix()
    generator_bytes = Path(__file__).read_bytes()
    corpus_manifest = {
        "corpus_version": CORPUS_VERSION,
        "evidence_version": EVIDENCE_VERSION,
        "format": "axiom-benchmark-corpus",
        "generator": {
            "path": generator_path,
            "sha256": raw_digest(generator_bytes),
            "version": CORPUS_VERSION,
        },
        "ir_version": IR_VERSION,
        "semantics": {"name": SEMANTICS_NAME, "sha256": SEMANTICS_SHA256},
        "tasks": root_tasks,
    }
    generated["corpus.json"] = pretty_bytes(corpus_manifest)
    return generated


def actual_generated_paths() -> set[str]:
    if not CORPUS_ROOT.exists():
        return set()
    return {
        path.relative_to(CORPUS_ROOT).as_posix()
        for path in CORPUS_ROOT.rglob("*")
        if path.is_file() and path.name != "README.md"
    }


def check_generated(expected: dict[str, bytes]) -> list[str]:
    errors = []
    expected_paths = set(expected)
    actual_paths = actual_generated_paths()
    for path in sorted(expected_paths - actual_paths):
        errors.append(f"missing generated file: {path}")
    for path in sorted(actual_paths - expected_paths):
        errors.append(f"unexpected generated file: {path}")
    for relative_path in sorted(expected_paths & actual_paths):
        actual = (CORPUS_ROOT / relative_path).read_bytes()
        if actual != expected[relative_path]:
            errors.append(f"generated file differs: {relative_path}")
    return errors


def write_generated(expected: dict[str, bytes]) -> None:
    for relative_path, data in sorted(expected.items()):
        path = CORPUS_ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="compare without writing")
    mode.add_argument("--write", action="store_true", help="write deterministic files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = build_generated_files()
    if args.write:
        write_generated(expected)
    errors = check_generated(expected)
    if errors:
        print("benchmark corpus check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"benchmark corpus passed ({len(expected)} generated files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
