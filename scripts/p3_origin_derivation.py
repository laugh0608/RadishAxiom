"""独立字段来源规则解释器：只信任完整 P1 类型前提，不调用生产标签 / 推导。"""
from dataclasses import dataclass, replace
import heapq
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
P2 = runpy.run_path(str(ROOT / "scripts/generate-p2-profile-review.py"))
canonical, digest, identity = P2["canonical"], P2["raw_digest"], P2["identity"]
GENERATOR = "sha256:" + "a" * 64


def make_set(ir):
    doc = identity("axiom-ir-v0.2:document", ir)
    return P2["obligation_set"]({"ir": ir, "ir_artifact": digest(canonical(ir).encode()),
        "ir_document_digest": doc, "definitions": P2["proposed_definitions"](ir, doc)})


def fields(v, names):
    assert isinstance(v, dict) and set(v) == set(names.split()), (v, names)


def join(*labels):
    return "sensitive" if "sensitive" in labels else "public"


def labels(inferred="public", declared="public", summary="public"):
    return dict(declared=declared, inferred=inferred, type_summary=summary,
                propagated=join(inferred, declared, summary))


def type_record(t):
    while t["kind"] == "option":
        t = t["inner"]
    return t.get("record_type") if t["kind"] == "record" else None


def order(definitions, predecessors):
    """独立 Kahn 队列；深度 / ID 确定序，不读取 P1 图遍历。"""
    remaining, reverse, depth = {}, {n: [] for n in definitions}, {n: 0 for n in definitions}
    for ident, item in definitions.items():
        deps = predecessors(item)
        remaining[ident] = len(deps)
        for dep in deps:
            reverse[dep].append(ident)
    queue = [(0, ident) for ident, n in remaining.items() if n == 0]
    heapq.heapify(queue)
    result = []
    while queue:
        d, ident = heapq.heappop(queue)
        result.append(ident)
        for parent in reverse[ident]:
            depth[parent] = max(depth[parent], d + 1)
            remaining[parent] -= 1
            if not remaining[parent]:
                heapq.heappush(queue, (depth[parent], parent))
    assert len(result) == len(definitions), "cyclic definitions"
    return result


@dataclass(frozen=True)
class AbstractValue:
    # shape: scalar; record=(record id, optional field summaries); option=(inner value or type, declared)
    kind: str
    data: object
    top: str
    content: str
    selection: object
    step: int


