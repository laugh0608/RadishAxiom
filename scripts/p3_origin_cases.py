"""P3-F 自有合成 IR 与手算期望；不使用生产标签或 expected benchmark 结果。"""
import copy
import runpy
from p3_origin_derivation import ROOT

V = runpy.run_path(str(ROOT / "scripts/generate-p3-query-vectors.py"))
IR, identified, normal = V["IR"], V["identified"], V["normal"]
BOOL, TEXT, INT, FIXED, YES, NO = [V[k] for k in ["BOOL", "TEXT", "INT", "FIXED", "YES", "NO"]]


def access(name, index=0):
    return {"op": "field", "record": {"op": "bound", "index": str(index)}, "field": name}


def literal(value):
    if isinstance(value, bool):
        return {"op": "literal_bool", "value": value}
    if isinstance(value, str):
        return {"op": "literal_text", "value": value}
    return V["literal"](value)


def condition():
    return {"op": "eq", "left": access("secret"), "right": literal("synthetic")}


class Case:
    def __init__(self, capacity=4):
        self.capacity = capacity
        self.doc = {"format": "axiom-ir", "ir_version": "0.2", "digest_algorithm": "sha-256",
            "semantics": {"name": "keyed-finite-table-semantics", "sha256": IR["SEMANTICS"]}, "effects": [],
            **{k: [] for k in ["enum_types", "record_types", "table_types", "nodes", "contracts", "outputs"]}}
        self.child = self.record([("open", BOOL, "public"), ("hidden", BOOL, "sensitive")])
        self.child_ty = {"kind": "record", "record_type": self.child}
        self.table = self.schema([("id", TEXT, "public"), ("secret", TEXT, "sensitive"),
            ("secnum", INT, "sensitive"), ("units", INT, "public"), ("flag", BOOL, "public"),
            ("cash", FIXED, "sensitive"), ("group", TEXT, "public"), ("nested", self.child_ty, "public"),
            ("maybe", {"kind": "option", "inner": self.child_ty}, "sensitive")])
        self.input = self.add("node", {"kind": "input", "port": "in", "table_type": self.table})

    def add(self, kind, definition):
        entry = identified(kind, normal(definition))
        collection = IR["COLLECTIONS"][kind]
        if not any(x["id"] == entry["id"] for x in self.doc[collection]):
            self.doc[collection].append(entry)
        return entry["id"]

    def record(self, fields):
        return self.add("record-type", {"fields": sorted([dict(name=n, type=t, label=l) for n, t, l in fields], key=lambda f: f["name"])})

    def schema(self, fields):
        return self.add("table-type", {"record_type": self.record(fields), "primary_key": ["id"], "capacity": str(self.capacity)})

    def mapped(self, expression, ty=TEXT, label="public", source=None, name="result"):
        table = self.schema([("id", TEXT, "public"), (name, ty, label)])
        return self.add("node", {"kind": "map", "source": source or self.input, "table_type": table,
            "fields": sorted([{"name": "id", "expression": access("id")}, {"name": name, "expression": expression}], key=lambda f: f["name"])})

    def filtered(self, source=None):
        return self.add("node", {"kind": "filter", "source": source or self.input, "table_type": self.table, "predicate": condition()})

    def finish(self, name, node, expected, aliases=False):
        self.doc["outputs"] = [{"name": "out", "node": node}]
        if aliases:
            self.doc["outputs"].append({"name": "别名/~😀", "node": node})
        return name, IR["ordered_document"](self.doc), expected


def expected(value="public", control="public", gaps=False, inferred=None, rules=()):
    return dict(field="result", value=value, control=control, gaps=gaps, inferred=inferred, rules=list(rules))


