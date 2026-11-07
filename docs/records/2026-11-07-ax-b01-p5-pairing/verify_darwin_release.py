"""Run the reviewed AX-B01 Darwin release through the independent receipt verifier."""

import argparse
import contextlib
import ctypes
import io
import os
import plistlib
import pwd
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_receipt import (  # noqa: E402
    ROOT, RULE, acceptance_bytes, main as verify_receipts, parse_canonical, raw_digest,
)

CANDIDATE = Path(__file__).resolve().with_name("darwin-release-candidate.jcs")
MANIFEST_PIN = "sha256:7fe8afc6fbc3416264069a263348a4d2a25d2ba33619a5d30030f1a21e417ff4"
SYSTEM_VERSION = Path("/System/Library/CoreServices/SystemVersion.plist")
SYSTEM_VERSION_PIN = "sha256:bd61e19dd67dd97ce9a27c79a2148d42cc9685a71c6f17ff27d62b819f39f983"
SHARED_CACHE = uuid.UUID("c284a291-b68b-3d0d-a1a0-3f866f87efdc")
PYTHON_PIN = "sha256:c015ab131972822e27ed108cf353582af6ca2fd7daf6296789576c7e7d1ad61a"
SCHEMA = ROOT / "contracts/pipeline-artifacts-v0.2/schemas/axiom-pipeline-receipt.schema.json"
STAGING = Path("/private/tmp")
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
IMAGE_LINE = re.compile(rb"dyld\[(\d+)\]: <([A-F0-9-]+)> ([^\n]+)\n")


def read_regular(path, limit):
    # O_NONBLOCK prevents a substituted FIFO from blocking before fstat.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            raise ValueError(f"invalid regular file or byte length: {path}")
        raw = source.read(limit + 1)
    if len(raw) != info.st_size:
        raise ValueError(f"file length changed during read: {path}")
    return raw, info


def matches(raw, descriptor):
    return descriptor == {"byte_length": str(len(raw)), "content_digest": raw_digest(raw)}


def reviewed_candidate():
    provenance, _ = read_regular(CANDIDATE, 1024 * 1024)
    if raw_digest(provenance) != MANIFEST_PIN:
        raise ValueError("Darwin build manifest digest mismatch")
    manifest = parse_canonical(provenance)
    original = ROOT / manifest["artifact_path"]
    if original.resolve(strict=True) != original:
        raise ValueError("retained candidate path is not canonical")
    binary, _ = read_regular(original, int(manifest["artifact"]["byte_length"]))
    if not matches(binary, manifest["artifact"]):
        raise ValueError("retained candidate bytes differ from build manifest")
    rule, _ = read_regular(RULE, 64 * 1024)
    if raw_digest(rule) != manifest["rule"]:
        raise ValueError("P5 rule differs from build manifest")
    return manifest, provenance, binary, rule


def check_host(manifest):
    system = os.uname()
    if (system.sysname, system.release, system.machine) != ("Darwin", "27.0.0", "arm64"):
        raise ValueError("outside reviewed Darwin arm64 host scope")
    version, _ = read_regular(SYSTEM_VERSION, 4096)
    values = plistlib.loads(version)
    host = manifest["host"]
    if (raw_digest(version) != SYSTEM_VERSION_PIN
            or values["ProductBuildVersion"] != host["BuildVersion"]
            or any(values[key] != host[key] for key in ("ProductName", "ProductVersion"))):
        raise ValueError("macOS product version or build drift")
    loader = manifest["material"]["dyld"]
    raw, _ = read_regular(Path("/usr/lib/dyld"), int(loader["byte_length"]))
    if not matches(raw, loader):
        raise ValueError("system dyld bytes differ from build manifest")
    cache = (ctypes.c_ubyte * 16)()
    get_uuid = ctypes.CDLL("/usr/lib/libSystem.B.dylib")._dyld_get_shared_cache_uuid
    get_uuid.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
    get_uuid.restype = ctypes.c_bool
    if not get_uuid(cache) or uuid.UUID(bytes=bytes(cache)) != SHARED_CACHE:
        raise ValueError("dyld shared cache UUID differs from reviewed host")
    interpreter, _ = read_regular(Path(sys.executable).resolve(strict=True), 32 * 1024 * 1024)
    if sys.version_info[:3] != (3, 14, 5) or raw_digest(interpreter) != PYTHON_PIN:
        raise ValueError("Python executable differs from reviewed verifier host")


def check_acl(path):
    result = subprocess.run(
        ["/bin/ls", "-ldeb", path], cwd="/", env=ENV, capture_output=True, check=True, timeout=5,
    )
    # The reviewed home directory has the standard deny-delete ACL.
    if any(entry.strip() != b"0: group:everyone deny delete" for entry in result.stdout.splitlines()[1:]):
        raise ValueError(f"unexpected ACL on protected path: {path}")


def trust_config_path():
    home = Path(pwd.getpwuid(os.geteuid()).pw_dir)
    return home / ".config/radishaxiom/p5/acceptance.sha256"


