#!/usr/bin/env python3
"""物化已接受 P2 独立材料；不是生产义务生成器、Evidence 迁移器或 checker。"""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import runpy

from pipeline_artifact_contracts.common import ContractError
from pipeline_artifact_contracts.validation import validate_obligation_set_bytes


ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "docs/evidence/p2-profile-review"
PROPOSAL = ROOT / "docs/evidence/p2-obligation-profile-review.md"
IR_ROOT = ROOT / "crates/axiom-ir/tests/fixtures/v0.2"
BASE = runpy.run_path(str(ROOT / "scripts/generate-ir-type-vectors.py"))
canonical = BASE["canonical"]
DOMAIN = "axiom-evidence-v0.2:obligation"
NUMERIC_OPS = {"int_add", "int_sub", "fixed_add", "fixed_sub", "count_where", "sum_where"}
CORE_KINDS = {"ir-structure", "effect-empty", "totality", "key-cardinality", "numeric-range",
              "row-coverage", "group-conservation", "field-origin", "contract-guarantee", "noninterference"}
# 按提案位置表人工核对：2 + 3*非 input 节点 + group + 范围位置 + 输出字段 + guarantee/NI。
EXPECTED_COUNTS = [13, 13, 13, 8, 8, 8, 14, 17, 17, 10, 13, 10, 21, 45, 17, 17, 9, 17, 17, 18, 10]
ROLE_MAP = {"normalize": "ir-normalizer", "generate-obligations": "obligation-generator",
            "prove": "prover", "check-certificate": "certificate-checker", "check-fixture": "fixture-checker",
            "execute-host": "host-executor", "compare-output": "output-comparator",
            "replay-counterexample": "counterexample-replayer"}


def raw_digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def identity(domain, definition):
    return raw_digest(domain.encode() + b"\0" + canonical(definition).encode())


def entry(definition):
    return {"id": identity(DOMAIN, definition), "definition": definition}


def obligation(kind, anchor, document_id):
    return entry({"kind": kind, "expectation": "check" if kind == "ir-structure" else "prove",
                  "subject": {**anchor, "ir_document_digest": document_id}})


def numeric_paths(value, path=()):
    # 只消费本仓已通过 P1 的闭合合成 IR；不是通用输入验证或 op 分派实现。
    if isinstance(value, dict):
        if value.get("op") in NUMERIC_OPS or value.get("kind") in {"count", "sum"}:
            yield list(path)
        for name, child in value.items():
            yield from numeric_paths(child, (*path, name))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from numeric_paths(child, (*path, str(index)))


def proposed_definitions(ir, document_id):
    result = [obligation(kind, {"kind": anchor}, document_id)
              for kind, anchor in [("ir-structure", "document"), ("effect-empty", "program")]]
    nodes = {item["id"]: item["definition"] for item in ir["nodes"]}
    for node_id, definition in nodes.items():
        anchor = {"kind": "node", "id": node_id}
        if definition["kind"] != "input":
            result.extend(obligation(kind, anchor, document_id)
                          for kind in ["totality", "key-cardinality", "row-coverage"])
        if definition["kind"] == "group":
            result.append(obligation("group-conservation", anchor, document_id))
        result.extend(obligation("numeric-range", {"kind": "node-path", "id": node_id, "path": path}, document_id)
                      for path in numeric_paths(definition))
    for contract in ir["contracts"]:
        definition, contract_id = contract["definition"], contract["id"]
        if definition["kind"] == "noninterference":
            result.append(obligation("noninterference", {"kind": "contract", "id": contract_id}, document_id))
        elif definition["role"] == "guarantee":
            result.append(obligation("contract-guarantee", {"kind": "contract", "id": contract_id}, document_id))
        result.extend(obligation("numeric-range", {"kind": "contract-path", "id": contract_id, "path": path}, document_id)
                      for path in numeric_paths(definition))
    tables = {item["id"]: item["definition"] for item in ir["table_types"]}
    records = {item["id"]: item["definition"] for item in ir["record_types"]}
    for output in ir["outputs"]:
        record = records[tables[nodes[output["node"]]["table_type"]]["record_type"]]
        result.extend(obligation("field-origin", {"kind": "field", "direction": "output",
            "interface": output["name"], "name": field["name"]}, document_id) for field in record["fields"])
    assert len({item["id"] for item in result}) == len(result), "proposal duplicated a position"
    return sorted(result, key=lambda item: item["id"])


