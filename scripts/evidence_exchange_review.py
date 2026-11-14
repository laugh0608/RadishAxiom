"""Evidence 交换草案的离线字节/绑定检查；不是独立语义 checker。"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs/evidence/evidence-v0.2-machine-contract"
DEST = HERE / "independent-check-v0.2"
sys.path.insert(0, str(ROOT / "scripts"))
OLD = runpy.run_path(str(ROOT / "scripts/generate-independent-check-contracts.py"))
VECTORS = runpy.run_path(str(HERE / "check_vectors.py"))
encode, strict = VECTORS["encode"], VECTORS["strict"]
digest, pretty = OLD["raw_digest"], OLD["pretty_bytes"]
Error = OLD["ContractError"]
obj = OLD["closed_object"]
PIN = OLD["digest_schema"]()
UINT = {"type": "string", "pattern": "^(0|[1-9][0-9]*)$"}
FORMAT_PATTERN = "^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$"
COMPONENT_LIMITS = {
    "model": {"candidate-bytes": "byte", "decode-steps": "step", "integer-digits": "digit",
              "text-bytes": "byte", "value-cells": "cell", "world-bytes": "byte"},
    "replay": {"comparisons": "comparison", "digit-work": "digit", "evaluation-steps": "step",
               "integer-digits": "digit", "output-bytes": "byte", "path-bytes": "byte", "rows": "row",
               "text-bytes": "byte", "type-items": "item", "value-cells": "cell", "world-bytes": "byte",
               "world-depth": "level", "world-nodes": "node"},
}
PROFILE = {"name": OLD["PROFILE_NAME"], "version": "0.2"}
DOMAINS = {k: f"axiom-independent-check-v0.2:{k}" for k in ("request", "manifest", "check", "result")}
CODE_REGISTRY = copy.deepcopy(OLD["CHECK_CODE_REGISTRY"])
CODE_REGISTRY["identity"] += ("source-binding", "source-binding-mismatch", "request-authority-mismatch")
CODE_REGISTRY["state-support"] += ("simulation-only", "source-unavailable", "state-support-checked", "interruption-cause-unverified")
for _kind in CODE_REGISTRY:
    CODE_REGISTRY[_kind] += ("verification-checked",)


def require(ok, code):
    if not ok:
        raise Error(code)


def keys(value, names):
    require(type(value) is dict, "invalid-shape")
    OLD["require_keys"](value, set(names.split()))


def pin(value):
    return OLD["require_digest"](value)


def ordered(values):
    require(type(values) is list, "invalid-shape")
    OLD["require_sorted_unique"](values)


def identity(kind, value):
    return digest(DOMAINS[kind].encode() + b"\0" + encode(value))


def schema_set():
    schemas = {name: OLD[f"{name}_schema"]() for name in ("request", "manifest", "result")}
    for name, schema in schemas.items():
        schema["$id"] = schema["$id"].replace(":0.1", ":0.2")
        schema["title"] = schema["title"].replace("v0.1", "v0.2 candidate")
        key = {"request": "request_version", "manifest": "bundle_version", "result": "result_version"}[name]
        schema["properties"][key] = {"const": "0.2"}
    request = schemas["request"]
    request["properties"]["checker_profile"] = obj({"name": {"const": PROFILE["name"]}, "version": {"const": "0.2"}})
    request["properties"]["source_binding"] = {"oneOf": [obj({
        "kind": {"const": "backend-batch"}, "backend_contract": PIN, "batch": PIN, "scope": {"const": "simulation"}}),
        obj({"kind": {"const": "no-backend"}, "scope": {"const": "simulation"}})]}
    request["required"].append("source_binding")
    schemas["manifest"]["properties"]["artifacts"]["items"]["properties"]["roles"]["items"]["enum"] += ["backend-contract", "source-batch"]
    schemas["manifest"]["properties"]["artifacts"]["items"]["properties"]["format"] = {"type": "string", "pattern": FORMAT_PATTERN}
    schemas["result"]["properties"]["scope"] = {"const": "simulation"}
    schemas["result"]["required"].append("scope")
    evidence_binding = schemas["result"]["properties"]["evidence"]
    missing_binding = obj({"expected_content_digest": PIN,
                           "document_digest": obj({"kind": {"const": "unavailable"}})})
    schemas["result"]["properties"]["evidence"] = {"oneOf": [evidence_binding, missing_binding]}
    schemas["result"]["allOf"] = [{
        "if": {"properties": {"evidence": missing_binding}},
        "then": {"properties": {
            "result": {"properties": {"kind": {"enum": ["incomplete", "rejected"]}}},
            "request": {"properties": {"document_digest": {"properties": {"kind": {"const": "available"}}}}},
            "missing_artifacts": {"minItems": 1},
            "remaining_trust": {"maxItems": 0},
        }},
    }]
    # Stable facts, never language-specific debug text. Counters not exposed by
    # current components are deliberately not invented here.
    limit = obj({"kind": {"const": "resource-limit"}, "resource": {"enum": [
        "candidate-bytes", "comparisons", "decode-steps", "digit-work", "evaluation-steps",
        "integer-digits", "output-bytes", "path-bytes", "rows", "text-bytes", "type-items",
        "value-cells", "world-bytes", "world-depth", "world-nodes"]}, "limit": UINT})
    invalid = obj({"kind": {"const": "input-error"}, "artifact": PIN,
                   "reason": {"enum": ["binding-mismatch", "invalid-model", "invalid-world", "noncanonical-world"]}})
    unsupported = obj({"kind": {"const": "unsupported"}, "feature": {"enum": ["ir-version", "obligation-kind", "profile", "semantic-feature"]}})
    internal = obj({"kind": {"const": "component-error"}})
    interruption = obj({
        "format": {"const": "axiom-evidence-replay-interruption"}, "version": {"const": "0.2"},
        "scope": {"const": "simulation"}, "generator": PIN, "request": PIN, "solve_execution": PIN, "component_policy": PIN,
        "stage": {"enum": ["model", "replay"]},
        "code": {"enum": ["component-limit", "model-decode", "replay-error", "unsupported"]},
        "cause": {"oneOf": [limit, invalid, unsupported, internal]},
        "diagnostic": {"oneOf": [obj({"kind": {"const": "absent"}}), obj({"kind": {"const": "artifact"}, "ref": PIN})]}})
    interruption.update({"$id": "urn:radishaxiom:schema:axiom-evidence-replay-interruption:0.2",
                         "$schema": OLD["SCHEMA_DIALECT"]})
    schemas["interruption"] = interruption
    policies = []
    for stage, limits in COMPONENT_LIMITS.items():
        policies.append(obj({"format": {"const": "axiom-evidence-component-policy"}, "version": {"const": "0.1"},
                             "stage": {"const": stage}, "limits": {"type": "array", "minItems": len(limits), "maxItems": len(limits), "items": False,
                             "prefixItems": [obj({"name": {"const": name}, "unit": {"const": unit}, "value": UINT}) for name, unit in sorted(limits.items())]}}))
    schemas["component-policy"] = {"$id": "urn:radishaxiom:schema:axiom-evidence-component-policy:0.1", "$schema": OLD["SCHEMA_DIALECT"], "oneOf": policies}
    return schemas


def backend_candidate():
    """New reviewed bytes; never overwrite the legacy local reader registry."""
    candidate = json.loads((HERE / "backend.json").read_bytes())
    candidate["version"] = "0.2"
    local = candidate["local_readback"]
    local["batch"]["version"] = "0.2"
    local["replay_interruption"] = {
        "format": "axiom-evidence-replay-interruption", "version": "0.2",
        "members": sorted(schema_set()["interruption"]["properties"]),
        "stages": ["model", "replay"], "diagnostic": "nonsemantic-artifact-or-absent",
        "cause": "closed-structured-facts-per-interruption-schema-and-stage-matrix",
    }
    local["inner_formats"]["component_policy"] = ["axiom-evidence-component-policy", "0.1"]
    local["inner_formats"]["diagnostic"] = ["component-diagnostic-text", "0.1"]
    return candidate


def validate_request(value):
    keys(value, "assurance_policy bundle_manifest checker_profile evidence limits request_version source_binding")
    require(value["request_version"] == "0.2" and value["checker_profile"] == PROFILE, "unsupported-version")
    source = value["source_binding"]
    require(type(source) is dict, "invalid-shape")
    kind = source.get("kind")
    require(kind in {"backend-batch", "no-backend"}, "unknown-tag")
    keys(source, "kind backend_contract batch scope" if kind == "backend-batch" else "kind scope")
    require(source["scope"] == "simulation", "unsupported-scope")
    if kind == "backend-batch":
        pin(source["backend_contract"])
        pin(source["batch"])
    # Reuse only the unchanged v0.1 request member constraints, after validating
    # the new closed envelope/version. This does not enable an old reader.
    common = {k: copy.deepcopy(v) for k, v in value.items() if k != "source_binding"}
    common["request_version"] = "0.1"
    common["checker_profile"]["version"] = "0.1"
    OLD["validate_request"](common)


def validate_manifest(value):
    keys(value, "artifacts bundle_version")
    require(value["bundle_version"] == "0.2", "unsupported-version")
    require(type(value["artifacts"]) is list and value["artifacts"], "evidence-cardinality")
    common = copy.deepcopy(value)
    common["bundle_version"] = "0.1"
    for item in common["artifacts"]:
        keys(item, "byte_length content_digest format format_version roles")
        ordered(item["roles"])
        # New roles have the same descriptor shape. Keep the other old roles
        # intact so unknown roles and evidence cardinality remain checked.
        item["roles"] = sorted(set("normative-spec" if r in {"backend-contract", "source-batch"} else r for r in item["roles"]))
        require(isinstance(item["format"], str) and re.fullmatch(FORMAT_PATTERN, item["format"]), "unknown-tag")
        item["format"] = item["format"].replace(".", "-")
    OLD["validate_manifest"](common)
    for role in ("backend-contract", "source-batch"):
        require(sum(role in d["roles"] for d in value["artifacts"]) <= 1, "source-binding-mismatch")


def validate_interruption(value):
    keys(value, "format version scope generator request solve_execution component_policy stage code cause diagnostic")
    require((value["format"], value["version"]) == ("axiom-evidence-replay-interruption", "0.2"), "unsupported-version")
    require(value["scope"] == "simulation", "unsupported-scope")
    for field in ("generator", "request", "solve_execution", "component_policy"):
        pin(value[field])
    stage, code, cause = value["stage"], value["code"], value["cause"]
    require(stage in {"model", "replay"}, "unknown-tag")
    require(type(cause) is dict, "invalid-shape")
    kind = cause.get("kind")
    if kind == "resource-limit":
        keys(cause, "kind resource limit")
        resources = COMPONENT_LIMITS[stage]
        require(cause["resource"] in resources and code == "component-limit", "cause-mismatch")
        require(isinstance(cause["limit"], str) and OLD["CANONICAL_UINT_PATTERN"].fullmatch(cause["limit"]), "limit-set-mismatch")
    elif kind == "input-error":
        keys(cause, "kind artifact reason")
        pin(cause["artifact"])
        reasons = {"binding-mismatch", "invalid-model"} if stage == "model" else {"binding-mismatch", "invalid-world", "noncanonical-world"}
        require(cause["reason"] in reasons and code == ("model-decode" if stage == "model" else "replay-error"), "cause-mismatch")
    elif kind == "unsupported":
        keys(cause, "kind feature")
        require(stage == "replay" and code == "unsupported" and cause["feature"] in {"ir-version", "obligation-kind", "profile", "semantic-feature"}, "cause-mismatch")
    elif kind == "component-error":
        keys(cause, "kind")
        require(code == ("model-decode" if stage == "model" else "replay-error"), "cause-mismatch")
    else:
        raise Error("unknown-tag")
    diagnostic = value["diagnostic"]
    require(type(diagnostic) is dict, "invalid-shape")
    if diagnostic.get("kind") == "absent":
        keys(diagnostic, "kind")
    else:
        keys(diagnostic, "kind ref")
        require(diagnostic["kind"] == "artifact", "unknown-tag")
        pin(diagnostic["ref"])


def validate_component_policy(value):
    keys(value, "format version stage limits")
    require(value["format"] == "axiom-evidence-component-policy" and value["version"] == "0.1", "unsupported-version")
    require(value["stage"] in COMPONENT_LIMITS, "unknown-tag")
    expected = sorted(COMPONENT_LIMITS[value["stage"]].items())
    require(type(value["limits"]) is list and len(value["limits"]) == len(expected), "limit-set-mismatch")
    for row, (name, unit) in zip(value["limits"], expected, strict=True):
        keys(row, "name unit value")
        require(row["name"] == name and row["unit"] == unit and isinstance(row["value"], str)
                and OLD["CANONICAL_UINT_PATTERN"].fullmatch(row["value"]), "limit-set-mismatch")


def interruption_policy_binding(value, policy_raw):
    validate_interruption(value)
    require(digest(policy_raw) == value["component_policy"], "component-policy-mismatch")
    policy = strict(policy_raw)
    validate_component_policy(policy)
    require(policy["stage"] == value["stage"], "component-policy-mismatch")
    if value["cause"]["kind"] == "resource-limit":
        limits = {v["name"]: v["value"] for v in policy["limits"]}
        require(limits[value["cause"]["resource"]] == value["cause"]["limit"], "component-policy-mismatch")


def identity_check(result, outcome, code, content):
    ref = {"kind": "artifact", "ref": content}
    return any(check["definition"]["kind"] == "identity"
               and check["definition"]["outcome"] == outcome
               and code in check["definition"]["codes"]
               and ref in check["definition"]["refs"] for check in result["checks"])


def validate_result(value):
    keys(value, "checker checks evidence missing_artifacts remaining_trust request result result_version scope tcb")
    require(value["result_version"] == "0.2", "unsupported-version")
    require(value["scope"] == "simulation", "unsupported-scope")
    checker = value["checker"]
    keys(checker, "artifact name source toolchain version")
    pin(checker["artifact"])
    pin(checker["source"])
    require(checker["name"] == "radishaxiom-independent-checker-go" and checker["toolchain"] == "go1.26.7", "checker-identity")
    require(isinstance(checker["version"], str) and checker["version"] not in {"", "latest"}, "checker-identity")
    request_availability = OLD["validate_binding"](value["request"])
    evidence = value["evidence"]
    require(type(evidence) is dict, "invalid-shape")
    missing_evidence = "expected_content_digest" in evidence
    if missing_evidence:
        keys(evidence, "expected_content_digest document_digest")
        pin(evidence["expected_content_digest"])
        require(evidence["document_digest"] == {"kind": "unavailable"}, "evidence-binding-mismatch")
    else:
        evidence_availability = OLD["validate_binding"](evidence)
    for field in ("missing_artifacts", "remaining_trust"):
        ordered(value[field])
        for content in value[field]:
            pin(content)
    ids = []
    require(type(value["checks"]) is list and value["checks"], "missing-required-member")
    for row in value["checks"]:
        keys(row, "id definition")
        definition = row["definition"]
        keys(definition, "kind outcome codes refs")
        kind, codes = definition["kind"], definition["codes"]
        require(kind in CODE_REGISTRY and type(codes) is list and codes, "unknown-tag")
        ordered(codes)
        require(all(c in CODE_REGISTRY[kind] for c in codes), "unknown-tag")
        require(definition["outcome"] in OLD["CHECK_OUTCOMES"], "unknown-tag")
        OLD["validate_refs"](definition["refs"])
        if "interruption-cause-unverified" in codes:
            require(definition["outcome"] == "incomplete"
                    and any(ref["kind"] == "artifact" for ref in definition["refs"]), "result-aggregation")
        require(row["id"] == identity("check", definition), "check-id-mismatch")
        ids.append(row["id"])
    ordered(ids)
    for row in value["checks"]:
        for ref in row["definition"]["refs"]:
            if ref["kind"] == "check":
                require(ref["ref"] in ids and ref["ref"] != row["id"], "result-reference-mismatch")
    require(type(value["tcb"]) is list, "invalid-shape")
    tcb_keys, categories = [], set()
    for item in value["tcb"]:
        keys(item, "artifact category version")
        pin(item["artifact"])
        require(item["category"] in OLD["TCB_CATEGORIES"] and isinstance(item["version"], str) and item["version"], "tcb-incomplete")
        tcb_keys.append((item["category"], item["artifact"]))
        categories.add(item["category"])
    ordered(tcb_keys)
    require(set(OLD["REQUIRED_TCB_CATEGORIES"]) <= categories, "tcb-incomplete")
    require(type(value["result"]) is dict, "invalid-shape")
    kind = value["result"].get("kind")
    keys(value["result"], "kind" if kind == "accepted" else "kind refs")
    require(kind in {"accepted", "accepted-with-trust", "incomplete", "rejected"}, "unknown-tag")
    if missing_evidence:
        require(kind in {"incomplete", "rejected"} and request_availability == "available", "result-aggregation")
        expected_digest = evidence["expected_content_digest"]
        require(expected_digest in value["missing_artifacts"] and not value["remaining_trust"]
                and identity_check(value, "incomplete", "artifact-missing", expected_digest), "evidence-binding-mismatch")
        require(not identity_check(value, "rejected", "digest-mismatch", expected_digest), "evidence-binding-mismatch")
    else:
        require(kind == "rejected" or request_availability == evidence_availability == "available", "result-aggregation")
    require(not any(row["definition"]["outcome"] == "trusted" for row in value["checks"]) or value["remaining_trust"], "result-aggregation")
    checks = value["checks"]
    outcomes = [r["definition"]["outcome"] for r in checks]
    expected = ("rejected" if "rejected" in outcomes else "incomplete" if "incomplete" in outcomes or value["missing_artifacts"]
                else "accepted-with-trust" if value["remaining_trust"] else "accepted")
    require(value["result"]["kind"] == expected, "result-aggregation")
    if expected != "accepted":
        selected = {"rejected": "rejected", "incomplete": "incomplete", "accepted-with-trust": "trusted"}[expected]
        refs = sorted(r["id"] for r in checks if r["definition"]["outcome"] == selected)
        require(bool(refs) and value["result"]["refs"] == refs, "result-aggregation")
    if expected == "accepted-with-trust":
        trusted_refs = set()
        for row in checks:
            if row["definition"]["outcome"] == "trusted":
                refs = {ref["ref"] for ref in row["definition"]["refs"] if ref["kind"] == "trust"}
                require(bool(refs), "trust-binding-mismatch")
                trusted_refs.update(refs)
        require(trusted_refs == set(value["remaining_trust"]), "trust-binding-mismatch")


def evidence_header(document):
    spec = VECTORS["SPEC"]
    keys(document, " ".join(spec["members"]["document"]))
    require(document["format"] == spec["format"] and document["evidence_version"] == spec["evidence_version"]
            and document["obligation_profile"] == spec["obligation_profile"]
            and document["digest_algorithm"] == "sha-256", "evidence-version-profile")
    for field in ("artifacts", "executions", "obligations", "tools", "trust", "uncovered"):
        require(type(document[field]) is list, "invalid-shape")
    subject = document["subject"]
    require(type(subject) is dict and subject.get("kind") in {"axiom-ir", "rejected-ir"}, "invalid-shape")
    shape = "subject_ir" if subject["kind"] == "axiom-ir" else "subject_rejected_ir"
    keys(subject, " ".join(spec["members"][shape]))
    if subject["kind"] == "axiom-ir":
        require(subject["ir_version"] == "0.2", "evidence-version-profile")


def evidence_exchange_closure(document, descriptors):
    """Check the exchange inventory and mode contracts, not P1/P2 semantics."""
    evidence_header(document)
    declared = {}
    for descriptor in document["artifacts"]:
        keys(descriptor, "byte_length content_digest format format_version")
        content = pin(descriptor["content_digest"])
        require(content not in declared, "manifest-coverage")
        declared[content] = descriptor
        actual = descriptors.get(content)
        require(actual is not None and "evidence-artifact" in actual["roles"], "manifest-coverage")
        require(all(actual[k] == v for k, v in descriptor.items()), "manifest-descriptor-mismatch")
    require(set(declared) == {k for k, d in descriptors.items() if "evidence-artifact" in d["roles"]}, "manifest-coverage")
    subject = document["subject"]
    subject_pin = subject["ir_artifact"] if subject["kind"] == "axiom-ir" else subject["artifact"]
    require({k for k, d in descriptors.items() if "subject" in d["roles"]} == {subject_pin}
            and subject_pin in declared, "manifest-subject-mismatch")
    spec = VECTORS["SPEC"]
    for kind, field in (("tool", "tools"), ("obligation", "obligations"), ("trust", "trust"), ("uncovered", "uncovered")):
        entry_ids = []
        for row in document[field]:
            keys(row, "definition id result" if kind == "obligation" else "definition id")
            require(row["id"] == VECTORS["identity"](kind, row["definition"]), "evidence-entry-identity")
            entry_ids.append(row["id"])
        ordered(entry_ids)
    tools = {t["id"]: t["definition"] for t in document["tools"]}
    require(all(t["artifact"] in declared for t in tools.values()), "execution-artifact-missing")
    obligations = {o["id"]: o["definition"] for o in document["obligations"]}
    backend_modes = backend_candidate()["modes"]
    ordinals, ids, backend = [], [], False
    for row in document["executions"]:
        keys(row, "definition id")
        run = row["definition"]
        keys(run, " ".join(spec["members"]["execution"]))
        require(row["id"] == VECTORS["identity"]("execution", run), "execution-identity")
        ids.append(row["id"])
        require(isinstance(run["ordinal"], str) and OLD["CANONICAL_UINT_PATTERN"].fullmatch(run["ordinal"]), "execution-order")
        ordinals.append(int(run["ordinal"]))
        mode = run["mode"]
        require(mode in spec["modes"] or mode in backend_modes, "unsupported-execution-mode")
        expected = spec["modes"].get(mode, backend_modes.get(mode))
        kind = expected.get("execution_kind", expected.get("kind"))
        require(run["kind"] == kind and run["tool"] in tools
                and spec["execution_roles"][kind] in tools[run["tool"]]["roles"], "execution-mode-binding")
        require(run["obligation"] in obligations, "execution-mode-binding")
        if mode in spec["modes"]:
            require(run["rule"] == expected["rule_digest"]
                    and obligations[run["obligation"]]["kind"] == expected["obligation_kind"], "execution-mode-binding")
        else:
            backend = True
        require(run["provenance"] in declared and run["rule"] in declared, "execution-artifact-missing")
        for field in ("inputs", "outputs"):
            require(type(run[field]) is list, "invalid-shape")
            for ref in run[field]:
                keys(ref, "artifact role")
                require(ref["artifact"] in declared, "execution-artifact-missing")
            if mode in backend_modes:
                continue
            roles = [ref["role"] for ref in run[field]]
            required = list(expected[field])
            if field == "outputs":
                if run["result"].get("kind") == "interrupted":
                    required = []
                elif mode == "strict-ir-v0.2" and subject["kind"] == "axiom-ir":
                    required.append("canonical-ir")
            require(sorted(roles) == sorted(required), "execution-mode-binding")
    ordered(ids)
    require(sorted(ordinals) == list(range(len(ordinals))), "execution-order")
    return backend


def bundle_binding(request_raw, manifest_raw, blobs, expected_request, expected_batch):
    """Return missing pins after known contradictions; no semantic acceptance."""
    # These limits protect this review harness, not a production resolver.
    require(len(request_raw) <= 65536 and len(manifest_raw) <= 1048576, "review-input-limit")
    require(digest(request_raw) == expected_request, "request-authority-mismatch")
    request, manifest = strict(request_raw), strict(manifest_raw)
    validate_request(request)
    validate_manifest(manifest)
    require(identity("manifest", manifest) == request["bundle_manifest"], "manifest-binding-mismatch")
    source = request["source_binding"]
    require(source.get("batch") == expected_batch, "source-binding-mismatch")
    limits = {v["name"]: int(v["value"]) for v in request["limits"]}
    descriptors = {d["content_digest"]: d for d in manifest["artifacts"]}
    require(set(blobs) <= set(descriptors), "unlisted-artifact")
    require(len(descriptors) <= limits["collection-items"], "review-input-limit")
    require(sum(int(d["byte_length"]) for d in descriptors.values()) <= limits["bundle-bytes"], "review-input-limit")
    missing = []
    for content, descriptor in descriptors.items():
        size = int(descriptor["byte_length"])
        require(size <= limits["artifact-bytes"], "review-input-limit")
        if content not in blobs:
            missing.append(content)
            continue
        raw = blobs[content]
        require(len(raw) == size, "length-mismatch")
        require(digest(raw) == content, "digest-mismatch")
    bindings = [("evidence", request["evidence"], "axiom-evidence", "0.2")]
    if source["kind"] == "backend-batch":
        bindings += [("backend-contract", source["backend_contract"], "axiom-evidence-backend-binding-review", "0.2"),
                     ("source-batch", source["batch"], "axiom-evidence-backend-batch", "0.2")]
    else:
        require(not any(set(d["roles"]) & {"backend-contract", "source-batch"} for d in descriptors.values()), "source-binding-mismatch")
    for role, content, fmt, version in bindings:
        matches = [d for d in descriptors.values() if role in d["roles"]]
        require(len(matches) == 1 and matches[0]["content_digest"] == content, "source-binding-mismatch")
        require((matches[0]["format"], matches[0]["format_version"]) == (fmt, version), "source-binding-mismatch")
    document = None
    if request["evidence"] in blobs:
        document = strict(blobs[request["evidence"]])
        has_backend = evidence_exchange_closure(document, descriptors)
        require(has_backend == (source["kind"] == "backend-batch"), "source-binding-mismatch")
    if source["kind"] == "no-backend":
        return sorted(missing)
    require(source["backend_contract"] == digest(pretty(backend_candidate())), "unsupported-backend-contract")
    if source["batch"] in blobs:
        batch = strict(blobs[source["batch"]])
        keys(batch, "format version scope contract subject obligation_set proof_policy executions")
        require(batch["format"] == "axiom-evidence-backend-batch" and batch["version"] == "0.2", "unsupported-version")
        require(batch["scope"] == "simulation" and batch["contract"] == source["backend_contract"], "source-binding-mismatch")
        if document is not None:
            validate_batch_inventory(batch, document, blobs)
    return sorted(missing)


def validate_batch_inventory(batch, document, blobs):
    require(batch["subject"] == document["subject"]["ir_document_digest"], "batch-subject-mismatch")
    pin(batch["obligation_set"])
    require(batch["proof_policy"] in {"attestation-allowed", "certificate-required"}, "unknown-tag")
    descriptors = {d["content_digest"]: d for d in document["artifacts"]}
    require(batch["obligation_set"] in descriptors and descriptors[batch["obligation_set"]]["format"] == "axiom-obligation-set", "batch-p2-mismatch")
    runs = sorted([r for r in document["executions"] if r["definition"]["mode"] in {"p4-solver-response-v0.2", "p4-target-replay-v0.1"}], key=lambda r: int(r["definition"]["ordinal"]))
    require(bool(runs), "source-binding-mismatch")
    require(type(batch["executions"]) is list and len(batch["executions"]) == len(runs), "batch-inventory-mismatch")
    invocations = set()
    for index, (entry, row) in enumerate(zip(batch["executions"], runs, strict=True)):
        keys(entry, "execution invocation provenance request upstream")
        run = row["definition"]
        inputs = {v["role"]: v["artifact"] for v in run["inputs"]}
        pin(entry["invocation"])
        require(entry["invocation"] not in invocations, "batch-invocation-mismatch")
        invocations.add(entry["invocation"])
        require(entry["execution"] == row["id"] and entry["provenance"] == run["provenance"] and entry["request"] == inputs["request"], "batch-entry-mismatch")
        require(inputs["obligation-set"] == batch["obligation_set"], "batch-p2-mismatch")
        if run["mode"] == "p4-solver-response-v0.2":
            require(entry["upstream"] == {"kind": "none"}, "batch-upstream-mismatch")
        else:
            require(index > 0, "batch-upstream-mismatch")
            parent, previous = runs[index - 1], batch["executions"][index - 1]
            require(entry["upstream"] == {"kind": "solve", "execution": parent["id"]}
                    and parent["definition"]["mode"] == "p4-solver-response-v0.2"
                    and parent["definition"]["obligation"] == run["obligation"]
                    and previous["request"] == entry["request"], "batch-upstream-mismatch")
        if entry["provenance"] in blobs:
            captured = strict(blobs[entry["provenance"]])
            name = "capture" if run["mode"] == "p4-solver-response-v0.2" else "replay_source"
            capture_contract = backend_candidate()[name]
            keys(captured, " ".join(capture_contract["members"]))
            require(captured["format"] == capture_contract["format"] and captured["version"] == capture_contract["version"]
                    and captured["scope"] == "simulation" and captured["invocation"] == entry["invocation"], "batch-source-mismatch")
            if name == "capture":
                require(captured["request"] == entry["request"] and captured["proof_policy"] == batch["proof_policy"], "batch-source-mismatch")
                keys(captured["launch"], " ".join(capture_contract["launch_members"]))
                references = [captured["observation"], *captured["launch"].values()]
                for stream in (captured["stdout"], captured["stderr"]):
                    require(type(stream) is dict and stream.get("kind") in capture_contract["streams"], "batch-source-mismatch")
                    keys(stream, " ".join(capture_contract["streams"][stream["kind"]]))
                    if stream["kind"] != "absent":
                        references.append(stream["artifact"])
            else:
                require(captured["solve_execution"] == entry["upstream"]["execution"], "batch-source-mismatch")
                references = [captured["observation"]]
            require(all(ref in descriptors for ref in references), "batch-source-artifact-missing")
            if name == "replay_source":
                replay_observation_inventory(captured, entry, run, inputs, descriptors, blobs)


def replay_observation_inventory(source, entry, run, inputs, descriptors, blobs):
    """Check structured references and production policy, not error causality."""
    def declared(content, fmt, version):
        require(content in descriptors, "interruption-artifact-missing")
        require((descriptors[content]["format"], descriptors[content]["format_version"]) == (fmt, version), "interruption-artifact-format")

    observation = source["observation"]
    terminal = source["terminal"]
    require(type(terminal) is dict and terminal.get("kind") in ("completed", "interrupted")
            and type(run["result"]) is dict and terminal["kind"] == run["result"].get("kind"),
            "interruption-source-mismatch")
    if terminal["kind"] == "completed":
        require((descriptors[observation]["format"], descriptors[observation]["format_version"])
                == ("axiom-p4-target-replay-observation", "0.1"), "replay-observation-format")
        require(run["outputs"] == [{"role": "target-replay", "artifact": observation}], "replay-observation-binding")
        if observation in blobs:
            value = strict(blobs[observation])
            require(type(value) is dict and value.get("format") == "axiom-p4-target-replay-observation"
                    and value.get("version") == "0.1", "replay-observation-format")
        return
    require(run["result"] == terminal, "interruption-source-mismatch")
    require(run["outputs"] == [], "interruption-input-binding")
    declared(observation, "axiom-evidence-replay-interruption", "0.2")
    if observation not in blobs:
        return
    value = strict(blobs[observation])
    validate_interruption(value)
    require(value["request"] == entry["request"] and value["solve_execution"] == entry["upstream"]["execution"]
            and terminal == {"kind": "interrupted", "code": value["code"]}, "interruption-source-mismatch")
    stage = value["stage"]
    expected_inputs = {"canonical-ir", "obligation-set", "request", "response"}
    if stage == "replay":
        expected_inputs |= {"model-world-candidate", "world"}
    require(set(inputs) == expected_inputs and len(run["inputs"]) == len(expected_inputs),
            "interruption-input-binding")
    declared(value["generator"], "generator-source", "0.1")
    declared(value["component_policy"], "axiom-evidence-component-policy", "0.1")
    if value["diagnostic"]["kind"] == "artifact":
        declared(value["diagnostic"]["ref"], "component-diagnostic-text", "0.1")
    if value["cause"]["kind"] == "input-error":
        blamed_role = "response" if stage == "model" else "world"
        require(value["cause"]["artifact"] == inputs[blamed_role], "interruption-input-binding")
    if value["component_policy"] in blobs:
        policy_raw = blobs[value["component_policy"]]
        interruption_policy_binding(value, policy_raw)
        policy = strict(policy_raw)
        if stage == "model":
            if entry["request"] not in blobs:
                return
            request = strict(blobs[entry["request"]])
            require(type(request) is dict and type(request.get("limits")) is dict
                    and type(request["limits"].get("component")) is dict, "component-policy-source-mismatch")
            limits = request["limits"]["component"]
            expected = [{"name": name, "unit": unit, "value": limits.get(name.replace("-", "_"))}
                        for name, unit in sorted(COMPONENT_LIMITS[stage].items())]
        else:
            expected = [v for v in run["limits"] if v["name"] in COMPONENT_LIMITS[stage]]
        require(policy["limits"] == expected, "component-policy-source-mismatch")


def wrap_packet(packet, *, native_backend=False):
    """Keep Evidence bytes; explicitly rebind synthetic batch to the new draft."""
    document = packet["document"]
    has_backend = any(row["definition"]["mode"] not in VECTORS["SPEC"]["modes"] for row in document["executions"])
    batch = copy.deepcopy(packet.get("batch"))
    candidate_raw = pretty(backend_candidate())
    if has_backend:
        version = "0.2" if native_backend else "0.1"
        contract = candidate_raw if native_backend else (HERE / "backend.json").read_bytes()
        require(type(batch) is dict and batch["version"] == version and batch["scope"] == "simulation"
                and batch["contract"] == digest(contract), "fixture-source-mismatch")
    # Existing completed replay packets need no diagnostic conversion. An old
    # Debug interruption cannot be upgraded by merely changing its version.
    for d in document["artifacts"]:
        if d["format"] == "axiom-evidence-replay-interruption":
            require(native_backend and d["format_version"] == "0.2", "interruption-conversion-required")
    if has_backend:
        batch.update(version="0.2", contract=digest(candidate_raw))
    blobs = {k: bytes.fromhex(v) for k, v in packet["blobs"].items()}
    descriptors = {d["content_digest"]: {**d, "roles": ["evidence-artifact"]} for d in document["artifacts"]}
    def add(raw, fmt, version, role):
        content = digest(raw)
        blobs[content] = raw
        if content in descriptors:
            d = descriptors[content]
            require((d["format"], d["format_version"]) == (fmt, version), "descriptor-conflict")
            d["roles"] = sorted(set(d["roles"] + [role]))
        else:
            descriptors[content] = {"content_digest": content, "byte_length": str(len(raw)), "format": fmt, "format_version": version, "roles": [role]}
        return content
    evidence = add(encode(document), "axiom-evidence", "0.2", "evidence")
    source = {"kind": "no-backend", "scope": "simulation"}
    if has_backend:
        batch_pin = add(encode(batch), "axiom-evidence-backend-batch", "0.2", "source-batch")
        contract_pin = add(candidate_raw, "axiom-evidence-backend-binding-review", "0.2", "backend-contract")
        source = {"kind": "backend-batch", "backend_contract": contract_pin, "batch": batch_pin, "scope": "simulation"}
    subject = document["subject"].get("ir_artifact", document["subject"].get("artifact"))
    descriptors[subject]["roles"] = sorted(set(descriptors[subject]["roles"] + ["subject"]))
    manifest = {"bundle_version": "0.2", "artifacts": sorted(descriptors.values(), key=lambda d: d["content_digest"])}
    request = OLD["base_request"](evidence, identity("manifest", manifest))
    request.update(request_version="0.2", checker_profile=PROFILE.copy(), source_binding=source)
    request["assurance_policy"] = {"proof_support": "attestation-allowed", "allowed_trust_categories": ["host-runtime", "production-generator", "proof-backend"]}
    # Exact measured byte budgets for an offline fixture, not solver budgets or
    # permission to change any launcher hard limits.
    for limit in request["limits"]:
        if limit["name"] == "artifact-bytes":
            limit["value"] = str(max(len(b) for b in blobs.values()))
        if limit["name"] == "bundle-bytes":
            limit["value"] = str(sum(len(b) for b in blobs.values()))
    return request, manifest, blobs


def check_packet(packet, *, native_backend=False):
    request, manifest, blobs = wrap_packet(packet, native_backend=native_backend)
    raw, manifest_raw = encode(request), encode(manifest)
    expected_request, expected_batch = digest(raw), request["source_binding"].get("batch")
    require(not bundle_binding(raw, manifest_raw, blobs, expected_request, expected_batch), "artifact-missing")
    return {"request_raw": expected_request, "request_document": identity("request", request),
            "manifest_raw": digest(manifest_raw), "manifest_document": identity("manifest", manifest),
            **({"batch_raw": expected_batch} if expected_batch is not None else {}), "evidence_raw": request["evidence"],
            "artifact_count": str(len(blobs)), "bundle_bytes": str(sum(map(len, blobs.values())))}


def companion_input(binding, raw, kind, result_kind):
    require(binding["content_digest"] == digest(raw), f"{kind}-binding-mismatch")
    try:
        value = strict(raw)
        (validate_request if kind == "request" else evidence_header)(value)
    except ValueError:
        require(result_kind == "rejected" and binding["document_digest"] == {"kind": "unavailable"}, f"{kind}-binding-mismatch")
        return None
    document_id = identity("request", value) if kind == "request" else digest(b"axiom-evidence-v0.2:document\0" + raw)
    require(binding["document_digest"] == {"kind": "available", "value": document_id}, f"{kind}-binding-mismatch")
    return value


def result_binding(result, request_raw, evidence_raw):
    """Check identity/policy of a supplied companion, never create acceptance."""
    validate_result(result)
    kind = result["result"]["kind"]
    request = companion_input(result["request"], request_raw, "request", kind)
    evidence = result["evidence"]
    unverified = [c["definition"] for c in result["checks"]
                  if "interruption-cause-unverified" in c["definition"]["codes"]]
    if "expected_content_digest" in evidence:
        require(evidence_raw is None and request is not None
                and evidence["expected_content_digest"] == request["evidence"], "evidence-binding-mismatch")
        require(not unverified, "result-reference-mismatch")
        return
    require(evidence_raw is not None, "evidence-binding-mismatch")
    if request is not None:
        expected = request["evidence"]
        require(expected not in result["missing_artifacts"]
                and not identity_check(result, "incomplete", "artifact-missing", expected), "evidence-binding-mismatch")
        mismatch = identity_check(result, "rejected", "digest-mismatch", expected)
        if evidence["content_digest"] != expected:
            require(kind == "rejected" and mismatch and not result["remaining_trust"], "evidence-binding-mismatch")
            require(not unverified, "result-reference-mismatch")
            companion_input(evidence, evidence_raw, "evidence", kind)
            return
        require(not mismatch, "evidence-binding-mismatch")
    document = companion_input(evidence, evidence_raw, "evidence", kind)
    if unverified:
        require(request is not None and document is not None, "result-reference-mismatch")
    if request is None or document is None:
        return
    trust = {row["id"]: row["definition"]["category"] for row in document["trust"]}
    require(set(result["remaining_trust"]) <= set(trust), "trust-binding-mismatch")
    if unverified:
        interruptions = {d["content_digest"] for d in document["artifacts"]
                         if (d["format"], d["format_version"]) == ("axiom-evidence-replay-interruption", "0.2")}
        for check in unverified:
            refs = {ref["ref"] for ref in check["refs"] if ref["kind"] == "artifact"}
            require(refs <= interruptions, "result-reference-mismatch")
        require(set(result["remaining_trust"]) == set(trust), "trust-binding-mismatch")
    accepted = result["result"]["kind"] in {"accepted", "accepted-with-trust"}
    if accepted:
        # This draft registers no trust discharge rule. A consumer cannot erase
        # assumptions merely by omitting their IDs from its companion result.
        require(set(result["remaining_trust"]) == set(trust), "trust-binding-mismatch")
        required = set(OLD["CHECK_KINDS"])
        require(required <= {c["definition"]["kind"] for c in result["checks"]}, "check-coverage")
        source_checks = [c["definition"] for c in result["checks"] if "source-binding" in c["definition"]["codes"]]
        source = request["source_binding"]
        source_artifacts = {source["batch"], source["backend_contract"]} if source["kind"] == "backend-batch" else {request["evidence"]}
        required_refs = [{"kind": "artifact", "ref": content} for content in source_artifacts]
        require(any(all(ref in c["refs"] for ref in required_refs) for c in source_checks), "source-binding-mismatch")
        namespaces = {"artifact": {d["content_digest"] for d in document["artifacts"]} | {request["evidence"]} | source_artifacts,
                      "request": {identity("request", request)}, "check": {c["id"] for c in result["checks"]}}
        for kind, field in (("obligation", "obligations"), ("tool", "tools"), ("trust", "trust")):
            namespaces[kind] = {v["id"] for v in document[field]}
        namespaces["evidence-entry"] = {v["id"] for field in ("tools", "executions", "obligations", "trust", "uncovered") for v in document[field]}
        for check in result["checks"]:
            for ref in check["definition"]["refs"]:
                require(ref["ref"] in namespaces[ref["kind"]], "result-reference-mismatch")
        policy = request["assurance_policy"]
        require(all(trust[t] in policy["allowed_trust_categories"] for t in result["remaining_trust"]), "trust-not-allowed")
        attested = any(row["result"].get("support", {}).get("kind") == "backend-attestation" for row in document["obligations"])
        require(not attested or policy["proof_support"] == "attestation-allowed", "attestation-not-allowed")
        require(not attested or result["result"]["kind"] == "accepted-with-trust", "result-aggregation")


PACKET_NAMES = ("correct", "pre-false", "wrong-add", "wrong-drop-zero")
STRUCTURED_PACKET_NAMES = ("model-invalid", "model-world-limit", "replay-world-limit")
HANDOFF_PACKET_NAMES = (
    "attestation", "timeout-then-attestation", "attestation-then-timeout",
    "last-compatible-attestation", "attestation-then-replay-limit",
    "missing-historical-trust", "conflicting-completed-supports",
)


def review_packet_exchange(packet, export_root=None):
    name = packet["name"]
    require(name in PACKET_NAMES, "unknown-packet")
    summary = check_packet(packet)
    if export_root is None:
        expected = json.loads((DEST / "packet-fingerprints.json").read_bytes())
        require(summary == expected[name], "exchange-fingerprint-mismatch")
    else:
        export_packet(packet, export_root, summary)
    print(f"{name}: exchange bindings matched ({summary['artifact_count']} artifacts); no independent acceptance")


def export_packet(packet, export_root, summary, *, native_backend=False):
    # Create a new directory for each fixture and keep caller pins beside it.
    name = packet["name"]
    require(name in PACKET_NAMES + STRUCTURED_PACKET_NAMES + HANDOFF_PACKET_NAMES, "unknown-packet")
    base = Path(export_root).resolve()
    tmp = (ROOT / ".tmp").resolve()
    require(base.is_relative_to(tmp) and base != tmp, "export-outside-task-temp")
    output = base / name
    output.mkdir(parents=True, exist_ok=False)
    request, manifest, blobs = wrap_packet(packet, native_backend=native_backend)
    bundle = output / "bundle"
    blob_dir = bundle / "blobs/sha256"
    blob_dir.mkdir(parents=True)
    (bundle / "request.jcs").write_bytes(encode(request))
    (bundle / "manifest.jcs").write_bytes(encode(manifest))
    for content, raw in blobs.items():
        (blob_dir / content[7:]).write_bytes(raw)
    (output / "authority.json").write_bytes(pretty(summary))
