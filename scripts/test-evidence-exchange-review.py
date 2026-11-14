#!/usr/bin/env python3
"""候选交换边界的正反例；不提供独立语义或真实来源验收。"""
import copy
import json
import os
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence_exchange_review as r

G = runpy.run_path(str(Path(__file__).with_name("generate-evidence-exchange-review.py")))


def packet_negative_checks(packet, *, native_backend=False):
    """Rebind synthetic outer IDs so each case reaches its intended boundary."""
    request, manifest, blobs = r.wrap_packet(packet, native_backend=native_backend)
    original_batch = request["source_binding"]["batch"]
    base = r.strict(blobs[original_batch])
    r.require(len(base["executions"]) >= 2, "packet-needs-solve-replay")
    cases = [
        ("history-delete", "batch-inventory-mismatch"),
        ("history-order", "batch-entry-mismatch"),
        ("invocation", "batch-invocation-mismatch"),
        ("unique-invocation", "batch-source-mismatch"),
        ("production-policy", "batch-source-mismatch"),
        ("request", "batch-entry-mismatch"),
        ("provenance", "batch-entry-mismatch"),
        ("upstream", "batch-upstream-mismatch"),
        ("subject", "batch-subject-mismatch"),
        ("p2", "batch-p2-mismatch"),
    ]
    for name, expected in cases:
        batch = copy.deepcopy(base)
        if name == "history-delete":
            batch["executions"].pop()
        elif name == "history-order":
            batch["executions"][:2] = reversed(batch["executions"][:2])
        elif name == "invocation":
            batch["executions"][1]["invocation"] = batch["executions"][0]["invocation"]
        elif name == "unique-invocation":
            batch["executions"][0]["invocation"] = r.digest(b"unique-but-not-captured-invocation")
        elif name == "production-policy":
            batch["proof_policy"] = "certificate-required"
        elif name in {"request", "provenance"}:
            batch["executions"][0][name] = r.digest(b"wrong-source-binding")
        elif name == "upstream":
            batch["executions"][1]["upstream"]["execution"] = r.digest(b"different-solve")
        else:
            batch["subject" if name == "subject" else "obligation_set"] = r.digest(b"different-subject-or-p2")
        raw = r.encode(batch)
        new_pin = r.digest(raw)
        changed_blobs = {k: v for k, v in blobs.items() if k != original_batch}
        changed_blobs[new_pin] = raw
        changed_manifest = copy.deepcopy(manifest)
        descriptor = next(d for d in changed_manifest["artifacts"] if d["content_digest"] == original_batch)
        descriptor.update(content_digest=new_pin, byte_length=str(len(raw)))
        changed_manifest["artifacts"].sort(key=lambda d: d["content_digest"])
        changed_request = copy.deepcopy(request)
        changed_request["source_binding"]["batch"] = new_pin
        changed_request["bundle_manifest"] = r.identity("manifest", changed_manifest)
        next(v for v in changed_request["limits"] if v["name"] == "bundle-bytes")["value"] = str(sum(map(len, changed_blobs.values())))
        request_raw = r.encode(changed_request)
        try:
            r.bundle_binding(request_raw, r.encode(changed_manifest), changed_blobs, r.digest(request_raw), new_pin)
        except r.Error as error:
            r.require(error.code == expected, f"wrong-negative-boundary-{name}:{error.code}")
        else:
            raise AssertionError(f"accepted {name} after rebinding synthetic outer identities")
    no_source = copy.deepcopy(request)
    no_source["source_binding"] = {"kind": "no-backend", "scope": "simulation"}
    no_manifest = copy.deepcopy(manifest)
    removed = {d["content_digest"] for d in no_manifest["artifacts"] if set(d["roles"]) & {"source-batch", "backend-contract"}}
    no_manifest["artifacts"] = [d for d in no_manifest["artifacts"] if d["content_digest"] not in removed]
    no_source["bundle_manifest"] = r.identity("manifest", no_manifest)
    no_blobs = {k: v for k, v in blobs.items() if k not in removed}
    raw = r.encode(no_source)
    try:
        r.bundle_binding(raw, r.encode(no_manifest), no_blobs, r.digest(raw), None)
    except r.Error as error:
        r.require(error.code == "source-binding-mismatch", "wrong-no-backend-boundary")
    else:
        raise AssertionError("backend executions hidden by no-backend branch")
    missing_source = copy.deepcopy(packet)
    capture = r.strict(bytes.fromhex(packet["blobs"][packet["batch"]["executions"][0]["provenance"]]))
    host = capture["launch"]["host"]
    missing_source["document"]["artifacts"] = [d for d in missing_source["document"]["artifacts"] if d["content_digest"] != host]
    del missing_source["blobs"][host]
    try:
        r.check_packet(missing_source, native_backend=native_backend)
    except r.Error as error:
        r.require(error.code == "batch-source-artifact-missing", "wrong-capture-closure-boundary")
    else:
        raise AssertionError("capture host hidden by deleting both artifact inventories")
    return len(cases) + 2


class ExchangeReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = G["minimal_packet"]()
        cls.request, cls.manifest, cls.blobs = r.wrap_packet(cls.packet)
        cls.request_raw = r.encode(cls.request)
        cls.manifest_raw = r.encode(cls.manifest)

    def rejects(self, code, action, *args):
        with self.assertRaises(r.Error) as caught:
            action(*args)
        self.assertEqual(caught.exception.code, code)

    def bind(self, request=None, manifest=None, blobs=None, authority=None, batch=None):
        request = self.request if request is None else request
        raw = r.encode(request)
        return r.bundle_binding(raw, r.encode(self.manifest if manifest is None else manifest),
                                self.blobs if blobs is None else blobs,
                                r.digest(self.request_raw) if authority is None else authority,
                                self.request["source_binding"].get("batch") if batch is None else batch)

    def test_canonical_unicode_and_malformed_bytes(self):
        expected = '{"text":"é","𐀀":"first","\ue000":"萝卜"}'.encode()
        self.assertEqual(r.encode({"\ue000": "萝卜", "𐀀": "first", "text": "e\u0301"}), expected)
        self.assertEqual(r.encode(r.strict(expected)), expected)
        for path in sorted((r.DEST / "fixtures/negative").glob("*.blob")):
            with self.subTest(path=path.name), self.assertRaises((ValueError, UnicodeError)):
                r.strict(path.read_bytes())

    def test_legacy_contracts_and_domains_remain_separate(self):
        for kind, value, validate in [("request", self.request, r.validate_request), ("manifest", self.manifest, r.validate_manifest)]:
            self.rejects("unknown-member" if kind == "request" else "unsupported-version", r.OLD[f"validate_{kind}"], value)
            old = copy.deepcopy(value)
            old["request_version" if kind == "request" else "bundle_version"] = "0.1"
            self.rejects("unsupported-version", validate, old)
        self.assertNotEqual(r.identity("request", self.request), r.digest(self.request_raw))
        self.assertNotEqual(r.identity("manifest", self.manifest), r.digest(self.manifest_raw))

    def test_request_is_closed_and_policy_explicit(self):
        value = copy.deepcopy(self.request)
        value["source_binding"]["authority"] = "producer"
        self.rejects("unknown-member", r.validate_request, value)
        value = copy.deepcopy(self.request)
        del value["source_binding"]
        self.rejects("missing-required-member", r.validate_request, value)
        value = copy.deepcopy(self.request)
        value["source_binding"]["scope"] = "qualified"
        self.rejects("unsupported-scope", r.validate_request, value)
        value = copy.deepcopy(self.request)
        value["assurance_policy"]["allowed_trust_categories"] *= 2
        self.rejects("noncanonical-order", r.validate_request, value)

    def test_manifest_dotted_format_is_versioned(self):
        value = copy.deepcopy(self.manifest)
        value["artifacts"][0]["format"] = "axiom-smtlib2-qf-uflia-query0.3"
        r.validate_manifest(value)
        for bad in ("../query", "query..3", "Query0.3", "query_0.3", "query0.3/"):
            value["artifacts"][0]["format"] = bad
            self.rejects("unknown-tag", r.validate_manifest, value)

    def test_valid_bundle_and_missing_versus_corruption(self):
        self.assertEqual(self.bind(), [])
        missing, corrupt = sorted(self.blobs)[:2]
        blobs = dict(self.blobs)
        del blobs[missing]
        self.assertEqual(self.bind(blobs=blobs), [missing])
        blobs[corrupt] = b"!" * len(blobs[corrupt])
        self.rejects("digest-mismatch", self.bind, None, None, blobs)
        blobs[corrupt] = b"different length"
        self.rejects("length-mismatch", self.bind, None, None, blobs)

    def test_request_and_batch_authority_cannot_come_from_replacement_bundle(self):
        request = copy.deepcopy(self.request)
        request["source_binding"] = {"kind": "backend-batch", "scope": "simulation", "batch": r.digest(b"replacement-batch"), "backend_contract": r.digest(r.pretty(r.backend_candidate()))}
        self.rejects("request-authority-mismatch", self.bind, request)
        self.rejects("source-binding-mismatch", self.bind, request, None, None, r.digest(r.encode(request)))
        request = copy.deepcopy(self.request)
        request["assurance_policy"]["proof_support"] = "certificate-required"
        self.rejects("request-authority-mismatch", self.bind, request)

    def test_export_readback_uses_fixed_request_pin(self):
        fingerprint_path = r.DEST / "handoff-fingerprints.json"
        fingerprints = json.loads(fingerprint_path.read_bytes())
        fixture = "attestation"
        pin = fingerprints[fixture]
        with TemporaryDirectory() as directory:
            path = Path(directory) / fixture
            bundle = path / "bundle"
            (bundle / "blobs/sha256").mkdir(parents=True)
            (path / "authority.json").write_bytes(r.pretty({**pin, "request_raw": r.digest(b"replacement")}))
            (bundle / "request.jcs").write_bytes(b"replacement")
            (bundle / "manifest.jcs").write_bytes(b"")
            self.rejects("request-authority-mismatch", G["packet_fingerprints"], fingerprint_path,
                         r.HANDOFF_PACKET_NAMES, Path(directory), False)

    def test_manifest_domain_and_role_binding(self):
        request = copy.deepcopy(self.request)
        request["bundle_manifest"] = r.digest(self.manifest_raw)
        self.rejects("manifest-binding-mismatch", self.bind, request, None, None, r.digest(r.encode(request)))
        manifest = copy.deepcopy(self.manifest)
        manifest["artifacts"][0]["roles"] = sorted(manifest["artifacts"][0]["roles"] + ["source-batch"])
        request = copy.deepcopy(self.request)
        request["bundle_manifest"] = r.identity("manifest", manifest)
        self.rejects("source-binding-mismatch", self.bind, request, manifest, None, r.digest(r.encode(request)))

    def test_resource_length_is_checked_before_hashing_blob(self):
        content = sorted(self.blobs)[0]
        blobs = dict(self.blobs)
        blobs[content] += b"extra"
        original = r.digest
        def guarded(raw):
            self.assertNotEqual(raw, blobs[content], "oversized blob was hashed")
            return original(raw)
        with patch.object(r, "digest", guarded):
            self.rejects("length-mismatch", self.bind, None, None, blobs)
        request = copy.deepcopy(self.request)
        request["limits"][0]["value"] = "1"
        self.rejects("review-input-limit", self.bind, request, None, None, r.digest(r.encode(request)))
        self.rejects("review-input-limit", r.bundle_binding, b" " * 65537, self.manifest_raw, self.blobs, "invalid", "invalid")

    def test_new_interruption_shapes_and_cross_stage_rejection(self):
        for name, value in G["interruptions"]().items():
            with self.subTest(name=name):
                r.validate_interruption(r.strict(r.encode(value)))
                old = copy.deepcopy(value)
                old["version"] = "0.1"
                self.rejects("unsupported-version", r.validate_interruption, old)
                old = copy.deepcopy(value)
                old["detail"] = "Rust Debug must not decide semantics"
                self.rejects("unknown-member", r.validate_interruption, old)
        value = G["interruptions"]()["model-component-limit-resource-limit"]
        value["cause"]["resource"] = "evaluation-steps"
        self.rejects("cause-mismatch", r.validate_interruption, value)
        value["cause"]["resource"] = "decode-steps"
        value["code"] = "model-decode"
        self.rejects("cause-mismatch", r.validate_interruption, value)

    def test_old_debug_diagnostic_cannot_be_relabelled(self):
        packet = copy.deepcopy(self.packet)
        packet["document"]["artifacts"][0]["format"] = "axiom-evidence-replay-interruption"
        self.rejects("interruption-conversion-required", r.wrap_packet, packet)

    def test_structure_rejection_needs_no_fabricated_ir_or_batch(self):
        document, blobs = r.VECTORS["vector"]("strict-ir-v0.2", reject="noncanonical-ir")
        r.VECTORS["check"](document, blobs, complete=True)
        packet = {"document": document, "blobs": {k: v.hex() for k, v in blobs.items()}}
        request, manifest, blobs = r.wrap_packet(packet)
        self.assertEqual(request["source_binding"], {"kind": "no-backend", "scope": "simulation"})
        raw = r.encode(request)
        self.assertEqual(r.bundle_binding(raw, r.encode(manifest), blobs, r.digest(raw), None), [])
        self.rejects("source-binding-mismatch", r.bundle_binding, raw, r.encode(manifest), blobs, r.digest(raw), r.digest(b"unexpected-batch"))

    def test_component_limit_binds_producer_policy_not_checker_budget(self):
        value = G["interruptions"]()["model-component-limit-resource-limit"]
        policy_raw = r.encode(G["component_policy"]("model"))
        r.interruption_policy_binding(value, policy_raw)
        value["cause"]["limit"] = "1"
        self.rejects("component-policy-mismatch", r.interruption_policy_binding, value, policy_raw)
        policy = G["component_policy"]("model")
        policy["limits"].pop()
        self.rejects("limit-set-mismatch", r.validate_component_policy, policy)

    def test_result_four_states_and_priority(self):
        for kind in ("accepted", "accepted-with-trust", "incomplete", "rejected"):
            result = G["protocol_result"](self.request, self.packet["document"], kind)
            r.validate_result(result)
        result = G["protocol_result"](self.request, self.packet["document"], "incomplete")
        row = result["checks"][0]
        row["definition"]["outcome"] = "rejected"
        row["id"] = r.identity("check", row["definition"])
        result["checks"].sort(key=lambda c: c["id"])
        self.rejects("result-aggregation", r.validate_result, result)
        result["result"] = {"kind": "rejected", "refs": [row["id"]]}
        r.validate_result(result)

    def test_result_identity_coverage_and_input_binding(self):
        evidence = r.encode(self.packet["document"])
        result = G["protocol_result"](self.request, self.packet["document"], "accepted")
        r.result_binding(result, self.request_raw, evidence)
        result["checks"][0]["id"] = r.digest(b"old-domain-check")
        self.rejects("check-id-mismatch", r.validate_result, result)
        result = G["protocol_result"](self.request, self.packet["document"], "accepted")
        result["checks"] = result["checks"][:-1]
        self.rejects("check-coverage", r.result_binding, result, self.request_raw, evidence)
        result = G["protocol_result"](self.request, self.packet["document"], "accepted")
        result["request"]["content_digest"] = r.digest(b"another-request")
        self.rejects("request-binding-mismatch", r.result_binding, result, self.request_raw, evidence)

    def test_policy_disagreement_does_not_rewrite_evidence(self):
        # These mutations test only companion binding/policy, not the validity
        # of a constructed proof. The full Rust fixtures test proof support.
        document = copy.deepcopy(self.packet["document"])
        trust_id = r.digest(b"synthetic-protocol-trust")
        document["trust"] = [{"id": trust_id, "definition": {"category": "proof-backend"}}]
        document["obligations"][0]["result"] = {"kind": "proved", "support": {"kind": "backend-attestation"}}
        raw = r.encode(document)
        request = copy.deepcopy(self.request)
        request["evidence"] = r.digest(raw)
        request["assurance_policy"]["proof_support"] = "certificate-required"
        result = G["protocol_result"](request, document, "accepted-with-trust")
        self.rejects("attestation-not-allowed", r.result_binding, result, r.encode(request), raw)
        request["assurance_policy"]["proof_support"] = "attestation-allowed"
        request["assurance_policy"]["allowed_trust_categories"] = []
        result = G["protocol_result"](request, document, "accepted-with-trust")
        self.rejects("trust-not-allowed", r.result_binding, result, r.encode(request), raw)
        self.assertEqual(r.encode(document), raw)

    def test_result_refs_and_unavailable_digest(self):
        result = G["protocol_result"](self.request, self.packet["document"], "accepted-with-trust")
        result["result"]["refs"] = [r.digest(b"not-a-check")]
        self.rejects("result-aggregation", r.validate_result, result)

        result = G["protocol_result"](self.request, self.packet["document"], "accepted-with-trust")
        result["remaining_trust"] = [r.digest(b"unreferenced-trust")]
        self.rejects("trust-binding-mismatch", r.validate_result, result)
        result = G["protocol_result"](self.request, self.packet["document"], "accepted")
        result["evidence"]["document_digest"] = {"kind": "unavailable"}
        self.rejects("result-aggregation", r.validate_result, result)

    def test_enclosed_evidence_version_profile_and_algorithm_are_checked(self):
        for field, changed in (("evidence_version", "0.1"), ("obligation_profile", {"name": "keyed-finite-table-verification", "version": "0.1"}), ("digest_algorithm", "sha-512")):
            packet = copy.deepcopy(self.packet)
            packet["document"][field] = changed
            request, manifest, blobs = r.wrap_packet(packet)
            raw = r.encode(request)
            with self.subTest(field=field):
                self.rejects("evidence-version-profile", r.bundle_binding, raw, r.encode(manifest), blobs, r.digest(raw), None)

    def test_manifest_cannot_hide_an_evidence_artifact(self):
        manifest, blobs = copy.deepcopy(self.manifest), dict(self.blobs)
        content = next(d["content_digest"] for d in manifest["artifacts"] if d["roles"] == ["evidence-artifact"])
        manifest["artifacts"] = [d for d in manifest["artifacts"] if d["content_digest"] != content]
        del blobs[content]
        request = copy.deepcopy(self.request)
        request["bundle_manifest"] = r.identity("manifest", manifest)
        self.rejects("manifest-coverage", self.bind, request, manifest, blobs, r.digest(r.encode(request)))

    def test_source_reference_cannot_disappear_from_both_inventories(self):
        packet = copy.deepcopy(self.packet)
        content = packet["document"]["executions"][0]["definition"]["provenance"]
        packet["document"]["artifacts"] = [d for d in packet["document"]["artifacts"] if d["content_digest"] != content]
        del packet["blobs"][content]
        request, manifest, blobs = r.wrap_packet(packet)
        raw = r.encode(request)
        self.rejects("execution-artifact-missing", r.bundle_binding, raw, r.encode(manifest), blobs, r.digest(raw), None)

    def test_no_backend_requires_the_mode_contract_not_only_its_name(self):
        for field, changed in (("kind", "replay-counterexample"), ("rule", r.digest(b"other-rule"))):
            packet = copy.deepcopy(self.packet)
            row = packet["document"]["executions"][0]
            old_id = row["id"]
            row["definition"][field] = changed
            new_id = r.VECTORS["identity"]("execution", row["definition"])
            packet["document"] = json.loads(r.encode(packet["document"]).replace(old_id.encode(), new_id.encode()))
            packet["document"]["executions"].sort(key=lambda v: v["id"])
            request, manifest, blobs = r.wrap_packet(packet)
            raw = r.encode(request)
            with self.subTest(field=field):
                self.rejects("execution-mode-binding", r.bundle_binding, raw, r.encode(manifest), blobs, r.digest(raw), None)

    def test_accepted_result_cannot_erase_evidence_trust(self):
        document = copy.deepcopy(self.packet["document"])
        document["trust"] = [{"id": r.digest(b"actual-runtime-trust"), "definition": {"category": "host-runtime"}}]
        request = copy.deepcopy(self.request)
        request["evidence"] = r.digest(r.encode(document))
        result = G["protocol_result"](request, document, "accepted")
        self.rejects("trust-binding-mismatch", r.result_binding, result, r.encode(request), r.encode(document))

    def test_rejected_companion_can_bind_noncanonical_evidence(self):
        raw = b"{}\n"
        request = copy.deepcopy(self.request)
        request["evidence"] = r.digest(raw)
        result = G["protocol_result"](request, self.packet["document"], "rejected")
        result["evidence"] = {"content_digest": r.digest(raw), "document_digest": {"kind": "unavailable"}}
        r.result_binding(result, r.encode(request), raw)

    def test_missing_evidence_reports_expected_digest_without_claiming_observation(self):
        expected = self.request["evidence"]
        blobs = self.blobs.copy()
        evidence = blobs.pop(expected)
        self.assertEqual(self.bind(blobs=blobs), [expected])
        for kind in ("incomplete", "rejected"):
            result = G["missing_evidence_result"](self.request, self.packet["document"], kind)
            with self.subTest(kind=kind):
                r.result_binding(result, self.request_raw, None)
                self.rejects("evidence-binding-mismatch", r.result_binding, result, self.request_raw, evidence)
                altered = copy.deepcopy(self.request)
                altered["evidence"] = r.digest(b"another expected evidence")
                raw = r.encode(altered)
                result["request"] = {"content_digest": r.digest(raw), "document_digest": {
                    "kind": "available", "value": r.identity("request", altered)}}
                self.rejects("evidence-binding-mismatch", r.result_binding, result, raw, None)

    def test_missing_evidence_requires_a_matching_missing_diagnostic(self):
        result = G["missing_evidence_result"](self.request, self.packet["document"])
        result["missing_artifacts"] = []
        self.rejects("evidence-binding-mismatch", r.validate_result, result)
        result = G["missing_evidence_result"](self.request, self.packet["document"])
        result["evidence"]["content_digest"] = self.request["evidence"]
        self.rejects("unknown-member", r.validate_result, result)
        result = G["protocol_result"](self.request, self.packet["document"], "incomplete")
        self.rejects("evidence-binding-mismatch", r.result_binding, result, self.request_raw, None)

    def test_rejected_evidence_can_report_the_measured_wrong_digest(self):
        wrong = b"{}\n"
        expected = self.request["evidence"]
        blobs = self.blobs.copy()
        blobs[expected] = b"\x20" * len(blobs[expected])
        self.rejects("digest-mismatch", r.bundle_binding, self.request_raw, self.manifest_raw,
                     blobs, r.digest(self.request_raw), None)
        result = G["protocol_result"](self.request, self.packet["document"], "rejected")
        result["evidence"] = {"content_digest": r.digest(wrong), "document_digest": {"kind": "unavailable"}}
        self.rejects("evidence-binding-mismatch", r.result_binding, result, self.request_raw, wrong)
        row = next(c for c in result["checks"] if c["definition"]["outcome"] == "rejected")
        row["definition"] = {"kind": "identity", "outcome": "rejected", "codes": ["digest-mismatch"],
                             "refs": [{"kind": "artifact", "ref": expected}]}
        row["id"] = r.identity("check", row["definition"])
        result["checks"].sort(key=lambda c: c["id"])
        result["result"]["refs"] = [row["id"]]
        r.result_binding(result, self.request_raw, wrong)
        result["evidence"]["content_digest"] = expected
        self.rejects("evidence-binding-mismatch", r.result_binding, result, self.request_raw, wrong)

    def test_evidence_digest_diagnostic_must_match_the_supplied_bytes(self):
        evidence = self.blobs[self.request["evidence"]]
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    result = G["missing_evidence_result"](self.request, self.packet["document"], "rejected")
                else:
                    result = G["protocol_result"](self.request, self.packet["document"], "rejected")
                row = next(c for c in result["checks"] if c["definition"]["outcome"] == "rejected")
                row["definition"] = {"kind": "identity", "outcome": "rejected", "codes": ["digest-mismatch"],
                                     "refs": [{"kind": "artifact", "ref": self.request["evidence"]}]}
                row["id"] = r.identity("check", row["definition"])
                result["checks"].sort(key=lambda c: c["id"])
                result["result"]["refs"] = [row["id"]]
                self.rejects("evidence-binding-mismatch", r.result_binding, result, self.request_raw,
                             None if missing else evidence)

    def test_missing_evidence_cannot_claim_an_unverified_interruption(self):
        result = G["missing_evidence_result"](self.request, self.packet["document"])
        definition = {"kind": "state-support", "outcome": "incomplete", "codes": ["interruption-cause-unverified"],
                      "refs": [{"kind": "artifact", "ref": r.digest(b"unbound interruption")}]}
        check_id = r.identity("check", definition)
        result["checks"].append({"id": check_id, "definition": definition})
        result["checks"].sort(key=lambda c: c["id"])
        result["result"]["refs"].append(check_id)
        result["result"]["refs"].sort()
        self.rejects("result-reference-mismatch", r.result_binding, result, self.request_raw, None)

    def test_incomplete_result_cannot_reference_a_nonexistent_check(self):
        result = G["protocol_result"](self.request, self.packet["document"], "incomplete")
        row = next(c for c in result["checks"] if c["definition"]["outcome"] == "incomplete")
        row["definition"]["refs"] = [{"kind": "check", "ref": r.digest(b"missing-check")}]
        row["id"] = r.identity("check", row["definition"])
        result["checks"].sort(key=lambda c: c["id"])
        result["result"]["refs"] = [row["id"]]
        self.rejects("result-reference-mismatch", r.validate_result, result)

    def test_unverified_interruption_cause_cannot_be_used_to_accept_a_bundle(self):
        result = G["protocol_result"](self.request, self.packet["document"], "accepted")
        row = next(c for c in result["checks"] if c["definition"]["kind"] == "state-support")
        row["definition"]["codes"] = ["interruption-cause-unverified"]
        row["definition"]["refs"] = [{"kind": "artifact", "ref": r.digest(b"synthetic interruption")}]
        row["id"] = r.identity("check", row["definition"])
        result["checks"].sort(key=lambda c: c["id"])
        self.rejects("result-aggregation", r.validate_result, result)


