"""Reconstruct AX-B01 P5 case observations without calling the Rust checker."""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import (  # noqa: E402
    CORPUS, MIGRATED_IR, ROOT, TASK, canonical_bytes, content_id, envelope, ir_identity,
    parse_canonical, raw_digest,
)
from verify_execution import PROFILE, RULE, attempt_record  # noqa: E402

EXPECTED_IR = "sha256:9a62d3b9397f2db664786d64ad77b848a53c46e62186edc29d2c31f665db9f2a"
EXPECTED_TASK = "sha256:94da3e83f9767aa8db3321beddbd6ff58ae834a6a7e3564621ef52fb40bb15b0"


def source(case, slot, cases):
    return CORPUS / cases[case][slot]["path"]


def reconstruct_attempt(case, slot, data, cap, cases, ir_id):
    if raw_digest(data) != cases[case][slot]["sha256"]:
        return {"kind": "error", "code": "fixture-binding"}, None
    fixture = json.loads(data)
    assert fixture["benchmark_id"] == "AX-B01" and fixture["data_version"] == "0.1"
    assert fixture["format"] == "axiom-benchmark-data"
    table, = fixture["tables"]
    assert table["name"] == ("orders" if slot == "input" else "net_orders")
    rows = table["rows"]
    keys = [r["order_id"] for r in rows]
    assert len(keys) <= 100 and keys == sorted(set(keys))
    if slot == "input":
        assert fixture["role"] == ("invalid-input" if case == "invalid" else "input")
        for row in rows:
            assert set(row) == {"order_id", "state", "discount_cents", "subtotal_cents"}
            for field in ("discount_cents", "subtotal_cents"):
                assert re.fullmatch(r"0|[1-9][0-9]*", row[field]) and int(row[field]) <= 100000
        if any(int(r["discount_cents"]) > int(r["subtotal_cents"]) for r in rows):
            return {"kind": "invalid", "code": "fixture-precondition"}, None
    else:
        assert fixture["role"] == "golden-output"
        for row in rows:
            assert set(row) == {"order_id", "net_cents"}
            assert re.fullmatch(r"0|[1-9][0-9]*", row["net_cents"]) and int(row["net_cents"]) <= 100000
    output = envelope("0.2", ir_id, "input" if slot == "input" else "output", fixture["tables"])
    if len(output) > cap:
        return {"kind": "resource-exhausted", "code": "host-byte-limit"}, None
    return {"kind": "completed"}, output


def reconstruct_case(case, data, golden, cap, *, ir, task, cases, tool, rule):
    _, ir_id = ir_identity(ir)
    lines, attempts = [], []
    final = {"kind": "completed"}
    for slot, fixture in (("input", data), ("golden", golden)):
        if fixture is None:
            final = {"kind": "error", "code": "missing-golden", "slot": "golden"}
            break
        result, output = reconstruct_attempt(case, slot, fixture, cap, cases, ir_id)
        attempt = canonical_bytes(attempt_record(
            ir=ir, task=task, fixture=fixture, case=case, slot=slot, cap=cap, result=result,
            output=output, tool=tool, rule=rule, task_pin=EXPECTED_TASK,
        ))
        lines.append(attempt)
        attempts.append({"slot": slot, "byte_length": str(len(attempt)), "content_digest": raw_digest(attempt)})
        if output is not None:
            lines.append(output)
        if result["kind"] != "completed":
            final = {**result, "slot": slot}
            break
    case_record = canonical_bytes({
        "attempts": attempts,
        "case": case,
        "expected_ir": EXPECTED_IR,
        "expected_task": EXPECTED_TASK,
        "format": "radishaxiom-private-p5-case",
        "result": final,
        "rule": rule,
        "tool": tool["id"],
        "version": "0.1",
    })
    return b"\n".join([case_record, *lines]), final


def verify_case(raw, pin, expected):
    if raw_digest(raw) != pin:
        raise ValueError("case-bundle-digest")
    if raw != expected:
        raise ValueError("case-reconstruction-mismatch")


def tool_identity(binary):
    pin = raw_digest(binary)
    definition = {
        "artifact": pin, "name": "radishaxiom-p5-fixture-check",
        "roles": ["fixture-checker"], "version": pin,
    }
    return {"definition": definition, "id": content_id(PROFILE, definition), "artifact_bytes": str(len(binary))}


