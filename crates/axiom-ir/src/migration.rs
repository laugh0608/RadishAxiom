//! 单向、显式的 v0.1 → v0.2 迁移。严格源验证先于所有重绑，目标再次 strict 检查。
//! 不猜测旧版 Unsupported，不携带 Evidence 结论或运行许可。

use std::collections::{BTreeMap, VecDeque};
use std::fmt;

use crate::contracts::ContractError;
use crate::declarations::{self as decode, DeclarationError, Members, ValueType, member_mut};
use crate::document::{CanonicalDocument, DocumentError, check_canonical_document};
use crate::expressions::normalization::normalize_checked;
use crate::json::{self, JsonLimits, Value};
use crate::nodes::{NodeKind, normalization::normalize_definition};
use crate::normalization::{NormalizedTypeDeclarations, content_id};
use crate::version::{ContentKind, IrVersion};

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum MigrationError {
    Source(DocumentError),
    WrongSourceVersion { actual: IrVersion },
    Target(DocumentError),
}

impl fmt::Display for MigrationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Source(error) => write!(f, "IR migration source: {error}"),
            Self::WrongSourceVersion { actual } => write!(
                f,
                "IR migration requires source 0.1, received {}",
                actual.as_str()
            ),
            Self::Target(error) => write!(f, "IR migration target: {error}"),
        }
    }
}

impl std::error::Error for MigrationError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Source(error) | Self::Target(error) => Some(error),
            Self::WrongSourceVersion { .. } => None,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IdMapping {
    kind: ContentKind,
    source: String,
    target: String,
}

impl IdMapping {
    pub fn kind(&self) -> ContentKind {
        self.kind
    }
    pub fn source(&self) -> &str {
        &self.source
    }
    pub fn target(&self) -> &str {
        &self.target
    }
}

/// 类型化内部迁移记录，不是公共 receipt、来源认证或可复用证明。
/// 归档者还须留存实际工具修订和源字节；crate 版本不唯一标识开发构建。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MigrationRecord {
    source_document_id: String,
    target_document_id: String,
    mappings: Vec<IdMapping>,
}

