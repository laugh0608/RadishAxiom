"""Read-only checks of synthetic Evidence v0.2 contract vectors."""

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import p3_effect_derivation as effects  # noqa: E402
import p3_origin_derivation as origins  # noqa: E402

SPEC = json.loads((HERE / "contract.json").read_bytes())
IR = ROOT / "crates/axiom-ir/tests/fixtures/v0.2/migrated"
SETS = ROOT / "contracts/ir-derived-obligations-v0.2/sets"
EFFECT_RECORDS = ROOT / "contracts/core-empty-effects-v0.1/records"
ORIGIN_RECORDS = ROOT / "contracts/core-field-origin-v0.1/records"


def require(condition, code):
    if not condition:
        raise ValueError(code)


def encode(value):
    return effects.canonical(value).encode()


def strict(raw):
    def pairs(items):
        result = dict(items)
        require(len(result) == len(items), "duplicate-member")
        return result

    def no_number(_):
        raise ValueError("json-number-or-null")

    def no_null(value):
        require(value is not None, "json-number-or-null")
        if isinstance(value, (list, dict)):
            for child in value.values() if isinstance(value, dict) else value:
                no_null(child)

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_int=no_number,
                       parse_float=no_number, parse_constant=no_number)
    no_null(value)
    require(encode(value) == raw, "noncanonical-json")
    return value


def identity(kind, definition):
    return effects.identity(SPEC["domains"][kind], definition)


def entry(kind, definition):
    return {"id": identity(kind, definition), "definition": definition}


def member_set(obj, shape):
    require(set(obj) == set(SPEC["members"][shape]), "invalid-shape")


def rejected_target(artifact):
    return entry("obligation", {"expectation": "check", "kind": "ir-structure",
                                "subject": {"kind": "rejected-ir", "artifact": artifact}})


def witness(observation, artifact):
    return {
        "kind": "structure-path", "minimality": {"kind": "unreduced"}, "preconditions": [],
        "worlds": [], "observed": {"reason": observation["reason"]},
        "trace": [{"artifact": artifact, **observation["location"]}],
    }


def rejected_fixture(raw, reason):
    if reason == "noncanonical-ir":
        return raw + b"\n", {"kind": "candidate-bytes", "offset": str(len(raw)), "length": "1"}
    if reason == "invalid-utf8":
        return b"{\xff", {"kind": "candidate-bytes", "offset": "1", "length": "1"}
    require(reason == "unknown-top-level-member", "structure-observation")
    return raw.replace(b'"nodes":', b'"metadata":true,"nodes":', 1), {
        "kind": "candidate-member", "path": ["metadata"],
    }


def check_definitions(actual, expected, *, complete):
    require((not complete or expected == actual) and all(row in expected for row in actual),
            "obligation-set")


