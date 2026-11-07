//! Explicit local readback of the proposed Evidence v0.2 verification contract.

mod execution;
mod support;
#[cfg(test)]
mod tests;

use std::{
    cell::Cell,
    collections::{BTreeMap, BTreeSet},
    fmt,
};

use crate::{
    declarations::{self as decode, DeclarationError, Members},
    document::{CanonicalDocument, DocumentError, check_canonical_document},
    json::{self, JsonError, JsonLimits, Value},
    normalization::content_id,
    obligations::{
        GenerationError, OBLIGATION_DOMAIN, ObligationLimits, ObligationProfile, ObligationSet,
        generate_obligations, raw_digest,
    },
    origins::OriginLimits,
    version::{IrVersion, V0_2_SEMANTICS_SHA256},
};

use execution::{Execution, read_executions, read_tools};

const PROFILE: &str = "keyed-finite-table-verification";
const DOCUMENT: &str = "axiom-evidence-v0.2:document";
const TOOL: &str = "axiom-evidence-v0.2:tool";
const EXECUTION: &str = "axiom-evidence-v0.2:execution";
const TRUST: &str = "axiom-evidence-v0.2:trust";
const UNCOVERED: &str = "axiom-evidence-v0.2:uncovered";

#[derive(Clone, Copy, Debug)]
pub struct ReviewLimits {
    pub evidence_json: JsonLimits,
    pub max_artifact_bytes: usize,
    pub max_total_artifact_bytes: usize,
    pub max_executions: usize,
    pub p2: ObligationLimits,
    pub derivation: OriginLimits,
}

#[derive(Debug)]
pub enum ReviewError {
    Json(JsonError),
    Shape(DeclarationError),
    Ir(DocumentError),
    Obligations(GenerationError),
    Effect(crate::effects::EffectError),
    Origin(crate::origins::OriginError),
    NonCanonical(&'static str),
    Version,
    Limit(&'static str),
    Invalid {
        at: &'static str,
        reason: &'static str,
    },
    MissingArtifact(String),
    ArtifactIdentity(String),
}

impl fmt::Display for ReviewError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Evidence v0.2 local readback: {self:?}")
    }
}

impl std::error::Error for ReviewError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Json(error) => Some(error),
            Self::Shape(error) => Some(error),
            Self::Ir(error) => Some(error),
            Self::Obligations(error) => Some(error),
            Self::Effect(error) => Some(error),
            Self::Origin(error) => Some(error),
            _ => None,
        }
    }
}

#[derive(Debug, Eq, PartialEq)]
pub struct Readback {
    pub artifact_digest: String,
    pub document_digest: String,
}

