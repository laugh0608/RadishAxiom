"""独立小域具体解释：Python 数学整数与实际表，绝不生成 SMT 或读取 Rust。"""

FAULT = object()


class Interpreter:
    def __init__(self, document, world):
        self.ir = document
        self.world = world
        self.records = {e["id"]: e["definition"] for e in document["record_types"]}
        self.tables = {e["id"]: e["definition"] for e in document["table_types"]}
        self.enums = {e["id"]: e["definition"]["members"] for e in document["enum_types"]}
        self.nodes = {e["id"]: e["definition"] for e in document["nodes"]}
        self.interfaces = {("input", n["port"]): ident for ident, n in self.nodes.items() if n["kind"] == "input"}
        self.interfaces.update({("output", e["name"]): e["node"] for e in document["outputs"]})
        self.computed = {}
        self.overflow = set()

    def value_wf(self, ty, value):
        kind = ty["kind"]
        if kind == "bool":
            return type(value) is bool
        if kind in {"int", "fixed"}:
            return type(value) is int and int(ty["lower"]) <= value <= int(ty["upper"])
        if kind == "text":
            return type(value) is str
        if kind == "enum":
            return type(value) is int and 0 <= value < len(self.enums[ty["enum_type"]])
        if kind == "option":
            return value is None or (set(value) == {"some"} and self.value_wf(ty["inner"], value["some"]))
        fields = self.records[ty["record_type"]]["fields"]
        return set(value) == {f["name"] for f in fields} and all(self.value_wf(f["type"], value[f["name"]]) for f in fields)

    def wf(self):
        for node in self.nodes.values():
            if node["kind"] != "input":
                continue
            ty = self.tables[node["table_type"]]
            slots = self.world[node["port"]]
            if len(slots) > int(ty["capacity"]):
                return False
            rows = [s["row"] for s in slots if s["active"]]
            if not all(self.value_wf({"kind": "record", "record_type": ty["record_type"]}, r) for r in rows):
                return False
            keys = [tuple(r[k] for k in ty["primary_key"]) for r in rows]
            if len(keys) != len(set(keys)):
                return False
        return True

    def node(self, ident):
        if ident in self.computed:
            return self.computed[ident]
        node = self.nodes[ident]
        if node["kind"] == "input":
            result = [s["row"] for s in self.world[node["port"]] if s["active"]]
        else:
            source = self.node(node["source"])
            if source is FAULT:
                result = FAULT
            elif node["kind"] == "filter":
                predicates = [self.expr(node["predicate"], [r], ident, ("predicate",)) for r in source]
                result = FAULT if any(p is FAULT for p in predicates) else [r for r, p in zip(source, predicates) if p]
            elif node["kind"] == "map":
                rows = [{f["name"]: self.expr(f["expression"], [r], ident, ("fields", str(i), "expression"))
                         for i, f in enumerate(node["fields"])} for r in source]
                result = FAULT if any(v is FAULT for r in rows for v in r.values()) else rows
            else:
                raise ValueError("independent interpreter unsupported node")
            if result is not FAULT and len(result) > int(self.tables[node["table_type"]]["capacity"]):
                result = FAULT
        self.computed[ident] = result
        return result

    def table(self, reference):
        ident = self.interfaces[(reference["kind"], reference["name"])]
        return self.node(ident), self.tables[self.nodes[ident]["table_type"]]

    def expr(self, e, env, anchor, path):
        op = e["op"]

        def child(key):
            return self.expr(e[key], env, anchor, (*path, key))

        if op == "literal_bool" or op == "literal_text":
            return e["value"]
        if op == "literal_int":
            return int(e["value"])
        if op == "literal_fixed":
            return int(e["coefficient"])
        if op == "literal_enum":
            return self.enums[e["enum_type"]].index(e["member"])
        if op == "bound":
            return env[int(e["index"])]
        if op == "field":
            value = child("record")
            return FAULT if value is FAULT else value[e["field"]]
        if op == "none":
            return None
        if op == "some":
            value = child("value")
            return FAULT if value is FAULT else {"some": value}
        if op == "record":
            result = {f["name"]: self.expr(f["expression"], env, anchor, (*path, "fields", str(i), "expression"))
                      for i, f in enumerate(e["fields"])}
            return FAULT if any(v is FAULT for v in result.values()) else result
        if op == "if":
            condition = child("condition")
            return FAULT if condition is FAULT else child("then" if condition else "else")
        if op == "match_option":
            value = child("subject")
            if value is FAULT:
                return FAULT
            if value is None:
                return child("none")
            return self.expr(e["some"], [value["some"], *env], anchor, (*path, "some"))
        if op == "not":
            value = child("value")
            return FAULT if value is FAULT else not value
        if op in {"and", "or"}:
            values = [self.expr(v, env, anchor, (*path, "values", str(i))) for i, v in enumerate(e["values"])]
            if any(v is FAULT for v in values):
                return FAULT
            return all(values) if op == "and" else any(values)
        if op in {"eq", "lt", "le", "gt", "ge"}:
            left, right = child("left"), child("right")
            if left is FAULT or right is FAULT:
                return FAULT
            if op == "eq":
                return left == right
            if op == "lt":
                return left < right
            if op == "le":
                return left <= right
            if op == "gt":
                return left > right
            return left >= right
        if op in {"int_add", "int_sub", "fixed_add", "fixed_sub"}:
            if op.endswith("_add"):
                left, right = [self.expr(v, env, anchor, (*path, "values", str(i))) for i, v in enumerate(e["values"])]
            else:
                left, right = child("left"), child("right")
            if left is FAULT or right is FAULT:
                return FAULT
            value = left + right if op.endswith("_add") else left - right
            ty = e["result_type"]
            if not int(ty["lower"]) <= value <= int(ty["upper"]):
                self.overflow.add((anchor, path))
                return FAULT
            return value
        if op == "forall_rows":
            table, _ = self.table(e["table"])
            if table is FAULT:
                return FAULT
            values = [self.expr(e["body"], [r, *env], anchor, (*path, "body")) for r in table]
            return FAULT if any(v is FAULT for v in values) else all(values)
        if op == "lookup":
            table, ty = self.table(e["table"])
            if table is FAULT:
                return FAULT
            keys = [self.expr(v, env, anchor, (*path, "keys", str(i))) for i, v in enumerate(e["keys"])]
            if any(v is FAULT for v in keys):
                return FAULT
            found = [r for r in table if [r[k] for k in ty["primary_key"]] == keys]
            assert len(found) <= 1, "lookup requires WF input and successful keyed transforms"
            return {"some": found[0]} if found else None
        raise ValueError("independent interpreter unsupported op " + op)

    def results(self, obligations):
        # 非法输入直接不在查询域；避免把重复键传给正常 lookup。
        if not self.wf():
            return [False] * len(obligations)
        assumes = [c for c in self.ir["contracts"] if c["definition"].get("role") == "assume"]
        pre_values = [self.expr(c["definition"]["expression"], [], c["id"], ("expression",)) for c in assumes]
        pre = all(v is True for v in pre_values)
        for ident in self.nodes:
            self.node(ident)
        program_ok = all(v is not FAULT for v in self.computed.values())
        guarantees = {}
        for c in self.ir["contracts"]:
            if c["definition"].get("role") == "guarantee":
                guarantees[c["id"]] = (program_ok and self.expr(c["definition"]["expression"], [], c["id"], ("expression",)) is True)
        result = []
        for obligation in obligations:
            definition = obligation["definition"]
            subject = definition["subject"]
            if definition["kind"] == "numeric-range":
                violation = (subject["id"], tuple(subject["path"])) in self.overflow
            else:
                violation = not guarantees[subject["id"]]
            result.append(pre and violation)
        return result

    def flatten(self, ty, value, inactive=False):
        kind = ty["kind"]
        if kind == "record":
            return [leaf for f in self.records[ty["record_type"]]["fields"]
                    for leaf in self.flatten(f["type"], value[f["name"]], inactive)]
        if kind == "option":
            payload = self.default(ty["inner"]) if value is None else value["some"]
            return [value is not None, *self.flatten(ty["inner"], payload, inactive or value is None)]
        return [value]

    def default(self, ty):
        if ty["kind"] == "record":
            return {f["name"]: self.default(f["type"]) for f in self.records[ty["record_type"]]["fields"]}
        return {"bool": False, "text": "", "int": 0, "fixed": 0, "enum": 0, "option": None}[ty["kind"]]

    def assignment(self, symbols):
        rows = {}
        for n in self.nodes.values():
            if n["kind"] != "input":
                continue
            ty = {"kind": "record", "record_type": self.tables[n["table_type"]]["record_type"]}
            rows[n["port"]] = (ty, self.world[n["port"]])
        result = {}
        for symbol in symbols:
            origin = symbol["origin"]
            if origin["kind"] == "text":
                value = origin["value"]
            else:
                ty, slots = rows[origin["interface"]]
                index = int(origin["slot"])
                slot = slots[index] if index < len(slots) else {"active": False, "row": self.default(ty)}
                if origin["component"] == "active":
                    value = slot["active"]
                else:
                    value = self.flatten(ty, slot["row"])[int(origin["component"])]
            result[symbol["name"]] = value
        return result
