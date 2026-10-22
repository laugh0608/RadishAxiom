#!/usr/bin/env python3
"""P3-C 合成输入、独立数学期望和容量前行观察；不改旧版材料。"""
import argparse
import copy
import json
from pathlib import Path
import runpy

from p3_query_semantics import FAULT, Interpreter
from p3_cardinality_semantics import prepared, results

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "contracts/map-filter-query-v0.3"
V = runpy.run_path(str(ROOT / "scripts/generate-p3-query-vectors.py"))
P2, IR = V["P2"], V["IR"]
build, arithmetic, literal, compare = [V[k] for k in ("build", "arithmetic", "literal", "compare")]
identified, normal, canonical = [V[k] for k in ("identified", "normal", "canonical")]
YES, NO = V["YES"], V["NO"]


def composite():
    name, document = build("composite-unicode", predicate=YES, filter_capacity=1)
    replacements = {}
    for entry in document["table_types"]:
        new = identified("table-type", {**entry["definition"], "primary_key": ["key", "text"]})
        replacements[entry["id"]] = new["id"]
        entry.update(new)
    # 遍历依赖次序后重新计算内容身份。
    for kind in ["input", "filter", "map"]:
        for entry in document["nodes"]:
            d = entry["definition"]
            if d["kind"] != kind:
                continue
            new_d = {**d, "table_type": replacements[d["table_type"]]}
            if "source" in d:
                new_d["source"] = replacements[d["source"]]
            new = identified("node", new_d)
            replacements[entry["id"]] = new["id"]
            entry.update(new)
    for output in document["outputs"]:
        output["node"] = replacements[output["node"]]
    return name, IR["ordered_document"](document)


def additions():
    overflow = arithmetic("int_add", literal(2), literal(1))
    fault = compare("eq", overflow, literal(0))
    cases = [
        build("capacity-zero", predicate=YES, filter_capacity=0),
        build("capacity-sparse", predicate=V["access"]("flag"), filter_capacity=1),
        build("predicate-fault-capacity", predicate={"op": "or", "values": [YES, fault]}, filter_capacity=0),
        build("capacity-pre-false", predicate=YES, filter_capacity=0, assumes=[NO]),
        build("capacity-pre-fault", predicate=YES, filter_capacity=0, assumes=[fault]),
        build("capacity-unrelated-fault", predicate=YES, filter_capacity=1),
        composite(),
    ]
    for name, document in cases:
        if name == "capacity-unrelated-fault":
            input_node = next(n for n in document["nodes"] if n["definition"]["kind"] == "input")
            mapped = next(n for n in document["nodes"] if n["definition"]["kind"] == "map")
            d = copy.deepcopy(mapped["definition"])
            d.update(source=input_node["id"], table_type=input_node["definition"]["table_type"])
            for field in d["fields"]:
                if field["name"] == "x":
                    field["expression"] = overflow
            other = identified("node", normal(d))
            document["nodes"].append(other)
            document["outputs"].append({"name": "other", "node": other["id"]})
        yield name, IR["ordered_document"](document)


def hand_check(name, document, worlds, targets, expected):
    nodes = {n["id"]: n["definition"] for n in document["nodes"]}
    for world, values in zip(worlds, expected):
        if not Interpreter(document, world).wf():
            assert not any(values)
            continue
        rows = [s["row"] for s in next(iter(world.values())) if s["active"]]
        for target, value in zip(targets, values):
            if target["definition"]["kind"] != "key-cardinality":
                continue
            node = nodes[target["definition"]["subject"]["id"]]
            if name in {"capacity-zero", "filter-capacity", "capacity-unrelated-fault", "composite-unicode"}:
                capacity = 0 if name == "capacity-zero" else 1
                assert value == (node["kind"] == "filter" and len(rows) > capacity), name
            elif name == "capacity-sparse":
                assert value == (node["kind"] == "filter" and sum(r["flag"] for r in rows) > 1)
            else:
                # 其余旧材料 / 新故障材料没有局部容量超限；WF 下不会产生重复键。
                assert not value, name


def artifacts():
    old = json.loads((ROOT / "contracts/map-filter-query-v0.2/cases.json").read_bytes())
    cases = [(c["name"], json.loads((ROOT / c["ir"]).read_bytes()), c["ir"], c["worlds"]) for c in old["cases"]]
    files = {}
    for name, document in additions():
        path = f"contracts/map-filter-query-v0.3/inputs/{name}.jcs"
        files[f"inputs/{name}.jcs"] = canonical(document).encode()
        worlds = V["worlds"](document)
        first = copy.deepcopy(worlds[-5]["in"][0])
        second = copy.deepcopy(first)
        second["row"]["key"] = 1
        # 增加双选中行、单分量相同与 NFC / NFD 不同的合法复合键。
        worlds.append({"in": [first, second]})
        if name == "composite-unicode":
            for key, text in [(0, "e\u0301"), (1, "é"), (0, "é")]:
                other = copy.deepcopy(first)
                other["row"].update(key=key, text=text)
                worlds.append({"in": [first, other]})
                worlds.append({"in": [first, {**other, "active": False}]})
        cases.append((name, document, path, worlds))
    manifest = []
    for name, document, path, worlds in cases:
        document_id = P2["identity"]("axiom-ir-v0.2:document", document)
        targets = [o for o in P2["proposed_definitions"](document, document_id)
                   if o["definition"]["kind"] in {"totality", "numeric-range", "contract-guarantee", "key-cardinality"}]
        expected = [results(document, world, targets) for world in worlds]
        hand_check(name, document, worlds, targets, expected)
        observations = []
        for world in worlds:
            interpreter = Interpreter(document, world)
            rows = {}
            for target in targets:
                if target["definition"]["kind"] == "key-cardinality":
                    prepared_rows = prepared(interpreter, target["definition"]["subject"]["id"])
                    rows[target["id"]] = {"ready": prepared_rows is not FAULT,
                                          "rows": None if prepared_rows is FAULT else prepared_rows}
            observations.append(rows)
        manifest.append({"name": name, "ir": path, "ir_raw": P2["raw_digest"](canonical(document).encode()),
                         "ir_document_digest": document_id, "targets": targets, "worlds": worlds,
                         "expected": expected, "prepared_observations": observations})
    sources = [Path(__file__), ROOT / "scripts/p3_cardinality_semantics.py", ROOT / "scripts/check-p3-cardinality-semantics.py",
               ROOT / "contracts/map-filter-query-v0.2/cases.json", ROOT / "contracts/map-filter-query-v0.3/v0.2-baseline.tsv",
               ROOT / "docs/query/map-filter-query-v0.3.md"]
    # 旧 manifest 的来源闭包也验证，不复制或改写旧材料。
    sources += [ROOT / p for p in old["sources"]]
    data = {"status": "finite-independent-expectations-not-proof", "profile": "axiom-p3-map-filter-query-v0.3",
            "sources": {str(p.relative_to(ROOT)): P2["raw_digest"](p.read_bytes()) for p in sources}, "cases": manifest}
    files["cases.json"] = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    return files, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, cases = artifacts()
    for name, data in files.items():
        path = DEST / name
        if args.check:
            assert path.is_file() and path.read_bytes() == data, "P3-C material drift: " + name
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"P3-C independent vectors: {len(cases)} cases / {sum(len(c['targets']) for c in cases)} targets / "
          f"{sum(len(c['targets']) * len(c['worlds']) for c in cases)} assignments; no solver or proof")


if __name__ == "__main__":
    main()