def verify_tool_candidate(raw, binary, tool, rule):
    candidate = parse_canonical(raw)
    assert candidate["format"] == "radishaxiom-private-p5-case-tool-candidate"
    assert candidate["version"] == "0.1" and candidate["tool"] == tool and candidate["rule"] == rule
    assert candidate["artifact"] == {"byte_length": str(len(binary)), "content_digest": raw_digest(binary)}
    sources = candidate["source_inputs"]
    paths = [source["path"] for source in sources]
    assert paths == sorted(set(paths)) and set(candidate["compiler_inputs"]) <= set(paths)
    assert raw_digest(canonical_bytes(sources)) == candidate["source_set_digest"]
    for source in sources:
        path = ROOT / source["path"]
        assert path.is_file() and path.resolve().is_relative_to(ROOT)
        data = path.read_bytes()
        assert str(len(data)) == source["byte_length"] and raw_digest(data) == source["content_digest"]
    return candidate["source_set_digest"]


def main(path, candidate_path=None):
    exe = Path(path).resolve(strict=True)
    assert exe.is_file() and 0 < exe.stat().st_size <= 32 * 1024 * 1024
    binary = exe.read_bytes()
    tool = tool_identity(binary)
    ir, task = MIGRATED_IR.read_bytes(), TASK.read_bytes()
    assert raw_digest(ir) == EXPECTED_IR and raw_digest(task) == EXPECTED_TASK
    cases = {item["name"]: item for item in json.loads(task)["fixtures"]}
    rule = raw_digest(RULE.read_bytes())
    tool_pin = tool["definition"]["artifact"]
    print("tool", len(binary), tool_pin, tool["id"])
    print("rule", rule)
    if candidate_path is not None:
        print("source-set", verify_tool_candidate(Path(candidate_path).read_bytes(), binary, tool, rule))

    def run(label, case, golden_case, cap):
        data = source(case, "input", cases)
        golden = source(golden_case, "golden", cases) if golden_case else None
        expected, result = reconstruct_case(
            case, data.read_bytes(), golden.read_bytes() if golden else None, cap,
            ir=ir, task=task, cases=cases, tool=tool, rule=rule,
        )
        assert exe.read_bytes() == binary
        proc = subprocess.run(
            [str(exe), tool_pin, str(MIGRATED_IR), EXPECTED_IR, str(TASK), EXPECTED_TASK,
             case, "case", str(data), str(cap), str(golden) if golden else "-"],
            cwd=ROOT, capture_output=True, timeout=20, check=False,
        )
        assert exe.read_bytes() == binary
        assert not proc.stderr and proc.returncode == (0 if result["kind"] == "completed" else 1), proc.stderr
        verify_case(proc.stdout, raw_digest(proc.stdout), expected)
        lines = proc.stdout.split(b"\n")
        print(label, result["kind"], result.get("code", "-"), raw_digest(lines[0]), raw_digest(proc.stdout))
        return lines, expected

    base, _ = run("base", "base", "base", 65536)
    boundary, expected_boundary = run("boundary", "boundary", "boundary", 65536)
    run("invalid", "invalid", "boundary", 65536)
    run("resource", "boundary", "boundary", 281)
    run("missing-golden", "boundary", None, 65536)
    run("wrong-golden", "boundary", "base", 65536)
    run("boundary-exact", "boundary", "boundary", 282)

    forged = list(boundary)
    forged[3:] = base[3:]
    receipt = parse_canonical(forged[0])
    receipt["attempts"][1]["byte_length"] = str(len(forged[3]))
    receipt["attempts"][1]["content_digest"] = raw_digest(forged[3])
    forged[0] = canonical_bytes(receipt)
    forged_raw = b"\n".join(forged)
    assert forged_raw != expected_boundary
    try:
        verify_case(forged_raw, raw_digest(forged_raw), expected_boundary)
    except ValueError as error:
        assert str(error) == "case-reconstruction-mismatch"
    else:
        raise AssertionError("rehashed cross-case golden output was accepted")
    print("rehashed cross-case golden record, envelope and bundle rejected")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: verify_case.py BUILT_EXAMPLE [CANDIDATE_RECORD]")
    main(*sys.argv[1:])