def read_trusted_pin(path):
    if (not path.is_absolute() or path.is_relative_to(ROOT) or path.is_relative_to(STAGING)
            or path.resolve(strict=True) != path):
        raise ValueError("trusted config requires a canonical path outside checkout and staging")
    for directory in reversed(path.parents):
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.geteuid())
                or info.st_mode & 0o022):
            raise ValueError(f"unprotected trusted config directory: {directory}")
        check_acl(directory)
    if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
        raise ValueError("trusted config directory must have mode 0700")
    raw, info = read_regular(path, 72)
    if (info.st_uid not in (0, os.geteuid()) or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) not in (0o400, 0o600)):
        raise ValueError("trusted config must be a private, single-link file")
    check_acl(path)
    if not re.fullmatch(rb"sha256:[0-9a-f]{64}\n", raw):
        raise ValueError("invalid trusted acceptance SHA-256 configuration")
    return raw[:-1].decode("ascii")


def load_approval(path, config, expected, provenance):
    try:
        pin = read_trusted_pin(config)
    except FileNotFoundError as error:
        raise ValueError(f"independent trusted acceptance configuration missing: {config}") from error
    record, _ = read_regular(path, 8192)
    if raw_digest(record) != pin:
        raise ValueError("trusted acceptance record digest mismatch")
    if record != expected:
        raise ValueError("acceptance record does not match the reviewed P5 scope")
    return record, pin, provenance


def check_images(stderr, executable, manifest):
    images = [(manifest["executable_uuid"], str(executable))]
    images.extend((row["uuid"], row["path"]) for row in manifest["dyld_images"])
    pid = None
    for expected in images:
        match = IMAGE_LINE.match(stderr)
        if match is None:
            raise ValueError("missing dyld observation for protected launch")
        if (pid is not None and match[1] != pid) or tuple(
            item.decode() for item in (match[2], match[3])
        ) != expected:
            raise ValueError(f"dyld launch path or image mismatch at {expected[1]}")
        pid = match[1]
        stderr = stderr[match.end():]
    if re.search(rb"(?m)^dyld\[", stderr):
        raise ValueError("unexpected additional dyld output")
    return stderr


class ProtectedLaunch:
    def __init__(self, directory, manifest, binary):
        self.directory = directory
        self.manifest = manifest
        self.executable = directory / "record_p5_fixture"
        self.directory_id = self.check_directory()
        with self.executable.open("xb") as staged:
            staged.write(binary)
        self.executable.chmod(0o500)
        self.executable_id = self.check_executable()

    def check_directory(self):
        info = self.directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError("protected staging directory changed")
        return info.st_dev, info.st_ino

    def check_executable(self):
        descriptor = self.manifest["artifact"]
        binary, info = read_regular(self.executable, int(descriptor["byte_length"]))
        if (info.st_uid != os.geteuid() or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o500 or not matches(binary, descriptor)):
            raise ValueError("staged candidate identity or bytes changed")
        return info.st_dev, info.st_ino

    def check_staged(self):
        if self.check_directory() != self.directory_id or self.check_executable() != self.executable_id:
            raise ValueError("protected staging inode changed")

    def __call__(self, argv):
        if argv[0] != str(self.executable) or argv[1] != self.manifest["artifact"]["content_digest"]:
            raise ValueError("unreviewed candidate launch path or digest")
        self.check_staged()
        result = subprocess.run(
            argv, cwd=self.directory, env={**ENV, "DYLD_PRINT_LIBRARIES": "1"},
            stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False,
        )
        self.check_staged()
        result.stderr = check_images(result.stderr, self.executable, self.manifest)
        return result


def main(draft, acceptance_record):
    if not sys.flags.isolated or not sys.dont_write_bytecode or sys.flags.optimize:
        raise ValueError("run the protected verifier with Python -I -B and assertions enabled")
    manifest, provenance, binary, rule = reviewed_candidate()
    if draft:
        sys.stdout.buffer.write(acceptance_bytes(binary, rule, provenance))
        return
    approval = None
    if acceptance_record is not None:
        approval = load_approval(acceptance_record, trust_config_path(),
                                 acceptance_bytes(binary, rule, provenance), provenance)
    check_host(manifest)
    for directory in (Path("/"), STAGING.parent, STAGING):
        info = directory.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or (mode != 0o1777 if directory == STAGING else mode & 0o022)):
            raise ValueError(f"unprotected staging ancestor: {directory}")
        check_acl(directory)
    report = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="radishaxiom-p5-", dir=STAGING) as tmp:
        directory = Path(tmp)
        check_acl(directory)
        launch = ProtectedLaunch(directory, manifest, binary)
        check_acl(launch.executable)
        with contextlib.redirect_stdout(report):
            verify_receipts(launch.executable, SCHEMA, False, invoke=launch, approval=approval, scratch=directory)
    reviewed_candidate()
    check_host(manifest)
    if approval and read_trusted_pin(trust_config_path()) != approval[1]:
        raise ValueError("trusted acceptance configuration changed during rerun")
    status = "accepted" if approval else "not-accepted"
    print(f"protected P5 Darwin rerun: {status}")
    print(report.getvalue(), end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--draft", action="store_true", help="emit draft bytes without approving or running P5")
    mode.add_argument("--acceptance-record", type=Path, help="use the independently configured approval pin")
    args = parser.parse_args()
    try:
        main(args.draft, args.acceptance_record)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"P5 Darwin rerun blocked: {error}\n")
