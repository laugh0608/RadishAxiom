use crate::canonical::{
    DocumentError, ShapeSpec, Value, as_object, canonical_bytes, domain_digest,
    domain_digest_value, member, parse_decimal, string_member, validate_digest, validate_shape,
};
use crate::receipt::valid_utc_timestamp;
use crate::registration::RegistrationRecord;

const OBSERVATION_FORMAT: &str = "radishaxiom-checker-runtime-bounded-observation";
const OBSERVATION_VERSION: &str = "0.1";
const ATTEMPT_FORMAT: &str = "radishaxiom-checker-runtime-attempt";
const ATTEMPT_VERSION: &str = "0.1";
const ATTEMPT_DOMAIN: &str = "radishaxiom.checker-runtime-attempt.v0.1";

pub const MAX_ATTEMPT_OBSERVATION_BYTES: usize = 4_096;
pub const MAX_ATTEMPTS_PER_REGISTRATION: u64 = 1_000_000;

const ATTEMPT_SHAPE: ShapeSpec<'static> = ShapeSpec {
    object_fields: &[
        (
            "$",
            "digest_domain,document_digest,format,format_version,observation,ordinal,registration",
        ),
        (
            "$.observation",
            "classification,code,format,format_version,observed_at,stage",
        ),
        ("$.registration", "id,record_digest"),
    ],
    array_paths: &[],
    bool_paths: &[],
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AttemptStage {
    Installation,
    Qualification,
    Invocation,
}

