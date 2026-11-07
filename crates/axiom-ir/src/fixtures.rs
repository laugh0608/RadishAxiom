//! ADR 0032 的内部 P5 检查。读取 IR 与具体夹具，返回类型化表值或有界诊断。

use std::{collections::BTreeMap, fmt};

use crate::{
    contracts::{ContractKind, FormulaRole},
    declarations::{
        self as decode, DeclarationError, DeclarationErrorKind, RecordType, TableType, ValueType,
    },
    document::CanonicalDocument,
    integer::Integer,
    json::{self, JsonError, JsonErrorKind, JsonLimits, Value},
    nodes::NodeKind,
    normalization::{NormalizedDeclaration, NormalizedTypeDeclarations},
    version::IrVersion,
};

#[cfg(test)]
mod tests;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FixtureRole {
    Input,
    InvalidInput,
    GoldenOutput,
}

impl FixtureRole {
    fn tag(self) -> &'static str {
        match self {
            Self::Input => "input",
            Self::InvalidInput => "invalid-input",
            Self::GoldenOutput => "golden-output",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FixtureLimits {
    pub fixture_json: JsonLimits,
    /// 文档使用字节上限，实际解码的每项前置定义也使用层级和单元上限。
    pub ir_json: JsonLimits,
    /// 每一方向的接口数。
    pub max_tables: usize,
    /// 单份夹具的总行数。
    pub max_rows: usize,
    pub max_integer_digits: usize,
    pub max_precondition_checks: usize,
    /// 结果保存的身份、名称和标量的 UTF-8 字节总量。
    pub max_output_bytes: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum FixtureResource {
    FixtureJson(JsonError),
    PreconditionJson(JsonError),
    IrBytes,
    Tables,
    Rows,
    IntegerDigits,
    PreconditionChecks,
    OutputBytes,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum FixtureError {
    Json(JsonError),
    Structure(DeclarationError),
    Binding {
        field: &'static str,
    },
    Unsupported {
        subject: String,
    },
    InvalidValue {
        path: String,
        kind: FixtureValueError,
    },
    Capacity {
        table: String,
    },
    MissingTable {
        table: String,
    },
    DuplicateTable {
        table: String,
    },
    TableOrder {
        previous: String,
        table: String,
    },
    DuplicateKey {
        table: String,
        key: String,
    },
    Precondition {
        contract: String,
        table: String,
        key: String,
        left: String,
        right: String,
    },
    Resource(FixtureResource),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FixtureValueError {
    IntegerSyntax,
    IntegerRange,
    UnknownEnumMember,
}

impl fmt::Display for FixtureError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P5 fixture: {self:?}")
    }
}

impl std::error::Error for FixtureError {}

impl From<DeclarationError> for FixtureError {
    fn from(error: DeclarationError) -> Self {
        Self::Structure(error)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum FixtureValue {
    Int(Integer),
    Text(String),
    Enum(String),
}

pub type FixtureRow = BTreeMap<String, FixtureValue>;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FixtureTable {
    pub name: String,
    pub rows: Vec<FixtureRow>,
}

/// 绑定这次检查的 IR 与原始字节。表与行已经按规范顺序排列。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CheckedFixture {
    ir_document_id: String,
    fixture_digest: String,
    role: FixtureRole,
    tables: Vec<FixtureTable>,
}

impl CheckedFixture {
    pub fn ir_document_id(&self) -> &str {
        &self.ir_document_id
    }
    pub fn fixture_digest(&self) -> &str {
        &self.fixture_digest
    }
    pub fn role(&self) -> FixtureRole {
        self.role
    }
    pub fn tables(&self) -> &[FixtureTable] {
        &self.tables
    }
}

struct TableSchema<'a> {
    table: &'a TableType,
    record: &'a RecordType,
    key: &'a str,
}

struct Precondition<'a> {
    contract: &'a str,
    table: &'a str,
    key: &'a str,
    left: String,
    right: String,
}

/// 按指定角色检查原始夹具。黄金输出仅检查声明的输出表模式。
pub fn check_fixture(
    document: &CanonicalDocument,
    benchmark_id: &str,
    role: FixtureRole,
    bytes: &[u8],
    expected_digest: &str,
    limits: FixtureLimits,
) -> Result<CheckedFixture, FixtureError> {
    if document.version() != IrVersion::V0_2 {
        return Err(unsupported("IR version"));
    }
    if document.canonical_bytes().len() > limits.ir_json.max_input_bytes {
        return Err(FixtureError::Resource(FixtureResource::IrBytes));
    }
    if bytes.len() > limits.fixture_json.max_input_bytes {
        return Err(fixture_json_error(JsonError {
            kind: JsonErrorKind::ResourceLimit(json::ResourceLimit::InputBytes),
            offset: limits.fixture_json.max_input_bytes,
        }));
    }
    let fixture_digest = format!("sha256:{}", radishaxiom_digest::digest_hex(bytes));
    if fixture_digest != expected_digest {
        return Err(FixtureError::Binding { field: "sha256" });
    }
    let fixture = json::parse(bytes, limits.fixture_json).map_err(fixture_json_error)?;
    let root = decode::object(
        &fixture,
        "",
        &["format", "data_version", "benchmark_id", "role", "tables"],
    )?;
    for (field, expected) in [
        ("format", "axiom-benchmark-data"),
        ("data_version", "0.1"),
        ("benchmark_id", benchmark_id),
        ("role", role.tag()),
    ] {
        if text(root, field, "")? != expected {
            return Err(FixtureError::Binding { field });
        }
    }
    let raw_tables = decode::array(decode::member(root, "tables"), "/tables")?;
    if raw_tables.len() > limits.max_tables {
        return Err(FixtureError::Resource(FixtureResource::Tables));
    }

    let components = document.components();
    let graph = components.analysis().graph();
    let types = graph.types();
    let mut inputs = BTreeMap::new();
    for node in graph.nodes() {
        match node.kind() {
            NodeKind::Input => {
                let name = node.input_port().expect("checked input port");
                if inputs.len() == limits.max_tables {
                    return Err(FixtureError::Resource(FixtureResource::Tables));
                }
                inputs.insert(name, schema(types, node.table_type())?);
            }
            NodeKind::Filter | NodeKind::Map => {}
            _ => return Err(unsupported(node.supplied_id())),
        }
    }
    if graph.outputs().len() > limits.max_tables {
        return Err(FixtureError::Resource(FixtureResource::Tables));
    }
    let outputs = graph
        .outputs()
        .iter()
        .map(|output| {
            schema(types, graph.nodes()[output.node].table_type())
                .map(|schema| (output.name.as_str(), schema))
        })
        .collect::<Result<BTreeMap<_, _>, _>>()?;
    let preconditions = read_preconditions(document, &inputs, limits.ir_json)?;
    let schemas = if role == FixtureRole::GoldenOutput {
        &outputs
    } else {
        &inputs
    };
    let mut budget = Budget {
        rows: limits.max_rows,
        output: limits.max_output_bytes,
    };
    budget.output(document.document_id().len() + fixture_digest.len())?;
    let tables = read_tables(raw_tables, schemas, types, limits, &mut budget)?;
    if role != FixtureRole::GoldenOutput {
        check_preconditions(&tables, &preconditions, limits.max_precondition_checks)?;
    }
    Ok(CheckedFixture {
        ir_document_id: document.document_id().to_owned(),
        fixture_digest,
        role,
        tables: tables.into_values().collect(),
    })
}

fn schema<'a>(
    types: &'a NormalizedTypeDeclarations,
    id: &str,
) -> Result<TableSchema<'a>, FixtureError> {
    let table = definition(types.table_types(), id);
    let record = definition(types.record_types(), &table.record_type);
    let [key] = table.primary_key.as_slice() else {
        return Err(unsupported(id));
    };
    if !record
        .fields
        .iter()
        .any(|f| f.name == *key && f.value_type == ValueType::Text)
        || record.fields.iter().any(|f| {
            !matches!(
                f.value_type,
                ValueType::Int { .. } | ValueType::Text | ValueType::Enum { .. }
            )
        })
    {
        return Err(unsupported(id));
    }
    Ok(TableSchema { table, record, key })
}

