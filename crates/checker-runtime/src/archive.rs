use std::fmt;

use crate::sha256::digest_hex;

const BLOCK_SIZE: usize = 512;
const NAME_SIZE: usize = 100;
const PREFIX_SIZE: usize = 155;

pub const CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER: [&str; 4] = [
    "checker-build-provenance-v0.1.jcs",
    "checker-payload-acceptance-v0.1.jcs",
    "checker-payload-retention-manifest-v0.1.jcs",
    "radishaxiom-independent-checker-go",
];

pub const CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER: [&str; 6] = [
    "checker-payload-candidate.tar",
    "checker-payload-distribution-acceptance-v0.1.jcs",
    "checker-payload-distribution-manifest-v0.1.jcs",
    "licenses/go/LICENSE",
    "licenses/go/PATENTS",
    "licenses/radishaxiom-checker/LICENSE",
];

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ArchiveValidationError {
    code: &'static str,
    detail: Box<str>,
}

impl ArchiveValidationError {
    fn new(code: &'static str, detail: impl Into<Box<str>>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    pub fn code(&self) -> &'static str {
        self.code
    }

    pub fn detail(&self) -> &str {
        &self.detail
    }
}

impl fmt::Display for ArchiveValidationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.detail.is_empty() {
            formatter.write_str(self.code)
        } else {
            write!(formatter, "{}: {}", self.code, self.detail)
        }
    }
}

impl std::error::Error for ArchiveValidationError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ArchiveMemberExpectation {
    name: Box<str>,
    mode: u32,
    byte_length: u64,
    raw_sha256: Box<str>,
}

