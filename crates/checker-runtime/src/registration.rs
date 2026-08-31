use std::fmt;

use crate::canonical::{
    DocumentError, ShapeSpec, Value, as_object, domain_digest, member, parse, parse_decimal,
    string_member, validate_digest, validate_shape,
};
use crate::selection::NativeTarget;

const REGISTRATION_FORMAT: &str = "radishaxiom-checker-runtime-payload-registration";
const REGISTRATION_VERSION: &str = "0.1";
const REGISTRATION_DOMAIN: &str = "radishaxiom.checker-runtime-payload-registration.v0.1";

const REGISTRATION_OBJECT_FIELDS: &[(&str, &str)] = &[
    (
        "$",
        "acceptance,artifact,build_provenance,candidate_archive,candidate_workflow,checker,digest_domain,durable_registration,format,format_version,id,record_digest,registration,retention,reverification,target",
    ),
    (
        "$.acceptance",
        "byte_length,decision,excluded_scope,format,format_version,kind,raw_sha256,scenarios,scope",
    ),
    (
        "$.acceptance.scenarios[]",
        "byte_length,id,outcome,raw_sha256",
    ),
    ("$.artifact", "byte_length,kind,raw_sha256"),
    (
        "$.build_provenance",
        "byte_length,format,format_version,kind,raw_sha256",
    ),
    (
        "$.candidate_archive",
        "byte_length,filename,format,kind,manifest,raw_sha256",
    ),
    (
        "$.candidate_archive.manifest",
        "byte_length,filename,format,format_version,raw_sha256",
    ),
    (
        "$.candidate_workflow",
        "ci,commit,default_branch_presence,file,promotion,remote_ref,repository,run,state,tree,trigger",
    ),
    ("$.candidate_workflow.ci", "conclusion,run_id,workflow"),
    (
        "$.candidate_workflow.promotion",
        "dev_ref,master_ref,merge_commit,merge_method,pr_ci,pr_number,push_ci,source_identity_commit",
    ),
    (
        "$.candidate_workflow.promotion.pr_ci",
        "conclusion,run_id,workflow",
    ),
    (
        "$.candidate_workflow.run",
        "attempt,conclusion,created_at,event,head_sha,inputs,jobs,ref,run_id,workflow",
    ),
    (
        "$.candidate_workflow.run.inputs",
        "confirm_candidate_upload,source_identity,version",
    ),
    ("$.candidate_workflow.run.jobs[]", "conclusion,id,name"),
    ("$.checker", "implementation,source,toolchain,version"),
    (
        "$.checker.source",
        "file_count,identity,manifest_byte_length",
    ),
    (
        "$.durable_registration",
        "distribution_package,provider,status",
    ),
    (
        "$.durable_registration.distribution_package",
        "acceptance,byte_length,filename,format,format_version,kind,manifest,raw_sha256",
    ),
    (
        "$.durable_registration.distribution_package.acceptance",
        "byte_length,decision,excluded_scope,format,format_version,raw_sha256,scope",
    ),
    (
        "$.durable_registration.distribution_package.manifest",
        "byte_length,filename,format,format_version,raw_sha256",
    ),
    (
        "$.durable_registration.provider",
        "independent_readback,kind,release,repository,repository_immutability",
    ),
    (
        "$.durable_registration.provider.independent_readback",
        "asset_api_metadata,cli_release_download,distribution_archive,inner_candidate,public_browser_download,verified_at",
    ),
    (
        "$.durable_registration.provider.release",
        "asset,attestation,draft,html_url,id,immutable,name,prerelease,published_at,release_classification,tag,tag_resolved_commit,target_commit,verification",
    ),
    (
        "$.durable_registration.provider.release.asset",
        "api_url,browser_download_url,byte_length,content_type,created_at,digest,id,name,node_id,raw_sha256,state,updated_at",
    ),
    (
        "$.durable_registration.provider.release.attestation",
        "asset_subject,asset_verified,certificate_subject_alternative_name,predicate_type,release_subject,release_verified,timestamp,trusted_root,verification_tool",
    ),
    (
        "$.durable_registration.provider.release.attestation.asset_subject",
        "digest,name",
    ),
    (
        "$.durable_registration.provider.release.attestation.release_subject",
        "digest,uri",
    ),
    (
        "$.durable_registration.provider.release.attestation.verification_tool",
        "name,version",
    ),
    (
        "$.durable_registration.provider.release.verification",
        "draft_asset_api_metadata_readback,draft_asset_raw_byte_readback,post_publication_asset_api_metadata_readback,post_publication_cli_raw_byte_readback,post_publication_distribution_and_inner_candidate_strict_verification,post_publication_public_raw_byte_readback,verified_at",
    ),
    (
        "$.durable_registration.provider.repository_immutability",
        "api_version,checked_at,enabled,enabled_at,endpoint,enforced_by_owner,status,viewer_permission",
    ),
    ("$.registration", "reasons,registered_at,status"),
    (
        "$.retention",
        "acceptance_bytes,artifact_bytes,candidate_archive_bytes,candidate_fetch,distribution_acceptance_bytes,distribution_manifest_bytes,distribution_package_bytes,fetch,provenance_bytes",
    ),
    (
        "$.retention.candidate_fetch",
        "kind,provider,readback,repository,workflow",
    ),
    (
        "$.retention.candidate_fetch.provider",
        "artifact_id,created_at,digest,expired_at_readback,expires_at,name,size_in_bytes,url",
    ),
    (
        "$.retention.candidate_fetch.readback",
        "distribution_archive_verified,exact_artifact_id,inner_candidate_verified,job_id,provider_metadata_verified",
    ),
    (
        "$.retention.candidate_fetch.workflow",
        "head_sha,ref,run_attempt,run_id",
    ),
    ("$.retention.fetch", "kind,provider,readback,repository"),
    (
        "$.retention.fetch.provider",
        "asset_api_url,asset_browser_download_url,asset_digest,asset_id,asset_name,asset_size,release_id,release_immutable,release_tag,target_commit",
    ),
    (
        "$.retention.fetch.readback",
        "asset_attestation_verified,distribution_archive_verified,exact_asset_id,inner_candidate_verified,provider_metadata_verified,public_download_verified,release_attestation_verified",
    ),
    ("$.reverification", "required_inputs,status"),
    ("$.target", "executable_format,goarch,goarm64,goos"),
];