fn definition<'a, T>(entries: &'a [NormalizedDeclaration<T>], id: &str) -> &'a T {
    let index = entries
        .binary_search_by(|entry| entry.id().cmp(id))
        .expect("checked type reference");
    entries[index].definition()
}

fn read_preconditions<'a>(
    document: &'a CanonicalDocument,
    inputs: &BTreeMap<&'a str, TableSchema<'a>>,
    limits: JsonLimits,
) -> Result<Vec<Precondition<'a>>, FixtureError> {
    let components = document.components();
    let mut assume_ids: Vec<_> = components
        .analysis()
        .contracts()
        .iter()
        .filter(|entry| {
            matches!(
                entry.kind(),
                ContractKind::Formula {
                    role: FormulaRole::Assume
                }
            )
        })
        .map(|entry| entry.supplied_id())
        .collect();
    assume_ids.sort_unstable();
    assume_ids
        .into_iter()
        .map(|contract| {
            let entries = components.contracts();
            let index = entries
                .binary_search_by(|entry| entry.id().cmp(contract))
                .expect("checked contract reference");
            let value =
                json::parse(entries[index].canonical_definition(), limits).map_err(|e| {
                    if matches!(e.kind, JsonErrorKind::ResourceLimit(_)) {
                        FixtureError::Resource(FixtureResource::PreconditionJson(e))
                    } else {
                        FixtureError::Json(e)
                    }
                })?;
            precondition(&value, inputs, contract).ok_or_else(|| unsupported(contract))
        })
        .collect()
}

