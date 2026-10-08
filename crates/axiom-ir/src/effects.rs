//! ADR 0023：纯核心空效果推导记录，不产生 Evidence、五态或执行许可。
mod encoding;
mod rules;
#[cfg(test)]
mod tests;

use crate::{
    document::CanonicalDocument,
    json::{self, JsonError, JsonLimits},
    obligations::{ObligationKind, ObligationSet, raw_digest},
    query::GeneratorIdentity,
    version::IrVersion,
};
use std::fmt;

pub const EFFECT_ARTIFACT: &str = "axiom-core-effect-derivation";
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EffectProfile {
    CoreV0_1,
}
impl EffectProfile {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::CoreV0_1 => "axiom-core-empty-effects-v0.1",
        }
    }
}
#[derive(Clone, Copy, Debug)]
pub struct EffectLimits {
    pub ir_json: JsonLimits,
    pub max_steps: usize,
    pub max_premise_edges: usize,
    pub max_path_bytes: usize,
    pub max_output_bytes: usize,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EffectResource {
    Steps,
    PremiseEdges,
    PathBytes,
    OutputBytes,
}
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct EffectUsage {
    pub steps: usize,
    pub premise_edges: usize,
    pub path_bytes: usize,
    pub output_bytes: usize,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum EffectError {
    UnsupportedIrVersion(IrVersion),
    BindingMismatch,
    UnknownObligation(String),
    UnsupportedKind(ObligationKind),
    Json(JsonError),
    ResourceLimit {
        resource: EffectResource,
    },
    InvalidConstruct {
        anchor: String,
        path: Vec<String>,
        reason: &'static str,
    },
    NonCanonical {
        offset: usize,
    },
    Internal(&'static str),
}
impl fmt::Display for EffectError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "empty effect derivation: {self:?}")
    }
}
impl std::error::Error for EffectError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Json(error) => Some(error),
            _ => None,
        }
    }
}
type Result<T> = std::result::Result<T, EffectError>;

/// 只读内部记录。源码摘要、动态核对与独立证明是不同层级。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EffectDerivation {
    bytes: Vec<u8>,
    digest: String,
    usage: EffectUsage,
}
impl EffectDerivation {
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
    pub fn usage(&self) -> EffectUsage {
        self.usage
    }
}

pub fn derive_empty_effects(
    profile: EffectProfile,
    document: &CanonicalDocument,
    obligations: &ObligationSet,
    obligation_id: &str,
    generator: &GeneratorIdentity,
    limits: EffectLimits,
) -> Result<EffectDerivation> {
    if document.version() != IrVersion::V0_2 {
        return Err(EffectError::UnsupportedIrVersion(document.version()));
    }
    // 全集构造器已核对定义 / ID；不可变类型不接受调用方拼装的成功缓存。
    if obligations.ir_document_digest() != document.document_id()
        || obligations.ir_artifact() != raw_digest(document.canonical_bytes())
    {
        return Err(EffectError::BindingMismatch);
    }
    let target = obligations
        .obligations()
        .iter()
        .find(|item| item.id() == obligation_id)
        .ok_or_else(|| EffectError::UnknownObligation(obligation_id.to_owned()))?;
    if target.kind() != ObligationKind::EffectEmpty {
        return Err(EffectError::UnsupportedKind(target.kind()));
    }
    let value =
        json::parse(document.canonical_bytes(), limits.ir_json).map_err(EffectError::Json)?;
    let mut builder = rules::Builder::new(limits);
    builder.document(&value, document)?;
    let binding = encoding::Binding {
        profile,
        document,
        obligations,
        obligation_id,
        generator,
    };
    let mut size = Some(0usize);
    encoding::envelope(&binding, &builder.steps, &mut |bytes| {
        size = size.and_then(|n| n.checked_add(bytes.len()));
    });
    builder.budget.charge(EffectResource::OutputBytes, size)?;
    let mut bytes = Vec::with_capacity(builder.budget.usage.output_bytes);
    encoding::envelope(&binding, &builder.steps, &mut |part| {
        bytes.extend_from_slice(part)
    });
    Ok(EffectDerivation {
        digest: raw_digest(&bytes),
        bytes,
        usage: builder.budget.usage,
    })
}

/// 外来字节先受上限约束，再完整重建比较；不修复、不升级或补齐候选。
pub fn check_empty_effects(
    profile: EffectProfile,
    bytes: &[u8],
    document: &CanonicalDocument,
    obligations: &ObligationSet,
    obligation_id: &str,
    generator: &GeneratorIdentity,
    limits: EffectLimits,
) -> Result<EffectDerivation> {
    if bytes.len() > limits.max_output_bytes {
        return Err(EffectError::ResourceLimit {
            resource: EffectResource::OutputBytes,
        });
    }
    let record = derive_empty_effects(
        profile,
        document,
        obligations,
        obligation_id,
        generator,
        limits,
    )?;
    if bytes != record.bytes {
        let offset = bytes
            .iter()
            .zip(&record.bytes)
            .position(|(a, b)| a != b)
            .unwrap_or(bytes.len().min(record.bytes.len()));
        return Err(EffectError::NonCanonical { offset });
    }
    Ok(record)
}

struct Budget {
    limits: EffectLimits,
    usage: EffectUsage,
}
impl Budget {
    fn charge(&mut self, resource: EffectResource, added: Option<usize>) -> Result<()> {
        let (used, limit) = match resource {
            EffectResource::Steps => (&mut self.usage.steps, self.limits.max_steps),
            EffectResource::PremiseEdges => {
                (&mut self.usage.premise_edges, self.limits.max_premise_edges)
            }
            EffectResource::PathBytes => (&mut self.usage.path_bytes, self.limits.max_path_bytes),
            EffectResource::OutputBytes => {
                (&mut self.usage.output_bytes, self.limits.max_output_bytes)
            }
        };
        *used = added
            .and_then(|n| used.checked_add(n))
            .filter(|n| *n <= limit)
            .ok_or(EffectError::ResourceLimit { resource })?;
        Ok(())
    }
}
