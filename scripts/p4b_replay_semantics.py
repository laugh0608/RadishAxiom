"""P4-B 独立有限观察：复用 P3 的 Python 值语义，增加动态位置与目标归因。"""
import copy
import json
from p3_query_semantics import FAULT, Interpreter

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def typed(interpreter, ty, value):
    kind = ty["kind"]
    if kind in {"bool", "text"}:
        return {"kind": kind, "value": value}
    if kind == "int":
        return {"kind": kind, "value": str(value)}
    if kind == "fixed":
        return {"kind": kind, "coefficient": str(value), "scale": ty["scale"]}
    if kind == "enum":
        members = interpreter.enums[ty["enum_type"]]
        return {"kind": kind, "enum_type": ty["enum_type"], "member": members[value] if 0 <= value < len(members) else "invalid-enum-member"}
    if kind == "option":
        return {"kind": "none"} if value is None else {"kind": "some", "value": typed(interpreter, ty["inner"], value["some"])}
    return {"kind": "record", "record_type": ty["record_type"], "fields": [
        {"name": f["name"], "value": typed(interpreter, f["type"], value[f["name"]])}
        for f in interpreter.records[ty["record_type"]]["fields"]]}


def world_bytes(document, world):
    interpreter = Interpreter(document, world)
    entries = []
    for node in interpreter.nodes.values():
        if node["kind"] != "input":
            continue
        ty = interpreter.tables[node["table_type"]]
        rows = [s["row"] for s in world[node["port"]] if s["active"]]
        rows.sort(key=lambda r: tuple(r[k] for k in ty["primary_key"]))
        entries.append({"interface": node["port"], "table_type": node["table_type"], "rows": [
            typed(interpreter, {"kind": "record", "record_type": ty["record_type"]}, row) for row in rows]})
    return canonical(sorted(entries, key=lambda e: e["interface"]))



class Trace(Interpreter):
    def __init__(self, document, world):
        super().__init__(document, world)
        self.context, self.faults, self.ranges, self.instances = [], [], {}, {}
        self.causes, self.prepared, self.selected = {}, {}, {}
        self.depths = {}
        pending = set(self.nodes)
        while pending:
            ready = sorted(n for n in pending if self.nodes[n]["kind"] == "input" or self.nodes[n]["source"] in self.depths)
            assert ready
            for n in ready:
                self.depths[n] = 0 if self.nodes[n]["kind"] == "input" else self.depths[self.nodes[n]["source"]] + 1
                pending.remove(n)
        self.order = sorted(self.nodes, key=lambda n: (self.depths[n], n))

    def key(self, node, row):
        table = self.tables[self.nodes[node]["table_type"]]
        types = {f["name"]: f["type"] for f in self.records[table["record_type"]]["fields"]}
        return [typed(self, types[k], row[k]) for k in table["primary_key"]]

    def location(self, anchor, path):
        return {"anchor": anchor, "path": list(path), "context": copy.deepcopy(self.context)}

    def expr(self, e, env, anchor, path):
        op = e["op"]
        if op in {"int_add", "int_sub", "fixed_add", "fixed_sub"}:
            key = (anchor, path)
            self.instances[key] = self.instances.get(key, 0) + 1
            if op.endswith("add"):
                a, b = [self.expr(v, env, anchor, (*path, "values", str(i))) for i, v in enumerate(e["values"])]
            else:
                a, b = [self.expr(e[k], env, anchor, (*path, k)) for k in ["left", "right"]]
            if a is FAULT or b is FAULT:
                return FAULT
            n = a + b if op.endswith("add") else a - b
            ty = e["result_type"]
            if not int(ty["lower"]) <= n <= int(ty["upper"]):
                location = self.location(anchor, path)
                self.faults.append(location)
                self.ranges.setdefault(key, {"kind": "numeric-range", "location": location,
                    "operands": [typed(self, ty, a), typed(self, ty, b)],
                    "mathematical_value": typed(self, ty, n), "result_type": ty})
                return FAULT
            return n
        if op == "forall_rows":
            node = self.interfaces[(e["table"]["kind"], e["table"]["name"])]
            table = self.node(node)
            if table is FAULT:
                return FAULT
            values = []
            for row in table:
                self.context.append({"node": node, "key": self.key(node, row)})
                values.append(self.expr(e["body"], [row, *env], anchor, (*path, "body")))
                self.context.pop()
            return FAULT if any(v is FAULT for v in values) else all(values)
        return super().expr(e, env, anchor, path)

    def node(self, ident):
        if ident in self.computed:
            return self.computed[ident]
        node = self.nodes[ident]
        if node["kind"] == "input":
            rows = [s["row"] for s in self.world[node["port"]] if s["active"]]
        else:
            source = self.node(node["source"])
            if source is FAULT:
                self.causes[ident] = {"kind": "dependency", "node": ident, "source": node["source"], "cause": self.causes[node["source"]]}
                self.computed[ident] = FAULT
                return FAULT
            rows, chosen, fault_at = [], [], len(self.faults)
            for row in source:
                self.context.append({"node": node["source"], "key": self.key(node["source"], row)})
                if node["kind"] == "filter":
                    keep = self.expr(node["predicate"], [row], ident, ("predicate",))
                    if keep is True:
                        rows.append(row)
                        chosen.append(row)
                else:
                    values = {f["name"]: self.expr(f["expression"], [row], ident, ("fields", str(i), "expression")) for i, f in enumerate(node["fields"])}
                    rows.append(values)
                    chosen.append(row)
                self.context.pop()
            if len(self.faults) > fault_at:
                self.causes[ident] = {"kind": "range", "location": self.faults[fault_at]}
                self.computed[ident] = FAULT
                return FAULT
            self.prepared[ident], self.selected[ident] = rows, chosen
        table = self.tables[node["table_type"]]
        rows.sort(key=lambda r: tuple(r[k] for k in table["primary_key"]))
        if len(rows) > int(table["capacity"]):
            self.causes[ident] = {"kind": "capacity", "node": ident, "actual_rows": str(len(rows)), "declared_capacity": table["capacity"]}
            self.computed[ident] = FAULT
        else:
            self.computed[ident] = rows
        return self.computed[ident]


