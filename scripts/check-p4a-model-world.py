#!/usr/bin/env python3
"""独立有限 P4-A 核对：由原 IR / 实际 query 重建布局与模型世界，不导入 Rust。"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def raw(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def parse(text):
    """固定测试字节上的独立 S-expression 栈；随后另核验受支持文法。"""
    tokens = re.findall(r";[^\r\n]*|[()]|[^\s();]+", text)
    roots, stack = [], []
    for token in tokens:
        if token.startswith(";"):
            continue
        if token == "(":
            stack.append([])
        elif token == ")":
            if not stack:
                raise ValueError("unmatched-close")
            value = stack.pop()
            (stack[-1] if stack else roots).append(value)
        else:
            (stack[-1] if stack else roots).append(token)
    if stack:
        raise ValueError("unclosed")
    return roots


def reconstruct(ir, query):
    records = {e["id"]: e["definition"] for e in ir["record_types"]}
    tables = {e["id"]: e["definition"] for e in ir["table_types"]}
    literals = {""}
    pending = [ir]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("op") == "literal_text":
                literals.add(item["value"])
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    free, derived = [], []
    for form in parse(query.decode()):
        if not isinstance(form, list):
            raise ValueError("query-form")
        if form[0] == "declare-const":
            free.append((form[1], form[2]))
        elif form[0] == "define-fun":
            assert form[2] == []
            derived.append({"name": form[1], "sort": form[3]})
    cursor, symbols, inputs = 0, [], []
    for literal in sorted(literals):
        name, sort = free[cursor]
        assert sort == "Text"
        symbols.append({"name": name, "sort": sort, "origin": {"kind": "text-literal", "value": literal}})
        cursor += 1
    for node in sorted((n for n in ir["nodes"] if n["definition"]["kind"] == "input"), key=lambda n: n["id"]):
        definition = node["definition"]
        table = tables[definition["table_type"]]
        components, todo = [], [({"kind": "record", "record_type": table["record_type"]}, [])]
        while todo:
            ty, path = todo.pop()
            if ty["kind"] == "record":
                for field in reversed(sorted(records[ty["record_type"]]["fields"], key=lambda f: f["name"])):
                    todo.append((field["type"], path + [field["name"]]))
                continue
            tag = ty["kind"] == "option"
            sort = "Bool" if ty["kind"] in ("bool", "option") else "Text" if ty["kind"] == "text" else "Int"
            components.append({"index": str(len(components)), "path": path, "role": "option-tag" if tag else "value", "sort": sort, "value_type": ty})
            if tag:
                todo.append((ty["inner"], path))
        port, capacity = definition["port"], int(table["capacity"])
        inputs.append({"interface": port, "node": node["id"], "table_type": definition["table_type"], "record_type": table["record_type"], "capacity": table["capacity"], "primary_key": table["primary_key"], "components": components})
        for slot in range(capacity):
            name, sort = free[cursor]
            assert sort == "Bool"
            symbols.append({"name": name, "sort": sort, "origin": {"kind": "input", "interface": port, "slot": str(slot), "component": "active"}})
            cursor += 1
            for component in components:
                name, sort = free[cursor]
                assert sort == component["sort"]
                symbols.append({"name": name, "sort": sort, "origin": {"kind": "input", "interface": port, "slot": str(slot), "component": component["index"]}})
                cursor += 1
    assert cursor == len(free)
    return sorted(symbols, key=lambda s: s["name"]), sorted(derived, key=lambda s: s["name"]), sorted(inputs, key=lambda i: i["interface"])


def decode(ir, symbols, derived, stdout):
    roots = parse(stdout.decode())
    if len(roots) != 2 or roots[0] != "sat" or not isinstance(roots[1], list):
        raise ValueError("not-complete-sat-frame")
    sorts = {s["name"]: s["sort"] for s in symbols + derived}
    definitions = {}
    for d in roots[1]:
        if not isinstance(d, list) or len(d) != 5 or d[0] != "define-fun" or d[2] != []:
            raise ValueError("definition")
        _, name, _, sort, value = d
        if name in definitions or sorts.get(name) != sort:
            raise ValueError("name-or-sort")
        definitions[name] = value
    if any(s["name"] not in definitions for s in symbols):
        raise ValueError("missing-free")
    resolved = {}
    for name in definitions:
        chain, visiting, current = [], set(), name
        while current not in resolved:
            if current in visiting or current not in definitions:
                raise ValueError("alias-cycle-or-missing")
            visiting.add(current)
            chain.append(current)
            value, sort = definitions[current], sorts[current]
            if isinstance(value, str) and value in sorts:
                if sorts[value] != sort:
                    raise ValueError("alias-sort")
                current = value
                continue
            if sort == "Bool" and value in ("true", "false"):
                result = value == "true"
            elif sort == "Int" and isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value):
                result = int(value)
            elif sort == "Int" and isinstance(value, list) and len(value) == 2 and value[0] == "-" and re.fullmatch(r"[1-9][0-9]*", value[1]):
                result = -int(value[1])
            elif sort == "Text":
                if isinstance(value, list) and len(value) == 3 and value[0] == "as" and value[2] == "Text":
                    value = value[1]
                if not isinstance(value, str) or not re.fullmatch(r"@Text_(0|[1-9][0-9]*)", value):
                    raise ValueError("text-atom")
                result = value
            else:
                raise ValueError("constant")
            resolved[current] = result
        for item in chain:
            resolved[item] = resolved[current]
    atoms, literals = {}, set()
    for s in symbols:
        if s["sort"] != "Text":
            continue
        atom = resolved[s["name"]]
        group = atoms.setdefault(atom, {"names": [], "literal": None})
        group["names"].append(s["name"])
        if s["origin"]["kind"] == "text-literal":
            literal = s["origin"]["value"]
            if group["literal"] is not None and group["literal"] != literal:
                raise ValueError("literal-conflict")
            group["literal"] = literal
            literals.add(literal)
    fresh = sorted((g for g in atoms.values() if g["literal"] is None), key=lambda g: min(g["names"]))
    for index, group in enumerate(fresh):
        nonce = 0
        while f"@axiom-text:{index}:{nonce}" in literals:
            nonce += 1
        group["text"] = f"@axiom-text:{index}:{nonce}"
    for group in atoms.values():
        if group["literal"] is not None:
            group["text"] = group["literal"]
    records = {e["id"]: e["definition"] for e in ir["record_types"]}
    enums = {e["id"]: e["definition"]["members"] for e in ir["enum_types"]}
    tables = {e["id"]: e["definition"] for e in ir["table_types"]}
    input_symbols = {(s["origin"]["interface"], int(s["origin"]["slot"]), s["origin"]["component"]): s["name"] for s in symbols if s["origin"]["kind"] == "input"}
    used = set()

    def value(ty, port, slot, position):
        kind = ty["kind"]
        if kind == "record":
            fields = []
            for f in sorted(records[ty["record_type"]]["fields"], key=lambda f: f["name"]):
                result, position = value(f["type"], port, slot, position)
                fields.append({"name": f["name"], "value": result})
            return {"kind": "record", "record_type": ty["record_type"], "fields": fields}, position
        name = input_symbols[port, slot, str(position)]
        actual = resolved[name]
        position += 1
        if kind == "option":
            if actual:
                result, position = value(ty["inner"], port, slot, position)
                return {"kind": "some", "value": result}, position
            # 只计算被遮蔽的宽度，不解释其值。
            todo = [ty["inner"]]
            while todo:
                inner = todo.pop()
                if inner["kind"] == "record":
                    todo.extend(f["type"] for f in records[inner["record_type"]]["fields"])
                else:
                    position += 1
                    if inner["kind"] == "option":
                        todo.append(inner["inner"])
            return {"kind": "none"}, position
        if kind in ("int", "fixed"):
            if not int(ty["lower"]) <= actual <= int(ty["upper"]):
                raise ValueError("numeric-range")
            return ({"kind": "int", "value": str(actual)} if kind == "int" else {"kind": "fixed", "coefficient": str(actual), "scale": ty["scale"]}), position
        if kind == "enum":
            if not 0 <= actual < len(enums[ty["enum_type"]]):
                raise ValueError("enum-index")
            return {"kind": "enum", "enum_type": ty["enum_type"], "member": enums[ty["enum_type"]][actual]}, position
        if kind == "text":
            used.add(name)
            actual = atoms[actual]["text"]
        return {"kind": kind, "value": actual}, position

    def key(row, primary):
        fields = {f["name"]: f["value"] for f in row["fields"]}
        result = []
        for name in primary:
            v = fields[name]
            if v["kind"] == "int":
                result.append(int(v["value"]))
            elif v["kind"] == "fixed":
                result.append(int(v["coefficient"]))
            elif v["kind"] == "enum":
                result.append(enums[v["enum_type"]].index(v["member"]))
            else:
                result.append(v["value"])
        return tuple(result)

    world = []
    for n in sorted((n["definition"] for n in ir["nodes"] if n["definition"]["kind"] == "input"), key=lambda n: n["port"]):
        table, port = tables[n["table_type"]], n["port"]
        rows = [value({"kind": "record", "record_type": table["record_type"]}, port, slot, 0)[0] for slot in range(int(table["capacity"])) if resolved[input_symbols[port, slot, "active"]]]
        rows.sort(key=lambda row: key(row, table["primary_key"]))
        if len({key(row, table["primary_key"]) for row in rows}) != len(rows):
            raise ValueError("duplicate-key")
        world.append({"interface": port, "table_type": n["table_type"], "rows": rows})
    classes = [{"symbols": sorted(set(g["names"]) & used), "text": g["text"]} for g in fresh if set(g["names"]) & used]
    return world, classes


def check(directory):
    ir_bytes, query = (directory / "ir.jcs").read_bytes(), (directory / "query.smt2").read_bytes()
    ir = json.loads(ir_bytes)
    symbols, derived, inputs = reconstruct(ir, query)
    expected_symbols = {"format": "axiom-p4-query-symbols", "version": "0.1", "query_raw_digest": raw(query), "symbols": symbols, "derived": derived}
    expected_layout = {"format": "axiom-p4-input-layout", "version": "0.1", "ir_artifact": raw(ir_bytes), "query_raw_digest": raw(query), "inputs": inputs}
    assert (directory / "symbols.jcs").read_bytes() == canonical(expected_symbols)
    assert (directory / "layout.jcs").read_bytes() == canonical(expected_layout)
    request_bytes = (directory / "request.jcs").read_bytes()
    request = json.loads(request_bytes)
    assert request_bytes == canonical(request)
    assert request["symbols"] == raw(canonical(expected_symbols))
    assert request["layout"] == raw(canonical(expected_layout))
    assert request["binding"]["ir_artifact"] == raw(ir_bytes)
    assert request["binding"]["obligation_set_artifact"] == raw((directory / "p2.jcs").read_bytes())
    assert request["query"]["raw_digest"] == raw(query)
    assert request["query"]["byte_length"] == str(len(query))
    stdout = (directory / "stdout.smt2").read_bytes()
    world, classes = decode(ir, symbols, derived, stdout)
    actual_bytes = (directory / "candidate.jcs").read_bytes()
    actual = json.loads(actual_bytes)
    observation = (directory / "response.jcs").read_bytes()
    expected_observation = {"format": "axiom-p4-solver-response-observation", "version": "0.1", "request": raw(request_bytes), "stdout": {"raw_digest": raw(stdout), "byte_length": str(len(stdout)), "complete": True}, "stderr": {"raw_digest": raw(b""), "byte_length": "0", "complete": True}, "exit": {"kind": "exited", "code": "0"}, "outer_termination": "none"}
    assert observation == canonical(expected_observation)
    assert actual == {"format": "axiom-p4-model-world-candidate", "version": "0.1", "request": raw(request_bytes), "response": raw(observation), "world": world, "text_classes": classes}
    assert actual_bytes == canonical(actual)
    if (directory / "expected-world.jcs").exists():
        assert canonical(world) == (directory / "expected-world.jcs").read_bytes(), "hand-world"
    if (directory / "hand-cases.json").exists():
        hand = json.loads((directory / "hand-cases.json").read_bytes())
        # 从手写列赋值推导类编号，不读取模型或生产 world 来生成手算期望。
        groups = {}
        for sym in symbols:
            if sym["sort"] != "Text":
                continue
            origin = sym["origin"]
            atom = hand["literal_atoms"][origin["value"]] if origin["kind"] == "text-literal" else hand["slots"][origin["interface"]][int(origin["slot"])]["values"][int(origin["component"])]
            groups.setdefault(atom, []).append(sym["name"])
        known = set(hand["literal_atoms"].values())
        replacements = {}
        for i, atom in enumerate(sorted((a for a in groups if a not in known), key=lambda a: min(groups[a]))):
            nonce = 0
            while f"@axiom-text:{i}:{nonce}" in hand["literal_atoms"]:
                nonce += 1
            replacements[atom] = f"@axiom-text:{i}:{nonce}"

        def expand(v):
            if isinstance(v, dict):
                if "text-class" in v:
                    return replacements[v["text-class"]]
                return {k: expand(x) for k, x in v.items()}
            if isinstance(v, list):
                return [expand(x) for x in v]
            return v

        def plain(v):
            kind = v["kind"]
            if kind == "record":
                return {f["name"]: plain(f["value"]) for f in v["fields"]}
            if kind == "some":
                return {"some": plain(v["value"])}
            if kind == "none":
                return None
            return v["coefficient"] if kind == "fixed" else v["member"] if kind == "enum" else v["value"]

        actual_plain = {t["interface"]: [plain(r) for r in t["rows"]] for t in world}
        assert actual_plain == expand(hand["expected_rows"]), "hand-composite-values-and-key-order"
    # 独立期望能区分规范语法内的候选篡改，不只复算候选摘要。
    tampered = json.loads(actual_bytes)
    tampered["world"] = []
    assert tampered != actual
    print("independent P4-A layout / symbols / model-world passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    check(parser.parse_args().directory)
