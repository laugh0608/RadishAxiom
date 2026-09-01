use crate::canonical::{
    DocumentError, ShapeSpec, Value, as_array, as_object, domain_digest, domain_digest_value,
    member, parse, parse_decimal, string_member, validate_digest, validate_shape,
};
use crate::policy::LauncherPolicy;
use crate::receipt::{InstallationReceipt, parse_installation_receipt, valid_utc_timestamp};
use crate::registration::{RegistrationRecord, RegistrationStatus};
use crate::selection::NativeTarget;
use crate::sha256::digest_hex;

const QUALIFICATION_FORMAT: &str = "radishaxiom-checker-runtime-qualification-record";
const QUALIFICATION_VERSION: &str = "0.1";
const QUALIFICATION_DOMAIN: &str = "radishaxiom.checker-runtime-qualification-record.v0.1";
const INDEPENDENT_RESULT_DOMAIN: &str = "axiom-independent-check-v0.1:result";

pub const QUALIFICATION_RECORD_FILENAME: &str = "qualification-record-v0.1.jcs";
pub const MAX_QUALIFICATION_RECORD_BYTES: usize = 65_536;
pub const MAX_QUALIFICATION_COMPANION_BYTES: usize = 1_048_576;

const QUALIFICATION_SHAPE: ShapeSpec<'static> = ShapeSpec {
    object_fields: &[
        (
            "$",
            "artifact,companions,digest_domain,document_digest,execution_profile,format,format_version,installation_receipt_digest,launcher_policy,qualified_at,registration,status,target",
        ),
        ("$.artifact", "byte_length,raw_sha256"),
        (
            "$.companions[]",
            "byte_length,document_digest,outcome,raw_sha256,scenario_id",
        ),
        ("$.execution_profile", "id,path,raw_sha256"),
        ("$.launcher_policy", "format,format_version,policy_digest"),
        ("$.registration", "id,record_digest"),
        ("$.target", "executable_format,goarch,goarm64,goos"),
    ],
    array_paths: &["$.companions"],
    bool_paths: &[],
};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct QualificationCompanionInput {
    scenario_id: Box<str>,
    canonical_result: Box<[u8]>,
    document_digest: Box<str>,
    outcome: Box<str>,
    checker_artifact: Box<str>,
    checker_name: Box<str>,
    checker_source: Box<str>,
    checker_toolchain: Box<str>,
    checker_version: Box<str>,
}

impl QualificationCompanionInput {
    pub fn try_new(
        scenario_id: impl Into<Box<str>>,
        canonical_result: impl Into<Box<[u8]>>,
    ) -> Result<Self, DocumentError> {
        let scenario_id = scenario_id.into();
        if scenario_id.contains('/')
            || crate::portable_path::validate_portable_relative_path(&scenario_id).is_err()
        {
            return Err(DocumentError::new("qualification-scenario-id", "$"));
        }
        let canonical_result = canonical_result.into();
        if canonical_result.is_empty() || canonical_result.len() > MAX_QUALIFICATION_COMPANION_BYTES
        {
            return Err(DocumentError::new("qualification-result-length", "$"));
        }
        let value = parse(&canonical_result, true)?;
        let root = as_object(&value, "$result")?;
        let checker = as_object(member(root, "checker", "$result")?, "$result.checker")?;
        let result = as_object(member(root, "result", "$result")?, "$result.result")?;
        let outcome = string_member(result, "kind", "$result.result")?;
        if !matches!(
            outcome,
            "accepted" | "accepted-with-trust" | "incomplete" | "rejected"
        ) {
            return Err(DocumentError::new(
                "qualification-outcome",
                "$result.result.kind",
            ));
        }
        let checker_artifact = string_member(checker, "artifact", "$result.checker")?;
        let checker_source = string_member(checker, "source", "$result.checker")?;
        validate_digest(checker_artifact, "$result.checker.artifact")?;
        validate_digest(checker_source, "$result.checker.source")?;
        Ok(Self {
            scenario_id,
            canonical_result,
            document_digest: domain_digest_value(INDEPENDENT_RESULT_DOMAIN, &value).into(),
            outcome: outcome.into(),
            checker_artifact: checker_artifact.into(),
            checker_name: string_member(checker, "name", "$result.checker")?.into(),
            checker_source: checker_source.into(),
            checker_toolchain: string_member(checker, "toolchain", "$result.checker")?.into(),
            checker_version: string_member(checker, "version", "$result.checker")?.into(),
        })
    }

    pub fn scenario_id(&self) -> &str {
        &self.scenario_id
    }

