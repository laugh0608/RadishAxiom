"""Construct negative Pipeline Artifact Contract fixtures."""

import copy
from typing import Any, Callable

from .common import canonical_bytes

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
