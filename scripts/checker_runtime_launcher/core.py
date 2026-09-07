"""Dependency-free local conformance core for ADR 0011 launcher boundaries.

This module validates policy decisions against synthetic filesystem and process
observations. It deliberately does not fetch, execute, install, or activate the
registered checker payload and is not a production launcher implementation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypeAlias


JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | bool
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
TARGET_COMPONENT = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
POLICY_VERSION = "0.3"
POLICY_DOMAIN = "radishaxiom.checker-runtime-launcher-policy.v0.3"
REGISTRATION_DOMAIN = "radishaxiom.checker-runtime-payload-registration.v0.1"
INSTALLATION_RECEIPT_DOMAIN = "radishaxiom.checker-runtime-installation-receipt.v0.1"


class LauncherValidationError(ValueError):
    def __init__(
        self,
        code: str,
        detail: str = "",
        classification: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.classification = classification


def validate_json(value: Any, path: str = "$") -> None:
    if type(value) is bool or isinstance(value, str):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise LauncherValidationError("non-string-member", path)
            validate_json(item, f"{path}.{key}")
        return
    raise LauncherValidationError("json-number-or-null", path)


def canonical_bytes(value: JsonValue) -> bytes:
    validate_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def domain_digest(domain: str, value: JsonValue) -> str:
    return raw_digest(domain.encode("ascii") + b"\0" + canonical_bytes(value))


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise LauncherValidationError("duplicate-member", key)
        value[key] = item
    return value


def _parse_json(data: bytes, *, require_canonical: bool) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LauncherValidationError("invalid-utf8") from exc
    try:
        value = json.loads(text, object_pairs_hook=_pairs)
    except LauncherValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise LauncherValidationError("invalid-json") from exc
    validate_json(value)
    if not isinstance(value, dict):
        raise LauncherValidationError("invalid-root")
    if require_canonical and canonical_bytes(value) != data:
        raise LauncherValidationError("noncanonical-json")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LauncherValidationError("invalid-object", path)
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise LauncherValidationError("invalid-array", path)
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise LauncherValidationError("invalid-string", path)
    return value


def _digest(value: Any, path: str) -> str:
    text = _string(value, path)
    if not SHA256_PATTERN.fullmatch(text):
        raise LauncherValidationError("invalid-digest", path)
    return text


def _keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    unknown = sorted(set(value) - expected)
    if unknown:
        raise LauncherValidationError("unknown-member", f"{path}.{unknown[0]}")
    missing = sorted(expected - set(value))
    if missing:
        raise LauncherValidationError("missing-member", f"{path}.{missing[0]}")


@dataclass(frozen=True, order=True, slots=True)
class Target:
    goos: str
    goarch: str
    goarm64: str
    executable_format: str

    def __post_init__(self) -> None:
        for name, value in (
            ("goos", self.goos),
            ("goarch", self.goarch),
            ("goarm64", self.goarm64),
            ("executable_format", self.executable_format),
        ):
            if value in {".", ".."} or not TARGET_COMPONENT.fullmatch(value):
                raise LauncherValidationError("invalid-target-component", name)

    @classmethod
    def from_json(cls, value: Any, path: str = "$.target") -> Target:
        obj = _object(value, path)
        _keys(obj, {"executable_format", "goarch", "goarm64", "goos"}, path)
        return cls(
            goos=_string(obj["goos"], f"{path}.goos"),
            goarch=_string(obj["goarch"], f"{path}.goarch"),
            goarm64=_string(obj["goarm64"], f"{path}.goarm64"),
            executable_format=_string(
                obj["executable_format"], f"{path}.executable_format"
            ),
        )

    def as_json(self) -> dict[str, str]:
        return {
            "executable_format": self.executable_format,
            "goarch": self.goarch,
            "goarm64": self.goarm64,
            "goos": self.goos,
        }


@dataclass(frozen=True, slots=True)
class HostIdentity:
    target: Target
    translated_process: bool = False


@dataclass(frozen=True, slots=True)
class SlotIdentity:
    target: Target
    distribution_raw_sha256: str

    def __post_init__(self) -> None:
        _digest(self.distribution_raw_sha256, "$.slot.distribution_raw_sha256")

    def relative_path(self) -> PurePosixPath:
        digest_component = self.distribution_raw_sha256.replace(":", "-")
        return PurePosixPath(
            "slots",
            self.target.goos,
            self.target.goarch,
            self.target.goarm64,
            self.target.executable_format,
            digest_component,
        )


@dataclass(frozen=True, slots=True)
class InstallationReceipt:
    value: dict[str, Any]
    canonical: bytes
    document_digest: str
    slot: SlotIdentity


@dataclass(frozen=True, slots=True)
class SlotVerification:
    artifact_raw_sha256: str
    artifact_byte_length: int
    receipt_document_digest: str
    tree_digest: str


def validate_launcher_policy(policy: dict[str, Any]) -> None:
    if policy.get("format") != "radishaxiom-checker-runtime-launcher-policy":
        raise LauncherValidationError("policy-format")
    if policy.get("format_version") != POLICY_VERSION:
        raise LauncherValidationError("policy-version")
    if policy.get("digest_domain") != POLICY_DOMAIN:
        raise LauncherValidationError("policy-domain")
    body = {key: item for key, item in policy.items() if key != "policy_digest"}
    if policy.get("policy_digest") != domain_digest(POLICY_DOMAIN, body):
        raise LauncherValidationError("policy-digest")

    host = _object(policy.get("host_selection"), "$.host_selection")
    if host.get("match") != "exact-goos-goarch-goarm64-executable-format":
        raise LauncherValidationError("target-fallback")
    if host.get("selection_cardinality") != "exactly-one-or-fail":
        raise LauncherValidationError("selection-cardinality-policy")
    if host.get("product_registration_status") != "active-only":
        raise LauncherValidationError("inactive-product-selection")
    if host.get("qualification_registration_status") != "registered-inactive-only":
        raise LauncherValidationError("qualification-selection")
    supported = [
        Target.from_json(item, "$.host_selection.current_supported_targets[]")
        for item in _array(
            host.get("current_supported_targets"),
            "$.host_selection.current_supported_targets",
        )
    ]
    if not supported or len(supported) != len(set(supported)):
        raise LauncherValidationError("supported-target-set")

    implementation = _object(policy.get("implementation"), "$.implementation")
    if (
        implementation.get("language") != "rust"
        or implementation.get("edition") != "2024"
        or implementation.get("toolchain") != "1.97.1"
        or implementation.get("workspace")
        != "same-cargo-workspace-and-product-release-graph-as-raxc"
    ):
        raise LauncherValidationError("product-runtime-host")
    if (
        implementation.get("checker_boundary")
        != "exact-digest-offline-subprocess-only-no-source-or-parser-reuse"
    ):
        raise LauncherValidationError("checker-implementation-reuse")
    if implementation.get("network_capability") != "absent-from-installer-launcher-core":
        raise LauncherValidationError("runtime-core-network-capability")
    if implementation.get("python_conformance") != "test-oracle-only-never-product-runtime":
        raise LauncherValidationError("python-runtime-dependency")
    if implementation.get("dependency_status") != "libc-0.2.189-exact-reviewed-and-authorized":
        raise LauncherValidationError("runtime-dependency-boundary")
    platform_binding = _object(
        implementation.get("platform_binding"), "$.implementation.platform_binding"
    )
    if platform_binding != {
        "build_boundary": "libc-upstream-build-script-only-no-project-c-shim",
        "crate": "radishaxiom-checker-runtime-darwin-store",
        "dependency": {
            "crates_io_checksum": "sha256:3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2",
            "license": "MIT OR Apache-2.0",
            "name": "libc",
            "version": "0.2.189",
        },
        "ffi": "darwin-filesystem-only",
        "target": "cfg-target-os-macos",
        "unsafe_boundary": "private-platform-crate-only-core-forbids-unsafe",
    }:
        raise LauncherValidationError("runtime-platform-binding")

    persistence = _object(policy.get("persistence"), "$.persistence")
    if persistence.get("interface") != "checker-runtime-store-v0.1":
        raise LauncherValidationError("runtime-store-interface")
    if persistence.get("root") != "product-injected-canonical-user-local-private-root":
        raise LauncherValidationError("runtime-store-root")
    if persistence.get("root_discovery") != "never-environment-cwd-repository-or-user-input":
        raise LauncherValidationError("runtime-store-root-discovery")
    installation = _object(policy.get("installation"), "$.installation")
    if installation.get("root") != persistence.get("root"):
        raise LauncherValidationError("runtime-store-root")
    if (
        installation.get("publication")
        != "same-filesystem-descriptor-relative-verified-staging-then-exclusive-renameatx-np"
    ):
        raise LauncherValidationError("runtime-store-publication")
    filesystem = _object(installation.get("filesystem"), "$.installation.filesystem")
    if filesystem != {
        "containment": "descriptor-relative-no-follow-beneath",
        "durability": "f-fullfsync-files-and-directories-before-success",
        "platform": "darwin",
        "publication": "renameatx-np-exclusive-no-follow-beneath",
        "required_primitives": [
            "f-fullfsync",
            "o-nofollow-any",
            "renameatx-np-rename-excl",
            "renameatx-np-rename-nofollow-any",
            "renameatx-np-rename-resolve-beneath",
        ],
        "unsupported": "fail-closed-no-weaker-fallback",
    }:
        raise LauncherValidationError("runtime-store-filesystem-boundary")
    expected_capabilities = [
        "acquire-target-lock",
        "create-owned-staging",
        "publish-slot-exclusive",
        "read-slot-exact",
        "create-qualification-exclusive",
        "append-attempt",
    ]
    if persistence.get("capabilities") != expected_capabilities:
        raise LauncherValidationError("runtime-store-capabilities")

    interfaces = _object(policy.get("runtime_interfaces"), "$.runtime_interfaces")
    if interfaces.get("fetch") != "separate-authorized-coordinator-never-core":
        raise LauncherValidationError("runtime-fetch-boundary")
    if (
        interfaces.get("result_consumer")
        != "single-product-rust-consumer-shared-by-qualification-and-invocation"
    ):
        raise LauncherValidationError("runtime-result-consumer")
    if (
        interfaces.get("outer_failure")
        != "typed-product-outcome-never-independent-result"
    ):
        raise LauncherValidationError("outer-failure-result-boundary")


def load_launcher_policy(path: Path) -> dict[str, Any]:
    policy = _parse_json(path.read_bytes(), require_canonical=True)
    validate_launcher_policy(policy)
    return policy


def validate_registration_record(record: dict[str, Any]) -> None:
    if record.get("format") != "radishaxiom-checker-runtime-payload-registration":
        raise LauncherValidationError("registration-format")
    if record.get("format_version") != "0.1":
        raise LauncherValidationError("registration-version")
    if record.get("digest_domain") != REGISTRATION_DOMAIN:
        raise LauncherValidationError("registration-domain")
    body = {key: item for key, item in record.items() if key != "record_digest"}
    if record.get("record_digest") != domain_digest(REGISTRATION_DOMAIN, body):
        raise LauncherValidationError("registration-digest")
    Target.from_json(record.get("target"))


def load_registration_record(path: Path) -> dict[str, Any]:
    record = _parse_json(path.read_bytes(), require_canonical=False)
    validate_registration_record(record)
    return record


def _supported_targets(policy: dict[str, Any]) -> set[Target]:
    host = _object(policy["host_selection"], "$.host_selection")
    return {
        Target.from_json(item, "$.host_selection.current_supported_targets[]")
        for item in _array(
            host["current_supported_targets"],
            "$.host_selection.current_supported_targets",
        )
    }


def select_registration(
    policy: dict[str, Any],
    records: list[dict[str, Any]],
    host: HostIdentity,
    purpose: Literal["product", "qualification"],
) -> dict[str, Any]:
    validate_launcher_policy(policy)
    if purpose not in {"product", "qualification"}:
        raise LauncherValidationError("invalid-selection-purpose")
    if host.translated_process:
        raise LauncherValidationError(
            "translated-process",
            classification="runtime-unavailable",
        )
    if host.target not in _supported_targets(policy):
        raise LauncherValidationError(
            "unsupported-target",
            classification="runtime-unavailable",
        )
    status = "active" if purpose == "product" else "registered-inactive"
    matches: list[dict[str, Any]] = []
    for record in records:
        validate_registration_record(record)
        registration = _object(record.get("registration"), "$.registration")
        if (
            Target.from_json(record.get("target")) == host.target
            and registration.get("status") == status
        ):
            matches.append(record)
    if len(matches) != 1:
        raise LauncherValidationError(
            "selection-cardinality",
            f"expected 1 {status} record, found {len(matches)}",
            classification="runtime-unavailable",
        )
    return matches[0]


def _installation_bindings(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_registration_record(record)
    durable = _object(record.get("durable_registration"), "$.durable_registration")
    distribution = _object(
        durable.get("distribution_package"),
        "$.durable_registration.distribution_package",
    )
    _digest(distribution.get("raw_sha256"), "$.distribution.raw_sha256")
    _string(distribution.get("byte_length"), "$.distribution.byte_length")
    provider = _object(durable.get("provider"), "$.durable_registration.provider")
    release = _object(provider.get("release"), "$.durable_registration.provider.release")
    asset = _object(release.get("asset"), "$.durable_registration.provider.release.asset")
    if asset.get("raw_sha256") != distribution["raw_sha256"]:
        raise LauncherValidationError("provider-distribution-digest")
    if asset.get("byte_length") != distribution["byte_length"]:
        raise LauncherValidationError("provider-distribution-length")
    if asset.get("name") != distribution.get("filename"):
        raise LauncherValidationError("provider-distribution-name")
    if release.get("immutable") is not True or release.get("draft") is not False:
        raise LauncherValidationError("provider-release-not-immutable")
    return distribution, provider


def slot_identity(record: dict[str, Any]) -> SlotIdentity:
    distribution, _ = _installation_bindings(record)
    return SlotIdentity(
        target=Target.from_json(record["target"]),
        distribution_raw_sha256=_digest(
            distribution["raw_sha256"], "$.distribution.raw_sha256"
        ),
    )


def _validate_verifier(verifier: dict[str, Any]) -> None:
    _keys(verifier, {"identity", "name", "version"}, "$.verifier")
    _digest(verifier.get("identity"), "$.verifier.identity")
    _string(verifier.get("name"), "$.verifier.name")
    _string(verifier.get("version"), "$.verifier.version")


def build_installation_receipt(
    policy: dict[str, Any],
    record: dict[str, Any],
    *,
    installed_at: str,
    verifier: dict[str, Any],
) -> InstallationReceipt:
    validate_launcher_policy(policy)
    validate_registration_record(record)
    registration = _object(record.get("registration"), "$.registration")
    if registration.get("status") != "registered-inactive":
        raise LauncherValidationError("installation-requires-registered-inactive")
    if not UTC_TIMESTAMP.fullmatch(installed_at):
        raise LauncherValidationError("invalid-installation-time")
    _validate_verifier(verifier)
    distribution, provider = _installation_bindings(record)
    release = _object(provider["release"], "$.durable_registration.provider.release")
    asset = _object(release["asset"], "$.durable_registration.provider.release.asset")
    checker = _object(record.get("checker"), "$.checker")
    source = _object(checker.get("source"), "$.checker.source")
    artifact = _object(record.get("artifact"), "$.artifact")
    slot = slot_identity(record)
    body: dict[str, Any] = {
        "artifact": {
            "byte_length": _string(artifact.get("byte_length"), "$.artifact.byte_length"),
            "raw_sha256": _digest(artifact.get("raw_sha256"), "$.artifact.raw_sha256"),
        },
        "checker": {
            "implementation": _string(checker.get("implementation"), "$.checker.implementation"),
            "source": _digest(source.get("identity"), "$.checker.source.identity"),
            "toolchain": _string(checker.get("toolchain"), "$.checker.toolchain"),
            "version": _string(checker.get("version"), "$.checker.version"),
        },
        "digest_domain": INSTALLATION_RECEIPT_DOMAIN,
        "distribution": {
            "byte_length": distribution["byte_length"],
            "raw_sha256": distribution["raw_sha256"],
        },
        "format": "radishaxiom-checker-runtime-installation-receipt",
        "format_version": "0.1",
        "installed_at": installed_at,
        "provider": {
            "asset_id": _string(asset.get("id"), "$.provider.asset.id"),
            "asset_name": _string(asset.get("name"), "$.provider.asset.name"),
            "release_id": _string(release.get("id"), "$.provider.release.id"),
            "release_tag": _string(release.get("tag"), "$.provider.release.tag"),
            "repository": _string(provider.get("repository"), "$.provider.repository"),
            "target_commit": _string(
                release.get("target_commit"), "$.provider.release.target_commit"
            ),
        },
        "registration": {
            "id": _string(record.get("id"), "$.registration_record.id"),
            "record_digest": _digest(
                record.get("record_digest"), "$.registration_record.record_digest"
            ),
        },
        "slot": {
            "relative_identity": slot.relative_path().as_posix(),
            "state": "installed-inactive",
        },
        "target": slot.target.as_json(),
        "verifier": dict(verifier),
    }
    document = {
        **body,
        "document_digest": domain_digest(INSTALLATION_RECEIPT_DOMAIN, body),
    }
    encoded = canonical_bytes(document)
    return InstallationReceipt(
        value=document,
        canonical=encoded,
        document_digest=document["document_digest"],
        slot=slot,
    )


def validate_installation_receipt(
    data: bytes,
    policy: dict[str, Any],
    record: dict[str, Any],
) -> InstallationReceipt:
    value = _parse_json(data, require_canonical=True)
    _keys(
        value,
        {
            "artifact",
            "checker",
            "digest_domain",
            "distribution",
            "document_digest",
            "format",
            "format_version",
            "installed_at",
            "provider",
            "registration",
            "slot",
            "target",
            "verifier",
        },
        "$",
    )
    if value.get("digest_domain") != INSTALLATION_RECEIPT_DOMAIN:
        raise LauncherValidationError("receipt-domain")
    if value.get("format") != "radishaxiom-checker-runtime-installation-receipt":
        raise LauncherValidationError("receipt-format")
    if value.get("format_version") != "0.1":
        raise LauncherValidationError("receipt-version")
    body = {key: item for key, item in value.items() if key != "document_digest"}
    if value.get("document_digest") != domain_digest(INSTALLATION_RECEIPT_DOMAIN, body):
        raise LauncherValidationError("receipt-document-digest")
    verifier = _object(value.get("verifier"), "$.verifier")
    expected = build_installation_receipt(
        policy,
        record,
        installed_at=_string(value.get("installed_at"), "$.installed_at"),
        verifier=verifier,
    )
    if value != expected.value:
        raise LauncherValidationError("receipt-binding-mismatch")
    return expected


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def _relative_entries(root: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    files: dict[str, Path] = {}
    directories: dict[str, Path] = {}
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in dirnames:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise LauncherValidationError("symbolic-link", relative)
            directories[relative] = path
        for name in filenames:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            files[relative] = path
    return files, directories


def _require_no_symlink_components(managed_root: Path, target: Path) -> None:
    managed_absolute = Path(os.path.abspath(managed_root))
    target_absolute = Path(os.path.abspath(target))
    try:
        relative = target_absolute.relative_to(managed_absolute)
    except ValueError as exc:
        raise LauncherValidationError("slot-root-escape") from exc
    current = managed_absolute
    if current.is_symlink():
        raise LauncherValidationError("symbolic-link", current.as_posix())
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise LauncherValidationError("symbolic-link", current.as_posix())


def _inspect_macho_arm64(data: bytes) -> None:
    if len(data) < 32 or data[:4] != bytes.fromhex("cffaedfe"):
        raise LauncherValidationError("executable-format-mismatch")
    if int.from_bytes(data[4:8], "little") != 0x0100000C:
        raise LauncherValidationError("executable-architecture-mismatch")


def _tree_digest(root: Path, files: dict[str, Path], directories: dict[str, Path]) -> str:
    rows: list[dict[str, str]] = []
    for name, path in sorted(directories.items()):
        rows.append({"kind": "directory", "mode": f"{_mode(path):04o}", "path": name})
    for name, path in sorted(files.items()):
        data = path.read_bytes()
        rows.append(
            {
                "byte_length": str(len(data)),
                "kind": "file",
                "mode": f"{_mode(path):04o}",
                "path": name,
                "raw_sha256": raw_digest(data),
            }
        )
    return domain_digest("radishaxiom.checker-runtime-slot-tree.v0.1", rows)


def verify_slot_contents(
    managed_root: Path,
    slot_root: Path,
    policy: dict[str, Any],
    record: dict[str, Any],
) -> SlotVerification:
    validate_launcher_policy(policy)
    validate_registration_record(record)
    _require_no_symlink_components(managed_root, slot_root)
    managed_real = managed_root.resolve(strict=True)
    if managed_root.is_symlink() or slot_root.is_symlink():
        raise LauncherValidationError("symbolic-link", slot_root.as_posix())
    slot_real = slot_root.resolve(strict=True)
    try:
        slot_real.relative_to(managed_real)
    except ValueError as exc:
        raise LauncherValidationError("slot-root-escape") from exc
    if not slot_root.is_dir():
        raise LauncherValidationError("slot-not-directory")
    if _mode(slot_root) != 0o755:
        raise LauncherValidationError("slot-directory-mode")

    installation = _object(policy.get("installation"), "$.installation")
    executable_policy = _object(installation.get("executable"), "$.installation.executable")
    receipt_policy = _object(installation.get("receipt"), "$.installation.receipt")
    executable_name = _string(
        executable_policy.get("relative_path"),
        "$.installation.executable.relative_path",
    )
    receipt_name = _string(receipt_policy.get("filename"), "$.installation.receipt.filename")
    expected_files = {executable_name, receipt_name}
    expected_directories = {
        parent.as_posix()
        for name in expected_files
        for parent in PurePosixPath(name).parents
        if parent != PurePosixPath(".")
    }
    files, directories = _relative_entries(slot_root)
    if set(files) != expected_files or set(directories) != expected_directories:
        raise LauncherValidationError("slot-inventory-mismatch")
    for name, path in directories.items():
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o755:
            raise LauncherValidationError("slot-directory-mode", name)

    artifact = _object(record.get("artifact"), "$.artifact")
    executable = files[executable_name]
    executable_stat = executable.lstat()
    if (
        not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_nlink != 1
        or stat.S_IMODE(executable_stat.st_mode) != 0o755
    ):
        raise LauncherValidationError("executable-file-boundary")
    executable_bytes = executable.read_bytes()
    if str(len(executable_bytes)) != artifact.get("byte_length"):
        raise LauncherValidationError("executable-length-mismatch")
    if raw_digest(executable_bytes) != artifact.get("raw_sha256"):
        raise LauncherValidationError("executable-digest-mismatch")
    _inspect_macho_arm64(executable_bytes)

    receipt_path = files[receipt_name]
    receipt_stat = receipt_path.lstat()
    if (
        not stat.S_ISREG(receipt_stat.st_mode)
        or receipt_stat.st_nlink != 1
        or stat.S_IMODE(receipt_stat.st_mode) != 0o644
    ):
        raise LauncherValidationError("receipt-file-boundary")
    receipt = validate_installation_receipt(receipt_path.read_bytes(), policy, record)
    return SlotVerification(
        artifact_raw_sha256=raw_digest(executable_bytes),
        artifact_byte_length=len(executable_bytes),
        receipt_document_digest=receipt.document_digest,
        tree_digest=_tree_digest(slot_root, files, directories),
    )


def _ensure_slot_parents(managed_root: Path, relative: PurePosixPath) -> Path:
    current = managed_root
    for component in relative.parts[:-1]:
        current = current / component
        if current.exists():
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or current.is_symlink():
                raise LauncherValidationError("slot-parent-boundary", current.as_posix())
            if stat.S_IMODE(info.st_mode) != 0o755:
                raise LauncherValidationError("slot-parent-mode", current.as_posix())
        else:
            current.mkdir(mode=0o755)
            os.chmod(current, 0o755)
    return managed_root / Path(*relative.parts)


def _discard_owned_staging(managed_root: Path, staging: Path) -> None:
    staging_parent = (managed_root / ".staging").resolve(strict=True)
    if staging.resolve(strict=True).parent != staging_parent or staging.is_symlink():
        raise LauncherValidationError("unowned-staging")
    shutil.rmtree(staging)


def publish_staged_slot(
    managed_root: Path,
    staging: Path,
    policy: dict[str, Any],
    record: dict[str, Any],
    *,
    lock_held: bool,
) -> tuple[Path, Literal["published", "reused"], SlotVerification]:
    if not lock_held:
        raise LauncherValidationError("installation-lock-required")
    managed_real = managed_root.resolve(strict=True)
    staging_parent = (managed_root / ".staging").resolve(strict=True)
    staging_real = staging.resolve(strict=True)
    if (
        staging_real.parent != staging_parent
        or staging.is_symlink()
        or staging.parent.is_symlink()
    ):
        raise LauncherValidationError("unowned-staging")
    staged_verification = verify_slot_contents(managed_root, staging, policy, record)
    slot = slot_identity(record)
    final = _ensure_slot_parents(managed_root, slot.relative_path())
    if staging.stat().st_dev != final.parent.stat().st_dev:
        raise LauncherValidationError("cross-filesystem-publication")

    if final.exists():
        final_verification = verify_slot_contents(managed_root, final, policy, record)
        if final_verification.tree_digest != staged_verification.tree_digest:
            raise LauncherValidationError("existing-slot-mismatch")
        _discard_owned_staging(managed_root, staging)
        return final, "reused", final_verification

    os.rename(staging, final)
    final_verification = verify_slot_contents(managed_root, final, policy, record)
    if final_verification != staged_verification:
        raise LauncherValidationError("post-publication-verification")
    if final.resolve(strict=True).parent == managed_real:
        raise LauncherValidationError("invalid-slot-depth")
    return final, "published", final_verification