def read_cases():
    cases = []
    for line in (IR_ROOT / "migrations.tsv").read_text().splitlines():
        name, source, target, old_id, new_id, old_raw, new_raw = line.split("\t")
        path = IR_ROOT / target
        data = path.read_bytes()
        assert raw_digest(data) == new_raw
        assert raw_digest((ROOT / source).read_bytes()) == old_raw
        cases.append((name, path, data, old_id, new_id))
    data = (IR_ROOT / "records.jcs").read_bytes()
    cases.append(("records", IR_ROOT / "records.jcs", data, "", (IR_ROOT / "records-document-id.txt").read_text().strip()))
    result = []
    for index, (name, path, data, old_id, new_id) in enumerate(cases):
        ir = json.loads(data)
        assert ir["ir_version"] == "0.2"
        assert canonical(ir).encode() == data
        assert identity("axiom-ir-v0.2:document", ir) == new_id
        definitions = proposed_definitions(ir, new_id)
        assert len(definitions) == EXPECTED_COUNTS[index], (name, len(definitions))
        result.append({"name": name, "path": str(path.relative_to(ROOT)), "ir_artifact": raw_digest(data),
                       "ir_document_digest": new_id, "old_document_id": old_id,
                       "ir": ir, "definitions": definitions})
    assert len(result) == len(EXPECTED_COUNTS)
    return result


def old_core_by_document():
    base = ROOT / "contracts/keyed-finite-table-checker-bundles-v0.1"
    bundle_set = json.loads((base / "bundle-set.jcs").read_bytes())
    found = {}
    # 只消费已锁定 artifact 身份与 obligation definition；不读取 expected 或 obligation.result。
    for scenario in bundle_set["scenarios"]:
        relative = scenario["bundle"]["path"] + "/blobs/sha256/" + scenario["evidence"]["content_digest"].split(":")[1]
        path = base / relative
        data = path.read_bytes()
        assert raw_digest(data) == scenario["evidence"]["content_digest"]
        evidence = json.loads(data)
        assert canonical(evidence).encode() == data
        assert identity("axiom-evidence-v0.1:document", evidence) == scenario["evidence"]["document_digest"]
        if evidence["subject"]["kind"] != "axiom-ir":
            continue
        core = []
        for item in evidence["obligations"]:
            if item["definition"]["kind"] not in CORE_KINDS:
                continue
            assert identity("axiom-evidence-v0.1:obligation", item["definition"]) == item["id"]
            core.append({"id": item["id"], "definition": item["definition"]})
        document_id = evidence["subject"]["ir_document_digest"]
        if document_id not in found:
            found[document_id] = {"path": str(path.relative_to(ROOT)), "sha256": raw_digest(data),
                                  "definitions": core}
    return found


def compatibility(cases):
    old = old_core_by_document()
    result = []
    for case in cases[:12]:
        source = old[case["old_document_id"]]
        old_ids = sorted(item["id"] for item in source["definitions"])
        new_ids = [item["id"] for item in case["definitions"]]
        assert len(old_ids) == len(new_ids)
        assert not set(old_ids) & set(new_ids)
        result.append({"case": case["name"], "source_evidence_path": source["path"],
            "source_evidence_sha256": source["sha256"], "source_ir_document_digest": case["old_document_id"],
            "target_ir_document_digest": case["ir_document_digest"], "source_core_ids": old_ids,
            "proposed_target_core_ids": new_ids, "result_transfer": "forbidden",
            "mapping": "regenerated-inventories-only", "full_evidence_migration": "not-performed"})
    return result


