//! ADR 0019 的 P3-A 内部组件；不运行 solver，不产生 Evidence 或证明状态。

mod encode;
mod expressions;
mod layout;
mod planning;
mod smt;
#[cfg(test)]
mod tests;

use crate::{
    document::CanonicalDocument,
    json::{self, JsonError, JsonLimits, Value},
    obligations::{ObligationKind, ObligationSet, raw_digest},
    version::IrVersion,
};
use std::fmt;

pub const ENCODING_PROFILE: &str = "axiom-p3-map-filter-query-v0.1";
pub const QUERY_ARTIFACT: &str = "axiom-smtlib2-qf-uflia-query0.2";
pub const SOLVER_DIALECT: &str = "SMT-LIB-2.6/QF_UFLIA";

#[derive(Clone, Copy, Debug)]
pub struct QueryLimits {
    pub ir_json: JsonLimits,
    pub max_input_slots: usize,
    pub max_value_cells: usize,
    pub max_expression_instances: usize,
    pub max_slot_comparisons: usize,
    /// 包含 AST 节点及操作数边，避免一个高元数节点绕过预算。
    pub max_smt_nodes: usize,
    pub max_output_bytes: usize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum QueryResource {
    InputSlots,
    ValueCells,
    ExpressionInstances,
    SlotComparisons,
    SmtNodes,
    OutputBytes,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct QueryUsage {
    pub input_slots: usize,
    pub value_cells: usize,
    pub expression_instances: usize,
    pub slot_comparisons: usize,
    pub smt_nodes: usize,
    pub output_bytes: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum QueryError {
    UnsupportedIrVersion(IrVersion),
    BindingMismatch,
    InvalidGeneratorIdentity,
    UnknownObligation(String),
    NotProve(String),
    UnsupportedKind(ObligationKind),
    UnsupportedFeature {
        anchor: String,
        feature: String,
    },
    Json(JsonError),
    ResourceLimit {
        resource: QueryResource,
        obligation: String,
    },
    NonCanonicalQuery {
        offset: usize,
    },
    Internal(&'static str),
}
impl fmt::Display for QueryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P3 query: {self:?}")
    }
}
impl std::error::Error for QueryError {}

/// 生成器源码身份由调用方明确声明，不等于构建 attestation 或执行验收。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct GeneratorIdentity {
    source_digest: String,
}
impl GeneratorIdentity {
    pub fn new(source_digest: &str) -> Result<Self, QueryError> {
        let valid = source_digest.strip_prefix("sha256:").is_some_and(|s| {
            s.len() == 64
                && s.bytes()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        });
        if !valid {
            return Err(QueryError::InvalidGeneratorIdentity);
        }
        Ok(Self {
            source_digest: source_digest.to_owned(),
        })
    }
    pub fn source_digest(&self) -> &str {
        &self.source_digest
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct QueryBinding {
    ir_artifact: String,
    ir_document_digest: String,
    obligation_set_artifact: String,
    obligation: String,
    semantics_digest: String,
    generator: GeneratorIdentity,
}
impl QueryBinding {
    pub fn ir_artifact(&self) -> &str {
        &self.ir_artifact
    }
    pub fn ir_document_digest(&self) -> &str {
        &self.ir_document_digest
    }
    pub fn obligation_set_artifact(&self) -> &str {
        &self.obligation_set_artifact
    }
    pub fn obligation(&self) -> &str {
        &self.obligation
    }
    pub fn semantics_digest(&self) -> &str {
        &self.semantics_digest
    }
    pub fn generator(&self) -> &GeneratorIdentity {
        &self.generator
    }
    pub fn encoding_profile(&self) -> &'static str {
        ENCODING_PROFILE
    }
    pub fn artifact_type(&self) -> &'static str {
        QUERY_ARTIFACT
    }
    pub fn solver_dialect(&self) -> &'static str {
        SOLVER_DIALECT
    }
}

