"""Read-only checks of the backend binding draft against simulation exports."""

import argparse
import copy
import json
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_vectors import ROOT, SPEC, effects, encode, entry, identity, rejects, require, strict  # noqa: E402

BACKEND = json.loads((HERE / "backend.json").read_bytes())
SIM = runpy.run_path(str(ROOT / "scripts/check-solver-simulation-export.py"))
SOLVE = "p4-solver-response-v0.2"
REPLAY = "p4-target-replay-v0.1"
REPLAY_TOOL = effects.digest(b"synthetic backend review replay executable")
ALLOWED_TRUST = {"host-runtime", "production-generator", "proof-backend"}
RULES = {
    SOLVE: effects.digest((ROOT / "docs/query/p4-request-response-model-v0.2.md").read_bytes()),
    REPLAY: effects.digest((ROOT / "docs/query/p4-concrete-target-replay-v0.1.md").read_bytes()),
}
IR_BY_CASE = {
    "minimal": ROOT / "contracts/map-filter-query-v0.1/inputs/minimal.jcs",
    "composite-sat": ROOT / "contracts/solver-model-v0.1/inputs/composite.jcs",
    "wrong-add-sat": ROOT / "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-wrong-add.jcs",
}


def refs(roles):
    return [{"role": role, "artifact": pin} for role, pin in sorted(roles.items())]


def envelope(shape, **fields):
    spec = BACKEND[shape]
    return {"format": spec["format"], "version": spec["version"], "scope": "simulation", **fields}


def terminal(shape, kind, code):
    spec = BACKEND[shape][kind]
    member = {"capture": "status", "replay_source": "outcome"}[shape] if kind == "completed" else "code"
    result = {"kind": kind, member: code}
    require(set(result) == set(spec["members"]) and code in spec.get("statuses", spec.get("codes", [])),
            "terminal-shape")
    return result


def limits(mode, record):
    if mode == SOLVE:
        outer = record["limits"]["process_outer"]
        inner = record["limits"]["tool_internal"]
        values = {
            "internal-semantic-steps": inner["semantic_steps"],
            "internal-wall-clock": inner["wall_clock_ms"],
            "outer-stderr": outer["stderr_bytes"],
            "outer-stdin": outer["stdin_bytes"],
            "outer-stdout": outer["stdout_bytes"],
            "outer-wall-clock": outer["wall_clock_ms"],
            "outer-working-memory": outer["working_memory_bytes"],
        }
    else:
        budgets = record["limits"]
        ir = budgets["ir_json"]
        values = {k.replace("_", "-"): v for k, v in budgets.items() if k != "ir_json"}
        values.update({"ir-input-bytes": ir["max_input_bytes"], "ir-nesting": ir["max_nesting"],
                       "ir-values": ir["max_values"]})
    units = BACKEND["modes"][mode]["limit_units"]
    require(values.keys() == units.keys(), "limits-shape")
    return [{"name": name, "unit": units[name], "value": values[name]} for name in sorted(values)]


def capture_terminal(observation, stdout):
    if observation["failures"]:
        first = observation["failures"][0]["kind"]
        return "interrupted", first if first in {
            "deadline", "memory", "stdout-limit", "stderr-limit", "cleanup"
        } else "protocol"
    if observation["exit"] != {"kind": "exited", "code": "0"}:
        return "interrupted", "exit"
    if observation["cleanup"] != "confirmed-empty":
        return "interrupted", "cleanup"
    if not all(observation[key]["complete"] for key in ("stdout", "stderr")):
        return "interrupted", "streams-incomplete"
    require(observation["started"], "not-started")
    tag = stdout.split(b"\n", 1)[0]
    require(tag in (b"sat", b"unsat", b"unknown"), "unsupported-vector-status")
    return "completed", tag.decode()


def counterexample(source, replay, obligation):
    assumes = sorted(row["id"] for row in source["ir"]["contracts"]
                     if row["definition"].get("role") == "assume")
    return {
        "kind": BACKEND["counterexample_kind"], "minimality": {"kind": "unreduced"},
        "observed": replay["result"]["witness"], "preconditions": assumes, "worlds": [source["world"]],
        "trace": [{"kind": "obligation", "ref": obligation},
                  {"kind": "replay-observation", "artifact": source["replay-pin"]}],
    }