def structured_packet_checks(packet):
    """Rust-observed synthetic errors: protocol/source checks, not independent causality."""
    expected = {
        "model-world-limit": ("model", "component-limit", "resource-limit"),
        "replay-world-limit": ("replay", "component-limit", "resource-limit"),
        "model-invalid": ("model", "model-decode", "input-error"),
    }
    r.require(packet["name"] in expected, "unknown-packet")
    stage, code, cause = expected[packet["name"]]
    summary = r.check_packet(packet, native_backend=True)
    request, manifest, blobs = r.wrap_packet(packet, native_backend=True)
    document = packet["document"]
    batch = r.strict(blobs[request["source_binding"]["batch"]])
    count = 0
    for row in document["executions"]:
        run = row["definition"]
        if run["mode"] != "p4-target-replay-v0.1":
            continue
        count += 1
        source = r.strict(blobs[run["provenance"]])
        value = r.strict(blobs[source["observation"]])
        r.require((value["stage"], value["code"], value["cause"]["kind"]) == (stage, code, cause), "unexpected-component-outcome")
        inputs = {v["role"]: v["artifact"] for v in run["inputs"]}
        expected_cause = {"kind": "resource-limit", "resource": "world-bytes", "limit": "0"} if cause == "resource-limit" else {
            "kind": "input-error", "artifact": inputs["response"], "reason": "invalid-model"}
        r.require(value["cause"] == expected_cause, "unexpected-component-outcome")
        r.require(value["diagnostic"] == {"kind": "absent"}, "unexpected-diagnostic")
        r.interruption_policy_binding(value, blobs[value["component_policy"]])
        for missing in (value["component_policy"], value["generator"]):
            partial = {k: v for k, v in blobs.items() if k != missing}
            r.require(r.bundle_binding(r.encode(request), r.encode(manifest), partial,
                                      r.digest(r.encode(request)), request["source_binding"]["batch"]) == [missing], "missing-artifact-lost")
    r.require(count == (9 if packet["name"] == "model-invalid" else 1), "unexpected-replay-count")

    entry = batch["executions"][1]
    source = r.strict(blobs[entry["provenance"]])
    observation = source["observation"]
    value = r.strict(blobs[observation])
    # An independent implementation may have the bytes and still lack causality.
    result = G["protocol_result"](request, document, "incomplete")
    result["remaining_trust"] = [row["id"] for row in document["trust"]]
    check = {"kind": "state-support", "outcome": "incomplete", "codes": ["interruption-cause-unverified"],
             "refs": [{"kind": "artifact", "ref": observation}]}
    check_id = r.identity("check", check)
    result["checks"] = [{"id": check_id, "definition": check}]
    result["result"]["refs"] = [check_id]
    evidence = blobs[request["evidence"]]
    r.result_binding(result, r.encode(request), evidence)
    result["remaining_trust"].pop()
    try:
        r.result_binding(result, r.encode(request), evidence)
    except r.Error as error:
        r.require(error.code == "trust-binding-mismatch", "wrong-unverified-interruption-trust-boundary")
    else:
        raise AssertionError("unverified causality erased historical trust")
    # Rebind the synthetic references so each mutation reaches the inventory check.
    for case, expected_code in (
        ("completed-source", "interruption-source-mismatch"),
        ("relabelled-completion", "replay-observation-format"),
        ("missing-legacy-observation", "interruption-artifact-format"),
        ("unrelated-input", "interruption-input-binding"),
        ("wrong-production-policy", "component-policy-source-mismatch"),
        ("missing-model-budget", "component-policy-source-mismatch"),
    ):
        if case == "unrelated-input" and cause != "input-error":
            continue
        if case == "missing-model-budget" and stage != "model":
            continue
        changed_document = copy.deepcopy(document)
        changed_batch = copy.deepcopy(batch)
        changed_blobs = blobs.copy()
        changed_entry = changed_batch["executions"][1]
        changed_run = next(row["definition"] for row in changed_document["executions"] if row["id"] == entry["execution"])
        changed_source = copy.deepcopy(source)
        changed_value = copy.deepcopy(value)
        if case in {"completed-source", "relabelled-completion"}:
            changed_source["terminal"] = {"kind": "completed", "outcome": "target-not-violated"}
            if case == "relabelled-completion":
                changed_run["result"] = {"kind": "completed"}
                changed_run["outputs"] = [{"role": "target-replay", "artifact": observation}]
                descriptor = next(d for d in changed_document["artifacts"] if d["content_digest"] == observation)
                descriptor.update(format="axiom-p4-target-replay-observation", format_version="0.1")
        elif case == "missing-legacy-observation":
            next(d for d in changed_document["artifacts"] if d["content_digest"] == observation)["format_version"] = "0.1"
            del changed_blobs[observation]
        elif case == "missing-model-budget":
            req = r.strict(blobs[value["request"]])
            del req["limits"]["component"]["world_bytes"]
            changed_blobs[value["request"]] = r.encode(req)
        else:
            if case == "unrelated-input":
                changed_value["cause"]["artifact"] = next(i["artifact"] for i in changed_run["inputs"] if i["role"] == "canonical-ir")
            else:
                policy = r.strict(blobs[value["component_policy"]])
                limit = next(v for v in policy["limits"] if v["name"] == "world-bytes")
                limit["value"] = str(int(limit["value"]) + 1)
                if cause == "resource-limit":
                    changed_value["cause"]["limit"] = limit["value"]
                policy_raw = r.encode(policy)
                changed_value["component_policy"] = r.digest(policy_raw)
                changed_blobs[changed_value["component_policy"]] = policy_raw
                next(d for d in changed_document["artifacts"] if d["content_digest"] == value["component_policy"])["content_digest"] = changed_value["component_policy"]
            changed_raw = r.encode(changed_value)
            changed_source["observation"] = r.digest(changed_raw)
            changed_blobs[changed_source["observation"]] = changed_raw
            next(d for d in changed_document["artifacts"] if d["content_digest"] == observation)["content_digest"] = changed_source["observation"]
        source_raw = r.encode(changed_source)
        changed_entry["provenance"] = changed_run["provenance"] = r.digest(source_raw)
        changed_blobs[changed_entry["provenance"]] = source_raw
        try:
            r.validate_batch_inventory(changed_batch, changed_document, changed_blobs)
        except r.Error as error:
            r.require(error.code == expected_code, f"wrong-interruption-boundary-{case}:{error.code}")
        else:
            raise AssertionError(f"structured inventory accepted {case}")

    try:
        r.wrap_packet(packet)
    except r.Error as error:
        r.require(str(error) == "fixture-source-mismatch", "unexpected-legacy-refusal")
    else:
        raise AssertionError("native batch was silently accepted by the legacy converter")
    negatives = packet_negative_checks(packet, native_backend=True)
    print(f"{packet['name']}: {count} Rust-observed interruptions matched structured contract; {negatives} rebound exchange mutations rejected")
    print(json.dumps({"name": packet["name"], "fingerprints": summary}, sort_keys=True))
    fingerprints = json.loads((r.HERE / "backend-structured-fingerprints.json").read_bytes())
    r.require(summary == fingerprints[packet["name"]], "structured-fingerprint-mismatch")
    export_root = os.environ.get("AXIOM_HANDOFF_REVIEW_EXPORT")
    if export_root:
        r.export_packet(packet, export_root, summary, native_backend=True)


