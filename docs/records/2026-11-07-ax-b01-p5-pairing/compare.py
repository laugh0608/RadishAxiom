"""Reproduce the ASCII review vectors for ADR 0033 from the locked AX-B01 corpus."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline_artifact_contracts.common import (  # noqa: E402
    canonical_bytes,
    content_id,
    parse_canonical,
    raw_digest,
)
from pipeline_artifact_contracts.validation import (  # noqa: E402
    validate_host_data_bytes,
    validate_receipt_bytes,
)


CORPUS = ROOT / "benchmarks/keyed-finite-table-v0.1"
OLD = ROOT / "contracts/pipeline-artifacts-v0.1/fixtures/minimal"
LEGACY_IR = CORPUS / "ax-b01/candidates/correct.ir.jcs"
MIGRATED_IR = ROOT / "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-correct.jcs"
TASK = CORPUS / "ax-b01/task.json"
HOST_ROLES = {"input": "input", "golden-output": "output"}


def ir_identity(raw):
    ir = parse_canonical(raw)
    return ir["ir_version"], content_id(f"axiom-ir-v{ir['ir_version']}:document", ir)


def envelope(version, document, role, tables):
    return canonical_bytes(
        {
            "format": "axiom-host-data",
            "format_version": version,
            "ir_document_digest": document,
            "role": role,
            "tables": tables,
        }
    )


def review_pair(raw, ir_raw, selected_ir_digest, source, source_ref, source_role):
    """Check the exact sample's pair and independent bytes, without producing an attempt."""
    if raw_digest(ir_raw) != selected_ir_digest:
        raise ValueError("ir-artifact-mismatch")
    version, document = ir_identity(ir_raw)
    if version != "0.2":
        raise ValueError("ir-version-mismatch")
    if raw_digest(source) != source_ref["sha256"]:
        raise ValueError("fixture-artifact-mismatch")
    data = json.loads(source)
    if data["role"] != source_role:
        raise ValueError("fixture-role-mismatch")
    proposed = parse_canonical(raw)
    if proposed["format_version"] != "0.2":
        raise ValueError("host-version-mismatch")
    if proposed["ir_document_digest"] != document:
        raise ValueError("ir-document-mismatch")
    host_role = HOST_ROLES[source_role]
    if proposed["role"] != host_role:
        raise ValueError("host-role-mismatch")
    if raw != envelope("0.2", document, host_role, data["tables"]):
        raise ValueError("fixture-replay-mismatch")


def rejects(code, fn, *args):
    try:
        fn(*args)
    except ValueError as error:
        if str(error) != code:
            raise
    else:
        raise AssertionError(f"expected {code}")
    print(f"reject {code}")


def main():
    task_raw = TASK.read_bytes()
    task = json.loads(task_raw)
    legacy, migrated = LEGACY_IR.read_bytes(), MIGRATED_IR.read_bytes()
    old_version, old_id = ir_identity(legacy)
    new_version, new_id = ir_identity(migrated)
    new_raw_id = raw_digest(migrated)
    assert (old_version, new_version) == ("0.1", "0.2")
    assert len({old_id, new_id, new_raw_id}) == 3
    assert old_id == next(c["document_digest"] for c in task["candidates"] if c["name"] == "correct")
    assert validate_host_data_bytes((OLD / "host-input.jcs").read_bytes())["ir_document_digest"] == old_id
    print("task", raw_digest(task_raw))
    print("ir 0.1", raw_digest(legacy), old_id)
    print("ir 0.2", new_raw_id, new_id)

    cases = {case["name"]: case for case in task["fixtures"]}
    samples = {}
    for case in ("base", "boundary"):
        for kind, source_role in (
            ("input", "input"),
            ("golden", "golden-output"),
        ):
            host_role = HOST_ROLES[source_role]
            source_ref = cases[case][kind]
            source = (CORPUS / source_ref["path"]).read_bytes()
            data = json.loads(source)
            tables = data["tables"]
            assert data["benchmark_id"] == task["benchmark_id"]
            old = envelope("0.1", old_id, host_role, tables)
            new = envelope("0.2", new_id, host_role, tables)
            assert validate_host_data_bytes(old)["tables"] == tables
            review_pair(new, migrated, new_raw_id, source, source_ref, source_role)
            samples[(case, kind)] = (old, new, source, source_ref, tables)
            print(f"{case}.{kind}", len(old), raw_digest(old), len(new), raw_digest(new))

    old, new, source, ref, tables = samples[("boundary", "input")]
    print("boundary.input v0.2", new.decode("ascii"))
    rejects("unsupported-version", validate_host_data_bytes, new)
    # A digest is only a string to the frozen shape checker.
    relabelled = envelope("0.1", new_id, "input", tables)
    assert validate_host_data_bytes(relabelled)["ir_document_digest"] == new_id
    print("legacy host shape checker accepts a v0.2 IR digest inside a v0.1 envelope")
    receipt = validate_receipt_bytes((OLD / "receipt.jcs").read_bytes())
    receipt["ir_version"] = "0.2"
    rejects("unsupported-version", validate_receipt_bytes, canonical_bytes(receipt))

    args = (migrated, new_raw_id, source, ref, "input")
    rejects("host-version-mismatch", review_pair, old, *args)
    rejects("ir-artifact-mismatch", review_pair, new, legacy, *args[1:])
    rejects("ir-version-mismatch", review_pair, new, legacy, raw_digest(legacy), *args[2:])
    rejects("ir-document-mismatch", review_pair, envelope("0.2", old_id, "input", tables), *args)
    rejects("ir-document-mismatch", review_pair, envelope("0.2", new_raw_id, "input", tables), *args)
    rejects("host-role-mismatch", review_pair, envelope("0.2", new_id, "output", tables), *args)
    rejects("fixture-artifact-mismatch", review_pair, new, *args[:2], source + b"\n", *args[3:])
    golden = samples[("boundary", "golden")]
    rejects("fixture-role-mismatch", review_pair, new, *args[:2], golden[2], golden[3], "input")
    base = samples[("base", "input")][1]
    # A legitimate, separately hashed output for another case fails reconstruction.
    assert raw_digest(base) != raw_digest(new)
    rejects("fixture-replay-mismatch", review_pair, base, *args)


if __name__ == "__main__":
    main()