def cases():
    expressions = [
        ("constant", literal("constant"), TEXT, expected()),
        ("direct-secret", access("secret"), TEXT, expected("sensitive", gaps=True)),
        ("same-branches", V["choose"](condition(), literal(0), literal(0)), INT, expected("sensitive", gaps=True)),
        ("dead-branch", V["choose"](NO, access("secnum"), literal(0)), INT, expected("sensitive", gaps=True)),
        ("x-minus-x", V["arithmetic"]("int_sub", access("secnum"), access("secnum")), INT, expected("sensitive", gaps=True)),
        ("strict-and", {"op": "and", "values": [NO, condition()]}, BOOL, expected("sensitive", gaps=True)),
        ("strict-or", {"op": "or", "values": [YES, condition()]}, BOOL, expected("sensitive", gaps=True)),
        ("not-secret", {"op": "not", "value": condition()}, BOOL, expected("sensitive", gaps=True)),
    ]
    for name, expr, ty, answer in expressions:
        c = Case()
        yield c.finish(name, c.mapped(expr, ty), answer)
    for op in ["eq", "lt", "le", "gt", "ge"]:
        c = Case()
        yield c.finish("compare-" + op, c.mapped(V["compare"](op, access("secnum"), literal(0)), BOOL), expected("sensitive", gaps=True))
    for op in ["int_add", "fixed_add", "fixed_sub"]:
        c = Case()
        ty, name = (FIXED, "cash") if op.startswith("fixed") else (INT, "secnum")
        yield c.finish(op, c.mapped(V["arithmetic"](op, access(name), access(name), ty), ty), expected("sensitive", gaps=True))
    for name in ["pre-false", "zero-capacity", "huge-capacity", "aliases"]:
        c = Case(0 if name == "zero-capacity" else 10**100 if name == "huge-capacity" else 4)
        if name == "pre-false":
            c.add("contract", {"kind": "formula", "role": "assume", "expression": NO})
        yield c.finish(name, c.mapped(access("secret")), expected("sensitive", gaps=True), aliases=name=="aliases")
    c = Case()
    upstream = c.mapped(access("secret"), name="copy/~😀")
    downstream = c.mapped(literal("public"), source=upstream)
    yield c.finish("constant-after-gap", downstream, expected(gaps=True))
    c = Case()
    upstream = c.mapped(access("secret"))
    yield c.finish("sensitive-relabel-after-gap", c.mapped(access("result"), label="sensitive", source=upstream), expected("sensitive", gaps=True))
    c = Case()
    upstream = c.mapped(literal("constant"), label="sensitive")
    yield c.finish("declared-sensitive-constant", c.mapped(access("result"), source=upstream), expected("sensitive", gaps=True))
    c = Case()
    other = c.mapped(access("secret"))
    name, document, answer = c.finish("unrelated-gap", c.mapped(literal("public")), expected())
    # P1 拒绝 DeadNode；用另一个命名输出保留独立分支，检验 out 的闭包隔离。
    document["outputs"].append({"name": "other", "node": other})
    yield name, IR["ordered_document"](document), answer
    c = Case()
    yield c.finish("sensitive-filter", c.mapped(literal("public"), source=c.filtered()), expected(control="sensitive"))
    c = Case()
    yield c.finish("nested-parent-summary", c.mapped({"op": "field", "record": access("nested"), "field": "open"}, BOOL), expected("sensitive", gaps=True))
    for name in ["none-record", "match-none", "shifted-binding", "nested-binding", "whole-subject", "conditional-record", "record-sibling", "record-local-gap"]:
        c = Case()
        none = {"op": "none", "type": {"kind": "option", "inner": c.child_ty}}
        some = {"op": "some", "value": NO}
        ty, expr, answer = BOOL, NO, expected()
        if name == "none-record":
            ty, expr = {"kind": "option", "inner": c.child_ty}, none
            answer = expected("sensitive", inferred="public")
        elif name == "match-none":
            expr = {"op": "match_option", "subject": none, "none": NO, "some": access("hidden"), "result_type": BOOL}
            answer = expected("sensitive", gaps=True)
        elif name in {"shifted-binding", "nested-binding"}:
            body = condition()
            body["left"]["record"]["index"] = "2" if name == "nested-binding" else "1"
            expr = {"op": "match_option", "subject": some, "none": NO, "some": body, "result_type": BOOL}
            if name == "nested-binding":
                expr = {"op": "match_option", "subject": some, "none": NO, "some": expr, "result_type": BOOL}
            answer = expected("sensitive", gaps=True)
        elif name == "whole-subject":
            expr = {"op": "match_option", "subject": {"op": "some", "value": {"op": "bound", "index": "0"}}, "none": NO,
                "some": access("flag"), "result_type": BOOL}
            answer = expected("sensitive", gaps=True)
        elif name == "conditional-record":
            select = V["choose"](condition(), access("nested"), access("nested"), c.child_ty)
            expr = {"op": "field", "record": select, "field": "open"}
            answer = expected("sensitive", gaps=True)
        else:
            value = {"op": "record", "record_type": c.child, "fields": [
                {"name": "open", "expression": condition() if name == "record-local-gap" else NO},
                {"name": "hidden", "expression": condition()}]}
            expr = {"op": "field", "record": value, "field": "open"}
            answer = expected("sensitive", gaps=True) if name == "record-local-gap" else expected()
        yield c.finish(name, c.mapped(expr, ty), answer)
    c = Case()
    rec = c.record([("open", BOOL, "public"), ("other", BOOL, "public")])
    fault = V["compare"]("eq", V["arithmetic"]("int_add", literal(2), literal(1)), literal(0))
    record = {"op": "record", "record_type": rec, "fields": [{"name": "open", "expression": NO}, {"name": "other", "expression": fault}]}
    yield c.finish("unread-sibling-fault", c.mapped({"op": "field", "record": record, "field": "open"}, BOOL), expected(rules=["expr.int_add"]))
    for mode in ["public", "secret-pairs", "right-filter"]:
        c = Case()
        right = c.add("node", {"kind": "input", "port": "right", "table_type": c.table})
        if mode == "right-filter":
            right = c.filtered(right)
        table = c.schema([("id", TEXT, "public"), ("result", TEXT, "public")])
        pair = "secret" if mode == "secret-pairs" else "id"
        joined = c.add("node", {"kind": "lookup_join", "left": c.input, "right": right, "table_type": table,
            "pairs": [{"left": pair, "right": pair}], "fields": [{"name": "id", "expression": access("id")}, {"name": "result", "expression": access("group", 1)}]})
        yield c.finish("join-" + mode, joined, expected() if mode == "public" else expected("sensitive", "sensitive", True))
    for mode in ["public", "filtered", "key-gap", "sum-gap"]:
        c = Case()
        source = c.filtered() if mode == "filtered" else c.input
        if mode in {"key-gap", "sum-gap"}:
            row = next(t["definition"]["record_type"] for t in c.doc["table_types"] if t["id"] == c.table)
            definition = next(r["definition"] for r in c.doc["record_types"] if r["id"] == row)
            changed = "group" if mode == "key-gap" else "units"
            expr = access("secret") if mode == "key-gap" else access("secnum")
            source = c.add("node", {"kind": "map", "source": source, "table_type": c.table,
                "fields": [{"name": f["name"], "expression": expr if f["name"] == changed else access(f["name"])} for f in definition["fields"]]})
        count = {"kind": "int", "lower": "0", "upper": "4"}
        table = c.schema([("id", TEXT, "public"), ("n", count, "public"), ("result", INT, "public")])
        grouped = c.add("node", {"kind": "group", "source": source, "table_type": table,
            "keys": [{"name": "id", "source_field": "group"}], "aggregates": [{"name": "n", "kind": "count"}, {"name": "result", "kind": "sum", "field": "units"}]})
        yield c.finish("group-" + mode, grouped, expected() if mode == "public" else expected("sensitive", "public" if mode == "sum-gap" else "sensitive", True))
