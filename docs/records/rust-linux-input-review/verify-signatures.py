#!/usr/bin/env python3
"""Run the fixed Rust release signature diagnostic inside an offline container."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


FINGERPRINT = "108F66205EAEB0AAA8DD5E1C85AB96E6FA1BE5FE"
KEY_SHA256 = "e54b09a439647e006b4831eec9785cbaaf3e07ab371c3a6ee6a68e1bdb9fbc6b"
FILES = (
    "channel-rust-1.97.1.toml",
    "rust-1.97.1-aarch64-unknown-linux-gnu.tar.xz",
    "rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz",
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def valid_status(status):
    rows = [line.split()[1:] for line in status.splitlines() if line.startswith("[GNUPG:] ")]
    bad = {"BADSIG", "ERRSIG", "EXPSIG", "EXPKEYSIG", "REVKEYSIG", "NO_PUBKEY", "FAILURE"}
    signatures = [row for row in rows if row[0] == "VALIDSIG"]
    return (not any(row[0] in bad for row in rows)
            and len(signatures) == 1 and len(signatures[0]) == 11
            and signatures[0][-1] == FINGERPRINT and signatures[0][8] in {"8", "9", "10"})


def main():
    inputs = Path("/inputs")
    key = inputs / "rust-key.gpg.ascii"
    if sha256(key) != KEY_SHA256:
        raise ValueError("public key transport bytes changed")
    result = {"kind": "diagnostic-observation", "acceptance": "not-assessed",
              "fingerprint": FINGERPRINT, "key_sha256": KEY_SHA256,
              "gpg_sha256": sha256(Path("/usr/bin/gpg")), "observations": []}
    with tempfile.TemporaryDirectory(prefix="rust-key-", dir="/tmp") as key_home:
        def run(*args):
            proc = subprocess.run(["/usr/bin/gpg", "--batch", "--no-options", "--homedir", key_home,
                                   *args], capture_output=True, text=True, timeout=40)
            return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        result["version"] = run("--version")
        result["key_show"] = run("--with-colons", "--import-options", "show-only", "--import", str(key))
        fingerprints = [line.split(":")[9] for line in result["key_show"]["stdout"].splitlines()
                        if line.startswith("fpr:")]
        if result["key_show"]["exit_code"] != 0 or not fingerprints or fingerprints[0] != FINGERPRINT:
            raise ValueError("full primary fingerprint mismatch")
        result["key_import"] = run("--import", str(key))
        result["key_certifications"] = run("--with-colons", "--check-sigs", FINGERPRINT)
        for name in FILES:
            observation = run("--status-fd", "1", "--verify", str(inputs / (name + ".asc")), str(inputs / name))
            observation.update({"file": name, "bytes": (inputs / name).stat().st_size,
                                "sha256": sha256(inputs / name),
                                "signature_sha256": sha256(inputs / (name + ".asc"))})
            observation["pinned_signature_passed"] = observation["exit_code"] == 0 and valid_status(observation["stdout"])
            result["observations"].append(observation)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["key_import"]["exit_code"] == 0 and all(row["pinned_signature_passed"] for row in result["observations"]) else 1


if __name__ == "__main__":
    sys.exit(main())
