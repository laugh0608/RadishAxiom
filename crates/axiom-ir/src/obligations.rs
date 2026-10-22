//! ADR 0018 的 P2 内部组件。只生成 IR 派生位置与身份，不生成证明或 Evidence。

mod encoding;
mod validation;
pub use validation::{SetError, SetErrorKind, check_obligation_set};

use crate::{
    document::CanonicalDocument,
    json::{self, JsonError, JsonLimits, Value},
    normalization::content_id,
    version::IrVersion,
};
use encoding::{PathPart, Subject};
use std::{collections::BTreeMap, fmt};

pub const OBLIGATION_DOMAIN: &str = "axiom-evidence-v0.2:obligation";

/// 调用方显式选择唯一已接受版本；不提供 latest、字符串 fallback 或默认值。
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ObligationProfile {
    VerificationV0_2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ObligationKind {
    IrStructure,
    EffectEmpty,
    Totality,
    KeyCardinality,
    RowCoverage,
    GroupConservation,
    NumericRange,
    FieldOrigin,
    ContractGuarantee,
    Noninterference,
}
impl ObligationKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::IrStructure => "ir-structure",
            Self::EffectEmpty => "effect-empty",
            Self::Totality => "totality",
            Self::KeyCardinality => "key-cardinality",
            Self::RowCoverage => "row-coverage",
            Self::GroupConservation => "group-conservation",
            Self::NumericRange => "numeric-range",
            Self::FieldOrigin => "field-origin",
            Self::ContractGuarantee => "contract-guarantee",
            Self::Noninterference => "noninterference",
        }
    }
    pub fn expectation(self) -> &'static str {
        if self == Self::IrStructure {
            "check"
        } else {
            "prove"
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct ObligationLimits {
    /// 对已验收的规范 IR 再解析一次，限制累计输入、值数和嵌套。
    pub ir_json: JsonLimits,
    pub max_obligations: usize,
    pub max_definition_bytes: usize,
    /// 所有实际 numeric-range path 的规范 JSON 数组字节之和。
    pub max_path_bytes: usize,
    pub max_output_bytes: usize,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ObligationResource {
    Count,
    DefinitionBytes,
    PathBytes,
    OutputBytes,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum GenerationError {
    UnsupportedIrVersion(IrVersion),
    Json(JsonError),
    ResourceLimit {
        resource: ObligationResource,
        obligation_index: usize,
    },
    DuplicateDefinition {
        id: String,
    },
    Internal(&'static str),
}
impl fmt::Display for GenerationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P2 generation: {self:?}")
    }
}
impl std::error::Error for GenerationError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        if let Self::Json(error) = self {
            Some(error)
        } else {
            None
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Obligation {
    kind: ObligationKind,
    id: String,
    canonical_definition: Vec<u8>,
}
impl Obligation {
    pub fn kind(&self) -> ObligationKind {
        self.kind
    }
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn canonical_definition(&self) -> &[u8] {
        &self.canonical_definition
    }
}

/// 只读的 ir-derived 全集。没有五态、conclusion、执行许可或独立 accepted。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ObligationSet {
    entries: Vec<Obligation>,
    canonical_bytes: Vec<u8>,
    artifact_digest: String,
    ir_document_digest: String,
    ir_artifact: String,
}
impl ObligationSet {
    pub fn obligations(&self) -> &[Obligation] {
        &self.entries
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.canonical_bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.artifact_digest
    }
    pub fn ir_document_digest(&self) -> &str {
        &self.ir_document_digest
    }
    pub fn ir_artifact(&self) -> &str {
        &self.ir_artifact
    }
    pub fn profile(&self) -> ObligationProfile {
        ObligationProfile::VerificationV0_2
    }
    pub fn scope(&self) -> &'static str {
        "ir-derived"
    }
}

pub fn generate_obligations(
    document: &CanonicalDocument,
    profile: ObligationProfile,
    limits: ObligationLimits,
) -> Result<ObligationSet, GenerationError> {
    match profile {
        ObligationProfile::VerificationV0_2 => {}
    }
    if document.version() != IrVersion::V0_2 {
        return Err(GenerationError::UnsupportedIrVersion(document.version()));
    }
    let value =
        json::parse(document.canonical_bytes(), limits.ir_json).map_err(GenerationError::Json)?;
    let ir_artifact = raw_digest(document.canonical_bytes());
    let mut builder = Builder {
        document_id: document.document_id(),
        limits,
        entries: Vec::new(),
        definition_bytes: 0,
        path_bytes: 0,
        output_bytes: 0,
    };
    // 空 envelope 长度 + 各 entry 长度恰等于完整输出，不需反复编码已有条目。
    let mut base = Some(0usize);
    encoding::envelope(&ir_artifact, document.document_id(), &[], &mut |bytes| {
        base = base.and_then(|n| n.checked_add(bytes.len()));
    });
    builder.output_bytes = builder.budget(
        0,
        base,
        limits.max_output_bytes,
        ObligationResource::OutputBytes,
    )?;
    builder.add(ObligationKind::IrStructure, Subject::Document)?;
    builder.add(ObligationKind::EffectEmpty, Subject::Program)?;
    let root = members(&value)?;
    for entry in array(member(root, "nodes")?)? {
        let entry = members(entry)?;
        let id = string(member(entry, "id")?)?;
        let definition = member(entry, "definition")?;
        let object = members(definition)?;
        let kind = string(member(object, "kind")?)?;
        if kind != "input" {
            for kind in [
                ObligationKind::Totality,
                ObligationKind::KeyCardinality,
                ObligationKind::RowCoverage,
            ] {
                builder.add(kind, Subject::Node(id))?;
            }
        }
        if kind == "group" {
            builder.add(ObligationKind::GroupConservation, Subject::Node(id))?;
            for (index, _) in array(member(object, "aggregates")?)?.iter().enumerate() {
                builder.add(
                    ObligationKind::NumericRange,
                    Subject::Path {
                        contract: false,
                        id,
                        path: &[PathPart::Name("aggregates"), PathPart::Index(index)],
                    },
                )?;
            }
        }
        builder.numeric(definition, id, false, &mut Vec::new())?;
    }
    for entry in array(member(root, "contracts")?)? {
        let entry = members(entry)?;
        let id = string(member(entry, "id")?)?;
        let definition = member(entry, "definition")?;
        let object = members(definition)?;
        if string(member(object, "kind")?)? == "noninterference" {
            builder.add(ObligationKind::Noninterference, Subject::Contract(id))?;
        } else if string(member(object, "role")?)? == "guarantee" {
            builder.add(ObligationKind::ContractGuarantee, Subject::Contract(id))?;
        }
        builder.numeric(definition, id, true, &mut Vec::new())?;
    }
    // P1 的原索引仅用于解析具名输出，不用于义务 path。共享类型不递归展开。
    let graph = document.components().analysis().graph();
    let tables: BTreeMap<_, _> = graph
        .types()
        .table_types()
        .iter()
        .map(|t| (t.id(), t.definition()))
        .collect();
    let records: BTreeMap<_, _> = graph
        .types()
        .record_types()
        .iter()
        .map(|r| (r.id(), r.definition()))
        .collect();
    for output in graph.outputs() {
        let table = tables[graph.nodes()[output.node].table_type()];
        for field in &records[table.record_type.as_str()].fields {
            builder.add(
                ObligationKind::FieldOrigin,
                Subject::Field {
                    interface: &output.name,
                    name: &field.name,
                },
            )?;
        }
    }
    builder
        .entries
        .sort_by(|left, right| left.id.cmp(&right.id));
    for pair in builder.entries.windows(2) {
        if pair[0].id == pair[1].id {
            return Err(GenerationError::DuplicateDefinition {
                id: pair[0].id.clone(),
            });
        }
    }
    let mut canonical_bytes = Vec::with_capacity(builder.output_bytes);
    encoding::envelope(
        &ir_artifact,
        document.document_id(),
        &builder.entries,
        &mut |bytes| canonical_bytes.extend_from_slice(bytes),
    );
    if canonical_bytes.len() != builder.output_bytes {
        return Err(GenerationError::Internal(
            "output length disagrees with preflight",
        ));
    }
    Ok(ObligationSet {
        entries: builder.entries,
        artifact_digest: raw_digest(&canonical_bytes),
        canonical_bytes,
        ir_artifact,
        ir_document_digest: document.document_id().to_owned(),
    })
}

struct Builder<'a> {
    document_id: &'a str,
    limits: ObligationLimits,
    entries: Vec<Obligation>,
    definition_bytes: usize,
    path_bytes: usize,
    output_bytes: usize,
}
impl Builder<'_> {
    fn budget(
        &self,
        current: usize,
        added: Option<usize>,
        maximum: usize,
        resource: ObligationResource,
    ) -> Result<usize, GenerationError> {
        added
            .and_then(|n| current.checked_add(n))
            .filter(|n| *n <= maximum)
            .ok_or(GenerationError::ResourceLimit {
                resource,
                obligation_index: self.entries.len(),
            })
    }
    fn add(&mut self, kind: ObligationKind, subject: Subject<'_>) -> Result<(), GenerationError> {
        self.budget(
            self.entries.len(),
            Some(1),
            self.limits.max_obligations,
            ObligationResource::Count,
        )?;
        let mut path_length = Some(0usize);
        if let Subject::Path { path, .. } = &subject {
            encoding::path(path, &mut |bytes| {
                path_length = path_length.and_then(|n| n.checked_add(bytes.len()));
            });
        }
        let path_total = self.budget(
            self.path_bytes,
            path_length,
            self.limits.max_path_bytes,
            ObligationResource::PathBytes,
        )?;
        let mut length = Some(0usize);
        encoding::definition(kind, &subject, self.document_id, &mut |bytes| {
            length = length.and_then(|n| n.checked_add(bytes.len()));
        });
        let definition_total = self.budget(
            self.definition_bytes,
            length,
            self.limits.max_definition_bytes,
            ObligationResource::DefinitionBytes,
        )?;
        let length = length.expect("checked length");
        // entry 的固定开销：闭合 wrapper + 长度固定的 sha256 ID JSON 字符串。
        let mut overhead = Some(0usize);
        encoding::entry(
            &[],
            "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            &mut |bytes| {
                overhead = overhead.and_then(|n| n.checked_add(bytes.len()));
            },
        );
        let added = overhead
            .and_then(|n| n.checked_add(length))
            .and_then(|n| n.checked_add(usize::from(!self.entries.is_empty())));
        let output_total = self.budget(
            self.output_bytes,
            added,
            self.limits.max_output_bytes,
            ObligationResource::OutputBytes,
        )?;
        let mut canonical_definition = Vec::with_capacity(length);
        encoding::definition(kind, &subject, self.document_id, &mut |bytes| {
            canonical_definition.extend_from_slice(bytes)
        });
        let id = content_id(OBLIGATION_DOMAIN, &canonical_definition);
        self.entries.push(Obligation {
            kind,
            id,
            canonical_definition,
        });
        self.path_bytes = path_total;
        self.definition_bytes = definition_total;
        self.output_bytes = output_total;
        Ok(())
    }
    fn numeric<'a>(
        &mut self,
        value: &'a Value,
        id: &str,
        contract: bool,
        path: &mut Vec<PathPart<'a>>,
    ) -> Result<(), GenerationError> {
        match value {
            Value::Object(object) => {
                if object.iter().any(|(key, value, _)| key == "op" && matches!(value, Value::String(op) if matches!(op.as_str(), "int_add" | "int_sub" | "fixed_add" | "fixed_sub" | "count_where" | "sum_where"))) {
                    self.add(ObligationKind::NumericRange, Subject::Path { contract, id, path })?;
                }
                for (name, child, _) in object {
                    path.push(PathPart::Name(name));
                    self.numeric(child, id, contract, path)?;
                    path.pop();
                }
            }
            Value::Array(values) => {
                for (index, child) in values.iter().enumerate() {
                    path.push(PathPart::Index(index));
                    self.numeric(child, id, contract, path)?;
                    path.pop();
                }
            }
            _ => {}
        }
        Ok(())
    }
}

pub(super) fn raw_digest(bytes: &[u8]) -> String {
    format!("sha256:{}", radishaxiom_digest::digest_hex(bytes))
}
// 这里只读取 CanonicalDocument 的只读字节；不可达形状错误不是用户 IR 非法。
fn members(value: &Value) -> Result<&[(String, Value, usize)], GenerationError> {
    if let Value::Object(value) = value {
        Ok(value)
    } else {
        Err(GenerationError::Internal("expected canonical object"))
    }
}
fn member<'a>(
    object: &'a [(String, Value, usize)],
    key: &str,
) -> Result<&'a Value, GenerationError> {
    object
        .iter()
        .find(|(name, _, _)| name == key)
        .map(|(_, value, _)| value)
        .ok_or(GenerationError::Internal("missing canonical member"))
}
fn array(value: &Value) -> Result<&[Value], GenerationError> {
    if let Value::Array(value) = value {
        Ok(value)
    } else {
        Err(GenerationError::Internal("expected canonical array"))
    }
}
fn string(value: &Value) -> Result<&str, GenerationError> {
    if let Value::String(value) = value {
        Ok(value)
    } else {
        Err(GenerationError::Internal("expected canonical string"))
    }
}
