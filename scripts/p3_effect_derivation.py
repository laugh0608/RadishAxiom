"""ADR 0023 独立效果规则重建；完整 P1 类型正确性是输入前提，不是证明 checker。"""
import heapq
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
P2 = runpy.run_path(str(ROOT / "scripts/generate-p2-profile-review.py"))
canonical, digest, identity = P2["canonical"], P2["raw_digest"], P2["identity"]
GENERATOR = "sha256:" + "a" * 64

# 精确子项模式，与 Rust 的 match / 路径栈分别实现。
LEAVES = {
    "literal_bool": "value", "literal_text": "value", "literal_int": "type value",
    "literal_fixed": "type coefficient", "literal_enum": "enum_type member", "none": "type", "bound": "index",
}
CHILDREN = {
    "field": ("field record", ["record"]), "some": ("value", ["value"]), "not": ("value", ["value"]),
    "and": ("values", ["values/*"]), "or": ("values", ["values/*"]),
    "int_add": ("values result_type", ["values/*"]), "fixed_add": ("values result_type", ["values/*"]),
    **{op: ("left right", ["left", "right"]) for op in ["eq", "lt", "le", "gt", "ge"]},
    **{op: ("left right result_type", ["left", "right"]) for op in ["int_sub", "fixed_sub"]},
    "if": ("condition then else result_type", ["condition", "then", "else"]),
    "match_option": ("subject none some result_type", ["subject", "none", "some"]),
    "record": ("record_type fields", ["fields/*/expression"]),
    "forall_rows": ("table body", ["body"]), "exists_rows": ("table body", ["body"]),
    "lookup": ("table keys", ["keys/*"]), "count_where": ("table predicate result_type", ["predicate"]),
    "sum_where": ("table predicate value result_type", ["predicate", "value"]),
}
TABLE_OPS = {"forall_rows", "exists_rows", "lookup", "count_where", "sum_where"}


def shape(value, names):
    assert isinstance(value, dict) and set(value) == set(names.split()), (value, names)


def make_set(ir):
    raw = canonical(ir).encode()
    doc_id = identity("axiom-ir-v0.2:document", ir)
    return P2["obligation_set"]({"ir": ir, "ir_artifact": digest(raw), "ir_document_digest": doc_id,
                                 "definitions": P2["proposed_definitions"](ir, doc_id)})