    pub fn canonical_result(&self) -> &[u8] {
        &self.canonical_result
    }

    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }

    pub fn raw_sha256(&self) -> String {
        format!("sha256:{}", digest_hex(&self.canonical_result))
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct QualificationArtifacts {
    qualification_record: Box<[u8]>,
    document_digest: Box<str>,
    companions: Vec<QualificationCompanionInput>,
    registration_digest: Box<str>,
}

impl QualificationArtifacts {
    pub fn validate(
        policy: &LauncherPolicy,
        record: &RegistrationRecord,
        installation_receipt: &InstallationReceipt,
        qualification_record: impl Into<Box<[u8]>>,
        mut companions: Vec<QualificationCompanionInput>,
    ) -> Result<Self, DocumentError> {
        if record.status() != RegistrationStatus::RegisteredInactive {
            return Err(DocumentError::new(
                "qualification-requires-registered-inactive",
                "$.registration.status",
            ));
        }
        parse_installation_receipt(installation_receipt.canonical_bytes(), policy, record)?;
        let qualification_record = qualification_record.into();
        if qualification_record.is_empty()
            || qualification_record.len() > MAX_QUALIFICATION_RECORD_BYTES
        {
            return Err(DocumentError::new("qualification-record-length", "$"));
        }
        let value = parse(&qualification_record, true)?;
        validate_shape(&value, &QUALIFICATION_SHAPE)?;
        let root = as_object(&value, "$")?;
        expect_string(
            root,
            "format",
            QUALIFICATION_FORMAT,
            "$",
            "qualification-format",
        )?;
        expect_string(
            root,
            "format_version",
            QUALIFICATION_VERSION,
            "$",
            "qualification-version",
        )?;
        expect_string(
            root,
            "digest_domain",
            QUALIFICATION_DOMAIN,
            "$",
            "qualification-domain",
        )?;
        expect_string(
            root,
            "status",
            "qualified-installed-inactive",
            "$",
            "qualification-status",
        )?;
        if !valid_utc_timestamp(string_member(root, "qualified_at", "$")?) {
            return Err(DocumentError::new(
                "invalid-qualification-time",
                "$.qualified_at",
            ));
        }
        let stored_digest = string_member(root, "document_digest", "$")?;
        validate_digest(stored_digest, "$.document_digest")?;
        if stored_digest != domain_digest(QUALIFICATION_DOMAIN, &value, "document_digest")? {
            return Err(DocumentError::new(
                "qualification-document-digest",
                "$.document_digest",
            ));
        }
        let installation_digest = string_member(root, "installation_receipt_digest", "$")?;
        validate_digest(installation_digest, "$.installation_receipt_digest")?;
        if installation_digest != installation_receipt.document_digest() {
            return Err(DocumentError::new(
                "qualification-receipt-binding",
                "$.installation_receipt_digest",
            ));
        }

        validate_artifact(root, record)?;
        validate_registration(root, record)?;
        validate_target(root, record.target())?;
        validate_policy(root, policy)?;
        validate_execution_profile(root, policy)?;

        companions.sort_by(|left, right| left.scenario_id.cmp(&right.scenario_id));
        if companions.len() != policy.qualification_scenarios().len()
            || companions
                .windows(2)
                .any(|pair| pair[0].scenario_id == pair[1].scenario_id)
        {
            return Err(DocumentError::new(
                "qualification-scenario-set",
                "$.companions",
            ));
        }
        validate_companion_inputs(policy, record, &companions)?;
        validate_companion_rows(root, &companions)?;

        Ok(Self {
            qualification_record,
            document_digest: stored_digest.into(),
            companions,
            registration_digest: record.document_digest().into(),
        })
    }

    pub fn qualification_record(&self) -> &[u8] {
        &self.qualification_record
    }

    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }

    pub fn companions(&self) -> &[QualificationCompanionInput] {
        &self.companions
    }

    pub(crate) fn registration_digest(&self) -> &str {
        &self.registration_digest
    }
}

fn validate_artifact(
    root: &[(String, Value)],
    record: &RegistrationRecord,
) -> Result<(), DocumentError> {
    let artifact = as_object(member(root, "artifact", "$")?, "$.artifact")?;
    if parse_decimal(
        string_member(artifact, "byte_length", "$.artifact")?,
        "$.artifact.byte_length",
    )? != record.artifact().byte_length()
        || string_member(artifact, "raw_sha256", "$.artifact")? != record.artifact().raw_sha256()
    {
        return Err(DocumentError::new(
            "qualification-artifact-binding",
            "$.artifact",
        ));
    }
    validate_digest(
        string_member(artifact, "raw_sha256", "$.artifact")?,
        "$.artifact.raw_sha256",
    )
}

fn validate_registration(
    root: &[(String, Value)],
    record: &RegistrationRecord,
) -> Result<(), DocumentError> {
    let registration = as_object(member(root, "registration", "$")?, "$.registration")?;
    if string_member(registration, "id", "$.registration")? != record.id()
        || string_member(registration, "record_digest", "$.registration")?
            != record.document_digest()
    {
        return Err(DocumentError::new(
            "qualification-registration-binding",
            "$.registration",
        ));
    }
    validate_digest(
        string_member(registration, "record_digest", "$.registration")?,
        "$.registration.record_digest",
    )
}

