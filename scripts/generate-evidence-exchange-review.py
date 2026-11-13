#!/usr/bin/env python3
"""物化 C1–C6 候选协议、合成向量与交接清单；不运行独立 checker。"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence_exchange_review as review


def minimal_packet():
    document, blobs = review.VECTORS["input_only_document"](stop=False)
    return {"name": "input-only", "document": document,
            "blobs": {k: v.hex() for k, v in blobs.items()}}


def protocol_result(request, evidence, kind):
    """Expected protocol shape only; synthetic checker identity, no execution."""
    raw = review.encode(evidence)
    artifact = review.digest(b"synthetic-checker-artifact-not-executed")
    request_raw = review.encode(request)
    definitions = [{"kind": k, "outcome": "passed", "codes": ["verification-checked"], "refs": []}
                   for k in review.OLD["CHECK_KINDS"]]
    source = next(d for d in definitions if d["kind"] == "identity")
    source["codes"] = ["source-binding"]
    source_artifacts = [request["source_binding"][k] for k in ("batch", "backend_contract")] if request["source_binding"]["kind"] == "backend-batch" else [request["evidence"]]
    source["refs"] = sorted([{"kind": "artifact", "ref": content} for content in source_artifacts], key=lambda r: (r["kind"], r["ref"]))
    selected = next(d for d in definitions if d["kind"] == "state-support")
    if kind != "accepted":
        selected["outcome"] = {"accepted-with-trust": "trusted", "incomplete": "incomplete", "rejected": "rejected"}[kind]
        selected["codes"] = [{"accepted-with-trust": "simulation-only", "incomplete": "source-unavailable", "rejected": "invalid-state-support"}[kind]]
        if kind == "accepted-with-trust":
            selected["refs"] = [{"kind": "trust", "ref": review.digest(b"synthetic-protocol-trust")}]
    checks = sorted([{"id": review.identity("check", d), "definition": d} for d in definitions], key=lambda r: r["id"])
    return {
        "result_version": "0.2", "scope": "simulation",
        "checker": {"name": "radishaxiom-independent-checker-go", "version": "0.0-synthetic-not-executed",
                    "artifact": artifact, "source": review.digest(b"synthetic-checker-source-not-executed"), "toolchain": "go1.26.7"},
        "request": {"content_digest": review.digest(request_raw), "document_digest": {"kind": "available", "value": review.identity("request", request)}},
        "evidence": {"content_digest": review.digest(raw), "document_digest": {"kind": "available", "value": review.digest(b"axiom-evidence-v0.2:document\0" + raw)}},
        "checks": checks, "missing_artifacts": [],
        "remaining_trust": [review.digest(b"synthetic-protocol-trust")] if kind == "accepted-with-trust" else [],
        "result": {"kind": kind, **({} if kind == "accepted" else {"refs": [review.identity("check", selected)]})},
        "tcb": [{"artifact": artifact, "category": c, "version": "0.0-synthetic-not-executed"} for c in review.OLD["REQUIRED_TCB_CATEGORIES"]],
    }


def component_policy(stage):
    return {"format": "axiom-evidence-component-policy", "version": "0.1", "stage": stage,
            "limits": [{"name": name, "unit": unit, "value": "0" if stage == "model" else "1"}
                       for name, unit in sorted(review.COMPONENT_LIMITS[stage].items())]}


def interruptions():
    cases = {}
    for stage, code, cause in [
        ("model", "component-limit", {"kind": "resource-limit", "resource": "decode-steps", "limit": "0"}),
        ("replay", "component-limit", {"kind": "resource-limit", "resource": "evaluation-steps", "limit": "1"}),
        ("model", "model-decode", {"kind": "input-error", "artifact": review.digest(b"synthetic-response"), "reason": "invalid-model"}),
        ("replay", "replay-error", {"kind": "input-error", "artifact": review.digest(b"synthetic-world"), "reason": "noncanonical-world"}),
        ("replay", "unsupported", {"kind": "unsupported", "feature": "obligation-kind"}),
        ("replay", "replay-error", {"kind": "component-error"}),
    ]:
        value = {"format": "axiom-evidence-replay-interruption", "version": "0.2", "scope": "simulation",
                 "generator": review.digest(b"synthetic-generator"), "request": review.digest(b"synthetic-request"),
                 "solve_execution": review.digest(b"synthetic-solve-id"), "stage": stage, "code": code,
                 "component_policy": review.digest(review.encode(component_policy(stage))),
                 "cause": cause, "diagnostic": {"kind": "absent"}}
        review.validate_interruption(value)
        review.interruption_policy_binding(value, review.encode(component_policy(stage)))
        cases[f"{stage}-{code}-{cause['kind']}"] = value
    return cases


def generated():
    files = {}
    for name, schema in review.schema_set().items():
        files[f"schemas/{name}.schema.json"] = review.pretty(schema)
    files["backend.json"] = review.pretty(review.backend_candidate())
    packet = minimal_packet()
    request, manifest, blobs = review.wrap_packet(packet)
    summary = review.check_packet(packet)
    files["fixtures/input-only/request.jcs"] = review.encode(request)
    files["fixtures/input-only/manifest.jcs"] = review.encode(manifest)
    for content, raw in blobs.items():
        files[f"fixtures/input-only/blobs/sha256/{content[7:]}"] = raw
    # Authority expectations are review metadata outside the untrusted bundle.
    files["input-only-authority.json"] = review.pretty(summary)
    rejected, rejected_blobs = review.VECTORS["vector"]("strict-ir-v0.2", reject="noncanonical-ir")
    review.VECTORS["check"](rejected, rejected_blobs, complete=True)
    rejected_packet = {"name": "s1-rejected", "document": rejected, "blobs": {k: v.hex() for k, v in rejected_blobs.items()}}
    rejected_request, rejected_manifest, rejected_blobs = review.wrap_packet(rejected_packet)
    files["s1-rejected-authority.json"] = review.pretty(review.check_packet(rejected_packet))
    files["fixtures/s1-rejected/request.jcs"] = review.encode(rejected_request)
    files["fixtures/s1-rejected/manifest.jcs"] = review.encode(rejected_manifest)
    for content, raw in rejected_blobs.items():
        files[f"fixtures/s1-rejected/blobs/sha256/{content[7:]}"] = raw
    for kind in ("accepted", "accepted-with-trust", "incomplete", "rejected"):
        result = protocol_result(request, packet["document"], kind)
        review.validate_result(result)
        if kind == "accepted":
            review.result_binding(result, review.encode(request), review.encode(packet["document"]))
        files[f"fixtures/protocol-results/{kind}.jcs"] = review.encode(result)
    for name, interruption in interruptions().items():
        files[f"fixtures/interruptions/{name}.jcs"] = review.encode(interruption)
    for stage in review.COMPONENT_LIMITS:
        files[f"fixtures/interruptions/{stage}-policy.jcs"] = review.encode(component_policy(stage))
    # Expected byte-level failures. Semantic/identity mutations live in the
    # test runner so all enclosing identities can be rebuilt before rejection.
    malformed = {
        "duplicate-key": b'{"a":"x","a":"y"}',
        "decoded-duplicate-key": b'{"a":"x","\\u0061":"y"}',
        "number": b'{"a":1}', "null": b'{"a":null}', "noncanonical": b'{ "a":"x"}',
        "unicode-key-order": '{"\ue000":"second","\U00010000":"first"}'.encode(),
        "surrogate": b'{"a":"\\ud800"}', "utf8": b'{"a":"\xff"}',
    }
    for name, raw in malformed.items():
        files[f"fixtures/negative/{name}.blob"] = raw
    files["fixtures/unicode.jcs"] = review.encode({"\ue000": "萝卜", "\U00010000": "first", "text": "e\u0301"})
    bound = [
        "docs/evidence/evidence-v0.2-machine-contract/contract.json",
        "docs/evidence/evidence-v0.2-machine-contract/backend.json",
        "docs/evidence/evidence-v0.2-machine-contract/backend-readback-fingerprints.json",
        "contracts/independent-check-v0.1/contract.json",
        "docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md",
        "docs/adr/0009-axiom-evidence-v0-drift-and-migration.md",
    ]
    contract = {
        "format": "axiom-independent-check-review", "version": "0.2",
        "status": "candidate-not-public-not-qualified", "scope": "simulation", "profile": review.PROFILE,
        "domains": review.DOMAINS, "certificate_profiles": [],
        "bindings": [{"path": p, "raw_sha256": review.digest((review.ROOT / p).read_bytes())} for p in bound],
        "backend_contract": review.digest(files["backend.json"]),
        "source_authority": "caller-pins-request-raw-and-batch-raw-outside-bundle",
        "source_variants": {"backend-batch": "required-for-any-backend-execution", "no-backend": "only-S1-S3-modes-no-source-roles-no-expected-batch"},
        "manifest_binding": "v0.2-domain-digest", "evidence_binding": "raw-digest",
        "completeness": "all-backend-executions-in-this-sealed-batch",
        "check_codes": {k: sorted(v) for k, v in review.CODE_REGISTRY.items()},
        "result_precedence": ["rejected", "incomplete", "accepted-with-trust", "accepted"],
        "trust_discharge_rules": [],
        "result_refs": "all-check-ids-of-selected-outcome-sorted",
        "required_check_kinds_for_acceptance": list(review.OLD["CHECK_KINDS"]),
        "interruption_schema": "schemas/interruption.schema.json",
        "interruption_conversion": "requires-new-structured-facts-never-parse-debug",
        "fixtures": {"input-only": "complete-synthetic-evidence-exchange-only",
                     "protocol-results": "shape-and-aggregation-expectations-not-checker-execution",
                     "interruptions": "structured-fact-vectors-not-observed-runs"},
        "files": [review.OLD["file_ref"](p, raw) for p, raw in sorted(files.items())],
        "generator": {"path": "scripts/generate-evidence-exchange-review.py", "version": "0.2"},
        "specification": {"path": "docs/evidence/evidence-v0.2-independent-check-review.md",
                          "raw_sha256": review.digest((review.ROOT / "docs/evidence/evidence-v0.2-independent-check-review.md").read_bytes())},
        "sources": [{"path": p, "raw_sha256": review.digest((review.ROOT / p).read_bytes())} for p in [
            "scripts/generate-evidence-exchange-review.py", "scripts/evidence_exchange_review.py",
            "scripts/test-evidence-exchange-review.py", "scripts/generate-independent-check-contracts.py",
            "docs/evidence/evidence-v0.2-machine-contract/check_vectors.py",
            "docs/evidence/evidence-v0.2-machine-contract/check_backend_readback.py",
        ]],
    }
    files["contract.json"] = review.pretty(contract)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--packet-dir", type=Path, help="with --write: import freshly exported four-packet identity summaries")
    args = parser.parse_args()
    if args.packet_dir and not args.write:
        parser.error("--packet-dir requires --write")
    files = generated()
    if args.packet_dir:
        fingerprints = {}
        legacy = json.loads((review.HERE / "backend-readback-fingerprints.json").read_bytes())
        for name in review.PACKET_NAMES:
            output = args.packet_dir / name
            summary = json.loads((output / "authority.json").read_bytes())
            bundle = output / "bundle"
            request_raw, manifest_raw = (bundle / "request.jcs").read_bytes(), (bundle / "manifest.jcs").read_bytes()
            blobs = {"sha256:" + p.name: p.read_bytes() for p in (bundle / "blobs/sha256").iterdir()}
            review.require(not review.bundle_binding(request_raw, manifest_raw, blobs, summary["request_raw"], summary["batch_raw"]), "artifact-missing")
            request, manifest = review.strict(request_raw), review.strict(manifest_raw)
            actual = {"request_raw": review.digest(request_raw), "request_document": review.identity("request", request),
                      "manifest_raw": review.digest(manifest_raw), "manifest_document": review.identity("manifest", manifest),
                      "batch_raw": request["source_binding"]["batch"], "evidence_raw": request["evidence"],
                      "artifact_count": str(len(blobs)), "bundle_bytes": str(sum(map(len, blobs.values())))}
            review.require(summary == actual and actual["evidence_raw"] == legacy[name]["artifact_digest"], "exchange-fingerprint-mismatch")
            fingerprints[name] = summary
        files["packet-fingerprints.json"] = review.pretty(fingerprints)
    packet_path = review.DEST / "packet-fingerprints.json"
    if "packet-fingerprints.json" not in files:
        review.require(packet_path.is_file(), "packet-fingerprints-required")
        files["packet-fingerprints.json"] = packet_path.read_bytes()
    fingerprints = json.loads(files["packet-fingerprints.json"])
    review.require(set(fingerprints) == set(review.PACKET_NAMES), "packet-fingerprint-set")
    legacy = json.loads((review.HERE / "backend-readback-fingerprints.json").read_bytes())
    for name, summary in fingerprints.items():
        review.require(summary["evidence_raw"] == legacy[name]["artifact_digest"], "legacy-evidence-drift")
    contract = json.loads(files["contract.json"])
    contract["files"].append(review.OLD["file_ref"]("packet-fingerprints.json", files["packet-fingerprints.json"]))
    contract["files"].sort(key=lambda row: row["path"])
    files["contract.json"] = review.pretty(contract)
    errors = []
    expected = set(files)
    if review.DEST.exists():
        actual = {str(p.relative_to(review.DEST)) for p in review.DEST.rglob("*") if p.is_file()}
        errors.extend(f"unexpected generated file: {p}" for p in sorted(actual - expected))
    for name, raw in files.items():
        path = review.DEST / name
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        elif not path.is_file() or path.read_bytes() != raw:
            errors.append(f"stale review bytes: {name}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Evidence exchange v0.2 candidate: {len(files)} generated files {'written' if args.write else 'matched'}; no checker execution")


if __name__ == "__main__":
    main()
