#!/usr/bin/env python3
"""将既有四版有限输入转换为 P4 world，独立解释原 IR；不执行 Rust 或 SMT。"""
import argparse
import json
from pathlib import Path

from p3_query_semantics import Interpreter
from p3_coverage_semantics import results
from p4b_replay_semantics import canonical, world_bytes, observe

ROOT = Path(__file__).resolve().parents[1]



def expected(document, world, targets):
    interp = Interpreter(document, world)
    if not interp.wf():
        return ["input-rejected"] * len(targets)
    pre = [interp.expr(c["definition"]["expression"], [], c["id"], ("expression",))
           for c in document["contracts"] if c["definition"].get("role") == "assume"]
    if not all(v is True for v in pre):
        return ["pre-rejected"] * len(targets)
    return ["target-violated" if v else "target-not-violated" for v in results(document, world, targets)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for version in ["v0.1", "v0.2", "v0.3", "v0.4"]:
        cases = json.loads((ROOT / f"contracts/map-filter-query-{version}/cases.json").read_bytes())["cases"]
        for case in cases:
            document = json.loads((ROOT / case["ir"]).read_bytes())
            items = []
            for index, world in enumerate(case["worlds"]):
                # Inactive slots disappear; this is the direct-world interpretation.
                active = {port: [s for s in slots if s["active"]] for port, slots in world.items()}
                outcomes = expected(document, active, case["targets"])
                name = f"{version}-{case['name']}-{index}.world.jcs"
                (args.directory / name).write_bytes(world_bytes(document, active))
                details = [observe(document, active, t["definition"]) for t in case["targets"]]
                assert [d["kind"] for d in details] == outcomes
                detail_name = name.replace(".world.jcs", ".expected.jcs")
                (args.directory / detail_name).write_bytes(canonical(details))
                items.append({"world": name, "expected": outcomes, "details": detail_name})
            manifest.append({"name": version + "-" + case["name"], "ir": case["ir"],
                             "targets": [t["id"] for t in case["targets"]], "items": items})
    (args.directory / "manifest.jcs").write_bytes(canonical(manifest))
    print(f"P4-B vectors: {len(manifest)} cases / {sum(len(c['items']) * len(c['targets']) for c in manifest)} finite target observations")


if __name__ == "__main__":
    main()