def assumptions(solve, *, attested):
    rows = [
        ("host-runtime", "execution", solve["id"], "The scoped runtime and capture report the execution faithfully."),
    ]
    if attested:
        rows += [
            ("production-generator", "execution", solve["id"], "Every valid violating world has a satisfying query assignment."),
            ("proof-backend", "tool", solve["definition"]["tool"], "The scoped backend is sound for the bound unsat query."),
        ]
    return sorted((entry("trust", {"category": category, "claim": claim, "mitigations": [],
                                  "scope": {"kind": scope, "ref": pin}})
                   for category, scope, pin, claim in rows), key=lambda row: row["id"])


def load_source(directory, name, *, policy):
    """Prepare the separate simulation pins before reading a candidate packet."""
    case = directory / name
    files = {role: SIM["read"](case / filename) for role, filename in (
        ("request", "request.jcs"), ("query", "query.smt2"), ("symbols", "symbols.jcs"),
        ("layout", "layout.jcs"), ("observation", "observation.jcs"), ("stdout", "stdout.raw"),
        ("stderr", "stderr.raw"),
    )}
    request, observation = (strict(files[key]) for key in ("request", "observation"))
    ir_raw = IR_BY_CASE.get(name, IR_BY_CASE["minimal"]).read_bytes()
    ir = strict(ir_raw)
    p2 = effects.make_set(ir)
    binding = request["binding"]
    target, = (row for row in p2["obligations"] if row["id"] == binding["obligation"])
    require(binding["ir_artifact"] == effects.digest(ir_raw)
            and binding["ir_document_digest"] == p2["ir_document_digest"]
            and binding["semantics_digest"] == p2["semantics"]["sha256"]
            and binding["obligation_set_artifact"] == effects.digest(encode(p2)), "request-target")
    require(target["definition"]["kind"] in BACKEND["target_kinds"]
            and target["definition"]["expectation"] == "prove", "target-kind")
    require(request["protocol_rules"] == RULES[SOLVE]
            and request["profile"] == "axiom-p4-cvc5-1.3.4-query0.3-model-v0.1"
            and request["query"]["encoding_profile"] == "axiom-p3-map-filter-query-v0.5"
            and request["query"]["artifact_type"] == BACKEND["formats"]["query"][0], "solver-profile")
    files.update({"canonical-ir": ir_raw, "obligation-set": encode(p2)})
    kind, code = capture_terminal(observation, files["stdout"])
    if kind == "completed":
        files["response"] = SIM["read"](case / "response.jcs")
    if code == "sat":
        for role, filename in (("model-world-candidate", "candidate.jcs"),
                               ("world", "world.jcs"), ("target-replay", "replay.jcs")):
            files[role] = SIM["read"](case / filename)
    pins = {role: effects.digest(data) for role, data in files.items()}
    for role, fmt in BACKEND["formats"].items():
        if role in files and role not in ("query", "world"):
            record = strict(files[role])
            version = record["ir_version"] if role == "canonical-ir" else record.get("version", record.get("format_version"))
            require([record["format"], version] == fmt, f"artifact-format: {role}")

    identity_raw = SIM["read"](directory / "identity.jcs")
    materials = strict(identity_raw)["materials"]
    material = {key: value["raw_digest"] for key, value in materials.items()}
    launch = {
        "acceptance": material["acceptance"], "archive": material["archive"], "cli": material["cli"],
        "dependencies": material["inventory"], "host": material["host"], "policy": material["policy"],
        "qualification": effects.digest(identity_raw), "supervisor": material["bootstrap"],
    }
    # These identities and pins originate only from the validated simulation export.
    invocation = effects.digest(encode(["simulation", name, pins["observation"], policy]))
    capture = envelope("capture", invocation=invocation, launch=launch, observation=pins["observation"],
                       proof_policy=policy, request=pins["request"], terminal=terminal("capture", kind, code),
                       **{stream: {"kind": observation[stream]["kind"], "artifact": pins[stream]}
                          for stream in ("stdout", "stderr")})
    return {
        "files": files, "pins": pins, "request": request, "ir": ir, "target": target,
        "terminal": (kind, code), "capture": capture, "expected-capture": effects.digest(encode(capture)),
        "other-target": next((row for row in p2["obligations"] if row != target
                              and row["definition"]["kind"] in BACKEND["target_kinds"]), None),
        **({"world": strict(files["world"]), "replay-pin": pins["target-replay"],
            "replay-invocation": effects.digest(encode(["simulation-replay", invocation, pins["target-replay"]]))}
           if code == "sat" else {}),
    }


