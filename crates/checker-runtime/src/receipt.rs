use crate::canonical::{
    DocumentError, ShapeSpec, Value, as_object, canonical_bytes, domain_digest,
    domain_digest_value, member, parse, string_member, validate_digest, validate_shape,
};
use crate::policy::LauncherPolicy;
use crate::registration::{ProviderReleaseIdentity, RegistrationRecord, RegistrationStatus};

const RECEIPT_FORMAT: &str = "radishaxiom-checker-runtime-installation-receipt";
const RECEIPT_VERSION: &str = "0.1";
const RECEIPT_DOMAIN: &str = "radishaxiom.checker-runtime-installation-receipt.v0.1";

const RECEIPT_OBJECT_FIELDS: &[(&str, &str)] = &[
    (
        "$",
        "artifact,checker,digest_domain,distribution,document_digest,format,format_version,installed_at,provider,registration,slot,target,verifier",
    ),
    ("$.artifact", "byte_length,raw_sha256"),
    ("$.checker", "implementation,source,toolchain,version"),
    ("$.distribution", "byte_length,raw_sha256"),
    (
        "$.provider",
        "asset_id,asset_name,release_id,release_tag,repository,target_commit",
    ),
    ("$.registration", "id,record_digest"),
    ("$.slot", "relative_identity,state"),
    ("$.target", "executable_format,goarch,goarm64,goos"),
    ("$.verifier", "identity,name,version"),
];

const RECEIPT_SHAPE: ShapeSpec<'static> = ShapeSpec {
    object_fields: RECEIPT_OBJECT_FIELDS,
    array_paths: &[],
    bool_paths: &[],
};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InstallationVerifierIdentity {
    identity: Box<str>,
    name: Box<str>,
    version: Box<str>,
}

impl InstallationVerifierIdentity {
    pub fn try_new(
        identity: impl Into<Box<str>>,
        name: impl Into<Box<str>>,
        version: impl Into<Box<str>>,
    ) -> Result<Self, DocumentError> {
        let verifier = Self {
            identity: identity.into(),
            name: name.into(),
            version: version.into(),
        };
        validate_digest(&verifier.identity, "$.verifier.identity")?;
        for (value, path) in [
            (verifier.name.as_ref(), "$.verifier.name"),
            (verifier.version.as_ref(), "$.verifier.version"),
        ] {
            if !value.is_ascii() {
                return Err(DocumentError::new("non-ascii-string", path));
            }
        }
        Ok(verifier)
    }

