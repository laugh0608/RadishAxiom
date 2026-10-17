#!/usr/bin/env python3
"""离线研究原型，不构成生产 EncodedQuery 或求解器请求。

只接纳 query/smt.rs 输出的类型化拓扑 DAG；改写仅使用 SMT Bool/Int 全函数
恒等式，不依赖 WF 假设。1 MiB 生产字节阈值与研究预算分别报告。
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


class PrototypeError(ValueError):
    """输入格式错误或研究预算明确拒绝；此时不产生 artifact。"""


@dataclass(frozen=True)
class Budgets:
    max_input_bytes: int = 64 * 1024 * 1024
    max_terms: int = 1_000_000
    max_edges: int = 5_000_000
    max_depth: int = 100_000
    max_output_bytes: int = 16 * 1024 * 1024
    max_integer_digits: int = 4096
    max_origins_bytes: int = 16 * 1024 * 1024
    max_syntax_depth: int = 16
    inline_bytes: int = 128
    inline_depth: int = 8
    inline_constant_bytes: int = 16
    min_free_name_digits: int = 1
    inline_multiuse_bytes: int = 32

    def validate(self) -> None:
        for name, value in asdict(self).items():
            minimum = 0 if name == "inline_multiuse_bytes" else 1
            if type(value) is not int or value < minimum:
                raise PrototypeError(f"invalid budget {name}: must be an integer >= {minimum}")
        if self.min_free_name_digits > self.max_output_bytes:
            raise PrototypeError("budget min_free_name_digits exceeds max_output_bytes")
        # 保留至少一位求和进位空间，避开 CPython 的十进制转换保护边界。
        if self.max_integer_digits > 4096:
            raise PrototypeError("max_integer_digits exceeds implementation ceiling 4096")


@dataclass(frozen=True)
class SymbolMapping:
    old: str
    new: str
    sort: str
    origin: Any = None


@dataclass(frozen=True)
class Artifact:
    smt_bytes: bytes
    free_symbols: tuple[SymbolMapping, ...]
    stats: dict[str, Any]

    def metadata(self) -> dict[str, Any]:
        return {
            "schema": "radishaxiom-query-compaction-research-v1",
            "artifact_kind": "offline-research-smt-not-production-request",
            "free_symbols": [asdict(symbol) for symbol in self.free_symbols],
            "stats": self.stats,
        }


@dataclass(frozen=True)
class Node:
    sort: str
    op: str
    args: tuple[int, ...] = ()
    value: str | int | bool | None = None


_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_NAT = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_SORTS = {"Bool", "Int", "Text"}
_RESERVED = _SORTS | {"true", "false", "and", "or", "not", "ite",
                      "_", "as", "let", "exists", "forall", "match", "par"}
_PRODUCTION_LIMIT = 1024 * 1024


def _commands(data: bytes, budget: Budgets):
    """非递归词法/语法分析；每次只保留一条顶层命令。"""
    if len(data) > budget.max_input_bytes:
        raise PrototypeError("budget max_input_bytes exceeded")
    try:
        source = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise PrototypeError("production SMT subset must be ASCII") from error
    stack: list[list[Any]] = []
    cursor = 0
    while cursor < len(source):
        char = source[cursor]
        if char in " \t\r\n":
            cursor += 1
            continue
        if char == "(":
            if len(stack) >= budget.max_syntax_depth:
                raise PrototypeError("budget max_syntax_depth exceeded")
            stack.append([])
            cursor += 1
        elif char == ")":
            if not stack:
                raise PrototypeError("unexpected closing parenthesis")
            expression = stack.pop()
            cursor += 1
            if stack:
                stack[-1].append(expression)
            else:
                yield expression
        else:
            end = cursor
            while end < len(source) and source[end] not in "() \t\r\n":
                end += 1
            token = source[cursor:end]
            if not stack:
                raise PrototypeError("top-level atom is not a command")
            # 生产子集不含字符串、转义名称、注释或属性，死代码亦须拒绝。
            if any(c in token for c in ';|"\\:'):
                raise PrototypeError("token outside production SMT subset")
            stack[-1].append(token)
            cursor = end
    if stack:
        raise PrototypeError("unclosed parenthesis")


class _Dag:
    def __init__(self, budget: Budgets):
        self.budget = budget
        self.nodes: list[Node] = []
        self.interned: dict[Node, int] = {}
        self.rewrites: Counter[str] = Counter()
        self.shared = 0

    def intern(self, node: Node) -> int:
        if node in self.interned:
            self.shared += 1
            return self.interned[node]
        if len(self.nodes) >= self.budget.max_terms:
            raise PrototypeError("budget max_terms exceeded by normalized DAG")
        term = len(self.nodes)
        self.nodes.append(node)
        self.interned[node] = term
        return term

    def constant(self, sort: str, value: bool | int) -> int:
        if sort == "Int" and len(str(abs(value))) > self.budget.max_integer_digits:
            raise PrototypeError("budget max_integer_digits exceeded by rewrite")
        return self.intern(Node(sort, "constant", value=value))

    def rewrite(self, rule: str, result: int) -> int:
        self.rewrites[rule] += 1
        return result

    def app(self, sort: str, op: str, args: tuple[int, ...]) -> int:
        nodes = [self.nodes[arg] for arg in args]
        if op == "not":
            a = nodes[0]
            if a.op == "constant":
                return self.rewrite("not-constant", self.constant("Bool", not a.value))
            if a.op == "not":
                return self.rewrite("not-not", a.args[0])
        elif op in {"and", "or"}:
            identity = op == "and"
            if any(a.op == "constant" and a.value != identity for a in nodes):
                return self.rewrite(f"{op}-absorbing", self.constant("Bool", not identity))
            filtered = tuple(dict.fromkeys(
                arg for arg, a in zip(args, nodes)
                if not (a.op == "constant" and a.value == identity)
            ))
            if filtered != args:
                self.rewrites[f"{op}-identity-dedup"] += 1
            args = filtered
            if not args:
                return self.constant("Bool", identity)
            if len(args) == 1:
                return args[0]
        elif op == "=":
            if args[0] == args[1]:
                return self.rewrite("eq-self", self.constant("Bool", True))
            if all(a.op == "constant" for a in nodes):
                return self.rewrite("eq-constants", self.constant("Bool", nodes[0].value == nodes[1].value))
            args = tuple(sorted(args))
        elif op in {"+", "-"}:
            a, b = nodes
            if all(n.op == "constant" for n in nodes):
                value = a.value + b.value if op == "+" else a.value - b.value
                return self.rewrite("arithmetic-constants", self.constant("Int", value))
            if b.op == "constant" and b.value == 0:
                return self.rewrite("arithmetic-right-zero", args[0])
            if op == "+" and a.op == "constant" and a.value == 0:
                return self.rewrite("add-left-zero", args[1])
            if op == "-" and args[0] == args[1]:
                return self.rewrite("sub-self", self.constant("Int", 0))
        elif op in {"<", "<=", ">", ">="}:
            if args[0] == args[1]:
                return self.rewrite("comparison-self", self.constant("Bool", op in {"<=", ">="}))
            if all(n.op == "constant" for n in nodes):
                a, b = nodes[0].value, nodes[1].value
                result = {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
                return self.rewrite("comparison-constants", self.constant("Bool", result))
        elif op == "ite":
            condition, a, b = nodes
            if condition.op == "constant":
                return self.rewrite("ite-condition", args[1] if condition.value else args[2])
            if args[1] == args[2]:
                return self.rewrite("ite-same-branch", args[1])
            if sort == "Bool" and a.op == b.op == "constant":
                if a.value and not b.value:
                    return self.rewrite("ite-bool", args[0])
                if not a.value and b.value:
                    return self.rewrite("ite-bool-not", self.app("Bool", "not", (args[0],)))
        return self.intern(Node(sort, op, args))


def _application_sort(op: Any, sorts: list[str]) -> str:
    if not isinstance(op, str):
        raise PrototypeError("application operator must be an atom")
    if op == "not" and sorts == ["Bool"]:
        return "Bool"
    if op in {"and", "or"} and all(sort == "Bool" for sort in sorts):
        return "Bool"
    if op == "=" and len(sorts) == 2 and sorts[0] == sorts[1]:
        return "Bool"
    if op in {"<", "<=", ">", ">="} and sorts == ["Int", "Int"]:
        return "Bool"
    if op in {"+", "-"} and sorts == ["Int", "Int"]:
        return "Int"
    if op == "ite" and len(sorts) == 3 and sorts[0] == "Bool" and sorts[1] == sorts[2]:
        return sorts[1]
    raise PrototypeError(f"unsupported or ill-typed application: {op}")


def transform(data: bytes, budgets: Budgets | None = None,
              origins: dict[str, Any] | None = None) -> Artifact:
    """返回完整研究 artifact，拒绝时抛异常，不产生部分 SMT。

    origins 可携带按原自由名称索引的外部来源；全部声明均保留，包含不可达输入
    和未激活 Text 值。此 API 的调用者负责约束外部来源对象的大小。
    """
    budget = budgets or Budgets()
    budget.validate()
    if not isinstance(data, bytes):
        raise PrototypeError("input must be bytes")
    dag = _Dag(budget)
    names: dict[str, tuple[int, str, int]] = {}
    free: dict[str, str] = {}
    term_count = edge_count = depth = 0
    root = None
    phase = 0
    commands = iter(_commands(data, budget))
    for expected in (["set-logic", "QF_UFLIA"], ["declare-sort", "Text", "0"]):
        if next(commands, None) != expected:
            raise PrototypeError("missing exact production SMT preamble")
    for command in commands:
        if not command or not isinstance(command[0], str):
            raise PrototypeError("invalid command")
        kind = command[0]
        if kind in {"declare-const", "define-fun"} and phase == 0:
            expected_len = 3 if kind == "declare-const" else 5
            if len(command) != expected_len:
                raise PrototypeError("invalid declaration/definition shape")
            name = command[1]
            if not isinstance(name, str) or not _NAME.fullmatch(name) or name in _RESERVED:
                raise PrototypeError("invalid production symbol name")
            if name in names:
                raise PrototypeError(f"duplicate name: {name}")
            sort = command[2] if kind == "declare-const" else command[3]
            if not isinstance(sort, str) or sort not in _SORTS:
                raise PrototypeError("unsupported sort")
            term_count += 1
            if term_count > budget.max_terms:
                raise PrototypeError("budget max_terms exceeded")
            node_depth = 1
            if kind == "declare-const":
                term = dag.intern(Node(sort, "symbol", value=name))
                free[name] = sort
            else:
                if command[2] != []:
                    raise PrototypeError("define-fun parameters must be empty")
                body = command[4]
                if isinstance(body, str) and body in {"true", "false"}:
                    if sort != "Bool":
                        raise PrototypeError("Boolean constant sort mismatch")
                    term = dag.constant("Bool", body == "true")
                elif isinstance(body, str) and _NAT.fullmatch(body):
                    if sort != "Int":
                        raise PrototypeError("integer constant sort mismatch")
                    if len(body) > budget.max_integer_digits:
                        raise PrototypeError("budget max_integer_digits exceeded")
                    term = dag.constant("Int", int(body))
                elif (isinstance(body, list) and len(body) == 2 and body[0] == "-"
                      and isinstance(body[1], str) and _NAT.fullmatch(body[1])):
                    if sort != "Int":
                        raise PrototypeError("negative integer constant sort mismatch")
                    if len(body[1]) > budget.max_integer_digits:
                        raise PrototypeError("budget max_integer_digits exceeded")
                    term = dag.constant("Int", -int(body[1]))
                elif isinstance(body, list) and body:
                    references = body[1:]
                    if any(not isinstance(ref, str) or ref not in names for ref in references):
                        raise PrototypeError("unknown, forward or nested application reference")
                    edges = len(references)
                    edge_count += edges
                    if edge_count > budget.max_edges:
                        raise PrototypeError("budget max_edges exceeded")
                    node_depth = 1 + max((names[ref][2] for ref in references), default=0)
                    if node_depth > budget.max_depth:
                        raise PrototypeError("budget max_depth exceeded")
                    app_sort = _application_sort(body[0], [names[ref][1] for ref in references])
                    if sort != app_sort:
                        raise PrototypeError("application result sort mismatch")
                    term = dag.app(sort, body[0], tuple(names[ref][0] for ref in references))
                else:
                    raise PrototypeError("unsupported definition body")
            depth = max(depth, node_depth)
            if depth > budget.max_depth:
                raise PrototypeError("budget max_depth exceeded")
            names[name] = (term, sort, node_depth)
        elif kind == "assert" and phase == 0:
            if len(command) != 2 or not isinstance(command[1], str) or command[1] not in names:
                raise PrototypeError("assert must reference one earlier term")
            term, sort, _ = names[command[1]]
            if sort != "Bool":
                raise PrototypeError("assert must have Bool sort")
            root = term
            phase = 1
        elif command == ["check-sat"] and phase == 1:
            phase = 2
        else:
            raise PrototypeError("unexpected command/order; require one assert then check-sat")
    if phase != 2 or root is None:
        raise PrototypeError("missing assert/check-sat")
    if origins is not None and (not isinstance(origins, dict) or set(origins) != set(free)):
        raise PrototypeError("external origins must cover exactly every free declaration")

    reachable: set[int] = set()
    pending = [root]
    while pending:
        term = pending.pop()
        if term not in reachable:
            reachable.add(term)
            pending.extend(dag.nodes[term].args)
    uses: Counter[int] = Counter({root: 1})
    for term in reachable:
        uses.update(dag.nodes[term].args)
    width = max(budget.min_free_name_digits, len(str(max(0, len(free) - 1))))
    mapping = tuple(SymbolMapping(name, f"s{index:0{width}d}", free[name],
                                  None if origins is None else origins[name])
                    for index, name in enumerate(sorted(free)))
    renamed = {entry.old: entry.new for entry in mapping}
    output: list[str] = []
    output_size = 0

    def emit(line: str) -> None:
        nonlocal output_size
        output_size += len(line)
        if output_size > budget.max_output_bytes:
            raise PrototypeError("budget max_output_bytes exceeded; refusing artifact")
        output.append(line)

    emit("(set-logic QF_UFLIA)\n(declare-sort Text 0)\n")
    for entry in mapping:
        emit(f"(declare-const {entry.new} {entry.sort})\n")
    references: dict[int, str] = {}
    inline_heights: dict[int, int] = {}
    definitions = inlined = 0
    for term in sorted(reachable):
        node = dag.nodes[term]
        if node.op == "symbol":
            references[term] = renamed[str(node.value)]
            inline_heights[term] = 0
            continue
        if node.op == "constant":
            if node.sort == "Bool":
                expression = "true" if node.value else "false"
            else:
                value = int(node.value)
                expression = str(value) if value >= 0 else f"(- {-value})"
            height = 0
        else:
            length = 2 + len(node.op) + sum(1 + len(references[arg]) for arg in node.args)
            if length > budget.max_output_bytes:
                raise PrototypeError("budget max_output_bytes exceeded by expression; refusing artifact")
            expression = f"({node.op}{''.join(' ' + references[arg] for arg in node.args)})"
            height = 1 + max((inline_heights[arg] for arg in node.args), default=0)
        # 此处只比较当前 DAG 直接引用数下的局部字节成本，不宣称全局最优。
        # 表达式与深度预算仍约束多次代入，0 显式禁用此表示决策。
        candidate_name = f"d{definitions}"
        declaration_cost = len(f"(define-fun {candidate_name} () {node.sort} {expression})\n")
        multiuse_inline = (uses[term] > 1 and len(expression) <= budget.inline_multiuse_bytes
                           and len(expression) <= budget.inline_bytes
                           and height <= budget.inline_depth
                           and uses[term] * len(expression)
                           < declaration_cost + uses[term] * len(candidate_name))
        inline = ((node.op == "constant" and len(expression) <= budget.inline_constant_bytes)
                  or (uses[term] == 1 and len(expression) <= budget.inline_bytes
                      and height <= budget.inline_depth)
                  or multiuse_inline)
        if inline:
            references[term] = expression
            inline_heights[term] = height
            inlined += 1
        else:
            name = f"d{definitions}"
            definitions += 1
            emit(f"(define-fun {name} () {node.sort} {expression})\n")
            references[term] = name
            inline_heights[term] = 0
    emit(f"(assert {references[root]})\n(check-sat)\n")
    smt_bytes = ''.join(output).encode("ascii")
    stats = {
        "input_bytes": len(data), "input_terms": term_count, "input_edges": edge_count,
        "input_depth": depth, "normalized_terms": len(dag.nodes),
        "reachable_terms": len(reachable),
        "reachable_edges": sum(len(dag.nodes[t].args) for t in reachable),
        "free_symbols": len(mapping), "shared_terms": dag.shared,
        "rewrites": dict(sorted(dag.rewrites.items())), "inlined_terms": inlined,
        "output_definitions": definitions, "output_bytes": len(smt_bytes),
        "production_limit_bytes": _PRODUCTION_LIMIT,
        "within_production_byte_limit": len(smt_bytes) <= _PRODUCTION_LIMIT,
        "production_request_status": "not-a-production-request",
        "production_byte_feasibility": ("within-byte-limit-only" if len(smt_bytes) <= _PRODUCTION_LIMIT
                                         else "refused-over-production-byte-limit"),
        "research_budgets": asdict(budget),
    }
    return Artifact(smt_bytes, mapping, stats)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--origins", type=Path, help="JSON object keyed by every original free name")
    for name, default in asdict(Budgets()).items():
        parser.add_argument("--" + name.replace('_', '-'), type=int, default=default)
    args = parser.parse_args(argv)
    paths = [args.input, args.output, args.metadata] + ([args.origins] if args.origins else [])
    if len({path.resolve() for path in paths}) != len(paths):
        parser.error("input, output, metadata and origins paths must be distinct")
    try:
        budget = Budgets(**{name: getattr(args, name) for name in asdict(Budgets())})
        budget.validate()
        # 读取阶段也受预算约束，避免先分配无界输入再拒绝。
        with args.input.open('rb') as source:
            data = source.read(budget.max_input_bytes + 1)
        origins = None
        if args.origins:
            with args.origins.open("rb") as source:
                origin_bytes = source.read(budget.max_origins_bytes + 1)
            if len(origin_bytes) > budget.max_origins_bytes:
                raise PrototypeError("budget max_origins_bytes exceeded")
            origins = json.loads(origin_bytes)
        artifact = transform(data, budget, origins)
        metadata = json.dumps(artifact.metadata(), ensure_ascii=True, indent=2) + '\n'
        # 验证和渲染成功后才创建目标；独占创建防止覆盖既有研究材料。
        created: list[Path] = []
        try:
            with args.output.open("xb") as output:
                created.append(args.output)
                output.write(artifact.smt_bytes)
            with args.metadata.open("x", encoding="utf-8") as output:
                created.append(args.metadata)
                output.write(metadata)
        except OSError:
            # 只删除本次独占创建的精确文件，保留所有既有目标。
            for path in created:
                path.unlink()
            raise
    except (PrototypeError, OSError, json.JSONDecodeError) as error:
        print(f"query compaction refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps(artifact.stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