const REGISTRATION_ARRAY_PATHS: &[&str] = &[
    "$.acceptance.excluded_scope",
    "$.acceptance.scenarios",
    "$.acceptance.scope",
    "$.candidate_workflow.run.jobs",
    "$.durable_registration.distribution_package.acceptance.excluded_scope",
    "$.durable_registration.distribution_package.acceptance.scope",
    "$.registration.reasons",
    "$.reverification.required_inputs",
];

const REGISTRATION_BOOL_PATHS: &[&str] = &[
    "$.candidate_workflow.run.inputs.confirm_candidate_upload",
    "$.durable_registration.provider.release.attestation.asset_verified",
    "$.durable_registration.provider.release.attestation.release_verified",
    "$.durable_registration.provider.release.draft",
    "$.durable_registration.provider.release.immutable",
    "$.durable_registration.provider.release.prerelease",
    "$.durable_registration.provider.release.verification.draft_asset_api_metadata_readback",
    "$.durable_registration.provider.release.verification.draft_asset_raw_byte_readback",
    "$.durable_registration.provider.release.verification.post_publication_asset_api_metadata_readback",
    "$.durable_registration.provider.release.verification.post_publication_cli_raw_byte_readback",
    "$.durable_registration.provider.release.verification.post_publication_distribution_and_inner_candidate_strict_verification",
    "$.durable_registration.provider.release.verification.post_publication_public_raw_byte_readback",
    "$.durable_registration.provider.repository_immutability.enabled",
    "$.durable_registration.provider.repository_immutability.enforced_by_owner",
    "$.retention.candidate_fetch.provider.expired_at_readback",
    "$.retention.candidate_fetch.readback.distribution_archive_verified",
    "$.retention.candidate_fetch.readback.exact_artifact_id",
    "$.retention.candidate_fetch.readback.inner_candidate_verified",
    "$.retention.candidate_fetch.readback.provider_metadata_verified",
    "$.retention.fetch.provider.release_immutable",
    "$.retention.fetch.readback.asset_attestation_verified",
    "$.retention.fetch.readback.distribution_archive_verified",
    "$.retention.fetch.readback.exact_asset_id",
    "$.retention.fetch.readback.inner_candidate_verified",
    "$.retention.fetch.readback.provider_metadata_verified",
    "$.retention.fetch.readback.public_download_verified",
    "$.retention.fetch.readback.release_attestation_verified",
];

const REGISTRATION_SHAPE: ShapeSpec<'static> = ShapeSpec {
    object_fields: REGISTRATION_OBJECT_FIELDS,
    array_paths: REGISTRATION_ARRAY_PATHS,
    bool_paths: REGISTRATION_BOOL_PATHS,
};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ArtifactIdentity {
    byte_length: u64,
    raw_sha256: Box<str>,
}