class Derivation:
    def __init__(self, ir):
        self.ir = ir
        self.records = {x["id"]: x["definition"] for x in ir["record_types"]}
        self.tables = {x["id"]: x["definition"] for x in ir["table_types"]}
        self.nodes = {x["id"]: x["definition"] for x in ir["nodes"]}
        self.steps, self.record_steps, self.field_steps, self.table_steps, self.done = [], {}, {}, {}, {}

    def add(self, anchor, path, item, rule, info=None, refs=(), gap=False):
        step = len(self.steps)
        assert all(isinstance(p, int) and p < step and p >= 0 for _, p in refs)
        self.steps.append(dict(anchor=dict(zip(("kind", "id"), anchor)), path=list(path), item=item,
            rule=rule, labels=info or labels(), premises=[dict(role=r, step=str(p)) for r, p in refs], gap=gap))
        return step

    def label(self, step):
        return self.steps[step]["labels"]["propagated"]

    def ts(self, ty):
        record = type_record(ty)
        return self.label(self.record_steps[record]) if record else "public"

    def field(self, record, name):
        return next(f for f in self.records[record]["fields"] if f["name"] == name)

    def shaped(self, ty, declared, step, top="public", selection=None):
        k = ty["kind"]
        kind, data = ("record", (ty["record_type"], None)) if k == "record" else (
            ("option-type", (ty["inner"], declared)) if k == "option" else ("scalar", None))
        return AbstractValue(kind, data, top, self.ts(ty) if declared else "public", selection, step)

    def declarations(self):
        for record in order(self.records, lambda r: [t for f in r["fields"] if (t := type_record(f["type"]))]):
            refs, summary = [], "public"
            for i, f in enumerate(self.records[record]["fields"]):
                refs_child = [("declaration", self.record_steps[t])] if (t := type_record(f["type"])) else []
                info = labels(declared=f["label"], summary=self.ts(f["type"]))
                step = self.add(("record-type", record), ["fields", str(i)], f["name"], "decl.field", info, refs_child)
                self.field_steps[record, f["name"]] = step
                refs.append(("declaration", step))
                summary = join(summary, info["propagated"])
            self.record_steps[record] = self.add(("record-type", record), [], "", "decl.record", labels(summary), refs)
        for table in sorted(self.tables):
            self.table_steps[table] = self.add(("table-type", table), [], "", "decl.table", refs=[("declaration", self.record_steps[self.tables[table]["record_type"]])])

    def expr(self, expr, anchor, path, scope):
        op = expr["op"]
        signatures = {
            "literal_bool": "value", "literal_text": "value", "literal_int": "type value",
            "literal_fixed": "type coefficient", "literal_enum": "enum_type member", "none": "type",
            "some": "value", "bound": "index", "field": "record field", "record": "record_type fields",
            "if": "condition then else result_type", "match_option": "subject none some result_type",
            "not": "value", "and": "values", "or": "values", "int_add": "values result_type", "fixed_add": "values result_type",
            **{op: "left right" for op in ["eq", "lt", "le", "gt", "ge"]},
            **{op: "left right result_type" for op in ["int_sub", "fixed_sub"]}}
        assert op in signatures, "unsupported row op"
        fields(expr, "op " + signatures[op])
        refs, info = [], labels()
        value = AbstractValue("scalar", None, "public", "public", None, -1)
        shaped = None

        def child(key, env=scope):
            return self.expr(expr[key], anchor, [*path, key], env)

        def use(v, role="value"):
            refs.extend([(role, v.step), ("evaluation", v.step)])

        if op == "bound":
            index = int(expr["index"])
            assert expr["index"] == str(index) and 0 <= index < len(scope)
            value = scope[-1-index]
            use(value)
            info = labels(self.label(value.step))
        elif op == "none":
            shaped = (expr["type"], False)
        elif op == "some":
            inner = child("value")
            use(inner)
            info = labels(self.label(inner.step))
            value = replace(value, kind="option-value", data=inner, content=info["propagated"])
        elif op == "field":
            source = child("record")
            assert source.kind == "record"
            record, known = source.data
            field = self.field(record, expr["field"])
            decl = self.field_steps[record, expr["field"]]
            origin = known[expr["field"]] if known is not None else decl
            dep = self.label(origin) if known is not None else field["label"]
            refs.append(("value", origin))
            if source.selection is not None:
                refs.append(("selection", source.selection))
            refs += [("evaluation", source.step), ("declaration", decl)]
            info = labels(join(source.top, dep), summary=self.ts(field["type"]))
            value = replace(value, top=info["inferred"])
            shaped = (field["type"], True)
        elif op == "record":
            record, known = expr["record_type"], {}
            summary = "public"
            for i, field in enumerate(expr["fields"]):
                fields(field, "name expression")
                p = [*path, "fields", str(i)]
                child_value = self.expr(field["expression"], anchor, [*p, "expression"], scope)
                name = field["name"]
                fi = labels(self.label(child_value.step), self.field(record, name)["label"])
                step = self.add(anchor, p, name, "expr.record-field", fi,
                    [("value", child_value.step), ("declaration", self.field_steps[record, name])],
                    fi["declared"] == "public" and fi["inferred"] == "sensitive")
                known[name] = step
                refs += [("value", step), ("evaluation", child_value.step)]
                summary = join(summary, fi["propagated"])
            refs.append(("declaration", self.record_steps[record]))
            info = labels(summary)
            value = replace(value, kind="record", data=(record, known), content=summary)
        elif op == "if":
            children = [child(k) for k in ["condition", "then", "else"]]
            for i, v in enumerate(children):
                use(v, "selection" if i == 0 else "value")
            info = labels(join(*(self.label(v.step) for v in children)))
            value = replace(value, top=info["inferred"])
            shaped = (expr["result_type"], False)
        elif op == "match_option":
            subject, none = child("subject"), child("none")
            use(subject, "selection")
            use(none)
            binding_refs = [("value", subject.step)]
            if subject.selection is not None:
                binding_refs.append(("selection", subject.selection))
            if subject.kind == "option-value":
                inner = subject.data
            else:
                assert subject.kind == "option-type"
                inner = self.shaped(*subject.data, step=-1)
            top = join(inner.top, subject.top)
            binder = self.add(anchor, [*path, "some"], "", "binding.some", labels(join(inner.content, top)), binding_refs)
            inner = replace(inner, top=top, selection=binder, step=binder)
            some = child("some", [*scope, inner])
            use(some)
            info = labels(join(*(self.label(v.step) for v in [subject, none, some])))
            value = replace(value, top=info["inferred"])
            shaped = (expr["result_type"], False)
        elif op in {"and", "or", "int_add", "fixed_add", "not", "eq", "lt", "le", "gt", "ge", "int_sub", "fixed_sub"}:
            if "values" in expr:
                children = [self.expr(v, anchor, [*path, "values", str(i)], scope) for i, v in enumerate(expr["values"])]
            else:
                children = [child(k) for k in (["value"] if op == "not" else ["left", "right"])]
            for v in children:
                use(v)
            info = labels(join(*(self.label(v.step) for v in children)))
            value = replace(value, top=info["inferred"])
        step = self.add(anchor, path, "", "expr." + op, info, refs)
        if shaped:
            return self.shaped(*shaped, step=step, top=value.top, selection=None if op == "none" else step)
        return replace(value, step=step, selection=value.selection if op in {"record", "some", "bound"} else step)

    def assign(self, anchor, path, record, name, rule, refs, gap_allowed=True):
        f = self.field(record, name)
        info = labels(join(*(self.label(p) for _, p in refs)), f["label"], self.ts(f["type"]))
        return self.add(anchor, path, name, rule, info, [*refs, ("declaration", self.field_steps[record, name])],
            gap_allowed and info["declared"] == "public" and info["inferred"] == "sensitive")

    def node(self, ident):
        n = self.nodes[ident]
        kind, table, anchor = n["kind"], n["table_type"], ("node", ident)
        signatures = {"input": "kind port table_type", "filter": "kind predicate source table_type",
            "map": "kind source table_type fields", "lookup_join": "kind left right table_type pairs fields",
            "group": "kind source table_type keys aggregates"}
        assert kind in signatures
        fields(n, signatures[kind])
        record = self.tables[table]["record_type"]
        field_map, evaluation = {}, []

        def control(rule, refs):
            return self.add(anchor, [], "", rule, labels(join(*(self.label(p) for _, p in refs))), refs)

        if kind == "input":
            for f in self.records[record]["fields"]:
                field_map[f["name"]] = self.add(anchor, ["port"], f["name"], "input.field", labels(declared=f["label"], summary=self.ts(f["type"])),
                    [("declaration", self.field_steps[record, f["name"]]), ("declaration", self.table_steps[table])])
            row = control("input.control", [])
            evaluation.append(("declaration", self.table_steps[table]))
        else:
            source = self.done[n["left"] if kind == "lookup_join" else n["source"]]
            right = self.done[n["right"]] if kind == "lookup_join" else None
            scope = ([right["value"]] if right else []) + [source["value"]]
            evaluation.append(("evaluation", source["evaluation"]))
            if kind == "filter":
                predicate = self.expr(n["predicate"], anchor, ["predicate"], scope)
                row = control("filter.control", [("selection", source["control"]), ("selection", predicate.step)])
                evaluation.append(("evaluation", predicate.step))
                for name, p in sorted(source["fields"].items()):
                    field_map[name] = self.assign(anchor, [], record, name, "filter.field", [("value", p)], False)
            elif kind in {"map", "lookup_join"}:
                match = None
                if right:
                    evaluation.append(("evaluation", right["evaluation"]))
                    refs = [("selection", source["control"]), ("selection", right["control"])]
                    for i, pair in enumerate(n["pairs"]):
                        fields(pair, "left right")
                        a, b = source["fields"][pair["left"]], right["fields"][pair["right"]]
                        p = self.add(anchor, ["pairs", str(i)], "", "join.pair", labels(join(self.label(a), self.label(b))), [("value", a), ("value", b)])
                        refs.append(("selection", p))
                    match = control("join.match", refs)
                    row = control("join.control", [("selection", match)])
                    evaluation.append(("evaluation", match))
                else:
                    row = control("map.control", [("selection", source["control"])])
                for i, field in enumerate(n["fields"]):
                    fields(field, "name expression")
                    path = ["fields", str(i)]
                    v = self.expr(field["expression"], anchor, [*path, "expression"], scope)
                    refs = [("value", v.step)] + ([("selection", match)] if match is not None else [])
                    p = self.assign(anchor, path, record, field["name"], "field.assign", refs)
                    field_map[field["name"]] = p
                    evaluation.append(("evaluation", p))
            else:
                refs = [("selection", source["control"])] + [("selection", source["fields"][k["source_field"]]) for k in n["keys"]]
                row = control("group.control", refs)
                for i, key in enumerate(n["keys"]):
                    fields(key, "name source_field")
                    p = self.assign(anchor, ["keys", str(i)], record, key["name"], "field.assign", [("value", source["fields"][key["source_field"]])])
                    field_map[key["name"]] = p
                    evaluation.append(("evaluation", p))
                for i, agg in enumerate(n["aggregates"]):
                    assert agg["kind"] in {"count", "sum"}
                    fields(agg, "kind name" + (" field" if agg["kind"] == "sum" else ""))
                    refs = [("selection", row)] + ([("value", source["fields"][agg["field"]])] if agg["kind"] == "sum" else [])
                    p = self.assign(anchor, ["aggregates", str(i)], record, agg["name"], "field.assign", refs)
                    field_map[agg["name"]] = p
                    evaluation.append(("evaluation", p))
        evaluation_step = self.add(anchor, [], "", ("join" if kind == "lookup_join" else kind) + ".evaluation", refs=evaluation)
        summary = join(*(self.label(v) for v in field_map.values()))
        record_step = self.add(anchor, [], "", "node.record", labels(summary), [("value", p) for _, p in sorted(field_map.items())] + [("evaluation", evaluation_step), ("declaration", self.table_steps[table])])
        self.done[ident] = dict(fields=field_map, control=row, evaluation=evaluation_step, record=record,
            value=AbstractValue("record", (record, field_map), "public", summary, None, record_step))

    def build(self):
        self.declarations()
        for ident in order(self.nodes, lambda n: [] if n["kind"] == "input" else ([n["left"], n["right"]] if n["kind"] == "lookup_join" else [n["source"]])):
            self.node(ident)

    def target(self, subject):
        interface, name = subject["interface"], subject["name"]
        output = next(o for o in self.ir["outputs"] if o["name"] == interface)
        n = self.done[output["node"]]
        p = n["fields"][name]
        root = self.add(("output", interface), [], name, "output.field", labels(self.label(p)), [("value", p), ("declaration", self.field_steps[n["record"], name])])
        roots = dict(control=n["control"], evaluation=n["evaluation"], value=root)
        live, stack = set(), list(roots.values())
        while stack:
            p = stack.pop()
            if p not in live:
                live.add(p)
                stack += [int(e["step"]) for e in self.steps[p]["premises"]]
        mapping = {old: new for new, old in enumerate(sorted(live))}
        steps = [dict(s, premises=[dict(e, step=str(mapping[int(e["step"])])) for e in s["premises"]]) for i, s in enumerate(self.steps) if i in live]
        usage = dict(steps=len(self.steps), premise_edges=sum(len(s["premises"]) for s in self.steps),
            path_bytes=sum(len(canonical(s["path"]).encode()) for s in self.steps))
        return dict(roots={r: str(mapping[p]) for r, p in roots.items()}, steps=steps,
            gaps=[str(i) for i, s in enumerate(steps) if s["gap"]], target=dict(interface=interface, name=name, node=output["node"], record_type=n["record"])), usage


