"""P3-B 具体语义：复用已冻结的表解释器；不使用生产 ok 或 SMT AST。"""
from p3_query_semantics import FAULT, Interpreter


def results(document, world, obligations):
    interpreter = Interpreter(document, world)
    if not interpreter.wf():
        return [False] * len(obligations)
    pre = all(interpreter.expr(c["definition"]["expression"], [], c["id"], ("expression",)) is True
              for c in document["contracts"] if c["definition"].get("role") == "assume")
    # 老解释器继续负责原两类目标；新目标只观察具体节点的值 / FAULT。
    old = [o for o in obligations if o["definition"]["kind"] != "totality"]
    old_results = iter(Interpreter(document, world).results(old))
    return [pre and interpreter.node(o["definition"]["subject"]["id"]) is FAULT
            if o["definition"]["kind"] == "totality" else next(old_results) for o in obligations]
