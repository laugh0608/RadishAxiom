"""Generate and verify execution profile contract artifacts."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any, Callable

from .common import (
    CHECKER_PROFILE,
    CONTRACT_ROOT,
    CVC5_PROFILE,
    DOCUMENT_DOMAIN,
    FORMAT_VERSION,
    GENERATOR_SOURCES,
    NODE_PROFILE,
    REPO_ROOT,
    canonical_bytes,
    content_id,
    file_ref,
    pretty_bytes,
    raw_digest,
)
from .model import build_manifest
from .schema import build_schema
from .validator import ContractError, validate_bytes, validate_manifest


Mutation = Callable[[dict[str, Any]], None]


def _profile(value: dict[str, Any], profile_id: str) -> dict[str, Any]:
    return next(item for item in value["profiles"] if item["id"] == profile_id)


def _limit_set(value: dict[str, Any], limit_set_id: str) -> dict[str, Any]:
    return next(item for item in value["limit_sets"] if item["id"] == limit_set_id)


def _mutations() -> list[tuple[str, str, Mutation]]:
    def unknown_member(value: dict[str, Any]) -> None:
        value["unexpected"] = "forbidden"

    def unknown_version(value: dict[str, Any]) -> None:
        value["format_version"] = "0.2"

    def unknown_format(value: dict[str, Any]) -> None:
        value["format"] = "radishaxiom-execution-profile-set-unknown"

    def unsorted_profiles(value: dict[str, Any]) -> None:
        value["profiles"] = list(reversed(value["profiles"]))

    def duplicate_profile(value: dict[str, Any]) -> None:
        value["profiles"].insert(1, copy.deepcopy(value["profiles"][0]))

    def missing_limit_set(value: dict[str, Any]) -> None:
        value["limit_sets"] = [
            item
            for item in value["limit_sets"]
            if item["id"] != "cvc5-1.3.4-qf-uflia-internal-v0.1"
        ]

    def zero_limit(value: dict[str, Any]) -> None:
        limits = _limit_set(value, "cvc5-1.3.4-qf-uflia-internal-v0.1")["limits"]
        limits[0]["value"] = "0"

    def duplicate_limit(value: dict[str, Any]) -> None:
        limits = _limit_set(value, "cvc5-1.3.4-qf-uflia-internal-v0.1")["limits"]
        limits.insert(1, copy.deepcopy(limits[0]))

    def cvc5_unknown_option(value: dict[str, Any]) -> None:
        tokens = _profile(value, CVC5_PROFILE)["invocation"]["argument_tokens"]
        tokens.append({"kind": "literal", "value": "--stats"})

    def cvc5_environment(value: dict[str, Any]) -> None:
        _profile(value, CVC5_PROFILE)["environment"]["inherit"] = "host"

    def cvc5_seed(value: dict[str, Any]) -> None:
        tokens = _profile(value, CVC5_PROFILE)["invocation"]["argument_tokens"]
        tokens.append({"kind": "literal", "value": "--random-seed=7"})

    def cvc5_path(value: dict[str, Any]) -> None:
        tokens = _profile(value, CVC5_PROFILE)["invocation"]["argument_tokens"]
        tokens.append({"kind": "artifact-path", "role": "query"})

    def cvc5_missing_strict(value: dict[str, Any]) -> None:
        tokens = _profile(value, CVC5_PROFILE)["invocation"]["argument_tokens"]
        _profile(value, CVC5_PROFILE)["invocation"]["argument_tokens"] = [
            token for token in tokens if token.get("value") != "--strict-parsing"
        ]

    def node_unknown_option(value: dict[str, Any]) -> None:
        tokens = _profile(value, NODE_PROFILE)["invocation"]["argument_tokens"]
        tokens.append({"kind": "literal", "value": "--inspect"})

    def node_environment(value: dict[str, Any]) -> None:
        _profile(value, NODE_PROFILE)["environment"]["set"] = [
            {"name": "NODE_OPTIONS", "value": "--inspect"}
        ]

    def node_network(value: dict[str, Any]) -> None:
        _profile(value, NODE_PROFILE)["capability_boundary"]["network"] = "allowed"

    def node_number_codec(value: dict[str, Any]) -> None:
        _profile(value, NODE_PROFILE)["codec"]["integer"] = "number"

    def node_output_limit_missing(value: dict[str, Any]) -> None:
        limit_set = _limit_set(value, "node-24-esm-invocation-process-v0.1")
        limit_set["limits"] = [
            item for item in limit_set["limits"] if item["name"] != "stdout-bytes"
        ]

    def checker_limit_missing(value: dict[str, Any]) -> None:
        limit_set = _limit_set(
            value, "keyed-finite-table-independent-check-request-v0.1"
        )
        limit_set["limits"] = [
            item for item in limit_set["limits"] if item["name"] != "semantic-steps"
        ]

    def checker_counters_reordered(value: dict[str, Any]) -> None:
        counters = _profile(value, CHECKER_PROFILE)["resource_counters"]
        counters[0], counters[1] = counters[1], counters[0]

    def checker_process_as_result(value: dict[str, Any]) -> None:
        boundary = _profile(value, CHECKER_PROFILE)["result_boundary"]
        boundary["outer-kill-crash-identity-failure-or-output-truncation"] = (
            "canonical-result-may-form"
        )

    def certificate_supported(value: dict[str, Any]) -> None:
        value["certificate_capabilities"]["supported_profiles"] = [
            "alethe-cvc5-1.3.4-v0.1"
        ]

    def attestation_upgraded(value: dict[str, Any]) -> None:
        cases = value["certificate_capabilities"]["policy_cases"]
        cases[0]["evidence_support"] = "certificate"

    def source_digest_drift(value: dict[str, Any]) -> None:
        value["source_bindings"][0]["sha256"] = "sha256:" + "0" * 64

    def coverage_drift(value: dict[str, Any]) -> None:
        value["coverage"][0]["readiness_scenarios"] = value["coverage"][0][
            "readiness_scenarios"
        ][1:]

    return [
        ("certificate-profile-unaccepted", "certificate-profile-unaccepted", certificate_supported),
        ("checker-counter-order", "checker-counter-order", checker_counters_reordered),
        ("checker-limit-missing", "checker-limit-set-mismatch", checker_limit_missing),
        ("checker-process-as-result", "checker-result-boundary", checker_process_as_result),
        ("coverage-drift", "coverage-mismatch", coverage_drift),
        ("cvc5-environment-inheritance", "environment-inheritance", cvc5_environment),
        ("cvc5-missing-strict-parsing", "required-cvc5-option-missing", cvc5_missing_strict),
        ("cvc5-path-input", "forbidden-cvc5-path-input", cvc5_path),
        ("cvc5-random-seed", "forbidden-cvc5-random-seed", cvc5_seed),
        ("cvc5-unknown-option", "cvc5-options-mismatch", cvc5_unknown_option),
        ("duplicate-limit", "duplicate-limit", duplicate_limit),
        ("duplicate-profile", "duplicate-entry", duplicate_profile),
        ("missing-limit-set", "limit-set-reference", missing_limit_set),
        ("node-environment-inheritance", "environment-inheritance", node_environment),
        ("node-network-capability", "node-capability-mismatch", node_network),
        ("node-number-codec", "node-codec-mismatch", node_number_codec),
        ("node-output-limit-missing", "limit-set-definition-mismatch", node_output_limit_missing),
        ("node-unknown-option", "node-options-mismatch", node_unknown_option),
        ("source-digest-drift", "source-digest-drift", source_digest_drift),
        ("attestation-upgraded", "certificate-boundary", attestation_upgraded),
        ("unknown-format", "unknown-format", unknown_format),
        ("unknown-member", "unknown-member", unknown_member),
        ("unknown-version", "unsupported-version", unknown_version),
        ("unsorted-profiles", "noncanonical-order", unsorted_profiles),
        ("zero-limit", "non-positive-limit", zero_limit),
    ]


def _negative_files(manifest: dict[str, Any]) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    files: dict[str, bytes] = {}
    expected: list[dict[str, str]] = []
    for name, code, mutation in sorted(_mutations()):
        value = copy.deepcopy(manifest)
        mutation(value)
        path = f"fixtures/negative/{name}.invalid.jcs"
        data = canonical_bytes(value)
        try:
            validate_bytes(data, manifest)
        except ContractError as exc:
            if exc.code != code:
                raise ValueError(f"negative fixture {name}: {exc.code} != {code}") from exc
        else:
            raise ValueError(f"negative fixture accepted: {name}")
        files[path] = data
        expected.append({"code": code, "path": path})

    duplicate_path = "fixtures/negative/duplicate-member.invalid.jcs"
    prefix = b'{"format":"radishaxiom-execution-profile-set",'
    duplicate = prefix + canonical_bytes(manifest)[1:]
    try:
        validate_bytes(duplicate, manifest)
    except ContractError as exc:
        if exc.code != "duplicate-member":
            raise ValueError(f"duplicate member fixture: {exc.code}") from exc
    else:
        raise ValueError("duplicate member fixture accepted")
    files[duplicate_path] = duplicate
    expected.append({"code": "duplicate-member", "path": duplicate_path})

    whitespace_path = "fixtures/negative/noncanonical-whitespace.invalid.jcs"
    whitespace = canonical_bytes(manifest) + b"\n"
    try:
        validate_bytes(whitespace, manifest)
    except ContractError as exc:
        if exc.code != "noncanonical-json":
            raise ValueError(f"whitespace fixture: {exc.code}") from exc
    else:
        raise ValueError("whitespace fixture accepted")
    files[whitespace_path] = whitespace
    expected.append({"code": "noncanonical-json", "path": whitespace_path})
    return files, sorted(expected, key=lambda item: item["path"])


def build_generated_files() -> dict[str, bytes]:
    manifest = build_manifest()
    validate_manifest(manifest, manifest)
    manifest_bytes = canonical_bytes(manifest)
    validate_bytes(manifest_bytes, manifest)

    files: dict[str, bytes] = {
        "manifest.jcs": manifest_bytes,
        "schemas/execution-profile-set.schema.json": pretty_bytes(
            build_schema(manifest)
        ),
    }
    for profile in manifest["profiles"]:
        files[f"fixtures/positive/{profile['id']}.jcs"] = canonical_bytes(profile)
    checker_limits = next(
        item
        for item in manifest["limit_sets"]
        if item["id"] == "keyed-finite-table-independent-check-request-v0.1"
    )
    files["fixtures/positive/checker-request-limits.jcs"] = canonical_bytes(
        checker_limits
    )
    files["fixtures/positive/certificate-capabilities.jcs"] = canonical_bytes(
        manifest["certificate_capabilities"]
    )

    negative_files, expected = _negative_files(manifest)
    files.update(negative_files)
    files["fixtures/negative/expected.json"] = pretty_bytes(expected)

    contract = {
        "contract_version": FORMAT_VERSION,
        "files": [file_ref(path, data) for path, data in sorted(files.items())],
        "format": "radishaxiom-execution-profile-contract",
        "generator_sources": [
            {
                "path": path.as_posix(),
                "sha256": raw_digest((REPO_ROOT / path).read_bytes()),
            }
            for path in GENERATOR_SOURCES
        ],
        "manifest": {
            "content_digest": raw_digest(manifest_bytes),
            "document_digest": content_id(DOCUMENT_DOMAIN, manifest),
            "path": "manifest.jcs",
        },
        "negative_fixture_count": str(len(expected)),
        "positive_fixture_count": str(len(manifest["profiles"]) + 2),
        "sources": manifest["source_bindings"],
    }
    files["contract.json"] = pretty_bytes(contract)
    return files


def actual_generated_paths() -> set[str]:
    if not CONTRACT_ROOT.exists():
        return set()
    return {
        path.relative_to(CONTRACT_ROOT).as_posix()
        for path in CONTRACT_ROOT.rglob("*")
        if path.is_file() and path.name != "README.md"
    }


def check_generated(expected: dict[str, bytes]) -> list[str]:
    errors = []
    expected_paths = set(expected)
    actual_paths = actual_generated_paths()
    for path in sorted(expected_paths - actual_paths):
        errors.append(f"missing generated file: {path}")
    for path in sorted(actual_paths - expected_paths):
        errors.append(f"unexpected generated file: {path}")
    for path in sorted(expected_paths & actual_paths):
        actual = (CONTRACT_ROOT / path).read_bytes()
        if actual != expected[path]:
            errors.append(f"generated file drifted: {path}")
    for path in CONTRACT_ROOT.rglob("*") if CONTRACT_ROOT.exists() else []:
        if path.is_symlink():
            errors.append(f"symlink forbidden in execution profile contract: {path}")
    return errors


def write_generated(expected: dict[str, bytes]) -> None:
    CONTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    for path in sorted(actual_generated_paths() - set(expected)):
        (CONTRACT_ROOT / path).unlink()
    for directory in sorted(
        (path for path in CONTRACT_ROOT.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass
    for path, data in expected.items():
        destination = CONTRACT_ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generated = build_generated_files()
        if args.write:
            write_generated(generated)
            print(f"wrote execution profile contract: {len(generated)} files")
            return 0
        errors = check_generated(generated)
    except (OSError, ValueError, KeyError, IndexError) as exc:
        print(f"execution profile contract error: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"execution profile contract passed: {len(generated)} files")
    return 0