/// Rebuilds the proposed verification document and checks its local support bindings.
/// The resolver is scoped to this invocation and supplies exact original bytes.
/// Readback does not authenticate execution provenance or produce an independent result.
pub fn readback_v02<'a>(
    bytes: &[u8],
    mut resolve: impl FnMut(&str) -> Option<&'a [u8]>,
    limits: ReviewLimits,
) -> Result<Readback> {
    let value = strict(bytes, limits.evidence_json, "evidence")?;
    let root = shape(
        &value,
        "/evidence",
        &[
            "artifacts",
            "conclusion",
            "digest_algorithm",
            "evidence_version",
            "executions",
            "format",
            "obligation_profile",
            "obligations",
            "producer",
            "subject",
            "tools",
            "trust",
            "uncovered",
        ],
    )?;
    let profile = shape(
        member(root, "obligation_profile"),
        "/obligation_profile",
        &["name", "version"],
    )?;
    if text(root, "format")? != "axiom-evidence"
        || text(root, "evidence_version")? != "0.2"
        || text(root, "digest_algorithm")? != "sha-256"
        || text(profile, "name")? != PROFILE
        || text(profile, "version")? != "0.2"
    {
        return Err(ReviewError::Version);
    }
    let artifacts = Artifacts::read(items(root, "artifacts")?, &mut resolve, limits)?;
    let subject = Subject::read(member(root, "subject"), &artifacts, limits.p2)?;
    let tools = read_tools(items(root, "tools")?, text(root, "producer")?, &artifacts)?;
    let executions = read_executions(items(root, "executions")?, &tools, &artifacts, limits)?;
    let trust = entries(items(root, "trust")?, TRUST, "trust", false)?;
    let uncovered = entries(items(root, "uncovered")?, UNCOVERED, "uncovered", false)?;
    if subject.document.is_none() && !trust.is_empty() {
        return Err(invalid("trust", "rejection profile"));
    }
    let obligations = entries(
        items(root, "obligations")?,
        OBLIGATION_DOMAIN,
        "obligations",
        true,
    )?;
    check_obligations(&subject, &obligations, &trust)?;

    for row in trust.values() {
        let definition = shape(
            member(row, "definition"),
            "/trust/definition",
            &["category", "claim", "mitigations", "scope"],
        )?;
        if !matches!(
            text(definition, "category")?,
            "specification-intent"
                | "sensitivity-classification"
                | "input-origin"
                | "decoder-normalizer"
                | "proof-backend"
                | "production-generator"
                | "host-runtime"
                | "cryptographic-primitive"
        ) || text(definition, "claim")?.is_empty()
        {
            return Err(invalid("trust", "category or claim"));
        }
        check_scope(
            member(definition, "scope"),
            &subject,
            &artifacts,
            &tools,
            &executions,
            &obligations,
        )?;
        let mut previous = None;
        for mitigation in items(definition, "mitigations")? {
            let reference = shape(mitigation, "/trust/mitigations", &["kind", "ref"])?;
            let kind = text(reference, "kind")?;
            let pin = text(reference, "ref")?;
            ordered(&mut previous, (kind, pin), "mitigations")?;
            match kind {
                "artifact" => {
                    artifacts.get(pin, None)?;
                }
                "execution" if executions.contains_key(pin) => {}
                _ => return Err(invalid("mitigations", "reference")),
            }
        }
    }
    for row in uncovered.values() {
        let definition = shape(
            member(row, "definition"),
            "/uncovered/definition",
            &["category", "scope", "statement"],
        )?;
        if !matches!(
            text(definition, "category")?,
            "real-world-intent"
                | "source-truth-completeness"
                | "resource-performance"
                | "timing-memory-log-side-channel"
                | "host-fidelity-for-all-inputs"
                | "legal-regulatory-compliance"
                | "long-term-archival-authenticity"
        ) || text(definition, "statement")?.is_empty()
        {
            return Err(invalid("uncovered", "category or statement"));
        }
        check_scope(
            member(definition, "scope"),
            &subject,
            &artifacts,
            &tools,
            &executions,
            &obligations,
        )?;
    }

    let mut checked = BTreeMap::new();
    for (&id, execution) in &executions {
        let row = obligations
            .get(execution.target)
            .ok_or(invalid("execution", "obligation"))?;
        let definition = shape(
            member(row, "definition"),
            "/obligation/definition",
            &["expectation", "kind", "subject"],
        )?;
        checked.insert(
            id,
            support::rebuild(
                execution,
                text(definition, "kind")?,
                &subject,
                &artifacts,
                limits,
            )?,
        );
    }
    let mut unknown = Vec::new();
    for (&id, row) in &obligations {
        if support::check_result(id, row, &trust, &checked, &executions)? {
            unknown.push(id);
        }
    }
    let conclusion = shape(member(root, "conclusion"), "/conclusion", &["kind", "refs"])?;
    let (expected_kind, refs) = if subject.document.is_none() {
        (
            "structure_rejected",
            obligations.keys().copied().collect::<Vec<_>>(),
        )
    } else if unknown.is_empty() {
        ("satisfied", Vec::new())
    } else {
        ("inconclusive", unknown)
    };
    if text(conclusion, "kind")? != expected_kind || strings(conclusion, "refs")? != refs {
        return Err(invalid("conclusion", "recomputed result"));
    }
    if artifacts.0.values().any(|artifact| !artifact.used.get()) {
        return Err(invalid("artifacts", "unused"));
    }
    Ok(Readback {
        artifact_digest: raw_digest(bytes),
        document_digest: content_id(DOCUMENT, bytes),
    })
}