def descriptor_units(ir, steps):
    # 规范化工作单元计数；与 Python 实际分配无关，不读取 Rust 返回的 usage。
    records = [r["definition"] for r in ir["record_types"]]
    nodes = [n["definition"] for n in ir["nodes"]]
    tables = {t["id"]: t["definition"] for t in ir["table_types"]}
    row_types = {r["id"]: r["definition"] for r in ir["record_types"]}
    units = 6 * len(records) + 2 * len(tables) + 5 * len(nodes) + 3 * steps
    units += sum(len(r["fields"]) + sum(type_record(f["type"]) is not None for f in r["fields"]) for r in records)
    expressions = []
    for n in nodes:
        units += 2 + len(row_types[tables[n["table_type"]]["record_type"]]["fields"])
        if n["kind"] != "input":
            units += 2 if n["kind"] == "lookup_join" else 1
        if n["kind"] == "filter":
            expressions.append(n["predicate"])
        elif n["kind"] in {"map", "lookup_join"}:
            expressions.extend(f["expression"] for f in n["fields"])
    while expressions:
        expr = expressions.pop()
        op = expr["op"]
        units += 1
        if op == "record":
            units += 1 + len(expr["fields"])
            expressions.extend(f["expression"] for f in expr["fields"])
        elif op == "some":
            units += 1
            expressions.append(expr["value"])
        elif op == "match_option":
            units += 2
            expressions.extend(expr[k] for k in ["subject", "none", "some"])
        elif op == "if":
            expressions.extend(expr[k] for k in ["condition", "then", "else"])
        elif op == "field":
            expressions.append(expr["record"])
        elif op == "not":
            expressions.append(expr["value"])
        elif op in {"and", "or", "int_add", "fixed_add"}:
            expressions.extend(expr["values"])
        elif op in {"eq", "lt", "le", "gt", "ge", "int_sub", "fixed_sub"}:
            expressions.extend([expr["left"], expr["right"]])
    return units


def derive(ir, obligations, target, generator=GENERATOR):
    assert ir["ir_version"] == "0.2" and obligations == make_set(ir)
    assert generator.startswith("sha256:") and len(generator) == 71 and all(c in "0123456789abcdef" for c in generator[7:])
    definition = next(o["definition"] for o in obligations["obligations"] if o["id"] == target)
    assert definition["kind"] == "field-origin"
    d = Derivation(ir)
    d.build()
    record, usage = d.target(definition["subject"])
    record.update(format="axiom-core-field-origin-derivation", format_version="0.1", rule_profile="axiom-core-field-origin-v0.1",
        binding=dict(generator=generator, ir_artifact=obligations["ir_artifact"], ir_document_digest=obligations["ir_document_digest"], ir_version="0.2",
            obligation=target, obligation_set_artifact=digest(canonical(obligations).encode()), semantics=obligations["semantics"]["sha256"]))
    usage["descriptors"] = descriptor_units(ir, usage["steps"])
    usage["output_bytes"] = len(canonical(record).encode())
    return record, usage


def check(ir, obligations, target, data, generator=GENERATOR):
    expected, _ = derive(ir, obligations, target, generator)
    assert data == canonical(expected).encode(), "field origin derivation mismatch"
    return expected