def negative_recipes(cases):
    case = next(item for item in cases if item["name"] == "ax-b03-correct")
    baseline = case["definitions"]
    recipes = []
    for kind in ["row-coverage", "group-conservation", "numeric-range"]:
        target = next(item for item in baseline if item["definition"]["kind"] == kind and
                      (kind != "numeric-range" or item["definition"]["subject"]["kind"] == "contract-path"))
        recipes.append({"name": "omit-" + kind, "operation": "remove", "id": target["id"],
                        "expected_rejection": "missing-required-definition"})
    target = next(item for item in baseline if item["definition"]["kind"] == "numeric-range")
    recipes.append({"name": "duplicate", "operation": "append", "entry": target,
                    "expected_rejection": "duplicate-position"})
    definition = copy.deepcopy(target["definition"])
    definition["expectation"] = "check"
    recipes.append({"name": "wrong-expectation", "operation": "replace", "id": target["id"],
                    "entry": entry(definition), "expected_rejection": "wrong-expectation"})
    definition = copy.deepcopy(target["definition"])
    definition["subject"]["path"].append("01")
    recipes.append({"name": "wrong-path", "operation": "replace", "id": target["id"],
                    "entry": entry(definition), "expected_rejection": "invalid-canonical-path"})
    definition = copy.deepcopy(target["definition"])
    definition["subject"]["ir_document_digest"] = cases[0]["ir_document_digest"]
    recipes.append({"name": "other-ir-context", "operation": "replace", "id": target["id"],
                    "entry": entry(definition), "expected_rejection": "wrong-ir-context"})
    definition = copy.deepcopy(target["definition"])
    del definition["subject"]["ir_document_digest"]
    recipes.append({"name": "old-anchor-shape", "operation": "replace", "id": target["id"],
                    "entry": entry(definition), "expected_rejection": "missing-ir-context"})
    input_node = next(item for item in case["ir"]["nodes"] if item["definition"]["kind"] == "input")
    extra = obligation("totality", {"kind": "node", "id": input_node["id"]}, case["ir_document_digest"])
    recipes.append({"name": "extra-input-totality", "operation": "append", "entry": extra,
                    "expected_rejection": "extra-definition"})
    for name, bad_id in [
        ("old-domain", identity("axiom-evidence-v0.1:obligation", target["definition"])),
        ("missing-nul", raw_digest(DOMAIN.encode() + canonical(target["definition"]).encode())),
        ("wrapper-hash", identity(DOMAIN, target)),
    ]:
        recipes.append({"name": name, "operation": "replace", "id": target["id"],
                        "entry": {**target, "id": bad_id}, "expected_rejection": "identity-mismatch"})
    recipes.append({"name": "result-in-p2", "operation": "replace", "id": target["id"],
                    "entry": {**target, "result": {"kind": "proved"}}, "expected_rejection": "result-forbidden"})
    recipes.append({"name": "reverse-order", "operation": "reverse", "expected_rejection": "noncanonical-order"})
    for recipe in recipes:
        mutated = copy.deepcopy(baseline)
        operation = recipe["operation"]
        if operation == "remove":
            mutated = [item for item in mutated if item["id"] != recipe["id"]]
        elif operation == "append":
            mutated.append(recipe["entry"])
        elif operation == "replace":
            mutated = [recipe["entry"] if item["id"] == recipe["id"] else item for item in mutated]
        else:
            mutated.reverse()
        if operation != "reverse":
            mutated.sort(key=lambda item: item["id"])
        assert mutated != baseline, recipe["name"]
        # 只确认配方确实形成所声明的差异；不冒充未实现的生产拒绝入口。
        if recipe["expected_rejection"] == "identity-mismatch":
            assert recipe["entry"]["id"] != identity(DOMAIN, recipe["entry"]["definition"])
        elif operation == "remove":
            assert len(mutated) == len(baseline) - 1
        elif operation == "append":
            assert len(mutated) == len(baseline) + 1
        recipe["baseline_case"] = case["name"]
    assert len(recipes) == 14
    return recipes


