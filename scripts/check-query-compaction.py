#!/usr/bin/env python3
"""离线紧凑表示验收：原 SMT、新 SMT、独立 IR 期望及完整符号映射；无 solver。"""
import argparse
import copy
import csv
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import re
import runpy

from p3_query_semantics import Interpreter
from p3_coverage_semantics import results as concrete_results
from p4b_replay_semantics import observe
from query_compaction_prototype import Budgets, transform

ROOT = Path(__file__).resolve().parents[1]
Smt = runpy.run_path(str(ROOT / "scripts/check-p3-query-semantics.py"))["Smt"]
LIMIT = 1_048_576


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def read_child(directory, name):
    path = (directory / name).resolve()
    assert path.is_relative_to(directory.resolve()), "manifest path escapes input directory"
    return path.read_bytes()


def independent_smt(data):
    """仅作双射 alpha 重命名，以复用冻结的独立 SMT 解释器；不调用原型 parser。"""
    names = re.findall(rb"\((?:declare-const|define-fun) ([^ ()\n]+)", data)
    assert len(names) == len(set(names)), "duplicate compact name"
    renamed = {name: ("q" + "0" * 64 + "_t" + str(i)).encode() for i, name in enumerate(names)}
    normalized = re.sub(rb"[^()\s]+", lambda m: renamed.get(m[0], m[0]), data)
    return Smt(normalized), {k.decode(): v.decode() for k, v in renamed.items()}


def ax_worlds(document):
    """原容量不变；合成世界含满容量、稀疏、故障与手算可区分两个 wrong 的输入。"""
    states = next(e["definition"]["members"] for e in document["enum_types"])
    settled = states.index("settled")
    other = next(i for i in range(len(states)) if i != settled)

    def slot(key, subtotal=10, discount=3, state=settled, active=True):
        return {"active": active, "row": {"order_id": key, "subtotal_cents": subtotal,
                "discount_cents": discount, "state": state}}

    full = [slot(f"order-{i:03}", 100, i, settled if i % 2 else other) for i in range(100)]
    return [
        ("empty", {"orders": []}),
        ("zero-net", {"orders": [slot("零", 10, 10)]}),
        ("nonzero-net", {"orders": [slot("é", 10, 3)]}),
        ("unselected", {"orders": [slot("pending", 10, 3, other)]}),
        ("wrong-add-overflow", {"orders": [slot("overflow", 100000, 1)]}),
        ("pre-false", {"orders": [slot("bad-pre", 1, 2)]}),
        ("input-out-of-range", {"orders": [slot("bad-range", -1, 0)]}),
        ("duplicate-key", {"orders": [slot("same"), slot("same", 20, 4)]}),
        ("sparse-inactive-garbage", {"orders": [slot("hidden", -999, 999999, 99, False), slot("visible", 10, 10)]}),
        ("unicode-distinct", {"orders": [slot("é"), slot("e\u0301", 10, 10)]}),
        ("full-capacity", {"orders": full}),
        ("full-capacity-reversed", {"orders": list(reversed(full))}),
    ]


def mapped_world(document, symbols, mapping, assignment):
    """从完整短名称赋值和原 origin 独立恢复槽位；不从优化 DAG 推导布局。"""
    interp = Interpreter(document, {})
    rename = {m["old"]: m["new"] for m in mapping}
    renamed = {rename[name]: value for name, value in assignment.items()}
    assert len(renamed) == len(assignment) == len(symbols)
    assert {name: renamed[new] for name, new in rename.items()} == assignment
    origins = {}
    for symbol in symbols:
        o = symbol["origin"]
        if o["kind"] == "input":
            key = (o["interface"], int(o["slot"]), str(o["component"]))
            assert key not in origins
            origins[key] = renamed[rename[symbol["name"]]]

    def value(ty, leaves):
        kind = ty["kind"]
        if kind == "record":
            return {f["name"]: value(f["type"], leaves)
                    for f in interp.records[ty["record_type"]]["fields"]}
        if kind == "option":
            present = next(leaves)
            inner = value(ty["inner"], leaves)
            return {"some": inner} if present else None
        return next(leaves)

    result = {}
    for n in interp.nodes.values():
        if n["kind"] != "input":
            continue
        port, table = n["port"], interp.tables[n["table_type"]]
        ty = {"kind": "record", "record_type": table["record_type"]}
        count = len(interp.flatten(ty, interp.default(ty)))
        result[port] = []
        for index in range(int(table["capacity"])):
            leaves = iter(origins[(port, index, str(c))] for c in range(count))
            row = value(ty, leaves)
            assert next(leaves, None) is None
            result[port].append({"active": origins[(port, index, "active")], "row": row})
    return result


def visible(world):
    return {port: [s["row"] for s in slots if s["active"]] for port, slots in world.items()}