def invalid_value(i, ty, value, path=()):
    kind = ty["kind"]
    if kind in {"int", "fixed"} and not int(ty["lower"]) <= value <= int(ty["upper"]):
        return list(path), "range"
    if kind == "enum" and not 0 <= value < len(i.enums[ty["enum_type"]]):
        return list(path), "enum-member"
    if kind == "option" and value is not None:
        return invalid_value(i, ty["inner"], value["some"], path)
    if kind == "record":
        for f in i.records[ty["record_type"]]["fields"]:
            bad = invalid_value(i, f["type"], value[f["name"]], (*path, f["name"]))
            if bad:
                return bad
    return None


def observe(document, world, target):
    i = Trace(document, world)
    for node in sorted((n for n in i.nodes.values() if n["kind"] == "input"), key=lambda n: n["port"]):
        rows = [s["row"] for s in world[node["port"]] if s["active"]]
        table = i.tables[node["table_type"]]
        rows.sort(key=lambda r: tuple(r[k] for k in table["primary_key"]))
        bad_rows, path, reason = [], [], None
        for index, row in enumerate(rows):
            bad = invalid_value(i, {"kind": "record", "record_type": table["record_type"]}, row)
            if bad:
                path, reason = bad
                bad_rows = [str(index)]
                break
        if reason is None and len(rows) > int(table["capacity"]):
            reason = "capacity"
        if reason is None:
            keys = [tuple(r[k] for k in table["primary_key"]) for r in rows]
            for n in range(1, len(keys)):
                if keys[n - 1] == keys[n]:
                    bad_rows, reason = [str(n - 1), str(n)], "duplicate-key"
                    break
        if reason:
            return {"kind": "input-rejected", "interface": node["port"], "rows": bad_rows, "path": path, "reason": reason}
    first = None
    for c in document["contracts"]:
        if c["definition"].get("role") == "assume":
            start = len(i.faults)
            value = i.expr(c["definition"]["expression"], [], c["id"], ("expression",))
            if value is not True and first is None:
                first = {"kind": "pre-rejected", "contract": c["id"], "reason": "fault" if value is FAULT else "false",
                         "location": i.faults[start] if value is FAULT else i.location(c["id"], ("expression",))}
    if first:
        return first
    for node in i.order:
        i.node(node)
    kind, subject = target["kind"], target["subject"]["id"]
    witness = None
    if kind in {"numeric-range", "contract-guarantee"}:
        contract = next((c for c in document["contracts"] if c["id"] == subject), None)
        program_ok = all(v is not FAULT for v in i.computed.values())
        start = len(i.faults)
        value = i.expr(contract["definition"]["expression"], [], subject, ("expression",)) if contract and contract["definition"].get("role") == "guarantee" and program_ok else None
        if kind == "numeric-range":
            key = (subject, tuple(target["subject"]["path"]))
            witness = i.ranges.get(key)
            detail = {"kind": kind, "instances": str(i.instances.get(key, 0))}
        else:
            detail = {"kind": kind, "contract": subject, "program_ok": True, "formula_ok": True, "value": True}
            if not program_ok:
                witness = {"kind": kind, "contract": subject, "reason": "program-fault", "cause": next(i.causes[n] for n in i.order if n in i.causes)}
            elif value is not True:
                witness = {"kind": kind, "contract": subject, "reason": "formula-fault" if value is FAULT else "false",
                           "cause": i.faults[start] if value is FAULT else i.location(subject, ("expression",))}
    elif kind == "totality":
        detail = {"kind": kind, "node": subject, "ok": True}
        if i.computed[subject] is FAULT:
            witness = {"kind": kind, "node": subject, "cause": i.causes[subject]}
    else:
        detail = {"kind": kind, "node": subject, "ready": subject in i.prepared}
        if subject not in i.prepared:
            detail["cause"] = i.causes[subject]
        else:
            node = i.nodes[subject]
            table = i.tables[node["table_type"]]
            rows = i.prepared[subject]
            keys = [tuple(r[k] for k in table["primary_key"]) for r in rows]
            if kind == "key-cardinality":
                detail.update(unique=True, capacity=True)
                for n in range(1, len(keys)):
                    if keys[n - 1] == keys[n]:
                        witness = {"kind": kind, "node": subject, "reason": "duplicate-key", "rows": [str(n - 1), str(n)], "key": i.key(subject, rows[n])}
                        break
                if witness is None and len(rows) > int(table["capacity"]):
                    witness = {"kind": kind, "node": subject, "reason": "capacity", "actual_rows": str(len(rows)), "declared_capacity": table["capacity"]}
            else:
                detail.update(forward=True, backward=True)
                mapping = {f["name"]: f["expression"]["field"] for f in node.get("fields", []) if f["name"] in table["primary_key"]}
                expected = [tuple(r[mapping.get(k, k)] for k in table["primary_key"]) for r in i.selected[subject]]
                # Full legal map/filter inputs preserve these keys; local injected relations are tested separately.
                assert all(keys.count(k) == 1 for k in expected) and all(expected.count(k) == 1 for k in keys)
    return {"kind": "target-violated", "witness": witness} if witness else {"kind": "target-not-violated", "observation": detail}