    pub fn identity(&self) -> &str {
        &self.identity
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn version(&self) -> &str {
        &self.version
    }

    fn from_value(value: &Value) -> Result<Self, DocumentError> {
        let object = as_object(value, "$.verifier")?;
        Self::try_new(
            string_member(object, "identity", "$.verifier")?,
            string_member(object, "name", "$.verifier")?,
            string_member(object, "version", "$.verifier")?,
        )
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InstallationReceipt {
    value: Value,
    canonical: Box<[u8]>,
    document_digest: Box<str>,
    installed_at: Box<str>,
    slot_relative_identity: Box<str>,
    verifier: InstallationVerifierIdentity,
}

impl InstallationReceipt {
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.canonical
    }

    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }

    pub fn installed_at(&self) -> &str {
        &self.installed_at
    }

    pub fn slot_relative_identity(&self) -> &str {
        &self.slot_relative_identity
    }

    pub fn verifier(&self) -> &InstallationVerifierIdentity {
        &self.verifier
    }
}

pub fn build_installation_receipt(
    _policy: &LauncherPolicy,
    record: &RegistrationRecord,
    installed_at: &str,
    verifier: &InstallationVerifierIdentity,
) -> Result<InstallationReceipt, DocumentError> {
    if record.status() != RegistrationStatus::RegisteredInactive {
        return Err(DocumentError::new(
            "installation-requires-registered-inactive",
            "$.registration.status",
        ));
    }
    if !valid_utc_timestamp(installed_at) {
        return Err(DocumentError::new(
            "invalid-installation-time",
            "$.installed_at",
        ));
    }
    validate_installation_bindings(record)?;

    let artifact = record.artifact();
    let checker = record.checker();
    let distribution = record.distribution();
    let provider = record.provider_release();
    let target = record.target();
    let slot_relative_identity = slot_relative_identity(record);

    let mut body_members = vec![
        (
            "artifact".into(),
            object([
                ("byte_length", string(artifact.byte_length().to_string())),
                ("raw_sha256", string(artifact.raw_sha256())),
            ]),
        ),
        (
            "checker".into(),
            object([
                ("implementation", string(checker.implementation())),
                ("source", string(checker.source())),
                ("toolchain", string(checker.toolchain())),
                ("version", string(checker.version())),
            ]),
        ),
        ("digest_domain".into(), string(RECEIPT_DOMAIN)),
        (
            "distribution".into(),
            object([
                (
                    "byte_length",
                    string(distribution.byte_length().to_string()),
                ),
                ("raw_sha256", string(distribution.raw_sha256())),
            ]),
        ),
        ("format".into(), string(RECEIPT_FORMAT)),
        ("format_version".into(), string(RECEIPT_VERSION)),
        ("installed_at".into(), string(installed_at)),
        ("provider".into(), provider_value(provider)),
        (
            "registration".into(),
            object([
                ("id", string(record.id())),
                ("record_digest", string(record.document_digest())),
            ]),
        ),
        (
            "slot".into(),
            object([
                ("relative_identity", string(&slot_relative_identity)),
                ("state", string("installed-inactive")),
            ]),
        ),
        (
            "target".into(),
            object([
                ("executable_format", string(target.executable_format())),
                ("goarch", string(target.goarch())),
                ("goarm64", string(target.variant())),
                ("goos", string(target.goos())),
            ]),
        ),
        (
            "verifier".into(),
            object([
                ("identity", string(verifier.identity())),
                ("name", string(verifier.name())),
                ("version", string(verifier.version())),
            ]),
        ),
    ];
    let body = Value::Object(body_members.clone());
    let document_digest = domain_digest_value(RECEIPT_DOMAIN, &body);
    body_members.insert(4, ("document_digest".into(), string(&document_digest)));
    let value = Value::Object(body_members);
    let canonical = canonical_bytes(&value).into_boxed_slice();

    Ok(InstallationReceipt {
        value,
        canonical,
        document_digest: document_digest.into(),
        installed_at: installed_at.into(),
        slot_relative_identity: slot_relative_identity.into(),
        verifier: verifier.clone(),
    })
}

pub(crate) fn slot_relative_identity(record: &RegistrationRecord) -> String {
    let target = record.target();
    format!(
        "slots/{}/{}/{}/{}/{}",
        target.goos(),
        target.goarch(),
        target.variant(),
        target.executable_format(),
        record.distribution().raw_sha256().replace(':', "-")
    )
}

pub fn parse_installation_receipt(
    bytes: &[u8],
    policy: &LauncherPolicy,
    record: &RegistrationRecord,
) -> Result<InstallationReceipt, DocumentError> {
    let value = parse(bytes, true)?;
    validate_shape(&value, &RECEIPT_SHAPE)?;
    let root = as_object(&value, "$")?;
    expect_string(root, "digest_domain", RECEIPT_DOMAIN, "receipt-domain")?;
    expect_string(root, "format", RECEIPT_FORMAT, "receipt-format")?;
    expect_string(root, "format_version", RECEIPT_VERSION, "receipt-version")?;

    let stored_digest = string_member(root, "document_digest", "$")?;
    validate_digest(stored_digest, "$.document_digest")?;
    if stored_digest != domain_digest(RECEIPT_DOMAIN, &value, "document_digest")? {
        return Err(DocumentError::new(
            "receipt-document-digest",
            "$.document_digest",
        ));
    }

    let installed_at = string_member(root, "installed_at", "$")?;
    let verifier = InstallationVerifierIdentity::from_value(member(root, "verifier", "$")?)?;
    let expected = build_installation_receipt(policy, record, installed_at, &verifier)?;
    if value != expected.value {
        return Err(DocumentError::new("receipt-binding-mismatch", "$"));
    }
    Ok(expected)
}

fn validate_installation_bindings(record: &RegistrationRecord) -> Result<(), DocumentError> {
    let distribution = record.distribution();
    let provider = record.provider_release();
    if provider.asset_raw_sha256() != distribution.raw_sha256() {
        return Err(DocumentError::new(
            "provider-distribution-digest",
            "$.durable_registration.provider.release.asset.raw_sha256",
        ));
    }
    if provider.asset_byte_length() != distribution.byte_length() {
        return Err(DocumentError::new(
            "provider-distribution-length",
            "$.durable_registration.provider.release.asset.byte_length",
        ));
    }
    if provider.asset_name() != record.distribution_filename() {
        return Err(DocumentError::new(
            "provider-distribution-name",
            "$.durable_registration.provider.release.asset.name",
        ));
    }
    if !provider.immutable() || provider.draft() {
        return Err(DocumentError::new(
            "provider-release-not-immutable",
            "$.durable_registration.provider.release",
        ));
    }
    Ok(())
}

fn provider_value(provider: &ProviderReleaseIdentity) -> Value {
    object([
        ("asset_id", string(provider.asset_id())),
        ("asset_name", string(provider.asset_name())),
        ("release_id", string(provider.release_id())),
        ("release_tag", string(provider.release_tag())),
        ("repository", string(provider.repository())),
        ("target_commit", string(provider.target_commit())),
    ])
}

pub(crate) fn valid_utc_timestamp(value: &str) -> bool {
    let bytes = value.as_bytes();
    bytes.len() == 20
        && bytes.iter().enumerate().all(|(index, byte)| match index {
            4 | 7 => *byte == b'-',
            10 => *byte == b'T',
            13 | 16 => *byte == b':',
            19 => *byte == b'Z',
            _ => byte.is_ascii_digit(),
        })
}

fn string(value: impl Into<String>) -> Value {
    Value::String(value.into())
}

fn object<const N: usize>(members: [(&str, Value); N]) -> Value {
    debug_assert!(members.windows(2).all(|pair| pair[0].0 < pair[1].0));
    Value::Object(
        members
            .into_iter()
            .map(|(name, value)| (name.into(), value))
            .collect(),
    )
}

fn expect_string(
    object: &[(String, Value)],
    name: &str,
    expected: &str,
    code: &'static str,
) -> Result<(), DocumentError> {
    if string_member(object, name, "$")? == expected {
        Ok(())
    } else {
        Err(DocumentError::new(code, format!("$.{name}")))
    }
}

#[cfg(test)]
mod tests {
    use super::{
        InstallationVerifierIdentity, RECEIPT_DOMAIN, build_installation_receipt,
        parse_installation_receipt,
    };
    use crate::canonical::{Value, canonical_bytes, domain_digest, parse};
    use crate::{parse_launcher_policy, parse_registration_record};

