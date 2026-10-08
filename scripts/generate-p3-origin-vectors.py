#!/usr/bin/env python3
"""P3-F 独立来源 / 标签记录，保留旧规范与向量字节。"""
import argparse
import json
from p3_origin_derivation import ROOT, canonical, derive, digest, make_set
from p3_origin_cases import cases as synthetic_cases

DEST = ROOT / "contracts/core-field-origin-v0.1"


def artifacts():
    frozen = [line.split("\t") for line in (ROOT / "contracts/ir-derived-obligations-v0.2/cases.tsv").read_text().splitlines()]
    baseline = {c[1]: (c[3], c[8]) for c in frozen}
    candidates = [(c[0], c[1], (ROOT / c[1]).read_bytes()) for c in
                  [line.split("\t") for line in (ROOT / "contracts/core-empty-effects-v0.1/cases.tsv").read_text().splitlines()]]
    files, rows, rules, gap_records = {}, [], set(), 0
    hand = []
    for name, ir, expected in synthetic_cases():
        data = canonical(ir).encode()
        source = str(DEST.relative_to(ROOT) / "inputs" / (name + ".jcs"))
        files["inputs/" + name + ".jcs"] = data
        candidates.append(("origin-" + name, source, data))
        hand.append(dict(name=name, ir=source, expected=expected))
    files["hand-checks.json"] = (json.dumps(hand, ensure_ascii=False, indent=2) + "\n").encode()
    for name, source, data in candidates:
        ir = json.loads(data)
        assert data == canonical(ir).encode()
        obligations = make_set(ir)
        if source in baseline:
            assert (digest(data), digest(canonical(obligations).encode())) == baseline[source]
        targets = [o for o in obligations["obligations"] if o["definition"]["kind"] == "field-origin"]
        for index, target in enumerate(targets):
            case = f"{name}-{index:03d}"
            record, usage = derive(ir, obligations, target["id"])
            encoded = canonical(record).encode()
            destination = f"records/{case}.jcs"
            assert destination not in files
            files[destination] = encoded
            rules.update(s["rule"] for s in record["steps"])
            gap_records += bool(record["gaps"])
            rows.append("\t".join([case, source, digest(data), target["id"], str(DEST.relative_to(ROOT) / destination), digest(encoded),
                *[str(usage[k]) for k in ["steps", "premise_edges", "descriptors", "path_bytes", "output_bytes"]], str(len(record["gaps"]))]))
    files["cases.tsv"] = ("\n".join(rows) + "\n").encode()
    sources = ["scripts/p3_origin_derivation.py", "scripts/p3_origin_cases.py", "scripts/generate-p3-origin-vectors.py", "scripts/check-p3-origin-derivations.py",
        "docs/query/core-field-origin-v0.1.md", "scripts/generate-p2-profile-review.py", "scripts/generate-ir-type-vectors.py", "scripts/generate-ir-v02-vectors.py", "scripts/generate-p3-query-vectors.py",
        "contracts/core-empty-effects-v0.1/cases.tsv", "contracts/ir-derived-obligations-v0.2/cases.tsv"]
    files["sources.json"] = (json.dumps(dict(status="independent-finite-analysis-not-proof", documents=len(candidates), records=len(rows),
        records_with_gaps=gap_records, rules=sorted(rules), sources={p: digest((ROOT / p).read_bytes()) for p in sources}), indent=2) + "\n").encode()
    return files, len(rows), gap_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, count, gaps = artifacts()
    for name, data in files.items():
        path = DEST / name
        if args.check:
            assert path.is_file() and path.read_bytes() == data, name
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"P3-F: {count} independent records; {gaps} with static gaps; no counterexamples or proof")


if __name__ == "__main__":
    main()