def verify_mapping(old, compact, alpha, symbols, mapping):
    assert {s["name"]: s["sort"] for s in symbols} == old.symbols
    assert len(mapping) == len(symbols)
    assert {m["old"]: m["sort"] for m in mapping} == old.symbols
    assert len({m["new"] for m in mapping}) == len(mapping)
    assert {alpha[m["new"]]: m["sort"] for m in mapping} == compact.symbols
    assert {m["old"]: m["origin"] for m in mapping} == {s["name"]: s["origin"] for s in symbols}
    ordered = sorted(mapping, key=lambda m: m["old"])
    assert [m["new"] for m in ordered] == sorted(m["new"] for m in mapping), "Text class order changed"


def mapping_rejections(old, compact, alpha, symbols, mapping):
    variants = [mapping[:-1]]
    wrong = copy.deepcopy(mapping)
    wrong[0]["sort"] = "Int" if wrong[0]["sort"] != "Int" else "Bool"
    variants.append(wrong)
    wrong = copy.deepcopy(mapping)
    wrong[0]["origin"] = {"kind": "unbound"}
    variants.append(wrong)
    wrong = copy.deepcopy(mapping)
    wrong[0]["new"] = wrong[1]["new"]
    variants.append(wrong)
    wrong = copy.deepcopy(mapping)
    wrong[0]["new"], wrong[1]["new"] = wrong[1]["new"], wrong[0]["new"]
    variants.append(wrong)
    for wrong in variants:
        try:
            verify_mapping(old, compact, alpha, symbols, wrong)
        except (AssertionError, KeyError):
            continue
        raise AssertionError("mapping mutation escaped independent check")
    return len(variants)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path, help="new directory; existing output is never overwritten")
    parser.add_argument("--baseline-representation", action="store_true",
                        help="reproduce the first pass: six-digit free names and no multi-use inlining")
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    rows = manifest["rows"]
    args.output.mkdir(parents=True, exist_ok=False)
    corpus_cache, checked_cases, unique, measurements = {}, set(), {}, []
    input_signatures = {}
    comparisons = layout_checks = replay_checks = mutations = mapping_mutations = arithmetic_mutations = 0
    budget = Budgets(min_free_name_digits=6, inline_multiuse_bytes=0) if args.baseline_representation else Budgets()
    manual = {}
    baseline_path = ROOT / "docs/query/ax-b01-query-size-review/measurements.tsv"
    baseline = {(r["candidate"], r["profile"], r["target"]): r
                for r in csv.DictReader(io.StringIO(baseline_path.read_text()), delimiter="\t")}
    for row in rows:
        raw = row["query_raw"]
        case = None
        if row.get("corpus_path"):
            corpus_path = row["corpus_path"]
            if corpus_path not in corpus_cache:
                corpus_cache[corpus_path] = json.loads((ROOT / corpus_path).read_bytes())
            case = next(c for c in corpus_cache[corpus_path]["cases"] if c["name"] == row["case_name"])
            target_index = int(row["target_index"])
            assert case["targets"][target_index] == {"id": row["target"], "definition": row["definition"]}
            signature = digest(json_bytes([row["ir_raw"], case["worlds"], [e[target_index] for e in case["expected"]]]))
            if raw in input_signatures:
                assert input_signatures[raw] == signature, "duplicate raw query has additional unverified worlds"
            input_signatures[raw] = signature
        if raw not in unique:
            data = read_child(args.manifest.parent, row["smt_path"])
            assert digest(data) == raw and len(data) == int(row["query_bytes"])
            document_bytes = (ROOT / row["ir_path"]).read_bytes()
            assert digest(document_bytes) == row["ir_raw"]
            document = json.loads(document_bytes)
            symbols = json.loads(read_child(args.manifest.parent, row["symbols_path"]))
            origins = {s["name"]: s["origin"] for s in symbols}
            artifact = transform(data, budget, origins=origins)
            # 重跑完整变换，实际核对确定性，不只比较估算。
            again = transform(data, budget, origins=origins)
            assert artifact.smt_bytes == again.smt_bytes and artifact.free_symbols == again.free_symbols
            del again
            old = Smt(data)
            compact, alpha = independent_smt(artifact.smt_bytes)
            mapping = [asdict(m) for m in artifact.free_symbols]
            verify_mapping(old, compact, alpha, symbols, mapping)
            if mapping_mutations == 0 and len(mapping) >= 2:
                mapping_mutations = mapping_rejections(old, compact, alpha, symbols, mapping)
            if case is not None:
                key = (corpus_path, case["name"])
                if key not in checked_cases:
                    for world, expected in zip(case["worlds"], case["expected"], strict=True):
                        assert concrete_results(document, world, case["targets"]) == expected
                    checked_cases.add(key)
                worlds = [(str(i), world) for i, world in enumerate(case["worlds"])]
                expectations = [e[target_index] for e in case["expected"]]
            else:
                worlds = ax_worlds(document)
                expectations = [concrete_results(document, w, [{"definition": row["definition"]}])[0]
                                for _, w in worlds]
            got_true = got_false = False
            for (label, world), expected in zip(worlds, expectations, strict=True):
                assignment = Interpreter(document, world).assignment(symbols)
                mapped = {alpha[m["new"]]: assignment[m["old"]] for m in mapping}
                assert old.evaluate(assignment) == expected, (row["candidate"], row["kind"], label, "old")
                actual = compact.evaluate(mapped)
                assert actual == expected, (row["candidate"], row["kind"], label, "compact")
                comparisons += 1
                restored = mapped_world(document, symbols, mapping, assignment)
                assert visible(restored) == visible(world), "model origin mapping changed active world"
                layout_checks += 1
                got_true |= actual
                got_false |= not actual
                if not row.get("corpus_path"):
                    observation = observe(document, restored, row["definition"])
                    assert (observation["kind"] == "target-violated") == actual
                    replay_checks += 1
                    if row["kind"] == "contract-guarantee" and label in {"zero-net", "nonzero-net"}:
                        manual[(row["candidate"], label)] = actual
            # 合法 Bool 常量替换目标应被正、负期望分别识别；确实解析被篡改字节。
            for literal, detected in [(b"false", got_true), (b"true", got_false)]:
                if detected:
                    changed = re.sub(rb"(?m)^\(assert .*\)$", b"(assert " + literal + b")", artifact.smt_bytes)
                    bad, bad_alpha = independent_smt(changed)
                    label, world = next((l, w) for (l, w), e in zip(worlds, expectations, strict=True) if e != (literal == b"true"))
                    assignment = Interpreter(document, world).assignment(symbols)
                    assert bad.evaluate({bad_alpha[m["new"]]: assignment[m["old"]] for m in mapping}) != old.evaluate(assignment)
                    mutations += 1
            if row["candidate"] == "int-add" and row["kind"] == "numeric-range":
                changed = artifact.smt_bytes.replace(b"(+ ", b"(- ", 1)
                assert changed != artifact.smt_bytes
                bad, bad_alpha = independent_smt(changed)
                found = False
                for (_, world), expected in zip(worlds, expectations, strict=True):
                    assignment = Interpreter(document, world).assignment(symbols)
                    found |= bad.evaluate({bad_alpha[m["new"]]: assignment[m["old"]] for m in mapping}) != expected
                assert found, "arithmetic mutation escaped independent check"
                arithmetic_mutations += 1
            stem = raw.removeprefix("sha256:")
            (args.output / (stem + ".smt2")).write_bytes(artifact.smt_bytes)
            (args.output / (stem + ".mapping.json")).write_bytes(json_bytes(mapping))
            unique[raw] = {"compact_raw": digest(artifact.smt_bytes), "compact_bytes": len(artifact.smt_bytes),
                           "free_symbols": len(mapping), "stats": artifact.stats}
            print(f"{len(unique)} unique / {row['candidate']} / {row['kind']}: {len(data)} -> {len(artifact.smt_bytes)} bytes", flush=True)
            del old, compact, data, artifact
        if not row.get("corpus_path"):
            previous = baseline[(row["candidate"], row["profile"], row["target"])]
            for field in ["query_raw", "ir_raw", "p2_raw"]:
                assert previous[field] == row[field]
            assert int(previous["query_bytes"]) == int(row["query_bytes"])
        result = unique[raw]
        measurements.append({k: row[k] for k in ["candidate", "profile", "kind", "target", "query_raw", "query_bytes"]}
                            | {k: result[k] for k in ["compact_raw", "compact_bytes", "free_symbols"]}
                            | {"within_1mib": result["compact_bytes"] <= LIMIT})
    if manual:
        assert manual == {(f"ax-b01-{candidate}", label): (candidate == "wrong-add" or (candidate == "wrong-drop-zero" and label == "zero-net"))
                          for candidate in ["correct", "wrong-add", "wrong-drop-zero"] for label in ["zero-net", "nonzero-net"]}
    with (args.output / "measurements.tsv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(measurements[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(measurements)
    sources = ["scripts/query_compaction_prototype.py", "scripts/check-query-compaction.py",
               "scripts/test-query-compaction-prototype.py",
               "scripts/check-p3-query-semantics.py", "scripts/p3_query_semantics.py", "scripts/p3_totality_semantics.py",
               "scripts/p3_cardinality_semantics.py", "scripts/p3_coverage_semantics.py", "scripts/p4b_replay_semantics.py",
               "crates/axiom-ir/examples/export_query_compaction_inputs.rs"]
    summary = {"status": "local-finite-feasibility-not-proof-not-solver-not-production-profile",
               "manifest_raw": digest(manifest_bytes), "sources": {p: digest((ROOT / p).read_bytes()) for p in sources},
               "profile_rows": len(rows), "unique_queries": len(unique), "finite_comparisons": comparisons,
               "mapping_world_checks": layout_checks, "independent_replay_checks": replay_checks,
               "assertion_mutations_detected": mutations, "stdin_limit_bytes": LIMIT,
               "mapping_mutation_classes_rejected": mapping_mutations,
               "arithmetic_mutations_detected": arithmetic_mutations,
               "research_budgets": asdict(budget),
               "within_limit_rows": sum(m["within_1mib"] for m in measurements),
               "compact_min_bytes": min(m["compact_bytes"] for m in measurements),
               "compact_max_bytes": max(m["compact_bytes"] for m in measurements),
               "unique": unique}
    (args.output / "summary.json").write_bytes(json_bytes(summary))
    print(json.dumps({k: v for k, v in summary.items() if k not in {"sources", "unique"}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
