#!/usr/bin/env python3
"""生成内部类型声明测试向量；仅用 Python 标准库，不调用 Rust 生产实现。"""

import argparse
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "crates/axiom-ir/tests/fixtures/type-identities"
SEMANTICS = "6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"


def ordered(value):
    if isinstance(value, dict):
        return {key: ordered(value[key]) for key in sorted(value, key=lambda k: k.encode("utf-16-be"))}
    if isinstance(value, list):
        return [ordered(item) for item in value]
    return value


def canonical(value):
    # 这里的自有合成输入只包含 string / bool / array / object，无 number / null。
    return json.dumps(ordered(value), ensure_ascii=False, separators=(",", ":"))


def entry(kind, definition):
    definition = copy.deepcopy(definition)
    if kind == "record":
        definition["fields"].sort(key=lambda field: field["name"])
    digest = hashlib.sha256(
        f"axiom-ir-v0.1:{kind}-type\0".encode() + canonical(definition).encode()
    ).hexdigest()
    return {"definition": definition, "id": "sha256:" + digest}


def field(name, value_type, label="public"):
    return {"name": name, "type": value_type, "label": label}


def reverse_objects(value):
    if isinstance(value, dict):
        return {key: reverse_objects(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_objects(item) for item in value]
    return value


def artifacts():
    enums = [entry("enum", {"name": name, "members": ["z", "a", "é", "e\u0301", "😀"]})
             for name in ["阶段/\"\\\u2028", "另一阶段"]]
    leaf = entry("record", {"fields": [
        field("\U00010000", {"kind": "text"}), field("\ue000", {"kind": "text"}),
        field("é", {"kind": "text"}), field("e\u0301", {"kind": "text"}),
    ]})
    main = entry("record", {"fields": [
        field("key", {"kind": "text"}), field("flag", {"kind": "bool"}),
        field("amount", {"kind": "int", "lower": "-" + "9" * 80, "upper": "9" * 80}),
        field("fixed", {"kind": "fixed", "lower": "-10", "upper": "0", "scale": "9" * 40}),
        field("state", {"kind": "enum", "enum_type": enums[0]["id"]}),
        field("nested", {"kind": "record", "record_type": leaf["id"]}),
        field("optional", {"kind": "option", "inner": {"kind": "option", "inner": {
            "kind": "record", "record_type": leaf["id"]}}}, "sensitive"),
    ]})
    tables = [entry("table", {"capacity": "100000000000000000000000",
                              "primary_key": keys, "record_type": leaf["id"]})
              for keys in [["\U00010000", "\ue000"], ["\ue000", "\U00010000"]]]
    tables.append(entry("table", {"capacity": "0", "primary_key": ["key"], "record_type": main["id"]}))
    document = {
        "contracts": [], "digest_algorithm": "sha-256", "effects": [],
        "enum_types": enums, "format": "axiom-ir", "ir_version": "0.1",
        "nodes": [], "outputs": [], "record_types": [main, leaf],
        "semantics": {"name": "keyed-finite-table-semantics", "sha256": SEMANTICS},
        "table_types": tables,
    }
    permuted = copy.deepcopy(document)
    for key in ["enum_types", "record_types", "table_types"]:
        permuted[key].reverse()
    for record in permuted["record_types"]:
        record["definition"]["fields"].reverse()
    expected = []
    for kind in ["enum", "record", "table"]:
        for declaration in sorted(document[kind + "_types"], key=lambda item: item["id"]):
            expected.append(f"{kind}\t{declaration['id']}\t{canonical(declaration['definition'])}\n")
    enum_bytes = canonical(enums[0]["definition"]).encode()
    wrong_hashes = {
        "raw-definition": enum_bytes,
        "missing-nul": b"axiom-ir-v0.1:enum-type" + enum_bytes,
        "wrong-domain": b"axiom-ir-v0.1:record-type\0" + enum_bytes,
        "extra-newline": b"axiom-ir-v0.1:enum-type\0" + enum_bytes + b"\n",
        "including-id": b"axiom-ir-v0.1:enum-type\0" + canonical(enums[0]).encode(),
    }
    return {
        "input.json": json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        "permuted.json": json.dumps(reverse_objects(permuted), ensure_ascii=True, indent=4) + "\n",
        "expected.tsv": "".join(expected),
        "wrong-hashes.tsv": "".join(
            f"{name}\t{enums[0]['id']}\tsha256:{hashlib.sha256(data).hexdigest()}\n"
            for name, data in wrong_hashes.items()
        ),
    }


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
    print("IR type identity vectors match" if args.check else "IR type identity vectors generated")


if __name__ == "__main__":
    main()