def vector(mode_name, field=None, *, reject=None, stop=False, source=None, derivation=None):
    blobs, descriptors = {}, {}

    def add(raw, fmt, version="0.1"):
        pin = effects.digest(raw)
        blobs[pin] = raw
        descriptors[pin] = {"byte_length": str(len(raw)), "content_digest": pin,
                            "format": fmt, "format_version": version}
        return pin

    ir_raw = (source or IR / "ax-b01-correct.jcs").read_bytes()
    ir = strict(ir_raw)
    p2 = effects.make_set(ir)
    if source is None:
        require(encode(p2) == (SETS / "ax-b01-correct.jcs").read_bytes(), "frozen-p2")
    mode = SPEC["modes"][mode_name]
    if reject:
        candidate_raw, location = rejected_fixture(ir_raw, reject)
        candidate = add(candidate_raw, "ir-candidate")
        subject = {"artifact": candidate, "kind": "rejected-ir"}
        target = rejected_target(candidate)
    else:
        candidate = add(ir_raw, "axiom-ir", "0.2")
        subject = {**{k: p2[k] for k in ("ir_artifact", "ir_document_digest", "ir_version", "semantics")},
                   "kind": "axiom-ir"}
        target, = [row for row in p2["obligations"] if row["definition"]["kind"] == mode["obligation_kind"]
                   and (field is None or row["definition"]["subject"].get("name") == field)]
    role = SPEC["execution_roles"][mode["execution_kind"]]
    tool = entry("tool", {"artifact": add(b"synthetic review tool", "synthetic-tool"),
                         "name": "review-vector", "roles": sorted(["evidence-producer", role]),
                         "version": "0.1.0"})
    provenance = add(b"synthetic execution source", "execution-provenance")
    rule = add((ROOT / mode["rule"]).read_bytes(), "evidence-rule")
    inputs, outputs, result = {}, {}, {}
    if mode["execution_kind"] == "normalize":
        inputs = {"candidate": candidate}
        if reject:
            observation = {"kind": "rejected", "reason": reject, "location": location}
            outputs["structure-observation"] = add(encode(observation), "axiom-ir-structure-observation")
            result = {"kind": "failed", "assumptions": [], "counterexample": witness(observation, candidate)}
        elif not stop:
            observation = {"kind": "accepted", "document": subject["ir_document_digest"]}
            outputs = {"canonical-ir": candidate,
                       "structure-observation": add(encode(observation), "axiom-ir-structure-observation")}
            result = {"kind": "checked", "assumptions": [],
                      "artifacts": sorted({*inputs.values(), *outputs.values()})}
    else:
        generator = add(b"synthetic generator source", "generator-source")
        inputs = {"canonical-ir": candidate, "generator-source": generator,
                  "obligation-set": add(encode(p2), "axiom-obligation-set", "0.2")}
        record = strict(derivation.read_bytes())
        record["binding"]["generator"] = generator
        outputs = {"derivation": add(encode(record), record["format"], record["format_version"])}
        result = {"kind": "proved", "assumptions": []}

    execution = entry("execution", {
        "inputs": [{"role": r, "artifact": a} for r, a in sorted(inputs.items())],
        "outputs": [{"role": r, "artifact": a} for r, a in sorted(outputs.items())],
        "limits": [{"name": name, "unit": unit, "value": str(
            128 if name == "max-nesting" else len(ir_raw) - 1 if stop and name == "max-input-bytes" else 1000000
        )} for name, unit in sorted(mode["limits"].items())],
        "kind": mode["execution_kind"], "mode": mode_name, "obligation": target["id"], "ordinal": "0",
        "provenance": provenance, "rule": rule, "tool": tool["id"],
        "result": {"kind": "resource-exhausted", "code": "input-bytes"} if stop else {"kind": "completed"},
    })
    if stop:
        result = {"kind": "unknown", "attempts": [execution["id"]], "reason": "resource-exhausted"}
    elif result["kind"] == "proved":
        result["support"] = {"kind": "kernel-replay", "execution": execution["id"]}
    else:
        result["execution"] = execution["id"]
    document = {
        **{key: SPEC[key] for key in ("format", "evidence_version", "obligation_profile")},
        "digest_algorithm": "sha-256", "subject": subject, "producer": tool["id"], "tools": [tool],
        "executions": [execution], "obligations": [{**target, "result": result}],
        "artifacts": sorted(descriptors.values(), key=lambda item: item["content_digest"]),
        "trust": [], "uncovered": [],
        "conclusion": {"kind": "structure_rejected", "refs": [target["id"]]} if reject else
                      {"kind": "inconclusive", "refs": [target["id"]]} if stop else
                      {"kind": "satisfied", "refs": []},
    }
    return document, blobs


