use std::fmt;

use crate::canonical::{
    DocumentError, Value, as_array, as_object, domain_digest_value, member, parse, string_member,
    validate_digest,
};
use crate::registration::RegistrationRecord;
use crate::sha256::digest_hex;

const RESULT_DOMAIN: &str = "axiom-independent-check-v0.1:result";
const CHECK_DOMAIN: &str = "axiom-independent-check-v0.1:check";
const RESULT_VERSION: &str = "0.1";
const CHECKER_NAME: &str = "radishaxiom-independent-checker-go";
const CHECKER_TOOLCHAIN: &str = "go1.26.7";
const INVOCATION_FAILURE_FORMAT: &str = "axiom-checker-invocation-failure";
const INVOCATION_FAILURE_VERSION: &str = "0.1";

pub const MAX_INDEPENDENT_RESULT_BYTES: usize = 1_048_576;
pub const MAX_INVOCATION_FAILURE_BYTES: usize = 65_536;

const REQUIRED_TCB_CATEGORIES: [&str; 4] = [
    "canonicalization",
    "checker-core",
    "cryptographic-primitive",
    "rule-interpreter",
];

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IndependentDocumentBinding {
    content_digest: Box<str>,
    document_digest: Option<Box<str>>,
}

impl IndependentDocumentBinding {
    pub fn try_available(
        content_digest: impl Into<Box<str>>,
        document_digest: impl Into<Box<str>>,
    ) -> Result<Self, DocumentError> {
        let content_digest = content_digest.into();
        let document_digest = document_digest.into();
        validate_digest(&content_digest, "$.content_digest")?;
        validate_digest(&document_digest, "$.document_digest")?;
        Ok(Self {
            content_digest,
            document_digest: Some(document_digest),
        })
    }

    pub fn try_unavailable(content_digest: impl Into<Box<str>>) -> Result<Self, DocumentError> {
        let content_digest = content_digest.into();
        validate_digest(&content_digest, "$.content_digest")?;
        Ok(Self {
            content_digest,
            document_digest: None,
        })
    }

    pub fn content_digest(&self) -> &str {
        &self.content_digest
    }

    pub fn document_digest(&self) -> Option<&str> {
        self.document_digest.as_deref()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum IndependentCheckOutcome {
    Accepted,
    AcceptedWithTrust,
    Incomplete,
    Rejected,
}

impl IndependentCheckOutcome {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Accepted => "accepted",
            Self::AcceptedWithTrust => "accepted-with-trust",
            Self::Incomplete => "incomplete",
            Self::Rejected => "rejected",
        }
    }
}

impl fmt::Display for IndependentCheckOutcome {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.as_str())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ConsumedIndependentResult {
    canonical_result: Box<[u8]>,
    document_digest: Box<str>,
    registration_digest: Box<str>,
    request: IndependentDocumentBinding,
    evidence: IndependentDocumentBinding,
    outcome: IndependentCheckOutcome,
    result_refs: Vec<Box<str>>,
    missing_artifacts: Vec<Box<str>>,
    remaining_trust: Vec<Box<str>>,
}

impl ConsumedIndependentResult {
    pub fn canonical_result(&self) -> &[u8] {
        &self.canonical_result
    }

