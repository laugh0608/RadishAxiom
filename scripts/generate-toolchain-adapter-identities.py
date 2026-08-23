#!/usr/bin/env python3
"""Generate and validate the toolchain / adapter identity registry v0.1.

The registry records reviewed publisher metadata and points to separately
versioned payload acceptance records. It never derives acceptance from a
version match or from another platform's artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = REPO_ROOT / "contracts/toolchain-adapters-v0.1"
FORMAT = "radishaxiom-toolchain-adapter-identities"
FORMAT_VERSION = "0.1"
DIGEST_DOMAIN = "radishaxiom.toolchain-adapter-identities.v0.1"
REVIEW_DATE = "2026-08-23"

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]*$")

ACCEPTED_ARTIFACTS = {
    "go1.26.7.darwin-arm64.tar.gz": (
        "contracts/toolchain-payload-acceptance-v0.1/records/"
        "go1.26.7-darwin-arm64.acceptance.json"
    ),
    "go1.26.7.src.tar.gz": (
        "contracts/toolchain-payload-acceptance-v0.1/records/"
        "go1.26.7-source.acceptance.json"
    ),
}

PLATFORMS = (
    {
        "architecture": "amd64",
        "id": "linux-amd64",
        "os": "linux",
        "rust_target": "x86_64-unknown-linux-gnu",
    },
    {
        "architecture": "arm64",
        "id": "linux-arm64",
        "os": "linux",
        "rust_target": "aarch64-unknown-linux-gnu",
    },
    {
        "architecture": "amd64",
        "id": "macos-amd64",
        "os": "macos",
        "rust_target": "x86_64-apple-darwin",
    },
    {
        "architecture": "arm64",
        "id": "macos-arm64",
        "os": "macos",
        "rust_target": "aarch64-apple-darwin",
    },
    {
        "architecture": "amd64",
        "id": "windows-amd64",
        "os": "windows",
        "rust_target": "x86_64-pc-windows-msvc",
    },
    {
        "architecture": "arm64",
        "id": "windows-arm64",
        "os": "windows",
        "rust_target": "aarch64-pc-windows-msvc",
    },
)

SOURCES = (
    {
        "id": "cvc5-copying-1.3.4",
        "kind": "license-bundle",
        "publisher": "cvc5",
        "reviewed_claims": [
            "cvc5-main-license",
            "gpl-build-distinction",
            "third-party-review-required",
        ],
        "url": "https://github.com/cvc5/cvc5/blob/cvc5-1.3.4/COPYING",
    },
    {
        "id": "cvc5-release-assets-1.3.4",
        "kind": "release-assets",
        "publisher": "cvc5",
        "reviewed_claims": [
            "artifact-filenames",
            "artifact-platforms",
            "publisher-recorded-sha256",
            "release-tag",
        ],
        "url": "https://github.com/cvc5/cvc5/releases/tag/cvc5-1.3.4",
    },
    {
        "id": "go-downloads-1.26.7",
        "kind": "release-index",
        "publisher": "Go project",
        "reviewed_claims": [
            "artifact-filenames",
            "artifact-platforms",
            "publisher-recorded-sha256",
            "source-archive",
        ],
        "url": "https://go.dev/dl/",
    },
    {
        "id": "go-license",
        "kind": "license",
        "publisher": "Go project",
        "reviewed_claims": ["go-main-license"],
        "url": "https://go.dev/LICENSE",
    },
    {
        "id": "node-license-24.19.0",
        "kind": "license-bundle",
        "publisher": "Node.js project",
        "reviewed_claims": [
            "node-main-license",
            "third-party-license-bundle-present",
        ],
        "url": "https://github.com/nodejs/node/blob/v24.19.0/LICENSE",
    },
    {
        "id": "node-shasums-24.19.0",
        "kind": "signed-checksum-manifest",
        "publisher": "Node.js project",
        "reviewed_claims": [
            "artifact-filenames",
            "artifact-platforms",
            "publisher-recorded-sha256",
            "signature-sidecars-present",
            "source-archive",
        ],
        "url": "https://nodejs.org/download/release/v24.19.0/SHASUMS256.txt",
    },
    {
        "id": "rust-dist-1.97.1",
        "kind": "release-index",
        "publisher": "Rust project",
        "reviewed_claims": [
            "publisher-checksum-endpoint-pattern",
            "release-version",
        ],
        "url": "https://static.rust-lang.org/dist/2026-07-16/index.html",
    },
    {
        "id": "rust-license",
        "kind": "license",
        "publisher": "Rust project",
        "reviewed_claims": ["rust-main-license"],
        "url": "https://rust-lang.org/policies/licenses/",
    },
    {
        "id": "rust-release-1.97.1",
        "kind": "release-announcement",
        "publisher": "Rust project",
        "reviewed_claims": [
            "miscompilation-fix",
            "release-date",
            "stable-release",
        ],
        "url": "https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/",
    },
)


def recorded_digest(sha256: str, source: str) -> dict[str, str]:
    return {
        "kind": "publisher-recorded",
        "sha256": sha256,
        "source": source,
    }


def pending_digest(source_url: str) -> dict[str, str]:
    return {
        "kind": "pending-publisher-capture",
        "reason": "checksum value was not captured from authoritative metadata",
        "source_url": source_url,
    }


def artifact(
    *,
    filename: str,
    platform: str,
    source_url: str,
    digest: dict[str, str],
) -> dict[str, Any]:
    result = {
        "acceptance": "not-accepted",
        "archive_inspection": "not-performed",
        "digest": digest,
        "filename": filename,
        "payload_verification": "not-downloaded",
        "platform": platform,
        "source_url": source_url,
    }
    acceptance_record = ACCEPTED_ARTIFACTS.get(filename)
    if acceptance_record is not None:
        result.update(
            {
                "acceptance": "accepted-for-controlled-build-input",
                "acceptance_record": acceptance_record,
                "archive_inspection": "passed-toolchain-tar-v0.1",
                "payload_verification": "sha256-matched-publisher-record",
            }
        )
    return result


def source_artifact(
    *, filename: str, source_url: str, digest: dict[str, str]
) -> dict[str, Any]:
    return artifact(
        filename=filename,
        platform="source",
        source_url=source_url,
        digest=digest,
    )


def rust_artifacts() -> list[dict[str, Any]]:
    base = "https://static.rust-lang.org/dist"
    result = [
        source_artifact(
            filename="rustc-1.97.1-src.tar.xz",
            source_url=f"{base}/rustc-1.97.1-src.tar.xz",
            digest=pending_digest(f"{base}/rustc-1.97.1-src.tar.xz.sha256"),
        )
    ]
    for platform in PLATFORMS:
        filename = f"rust-1.97.1-{platform['rust_target']}.tar.xz"
        result.append(
            artifact(
                filename=filename,
                platform=platform["id"],
                source_url=f"{base}/{filename}",
                digest=pending_digest(f"{base}/{filename}.sha256"),
            )
        )
    return sorted(result, key=lambda item: (item["platform"], item["filename"]))


def go_artifacts() -> list[dict[str, Any]]:
    base = "https://go.dev/dl"
    values = (
        ("source", "go1.26.7.src.tar.gz", "0ed24eac755105085b89fe9cabc2742b91a0ad7b94b59d3ad364918ebc8956ad"),
        ("linux-amd64", "go1.26.7.linux-amd64.tar.gz", "ffb5f8de10c62550dfddab66b36b57030721e0a44a3218e9e1181d7b59f121ca"),
        ("linux-arm64", "go1.26.7.linux-arm64.tar.gz", "5a4ec883379d51ee9ce1040d5e87f8d35e20387574dd8c947feb01eabc3c1b37"),
        ("macos-amd64", "go1.26.7.darwin-amd64.tar.gz", "92e8b34bff3c89ab16404c595669ac8cb004cc2f676dcbd1f5b87a6b8def3b47"),
        ("macos-arm64", "go1.26.7.darwin-arm64.tar.gz", "020a1e8224811be75163e920bc77e0926a1390a6aeea19bdcf23f74b9d749f6d"),
        ("windows-amd64", "go1.26.7.windows-amd64.zip", "f4f534a486e4bc3387fa18f08208f2f854b7aaea8a08f2a2d829a914a05abb11"),
        ("windows-arm64", "go1.26.7.windows-arm64.zip", "6f1b08de9e2dd94f69c52e524ab6834737275253291e8fd7f1c12ed4eceeda89"),
    )
    return [
        artifact(
            filename=filename,
            platform=platform,
            source_url=f"{base}/{filename}",
            digest=recorded_digest(sha256, "go-downloads-1.26.7"),
        )
        for platform, filename, sha256 in values
    ]


def cvc5_artifacts() -> list[dict[str, Any]]:
    base = "https://github.com/cvc5/cvc5/releases/download/cvc5-1.3.4"
    values = (
        ("linux-amd64", "cvc5-Linux-x86_64-static.zip", "dcdbfada0ce493ee98259c0816e0daafc561c223aadb3af298c2968e73ea39c6"),
        ("linux-arm64", "cvc5-Linux-arm64-static.zip", "2a4c108367f20b0c8990abd6b9535a5d62e08908d471d4671c00734e408f85bc"),
        ("macos-amd64", "cvc5-macOS-x86_64-static.zip", "5a7976affaf37dcf03ee44c3d0297c8e0ba08afd44ac832dab97400da726b852"),
        ("macos-arm64", "cvc5-macOS-arm64-static.zip", "3840aa53f6ee6fc357415dcfe291d7f5ffec6cfb1ccca6fef64120a0d2be4cb6"),
        ("windows-amd64", "cvc5-Win64-x86_64-static.zip", "279fe7e95810cfb62433fcfc2932f35325a665f32d3697ff33f75e31d5c6a179"),
        ("windows-arm64", "cvc5-Win64-arm64-static.zip", "2fd3e9c9aa6deb64fd1cd07ff20fe074985c306394d9003f8e278e10fc372360"),
    )
    result = [
        source_artifact(
            filename="cvc5-cvc5-1.3.4.tar.gz",
            source_url="https://github.com/cvc5/cvc5/archive/refs/tags/cvc5-1.3.4.tar.gz",
            digest=pending_digest(
                "https://github.com/cvc5/cvc5/releases/tag/cvc5-1.3.4"
            ),
        )
    ]
    result.extend(
        artifact(
            filename=filename,
            platform=platform,
            source_url=f"{base}/{filename}",
            digest=recorded_digest(sha256, "cvc5-release-assets-1.3.4"),
        )
        for platform, filename, sha256 in values
    )
    return sorted(result, key=lambda item: (item["platform"], item["filename"]))


def node_artifacts() -> list[dict[str, Any]]:
    base = "https://nodejs.org/download/release/v24.19.0"
    values = (
        ("source", "node-v24.19.0.tar.xz", "f6d95e10a0431ee1067fc6aabe9f762908b4716dd35324e1ddb4b1466b76659f"),
        ("linux-amd64", "node-v24.19.0-linux-x64.tar.xz", "14b342e71204f811bde6153be8e04b62aef63c236fef92b55f9c83154b409647"),
        ("linux-arm64", "node-v24.19.0-linux-arm64.tar.xz", "01443c1e1a29e531ccad5a46fefa6df490d2189c49f7955904aecdbb0fe86fdc"),
        ("macos-amd64", "node-v24.19.0-darwin-x64.tar.xz", "d35e95230f46f6f0751df497c56622c6735e05d5e1fb1630996a005b9d328fe4"),
        ("macos-arm64", "node-v24.19.0-darwin-arm64.tar.xz", "3f1cf157479c1480352083105e13faf9d008ede98e7e157746b6df940d197b94"),
        ("windows-amd64", "node-v24.19.0-win-x64.zip", "57f71ab3652e797d84acddc79c81cc9ff1c6ddb2a1974cdb83f00fee9bff4c73"),
        ("windows-arm64", "node-v24.19.0-win-arm64.zip", "8502f4a50b458d4cc38ed8f2001556c2cd239d464920f74017926ccb1e1c157f"),
    )
    return [
        artifact(
            filename=filename,
            platform=platform,
            source_url=f"{base}/{filename}",
            digest=recorded_digest(sha256, "node-shasums-24.19.0"),
        )
        for platform, filename, sha256 in values
    ]


def tool(
    *,
    artifacts: list[dict[str, Any]],
    dependencies: list[str],
    identity: str,
    license_expression: list[str],
    license_source: str,
    provenance: str,
    role: str,
    version: str,
) -> dict[str, Any]:
    return {
        "artifacts": sorted(
            artifacts, key=lambda item: (item["platform"], item["filename"])
        ),
        "dependencies": {
            "declared_review_targets": sorted(set(dependencies)),
            "inventory_status": "artifact-contents-not-inspected",
        },
        "id": identity,
        "license": {
            "artifact_inventory_status": "not-inspected",
            "main_expressions": sorted(set(license_expression)),
            "review_status": "not-accepted",
            "source": license_source,
        },
        "provenance_status": provenance,
        "role": role,
        "version": version,
    }


def build_tools() -> list[dict[str, Any]]:
    return [
        tool(
            artifacts=cvc5_artifacts(),
            dependencies=[
                "CaDiCaL",
                "GMP",
                "MPFR",
                "SymFPU",
                "compiler-runtime",
                "other-bundled-components",
            ],
            identity="cvc5-cli",
            license_expression=["BSD-3-Clause"],
            license_source="cvc5-copying-1.3.4",
            provenance="signed-release-tag-publisher-asset-digests-recorded",
            role="verification-backend",
            version="1.3.4",
        ),
        tool(
            artifacts=go_artifacts(),
            dependencies=["Go-standard-library", "bundled-toolchain-components"],
            identity="go-toolchain",
            license_expression=["BSD-3-Clause"],
            license_source="go-license",
            provenance="publisher-index-digests-recorded",
            role="independent-checker-toolchain",
            version="go1.26.7",
        ),
        tool(
            artifacts=node_artifacts(),
            dependencies=["V8", "Node-bundled-third-party-components"],
            identity="node-runtime",
            license_expression=["MIT", "LicenseRef-Node-Bundled-Third-Party"],
            license_source="node-license-24.19.0",
            provenance="signed-checksum-manifest-present-signature-not-verified",
            role="target-runtime",
            version="24.19.0",
        ),
        tool(
            artifacts=rust_artifacts(),
            dependencies=["Rust-standard-library", "LLVM", "bundled-toolchain-components"],
            identity="rust-toolchain",
            license_expression=["Apache-2.0", "MIT"],
            license_source="rust-license",
            provenance="release-version-reviewed-checksums-pending-capture",
            role="production-toolchain",
            version="1.97.1",
        ),
    ]


PROFILES = (
    {
        "boundary": {
            "artifact_resolution": "exact-registered-artifact-only",
            "fallback": "forbidden",
            "network": "forbidden",
            "process_model": "one-process-per-obligation",
            "transport": "stdin-stdout-stderr",
        },
        "id": "cvc5-1.3.4-qf-uflia-v0.1",
        "kind": "verification-adapter",
        "materialization": "specified-not-materialized",
        "specification": "docs/adr/0005-first-verification-backend.md",
        "tool": "cvc5-cli",
    },
    {
        "boundary": {
            "artifact_resolution": "exact-registered-artifact-only",
            "build_network": "forbidden",
            "cgo": "forbidden",
            "external_modules": "forbidden-in-initial-core",
            "toolchain_switching": "forbidden",
        },
        "id": "go1.26.7-independent-check-build-v0.1",
        "kind": "checker-build-profile",
        "materialization": "reserved-not-materialized",
        "specification": "docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md",
        "tool": "go-toolchain",
    },
    {
        "boundary": {
            "implementation_language": "go-1.26",
            "production-code-reuse": "forbidden",
            "repository": "separate-from-production",
            "result_transport": "offline-content-addressed-bundle",
        },
        "id": "keyed-finite-table-independent-check-v0.1",
        "kind": "checker-implementation-profile",
        "materialization": "specified-not-materialized",
        "specification": "docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md",
        "tool": "go-toolchain",
    },
    {
        "boundary": {
            "artifact_resolution": "exact-registered-artifact-only",
            "environment_inheritance": "deny-by-default",
            "fallback": "forbidden",
            "permission_model": "required-deny-by-default",
            "process_model": "one-process-per-artifact-input",
            "transport": "stdin-stdout-stderr",
        },
        "id": "node-24-esm-invocation-v0.1",
        "kind": "runtime-invocation-profile",
        "materialization": "specified-not-materialized",
        "specification": "docs/adr/0006-first-target-runtime-and-execution-path.md",
        "tool": "node-runtime",
    },
    {
        "boundary": {
            "artifact_resolution": "exact-registered-artifact-only",
            "dynamic-code": "forbidden",
            "fallback": "forbidden",
            "npm": "forbidden",
            "semantic-integers": "bigint-only",
        },
        "id": "node-24-esm-keyed-finite-table-v0.1",
        "kind": "target-profile",
        "materialization": "specified-not-materialized",
        "specification": "docs/adr/0006-first-target-runtime-and-execution-path.md",
        "tool": "node-runtime",
    },
    {
        "boundary": {
            "artifact_identity": "sha256-raw-bytes-plus-format-version",
            "fallback": "forbidden",
            "network": "forbidden",
            "verification_gate": "failed-unknown-invalid-block-target",
        },
        "id": "raxc-keyed-finite-table-pipeline-v0.1",
        "kind": "pipeline-profile",
        "materialization": "specified-artifact-contracts-pending",
        "specification": "docs/adr/0007-first-verification-first-compilation-pipeline.md",
        "tool": "rust-toolchain",
    },
    {
        "boundary": {
            "cargo_locked": "required",
            "edition": "2024",
            "nightly": "forbidden",
            "toolchain_resolution": "exact-pinned-no-path-fallback",
        },
        "id": "rust-1.97.1-raxc-build-v0.1",
        "kind": "production-build-profile",
        "materialization": "reserved-not-materialized",
        "specification": "docs/adr/0004-raxc-production-implementation-language.md",
        "tool": "rust-toolchain",
    },
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode(
        "ascii"
    )


def registry_digest(body: dict[str, Any]) -> str:
    payload = DIGEST_DOMAIN.encode("ascii") + b"\0" + canonical_bytes(body)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def profile_records() -> list[dict[str, Any]]:
    result = []
    for profile in PROFILES:
        specification = REPO_ROOT / profile["specification"]
        digest = "sha256:" + hashlib.sha256(specification.read_bytes()).hexdigest()
        result.append({**profile, "specification_sha256": digest})
    return result


def build_registry() -> dict[str, Any]:
    body = {
        "digest_domain": DIGEST_DOMAIN,
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "platforms": list(PLATFORMS),
        "profiles": profile_records(),
        "review_date": REVIEW_DATE,
        "sources": list(SOURCES),
        "tools": build_tools(),
    }
    return {**body, "registry_digest": registry_digest(body)}


def schema() -> dict[str, Any]:
    digest = {
        "oneOf": [
            {
                "additionalProperties": False,
                "properties": {
                    "kind": {"const": "publisher-recorded"},
                    "sha256": {"pattern": "^[0-9a-f]{64}$", "type": "string"},
                    "source": {"pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
                },
                "required": ["kind", "sha256", "source"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "kind": {"const": "pending-publisher-capture"},
                    "reason": {"minLength": 1, "type": "string"},
                    "source_url": {"format": "uri", "type": "string"},
                },
                "required": ["kind", "reason", "source_url"],
                "type": "object",
            },
        ]
    }
    artifact_schema = {
        "additionalProperties": False,
        "allOf": [
            {
                "else": {"not": {"required": ["acceptance_record"]}},
                "if": {
                    "properties": {
                        "acceptance": {
                            "const": "accepted-for-controlled-build-input"
                        }
                    },
                    "required": ["acceptance"],
                },
                "then": {"required": ["acceptance_record"]},
            }
        ],
        "properties": {
            "acceptance": {
                "enum": [
                    "accepted-for-controlled-build-input",
                    "not-accepted",
                ]
            },
            "acceptance_record": {
                "pattern": (
                    "^contracts/toolchain-payload-acceptance-v0\\.1/records/"
                    "[a-z0-9.-]+\\.acceptance\\.json$"
                ),
                "type": "string",
            },
            "archive_inspection": {
                "enum": ["not-performed", "passed-toolchain-tar-v0.1"]
            },
            "digest": {"$ref": "#/$defs/digestEvidence"},
            "filename": {"minLength": 1, "type": "string"},
            "payload_verification": {
                "enum": ["not-downloaded", "sha256-matched-publisher-record"]
            },
            "platform": {
                "enum": [
                    "linux-amd64",
                    "linux-arm64",
                    "macos-amd64",
                    "macos-arm64",
                    "source",
                    "windows-amd64",
                    "windows-arm64",
                ]
            },
            "source_url": {"format": "uri", "type": "string"},
        },
        "required": [
            "acceptance",
            "archive_inspection",
            "digest",
            "filename",
            "payload_verification",
            "platform",
            "source_url",
        ],
        "type": "object",
    }
    platform_schema = {
        "additionalProperties": False,
        "properties": {
            "architecture": {"enum": ["amd64", "arm64"]},
            "id": {"pattern": "^[a-z0-9-]+$", "type": "string"},
            "os": {"enum": ["linux", "macos", "windows"]},
            "rust_target": {"minLength": 1, "type": "string"},
        },
        "required": ["architecture", "id", "os", "rust_target"],
        "type": "object",
    }
    profile_schema = {
        "additionalProperties": False,
        "properties": {
            "boundary": {
                "additionalProperties": {"minLength": 1, "type": "string"},
                "minProperties": 1,
                "type": "object",
            },
            "id": {"pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
            "kind": {"minLength": 1, "type": "string"},
            "materialization": {
                "enum": [
                    "reserved-not-materialized",
                    "specified-artifact-contracts-pending",
                    "specified-not-materialized",
                ]
            },
            "specification": {"minLength": 1, "type": "string"},
            "specification_sha256": {
                "pattern": "^sha256:[0-9a-f]{64}$",
                "type": "string",
            },
            "tool": {"pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
        },
        "required": [
            "boundary",
            "id",
            "kind",
            "materialization",
            "specification",
            "specification_sha256",
            "tool",
        ],
        "type": "object",
    }
    source_schema = {
        "additionalProperties": False,
        "properties": {
            "id": {"pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
            "kind": {"minLength": 1, "type": "string"},
            "publisher": {"minLength": 1, "type": "string"},
            "reviewed_claims": {
                "items": {"pattern": "^[a-z0-9-]+$", "type": "string"},
                "minItems": 1,
                "type": "array",
                "uniqueItems": True,
            },
            "url": {"format": "uri", "type": "string"},
        },
        "required": ["id", "kind", "publisher", "reviewed_claims", "url"],
        "type": "object",
    }
    tool_schema = {
        "additionalProperties": False,
        "properties": {
            "artifacts": {
                "items": {"$ref": "#/$defs/artifact"},
                "maxItems": 7,
                "minItems": 7,
                "type": "array",
            },
            "dependencies": {
                "additionalProperties": False,
                "properties": {
                    "declared_review_targets": {
                        "items": {"minLength": 1, "type": "string"},
                        "minItems": 1,
                        "type": "array",
                        "uniqueItems": True,
                    },
                    "inventory_status": {
                        "const": "artifact-contents-not-inspected"
                    },
                },
                "required": ["declared_review_targets", "inventory_status"],
                "type": "object",
            },
            "id": {
                "enum": [
                    "cvc5-cli",
                    "go-toolchain",
                    "node-runtime",
                    "rust-toolchain",
                ]
            },
            "license": {
                "additionalProperties": False,
                "properties": {
                    "artifact_inventory_status": {"const": "not-inspected"},
                    "main_expressions": {
                        "items": {"minLength": 1, "type": "string"},
                        "minItems": 1,
                        "type": "array",
                        "uniqueItems": True,
                    },
                    "review_status": {"const": "not-accepted"},
                    "source": {
                        "pattern": "^[a-z0-9][a-z0-9.-]*$",
                        "type": "string",
                    },
                },
                "required": [
                    "artifact_inventory_status",
                    "main_expressions",
                    "review_status",
                    "source",
                ],
                "type": "object",
            },
            "provenance_status": {"minLength": 1, "type": "string"},
            "role": {
                "enum": [
                    "independent-checker-toolchain",
                    "production-toolchain",
                    "target-runtime",
                    "verification-backend",
                ]
            },
            "version": {"minLength": 1, "type": "string"},
        },
        "required": [
            "artifacts",
            "dependencies",
            "id",
            "license",
            "provenance_status",
            "role",
            "version",
        ],
        "type": "object",
    }
    return {
        "$id": "https://radishaxiom.dev/schema/toolchain-adapter-identities/0.1",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "properties": {
            "format": {"const": FORMAT},
            "format_version": {"const": FORMAT_VERSION},
            "digest_domain": {"const": DIGEST_DOMAIN},
            "platforms": {
                "items": {"$ref": "#/$defs/platform"},
                "maxItems": 6,
                "minItems": 6,
                "type": "array",
            },
            "profiles": {
                "items": {"$ref": "#/$defs/profile"},
                "maxItems": 7,
                "minItems": 7,
                "type": "array",
            },
            "registry_digest": {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"},
            "review_date": {"const": REVIEW_DATE},
            "sources": {
                "items": {"$ref": "#/$defs/source"},
                "maxItems": 9,
                "minItems": 9,
                "type": "array",
            },
            "tools": {
                "items": {"$ref": "#/$defs/tool"},
                "maxItems": 4,
                "minItems": 4,
                "type": "array",
            },
        },
        "required": [
            "format",
            "format_version",
            "digest_domain",
            "platforms",
            "profiles",
            "registry_digest",
            "review_date",
            "sources",
            "tools",
        ],
        "title": "RadishAxiom toolchain and adapter identity registry v0.1",
        "type": "object",
        "$defs": {
            "artifact": artifact_schema,
            "digestEvidence": digest,
            "platform": platform_schema,
            "profile": profile_schema,
            "source": source_schema,
            "tool": tool_schema,
        },
    }


def require_sorted_unique(values: list[str], label: str) -> None:
    if values != sorted(values) or len(values) != len(set(values)):
        raise ValueError(f"{label} must be sorted and unique")


def validate_registry(value: dict[str, Any]) -> None:
    expected_keys = {
        "format",
        "format_version",
        "digest_domain",
        "platforms",
        "profiles",
        "registry_digest",
        "review_date",
        "sources",
        "tools",
    }
    if set(value) != expected_keys:
        raise ValueError("registry top-level members drifted")
    if value["format"] != FORMAT or value["format_version"] != FORMAT_VERSION:
        raise ValueError("registry format identity drifted")
    if value["digest_domain"] != DIGEST_DOMAIN:
        raise ValueError("registry digest domain drifted")
    if value["review_date"] != REVIEW_DATE:
        raise ValueError("registry review date drifted")

    body = {key: item for key, item in value.items() if key != "registry_digest"}
    if value["registry_digest"] != registry_digest(body):
        raise ValueError("registry digest mismatch")

    platform_ids = [item["id"] for item in value["platforms"]]
    require_sorted_unique(platform_ids, "platform ids")
    expected_platforms = {
        "linux-amd64",
        "linux-arm64",
        "macos-amd64",
        "macos-arm64",
        "windows-amd64",
        "windows-arm64",
    }
    if set(platform_ids) != expected_platforms:
        raise ValueError("platform matrix must contain Linux/macOS/Windows amd64/arm64")

    source_ids = [item["id"] for item in value["sources"]]
    require_sorted_unique(source_ids, "source ids")
    for source in value["sources"]:
        if not ID_PATTERN.fullmatch(source["id"]):
            raise ValueError(f"invalid source id: {source['id']}")
        if source["reviewed_claims"] != sorted(set(source["reviewed_claims"])):
            raise ValueError(f"source claims must be sorted and unique: {source['id']}")
        if not source["url"].startswith("https://"):
            raise ValueError(f"source URL must use HTTPS: {source['id']}")

    tools = value["tools"]
    tool_ids = [item["id"] for item in tools]
    require_sorted_unique(tool_ids, "tool ids")
    if tool_ids != ["cvc5-cli", "go-toolchain", "node-runtime", "rust-toolchain"]:
        raise ValueError("tool set drifted")
    expected_versions = {
        "cvc5-cli": "1.3.4",
        "go-toolchain": "go1.26.7",
        "node-runtime": "24.19.0",
        "rust-toolchain": "1.97.1",
    }

    for item in tools:
        if item["version"] != expected_versions[item["id"]]:
            raise ValueError(f"tool version drifted: {item['id']}")
        artifacts = item["artifacts"]
        artifact_platforms = [entry["platform"] for entry in artifacts]
        if set(artifact_platforms) != expected_platforms | {"source"}:
            raise ValueError(f"tool artifact matrix incomplete: {item['id']}")
        if len(artifact_platforms) != 7:
            raise ValueError(f"tool artifact matrix has duplicates: {item['id']}")
        if item["license"]["review_status"] != "not-accepted":
            raise ValueError(f"license review overclaimed: {item['id']}")
        if item["license"]["source"] not in source_ids:
            raise ValueError(f"license source is unknown: {item['id']}")
        if item["dependencies"]["inventory_status"] != "artifact-contents-not-inspected":
            raise ValueError(f"dependency inventory overclaimed: {item['id']}")
        dependency_targets = item["dependencies"]["declared_review_targets"]
        require_sorted_unique(dependency_targets, f"dependency targets for {item['id']}")
        license_expressions = item["license"]["main_expressions"]
        require_sorted_unique(license_expressions, f"license expressions for {item['id']}")
        artifact_keys = [
            (entry["platform"], entry["filename"]) for entry in artifacts
        ]
        if artifact_keys != sorted(artifact_keys):
            raise ValueError(f"tool artifacts must be sorted: {item['id']}")
        for entry in artifacts:
            acceptance_record = ACCEPTED_ARTIFACTS.get(entry["filename"])
            if acceptance_record is None:
                if entry["acceptance"] != "not-accepted":
                    raise ValueError(
                        f"artifact acceptance overclaimed: {entry['filename']}"
                    )
                if entry["payload_verification"] != "not-downloaded":
                    raise ValueError(
                        f"payload verification overclaimed: {entry['filename']}"
                    )
                if entry["archive_inspection"] != "not-performed":
                    raise ValueError(
                        f"archive inspection overclaimed: {entry['filename']}"
                    )
                if "acceptance_record" in entry:
                    raise ValueError(
                        f"unaccepted artifact has a record: {entry['filename']}"
                    )
            else:
                expected_status = {
                    "acceptance": "accepted-for-controlled-build-input",
                    "archive_inspection": "passed-toolchain-tar-v0.1",
                    "payload_verification": "sha256-matched-publisher-record",
                }
                for field, expected in expected_status.items():
                    if entry[field] != expected:
                        raise ValueError(
                            f"accepted artifact {field} drifted: {entry['filename']}"
                        )
                if entry.get("acceptance_record") != acceptance_record:
                    raise ValueError(
                        f"artifact acceptance record drifted: {entry['filename']}"
                    )
                if item["id"] != "go-toolchain":
                    raise ValueError(
                        f"unexpected accepted tool artifact: {entry['filename']}"
                    )
            if not entry["source_url"].startswith("https://"):
                raise ValueError(f"artifact URL must use HTTPS: {entry['filename']}")
            digest = entry["digest"]
            if digest["kind"] == "publisher-recorded":
                if not SHA256_PATTERN.fullmatch(digest["sha256"]):
                    raise ValueError(f"invalid publisher digest: {entry['filename']}")
                if digest["source"] not in source_ids:
                    raise ValueError(f"unknown digest source: {entry['filename']}")
            elif digest["kind"] == "pending-publisher-capture":
                if set(digest) != {"kind", "reason", "source_url"}:
                    raise ValueError(f"pending digest shape drifted: {entry['filename']}")
            else:
                raise ValueError(f"unknown digest status: {entry['filename']}")
            if item["id"] == "cvc5-cli" and "-gpl" in entry["filename"].lower():
                raise ValueError("GPL cvc5 artifact entered the candidate matrix")

    profile_ids = [item["id"] for item in value["profiles"]]
    require_sorted_unique(profile_ids, "profile ids")
    expected_profiles = [
        "cvc5-1.3.4-qf-uflia-v0.1",
        "go1.26.7-independent-check-build-v0.1",
        "keyed-finite-table-independent-check-v0.1",
        "node-24-esm-invocation-v0.1",
        "node-24-esm-keyed-finite-table-v0.1",
        "raxc-keyed-finite-table-pipeline-v0.1",
        "rust-1.97.1-raxc-build-v0.1",
    ]
    if profile_ids != expected_profiles:
        raise ValueError("profile set drifted")
    for profile in value["profiles"]:
        if profile["tool"] not in tool_ids:
            raise ValueError(f"profile references unknown tool: {profile['id']}")
        if profile["materialization"] == "materialized":
            raise ValueError(f"profile materialization overclaimed: {profile['id']}")
        specification = REPO_ROOT / profile["specification"]
        if not specification.is_file():
            raise ValueError(f"profile specification missing: {profile['id']}")
        actual_specification_digest = (
            "sha256:" + hashlib.sha256(specification.read_bytes()).hexdigest()
        )
        if profile["specification_sha256"] != actual_specification_digest:
            raise ValueError(f"profile specification digest drifted: {profile['id']}")


def outputs() -> dict[Path, bytes]:
    registry = build_registry()
    validate_registry(registry)
    return {
        CONTRACT_ROOT / "registry.json": pretty_bytes(registry),
        CONTRACT_ROOT / "schemas/toolchain-adapter-identities.schema.json": pretty_bytes(
            schema()
        ),
    }


def write_outputs(expected: dict[Path, bytes]) -> None:
    for path, data in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"wrote toolchain adapter identities ({len(expected)} generated files)")


def check_outputs(expected: dict[Path, bytes]) -> int:
    errors: list[str] = []
    for path, data in expected.items():
        if not path.is_file():
            errors.append(f"missing generated file: {path.relative_to(REPO_ROOT)}")
        elif path.read_bytes() != data:
            errors.append(f"generated file drifted: {path.relative_to(REPO_ROOT)}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"toolchain adapter identities passed ({len(expected)} generated files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = outputs()
    if args.write:
        write_outputs(expected)
        return 0
    return check_outputs(expected)


if __name__ == "__main__":
    raise SystemExit(main())