def tool(mode, artifact):
    kind = BACKEND["modes"][mode]["kind"]
    return entry("tool", {"name": kind, "roles": [SPEC["execution_roles"][kind]],
                          "artifact": artifact, "version": "0.1-review"})


def run(mode, source, actor, provenance, ordinal, record, state):
    spec = BACKEND["modes"][mode]
    pins = source["pins"]
    return entry("execution", {
        "kind": spec["kind"], "mode": mode, "tool": actor["id"], "rule": RULES[mode],
        "provenance": provenance, "ordinal": str(ordinal), "obligation": source["target"]["id"],
        "inputs": refs({role: pins[role] for role in spec["inputs"]}),
        "outputs": refs({role: pins[role] for role in spec["outputs"] if role in pins}),
        "result": state, "limits": limits(mode, record),
    })


def unknown(execution, code):
    return {"kind": "unknown", "attempts": [execution["id"]], "reason": BACKEND["reason_by_code"][code]}


def build_packet(source):
    pins, capture = source["pins"], source["capture"]
    capture_raw = encode(capture)
    artifacts = {effects.digest(capture_raw): capture_raw}
    actor = tool(SOLVE, capture["launch"]["cli"])
    kind, code = source["terminal"]
    state = {"kind": kind}
    if kind == "interrupted":
        state["code"] = code
    solve = run(SOLVE, source, actor, effects.digest(capture_raw), 0, source["request"], state)
    executions, tools, trust = [solve], [actor], []
    if code == "sat":
        replay = strict(source["files"]["target-replay"])
        replay_source = envelope("replay_source", invocation=source["replay-invocation"],
                                 observation=pins["target-replay"], solve_execution=solve["id"],
                                 terminal=terminal("replay_source", "completed", replay["result"]["kind"]))
        provenance = encode(replay_source)
        pin = effects.digest(provenance)
        artifacts[pin] = provenance
        actor = tool(REPLAY, REPLAY_TOOL)
        check = run(REPLAY, source, actor, pin, 1, replay, {"kind": "completed"})
        executions.append(check)
        tools.append(actor)
        if replay["result"]["kind"] == "target-violated":
            trust = assumptions(solve, attested=False)
            result = {"kind": "failed", "assumptions": [row["id"] for row in trust],
                      "execution": check["id"], "counterexample": counterexample(source, replay, source["target"]["id"])}
        else:
            result = unknown(check, replay["result"]["kind"])
    elif code == "unsat" and capture["proof_policy"] == "attestation-allowed":
        trust = assumptions(solve, attested=True)
        backend, = [row["id"] for row in trust if row["definition"]["category"] == "proof-backend"]
        result = {"kind": "proved", "assumptions": [row["id"] for row in trust],
                  "support": {"kind": "backend-attestation", "execution": solve["id"],
                              "query": pins["query"], "response": pins["response"], "trust": backend}}
    else:
        code = {"unknown": "backend-unknown", "unsat": "certificate-unavailable"}.get(code, code)
        result = unknown(solve, code)
    packet = {**{key: BACKEND[key] for key in ("format", "version")},
              "executions": sorted(executions, key=lambda row: row["id"]),
              "tools": sorted(tools, key=lambda row: row["id"]), "trust": trust,
              "obligation": {**source["target"], "result": result}}
    return packet, artifacts


def check_envelope(record, shape):
    spec = BACKEND[shape]
    require(set(record) == set(spec["members"])
            and record["format"] == spec["format"] and record["version"] == spec["version"],
            "provenance-shape")
    require(record["scope"] == "simulation", "fixture-scope")


def read_artifact(pin, artifacts):
    require(pin in artifacts, "artifact-missing")
    require(effects.digest(artifacts[pin]) == pin, "artifact-identity")
    return strict(artifacts[pin])


