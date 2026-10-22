#!/usr/bin/env python3
"""独立核对 E1–E2 合成导出；不调用 Rust、Docker 或 solver，不认证来源。"""
import argparse
import hashlib
import json
import re
from pathlib import Path

MAX_FILE = 32_000_000
PROCESS = {"stdin_bytes": "1048576", "stdout_bytes": "4194304", "stderr_bytes": "65536",
           "wall_clock_ms": "6000", "working_memory_bytes": "134217728"}
ARGUMENTS = ["--safe-mode=safe", "--strict-parsing", "--force-logic=QF_UFLIA", "--lang=smt2",
             "--no-incremental", "--produce-models", "--dump-models", "--check-models",
             "--produce-proofs", "--check-proofs", "--rlimit-per=1000000", "--tlimit-per=5000"]
KINDS = ["deadline", "memory", "stdout-limit", "stderr-limit", "crash", "transport", "control",
         "interrupted", "cleanup", "missing-exit", "invalid-sequence"]
STAGES = ["plan", "create", "attach", "start", "stdin", "capture", "wait", "inspect",
          "terminate", "cleanup", "publish"]
ROLES = {"archive", "cli", "inventory", "licenses", "acceptance", "host", "context", "daemon",
         "kernel", "runtime", "image", "bootstrap", "policy"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def raw(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read(path):
    require(path.is_file() and not path.is_symlink(), f"not regular file: {path}")
    require(path.stat().st_size <= MAX_FILE, f"file budget: {path}")
    return path.read_bytes()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, f"duplicate key: {key}")
        result[key] = value
    return result


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(value[k]) for k in sorted(value, key=lambda k: k.encode("utf-16-be"))}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    require(isinstance(value, (str, bool)), "number/null outside canonical subset")
    return value


def parse(data):
    value = json.loads(data, object_pairs_hook=pairs)
    expected = json.dumps(normalized(value), ensure_ascii=False, separators=(",", ":")).encode()
    require(data == expected, "noncanonical bytes")
    return value


def decimal(value):
    require(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value), "noncanonical natural")
    return int(value)


def stream(record, cap):
    data = bytes.fromhex(record["raw_hex"])
    require(data.hex() == record["raw_hex"], "noncanonical hex")
    require(len(data) == decimal(record["captured_bytes"]) <= cap, "capture length")
    complete, exceeded = record["complete"], record["exceeded"]
    require(type(complete) is bool and type(exceeded) is bool, "stream flags")
    count = decimal(record["observed_bytes_lower_bound"])
    if exceeded:
        require(not complete and len(data) == cap and count > cap, "over-limit observation")
    else:
        require(count == len(data), "complete/prefix observed count")
    key = "full_raw_digest" if complete else "prefix_raw_digest"
    other = "prefix_raw_digest" if complete else "full_raw_digest"
    require(record.get(key) == raw(data) and other not in record, "full/prefix digest separation")
    require(record["kind"] == ("complete" if complete else "prefix"), "stream kind")
    return data


