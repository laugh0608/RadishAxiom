#!/usr/bin/env python3
"""从固定 ZIP 与已获取来源生成静态依赖线索；不下载、不解包、不执行载荷。"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import struct
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "scripts/inspect-cvc5-static-zip.py"))
MANIFEST = ROOT / "docs/records/cvc5-cli-dependencies-2026-10-17/source-inputs.json"
BASELINE = ROOT / "docs/records/cvc5-linux-arm64-preparation-2026-10-17/static-inspection.json"
COMMIT = "f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sections(data):
    M["inspect_elf"](data)
    h = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    require(h[11] == 64 and 0 < h[12] <= 128 and h[13] < h[12], "section-header-shape")
    require(h[6] >= 64 and h[6] + h[11] * h[12] <= len(data), "section-header-bounds")
    rows = [struct.unpack_from("<IIQQQQIIQQ", data, h[6] + i * h[11]) for i in range(h[12])]
    table = rows[h[13]]
    require(table[1] == 3 and table[4] + table[5] <= len(data), "section-names-bounds")
    names = data[table[4]:table[4] + table[5]]
    result = []
    for row in rows:
        require(row[0] < len(names), "section-name-offset")
        end = names.find(b"\0", row[0])
        require(end >= 0, "unterminated-section-name")
        name = names[row[0]:end].decode("ascii")
        require(row[1] == 8 or row[4] + row[5] <= len(data), "section-data-bounds")
        item = {"name": name, "type": row[1], "offset": row[4], "bytes": row[5]}
        if name == ".comment":
            require(row[5] <= 4096, "comment-size")
            item["strings"] = [s.decode("ascii") for s in data[row[4]:row[4] + row[5]].split(b"\0") if s]
        result.append(item)
    return result


def check_source(source_dir, entry):
    name = entry["file"]
    require(Path(name).name == name and name not in ("", ".", ".."), "source-file-name")
    path = source_dir / name
    with path.open("rb") as source:
        raw = source.read(4 * 1024 * 1024 + 1)
    require(len(raw) <= 4 * 1024 * 1024, "source-size-limit")
    require(len(raw) == entry["bytes"] and digest(raw) == entry["raw_digest"], "source-digest-mismatch")
    if "git_blob_sha1" in entry:
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(blob == entry["git_blob_sha1"], "git-blob-mismatch")
    return raw


def one(text, pattern):
    matches = re.findall(pattern, text)
    require(len(matches) == 1, "source-pattern-not-unique")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "output-already-exists")
    baseline_bytes = BASELINE.read_bytes()
    baseline = json.loads(baseline_bytes)
    with args.archive.open("rb") as source:
        archive_bytes = source.read(M["MAX_ARCHIVE"] + 1)
    require(digest(archive_bytes) == baseline["archive"]["raw_digest"], "archive-digest-mismatch")
    with ZipFile(io.BytesIO(archive_bytes)) as archive:
        M["validate_members"](archive.infolist())
        cli = archive.read(baseline["inspection"]["cli"]["path"])
    require(digest(cli) == baseline["inspection"]["cli"]["raw_digest"], "cli-digest-mismatch")
    manifest_bytes = MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    source = {entry["file"]: check_source(args.source_dir, entry) for entry in manifest["sources"]}
    texts = {name: raw.decode("utf-8") for name, raw in source.items()}
    recipes = {
        "cadical": {"version": one(texts["cmake__FindCaDiCaL.cmake"], r'set\(CaDiCaL_VERSION "(rel-[^" ]+)"\)'),
                    "archive_sha256": one(texts["cmake__FindCaDiCaL.cmake"], r'set\(CaDiCaL_CHECKSUM "([0-9a-f]{64})"\)')},
        "symfpu": {"commit": one(texts["cmake__FindSymFPU.cmake"], r'set\(SymFPU_COMMIT "([0-9a-f]{40})"\)'),
                   "archive_sha256": one(texts["cmake__FindSymFPU.cmake"], r'set\(SymFPU_CHECKSUM "([0-9a-f]{64})"\)')},
        "libpoly": {"version": one(texts["cmake__FindPoly.cmake"], r'set\(Poly_VERSION "([^" ]+)"\)'),
                    "archive_sha256": one(texts["cmake__FindPoly.cmake"], r'URL_HASH SHA256=([0-9a-f]{64})')},
        "gmp": {"version": one(texts["cmake__FindGMP.cmake"], r'set\(GMP_VERSION "([^" ]+)"\)'),
                "archive_sha256": one(texts["cmake__FindGMP.cmake"], r'URL_HASH SHA256=([0-9a-f]{64})')},
    }
    commit = json.loads(source["cvc5-commit.json"])
    require(commit["sha"] == COMMIT, "source-commit-mismatch")
    jobs = json.loads(source["cvc5-ci-jobs.json"])["jobs"]
    selected = [job for job in jobs if job["name"] == "ubuntu:production-arm64"]
    require(len(selected) == 1 and selected[0]["head_sha"] == COMMIT, "ci-job-mismatch")
    job = selected[0]
    markers = ["cadical-2.1.3-elevate-f3b21c4", "FloatingPointLiteralSymFPU",
               "  GMP - Gnu Multi Precision Arithmetic Library", "  LibPoly polynomial library",
               "  Editline Library", "/etc/terminfo:/lib/terminfo:/usr/share/terminfo",
               "Fatal glibc error:", "_GLIBCXX_REGEX_STATE_LIMIT"]
    result = {
        "format": "radishaxiom-cvc5-static-dependency-observation", "version": "0.1",
        "scope": "static-markers-pinned-recipes-and-license-sources-not-acceptance",
        "inspector_raw": digest(Path(__file__).read_bytes()),
        "base_inspector_raw": digest((ROOT / "scripts/inspect-cvc5-static-zip.py").read_bytes()),
        "static_observation_raw": digest(baseline_bytes), "source_inputs_raw": digest(manifest_bytes),
        "archive_raw": digest(archive_bytes), "cli_raw": digest(cli), "elf_sections": sections(cli),
        "cli_markers": [{"ascii": marker, "first_offset": cli.find(marker.encode()),
                         "occurrences": cli.count(marker.encode())} for marker in markers],
        "declared_fallback_recipes_not_proven_binary_inputs": recipes,
        "ci_job_observation": {key: job[key] for key in
                               ["id", "name", "head_sha", "conclusion", "labels", "html_url", "started_at", "completed_at"]},
        "ci_static_publish_step": [step for step in job["steps"]
                                   if step["name"] == "Create and add static package to latest and release"],
        "ci_logs_failure": json.loads(source["cvc5-ci-arm64.log"]),
        "source_count": len(source),
        "not_established": ["complete-linked-component-inventory", "exact-system-library-package-versions",
                            "recipe-to-binary-authenticated-provenance", "reproducible-build",
                            "license-acceptance", "redistribution-acceptance", "execution", "runtime-qualification"],
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(f"static dependency observation passed: {len(source)} sources; no execution or acceptance")


if __name__ == "__main__":
    main()