def check(document, blobs, *, complete):
    """Check the one-target vector packets and the complete S1 rejection document."""
    member_set(document, "document")
    require(all(document[k] == SPEC[k] for k in ("format", "evidence_version", "obligation_profile"))
            and document["digest_algorithm"] == "sha-256", "version-profile")
    artifacts = {}
    used = set()
    for item in document["artifacts"]:
        member_set(item, "artifact")
        pin = item["content_digest"]
        require(pin in blobs, "artifact-missing")
        require(pin == effects.digest(blobs[pin]) and item["byte_length"] == str(len(blobs[pin])),
                "artifact-identity")
        require(pin not in artifacts, "artifact-duplicate")
        artifacts[pin] = item
    require(list(artifacts) == sorted(artifacts), "artifact-order")

    def read(pin, kind=None, version="0.1"):
        require(pin in artifacts, "artifact-reference")
        used.add(pin)
        item = artifacts[pin]
        require(kind is None or (item["format"], item["format_version"]) == (kind, version), "artifact-format")
        return blobs[pin]

    obligation, = document["obligations"]
    tool, = document["tools"]
    attempt, = document["executions"]
    for kind, item in (("obligation", obligation), ("tool", tool), ("execution", attempt)):
        member_set(item, "obligation_entry" if kind == "obligation" else "entry")
        member_set(item["definition"], kind)
        require(identity(kind, item["definition"]) == item["id"], "entry-identity")
    require(not document["trust"] and not document["uncovered"], "synthetic-vector-boundary")

    subject = document["subject"]
    rejected = subject["kind"] == "rejected-ir"
    if rejected:
        member_set(subject, "subject_rejected_ir")
        expected = [rejected_target(subject["artifact"])]
        ir = None
        read(subject["artifact"], "ir-candidate")
    else:
        member_set(subject, "subject_ir")
        ir = strict(read(subject["ir_artifact"], "axiom-ir", "0.2"))
        p2 = effects.make_set(ir)
        require(subject == {**{k: p2[k] for k in
                               ("ir_artifact", "ir_document_digest", "ir_version", "semantics")},
                            "kind": "axiom-ir"}, "subject-binding")
        expected = p2["obligations"]
    target = {"id": obligation["id"], "definition": obligation["definition"]}
    check_definitions([target], expected, complete=complete)

    run = attempt["definition"]
    td = tool["definition"]
    role = SPEC["execution_roles"].get(run["kind"])
    require(role is not None and role in td["roles"] and td["roles"] == sorted(set(td["roles"]))
            and "evidence-producer" in td["roles"] and document["producer"] == tool["id"]
            and run["tool"] == tool["id"], "invalid-state-support")
    read(td["artifact"])
    read(run["provenance"], "execution-provenance")
    require(run["mode"] in SPEC["modes"], "unsupported-mode")
    mode = SPEC["modes"][run["mode"]]
    require(run["kind"] == mode["execution_kind"] and run["obligation"] == target["id"]
            and target["definition"]["kind"] == mode["obligation_kind"] and run["ordinal"] == "0", "execution-target")
    require(run["rule"] == mode["rule_digest"] and
            read(run["rule"], "evidence-rule") == (ROOT / mode["rule"]).read_bytes(), "rule-binding")
    for limit in run["limits"]:
        member_set(limit, "limit")
        require(limit["value"].isascii() and limit["value"].isdecimal()
                and str(int(limit["value"])) == limit["value"], "budget")
    require([(l["name"], l["unit"]) for l in run["limits"]] == sorted(mode["limits"].items()), "budget")
    limits = {limit["name"]: int(limit["value"]) for limit in run["limits"]}

    def refs(key, roles):
        rows = run[key]
        require([r["role"] for r in rows] == roles, "artifact-role")
        for row in rows:
            member_set(row, "reference")
        return {r["role"]: r["artifact"] for r in rows}

    result = obligation["result"]
    kind = result["kind"]
    require(set(result) == set(SPEC["result_members"][kind]), "invalid-state-support")
    require(not result.get("assumptions"), "synthetic-vector-boundary")
    inputs = refs("inputs", mode["inputs"])
    if kind == "unknown":
        refs("outputs", [])
        require(not rejected and result["attempts"] == [attempt["id"]]
                and result["reason"] == SPEC["unknown_reasons"].get(run["result"]["kind"]), "attempt-state")
        require(inputs.get("candidate") == subject["ir_artifact"], "subject-binding")
        require(run["result"] == {"kind": "resource-exhausted", "code": "input-bytes"}
                and len(blobs[inputs["candidate"]]) > limits["max-input-bytes"], "budget")
    else:
        require(run["result"] == {"kind": "completed"}, "attempt-state")
        outputs = refs("outputs", ["canonical-ir", *mode["outputs"]] if kind == "checked" else mode["outputs"])
        ir_pin = inputs.get("candidate") or inputs["canonical-ir"]
        require(len(blobs[ir_pin]) <= limits["max-input-bytes"], "budget")
        if kind == "proved":
            require(result["support"] == {"kind": "kernel-replay", "execution": attempt["id"]}
                    and ir is not None and target["definition"]["expectation"] == "prove",
                    "invalid-state-support")
            require(inputs["canonical-ir"] == subject["ir_artifact"]
                    and read(inputs["obligation-set"], "axiom-obligation-set", "0.2") == encode(p2), "p2-binding")
            generator = inputs["generator-source"]
            read(generator, "generator-source")
            if mode["obligation_kind"] == "effect-empty":
                expected_record = effects.derive(ir, p2, generator)
                counts = effects.usage(expected_record)
                usage = dict(zip(("steps", "premise_edges", "path_bytes", "output_bytes"), counts))
            else:
                expected_record, usage = origins.derive(ir, p2, target["id"], generator)
                roots, steps = expected_record["roots"], expected_record["steps"]
                record_type = expected_record["target"]["record_type"]
                fields, = [row["definition"]["fields"] for row in ir["record_types"] if row["id"] == record_type]
                field, = [row for row in fields if row["name"] == expected_record["target"]["name"]]
                require(field["label"] == "public" and field["type"]["kind"] not in ("option", "record")
                        and all(node["definition"]["kind"] in ("input", "filter", "map") for node in ir["nodes"])
                        and not expected_record["gaps"]
                        and steps[int(roots["value"])]["labels"]["inferred"] == "public" and all(
                    steps[int(roots[key])]["labels"]["propagated"] == "public"
                    for key in ("value", "control")), "origin-condition")
            require(all(count <= limits["max-" + name.replace("_", "-")]
                        for name, count in usage.items()), "budget")
            require(read(outputs["derivation"], expected_record["format"]) == encode(expected_record),
                    "derivation-binding")
        else:
            require(result["execution"] == attempt["id"] and mode["execution_kind"] == "normalize",
                    "invalid-state-support")
            observation = strict(read(outputs["structure-observation"], "axiom-ir-structure-observation"))
            if kind == "checked":
                require(not rejected and inputs["candidate"] == outputs["canonical-ir"] == subject["ir_artifact"],
                        "subject-binding")
                require(observation == {"kind": "accepted", "document": subject["ir_document_digest"]},
                        "structure-observation")
                require(result["artifacts"] == sorted({*inputs.values(), *outputs.values()}), "artifact-role")
            else:
                require(kind == "failed" and rejected and inputs["candidate"] == subject["artifact"],
                        "subject-binding")
                require(result["counterexample"] == witness(observation, subject["artifact"]), "structure-witness")
                base = (IR / "ax-b01-correct.jcs").read_bytes()
                candidate_raw, location = rejected_fixture(base, observation["reason"])
                require(observation == {"kind": "rejected", "reason": observation["reason"], "location": location}
                        and blobs[subject["artifact"]] == candidate_raw, "structure-observation")
    require(used == artifacts.keys(), "artifact-unused")
    if complete:
        require(rejected and kind == "failed" and document["conclusion"] ==
                {"kind": "structure_rejected", "refs": [target["id"]]}, "conclusion")


