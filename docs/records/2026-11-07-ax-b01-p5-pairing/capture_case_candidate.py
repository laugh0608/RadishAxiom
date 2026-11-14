"""Build the local P5 tool from a copied source set and report the exact candidate."""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import ROOT, canonical_bytes, raw_digest  # noqa: E402
from verify_case import tool_identity  # noqa: E402
from verify_execution import RULE  # noqa: E402

TOOLCHAIN = "1.97.1-aarch64-apple-darwin"
BUILD = ["build", "--package", "radishaxiom-ir", "--example", "record_p5_fixture", "--locked", "--offline"]
EXAMPLE = Path("target/debug/examples/record_p5_fixture")


def dependencies(depfile, root):
    lines = depfile.read_text().splitlines()
    if len(lines) != 1:
        raise ValueError("unexpected Cargo depfile")
    _, files = lines[0].split(": ", 1)
    paths = {Path(item).resolve(strict=True).relative_to(root) for item in shlex.split(files)}
    if EXAMPLE.name + ".rs" not in {path.name for path in paths}:
        raise ValueError("missing observation entry in depfile")
    return paths


def workspace_materials():
    paths = {Path(name) for name in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "LICENSE")}
    workspace = tomllib.loads((ROOT / "Cargo.toml").read_text())["workspace"]
    for member in workspace["members"]:
        root = Path(member)
        manifest = root / "Cargo.toml"
        paths.update((manifest, root / "src/lib.rs"))
        config = tomllib.loads((ROOT / manifest).read_text())
        for target in ("bin", "example", "test", "bench"):
            paths.update(root / item["path"] for item in config.get(target, []) if "path" in item)
    return paths


def artifact(raw):
    return {"byte_length": str(len(raw)), "content_digest": raw_digest(raw)}


def find_tool(name):
    raw = subprocess.check_output(["rustup", "which", "--toolchain", TOOLCHAIN, name], text=True)
    path = Path(raw.strip()).resolve(strict=True)
    assert path.is_absolute() and path.is_file()
    return path


def main(discovery_depfile):
    deps = dependencies(discovery_depfile, ROOT)
    paths = sorted(deps | workspace_materials(), key=Path.as_posix)
    source = {path: (ROOT / path).read_bytes() for path in paths}
    source_set = [{"path": path.as_posix(), **artifact(raw)} for path, raw in source.items()]
    cargo, rustc = find_tool("cargo"), find_tool("rustc")
    tool_bytes = {"cargo": cargo.read_bytes(), "rustc": rustc.read_bytes()}
    cargo_home = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")).resolve(strict=True)
    if any((cargo_home / name).exists() for name in ("config", "config.toml")):
        raise ValueError("local Cargo configuration requires separate review")
    env = {
        "CARGO_HOME": str(cargo_home), "CARGO_INCREMENTAL": "0", "LANG": "C",
        "LC_ALL": "C", "PATH": "/usr/bin:/bin", "RUSTC": str(rustc),
    }
    with tempfile.TemporaryDirectory(prefix="radishaxiom-p5-case-") as temporary:
        snapshot = Path(temporary).resolve()
        for path, raw in source.items():
            copy = snapshot / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(raw)
        subprocess.run([str(cargo), *BUILD], cwd=snapshot, env=env, check=True, timeout=90,
                       stdout=sys.stderr)
        executable = snapshot / EXAMPLE
        assert dependencies(executable.with_suffix(".d"), snapshot) == deps
        assert all((snapshot / path).read_bytes() == raw == (ROOT / path).read_bytes()
                   for path, raw in source.items())
        assert cargo.read_bytes() == tool_bytes["cargo"] and rustc.read_bytes() == tool_bytes["rustc"]
        assert 0 < executable.stat().st_size <= 32 * 1024 * 1024
        binary = executable.read_bytes()
        identity = tool_identity(binary)
        digest = identity["definition"]["artifact"].removeprefix("sha256:")
        relative = Path("target/p5-case-candidates") / digest / EXAMPLE.name
        retained = ROOT / relative
        retained.parent.parent.mkdir(parents=True, exist_ok=True)
        if not retained.parent.exists():
            retained.parent.mkdir()
            shutil.copy2(executable, retained)
        assert retained.is_file() and retained.read_bytes() == binary

    record = {
        "artifact": artifact(binary),
        "artifact_path": relative.as_posix(),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "build": BUILD,
        "compiler_inputs": sorted(path.as_posix() for path in deps),
        "format": "radishaxiom-private-p5-case-tool-candidate",
        "rule": raw_digest(source[RULE.relative_to(ROOT)]),
        "source_inputs": source_set,
        "source_set_digest": raw_digest(canonical_bytes(source_set)),
        "tool": identity,
        "toolchain": TOOLCHAIN,
        "tools": {name: artifact(raw) for name, raw in tool_bytes.items()},
        "version": "0.1",
    }
    sys.stdout.buffer.write(canonical_bytes(record))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: capture_case_candidate.py DISCOVERY_DEPFILE")
    main(Path(sys.argv[1]))