def check_run(row, mode, source, actor, record, ordinal):
    spec = BACKEND["modes"][mode]
    run = row["definition"]
    require(set(run) == set(SPEC["members"]["execution"]) and run["mode"] == mode
            and run["kind"] == spec["kind"] and run["ordinal"] == str(ordinal),
            "execution-mode")
    require(run["obligation"] == source["request"]["binding"]["obligation"], "execution-target")
    require(run["tool"] == actor["id"]
            and SPEC["execution_roles"][spec["kind"]] in actor["definition"]["roles"],
            "execution-role")
    require(run["rule"] == RULES[mode] and run["limits"] == limits(mode, record), "execution-rules")
    pins = source["pins"]
    require(run["inputs"] == refs({role: pins[role] for role in spec["inputs"]}), "execution-inputs")
    require(run["outputs"] == refs({role: pins[role] for role in spec["outputs"] if role in pins}),
            "execution-outputs")
    return run


def check_packet(raw, artifacts, source, expected_capture, *, consumer_policy, allowed_trust):
    """Validate the packet's references using prevalidated simulation inputs."""
    packet = strict(raw)
    require(set(packet) == set(BACKEND["packet_members"]) and all(
        packet[key] == BACKEND[key] for key in ("format", "version")), "packet-shape")
    require(consumer_policy in BACKEND["capture"]["proof_policies"], "consumer-policy")
    obligation = packet["obligation"]
    require(set(obligation) == set(SPEC["members"]["obligation_entry"]) and
            {key: obligation[key] for key in ("id", "definition")} == source["target"],
            "obligation-binding")
    for field, domain in (("executions", "execution"), ("tools", "tool"), ("trust", "trust")):
        ids = [row["id"] for row in packet[field]]
        require(ids == sorted(set(ids)), "entry-order")
        for row in packet[field]:
            require(set(row) == {"id", "definition"}
                    and row["id"] == identity(domain, row["definition"]), "entry-identity")

    executions = sorted(packet["executions"], key=lambda row: row["definition"]["ordinal"])
    kind, code = source["terminal"]
    require(len(executions) == len(packet["tools"]) == (2 if code == "sat" else 1),
            "execution-closure")
    actors = {row["id"]: row for row in packet["tools"]}
    solve = executions[0]
    request, pins = source["request"], source["pins"]
    actor = actors.get(solve["definition"]["tool"], {})
    require(actor and set(actor["definition"]) == set(SPEC["members"]["tool"]), "execution-role")
    run = check_run(solve, SOLVE, source, actor, request, 0)
    capture = read_artifact(run["provenance"], artifacts)
    check_envelope(capture, "capture")
    require(expected_capture is not None and run["provenance"] == expected_capture, "capture-authority")
    require(capture["invocation"] == source["capture"]["invocation"]
            and capture["request"] == pins["request"]
            and capture["observation"] == pins["observation"]
            and capture["proof_policy"] in BACKEND["capture"]["proof_policies"]
            and capture["terminal"] == terminal("capture", kind, code), "capture-binding")
    launch = capture["launch"]
    require(set(launch) == set(BACKEND["capture"]["launch_members"])
            and launch == source["capture"]["launch"]
            and launch["archive"] == request["tool"]["payload_digest"]
            and launch["acceptance"] == request["tool"]["acceptance_record_digest"]
            and launch["cli"] == actor["definition"]["artifact"] != launch["archive"], "launch-binding")
    for stream in ("stdout", "stderr"):
        desc = capture[stream]
        require(set(desc) == set(BACKEND["capture"]["streams"].get(desc.get("kind"), []))
                and desc == source["capture"][stream] and desc["artifact"] == pins[stream],
                "stream-binding")
    require(run["result"] == ({"kind": kind} if kind == "completed" else {"kind": kind, "code": code}),
            "execution-terminal")

    result = obligation["result"]
    require(result["kind"] in ("failed", "proved", "unknown")
            and set(result) == set(SPEC["result_members"][result["kind"]]), "result-shape")
    if code == "sat":
        replay = strict(source["files"]["target-replay"])
        replay_row = executions[1]
        replay_actor = actors.get(replay_row["definition"]["tool"], {})
        require(replay_actor and replay_actor["definition"].get("artifact") == REPLAY_TOOL, "replay-tool")
        step = check_run(replay_row, REPLAY, source, replay_actor, replay, 1)
        require(step["result"] == {"kind": "completed"}, "replay-terminal")
        provenance = read_artifact(step["provenance"], artifacts)
        check_envelope(provenance, "replay_source")
        require(provenance["solve_execution"] == solve["id"]
                and provenance["invocation"] == source["replay-invocation"] != capture["invocation"]
                and provenance["observation"] == pins["target-replay"]
                and provenance["terminal"] == terminal("replay_source", "completed", replay["result"]["kind"]),
                "replay-source")
        candidate = strict(source["files"]["model-world-candidate"])
        require(candidate["request"] == pins["request"] and candidate["response"] == pins["response"]
                and candidate["world"] == source["world"] and replay["world_raw_digest"] == pins["world"],
                "replay-world")
        binding = dict(request["binding"])
        generator = binding.pop("generator_source")
        require(replay["binding"] == {**binding, "generator": replay["binding"]["generator"]}
                and replay["source"] == {
                    "kind": "model-candidate", "request": pins["request"], "response": pins["response"],
                    "candidate": pins["model-world-candidate"], "query": pins["query"],
                    "query_profile": request["query"]["encoding_profile"], "query_generator": generator,
                } and replay["rule_digest"] == RULES[REPLAY], "replay-binding")
        if replay["result"]["kind"] != "target-violated":
            require(result == unknown(replay_row, replay["result"]["kind"]) and not packet["trust"],
                    "attempt-state")
            return "indeterminate"
        require(result["kind"] == "failed" and result["execution"] == replay_row["id"]
                and set(result["counterexample"]) == set(BACKEND["counterexample_members"])
                and result["counterexample"] == counterexample(source, replay, obligation["id"]),
                "replay-witness")
        trust = assumptions(solve, attested=False)
        require(packet["trust"] == trust and result["assumptions"] == [row["id"] for row in trust],
                "trust-binding")
        return "replay-bound" if {"host-runtime"} <= allowed_trust else "policy-incomplete"

    if code != "unsat" or capture["proof_policy"] != "attestation-allowed":
        code = {"unknown": "backend-unknown", "unsat": "certificate-unavailable"}.get(code, code)
        require(result == unknown(solve, code) and not packet["trust"], "attempt-state")
        return result["reason"]
    require(result["kind"] == "proved" and set(result["support"]) == set(BACKEND["attestation_members"]),
            "attestation-binding")
    trust = assumptions(solve, attested=True)
    require(packet["trust"] == trust and result["assumptions"] == [row["id"] for row in trust],
            "trust-binding")
    backend, = [row["id"] for row in trust if row["definition"]["category"] == "proof-backend"]
    require(result["support"] == {"kind": "backend-attestation", "execution": solve["id"],
                                  "query": pins["query"], "response": pins["response"], "trust": backend},
            "attestation-binding")
    return ("attestation-bound" if consumer_policy == "attestation-allowed" and ALLOWED_TRUST <= allowed_trust
            else "policy-incomplete")