def check(directory):
    manifest = parse(read(directory / "manifest.jcs"))
    require(manifest["format"] == "axiom-solver-simulation-export" and manifest["version"] == "0.1", "manifest version")
    require(manifest["scope"] == "simulation" and manifest["real_execution"] == "blocked-E0-E3", "execution gate")
    identity_bytes = read(directory / "identity.jcs")
    identity = parse(identity_bytes)
    require(identity["format"] == "axiom-solver-simulation-identity" and identity["version"] == "0.1", "identity version")
    require(raw(identity_bytes) == manifest["identity_raw_digest"], "identity digest")
    require(identity["scope"] == "simulation" and identity["claim_status"] == "simulation-only-not-accepted-not-qualified", "identity scope")
    require(identity["platform"] == "linux-arm64" and identity["context"] == "orbstack", "identity platform/context")
    require(set(identity["materials"]) == ROLES, "material inventory")
    for material in identity["materials"].values():
        data = bytes.fromhex(material["raw_hex"])
        require(data.hex() == material["raw_hex"] and material["scope"] == "simulation", "material encoding/scope")
        require(raw(data) == material["raw_digest"] and len(data) == decimal(material["byte_length"]), "material raw")
    seen = set()
    results = []
    for row in manifest["cases"]:
        name = row["case"]
        require(re.fullmatch(r"[a-z0-9-]+", name) and name not in seen, "case name")
        seen.add(name)
        case = directory / name
        files = {kind: read(case / file) for kind, file in {
            "request": "request.jcs", "query": "query.smt2", "plan": "plan.jcs",
            "observation": "observation.jcs", "stdout": "stdout.raw", "stderr": "stderr.raw"}.items()}
        for kind, data in files.items():
            require(raw(data) == row[kind + "_raw_digest"], name + " " + kind + " digest")
        request, plan, observation = [parse(files[k]) for k in ["request", "plan", "observation"]]
        for record, kind in [(plan, "plan"), (observation, "observation")]:
            require(record["format"] == "axiom-solver-simulation-" + kind and record["version"] == "0.1", "record version")
        require(observation["source"] == "simulation-not-authenticated-capture", "capture source")
        require(row["scope"] == plan["scope"] == observation["scope"] == "simulation", "record scope")
        require(plan["real_execution"] == "blocked-E0-E3" and plan["attempts"] == "1" and plan["environment"] == [], "plan gate/attempt/environment")
        require(plan["identity_record_raw_digest"] == observation["identity_record_raw_digest"] == raw(identity_bytes), "identity binding")
        require(observation["plan_record_raw_digest"] == raw(files["plan"]), "plan binding")
        require(plan["request_raw_digest"] == observation["request_raw_digest"] == raw(files["request"]), "request binding")
        require(plan["query_raw_digest"] == observation["query_raw_digest"] == request["query"]["raw_digest"] == raw(files["query"]), "query binding")
        require(bytes.fromhex(plan["stdin_raw_hex"]) == files["query"] and bytes.fromhex(plan["request_raw_hex"]) == files["request"], "exact input bytes")
        require(plan["argument_tokens"] == request["adapter"]["argument_tokens"] == ARGUMENTS, "argv")
        require(request["limits"]["process_outer"] == PROCESS, "process limits")
        require(all(plan["limits"][k] == v for k, v in PROCESS.items()), "plan limits")
        require(plan["limits"]["semantic_steps"] == "1000000" and plan["limits"]["internal_wall_clock_ms"] == "5000" and plan["limits"]["memory_swap_max"] == "0", "internal limits")
        require(plan["archive_raw_digest"] == request["tool"]["payload_digest"] == identity["materials"]["archive"]["raw_digest"], "archive identity")
        require(plan["cli_raw_digest"] == identity["materials"]["cli"]["raw_digest"], "CLI identity")
        require(plan["acceptance_raw_digest"] == request["tool"]["acceptance_record_digest"] == identity["materials"]["acceptance"]["raw_digest"], "acceptance binding")
        require(decimal(row["query_bytes"]) == len(files["query"]) <= 1048576, "query limit")
        for kind in ["symbols", "layout"]:
            data = read(case / (kind + ".jcs"))
            parse(data)
            require(raw(data) == request[kind], kind + " binding")
        for kind, cap in [("stdout", 4194304), ("stderr", 65536), ("control_diagnostics", 65536)]:
            data = stream(observation[kind], cap)
            if kind in files:
                require(data == files[kind], kind + " captured bytes")
        failures = observation["failures"]
        order = lambda f: (decimal(f["at_ms"]), KINDS.index(f["kind"]), STAGES.index(f["stage"]))
        require(failures == sorted(failures, key=order), "failure order")
        require(len({tuple(sorted(f.items())) for f in failures}) == len(failures), "duplicate facts")
        require(all(decimal(f["at_ms"]) <= decimal(observation["elapsed_ms"]) for f in failures), "failure time")
        first = failures[0]["kind"] if failures else "none"
        primary = first if first in KINDS[:5] or first == "none" else "unavailable"
        require(observation["primary_outer"] == primary, "earliest outer failure")
        if decimal(observation["elapsed_ms"]) >= 6000:
            require(any(f["kind"] == "deadline" for f in failures), "missing deadline")
        require(all(decimal(f["at_ms"]) >= 6000 for f in failures if f["kind"] == "deadline"), "early deadline")
        eligible = (observation["started"] and observation["exit"] == {"kind": "exited", "code": "0"}
                    and observation["cleanup"] == "confirmed-empty" and not failures
                    and all(observation[k]["complete"] and not observation[k]["exceeded"]
                            for k in ["stdout", "stderr", "control_diagnostics"]))
        require(eligible == (row["status"] != "rejected-before-P4"), "P4 eligibility")
        if eligible:
            response = parse(read(case / "response.jcs"))
            require(response["request"] == raw(files["request"]) and response["outer_termination"] == "none", "P4 source")
            for kind in ["stdout", "stderr"]:
                require(response[kind]["raw_digest"] == raw(files[kind]), "P4 raw transfer")
        else:
            require(not (case / "response.jcs").exists() and not (case / "candidate.jcs").exists(), "failed capture reached P4")
        if row["status"] in ["Unsat", "Unknown"]:
            require(files["stdout"] == (row["status"].lower() + "\n").encode(), "backend status")
            require(not (case / "world.jcs").exists(), "non-sat produced world")
        if name == "exit137":
            require(observation["exit"] == {"kind": "exited", "code": "137"} and not any(f["kind"] == "memory" for f in failures), "exit137 guessed OOM")
        if name in ["oom-before-deadline", "deadline-before-oom", "deadline-with-oom"]:
            times = {f["kind"]: decimal(f["at_ms"]) for f in failures}
            require("memory" in times and "deadline" in times, "lost outer cause")
            if name == "oom-before-deadline":
                require(times["memory"] < times["deadline"] and primary == "memory", "early OOM priority")
            elif name == "deadline-before-oom":
                require(times["deadline"] < times["memory"] and primary == "deadline", "early deadline priority")
            else:
                require(times["deadline"] == times["memory"] and primary == "deadline", "tie priority")
        if name == "stdout-limit":
            require(observation["stdout"]["exceeded"] and not observation["stdout"]["complete"]
                    and len(files["stdout"]) == 4194304 and observation["stdout"]["observed_bytes_lower_bound"] == "4194305"
                    and observation["stderr"]["complete"] and primary == "stdout-limit", "prefix boundary")
        results.append({"case": name, "status": row["status"], "primary_outer": primary, "query_bytes": row["query_bytes"],
                        "plan_raw_digest": raw(files["plan"]), "observation_raw_digest": raw(files["observation"])})
    require({"minimal-sat", "composite-sat", "wrong-add-sat", "minimal-unsat", "minimal-unknown", "cleanup-failure", "exit137",
             "stdout-limit", "oom-before-deadline", "deadline-before-oom", "deadline-with-oom"} == seen, "acceptance cases")
    wrong = directory / "wrong-add-sat"
    query = read(wrong / "query.smt2")
    require(len(query) == 962642 and raw(query) == "sha256:5ba58e0d9754c3448f299ce4d9be2060c2d91d829253ec3e4a170e0d4d07a85a", "original capacity target")
    require(len(re.findall(rb"\(declare-const ", query)) == 501, "free symbol count")
    world = parse(read(wrong / "world.jcs"))
    require(len(world) == 1 and world[0]["interface"] == "orders" and len(world[0]["rows"]) == 3, "finite world")
    values = [{f["name"]: f["value"] for f in row["fields"]} for row in world[0]["rows"]]
    require(len({v["order_id"]["value"] for v in values}) == 3, "primary keys")
    require(all(0 <= int(v["discount_cents"]["value"]) <= int(v["subtotal_cents"]["value"]) for v in values), "finite Pre")
    settled = [v for v in values if v["state"]["member"] == "settled"]
    require(len(settled) == 2 and any(int(v["subtotal_cents"]["value"]) + int(v["discount_cents"]["value"]) != int(v["subtotal_cents"]["value"]) - int(v["discount_cents"]["value"]) for v in settled), "wrong-add witness")
    replay = parse(read(wrong / "replay.jcs"))
    require(replay["result"]["kind"] == "target-violated" and replay["binding"]["obligation"] == "sha256:4916b2ef17b43cab21bff8ae87433922c60fbf86fb72fc52972e06964584476e", "exact replay target")
    for field, filename in [("candidate", "candidate.jcs"), ("response", "response.jcs"), ("request", "request.jcs")]:
        require(replay["source"][field] == raw(read(wrong / filename)), "replay source chain")
    require(replay["world_raw_digest"] == raw(read(wrong / "world.jcs")), "replay world")
    return {"format": "axiom-solver-simulation-independent-check", "version": "0.1", "scope": "simulation",
            "real_execution": "blocked-E0-E3", "manifest_raw_digest": raw(read(directory / "manifest.jcs")),
            "cases": results, "wrong_add_finite_check": "passed-not-proof"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.directory)
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(1, f"simulation export rejected: {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
