"""Build and describe a Darwin arm64 P5 release candidate without approving it."""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_case_candidate import (  # noqa: E402
    ROOT, RULE, TOOLCHAIN, artifact, canonical_bytes, dependencies, find_tool, raw_digest,
    workspace_materials,
)

TARGET = "aarch64-apple-darwin"
EXAMPLE = Path("target") / TARGET / "release/examples/record_p5_fixture"
STD = ROOT / ("contracts/toolchain-payload-acceptance-v0.1/records/"
              "rust-std-1.97.1-aarch64-apple-darwin.acceptance.json")
RECIPE = [
    "rustc", "--package", "radishaxiom-ir", "--example", EXAMPLE.name,
    "--target", TARGET, "--release", "--locked", "--offline",
]
LINKER_OBSERVER = """#!/bin/sh
set -eCu
printf '%s\\0' "$@" > "$P5_LD_ARGS"
if "$P5_LD" "$@" > "$P5_LD_TRACE" 2> "$P5_LD_STDERR"; then
    cat "$P5_LD_STDERR" >&2
else
    code=$?
    cat "$P5_LD_STDERR" >&2
    exit "$code"
fi
"""


def command(*argv, cwd=ROOT, env=None):
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, check=True, timeout=90,
    ).stdout.decode().strip()


def observe_std(path, installed):
    record = json.loads(STD.read_bytes())
    expected = record["provenance"]["project_recomputation"]["raw_sha256"]
    actual = artifact(path.read_bytes())
    if actual != {"byte_length": record["artifact"]["bytes"], "content_digest": expected}:
        raise ValueError("rust-std archive differs from the accepted input")
    selected = {}
    prefix = f"rust-std-1.97.1-{TARGET}/rust-std-{TARGET}/lib/rustlib/{TARGET}/lib"
    expected_members = {f"{prefix}/{name}": name for name in installed}
    with tarfile.open(path, "r|xz") as tar:
        for member in tar:
            file = expected_members.get(member.name)
            if file is None:
                continue
            descriptor = installed[file]
            if file in selected or not member.isfile() or artifact(tar.extractfile(member).read()) != descriptor:
                raise ValueError(f"installed rust-std archive differs for {file}")
            selected[file] = descriptor
    if selected != installed:
        raise ValueError("missing installed archive members in accepted rust-std input")
    return {"archive": actual, "acceptance": artifact(STD.read_bytes()), "link_archives": selected}


def retain(directory, name, raw):
    path = directory / name
    if not path.exists():
        with path.open("xb") as output:
            output.write(raw)
    if path.is_symlink() or path.read_bytes() != raw:
        raise ValueError(f"retained bytes differ for {name}")


