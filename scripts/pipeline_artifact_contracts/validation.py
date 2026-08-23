"""Validate Pipeline Artifact Contract canonical bytes and invariants."""

import re
from typing import Any

from .builders import build_obligation_set, cache_key, semantics
from .common import (
    CANONICAL_UINT_PATTERN,
    CVC5_PROFILE,
    ContractError,
    EVIDENCE_VERSION,
    FORMAT_VERSION,
    IR_VERSION,
    NODE_INVOCATION_PROFILE,
    NODE_TARGET_PROFILE,
    OBLIGATION_EXPECTATIONS,
    OBLIGATION_KINDS,
    PIPELINE_PROFILE,
    STABLE_ID_PATTERN,
    STAGE_KINDS,
    STAGE_RESULTS,
    canonical_bytes,
    content_id,
    parse_canonical,
    require_array,
    require_digest,
    require_members,
    require_object,
    require_sorted_unique,
)

def validate_semantics(value: Any) -> None:
    item = require_object(value)
    require_members(item, {"name", "sha256"})
    if item != semantics():
        raise ContractError("semantics-mismatch")


def validate_subject(value: Any) -> None:
    item = require_object(value, "invalid-subject")
    kind = item.get("kind")
    if kind in {"document", "program"}:
        require_members(item, {"ir_document_digest", "kind"})
        require_digest(item["ir_document_digest"])
        return
    if kind in {"node", "contract"}:
        require_members(item, {"id", "kind"})
        require_digest(item["id"])
        return
    if kind in {"node-path", "contract-path"}:
        require_members(item, {"id", "kind", "path"})
        require_digest(item["id"])
        path = require_array(item["path"], "invalid-subject")
        if not path or not all(isinstance(part, str) and part for part in path):
            raise ContractError("invalid-subject")
        return
    if kind == "interface":
        require_members(item, {"direction", "kind", "name"})
        if item["direction"] not in {"input", "output"}:
            raise ContractError("invalid-subject")
        if not isinstance(item["name"], str) or not item["name"]:
            raise ContractError("invalid-subject")
        return
    if kind == "field":
        require_members(item, {"direction", "interface", "kind", "name"})
        if item["direction"] not in {"input", "output"}:
            raise ContractError("invalid-subject")
        if not all(isinstance(item[key], str) and item[key] for key in ("interface", "name")):
            raise ContractError("invalid-subject")
        return
    if kind == "artifact":
        require_members(item, {"artifact", "kind"})
        require_digest(item["artifact"])
        return
    if kind == "trust":
        require_members(item, {"category", "kind", "scope"})
        if not all(isinstance(item[key], str) and item[key] for key in ("category", "scope")):
            raise ContractError("invalid-subject")
        return
    raise ContractError("invalid-subject")