impl ArchiveMemberExpectation {
    pub fn new(
        name: impl Into<Box<str>>,
        mode: u32,
        byte_length: u64,
        raw_sha256: impl Into<Box<str>>,
    ) -> Result<Self, ArchiveValidationError> {
        let expectation = Self {
            name: name.into(),
            mode,
            byte_length,
            raw_sha256: raw_sha256.into(),
        };
        expectation.validate()?;
        Ok(expectation)
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn mode(&self) -> u32 {
        self.mode
    }

    pub fn byte_length(&self) -> u64 {
        self.byte_length
    }

    pub fn raw_sha256(&self) -> &str {
        &self.raw_sha256
    }

    fn validate(&self) -> Result<(), ArchiveValidationError> {
        validate_member_name(&self.name)?;
        if self.mode != 0o644 && self.mode != 0o755 {
            return Err(ArchiveValidationError::new(
                "unknown-member-or-mode",
                self.name.clone(),
            ));
        }
        if !valid_sha256(&self.raw_sha256) {
            return Err(ArchiveValidationError::new(
                "invalid-member-digest",
                self.name.clone(),
            ));
        }
        canonical_name_fields(&self.name)?;
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ValidatedArchiveMember<'archive> {
    name: Box<str>,
    mode: u32,
    data: &'archive [u8],
    raw_sha256: Box<str>,
}

impl<'archive> ValidatedArchiveMember<'archive> {
    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn mode(&self) -> u32 {
        self.mode
    }

    pub fn data(&self) -> &'archive [u8] {
        self.data
    }

    pub fn byte_length(&self) -> u64 {
        u64::try_from(self.data.len()).expect("usize fits in u64")
    }

    pub fn raw_sha256(&self) -> &str {
        &self.raw_sha256
    }
}

pub fn validate_ustar<'archive>(
    data: &'archive [u8],
    expected_members: &[ArchiveMemberExpectation],
) -> Result<Vec<ValidatedArchiveMember<'archive>>, ArchiveValidationError> {
    if !data.len().is_multiple_of(BLOCK_SIZE) {
        return Err(ArchiveValidationError::new("truncated-archive", ""));
    }
    for expectation in expected_members {
        expectation.validate()?;
    }
    for (index, expectation) in expected_members.iter().enumerate() {
        if expected_members[..index]
            .iter()
            .any(|previous| previous.name == expectation.name)
        {
            return Err(ArchiveValidationError::new(
                "duplicate-expected-member",
                expectation.name.clone(),
            ));
        }
    }

    let mut members = Vec::with_capacity(expected_members.len());
    let mut offset = 0_usize;
    let found_trailer = loop {
        let Some(header_end) = offset.checked_add(BLOCK_SIZE) else {
            return Err(ArchiveValidationError::new("truncated-header", ""));
        };
        if header_end > data.len() {
            break false;
        }
        let header: &[u8; BLOCK_SIZE] = data[offset..header_end]
            .try_into()
            .expect("header slice has exact block length");
        if header.iter().all(|byte| *byte == 0) {
            let trailer_end = offset
                .checked_add(2 * BLOCK_SIZE)
                .ok_or_else(|| ArchiveValidationError::new("truncated-archive", ""))?;
            if trailer_end != data.len() || data[offset..trailer_end].iter().any(|byte| *byte != 0)
            {
                return Err(ArchiveValidationError::new("extra-or-trailing-bytes", ""));
            }
            break true;
        }

        let (name, mode, size) = parse_header(header)?;
        if members
            .iter()
            .any(|previous: &ValidatedArchiveMember<'_>| previous.name == name)
        {
            return Err(ArchiveValidationError::new("duplicate-member", name));
        }
        let Some(expectation) = expected_members.get(members.len()) else {
            return Err(ArchiveValidationError::new("unknown-member-or-order", name));
        };
        if name != expectation.name {
            return Err(ArchiveValidationError::new("unknown-member-or-order", name));
        }
        if mode != expectation.mode {
            return Err(ArchiveValidationError::new("unknown-member-or-mode", name));
        }
        if size != expectation.byte_length {
            return Err(ArchiveValidationError::new("member-length-mismatch", name));
        }
        let member_length = usize::try_from(size)
            .map_err(|_| ArchiveValidationError::new("truncated-member", name.clone()))?;
        let data_start = header_end;
        let data_end = data_start
            .checked_add(member_length)
            .ok_or_else(|| ArchiveValidationError::new("truncated-member", name.clone()))?;
        let padded_length = member_length
            .checked_add(BLOCK_SIZE - 1)
            .map(|length| length / BLOCK_SIZE * BLOCK_SIZE)
            .ok_or_else(|| ArchiveValidationError::new("truncated-member", name.clone()))?;
        let padded_end = data_start
            .checked_add(padded_length)
            .ok_or_else(|| ArchiveValidationError::new("truncated-member", name.clone()))?;
        if padded_end > data.len() {
            return Err(ArchiveValidationError::new("truncated-member", name));
        }
        if data[data_end..padded_end].iter().any(|byte| *byte != 0) {
            return Err(ArchiveValidationError::new("nonzero-member-padding", name));
        }
        let member_data = &data[data_start..data_end];
        let raw_sha256 = format!("sha256:{}", digest_hex(member_data));
        if raw_sha256 != expectation.raw_sha256.as_ref() {
            return Err(ArchiveValidationError::new("member-digest-mismatch", name));
        }
        members.push(ValidatedArchiveMember {
            name,
            mode,
            data: member_data,
            raw_sha256: raw_sha256.into(),
        });
        offset = padded_end;
    };

    if !found_trailer {
        return Err(ArchiveValidationError::new("missing-ustar-trailer", ""));
    }

    if members.len() != expected_members.len() {
        return Err(ArchiveValidationError::new("unknown-member-or-order", ""));
    }
    Ok(members)
}

fn parse_header(header: &[u8; BLOCK_SIZE]) -> Result<(Box<str>, u32, u64), ArchiveValidationError> {
    if header[257..263] != *b"ustar\0" || header[263..265] != *b"00" {
        return Err(ArchiveValidationError::new("non-ustar-header", ""));
    }
    let expected_checksum = parse_octal(&header[148..156], "checksum")?;
    let actual_checksum = header[..148]
        .iter()
        .chain([b' '; 8].iter())
        .chain(header[156..].iter())
        .map(|byte| u64::from(*byte))
        .sum::<u64>();
    if actual_checksum != expected_checksum {
        return Err(ArchiveValidationError::new("header-checksum-mismatch", ""));
    }

    match header[156] {
        b'1' => return Err(ArchiveValidationError::new("hard-link", "")),
        b'2' => return Err(ArchiveValidationError::new("symbolic-link", "")),
        b'3' | b'4' => return Err(ArchiveValidationError::new("device", "")),
        b'6' => return Err(ArchiveValidationError::new("fifo", "")),
        b'x' | b'g' => return Err(ArchiveValidationError::new("pax-or-xattr", "")),
        b'0' => {}
        _ => {
            return Err(ArchiveValidationError::new("unknown-member-or-mode", ""));
        }
    }
    if header[157..257].iter().any(|byte| *byte != 0) {
        return Err(ArchiveValidationError::new("hard-link", ""));
    }

    let suffix = ascii_field(&header[..100], "name")?;
    let prefix = ascii_field(&header[345..500], "prefix")?;
    let name: Box<str> = if prefix.is_empty() {
        suffix.into()
    } else {
        format!("{prefix}/{suffix}").into()
    };
    validate_member_name(&name)?;
    let mode = u32::try_from(parse_octal(&header[100..108], "mode")?)
        .map_err(|_| ArchiveValidationError::new("noncanonical-header", "mode"))?;
    let size = parse_octal(&header[124..136], "size")?;

    let canonical = canonical_header(&name, mode, size)?;
    if header != &canonical {
        return Err(ArchiveValidationError::new("noncanonical-header", name));
    }
    Ok((name, mode, size))
}