def rejects(code, action, *args, **kwargs):
    try:
        action(*args, **kwargs)
    except ValueError as error:
        require(str(error) == code, f"wanted {code}, got {error}")
        return
    raise ValueError(f"expected rejection: {code}")


def rebind(document):
    execution, = document["executions"]
    execution["id"] = identity("execution", execution["definition"])
    result = document["obligations"][0]["result"]
    result.get("support", result)["execution"] = execution["id"]


def main():
    samples = {
        "s1-rejected": vector("strict-ir-v0.2", reject="noncanonical-ir"),
        "s1-utf8": vector("strict-ir-v0.2", reject="invalid-utf8"),
        "s1-unknown-member": vector("strict-ir-v0.2", reject="unknown-top-level-member"),
        "s1-checked": vector("strict-ir-v0.2"),
        "s1-resource": vector("strict-ir-v0.2", stop=True),
        "s2-effect": vector("core-empty-effects-v0.1", derivation=EFFECT_RECORDS / "ax-b01-correct.jcs"),
        "s3-order-id": vector("core-field-origin-v0.1", "order_id",
                              derivation=ORIGIN_RECORDS / "ax-b01-correct-000.jcs"),
        "s3-net-cents": vector("core-field-origin-v0.1", "net_cents",
                               derivation=ORIGIN_RECORDS / "ax-b01-correct-001.jcs"),
    }
    fingerprints = {}
    for name, (document, blobs) in samples.items():
        complete = document["subject"]["kind"] == "rejected-ir"
        check(strict(encode(document)) if complete else document, blobs, complete=complete)
        fingerprints[name] = {key: document[key + "s"][0]["id"] for key in ("execution", "obligation")}
        if complete:
            fingerprints[name].update(raw=effects.digest(encode(document)), document=identity("document", document))
        else:
            rejects("obligation-set", check, document, blobs, complete=True)
    if sys.argv[1:] == ["--show-fingerprints"]:
        print(json.dumps(fingerprints, sort_keys=True, indent=2))
        return
    require(not sys.argv[1:], "unexpected-argument")
    require(fingerprints == json.loads((HERE / "fingerprints.json").read_bytes()), "vector-fingerprint")

    rejected = samples["s1-rejected"][0]
    rejects("noncanonical-json", strict, encode(rejected) + b"\n")
    rejects("duplicate-member", strict, b'{"mode":"a","mode":"b"}')
    rejects("json-number-or-null", strict, b'{"ordinal":1}')
    require(encode({"\ue000": "second", "\U00010000": "first"}) == '{"\U00010000":"first","\ue000":"second"}'.encode(),
            "utf16-order")
    first = samples["s1-checked"][0]["executions"][0]
    require(first["id"] != identity("execution", {**first["definition"], "ordinal": "1"}), "attempt-ordinal")
    doc, blobs = copy.deepcopy(samples["s1-rejected"])
    doc["evidence_version"] = "0.1"
    rejects("version-profile", check, doc, blobs, complete=True)
    doc, blobs = copy.deepcopy(samples["s1-rejected"])
    run = doc["executions"][0]
    run["id"] = effects.identity("axiom-evidence-v0.1:execution", run["definition"])
    doc["obligations"][0]["result"]["execution"] = run["id"]
    rejects("entry-identity", check, doc, blobs, complete=True)
    legacy = ROOT / "contracts/keyed-finite-table-checker-bundles-v0.1/s/chk-proof-02/bundle"
    request = strict((legacy / "request.jcs").read_bytes())
    old_raw = (legacy / "blobs/sha256" / request["evidence"].removeprefix("sha256:")).read_bytes()
    require(effects.digest(old_raw) == request["evidence"], "legacy-source")
    old, = [row["result"] for row in strict(old_raw)["obligations"]
            if row["definition"]["kind"] == "ir-structure"]
    doc, blobs = copy.deepcopy(samples["s1-checked"])
    doc["obligations"][0]["result"] = old
    rejects("invalid-state-support", check, doc, blobs, complete=False)
    doc, blobs = copy.deepcopy(samples["s1-rejected"])
    doc["obligations"][0]["result"]["counterexample"]["trace"][0]["offset"] = "0"
    rejects("structure-witness", check, doc, blobs, complete=True)
    pin = doc["subject"]["artifact"]
    blobs[pin] += b" "
    rejects("artifact-identity", check, doc, blobs, complete=True)
    del blobs[pin]
    rejects("artifact-missing", check, doc, blobs, complete=True)

    doc, blobs = copy.deepcopy(samples["s2-effect"])
    tool = doc["tools"][0]
    tool["definition"]["roles"] = ["evidence-producer", "fixture-checker"]
    tool["id"] = doc["producer"] = identity("tool", tool["definition"])
    doc["executions"][0]["definition"]["tool"] = tool["id"]
    rebind(doc)
    rejects("invalid-state-support", check, doc, blobs, complete=False)
    doc["executions"][0]["definition"]["kind"] = "replay-counterexample"
    rebind(doc)
    rejects("invalid-state-support", check, doc, blobs, complete=False)
    doc, blobs = copy.deepcopy(samples["s2-effect"])
    next(limit for limit in doc["executions"][0]["definition"]["limits"]
         if limit["name"] == "max-steps")["value"] = "53"
    rebind(doc)
    rejects("budget", check, doc, blobs, complete=False)
    doc, blobs = copy.deepcopy(samples["s3-order-id"])
    other = samples["s3-net-cents"][0]["obligations"][0]
    doc["obligations"][0].update(id=other["id"], definition=other["definition"])
    doc["executions"][0]["definition"]["obligation"] = other["id"]
    rebind(doc)
    rejects("derivation-binding", check, doc, blobs, complete=False)
    doc, blobs = copy.deepcopy(samples["s1-resource"])
    doc["obligations"][0]["result"]["attempts"] = []
    rejects("attempt-state", check, doc, blobs, complete=False)
    sensitive = ROOT / "contracts/core-field-origin-v0.1/inputs/sensitive-filter.jcs"
    doc, blobs = vector("core-field-origin-v0.1", "result", source=sensitive,
                        derivation=ORIGIN_RECORDS / "origin-sensitive-filter-001.jcs")
    rejects("origin-condition", check, doc, blobs, complete=False)

    group_ir = strict((IR / "ax-b03-correct.jcs").read_bytes())
    group_set = effects.make_set(group_ir)
    require(encode(group_set) == (SETS / "ax-b03-correct.jcs").read_bytes(), "group-p2")
    group, = [r["definition"]["subject"] for r in group_set["obligations"]
              if r["definition"]["kind"] == "group-conservation"]
    require({r["definition"]["kind"] for r in group_set["obligations"] if r["definition"]["subject"] == group}
            >= {"row-coverage", "group-conservation"}, "group-p2")
    for missing in ("row-coverage", "group-conservation"):
        definitions = group_set["obligations"]
        omitted = [r for r in definitions if not (r["definition"]["kind"] == missing
                                                  and r["definition"]["subject"] == group)]
        require(len(omitted) == len(definitions) - 1, "group-p2")
        rejects("obligation-set", check_definitions, omitted, definitions, complete=True)
    print("8 review vectors passed; 5 partial documents refused; byte, binding and group checks passed")


if __name__ == "__main__":
    require(not sys.flags.optimize, "review vectors require enabled assertions")
    main()
