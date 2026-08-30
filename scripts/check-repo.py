#!/usr/bin/env python3
"""Dependency-free repository governance and text hygiene checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_PATH_LENGTH = 180
MAX_FILE_BYTES = 10 * 1024 * 1024

REQUIRED_FILES = (
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug-report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/semantic-proposal.yml",
    ".github/rulesets/README.md",
    ".github/rulesets/master-protection.json",
    ".github/workflows/pr-check.yml",
    "AGENTS.md",
    "CLAUDE.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "benchmarks/keyed-finite-table-v0.1/README.md",
    "benchmarks/keyed-finite-table-v0.1/corpus.json",
    "contracts/README.md",
    "contracts/checker-runtime-payloads-v0.1/README.md",
    "contracts/checker-runtime-payloads-v0.1/contract.json",
    "contracts/checker-runtime-payloads-v0.1/fixtures/launcher-negative/expected.json",
    "contracts/checker-runtime-payloads-v0.1/fixtures/negative/expected.json",
    "contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs",
    "contracts/checker-runtime-payloads-v0.1/records/checker-go0.1-dev-darwin-arm64-current-registered-inactive.json",
    "contracts/checker-runtime-payloads-v0.1/records/checker-go0.1-dev-darwin-arm64-historical.json",
    "contracts/checker-runtime-payloads-v0.1/schemas/checker-runtime-launcher-policy.schema.json",
    "contracts/checker-runtime-payloads-v0.1/schemas/checker-runtime-payload-registration.schema.json",
    "contracts/execution-profiles-v0.1/README.md",
    "contracts/execution-profiles-v0.1/contract.json",
    "contracts/execution-profiles-v0.1/fixtures/negative/expected.json",
    "contracts/execution-profiles-v0.1/manifest.jcs",
    "contracts/execution-profiles-v0.1/schemas/execution-profile-set.schema.json",
    "contracts/independent-check-v0.1/README.md",
    "contracts/independent-check-v0.1/contract.json",
    "contracts/implementation-readiness-v0.1/README.md",
    "contracts/implementation-readiness-v0.1/contract.json",
    "contracts/implementation-readiness-v0.1/fixtures/negative/expected.json",
    "contracts/implementation-readiness-v0.1/manifest.jcs",
    "contracts/implementation-readiness-v0.1/schemas/implementation-readiness-manifest.schema.json",
    "contracts/keyed-finite-table-checker-bundles-v0.1/README.md",
    "contracts/keyed-finite-table-checker-bundles-v0.1/bundle-set.jcs",
    "contracts/keyed-finite-table-checker-bundles-v0.1/contract.json",
    "contracts/keyed-finite-table-checker-bundles-v0.1/schemas/keyed-finite-table-checker-bundle-set.schema.json",
    "contracts/pipeline-artifacts-v0.1/README.md",
    "contracts/pipeline-artifacts-v0.1/contract.json",
    "contracts/pipeline-artifacts-v0.1/fixtures/expected.json",
    "contracts/pipeline-artifacts-v0.1/schemas/axiom-host-data.schema.json",
    "contracts/pipeline-artifacts-v0.1/schemas/axiom-obligation-set.schema.json",
    "contracts/pipeline-artifacts-v0.1/schemas/axiom-pipeline-receipt.schema.json",
    "contracts/toolchain-adapters-v0.1/README.md",
    "contracts/toolchain-adapters-v0.1/registry.json",
    "contracts/toolchain-adapters-v0.1/schemas/toolchain-adapter-identities.schema.json",
    "contracts/toolchain-payload-acceptance-v0.1/README.md",
    "contracts/toolchain-payload-acceptance-v0.1/contract.json",
    "contracts/toolchain-payload-acceptance-v0.1/fixtures/negative/expected.json",
    "contracts/toolchain-payload-acceptance-v0.1/observations/go1.26.7-darwin-arm64.inspection.json",
    "contracts/toolchain-payload-acceptance-v0.1/observations/go1.26.7-source.inspection.json",
    "contracts/toolchain-payload-acceptance-v0.1/records/go1.26.7-darwin-arm64.acceptance.json",
    "contracts/toolchain-payload-acceptance-v0.1/records/go1.26.7-source.acceptance.json",
    "contracts/toolchain-payload-acceptance-v0.1/schemas/toolchain-payload-acceptance-record.schema.json",
    "contracts/toolchain-payload-acceptance-v0.1/schemas/toolchain-tar-inspection-observation.schema.json",
    "docs/README.md",
    "docs/adr/0001-branch-and-pr-governance.md",
    "docs/adr/0011-checker-runtime-launcher-installation-and-activation.md",
    "docs/adr/0012-product-checker-runtime-host-and-persistence-interface.md",
    "docs/benchmarks/keyed-finite-table-corpus-v0.md",
    "docs/experiments/agent-representation-preregistration-v0.md",
    "docs/governance/agent-collaboration.md",
    "docs/governance/repository-governance.md",
    "docs/licensing-strategy.md",
    "docs/product-definition.md",
    "docs/status/current.md",
    "experiments/agent-representation-v0.1/README.md",
    "experiments/agent-representation-v0.1/registration.json",
    "experiments/agent-representation-v0.1/registration.sha256",
    "scripts/check-repo.py",
    "scripts/check-repo.ps1",
    "scripts/check-repo.sh",
    "scripts/check-checker-runtime-launcher.py",
    "scripts/checker_runtime_launcher/__init__.py",
    "scripts/checker_runtime_launcher/core.py",
    "scripts/checker_runtime_launcher/qualification.py",
    "scripts/checker_runtime_launcher/tests.py",
    "scripts/checker_runtime_launcher/ustar.py",
    "scripts/generate-benchmark-corpus.py",
    "scripts/generate-checker-runtime-payloads.py",
    "scripts/generate-checker-bundle-contracts.py",
    "scripts/generate-execution-profile-contracts.py",
    "scripts/generate-independent-check-contracts.py",
    "scripts/generate-implementation-readiness.py",
    "scripts/generate-pipeline-artifact-contracts.py",
    "scripts/generate-toolchain-adapter-identities.py",
    "scripts/generate-toolchain-payload-acceptance.py",
    "scripts/inspect-toolchain-tar.py",
)

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".dart",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsonc",
    ".jsx",
    ".kt",
    ".kts",
    ".md",
    ".mjs",
    ".proto",
    ".ps1",
    ".py",
    ".rax",
    ".rs",
    ".sha256",
    ".scss",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

TEXT_NAMES = {
    ".dockerignore",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
    "Makefile",
}

CONVENTIONAL_COMMIT = re.compile(
    r"^(feat|fix|docs|refactor|test|chore|ci|build|perf|revert)"
    r"(\([a-z0-9._/-]+\))?!?: .+"
)
ALLOWED_MERGE_COMMIT = re.compile(
    r"^Merge (pull request|branch|remote-tracking branch)"
)
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def repository_files() -> list[Path]:
    result = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return sorted(
        (REPO_ROOT / item for item in result.stdout.split("\0") if item),
        key=lambda path: path.as_posix(),
    )


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def is_text_file(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def check_required_files(errors: list[str]) -> None:
    for item in REQUIRED_FILES:
        if not (REPO_ROOT / item).is_file():
            errors.append(f"missing required file: {item}")


def check_paths_and_sizes(paths: list[Path], errors: list[str]) -> None:
    for path in paths:
        name = relative(path)
        if len(name) > MAX_PATH_LENGTH:
            errors.append(f"path exceeds {MAX_PATH_LENGTH} characters: {name}")
        if path.is_file() and path.stat().st_size > MAX_FILE_BYTES:
            errors.append(
                f"file exceeds 10 MiB; use an explicit artifact or LFS policy: {name}"
            )


def check_text_files(paths: list[Path], errors: list[str]) -> None:
    for path in paths:
        if not path.is_file() or not is_text_file(path):
            continue

        name = relative(path)
        data = path.read_bytes()
        if data.startswith(b"\xef\xbb\xbf"):
            errors.append(f"UTF-8 BOM is not allowed: {name}")
            continue

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"text file is not valid UTF-8: {name}: {exc}")
            continue

        if "\x00" in text:
            errors.append(f"NUL byte found in declared text file: {name}")
        if "\r" in text:
            errors.append(f"text file must use LF line endings: {name}")
        if text and not text.endswith("\n"):
            errors.append(f"text file is missing final newline: {name}")

        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.endswith((" ", "\t")):
                errors.append(f"trailing whitespace: {name}:{line_number}")


def check_json_files(paths: list[Path], errors: list[str]) -> None:
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON: {relative(path)}: {exc}")


def check_markdown_links(paths: list[Path], errors: list[str]) -> None:
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            target = unquote(match.group(1))
            if target.startswith(("#", "/", "http://", "https://", "mailto:")):
                continue
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(REPO_ROOT)
            except ValueError:
                errors.append(f"relative link escapes repository: {relative(path)} -> {target}")
                continue
            if not resolved.exists():
                errors.append(f"broken relative link: {relative(path)} -> {target}")


def check_agent_files(errors: list[str]) -> None:
    agents = REPO_ROOT / "AGENTS.md"
    claude = REPO_ROOT / "CLAUDE.md"
    if agents.is_file() and claude.is_file() and agents.read_bytes() != claude.read_bytes():
        errors.append("AGENTS.md and CLAUDE.md must remain identical")


def find_rule(rules: list[object], rule_type: str) -> dict[str, object] | None:
    for rule in rules:
        if isinstance(rule, dict) and rule.get("type") == rule_type:
            return rule
    return None


def check_ruleset_contract(errors: list[str]) -> None:
    path = REPO_ROOT / ".github/rulesets/master-protection.json"
    if not path.is_file():
        return
    try:
        ruleset = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    include = ruleset.get("conditions", {}).get("ref_name", {}).get("include", [])
    if include != ["refs/heads/master"]:
        errors.append("master ruleset must target only refs/heads/master")

    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        errors.append("master ruleset must define a rules array")
        return

    for required_type in ("deletion", "non_fast_forward", "pull_request", "required_status_checks"):
        if find_rule(rules, required_type) is None:
            errors.append(f"master ruleset is missing rule: {required_type}")

    pull_request = find_rule(rules, "pull_request")
    if pull_request is not None:
        parameters = pull_request.get("parameters", {})
        if parameters.get("allowed_merge_methods") != ["merge", "rebase"]:
            errors.append("master ruleset must allow merge and rebase, in that order")
        if parameters.get("required_review_thread_resolution") is not True:
            errors.append("master ruleset must require review thread resolution")
        if parameters.get("required_approving_review_count") != 0:
            errors.append("single-maintainer baseline must require zero approvals")

    checks = find_rule(rules, "required_status_checks")
    if checks is not None:
        parameters = checks.get("parameters", {})
        contexts = [
            item.get("context")
            for item in parameters.get("required_status_checks", [])
            if isinstance(item, dict)
        ]
        if contexts != ["Candidate Quality"]:
            errors.append("master ruleset must require only the Candidate Quality context")
        if parameters.get("strict_required_status_checks_policy") is not True:
            errors.append("master ruleset must require the branch to be up to date")


def check_workflow_contract(errors: list[str]) -> None:
    path = REPO_ROOT / ".github/workflows/pr-check.yml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    required_fragments = (
        "pull_request:",
        "      - dev",
        "      - master",
        "name: Repo Hygiene",
        "name: Candidate Quality",
        "./scripts/check-repo.sh",
    )
    for fragment in required_fragments:
        if fragment not in text:
            errors.append(f"PR workflow is missing contract fragment: {fragment.strip()}")


def check_benchmark_corpus(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-benchmark-corpus.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"benchmark corpus check failed: {detail}")


def check_independent_check_contracts(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-independent-check-contracts.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"independent check contracts failed: {detail}")


def check_toolchain_adapter_identities(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-toolchain-adapter-identities.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"toolchain adapter identities failed: {detail}")


def check_toolchain_payload_acceptance(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-toolchain-payload-acceptance.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"toolchain payload acceptance failed: {detail}")


def check_checker_runtime_payloads(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-checker-runtime-payloads.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"checker runtime payload registrations failed: {detail}")


def check_checker_runtime_launcher(errors: list[str]) -> None:
    checker = REPO_ROOT / "scripts/check-checker-runtime-launcher.py"
    if not checker.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(checker)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"checker runtime launcher conformance failed: {detail}")


def check_pipeline_artifact_contracts(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-pipeline-artifact-contracts.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"pipeline artifact contracts failed: {detail}")


def check_implementation_readiness(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-implementation-readiness.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"implementation readiness contract failed: {detail}")


def check_execution_profile_contracts(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-execution-profile-contracts.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"execution profile contracts failed: {detail}")


def check_checker_bundle_contracts(errors: list[str]) -> None:
    generator = REPO_ROOT / "scripts/generate-checker-bundle-contracts.py"
    if not generator.is_file():
        return

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"checker bundle contract failed: {detail}")


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def check_agent_experiment_registration(errors: list[str]) -> None:
    root = REPO_ROOT / "experiments/agent-representation-v0.1"
    path = root / "registration.json"
    digest_path = root / "registration.sha256"
    if not path.is_file() or not digest_path.is_file():
        return

    expected_line = f"{sha256(path).removeprefix('sha256:')}  registration.json\n"
    if digest_path.read_text(encoding="utf-8") != expected_line:
        errors.append("agent experiment registration.sha256 does not match registration.json")

    try:
        registration = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(registration, dict):
        errors.append("agent experiment registration must be a JSON object")
        return

    bindings = registration.get("bindings")
    if not isinstance(bindings, dict):
        errors.append("agent experiment registration must define bindings")
        return
    for name, binding in bindings.items():
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
            errors.append(f"agent experiment binding is invalid: {name}")
            continue
        bound_path = (REPO_ROOT / binding["path"]).resolve()
        try:
            bound_path.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"agent experiment binding escapes repository: {name}")
            continue
        if not bound_path.is_file():
            errors.append(f"agent experiment binding is missing: {name}")
        elif sha256(bound_path) != binding.get("raw_sha256"):
            errors.append(f"agent experiment binding digest changed: {name}")

    models = registration.get("models", [])
    representations = registration.get("representations", [])
    tasks = registration.get("tasks", [])
    replicates = registration.get("replicates", [])
    schedule = registration.get("schedule", {})
    budgets = registration.get("budgets", {})
    if not all(
        isinstance(value, list)
        for value in (models, representations, tasks, replicates)
    ) or not isinstance(schedule, dict) or not isinstance(budgets, dict):
        errors.append("agent experiment design arrays or budget objects are invalid")
        return
    bundle_count = len(models) * len(representations) * len(tasks) * len(replicates)
    if (len(models), len(representations), len(tasks), len(replicates)) != (2, 3, 4, 3):
        errors.append("agent experiment must keep the registered 2x3x4x3 design")
    if schedule.get("bundle_count") != bundle_count or bundle_count != 72:
        errors.append("agent experiment bundle count is inconsistent")
    maximum_calls = bundle_count * budgets.get("maximum_calls_per_bundle", 0)
    if budgets.get("maximum_total_model_calls") != maximum_calls or maximum_calls != 432:
        errors.append("agent experiment model-call budget is inconsistent")
    if budgets.get("maximum_total_visible_input_tokens") != (
        maximum_calls * budgets.get("per_call_visible_input_tokens", 0)
    ):
        errors.append("agent experiment input-token budget is inconsistent")
    if budgets.get("maximum_total_visible_output_tokens") != (
        maximum_calls * budgets.get("per_call_visible_output_tokens", 0)
    ):
        errors.append("agent experiment output-token budget is inconsistent")

    corpus_binding = bindings.get("corpus", {})
    if not isinstance(corpus_binding, dict) or not isinstance(corpus_binding.get("path"), str):
        errors.append("agent experiment corpus binding is invalid")
        return
    corpus_path = REPO_ROOT / corpus_binding.get("path", "")
    if corpus_path.is_file():
        try:
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            corpus = {}
        if not isinstance(corpus, dict):
            corpus = {}
        corpus_tasks = [item.get("benchmark_id") for item in corpus.get("tasks", [])]
        if tasks != corpus_tasks:
            errors.append("agent experiment task list differs from the bound corpus")

    if registration.get("status") not in {"proposed", "accepted"}:
        errors.append("agent experiment registration has an invalid status")
    if registration.get("execution_lock", {}).get("required_before_benchmark_calls") is not True:
        errors.append("agent experiment must require an execution lock before model calls")


def check_diff(base_ref: str | None, errors: list[str]) -> None:
    commands = []
    if base_ref:
        if git("rev-parse", "--verify", base_ref, check=False).returncode != 0:
            errors.append(f"base ref does not resolve: {base_ref}")
            return
        commands.append(("diff", "--check", f"{base_ref}...HEAD"))
    else:
        commands.extend((("diff", "--check"), ("diff", "--cached", "--check")))

    for command in commands:
        result = git(*command, check=False)
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip()
            errors.append(f"git {' '.join(command)} failed: {detail}")


def check_commit_messages(base_ref: str | None, errors: list[str]) -> None:
    if not base_ref:
        return
    result = git("log", "--format=%H%x09%s", f"{base_ref}...HEAD")
    for line in result.stdout.splitlines():
        commit, _, subject = line.partition("\t")
        if CONVENTIONAL_COMMIT.fullmatch(subject) or ALLOWED_MERGE_COMMIT.match(subject):
            continue
        errors.append(f"non-conventional commit subject: {commit[:12]} {subject}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        help="optional base commit/ref for PR diff and commit-message checks",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    paths = repository_files()

    check_required_files(errors)
    check_paths_and_sizes(paths, errors)
    check_text_files(paths, errors)
    check_json_files(paths, errors)
    check_markdown_links(paths, errors)
    check_agent_files(errors)
    check_ruleset_contract(errors)
    check_workflow_contract(errors)
    check_benchmark_corpus(errors)
    check_independent_check_contracts(errors)
    check_toolchain_adapter_identities(errors)
    check_toolchain_payload_acceptance(errors)
    check_checker_runtime_payloads(errors)
    check_checker_runtime_launcher(errors)
    check_pipeline_artifact_contracts(errors)
    check_implementation_readiness(errors)
    check_execution_profile_contracts(errors)
    check_checker_bundle_contracts(errors)
    check_agent_experiment_registration(errors)
    check_diff(args.base_ref, errors)
    check_commit_messages(args.base_ref, errors)

    if errors:
        print("repository baseline failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"repository baseline passed ({len(paths)} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
