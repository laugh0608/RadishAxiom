"""Check actual v0.2 P5 receipts against independently reconstructed AX-B01 material."""

import argparse
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_case import (  # noqa: E402
    EXPECTED_IR, EXPECTED_TASK, MIGRATED_IR, ROOT, RULE, TASK, canonical_bytes,
    content_id, ir_identity, parse_canonical, raw_digest, reconstruct_case, source, tool_identity,
)
from pipeline_artifact_contracts.validation import validate_receipt_bytes  # noqa: E402

PROFILE = "raxc-keyed-finite-table-pipeline-v0.2"
SEMANTICS = "sha256:a40ec7c4eecfde23a340fb61b67727b5393f01b7288d151a34168ec88a87dac7"


def identity(kind, value):
    return content_id(f"axiom-pipeline-v0.2:{kind}", value)


def attempt_entry(definition):
    basis = {key: definition[key] for key in ("inputs", "kind", "limits", "options", "rule", "tool")}
    definition["cache_key"] = identity("cache-key", basis)
    return {"id": identity("attempt", definition), "definition": definition}


def expected_receipt(case, private, final, *, ir, binary, tool, rule_bytes):
    case_bytes, *lines = private.split(b"\n")
    private_case = parse_canonical(case_bytes)
    artifacts = {}

    def add(digest, length, format_name, version):
        descriptor = {
            "byte_length": str(length), "content_digest": digest,
            "format": format_name, "format_version": version,
        }
        assert artifacts.setdefault(digest, descriptor) == descriptor
        return digest

    def reference(role, artifact):
        return {"role": role, "artifact": artifact}

    definition = tool["definition"]
    tool_id = identity("tool", definition)
    add(raw_digest(binary), len(binary), "native-executable", "0.1")
    rule = add(raw_digest(rule_bytes), len(rule_bytes), "axiom-p5-rule", "0.1")
    attempts = []
    for ordinal, ref in enumerate(private_case["attempts"]):
        attempt_raw = lines.pop(0)
        assert raw_digest(attempt_raw) == ref["content_digest"]
        attempt = parse_canonical(attempt_raw)
        inputs = []
        for item in attempt["inputs"]:
            role = item["role"]
            name, version = {
                "canonical-ir": ("axiom-ir", "0.2"),
                "benchmark-task": ("axiom-benchmark-task", "0.1"),
                "fixture": ("axiom-benchmark-data", "0.1"),
            }[role]
            inputs.append(reference(role, add(item["content_digest"], item["byte_length"], name, version)))
        outputs = []
        for item in attempt["outputs"]:
            raw = lines.pop(0)
            assert raw_digest(raw) == item["content_digest"]
            outputs.append(reference(item["role"], add(raw_digest(raw), len(raw), "axiom-host-data", "0.2")))
        attempts.append(attempt_entry({
            "inputs": inputs, "kind": "check-fixture", "limits": attempt["limits"],
            "options": attempt["options"], "ordinal": str(ordinal), "outputs": outputs,
            "result": attempt["result"], "rule": rule, "tool": tool_id,
        }))
    assert not lines
    return {
        "artifacts": [artifacts[key] for key in sorted(artifacts)],
        "attempts": attempts,
        "evidence": {"kind": "not-assembled"},
        "format": "axiom-pipeline-receipt",
        "format_version": "0.2",
        "ir": {"artifact": EXPECTED_IR, "document_id": ir_identity(ir)[1], "semantics": SEMANTICS, "version": "0.2"},
        "mode": "benchmark-node24",
        "outcome": "partial" if final["kind"] == "completed" else "blocked",
        "p5": {"attempts": [item["id"] for item in attempts], "case": case, "result": final, "task": EXPECTED_TASK},
        "pipeline_profile": PROFILE,
        "tool": {"acceptance": {"kind": "not-accepted"}, "definition": definition, "id": tool_id},
        "verification_gate": {"decision": "closed", "reason": "p6-not-evaluated"},
    }