def handoff_packet_checks(packet):
    name = packet["name"]
    r.require(name in r.HANDOFF_PACKET_NAMES, "unknown-packet")
    summary = r.check_packet(packet, native_backend=True)
    request, manifest, blobs = r.wrap_packet(packet, native_backend=True)
    raw = r.encode(request)
    wrong_batch = r.digest(b"another sealed batch")
    try:
        r.bundle_binding(raw, r.encode(manifest), blobs, summary["request_raw"], wrong_batch)
    except r.Error as error:
        r.require(error.code == "source-binding-mismatch", "wrong-external-batch-boundary")
    else:
        raise AssertionError("a mismatched external batch pin was accepted")
    export_root = os.environ.get("AXIOM_HANDOFF_REVIEW_EXPORT")
    if export_root:
        r.export_packet(packet, export_root, summary, native_backend=True)
    else:
        fingerprints = json.loads((r.DEST / "handoff-fingerprints.json").read_bytes())
        r.require(summary == fingerprints[name], "handoff-fingerprint-mismatch")
    print(f"{name}: exchange bytes checked; semantic expectation is evaluated separately")


if __name__ == "__main__":
    if sys.flags.optimize:
        raise RuntimeError("review tests require enabled assertions")
    if sys.argv[1:] == ["--structured-packet"]:
        structured_packet_checks(json.load(sys.stdin))
    elif sys.argv[1:] == ["--handoff-packet"]:
        handoff_packet_checks(json.load(sys.stdin))
    else:
        unittest.main()
