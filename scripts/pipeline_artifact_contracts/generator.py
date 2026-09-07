"""Assemble, validate, write, and check generated contract files."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from .builders import (
    build_host_data,
    build_obligation_set,
    build_options,
    build_policy,
    build_query,
    build_receipt,
    build_target_module,
)
from .common import (
    CONTRACT_ROOT,
    CVC5_PROFILE,
    ContractError,
    NODE_TARGET_PROFILE,
    PIPELINE_PROFILE,
    REPO_ROOT,
    TOOL_REGISTRY_PATH,
    canonical_bytes,
    pretty_bytes,
    raw_digest,
)
from .negative_fixtures import negative_json_fixtures, raw_negative_fixtures
from .schemas import host_data_schema, obligation_schema, receipt_schema
from .validation import (
    validate_host_data_bytes,
    validate_obligation_set_bytes,
    validate_query_bytes,
    validate_receipt_bytes,
    validate_target_bytes,
)

def generated_contract(expected_files: dict[str, bytes], negatives: dict[str, tuple[bytes, str, str]]) -> dict[str, Any]:
    bindings = []
    for name, path in (
        ("adr-0007", Path("docs/adr/0007-first-verification-first-compilation-pipeline.md")),
        ("axiom-evidence-v0.1", Path("docs/evidence/axiom-evidence-v0.md")),
        ("axiom-ir-v0.1", Path("docs/ir/axiom-ir-v0.md")),
        ("keyed-finite-table-semantics", Path("docs/semantics/keyed-finite-table-semantics.md")),
        ("toolchain-adapter-identities-v0.1", TOOL_REGISTRY_PATH),
    ):
        data = (REPO_ROOT / path).read_bytes()
        binding: dict[str, str] = {
            "name": name,
            "path": path.as_posix(),
            "raw_sha256": raw_digest(data),
        }
        if path == TOOL_REGISTRY_PATH:
            registry = json.loads(data)
            binding["registry_digest"] = registry["registry_digest"]
        bindings.append(binding)
    bindings.sort(key=lambda item: item["name"])

    generated = [
        {
            "byte_length": str(len(data)),
            "path": path,
            "sha256": raw_digest(data),
        }
        for path, data in sorted(expected_files.items())
        if path != "contract.json"
    ]
    return {
        "bindings": bindings,
        "content_domains": {
            "attempt": "axiom-pipeline-v0.1:attempt",
            "cache_key": "axiom-pipeline-v0.1:cache-key",
            "obligation": "axiom-evidence-v0.1:obligation",
            "tool": "axiom-evidence-v0.1:tool",
        },
        "formats": [
            {"kind": "canonical-json", "name": "axiom-host-data", "schema": "schemas/axiom-host-data.schema.json", "version": "0.1"},
            {"kind": "canonical-json", "name": "axiom-obligation-set", "schema": "schemas/axiom-obligation-set.schema.json", "version": "0.1"},
            {"kind": "raw-utf8-lf", "name": "axiom-node-esm", "profile": NODE_TARGET_PROFILE, "version": NODE_TARGET_PROFILE},
            {"kind": "canonical-json", "name": "axiom-pipeline-receipt", "schema": "schemas/axiom-pipeline-receipt.schema.json", "version": "0.1"},
            {"kind": "raw-ascii-lf", "name": "axiom-smtlib2-qf-uflia-query", "profile": CVC5_PROFILE, "version": "0.1"},
        ],
        "generated_files": generated,
        "negative_fixture_count": str(len(negatives)),
        "pipeline_profile": PIPELINE_PROFILE,
        "raw_byte_profiles": {
            "axiom-node-esm": {
                "encoding": "UTF-8",
                "final_lf": "exactly-one",
                "line_endings": "LF",
                "validator_scope": "contract-fixture-subset-not-a-complete-ecmascript-parser",
            },
            "axiom-smtlib2-qf-uflia-query": {
                "encoding": "ASCII",
                "final_lf": "exactly-one",
                "line_endings": "LF",
                "validator_scope": "contract-fixture-subset-not-a-complete-smtlib-parser",
            },
        },
        "version": "0.1",
    }


def build_outputs() -> dict[Path, bytes]:
    obligation_set = build_obligation_set()
    host_input = build_host_data("input")
    host_output = build_host_data("output")
    totality_id = next(
        item["id"]
        for item in obligation_set["obligations"]
        if item["definition"]["kind"] == "totality"
    )
    fixture_bytes: dict[str, bytes] = {
        "fixtures/minimal/host-input.jcs": canonical_bytes(host_input),
        "fixtures/minimal/host-output.jcs": canonical_bytes(host_output),
        "fixtures/minimal/obligation-set.jcs": canonical_bytes(obligation_set),
        "fixtures/minimal/options.jcs": canonical_bytes(build_options()),
        "fixtures/minimal/policy.jcs": canonical_bytes(build_policy()),
        "fixtures/minimal/query.smt2": build_query(totality_id),
        "fixtures/minimal/target.mjs": build_target_module(),
        "fixtures/minimal/tool.txt": b"synthetic pipeline contract tool artifact; not executable\n",
    }
    completed_receipt = build_receipt(fixture_bytes, obligation_set, partial=False)
    partial_receipt = build_receipt(fixture_bytes, obligation_set, partial=True)
    fixture_bytes["fixtures/minimal/receipt.jcs"] = canonical_bytes(completed_receipt)
    fixture_bytes["fixtures/partial/backend-timeout.receipt.jcs"] = canonical_bytes(partial_receipt)

    negatives = negative_json_fixtures(
        obligation_set, host_input, completed_receipt, partial_receipt
    )
    negatives.update(
        raw_negative_fixtures(
            fixture_bytes["fixtures/minimal/query.smt2"],
            fixture_bytes["fixtures/minimal/target.mjs"],
        )
    )
    expected_index = {
        "negative": [
            {
                "expected_code": code,
                "kind": kind,
                "path": f"fixtures/negative/{name}",
                "sha256": raw_digest(data),
            }
            for name, (data, code, kind) in sorted(negatives.items())
        ],
        "positive": [
            {
                "byte_length": str(len(data)),
                "path": path,
                "sha256": raw_digest(data),
            }
            for path, data in sorted(fixture_bytes.items())
        ],
    }

    output_bytes: dict[str, bytes] = dict(fixture_bytes)
    for name, (data, _, _) in negatives.items():
        output_bytes[f"fixtures/negative/{name}"] = data
    output_bytes["fixtures/expected.json"] = pretty_bytes(expected_index)
    output_bytes["schemas/axiom-host-data.schema.json"] = pretty_bytes(host_data_schema())
    output_bytes["schemas/axiom-obligation-set.schema.json"] = pretty_bytes(obligation_schema())
    output_bytes["schemas/axiom-pipeline-receipt.schema.json"] = pretty_bytes(receipt_schema())
    contract = generated_contract(output_bytes, negatives)
    output_bytes["contract.json"] = pretty_bytes(contract)

    validate_obligation_set_bytes(fixture_bytes["fixtures/minimal/obligation-set.jcs"])
    validate_host_data_bytes(fixture_bytes["fixtures/minimal/host-input.jcs"])
    validate_host_data_bytes(fixture_bytes["fixtures/minimal/host-output.jcs"])
    validate_query_bytes(fixture_bytes["fixtures/minimal/query.smt2"])
    validate_target_bytes(fixture_bytes["fixtures/minimal/target.mjs"])
    validate_receipt_bytes(fixture_bytes["fixtures/minimal/receipt.jcs"])
    validate_receipt_bytes(fixture_bytes["fixtures/partial/backend-timeout.receipt.jcs"])
    for name, (data, expected_code, kind) in negatives.items():
        validator: Callable[[bytes], Any]
        if kind == "obligation-set":
            validator = validate_obligation_set_bytes
        elif kind == "host-data":
            validator = validate_host_data_bytes
        elif kind == "receipt":
            validator = validate_receipt_bytes
        elif kind == "query":
            validator = validate_query_bytes
        elif kind == "target":
            validator = validate_target_bytes
        else:
            raise AssertionError(kind)
        try:
            validator(data)
        except ContractError as exc:
            if exc.code != expected_code:
                raise ValueError(
                    f"negative fixture {name} returned {exc.code}, expected {expected_code}"
                ) from exc
        else:
            raise ValueError(f"negative fixture unexpectedly accepted: {name}")
    return {CONTRACT_ROOT / path: data for path, data in output_bytes.items()}


def write_outputs(expected: dict[Path, bytes]) -> None:
    for path, data in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"wrote pipeline artifact contracts ({len(expected)} generated files)")


def check_outputs(expected: dict[Path, bytes]) -> int:
    errors: list[str] = []
    for path, data in expected.items():
        if not path.is_file():
            errors.append(f"missing generated file: {path.relative_to(REPO_ROOT)}")
        elif path.read_bytes() != data:
            errors.append(f"generated file drifted: {path.relative_to(REPO_ROOT)}")
    generated_roots = {
        path.relative_to(CONTRACT_ROOT).as_posix() for path in expected
    }
    if CONTRACT_ROOT.is_dir():
        for path in CONTRACT_ROOT.rglob("*"):
            if not path.is_file() or path.name == "README.md":
                continue
            relative = path.relative_to(CONTRACT_ROOT).as_posix()
            if relative not in generated_roots:
                errors.append(f"unexpected generated file: {path.relative_to(REPO_ROOT)}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"pipeline artifact contracts passed ({len(expected)} generated files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = build_outputs()
    if args.write:
        write_outputs(expected)
        return 0
    return check_outputs(expected)


if __name__ == "__main__":
    raise SystemExit(main())
