"""P3-D 独立具体关系：按 IR 求来源选择与完整候选，不复用 SMT 关系。"""
from p3_query_semantics import FAULT, Interpreter
from p3_cardinality_semantics import prepared, results as old_results


def coverage(expected_keys, output_keys):
    # 以实际行出现次数检查双射；不是仅集合相等或总行数相等。
    return (all(output_keys.count(k) == 1 for k in expected_keys)
            and all(expected_keys.count(k) == 1 for k in output_keys))


def observe(document, world, ident):
    interpreter = Interpreter(document, world)
    node = interpreter.nodes[ident]
    source = interpreter.node(node["source"])
    output = prepared(interpreter, ident)
    if output is FAULT:
        return {"ready": False, "expected_keys": None, "output": None}
    keys = interpreter.tables[node["table_type"]]["primary_key"]
    if node["kind"] == "filter":
        chosen = [r for r in source if interpreter.expr(node["predicate"], [r], ident, ("predicate",)) is True]
        expected = [[r[k] for k in keys] for r in chosen]
    else:
        # 读取规范直接字段投影；不从 prepared 的输出恢复期望键。
        mapping = {f["name"]: f["expression"]["field"] for f in node["fields"] if f["name"] in keys}
        expected = [[r[mapping[k]] for k in keys] for r in source]
    return {"ready": True, "expected_keys": expected, "output": output}


def results(document, world, obligations):
    interpreter = Interpreter(document, world)
    if not interpreter.wf():
        return [False] * len(obligations)
    pre = all(interpreter.expr(c["definition"]["expression"], [], c["id"], ("expression",)) is True
              for c in document["contracts"] if c["definition"].get("role") == "assume")
    old = iter(old_results(document, world, [o for o in obligations if o["definition"]["kind"] != "row-coverage"]))
    result = []
    for o in obligations:
        d = o["definition"]
        if d["kind"] != "row-coverage":
            result.append(next(old))
            continue
        obs = observe(document, world, d["subject"]["id"])
        keys = interpreter.tables[interpreter.nodes[d["subject"]["id"]]["table_type"]]["primary_key"]
        result.append(pre and obs["ready"] and not coverage(obs["expected_keys"], [[r[k] for k in keys] for r in obs["output"]]))
    return result