def main(discovery, std_archive):
    deps = dependencies(discovery, ROOT)
    source = {path: (ROOT / path).read_bytes() for path in sorted(deps | workspace_materials())}
    cargo, rustc = find_tool("cargo"), find_tool("rustc")
    cargo_home = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")).resolve(strict=True)
    if any((cargo_home / name).exists() for name in ("config", "config.toml")):
        raise ValueError("local Cargo configuration requires separate review")
    xcode = Path(command("/usr/bin/xcode-select", "-p")).resolve(strict=True)
    env = {"DEVELOPER_DIR": str(xcode), "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}

    def xcrun(*args):
        return command("/usr/bin/xcrun", *args, env=env)

    sdk = Path(xcrun("--sdk", "macosx", "--show-sdk-path")).resolve(strict=True)
    clang, ld = (Path(xcrun("--find", name)).resolve(strict=True) for name in ("clang", "ld"))
    std_dir = Path(command(rustc, "--print", "target-libdir", "--target", TARGET)).resolve(strict=True)
    rust_home = rustc.parent.parent
    driver, = sorted((rust_home / "lib").glob("librustc_driver-*.dylib"))
    sdk_settings = sdk / "SDKSettings.json"
    libsystem = (sdk / "usr/lib/libSystem.tbd").resolve(strict=True)
    notice = rust_home / "share/doc/rust/COPYRIGHT-library.html"
    paths = {
        "cargo": cargo, "rustc": rustc, "librustc_driver": driver, "clang": clang, "ld": ld,
        "sdk_settings": sdk_settings, "sdk_libsystem_stub": libsystem,
        "rust_library_copyright": notice, "dyld": Path("/usr/lib/dyld"),
    }
    material = {name: artifact(path.read_bytes()) for name, path in paths.items()}
    std_before = {p.name: artifact(p.read_bytes()) for p in sorted(std_dir.glob("*.rlib"))}
    env.update({
        "CARGO_HOME": str(cargo_home), "CARGO_INCREMENTAL": "0", "RUSTC": str(rustc),
        "SDKROOT": str(sdk), "MACOSX_DEPLOYMENT_TARGET": "14.0",
    })

    with tempfile.TemporaryDirectory(prefix="radishaxiom-p5-release-") as temporary:
        snapshot = Path(temporary).resolve()
        for path, raw in source.items():
            copy = snapshot / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(raw)
        linker = snapshot / "observe-ld"
        linker.write_text(LINKER_OBSERVER)
        linker.chmod(0o700)
        ld_args = snapshot / "ld-args.nul"
        ld_trace = snapshot / "ld-trace.txt"
        dependency_info = snapshot / "ld-deps.bin"
        env.update({
            "CARGO_ENCODED_RUSTFLAGS": f"-Clinker={clang}\x1f-Clink-arg=--ld-path={linker}",
            "P5_LD": str(ld), "P5_LD_ARGS": str(ld_args),
            "P5_LD_TRACE": str(ld_trace), "P5_LD_STDERR": str(snapshot / "ld-stderr.txt"),
        })
        link_map = snapshot / "link.map"
        build = [*RECIPE, "--", "--print=link-args", "-Clink-arg=-Wl,-t",
                 f"-Clink-arg=-Wl,-map,{link_map}", f"-Clink-arg=-Wl,-dependency_info,{dependency_info}"]
        result = subprocess.run([cargo, *build], cwd=snapshot, env=env, capture_output=True, timeout=90)
        if result.returncode:
            sys.stderr.buffer.write(result.stderr)
            raise SystemExit(result.returncode)
        executable = snapshot / EXAMPLE
        trace = ld_trace.read_bytes()
        argv = ld_args.read_bytes().split(b"\0")
        dependencies_raw = dependency_info.read_bytes()
        map_text = link_map.read_bytes().decode(errors="replace")
        if os.fsencode(clang) not in result.stdout or os.fsencode(sdk) not in argv:
            raise ValueError("unexpected compiler driver or linker sysroot")
        # The Darwin dependency-info file uses NUL-terminated, opcode-prefixed
        # records. 0x10 identifies a concrete input, excluding failed lookups.
        link_inputs = {Path(os.fsdecode(row[1:])) for row in dependencies_raw.split(b"\0")
                       if row.startswith(b"\x10")}
        sdk_stubs = {}
        for path in sorted(link_inputs):
            if path.suffix == ".tbd":
                relative = path.resolve(strict=True).relative_to(sdk).as_posix()
                sdk_stubs[relative] = artifact(path.read_bytes())
            elif path.suffix not in {".o", ".rlib"}:
                raise ValueError(f"unexpected linker input class: {path.name}")
        if sdk_stubs.get(libsystem.relative_to(sdk).as_posix()) != material["sdk_libsystem_stub"]:
            raise ValueError("SDK libSystem stub missing from actual linker observations")
        linked = {Path(os.fsdecode(path)).name for path in argv
                  if path.startswith(os.fsencode(std_dir) + b"/") and path.endswith(b".rlib")}
        mapped = set(re.findall(re.escape(str(std_dir)) + r"/([^/\s\"()]+\.rlib)", map_text))
        if not mapped or not mapped <= linked:
            raise ValueError("link map Rust archive boundary differs from linker arguments")
        if not linked or any(artifact((std_dir / name).read_bytes()) != std_before[name] for name in linked):
            raise ValueError("missing or changed rust-std link archive")
        std = observe_std(std_archive, {name: std_before[name] for name in linked})
        if (dependencies(executable.with_suffix(".d"), snapshot) != deps
                or any((snapshot / path).read_bytes() != raw or (ROOT / path).read_bytes() != raw
                       for path, raw in source.items())
                or any(artifact(path.read_bytes()) != material[name] for name, path in paths.items())):
            raise ValueError("build materials changed")
        binary = executable.read_bytes()
        otool = xcrun("--find", "otool")
        direct = command(otool, "-L", executable, env=env).splitlines()[1:]
        if len(direct) != 1 or direct[0].strip().split()[0] != "/usr/lib/libSystem.B.dylib":
            raise ValueError("unexpected dynamic library boundary")
        load = subprocess.run(
            [executable], cwd=snapshot, env={
                "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "DYLD_PRINT_LIBRARIES": "1",
            }, capture_output=True, timeout=20,
        )
        images = re.findall(r"^dyld\[\d+\]: <([A-F0-9-]+)> (.+)$", load.stderr.decode(), re.MULTILINE)
        if (load.returncode != 2 or not images or images[0][1] != str(executable)
                or "/usr/lib/libSystem.B.dylib" not in {path for _, path in images[1:]}
                or any(not path.startswith("/usr/lib/") for _, path in images[1:])):
            raise ValueError("unexpected local dyld image observation")
        vtool = xcrun("--find", "vtool")
        metadata = command(vtool, "-show-build", executable, env=env).splitlines()[1:]
        source_set = [{"path": path.as_posix(), **artifact(raw)} for path, raw in source.items()]
        digest = raw_digest(binary).removeprefix("sha256:")
        trace_digest = raw_digest(ld_args.read_bytes()).removeprefix("sha256:")
        retained = ROOT / "target/p5-release-candidates" / digest / trace_digest
        retained.mkdir(parents=True, exist_ok=True)
        if retained.is_symlink():
            raise ValueError("retention directory must be local")
        retain(retained, EXAMPLE.name, binary)
        (retained / EXAMPLE.name).chmod(0o755)
        retain(retained, "link-args.txt", result.stdout)
        retain(retained, "ld-args.nul", ld_args.read_bytes())
        retain(retained, "ld-trace.txt", trace)
        retain(retained, "ld-deps.bin", dependencies_raw)
        retain(retained, "link.map", link_map.read_bytes())
        retain(retained, "COPYRIGHT-library.html", notice.read_bytes())
        record = {
            "artifact": artifact(binary),
            "artifact_path": (retained / EXAMPLE.name).relative_to(ROOT).as_posix(),
            "base_commit": command("git", "rev-parse", "HEAD"),
            "build": RECIPE,
            "compiler_inputs": sorted(path.as_posix() for path in deps),
            "direct_libraries": [line.strip() for line in direct],
            "dyld_images": [{"path": path, "uuid": uuid} for uuid, path in images[1:]],
            "executable_uuid": images[0][0],
            "format": "radishaxiom-p5-darwin-build",
            "format_version": "0.1",
            "host": {key: value.strip() for key, value in
                     (line.split(":", 1) for line in command("/usr/bin/sw_vers").splitlines())},
            "link_args": artifact(result.stdout),
            "linker_args": artifact(ld_args.read_bytes()),
            "linker_dependencies": artifact(dependencies_raw),
            "linker_observer": artifact(LINKER_OBSERVER.encode()),
            "linker_trace": artifact(trace),
            "link_map": artifact(link_map.read_bytes()),
            "link_metadata": [line.strip() for line in metadata],
            "material": material,
            "minimum_macos": env["MACOSX_DEPLOYMENT_TARGET"],
            "rule": raw_digest(source[RULE.relative_to(ROOT)]),
            "rust_std": std,
            "rust_std_contributing_archives": sorted(mapped),
            "sdk_version": xcrun("--sdk", "macosx", "--show-sdk-version"),
            "sdk_link_stubs": sdk_stubs,
            "source_inputs": source_set,
            "source_set_digest": raw_digest(canonical_bytes(source_set)),
            "target": TARGET,
            "toolchain": TOOLCHAIN,
            "xcode": command("/usr/bin/xcodebuild", "-version", env=env).splitlines(),
        }
    sys.stdout.buffer.write(canonical_bytes(record))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: capture_darwin_release.py DISCOVERY_DEPFILE ACCEPTED_RUST_STD_ARCHIVE")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
