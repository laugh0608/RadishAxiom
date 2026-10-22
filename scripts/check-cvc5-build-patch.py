#!/usr/bin/env python3
"""只读复核固定 cvc5 构建 patch；不运行上游脚本、CMake 或编译器。"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

COMMIT = "f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341"
ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_RECORD = "docs/records/solver-cvc5-source-review-2026-10-17/cvc5-tree.json"
FILES = {"CMakeLists.txt", "cmake/cvc5-c0-inputs.cmake", "cmake/version.cmake"} | {
    "cmake/Find" + name + ".cmake"
    for name in ("GMP", "CaDiCaL", "Poly", "SymFPU", "Editline")
}
HUNK = re.compile(rb"@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def safe_path(value):
    require(isinstance(value, str) and value and "\\" not in value and "\x00" not in value,
            "patch-unsafe-path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value
            and all(p not in (".", "..", ".git") for p in path.parts), "patch-unsafe-path")
    return value


def inventory(root):
    """包括所有普通文件；目录无内容身份，任何符号链接/特殊文件均拒绝。"""
    require(root.is_dir() and not root.is_symlink(), "source-root-not-directory")
    rows = []
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), "source-symlink")
        if stat.S_ISDIR(mode):
            continue
        require(stat.S_ISREG(mode), "source-special-file")
        raw = path.read_bytes()
        rows.append({"path": safe_path(path.relative_to(root).as_posix()), "bytes": len(raw),
                     "raw_digest": digest(raw), "executable": bool(mode & 0o111)})
    require(rows, "source-empty")
    return sorted(rows, key=lambda row: row["path"])


def apply_exact(raw, originals, allowed):
    """解析自有 unified diff；hunk 必须在声明行精确匹配，绝不搜索附近位置。"""
    require(raw.endswith(b"\n") and b"\r" not in raw and b"\x00" not in raw, "patch-text-format")
    lines = raw.splitlines(keepends=True)
    out, i = {}, 0
    while i < len(lines):
        match = re.fullmatch(rb"diff --git a/([^\n ]+) b/([^\n ]+)\n", lines[i])
        require(match is not None, "patch-diff-header")
        old, new = [safe_path(x.decode("utf-8")) for x in match.groups()]
        require(old == new and new in allowed and new not in out, "patch-file-set")
        i += 1
        if i < len(lines) and lines[i] == b"new file mode 100644\n":
            require(new not in originals, "patch-new-file-exists")
            old_marker = b"/dev/null"
            i += 1
        else:
            require(new in originals, "patch-old-file-missing")
            old_marker = b"a/" + new.encode()
        require(lines[i:i + 2] == [b"--- " + old_marker + b"\n", b"+++ b/" + new.encode() + b"\n"],
                "patch-file-header")
        i += 2
        original = originals.get(new, b"").splitlines(keepends=True)
        result, consumed, hunks = [], 0, 0
        while i < len(lines) and not lines[i].startswith(b"diff --git "):
            hunk = HUNK.fullmatch(lines[i])
            require(hunk is not None, "patch-hunk-header")
            old_line, old_count, new_line, new_count = map(int, hunk.groups())
            start = old_line - 1 if old_count else old_line
            require(consumed <= start <= len(original), "patch-hunk-position")
            result.extend(original[consumed:start])
            require(new_line == (len(result) + 1 if new_count else len(result)), "patch-new-hunk-position")
            consumed = start
            i += 1
            removed, added = 0, 0
            while i < len(lines) and not lines[i].startswith((b"@@ ", b"diff --git ")):
                line = lines[i]
                require(line[:1] in (b" ", b"-", b"+"), "patch-hunk-line")
                if line[:1] == b"+":
                    require(not line[:-1].endswith((b" ", b"\t")), "patch-added-trailing-whitespace")
                if line[:1] in (b" ", b"-"):
                    require(consumed < len(original) and original[consumed] == line[1:], "patch-preimage-mismatch")
                    consumed += 1
                    removed += 1
                if line[:1] in (b" ", b"+"):
                    result.append(line[1:])
                    added += 1
                i += 1
            require((removed, added) == (old_count, new_count), "patch-truncated-or-count-mismatch")
            hunks += 1
        require(hunks > 0, "patch-no-hunks")
        result.extend(original[consumed:])
        out[new] = b"".join(result)
    require(set(out) == set(allowed), "patch-file-set")
    return out


def check_no_fallback(contents):
    # 限于已替换的五个 Find 模块；完整源码其余 lookup 另由配置矩阵逐项审阅。
    forbidden = re.compile(rb"\b(find_path|find_library|find_program|pkg_check_modules|"
                           rb"ExternalProject_Add|check_ep_downloaded|check_auto_download|try_run|try_compile)\s*\(", re.I)
    for name, raw in contents.items():
        if name.startswith("cmake/Find"):
            require(forbidden.search(raw) is None, "patch-fallback-left-behind:" + name)
            require(re.search(rb"(?<![A-Za-z_])(-l[a-zA-Z]|\bbsd\b|\btinfo\b|\bmd\b)", raw) is None,
                    "patch-bare-link-left-behind:" + name)


def inspect(source, patch, record):
    require(record["format"] == "radishaxiom-cvc5-build-patch-review"
            and record["version"] == "0.1" and record["upstream_commit"] == COMMIT,
            "patch-upstream-identity")
    require(record["build_ready"] is False and record["acceptance"] == "not-accepted"
            and record["scope"] == "static-text-review-only-not-configure-or-build"
            and record["actual_dependency_manifest"] is None
            and record["actual_sdk_archive_inputs"] is None, "patch-review-acceptance-overclaim")
    require(record["patch_state"] == "prepared-static-candidate-not-executed"
            and record["executed"] == ["self-authored Python text inventory/diff/exact-application",
                                       "host git apply --check (text only)"]
            and record["not_executed"] == ["upstream scripts", "CMake", "Make", "autotools",
                                           "compiler", "solver", "probe"], "patch-review-execution-overclaim")
    require(set(record["changed_files"]) == FILES, "patch-review-changed-file-set")
    require(record["upstream_source_record"] == UPSTREAM_RECORD, "patch-upstream-record-path")
    upstream_raw = (ROOT / UPSTREAM_RECORD).read_bytes()
    require(digest(upstream_raw) == record["upstream_source_record_raw_digest"], "patch-upstream-record-digest")
    upstream = json.loads(upstream_raw)
    require(upstream["source_id"] == "cvc5" and upstream["top"] == "cvc5-" + COMMIT
            and upstream["global_pax"] == {"comment": COMMIT}, "patch-upstream-archive-identity")
    rows = inventory(source)
    expected = sorted((r["path"].removeprefix(upstream["top"] + "/"), r["bytes"], "sha256:" + r["sha256"])
                      for r in upstream["entries"] if r["kind"] == "file")
    require([(r["path"], r["bytes"], r["raw_digest"]) for r in rows] == expected,
            "source-archive-file-mismatch")
    require(len(rows) == record["before"]["file_count"]
            and digest(canonical(rows)) == record["before"]["inventory_digest"], "source-tree-mismatch")
    raw = patch.read_bytes()
    require(digest(raw) == record["patch"]["raw_digest"] and len(raw) == record["patch"]["bytes"], "patch-digest-mismatch")
    originals = {name: (source / name).read_bytes() for name in FILES if (source / name).exists()}
    changed = apply_exact(raw, originals, FILES)
    check_no_fallback(changed)
    after = {r["path"]: r.copy() for r in rows}
    for name, body in changed.items():
        after[name] = {"path": name, "bytes": len(body), "raw_digest": digest(body),
                       "executable": after.get(name, {}).get("executable", False)}
    after_rows = [after[name] for name in sorted(after)]
    require(digest(canonical(after_rows)) == record["after"]["inventory_digest"]
            and len(after_rows) == record["after"]["file_count"], "patched-tree-mismatch")
    for name in FILES:
        require(record["changed_files"][name] == {
            "before": digest(originals[name]) if name in originals else None,
            "after": digest(changed[name])}, "patch-file-digest-mismatch")
    return {"source_files": len(rows), "patched_files": len(changed), "execution": "none",
            "build_ready": False, "acceptance": "not-accepted"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("patch", type=Path)
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.source, args.patch, json.loads(args.record.read_bytes())), sort_keys=True))


if __name__ == "__main__":
    main()