impl MigrationRecord {
    pub fn tool_name(&self) -> &'static str {
        "radishaxiom-ir"
    }
    pub fn tool_version(&self) -> &'static str {
        env!("CARGO_PKG_VERSION")
    }
    pub fn rule_name(&self) -> &'static str {
        "axiom-ir-0.1-to-0.2"
    }
    pub fn rule_version(&self) -> &'static str {
        "1"
    }
    pub fn source_version(&self) -> IrVersion {
        IrVersion::V0_1
    }
    pub fn target_version(&self) -> IrVersion {
        IrVersion::V0_2
    }
    pub fn source_document_id(&self) -> &str {
        &self.source_document_id
    }
    pub fn target_document_id(&self) -> &str {
        &self.target_document_id
    }
    pub fn mappings(&self) -> &[IdMapping] {
        &self.mappings
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MigratedDocument {
    record: MigrationRecord,
    target: CanonicalDocument,
}

impl MigratedDocument {
    pub fn record(&self) -> &MigrationRecord {
        &self.record
    }
    pub fn target(&self) -> &CanonicalDocument {
        &self.target
    }
}

pub fn migrate_v0_1_to_v0_2(
    input: &[u8],
    limits: JsonLimits,
) -> Result<MigratedDocument, MigrationError> {
    let source = check_canonical_document(input, limits).map_err(MigrationError::Source)?;
    if source.version() != IrVersion::V0_1 {
        return Err(MigrationError::WrongSourceVersion {
            actual: source.version(),
        });
    }
    // 只解析已经 strict 验证的原字节，预算不因源规范化而放宽。
    let mut value = json::parse(input, limits).map_err(|error| {
        MigrationError::Source(DocumentError::Ir(ContractError::Input(
            DeclarationError::Json(error),
        )))
    })?;
    let root = object_mut(&mut value);
    let graph = source.components().analysis().graph();
    let mut mappings = Mappings::default();

    for entry in entries_mut(root, "enum_types").iter_mut() {
        rekey(entry, ContentKind::EnumType, &mut mappings);
    }
    let records = entries_mut(root, "record_types");
    for index in record_order(graph.types()) {
        let entry = &mut records[index];
        rewrite_type_references(member_mut(object_mut(entry), "definition"), &mappings);
        rekey(entry, ContentKind::RecordType, &mut mappings);
    }
    for entry in entries_mut(root, "table_types").iter_mut() {
        rewrite_type_references(member_mut(object_mut(entry), "definition"), &mappings);
        rekey(entry, ContentKind::TableType, &mut mappings);
    }
    let nodes = entries_mut(root, "nodes");
    for &index in graph.topological_order() {
        let entry = &mut nodes[index];
        let definition = member_mut(object_mut(entry), "definition");
        rewrite_type_references(definition, &mappings);
        let kind = graph.nodes()[index].kind();
        let references: &[&str] = match kind {
            NodeKind::Input => &[],
            NodeKind::Filter | NodeKind::Map | NodeKind::Group => &["source"],
            NodeKind::LookupJoin => &["left", "right"],
        };
        for key in references {
            mappings.rewrite(member_mut(object_mut(definition), key), ContentKind::Node);
        }
        // 新引用会改变子式的 JCS 排序键，必须重做规范化后再计算目标 ID。
        normalize_definition(definition, kind);
        rekey(entry, ContentKind::Node, &mut mappings);
    }
    for entry in entries_mut(root, "contracts").iter_mut() {
        let definition = member_mut(object_mut(entry), "definition");
        rewrite_type_references(definition, &mappings);
        normalize_checked(definition);
        rekey(entry, ContentKind::Contract, &mut mappings);
    }
    for output in entries_mut(root, "outputs") {
        mappings.rewrite(member_mut(object_mut(output), "node"), ContentKind::Node);
    }
    *member_mut(root, "ir_version") = Value::String(IrVersion::V0_2.as_str().to_owned());
    *member_mut(object_mut(member_mut(root, "semantics")), "sha256") =
        Value::String(IrVersion::V0_2.semantics_sha256().to_owned());
    for collection in [
        "enum_types",
        "record_types",
        "table_types",
        "nodes",
        "contracts",
    ] {
        entries_mut(root, collection).sort_by(|a, b| entry_id(a).cmp(entry_id(b)));
    }
    let mut target_bytes = Vec::with_capacity(input.len());
    json::encode(&value, &mut target_bytes);
    // check_canonical_document 同时执行真实目标 normalizer 与严格字节比较。
    let target = check_canonical_document(&target_bytes, limits).map_err(MigrationError::Target)?;
    let record = MigrationRecord {
        source_document_id: source.document_id().to_owned(),
        target_document_id: target.document_id().to_owned(),
        mappings: mappings.into_entries(),
    };
    Ok(MigratedDocument { record, target })
}

#[derive(Default)]
struct Mappings(BTreeMap<ContentKind, BTreeMap<String, String>>);

impl Mappings {
    fn rewrite(&self, value: &mut Value, kind: ContentKind) {
        let Value::String(id) = value else {
            unreachable!("strict source reference")
        };
        *id = self.0[&kind][id].clone();
    }

    fn into_entries(self) -> Vec<IdMapping> {
        self.0
            .into_iter()
            .flat_map(|(kind, entries)| {
                entries.into_iter().map(move |(source, target)| IdMapping {
                    kind,
                    source,
                    target,
                })
            })
            .collect()
    }
}

fn rekey(entry: &mut Value, kind: ContentKind, mappings: &mut Mappings) {
    let entry = object_mut(entry);
    let mut bytes = Vec::new();
    json::encode(decode::member(entry, "definition"), &mut bytes);
    let target = content_id(&IrVersion::V0_2.domain(kind), &bytes);
    let Value::String(id) = member_mut(entry, "id") else {
        unreachable!("strict source identity")
    };
    let source = std::mem::replace(id, target.clone());
    mappings.0.entry(kind).or_default().insert(source, target);
}

/// 在闭合类型 / 表达式结构中，这三个成员只可能是类型引用。
/// 不重写任意字符串；Text、名称、枚举 member 即使等于 ID 也保持原样。
fn rewrite_type_references(value: &mut Value, mappings: &Mappings) {
    match value {
        Value::Object(members) => {
            for (key, value, _) in members {
                match key.as_str() {
                    "enum_type" => mappings.rewrite(value, ContentKind::EnumType),
                    "record_type" => mappings.rewrite(value, ContentKind::RecordType),
                    "table_type" => mappings.rewrite(value, ContentKind::TableType),
                    _ => rewrite_type_references(value, mappings),
                }
            }
        }
        Value::Array(values) => {
            for value in values {
                rewrite_type_references(value, mappings);
            }
        }
        Value::Bool(_) | Value::String(_) => {}
    }
}

fn record_order(types: &NormalizedTypeDeclarations) -> Vec<usize> {
    let records = types.record_types();
    let mut remaining = vec![0; records.len()];
    let mut dependents = vec![Vec::new(); records.len()];
    for (index, record) in records.iter().enumerate() {
        for field in &record.definition().fields {
            let mut ty = &field.value_type;
            while let ValueType::Option { inner } = ty {
                ty = inner;
            }
            if let ValueType::Record { record_type } = ty {
                let child = records
                    .binary_search_by(|entry| entry.id().cmp(record_type))
                    .expect("strict source record reference");
                remaining[index] += 1;
                dependents[child].push(index);
            }
        }
    }
    let mut ready: VecDeque<_> = remaining
        .iter()
        .enumerate()
        .filter_map(|(index, count)| (*count == 0).then_some(index))
        .collect();
    let mut order = Vec::with_capacity(records.len());
    while let Some(index) = ready.pop_front() {
        order.push(index);
        for &dependent in &dependents[index] {
            remaining[dependent] -= 1;
            if remaining[dependent] == 0 {
                ready.push_back(dependent);
            }
        }
    }
    assert_eq!(order.len(), records.len(), "strict source record DAG");
    order
}

fn object_mut(value: &mut Value) -> &mut Members {
    let Value::Object(members) = value else {
        unreachable!("strict source object")
    };
    members
}

fn entries_mut<'a>(root: &'a mut Members, key: &str) -> &'a mut Vec<Value> {
    let Value::Array(entries) = member_mut(root, key) else {
        unreachable!("strict source array")
    };
    entries
}

fn entry_id(value: &Value) -> &str {
    let Value::Object(members) = value else {
        unreachable!("strict source entry")
    };
    decode::string(decode::member(members, "id"), "").expect("strict source id")
}
