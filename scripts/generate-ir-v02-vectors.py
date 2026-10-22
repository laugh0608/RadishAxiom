#!/usr/bin/env python3
"""IR v0.2 独立期望：标准库递归依赖重建、手工记录构造和版本化负例。"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import runpy


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "crates/axiom-ir/tests/fixtures/v0.2"
BASE = runpy.run_path(str(ROOT / "scripts/generate-ir-type-vectors.py"))
canonical = BASE["canonical"]
field = BASE["field"]
OLD_SEMANTICS = BASE["SEMANTICS"]
SEMANTICS = "a40ec7c4eecfde23a340fb61b67727b5393f01b7288d151a34168ec88a87dac7"
COLLECTIONS = {"enum-type": "enum_types", "record-type": "record_types",
               "table-type": "table_types", "node": "nodes", "contract": "contracts"}
BOOL, TEXT = {"kind": "bool"}, {"kind": "text"}
YES, NO = {"op": "literal_bool", "value": True}, {"op": "literal_bool", "value": False}


def identified(kind, definition, version="0.2"):
    data = f"axiom-ir-v{version}:{kind}\0".encode() + canonical(definition).encode()
    return {"id": "sha256:" + hashlib.sha256(data).hexdigest(), "definition": definition}


def ordered_document(document):
    document = copy.deepcopy(document)
    for collection in COLLECTIONS.values():
        document[collection].sort(key=lambda item: item["id"])
    document["outputs"].sort(key=lambda item: item["name"])
    return document


def normal_expression(value):
    # 独立 Python 规则仅用于本批明确的已良构合成 / 既有规范输入，不是生产验证器。
    if isinstance(value, list):
        return [normal_expression(item) for item in value]
    if not isinstance(value, dict):
        return value
    value = {key: normal_expression(item) for key, item in value.items()}
    op = value.get("op")
    if op in ["and", "or"]:
        flat = []
        for item in value["values"]:
            flat.extend(item["values"] if item.get("op") == op else [item])
        unique = {canonical(item): item for item in flat}
        value["values"] = [unique[key] for key in sorted(unique, key=lambda text: text.encode())]
        return value["values"][0] if len(value["values"]) == 1 else value
    if op == "eq":
        value["left"], value["right"] = sorted([value["left"], value["right"]], key=lambda v: canonical(v).encode())
    if op in ["int_add", "fixed_add"]:
        value["values"].sort(key=lambda v: canonical(v).encode())
    if op == "record":
        value["fields"].sort(key=lambda item: item["name"])
    return value


def migrate_expected(source):
    # 与 Rust 的拓扑队列不同：从每项递归构建其依赖并记忆目标 definition。
    originals = {kind: {entry["id"]: entry["definition"] for entry in source[collection]}
                 for kind, collection in COLLECTIONS.items()}
    targets = {kind: {} for kind in COLLECTIONS}

    def types(value):
        if isinstance(value, list):
            return [types(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            kind = {"enum_type": "enum-type", "record_type": "record-type", "table_type": "table-type"}.get(key)
            result[key] = build(kind, item)["id"] if kind else types(item)
        return result

    def build(kind, old_id):
        if old_id not in targets[kind]:
            definition = types(originals[kind][old_id])
            if kind == "node":
                for key in {"input": [], "filter": ["source"], "map": ["source"],
                            "group": ["source"], "lookup_join": ["left", "right"]}[definition["kind"]]:
                    definition[key] = build("node", definition[key])["id"]
            definition = normal_expression(definition)
            targets[kind][old_id] = identified(kind, definition)
        return targets[kind][old_id]

    result = copy.deepcopy(source)
    result["ir_version"] = "0.2"
    result["semantics"]["sha256"] = SEMANTICS
    mappings = []
    for kind, collection in COLLECTIONS.items():
        result[collection] = [build(kind, entry["id"]) for entry in source[collection]]
        mappings.extend((kind, old, targets[kind][old]["id"]) for old in sorted(targets[kind]))
    for output in result["outputs"]:
        output["node"] = targets["node"][output["node"]]["id"]
    return ordered_document(result), mappings


def access(name, index="0"):
    return {"op": "field", "field": name, "record": {"op": "bound", "index": index}}


def record_type(fields):
    return identified("record-type", {"fields": sorted(fields, key=lambda f: f["name"])})


def record_value(record, fields):
    return {"op": "record", "record_type": record["id"],
            "fields": [{"name": name, "expression": expression} for name, expression in sorted(fields.items())]}


def record_cases():
    leaf = record_type([field("visible", BOOL), field("secret", BOOL, "sensitive")])
    leaf_type = {"kind": "record", "record_type": leaf["id"]}
    wrapper = record_type([field("inner", {"kind": "option", "inner": leaf_type}), field("tag", TEXT)])
    wrapper_type = {"kind": "record", "record_type": wrapper["id"]}
    row = record_type([field("key", TEXT), field("flag", BOOL), field("secret", BOOL, "sensitive"),
                       field("optional", {"kind": "option", "inner": BOOL})])
    out = record_type([field("key", TEXT), field("built", leaf_type), field("maybe", wrapper_type), field("public", BOOL)])
    tables = [identified("table-type", {"capacity": "3", "primary_key": ["key"], "record_type": r["id"]})
              for r in [row, out]]
    source = identified("node", {"kind": "input", "port": "source", "table_type": tables[0]["id"]})
    built = record_value(leaf, {"secret": access("secret"), "visible": access("flag")})
    optional = {"op": "match_option", "subject": access("optional"), "none": NO,
                "some": {"op": "bound", "index": "0"}, "result_type": BOOL}
    wrapped = record_value(wrapper, {"inner": {"op": "some", "value": record_value(leaf, {
        "secret": access("secret"), "visible": optional})}, "tag": {"op": "literal_text", "value": "嵌套/😀"}})
    public = {"op": "field", "field": "visible", "record": built}
    fields = {"key": access("key"), "built": built, "maybe": wrapped, "public": public}
    mapped = identified("node", {"kind": "map", "source": source["id"], "table_type": tables[1]["id"],
                                 "fields": [{"name": name, "expression": value} for name, value in sorted(fields.items())]})
    scoped = record_value(leaf, {"secret": access("secret", "0"), "visible": access("flag", "1")})
    contract = identified("contract", {"kind": "formula", "role": "guarantee", "expression": {
        "op": "forall_rows", "table": {"kind": "input", "name": "source"}, "body": {
            "op": "match_option", "subject": {"op": "some", "value": {"op": "bound", "index": "0"}},
            "none": NO, "some": {"op": "field", "field": "visible", "record": scoped}, "result_type": BOOL}}})
    document = ordered_document({"format": "axiom-ir", "ir_version": "0.2", "digest_algorithm": "sha-256",
        "semantics": {"name": "keyed-finite-table-semantics", "sha256": SEMANTICS}, "effects": [], "enum_types": [],
        "record_types": [leaf, wrapper, row, out], "table_types": tables, "nodes": [source, mapped],
        "contracts": [contract], "outputs": [{"name": "result", "node": mapped["id"]}]})
    raw = copy.deepcopy(document)

    def permute(value):
        if isinstance(value, dict):
            for item in value.values():
                permute(item)
            if value.get("op") == "record":
                value["fields"].reverse()
                for item in value["fields"]:
                    if item["name"] == "visible":
                        expression = item["expression"]
                        item["expression"] = {"op": "and", "values": [expression, copy.deepcopy(expression)]}
        elif isinstance(value, list):
            for item in value:
                permute(item)

    permute(raw)
    for collection in COLLECTIONS.values():
        raw[collection].reverse()
    expressions = [("record", built, leaf_type, "sensitive"), ("nested", wrapped, wrapper_type, "sensitive"),
                   ("public-field", public, BOOL, "public"),
                   ("secret-field", {"op": "field", "field": "secret", "record": built}, BOOL, "sensitive")]
    rows = []
    for name, expression, ty, label in expressions:
        unordered = copy.deepcopy(expression)
        permute(unordered)
        rows.append(f"{name}\t{canonical(unordered)}\t{canonical(expression)}\t{canonical(ty)}\t{label}\n")
    ids = {"leaf": leaf["id"], "wrapper": wrapper["id"], "row": row["id"], "out": out["id"],
           "source": source["id"], "map": mapped["id"], "source-table": tables[0]["id"], "output-table": tables[1]["id"]}
    return document, raw, "".join(rows), ids


def reference_strings(source):
    source = copy.deepcopy(source)
    # 增加多个枚举，让至少一个 and 子式的比较键顺序因重绑而改变。
    for index in range(8):
        source["enum_types"].append(identified("enum-type", {"name": f"Reorder-{index}", "members": ["a"]}, "0.1"))
    preserved = source["enum_types"][0]["id"]
    old_node = source["nodes"][0]["id"]
    source["nodes"][0]["definition"]["port"] = preserved
    source["nodes"][0] = identified("node", source["nodes"][0]["definition"], "0.1")
    for output in source["outputs"]:
        if output["node"] == old_node:
            output["node"] = source["nodes"][0]["id"]
            output["name"] = preserved
    expressions = []
    for enum in source["enum_types"]:
        literal = {"op": "literal_enum", "enum_type": enum["id"], "member": enum["definition"]["members"][0]}
        expressions.append({"op": "eq", "left": literal, "right": literal})
    text = {"op": "literal_text", "value": preserved}
    expressions.append({"op": "eq", "left": text, "right": text})
    body = normal_expression({"op": "and", "values": expressions})
    source["contracts"] = [identified("contract", {"kind": "formula", "role": "guarantee", "expression": body}, "0.1")]
    return ordered_document(source), preserved


def negative_cases(document):
    # 语义负例仍用独立摘要重建被修改的 definition；避免旧 ID 掩盖真正拒绝原因。
    cases = []
    mapped = next(item for item in document["nodes"] if item["definition"]["kind"] == "map")
    built = next(item["expression"] for item in mapped["definition"]["fields"] if item["name"] == "built")
    prefix = "/contracts/0/definition/expression/body"

    def formula(name, body, category, suffix):
        doc = copy.deepcopy(document)
        doc["contracts"] = [identified("contract", {"kind": "formula", "role": "guarantee", "expression": {
            "op": "forall_rows", "table": {"kind": "input", "name": "source"}, "body": body}})]
        cases.append((name, ordered_document(doc), category, prefix + suffix))

    def malformed_record(name, mutate, category, suffix):
        record = copy.deepcopy(built)
        mutate(record)
        formula(name, {"op": "field", "field": "visible", "record": record}, category, "/record" + suffix)

    malformed_record("missing-field", lambda r: r["fields"].pop(), "type:IncompleteFields", "/fields")
    malformed_record("duplicate-field", lambda r: r["fields"].append(copy.deepcopy(r["fields"][0])),
                     "input:DuplicateName", "/fields/2/name")
    malformed_record("unknown-field", lambda r: r["fields"][0].update(name="missing"),
                     "type:UnknownField", "/fields/0/name")
    malformed_record("extra-member", lambda r: r["fields"][0].update(cached_type=BOOL),
                     "input:UnknownMember", "/fields/0/cached_type")
    malformed_record("old-value-spelling", lambda r: r["fields"][0].update(value=r["fields"][0].pop("expression")),
                     "input:UnknownMember", "/fields/0/value")
    malformed_record("wrong-field-type", lambda r: r["fields"][0].update(expression={"op": "literal_text", "value": "false"}),
                     "type:TypeMismatch", "/fields/0/expression")
    malformed_record("unknown-record", lambda r: r.update(record_type="sha256:" + "0" * 64),
                     "input:UnresolvedReference", "/record_type")
    malformed_record("field-does-not-bind", lambda r: r["fields"][1].update(expression=access("flag", "1")),
                     "type:BoundOutOfRange", "/fields/1/expression/record/index")
    malformed_record("hidden-is-some", lambda r: r["fields"][0].update(expression={"op": "is_some"}),
                     "type:UnknownOperator", "/fields/0/expression/op")
    operand = {"op": "bound", "index": "0"}
    for depth in range(3):
        formula(f"record-equality-option-{depth}", {"op": "eq", "left": operand, "right": operand},
                "type:NonEquatableType", "")
        operand = {"op": "some", "value": operand}

    doc = copy.deepcopy(document)
    mapped = next(item for item in doc["nodes"] if item["definition"]["kind"] == "map")
    key = next(item for item in mapped["definition"]["fields"] if item["name"] == "key")
    key["expression"] = {"op": "if", "condition": NO, "then": key["expression"],
                         "else": copy.deepcopy(key["expression"]), "result_type": TEXT}
    replacement = identified("node", mapped["definition"])
    doc["nodes"] = [replacement if item["id"] == mapped["id"] else item for item in doc["nodes"]]
    doc["outputs"][0]["node"] = replacement["id"]
    doc = ordered_document(doc)
    index = next(i for i, item in enumerate(doc["nodes"]) if item["id"] == replacement["id"])
    cases.append(("complex-key", doc, "node:InvalidKeyProjection", f"/nodes/{index}/definition/fields/1/expression"))

    mapped = next(item for item in document["nodes"] if item["definition"]["kind"] == "map")
    for payload in ["built", "maybe"]:
        doc = copy.deepcopy(document)
        join = identified("node", {"kind": "lookup_join", "left": mapped["id"], "right": mapped["id"],
            "table_type": mapped["definition"]["table_type"], "pairs": [{"left": payload, "right": payload}],
            "fields": [{"name": item["name"], "expression": access(item["name"])} for item in mapped["definition"]["fields"]]})
        doc["nodes"].append(join)
        doc["outputs"][0]["node"] = join["id"]
        doc = ordered_document(doc)
        index = next(i for i, item in enumerate(doc["nodes"]) if item["id"] == join["id"])
        cases.append((f"join-record-{payload}", doc, "node:NonEquatablePair", f"/nodes/{index}/definition/pairs/0"))
    for name, version, semantics, path in [
        ("unknown-version", "0.3", SEMANTICS, "/ir_version"),
        ("old-version-new-semantics", "0.1", SEMANTICS, "/semantics/sha256"),
        ("new-version-old-semantics", "0.2", OLD_SEMANTICS, "/semantics/sha256"),
    ]:
        doc = copy.deepcopy(document)
        doc["ir_version"], doc["semantics"]["sha256"] = version, semantics
        cases.append((name, doc, "input:UnsupportedValue", path))
    return cases


def artifacts():
    semantic_path = ROOT / "docs/semantics/keyed-finite-table-semantics-v0.2.md"
    assert hashlib.sha256(semantic_path.read_bytes()).hexdigest() == SEMANTICS, "v0.2 semantics drift"
    assert hashlib.sha256((ROOT / "docs/semantics/keyed-finite-table-semantics.md").read_bytes()).hexdigest() == OLD_SEMANTICS
    version_source = (ROOT / "crates/axiom-ir/src/version.rs").read_text()
    for name, expected in [("V0_1", OLD_SEMANTICS), ("V0_2", SEMANTICS)]:
        assert re.search(rf'{name}_SEMANTICS_SHA256: &str\s*=\s*"{expected}"', version_source), "Rust semantic binding drift"
    for file in ["docs/ir/axiom-ir-v0.2.md", "docs/ir/ir-v0.1-to-v0.2-migration.md"]:
        assert SEMANTICS in (ROOT / file).read_text(), "normative semantic binding drift"

    sources = []
    for slug in ["ax-b01", "ax-b02", "ax-b03", "ax-b04"]:
        task = json.loads((ROOT / f"benchmarks/keyed-finite-table-v0.1/{slug}/task.json").read_text())
        for candidate in task["candidates"]:
            path = Path("benchmarks/keyed-finite-table-v0.1") / candidate["canonical"]["path"]
            sources.append((f"{slug}-{path.name.removesuffix('.ir.jcs')}", path, json.loads((ROOT / path).read_bytes())))
    for name in ["node", "contract", "type", "deep-binders", "mixed-int-ranges", "unicode-nfc", "unicode-nfd"]:
        path = Path(f"crates/axiom-ir/tests/fixtures/document-identities/{name}.jcs")
        sources.append((name, path, json.loads((ROOT / path).read_bytes())))
    references, preserved = reference_strings(next(doc for name, _, doc in sources if name == "type"))
    source_path = DESTINATION.relative_to(ROOT) / "references-source.jcs"
    sources.append(("references", source_path, references))
    result = {"references-source.jcs": canonical(references), "preserved-text.txt": preserved + "\n"}
    rows, mapping_rows = [], []
    for name, path, source in sources:
        target, mappings = migrate_expected(source)
        target_file = f"migrated/{name}.jcs"
        result[target_file] = canonical(target)
        source_id = identified("document", source, "0.1")["id"]
        target_id = identified("document", target)["id"]
        rows.append(f"{name}\t{path}\t{target_file}\t{source_id}\t{target_id}\t"
                    f"sha256:{hashlib.sha256(canonical(source).encode()).hexdigest()}\t"
                    f"sha256:{hashlib.sha256(canonical(target).encode()).hexdigest()}\n")
        mapping_rows.extend(f"{name}\t{kind}\t{old}\t{new}\n" for kind, old, new in mappings)
        if name == "references":
            original_order = [item["left"]["enum_type"] for item in source["contracts"][0]["definition"]["expression"]["values"]
                              if item["left"]["op"] == "literal_enum"]
            mapped = {old: new for kind, old, new in mappings if kind == "enum-type"}
            assert [mapped[old] for old in original_order] != sorted(mapped[old] for old in original_order)
    result["migrations.tsv"], result["mappings.tsv"] = "".join(rows), "".join(mapping_rows)
    document, raw, expressions, ids = record_cases()
    result["records.jcs"] = canonical(document)
    result["records-input.json"] = json.dumps(BASE["reverse_objects"](raw), ensure_ascii=False, indent=2) + "\n"
    result["record-expressions.tsv"] = expressions
    result["record-ids.tsv"] = "".join(f"{name}\t{identity}\n" for name, identity in ids.items())
    result["records-document-id.txt"] = identified("document", document)["id"] + "\n"
    rejected = []
    for name, value, category, path in negative_cases(document):
        file = f"negative/{name}.jcs"
        result[file] = canonical(value)
        rejected.append(f"{file}\t{category}\t{path}\n")
    result["negative.tsv"] = "".join(rejected)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, content in artifacts().items():
        path = DESTINATION / name
        data = content.encode("utf-8")
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                raise SystemExit(f"fixture drift: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print("IR v0.2 vectors match" if args.check else "IR v0.2 vectors generated")


if __name__ == "__main__":
    main()