fn validate_target(root: &[(String, Value)], expected: &NativeTarget) -> Result<(), DocumentError> {
    let actual = NativeTarget::from_value(member(root, "target", "$")?, "$.target")?;
    if &actual == expected {
        Ok(())
    } else {
        Err(DocumentError::new(
            "qualification-target-binding",
            "$.target",
        ))
    }
}

fn validate_policy(root: &[(String, Value)], policy: &LauncherPolicy) -> Result<(), DocumentError> {
    let value = as_object(member(root, "launcher_policy", "$")?, "$.launcher_policy")?;
    if string_member(value, "format", "$.launcher_policy")?
        != "radishaxiom-checker-runtime-launcher-policy"
        || string_member(value, "format_version", "$.launcher_policy")? != "0.3"
        || string_member(value, "policy_digest", "$.launcher_policy")? != policy.document_digest()
    {
        return Err(DocumentError::new(
            "qualification-policy-binding",
            "$.launcher_policy",
        ));
    }
    validate_digest(
        string_member(value, "policy_digest", "$.launcher_policy")?,
        "$.launcher_policy.policy_digest",
    )
}

fn validate_execution_profile(
    root: &[(String, Value)],
    policy: &LauncherPolicy,
) -> Result<(), DocumentError> {
    let value = as_object(
        member(root, "execution_profile", "$")?,
        "$.execution_profile",
    )?;
    let expected = policy.execution_profile();
    if string_member(value, "id", "$.execution_profile")? != &*expected.id
        || string_member(value, "path", "$.execution_profile")? != &*expected.path
        || string_member(value, "raw_sha256", "$.execution_profile")? != &*expected.raw_sha256
    {
        return Err(DocumentError::new(
            "qualification-execution-profile-binding",
            "$.execution_profile",
        ));
    }
    validate_digest(
        string_member(value, "raw_sha256", "$.execution_profile")?,
        "$.execution_profile.raw_sha256",
    )
}

fn validate_companion_inputs(
    policy: &LauncherPolicy,
    record: &RegistrationRecord,
    companions: &[QualificationCompanionInput],
) -> Result<(), DocumentError> {
    let checker = record.checker();
    for (input, expected) in companions.iter().zip(policy.qualification_scenarios()) {
        if input.scenario_id.as_ref() != expected.id.as_ref()
            || input.canonical_result.len() as u64 != expected.byte_length
            || input.raw_sha256() != expected.raw_sha256.as_ref()
            || input.outcome.as_ref() != expected.outcome.as_ref()
        {
            return Err(DocumentError::new(
                "qualification-companion-policy-binding",
                format!("$.companions.{}", input.scenario_id),
            ));
        }
        if input.checker_artifact.as_ref() != record.artifact().raw_sha256()
            || input.checker_name.as_ref() != checker.implementation()
            || input.checker_source.as_ref() != checker.source()
            || input.checker_toolchain.as_ref() != checker.toolchain()
            || input.checker_version.as_ref() != checker.version()
        {
            return Err(DocumentError::new(
                "qualification-checker-identity",
                format!("$.companions.{}", input.scenario_id),
            ));
        }
    }
    Ok(())
}

fn validate_companion_rows(
    root: &[(String, Value)],
    companions: &[QualificationCompanionInput],
) -> Result<(), DocumentError> {
    let rows = as_array(member(root, "companions", "$")?, "$.companions")?;
    if rows.len() != companions.len() {
        return Err(DocumentError::new(
            "qualification-scenario-set",
            "$.companions",
        ));
    }
    for (index, (row, input)) in rows.iter().zip(companions).enumerate() {
        let path = format!("$.companions[{index}]");
        let row = as_object(row, &path)?;
        if string_member(row, "scenario_id", &path)? != input.scenario_id.as_ref()
            || parse_decimal(
                string_member(row, "byte_length", &path)?,
                &format!("{path}.byte_length"),
            )? != input.canonical_result.len() as u64
            || string_member(row, "raw_sha256", &path)? != input.raw_sha256()
            || string_member(row, "document_digest", &path)? != input.document_digest.as_ref()
            || string_member(row, "outcome", &path)? != input.outcome.as_ref()
        {
            return Err(DocumentError::new(
                "qualification-companion-record-binding",
                path,
            ));
        }
        validate_digest(
            string_member(row, "raw_sha256", &path)?,
            &format!("{path}.raw_sha256"),
        )?;
        validate_digest(
            string_member(row, "document_digest", &path)?,
            &format!("{path}.document_digest"),
        )?;
    }
    Ok(())
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