def main(executable, schema_path):
    exe = Path(executable).resolve(strict=True)
    assert exe.is_file() and 0 < exe.stat().st_size <= 32 * 1024 * 1024
    binary = exe.read_bytes()
    tool = tool_identity(binary)
    ir, task, rule_bytes = MIGRATED_IR.read_bytes(), TASK.read_bytes(), RULE.read_bytes()
    assert raw_digest(ir) == EXPECTED_IR and raw_digest(task) == EXPECTED_TASK
    cases = {item["name"]: item for item in json.loads(task)["fixtures"]}
    validate_schema = None
    if schema_path is not None:
        from jsonschema import Draft202012Validator
        schema = json.loads(Path(schema_path).read_bytes())
        Draft202012Validator.check_schema(schema)
        validate_schema = Draft202012Validator(schema).validate

    def launch(case, golden_case, cap, mode, extra=()):
        fixture = source(case, "input", cases)
        golden = source(golden_case, "golden", cases) if golden_case else "-"
        assert exe.read_bytes() == binary
        result = subprocess.run(
            [str(exe), raw_digest(binary), str(MIGRATED_IR), EXPECTED_IR, str(TASK), EXPECTED_TASK,
             case, mode, str(fixture), str(cap), str(golden), *extra],
            cwd=ROOT, capture_output=True, timeout=20, check=False,
        )
        assert exe.read_bytes() == binary
        return result

    def check(raw, case, golden, cap, *, accepted):
        with tempfile.TemporaryDirectory(prefix="radishaxiom-receipt-") as tmp:
            path = Path(tmp) / "receipt.jcs"
            path.write_bytes(raw)
            proc = launch(case, golden, cap, "receipt-check", [str(path), raw_digest(raw)])
        assert not proc.stdout
        if accepted:
            assert proc.returncode == 0 and not proc.stderr, proc.stderr
        else:
            assert proc.returncode == 2 and b"ReceiptMismatch" in proc.stderr, proc.stderr

    def run(label, case, golden_case, cap):
        fixture = source(case, "input", cases).read_bytes()
        golden = source(golden_case, "golden", cases).read_bytes() if golden_case else None
        private, result = reconstruct_case(
            case, fixture, golden, cap, ir=ir, task=task, cases=cases, tool=tool, rule=raw_digest(rule_bytes),
        )
        expected = expected_receipt(case, private, result, ir=ir, binary=binary, tool=tool, rule_bytes=rule_bytes)
        proc = launch(case, golden_case, cap, "receipt")
        assert not proc.stderr and proc.returncode == (0 if result["kind"] == "completed" else 1)
        assert proc.stdout == canonical_bytes(expected)
        if validate_schema:
            validate_schema(parse_canonical(proc.stdout))
        check(proc.stdout, case, golden_case, cap, accepted=True)
        print(label, result["kind"], raw_digest(proc.stdout))
        return expected

    base = run("base", "base", "base", 65536)
    boundary = run("boundary", "boundary", "boundary", 65536)
    run("invalid", "invalid", "boundary", 65536)
    run("resource", "boundary", "boundary", 281)
    run("missing-golden", "boundary", None, 65536)
    run("wrong-golden", "boundary", "base", 65536)
    run("boundary-exact", "boundary", "boundary", 282)

    mixed = copy.deepcopy(boundary)
    old_golden = mixed["attempts"][1]["definition"]
    transplanted = copy.deepcopy(base["attempts"][1]["definition"])
    transplanted["options"]["case"] = "boundary"
    replacement = attempt_entry(transplanted)
    mixed["attempts"][1] = replacement
    mixed["p5"]["attempts"][1] = replacement["id"]
    retired = {old_golden["inputs"][2]["artifact"], old_golden["outputs"][0]["artifact"]}
    added = {transplanted["inputs"][2]["artifact"], transplanted["outputs"][0]["artifact"]}
    mixed["artifacts"] = sorted(
        [row for row in mixed["artifacts"] if row["content_digest"] not in retired]
        + [row for row in base["artifacts"] if row["content_digest"] in added],
        key=lambda row: row["content_digest"],
    )
    if validate_schema:
        validate_schema(mixed)
    check(canonical_bytes(mixed), "boundary", "boundary", 65536, accepted=False)

    role = copy.deepcopy(boundary)
    role["tool"]["definition"]["roles"] = ["prover"]
    role["tool"]["id"] = identity("tool", role["tool"]["definition"])
    for item in role["attempts"]:
        item["definition"]["tool"] = role["tool"]["id"]
    role["attempts"] = [attempt_entry(item["definition"]) for item in role["attempts"]]
    role["p5"]["attempts"] = [item["id"] for item in role["attempts"]]
    check(canonical_bytes(role), "boundary", "boundary", 65536, accepted=False)
    check(canonical_bytes({**boundary, "format_version": "0.1"}), "boundary", "boundary", 65536, accepted=False)
    check(canonical_bytes({**boundary, "tool": {**boundary["tool"], "acceptance": {"kind": "accepted"}}}),
          "boundary", "boundary", 65536, accepted=False)
    check(canonical_bytes({**boundary, "verification_gate": {"decision": "opened", "reason": "p5-completed"}}),
          "boundary", "boundary", 65536, accepted=False)
    old = ROOT / "contracts/pipeline-artifacts-v0.1/fixtures/minimal/receipt.jcs"
    check(old.read_bytes(), "boundary", "boundary", 65536, accepted=False)
    validate_receipt_bytes(old.read_bytes())
    try:
        validate_receipt_bytes(canonical_bytes(boundary))
    except ValueError:
        pass
    else:
        raise AssertionError("v0.1 reader accepted a v0.2 receipt")
    print("rehashed golden substitution, tool role, tool acceptance, gate and cross-version inputs rejected")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable")
    parser.add_argument("--schema")
    args = parser.parse_args()
    main(args.executable, args.schema)