impl ArtifactIdentity {
    pub fn byte_length(&self) -> u64 {
        self.byte_length
    }

    pub fn raw_sha256(&self) -> &str {
        &self.raw_sha256
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CheckerIdentity {
    implementation: Box<str>,
    source: Box<str>,
    toolchain: Box<str>,
    version: Box<str>,
}

impl CheckerIdentity {
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
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RegistrationStatus {
    RegisteredInactive,
    Active,
    Revoked,
}

impl fmt::Display for RegistrationStatus {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::RegisteredInactive => "registered-inactive",
            Self::Active => "active",
            Self::Revoked => "revoked",
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RegistrationRecord {
    id: Box<str>,
    document_digest: Box<str>,
    status: RegistrationStatus,
    target: NativeTarget,
    checker: CheckerIdentity,
    artifact: ArtifactIdentity,
    distribution: ArtifactIdentity,
}

impl RegistrationRecord {
    pub fn id(&self) -> &str {
        &self.id
    }

    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }

    pub fn status(&self) -> RegistrationStatus {
        self.status
    }

    pub fn target(&self) -> &NativeTarget {
        &self.target
    }

    pub fn checker(&self) -> &CheckerIdentity {
        &self.checker
    }

    pub fn artifact(&self) -> &ArtifactIdentity {
        &self.artifact
    }

    pub fn distribution(&self) -> &ArtifactIdentity {
        &self.distribution
    }
}

pub fn parse_registration_record(bytes: &[u8]) -> Result<RegistrationRecord, DocumentError> {
    let value = parse(bytes, false)?;
    validate_shape(&value, &REGISTRATION_SHAPE)?;
    let root = as_object(&value, "$")?;

    expect_string(
        root,
        "format",
        REGISTRATION_FORMAT,
        "$",
        "registration-format",
    )?;
    expect_string(
        root,
        "format_version",
        REGISTRATION_VERSION,
        "$",
        "registration-version",
    )?;
    expect_string(
        root,
        "digest_domain",
        REGISTRATION_DOMAIN,
        "$",
        "registration-domain",
    )?;

    let stored_digest = string_member(root, "record_digest", "$")?;
    validate_digest(stored_digest, "$.record_digest")?;
    let calculated_digest = domain_digest(REGISTRATION_DOMAIN, &value, "record_digest")?;
    if stored_digest != calculated_digest {
        return Err(DocumentError::new("registration-digest", "$.record_digest"));
    }

    let id = string_member(root, "id", "$")?;
    if id.is_empty() {
        return Err(DocumentError::new("registration-id", "$.id"));
    }
    let target = NativeTarget::from_value(member(root, "target", "$")?, "$.target")?;
    let registration = object_member(root, "registration", "$")?;
    let status = match string_member(registration, "status", "$.registration")? {
        "registered-inactive" => RegistrationStatus::RegisteredInactive,
        "active" => RegistrationStatus::Active,
        "revoked" => RegistrationStatus::Revoked,
        _ => {
            return Err(DocumentError::new(
                "registration-status",
                "$.registration.status",
            ));
        }
    };

    let checker_value = object_member(root, "checker", "$")?;
    let source_value = object_member(checker_value, "source", "$.checker")?;
    let source = string_member(source_value, "identity", "$.checker.source")?;
    validate_digest(source, "$.checker.source.identity")?;
    let checker = CheckerIdentity {
        implementation: string_member(checker_value, "implementation", "$.checker")?.into(),
        source: source.into(),
        toolchain: string_member(checker_value, "toolchain", "$.checker")?.into(),
        version: string_member(checker_value, "version", "$.checker")?.into(),
    };

    let artifact = parse_artifact(object_member(root, "artifact", "$")?, "$.artifact")?;
    let durable = object_member(root, "durable_registration", "$")?;
    let distribution = parse_artifact(
        object_member(durable, "distribution_package", "$.durable_registration")?,
        "$.durable_registration.distribution_package",
    )?;

    Ok(RegistrationRecord {
        id: id.into(),
        document_digest: calculated_digest.into(),
        status,
        target,
        checker,
        artifact,
        distribution,
    })
}

fn parse_artifact(
    object: &[(String, Value)],
    path: &str,
) -> Result<ArtifactIdentity, DocumentError> {
    let byte_length = parse_decimal(
        string_member(object, "byte_length", path)?,
        &format!("{path}.byte_length"),
    )?;
    let raw_sha256 = string_member(object, "raw_sha256", path)?;
    validate_digest(raw_sha256, &format!("{path}.raw_sha256"))?;
    Ok(ArtifactIdentity {
        byte_length,
        raw_sha256: raw_sha256.into(),
    })
}

fn object_member<'a>(
    object: &'a [(String, Value)],
    name: &str,
    path: &str,
) -> Result<&'a [(String, Value)], DocumentError> {
    as_object(member(object, name, path)?, &format!("{path}.{name}"))
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

#[cfg(test)]
mod tests {
    use super::{REGISTRATION_DOMAIN, RegistrationStatus, parse_registration_record};
    use crate::canonical::{Value, canonical_bytes, domain_digest, parse};
    use crate::{
        NativeHostIdentity, NativeProcessMode, NativeTarget, SelectionError, SelectionPurpose,
        parse_launcher_policy, select_registration,
    };

    const POLICY: &[u8] =
        include_bytes!("../../../contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs");
    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));

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

