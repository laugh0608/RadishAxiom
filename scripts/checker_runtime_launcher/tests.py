"""Synthetic filesystem, archive, qualification, and process fixtures."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from .core import (
    POLICY_DOMAIN,
    REGISTRATION_DOMAIN,
    HostIdentity,
    LauncherValidationError,
    Target,
    build_installation_receipt,
    canonical_bytes,
    domain_digest,
    load_launcher_policy,
    load_registration_record,
    publish_staged_slot,
    raw_digest,
    select_registration,
    validate_installation_receipt,
    verify_slot_contents,
)
from .qualification import (
    INDEPENDENT_RESULT_DOMAIN,
    CompanionObservation,
    ProcessObservation,
    build_qualification_record,
    classify_process,
    validate_qualification_record,
    write_qualification_record_exclusive,
)
from .ustar import ArchiveMemberExpectation, ArchiveValidationError, validate_ustar


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs"
RECORD_PATH = (
    REPO_ROOT
    / "contracts/checker-runtime-payloads-v0.1/records"
    / "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
)
VERIFIER = {
    "identity": "sha256:" + ("1" * 64),
    "name": "radishaxiom-launcher-conformance-core",
    "version": "0.1-test",
}


def _refresh_document_digest(value: dict[str, Any], field: str, domain: str) -> None:
    body = {key: item for key, item in value.items() if key != field}
    value[field] = domain_digest(domain, body)


def _synthetic_binary() -> bytes:
    header = bytearray(32)
    header[:4] = bytes.fromhex("cffaedfe")
    header[4:8] = (0x0100000C).to_bytes(4, "little")
    return bytes(header) + b"radishaxiom-synthetic-checker"


def _synthetic_record(
    record: dict[str, Any],
    *,
    binary: bytes | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    value = copy.deepcopy(record)
    if binary is not None:
        value["artifact"]["byte_length"] = str(len(binary))
        value["artifact"]["raw_sha256"] = raw_digest(binary)
        distribution_bytes = b"synthetic-distribution-for-local-fixtures"
        distribution = value["durable_registration"]["distribution_package"]
        distribution["byte_length"] = str(len(distribution_bytes))
        distribution["raw_sha256"] = raw_digest(distribution_bytes)
        asset = value["durable_registration"]["provider"]["release"]["asset"]
        asset["byte_length"] = distribution["byte_length"]
        asset["raw_sha256"] = distribution["raw_sha256"]
        asset["digest"] = distribution["raw_sha256"]
    if status is not None:
        value["registration"]["status"] = status
        value["registration"]["reasons"] = [f"synthetic-{status}-fixture"]
    _refresh_document_digest(value, "record_digest", REGISTRATION_DOMAIN)
    return value


def _synthetic_result(record: dict[str, Any], outcome: str) -> bytes:
    checker = record["checker"]
    value = {
        "checker": {
            "artifact": record["artifact"]["raw_sha256"],
            "name": checker["implementation"],
            "source": checker["source"]["identity"],
            "toolchain": checker["toolchain"],
            "version": checker["version"],
        },
        "result": {"kind": outcome},
        "result_version": "0.1",
    }
    return canonical_bytes(value)


def _synthetic_policy(
    policy: dict[str, Any],
    results: dict[str, bytes],
) -> dict[str, Any]:
    value = copy.deepcopy(policy)
    for row in value["runtime_companion"]["qualification_scenarios"]:
        data = results[row["id"]]
        row["byte_length"] = str(len(data))
        row["raw_sha256"] = raw_digest(data)
    _refresh_document_digest(value, "policy_digest", POLICY_DOMAIN)
    return value


def _octal(value: int, width: int) -> bytes:
    digits = f"{value:0{width - 1}o}".encode("ascii")
    if len(digits) != width - 1:
        raise ValueError("fixture octal field overflow")
    return digits + b"\0"


def _ustar(
    entries: list[tuple[str, bytes, int, bytes]],
) -> bytes:
    archive = bytearray()
    for name, data, mode, typeflag in entries:
        header = bytearray(512)
        encoded_name = name.encode("ascii")
        if len(encoded_name) > 99:
            raise ValueError("fixture name too long")
        header[: len(encoded_name)] = encoded_name
        header[100:108] = _octal(mode, 8)
        header[108:116] = _octal(0, 8)
        header[116:124] = _octal(0, 8)
        header[124:136] = _octal(len(data), 12)
        header[136:148] = _octal(0, 12)
        header[148:156] = b"        "
        header[156:157] = typeflag
        header[257:263] = b"ustar\0"
        header[263:265] = b"00"
        header[329:337] = _octal(0, 8)
        header[337:345] = _octal(0, 8)
        checksum = sum(header)
        header[148:156] = f"{checksum:06o}".encode("ascii") + b"\0 "
        archive.extend(header)
        archive.extend(data)
        archive.extend(bytes((-len(data)) % 512))
    archive.extend(bytes(1024))
    return bytes(archive)


def _make_staging(
    managed_root: Path,
    name: str,
    binary: bytes,
    receipt: bytes,
) -> Path:
    staging_parent = managed_root / ".staging"
    staging_parent.mkdir(exist_ok=True)
    os.chmod(staging_parent, 0o755)
    staging = staging_parent / name
    staging.mkdir()
    os.chmod(staging, 0o755)
    payload = staging / "payload"
    payload.mkdir()
    os.chmod(payload, 0o755)
    executable = payload / "radishaxiom-independent-checker-go"
    executable.write_bytes(binary)
    os.chmod(executable, 0o755)
    receipt_path = staging / "checker-runtime-installation-receipt-v0.1.jcs"
    receipt_path.write_bytes(receipt)
    os.chmod(receipt_path, 0o644)
    return staging


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_launcher_policy(POLICY_PATH)
        cls.record = load_registration_record(RECORD_PATH)
        cls.target = Target.from_json(cls.record["target"])

    def test_inactive_record_is_qualification_only(self) -> None:
        selected = select_registration(
            self.policy,
            [self.record],
            HostIdentity(self.target),
            "qualification",
        )
        self.assertEqual(selected["id"], self.record["id"])
        with self.assertRaisesRegex(LauncherValidationError, "selection-cardinality") as raised:
            select_registration(
                self.policy,
                [self.record],
                HostIdentity(self.target),
                "product",
            )
        self.assertEqual(raised.exception.classification, "runtime-unavailable")

    def test_exact_active_record_is_product_selectable(self) -> None:
        active = _synthetic_record(self.record, status="active")
        selected = select_registration(
            self.policy,
            [active],
            HostIdentity(self.target),
            "product",
        )
        self.assertEqual(selected["record_digest"], active["record_digest"])

    def test_duplicate_active_record_fails_closed(self) -> None:
        active = _synthetic_record(self.record, status="active")
        with self.assertRaisesRegex(LauncherValidationError, "selection-cardinality"):
            select_registration(
                self.policy,
                [active, copy.deepcopy(active)],
                HostIdentity(self.target),
                "product",
            )

    def test_target_and_translation_do_not_fallback(self) -> None:
        active = _synthetic_record(self.record, status="active")
        wrong_variant = Target(
            goos="darwin",
            goarch="arm64",
            goarm64="v8.1",
            executable_format="macho-64-arm64",
        )
        for host in (
            HostIdentity(wrong_variant),
            HostIdentity(self.target, translated_process=True),
        ):
            with self.subTest(host=host):
                with self.assertRaises(LauncherValidationError) as raised:
                    select_registration(self.policy, [active], host, "product")
                self.assertEqual(raised.exception.classification, "runtime-unavailable")

    def test_target_components_cannot_escape_slot_root(self) -> None:
        with self.assertRaisesRegex(LauncherValidationError, "invalid-target-component"):
            Target(
                goos="..",
                goarch="arm64",
                goarm64="v8.0",
                executable_format="macho-64-arm64",
            )

    def test_product_host_store_and_network_boundaries_fail_closed(self) -> None:
        mutations = (
            (("implementation", "language"), "python", "product-runtime-host"),
            (
                ("implementation", "checker_boundary"),
                "in-process-go-parser-reuse",
                "checker-implementation-reuse",
            ),
            (
                ("implementation", "network_capability"),
                "provider-download-enabled",
                "runtime-core-network-capability",
            ),
            (
                ("persistence", "root_discovery"),
                "environment-or-current-directory",
                "runtime-store-root-discovery",
            ),
        )
        for path, replacement, code in mutations:
            with self.subTest(code=code):
                value = copy.deepcopy(self.policy)
                value[path[0]][path[1]] = replacement
                _refresh_document_digest(value, "policy_digest", POLICY_DOMAIN)
                with self.assertRaisesRegex(LauncherValidationError, code):
                    select_registration(
                        value,
                        [self.record],
                        HostIdentity(self.target),
                        "qualification",
                    )

    def test_superseded_policy_version_is_not_accepted(self) -> None:
        value = copy.deepcopy(self.policy)
        value["format_version"] = "0.1"
        _refresh_document_digest(value, "policy_digest", POLICY_DOMAIN)
        with self.assertRaisesRegex(LauncherValidationError, "policy-version"):
            select_registration(
                value,
                [self.record],
                HostIdentity(self.target),
                "qualification",
            )

    def test_installation_and_store_roots_cannot_diverge(self) -> None:
        value = copy.deepcopy(self.policy)
        value["installation"]["root"] = "separately-discovered-installation-root"
        _refresh_document_digest(value, "policy_digest", POLICY_DOMAIN)
        with self.assertRaisesRegex(LauncherValidationError, "runtime-store-root"):
            select_registration(
                value,
                [self.record],
                HostIdentity(self.target),
                "qualification",
            )


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.binary = _synthetic_binary()
        self.receipt = b'{"fixture":"receipt"}'
        self.entries = [
            ("payload/radishaxiom-independent-checker-go", self.binary, 0o755, b"0"),
            ("checker-runtime-installation-receipt-v0.1.jcs", self.receipt, 0o644, b"0"),
        ]
        self.expected = tuple(
            ArchiveMemberExpectation(name, mode, len(data), raw_digest(data))
            for name, data, mode, _ in self.entries
        )

    def test_exact_closed_inventory_is_accepted(self) -> None:
        members = validate_ustar(_ustar(self.entries), self.expected)
        self.assertEqual([item.name for item in members], [item.name for item in self.expected])

    def test_forbidden_paths_and_types_are_rejected(self) -> None:
        cases = (
            ([('/absolute', b'x', 0o644, b"0")], "absolute-path"),
            ([('../escape', b'x', 0o644, b"0")], "dot-dot-or-empty-component"),
            ([('payload/link', b'', 0o755, b"2")], "symbolic-link"),
            ([('payload/hard', b'', 0o755, b"1")], "hard-link"),
            ([('payload/pax', b'', 0o644, b"x")], "pax-or-xattr"),
            ([('payload/null-type', b'', 0o644, b"\0")], "unknown-member-or-mode"),
        )
        for entries, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(ArchiveValidationError, code):
                    validate_ustar(_ustar(entries), self.expected)

    def test_mode_digest_order_and_trailing_bytes_are_rejected(self) -> None:
        wrong_mode = copy.deepcopy(self.entries)
        wrong_mode[0] = (wrong_mode[0][0], wrong_mode[0][1], 0o644, b"0")
        wrong_digest = list(self.expected)
        wrong_digest[0] = ArchiveMemberExpectation(
            wrong_digest[0].name,
            wrong_digest[0].mode,
            wrong_digest[0].byte_length,
            "sha256:" + ("0" * 64),
        )
        cases = (
            (_ustar(wrong_mode), self.expected, "unknown-member-or-mode"),
            (_ustar(self.entries), tuple(wrong_digest), "member-digest-mismatch"),
            (_ustar(list(reversed(self.entries))), self.expected, "unknown-member-or-order"),
            (_ustar(self.entries) + bytes(512), self.expected, "extra-or-trailing-bytes"),
        )
        for archive, expected, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(ArchiveValidationError, code):
                    validate_ustar(archive, expected)

    def test_noncanonical_header_profile_is_rejected(self) -> None:
        archive = bytearray(_ustar(self.entries))
        archive[108] = ord("1")
        archive[148:156] = b"        "
        archive[148:156] = f"{sum(archive[:512]):06o}".encode("ascii") + b"\0 "
        with self.assertRaisesRegex(ArchiveValidationError, "noncanonical-header"):
            validate_ustar(bytes(archive), self.expected)


class InstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_launcher_policy(POLICY_PATH)
        cls.original_record = load_registration_record(RECORD_PATH)
        cls.binary = _synthetic_binary()
        cls.record = _synthetic_record(cls.original_record, binary=cls.binary)

    def _receipt(self, installed_at: str = "2026-08-30T10:00:00Z"):
        return build_installation_receipt(
            self.policy,
            self.record,
            installed_at=installed_at,
            verifier=VERIFIER,
        )

    def test_receipt_is_canonical_and_closed(self) -> None:
        receipt = self._receipt()
        parsed = validate_installation_receipt(receipt.canonical, self.policy, self.record)
        self.assertEqual(parsed.document_digest, receipt.document_digest)
        self.assertFalse(receipt.canonical.endswith(b"\n"))
        self.assertNotIn(tempfile.gettempdir().encode(), receipt.canonical)
        with self.assertRaisesRegex(LauncherValidationError, "noncanonical-json"):
            validate_installation_receipt(receipt.canonical + b"\n", self.policy, self.record)

    def test_real_record_receipt_matches_rust_golden(self) -> None:
        receipt = build_installation_receipt(
            self.policy,
            self.original_record,
            installed_at="2026-08-30T10:00:00Z",
            verifier=VERIFIER,
        )
        self.assertEqual(len(receipt.canonical), 1_797)
        self.assertEqual(
            raw_digest(receipt.canonical),
            "sha256:54c1dad27b5f35efcc706a8599dd1b23798de9cda1ce313b48bbec798efe53c1",
        )
        self.assertEqual(
            receipt.document_digest,
            "sha256:7a53b34f39059e97363a87d33532ee265cf4faa3d438a22a709f25ee47170ac2",
        )

    def test_atomic_publish_and_exact_reuse(self) -> None:
        receipt = self._receipt()
        with tempfile.TemporaryDirectory(prefix="radishaxiom-launcher-") as temporary:
            managed_root = Path(temporary) / "managed"
            managed_root.mkdir()
            first = _make_staging(managed_root, "first", self.binary, receipt.canonical)
            final, action, first_verification = publish_staged_slot(
                managed_root,
                first,
                self.policy,
                self.record,
                lock_held=True,
            )
            self.assertEqual(action, "published")
            self.assertTrue(final.is_dir())
            self.assertFalse(first.exists())

            second = _make_staging(managed_root, "second", self.binary, receipt.canonical)
            reused, action, second_verification = publish_staged_slot(
                managed_root,
                second,
                self.policy,
                self.record,
                lock_held=True,
            )
            self.assertEqual((reused, action), (final, "reused"))
            self.assertEqual(first_verification, second_verification)
            self.assertFalse(second.exists())

    def test_mismatched_existing_slot_is_not_overwritten(self) -> None:
        receipt = self._receipt()
        changed_receipt = self._receipt("2026-08-30T10:00:01Z")
        with tempfile.TemporaryDirectory(prefix="radishaxiom-launcher-") as temporary:
            managed_root = Path(temporary) / "managed"
            managed_root.mkdir()
            first = _make_staging(managed_root, "first", self.binary, receipt.canonical)
            final, _, original = publish_staged_slot(
                managed_root,
                first,
                self.policy,
                self.record,
                lock_held=True,
            )
            second = _make_staging(
                managed_root,
                "second",
                self.binary,
                changed_receipt.canonical,
            )
            with self.assertRaisesRegex(LauncherValidationError, "existing-slot-mismatch"):
                publish_staged_slot(
                    managed_root,
                    second,
                    self.policy,
                    self.record,
                    lock_held=True,
                )
            self.assertTrue(second.exists())
            self.assertEqual(
                verify_slot_contents(managed_root, final, self.policy, self.record),
                original,
            )

    def test_symlink_and_missing_lock_do_not_publish(self) -> None:
        receipt = self._receipt()
        with tempfile.TemporaryDirectory(prefix="radishaxiom-launcher-") as temporary:
            managed_root = Path(temporary) / "managed"
            managed_root.mkdir()
            unlocked = _make_staging(managed_root, "unlocked", self.binary, receipt.canonical)
            with self.assertRaisesRegex(LauncherValidationError, "installation-lock-required"):
                publish_staged_slot(
                    managed_root,
                    unlocked,
                    self.policy,
                    self.record,
                    lock_held=False,
                )
            executable = unlocked / "payload/radishaxiom-independent-checker-go"
            executable.unlink()
            executable.symlink_to("../checker-runtime-installation-receipt-v0.1.jcs")
            with self.assertRaises(LauncherValidationError):
                publish_staged_slot(
                    managed_root,
                    unlocked,
                    self.policy,
                    self.record,
                    lock_held=True,
                )
            self.assertFalse((managed_root / "slots").exists())


class QualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_policy = load_launcher_policy(POLICY_PATH)
        original_record = load_registration_record(RECORD_PATH)
        cls.record = _synthetic_record(original_record, binary=_synthetic_binary())
        outcomes = {
            "ax-b01-correct": "accepted-with-trust",
            "chk-digest-01": "rejected",
            "chk-resource-01": "incomplete",
        }
        cls.results = {
            scenario: _synthetic_result(cls.record, outcome)
            for scenario, outcome in outcomes.items()
        }
        cls.policy = _synthetic_policy(original_policy, cls.results)
        cls.observations = [
            CompanionObservation(scenario, cls.results[scenario], True)
            for scenario in sorted(cls.results)
        ]
        cls.receipt = build_installation_receipt(
            cls.policy,
            cls.record,
            installed_at="2026-08-30T10:00:00Z",
            verifier=VERIFIER,
        )

    def test_exact_three_companions_form_exclusive_record(self) -> None:
        record = build_qualification_record(
            self.policy,
            self.record,
            self.receipt,
            self.observations,
            qualified_at="2026-08-30T10:01:00Z",
        )
        validated = validate_qualification_record(record.canonical)
        self.assertEqual(validated.document_digest, record.document_digest)
        expected_documents = {
            scenario: domain_digest(
                INDEPENDENT_RESULT_DOMAIN,
                json.loads(data),
            )
            for scenario, data in self.results.items()
        }
        actual_documents = {
            item["scenario_id"]: item["document_digest"]
            for item in record.value["companions"]
        }
        self.assertEqual(actual_documents, expected_documents)
        with tempfile.TemporaryDirectory(prefix="radishaxiom-qualification-") as temporary:
            path = Path(temporary) / "qualification.jcs"
            write_qualification_record_exclusive(path, record)
            self.assertEqual(path.read_bytes(), record.canonical)
            with self.assertRaises(FileExistsError):
                write_qualification_record_exclusive(path, record)

    def test_missing_unvalidated_and_wrong_outcome_fail_closed(self) -> None:
        missing = self.observations[:-1]
        unvalidated = list(self.observations)
        unvalidated[0] = CompanionObservation(
            unvalidated[0].scenario_id,
            unvalidated[0].canonical_result,
            False,
        )
        wrong_result = _synthetic_result(self.record, "accepted")
        wrong_results = dict(self.results)
        wrong_results["ax-b01-correct"] = wrong_result
        wrong_policy = _synthetic_policy(self.policy, wrong_results)
        wrong_observations = list(self.observations)
        wrong_observations[0] = CompanionObservation("ax-b01-correct", wrong_result, True)
        cases = (
            (self.policy, missing, "qualification-scenario-set"),
            (self.policy, unvalidated, "qualification-contract-not-validated"),
            (wrong_policy, wrong_observations, "qualification-outcome"),
        )
        for policy, observations, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(LauncherValidationError, code):
                    build_qualification_record(
                        policy,
                        self.record,
                        build_installation_receipt(
                            policy,
                            self.record,
                            installed_at="2026-08-30T10:00:00Z",
                            verifier=VERIFIER,
                        ),
                        observations,
                        qualified_at="2026-08-30T10:01:00Z",
                    )

    def test_digest_valid_but_incomplete_qualification_record_is_rejected(self) -> None:
        record = build_qualification_record(
            self.policy,
            self.record,
            self.receipt,
            self.observations,
            qualified_at="2026-08-30T10:01:00Z",
        )
        incomplete = copy.deepcopy(record.value)
        del incomplete["target"]
        _refresh_document_digest(
            incomplete,
            "document_digest",
            "radishaxiom.checker-runtime-qualification-record.v0.1",
        )
        with self.assertRaisesRegex(LauncherValidationError, "missing-member"):
            validate_qualification_record(canonical_bytes(incomplete))


class ProcessClassificationTests(unittest.TestCase):
    def test_process_and_identity_failures_never_become_four_state_results(self) -> None:
        cases = (
            (ProcessObservation(), ("completed", "consumable")),
            (
                ProcessObservation(preflight_available=False),
                ("runtime-unavailable", "not-produced"),
            ),
            (ProcessObservation(spawned=False), ("process-failure", "not-produced")),
            (ProcessObservation(timed_out=True), ("process-failure", "not-produced")),
            (ProcessObservation(killed=True), ("process-failure", "not-produced")),
            (ProcessObservation(signal=9), ("process-failure", "not-produced")),
            (ProcessObservation(exit_code=1), ("process-failure", "not-produced")),
            (
                ProcessObservation(stdout_complete=False),
                ("process-failure", "not-produced"),
            ),
            (
                ProcessObservation(canonical_result=False),
                ("process-failure", "not-produced"),
            ),
            (
                ProcessObservation(result_identity_matches=False),
                ("identity-failure", "not-consumable"),
            ),
            (
                ProcessObservation(postflight_identity_matches=False),
                ("identity-failure", "not-consumable"),
            ),
            (
                ProcessObservation(registration_still_active=False),
                ("identity-failure", "not-consumable"),
            ),
        )
        for observation, expected in cases:
            with self.subTest(observation=observation):
                outcome = classify_process(observation)
                self.assertEqual((outcome.classification, outcome.independent_result), expected)


def run() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__, fromlist=["*"]))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    print(f"checker runtime launcher conformance passed ({result.testsRun} tests)")
    return 0
