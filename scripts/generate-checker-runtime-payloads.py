#!/usr/bin/env python3
"""Generate and validate checker runtime payload registration records v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = REPO_ROOT / "contracts/checker-runtime-payloads-v0.1"
FORMAT = "radishaxiom-checker-runtime-payload-registration"
FORMAT_VERSION = "0.1"
RECORD_DOMAIN = "radishaxiom.checker-runtime-payload-registration.v0.1"
SET_FORMAT = "radishaxiom-checker-runtime-payload-registration-set"
SET_DOMAIN = "radishaxiom.checker-runtime-payload-registration-set.v0.1"
LAUNCHER_POLICY_FORMAT = "radishaxiom-checker-runtime-launcher-policy"
LAUNCHER_POLICY_VERSION = "0.1"
LAUNCHER_POLICY_DOMAIN = "radishaxiom.checker-runtime-launcher-policy.v0.1"
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

CURRENT_SOURCE = {
    "file_count": "703",
    "identity": "sha256:401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999",
    "manifest_byte_length": "187178",
}
HISTORICAL_SOURCE = {
    "file_count": "682",
    "identity": "sha256:3b809ba6f062dbc1c543b64d9eb01f1fe46bdadf29f2d441b6d1c068200d90b4",
    "manifest_byte_length": "183203",
}
ACCEPTED_SCOPE = [
    "artifact-byte-reproducibility",
    "build-metadata",
    "runtime-self-identity",
    "scenario-behavior",
]
EXCLUDED_SCOPE = [
    "cross-platform-equivalence",
    "installation",
    "launcher-hard-isolation",
    "legal-compliance-for-distribution",
    "publication",
    "release-signing",
]

CURRENT_ARTIFACT = {
    "byte_length": "4689378",
    "kind": "known-digest",
    "raw_sha256": "sha256:7e2816eedec7a3cbcee7c25a0fdc79ecec7467cf7784d7a240dcac26942c5aaf",
}
CURRENT_PROVENANCE = {
    "byte_length": "1389",
    "format": "radishaxiom-checker-build-provenance",
    "format_version": "0.1",
    "kind": "known-digest",
    "raw_sha256": "sha256:45d0ef1c8ab6efaaa2b2085724d31fe10705cf2ccef7e89aac465a32aea52404",
}
CURRENT_ACCEPTANCE = {
    "byte_length": "1580",
    "decision": "accepted-for-controlled-runtime-registration",
    "excluded_scope": EXCLUDED_SCOPE,
    "format": "radishaxiom-checker-payload-acceptance",
    "format_version": "0.1",
    "kind": "known-digest",
    "raw_sha256": "sha256:57570571f014a1b2acdb2abd14fb258c6a7973cea0df8f0963babf1f34447b55",
    "scenarios": [
        {
            "byte_length": "7699",
            "id": "ax-b01-correct",
            "outcome": "accepted-with-trust",
            "raw_sha256": "sha256:2900dd849bf5527c681a38e8003673aa0719822be9a998d39877c9eba2e5652d",
        },
        {
            "byte_length": "2254",
            "id": "chk-digest-01",
            "outcome": "rejected",
            "raw_sha256": "sha256:8ca04f097bf6acd2c74ca1dd5aa974d6ceece06dc0b7bf5f607d050741717384",
        },
        {
            "byte_length": "2935",
            "id": "chk-resource-01",
            "outcome": "incomplete",
            "raw_sha256": "sha256:a2d5f0040bd1cba29d7b8dbb88b73455add0a3642d0a217612563470a22d9bca",
        },
    ],
    "scope": ACCEPTED_SCOPE,
}
CURRENT_CANDIDATE_ARCHIVE = {
    "byte_length": "4697600",
    "filename": "checker-payload-candidate.tar",
    "format": "ustar",
    "kind": "known-digest",
    "manifest": {
        "byte_length": "1295",
        "filename": "checker-payload-retention-manifest-v0.1.jcs",
        "format": "radishaxiom-checker-payload-retention-manifest",
        "format_version": "0.1",
        "raw_sha256": "sha256:6420a65ecdd3dbccb117ffd1b97c6af535fbcd76bac75e1e95db75985888143a",
    },
    "raw_sha256": "sha256:fb33647de406af5076567abd56032a80e148362d2bf3e9a269d4a3892c84f3ea",
}
CURRENT_DISTRIBUTION_PACKAGE = {
    "acceptance": {
        "byte_length": "1869",
        "decision": "accepted-for-controlled-durable-publication-candidate",
        "excluded_scope": [
            "cross-platform-equivalence",
            "installation",
            "jurisdiction-wide-legal-compliance",
            "launcher-hard-isolation",
            "provider-publication",
            "release-signing",
            "runtime-activation",
        ],
        "format": "radishaxiom-checker-payload-distribution-acceptance",
        "format_version": "0.1",
        "raw_sha256": "sha256:6f3e6d817da72e48837792f465ca8693b6b1c82ad2d6b0723f8b92d4bcbca034",
        "scope": [
            "distribution-byte-inventory",
            "license-material-inclusion",
            "payload-identity-binding",
            "target-scoped-distribution",
        ],
    },
    "byte_length": "4720640",
    "filename": "radishaxiom-checker-go0.1-dev-darwin-arm64-v8.0-sha256-401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999.distribution.tar",
    "format": "radishaxiom-checker-runtime-distribution",
    "format_version": "0.1",
    "kind": "known-digest",
    "manifest": {
        "byte_length": "1721",
        "filename": "checker-payload-distribution-manifest-v0.1.jcs",
        "format": "radishaxiom-checker-runtime-distribution-manifest",
        "format_version": "0.1",
        "raw_sha256": "sha256:b4c95c457b73d759ccb3eaa6e8d93112f7020e7449146612010f887d0a6c36ad",
    },
    "raw_sha256": "sha256:17b44a1eb5ea9caeafd7b590bb8eb0ba87359bf53d5af2933a424d17fadfa437",
}
IMMUTABLE_RELEASES_OBSERVATION = {
    "api_version": "2026-03-10",
    "checked_at": "2026-08-30T08:43:30Z",
    "enabled": True,
    "enabled_at": "2026-08-30T08:43:23Z",
    "endpoint": "/repos/laugh0608/RadishAxiomChecker/immutable-releases",
    "enforced_by_owner": False,
    "status": "verified-enabled",
    "viewer_permission": "ADMIN",
}
CURRENT_DURABLE_RELEASE = {
    "asset": {
        "api_url": "https://api.github.com/repos/laugh0608/RadishAxiomChecker/releases/assets/536372439",
        "browser_download_url": "https://github.com/laugh0608/RadishAxiomChecker/releases/download/checker-payload/go0.1-dev/darwin-arm64-v8.0/sha256-401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999/radishaxiom-checker-go0.1-dev-darwin-arm64-v8.0-sha256-401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999.distribution.tar",
        "byte_length": CURRENT_DISTRIBUTION_PACKAGE["byte_length"],
        "content_type": "application/x-tar",
        "created_at": "2026-08-30T08:50:52Z",
        "digest": CURRENT_DISTRIBUTION_PACKAGE["raw_sha256"],
        "id": "536372439",
        "name": CURRENT_DISTRIBUTION_PACKAGE["filename"],
        "node_id": "RA_kwDOUHvPb84f-GTX",
        "raw_sha256": CURRENT_DISTRIBUTION_PACKAGE["raw_sha256"],
        "state": "uploaded",
        "updated_at": "2026-08-30T08:51:09Z",
    },
    "attestation": {
        "asset_subject": {
            "digest": CURRENT_DISTRIBUTION_PACKAGE["raw_sha256"],
            "name": CURRENT_DISTRIBUTION_PACKAGE["filename"],
        },
        "asset_verified": True,
        "certificate_subject_alternative_name": "https://dotcom.releases.github.com",
        "predicate_type": "https://in-toto.io/attestation/release/v0.2",
        "release_subject": {
            "digest": "sha1:f960603aa1120ebe427eb9227f116f4a41513d5e",
            "uri": "pkg:github/laugh0608/RadishAxiomChecker@checker-payload%2Fgo0.1-dev%2Fdarwin-arm64-v8.0%2Fsha256-401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999",
        },
        "release_verified": True,
        "timestamp": "2026-08-30T08:53:08Z",
        "trusted_root": "github-instance-root-fetched-by-gh-attestation-trusted-root",
        "verification_tool": {"name": "gh", "version": "2.96.0"},
    },
    "draft": False,
    "html_url": "https://github.com/laugh0608/RadishAxiomChecker/releases/tag/checker-payload/go0.1-dev/darwin-arm64-v8.0/sha256-401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999",
    "id": "379226889",
    "immutable": True,
    "name": "RadishAxiom Checker go0.1-dev darwin-arm64-v8.0",
    "prerelease": False,
    "published_at": "2026-08-30T08:53:07Z",
    "release_classification": "checker-runtime-payload-not-product-release",
    "tag": "checker-payload/go0.1-dev/darwin-arm64-v8.0/sha256-401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999",
    "target_commit": "f960603aa1120ebe427eb9227f116f4a41513d5e",
    "tag_resolved_commit": "f960603aa1120ebe427eb9227f116f4a41513d5e",
    "verification": {
        "draft_asset_api_metadata_readback": True,
        "draft_asset_raw_byte_readback": True,
        "post_publication_asset_api_metadata_readback": True,
        "post_publication_cli_raw_byte_readback": True,
        "post_publication_distribution_and_inner_candidate_strict_verification": True,
        "post_publication_public_raw_byte_readback": True,
        "verified_at": "2026-08-30T08:59:00Z",
    },
}
CURRENT_CANDIDATE_RUN = {
    "attempt": "1",
    "conclusion": "success",
    "created_at": "2026-08-30T08:19:13Z",
    "event": "workflow_dispatch",
    "head_sha": "f960603aa1120ebe427eb9227f116f4a41513d5e",
    "inputs": {
        "confirm_candidate_upload": True,
        "source_identity": CURRENT_SOURCE["identity"],
        "version": "0.1-dev",
    },
    "jobs": [
        {
            "conclusion": "success",
            "id": "99229841973",
            "name": "Build, Accept, Distribute, and Upload Candidate",
        },
        {
            "conclusion": "success",
            "id": "99229998823",
            "name": "Read Back Exact Distribution Candidate by Artifact ID",
        },
    ],
    "ref": "refs/heads/master",
    "run_id": "33301288846",
    "workflow": "Checker Payload Candidate",
}

STORAGE_POLICY = {
    "active_runtime": {
        "launcher_policy": {
            "format": LAUNCHER_POLICY_FORMAT,
            "format_version": LAUNCHER_POLICY_VERSION,
            "path": "contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs",
            "status": "specified-not-implemented",
        },
        "provider": "github-immutable-release-asset",
        "requirements": [
            "durable-registration",
            "exact-os-architecture-variant-match",
            "installation-coordination",
            "launcher-hard-isolation",
            "runtime-companion",
            "separate-activation-authorization",
        ],
        "status": "registered-inactive-launcher-policy-specified-installation-and-companion-not-materialized",
    },
    "candidate": {
        "activation_precondition": "workflow-file-present-on-default-branch",
        "activation_precondition_status": "satisfied",
        "build_runner": "macos-15-arm64",
        "default_branch_deployment": {
            "dev_ref": "refs/heads/dev",
            "master_ref": "refs/heads/master",
            "merge_commit": "f960603aa1120ebe427eb9227f116f4a41513d5e",
            "merge_method": "merge-commit",
            "pr_ci": {
                "conclusion": "success",
                "run_id": "33255345832",
                "workflow": "Checker Checks",
            },
            "pr_number": "2",
            "push_ci": "not-triggered-by-governance",
            "source_identity_commit": "4b95b2a81616110f5d3ed076f882a18ddc6aba37",
        },
        "download_action": {
            "commit": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
            "name": "actions/download-artifact",
            "version": "v8.0.1",
        },
        "expiration_effect": "candidate-becomes-unavailable",
        "fetch_resolution": "exact-artifact-id-only",
        "implementation_commit": "f6a02b9314051fd841e1f3d3d1491a8a73ad7da7",
        "implementation_ci": {
            "conclusion": "success",
            "run_id": "33253582957",
            "workflow": "Checker Checks",
        },
        "implementation_remote_ref": "refs/heads/dev",
        "implementation_tree": "837ed9bae4b47e8fd4001829e0dd77d70f0ea36f",
        "provider": "github-actions-direct-file-artifact",
        "readback": "separate-job-exact-artifact-id-direct-file-download-and-distribution-verification",
        "registration_effect": "candidate-only-never-active",
        "repository": "laugh0608/RadishAxiomChecker",
        "required_inner_bindings": [
            "distribution-acceptance-byte-length",
            "distribution-acceptance-raw-sha256",
            "distribution-archive-byte-length",
            "distribution-archive-raw-sha256",
            "distribution-manifest-byte-length",
            "distribution-manifest-raw-sha256",
            "inner-candidate-byte-length",
            "inner-candidate-raw-sha256",
            "retention-manifest-byte-length",
            "retention-manifest-raw-sha256",
        ],
        "required_provider_bindings": [
            "artifact-id",
            "artifact-name",
            "created-at",
            "expires-at",
            "provider-direct-file-digest",
            "provider-direct-file-size",
            "workflow-head-sha",
            "workflow-ref",
            "workflow-run-attempt",
            "workflow-run-id",
        ],
        "retention_days": "90",
        "status": "distribution-candidate-retained-temporarily-provider-readback-passed",
        "upload_action": {
            "archive": "false",
            "commit": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
            "name": "actions/upload-artifact",
            "version": "v7.0.1",
        },
        "upload_object": "deterministic-outer-distribution-ustar-direct-file-no-provider-archive",
        "workflow_file": ".github/workflows/checker-payload-candidate.yml",
        "workflow_trigger": "workflow-dispatch-only",
    },
    "durable": {
        "asset_name_template": "radishaxiom-checker-go0.1-dev-<goos>-<goarch>-<variant>-sha256-<checker-source-hex>.distribution.tar",
        "distribution_format": {
            "format": "radishaxiom-checker-runtime-distribution",
            "format_version": "0.1",
            "outer_archive": "deterministic-ustar",
            "required_members": [
                "checker-payload-candidate.tar",
                "checker-payload-distribution-acceptance-v0.1.jcs",
                "checker-payload-distribution-manifest-v0.1.jcs",
                "licenses/go/LICENSE",
                "licenses/go/PATENTS",
                "licenses/radishaxiom-checker/LICENSE",
            ],
        },
        "draft_policy": "assemble-and-read-back-all-assets-before-single-publication",
        "latest_alias_policy": "forbidden",
        "provider": "github-immutable-release-asset",
        "provider_attestation_role": "supplemental-provider-provenance-not-payload-acceptance",
        "provider_selection_status": "selected-setting-enabled-release-published-immutable-verified",
        "repository_immutability": IMMUTABLE_RELEASES_OBSERVATION,
        "release_cardinality": "one-checker-source-version-target-per-release",
        "repository": "laugh0608/RadishAxiomChecker",
        "required_provider_bindings": [
            "asset-api-url",
            "asset-browser-download-url",
            "asset-digest",
            "asset-id",
            "asset-name",
            "asset-size",
            "asset-state",
            "published-at",
            "release-id",
            "release-immutable-true",
            "release-tag",
            "target-commit-sha",
        ],
        "required_verifications": [
            "distribution-package-independent-acceptance",
            "draft-asset-byte-length-and-sha256",
            "draft-inner-candidate-and-license-inventory",
            "post-publication-exact-asset-independent-readback",
            "post-publication-provider-metadata-readback",
            "release-attestation-verification",
            "repository-immutable-releases-enabled-before-draft",
        ],
        "status": "registered-inactive-launcher-policy-specified-installation-companion-and-activation-pending",
        "tag_template": "checker-payload/go0.1-dev/<goos>-<goarch>-<variant>/sha256-<checker-source-hex>",
        "current_release": CURRENT_DURABLE_RELEASE,
    },
    "registration_state_machine": {
        "replacement_policy": "append-new-record-and-release-never-mutate-or-repoint",
        "states": [
            "candidate-retained-temporarily",
            "distribution-package-accepted",
            "durable-published",
            "registered-inactive",
            "active",
            "revoked",
        ],
        "transitions": [
            "candidate-retained-temporarily->distribution-package-accepted",
            "distribution-package-accepted->durable-published",
            "durable-published->revoked",
            "durable-published->registered-inactive",
            "registered-inactive->active",
            "registered-inactive->revoked",
            "active->revoked",
        ],
        "transition_policy": "explicit-evidence-and-separate-authorization-no-automatic-promotion",
    },
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    ).encode("ascii")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def domain_digest(domain: str, body: dict[str, Any]) -> str:
    return sha256_bytes(domain.encode("ascii") + b"\0" + canonical_bytes(body))


def launcher_policy() -> dict[str, Any]:
    target = {
        "executable_format": "macho-64-arm64",
        "goarch": "arm64",
        "goarm64": "v8.0",
        "goos": "darwin",
    }
    body = {
        "activation": {
            "authorization": "separate-explicit-authorization-required",
            "current_status": "not-authorized",
            "preconditions": [
                "active-registration-transition-authorized",
                "durable-registration-still-valid-and-not-revoked",
                "exact-target-launcher-policy-implemented-and-native-tested",
                "immutable-installation-slot-and-complete-receipt-reverified",
                "qualification-record-and-companions-exactly-match-accepted-scenarios",
            ],
            "product_selection": "active-registration-and-qualified-installation-only",
            "runtime_cardinality": "exactly-one-active-record-per-target-or-fail",
        },
        "authority": [
            {
                "name": "adr-0011",
                "path": "docs/adr/0011-checker-runtime-launcher-installation-and-activation.md",
                "raw_sha256": raw_sha256(
                    REPO_ROOT
                    / "docs/adr/0011-checker-runtime-launcher-installation-and-activation.md"
                ),
            },
            {
                "name": "execution-profile-v0.1",
                "path": "contracts/execution-profiles-v0.1/manifest.jcs",
                "raw_sha256": raw_sha256(
                    REPO_ROOT / "contracts/execution-profiles-v0.1/manifest.jcs"
                ),
            },
            {
                "name": "independent-check-v0.1",
                "path": "contracts/independent-check-v0.1/contract.json",
                "raw_sha256": raw_sha256(
                    REPO_ROOT / "contracts/independent-check-v0.1/contract.json"
                ),
            },
        ],
        "digest_domain": LAUNCHER_POLICY_DOMAIN,
        "failure_boundary": [
            {
                "classification": "runtime-unavailable",
                "condition": "no-active-record-target-mismatch-or-installed-identity-failure",
                "independent_result": "not-produced",
            },
            {
                "classification": "installation-failed",
                "condition": "fetch-unpack-verification-or-atomic-publication-failure",
                "independent_result": "not-produced",
            },
            {
                "classification": "qualification-failed",
                "condition": "qualification-output-identity-outcome-or-digest-mismatch",
                "independent_result": "not-produced",
            },
            {
                "classification": "process-failure",
                "condition": "spawn-kill-timeout-memory-crash-signal-nonzero-exit-or-output-failure",
                "independent_result": "not-produced",
            },
            {
                "classification": "identity-failure",
                "condition": "canonical-result-does-not-bind-active-registration-request-or-executable",
                "independent_result": "not-consumable",
            },
            {
                "classification": "completed",
                "condition": "one-canonical-result-strictly-parsed-and-all-runtime-identities-match",
                "independent_result": "consumable",
            },
        ],
        "format": LAUNCHER_POLICY_FORMAT,
        "format_version": LAUNCHER_POLICY_VERSION,
        "host_selection": {
            "current_supported_targets": [target],
            "executable_format_verification": "inspect-installed-bytes-never-infer-from-name",
            "forbidden_resolution": [
                "actions-artifact",
                "adjacent-directory",
                "current-working-directory",
                "latest-alias",
                "neighbor-cache",
                "path-search",
                "system-go-installation",
                "user-supplied-executable",
            ],
            "host_identity_source": "trusted-launcher-adapter-and-native-process-identity",
            "match": "exact-goos-goarch-goarm64-executable-format",
            "product_registration_status": "active-only",
            "qualification_registration_status": "registered-inactive-only",
            "rosetta_policy": "translated-amd64-process-cannot-select-arm64-payload",
            "selection_cardinality": "exactly-one-or-fail",
            "unknown_target": "fail-closed-no-fallback",
            "variant_policy": "closed-launcher-table-darwin-arm64-maps-only-to-v8.0",
        },
        "installation": {
            "authorization": "separate-explicit-authorization-required",
            "current_status": "not-materialized",
            "executable": {
                "mode": "0755",
                "relative_path": "payload/radishaxiom-independent-checker-go",
                "required_checks": [
                    "absolute-canonical-slot-contained-realpath",
                    "exact-byte-length",
                    "exact-raw-sha256",
                    "macho-64-arm64",
                    "no-setuid-setgid-sticky",
                    "regular-file-no-links",
                ],
            },
            "fetch": "exact-immutable-release-and-asset-identities-only",
            "installed_state": "installed-inactive",
            "network_boundary": "installation-coordinator-only-checker-remains-offline",
            "publication": "same-filesystem-verified-staging-then-atomic-rename",
            "receipt": {
                "canonicalization": "canonical-json-ascii-no-trailing-newline",
                "digest_domain": "radishaxiom.checker-runtime-installation-receipt.v0.1",
                "filename": "checker-runtime-installation-receipt-v0.1.jcs",
                "format": "radishaxiom-checker-runtime-installation-receipt",
                "format_version": "0.1",
                "required_bindings": [
                    "artifact-byte-length-and-raw-sha256",
                    "checker-source-version-toolchain",
                    "distribution-byte-length-and-raw-sha256",
                    "installation-time",
                    "installation-verifier-identity",
                    "provider-repository-release-tag-and-asset-ids",
                    "registration-record-id-and-digest-at-installation",
                    "slot-relative-identity",
                    "target-goos-goarch-goarm64-executable-format",
                ],
                "status": "required-not-materialized",
            },
            "recovery": "discard-only-owned-incomplete-staging-while-lock-held",
            "root": "product-managed-user-local-private-data-root",
            "single_writer": "per-target-installation-lock",
            "slot_identity": "target-and-distribution-raw-sha256",
            "slot_mutation": "immutable-no-in-place-repair-or-replacement",
            "staging_rejections": [
                "absolute-path",
                "device",
                "dot-dot-or-empty-component",
                "extra-or-trailing-bytes",
                "fifo",
                "hard-link",
                "pax-or-xattr",
                "socket",
                "symbolic-link",
                "unknown-member-or-mode",
            ],
        },
        "invocation": {
            "argument_tokens": [
                "check",
                "--bundle-root=<caller-mounted-readonly-canonical-realpath>",
            ],
            "bundle": "caller-mounted-readonly-canonical-realpath",
            "environment": "empty-no-inheritance",
            "executable_resolution": "exact-active-content-addressed-slot-only",
            "execution_profile": {
                "id": "keyed-finite-table-independent-check-v0.1",
                "path": "contracts/execution-profiles-v0.1/manifest.jcs",
                "raw_sha256": raw_sha256(
                    REPO_ROOT / "contracts/execution-profiles-v0.1/manifest.jcs"
                ),
            },
            "identity_revalidation": "before-and-after-every-spawn",
            "network": "forbidden",
            "retry": "new-attempt-same-exact-slot-only-never-automatic-fallback",
            "stderr": "bounded-diagnostic-never-result",
            "stdin": "empty-then-eof",
            "stdout": "one-canonical-independent-result-or-no-result",
            "working_directory": "isolated-empty",
        },
        "level": "specified-not-implemented",
        "runtime_companion": {
            "current_status": "not-materialized-by-product-launcher",
            "format": "axiom-independent-check-result",
            "format_version": "0.1",
            "identity_requirements": [
                "actual-installed-checker-artifact",
                "checker-source-and-implementation-version",
                "exact-go1.26.7-toolchain",
                "four-runtime-tcb-artifacts",
                "request-and-evidence-identities",
                "strict-result-document-digest",
            ],
            "invocation_failure_format": "axiom-checker-invocation-failure-0.1-when-canonical-request-identity-exists",
            "qualification_record": {
                "canonicalization": "canonical-json-ascii-no-trailing-newline",
                "current_status": "not-materialized",
                "digest_domain": "radishaxiom.checker-runtime-qualification-record.v0.1",
                "format": "radishaxiom-checker-runtime-qualification-record",
                "format_version": "0.1",
                "required_bindings": [
                    "actual-artifact-and-target",
                    "installation-receipt-digest",
                    "launcher-policy-and-execution-profile-identities",
                    "qualification-companion-scenario-outcome-raw-and-document-digests",
                ],
                "storage": "product-managed-evidence-area-outside-immutable-slot",
            },
            "qualification_scenarios": [
                {
                    "byte_length": item["byte_length"],
                    "id": item["id"],
                    "outcome": item["outcome"],
                    "raw_sha256": item["raw_sha256"],
                }
                for item in CURRENT_ACCEPTANCE["scenarios"]
            ],
            "qualification_status": "required-not-run-by-product-launcher",
            "role": "existing-independent-check-canonical-result-not-launcher-metadata",
            "strict_contract": "contracts/independent-check-v0.1/contract.json",
        },
    }
    return {**body, "policy_digest": domain_digest(LAUNCHER_POLICY_DOMAIN, body)}


def validate_launcher_policy(value: dict[str, Any]) -> None:
    expected = launcher_policy()
    if set(value) != set(expected):
        raise ValueError("runtime launcher policy members drifted")
    body = {key: item for key, item in value.items() if key != "policy_digest"}
    if value.get("policy_digest") != domain_digest(LAUNCHER_POLICY_DOMAIN, body):
        raise ValueError("runtime launcher policy digest mismatch")
    if canonical_bytes(value) != canonical_bytes(expected):
        raise ValueError("runtime launcher policy exceeds or drifts from accepted boundaries")


def refreshed_launcher_policy(value: dict[str, Any]) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key != "policy_digest"}
    value["policy_digest"] = domain_digest(LAUNCHER_POLICY_DOMAIN, body)
    return value


def record(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "record_digest": domain_digest(RECORD_DOMAIN, body)}


def common(record_id: str, source: dict[str, str]) -> dict[str, Any]:
    return {
        "checker": {
            "implementation": "radishaxiom-independent-checker-go",
            "source": source,
            "toolchain": "go1.26.7",
            "version": "0.1-dev",
        },
        "digest_domain": RECORD_DOMAIN,
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "id": record_id,
        "target": {
            "executable_format": "macho-64-arm64",
            "goarch": "arm64",
            "goarm64": "v8.0",
            "goos": "darwin",
        },
    }


def historical_record() -> dict[str, Any]:
    body = {
        **common("checker-go0.1-dev-darwin-arm64-historical-2026-08-28", HISTORICAL_SOURCE),
        "acceptance": {
            "byte_length": "1580",
            "decision": "accepted-for-controlled-runtime-registration",
            "excluded_scope": EXCLUDED_SCOPE,
            "format": "radishaxiom-checker-payload-acceptance",
            "format_version": "0.1",
            "kind": "known-digest",
            "raw_sha256": "sha256:fb148d749622511ab6d13bcc2c35db10076a4cc9286e95d08443d3822ca1742a",
            "scenarios": [
                {
                    "byte_length": "7699",
                    "id": "ax-b01-correct",
                    "outcome": "accepted-with-trust",
                    "raw_sha256": "sha256:0f519d63ce293548c2988915ee0e9dd269ad3632e9c4f7a06c0ff3cb6332a97b",
                },
                {
                    "byte_length": "2254",
                    "id": "chk-digest-01",
                    "outcome": "rejected",
                    "raw_sha256": "sha256:97695d7a83bf2f3b46823037d2e7f2a44cde0754cd9d5727c39d9d7da1b72875",
                },
                {
                    "byte_length": "2935",
                    "id": "chk-resource-01",
                    "outcome": "incomplete",
                    "raw_sha256": "sha256:4b70570fcdf47be6d4cb329eb4da3de3739fb1557316a8a2630625f000879251",
                },
            ],
            "scope": ACCEPTED_SCOPE,
        },
        "artifact": {
            "byte_length": "4689378",
            "kind": "known-digest",
            "raw_sha256": "sha256:ef66c4d9098d058796e4f9d7e0f7713e73fc954e94c97a4001abd28acdbd99dc",
        },
        "build_provenance": {
            "byte_length": "1389",
            "format": "radishaxiom-checker-build-provenance",
            "format_version": "0.1",
            "kind": "known-digest",
            "raw_sha256": "sha256:7916666ae8f2883f5787a58307253416a653f8aca69e1cd1babc8f22639a38e0",
        },
        "registration": {
            "reasons": [
                "acceptance-bytes-not-retained",
                "artifact-bytes-not-retained",
                "checker-source-not-current",
                "provenance-bytes-not-retained",
            ],
            "status": "historical-ineligible",
        },
        "retention": {
            "acceptance_bytes": "not-retained",
            "artifact_bytes": "not-retained",
            "fetch": {
                "kind": "unavailable",
                "reason": "ephemeral build and acceptance outputs were deleted after identities were recorded",
            },
            "provenance_bytes": "not-retained",
        },
        "reverification": {
            "required_inputs": [
                "acceptance-bytes",
                "artifact-bytes",
                "current-source-match",
                "provenance-bytes",
            ],
            "status": "blocked-missing-bytes-and-source-mismatch",
        },
    }
    return record(body)


def registered_inactive_record() -> dict[str, Any]:
    body = {
        **common("checker-go0.1-dev-darwin-arm64-current-registered-inactive-2026-08-30", CURRENT_SOURCE),
        "acceptance": CURRENT_ACCEPTANCE,
        "artifact": CURRENT_ARTIFACT,
        "build_provenance": CURRENT_PROVENANCE,
        "candidate_archive": CURRENT_CANDIDATE_ARCHIVE,
        "candidate_workflow": {
            "ci": {
                "conclusion": "success",
                "run_id": "33253582957",
                "workflow": "Checker Checks",
            },
            "commit": "f6a02b9314051fd841e1f3d3d1491a8a73ad7da7",
            "default_branch_presence": "deployed",
            "file": ".github/workflows/checker-payload-candidate.yml",
            "promotion": {
                "dev_ref": "refs/heads/dev",
                "master_ref": "refs/heads/master",
                "merge_commit": "f960603aa1120ebe427eb9227f116f4a41513d5e",
                "merge_method": "merge-commit",
                "pr_ci": {
                    "conclusion": "success",
                    "run_id": "33255345832",
                    "workflow": "Checker Checks",
                },
                "pr_number": "2",
                "push_ci": "not-triggered-by-governance",
                "source_identity_commit": "4b95b2a81616110f5d3ed076f882a18ddc6aba37",
            },
            "remote_ref": "refs/heads/master",
            "repository": "laugh0608/RadishAxiomChecker",
            "run": CURRENT_CANDIDATE_RUN,
            "state": "distribution-candidate-built-accepted-uploaded-and-read-back",
            "tree": "837ed9bae4b47e8fd4001829e0dd77d70f0ea36f",
            "trigger": "workflow-dispatch-only",
        },
        "durable_registration": {
            "distribution_package": CURRENT_DISTRIBUTION_PACKAGE,
            "provider": {
                "independent_readback": {
                    "asset_api_metadata": "verified",
                    "cli_release_download": "verified",
                    "distribution_archive": "verified",
                    "inner_candidate": "verified",
                    "public_browser_download": "verified",
                    "verified_at": "2026-08-30T08:59:00Z",
                },
                "kind": "github-immutable-release-asset",
                "release": CURRENT_DURABLE_RELEASE,
                "repository": "laugh0608/RadishAxiomChecker",
                "repository_immutability": IMMUTABLE_RELEASES_OBSERVATION,
            },
            "status": "registered-inactive-immutable-provider-readback-passed",
        },
        "registration": {
            "reasons": [
                "activation-transition-requires-separate-authorization",
                "installation-not-materialized",
                "launcher-isolation-not-implemented",
            ],
            "registered_at": "2026-08-30T09:21:33Z",
            "status": "registered-inactive",
        },
        "retention": {
            "acceptance_bytes": "retained-in-candidate-archive",
            "artifact_bytes": "retained-in-candidate-archive",
            "candidate_archive_bytes": "retained-in-distribution-package",
            "candidate_fetch": {
                "kind": "github-actions-direct-file-exact-artifact-id",
                "provider": {
                    "artifact_id": "9729031154",
                    "created_at": "2026-08-30T08:20:28Z",
                    "digest": CURRENT_DISTRIBUTION_PACKAGE["raw_sha256"],
                    "expired_at_readback": False,
                    "expires_at": "2026-11-28T08:19:14Z",
                    "name": CURRENT_DISTRIBUTION_PACKAGE["filename"],
                    "size_in_bytes": CURRENT_DISTRIBUTION_PACKAGE["byte_length"],
                    "url": "https://github.com/laugh0608/RadishAxiomChecker/actions/runs/33301288846/artifacts/9729031154",
                },
                "readback": {
                    "distribution_archive_verified": True,
                    "exact_artifact_id": True,
                    "inner_candidate_verified": True,
                    "job_id": "99229998823",
                    "provider_metadata_verified": True,
                },
                "repository": "laugh0608/RadishAxiomChecker",
                "workflow": {
                    "head_sha": CURRENT_CANDIDATE_RUN["head_sha"],
                    "ref": CURRENT_CANDIDATE_RUN["ref"],
                    "run_attempt": CURRENT_CANDIDATE_RUN["attempt"],
                    "run_id": CURRENT_CANDIDATE_RUN["run_id"],
                },
            },
            "distribution_acceptance_bytes": "retained-in-distribution-package",
            "distribution_manifest_bytes": "retained-in-distribution-package",
            "distribution_package_bytes": "retained-by-immutable-release-asset",
            "fetch": {
                "kind": "github-immutable-release-asset-exact-id-and-tag",
                "provider": {
                    "asset_api_url": CURRENT_DURABLE_RELEASE["asset"]["api_url"],
                    "asset_browser_download_url": CURRENT_DURABLE_RELEASE["asset"]["browser_download_url"],
                    "asset_digest": CURRENT_DURABLE_RELEASE["asset"]["digest"],
                    "asset_id": CURRENT_DURABLE_RELEASE["asset"]["id"],
                    "asset_name": CURRENT_DURABLE_RELEASE["asset"]["name"],
                    "asset_size": CURRENT_DURABLE_RELEASE["asset"]["byte_length"],
                    "release_id": CURRENT_DURABLE_RELEASE["id"],
                    "release_immutable": CURRENT_DURABLE_RELEASE["immutable"],
                    "release_tag": CURRENT_DURABLE_RELEASE["tag"],
                    "target_commit": CURRENT_DURABLE_RELEASE["target_commit"],
                },
                "readback": {
                    "asset_attestation_verified": True,
                    "distribution_archive_verified": True,
                    "exact_asset_id": True,
                    "inner_candidate_verified": True,
                    "public_download_verified": True,
                    "provider_metadata_verified": True,
                    "release_attestation_verified": True,
                },
                "repository": "laugh0608/RadishAxiomChecker",
            },
            "provenance_bytes": "retained-in-candidate-archive",
        },
        "reverification": {
            "required_inputs": [
                "accepted-current-source-candidate",
                "retained-or-fetchable-acceptance-bytes",
                "retained-or-fetchable-artifact-bytes",
                "retained-or-fetchable-candidate-archive",
                "retained-or-fetchable-distribution-acceptance-bytes",
                "retained-or-fetchable-distribution-manifest-bytes",
                "retained-or-fetchable-distribution-package",
                "retained-or-fetchable-provenance-bytes",
            ],
            "status": "registered-inactive-provider-and-strict-readback-passed",
        },
    }
    return record(body)


def require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{label} is not a sha256 identity")


def validate_record(value: dict[str, Any]) -> None:
    expected = historical_record() if value.get("id") == historical_record()["id"] else registered_inactive_record()
    if value.get("id") not in {historical_record()["id"], registered_inactive_record()["id"]}:
        raise ValueError("unknown runtime payload record id")
    if set(value) != set(expected):
        raise ValueError("runtime payload record members drifted")
    body = {key: item for key, item in value.items() if key != "record_digest"}
    if value.get("record_digest") != domain_digest(RECORD_DOMAIN, body):
        raise ValueError("runtime payload record digest mismatch")
    require_digest(value["checker"]["source"]["identity"], "checker source")
    if canonical_bytes(value) != canonical_bytes(expected):
        raise ValueError("runtime payload record exceeds or drifts from recorded facts")


def infer_schema(values: list[Any], key: str = "") -> dict[str, Any]:
    if values and all(isinstance(value, dict) for value in values):
        dictionaries = values
        all_keys = sorted(set().union(*(value.keys() for value in dictionaries)))
        required = sorted(set.intersection(*(set(value) for value in dictionaries)))
        return {
            "additionalProperties": False,
            "properties": {
                child: infer_schema([value[child] for value in dictionaries if child in value], child)
                for child in all_keys
            },
            "required": required,
            "type": "object",
        }
    if values and all(isinstance(value, list) for value in values):
        items = [item for value in values for item in value]
        result: dict[str, Any] = {"type": "array"}
        if items:
            result["items"] = infer_schema(items, key)
        return result
    if values and all(isinstance(value, str) for value in values):
        if all(SHA256_PATTERN.fullmatch(value) for value in values):
            return {"pattern": "^sha256:[0-9a-f]{64}$", "type": "string"}
        if all(re.fullmatch(r"0|[1-9][0-9]*", value) for value in values):
            return {"pattern": "^(0|[1-9][0-9]*)$", "type": "string"}
        return {"type": "string"}
    if values and all(isinstance(value, bool) for value in values):
        return {"type": "boolean"}
    raise ValueError(f"cannot infer schema for {key}")


def schema(records: list[dict[str, Any]]) -> dict[str, Any]:
    variants = []
    for value in records:
        variant = infer_schema([value])
        variant["properties"]["format"] = {"const": FORMAT}
        variant["properties"]["format_version"] = {"const": FORMAT_VERSION}
        variant["properties"]["digest_domain"] = {"const": RECORD_DOMAIN}
        variant["properties"]["id"] = {"const": value["id"]}
        variant["properties"]["registration"]["properties"]["status"] = {
            "const": value["registration"]["status"]
        }
        variant["properties"]["artifact"]["properties"]["kind"] = {
            "const": value["artifact"]["kind"]
        }
        variant["properties"]["build_provenance"]["properties"]["kind"] = {
            "const": value["build_provenance"]["kind"]
        }
        variant["properties"]["acceptance"]["properties"]["kind"] = {
            "const": value["acceptance"]["kind"]
        }
        variants.append(variant)
    return {
        "$id": "https://radishaxiom.dev/schema/checker-runtime-payload-registration/0.1",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "oneOf": variants,
        "title": "RadishAxiom checker runtime payload registration v0.1",
    }


def refreshed(value: dict[str, Any]) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key != "record_digest"}
    value["record_digest"] = domain_digest(RECORD_DOMAIN, body)
    return value


def negative_fixtures(historical: dict[str, Any], current: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    value = copy.deepcopy(historical)
    value["checker"]["source"] = copy.deepcopy(CURRENT_SOURCE)
    rows.append(("historical-artifact-current-source.invalid.json", "historical artifact cannot be rebound to current source", refreshed(value)))
    value = copy.deepcopy(historical)
    value["retention"]["artifact_bytes"] = "retained"
    rows.append(("missing-artifact-retention-overclaim.invalid.json", "deleted artifact bytes cannot be claimed as retained", refreshed(value)))
    value = copy.deepcopy(historical)
    value["registration"]["status"] = "registered"
    rows.append(("historical-payload-registered.invalid.json", "source-mismatched unavailable payload cannot be registered", refreshed(value)))
    value = copy.deepcopy(historical)
    value["acceptance"]["excluded_scope"].remove("installation")
    rows.append(("installation-exclusion-missing.invalid.json", "acceptance cannot be expanded to installation", refreshed(value)))
    value = copy.deepcopy(current)
    value["build_provenance"] = {"kind": "not-produced"}
    rows.append(("registered-inactive-without-provenance.invalid.json", "registered-inactive payload requires retained build provenance", refreshed(value)))
    value = copy.deepcopy(current)
    value["unexpected"] = "member"
    rows.append(("unknown-member.invalid.json", "closed registration rejects unknown members", refreshed(value)))
    value = copy.deepcopy(current)
    value["registration"]["status"] = "active"
    rows.append(("registered-inactive-direct-active.invalid.json", "registered-inactive payload cannot bypass launcher isolation, installation, and activation authorization", refreshed(value)))
    value = copy.deepcopy(current)
    value["durable_registration"]["provider"]["release"] = "materialized-mutable"
    value["registration"]["status"] = "registered-inactive"
    rows.append(("mutable-release-registered.invalid.json", "mutable release cannot back a registered payload", refreshed(value)))
    value = copy.deepcopy(current)
    value["durable_registration"]["provider"]["fetch"] = "releases-latest-download"
    rows.append(("latest-release-alias.invalid.json", "latest release alias cannot identify durable bytes", refreshed(value)))
    value = copy.deepcopy(current)
    value["durable_registration"]["distribution_package"] = {
        "kind": "accepted-by-provider-release-attestation"
    }
    rows.append(("release-attestation-as-acceptance.invalid.json", "provider attestation cannot replace distribution acceptance", refreshed(value)))
    value = copy.deepcopy(current)
    value["durable_registration"]["provider"]["independent_readback"] = "not-performed"
    rows.append(("durable-release-without-readback.invalid.json", "durable registration requires independent exact-asset readback", refreshed(value)))
    value = copy.deepcopy(current)
    value["durable_registration"]["replacement"] = "replace-existing-asset-in-place"
    rows.append(("in-place-replacement.invalid.json", "replacement must use a new immutable release and record", refreshed(value)))
    return rows


def launcher_negative_fixtures(
    policy: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    value = copy.deepcopy(policy)
    value["host_selection"]["product_registration_status"] = "registered-inactive-or-active"
    rows.append((
        "registered-inactive-selectable.invalid.json",
        "product launcher cannot select a registered-inactive payload",
        refreshed_launcher_policy(value),
    ))
    value = copy.deepcopy(policy)
    value["host_selection"]["match"] = "compatible-target-with-fallback"
    rows.append((
        "target-fallback.invalid.json",
        "OS architecture variant and executable format require exact matching",
        refreshed_launcher_policy(value),
    ))
    value = copy.deepcopy(policy)
    value["invocation"]["executable_resolution"] = "path-search-or-active-slot"
    rows.append((
        "path-fallback.invalid.json",
        "launcher cannot resolve checker through PATH or another fallback",
        refreshed_launcher_policy(value),
    ))
    value = copy.deepcopy(policy)
    value["installation"]["publication"] = "copy-over-existing-slot"
    rows.append((
        "non-atomic-install.invalid.json",
        "installation must publish a verified same-filesystem staging directory atomically",
        refreshed_launcher_policy(value),
    ))
    value = copy.deepcopy(policy)
    value["installation"]["receipt"]["status"] = "optional"
    rows.append((
        "installation-receipt-optional.invalid.json",
        "a complete installation receipt is required before qualification or activation",
        refreshed_launcher_policy(value),
    ))
    value = copy.deepcopy(policy)
    value["runtime_companion"]["qualification_status"] = "optional"
    rows.append((
        "runtime-companion-optional.invalid.json",
        "formal runtime companions are required before activation",
        refreshed_launcher_policy(value),
    ))
    value = copy.deepcopy(policy)
    value["failure_boundary"][3]["independent_result"] = "incomplete"
    rows.append((
        "process-failure-as-result.invalid.json",
        "outer process failure cannot be reclassified as an independent incomplete result",
        refreshed_launcher_policy(value),
    ))
    value = copy.deepcopy(policy)
    value["invocation"]["identity_revalidation"] = "installation-time-only"
    rows.append((
        "preinvoke-reverification-omitted.invalid.json",
        "active executable identity must be checked before and after every spawn",
        refreshed_launcher_policy(value),
    ))
    return rows


def launcher_policy_schema(policy: dict[str, Any]) -> dict[str, Any]:
    result = infer_schema([policy])
    result["$id"] = "https://radishaxiom.dev/schema/checker-runtime-launcher-policy/0.1"
    result["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    result["properties"]["digest_domain"] = {"const": LAUNCHER_POLICY_DOMAIN}
    result["properties"]["format"] = {"const": LAUNCHER_POLICY_FORMAT}
    result["properties"]["format_version"] = {"const": LAUNCHER_POLICY_VERSION}
    result["title"] = "RadishAxiom checker runtime launcher policy v0.1"
    return result


def build_contract(records: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    policy = launcher_policy()
    rows = []
    for path, value in records:
        rows.append({
            "id": value["id"],
            "path": path,
            "raw_sha256": sha256_bytes(pretty_bytes(value)),
            "record_digest": value["record_digest"],
            "registration_status": value["registration"]["status"],
            "source": value["checker"]["source"]["identity"],
        })
    body = {
        "activation_readiness": {
            "authorization": "not-granted",
            "decision": "blocked",
            "installation": "not-materialized",
            "launcher_policy": {
                "format": policy["format"],
                "format_version": policy["format_version"],
                "path": "contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs",
                "policy_digest": policy["policy_digest"],
                "status": policy["level"],
            },
            "reasons": [
                "activation-transition-requires-separate-authorization",
                "installation-not-materialized",
                "launcher-policy-not-implemented",
                "runtime-companion-not-materialized-by-product-launcher",
            ],
            "runtime_companion": "not-materialized-by-product-launcher",
        },
        "counts": {
            "active": "0",
            "historical_ineligible": "1",
            "launcher_policies": "1",
            "records": "2",
            "registered_inactive": "1",
        },
        "current_checker_source": CURRENT_SOURCE,
        "digest_domain": SET_DOMAIN,
        "format": SET_FORMAT,
        "format_version": FORMAT_VERSION,
        "generator": {"path": "scripts/generate-checker-runtime-payloads.py", "raw_sha256": raw_sha256(Path(__file__))},
        "launcher_policy": {
            "format": policy["format"],
            "format_version": policy["format_version"],
            "level": policy["level"],
            "path": "contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs",
            "policy_digest": policy["policy_digest"],
            "raw_sha256": sha256_bytes(canonical_bytes(policy)),
        },
        "records": rows,
        "runtime_statement": "current-source-runtime-payload-is-registered-inactive-not-active",
        "storage_policy": STORAGE_POLICY,
    }
    return {**body, "contract_digest": domain_digest(SET_DOMAIN, body)}


def outputs() -> dict[Path, bytes]:
    historical = historical_record()
    current = registered_inactive_record()
    policy = launcher_policy()
    records = [
        ("contracts/checker-runtime-payloads-v0.1/records/checker-go0.1-dev-darwin-arm64-historical.json", historical),
        ("contracts/checker-runtime-payloads-v0.1/records/checker-go0.1-dev-darwin-arm64-current-registered-inactive.json", current),
    ]
    for _, value in records:
        validate_record(value)
    validate_launcher_policy(policy)
    expected = {REPO_ROOT / path: pretty_bytes(value) for path, value in records}
    expected[CONTRACT_ROOT / "contract.json"] = pretty_bytes(build_contract(records))
    expected[CONTRACT_ROOT / "launcher-policy.jcs"] = canonical_bytes(policy)
    expected[CONTRACT_ROOT / "schemas/checker-runtime-launcher-policy.schema.json"] = pretty_bytes(
        launcher_policy_schema(policy)
    )
    expected[CONTRACT_ROOT / "schemas/checker-runtime-payload-registration.schema.json"] = pretty_bytes(schema([historical, current]))
    negative_rows = []
    for filename, reason, value in negative_fixtures(historical, current):
        try:
            validate_record(value)
        except ValueError:
            pass
        else:
            raise ValueError(f"negative fixture was accepted: {filename}")
        expected[CONTRACT_ROOT / "fixtures/negative" / filename] = pretty_bytes(value)
        negative_rows.append({"file": filename, "reason": reason})
    expected[CONTRACT_ROOT / "fixtures/negative/expected.json"] = pretty_bytes({
        "fixtures": negative_rows,
        "format": "radishaxiom-checker-runtime-payload-negative-set",
        "format_version": FORMAT_VERSION,
    })
    launcher_negative_rows = []
    for filename, reason, value in launcher_negative_fixtures(policy):
        try:
            validate_launcher_policy(value)
        except ValueError:
            pass
        else:
            raise ValueError(f"launcher negative fixture was accepted: {filename}")
        expected[CONTRACT_ROOT / "fixtures/launcher-negative" / filename] = pretty_bytes(value)
        launcher_negative_rows.append({"file": filename, "reason": reason})
    expected[CONTRACT_ROOT / "fixtures/launcher-negative/expected.json"] = pretty_bytes({
        "fixtures": launcher_negative_rows,
        "format": "radishaxiom-checker-runtime-launcher-policy-negative-set",
        "format_version": LAUNCHER_POLICY_VERSION,
    })
    return expected


def write_outputs(expected: dict[Path, bytes]) -> None:
    for path, data in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"wrote checker runtime payload registrations ({len(expected)} generated files)")


def check_outputs(expected: dict[Path, bytes]) -> int:
    errors = []
    for path, data in expected.items():
        if not path.is_file():
            errors.append(f"missing generated file: {path.relative_to(REPO_ROOT)}")
        elif path.read_bytes() != data:
            errors.append(f"generated file drifted: {path.relative_to(REPO_ROOT)}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"checker runtime payload registrations passed ({len(expected)} generated files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        expected = outputs()
        if args.write:
            write_outputs(expected)
            return 0
        return check_outputs(expected)
    except (KeyError, OSError, UnicodeError, ValueError) as error:
        print(f"checker runtime payload registration failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