fn precondition<'a>(
    value: &Value,
    inputs: &BTreeMap<&'a str, TableSchema<'a>>,
    contract: &'a str,
) -> Option<Precondition<'a>> {
    let root = decode::object(value, "", &["kind", "role", "expression"]).ok()?;
    let expression = decode::object(
        decode::member(root, "expression"),
        "",
        &["op", "table", "body"],
    )
    .ok()?;
    if text(expression, "op", "").ok()? != "forall_rows" {
        return None;
    }
    let table = decode::object(decode::member(expression, "table"), "", &["kind", "name"]).ok()?;
    if text(table, "kind", "").ok()? != "input" {
        return None;
    }
    let (&table, schema) = inputs.get_key_value(text(table, "name", "").ok()?)?;
    let body = decode::object(
        decode::member(expression, "body"),
        "",
        &["op", "left", "right"],
    )
    .ok()?;
    if text(body, "op", "").ok()? != "le" {
        return None;
    }
    Some(Precondition {
        contract,
        table,
        key: schema.key,
        left: row_field(decode::member(body, "left"))?.to_owned(),
        right: row_field(decode::member(body, "right"))?.to_owned(),
    })
}

fn row_field(value: &Value) -> Option<&str> {
    let field = decode::object(value, "", &["op", "record", "field"]).ok()?;
    let record = decode::object(decode::member(field, "record"), "", &["op", "index"]).ok()?;
    if text(field, "op", "").ok()? != "field"
        || text(record, "op", "").ok()? != "bound"
        || text(record, "index", "").ok()? != "0"
    {
        return None;
    }
    text(field, "field", "").ok()
}

fn check_preconditions(
    tables: &BTreeMap<&str, FixtureTable>,
    preconditions: &[Precondition<'_>],
    mut remaining: usize,
) -> Result<(), FixtureError> {
    for condition in preconditions {
        let table = &tables[condition.table];
        for row in &table.rows {
            charge(&mut remaining, 1, FixtureResource::PreconditionChecks)?;
            let (FixtureValue::Int(left), FixtureValue::Int(right)) =
                (&row[&condition.left], &row[&condition.right])
            else {
                unreachable!("checked Int comparison");
            };
            if left > right {
                return Err(FixtureError::Precondition {
                    contract: condition.contract.to_owned(),
                    table: table.name.clone(),
                    key: key(row, condition.key).to_owned(),
                    left: condition.left.clone(),
                    right: condition.right.clone(),
                });
            }
        }
    }
    Ok(())
}

fn read_tables<'a>(
    raw_tables: &[Value],
    schemas: &BTreeMap<&'a str, TableSchema<'_>>,
    types: &NormalizedTypeDeclarations,
    limits: FixtureLimits,
    budget: &mut Budget,
) -> Result<BTreeMap<&'a str, FixtureTable>, FixtureError> {
    let mut tables = BTreeMap::new();
    let mut previous: Option<&str> = None;
    for (i, raw) in raw_tables.iter().enumerate() {
        let path = format!("/tables/{i}");
        let table = decode::object(raw, &path, &["name", "rows"])?;
        let name = text(table, "name", &path)?;
        let Some((&name, schema)) = schemas.get_key_value(name) else {
            return Err(decode::error(
                DeclarationErrorKind::UnknownMember,
                &format!("{path}/name"),
            )
            .into());
        };
        if tables.contains_key(name) {
            return Err(FixtureError::DuplicateTable {
                table: name.to_owned(),
            });
        }
        if let Some(prior) = previous
            && prior > name
        {
            return Err(FixtureError::TableOrder {
                previous: prior.to_owned(),
                table: name.to_owned(),
            });
        }
        previous = Some(name);
        let rows_path = format!("{path}/rows");
        let raw_rows = decode::array(decode::member(table, "rows"), &rows_path)?;
        charge(&mut budget.rows, raw_rows.len(), FixtureResource::Rows)?;
        let count = Integer::parse(&raw_rows.len().to_string()).expect("row count");
        if count > schema.table.capacity {
            return Err(FixtureError::Capacity {
                table: name.to_owned(),
            });
        }
        budget.output(name.len())?;
        let mut rows = Vec::with_capacity(raw_rows.len());
        for (j, raw_row) in raw_rows.iter().enumerate() {
            rows.push(read_row(
                raw_row,
                schema.record,
                types,
                limits.max_integer_digits,
                &format!("{rows_path}/{j}"),
                budget,
            )?);
        }
        rows.sort_unstable_by(|left, right| key(left, schema.key).cmp(key(right, schema.key)));
        for pair in rows.windows(2) {
            let first = key(&pair[0], schema.key);
            if first == key(&pair[1], schema.key) {
                return Err(FixtureError::DuplicateKey {
                    table: name.to_owned(),
                    key: first.to_owned(),
                });
            }
        }
        tables.insert(
            name,
            FixtureTable {
                name: name.to_owned(),
                rows,
            },
        );
    }
    if let Some(&table) = schemas.keys().find(|name| !tables.contains_key(*name)) {
        return Err(FixtureError::MissingTable {
            table: table.to_owned(),
        });
    }
    Ok(tables)
}

