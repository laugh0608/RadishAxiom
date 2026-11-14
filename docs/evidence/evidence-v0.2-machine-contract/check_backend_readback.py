#!/usr/bin/env python3
"""独立核对候选包中的有限重放语义；不认证来源、不产生独立四态或证明。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
REPLAY = runpy.run_path(str(ROOT / "scripts/check-p4b-replay.py"))
from p4b_replay_semantics import canonical, observe


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def check(packet):
    document = packet["document"]
    blobs = {pin: bytes.fromhex(raw) for pin, raw in packet["blobs"].items()}
    assert all(digest(raw) == pin for pin, raw in blobs.items())
    ir = json.loads(blobs[document["subject"]["ir_artifact"]])
    obligations = {row["id"]: row for row in document["obligations"]}
    results = []
    kinds = set()
    for row in document["executions"]:
        run = row["definition"]
        if run["mode"] != "p4-target-replay-v0.1" or run["result"] != {"kind": "completed"}:
            continue
        inputs = {ref["role"]: ref["artifact"] for ref in run["inputs"]}
        outputs = {ref["role"]: ref["artifact"] for ref in run["outputs"]}
        obligation = obligations[run["obligation"]]
        target = obligation["definition"]
        world = json.loads(blobs[inputs["world"]])
        expected = observe(ir, REPLAY["world"](ir, world), target)
        actual = json.loads(blobs[outputs["target-replay"]])
        assert actual["result"] == expected, (target["kind"], expected, actual["result"])
        result = obligation["result"]
        if expected["kind"] == "target-violated":
            assert result["kind"] == "failed" and result["execution"] == row["id"]
            witness = result["counterexample"]
            assert witness["observed"] == expected["witness"]
            assert witness["worlds"] == [world]
            assert witness["preconditions"] == sorted(
                c["id"] for c in ir["contracts"] if c["definition"].get("role") == "assume")
            assert witness["trace"] == [
                {"kind": "obligation", "ref": run["obligation"]},
                {"kind": "replay-observation", "artifact": outputs["target-replay"]}]
        else:
            assert result == {"kind": "unknown", "reason": "indeterminate", "attempts": [row["id"]]}
        kinds.add(target["kind"])
        results.append((target["kind"], expected["kind"]))
    assert results
    failed = sorted(row["id"] for row in obligations.values() if row["result"]["kind"] == "failed")
    unknown = sorted(row["id"] for row in obligations.values() if row["result"]["kind"] == "unknown")
    expected = {"kind": "violated", "refs": failed} if failed else {"kind": "inconclusive", "refs": unknown}
    assert document["conclusion"] == expected
    name = packet["name"]
    if name in {"correct", "wrong-add", "wrong-drop-zero"}:
        assert kinds == {"numeric-range", "totality", "key-cardinality", "row-coverage", "contract-guarantee"}
        assert len(results) == 9
        assert all(outcome == "target-not-violated" for kind, outcome in results if kind != "contract-guarantee")
        assert all(outcome == ("target-not-violated" if name == "correct" else "target-violated")
                   for kind, outcome in results if kind == "contract-guarantee")
    if name == "pre-false":
        assert all(outcome == "pre-rejected" for _, outcome in results)
    return len(results)


def main():
    packet = json.load(sys.stdin)
    count = check(packet)
    mutant = copy.deepcopy(packet)
    row = next(row for row in mutant["document"]["obligations"]
               if row["definition"]["kind"] == "contract-guarantee")
    if row["result"]["kind"] == "failed":
        row["result"]["counterexample"]["observed"] = {"kind": "wrong-witness"}
    else:
        row["result"]["reason"] = "timeout"
    try:
        check(mutant)
    except AssertionError:
        pass
    else:
        raise AssertionError("disagreeing producer result accepted")
    raw = canonical(packet["document"])
    fingerprints = {
        "artifact_digest": digest(raw),
        "document_digest": digest(b"axiom-evidence-v0.2:document\0" + raw),
        "batch_digest": digest(canonical(packet["batch"])),
        "contract_digest": packet["batch"]["contract"],
    }
    expected = json.loads(Path(__file__).with_name("backend-readback-fingerprints.json").read_bytes())
    assert fingerprints == expected[packet["name"]], (packet["name"], fingerprints)
    # Separate exchange-only review; the existing Evidence bytes and finite
    # semantic expectations above remain unchanged.
    from evidence_exchange_review import review_packet_exchange
    review_packet_exchange(packet, os.environ.get("AXIOM_EXCHANGE_REVIEW_EXPORT"))
    exchange_tests = runpy.run_path(str(ROOT / "scripts/test-evidence-exchange-review.py"))
    negatives = exchange_tests["packet_negative_checks"](packet)
    print(f"{packet['name']}: {negatives} rebound exchange mutations rejected")
    print(f"{packet['name']}: {count} independent finite replay results matched; producer mismatch rejected")


if __name__ == "__main__":
    if sys.flags.optimize:
        raise RuntimeError("review checks require enabled assertions")
    main()