def checks(directory):
    SIM["check"](directory)
    expected = {
        "minimal-unsat": "attestation-bound", "minimal-sat": "indeterminate",
        "minimal-unknown": "indeterminate", "wrong-add-sat": "replay-bound",
        "composite-sat": "replay-bound", "cleanup-failure": "operational-error",
        "exit137": "operational-error", "stdout-limit": "resource-exhausted",
        "oom-before-deadline": "resource-exhausted", "deadline-before-oom": "timeout",
        "deadline-with-oom": "timeout",
    }
    packets = {}
    fingerprints = {}
    for name, outcome in {**expected, "certificate-required": "incomplete-certificate"}.items():
        source = load_source(directory, "minimal-unsat" if name == "certificate-required" else name,
                             policy="certificate-required" if name == "certificate-required" else "attestation-allowed")
        packet, blobs = build_packet(source)
        raw = encode(packet)
        require(check_packet(raw, blobs, source, source["expected-capture"],
                             consumer_policy="attestation-allowed", allowed_trust=ALLOWED_TRUST) == outcome, name)
        packets[name] = (packet, blobs, source)
        fingerprints[name] = effects.digest(raw)

    def verify(packet, blobs, source):
        return check_packet(encode(packet), blobs, source, source["expected-capture"],
                            consumer_policy="attestation-allowed", allowed_trust=ALLOWED_TRUST)

    def change_provenance(packet, blobs, mode, edit):
        row, = [r for r in packet["executions"] if r["definition"]["mode"] == mode]
        definition = row["definition"]
        record = strict(blobs[definition["provenance"]])
        edit(record)
        raw = encode(record)
        definition["provenance"] = effects.digest(raw)
        blobs[definition["provenance"]] = raw
        row["id"] = identity("execution", definition)
        packet["executions"].sort(key=lambda item: item["id"])

    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    require(check_packet(encode(packet), blobs, source, source["expected-capture"],
                         consumer_policy="certificate-required", allowed_trust=ALLOWED_TRUST)
            == "policy-incomplete", "certificate-policy")
    require(check_packet(encode(packet), blobs, source, source["expected-capture"],
                         consumer_policy="attestation-allowed", allowed_trust={"proof-backend"})
            == "policy-incomplete", "remaining-trust-policy")
    rejects("capture-authority", check_packet, encode(packet), blobs, source, None,
            consumer_policy="attestation-allowed", allowed_trust=ALLOWED_TRUST)
    change_provenance(packet, blobs, SOLVE, lambda record: record.update(scope="qualified"))
    rejects("fixture-scope", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    change_provenance(packet, blobs, SOLVE, lambda record: record.update(proof_policy="certificate-required"))
    rejects("capture-authority", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    change_provenance(packet, blobs, SOLVE, lambda record: record["launch"].update(host=record["launch"]["archive"]))
    rejects("capture-authority", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    row = packet["tools"][0]
    row["definition"]["artifact"] = source["capture"]["launch"]["archive"]
    row["id"] = identity("tool", row["definition"])
    packet["executions"][0]["definition"]["tool"] = row["id"]
    packet["executions"][0]["id"] = identity("execution", packet["executions"][0]["definition"])
    rejects("launch-binding", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    row = packet["tools"][0]
    row["definition"]["roles"] = ["evidence-producer"]
    row["id"] = identity("tool", row["definition"])
    packet["executions"][0]["definition"]["tool"] = row["id"]
    packet["executions"][0]["id"] = identity("execution", packet["executions"][0]["definition"])
    rejects("execution-role", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    packet["trust"] = [row for row in packet["trust"] if row["definition"]["category"] != "production-generator"]
    packet["obligation"]["result"]["assumptions"] = [row["id"] for row in packet["trust"]]
    rejects("trust-binding", verify, packet, blobs, source)
    legacy = ROOT / "contracts/keyed-finite-table-checker-bundles-v0.1/s/chk-proof-02/bundle"
    old_request = strict((legacy / "request.jcs").read_bytes())
    old_raw = (legacy / "blobs/sha256" / old_request["evidence"].removeprefix("sha256:")).read_bytes()
    require(effects.digest(old_raw) == old_request["evidence"], "legacy-source")
    old_support = next(row["result"]["support"] for row in strict(old_raw)["obligations"]
                       if row["result"].get("support", {}).get("kind") == "backend-attestation")
    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    packet["obligation"]["result"]["support"] = old_support
    rejects("attestation-binding", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["minimal-unknown"])
    packet["obligation"]["result"]["attempts"] = []
    rejects("attempt-state", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["exit137"])
    packet["obligation"]["result"]["reason"] = "resource-exhausted"
    rejects("attempt-state", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["stdout-limit"])
    change_provenance(packet, blobs, SOLVE, lambda record: record["stdout"].update(kind="complete"))
    rejects("capture-authority", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["wrong-add-sat"])
    change_provenance(packet, blobs, REPLAY, lambda record: record.update(solve_execution=record["invocation"]))
    rejects("replay-source", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["wrong-add-sat"])
    packet["obligation"]["result"]["counterexample"]["preconditions"] = []
    rejects("replay-witness", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["wrong-add-sat"])
    packet["obligation"].update(source["other-target"])
    for row in packet["executions"]:
        row["definition"]["obligation"] = packet["obligation"]["id"]
        row["id"] = identity("execution", row["definition"])
    packet["executions"].sort(key=lambda item: item["id"])
    rejects("obligation-binding", verify, packet, blobs, source)
    packet, blobs, source = copy.deepcopy(packets["minimal-unsat"])
    pin = packet["executions"][0]["definition"]["provenance"]
    blobs[pin] += b" "
    rejects("artifact-identity", verify, packet, blobs, source)
    del blobs[pin]
    rejects("artifact-missing", verify, packet, blobs, source)
    return fingerprints


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--show-fingerprints", action="store_true")
    args = parser.parse_args()
    actual = checks(args.export)
    if args.show_fingerprints:
        print(json.dumps(actual, sort_keys=True, indent=2))
    else:
        require(actual == json.loads((HERE / "backend-fingerprints.json").read_bytes()), "packet-fingerprint")
        print("12 backend binding review vectors passed; 16 negative cases refused (simulation only)")