fn read_row(
    raw: &Value,
    record: &RecordType,
    types: &NormalizedTypeDeclarations,
    integer_digits: usize,
    path: &str,
    budget: &mut Budget,
) -> Result<FixtureRow, FixtureError> {
    let Value::Object(members) = raw else {
        return Err(decode::error(DeclarationErrorKind::ExpectedObject, path).into());
    };
    let mut row = BTreeMap::new();
    for (name, value, _) in members {
        let field_path = decode::child(path, name);
        let index = record
            .fields
            .binary_search_by(|f| f.name.cmp(name))
            .map_err(|_| decode::error(DeclarationErrorKind::UnknownMember, &field_path))?;
        let text = decode::string(value, &field_path)?;
        budget.output(name.len())?;
        budget.output(text.len())?;
        let value = match &record.fields[index].value_type {
            ValueType::Text => FixtureValue::Text(text.to_owned()),
            ValueType::Enum { enum_type } => {
                if !definition(types.enum_types(), enum_type)
                    .members
                    .iter()
                    .any(|member| member == text)
                {
                    return Err(FixtureError::InvalidValue {
                        path: field_path,
                        kind: FixtureValueError::UnknownEnumMember,
                    });
                }
                FixtureValue::Enum(text.to_owned())
            }
            ValueType::Int { lower, upper } => {
                if text.strip_prefix('-').unwrap_or(text).len() > integer_digits {
                    return Err(FixtureError::Resource(FixtureResource::IntegerDigits));
                }
                let Some(number) = Integer::parse(text) else {
                    return Err(FixtureError::InvalidValue {
                        path: field_path,
                        kind: FixtureValueError::IntegerSyntax,
                    });
                };
                if &number < lower || &number > upper {
                    return Err(FixtureError::InvalidValue {
                        path: field_path,
                        kind: FixtureValueError::IntegerRange,
                    });
                }
                FixtureValue::Int(number)
            }
            _ => unreachable!("checked fixture type"),
        };
        row.insert(name.to_owned(), value);
    }
    if row.len() != record.fields.len() {
        let field = record
            .fields
            .iter()
            .find(|f| !row.contains_key(&f.name))
            .expect("missing field");
        return Err(decode::error(
            DeclarationErrorKind::MissingMember,
            &decode::child(path, &field.name),
        )
        .into());
    }
    Ok(row)
}

fn key<'a>(row: &'a FixtureRow, name: &str) -> &'a str {
    let FixtureValue::Text(value) = &row[name] else {
        unreachable!("checked Text key");
    };
    value
}

fn text<'a>(
    members: &'a decode::Members,
    field: &str,
    path: &str,
) -> Result<&'a str, DeclarationError> {
    decode::string(decode::member(members, field), &decode::child(path, field))
}

fn unsupported(subject: &str) -> FixtureError {
    FixtureError::Unsupported {
        subject: subject.to_owned(),
    }
}

fn fixture_json_error(error: JsonError) -> FixtureError {
    if matches!(error.kind, JsonErrorKind::ResourceLimit(_)) {
        FixtureError::Resource(FixtureResource::FixtureJson(error))
    } else {
        FixtureError::Json(error)
    }
}

struct Budget {
    rows: usize,
    output: usize,
}

impl Budget {
    fn output(&mut self, bytes: usize) -> Result<(), FixtureError> {
        charge(&mut self.output, bytes, FixtureResource::OutputBytes)
    }
}

fn charge(
    remaining: &mut usize,
    cost: usize,
    resource: FixtureResource,
) -> Result<(), FixtureError> {
    *remaining = remaining
        .checked_sub(cost)
        .ok_or(FixtureError::Resource(resource))?;
    Ok(())
}
