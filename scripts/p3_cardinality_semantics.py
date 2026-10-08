"""P3-C 独立具体观察：实际来源成功后的容量前行；不读取生产 AST。"""
from p3_query_semantics import FAULT, Interpreter
from p3_totality_semantics import results as old_results


def prepared(interpreter, ident):
    node = interpreter.nodes[ident]
    source = interpreter.node(node["source"])
    if source is FAULT:
        return FAULT
    if node["kind"] == "filter":
        values = [interpreter.expr(node["predicate"], [r], ident, ("predicate",)) for r in source]
        return FAULT if any(v is FAULT for v in values) else [r for r, v in zip(source, values) if v]
    assert node["kind"] == "map"
    rows = [{f["name"]: interpreter.expr(f["expression"], [r], ident, ("fields", str(i), "expression"))
             for i, f in enumerate(node["fields"])} for r in source]
    return FAULT if any(v is FAULT for r in rows for v in r.values()) else rows


def results(document, world, obligations):
    interpreter = Interpreter(document, world)
    if not interpreter.wf():
        return [False] * len(obligations)
    pre = all(interpreter.expr(c["definition"]["expression"], [], c["id"], ("expression",)) is True
              for c in document["contracts"] if c["definition"].get("role") == "assume")
    old = iter(old_results(document, world, [o for o in obligations if o["definition"]["kind"] != "key-cardinality"]))
    result = []
    for obligation in obligations:
        d = obligation["definition"]
        if d["kind"] != "key-cardinality":
            result.append(next(old))
            continue
        ident = d["subject"]["id"]
        rows = prepared(interpreter, ident)
        table = interpreter.tables[interpreter.nodes[ident]["table_type"]]
        if not pre or rows is FAULT:
            result.append(False)
        else:
            keys = [tuple(r[k] for k in table["primary_key"]) for r in rows]
            result.append(len(keys) != len(set(keys)) or len(rows) > int(table["capacity"]))
    return result