def group_separation():
    source = [{"key": "a", "units": "2"}, {"key": "b", "units": "0"}]
    rows = [
        ("correct", source, source, True, True),
        ("omit-zero-group", source, source[:1], False, True),
        ("wrong-aggregate", source, [{"key": "a", "units": "3"}, source[1]], True, False),
        ("same-global-sum-wrong-groups", source, [{"key": "a", "units": "1"}, {"key": "b", "units": "1"}], True, False),
        ("empty", [], [], True, True),
        ("upstream-key-rewrite", [{"key": "merged", "units": "2"}, {"key": "merged", "units": "0"}],
         [{"key": "merged", "units": "2"}], True, True),
        ("upstream-value-rewrite", [{"key": "a", "units": "1"}, {"key": "b", "units": "1"}],
         [{"key": "a", "units": "1"}, {"key": "b", "units": "1"}], True, True),
    ]
    result = []
    for name, direct_source, output, expected_coverage, expected_conservation in rows:
        sums = Counter()
        for item in direct_source:
            sums[item["key"]] += int(item["units"])
        coverage = set(sums) == {item["key"] for item in output}
        conservation = (all(int(item["units"]) == sums[item["key"]] for item in output) and
                        sum(int(item["units"]) for item in output) == sum(sums.values()))
        assert (coverage, conservation) == (expected_coverage, expected_conservation), name
        item = {"name": name, "direct_source": direct_source, "observed_groups": output,
                "row_coverage": coverage, "group_conservation": conservation}
        if name.startswith("upstream-"):
            item["original_input"] = source
            original_sums = Counter()
            for row in source:
                original_sums[row["key"]] += int(row["units"])
            item["task_group_equals_original"] = (
                {row["key"] for row in output} == set(original_sums) and
                all(int(row["units"]) == original_sums[row["key"]] for row in output)
            )
            assert not item["task_group_equals_original"]
        result.append(item)
    return result


