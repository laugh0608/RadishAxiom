#!/usr/bin/env python3
"""离线复核四份公开来源观察；不访问网络、不执行载荷、不产生接受记录。"""
import argparse
import hashlib
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/records/cvc5-provenance-followup-2026-10-17"
PRIOR = ROOT / "docs/records/cvc5-cli-dependencies-2026-10-17"
LIMIT = 1024 * 1024
COMMIT = "f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341"
ZIP = "sha256:2a4c108367f20b0c8990abd6b9535a5d62e08908d471d4671c00734e408f85bc"
CLI = "sha256:26fa94d71ecb3d4f1458eb06b9b9d4762fb3753cfb5cb9dca6f917fbf4dbe6c7"
API = "https://api.github.com/repos/cvc5/cvc5/"
EXPECTED = {
    "run-artifacts.json": (API + "actions/runs/25505454189/artifacts?per_page=100", 200),
    "zip-attestations.json": (API + "attestations/" + ZIP, 404),
    "cli-attestations.json": (API + "attestations/" + CLI, 404),
    "setup-cache.yml": ("https://raw.githubusercontent.com/cvc5/cvc5/" + COMMIT
                        + "/.github/actions/setup-cache/action.yml", 200),
}
RECIPE_URLS = {
    "cadical": "https://github.com/arminbiere/cadical/archive/rel-2.1.3-elevate.tar.gz",
    "symfpu": "https://github.com/cvc5/symfpu/archive/227a7246b8ce513b393cc2645d6d65d3490ea1de.tar.gz",
    "libpoly": "https://github.com/SRI-CSL/libpoly/archive/refs/tags/v0.2.1.tar.gz",
    "gmp": "https://github.com/cvc5/cvc5-deps/blob/main/gmp-6.3.0.tar.bz2?raw=true",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def read_bounded(path, limit=LIMIT):
    require(not path.is_symlink(), "source-symlink")
    require(stat.S_ISREG(path.stat().st_mode), "source-not-regular-file")
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    require(len(raw) <= limit, "source-size-limit")
    return raw


def check_archives(download, recipes):
    require(download["state"] == "approval-wait-aborted-by-user-no-observed-download-execution", "archive-download-state")
    archives = download["archives"]
    require(len(archives) == 4 and {r["component"] for r in archives} == set(recipes), "archive-recipe-set-mismatch")
    for item in archives:
        require(all(item.get(k) == v for k, v in recipes[item["component"]].items())
                and item["recipe_url"] == RECIPE_URLS[item["component"]]
                and item["status"] == "not-obtained" and item["recomputed_archive_digest"] is None
                and item["actual_binary_link"] is None, "archive-recipe-observation-mismatch")


def read_source(directory, row):
    name = row["file"]
    require(name in EXPECTED and Path(name).name == name, "source-file-name")
    require((row["url"], row["http_status"]) == EXPECTED[name], "source-request-mismatch")
    raw = read_bounded(directory / name)
    require(len(raw) == row["bytes"] and digest(raw) == row["raw_digest"], "source-digest-mismatch")
    return raw


def classify(name, raw, row):
    if name == "run-artifacts.json":
        body = json.loads(raw)
        require(type(body.get("total_count")) is int and body["total_count"] == 0
                and body.get("artifacts") == [], "artifact-count-body-mismatch")
        require(not row.get("link") or 'rel="next"' not in row["link"], "artifact-pagination")
        return {"http_status": 200, "artifact_count": 0,
                "conclusion": "no-artifacts-returned-at-observation-time-not-historical-absence"}
    if name.endswith("attestations.json"):
        body = json.loads(raw)
        require(body.get("status") == "404" and body.get("message") == "Not Found"
                and body.get("documentation_url") == "https://docs.github.com/rest/repos/attestations#list-attestations",
                "attestation-error-body-mismatch")
        return {"http_status": 404, "body_status": body["status"], "body_message": body["message"],
                "conclusion": "not-obtained-no-absence-claim-access-or-endpoint-behavior-not-excluded"}
    text = raw.decode("utf-8")
    for marker in ["uses: actions/cache@v5", "build-shared/deps", "build-static/deps",
                   "hashFiles('cmake/**')", "hashFiles('.github/**')"]:
        require(marker in text, "cache-recipe-marker-missing")
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return {"http_status": 200, "git_blob_sha1": blob,
            "conclusion": "pinned-cache-recipe-not-actual-hit-or-build-input-inventory"}


def inspect(directory):
    manifest_raw = read_bounded(RECORD / "source-inputs.json")
    manifest = json.loads(manifest_raw)
    rows = manifest["sources"]
    require(len(rows) == 4 and {r["file"] for r in rows} == set(EXPECTED), "source-set-mismatch")
    raw = {r["file"]: read_source(directory, r) for r in rows}
    observations = {r["file"]: classify(r["file"], raw[r["file"]], r) for r in rows}
    prior_raw = read_bounded(PRIOR / "dependency-observation.json")
    prior = json.loads(prior_raw)
    require(prior["cli_raw"] == CLI and prior["archive_raw"] == ZIP
            and prior["ci_job_observation"]["head_sha"] == COMMIT
            and prior["ci_job_observation"]["id"] == 74849773758, "prior-candidate-mismatch")
    require(digest(prior_raw) == manifest["prior_observation_raw"], "prior-observation-mismatch")
    check_archives(manifest["archive_download"], prior["declared_fallback_recipes_not_proven_binary_inputs"])
    # 新缓存文件的 blob 必须在前批已固定 tree 中，不把任意同名文本当作固定提交来源。
    prior_index_raw = read_bounded(PRIOR / "source-inputs.json")
    require(digest(prior_index_raw) == prior["source_inputs_raw"], "prior-source-index-mismatch")
    tree_row = next(r for r in json.loads(prior_index_raw)["sources"] if r["file"] == "cvc5-tree.json")
    tree_raw = read_bounded(directory.parent / "solver-cli-licenses-2026-10-17" / tree_row["file"], 4 * LIMIT)
    require(len(tree_raw) == tree_row["bytes"] and digest(tree_raw) == tree_row["raw_digest"], "tree-digest-mismatch")
    entries = [r for r in json.loads(tree_raw)["tree"] if r["path"] == ".github/actions/setup-cache/action.yml"]
    require(len(entries) == 1 and entries[0]["type"] == "blob"
            and entries[0]["sha"] == observations["setup-cache.yml"]["git_blob_sha1"], "cache-git-blob-mismatch")
    return {"format": "radishaxiom-cvc5-provenance-followup-observation", "version": "0.1",
            "scope": "bounded-public-source-observations-not-tool-acceptance", "acceptance": "not-accepted",
            "inspector_raw": digest(Path(__file__).read_bytes()), "source_inputs_raw": digest(manifest_raw),
            "prior_observation_raw": digest(prior_raw), "cli_raw": CLI, "archive_raw": ZIP,
            "observations": observations, "actual_binary_input_links": [],
            "unclosed": ["B1-exact-linked-system-components", "B2-actual-dependency-inputs", "B3-license-and-tool-acceptance"],
            "archive_download": manifest["archive_download"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "output-already-exists")
    result = inspect(args.source_dir)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print("4 source observations checked; B1/B2/B3 remain unclosed; not accepted")


if __name__ == "__main__":
    main()