    const POLICY: &[u8] =
        include_bytes!("../../../contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs");
    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));
    const REGISTRATION_DOMAIN: &str = "radishaxiom.checker-runtime-payload-registration.v0.1";
    const GOLDEN_DOCUMENT_DIGEST: &str =
        "sha256:7a53b34f39059e97363a87d33532ee265cf4faa3d438a22a709f25ee47170ac2";
    const GOLDEN_RAW_DIGEST: &str =
        "54c1dad27b5f35efcc706a8599dd1b23798de9cda1ce313b48bbec798efe53c1";

    fn verifier() -> InstallationVerifierIdentity {
        InstallationVerifierIdentity::try_new(
            format!("sha256:{}", "1".repeat(64)),
            "radishaxiom-launcher-conformance-core",
            "0.1-test",
        )
        .unwrap()
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

    fn set_string(value: &mut Value, path: &[&str], replacement: &str) {
        let (parents, leaf) = path.split_at(path.len() - 1);
        let object = object_mut(value, parents);
        let (_, member) = object.iter_mut().find(|(name, _)| name == leaf[0]).unwrap();
        *member = Value::String(replacement.into());
    }

    fn set_bool(value: &mut Value, path: &[&str], replacement: bool) {
        let (parents, leaf) = path.split_at(path.len() - 1);
        let object = object_mut(value, parents);
        let (_, member) = object.iter_mut().find(|(name, _)| name == leaf[0]).unwrap();
        *member = Value::Bool(replacement);
    }

    fn refresh_digest(value: &mut Value, domain: &str, field: &str) {
        let digest = domain_digest(domain, value, field).unwrap();
        set_string(value, &[field], &digest);
    }

    #[test]
    fn real_record_matches_python_canonical_golden() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let record = parse_registration_record(RECORD).unwrap();
        let receipt =
            build_installation_receipt(&policy, &record, "2026-08-30T10:00:00Z", &verifier())
                .unwrap();

        assert_eq!(receipt.canonical_bytes().len(), 1_797);
        assert_eq!(
            crate::sha256::digest_hex(receipt.canonical_bytes()),
            GOLDEN_RAW_DIGEST
        );
        assert_eq!(receipt.document_digest(), GOLDEN_DOCUMENT_DIGEST);
        assert_eq!(
            receipt.slot_relative_identity(),
            concat!(
                "slots/darwin/arm64/v8.0/macho-64-arm64/",
                "sha256-17b44a1eb5ea9caeafd7b590bb8eb0ba87359bf53d5af2933a424d17fadfa437"
            )
        );
        assert_eq!(
            parse_installation_receipt(receipt.canonical_bytes(), &policy, &record).unwrap(),
            receipt
        );
    }

    #[test]
    fn receipt_requires_compact_closed_shape_and_valid_document_digest() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let record = parse_registration_record(RECORD).unwrap();
        let receipt =
            build_installation_receipt(&policy, &record, "2026-08-30T10:00:00Z", &verifier())
                .unwrap();

        let mut newline = receipt.canonical_bytes().to_vec();
        newline.push(b'\n');
        assert_eq!(
            parse_installation_receipt(&newline, &policy, &record)
                .unwrap_err()
                .code(),
            "noncanonical-json"
        );

        let mut unknown = parse(receipt.canonical_bytes(), true).unwrap();
        object_mut(&mut unknown, &["slot"])
            .push(("unknown".into(), Value::String("closed".into())));
        assert_eq!(
            parse_installation_receipt(&canonical_bytes(&unknown), &policy, &record)
                .unwrap_err()
                .code(),
            "unknown-member"
        );

        let mut drift = parse(receipt.canonical_bytes(), true).unwrap();
        set_string(
            &mut drift,
            &["document_digest"],
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        );
        assert_eq!(
            parse_installation_receipt(&canonical_bytes(&drift), &policy, &record)
                .unwrap_err()
                .code(),
            "receipt-document-digest"
        );
    }

    #[test]
    fn digest_correct_receipt_binding_drift_fails_closed() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let record = parse_registration_record(RECORD).unwrap();
        let receipt =
            build_installation_receipt(&policy, &record, "2026-08-30T10:00:00Z", &verifier())
                .unwrap();
        let mut value = parse(receipt.canonical_bytes(), true).unwrap();
        set_string(&mut value, &["slot", "state"], "installed-active");
        refresh_digest(&mut value, RECEIPT_DOMAIN, "document_digest");

        assert_eq!(
            parse_installation_receipt(&canonical_bytes(&value), &policy, &record)
                .unwrap_err()
                .code(),
            "receipt-binding-mismatch"
        );
    }

    #[test]
    fn construction_rejects_active_or_mutable_provider_records() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let mut active = parse(RECORD, false).unwrap();
        set_string(&mut active, &["registration", "status"], "active");
        refresh_digest(&mut active, REGISTRATION_DOMAIN, "record_digest");
        let active = parse_registration_record(&canonical_bytes(&active)).unwrap();
        assert_eq!(
            build_installation_receipt(&policy, &active, "2026-08-30T10:00:00Z", &verifier(),)
                .unwrap_err()
                .code(),
            "installation-requires-registered-inactive"
        );

        let mut mutable = parse(RECORD, false).unwrap();
        set_bool(
            &mut mutable,
            &["durable_registration", "provider", "release", "immutable"],
            false,
        );
        refresh_digest(&mut mutable, REGISTRATION_DOMAIN, "record_digest");
        let mutable = parse_registration_record(&canonical_bytes(&mutable)).unwrap();
        assert_eq!(
            build_installation_receipt(&policy, &mutable, "2026-08-30T10:00:00Z", &verifier(),)
                .unwrap_err()
                .code(),
            "provider-release-not-immutable"
        );
    }

    #[test]
    fn timestamp_verifier_and_provider_distribution_bindings_are_closed() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let record = parse_registration_record(RECORD).unwrap();
        assert_eq!(
            build_installation_receipt(&policy, &record, "2026-08-30", &verifier())
                .unwrap_err()
                .code(),
            "invalid-installation-time"
        );
        assert_eq!(
            InstallationVerifierIdentity::try_new("sha256:bad", "verifier", "0.1")
                .unwrap_err()
                .code(),
            "invalid-digest"
        );
        assert_eq!(
            InstallationVerifierIdentity::try_new(
                format!("sha256:{}", "1".repeat(64)),
                "vérifier",
                "0.1",
            )
            .unwrap_err()
            .code(),
            "non-ascii-string"
        );

        for (field, replacement, code) in [
            (
                "raw_sha256",
                "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "provider-distribution-digest",
            ),
            ("byte_length", "1", "provider-distribution-length"),
            ("name", "wrong.tar", "provider-distribution-name"),
        ] {
            let mut mismatch = parse(RECORD, false).unwrap();
            set_string(
                &mut mismatch,
                &[
                    "durable_registration",
                    "provider",
                    "release",
                    "asset",
                    field,
                ],
                replacement,
            );
            refresh_digest(&mut mismatch, REGISTRATION_DOMAIN, "record_digest");
            let mismatch = parse_registration_record(&canonical_bytes(&mismatch)).unwrap();
            assert_eq!(
                build_installation_receipt(
                    &policy,
                    &mismatch,
                    "2026-08-30T10:00:00Z",
                    &verifier(),
                )
                .unwrap_err()
                .code(),
                code
            );
        }
    }
}