impl AttemptStage {
    fn as_str(self) -> &'static str {
        match self {
            Self::Installation => "installation",
            Self::Qualification => "qualification",
            Self::Invocation => "invocation",
        }
    }

    fn parse(value: &str) -> Result<Self, DocumentError> {
        match value {
            "installation" => Ok(Self::Installation),
            "qualification" => Ok(Self::Qualification),
            "invocation" => Ok(Self::Invocation),
            _ => Err(DocumentError::new("attempt-stage", "$.observation.stage")),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AttemptClassification {
    InstallationFailed,
    QualificationFailed,
    ProcessFailure,
    IdentityFailure,
    ResourceExhausted,
}

impl AttemptClassification {
    fn as_str(self) -> &'static str {
        match self {
            Self::InstallationFailed => "installation-failed",
            Self::QualificationFailed => "qualification-failed",
            Self::ProcessFailure => "process-failure",
            Self::IdentityFailure => "identity-failure",
            Self::ResourceExhausted => "resource-exhausted",
        }
    }

    fn parse(value: &str) -> Result<Self, DocumentError> {
        match value {
            "installation-failed" => Ok(Self::InstallationFailed),
            "qualification-failed" => Ok(Self::QualificationFailed),
            "process-failure" => Ok(Self::ProcessFailure),
            "identity-failure" => Ok(Self::IdentityFailure),
            "resource-exhausted" => Ok(Self::ResourceExhausted),
            _ => Err(DocumentError::new(
                "attempt-classification",
                "$.observation.classification",
            )),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BoundedAttemptObservation {
    value: Value,
    canonical: Box<[u8]>,
    stage: AttemptStage,
    classification: AttemptClassification,
    code: Box<str>,
    observed_at: Box<str>,
}

impl BoundedAttemptObservation {
    pub fn try_new(
        stage: AttemptStage,
        classification: AttemptClassification,
        code: impl Into<Box<str>>,
        observed_at: impl Into<Box<str>>,
    ) -> Result<Self, DocumentError> {
        let code = code.into();
        let observed_at = observed_at.into();
        validate_stage_classification(stage, classification)?;
        validate_code(&code)?;
        if !valid_utc_timestamp(&observed_at) {
            return Err(DocumentError::new(
                "invalid-attempt-time",
                "$.observation.observed_at",
            ));
        }
        let value = object([
            ("classification", string(classification.as_str())),
            ("code", string(&*code)),
            ("format", string(OBSERVATION_FORMAT)),
            ("format_version", string(OBSERVATION_VERSION)),
            ("observed_at", string(&*observed_at)),
            ("stage", string(stage.as_str())),
        ]);
        let canonical = canonical_bytes(&value).into_boxed_slice();
        if canonical.len() > MAX_ATTEMPT_OBSERVATION_BYTES {
            return Err(DocumentError::new(
                "attempt-observation-too-large",
                "$.observation",
            ));
        }
        Ok(Self {
            value,
            canonical,
            stage,
            classification,
            code,
            observed_at,
        })
    }

    pub fn canonical_bytes(&self) -> &[u8] {
        &self.canonical
    }

    pub fn stage(&self) -> AttemptStage {
        self.stage
    }

    pub fn classification(&self) -> AttemptClassification {
        self.classification
    }

    pub fn code(&self) -> &str {
        &self.code
    }

    pub fn observed_at(&self) -> &str {
        &self.observed_at
    }

    fn from_value(value: &Value) -> Result<Self, DocumentError> {
        let object = as_object(value, "$.observation")?;
        expect_string(
            object,
            "format",
            OBSERVATION_FORMAT,
            "$.observation",
            "attempt-observation-format",
        )?;
        expect_string(
            object,
            "format_version",
            OBSERVATION_VERSION,
            "$.observation",
            "attempt-observation-version",
        )?;
        Self::try_new(
            AttemptStage::parse(string_member(object, "stage", "$.observation")?)?,
            AttemptClassification::parse(string_member(
                object,
                "classification",
                "$.observation",
            )?)?,
            string_member(object, "code", "$.observation")?,
            string_member(object, "observed_at", "$.observation")?,
        )
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct AttemptDocument {
    canonical: Box<[u8]>,
    document_digest: Box<str>,
    ordinal: u64,
}

impl AttemptDocument {
    pub(crate) fn build(
        record: &RegistrationRecord,
        ordinal: u64,
        observation: &BoundedAttemptObservation,
    ) -> Result<Self, DocumentError> {
        if ordinal >= MAX_ATTEMPTS_PER_REGISTRATION {
            return Err(DocumentError::new("attempt-capacity", "$.ordinal"));
        }
        let mut members = vec![
            ("digest_domain".into(), string(ATTEMPT_DOMAIN)),
            ("format".into(), string(ATTEMPT_FORMAT)),
            ("format_version".into(), string(ATTEMPT_VERSION)),
            ("observation".into(), observation.value.clone()),
            ("ordinal".into(), string(ordinal.to_string())),
            (
                "registration".into(),
                object([
                    ("id", string(record.id())),
                    ("record_digest", string(record.document_digest())),
                ]),
            ),
        ];
        let body = Value::Object(members.clone());
        let document_digest = domain_digest_value(ATTEMPT_DOMAIN, &body);
        members.insert(1, ("document_digest".into(), string(&document_digest)));
        let canonical = canonical_bytes(&Value::Object(members)).into_boxed_slice();
        Ok(Self {
            canonical,
            document_digest: document_digest.into(),
            ordinal,
        })
    }

    pub(crate) fn parse(bytes: &[u8], record: &RegistrationRecord) -> Result<Self, DocumentError> {
        let value = crate::canonical::parse(bytes, true)?;
        validate_shape(&value, &ATTEMPT_SHAPE)?;
        let root = as_object(&value, "$")?;
        expect_string(root, "digest_domain", ATTEMPT_DOMAIN, "$", "attempt-domain")?;
        expect_string(root, "format", ATTEMPT_FORMAT, "$", "attempt-format")?;
        expect_string(
            root,
            "format_version",
            ATTEMPT_VERSION,
            "$",
            "attempt-version",
        )?;
        let stored_digest = string_member(root, "document_digest", "$")?;
        validate_digest(stored_digest, "$.document_digest")?;
        if stored_digest != domain_digest(ATTEMPT_DOMAIN, &value, "document_digest")? {
            return Err(DocumentError::new(
                "attempt-document-digest",
                "$.document_digest",
            ));
        }
        let registration = as_object(member(root, "registration", "$")?, "$.registration")?;
        if string_member(registration, "id", "$.registration")? != record.id()
            || string_member(registration, "record_digest", "$.registration")?
                != record.document_digest()
        {
            return Err(DocumentError::new(
                "attempt-registration-binding",
                "$.registration",
            ));
        }
        validate_digest(
            string_member(registration, "record_digest", "$.registration")?,
            "$.registration.record_digest",
        )?;
        let ordinal = parse_decimal(string_member(root, "ordinal", "$")?, "$.ordinal")?;
        if ordinal >= MAX_ATTEMPTS_PER_REGISTRATION {
            return Err(DocumentError::new("attempt-capacity", "$.ordinal"));
        }
        let observation = BoundedAttemptObservation::from_value(member(root, "observation", "$")?)?;
        if canonical_bytes(&observation.value).len() > MAX_ATTEMPT_OBSERVATION_BYTES {
            return Err(DocumentError::new(
                "attempt-observation-too-large",
                "$.observation",
            ));
        }
        Ok(Self {
            canonical: bytes.into(),
            document_digest: stored_digest.into(),
            ordinal,
        })
    }

    pub(crate) fn canonical_bytes(&self) -> &[u8] {
        &self.canonical
    }

    pub(crate) fn document_digest(&self) -> &str {
        &self.document_digest
    }

    pub(crate) fn ordinal(&self) -> u64 {
        self.ordinal
    }
}

fn validate_stage_classification(
    stage: AttemptStage,
    classification: AttemptClassification,
) -> Result<(), DocumentError> {
    let valid = match stage {
        AttemptStage::Installation => matches!(
            classification,
            AttemptClassification::InstallationFailed | AttemptClassification::ResourceExhausted
        ),
        AttemptStage::Qualification => matches!(
            classification,
            AttemptClassification::QualificationFailed
                | AttemptClassification::ProcessFailure
                | AttemptClassification::IdentityFailure
                | AttemptClassification::ResourceExhausted
        ),
        AttemptStage::Invocation => matches!(
            classification,
            AttemptClassification::ProcessFailure
                | AttemptClassification::IdentityFailure
                | AttemptClassification::ResourceExhausted
        ),
    };
    if valid {
        Ok(())
    } else {
        Err(DocumentError::new(
            "attempt-stage-classification",
            "$.observation.classification",
        ))
    }
}

fn validate_code(code: &str) -> Result<(), DocumentError> {
    if code.is_empty()
        || code.len() > 64
        || !code
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
        || code.starts_with('-')
        || code.ends_with('-')
        || code.contains("--")
    {
        return Err(DocumentError::new("attempt-code", "$.observation.code"));
    }
    Ok(())
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
    use super::{AttemptClassification, AttemptDocument, AttemptStage, BoundedAttemptObservation};
    use crate::canonical::{Value, canonical_bytes, domain_digest, parse};
    use crate::parse_registration_record;

    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));
    const REGISTRATION_DOMAIN: &str = "radishaxiom.checker-runtime-payload-registration.v0.1";

    #[test]
    fn bounded_observation_has_no_free_form_payload() {
        let observation = BoundedAttemptObservation::try_new(
            AttemptStage::Qualification,
            AttemptClassification::QualificationFailed,
            "qualification-result-digest",
            "2026-09-01T10:00:00Z",
        )
        .unwrap();
        assert_eq!(observation.stage(), AttemptStage::Qualification);
        assert!(!observation.canonical_bytes().contains(&b'/'));

        for invalid in [
            "",
            "UPPER",
            "absolute/path",
            "environment_value",
            "two--codes",
        ] {
            assert!(
                BoundedAttemptObservation::try_new(
                    AttemptStage::Qualification,
                    AttemptClassification::QualificationFailed,
                    invalid,
                    "2026-09-01T10:00:00Z",
                )
                .is_err()
            );
        }
        assert!(
            BoundedAttemptObservation::try_new(
                AttemptStage::Installation,
                AttemptClassification::IdentityFailure,
                "identity-drift",
                "2026-09-01T10:00:00Z",
            )
            .is_err()
        );
    }

    #[test]
    fn attempt_document_is_canonical_and_registration_bound() {
        let record = parse_registration_record(RECORD).unwrap();
        let observation = BoundedAttemptObservation::try_new(
            AttemptStage::Invocation,
            AttemptClassification::ProcessFailure,
            "stdout-truncated",
            "2026-09-01T10:00:00Z",
        )
        .unwrap();
        let attempt = AttemptDocument::build(&record, 0, &observation).unwrap();
        assert_eq!(
            AttemptDocument::parse(attempt.canonical_bytes(), &record).unwrap(),
            attempt
        );

        let mut different = parse(RECORD, false).unwrap();
        {
            let Value::Object(root) = &mut different else {
                unreachable!()
            };
            let (_, Value::Object(registration)) = root
                .iter_mut()
                .find(|(name, _)| name == "registration")
                .unwrap()
            else {
                unreachable!()
            };
            let (_, status) = registration
                .iter_mut()
                .find(|(name, _)| name == "status")
                .unwrap();
            *status = Value::String("active".into());
        }
        let digest = domain_digest(REGISTRATION_DOMAIN, &different, "record_digest").unwrap();
        let Value::Object(root) = &mut different else {
            unreachable!()
        };
        let (_, stored) = root
            .iter_mut()
            .find(|(name, _)| name == "record_digest")
            .unwrap();
        *stored = Value::String(digest);
        let different = parse_registration_record(&canonical_bytes(&different)).unwrap();
        assert_eq!(
            AttemptDocument::parse(attempt.canonical_bytes(), &different)
                .unwrap_err()
                .code(),
            "attempt-registration-binding"
        );
    }
}
