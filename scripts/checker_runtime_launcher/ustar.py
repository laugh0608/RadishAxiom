"""Strict, extraction-free USTAR inventory validation for launcher fixtures."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


BLOCK_SIZE = 512
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PORTABLE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")


class ArchiveValidationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ArchiveMemberExpectation:
    name: str
    mode: int
    byte_length: int
    raw_sha256: str

    def __post_init__(self) -> None:
        _validate_member_name(self.name)
        if self.mode not in {0o644, 0o755}:
            raise ArchiveValidationError("unknown-member-or-mode", self.name)
        if self.byte_length < 0:
            raise ArchiveValidationError("invalid-member-length", self.name)
        if not SHA256_PATTERN.fullmatch(self.raw_sha256):
            raise ArchiveValidationError("invalid-member-digest", self.name)


@dataclass(frozen=True, slots=True)
class ValidatedArchiveMember:
    name: str
    mode: int
    data: bytes
    raw_sha256: str


def _raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _nul_terminated(raw: bytes, label: str) -> bytes:
    value, separator, trailing = raw.partition(b"\0")
    if separator and any(trailing):
        raise ArchiveValidationError("noncanonical-header", label)
    return value if separator else raw


def _ascii_field(raw: bytes, label: str) -> str:
    value = _nul_terminated(raw, label)
    try:
        return value.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ArchiveValidationError("nonportable-member-name", label) from exc


def _octal_field(raw: bytes, label: str) -> int:
    if raw and raw[0] & 0x80:
        raise ArchiveValidationError("noncanonical-header", label)
    stripped = raw.rstrip(b"\0 ").lstrip(b" ")
    if not stripped or any(byte not in b"01234567" for byte in stripped):
        raise ArchiveValidationError("noncanonical-header", label)
    return int(stripped, 8)


def _validate_member_name(name: str) -> None:
    if not name or name.startswith(("/", "\\")):
        raise ArchiveValidationError("absolute-path", name)
    components = name.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise ArchiveValidationError("dot-dot-or-empty-component", name)
    if any(not PORTABLE_COMPONENT.fullmatch(component) for component in components):
        raise ArchiveValidationError("nonportable-member-name", name)


def _header_checksum(header: bytes) -> int:
    return sum(header[:148]) + (8 * ord(" ")) + sum(header[156:])


def _parse_header(header: bytes) -> tuple[str, int, int]:
    if len(header) != BLOCK_SIZE:
        raise ArchiveValidationError("truncated-header")
    if header[257:263] != b"ustar\0" or header[263:265] != b"00":
        raise ArchiveValidationError("non-ustar-header")
    expected_checksum = _octal_field(header[148:156], "checksum")
    if _header_checksum(header) != expected_checksum:
        raise ArchiveValidationError("header-checksum-mismatch")

    typeflag = header[156:157]
    if typeflag in {b"1", b"2"}:
        code = "hard-link" if typeflag == b"1" else "symbolic-link"
        raise ArchiveValidationError(code)
    if typeflag in {b"3", b"4"}:
        raise ArchiveValidationError("device")
    if typeflag == b"6":
        raise ArchiveValidationError("fifo")
    if typeflag in {b"x", b"g"}:
        raise ArchiveValidationError("pax-or-xattr")
    if typeflag not in {b"0", b"\0"}:
        raise ArchiveValidationError("unknown-member-or-mode")
    if any(header[157:257]):
        raise ArchiveValidationError("hard-link")

    name = _ascii_field(header[:100], "name")
    prefix = _ascii_field(header[345:500], "prefix")
    if prefix:
        name = f"{prefix}/{name}"
    _validate_member_name(name)
    mode = _octal_field(header[100:108], "mode")
    size = _octal_field(header[124:136], "size")
    return name, mode, size


def validate_ustar(
    data: bytes,
    expected_members: tuple[ArchiveMemberExpectation, ...],
) -> tuple[ValidatedArchiveMember, ...]:
    """Validate an exact closed USTAR inventory without extracting any member."""

    if len(data) % BLOCK_SIZE != 0:
        raise ArchiveValidationError("truncated-archive")
    if len({item.name for item in expected_members}) != len(expected_members):
        raise ArchiveValidationError("duplicate-expected-member")

    members: list[ValidatedArchiveMember] = []
    offset = 0
    while offset + BLOCK_SIZE <= len(data):
        header = data[offset : offset + BLOCK_SIZE]
        if header == bytes(BLOCK_SIZE):
            trailer = data[offset:]
            if trailer != bytes(2 * BLOCK_SIZE):
                raise ArchiveValidationError("extra-or-trailing-bytes")
            break
        name, mode, size = _parse_header(header)
        data_start = offset + BLOCK_SIZE
        data_end = data_start + size
        padded_end = data_start + ((size + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
        if padded_end > len(data):
            raise ArchiveValidationError("truncated-member", name)
        member_data = data[data_start:data_end]
        if any(data[data_end:padded_end]):
            raise ArchiveValidationError("nonzero-member-padding", name)
        members.append(
            ValidatedArchiveMember(
                name=name,
                mode=mode,
                data=member_data,
                raw_sha256=_raw_digest(member_data),
            )
        )
        offset = padded_end
    else:
        raise ArchiveValidationError("missing-ustar-trailer")

    actual_names = [item.name for item in members]
    expected_names = [item.name for item in expected_members]
    if len(actual_names) != len(set(actual_names)):
        raise ArchiveValidationError("duplicate-member")
    if actual_names != expected_names:
        raise ArchiveValidationError("unknown-member-or-order")
    for actual, expected in zip(members, expected_members, strict=True):
        if actual.mode != expected.mode:
            raise ArchiveValidationError("unknown-member-or-mode", actual.name)
        if len(actual.data) != expected.byte_length:
            raise ArchiveValidationError("member-length-mismatch", actual.name)
        if actual.raw_sha256 != expected.raw_sha256:
            raise ArchiveValidationError("member-digest-mismatch", actual.name)
    return tuple(members)
