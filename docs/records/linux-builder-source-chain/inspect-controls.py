#!/usr/bin/env python3
"""Read control metadata from these hash-checked .deb inputs, never install."""

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("debian_chain", ROOT / "scripts/inspect-debian-source-chain.py")
assert SPEC and SPEC.loader
CHAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHAIN)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("directory", type=Path)
parser.add_argument("--include-text", action="store_true", help="include maintainer script text for local review")
args = parser.parse_args()
report_bytes = (args.directory / "payload-chain-final.json").read_bytes()
report = json.loads(report_bytes)
assert report["payload_verification"] == "all-lengths-and-sha256-match"
packages = []
for artifact in report["artifacts"]:
    if artifact["role"] != "binary":
        continue
    data = (args.directory / artifact["filename"]).read_bytes()
    if len(data) != artifact["bytes"] or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
        raise ValueError("binary changed since source-chain verification")
    if data[:8] != b"!<arch>\n":
        raise ValueError("invalid ar envelope")
    offset, entries = 8, {}
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) != 60 or header[58:60] != b"`\n":
            raise ValueError("invalid ar header")
        size = int(header[48:58])
        name = header[:16].decode("ascii").strip().removesuffix("/")
        if size < 0 or name in entries or offset + 60 + size > len(data):
            raise ValueError("duplicate or invalid ar member")
        entries[name] = data[offset + 60:offset + 60 + size]
        offset += 60 + size + size % 2
    if offset != len(data) or entries.get("debian-binary") != b"2.0\n" or set(entries) != {"debian-binary", "control.tar.xz", "data.tar.xz"}:
        raise ValueError("unexpected Debian package layout")
    files, seen, fields = [], set(), None
    with tarfile.open(fileobj=io.BytesIO(entries["control.tar.xz"]), mode="r:xz") as archive:
        for member in archive:
            if member.isdir() and member.name == ".":
                continue
            name = member.name.removeprefix("./")
            if not member.isfile() or "/" in name or name in {"", ".", ".."} or name in seen or not 0 <= member.size <= 65536 or len(seen) >= 32:
                raise ValueError("unexpected control archive member")
            seen.add(name)
            stream = archive.extractfile(member)
            assert stream is not None
            content = stream.read(65537)
            if len(content) != member.size:
                raise ValueError("control file length mismatch")
            row = {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            if name == "control":
                records = list(CHAIN.stanzas(content.decode().splitlines(keepends=True)))
                if len(records) != 1:
                    raise ValueError("invalid binary control record")
                fields = {key: records[0].get(key) for key in ("package", "version", "source", "architecture", "depends", "pre-depends", "recommends", "conflicts", "replaces")}
                signed = report["binary_stanzas"][artifact["package"]]
                if any(value != signed.get(key) for key, value in fields.items()):
                    raise ValueError("binary control metadata differs from signed Packages")
            elif args.include_text and name in {"preinst", "postinst", "prerm", "postrm", "triggers"}:
                row["utf8_text"] = content.decode()
            files.append(row)
    if fields is None:
        raise ValueError("missing binary control file")
    packages.append({"package": artifact["package"], "fields": fields, "control_files": files})
print(json.dumps({"kind": "diagnostic-control-file-review", "acceptance": "not-assessed",
                  "source_chain_sha256": hashlib.sha256(report_bytes).hexdigest(),
                  "method_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "parser_sha256": hashlib.sha256((ROOT / "scripts/inspect-debian-source-chain.py").read_bytes()).hexdigest(),
                  "packages": packages}, sort_keys=True, indent=2))
