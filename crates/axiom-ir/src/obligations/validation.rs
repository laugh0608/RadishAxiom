//! 在本生产路径内重建全集；不是职责独立的 Evidence checker。

use super::{
    GenerationError, OBLIGATION_DOMAIN, ObligationLimits, ObligationProfile, ObligationSet,
    generate_obligations, raw_digest,
};
use crate::{
    document::CanonicalDocument,
    json::{self, JsonError, JsonLimits, Value},
    normalization::content_id,
    version::V0_2_SEMANTICS_SHA256,
};
use std::{collections::BTreeSet, fmt};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SetErrorKind {
    InvalidShape,
    MissingMember,
    UnexpectedMember,
    BindingMismatch,
    IdentityMismatch,
    DuplicateId,
    NonCanonicalOrder,
    MissingObligation,
    UnexpectedObligation,
    DefinitionMismatch,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SetError {
    Json(JsonError),
    Generation(GenerationError),
    Invalid { kind: SetErrorKind, path: String },
    NonCanonical { offset: usize },
}
impl fmt::Display for SetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P2 set check: {self:?}")
    }
}
impl std::error::Error for SetError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Json(error) => Some(error),
            Self::Generation(error) => Some(error),
            _ => None,
        }
    }
}

/// 只接受与真实生成全集完全相同的规范字节；不排序、补齐、修复或静默迁移。
/// candidate_limits 独立限制外来集合，不能使用它放宽 IR 或生成预算。
pub fn check_obligation_set(
    input: &[u8],
    document: &CanonicalDocument,
    profile: ObligationProfile,
    limits: ObligationLimits,
    candidate_limits: JsonLimits,
) -> Result<ObligationSet, SetError> {
    let value = json::parse(input, candidate_limits).map_err(SetError::Json)?;
    let root = object(
        &value,
        "",
        &[
            "format",
            "format_version",
            "ir_version",
            "ir_artifact",
            "ir_document_digest",
            "semantics",
            "obligation_profile",
            "scope",
            "obligations",
        ],
    )?;
    for (key, expected) in [
        ("format", "axiom-obligation-set"),
        ("format_version", "0.2"),
        ("ir_version", "0.2"),
        ("scope", "ir-derived"),
        ("ir_document_digest", document.document_id()),
        ("ir_artifact", &raw_digest(document.canonical_bytes())),
    ] {
        equal(member(root, key), expected, &format!("/{key}"))?;
    }
    let semantics = object(member(root, "semantics"), "/semantics", &["name", "sha256"])?;
    equal(
        member(semantics, "name"),
        "keyed-finite-table-semantics",
        "/semantics/name",
    )?;
    equal(
        member(semantics, "sha256"),
        &format!("sha256:{V0_2_SEMANTICS_SHA256}"),
        "/semantics/sha256",
    )?;
    let profile_object = object(
        member(root, "obligation_profile"),
        "/obligation_profile",
        &["name", "version"],
    )?;
    equal(
        member(profile_object, "name"),
        "keyed-finite-table-verification",
        "/obligation_profile/name",
    )?;
    equal(
        member(profile_object, "version"),
        "0.2",
        "/obligation_profile/version",
    )?;
    let Value::Array(entries) = member(root, "obligations") else {
        return Err(invalid(SetErrorKind::InvalidShape, "/obligations"));
    };
    let generated =
        generate_obligations(document, profile, limits).map_err(SetError::Generation)?;
    let mut seen = BTreeSet::new();
    let mut previous: Option<&str> = None;
    for (index, entry) in entries.iter().enumerate() {
        let path = format!("/obligations/{index}");
        let entry = object(entry, &path, &["definition", "id"])?;
        let Value::String(id) = member(entry, "id") else {
            return Err(invalid(SetErrorKind::InvalidShape, &format!("{path}/id")));
        };
        if !seen.insert(id.as_str()) {
            return Err(invalid(SetErrorKind::DuplicateId, &format!("{path}/id")));
        }
        if previous.is_some_and(|previous| previous > id.as_str()) {
            return Err(invalid(
                SetErrorKind::NonCanonicalOrder,
                &format!("{path}/id"),
            ));
        }
        previous = Some(id);
        let definition = member(entry, "definition");
        object(
            definition,
            &format!("{path}/definition"),
            &["expectation", "kind", "subject"],
        )?;
        let mut canonical = Vec::new();
        json::encode(definition, &mut canonical);
        if content_id(OBLIGATION_DOMAIN, &canonical) != *id {
            return Err(invalid(
                SetErrorKind::IdentityMismatch,
                &format!("{path}/id"),
            ));
        }
        let matched = generated
            .obligations()
            .binary_search_by(|item| item.id().cmp(id))
            .map_err(|_| invalid(SetErrorKind::UnexpectedObligation, &path))?;
        if generated.obligations()[matched].canonical_definition() != canonical {
            return Err(invalid(
                SetErrorKind::DefinitionMismatch,
                &format!("{path}/definition"),
            ));
        }
    }
    // 所有候选均为唯一全集成员，长度相同才保证没有遗漏。
    if entries.len() != generated.obligations().len() {
        return Err(invalid(SetErrorKind::MissingObligation, "/obligations"));
    }
    if input != generated.canonical_bytes() {
        let offset = input
            .iter()
            .zip(generated.canonical_bytes())
            .position(|(left, right)| left != right)
            .unwrap_or_else(|| input.len().min(generated.canonical_bytes().len()));
        return Err(SetError::NonCanonical { offset });
    }
    Ok(generated)
}

fn invalid(kind: SetErrorKind, path: &str) -> SetError {
    SetError::Invalid {
        kind,
        path: path.to_owned(),
    }
}
fn object<'a>(
    value: &'a Value,
    path: &str,
    keys: &[&str],
) -> Result<&'a [(String, Value, usize)], SetError> {
    let Value::Object(object) = value else {
        return Err(invalid(SetErrorKind::InvalidShape, path));
    };
    for (key, _, _) in object {
        if !keys.contains(&key.as_str()) {
            let escaped = key.replace('~', "~0").replace('/', "~1");
            return Err(invalid(
                SetErrorKind::UnexpectedMember,
                &format!("{path}/{escaped}"),
            ));
        }
    }
    for key in keys {
        if !object.iter().any(|(found, _, _)| found == key) {
            return Err(invalid(
                SetErrorKind::MissingMember,
                &format!("{path}/{key}"),
            ));
        }
    }
    Ok(object)
}
fn member<'a>(object: &'a [(String, Value, usize)], key: &str) -> &'a Value {
    &object
        .iter()
        .find(|(found, _, _)| found == key)
        .expect("checked member")
        .1
}
fn equal(value: &Value, expected: &str, path: &str) -> Result<(), SetError> {
    if matches!(value, Value::String(found) if found == expected) {
        Ok(())
    } else {
        Err(invalid(SetErrorKind::BindingMismatch, path))
    }
}