fn canonical_header(
    name: &str,
    mode: u32,
    size: u64,
) -> Result<[u8; BLOCK_SIZE], ArchiveValidationError> {
    let (prefix, suffix) = canonical_name_fields(name)?;
    let mut header = [0_u8; BLOCK_SIZE];
    write_string(&mut header[..100], suffix, "name")?;
    write_octal(&mut header[100..108], u64::from(mode), "mode")?;
    write_octal(&mut header[108..116], 0, "uid")?;
    write_octal(&mut header[116..124], 0, "gid")?;
    write_octal(&mut header[124..136], size, "size")?;
    write_octal(&mut header[136..148], 0, "mtime")?;
    header[148..156].fill(b' ');
    header[156] = b'0';
    header[257..263].copy_from_slice(b"ustar\0");
    header[263..265].copy_from_slice(b"00");
    write_octal(&mut header[329..337], 0, "device-major")?;
    write_octal(&mut header[337..345], 0, "device-minor")?;
    write_string(&mut header[345..500], prefix, "prefix")?;
    let checksum = header.iter().map(|byte| u64::from(*byte)).sum();
    write_checksum(&mut header[148..156], checksum)?;
    Ok(header)
}

fn canonical_name_fields(name: &str) -> Result<(&str, &str), ArchiveValidationError> {
    if name.len() <= NAME_SIZE {
        return Ok(("", name));
    }
    let split_limit = name.len().min(PREFIX_SIZE + 1);
    let Some(index) = name[..split_limit].rfind('/') else {
        return Err(ArchiveValidationError::new("nonportable-member-name", name));
    };
    let prefix = &name[..index];
    let suffix = &name[index + 1..];
    if prefix.is_empty()
        || prefix.len() > PREFIX_SIZE
        || suffix.is_empty()
        || suffix.len() > NAME_SIZE
    {
        return Err(ArchiveValidationError::new("nonportable-member-name", name));
    }
    Ok((prefix, suffix))
}

fn ascii_field<'field>(
    field: &'field [u8],
    label: &'static str,
) -> Result<&'field str, ArchiveValidationError> {
    let end = field
        .iter()
        .position(|byte| *byte == 0)
        .unwrap_or(field.len());
    if field[end..].iter().any(|byte| *byte != 0) {
        return Err(ArchiveValidationError::new("noncanonical-header", label));
    }
    std::str::from_utf8(&field[..end])
        .ok()
        .filter(|value| value.is_ascii())
        .ok_or_else(|| ArchiveValidationError::new("nonportable-member-name", label))
}

fn parse_octal(field: &[u8], label: &'static str) -> Result<u64, ArchiveValidationError> {
    if field.first().is_some_and(|byte| byte & 0x80 != 0) {
        return Err(ArchiveValidationError::new("noncanonical-header", label));
    }
    let trimmed_end = field
        .iter()
        .rposition(|byte| *byte != 0 && *byte != b' ')
        .map_or(0, |index| index + 1);
    let digits = field[..trimmed_end]
        .iter()
        .skip_while(|byte| **byte == b' ')
        .copied();
    let mut value = 0_u64;
    let mut found_digit = false;
    for byte in digits {
        if !(b'0'..=b'7').contains(&byte) {
            return Err(ArchiveValidationError::new("noncanonical-header", label));
        }
        found_digit = true;
        value = value
            .checked_mul(8)
            .and_then(|number| number.checked_add(u64::from(byte - b'0')))
            .ok_or_else(|| ArchiveValidationError::new("noncanonical-header", label))?;
    }
    if !found_digit {
        return Err(ArchiveValidationError::new("noncanonical-header", label));
    }
    Ok(value)
}

