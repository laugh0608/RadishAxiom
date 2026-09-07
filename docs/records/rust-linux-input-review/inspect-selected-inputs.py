#!/usr/bin/env python3
"""Read selected, hash-bound installer/license/ELF bytes without executing them."""

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import struct
import tarfile


HOST = "rust-1.97.1-aarch64-unknown-linux-gnu"
MUSL = "rust-std-1.97.1-aarch64-unknown-linux-musl"
SELECTED = {
    HOST: {"install.sh", "COPYRIGHT", "rustc/share/doc/rust/COPYRIGHT-library.html",
           "rustc/bin/rustc", "cargo/bin/cargo",
           "rustc/lib/rustlib/aarch64-unknown-linux-gnu/bin/rust-lld"},
    MUSL: {"install.sh", "COPYRIGHT"},
    "linux-6.18.49": {"COPYING", "LICENSES/preferred/GPL-2.0",
                      "LICENSES/exceptions/Linux-syscall-note", "Documentation/process/license-rules.rst"},
}
PINS = {HOST: "9a7a2c336b4787f1b72f6bab7c35d5b7af2fd03cbd39b4fc721466a70d402a7d",
        MUSL: "49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31",
        "linux-6.18.49": "ae826f33111fea6f1d279dde7299d7463c8dfd204aeb75a8fb5432bc60a28191"}


def elf_dependencies(data):
    if data[:6] != b"\x7fELF\x02\x01" or len(data) < 64:
        raise ValueError("expected ELF64 little endian")
    offset = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    if stride != 56 or not 0 < count <= 512 or offset + stride * count > len(data):
        raise ValueError("invalid program headers")
    loads, dynamics, interpreter = [], [], None
    for index in range(count):
        kind, flags, file_offset, address, physical, size, memory, alignment = struct.unpack_from("<IIQQQQQQ", data, offset + index * stride)
        if file_offset + size > len(data):
            raise ValueError("segment outside file")
        if kind == 1:
            loads.append((address, file_offset, size))
        elif kind == 2:
            if size % 16 or size > 1024**2:
                raise ValueError("invalid dynamic segment")
            for place in range(file_offset, file_offset + size, 16):
                tag, value = struct.unpack_from("<qQ", data, place)
                if tag == 0:
                    break
                dynamics.append((tag, value))
        elif kind == 3:
            if interpreter is not None or size > 4096 or not data[file_offset:file_offset + size].endswith(b"\0"):
                raise ValueError("invalid interpreter")
            interpreter = data[file_offset:file_offset + size - 1].decode("ascii")
    def one(tag):
        values = [value for current, value in dynamics if current == tag]
        if len(values) != 1:
            raise ValueError("missing or duplicate dynamic string metadata")
        return values[0]
    strings = {}
    if dynamics:
        address, size = one(5), one(10)
        matches = [(start, off, length) for start, off, length in loads if start <= address and address + size <= start + length]
        if len(matches) != 1:
            raise ValueError("unmapped dynamic string table")
        start, off, length = matches[0]
        table = data[off + address - start:off + address - start + size]
        for tag, value in dynamics:
            if tag in {1, 15, 29}:
                if value >= len(table) or b"\0" not in table[value:value + 4096]:
                    raise ValueError("unbounded dynamic string")
                strings.setdefault(str(tag), []).append(table[value:].split(b"\0", 1)[0].decode("ascii"))
    return {"machine": struct.unpack_from("<H", data, 18)[0], "interpreter": interpreter,
            "needed": strings.get("1", []), "rpath": strings.get("15", []), "runpath": strings.get("29", [])}


def read_selected(path, top, include_text):
    rows = []
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != PINS[top]:
            raise ValueError("pinned archive mismatch")
        source.seek(0)
        with tarfile.open(fileobj=source, mode="r|xz") as archive:
            for member in archive:
                if member.name not in {top + "/" + name for name in SELECTED[top]}:
                    continue
                if not member.isfile() or member.size > 64 * 1024**2:
                    raise ValueError("selected input is not a bounded regular file")
                content = archive.extractfile(member).read()
                row = {"path": member.name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                if content.startswith(b"\x7fELF"):
                    row["elf"] = elf_dependencies(content)
                else:
                    text = content.decode("utf-8")
                    if include_text:
                        row["text"] = text
                    if member.name.endswith("/install.sh"):
                        row["selected_lines"] = [{"line": n, "text": line} for n, line in enumerate(text.splitlines(), 1)
                                                 if re.search(r"components|ldconfig|prefix|destdir", line)]
                    elif member.name.endswith("COPYRIGHT-library.html"):
                        plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
                        plain = re.sub(r"\s+", " ", plain)
                        row["attribution_matches"] = [{"term": term, "position": match.start(),
                                                       "excerpt": plain[max(0, match.start() - 120):match.end() + 240]}
                                                      for term in ("musl", "libunwind", "compiler-rt", "compiler_builtins")
                                                      for match in re.finditer(re.escape(term), plain, re.I)]
                rows.append(row)
                if len(rows) == len(SELECTED[top]):
                    break
    if len(rows) != len(SELECTED[top]):
        raise ValueError("selected inputs missing")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_inputs", type=Path)
    parser.add_argument("kernel_archive", type=Path)
    parser.add_argument("--include-text", action="store_true")
    args = parser.parse_args()
    result = {"kind": "diagnostic-observation", "acceptance": "not-assessed",
              "method_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "inputs": []}
    for top in SELECTED:
        path = args.kernel_archive if top == "linux-6.18.49" else args.rust_inputs / (top + ".tar.xz")
        result["inputs"].append({"file": path.name, "sha256": PINS[top], "selected_files": read_selected(path, top, args.include_text)})
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