    fn refresh_digest(value: &mut Value) {
        let digest = domain_digest(REGISTRATION_DOMAIN, value, "record_digest").unwrap();
        set_nested_string(value, &["record_digest"], &digest);
    }

    fn active_record() -> super::RegistrationRecord {
        let mut value = parse(RECORD, false).unwrap();
        set_nested_string(&mut value, &["registration", "status"], "active");
        refresh_digest(&mut value);
        parse_registration_record(&canonical_bytes(&value)).unwrap()
    }

    #[test]
    fn current_inactive_record_and_identities_are_accepted() {
        let record = parse_registration_record(RECORD).unwrap();
        assert_eq!(record.status(), RegistrationStatus::RegisteredInactive);
        assert_eq!(
            record.document_digest(),
            "sha256:7b7bac3a1541253792f475de0dba2d92030ad5a28ad61bfb50c80803e667808d"
        );
        assert_eq!(record.artifact().byte_length(), 4_689_378);
        assert_eq!(record.distribution().byte_length(), 4_720_640);
        assert_eq!(record.checker().toolchain(), "go1.26.7");
    }

    #[test]
    fn unknown_nested_member_and_digest_drift_fail_closed() {
        let mut unknown = parse(RECORD, false).unwrap();
        object_mut(&mut unknown, &["target"])
            .push(("unknown".into(), Value::String("closed".into())));
        refresh_digest(&mut unknown);
        assert_eq!(
            parse_registration_record(&canonical_bytes(&unknown))
                .unwrap_err()
                .code(),
            "unknown-member"
        );

        let mut digest = parse(RECORD, false).unwrap();
        set_nested_string(
            &mut digest,
            &["record_digest"],
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        );
        assert_eq!(
            parse_registration_record(&canonical_bytes(&digest))
                .unwrap_err()
                .code(),
            "registration-digest"
        );
    }

    #[test]
    fn qualification_and_product_selection_do_not_fallback() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let inactive = parse_registration_record(RECORD).unwrap();
        let target = inactive.target().clone();
        let native = NativeHostIdentity::new(target.clone(), NativeProcessMode::Native);

        assert_eq!(
            select_registration(
                &policy,
                std::slice::from_ref(&inactive),
                &native,
                SelectionPurpose::Qualification,
            )
            .unwrap()
            .id(),
            inactive.id()
        );
        assert!(matches!(
            select_registration(
                &policy,
                std::slice::from_ref(&inactive),
                &native,
                SelectionPurpose::Product,
            ),
            Err(SelectionError::Cardinality { actual: 0, .. })
        ));

        let active = active_record();
        assert_eq!(
            select_registration(
                &policy,
                std::slice::from_ref(&active),
                &native,
                SelectionPurpose::Product,
            )
            .unwrap()
            .status(),
            RegistrationStatus::Active
        );
        assert!(matches!(
            select_registration(
                &policy,
                &[active.clone(), active],
                &native,
                SelectionPurpose::Product,
            ),
            Err(SelectionError::Cardinality { actual: 2, .. })
        ));
    }

    #[test]
    fn unknown_architecture_variant_and_translation_fail_closed() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let active = active_record();
        for host in [
            NativeHostIdentity::new(
                NativeTarget::try_new("darwin", "amd64", "v8.0", "macho-64-arm64").unwrap(),
                NativeProcessMode::Native,
            ),
            NativeHostIdentity::new(
                NativeTarget::try_new("darwin", "arm64", "v8.1", "macho-64-arm64").unwrap(),
                NativeProcessMode::Native,
            ),
            NativeHostIdentity::new(active.target().clone(), NativeProcessMode::Translated),
        ] {
            let error = select_registration(
                &policy,
                std::slice::from_ref(&active),
                &host,
                SelectionPurpose::Product,
            )
            .unwrap_err();
            assert_eq!(error.classification(), "runtime-unavailable");
        }
    }
}
