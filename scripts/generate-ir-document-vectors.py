#!/usr/bin/env python3
"""组合既有独立组件向量，生成完整 IR 字节与文档域身份；不调用 Rust 实现。"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "crates/axiom-ir/tests/fixtures/document-identities"
GENERATORS = {kind: runpy.run_path(str(ROOT / f"scripts/generate-ir-{kind}-vectors.py"))
              for kind in ["type", "node", "contract"]}
canonical = GENERATORS["type"]["canonical"]
identified = GENERATORS["contract"]["identified"]


def ordered_document(document):
    # definition 的规范期望来自上游逐例指定的向量；这里只排列顶层无语义顺序数组。
    document = copy.deepcopy(document)
    for kind in ["enum_types", "record_types", "table_types", "nodes", "contracts"]:
        document[kind].sort(key=lambda item: item["id"])
    document["outputs"].sort(key=lambda item: item["name"])
    return document


def artifacts():
    upstream = {kind: generator["artifacts"]() for kind, generator in GENERATORS.items()}
    documents = {kind: ordered_document(json.loads(upstream[kind]["normalized-input.json"]))
                 for kind in ["node", "contract"]}
    # 给类型向量补上真实 input / output，使全部类型、嵌套引用与语义顺序经文档入口检查。
    types = json.loads(upstream["type"]["input.json"])
    names = ["\U00010000", "\ue000", '引号"\\/\u2028']
    nodes = [identified("node", {"kind": "input", "port": name, "table_type": table["id"]})
             for name, table in zip(names, types["table_types"])]
    outputs = [{"name": name, "node": node["id"]} for name, node in zip(names, nodes)]
    types["nodes"] = nodes
    types["outputs"] = outputs
    documents["type"] = ordered_document(types)
    raw_types = json.loads(upstream["type"]["permuted.json"])
    raw_types["nodes"] = list(reversed(nodes))
    raw_types["outputs"] = list(reversed(outputs))

    renamed = copy.deepcopy(types)
    renamed["outputs"][0]["name"] = "renamed"
    documents["renamed-output"] = ordered_document(renamed)
    # 两个表仅主键顺序不同；替换一个 input 的类型，按内容身份更新它和唯一引用。
    changed_key = copy.deepcopy(types)
    changed_node = identified("node", {**nodes[0]["definition"], "table_type": types["table_types"][1]["id"]})
    changed_key["nodes"][0] = changed_node
    changed_key["outputs"][0]["node"] = changed_node["id"]
    documents["reordered-key"] = ordered_document(changed_key)

    deep = copy.deepcopy(types)
    body = {"op": "literal_bool", "value": True}
    for _ in range(122):
        body = {"op": "forall_rows", "table": {"kind": "input", "name": names[0]}, "body": body}
    deep["contracts"] = [identified("contract", {"kind": "formula", "role": "assume", "expression": body})]
    documents["deep-binders"] = ordered_document(deep)

    result = {f"{name}.jcs": canonical(document) for name, document in documents.items()}
    result["type-input.json"] = json.dumps(GENERATORS["type"]["reverse_objects"](raw_types), ensure_ascii=True, indent=2) + "\n"
    result["identities.tsv"] = "".join(
        f"{name}\t{identified('document', document)['id']}\tsha256:{hashlib.sha256(canonical(document).encode()).hexdigest()}\n"
        for name, document in documents.items())
    data = result["contract.jcs"].encode()
    wrong = {"raw-file": data,
             "missing-nul": b"axiom-ir-v0.1:document" + data,
             "wrong-domain": b"axiom-ir-v0.1:contract\0" + data,
             "extra-newline": b"axiom-ir-v0.1:document\0" + data + b"\n",
             "pretty-input": b"axiom-ir-v0.1:document\0" + upstream["contract"]["normalized-input.json"].encode()}
    result["wrong-hashes.tsv"] = "".join(f"{name}\tsha256:{hashlib.sha256(value).hexdigest()}\n" for name, value in wrong.items())
    # 只提取既有语料清单的实际身份与路径，不读取 expected outcome，也不重新生成候选。
    candidates = []
    for slug in ["ax-b01", "ax-b02", "ax-b03", "ax-b04"]:
        task = json.loads((ROOT / f"benchmarks/keyed-finite-table-v0.1/{slug}/task.json").read_text())
        for candidate in task["candidates"]:
            candidates.append(f"{candidate['canonical']['path']}\t{candidate['document_digest']}\t{candidate['canonical']['sha256']}\n")
    result["candidates.tsv"] = "".join(candidates)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只核对已提交字节，不改文件")
    args = parser.parse_args()
    for name, content in artifacts().items():
        path = DESTINATION / name
        data = content.encode("utf-8")
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                raise SystemExit(f"fixture drift: {path.relative_to(ROOT)}")
        else:
            DESTINATION.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print("IR document identity vectors match" if args.check else "IR document identity vectors generated")


if __name__ == "__main__":
    main()
