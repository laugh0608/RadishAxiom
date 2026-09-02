use crate::archive::{
    ArchiveMemberExpectation, CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER,
    CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER, ValidatedArchiveMember, validate_ustar,
};
use crate::canonical::{
    DocumentError, ShapeSpec, Value, as_array, as_object, member, parse, parse_decimal,
    string_member, validate_digest, validate_shape,
};
use crate::registration::{ArtifactIdentity, RegistrationRecord};
use crate::selection::NativeTarget;

pub const MAX_CHECKER_RUNTIME_MANIFEST_BYTES: usize = 64 * 1024;

const CANDIDATE_FORMAT: &str = "radishaxiom-checker-payload-retention-manifest";
const DISTRIBUTION_FORMAT: &str = "radishaxiom-checker-runtime-distribution-manifest";
const FORMAT_VERSION: &str = "0.1";
const IMPLEMENTATION: &str = "radishaxiom-independent-checker-go";
const TOOLCHAIN: &str = "go1.26.7";

const CANDIDATE_MANIFEST_NAME: &str = "checker-payload-retention-manifest-v0.1.jcs";
const DISTRIBUTION_MANIFEST_NAME: &str = "checker-payload-distribution-manifest-v0.1.jcs";

const CANDIDATE_OBJECT_FIELDS: &[(&str, &str)] = &[
    ("$", "contents,format,format_version,identity,packaging"),
    ("$.contents[]", "byte_length,mode,path,raw_sha256,role"),
    (
        "$.identity",
        "implementation,source,target,toolchain,version",
    ),
    ("$.identity.target", "executable_format,goarch,goarm64,goos"),
    ("$.packaging", "archive_format,header_profile,member_order"),
    (
        "$.packaging.header_profile",
        "gid,gname,mtime,type,uid,uname",
    ),
];

const DISTRIBUTION_OBJECT_FIELDS: &[(&str, &str)] = &[
    ("$", "contents,format,format_version,identity,packaging"),
    ("$.contents[]", "byte_length,mode,path,raw_sha256,role"),
    (
        "$.identity",
        "implementation,source,target,toolchain,version",
    ),
    ("$.identity.target", "goarch,goarm64,goos,macho"),
    ("$.packaging", "archive_format,header_profile,member_order"),
    (
        "$.packaging.header_profile",
        "gid,gname,mtime,type,uid,uname",
    ),
];

const MANIFEST_ARRAY_PATHS: &[&str] = &["$.contents", "$.packaging.member_order"];

const CANDIDATE_SHAPE: ShapeSpec<'static> = ShapeSpec {
    object_fields: CANDIDATE_OBJECT_FIELDS,
    array_paths: MANIFEST_ARRAY_PATHS,
    bool_paths: &[],
};

const DISTRIBUTION_SHAPE: ShapeSpec<'static> = ShapeSpec {
    object_fields: DISTRIBUTION_OBJECT_FIELDS,
    array_paths: MANIFEST_ARRAY_PATHS,
    bool_paths: &[],
};

const CANDIDATE_CONTENT_ORDER: [(&str, &str, u32); 3] = [
    (
        "checker-build-provenance-v0.1.jcs",
        "build-provenance",
        0o644,
    ),
    (
        "checker-payload-acceptance-v0.1.jcs",
        "payload-acceptance",
        0o644,
    ),
    (
        "radishaxiom-independent-checker-go",
        "checker-artifact",
        0o755,
    ),
];

const DISTRIBUTION_CONTENT_ORDER: [(&str, &str, u32); 5] = [
    ("checker-payload-candidate.tar", "candidate-archive", 0o644),
    (
        "checker-payload-distribution-acceptance-v0.1.jcs",
        "distribution-acceptance",
        0o644,
    ),
    ("licenses/go/LICENSE", "go-license", 0o644),
    ("licenses/go/PATENTS", "go-patent-grant", 0o644),
    (
        "licenses/radishaxiom-checker/LICENSE",
        "checker-license",
        0o644,
    ),
];

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PayloadManifestIdentity {
    implementation: Box<str>,
    source: Box<str>,
    toolchain: Box<str>,
    version: Box<str>,
    target: NativeTarget,
}

impl PayloadManifestIdentity {
    pub fn implementation(&self) -> &str {
        &self.implementation
    }

    pub fn source(&self) -> &str {
        &self.source
    }

    pub fn toolchain(&self) -> &str {
        &self.toolchain
    }

    pub fn version(&self) -> &str {
        &self.version
    }