fn check_scope(
    value: &Value,
    subject: &Subject<'_>,
    artifacts: &Artifacts<'_, '_>,
    tools: &BTreeMap<&str, BTreeSet<&str>>,
    executions: &BTreeMap<&str, Execution<'_>>,
    obligations: &Entries<'_>,
) -> Result<()> {
    let scope = shape(value, "/scope", &["kind", "ref"])?;
    let pin = text(scope, "ref")?;
    match text(scope, "kind")? {
        "artifact" => {
            artifacts.get(pin, None)?;
        }
        "subject"
            if pin
                == subject
                    .document
                    .as_ref()
                    .map_or(subject.artifact, CanonicalDocument::document_id) => {}
        "tool" if tools.contains_key(pin) => {}
        "execution" if executions.contains_key(pin) => {}
        "obligation" if obligations.contains_key(pin) => {}
        _ => return Err(invalid("scope", "reference")),
    }
    Ok(())
}

fn check_obligations(
    subject: &Subject<'_>,
    obligations: &Entries<'_>,
    trust: &Entries<'_>,
) -> Result<()> {
    if let Some(p2) = &subject.p2 {
        if obligations.len() != p2.obligations().len() + trust.len() {
            return Err(invalid("obligations", "incomplete or extra"));
        }
        for item in p2.obligations() {
            let row = obligations
                .get(item.id())
                .ok_or(invalid("obligations", "missing IR obligation"))?;
            if encode(member(row, "definition")) != item.canonical_definition() {
                return Err(invalid("obligations", "IR definition"));
            }
        }
        for (&id, row) in trust {
            let category = string(
                named(member(row, "definition"), "category")?,
                "/trust/category",
            )?;
            let definition = value_object([
                ("expectation", value_string("trust")),
                ("kind", value_string("trust-boundary")),
                (
                    "subject",
                    value_object([
                        ("category", value_string(category)),
                        ("kind", value_string("trust")),
                        ("scope", value_string(id)),
                    ]),
                ),
            ]);
            if !obligations
                .contains_key(content_id(OBLIGATION_DOMAIN, &encode(&definition)).as_str())
            {
                return Err(invalid("obligations", "missing trust obligation"));
            }
        }
    } else {
        let definition = value_object([
            ("expectation", value_string("check")),
            ("kind", value_string("ir-structure")),
            (
                "subject",
                value_object([
                    ("artifact", value_string(subject.artifact)),
                    ("kind", value_string("rejected-ir")),
                ]),
            ),
        ]);
        if obligations.len() != 1
            || !obligations
                .contains_key(content_id(OBLIGATION_DOMAIN, &encode(&definition)).as_str())
        {
            return Err(invalid("obligations", "rejection definition"));
        }
    }
    Ok(())
}

struct Subject<'a> {
    artifact: &'a str,
    document: Option<CanonicalDocument>,
    p2: Option<ObligationSet>,
}