def derive(ir, obligations, generator=GENERATOR):
    assert ir["ir_version"] == "0.2" and ir["effects"] == []
    assert obligations == make_set(ir), "P2 binding or completeness"
    assert generator.startswith("sha256:") and len(generator) == 71 and all(c in "0123456789abcdef" for c in generator[7:])
    targets = [o for o in obligations["obligations"] if o["definition"]["kind"] == "effect-empty"]
    assert len(targets) == 1
    nodes = {e["id"]: e["definition"] for e in ir["nodes"]}
    steps, done, inputs, outputs = [], {}, {}, {}

    def add(kind, ident, path, rule, premises=()):
        assert all(isinstance(p, int) and 0 <= p < len(steps) for p in premises)
        index = len(steps)
        steps.append({"anchor": {"kind": kind, "id": ident}, "path": list(path),
                      "premises": list(map(str, premises)), "rule": rule})
        return index

    def expression(v, anchor, path, depth, mode):
        op = v["op"]
        if op in LEAVES:
            shape(v, "op " + LEAVES[op])
            if op == "bound":
                assert v["index"] == str(int(v["index"])) and 0 <= int(v["index"]) < depth
            return add(*anchor, path, "expr." + op)
        assert op in CHILDREN, "unknown expression"
        members, selectors = CHILDREN[op]
        shape(v, "op " + members)
        edges = []
        if op in TABLE_OPS:
            table = v["table"]
            shape(table, "kind name")
            assert mode in {"assume", "guarantee"}
            assert table["kind"] in {"input", "output"} and (mode != "assume" or table["kind"] == "input")
            ref = (inputs if table["kind"] == "input" else outputs)[table["name"]]
            edges.append(add(*anchor, (*path, "table"), "interface." + table["kind"], [ref]))
        for selector in selectors:
            if selector == "fields/*/expression":
                for i, field in enumerate(v["fields"]):
                    shape(field, "name expression")
                    edges.append(expression(field["expression"], anchor, (*path, "fields", str(i), "expression"), depth, mode))
            elif selector.endswith("/*"):
                key = selector[:-2]
                edges.extend(expression(child, anchor, (*path, key, str(i)), depth, mode) for i, child in enumerate(v[key]))
            else:
                bound = op in TABLE_OPS or (op == "match_option" and selector == "some")
                edges.append(expression(v[selector], anchor, (*path, selector), depth + int(bound), mode))
        return add(*anchor, path, "expr." + op, edges)

    # Kahn 队列按深度与 ID 排序；不借用生产 P1 图顺序，也不递归展开图。
    deps, parents, depths = {}, {n: [] for n in nodes}, {n: 0 for n in nodes}
    for ident, node in nodes.items():
        kind = node["kind"]
        fields = {"input": "kind port table_type", "filter": "kind predicate source table_type",
                  "map": "kind fields source table_type", "lookup_join": "kind left right pairs fields table_type",
                  "group": "kind source keys aggregates table_type"}
        assert kind in fields
        shape(node, fields[kind])
        refs = [] if kind == "input" else ([node["left"], node["right"]] if kind == "lookup_join" else [node["source"]])
        deps[ident] = set(refs)
        for ref in deps[ident]: parents[ref].append(ident)
    ready = [(0, n) for n in nodes if not deps[n]]
    heapq.heapify(ready)
    while ready:
        depth, ident = heapq.heappop(ready)
        node, anchor = nodes[ident], ("node", ident)
        kind = node["kind"]
        edges = [] if kind == "input" else ([done[node["left"]], done[node["right"]]] if kind == "lookup_join" else [done[node["source"]]])
        if kind == "filter": edges.append(expression(node["predicate"], anchor, ("predicate",), 1, None))
        if kind == "lookup_join":
            for i, pair in enumerate(node["pairs"]):
                shape(pair, "left right")
                edges.append(add(*anchor, ("pairs", str(i)), "join.pair"))
        if kind in {"map", "lookup_join"}:
            for i, field in enumerate(node["fields"]):
                shape(field, "name expression")
                edges.append(expression(field["expression"], anchor, ("fields", str(i), "expression"), 2 if kind == "lookup_join" else 1, None))
        if kind == "group":
            for i, key in enumerate(node["keys"]):
                shape(key, "name source_field")
                edges.append(add(*anchor, ("keys", str(i)), "group.key"))
            for i, agg in enumerate(node["aggregates"]):
                assert agg["kind"] in {"count", "sum"}
                shape(agg, "kind name" + (" field" if agg["kind"] == "sum" else ""))
                edges.append(add(*anchor, ("aggregates", str(i)), "group." + agg["kind"]))
        done[ident] = add(*anchor, (), "node." + kind, edges)
        if kind == "input":
            assert node["port"] not in inputs
            inputs[node["port"]] = done[ident]
        for parent in parents[ident]:
            depths[parent] = max(depths[parent], depth + 1)
            deps[parent].remove(ident)
            if not deps[parent]: heapq.heappush(ready, (depths[parent], parent))
    assert len(done) == len(nodes), "cyclic graph"
    for output in ir["outputs"]:
        shape(output, "name node")
        assert output["name"] not in outputs
        outputs[output["name"]] = add("output", output["name"], (), "output.bind", [done[output["node"]]])
    contracts = []
    for entry in ir["contracts"]:
        c, anchor = entry["definition"], ("contract", entry["id"])
        if c["kind"] == "formula":
            shape(c, "kind role expression")
            assert c["role"] in {"assume", "guarantee"}
            edges = [expression(c["expression"], anchor, ("expression",), 0, c["role"])]
            rule = "contract." + c["role"]
        else:
            assert c["kind"] == "noninterference"
            shape(c, "kind inputs outputs")
            edges = [inputs[n] for n in c["inputs"]] + [outputs[n] for n in c["outputs"]]
            rule = "contract.noninterference"
        contracts.append(add(*anchor, (), rule, edges))
    doc_id = obligations["ir_document_digest"]
    empty = add("document", doc_id, ("effects",), "effects.empty")
    root = add("document", doc_id, (), "program.empty", [empty, *[done[n] for n in sorted(done)], *outputs.values(), *contracts])
    return {"format": "axiom-core-effect-derivation", "format_version": "0.1", "rule_profile": "axiom-core-empty-effects-v0.1",
            "binding": {"generator": generator, "ir_artifact": obligations["ir_artifact"], "ir_document_digest": doc_id,
                        "ir_version": "0.2", "obligation": targets[0]["id"], "obligation_set_artifact": digest(canonical(obligations).encode()),
                        "semantics": obligations["semantics"]["sha256"]}, "root": str(root), "steps": steps}


def usage(record):
    return [len(record["steps"]), sum(len(s["premises"]) for s in record["steps"]),
            sum(len(canonical(s["path"]).encode()) for s in record["steps"]), len(canonical(record).encode())]


def check(ir, obligations, data, generator=GENERATOR):
    # 候选原始字节必须等于独立重建；重复成员、空白、未知版本亦不例外。
    expected = derive(ir, obligations, generator)
    assert data == canonical(expected).encode(), "effect derivation mismatch"
    return expected