/// component 为记录按规范字段序深度优先展开后的叶 / Option 标签序号；None 表示活动位。
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SymbolOrigin {
    Input {
        interface: std::sync::Arc<str>,
        slot: usize,
        component: Option<usize>,
    },
    TextLiteral(String),
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct QuerySymbol {
    name: String,
    sort: &'static str,
    origin: SymbolOrigin,
}
impl QuerySymbol {
    pub fn name(&self) -> &str {
        &self.name
    }
    pub fn sort(&self) -> &'static str {
        self.sort
    }
    pub fn origin(&self) -> &SymbolOrigin {
        &self.origin
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EncodedQuery {
    bytes: Vec<u8>,
    artifact_digest: String,
    binding: QueryBinding,
    symbols: Vec<QuerySymbol>,
    usage: QueryUsage,
}
impl EncodedQuery {
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.artifact_digest
    }
    pub fn binding(&self) -> &QueryBinding {
        &self.binding
    }
    pub fn symbols(&self) -> &[QuerySymbol] {
        &self.symbols
    }
    pub fn usage(&self) -> QueryUsage {
        self.usage
    }
}

pub fn encode_query(
    document: &CanonicalDocument,
    obligations: &ObligationSet,
    obligation_id: &str,
    generator: &GeneratorIdentity,
    limits: QueryLimits,
) -> Result<EncodedQuery, QueryError> {
    if document.version() != IrVersion::V0_2 {
        return Err(QueryError::UnsupportedIrVersion(document.version()));
    }
    // ObligationSet 无可写字段，唯一构造入口都已生成 / 重建完整集合。
    if obligations.ir_document_digest() != document.document_id()
        || obligations.ir_artifact() != raw_digest(document.canonical_bytes())
    {
        return Err(QueryError::BindingMismatch);
    }
    let target = obligations
        .obligations()
        .iter()
        .find(|o| o.id() == obligation_id)
        .ok_or_else(|| QueryError::UnknownObligation(obligation_id.to_owned()))?;
    if target.kind().expectation() != "prove" {
        return Err(QueryError::NotProve(obligation_id.to_owned()));
    }
    if !matches!(
        target.kind(),
        ObligationKind::NumericRange | ObligationKind::ContractGuarantee
    ) {
        return Err(QueryError::UnsupportedKind(target.kind()));
    }
    let root = json::parse(document.canonical_bytes(), limits.ir_json).map_err(QueryError::Json)?;
    let definition =
        json::parse(target.canonical_definition(), limits.ir_json).map_err(QueryError::Json)?;
    let binding = QueryBinding {
        ir_artifact: obligations.ir_artifact().to_owned(),
        ir_document_digest: document.document_id().to_owned(),
        obligation_set_artifact: obligations.artifact_digest().to_owned(),
        obligation: obligation_id.to_owned(),
        semantics_digest: format!("sha256:{}", document.version().semantics_sha256()),
        generator: generator.clone(),
    };
    encode::encode(document, &root, &definition, target.kind(), binding, limits)
}

/// 从已验收输入重建并逐字节比较，不把词法检查当成编码正确性或独立证明。
pub fn check_query(
    bytes: &[u8],
    document: &CanonicalDocument,
    obligations: &ObligationSet,
    obligation_id: &str,
    generator: &GeneratorIdentity,
    limits: QueryLimits,
) -> Result<EncodedQuery, QueryError> {
    if bytes.len() > limits.max_output_bytes {
        return Err(QueryError::ResourceLimit {
            resource: QueryResource::OutputBytes,
            obligation: obligation_id.to_owned(),
        });
    }
    let query = encode_query(document, obligations, obligation_id, generator, limits)?;
    if bytes != query.bytes {
        let offset = bytes
            .iter()
            .zip(&query.bytes)
            .position(|(a, b)| a != b)
            .unwrap_or(bytes.len().min(query.bytes.len()));
        return Err(QueryError::NonCanonicalQuery { offset });
    }
    Ok(query)
}

type Result<T, E = QueryError> = std::result::Result<T, E>;

struct Budget {
    limits: QueryLimits,
    usage: QueryUsage,
    obligation: String,
}
impl Budget {
    fn error(&self, resource: QueryResource) -> QueryError {
        QueryError::ResourceLimit {
            resource,
            obligation: self.obligation.clone(),
        }
    }
    fn charge(&mut self, resource: QueryResource, added: usize) -> Result<()> {
        let (used, maximum) = match resource {
            QueryResource::InputSlots => (&mut self.usage.input_slots, self.limits.max_input_slots),
            QueryResource::ValueCells => (&mut self.usage.value_cells, self.limits.max_value_cells),
            QueryResource::ExpressionInstances => (
                &mut self.usage.expression_instances,
                self.limits.max_expression_instances,
            ),
            QueryResource::SlotComparisons => (
                &mut self.usage.slot_comparisons,
                self.limits.max_slot_comparisons,
            ),
            QueryResource::SmtNodes => (&mut self.usage.smt_nodes, self.limits.max_smt_nodes),
            QueryResource::OutputBytes => {
                (&mut self.usage.output_bytes, self.limits.max_output_bytes)
            }
        };
        let value = used.checked_add(added).filter(|n| *n <= maximum);
        if let Some(value) = value {
            *used = value;
            Ok(())
        } else {
            Err(self.error(resource))
        }
    }
}

// 已通过 P1 的规范树；结构不符属于内部不变量错误，不再提供宽松解析入口。
fn object(v: &Value) -> &[(String, Value, usize)] {
    let Value::Object(v) = v else {
        unreachable!("P1 canonical object")
    };
    v
}
fn get<'a>(v: &'a Value, key: &str) -> &'a Value {
    crate::declarations::member(object(v), key)
}
fn array(v: &Value) -> &[Value] {
    let Value::Array(v) = v else {
        unreachable!("P1 canonical array")
    };
    v
}
fn string(v: &Value) -> &str {
    let Value::String(v) = v else {
        unreachable!("P1 canonical string")
    };
    v
}
fn text<'a>(v: &'a Value, key: &str) -> &'a str {
    string(get(v, key))
}
