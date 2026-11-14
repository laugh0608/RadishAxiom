"""Reproduce review observations; this is not a production acceptance checker.

Read a freshly generated simulation export. Mutations stay in memory; existing
contract bytes and vector fingerprints are never rewritten. Unexpected findings
are printed for review, not blessed as accepted behavior.
"""

import argparse
import copy
import hashlib
import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REVIEW = ROOT / "docs/evidence/evidence-v0.2-machine-contract"
API = runpy.run_path(str(REVIEW / "check_backend_vectors.py"))


def check(packet, blobs, source, allowed_trust=None):
    return API["check_packet"](
        API["encode"](packet), blobs, source, source["expected-capture"],
        consumer_policy="attestation-allowed",
        allowed_trust=API["ALLOWED_TRUST"] if allowed_trust is None else allowed_trust,
    )


def replay_tool_mutation(original, field, value):
    packet, blobs, source = copy.deepcopy(original)
    replay, = [row for row in packet["executions"]
               if row["definition"]["mode"] == API["REPLAY"]]
    actor, = [row for row in packet["tools"] if row["id"] == replay["definition"]["tool"]]
    actor["definition"][field] = value
    actor["id"] = API["identity"]("tool", actor["definition"])
    replay["definition"]["tool"] = actor["id"]
    replay["id"] = API["identity"]("execution", replay["definition"])
    packet["obligation"]["result"]["execution"] = replay["id"]
    for key in ("tools", "executions"):
        packet[key].sort(key=lambda row: row["id"])
    return check(packet, blobs, source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    actual = API["checks"](args.export)
    API["require"](actual == json.loads((REVIEW / "backend-fingerprints.json").read_bytes()),
                   "baseline-fingerprints")
    source = API["load_source"](args.export, "wrong-add-sat", policy="attestation-allowed")
    packet, blobs = API["build_packet"](source)
    API["require"](check(packet, blobs, source) == "replay-bound", "probe-baseline")
    original = packet, blobs, source
    observations = []
    for name, field, value in (
        ("replay-tool-extra-member", "unexpected", "synthetic-review-marker"),
        ("replay-tool-mutable-version", "version", "latest"),
        ("replay-tool-duplicate-role", "roles", ["counterexample-replayer"] * 2),
        ("replay-tool-unknown-role", "roles", ["counterexample-replayer", "unregistered-role"]),
    ):
        observations.append({"case": name, "observed": replay_tool_mutation(original, field, value),
                             "required_by_base_contract": "reject-tool"})

    source = API["load_source"](args.export, "minimal-unknown", policy="attestation-allowed")
    packet, blobs = API["build_packet"](source)
    observations.append({"case": "unknown-with-empty-allowed-trust",
                         "observed": check(packet, blobs, source, allowed_trust=set()),
                         "trust_entries": str(len(packet["trust"])),
                         "meaning": "unknown runtime trust representation needs a decision"})

    # A second synthetic execution only tests the projection's cardinality gate.
    # It is not an authenticated retry and cannot establish history semantics.
    duplicate = copy.deepcopy(packet["executions"][0])
    duplicate["definition"]["ordinal"] = "1"
    duplicate["id"] = API["identity"]("execution", duplicate["definition"])
    packet["executions"].append(duplicate)
    packet["executions"].sort(key=lambda row: row["id"])
    try:
        outcome = check(packet, blobs, source)
    except ValueError as error:
        outcome = str(error)
    observations.append({"case": "second-execution-cardinality", "observed": outcome,
                         "meaning": "single-attempt projection; no retry acceptance tested"})

    files = [
        "docs/evidence/evidence-v0.2-machine-contract/backend.json",
        "docs/evidence/evidence-v0.2-machine-contract/contract.json",
        "docs/evidence/evidence-v0.2-machine-contract/check_backend_vectors.py",
        "docs/evidence/evidence-v0.2-machine-contract/check_vectors.py",
        "docs/evidence/evidence-v0.2-machine-contract/backend-fingerprints.json",
        "scripts/check-solver-simulation-export.py",
        "crates/solver-diagnostic-host/examples/export_simulation_observations.rs",
        "crates/axiom-ir/src/evidence_review.rs",
        "crates/axiom-ir/src/evidence_review/execution.rs",
        "crates/axiom-ir/src/evidence_review/support.rs",
        "docs/records/2026-11-13-evidence-backend-review/probe.py",
    ]
    print(json.dumps({
        "scope": "simulation-review-only-not-acceptance",
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
        "export_manifest_sha256": hashlib.sha256((args.export / "manifest.jcs").read_bytes()).hexdigest(),
        "baseline": "12 vectors matched; 16 negative cases refused",
        "observations": observations,
    }, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