    pub fn target(&self) -> &NativeTarget {
        &self.target
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PayloadManifestContent {
    path: Box<str>,
    role: Box<str>,
    mode: u32,
    artifact: ArtifactIdentity,
}

impl PayloadManifestContent {
    pub fn path(&self) -> &str {
        &self.path
    }

    pub fn role(&self) -> &str {
        &self.role
    }

    pub fn mode(&self) -> u32 {
        self.mode
    }

    pub fn artifact(&self) -> &ArtifactIdentity {
        &self.artifact
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ValidatedPayloadManifest {
    format: &'static str,
    raw: ArtifactIdentity,
    identity: PayloadManifestIdentity,
    contents: Vec<PayloadManifestContent>,
}

impl ValidatedPayloadManifest {
    pub fn format(&self) -> &'static str {
        self.format
    }

    pub fn raw(&self) -> &ArtifactIdentity {
        &self.raw
    }

    pub fn identity(&self) -> &PayloadManifestIdentity {
        &self.identity
    }

    pub fn contents(&self) -> &[PayloadManifestContent] {
        &self.contents
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ValidatedPayloadManifests {
    candidate: ValidatedPayloadManifest,
    distribution: ValidatedPayloadManifest,
}

impl ValidatedPayloadManifests {
    pub fn candidate(&self) -> &ValidatedPayloadManifest {
        &self.candidate
    }

    pub fn distribution(&self) -> &ValidatedPayloadManifest {
        &self.distribution
    }
}

pub fn validate_payload_manifests(
    registration: &RegistrationRecord,
    distribution_members: &[ValidatedArchiveMember<'_>],
) -> Result<ValidatedPayloadManifests, DocumentError> {
    validate_member_order(
        distribution_members,
        &CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER,
        0o644,
        "$.distribution",
    )?;
    bind_archive(
        distribution_members,
        registration.distribution(),
        "$.distribution",
    )?;

    let distribution_manifest_member =
        required_member(distribution_members, DISTRIBUTION_MANIFEST_NAME)?;
    bind_artifact(
        distribution_manifest_member,
        registration.distribution_manifest(),
        "manifest-registration-binding",
        "$.distribution.manifest",
    )?;
    let distribution = parse_distribution_manifest(
        distribution_manifest_member,
        distribution_members,
        registration,
    )?;

    let candidate_archive_member = required_member(
        distribution_members,
        CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[0],
    )?;
    bind_artifact(
        candidate_archive_member,
        registration.candidate_archive(),
        "manifest-registration-binding",
        "$.distribution.contents[0]",
    )?;
    let candidate_expectations = candidate_expectations(registration)?;
    let candidate_members =
        validate_ustar(candidate_archive_member.data(), &candidate_expectations).map_err(
            |error| DocumentError::new(error.code(), format!("$.candidate: {}", error.detail())),
        )?;
    bind_archive(
        &candidate_members,
        registration.candidate_archive(),
        "$.candidate",
    )?;

    let candidate_manifest_member = required_member(&candidate_members, CANDIDATE_MANIFEST_NAME)?;
    bind_artifact(
        candidate_manifest_member,
        registration.candidate_manifest(),
        "manifest-registration-binding",
        "$.candidate.manifest",
    )?;
    let candidate =
        parse_candidate_manifest(candidate_manifest_member, &candidate_members, registration)?;

    if candidate.identity != distribution.identity {
        return Err(DocumentError::new(
            "manifest-cross-layer-identity",
            "$.identity",
        ));
    }

    Ok(ValidatedPayloadManifests {
        candidate,
        distribution,
    })
}

fn candidate_expectations(
    registration: &RegistrationRecord,
) -> Result<Vec<ArchiveMemberExpectation>, DocumentError> {
    let identities = [
        registration.build_provenance(),
        registration.payload_acceptance(),
        registration.candidate_manifest(),
        registration.artifact(),
    ];
    let modes = [0o644, 0o644, 0o644, 0o755];
    CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER
        .iter()
        .zip(modes)
        .zip(identities)
        .map(|((name, mode), identity)| {
            ArchiveMemberExpectation::new(
                *name,
                mode,
                identity.byte_length(),
                identity.raw_sha256(),
            )
            .map_err(|error| {
                DocumentError::new(error.code(), format!("$.candidate: {}", error.detail()))
            })
        })
        .collect()
}

fn parse_candidate_manifest(
    manifest_member: &ValidatedArchiveMember<'_>,
    members: &[ValidatedArchiveMember<'_>],
    registration: &RegistrationRecord,
) -> Result<ValidatedPayloadManifest, DocumentError> {
    let value = parse_manifest_document(manifest_member.data(), &CANDIDATE_SHAPE, "$.candidate")?;
    let root = as_object(&value, "$.candidate")?;
    expect_string(
        root,
        "format",
        CANDIDATE_FORMAT,
        "$.candidate",
        "manifest-format",
    )?;
    expect_string(
        root,
        "format_version",
        FORMAT_VERSION,
        "$.candidate",
        "manifest-version",
    )?;
    let identity = validate_identity(root, registration, false, "$.candidate.identity")?;
    validate_packaging(
        root,
        &CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER,
        "$.candidate.packaging",
    )?;
    let contents = validate_contents(
        root,
        members,
        &CANDIDATE_CONTENT_ORDER,
        "$.candidate.contents",
    )?;
    for (content, expected) in contents.iter().zip([
        registration.build_provenance(),
        registration.payload_acceptance(),
        registration.artifact(),
    ]) {
        if content.artifact != *expected {
            return Err(DocumentError::new(
                "manifest-registration-binding",
                format!("$.candidate.contents[{}]", content.path),
            ));
        }
    }
    Ok(ValidatedPayloadManifest {
        format: CANDIDATE_FORMAT,
        raw: artifact_from_member(manifest_member),
        identity,
        contents,
    })
}

fn parse_distribution_manifest(
    manifest_member: &ValidatedArchiveMember<'_>,
    members: &[ValidatedArchiveMember<'_>],
    registration: &RegistrationRecord,
) -> Result<ValidatedPayloadManifest, DocumentError> {
    let value = parse_manifest_document(
        manifest_member.data(),
        &DISTRIBUTION_SHAPE,
        "$.distribution",
    )?;
    let root = as_object(&value, "$.distribution")?;
    expect_string(
        root,
        "format",
        DISTRIBUTION_FORMAT,
        "$.distribution",
        "manifest-format",
    )?;
    expect_string(
        root,
        "format_version",
        FORMAT_VERSION,
        "$.distribution",
        "manifest-version",
    )?;
    let identity = validate_identity(root, registration, true, "$.distribution.identity")?;
    validate_packaging(
        root,
        &CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER,
        "$.distribution.packaging",
    )?;
    let contents = validate_contents(
        root,
        members,
        &DISTRIBUTION_CONTENT_ORDER,
        "$.distribution.contents",
    )?;
    for (content, expected) in contents[..2].iter().zip([
        registration.candidate_archive(),
        registration.distribution_acceptance(),
    ]) {
        if content.artifact != *expected {
            return Err(DocumentError::new(
                "manifest-registration-binding",
                format!("$.distribution.contents[{}]", content.path),
            ));
        }
    }
    Ok(ValidatedPayloadManifest {
        format: DISTRIBUTION_FORMAT,
        raw: artifact_from_member(manifest_member),
        identity,
        contents,
    })
}

fn parse_manifest_document(
    bytes: &[u8],
    shape: &ShapeSpec<'_>,
    path: &str,
) -> Result<Value, DocumentError> {
    if bytes.len() > MAX_CHECKER_RUNTIME_MANIFEST_BYTES {
        return Err(DocumentError::new("manifest-byte-limit", path));
    }
    let value = parse(bytes, true)?;
    validate_shape(&value, shape)?;
    Ok(value)
}

fn validate_identity(
    root: &[(String, Value)],
    registration: &RegistrationRecord,
    distribution: bool,
    path: &str,
) -> Result<PayloadManifestIdentity, DocumentError> {
    let identity = as_object(member(root, "identity", &parent_path(path))?, path)?;
    let implementation = string_member(identity, "implementation", path)?;
    let source = string_member(identity, "source", path)?;
    let toolchain = string_member(identity, "toolchain", path)?;
    let version = string_member(identity, "version", path)?;
    validate_digest(source, &format!("{path}.source"))?;
    validate_exact_version(version, &format!("{path}.version"))?;
    if implementation != IMPLEMENTATION
        || implementation != registration.checker().implementation()
        || source != registration.checker().source()
        || toolchain != TOOLCHAIN
        || toolchain != registration.checker().toolchain()
        || version != registration.checker().version()
    {
        return Err(DocumentError::new("manifest-identity-binding", path));
    }

    let target_path = format!("{path}.target");
    let target = as_object(member(identity, "target", path)?, &target_path)?;
    let registered = registration.target();
    let common_matches = string_member(target, "goos", &target_path)? == registered.goos()
        && string_member(target, "goarch", &target_path)? == registered.goarch()
        && string_member(target, "goarm64", &target_path)? == registered.variant();
    let format_matches = if distribution {
        string_member(target, "macho", &target_path)? == "64-bit-arm64-executable"
            && registered.executable_format() == "macho-64-arm64"
    } else {
        string_member(target, "executable_format", &target_path)? == registered.executable_format()
    };
    if !common_matches || !format_matches {
        return Err(DocumentError::new("manifest-target-binding", target_path));
    }

    Ok(PayloadManifestIdentity {
        implementation: implementation.into(),
        source: source.into(),
        toolchain: toolchain.into(),
        version: version.into(),
        target: registered.clone(),
    })
}

fn validate_packaging(
    root: &[(String, Value)],
    expected_order: &[&str],
    path: &str,
) -> Result<(), DocumentError> {
    let packaging = as_object(member(root, "packaging", &parent_path(path))?, path)?;
    if string_member(packaging, "archive_format", path)? != "ustar" {
        return Err(DocumentError::new("manifest-packaging", path));
    }
    let header_path = format!("{path}.header_profile");
    let header = as_object(member(packaging, "header_profile", path)?, &header_path)?;
    for (name, expected) in [
        ("gid", "0"),
        ("gname", ""),
        ("mtime", "1970-01-01T00:00:00Z"),
        ("type", "regular"),
        ("uid", "0"),
        ("uname", ""),
    ] {
        if string_member(header, name, &header_path)? != expected {
            return Err(DocumentError::new(
                "manifest-header-profile",
                format!("{header_path}.{name}"),
            ));
        }
    }
    let order_path = format!("{path}.member_order");
    let order = as_array(member(packaging, "member_order", path)?, &order_path)?;
    if order.len() != expected_order.len() {
        return Err(DocumentError::new("manifest-member-order", order_path));
    }
    for (index, expected) in expected_order.iter().enumerate() {
        if crate::canonical::as_string(&order[index], &format!("{order_path}[{index}]"))?
            != *expected
        {
            return Err(DocumentError::new(
                "manifest-member-order",
                format!("{order_path}[{index}]"),
            ));
        }
    }
    Ok(())
}

fn validate_contents(
    root: &[(String, Value)],
    members: &[ValidatedArchiveMember<'_>],
    expected: &[(&str, &str, u32)],
    path: &str,
) -> Result<Vec<PayloadManifestContent>, DocumentError> {
    let contents = as_array(member(root, "contents", &parent_path(path))?, path)?;
    if contents.len() != expected.len() {
        return Err(DocumentError::new("manifest-content-count", path));
    }
    let mut result = Vec::with_capacity(contents.len());
    for (index, (expected_path, expected_role, expected_mode)) in expected.iter().enumerate() {
        let record_path = format!("{path}[{index}]");
        let record = as_object(&contents[index], &record_path)?;
        let actual = required_member(members, expected_path)?;
        if string_member(record, "path", &record_path)? != *expected_path
            || string_member(record, "role", &record_path)? != *expected_role
        {
            return Err(DocumentError::new(
                "manifest-content-order-or-role",
                record_path,
            ));
        }
        if actual.mode() != *expected_mode
            || string_member(record, "mode", &record_path)? != format!("{expected_mode:04o}")
        {
            return Err(DocumentError::new("manifest-content-mode", record_path));
        }
        let declared_length = parse_decimal(
            string_member(record, "byte_length", &record_path)?,
            &format!("{record_path}.byte_length"),
        )?;
        let declared_digest = string_member(record, "raw_sha256", &record_path)?;
        validate_digest(declared_digest, &format!("{record_path}.raw_sha256"))?;
        if declared_length != actual.byte_length() || declared_digest != actual.raw_sha256() {
            return Err(DocumentError::new("manifest-content-identity", record_path));
        }
        result.push(PayloadManifestContent {
            path: (*expected_path).into(),
            role: (*expected_role).into(),
            mode: *expected_mode,
            artifact: artifact_from_member(actual),
        });
    }
    Ok(result)
}

fn validate_member_order(
    members: &[ValidatedArchiveMember<'_>],
    expected: &[&str],
    expected_mode: u32,
    path: &str,
) -> Result<(), DocumentError> {
    if members.len() != expected.len() {
        return Err(DocumentError::new("manifest-archive-inventory", path));
    }
    for (index, expected_name) in expected.iter().enumerate() {
        if members[index].name() != *expected_name || members[index].mode() != expected_mode {
            return Err(DocumentError::new(
                "manifest-archive-inventory",
                format!("{path}[{index}]"),
            ));
        }
    }
    Ok(())
}

fn bind_archive(
    members: &[ValidatedArchiveMember<'_>],
    expected: &ArtifactIdentity,
    path: &str,
) -> Result<(), DocumentError> {
    let Some(first) = members.first() else {
        return Err(DocumentError::new("manifest-archive-inventory", path));
    };
    if first.archive_byte_length() != expected.byte_length()
        || first.archive_raw_sha256() != expected.raw_sha256()
        || members.iter().any(|member| {
            member.archive_byte_length() != first.archive_byte_length()
                || member.archive_raw_sha256() != first.archive_raw_sha256()
        })
    {
        return Err(DocumentError::new("manifest-archive-binding", path));
    }
    Ok(())
}

fn required_member<'a, 'archive>(
    members: &'a [ValidatedArchiveMember<'archive>],
    name: &str,
) -> Result<&'a ValidatedArchiveMember<'archive>, DocumentError> {
    members
        .iter()
        .find(|member| member.name() == name)
        .ok_or_else(|| DocumentError::new("manifest-archive-inventory", name))
}

fn bind_artifact(
    actual: &ValidatedArchiveMember<'_>,
    expected: &ArtifactIdentity,
    code: &'static str,
    path: &str,
) -> Result<(), DocumentError> {
    if actual.byte_length() != expected.byte_length()
        || actual.raw_sha256() != expected.raw_sha256()
    {
        Err(DocumentError::new(code, path))
    } else {
        Ok(())
    }
}

fn artifact_from_member(member: &ValidatedArchiveMember<'_>) -> ArtifactIdentity {
    ArtifactIdentity::from_parts(member.byte_length(), member.raw_sha256())
}

fn expect_string(
    object: &[(String, Value)],
    name: &str,
    expected: &str,
    path: &str,
    code: &'static str,
) -> Result<(), DocumentError> {
    if string_member(object, name, path)? == expected {
        Ok(())
    } else {
        Err(DocumentError::new(code, format!("{path}.{name}")))
    }
}

fn validate_exact_version(value: &str, path: &str) -> Result<(), DocumentError> {
    let mut bytes = value.bytes();
    let first = bytes.next();
    if value == "latest"
        || value.len() > 64
        || !matches!(first, Some(byte) if byte.is_ascii_alphanumeric())
        || !bytes
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'+' | b'-'))
    {
        return Err(DocumentError::new("manifest-version-identity", path));
    }
    Ok(())
}

fn parent_path(path: &str) -> String {
    path.rsplit_once('.')
        .map_or_else(|| "$".to_owned(), |(parent, _)| parent.to_owned())
}

#[cfg(test)]
mod tests {
    use super::{
        CANDIDATE_FORMAT, DISTRIBUTION_FORMAT, MAX_CHECKER_RUNTIME_MANIFEST_BYTES,
        validate_payload_manifests,
    };
    use crate::archive::{
        ArchiveMemberExpectation, CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER,
        CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER, canonical_header, validate_ustar,
    };
    use crate::canonical::{Value, canonical_bytes, domain_digest, parse};
    use crate::registration::{REGISTRATION_DOMAIN, RegistrationRecord, parse_registration_record};
    use crate::sha256::digest_hex;

    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));
    const SOURCE: &str = "sha256:1111111111111111111111111111111111111111111111111111111111111111";
    const VERSION: &str = "0.1-test";

    type ManifestMutation = fn(Vec<u8>) -> Vec<u8>;

    struct SyntheticFixture {
        outer: Vec<u8>,
        outer_expectations: Vec<ArchiveMemberExpectation>,
        registration: Vec<u8>,
    }

    impl SyntheticFixture {
        fn record(&self) -> RegistrationRecord {
            parse_registration_record(&self.registration).unwrap()
        }

        fn outer_members(&self) -> Vec<crate::ValidatedArchiveMember<'_>> {
            validate_ustar(&self.outer, &self.outer_expectations).unwrap()
        }

        fn validate(&self) -> Result<super::ValidatedPayloadManifests, crate::DocumentError> {
            validate_payload_manifests(&self.record(), &self.outer_members())
        }

        fn mutate_registration(&mut self, path: &[&str], replacement: &str) {
            let mut value = parse(&self.registration, false).unwrap();
            set_nested_string(&mut value, path, replacement);
            refresh_record_digest(&mut value);
            self.registration = canonical_bytes(&value);
        }
    }

    #[test]
    fn synthetic_two_layer_manifests_close_inventory_and_identity() {
        let fixture = synthetic_fixture(identity, identity);
        let validated = fixture.validate().unwrap();

        assert_eq!(validated.candidate().format(), CANDIDATE_FORMAT);
        assert_eq!(validated.distribution().format(), DISTRIBUTION_FORMAT);
        assert_eq!(validated.candidate().identity().source(), SOURCE);
        assert_eq!(validated.candidate().identity().version(), VERSION);
        assert_eq!(validated.candidate().contents().len(), 3);
        assert_eq!(validated.distribution().contents().len(), 5);
        assert_eq!(validated.candidate().contents()[2].mode(), 0o755);
        assert_eq!(
            validated.distribution().contents()[3].role(),
            "go-patent-grant"
        );
    }

    #[test]
    fn ustar_success_does_not_substitute_for_business_manifest_validation() {
        let fixture = synthetic_fixture(add_unknown_candidate_member, identity);
        assert_eq!(fixture.outer_members().len(), 6);
        assert_eq!(fixture.validate().unwrap_err().code(), "unknown-member");

        let fixture = synthetic_fixture(identity, change_distribution_header_profile);
        assert_eq!(fixture.outer_members().len(), 6);
        assert_eq!(
            fixture.validate().unwrap_err().code(),
            "manifest-header-profile"
        );
    }

    #[test]
    fn manifest_identity_inventory_and_canonical_bytes_fail_closed() {
        for (candidate_mutation, distribution_mutation, code) in [
            (
                change_candidate_source as ManifestMutation,
                identity as ManifestMutation,
                "manifest-identity-binding",
            ),
            (
                change_candidate_content_digest,
                identity,
                "manifest-content-identity",
            ),
            (prefix_candidate_whitespace, identity, "noncanonical-json"),
            (
                identity,
                change_distribution_candidate_digest,
                "manifest-content-identity",
            ),
            (
                identity,
                swap_distribution_member_order,
                "manifest-member-order",
            ),
        ] {
            let fixture = synthetic_fixture(candidate_mutation, distribution_mutation);
            assert_eq!(fixture.validate().unwrap_err().code(), code);
        }
    }

    #[test]
    fn registration_bindings_cover_both_manifests_and_embedded_materials() {
        let mut distribution_archive = synthetic_fixture(identity, identity);
        distribution_archive.mutate_registration(
            &["durable_registration", "distribution_package", "raw_sha256"],
            "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        );
        assert_eq!(
            distribution_archive.validate().unwrap_err().code(),
            "manifest-archive-binding"
        );

        let mut distribution_acceptance = synthetic_fixture(identity, identity);
        distribution_acceptance.mutate_registration(
            &[
                "durable_registration",
                "distribution_package",
                "acceptance",
                "raw_sha256",
            ],
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        );
        assert_eq!(
            distribution_acceptance.validate().unwrap_err().code(),
            "manifest-registration-binding"
        );

        let mut candidate_artifact = synthetic_fixture(identity, identity);
        candidate_artifact.mutate_registration(
            &["artifact", "raw_sha256"],
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        );
        assert_eq!(
            candidate_artifact.validate().unwrap_err().code(),
            "member-digest-mismatch"
        );

        let mut distribution_manifest = synthetic_fixture(identity, identity);
        distribution_manifest.mutate_registration(
            &[
                "durable_registration",
                "distribution_package",
                "manifest",
                "raw_sha256",
            ],
            "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        );
        assert_eq!(
            distribution_manifest.validate().unwrap_err().code(),
            "manifest-registration-binding"
        );
    }

    #[test]
    fn candidate_manifest_has_a_preparse_byte_limit() {
        let fixture = synthetic_fixture(oversize_candidate_manifest, identity);
        assert_eq!(
            fixture.validate().unwrap_err().code(),
            "manifest-byte-limit"
        );
    }

    fn synthetic_fixture(
        candidate_mutation: ManifestMutation,
        distribution_mutation: ManifestMutation,
    ) -> SyntheticFixture {
        let provenance = b"synthetic provenance".to_vec();
        let payload_acceptance = b"synthetic payload acceptance".to_vec();
        let executable = b"synthetic checker executable".to_vec();
        let candidate_manifest = candidate_mutation(candidate_manifest(
            &provenance,
            &payload_acceptance,
            &executable,
        ));
        let candidate_entries = vec![
            (
                CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[0],
                0o644,
                provenance.clone(),
            ),
            (
                CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[1],
                0o644,
                payload_acceptance.clone(),
            ),
            (
                CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[2],
                0o644,
                candidate_manifest.clone(),
            ),
            (
                CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER[3],
                0o755,
                executable.clone(),
            ),
        ];
        let candidate_archive = make_ustar(&candidate_entries);

        let distribution_acceptance = b"synthetic distribution acceptance".to_vec();
        let go_license = b"synthetic Go license\n".to_vec();
        let go_patents = b"synthetic Go patents\n".to_vec();
        let checker_license = b"synthetic checker license\n".to_vec();
        let distribution_manifest = distribution_mutation(distribution_manifest(
            &candidate_archive,
            &distribution_acceptance,
            &go_license,
            &go_patents,
            &checker_license,
        ));
        let outer_entries = vec![
            (
                CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[0],
                0o644,
                candidate_archive.clone(),
            ),
            (
                CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[1],
                0o644,
                distribution_acceptance.clone(),
            ),
            (
                CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[2],
                0o644,
                distribution_manifest.clone(),
            ),
            (
                CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[3],
                0o644,
                go_license,
            ),
            (
                CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[4],
                0o644,
                go_patents,
            ),
            (
                CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER[5],
                0o644,
                checker_license,
            ),
        ];
        let outer = make_ustar(&outer_entries);
        let outer_expectations = expectations(&outer_entries);
        let registration = synthetic_registration(
            &provenance,
            &payload_acceptance,
            &executable,
            &candidate_manifest,
            &candidate_archive,
            &distribution_acceptance,
            &distribution_manifest,
            &outer,
        );
        SyntheticFixture {
            outer,
            outer_expectations,
            registration,
        }
    }

    fn candidate_manifest(provenance: &[u8], acceptance: &[u8], executable: &[u8]) -> Vec<u8> {
        format!(
            concat!(
                "{{\"contents\":[",
                "{{\"byte_length\":\"{}\",\"mode\":\"0644\",\"path\":\"checker-build-provenance-v0.1.jcs\",\"raw_sha256\":\"{}\",\"role\":\"build-provenance\"}},",
                "{{\"byte_length\":\"{}\",\"mode\":\"0644\",\"path\":\"checker-payload-acceptance-v0.1.jcs\",\"raw_sha256\":\"{}\",\"role\":\"payload-acceptance\"}},",
                "{{\"byte_length\":\"{}\",\"mode\":\"0755\",\"path\":\"radishaxiom-independent-checker-go\",\"raw_sha256\":\"{}\",\"role\":\"checker-artifact\"}}],",
                "\"format\":\"radishaxiom-checker-payload-retention-manifest\",\"format_version\":\"0.1\",",
                "\"identity\":{{\"implementation\":\"radishaxiom-independent-checker-go\",\"source\":\"{}\",",
                "\"target\":{{\"executable_format\":\"macho-64-arm64\",\"goarch\":\"arm64\",\"goarm64\":\"v8.0\",\"goos\":\"darwin\"}},",
                "\"toolchain\":\"go1.26.7\",\"version\":\"{}\"}},",
                "\"packaging\":{{\"archive_format\":\"ustar\",\"header_profile\":{{\"gid\":\"0\",\"gname\":\"\",\"mtime\":\"1970-01-01T00:00:00Z\",\"type\":\"regular\",\"uid\":\"0\",\"uname\":\"\"}},",
                "\"member_order\":[\"checker-build-provenance-v0.1.jcs\",\"checker-payload-acceptance-v0.1.jcs\",\"checker-payload-retention-manifest-v0.1.jcs\",\"radishaxiom-independent-checker-go\"]}}}}"
            ),
            provenance.len(),
            raw_digest(provenance),
            acceptance.len(),
            raw_digest(acceptance),
            executable.len(),
            raw_digest(executable),
            SOURCE,
            VERSION,
        )
        .into_bytes()
    }

    fn distribution_manifest(
        candidate: &[u8],
        acceptance: &[u8],
        go_license: &[u8],
        go_patents: &[u8],
        checker_license: &[u8],
    ) -> Vec<u8> {
        let records = [
            (
                candidate,
                "checker-payload-candidate.tar",
                "candidate-archive",
            ),
            (
                acceptance,
                "checker-payload-distribution-acceptance-v0.1.jcs",
                "distribution-acceptance",
            ),
            (go_license, "licenses/go/LICENSE", "go-license"),
            (go_patents, "licenses/go/PATENTS", "go-patent-grant"),
            (
                checker_license,
                "licenses/radishaxiom-checker/LICENSE",
                "checker-license",
            ),
        ];
        let contents = records
            .iter()
            .map(|(raw, path, role)| {
                format!(
                    "{{\"byte_length\":\"{}\",\"mode\":\"0644\",\"path\":\"{path}\",\"raw_sha256\":\"{}\",\"role\":\"{role}\"}}",
                    raw.len(),
                    raw_digest(raw),
                )
            })
            .collect::<Vec<_>>()
            .join(",");
        format!(
            concat!(
                "{{\"contents\":[{}],\"format\":\"radishaxiom-checker-runtime-distribution-manifest\",\"format_version\":\"0.1\",",
                "\"identity\":{{\"implementation\":\"radishaxiom-independent-checker-go\",\"source\":\"{}\",",
                "\"target\":{{\"goarch\":\"arm64\",\"goarm64\":\"v8.0\",\"goos\":\"darwin\",\"macho\":\"64-bit-arm64-executable\"}},",
                "\"toolchain\":\"go1.26.7\",\"version\":\"{}\"}},",
                "\"packaging\":{{\"archive_format\":\"ustar\",\"header_profile\":{{\"gid\":\"0\",\"gname\":\"\",\"mtime\":\"1970-01-01T00:00:00Z\",\"type\":\"regular\",\"uid\":\"0\",\"uname\":\"\"}},",
                "\"member_order\":[\"checker-payload-candidate.tar\",\"checker-payload-distribution-acceptance-v0.1.jcs\",\"checker-payload-distribution-manifest-v0.1.jcs\",\"licenses/go/LICENSE\",\"licenses/go/PATENTS\",\"licenses/radishaxiom-checker/LICENSE\"]}}}}"
            ),
            contents, SOURCE, VERSION,
        )
        .into_bytes()
    }

    #[allow(clippy::too_many_arguments)]
    fn synthetic_registration(
        provenance: &[u8],
        payload_acceptance: &[u8],
        executable: &[u8],
        candidate_manifest: &[u8],
        candidate_archive: &[u8],
        distribution_acceptance: &[u8],
        distribution_manifest: &[u8],
        distribution_archive: &[u8],
    ) -> Vec<u8> {
        let mut value = parse(RECORD, false).unwrap();
        set_nested_string(&mut value, &["checker", "source", "identity"], SOURCE);
        set_nested_string(&mut value, &["checker", "version"], VERSION);
        set_artifact(&mut value, &["build_provenance"], provenance);
        set_artifact(&mut value, &["acceptance"], payload_acceptance);
        set_artifact(&mut value, &["artifact"], executable);
        set_artifact(
            &mut value,
            &["candidate_archive", "manifest"],
            candidate_manifest,
        );
        set_artifact(&mut value, &["candidate_archive"], candidate_archive);
        set_artifact(
            &mut value,
            &["durable_registration", "distribution_package", "acceptance"],
            distribution_acceptance,
        );
        set_artifact(
            &mut value,
            &["durable_registration", "distribution_package", "manifest"],
            distribution_manifest,
        );
        set_artifact(
            &mut value,
            &["durable_registration", "distribution_package"],
            distribution_archive,
        );
        set_artifact(
            &mut value,
            &["durable_registration", "provider", "release", "asset"],
            distribution_archive,
        );
        refresh_record_digest(&mut value);
        canonical_bytes(&value)
    }

    fn make_ustar(entries: &[(&str, u32, Vec<u8>)]) -> Vec<u8> {
        let mut archive = Vec::new();
        for (name, mode, raw) in entries {
            archive.extend_from_slice(
                &canonical_header(name, *mode, u64::try_from(raw.len()).unwrap()).unwrap(),
            );
            archive.extend_from_slice(raw);
            let padding = (512 - raw.len() % 512) % 512;
            archive.resize(archive.len() + padding, 0);
        }
        archive.resize(archive.len() + 1024, 0);
        archive
    }

    fn expectations(entries: &[(&str, u32, Vec<u8>)]) -> Vec<ArchiveMemberExpectation> {
        entries
            .iter()
            .map(|(name, mode, raw)| {
                ArchiveMemberExpectation::new(
                    *name,
                    *mode,
                    u64::try_from(raw.len()).unwrap(),
                    raw_digest(raw),
                )
                .unwrap()
            })
            .collect()
    }

    fn raw_digest(raw: &[u8]) -> String {
        format!("sha256:{}", digest_hex(raw))
    }

    fn identity(raw: Vec<u8>) -> Vec<u8> {
        raw
    }

    fn add_unknown_candidate_member(mut raw: Vec<u8>) -> Vec<u8> {
        raw.pop();
        raw.extend_from_slice(b",\"unexpected\":\"closed\"}");
        raw
    }

    fn change_candidate_source(raw: Vec<u8>) -> Vec<u8> {
        replace_once(
            raw,
            SOURCE,
            "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        )
    }

    fn change_candidate_content_digest(raw: Vec<u8>) -> Vec<u8> {
        let current = raw_digest(b"synthetic provenance");
        replace_once(
            raw,
            &current,
            "sha256:3333333333333333333333333333333333333333333333333333333333333333",
        )
    }

    fn prefix_candidate_whitespace(mut raw: Vec<u8>) -> Vec<u8> {
        raw.insert(0, b' ');
        raw
    }

    fn change_distribution_candidate_digest(raw: Vec<u8>) -> Vec<u8> {
        let marker = b"\"raw_sha256\":\"sha256:";
        let offset = raw
            .windows(marker.len())
            .position(|window| window == marker)
            .unwrap()
            + marker.len();
        let mut changed = raw;
        changed[offset] = if changed[offset] == b'a' { b'b' } else { b'a' };
        changed
    }

    fn change_distribution_header_profile(raw: Vec<u8>) -> Vec<u8> {
        replace_once(raw, "1970-01-01T00:00:00Z", "1970-01-01T00:00:01Z")
    }

    fn swap_distribution_member_order(raw: Vec<u8>) -> Vec<u8> {
        replace_once(
            raw,
            "\"checker-payload-candidate.tar\",\"checker-payload-distribution-acceptance-v0.1.jcs\"",
            "\"checker-payload-distribution-acceptance-v0.1.jcs\",\"checker-payload-candidate.tar\"",
        )
    }

    fn oversize_candidate_manifest(_: Vec<u8>) -> Vec<u8> {
        vec![b' '; MAX_CHECKER_RUNTIME_MANIFEST_BYTES + 1]
    }

    fn replace_once(raw: Vec<u8>, needle: &str, replacement: &str) -> Vec<u8> {
        assert_eq!(needle.len(), replacement.len());
        let mut text = String::from_utf8(raw).unwrap();
        let offset = text.find(needle).unwrap();
        text.replace_range(offset..offset + needle.len(), replacement);
        text.into_bytes()
    }

    fn set_artifact(value: &mut Value, path: &[&str], raw: &[u8]) {
        set_nested_string(
            value,
            &[path, &["byte_length"]].concat(),
            &raw.len().to_string(),
        );
        set_nested_string(value, &[path, &["raw_sha256"]].concat(), &raw_digest(raw));
    }

    fn object_mut<'a>(value: &'a mut Value, path: &[&str]) -> &'a mut Vec<(String, Value)> {
        let mut current = value;
        for component in path {
            let Value::Object(object) = current else {
                panic!("fixture path must contain objects");
            };
            current = &mut object
                .iter_mut()
                .find(|(name, _)| name == component)
                .unwrap()
                .1;
        }
        let Value::Object(object) = current else {
            panic!("fixture target must be an object");
        };
        object
    }

    fn set_nested_string(value: &mut Value, path: &[&str], replacement: &str) {
        let (parents, leaf) = path.split_at(path.len() - 1);
        let object = object_mut(value, parents);
        let (_, member) = object.iter_mut().find(|(name, _)| name == leaf[0]).unwrap();
        *member = Value::String(replacement.into());
    }

    fn refresh_record_digest(value: &mut Value) {
        let digest = domain_digest(REGISTRATION_DOMAIN, value, "record_digest").unwrap();
        set_nested_string(value, &["record_digest"], &digest);
    }
}