impl<'a> Subject<'a> {
    fn read(
        value: &'a Value,
        artifacts: &Artifacts<'_, '_>,
        limits: ObligationLimits,
    ) -> Result<Self> {
        match kind(value)? {
            "rejected-ir" => {
                let subject = shape(value, "/subject", &["artifact", "kind"])?;
                let artifact = text(subject, "artifact")?;
                artifacts.get(artifact, Some(("ir-candidate", "0.1")))?;
                Ok(Self {
                    artifact,
                    document: None,
                    p2: None,
                })
            }
            "axiom-ir" => {
                let subject = shape(
                    value,
                    "/subject",
                    &[
                        "ir_artifact",
                        "ir_document_digest",
                        "ir_version",
                        "kind",
                        "semantics",
                    ],
                )?;
                let semantics = shape(
                    member(subject, "semantics"),
                    "/subject/semantics",
                    &["name", "sha256"],
                )?;
                let artifact = text(subject, "ir_artifact")?;
                let ir = artifacts.get(artifact, Some(("axiom-ir", "0.2")))?;
                let document =
                    check_canonical_document(ir, limits.ir_json).map_err(ReviewError::Ir)?;
                if document.version() != IrVersion::V0_2
                    || text(subject, "ir_version")? != "0.2"
                    || text(subject, "ir_document_digest")? != document.document_id()
                    || text(semantics, "name")? != "keyed-finite-table-semantics"
                    || text(semantics, "sha256")?.strip_prefix("sha256:")
                        != Some(V0_2_SEMANTICS_SHA256)
                {
                    return Err(invalid("subject", "IR binding"));
                }
                let p2 =
                    generate_obligations(&document, ObligationProfile::VerificationV0_2, limits)
                        .map_err(ReviewError::Obligations)?;
                Ok(Self {
                    artifact,
                    document: Some(document),
                    p2: Some(p2),
                })
            }
            _ => Err(invalid("subject", "kind")),
        }
    }
}

struct Artifact<'a, 'b> {
    format: &'a str,
    version: &'a str,
    bytes: &'b [u8],
    used: Cell<bool>,
}

struct Artifacts<'a, 'b>(BTreeMap<&'a str, Artifact<'a, 'b>>);

impl<'a, 'b> Artifacts<'a, 'b> {
    fn read(
        values: &'a [Value],
        resolve: &mut impl FnMut(&str) -> Option<&'b [u8]>,
        limits: ReviewLimits,
    ) -> Result<Self> {
        let mut map = BTreeMap::new();
        let mut previous = None;
        let mut total = 0usize;
        for value in values {
            let row = shape(
                value,
                "/artifacts",
                &["byte_length", "content_digest", "format", "format_version"],
            )?;
            let id = text(row, "content_digest")?;
            if !digest(id) {
                return Err(invalid("artifacts", "digest syntax"));
            }
            ordered(&mut previous, id, "artifacts")?;
            let length = decimal(text(row, "byte_length")?, "byte_length")?;
            total = total
                .checked_add(length)
                .ok_or(ReviewError::Limit("artifact total"))?;
            if length > limits.max_artifact_bytes || total > limits.max_total_artifact_bytes {
                return Err(ReviewError::Limit("artifact bytes"));
            }
            let bytes = resolve(id).ok_or_else(|| ReviewError::MissingArtifact(id.to_owned()))?;
            if bytes.len() != length || raw_digest(bytes) != id {
                return Err(ReviewError::ArtifactIdentity(id.to_owned()));
            }
            map.insert(
                id,
                Artifact {
                    format: nonempty(row, "format")?,
                    version: nonempty(row, "format_version")?,
                    bytes,
                    used: Cell::new(false),
                },
            );
        }
        Ok(Self(map))
    }

    fn get(&self, id: &str, format: Option<(&str, &str)>) -> Result<&'b [u8]> {
        let artifact = self
            .0
            .get(id)
            .ok_or(invalid("artifact", "undeclared reference"))?;
        if format.is_some_and(|pair| pair != (artifact.format, artifact.version)) {
            return Err(invalid("artifact", "format or version"));
        }
        artifact.used.set(true);
        Ok(artifact.bytes)
    }
}

type Result<T> = std::result::Result<T, ReviewError>;
type Entries<'a> = BTreeMap<&'a str, &'a Members>;

