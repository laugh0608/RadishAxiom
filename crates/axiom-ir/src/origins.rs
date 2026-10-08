//! ADR 0024：字段来源与保守标签推导记录，不产生 Evidence、五态或执行许可。
mod build;
mod encoding;
mod expressions;
mod nodes;
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

pub const ORIGIN_ARTIFACT: &str = "axiom-core-field-origin-derivation";
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OriginProfile {
    CoreFieldOriginV0_1,
}
impl OriginProfile {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::CoreFieldOriginV0_1 => "axiom-core-field-origin-v0.1",
        }
    }
}
#[derive(Clone, Copy, Debug)]
pub struct OriginLimits {
    pub ir_json: JsonLimits,
    pub max_steps: usize,
    pub max_premise_edges: usize,
    pub max_descriptors: usize,
    pub max_path_bytes: usize,
    pub max_output_bytes: usize,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OriginResource {
    Steps,
    PremiseEdges,
    Descriptors,
    PathBytes,
    OutputBytes,
}
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct OriginUsage {
    pub steps: usize,
    pub premise_edges: usize,
    pub descriptors: usize,
    pub path_bytes: usize,
    pub output_bytes: usize,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum OriginError {
    UnsupportedIrVersion(IrVersion),
    BindingMismatch,
    UnknownObligation(String),
    UnsupportedKind(ObligationKind),
    Json(JsonError),
    ResourceLimit {
        resource: OriginResource,
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
impl fmt::Display for OriginError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "field origin derivation: {self:?}")
    }
}
impl std::error::Error for OriginError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Json(error) => Some(error),
            _ => None,
        }
    }
}
type Result<T> = std::result::Result<T, OriginError>;

/// 只读内部记录。源码摘要、动态核对与独立证明是不同层级。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OriginDerivation {
    bytes: Vec<u8>,
    digest: String,
    usage: OriginUsage,
}
impl OriginDerivation {
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
    pub fn usage(&self) -> OriginUsage {
        self.usage
    }
}

pub fn derive_field_origin(
    profile: OriginProfile,
    document: &CanonicalDocument,
    obligations: &ObligationSet,
    obligation_id: &str,
    generator: &GeneratorIdentity,
    limits: OriginLimits,
) -> Result<OriginDerivation> {
    if document.version() != IrVersion::V0_2 {
        return Err(OriginError::UnsupportedIrVersion(document.version()));
    }
    // 全集构造器已核对定义 / ID；不可变类型不接受调用方拼装的成功缓存。
    if obligations.ir_document_digest() != document.document_id()
        || obligations.ir_artifact() != raw_digest(document.canonical_bytes())
    {
        return Err(OriginError::BindingMismatch);
    }
    let target = obligations
        .obligations()
        .iter()
        .find(|item| item.id() == obligation_id)
        .ok_or_else(|| OriginError::UnknownObligation(obligation_id.to_owned()))?;
    if target.kind() != ObligationKind::FieldOrigin {
        return Err(OriginError::UnsupportedKind(target.kind()));
    }
    let value =
        json::parse(document.canonical_bytes(), limits.ir_json).map_err(OriginError::Json)?;
    let definition =
        json::parse(target.canonical_definition(), limits.ir_json).map_err(OriginError::Json)?;
    let mut builder = build::Builder::new(limits);
    let target = builder.document(&value, document, &definition)?;
    let pruned = builder.prune(&target)?;
    let binding = encoding::Binding {
        profile,
        document,
        obligations,
        obligation_id,
        generator,
    };
    let mut size = Some(0usize);
    encoding::envelope(&binding, &builder.steps, &target, &pruned, &mut |bytes| {
        size = size.and_then(|n| n.checked_add(bytes.len()));
    });
    builder.budget.charge(OriginResource::OutputBytes, size)?;
    let mut bytes = Vec::with_capacity(builder.budget.usage.output_bytes);
    encoding::envelope(&binding, &builder.steps, &target, &pruned, &mut |part| {
        bytes.extend_from_slice(part)
    });
    Ok(OriginDerivation {
        digest: raw_digest(&bytes),
        bytes,
        usage: builder.budget.usage,
    })
}

/// 外来字节先受上限约束，再完整重建比较；不修复、不升级或补齐候选。
pub fn check_field_origin(
    profile: OriginProfile,
    bytes: &[u8],
    document: &CanonicalDocument,
    obligations: &ObligationSet,
    obligation_id: &str,
    generator: &GeneratorIdentity,
    limits: OriginLimits,
) -> Result<OriginDerivation> {
    if bytes.len() > limits.max_output_bytes {
        return Err(OriginError::ResourceLimit {
            resource: OriginResource::OutputBytes,
        });
    }
    let record = derive_field_origin(
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
        return Err(OriginError::NonCanonical { offset });
    }
    Ok(record)
}

struct Budget {
    limits: OriginLimits,
    usage: OriginUsage,
}
impl Budget {
    fn charge(&mut self, resource: OriginResource, added: Option<usize>) -> Result<()> {
        let (used, limit) = match resource {
            OriginResource::Steps => (&mut self.usage.steps, self.limits.max_steps),
            OriginResource::PremiseEdges => {
                (&mut self.usage.premise_edges, self.limits.max_premise_edges)
            }
            OriginResource::Descriptors => {
                (&mut self.usage.descriptors, self.limits.max_descriptors)
            }
            OriginResource::PathBytes => (&mut self.usage.path_bytes, self.limits.max_path_bytes),
            OriginResource::OutputBytes => {
                (&mut self.usage.output_bytes, self.limits.max_output_bytes)
            }
        };
        *used = added
            .and_then(|n| used.checked_add(n))
            .filter(|n| *n <= limit)
            .ok_or(OriginError::ResourceLimit { resource })?;
        Ok(())
    }
}