fn write_string(
    field: &mut [u8],
    value: &str,
    label: &'static str,
) -> Result<(), ArchiveValidationError> {
    if value.len() > field.len() || !value.is_ascii() {
        return Err(ArchiveValidationError::new("noncanonical-header", label));
    }
    field.fill(0);
    field[..value.len()].copy_from_slice(value.as_bytes());
    Ok(())
}

fn write_octal(
    field: &mut [u8],
    value: u64,
    label: &'static str,
) -> Result<(), ArchiveValidationError> {
    let digits = format!("{value:o}");
    if digits.len() >= field.len() {
        return Err(ArchiveValidationError::new("noncanonical-header", label));
    }
    field.fill(b'0');
    let field_end = field.len() - 1;
    let start = field_end - digits.len();
    field[start..field_end].copy_from_slice(digits.as_bytes());
    field[field_end] = 0;
    Ok(())
}

fn write_checksum(field: &mut [u8], value: u64) -> Result<(), ArchiveValidationError> {
    let digits = format!("{value:o}");
    if field.len() != 8 || digits.len() > 6 {
        return Err(ArchiveValidationError::new(
            "noncanonical-header",
            "checksum",
        ));
    }
    field.fill(b'0');
    let start = 6 - digits.len();
    field[start..6].copy_from_slice(digits.as_bytes());
    field[6] = 0;
    field[7] = b' ';
    Ok(())
}

