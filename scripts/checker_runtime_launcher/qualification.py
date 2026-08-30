"""Qualification companion binding and launcher process classification."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import (
    InstallationReceipt,
    LauncherValidationError,
    Target,
    UTC_TIMESTAMP,
    _array,
    _digest,
    _keys,
    _object,
    _parse_json,
    _string,
    canonical_bytes,
    domain_digest,
    raw_digest,
    validate_installation_receipt,
    validate_launcher_policy,
    validate_registration_record,
)


DECIMAL_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
QUALIFICATION_RECORD_DOMAIN = "radishaxiom.checker-runtime-qualification-record.v0.1"
INDEPENDENT_RESULT_DOMAIN = "axiom-independent-check-v0.1:result"


@dataclass(frozen=True, slots=True)
class CompanionObservation:
    scenario_id: str
    canonical_result: bytes
    contract_validated: bool


@dataclass(frozen=True, slots=True)
class QualificationRecord:
    value: dict[str, Any]
    canonical: bytes
    document_digest: str


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    preflight_available: bool = True
    spawned: bool = True
    timed_out: bool = False
    killed: bool = False
    signal: int | None = None
    exit_code: int | None = 0
    stdout_complete: bool = True
    canonical_result: bool = True
    result_identity_matches: bool = True
    postflight_identity_matches: bool = True
    registration_still_active: bool = True


@dataclass(frozen=True, slots=True)
class InvocationOutcome:
    classification: str
    independent_result: str


def _validate_companions(
    policy: dict[str, Any],
    record: dict[str, Any],
    observations: list[CompanionObservation],
) -> list[dict[str, str]]:
    runtime = _object(policy.get("runtime_companion"), "$.runtime_companion")
    expected_rows = _array(runtime.get("qualification_scenarios"), "$.qualification_scenarios")
    expected_by_id = {
        _string(_object(item, "$.qualification_scenarios[]").get("id"), "$.scenario.id"): _object(
            item, "$.qualification_scenarios[]"
        )
        for item in expected_rows
    }
    if len(expected_by_id) != len(expected_rows):
        raise LauncherValidationError("duplicate-qualification-scenario")
    if [item.scenario_id for item in observations] != sorted(expected_by_id):
        raise LauncherValidationError("qualification-scenario-set")

    checker_record = _object(record.get("checker"), "$.checker")
    checker_source = _object(checker_record.get("source"), "$.checker.source")
    artifact = _object(record.get("artifact"), "$.artifact")
    rows: list[dict[str, str]] = []
    for observation in observations:
        if not observation.contract_validated:
            raise LauncherValidationError("qualification-contract-not-validated")
        document = _parse_json(observation.canonical_result, require_canonical=True)
        expected = expected_by_id[observation.scenario_id]
        if str(len(observation.canonical_result)) != expected.get("byte_length"):
            raise LauncherValidationError("qualification-result-length", observation.scenario_id)
        if raw_digest(observation.canonical_result) != expected.get("raw_sha256"):
            raise LauncherValidationError("qualification-result-digest", observation.scenario_id)
        checker = _object(document.get("checker"), "$.checker")
        expected_checker = {
            "artifact": artifact.get("raw_sha256"),
            "name": checker_record.get("implementation"),
            "source": checker_source.get("identity"),
            "toolchain": checker_record.get("toolchain"),
            "version": checker_record.get("version"),
        }
        if checker != expected_checker:
            raise LauncherValidationError("qualification-checker-identity", observation.scenario_id)
        result = _object(document.get("result"), "$.result")
        if result.get("kind") != expected.get("outcome"):
            raise LauncherValidationError("qualification-outcome", observation.scenario_id)
        rows.append(
            {
                "byte_length": str(len(observation.canonical_result)),
                "document_digest": domain_digest(INDEPENDENT_RESULT_DOMAIN, document),
                "outcome": _string(result.get("kind"), "$.result.kind"),
                "raw_sha256": raw_digest(observation.canonical_result),
                "scenario_id": observation.scenario_id,
            }
        )
    return rows


def build_qualification_record(
    policy: dict[str, Any],
    record: dict[str, Any],
    installation_receipt: InstallationReceipt,
    observations: list[CompanionObservation],
    *,
    qualified_at: str,
) -> QualificationRecord:
    validate_launcher_policy(policy)
    validate_registration_record(record)
    if not UTC_TIMESTAMP.fullmatch(qualified_at):
        raise LauncherValidationError("invalid-qualification-time")
    validate_installation_receipt(installation_receipt.canonical, policy, record)
    companions = _validate_companions(policy, record, observations)
    artifact = _object(record.get("artifact"), "$.artifact")
    execution_profile = _object(
        _object(policy.get("invocation"), "$.invocation").get("execution_profile"),
        "$.invocation.execution_profile",
    )
    body: dict[str, Any] = {
        "artifact": {
            "byte_length": artifact.get("byte_length"),
            "raw_sha256": artifact.get("raw_sha256"),
        },
        "companions": companions,
        "digest_domain": QUALIFICATION_RECORD_DOMAIN,
        "execution_profile": dict(execution_profile),
        "format": "radishaxiom-checker-runtime-qualification-record",
        "format_version": "0.1",
        "installation_receipt_digest": installation_receipt.document_digest,
        "launcher_policy": {
            "format": policy.get("format"),
            "format_version": policy.get("format_version"),
            "policy_digest": policy.get("policy_digest"),
        },
        "qualified_at": qualified_at,
        "registration": {
            "id": record.get("id"),
            "record_digest": record.get("record_digest"),
        },
        "status": "qualified-installed-inactive",
        "target": Target.from_json(record.get("target")).as_json(),
    }
    document = {
        **body,
        "document_digest": domain_digest(QUALIFICATION_RECORD_DOMAIN, body),
    }
    return QualificationRecord(
        value=document,
        canonical=canonical_bytes(document),
        document_digest=document["document_digest"],
    )


def validate_qualification_record(data: bytes) -> QualificationRecord:
    value = _parse_json(data, require_canonical=True)
    _keys(
        value,
        {
            "artifact",
            "companions",
            "digest_domain",
            "document_digest",
            "execution_profile",
            "format",
            "format_version",
            "installation_receipt_digest",
            "launcher_policy",
            "qualified_at",
            "registration",
            "status",
            "target",
        },
        "$",
    )
    if value.get("format") != "radishaxiom-checker-runtime-qualification-record":
        raise LauncherValidationError("qualification-format")
    if value.get("format_version") != "0.1":
        raise LauncherValidationError("qualification-version")
    if value.get("digest_domain") != QUALIFICATION_RECORD_DOMAIN:
        raise LauncherValidationError("qualification-domain")
    if value.get("status") != "qualified-installed-inactive":
        raise LauncherValidationError("qualification-status")
    if not UTC_TIMESTAMP.fullmatch(
        _string(value.get("qualified_at"), "$.qualified_at")
    ):
        raise LauncherValidationError("invalid-qualification-time")
    _digest(
        value.get("installation_receipt_digest"),
        "$.installation_receipt_digest",
    )

    artifact = _object(value.get("artifact"), "$.artifact")
    _keys(artifact, {"byte_length", "raw_sha256"}, "$.artifact")
    artifact_length = _string(artifact.get("byte_length"), "$.artifact.byte_length")
    if not DECIMAL_PATTERN.fullmatch(artifact_length):
        raise LauncherValidationError("invalid-artifact-length")
    _digest(artifact.get("raw_sha256"), "$.artifact.raw_sha256")

    profile = _object(value.get("execution_profile"), "$.execution_profile")
    _keys(profile, {"id", "path", "raw_sha256"}, "$.execution_profile")
    _string(profile.get("id"), "$.execution_profile.id")
    _string(profile.get("path"), "$.execution_profile.path")
    _digest(profile.get("raw_sha256"), "$.execution_profile.raw_sha256")

    launcher_policy = _object(value.get("launcher_policy"), "$.launcher_policy")
    _keys(
        launcher_policy,
        {"format", "format_version", "policy_digest"},
        "$.launcher_policy",
    )
    if launcher_policy.get("format") != "radishaxiom-checker-runtime-launcher-policy":
        raise LauncherValidationError("qualification-policy-format")
    if launcher_policy.get("format_version") != "0.1":
        raise LauncherValidationError("qualification-policy-version")
    _digest(launcher_policy.get("policy_digest"), "$.launcher_policy.policy_digest")

    registration = _object(value.get("registration"), "$.registration")
    _keys(registration, {"id", "record_digest"}, "$.registration")
    _string(registration.get("id"), "$.registration.id")
    _digest(registration.get("record_digest"), "$.registration.record_digest")
    Target.from_json(value.get("target"))

    companions = _array(value.get("companions"), "$.companions")
    if len(companions) != 3:
        raise LauncherValidationError("qualification-scenario-set")
    scenario_ids: list[str] = []
    for index, item in enumerate(companions):
        path = f"$.companions[{index}]"
        companion = _object(item, path)
        _keys(
            companion,
            {
                "byte_length",
                "document_digest",
                "outcome",
                "raw_sha256",
                "scenario_id",
            },
            path,
        )
        length = _string(companion.get("byte_length"), f"{path}.byte_length")
        if not DECIMAL_PATTERN.fullmatch(length):
            raise LauncherValidationError("invalid-companion-length", path)
        _digest(companion.get("document_digest"), f"{path}.document_digest")
        _digest(companion.get("raw_sha256"), f"{path}.raw_sha256")
        outcome = _string(companion.get("outcome"), f"{path}.outcome")
        if outcome not in {"accepted", "accepted-with-trust", "incomplete", "rejected"}:
            raise LauncherValidationError("qualification-outcome", path)
        scenario_ids.append(
            _string(companion.get("scenario_id"), f"{path}.scenario_id")
        )
    if scenario_ids != sorted(set(scenario_ids)):
        raise LauncherValidationError("qualification-scenario-set")

    body = {key: item for key, item in value.items() if key != "document_digest"}
    digest = domain_digest(QUALIFICATION_RECORD_DOMAIN, body)
    if value.get("document_digest") != digest:
        raise LauncherValidationError("qualification-document-digest")
    return QualificationRecord(value=value, canonical=data, document_digest=digest)


def write_qualification_record_exclusive(path: Path, record: QualificationRecord) -> None:
    validate_qualification_record(record.canonical)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(record.canonical)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def classify_process(observation: ProcessObservation) -> InvocationOutcome:
    if not observation.preflight_available:
        return InvocationOutcome("runtime-unavailable", "not-produced")
    if (
        not observation.spawned
        or observation.timed_out
        or observation.killed
        or observation.signal is not None
        or observation.exit_code != 0
        or not observation.stdout_complete
        or not observation.canonical_result
    ):
        return InvocationOutcome("process-failure", "not-produced")
    if (
        not observation.result_identity_matches
        or not observation.postflight_identity_matches
        or not observation.registration_still_active
    ):
        return InvocationOutcome("identity-failure", "not-consumable")
    return InvocationOutcome("completed", "consumable")
