#!/usr/bin/env python3
"""Follow a diagnostic GnuPG observation through Debian indexes and payloads.

The GnuPG observation and candidate selection are trusted task inputs, not proof
certificates. This script does not implement cryptography, run apt, or install.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import io
import json
import lzma
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "docs/records/linux-6.18.49-archive-inventory/builder-package-candidates.json"
BOOKWORM_ARCHIVE = "B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8"
BOOKWORM_RELEASE = "4D64FEC119C2029067D6E791F8D2585B8783D481"
ALLOWED_SIGNERS = {BOOKWORM_ARCHIVE, BOOKWORM_RELEASE, "04B54C3CDCA79751B16BC6B5225629DF75B188BD"}
INDEX_PATHS = {"Packages.xz": "main/binary-arm64/Packages.xz", "Sources.xz": "main/source/Sources.xz"}
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_DECODED_BYTES = 256 * 1024 * 1024
MAX_STANZA_BYTES = 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path, expected: dict) -> None:
    if path.stat().st_size != expected["bytes"]:
        raise ValueError(f"length mismatch: {path.name}")
    state = hashlib.sha256()
    with path.open("rb") as stream:
        remaining = expected["bytes"]
        while remaining:
            data = stream.read(min(1024 * 1024, remaining))
            if not data:
                raise ValueError(f"truncated input: {path.name}")
            state.update(data)
            remaining -= len(data)
        if stream.read(1):
            raise ValueError(f"input grew: {path.name}")
    if state.hexdigest() != expected["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.name}")


def stanzas(lines):
    row, key, size = {}, None, 0
    for line in lines:
        if not line.endswith("\n") or "\r" in line:
            raise ValueError("Deb822 input must use complete LF lines")
        if line == "\n":
            if row:
                yield row
            row, key, size = {}, None, 0
            continue
        size += len(line.encode("utf-8"))
        if size > MAX_STANZA_BYTES:
            raise ValueError("Deb822 stanza limit exceeded")
        if line[0] in " \t":
            if key is None:
                raise ValueError("orphan Deb822 continuation")
            row[key] += "\n" + line[1:-1]
        else:
            name, colon, value = line[:-1].partition(":")
            key = name.lower()
            if not colon or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key) or key in row:
                raise ValueError("invalid or duplicate Deb822 field")
            row[key] = value.lstrip(" \t")
    if row:
        yield row


def checksums(value: str) -> dict:
    rows = {}
    for line in value.splitlines():
        if not line:
            continue
        fields = line.split()
        if len(fields) != 3 or not re.fullmatch(r"[0-9a-f]{64}", fields[0]) or not fields[1].isdigit():
            raise ValueError("invalid SHA-256 index row")
        path = fields[2]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+._/-]*", path) or any(p in {"", ".", ".."} for p in path.split("/")):
            raise ValueError("noncanonical index path")
        if path in rows:
            raise ValueError("duplicate checksum path")
        rows[path] = {"bytes": int(fields[1]), "sha256": fields[0]}
    if not rows:
        raise ValueError("missing SHA-256 rows")
    return rows


def signature_observation(observation: dict, inrelease: bytes) -> list[str]:
    if observation["exit_code"] != 0 or observation["inrelease_sha256"] != sha256(inrelease):
        raise ValueError("signature observation failed or refers to another InRelease")
    signers = []
    for line in observation["status"].splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] != "[GNUPG:]":
            raise ValueError("invalid GnuPG status line")
        if fields[1] in {"BADSIG", "ERRSIG", "EXPSIG", "EXPKEYSIG", "REVKEYSIG", "NO_PUBKEY", "FAILURE", "ERROR"}:
            raise ValueError("GnuPG failure status")
        if fields[1] == "VALIDSIG":
            if len(fields) != 12 or fields[-1] not in ALLOWED_SIGNERS or fields[9] not in {"8", "9", "10"}:
                raise ValueError("unexpected signer, status format or digest algorithm")
            signers.append(fields[-1])
    if len(signers) != len(set(signers)) or not {BOOKWORM_ARCHIVE, BOOKWORM_RELEASE} <= set(signers):
        raise ValueError("required independent bookworm signing roles missing or duplicated")
    text = inrelease.decode("utf-8")
    if not text.startswith("-----BEGIN PGP SIGNED MESSAGE-----\n"):
        raise ValueError("unexpected InRelease envelope")
    body = text.split("\n\n", 1)[1].split("-----BEGIN PGP SIGNATURE-----\n", 1)[0]
    cleartext = "".join(line[2:] if line.startswith("- ") else line for line in body.splitlines(keepends=True))
    if cleartext != observation["verified_text"]:
        raise ValueError("verified plaintext differs from InRelease")
    return sorted(signers)


def index_stanzas(path: Path, expected: dict):
    if expected["bytes"] > MAX_INDEX_BYTES:
        raise ValueError("compressed index limit exceeded")
    if path.stat().st_size != expected["bytes"]:
        raise ValueError("compressed index length mismatch")
    # Verify before decoding; hash the exact same bytes consumed by the decoder.
    data = path.read_bytes()
    if len(data) != expected["bytes"] or sha256(data) != expected["sha256"]:
        raise ValueError(f"signed index identity mismatch: {path.name}")
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128 * 1024 * 1024)
    source = io.BytesIO(data)

    def lines():
        pending, total = b"", 0
        while not decoder.eof:
            chunk = source.read(65536) if decoder.needs_input else b""
            if decoder.needs_input and not chunk:
                raise ValueError("truncated compressed index")
            decoded = decoder.decompress(chunk, max_length=65536)
            total += len(decoded)
            if total > MAX_DECODED_BYTES:
                raise ValueError("decoded index limit exceeded")
            pending += decoded
            parts = pending.split(b"\n")
            pending = parts.pop()
            for part in parts:
                if len(part) > MAX_STANZA_BYTES:
                    raise ValueError("index line limit exceeded")
                yield (part + b"\n").decode("utf-8")
            if len(pending) > MAX_STANZA_BYTES:
                raise ValueError("index line limit exceeded")
        if pending or decoder.unused_data or source.read(1):
            raise ValueError("incomplete line or trailing compressed index")
    yield from stanzas(lines())


def unique_selection(rows, expected: dict[str, str], *, binary: bool) -> dict:
    selected = {}
    for row in rows:
        name = row.get("package")
        if name not in expected:
            continue
        if name in selected:
            raise ValueError(f"duplicate selected package: {name}")
        if row.get("version") != expected[name] or (binary and row.get("architecture") != "arm64"):
            raise ValueError(f"selected package identity drift: {name}")
        selected[name] = row
    if set(selected) != set(expected):
        raise ValueError("selected package missing from signed index")
    return selected


def inspect(directory: Path, verify_payloads: bool, observed_at: datetime) -> dict:
    candidates_bytes = CANDIDATES.read_bytes()
    candidates = json.loads(candidates_bytes)["packages"]
    observation = json.loads((directory / "release-verification.json").read_text())
    inrelease = (directory / "InRelease").read_bytes()
    signers = signature_observation(observation, inrelease)
    releases = list(stanzas(observation["verified_text"].splitlines(keepends=True)))
    if len(releases) != 1:
        raise ValueError("Release must be a single stanza")
    release = releases[0]
    for key, value in {"origin": "Debian", "label": "Debian", "suite": "oldstable", "codename": "bookworm", "version": "12.15"}.items():
        if release.get(key) != value:
            raise ValueError(f"Release identity drift: {key}")
    published = parsedate_to_datetime(release["date"])
    if published.tzinfo is None or published > observed_at:
        raise ValueError("Release date is invalid or in the future")
    valid_until = release.get("valid-until")
    if valid_until and parsedate_to_datetime(valid_until) < observed_at:
        raise ValueError("Release has expired")
    indexes = checksums(release.get("sha256", ""))
    binary = unique_selection(index_stanzas(directory / "Packages.xz", indexes[INDEX_PATHS["Packages.xz"]]),
                              {c["package"]: c["version"] for c in candidates}, binary=True)
    sources = unique_selection(index_stanzas(directory / "Sources.xz", indexes[INDEX_PATHS["Sources.xz"]]),
                               {c["source_package"]: c["source_version"] for c in candidates}, binary=False)
    artifacts = []
    for candidate in candidates:
        name = candidate["package"]
        row = binary[name]
        source_identity = row.get("source", name)
        match = re.fullmatch(r"([a-z0-9+.-]+)(?: \(([^)]+)\))?", source_identity)
        if match is None or match[1] != candidate["source_package"] or (match[2] or row["version"]) != candidate["source_version"]:
            raise ValueError(f"binary/source identity mismatch: {name}")
        relative = f"pool/main/{name[0]}/{name}/{candidate['filename']}"
        if candidate["url"] != "https://deb.debian.org/debian/" + relative or row.get("filename") != relative or row.get("sha256") != candidate["publisher_sha256"] or row.get("size") != str(candidate["publisher_bytes"]):
            raise ValueError(f"candidate differs from signed binary metadata: {name}")
        artifacts.append({"package": name, "role": "binary", "filename": candidate["filename"],
                          "url": candidate["url"], "bytes": int(row["size"]), "sha256": row["sha256"]})
        source = sources[candidate["source_package"]]
        pool = f"pool/main/{name[0]}/{name}"
        if source.get("directory") != pool:
            raise ValueError("unexpected source pool directory")
        for filename, identity in checksums(source.get("checksums-sha256", "")).items():
            if "/" in filename:
                raise ValueError("source filename must be a basename")
            artifacts.append({"package": name, "role": "source", "filename": filename,
                              "url": "https://deb.debian.org/debian/" + pool + "/" + filename, **identity})
    if len({a["filename"] for a in artifacts}) != len(artifacts):
        raise ValueError("artifact basename collision")
    if verify_payloads:
        for artifact in artifacts:
            hash_file(directory / artifact["filename"], artifact)
    return {"kind": "diagnostic-debian-source-chain", "format_version": "1", "acceptance": "not-assessed",
            "observed_at": observed_at.isoformat(), "method_sha256": sha256(Path(__file__).read_bytes()),
            "candidate_record_sha256": sha256(candidates_bytes), "inrelease_sha256": sha256(inrelease),
            "signature_observation_sha256": sha256((directory / "release-verification.json").read_bytes()),
            "signer_primary_fingerprints": signers,
            "release": {key: release.get(key) for key in ("origin", "suite", "codename", "version", "date", "valid-until")},
            "freshness": "publisher-expiry-checked" if valid_until else "no-publisher-expiry; fixed snapshot only, no latest-security claim",
            "indexes": {name: {"path": path, **indexes[path]} for name, path in INDEX_PATHS.items()},
            "binary_stanzas": binary, "source_stanzas": sources, "artifacts": artifacts,
            "payload_verification": "all-lengths-and-sha256-match" if verify_payloads else "not-performed"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--verify-payloads", action="store_true")
    parser.add_argument("--observed-at", required=True, help="ISO-8601 UTC timestamp for this observation")
    args = parser.parse_args()
    try:
        observed = datetime.fromisoformat(args.observed_at)
        if observed.tzinfo is None or observed.utcoffset().total_seconds() != 0:
            raise ValueError("observation time must include UTC offset")
        result = inspect(args.directory, args.verify_payloads, observed)
    except (OSError, ValueError, KeyError, TypeError, lzma.LZMAError) as error:
        print(f"Debian chain inspection failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