fn validate_member_name(name: &str) -> Result<(), ArchiveValidationError> {
    if name.is_empty() || name.starts_with('/') || name.starts_with('\\') {
        return Err(ArchiveValidationError::new("absolute-path", name));
    }
    for component in name.split('/') {
        if component.is_empty() || component == "." || component == ".." {
            return Err(ArchiveValidationError::new(
                "dot-dot-or-empty-component",
                name,
            ));
        }
        if !component
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
        {
            return Err(ArchiveValidationError::new("nonportable-member-name", name));
        }
    }
    Ok(())
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

#[cfg(test)]
mod tests {
    use super::{
        ArchiveMemberExpectation, BLOCK_SIZE, CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER,
        CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER, canonical_header, digest_hex, validate_ustar,
    };

    #[derive(Clone)]
    struct Entry<'data> {
        name: &'data str,
        data: &'data [u8],
        mode: u32,
        typeflag: u8,
    }

    fn archive(entries: &[Entry<'_>]) -> Vec<u8> {
        let mut output = Vec::new();
        for entry in entries {
            let mut header = canonical_header(
                entry.name,
                entry.mode,
                u64::try_from(entry.data.len()).unwrap(),
            )
            .unwrap();
            header[156] = entry.typeflag;
            refresh_checksum(&mut header);
            output.extend_from_slice(&header);
            output.extend_from_slice(entry.data);
            output.resize(output.len().next_multiple_of(BLOCK_SIZE), 0);
        }
        output.extend_from_slice(&[0_u8; 2 * BLOCK_SIZE]);
        output
    }

    fn refresh_checksum(header: &mut [u8; BLOCK_SIZE]) {
        header[148..156].fill(b' ');
        let checksum: u64 = header.iter().map(|byte| u64::from(*byte)).sum();
        let encoded = format!("{checksum:06o}\0 ");
        header[148..156].copy_from_slice(encoded.as_bytes());
    }

    fn expectation(entry: &Entry<'_>) -> ArchiveMemberExpectation {
        ArchiveMemberExpectation::new(
            entry.name,
            entry.mode,
            u64::try_from(entry.data.len()).unwrap(),
            format!("sha256:{}", digest_hex(entry.data)),
        )
        .unwrap()
    }

    fn error_code(archive: &[u8], expected: &[ArchiveMemberExpectation]) -> &'static str {
        validate_ustar(archive, expected).unwrap_err().code()
    }

    #[test]
    fn python_oracle_outer_and_inner_inventories_match() {
        let inner_entries = [
            Entry {
                name: CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[0],
                data: b"provenance",
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[1],
                data: b"acceptance",
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[2],
                data: b"retention",
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[3],
                data: b"binary",
                mode: 0o755,
                typeflag: b'0',
            },
        ];
        let inner = archive(&inner_entries);
        assert_eq!(inner.len(), 5_120);
        assert_eq!(
            digest_hex(&inner),
            "d8c51c18196507d868816a2456b24a9fb756286e87f6aa124bccc806173782c2"
        );
        let inner_expected: Vec<_> = inner_entries.iter().map(expectation).collect();
        let inner_members = validate_ustar(&inner, &inner_expected).unwrap();
        assert_eq!(
            inner_members
                .iter()
                .map(|member| member.name())
                .collect::<Vec<_>>(),
            CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER
        );

        let outer_entries = [
            Entry {
                name: CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[0],
                data: &inner,
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[1],
                data: b"distribution-acceptance",
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[2],
                data: b"distribution-manifest",
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[3],
                data: b"go-license",
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[4],
                data: b"go-patents",
                mode: 0o644,
                typeflag: b'0',
            },
            Entry {
                name: CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[5],
                data: b"checker-license",
                mode: 0o644,
                typeflag: b'0',
            },
        ];
        let outer = archive(&outer_entries);
        assert_eq!(outer.len(), 11_776);
        assert_eq!(
            digest_hex(&outer),
            "d5ce0e3a00d7a66366c152257d54f71957778c39d08315b7ca65cd22dd8dd424"
        );
        let outer_expected: Vec<_> = outer_entries.iter().map(expectation).collect();
        let outer_members = validate_ustar(&outer, &outer_expected).unwrap();
        assert_eq!(outer_members[0].data(), inner);
        validate_ustar(outer_members[0].data(), &inner_expected).unwrap();
    }

    #[test]
    fn forbidden_paths_and_member_types_fail_closed() {
        let cases = [
            ("/absolute", b'0', "absolute-path"),
            ("../escape", b'0', "dot-dot-or-empty-component"),
            ("payload//empty", b'0', "dot-dot-or-empty-component"),
            ("payload/link", b'1', "hard-link"),
            ("payload/link", b'2', "symbolic-link"),
            ("payload/device", b'3', "device"),
            ("payload/device", b'4', "device"),
            ("payload/fifo", b'6', "fifo"),
            ("payload/pax", b'x', "pax-or-xattr"),
            ("payload/xattr", b'g', "pax-or-xattr"),
            ("payload/null-type", 0, "unknown-member-or-mode"),
            ("payload/socket", b's', "unknown-member-or-mode"),
        ];
        for (name, typeflag, expected_code) in cases {
            let entry = Entry {
                name,
                data: b"x",
                mode: 0o644,
                typeflag,
            };
            let raw = archive(std::slice::from_ref(&entry));
            let expected = ArchiveMemberExpectation::new(
                "safe",
                0o644,
                1,
                format!("sha256:{}", digest_hex(b"x")),
            )
            .unwrap();
            assert_eq!(error_code(&raw, &[expected]), expected_code);
        }
    }

    #[test]
    fn canonical_header_profile_is_enforced() {
        let entry = Entry {
            name: "payload/checker",
            data: b"binary",
            mode: 0o755,
            typeflag: b'0',
        };
        let expected = [expectation(&entry)];

        let mut checksum_mismatch = archive(std::slice::from_ref(&entry));
        checksum_mismatch[0] ^= 1;
        assert_eq!(
            error_code(&checksum_mismatch, &expected),
            "header-checksum-mismatch"
        );

        for range in [
            108..116,
            116..124,
            136..148,
            265..297,
            297..329,
            329..337,
            337..345,
            500..512,
        ] {
            let mut changed = archive(std::slice::from_ref(&entry));
            changed[range.start] = b'1';
            refresh_checksum((&mut changed[..BLOCK_SIZE]).try_into().unwrap());
            assert_eq!(error_code(&changed, &expected), "noncanonical-header");
        }

        let mut base256_size = archive(std::slice::from_ref(&entry));
        base256_size[124] = 0x80;
        refresh_checksum((&mut base256_size[..BLOCK_SIZE]).try_into().unwrap());
        assert_eq!(error_code(&base256_size, &expected), "noncanonical-header");
    }

    #[test]
    fn padding_trailer_inventory_and_identity_failures_are_distinct() {
        let first = Entry {
            name: "a",
            data: b"one",
            mode: 0o644,
            typeflag: b'0',
        };
        let second = Entry {
            name: "b",
            data: b"two",
            mode: 0o755,
            typeflag: b'0',
        };
        let expected = [expectation(&first), expectation(&second)];

        let mut nonzero_padding = archive(&[first.clone(), second.clone()]);
        nonzero_padding[BLOCK_SIZE + first.data.len()] = 1;
        assert_eq!(
            error_code(&nonzero_padding, &expected),
            "nonzero-member-padding"
        );

        let mut extra_trailer = archive(&[first.clone(), second.clone()]);
        extra_trailer.extend_from_slice(&[0_u8; BLOCK_SIZE]);
        assert_eq!(
            error_code(&extra_trailer, &expected),
            "extra-or-trailing-bytes"
        );

        let mut missing_trailer = archive(&[first.clone(), second.clone()]);
        missing_trailer.truncate(missing_trailer.len() - 2 * BLOCK_SIZE);
        assert_eq!(
            error_code(&missing_trailer, &expected),
            "missing-ustar-trailer"
        );

        let mut truncated_archive = archive(&[first.clone(), second.clone()]);
        truncated_archive.pop();
        assert_eq!(
            error_code(&truncated_archive, &expected),
            "truncated-archive"
        );

        let mut truncated_member = archive(std::slice::from_ref(&first));
        truncated_member[..BLOCK_SIZE]
            .copy_from_slice(&canonical_header(first.name, first.mode, 2_048).unwrap());
        let oversized = [ArchiveMemberExpectation::new(
            first.name,
            first.mode,
            2_048,
            "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        )
        .unwrap()];
        assert_eq!(
            error_code(&truncated_member, &oversized),
            "truncated-member"
        );

        let reversed = archive(&[second.clone(), first.clone()]);
        assert_eq!(error_code(&reversed, &expected), "unknown-member-or-order");

        let duplicate = archive(&[first.clone(), first.clone()]);
        assert_eq!(error_code(&duplicate, &expected), "duplicate-member");

        let wrong_mode = archive(&[
            Entry {
                mode: 0o755,
                ..first.clone()
            },
            second.clone(),
        ]);
        assert_eq!(error_code(&wrong_mode, &expected), "unknown-member-or-mode");

        let wrong_length = [
            ArchiveMemberExpectation::new(
                first.name,
                first.mode,
                4,
                format!("sha256:{}", digest_hex(first.data)),
            )
            .unwrap(),
            expectation(&second),
        ];
        assert_eq!(
            error_code(&archive(&[first.clone(), second.clone()]), &wrong_length),
            "member-length-mismatch"
        );

        let wrong_digest = [
            ArchiveMemberExpectation::new(
                first.name,
                first.mode,
                3,
                "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            )
            .unwrap(),
            expectation(&second),
        ];
        assert_eq!(
            error_code(&archive(&[first, second]), &wrong_digest),
            "member-digest-mismatch"
        );
    }

    #[test]
    fn expectations_reject_invalid_identity_and_duplicates() {
        assert_eq!(
            ArchiveMemberExpectation::new(
                "safe",
                0o600,
                0,
                "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            )
            .unwrap_err()
            .code(),
            "unknown-member-or-mode"
        );
        assert_eq!(
            ArchiveMemberExpectation::new("safe", 0o644, 0, "sha256:ABC")
                .unwrap_err()
                .code(),
            "invalid-member-digest"
        );
        assert_eq!(
            ArchiveMemberExpectation::new(
                "../escape",
                0o644,
                0,
                "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            )
            .unwrap_err()
            .code(),
            "dot-dot-or-empty-component"
        );
        let duplicate = ArchiveMemberExpectation::new(
            "safe",
            0o644,
            0,
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        .unwrap();
        assert_eq!(
            validate_ustar(&[0_u8; 2 * BLOCK_SIZE], &[duplicate.clone(), duplicate])
                .unwrap_err()
                .code(),
            "duplicate-expected-member"
        );
    }
}