def validate_obligation_set_bytes(data: bytes) -> dict[str, Any]:
    root = require_object(parse_canonical(data))
    require_members(
        root,
        {
            "format",
            "format_version",
            "ir_artifact",
            "ir_document_digest",
            "obligation_profile",
            "obligations",
            "semantics",
        },
    )
    if root["format"] != "axiom-obligation-set":
        raise ContractError("unsupported-format")
    if root["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    require_digest(root["ir_artifact"])
    require_digest(root["ir_document_digest"])
    validate_semantics(root["semantics"])
    profile = require_object(root["obligation_profile"])
    require_members(profile, {"name", "version"})
    if profile not in (
        {"name": "keyed-finite-table-benchmark", "version": "0.1"},
        {"name": "keyed-finite-table-verification", "version": "0.1"},
    ):
        raise ContractError("unsupported-profile")
    obligations = require_array(root["obligations"])
    if not obligations:
        raise ContractError("empty-obligation-set")
    ids: list[str] = []
    definitions: set[bytes] = set()
    for value in obligations:
        item = require_object(value)
        require_members(item, {"definition", "id"})
        obligation_id = require_digest(item["id"])
        definition = require_object(item["definition"])
        require_members(definition, {"expectation", "kind", "subject"})
        kind = definition["kind"]
        if kind not in OBLIGATION_KINDS:
            raise ContractError("unknown-obligation-kind")
        if definition["expectation"] != OBLIGATION_EXPECTATIONS[kind]:
            raise ContractError("expectation-mismatch")
        validate_subject(definition["subject"])
        expected_id = content_id("axiom-evidence-v0.1:obligation", definition)
        if obligation_id != expected_id:
            raise ContractError("obligation-id-mismatch")
        encoded = canonical_bytes(definition)
        if encoded in definitions:
            raise ContractError("duplicate-obligation")
        definitions.add(encoded)
        ids.append(obligation_id)
    require_sorted_unique(ids, "obligations-not-sorted")
    return root


def validate_host_value(value: Any) -> None:
    if type(value) is bool or isinstance(value, str):
        return
    item = require_object(value, "invalid-host-value")
    kind = item.get("kind")
    if kind == "none":
        require_members(item, {"kind"})
        return
    if kind == "some":
        require_members(item, {"kind", "value"})
        validate_host_value(item["value"])
        return
    raise ContractError("invalid-host-value")


def validate_host_data_bytes(data: bytes) -> dict[str, Any]:
    root = require_object(parse_canonical(data))
    require_members(
        root,
        {"format", "format_version", "ir_document_digest", "role", "tables"},
    )
    if root["format"] != "axiom-host-data":
        raise ContractError("unsupported-format")
    if root["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    require_digest(root["ir_document_digest"])
    if root["role"] not in {"input", "output"}:
        raise ContractError("unknown-host-role")
    tables = require_array(root["tables"])
    table_names: list[str] = []
    for table_value in tables:
        table = require_object(table_value)
        require_members(table, {"name", "rows"})
        name = table["name"]
        if not isinstance(name, str) or not name:
            raise ContractError("invalid-table-name")
        table_names.append(name)
        rows = require_array(table["rows"])
        for row_value in rows:
            row = require_object(row_value, "invalid-row")
            if not row:
                raise ContractError("invalid-row")
            for field_name, field_value in row.items():
                if not field_name:
                    raise ContractError("invalid-field-name")
                validate_host_value(field_value)
    require_sorted_unique(table_names, "tables-not-sorted")
    return root


def validate_query_bytes(data: bytes) -> None:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ContractError("query-not-ascii", str(exc)) from exc
    if "\r" in text:
        raise ContractError("query-line-ending")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ContractError("query-final-lf")
    if ";" in text:
        raise ContractError("query-comment-forbidden")
    forbidden = (
        (r"\((?:forall|exists)\b", "query-quantifier-forbidden"),
        (r"\(set-option\b", "query-option-forbidden"),
        (r"\b(?:String|Real|Float16|Float32|Float64)\b", "query-theory-forbidden"),
        (r"(?<![A-Za-z0-9_])[0-9]+\.[0-9]+", "query-float-forbidden"),
        (r"(?:/Users/|/home/|[A-Za-z]:\\)", "query-path-forbidden"),
        (r"(?i)(?:random|seed|timestamp|hostname)", "query-nondeterminism-forbidden"),
    )
    for pattern, code in forbidden:
        if re.search(pattern, text):
            raise ContractError(code)
    lines = text.splitlines()
    if not lines or lines[0] != "(set-logic QF_UFLIA)":
        raise ContractError("query-logic-mismatch")
    if lines[-1] != "(check-sat)":
        raise ContractError("query-check-sat-missing")
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ContractError("query-parentheses")
    if depth != 0:
        raise ContractError("query-parentheses")


def validate_target_bytes(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("target-invalid-utf8", str(exc)) from exc
    if "\r" in text:
        raise ContractError("target-line-ending")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ContractError("target-final-lf")
    if NODE_TARGET_PROFILE not in text:
        raise ContractError("target-profile-missing")
    forbidden = (
        (r"\bimport\b|\brequire\s*\(", "target-import-forbidden"),
        (r"\beval\s*\(|\bFunction\s*\(", "target-dynamic-code-forbidden"),
        (r"\bNumber\s*\(", "target-number-forbidden"),
        (r"\bprocess\.env\b", "target-environment-forbidden"),
        (r"\b(?:fetch|WebSocket|WebAssembly|Worker)\b", "target-capability-forbidden"),
        (r"\b(?:Date|Intl)\b|Math\.random|\.localeCompare\s*\(|\.normalize\s*\(", "target-nondeterminism-forbidden"),
        (r"(?:/Users/|/home/|[A-Za-z]:\\)", "target-path-forbidden"),
        (r"//# sourceMappingURL|/\*|//", "target-comment-forbidden"),
    )
    for pattern, code in forbidden:
        if re.search(pattern, text):
            raise ContractError(code)


def validate_artifact_ref(value: Any, artifact_ids: set[str]) -> tuple[str, str]:
    item = require_object(value)
    require_members(item, {"artifact", "role"})
    digest = require_digest(item["artifact"])
    if digest not in artifact_ids:
        raise ContractError("artifact-reference-unknown")
    role = item["role"]
    if not isinstance(role, str) or not STABLE_ID_PATTERN.fullmatch(role):
        raise ContractError("invalid-artifact-role")
    return role, digest


def validate_result(value: Any, allow_not_run: bool) -> str:
    item = require_object(value)
    kind = item.get("kind")
    if kind not in STAGE_RESULTS:
        raise ContractError("unknown-stage-result")
    if kind == "completed":
        require_members(item, {"kind"})
    elif kind == "not-run":
        if not allow_not_run:
            raise ContractError("attempt-not-run-forbidden")
        require_members(item, {"blocked_by", "kind"})
        blocker = require_object(item["blocked_by"])
        require_members(blocker, {"id", "kind"})
        if blocker["kind"] not in {"gate", "stage"}:
            raise ContractError("not-run-blocker")
        if not isinstance(blocker["id"], str) or not blocker["id"]:
            raise ContractError("not-run-blocker")
    else:
        require_members(item, {"code", "kind"})
        if not isinstance(item["code"], str) or not STABLE_ID_PATTERN.fullmatch(item["code"]):
            raise ContractError("invalid-stage-code")
    return kind


def validate_receipt_bytes(data: bytes) -> dict[str, Any]:
    root = require_object(parse_canonical(data))
    require_members(
        root,
        {
            "artifacts",
            "assurance_policy",
            "evidence_version",
            "format",
            "format_version",
            "ir_version",
            "mode",
            "outcome",
            "pipeline_profile",
            "semantics",
            "stages",
            "tools",
            "verification_gate",
        },
    )
    if root["format"] != "axiom-pipeline-receipt":
        raise ContractError("unsupported-format")
    if root["format_version"] != FORMAT_VERSION:
        raise ContractError("unsupported-version")
    if root["pipeline_profile"] != PIPELINE_PROFILE:
        raise ContractError("unsupported-profile")
    if root["mode"] not in {"benchmark-node24", "verification"}:
        raise ContractError("unsupported-mode")
    if root["ir_version"] != IR_VERSION or root["evidence_version"] != EVIDENCE_VERSION:
        raise ContractError("unsupported-version")
    if root["outcome"] not in {"blocked", "completed", "error", "partial"}:
        raise ContractError("unknown-receipt-outcome")
    validate_semantics(root["semantics"])
    policy_digest = require_digest(root["assurance_policy"])

    artifacts = require_array(root["artifacts"])
    artifact_ids: list[str] = []
    for value in artifacts:
        item = require_object(value)
        require_members(item, {"byte_length", "content_digest", "format", "format_version"})
        if not isinstance(item["byte_length"], str) or not CANONICAL_UINT_PATTERN.fullmatch(item["byte_length"]):
            raise ContractError("invalid-byte-length")
        artifact_ids.append(require_digest(item["content_digest"]))
        if not all(isinstance(item[key], str) and item[key] for key in ("format", "format_version")):
            raise ContractError("invalid-artifact-format")
    require_sorted_unique(artifact_ids, "artifacts-not-sorted")
    artifact_id_set = set(artifact_ids)
    if policy_digest not in artifact_id_set:
        raise ContractError("assurance-policy-missing")

    tools = require_array(root["tools"])
    tool_ids: list[str] = []
    for value in tools:
        item = require_object(value)
        require_members(item, {"definition", "id"})
        tool_id = require_digest(item["id"])
        definition = require_object(item["definition"])
        require_members(definition, {"artifact", "name", "roles", "version"})
        if require_digest(definition["artifact"]) not in artifact_id_set:
            raise ContractError("tool-artifact-missing")
        roles = require_array(definition["roles"])
        if not roles or not all(isinstance(role, str) and role for role in roles):
            raise ContractError("invalid-tool-role")
        require_sorted_unique(roles, "tool-roles-not-sorted")
        if not all(isinstance(definition[key], str) and definition[key] for key in ("name", "version")):
            raise ContractError("invalid-tool-identity")
        if tool_id != content_id("axiom-evidence-v0.1:tool", definition):
            raise ContractError("tool-id-mismatch")
        tool_ids.append(tool_id)
    require_sorted_unique(tool_ids, "tools-not-sorted")
    tool_id_set = set(tool_ids)

    stages = require_array(root["stages"])
    stage_ids = [require_object(item).get("id") for item in stages]
    if stage_ids != list(STAGE_KINDS):
        raise ContractError("stages-not-sorted")
    attempt_ids: set[str] = set()
    stage_results: dict[str, str] = {}
    stage_by_id: dict[str, dict[str, Any]] = {}
    for value in stages:
        item = require_object(value)
        require_members(item, {"attempts", "dependencies", "id", "kind", "result"})
        stage_id = item["id"]
        if item["kind"] != STAGE_KINDS.get(stage_id):
            raise ContractError("stage-kind-mismatch")
        dependencies = require_array(item["dependencies"])
        if dependencies != sorted(set(dependencies)):
            raise ContractError("dependencies-not-sorted")
        if any(dependency not in STAGE_KINDS for dependency in dependencies):
            raise ContractError("dependency-unknown")
        stage_result = validate_result(item["result"], allow_not_run=True)
        stage_results[stage_id] = stage_result
        stage_by_id[stage_id] = item
        attempts = require_array(item["attempts"])
        if stage_result == "not-run":
            if attempts:
                raise ContractError("not-run-has-attempt")
            continue
        if not attempts:
            raise ContractError("stage-attempt-missing")
        ordinals: list[str] = []
        final_attempt_result = ""
        for attempt_value in attempts:
            attempt = require_object(attempt_value)
            require_members(attempt, {"definition", "id"})
            attempt_id = require_digest(attempt["id"])
            definition = require_object(attempt["definition"])
            require_members(
                definition,
                {
                    "adapter_profile",
                    "cache",
                    "inputs",
                    "limits",
                    "options",
                    "ordinal",
                    "outputs",
                    "result",
                    "tool",
                },
            )
            if definition["tool"] not in tool_id_set:
                raise ContractError("tool-reference-unknown")
            ordinals.append(definition["ordinal"])
            if not CANONICAL_UINT_PATTERN.fullmatch(definition["ordinal"]):
                raise ContractError("invalid-attempt-ordinal")
            adapter = require_object(definition["adapter_profile"])
            adapter_kind = adapter.get("kind")
            if adapter_kind == "not-applicable":
                require_members(adapter, {"kind"})
            elif adapter_kind == "profile":
                require_members(adapter, {"kind", "value"})
                allowed_profiles = {CVC5_PROFILE, NODE_INVOCATION_PROFILE, NODE_TARGET_PROFILE}
                if adapter["value"] not in allowed_profiles:
                    raise ContractError("adapter-profile-unknown")
            else:
                raise ContractError("adapter-profile-unknown")
            input_values = require_array(definition["inputs"])
            input_keys = [validate_artifact_ref(ref, artifact_id_set) for ref in input_values]
            if input_keys != sorted(set(input_keys)):
                raise ContractError("artifact-refs-not-sorted")
            output_values = require_array(definition["outputs"])
            output_keys = [validate_artifact_ref(ref, artifact_id_set) for ref in output_values]
            if output_keys != sorted(set(output_keys)):
                raise ContractError("artifact-refs-not-sorted")
            limit_values = require_array(definition["limits"])
            limit_keys: list[tuple[str, str]] = []
            for limit_value in limit_values:
                limit = require_object(limit_value)
                require_members(limit, {"name", "unit", "value"})
                if not CANONICAL_UINT_PATTERN.fullmatch(limit["value"]):
                    raise ContractError("invalid-limit")
                limit_keys.append((limit["name"], limit["unit"]))
            if limit_keys != sorted(set(limit_keys)):
                raise ContractError("limits-not-sorted")
            options_digest = require_digest(definition["options"])
            if options_digest not in artifact_id_set:
                raise ContractError("options-artifact-missing")
            expected_cache = cache_key(
                adapter_profile=adapter,
                assurance_policy=policy_digest,
                inputs=input_values,
                limits_value=limit_values,
                options=options_digest,
                stage_id=stage_id,
                tool=definition["tool"],
            )
            cache = require_object(definition["cache"])
            require_members(cache, {"key", "kind"})
            if cache["key"] != expected_cache:
                raise ContractError("cache-key-mismatch")
            if cache["kind"] not in {"hit", "miss"}:
                raise ContractError("cache-kind-unknown")
            if cache["kind"] == "hit" and not output_values:
                raise ContractError("cache-hit-invalid")
            final_attempt_result = validate_result(definition["result"], allow_not_run=False)
            expected_attempt_id = content_id("axiom-pipeline-v0.1:attempt", definition)
            if attempt_id != expected_attempt_id:
                raise ContractError("attempt-id-mismatch")
            if attempt_id in attempt_ids:
                raise ContractError("duplicate-attempt")
            attempt_ids.add(attempt_id)
        expected_ordinals = [str(index) for index in range(len(ordinals))]
        if ordinals != expected_ordinals:
            raise ContractError("attempts-not-ordered")
        if final_attempt_result != stage_result:
            raise ContractError("stage-result-mismatch")

    gate = require_object(root["verification_gate"])
    require_members(gate, {"decision", "id", "requirements"})
    if gate["id"] != "verification-gate" or gate["decision"] not in {"closed", "opened"}:
        raise ContractError("gate-invalid")
    requirements = require_array(gate["requirements"])
    expected_requirement_kinds = [
        "all-prove-proved",
        "all-trust-declared",
        "assurance-policy-accepted",
        "input-checked",
        "ir-accepted",
    ]
    requirement_kinds = [require_object(value).get("kind") for value in requirements]
    if requirement_kinds != expected_requirement_kinds:
        raise ContractError("gate-requirements-not-sorted")
    obligation_ids = {
        item["id"] for item in build_obligation_set()["obligations"]
    }
    statuses: list[str] = []
    for value in requirements:
        requirement = require_object(value)
        require_members(requirement, {"kind", "refs", "status"})
        if requirement["status"] not in {"satisfied", "unsatisfied"}:
            raise ContractError("gate-status-unknown")
        statuses.append(requirement["status"])
        refs = require_array(requirement["refs"])
        ref_keys: list[tuple[str, str]] = []
        for ref_value in refs:
            ref = require_object(ref_value)
            require_members(ref, {"kind", "value"})
            ref_kind = ref["kind"]
            ref_id = require_digest(ref["value"])
            if ref_kind == "artifact" and ref_id not in artifact_id_set:
                raise ContractError("gate-reference-unknown")
            if ref_kind == "attempt" and ref_id not in attempt_ids:
                raise ContractError("gate-reference-unknown")
            if ref_kind == "obligation" and ref_id not in obligation_ids:
                raise ContractError("gate-reference-unknown")
            if ref_kind not in {"artifact", "attempt", "obligation"}:
                raise ContractError("gate-reference-unknown")
            ref_keys.append((ref_kind, ref_id))
        if ref_keys != sorted(set(ref_keys)):
            raise ContractError("gate-refs-not-sorted")
    expected_decision = "opened" if all(status == "satisfied" for status in statuses) else "closed"
    if gate["decision"] != expected_decision:
        raise ContractError("gate-decision-mismatch")
    if gate["decision"] == "opened":
        if any(stage_results[stage_id] != "completed" for stage_id in ("P1", "P2", "P3", "P4", "P5")):
            raise ContractError("gate-bypass")
        if any(stage_results[stage_id] != "completed" for stage_id in ("P6", "P7", "P8")):
            raise ContractError("gate-open-target-missing")
    else:
        if any(stage_results[stage_id] != "not-run" for stage_id in ("P6", "P7", "P8")):
            raise ContractError("gate-bypass")
    if root["outcome"] == "completed" and (
        gate["decision"] != "opened"
        or any(result != "completed" for result in stage_results.values())
    ):
        raise ContractError("receipt-outcome-mismatch")
    if root["outcome"] == "partial" and all(
        result == "completed" for result in stage_results.values()
    ):
        raise ContractError("receipt-outcome-mismatch")
    return root
