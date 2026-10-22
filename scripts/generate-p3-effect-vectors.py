#!/usr/bin/env python3
"""生成独立空效果推导向量，不调用生产组件或外部工具。"""
import argparse
import json
from pathlib import Path
from p3_effect_derivation import ROOT, canonical, derive, digest, make_set, usage

DEST = ROOT / "contracts/core-empty-effects-v0.1"


def artifacts():
    frozen = [line.split("\t") for line in (ROOT / "contracts/ir-derived-obligations-v0.2/cases.tsv").read_text().splitlines()]
    baseline = {c[1]: (c[3], c[8]) for c in frozen}
    candidates = [(c[0], c[1]) for c in frozen]
    candidates += [("query-" + c["name"], c["ir"]) for c in json.loads((ROOT / "contracts/map-filter-query-v0.4/cases.json").read_bytes())["cases"]]
    # 原 query 会拒绝的资源场景在纯结构推导中不展开容量 / 量词实例。
    candidates += [("resource-" + p.stem, str(p.relative_to(ROOT))) for p in sorted((ROOT / "contracts/map-filter-query-v0.2/resource-inputs").glob("*.jcs"))]
    candidates.append(("nested-expansion", "contracts/map-filter-query-v0.1/resource-inputs/nested-expansion.jcs"))
    files, rows, seen, rules = {}, [], set(), set()
    for name, path in candidates:
        if path in seen: continue
        seen.add(path)
        data = (ROOT / path).read_bytes()
        ir = json.loads(data)
        assert data == canonical(ir).encode()
        obligations = make_set(ir)
        if path in baseline:
            assert (digest(data), digest(canonical(obligations).encode())) == baseline[path], "frozen P2 drift"
        record = derive(ir, obligations)
        encoded = canonical(record).encode()
        destination = f"records/{name}.jcs"
        files[destination] = encoded
        rules.update(s["rule"] for s in record["steps"])
        rows.append("\t".join([name, path, digest(data), str(DEST.relative_to(ROOT) / destination), digest(encoded), *map(str, usage(record))]))
    files["cases.tsv"] = ("\n".join(rows) + "\n").encode()
    sources = ["scripts/p3_effect_derivation.py", "scripts/generate-p3-effect-vectors.py", "scripts/check-p3-effect-derivations.py",
               "docs/query/core-empty-effects-v0.1.md", "scripts/generate-p2-profile-review.py", "scripts/generate-ir-type-vectors.py", "contracts/ir-derived-obligations-v0.2/cases.tsv",
               "contracts/map-filter-query-v0.4/cases.json"]
    files["sources.json"] = (json.dumps({"status": "independent-finite-rule-checks-not-proof", "rules": sorted(rules),
                                       "sources": {p: digest((ROOT / p).read_bytes()) for p in sources}}, indent=2) + "\n").encode()
    return files, len(rows), len(rules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, count, rules = artifacts()
    for name, data in files.items():
        path = DEST / name
        if args.check: assert path.is_file() and path.read_bytes() == data, name
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"P3-E: {count} independent derivations / {rules} rule IDs; no solver or proof")


if __name__ == "__main__": main()