fn entries<'a>(
    rows: &'a [Value],
    domain: &str,
    at: &'static str,
    result: bool,
) -> Result<Entries<'a>> {
    let mut entries = BTreeMap::new();
    let mut previous = None;
    let keys: &[_] = if result {
        &["definition", "id", "result"]
    } else {
        &["definition", "id"]
    };
    for row in rows {
        let row = shape(row, at, keys)?;
        let id = text(row, "id")?;
        ordered(&mut previous, id, at)?;
        if id != content_id(domain, &encode(member(row, "definition"))) {
            return Err(invalid(at, "entry identity"));
        }
        entries.insert(id, row);
    }
    Ok(entries)
}

fn ordered<T: Ord + Copy>(previous: &mut Option<T>, current: T, at: &'static str) -> Result<()> {
    if previous.is_some_and(|last| last >= current) {
        return Err(invalid(at, "order or duplicate"));
    }
    *previous = Some(current);
    Ok(())
}

fn invalid(at: &'static str, reason: &'static str) -> ReviewError {
    ReviewError::Invalid { at, reason }
}

fn strict(bytes: &[u8], limits: JsonLimits, at: &'static str) -> Result<Value> {
    let value = json::parse(bytes, limits).map_err(ReviewError::Json)?;
    if encode(&value) != bytes {
        return Err(ReviewError::NonCanonical(at));
    }
    Ok(value)
}

fn encode(value: &Value) -> Vec<u8> {
    let mut bytes = Vec::new();
    json::encode(value, &mut bytes);
    bytes
}

fn value_string(text: &str) -> Value {
    Value::String(text.to_owned())
}

fn value_object<const N: usize>(fields: [(&str, Value); N]) -> Value {
    let mut members: Vec<_> = fields
        .into_iter()
        .map(|(key, value)| (key.to_owned(), value, 0))
        .collect();
    members.sort_unstable_by(|left, right| left.0.cmp(&right.0));
    Value::Object(members)
}

fn shape<'a>(value: &'a Value, at: &str, keys: &[&str]) -> Result<&'a Members> {
    decode::object(value, at, keys).map_err(ReviewError::Shape)
}

fn named<'a>(value: &'a Value, key: &'static str) -> Result<&'a Value> {
    if let Value::Object(members) = value
        && let Some((_, value, _)) = members.iter().find(|(name, _, _)| name == key)
    {
        return Ok(value);
    }
    Err(invalid(key, "missing member"))
}

fn member<'a>(object: &'a Members, key: &str) -> &'a Value {
    decode::member(object, key)
}

fn string<'a>(value: &'a Value, at: &str) -> Result<&'a str> {
    decode::string(value, at).map_err(ReviewError::Shape)
}

fn kind(value: &Value) -> Result<&str> {
    string(named(value, "kind")?, "/kind")
}

fn text<'a>(object: &'a Members, key: &str) -> Result<&'a str> {
    string(member(object, key), key)
}

fn nonempty<'a>(object: &'a Members, key: &'static str) -> Result<&'a str> {
    let value = text(object, key)?;
    if value.trim().is_empty() {
        return Err(invalid(key, "empty"));
    }
    Ok(value)
}

fn items<'a>(object: &'a Members, key: &str) -> Result<&'a [Value]> {
    decode::array(member(object, key), key).map_err(ReviewError::Shape)
}

fn strings<'a>(object: &'a Members, key: &str) -> Result<Vec<&'a str>> {
    items(object, key)?
        .iter()
        .map(|value| string(value, key))
        .collect()
}

fn digest(value: &str) -> bool {
    value.strip_prefix("sha256:").is_some_and(|hex| {
        hex.len() == 64
            && hex
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    })
}

fn decimal(value: &str, at: &'static str) -> Result<usize> {
    if value.is_empty()
        || (value.len() > 1 && value.starts_with('0'))
        || !value.bytes().all(|byte| byte.is_ascii_digit())
    {
        return Err(invalid(at, "decimal"));
    }
    value.parse().map_err(|_| ReviewError::Limit(at))
}