def artifacts():
    cases = read_cases()
    all_ids = [item["id"] for case in cases for item in case["definitions"]]
    assert len(all_ids) == len(set(all_ids)) == 315, "distinct IR contexts must not share proposed IDs"
    guarantees = [next(item for item in case["definitions"] if item["definition"]["kind"] == "contract-guarantee")
                  for case in cases[:2]]
    assert guarantees[0]["definition"]["subject"]["id"] == guarantees[1]["definition"]["subject"]["id"]
    assert guarantees[0]["id"] != guarantees[1]["id"], "same contract under different IR is not the same obligation"
    metadata, definitions = [], []
    for case in cases:
        counts = Counter(item["definition"]["kind"] for item in case["definitions"])
        metadata.append({"name": case["name"], "ir_path": case["path"], "ir_artifact": case["ir_artifact"],
            "ir_document_digest": case["ir_document_digest"], "count": str(len(case["definitions"])),
            "by_kind": {kind: str(count) for kind, count in sorted(counts.items())}})
        definitions.extend(f"{case['name']}\t{item['id']}\t{canonical(item['definition'])}\n" for item in case["definitions"])
    roles = [{"execution_kind": kind, "roles": [role], "compatible": True} for kind, role in ROLE_MAP.items()]
    roles.extend([{"execution_kind": "replay-counterexample", "roles": ["fixture-checker"], "compatible": False},
                  {"execution_kind": "prove", "roles": ["evidence-producer"], "compatible": False}])
    for case in roles:
        assert (ROLE_MAP[case["execution_kind"]] in case["roles"]) == case["compatible"]
    values = {"cases.json": {"status": "accepted-ir-derived-only", "scope": "ir-derived",
        "obligation_domain": DOMAIN, "proposal_sha256": raw_digest(PROPOSAL.read_bytes()),
        "generator_sha256": raw_digest(Path(__file__).read_bytes()), "cases": metadata},
        "compatibility.json": compatibility(cases), "negative-cases.json": negative_recipes(cases),
        "group-separation.json": group_separation(), "role-cases.json": roles}
    result = {name: json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n" for name, value in values.items()}
    result["obligations.tsv"] = "".join(definitions)
    return result


def extra_cases():
    helpers = runpy.run_path(str(ROOT / "scripts/generate-ir-v02-vectors.py"))
    identified, ordered, normalize = (helpers[key] for key in ["identified", "ordered_document", "normal_expression"])
    field, record_type, read = helpers["field"], helpers["record_type"], helpers["access"]
    integer = {"kind": "int", "lower": "0", "upper": "10"}
    fixed = {"kind": "fixed", "scale": "2", "lower": "0", "upper": "100"}
    one = {"op": "literal_int", "type": integer, "value": "1"}
    money = {"op": "literal_fixed", "type": fixed, "coefficient": "1"}
    add = {"op": "int_add", "result_type": integer, "values": [read("n"), one]}
    sub = {"op": "int_sub", "result_type": integer, "left": read("n"), "right": one}
    fadd = {"op": "fixed_add", "result_type": fixed, "values": [read("f"), money]}
    fsub = {"op": "fixed_sub", "result_type": fixed, "left": fadd, "right": money}
    leaf = record_type([field("x/😀", integer)])
    row = record_type([field("key", {"kind": "text"}), field("n", integer), field("f", fixed)])
    result = record_type([*row["definition"]["fields"], field("built", {"kind": "record", "record_type": leaf["id"]})])
    tables = [identified("table-type", {"capacity": "0", "primary_key": ["key"], "record_type": r["id"]}) for r in [row, result]]
    source = identified("node", {"kind": "input", "port": "源", "table_type": tables[0]["id"]})
    mapped = identified("node", normalize({"kind": "map", "source": source["id"], "table_type": tables[1]["id"], "fields": [
        {"name": "built", "expression": helpers["record_value"](leaf, {"x/😀": add})},
        {"name": "f", "expression": fsub}, {"name": "key", "expression": read("key")},
        {"name": "n", "expression": {"op": "if", "condition": helpers["NO"], "then": add, "else": sub, "result_type": integer}}]}))
    table_ref = {"kind": "input", "name": "源"}
    count = {"op": "count_where", "predicate": helpers["NO"], "table": table_ref, "result_type": integer}
    summed = {"op": "sum_where", "predicate": helpers["YES"], "table": table_ref, "result_type": integer, "value": add}
    assume = identified("contract", normalize({"kind": "formula", "role": "assume", "expression": {
        "op": "and", "values": [{"op": "le", "left": count, "right": one}, {"op": "le", "left": summed, "right": one}]}}))
    constant_add = {**add, "values": [one, one]}
    equality = {"op": "eq", "left": constant_add, "right": constant_add}
    guarantee = identified("contract", normalize({"kind": "formula", "role": "guarantee", "expression": {
        "op": "and", "values": [equality, equality]}}))
    document = ordered({"format": "axiom-ir", "ir_version": "0.2", "digest_algorithm": "sha-256", "semantics": {
        "name": "keyed-finite-table-semantics", "sha256": helpers["SEMANTICS"]}, "effects": [], "enum_types": [],
        "record_types": [row, result, leaf], "table_types": tables, "nodes": [source, mapped], "contracts": [assume, guarantee],
        "outputs": [{"name": '另一个"\\/😀', "node": mapped["id"]}, {"name": "result", "node": mapped["id"]}]})
    variants = [("all-numeric-positions", document, 24)]
    changed = copy.deepcopy(document)
    changed["contracts"].append(identified("contract", {"kind": "formula", "role": "assume", "expression": helpers["NO"]}))
    variants.append(("changed-pre", ordered(changed), 24))
    key_row = record_type([field("key", {"kind": "text"})])
    key_table = identified("table-type", {"capacity": "0", "primary_key": ["key"], "record_type": key_row["id"]})
    key_source = identified("node", {"kind": "input", "port": "空输入", "table_type": key_table["id"]})
    group = identified("node", {"kind": "group", "keys": [{"name": "key", "source_field": "key"}], "aggregates": [],
                               "source": key_source["id"], "table_type": key_table["id"]})
    empty = ordered({**document, "record_types": [key_row], "table_types": [key_table], "nodes": [key_source, group],
                     "contracts": [], "outputs": [{"name": "空结果", "node": group["id"]}]})
    variants.append(("empty-group-no-aggregates", empty, 7))
    duplicate = copy.deepcopy(empty)
    duplicate["outputs"].append({"name": "同源输出", "node": group["id"]})
    variants.append(("same-node-two-outputs", ordered(duplicate), 8))
    deep = one
    for _ in range(100):
        deep = {"op": "int_sub", "left": deep, "right": one, "result_type": integer}
    contract = identified("contract", {"kind": "formula", "role": "guarantee", "expression": {"op": "le", "left": deep, "right": one}})
    deep_doc = ordered({**empty, "nodes": [key_source], "outputs": [{"name": "空结果", "node": key_source["id"]}], "contracts": [contract]})
    variants.append(("deep-numeric", deep_doc, 104))
    result = []
    for name, ir, count in variants:
        data = canonical(ir).encode()
        document_id = identity("axiom-ir-v0.2:document", ir)
        definitions = proposed_definitions(ir, document_id)
        assert len(definitions) == count, (name, len(definitions), count)
        result.append({"name": name, "path": "contracts/ir-derived-obligations-v0.2/inputs/" + name + ".jcs",
            "ir": ir, "ir_artifact": raw_digest(data), "ir_document_digest": document_id, "definitions": definitions})
    return result


def obligation_set(case):
    ir = case["ir"]
    return {"format": "axiom-obligation-set", "format_version": "0.2", "ir_version": "0.2",
        "ir_artifact": case["ir_artifact"], "ir_document_digest": case["ir_document_digest"],
        "semantics": {"name": ir["semantics"]["name"], "sha256": "sha256:" + ir["semantics"]["sha256"]},
        "scope": "ir-derived", "obligation_profile": {"name": "keyed-finite-table-verification", "version": "0.2"},
        "obligations": case["definitions"]}


def contract_artifacts():
    originals = read_cases()
    extras = extra_cases()
    cases = originals + extras
    result, manifest = {}, []
    for case in cases:
        name, definitions = case["name"], case["definitions"]
        data = canonical(obligation_set(case))
        definition_bytes = sum(len(canonical(item["definition"]).encode()) for item in definitions)
        path_bytes = sum(len(canonical(item["definition"]["subject"]["path"]).encode()) for item in definitions if "path" in item["definition"]["subject"])
        result[f"sets/{name}.jcs"] = data
        manifest.append(f"{name}\t{case['path']}\t{case['ir_document_digest']}\t{case['ir_artifact']}\t{len(definitions)}\t{definition_bytes}\t{path_bytes}\t{len(data.encode())}\t{raw_digest(data.encode())}\n")
    for case in extras:
        result[f"inputs/{case['name']}.jcs"] = canonical(case["ir"])
    # 原数组位置、字段序、可归一化的 and 重复与 JCS 对象顺序都不应变成 P2 path。
    raw = copy.deepcopy(extras[0]["ir"])
    for key in ["nodes", "contracts", "record_types", "table_types", "outputs"]:
        raw[key].reverse()
    for node in raw["nodes"]:
        if node["definition"]["kind"] == "map": node["definition"]["fields"].reverse()
    for contract in raw["contracts"]:
        if contract["definition"]["role"] == "guarantee":
            expr = contract["definition"]["expression"]
            contract["definition"]["expression"] = {"op": "and", "values": [expr, expr]}
    result["inputs/all-numeric-positions-input.json"] = json.dumps(raw, ensure_ascii=True, indent=2) + "\n"
    result["cases.tsv"] = "".join(manifest)
    baseline = next(case for case in originals if case["name"] == "ax-b03-correct")
    negative_rows = []
    diagnostics = {"missing-required-definition": "MissingObligation", "duplicate-position": "DuplicateId",
        "identity-mismatch": "IdentityMismatch", "result-forbidden": "UnexpectedMember", "noncanonical-order": "NonCanonicalOrder"}
    def negative(name, value, error):
        result[f"negative/{name}.jcs"] = canonical(value)
        negative_rows.append(f"{name}\tax-b03-correct\t{error}\n")
    for recipe in negative_recipes(originals):
        value = obligation_set(copy.deepcopy(baseline))
        entries, op = value["obligations"], recipe["operation"]
        if op == "remove": value["obligations"] = [item for item in entries if item["id"] != recipe["id"]]
        elif op == "append": entries.append(recipe["entry"])
        elif op == "replace": value["obligations"] = [recipe["entry"] if item["id"] == recipe["id"] else item for item in entries]
        else: entries.reverse()
        if op != "reverse": value["obligations"].sort(key=lambda item: item["id"])
        negative(recipe["name"], value, diagnostics.get(recipe["expected_rejection"], "UnexpectedObligation"))
    for aggregate_index in ["0", "1"]:
        value = obligation_set(copy.deepcopy(baseline))
        value["obligations"] = [item for item in value["obligations"] if item["definition"]["subject"].get("path") != ["aggregates", aggregate_index]]
        assert len(value["obligations"]) == len(baseline["definitions"]) - 1
        negative("omit-aggregate-" + aggregate_index, value, "MissingObligation")
    for key, replacement in [("scope", "full"), ("format_version", "0.1"), ("ir_version", "0.1"),
        ("format", "axiom-evidence"), ("ir_artifact", baseline["ir_document_digest"]), ("ir_document_digest", baseline["ir_artifact"])]:
        value = obligation_set(copy.deepcopy(baseline)); value[key] = replacement
        negative("wrong-" + key, value, "BindingMismatch")
    for key in ["scope", "ir_version"]:
        value = obligation_set(copy.deepcopy(baseline)); del value[key]
        negative("missing-" + key, value, "MissingMember")
    for key, member, replacement in [("semantics", "sha256", baseline["ir"]["semantics"]["sha256"]),
        ("obligation_profile", "name", "keyed-finite-table-benchmark"), ("obligation_profile", "version", "0.3")]:
        value = obligation_set(copy.deepcopy(baseline)); value[key][member] = replacement
        negative("wrong-" + key + "-" + member, value, "BindingMismatch")
    value = obligation_set(copy.deepcopy(baseline)); value["conclusion"] = "satisfied"
    negative("conclusion-forbidden", value, "UnexpectedMember")
    value = obligation_set(copy.deepcopy(baseline)); value["obligations"] = []
    negative("empty-inventory", value, "MissingObligation")
    result["negative.tsv"] = "".join(negative_rows)
    compatibility_rows = []
    old_probe = obligation_set(copy.deepcopy(baseline))
    for name in ["new-scope", "strip-new-members", "forge-old-version"]:
        if name == "strip-new-members":
            del old_probe["scope"]
            del old_probe["ir_version"]
        elif name == "forge-old-version":
            old_probe["format_version"] = "0.1"
        try:
            validate_obligation_set_bytes(canonical(old_probe).encode())
        except ContractError as error:
            compatibility_rows.append(f"{name}\t{error.code}\n")
        else:
            raise AssertionError("old pipeline accepted new P2 scope")
    assert [row.split("\t")[1].strip() for row in compatibility_rows] == ["unknown-member", "unsupported-version", "semantics-mismatch"]
    result["old-pipeline-rejections.tsv"] = "".join(compatibility_rows)
    # 候选都是规范 JSON；语义 / profile 负例由实际 Rust strict 路径消费。
    result["provenance.json"] = json.dumps({"status": "accepted-ir-derived-only", "generator_sha256": raw_digest(Path(__file__).read_bytes()),
        "rule_sha256": raw_digest((ROOT / "docs/evidence/ir-derived-obligations-v0.2.md").read_bytes()),
        "adr_sha256": raw_digest((ROOT / "docs/adr/0018-ir-derived-obligation-profile.md").read_bytes()),
        "positive_count": str(len(cases)), "negative_count": str(len(negative_rows)),
        "old_evidence_results_transferred": False}, sort_keys=True, indent=2) + "\n"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    all_artifacts = {DEST / name: content for name, content in artifacts().items()}
    contract_root = ROOT / "contracts/ir-derived-obligations-v0.2"
    all_artifacts.update({contract_root / name: content for name, content in contract_artifacts().items()})
    for path, content in all_artifacts.items():
        expected = content.encode()
        if args.check:
            if not path.exists() or path.read_bytes() != expected:
                raise SystemExit(f"P2 material drift: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    print("P2 independent materials match" if args.check else "P2 independent materials generated")


if __name__ == "__main__":
    main()
