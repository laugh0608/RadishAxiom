"""Run the local P5 example and check its complete records and raw envelopes."""

import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import (  # noqa: E402
    CORPUS,
    MIGRATED_IR,
    ROOT,
    TASK,
    canonical_bytes,
    content_id,
    envelope,
    ir_identity,
    parse_canonical,
    raw_digest,
)

RULE = ROOT / "docs/adr/0033-p5-host-data-ir-v02-pairing.md"
PROFILE = "radishaxiom-private-p5-v0.1:tool"
JSON_LIMITS = {"max_input_bytes": "65536", "max_nesting": "64", "max_values": "4096"}
OTHER_LIMITS = {
    "fixture_json": JSON_LIMITS,
    "ir_json": JSON_LIMITS,
    "max_integer_digits": "64",
    "max_output_bytes": "65536",
    "max_precondition_checks": "256",
    "max_rows": "256",
    "max_tables": "4",
    "task_json": JSON_LIMITS,
}
WRONG = "sha256:" + "0" * 64


def reference(role, raw):
    return {"role": role, "byte_length": str(len(raw)), "content_digest": raw_digest(raw)}


def attempt_record(*, ir, task, fixture, case, slot, cap, result, output, tool, rule, task_pin):
    outputs = []
    if output is not None:
        outputs.append({
            **reference("host-input" if slot == "input" else "golden-host-output", output),
            "format": "axiom-host-data",
            "format_version": "0.2",
        })
    return {
        "format": "radishaxiom-private-p5-execution",
        "inputs": [
            reference("benchmark-task", task),
            reference("canonical-ir", ir),
            reference("fixture", fixture),
        ],
        "kind": "check-fixture",
        "limits": {**OTHER_LIMITS, "envelope_bytes": str(cap)},
        "options": {"case": case, "expected_ir": raw_digest(ir), "expected_task": task_pin, "slot": slot},
        "outputs": outputs,
        "result": result,
        "rule": rule,
        "tool": tool,
        "version": "0.1",
    }


def main(path):
    executable = Path(path).resolve(strict=True)
    assert executable.is_file() and 0 < executable.stat().st_size <= 32 * 1024 * 1024
    binary = executable.read_bytes()
    tool_pin = raw_digest(binary)
    definition = {
        "artifact": tool_pin,
        "name": "radishaxiom-p5-fixture-check",
        "roles": ["fixture-checker"],
        "version": tool_pin,
    }
    tool = {
        "definition": definition,
        "id": content_id(PROFILE, definition),
        "artifact_bytes": str(len(binary)),
    }
    ir_raw, task_raw = MIGRATED_IR.read_bytes(), TASK.read_bytes()
    ir_pin, task_pin = raw_digest(ir_raw), raw_digest(task_raw)
    version, ir_id = ir_identity(ir_raw)
    assert version == "0.2"
    rule = raw_digest(RULE.read_bytes())
    cases = {case["name"]: case for case in json.loads(task_raw)["fixtures"]}
    print("tool", len(binary), tool_pin, tool["id"])
    print("rule", rule)

    def fixture_path(case, slot):
        return CORPUS / cases[case][slot]["path"]

    def run(case, slot, cap, result, *, source=None, wanted_task=task_pin):
        if source is None:
            source = fixture_path(case, slot)
        data = source.read_bytes()
        proc = launch(case, slot, cap, source, wanted_task)
        assert not proc.stderr, proc.stderr
        record, separator, output = proc.stdout.partition(b"\n")
        assert separator
        if result["kind"] == "completed":
            assert proc.returncode == 0
            assert raw_digest(data) == cases[case][slot]["sha256"]
            expected_role = "input" if slot == "input" else "output"
            assert output == envelope("0.2", ir_id, expected_role, json.loads(data)["tables"])
        else:
            assert proc.returncode == 1 and not output
        expected = attempt_record(
            ir=ir_raw, task=task_raw, fixture=data, case=case, slot=slot, cap=cap, result=result,
            output=output or None, tool=tool, rule=rule, task_pin=wanted_task,
        )
        assert parse_canonical(record) == expected
        assert record == canonical_bytes(expected)
        print(case, slot, cap, result["kind"], result.get("code", "-"),
              raw_digest(record), raw_digest(output) if output else "-")

    def launch(case, slot, cap, source, wanted_task, wanted_tool=tool_pin):
        assert executable.read_bytes() == binary
        proc = subprocess.run(
            [str(executable), wanted_tool, str(MIGRATED_IR), ir_pin, str(TASK), wanted_task,
             case, slot, str(source), str(cap)],
            cwd=ROOT, capture_output=True, timeout=20, check=False,
        )
        assert executable.read_bytes() == binary
        return proc

    for case, slot, cap in (
        ("base", "input", 65536),
        ("base", "golden", 65536),
        ("boundary", "input", 282),
        ("boundary", "golden", 65536),
    ):
        run(case, slot, cap, {"kind": "completed"})
    invalid = json.loads(fixture_path("invalid", "input").read_bytes())
    row, = invalid["tables"][0]["rows"]
    assert row["order_id"] == "OX" and int(row["discount_cents"]) > int(row["subtotal_cents"])
    run("invalid", "input", 65536, {"kind": "invalid", "code": "fixture-precondition"})
    run("boundary", "input", 281, {"kind": "resource-exhausted", "code": "host-byte-limit"})
    run("boundary", "input", 65536, {"kind": "error", "code": "fixture-binding"},
        source=fixture_path("base", "input"))
    run("boundary", "input", 65536, {"kind": "error", "code": "task-artifact-mismatch"},
        wanted_task=WRONG)
    rejected = launch("base", "input", 65536, fixture_path("base", "input"), task_pin, WRONG)
    assert rejected.returncode == 2 and not rejected.stdout
    assert rejected.stderr == b"P5 observation: tool-digest\n"
    print("tool pin mismatch rejected before conversion")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_execution.py BUILT_EXAMPLE")
    main(sys.argv[1])
