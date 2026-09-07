#!/usr/bin/env python3
"""Collect a Debian Linux builder inventory; never install or accept its tools.

Run only in an explicitly selected, isolated environment. The caller retains the
exact image identity, this input script, raw output, and invocation constraints.
The JSON is a diagnostic observation, not a public tool acceptance record.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


TOOLS = {
    "gcc": ["--version"],
    "ld": ["--version"],
    "make": ["--version"],
    "bash": ["--version"],
    "flex": ["--version"],
    "bison": ["--version"],
    "bc": ["--version"],
    "perl": ["-e", "print $^V"],
    "python3": ["--version"],
    "pkg-config": ["--version"],
    "tar": ["--version"],
    "xz": ["--version"],
    "gpg": ["--version"],
    "rustc": ["--version", "--verbose"],
    "cargo": ["--version"],
    "go": ["version"],
}


def run(args: list[str]) -> dict[str, str]:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", timeout=3,
            check=False, env={**os.environ, "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"inventory command timed out: {args[0]}") from error
    return {
        "exit_code": str(result.returncode),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def os_release() -> dict[str, str]:
    names = {"ID", "VERSION_ID", "VERSION_CODENAME", "PRETTY_NAME"}
    result = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key in names:
            if key in result:
                raise ValueError(f"duplicate OS release field: {key}")
            words = shlex.split(value)
            if len(words) != 1:
                raise ValueError(f"invalid OS release field: {key}")
            result[key] = words[0]
    if result.get("ID") != "debian":
        raise ValueError("this inventory entry requires Debian; no distro fallback")
    return result


def parse_packages(text: str) -> list[dict[str, str]]:
    fields = ("package", "version", "architecture", "status", "source", "source_version")
    rows = []
    seen = set()
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != len(fields) or any(not value for value in parts):
            raise ValueError("invalid dpkg inventory row")
        row = dict(zip(fields, parts, strict=True))
        identity = (row["package"], row["architecture"])
        if identity in seen:
            raise ValueError(f"duplicate package identity: {identity}")
        seen.add(identity)
        rows.append(row)
    if not rows:
        raise ValueError("empty dpkg inventory")
    return sorted(rows, key=lambda row: (row["package"], row["architecture"]))


def file_identity(path: str) -> dict[str, str]:
    resolved = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return {"resolved_path": str(resolved), "raw_sha256": "sha256:" + digest.hexdigest()}


def inventory() -> dict:
    if sys.platform != "linux":
        raise ValueError("Linux is required; host execution is not a builder observation")
    release = os_release()
    query = shutil.which("dpkg-query")
    if query is None:
        raise ValueError("dpkg-query is missing")
    package_format = "\t".join(
        "${" + key + "}" for key in (
            "binary:Package", "Version", "Architecture", "db:Status-Status",
            "source:Package", "source:Version",
        )
    ) + "\n"
    packages = run([query, "-W", "-f=" + package_format])
    if packages["exit_code"] != "0":
        raise ValueError(f"dpkg inventory failed: {packages['stderr'].strip()}")
    tools = []
    for name, arguments in TOOLS.items():
        path = shutil.which(name)
        if path is None:
            tools.append({"name": name, "status": "missing"})
            continue
        probe = run([path, *arguments])
        tool = {
            "name": name,
            "status": "observed" if probe["exit_code"] == "0" else "probe-failed",
            "invocation_path": path,
            "invocation_file": file_identity(path),
            "version_probe": probe,
        }
        # The rustc/cargo commands can be rustup shims. Bind the selected binary
        # separately instead of presenting the shim hash as the compiler hash.
        if name in {"rustc", "cargo"}:
            rustup = shutil.which("rustup")
            if rustup is None:
                tool["selected_binary"] = {"status": "not-resolved-no-rustup"}
            else:
                selected = run([rustup, "which", name])
                target = selected["stdout"].strip()
                if selected["exit_code"] != "0" or not target.startswith("/"):
                    tool["selected_binary"] = {"status": "resolution-failed", "probe": selected}
                else:
                    tool["selected_binary"] = {"status": "observed", **file_identity(target)}
        tools.append(tool)
    return {
        "format": "radishaxiom-linux-builder-inventory",
        "format_version": "0.1",
        "kind": "diagnostic-observation",
        "acceptance": "not-assessed",
        "os_release": release,
        "kernel": {"release": os.uname().release, "machine": os.uname().machine},
        "packages": parse_packages(packages["stdout"]),
        "tools": sorted(tools, key=lambda tool: tool["name"]),
    }


def main() -> int:
    try:
        result = inventory()
    except (OSError, UnicodeError, ValueError) as error:
        print(f"builder inventory failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
