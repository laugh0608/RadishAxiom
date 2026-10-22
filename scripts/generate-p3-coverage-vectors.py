#!/usr/bin/env python3
"""P3-D 独立有限期望与选择 / 完整输出观察，保留旧版材料。"""
import argparse
import copy
import json
from pathlib import Path
import runpy

from p3_coverage_semantics import observe, results

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "contracts/map-filter-query-v0.4"
V = runpy.run_path(str(ROOT / "scripts/generate-p3-query-vectors.py"))
P2, IR = V["P2"], V["IR"]
canonical, identified, normal = V["canonical"], V["identified"], V["normal"]


def additions():
    yield V["build"]("select-none", predicate=V["NO"], filter_capacity=0)
    yield V["build"]("wrong-business-predicate", predicate=V["compare"]("gt", V["access"]("x"), V["literal"](0)))
    # 两个同型整数键，保留非键 text：交换 / 重命名不能靠 sort mismatch 提前暴露。
    name, document = V["build"]("composite-key-permutation")
    old_table = document["table_types"][0]
    old_record = next(r for r in document["record_types"] if r["id"] == old_table["definition"]["record_type"])
    in_table = identified("table-type", {**old_table["definition"], "primary_key": ["key", "x"]})
    fields = copy.deepcopy(old_record["definition"]["fields"])
    for f in fields:
        if f["name"] == "key": f["name"] = "renamed_key"
    out_record = V["record_type"](fields)
    out_table = identified("table-type", {**old_table["definition"], "record_type": out_record["id"], "primary_key": ["x", "renamed_key"]})
    source = next(n for n in document["nodes"] if n["definition"]["kind"] == "input")
    source = identified("node", {**source["definition"], "table_type": in_table["id"]})
    mapped = next(n for n in document["nodes"] if n["definition"]["kind"] == "map")
    d = copy.deepcopy(mapped["definition"])
    d.update(source=source["id"], table_type=out_table["id"])
    for f in d["fields"]:
        if f["name"] == "key": f["name"] = "renamed_key"
    d["fields"].sort(key=lambda f: f["name"])
    mapped = identified("node", normal(d))
    document.update(nodes=[source, mapped], table_types=[in_table, out_table], outputs=[{"name": "out", "node": mapped["id"]}])
    document["record_types"].append(out_record)
    yield name, IR["ordered_document"](document)


def artifacts():
    old = json.loads((ROOT / "contracts/map-filter-query-v0.3/cases.json").read_bytes())
    cases = [(c["name"], json.loads((ROOT / c["ir"]).read_bytes()), c["ir"], c["worlds"]) for c in old["cases"]]
    files = {}
    for name, doc in additions():
        path = f"contracts/map-filter-query-v0.4/inputs/{name}.jcs"
        files[f"inputs/{name}.jcs"] = canonical(doc).encode()
        worlds = V["worlds"](doc)
        if name == "composite-key-permutation":
            row = copy.deepcopy(next(s["row"] for w in worlds for s in w["in"] if s["active"]))
            for key, x in [(0, 1), (1, 0), (1, 1)]:
                worlds.append({"in": [{"active": True, "row": {**row, "key": 0, "x": 0}},
                                      {"active": True, "row": {**row, "key": key, "x": x}}]})
        cases.append((name, doc, path, worlds))
    manifest = []
    for name, doc, path, worlds in cases:
        document_id = P2["identity"]("axiom-ir-v0.2:document", doc)
        targets = [o for o in P2["proposed_definitions"](doc, document_id) if o["definition"]["kind"] in
                   {"numeric-range", "contract-guarantee", "totality", "key-cardinality", "row-coverage"}]
        expected = [results(doc, w, targets) for w in worlds]
        # 合法 map / filter 忠实操作不会出现覆盖反例，故负例必须另作局部注入。
        assert all(not row[i] for row in expected for i, t in enumerate(targets) if t["definition"]["kind"] == "row-coverage")
        observations = [{t["id"]: observe(doc, w, t["definition"]["subject"]["id"])
                         for t in targets if t["definition"]["kind"] == "row-coverage"} for w in worlds]
        manifest.append({"name": name, "ir": path, "ir_raw": P2["raw_digest"](canonical(doc).encode()),
                         "ir_document_digest": document_id, "targets": targets, "worlds": worlds,
                         "expected": expected, "coverage_observations": observations})
    sources = [Path(__file__), ROOT / "scripts/p3_coverage_semantics.py", ROOT / "scripts/check-p3-coverage-semantics.py",
               ROOT / "contracts/map-filter-query-v0.3/cases.json", ROOT / "contracts/map-filter-query-v0.4/v0.3-baseline.tsv",
               ROOT / "docs/query/map-filter-query-v0.4.md", *[ROOT / p for p in old["sources"]]]
    data = {"status": "finite-independent-expectations-not-proof", "profile": "axiom-p3-map-filter-query-v0.4",
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
            assert path.is_file() and path.read_bytes() == data, "P3-D material drift: " + name
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"P3-D independent vectors: {len(cases)} cases / {sum(len(c['targets']) for c in cases)} queries / "
          f"{sum(len(c['targets']) * len(c['worlds']) for c in cases)} assignments; no solver or proof")


if __name__ == "__main__":
    main()