    pub fn raw_sha256(&self) -> String {
        format!("sha256:{}", digest_hex(&self.canonical_result))
    }

    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }

    pub fn registration_digest(&self) -> &str {
        &self.registration_digest
    }

    pub fn request(&self) -> &IndependentDocumentBinding {
        &self.request
    }

    pub fn evidence(&self) -> &IndependentDocumentBinding {
        &self.evidence
    }

    pub fn outcome(&self) -> IndependentCheckOutcome {
        self.outcome
    }

    pub fn result_refs(&self) -> impl ExactSizeIterator<Item = &str> {
        self.result_refs.iter().map(Box::as_ref)
    }

    pub fn missing_artifacts(&self) -> impl ExactSizeIterator<Item = &str> {
        self.missing_artifacts.iter().map(Box::as_ref)
    }

    pub fn remaining_trust(&self) -> impl ExactSizeIterator<Item = &str> {
        self.remaining_trust.iter().map(Box::as_ref)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CheckerInvocationFailure {
    canonical_failure: Box<[u8]>,
    code: Box<str>,
}

impl CheckerInvocationFailure {
    pub fn canonical_failure(&self) -> &[u8] {
        &self.canonical_failure
    }

    pub fn code(&self) -> &str {
        &self.code
    }
}

pub fn consume_independent_result(
    canonical_result: impl Into<Box<[u8]>>,
    record: &RegistrationRecord,
    request: &IndependentDocumentBinding,
    evidence: &IndependentDocumentBinding,
) -> Result<ConsumedIndependentResult, DocumentError> {
    let canonical_result = canonical_result.into();
    if canonical_result.is_empty() || canonical_result.len() > MAX_INDEPENDENT_RESULT_BYTES {
        return Err(DocumentError::new("independent-result-length", "$"));
    }
    if request.document_digest().is_none() {
        return Err(DocumentError::new(
            "result-request-identity",
            "$.request.document_digest",
        ));
    }
    let value = parse(&canonical_result, true)?;
    let parsed = validate_result_document(&value)?;
    bind_checker(&parsed.checker, record)?;
    bind_document(
        &parsed.request,
        request,
        "result-request-identity",
        "$.request",
    )?;
    bind_document(
        &parsed.evidence,
        evidence,
        "result-evidence-identity",
        "$.evidence",
    )?;
    bind_tcb(&parsed.tcb, record)?;

    Ok(ConsumedIndependentResult {
        canonical_result,
        document_digest: domain_digest_value(RESULT_DOMAIN, &value).into(),
        registration_digest: record.document_digest().into(),
        request: request.clone(),
        evidence: evidence.clone(),
        outcome: parsed.outcome,
        result_refs: parsed.result_refs,
        missing_artifacts: parsed.missing_artifacts,
        remaining_trust: parsed.remaining_trust,
    })
}

pub fn parse_checker_invocation_failure(
    canonical_failure: impl Into<Box<[u8]>>,
    request: &IndependentDocumentBinding,
) -> Result<CheckerInvocationFailure, DocumentError> {
    let canonical_failure = canonical_failure.into();
    if canonical_failure.is_empty() || canonical_failure.len() > MAX_INVOCATION_FAILURE_BYTES {
        return Err(DocumentError::new("invocation-failure-length", "$"));
    }
    let value = parse(&canonical_failure, true)?;
    let root = as_object(&value, "$")?;
    require_fields(
        root,
        &["code", "format", "format_version", "request", "result"],
        "$",
    )?;
    expect_string(
        root,
        "format",
        INVOCATION_FAILURE_FORMAT,
        "$",
        "invocation-failure-format",
    )?;
    expect_string(
        root,
        "format_version",
        INVOCATION_FAILURE_VERSION,
        "$",
        "unsupported-version",
    )?;
    expect_string(
        root,
        "result",
        "not-produced",
        "$",
        "invocation-failure-result",
    )?;
    let code = string_member(root, "code", "$")?;
    if !valid_stable_code(code) {
        return Err(DocumentError::new("invocation-failure-code", "$.code"));
    }

    let request_value = as_object(member(root, "request", "$")?, "$.request")?;
    require_fields(
        request_value,
        &["content_digest", "document_digest"],
        "$.request",
    )?;
    let content_digest = string_member(request_value, "content_digest", "$.request")?;
    let document_digest = string_member(request_value, "document_digest", "$.request")?;
    validate_digest(content_digest, "$.request.content_digest")?;
    validate_digest(document_digest, "$.request.document_digest")?;
    if request.content_digest() != content_digest
        || request.document_digest() != Some(document_digest)
    {
        return Err(DocumentError::new(
            "invocation-failure-request-identity",
            "$.request",
        ));
    }

    Ok(CheckerInvocationFailure {
        canonical_failure,
        code: code.into(),
    })
}

#[derive(Debug)]
struct ParsedResult {
    checker: ParsedChecker,
    request: ParsedBinding,
    evidence: ParsedBinding,
    tcb: Vec<ParsedTcb>,
    outcome: IndependentCheckOutcome,
    result_refs: Vec<Box<str>>,
    missing_artifacts: Vec<Box<str>>,
    remaining_trust: Vec<Box<str>>,
}

#[derive(Debug)]
struct ParsedChecker {
    artifact: Box<str>,
    name: Box<str>,
    source: Box<str>,
    toolchain: Box<str>,
    version: Box<str>,
}

#[derive(Debug, Eq, PartialEq)]
struct ParsedBinding {
    content_digest: Box<str>,
    document_digest: Option<Box<str>>,
}

#[derive(Debug)]
struct ParsedTcb {
    artifact: Box<str>,
    category: Box<str>,
    version: Box<str>,
}

fn validate_result_document(value: &Value) -> Result<ParsedResult, DocumentError> {
    let root = as_object(value, "$")?;
    require_fields(
        root,
        &[
            "checker",
            "checks",
            "evidence",
            "missing_artifacts",
            "remaining_trust",
            "request",
            "result",
            "result_version",
            "tcb",
        ],
        "$",
    )?;
    expect_string(
        root,
        "result_version",
        RESULT_VERSION,
        "$",
        "unsupported-version",
    )?;

    let checker = validate_checker(member(root, "checker", "$")?)?;
    let evidence = validate_binding(member(root, "evidence", "$")?, "$.evidence")?;
    let request = validate_binding(member(root, "request", "$")?, "$.request")?;
    let missing_artifacts = validate_digest_array(
        member(root, "missing_artifacts", "$")?,
        "$.missing_artifacts",
        false,
    )?;
    let remaining_trust = validate_digest_array(
        member(root, "remaining_trust", "$")?,
        "$.remaining_trust",
        false,
    )?;
    let checks = validate_checks(member(root, "checks", "$")?)?;
    let tcb = validate_tcb(member(root, "tcb", "$")?)?;
    let (outcome, result_refs) = validate_result_variant(member(root, "result", "$")?, &checks)?;

    validate_aggregation(
        outcome,
        &result_refs,
        &checks,
        &missing_artifacts,
        &remaining_trust,
        &evidence,
        &request,
    )?;

    Ok(ParsedResult {
        checker,
        request,
        evidence,
        tcb,
        outcome,
        result_refs,
        missing_artifacts,
        remaining_trust,
    })
}

fn validate_checker(value: &Value) -> Result<ParsedChecker, DocumentError> {
    let checker = as_object(value, "$.checker")?;
    require_fields(
        checker,
        &["artifact", "name", "source", "toolchain", "version"],
        "$.checker",
    )?;
    let artifact = string_member(checker, "artifact", "$.checker")?;
    let name = string_member(checker, "name", "$.checker")?;
    let source = string_member(checker, "source", "$.checker")?;
    let toolchain = string_member(checker, "toolchain", "$.checker")?;
    let version = string_member(checker, "version", "$.checker")?;
    validate_digest(artifact, "$.checker.artifact")?;
    validate_digest(source, "$.checker.source")?;
    if name != CHECKER_NAME
        || toolchain != CHECKER_TOOLCHAIN
        || version.is_empty()
        || version == "latest"
    {
        return Err(DocumentError::new("checker-identity", "$.checker"));
    }
    Ok(ParsedChecker {
        artifact: artifact.into(),
        name: name.into(),
        source: source.into(),
        toolchain: toolchain.into(),
        version: version.into(),
    })
}

fn validate_binding(value: &Value, path: &str) -> Result<ParsedBinding, DocumentError> {
    let binding = as_object(value, path)?;
    require_fields(binding, &["content_digest", "document_digest"], path)?;
    let content_digest = string_member(binding, "content_digest", path)?;
    validate_digest(content_digest, &format!("{path}.content_digest"))?;
    let document_path = format!("{path}.document_digest");
    let document = as_object(member(binding, "document_digest", path)?, &document_path)?;
    let kind = string_member(document, "kind", &document_path)?;
    let document_digest = match kind {
        "available" => {
            require_fields(document, &["kind", "value"], &document_path)?;
            let digest = string_member(document, "value", &document_path)?;
            validate_digest(digest, &format!("{document_path}.value"))?;
            Some(digest.into())
        }
        "unavailable" => {
            require_fields(document, &["kind"], &document_path)?;
            None
        }
        _ => {
            return Err(DocumentError::new(
                "unknown-tag",
                format!("{document_path}.kind"),
            ));
        }
    };
    Ok(ParsedBinding {
        content_digest: content_digest.into(),
        document_digest,
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum CheckOutcome {
    Incomplete,
    Passed,
    Rejected,
    Trusted,
}

#[derive(Debug)]
struct ParsedCheck {
    id: Box<str>,
    outcome: CheckOutcome,
}

fn validate_checks(value: &Value) -> Result<Vec<ParsedCheck>, DocumentError> {
    let values = as_array(value, "$.checks")?;
    if values.is_empty() {
        return Err(DocumentError::new("missing-required-member", "$.checks"));
    }
    let mut checks = Vec::with_capacity(values.len());
    let mut previous_id: Option<&str> = None;
    for (index, value) in values.iter().enumerate() {
        let path = format!("$.checks[{index}]");
        let check = as_object(value, &path)?;
        require_fields(check, &["definition", "id"], &path)?;
        let definition_path = format!("{path}.definition");
        let definition_value = member(check, "definition", &path)?;
        let definition = as_object(definition_value, &definition_path)?;
        require_fields(
            definition,
            &["codes", "kind", "outcome", "refs"],
            &definition_path,
        )?;
        let kind = string_member(definition, "kind", &definition_path)?;
        let outcome = parse_check_outcome(string_member(definition, "outcome", &definition_path)?)?;
        validate_codes(
            member(definition, "codes", &definition_path)?,
            kind,
            &definition_path,
        )?;
        validate_check_refs(
            member(definition, "refs", &definition_path)?,
            &definition_path,
        )?;
        let expected_id = domain_digest_value(CHECK_DOMAIN, definition_value);
        let stored_id = string_member(check, "id", &path)?;
        validate_digest(stored_id, &format!("{path}.id"))?;
        if stored_id != expected_id {
            return Err(DocumentError::new(
                "check-id-mismatch",
                format!("{path}.id"),
            ));
        }
        if previous_id.is_some_and(|previous| previous >= stored_id) {
            return Err(DocumentError::new("noncanonical-order", "$.checks"));
        }
        previous_id = Some(stored_id);
        checks.push(ParsedCheck {
            id: stored_id.into(),
            outcome,
        });
    }
    Ok(checks)
}

fn validate_codes(value: &Value, kind: &str, path: &str) -> Result<(), DocumentError> {
    if !valid_check_kind(kind) {
        return Err(DocumentError::new("unknown-tag", format!("{path}.kind")));
    }
    let codes_path = format!("{path}.codes");
    let codes = as_array(value, &codes_path)?;
    if codes.is_empty() {
        return Err(DocumentError::new("unknown-tag", codes_path));
    }
    let mut previous: Option<&str> = None;
    for (index, value) in codes.iter().enumerate() {
        let code = crate::canonical::as_string(value, &format!("{codes_path}[{index}]"))?;
        if !valid_check_code(kind, code) {
            return Err(DocumentError::new(
                "unknown-tag",
                format!("{codes_path}[{index}]"),
            ));
        }
        if previous.is_some_and(|previous| previous >= code) {
            return Err(DocumentError::new("noncanonical-order", &codes_path));
        }
        previous = Some(code);
    }
    Ok(())
}

fn validate_check_refs(value: &Value, path: &str) -> Result<(), DocumentError> {
    let refs_path = format!("{path}.refs");
    let refs = as_array(value, &refs_path)?;
    let mut previous: Option<(&str, &str)> = None;
    for (index, value) in refs.iter().enumerate() {
        let item_path = format!("{refs_path}[{index}]");
        let item = as_object(value, &item_path)?;
        require_fields(item, &["kind", "ref"], &item_path)?;
        let kind = string_member(item, "kind", &item_path)?;
        let reference = string_member(item, "ref", &item_path)?;
        if !matches!(
            kind,
            "artifact" | "check" | "evidence-entry" | "obligation" | "request" | "tool" | "trust"
        ) {
            return Err(DocumentError::new(
                "unknown-tag",
                format!("{item_path}.kind"),
            ));
        }
        validate_digest(reference, &format!("{item_path}.ref"))?;
        if previous.is_some_and(|previous| previous >= (kind, reference)) {
            return Err(DocumentError::new("noncanonical-order", refs_path));
        }
        previous = Some((kind, reference));
    }
    Ok(())
}

fn validate_tcb(value: &Value) -> Result<Vec<ParsedTcb>, DocumentError> {
    let values = as_array(value, "$.tcb")?;
    let mut tcb = Vec::with_capacity(values.len());
    let mut previous: Option<(&str, &str)> = None;
    let mut present = [false; REQUIRED_TCB_CATEGORIES.len()];
    for (index, value) in values.iter().enumerate() {
        let path = format!("$.tcb[{index}]");
        let item = as_object(value, &path)?;
        require_fields(item, &["artifact", "category", "version"], &path)?;
        let artifact = string_member(item, "artifact", &path)?;
        let category = string_member(item, "category", &path)?;
        let version = string_member(item, "version", &path)?;
        validate_digest(artifact, &format!("{path}.artifact"))?;
        if !matches!(
            category,
            "canonicalization"
                | "certificate-checker"
                | "checker-core"
                | "cryptographic-primitive"
                | "rule-interpreter"
        ) {
            return Err(DocumentError::new(
                "unknown-tag",
                format!("{path}.category"),
            ));
        }
        if version.is_empty() {
            return Err(DocumentError::new(
                "unsupported-version",
                format!("{path}.version"),
            ));
        }
        if previous.is_some_and(|previous| previous >= (category, artifact)) {
            return Err(DocumentError::new("noncanonical-order", "$.tcb"));
        }
        previous = Some((category, artifact));
        if let Some(position) = REQUIRED_TCB_CATEGORIES
            .iter()
            .position(|required| *required == category)
        {
            present[position] = true;
        }
        tcb.push(ParsedTcb {
            artifact: artifact.into(),
            category: category.into(),
            version: version.into(),
        });
    }
    if present.iter().any(|present| !present) {
        return Err(DocumentError::new("tcb-incomplete", "$.tcb"));
    }
    Ok(tcb)
}

fn validate_result_variant(
    value: &Value,
    checks: &[ParsedCheck],
) -> Result<(IndependentCheckOutcome, Vec<Box<str>>), DocumentError> {
    let result = as_object(value, "$.result")?;
    let kind = string_member(result, "kind", "$.result")?;
    let outcome = match kind {
        "accepted" => {
            require_fields(result, &["kind"], "$.result")?;
            return Ok((IndependentCheckOutcome::Accepted, Vec::new()));
        }
        "accepted-with-trust" => IndependentCheckOutcome::AcceptedWithTrust,
        "incomplete" => IndependentCheckOutcome::Incomplete,
        "rejected" => IndependentCheckOutcome::Rejected,
        _ => return Err(DocumentError::new("unknown-tag", "$.result.kind")),
    };
    require_fields(result, &["kind", "refs"], "$.result")?;
    let refs = validate_digest_array(member(result, "refs", "$.result")?, "$.result.refs", true)?;
    if refs.iter().any(|reference| {
        !checks
            .iter()
            .any(|check| check.id.as_ref() == reference.as_ref())
    }) {
        return Err(DocumentError::new("result-aggregation", "$.result.refs"));
    }
    Ok((outcome, refs))
}

fn validate_aggregation(
    outcome: IndependentCheckOutcome,
    result_refs: &[Box<str>],
    checks: &[ParsedCheck],
    missing_artifacts: &[Box<str>],
    remaining_trust: &[Box<str>],
    evidence: &ParsedBinding,
    request: &ParsedBinding,
) -> Result<(), DocumentError> {
    if outcome != IndependentCheckOutcome::Rejected
        && (evidence.document_digest.is_none() || request.document_digest.is_none())
    {
        return Err(DocumentError::new("result-aggregation", "$.result"));
    }
    let valid = match outcome {
        IndependentCheckOutcome::Accepted => {
            missing_artifacts.is_empty()
                && remaining_trust.is_empty()
                && checks
                    .iter()
                    .all(|check| check.outcome == CheckOutcome::Passed)
        }
        IndependentCheckOutcome::AcceptedWithTrust => {
            missing_artifacts.is_empty()
                && !remaining_trust.is_empty()
                && checks.iter().all(|check| {
                    !matches!(
                        check.outcome,
                        CheckOutcome::Incomplete | CheckOutcome::Rejected
                    )
                })
        }
        IndependentCheckOutcome::Incomplete => {
            !missing_artifacts.is_empty()
                || checks
                    .iter()
                    .any(|check| check.outcome == CheckOutcome::Incomplete)
        }
        IndependentCheckOutcome::Rejected => result_refs.iter().any(|reference| {
            checks.iter().any(|check| {
                check.id.as_ref() == reference.as_ref() && check.outcome == CheckOutcome::Rejected
            })
        }),
    };
    if valid {
        Ok(())
    } else {
        Err(DocumentError::new("result-aggregation", "$.result"))
    }
}

fn validate_digest_array(
    value: &Value,
    path: &str,
    require_nonempty: bool,
) -> Result<Vec<Box<str>>, DocumentError> {
    let values = as_array(value, path)?;
    if require_nonempty && values.is_empty() {
        return Err(DocumentError::new("result-aggregation", path));
    }
    let mut result = Vec::with_capacity(values.len());
    let mut previous: Option<&str> = None;
    for (index, value) in values.iter().enumerate() {
        let digest = crate::canonical::as_string(value, &format!("{path}[{index}]"))?;
        validate_digest(digest, &format!("{path}[{index}]"))?;
        if previous.is_some_and(|previous| previous >= digest) {
            return Err(DocumentError::new("noncanonical-order", path));
        }
        previous = Some(digest);
        result.push(digest.into());
    }
    Ok(result)
}

fn bind_checker(checker: &ParsedChecker, record: &RegistrationRecord) -> Result<(), DocumentError> {
    let expected = record.checker();
    if checker.artifact.as_ref() == record.artifact().raw_sha256()
        && checker.name.as_ref() == expected.implementation()
        && checker.source.as_ref() == expected.source()
        && checker.toolchain.as_ref() == expected.toolchain()
        && checker.version.as_ref() == expected.version()
    {
        Ok(())
    } else {
        Err(DocumentError::new("result-checker-identity", "$.checker"))
    }
}

fn bind_document(
    actual: &ParsedBinding,
    expected: &IndependentDocumentBinding,
    code: &'static str,
    path: &str,
) -> Result<(), DocumentError> {
    if actual.content_digest.as_ref() == expected.content_digest()
        && actual.document_digest.as_deref() == expected.document_digest()
    {
        Ok(())
    } else {
        Err(DocumentError::new(code, path))
    }
}

fn bind_tcb(tcb: &[ParsedTcb], record: &RegistrationRecord) -> Result<(), DocumentError> {
    if tcb.len() != REQUIRED_TCB_CATEGORIES.len() {
        return Err(DocumentError::new("result-tcb-identity", "$.tcb"));
    }
    for (item, expected_category) in tcb.iter().zip(REQUIRED_TCB_CATEGORIES) {
        if item.category.as_ref() != expected_category
            || item.artifact.as_ref() != record.artifact().raw_sha256()
            || item.version.as_ref() != record.checker().version()
        {
            return Err(DocumentError::new("result-tcb-identity", "$.tcb"));
        }
    }
    Ok(())
}

fn parse_check_outcome(value: &str) -> Result<CheckOutcome, DocumentError> {
    match value {
        "incomplete" => Ok(CheckOutcome::Incomplete),
        "passed" => Ok(CheckOutcome::Passed),
        "rejected" => Ok(CheckOutcome::Rejected),
        "trusted" => Ok(CheckOutcome::Trusted),
        _ => Err(DocumentError::new(
            "unknown-tag",
            "$.checks[].definition.outcome",
        )),
    }
}

fn valid_check_kind(kind: &str) -> bool {
    matches!(
        kind,
        "conclusion-recompute"
            | "concrete-check-replay"
            | "counterexample-replay"
            | "identity"
            | "isolation-report"
            | "obligation-reconstruction"
            | "proof-support"
            | "state-support"
            | "strict-parse"
            | "subject"
    )
}

fn valid_check_code(kind: &str, code: &str) -> bool {
    match kind {
        "conclusion-recompute" => matches!(code, "conclusion-mismatch" | "result-aggregation"),
        "concrete-check-replay" => {
            matches!(code, "concrete-check-mismatch" | "host-output-mismatch")
        }
        "counterexample-replay" => {
            matches!(code, "counterexample-invalid" | "minimality-unsupported")
        }
        "identity" => matches!(
            code,
            "artifact-missing"
                | "check-id-mismatch"
                | "digest-mismatch"
                | "duplicate-artifact"
                | "evidence-cardinality"
                | "length-mismatch"
                | "manifest-coverage"
                | "request-binding-mismatch"
        ),
        "isolation-report" => matches!(
            code,
            "checker-identity" | "isolation-boundary-violation" | "tcb-incomplete"
        ),
        "obligation-reconstruction" => code == "obligation-mismatch",
        "proof-support" => matches!(
            code,
            "attestation-not-allowed"
                | "certificate-incomplete"
                | "proof-support-mismatch"
                | "proof-support-unsupported"
        ),
        "state-support" => matches!(code, "invalid-state-support" | "trust-not-allowed"),
        "strict-parse" => matches!(
            code,
            "duplicate-member"
                | "evidence-missing-required-members"
                | "invalid-json"
                | "invalid-utf8"
                | "json-number-or-null"
                | "limit-set-mismatch"
                | "missing-required-member"
                | "noncanonical-json"
                | "noncanonical-order"
                | "unknown-member"
                | "unknown-tag"
                | "unsupported-version"
        ),
        "subject" => matches!(code, "invalid-ir" | "subject-mismatch"),
        _ => false,
    }
}

fn valid_stable_code(code: &str) -> bool {
    !code.is_empty()
        && code.as_bytes()[0].is_ascii_lowercase()
        && code
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
}

fn require_fields(
    object: &[(String, Value)],
    expected: &[&str],
    path: &str,
) -> Result<(), DocumentError> {
    for (name, _) in object {
        if expected.binary_search(&name.as_str()).is_err() {
            return Err(DocumentError::new(
                "unknown-member",
                format!("{path}.{name}"),
            ));
        }
    }
    for name in expected {
        if object
            .binary_search_by(|(actual, _)| actual.as_str().cmp(name))
            .is_err()
        {
            return Err(DocumentError::new(
                "missing-member",
                format!("{path}.{name}"),
            ));
        }
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

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::{Path, PathBuf};

    use super::{
        IndependentCheckOutcome, IndependentDocumentBinding, consume_independent_result,
        parse_checker_invocation_failure, validate_binding, validate_result_document,
    };
    use crate::canonical::{Value, as_object, canonical_bytes, domain_digest_value, member, parse};
    use crate::parse_registration_record;

    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));
    const STRICT_RESULT: &[u8] = include_bytes!(concat!(
        "../../../contracts/independent-check-v0.1/fixtures/",
        "strict-evidence-rejection/expected-result.jcs"
    ));
    const PROCESS_FAILURE: &[u8] = include_bytes!(concat!(
        "../../../contracts/keyed-finite-table-checker-bundles-v0.1/s/",
        "chk-process-01/expected-process-failure.jcs"
    ));

    fn contract_root() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../contracts")
    }

    fn result_paths(root: &Path, output: &mut Vec<PathBuf>) {
        for entry in fs::read_dir(root).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                result_paths(&path, output);
            } else if path
                .file_name()
                .is_some_and(|name| name == "expected-result.jcs")
            {
                output.push(path);
            }
        }
    }

    fn set_string(value: &mut Value, path: &[&str], replacement: &str) {
        let mut current = value;
        for component in &path[..path.len() - 1] {
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
            .iter_mut()
            .find(|(name, _)| name == path[path.len() - 1])
            .unwrap()
            .1 = Value::String(replacement.into());
    }

    fn bind_result_to_record(bytes: &[u8]) -> Vec<u8> {
        let record = parse_registration_record(RECORD).unwrap();
        let checker = record.checker();
        let mut value = parse(bytes, true).unwrap();
        set_string(
            &mut value,
            &["checker", "artifact"],
            record.artifact().raw_sha256(),
        );
        set_string(&mut value, &["checker", "name"], checker.implementation());
        set_string(&mut value, &["checker", "source"], checker.source());
        set_string(&mut value, &["checker", "toolchain"], checker.toolchain());
        set_string(&mut value, &["checker", "version"], checker.version());
        let Value::Object(root) = &mut value else {
            unreachable!();
        };
        let Value::Array(tcb) = &mut root.iter_mut().find(|(name, _)| name == "tcb").unwrap().1
        else {
            unreachable!();
        };
        for item in tcb {
            let Value::Object(item) = item else {
                unreachable!();
            };
            item.iter_mut()
                .find(|(name, _)| name == "artifact")
                .unwrap()
                .1 = Value::String(record.artifact().raw_sha256().into());
            item.iter_mut()
                .find(|(name, _)| name == "version")
                .unwrap()
                .1 = Value::String(checker.version().into());
        }
        canonical_bytes(&value)
    }

    fn accepted_result() -> Vec<u8> {
        let mut value = parse(STRICT_RESULT, true).unwrap();
        let Value::Object(root) = &mut value else {
            unreachable!();
        };
        let Value::Array(checks) = &mut root
            .iter_mut()
            .find(|(name, _)| name == "checks")
            .unwrap()
            .1
        else {
            unreachable!();
        };
        let Value::Object(check) = &mut checks[0] else {
            unreachable!();
        };
        let definition = &mut check
            .iter_mut()
            .find(|(name, _)| name == "definition")
            .unwrap()
            .1;
        let Value::Object(definition_members) = definition else {
            unreachable!();
        };
        definition_members
            .iter_mut()
            .find(|(name, _)| name == "outcome")
            .unwrap()
            .1 = Value::String("passed".into());
        let id = domain_digest_value(super::CHECK_DOMAIN, definition);
        check.iter_mut().find(|(name, _)| name == "id").unwrap().1 = Value::String(id);

        let Value::Object(evidence) = &mut root
            .iter_mut()
            .find(|(name, _)| name == "evidence")
            .unwrap()
            .1
        else {
            unreachable!();
        };
        evidence
            .iter_mut()
            .find(|(name, _)| name == "document_digest")
            .unwrap()
            .1 = Value::Object(vec![
            ("kind".into(), Value::String("available".into())),
            (
                "value".into(),
                Value::String(format!("sha256:{}", "5".repeat(64))),
            ),
        ]);
        root.iter_mut()
            .find(|(name, _)| name == "result")
            .unwrap()
            .1 = Value::Object(vec![("kind".into(), Value::String("accepted".into()))]);
        canonical_bytes(&value)
    }

    fn bindings(bytes: &[u8]) -> (IndependentDocumentBinding, IndependentDocumentBinding) {
        let value = parse(bytes, true).unwrap();
        let root = as_object(&value, "$").unwrap();
        let request = validate_binding(member(root, "request", "$").unwrap(), "$.request").unwrap();
        let evidence =
            validate_binding(member(root, "evidence", "$").unwrap(), "$.evidence").unwrap();
        let convert = |binding: super::ParsedBinding| match binding.document_digest {
            Some(document) => {
                IndependentDocumentBinding::try_available(binding.content_digest, document).unwrap()
            }
            None => IndependentDocumentBinding::try_unavailable(binding.content_digest).unwrap(),
        };
        (convert(request), convert(evidence))
    }

    #[test]
    fn every_public_canonical_result_is_consumed_after_synthetic_identity_binding() {
        let record = parse_registration_record(RECORD).unwrap();
        let mut paths = Vec::new();
        result_paths(&contract_root().join("independent-check-v0.1"), &mut paths);
        result_paths(
            &contract_root().join("keyed-finite-table-checker-bundles-v0.1"),
            &mut paths,
        );
        paths.sort();
        assert_eq!(paths.len(), 28);
        for path in paths {
            let bytes = fs::read(&path).unwrap();
            let value =
                parse(&bytes, true).unwrap_or_else(|error| panic!("{}: {error}", path.display()));
            validate_result_document(&value)
                .unwrap_or_else(|error| panic!("{}: {error}", path.display()));
            let bound = bind_result_to_record(&bytes);
            let (request, evidence) = bindings(&bound);
            consume_independent_result(bound, &record, &request, &evidence)
                .unwrap_or_else(|error| panic!("{}: {error}", path.display()));
        }
        let strict = parse(STRICT_RESULT, true).unwrap();
        assert_eq!(
            domain_digest_value(super::RESULT_DOMAIN, &strict),
            "sha256:24e81c66e17150c70c1b2d2eac50b47f16fc20c6a094111be3410546c7b6e608"
        );
    }

    #[test]
    fn every_public_result_negative_is_rejected_with_locked_code() {
        let root = contract_root().join("independent-check-v0.1/fixtures/negative");
        let cases = [
            (
                "result-accepted-unavailable-document.invalid.jcs",
                "result-aggregation",
            ),
            (
                "result-accepted-with-trust.invalid.jcs",
                "result-aggregation",
            ),
            ("result-check-id-mismatch.invalid.jcs", "check-id-mismatch"),
            (
                "result-incomplete-without-refs.invalid.jcs",
                "result-aggregation",
            ),
            (
                "result-production-checker-name.invalid.jcs",
                "checker-identity",
            ),
            (
                "result-trusted-without-trust.invalid.jcs",
                "result-aggregation",
            ),
            ("result-unsorted-tcb.invalid.jcs", "noncanonical-order"),
        ];
        for (name, expected) in cases {
            let value = parse(&fs::read(root.join(name)).unwrap(), true).unwrap();
            assert_eq!(
                validate_result_document(&value).unwrap_err().code(),
                expected,
                "{name}"
            );
        }
    }

    #[test]
    fn closed_shape_version_registry_and_tcb_fail_closed() {
        let base = parse(STRICT_RESULT, true).unwrap();

        let mut missing = base.clone();
        let Value::Object(root) = &mut missing else {
            unreachable!();
        };
        root.remove(root.iter().position(|(name, _)| name == "checks").unwrap());
        assert_eq!(
            validate_result_document(&missing).unwrap_err().code(),
            "missing-member"
        );

        let mut unknown = base.clone();
        let Value::Object(root) = &mut unknown else {
            unreachable!();
        };
        root.push(("zzz".into(), Value::String("unexpected".into())));
        assert_eq!(
            validate_result_document(&unknown).unwrap_err().code(),
            "unknown-member"
        );

        let mut version = base.clone();
        set_string(&mut version, &["result_version"], "0.2");
        assert_eq!(
            validate_result_document(&version).unwrap_err().code(),
            "unsupported-version"
        );

        let mut code = base.clone();
        let Value::Object(root) = &mut code else {
            unreachable!();
        };
        let Value::Array(checks) = &mut root
            .iter_mut()
            .find(|(name, _)| name == "checks")
            .unwrap()
            .1
        else {
            unreachable!();
        };
        let Value::Object(check) = &mut checks[0] else {
            unreachable!();
        };
        let Value::Object(definition) = &mut check
            .iter_mut()
            .find(|(name, _)| name == "definition")
            .unwrap()
            .1
        else {
            unreachable!();
        };
        definition
            .iter_mut()
            .find(|(name, _)| name == "codes")
            .unwrap()
            .1 = Value::Array(vec![Value::String("unregistered-code".into())]);
        assert_eq!(
            validate_result_document(&code).unwrap_err().code(),
            "unknown-tag"
        );

        let mut tcb = base;
        let Value::Object(root) = &mut tcb else {
            unreachable!();
        };
        let Value::Array(items) = &mut root.iter_mut().find(|(name, _)| name == "tcb").unwrap().1
        else {
            unreachable!();
        };
        items.pop();
        assert_eq!(
            validate_result_document(&tcb).unwrap_err().code(),
            "tcb-incomplete"
        );
    }

    #[test]
    fn result_consumption_binds_registration_request_evidence_and_tcb() {
        let record = parse_registration_record(RECORD).unwrap();
        let bytes = bind_result_to_record(STRICT_RESULT);
        let (request, evidence) = bindings(&bytes);
        let consumed =
            consume_independent_result(bytes.clone(), &record, &request, &evidence).unwrap();
        assert_eq!(consumed.outcome(), IndependentCheckOutcome::Rejected);
        assert_eq!(consumed.canonical_result(), bytes);
        assert_eq!(consumed.registration_digest(), record.document_digest());
        assert_eq!(consumed.request(), &request);
        assert_eq!(consumed.evidence(), &evidence);
        assert_eq!(
            consumed.document_digest(),
            "sha256:91d3ce53047db8d5b2dfb4c2c9891ed52a7352e9ed3cfe533636425f57b86513"
        );
        assert_eq!(consumed.result_refs().len(), 1);

        let wrong_request = IndependentDocumentBinding::try_available(
            format!("sha256:{}", "0".repeat(64)),
            request.document_digest().unwrap(),
        )
        .unwrap();
        assert_eq!(
            consume_independent_result(bytes.clone(), &record, &wrong_request, &evidence)
                .unwrap_err()
                .code(),
            "result-request-identity"
        );
        let unavailable_request =
            IndependentDocumentBinding::try_unavailable(request.content_digest()).unwrap();
        assert_eq!(
            consume_independent_result(bytes.clone(), &record, &unavailable_request, &evidence)
                .unwrap_err()
                .code(),
            "result-request-identity"
        );

        let wrong_evidence =
            IndependentDocumentBinding::try_unavailable(format!("sha256:{}", "2".repeat(64)))
                .unwrap();
        assert_eq!(
            consume_independent_result(bytes.clone(), &record, &request, &wrong_evidence)
                .unwrap_err()
                .code(),
            "result-evidence-identity"
        );

        let mut drifted = parse(&bytes, true).unwrap();
        set_string(
            &mut drifted,
            &["checker", "artifact"],
            &format!("sha256:{}", "1".repeat(64)),
        );
        assert_eq!(
            consume_independent_result(canonical_bytes(&drifted), &record, &request, &evidence)
                .unwrap_err()
                .code(),
            "result-checker-identity"
        );

        let mut drifted_tcb = parse(&bytes, true).unwrap();
        let Value::Object(root) = &mut drifted_tcb else {
            unreachable!();
        };
        let Value::Array(tcb) = &mut root.iter_mut().find(|(name, _)| name == "tcb").unwrap().1
        else {
            unreachable!();
        };
        let Value::Object(first) = &mut tcb[0] else {
            unreachable!();
        };
        first
            .iter_mut()
            .find(|(name, _)| name == "artifact")
            .unwrap()
            .1 = Value::String(format!("sha256:{}", "3".repeat(64)));
        assert_eq!(
            consume_independent_result(
                canonical_bytes(&drifted_tcb),
                &record,
                &request,
                &evidence,
            )
            .unwrap_err()
            .code(),
            "result-tcb-identity"
        );
    }

    #[test]
    fn accepted_variant_is_consumed_without_trust_or_refs() {
        let record = parse_registration_record(RECORD).unwrap();
        let bytes = bind_result_to_record(&accepted_result());
        let (request, evidence) = bindings(&bytes);
        let consumed = consume_independent_result(bytes, &record, &request, &evidence).unwrap();
        assert_eq!(consumed.outcome(), IndependentCheckOutcome::Accepted);
        assert_eq!(consumed.result_refs().len(), 0);
        assert_eq!(consumed.remaining_trust().len(), 0);
        assert_eq!(consumed.missing_artifacts().len(), 0);
    }

    #[test]
    fn invocation_failure_is_a_separate_request_bound_type() {
        let request = IndependentDocumentBinding::try_available(
            "sha256:6005548377e1725fe3ff86ac2ac0ad47d34b560f63bed50567685b0dbccd261b",
            "sha256:31e60c47a9c346c96daf18bcec22baea5107ad00e414bed77260837914c9443c",
        )
        .unwrap();
        let failure = parse_checker_invocation_failure(PROCESS_FAILURE, &request).unwrap();
        assert_eq!(failure.code(), "checker-process-failure");

        let wrong_request = IndependentDocumentBinding::try_available(
            format!("sha256:{}", "4".repeat(64)),
            request.document_digest().unwrap(),
        )
        .unwrap();
        assert_eq!(
            parse_checker_invocation_failure(PROCESS_FAILURE, &wrong_request)
                .unwrap_err()
                .code(),
            "invocation-failure-request-identity"
        );

        let record = parse_registration_record(RECORD).unwrap();
        let evidence = IndependentDocumentBinding::try_unavailable(
            "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        )
        .unwrap();
        assert!(consume_independent_result(PROCESS_FAILURE, &record, &request, &evidence).is_err());
    }

    #[test]
    fn consumer_rejects_oversize_and_excessive_depth_before_use() {
        let record = parse_registration_record(RECORD).unwrap();
        let binding =
            IndependentDocumentBinding::try_unavailable(format!("sha256:{}", "0".repeat(64)))
                .unwrap();
        assert_eq!(
            consume_independent_result(
                vec![b'x'; super::MAX_INDEPENDENT_RESULT_BYTES + 1],
                &record,
                &binding,
                &binding,
            )
            .unwrap_err()
            .code(),
            "independent-result-length"
        );
        let deep = format!("{}\"x\"{}", "[".repeat(129), "]".repeat(129));
        assert_eq!(
            parse(deep.as_bytes(), true).unwrap_err().code(),
            "json-depth-limit"
        );
    }
}
