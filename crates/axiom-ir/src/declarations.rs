//! 精确版本绑定下的类型声明解码及局部良构检查。
//! 返回值中的 ID 尚未重算，不表示整个 IR 合法；节点、契约、输出内容不在本层范围内。

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fmt;

use crate::integer::Integer;
use crate::json::{self, JsonError, JsonLimits, Value};
use crate::version::IrVersion;

pub use crate::version::V0_1_SEMANTICS_SHA256 as SEMANTICS_SHA256;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DeclarationErrorKind {
    ExpectedObject,
    ExpectedArray,
    ExpectedString,
    MissingMember,
    UnknownMember,
    UnsupportedValue,
    NonEmptyEffects,
    EmptyCollection,
    InvalidName,
    InvalidInteger,
    NegativeInteger,
    ReversedRange,
    InvalidId,
    DuplicateId,
    DuplicateName,
    UnresolvedReference,
    RecursiveRecord,
    InvalidPrimaryKey,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DeclarationError {
    Json(JsonError),
    /// 两个 ID 都是规范词法；只报告差异，不自动替换或修复输入。
    ContentIdMismatch {
        path: String,
        supplied: String,
        computed: String,
    },
    /// path 使用 JSON Pointer；空字符串指向根。索引指向原输入数组，不先排序。
    Structure {
        kind: DeclarationErrorKind,
        path: String,
    },
}

impl fmt::Display for DeclarationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Json(error) => error.fmt(f),
            Self::ContentIdMismatch {
                path,
                supplied,
                computed,
            } => {
                write!(
                    f,
                    "IR declaration content ID mismatch at {path:?}: supplied {supplied}, computed {computed}"
                )
            }
            Self::Structure { kind, path } => write!(f, "IR declaration {kind:?} at {path:?}"),
        }
    }
}

impl std::error::Error for DeclarationError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Json(error) => Some(error),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ValueType {
    Bool,
    Int {
        lower: Integer,
        upper: Integer,
    },
    Fixed {
        scale: Integer,
        lower: Integer,
        upper: Integer,
    },
    Text,
    Enum {
        enum_type: String,
    },
    Option {
        inner: Box<ValueType>,
    },
    Record {
        record_type: String,
    },
}

impl ValueType {
    /// 当前相等支持集合；记录及其任意 Option 包装尚无通用相等语义。
    pub(crate) fn supports_value_equality(&self) -> bool {
        let mut ty = self;
        while let Self::Option { inner } = ty {
            ty = inner;
        }
        !matches!(ty, Self::Record { .. })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Label {
    Public,
    Sensitive,
}

impl Label {
    pub(crate) fn join(self, other: Self) -> Self {
        if self == Self::Sensitive || other == Self::Sensitive {
            Self::Sensitive
        } else {
            Self::Public
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Field {
    pub name: String,
    pub label: Label,
    pub value_type: ValueType,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EnumType {
    pub name: String,
    /// 声明顺序有语义，保持输入顺序。
    pub members: Vec<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RecordType {
    /// 此解码步骤保持输入顺序；后续规范器按 Unicode scalar 排序。
    pub fields: Vec<Field>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TableType {
    pub capacity: Integer,
    pub primary_key: Vec<String>,
    pub record_type: String,
}

/// supplied_id 仅检查了词法；尚未绑定 definition 的规范字节摘要。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct UnverifiedDeclaration<T> {
    pub supplied_id: String,
    pub definition: T,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct UnverifiedTypeDeclarations {
    pub version: IrVersion,
    pub enum_types: Vec<UnverifiedDeclaration<EnumType>>,
    pub record_types: Vec<UnverifiedDeclaration<RecordType>>,
    pub table_types: Vec<UnverifiedDeclaration<TableType>>,
}

/// 从现有 IR candidate bytes 解码声明，不定义第二种声明文件格式。
/// 检查顶层闭合成员、版本、语义摘要、算法、空效果及各顶层数组形状；
/// 声明内部检查名称、整数、成员、类型引用、记录无环和主键约束。
/// 不检查 nodes / contracts / outputs 的元素、基数与语义，也不重算任何 ID。
/// 成功只返回 UnverifiedTypeDeclarations，不能作为 P1 或 target gate 的成功信号。
pub fn decode_type_declarations(
    input: &[u8],
    limits: JsonLimits,
) -> Result<UnverifiedTypeDeclarations, DeclarationError> {
    let value = json::parse(input, limits).map_err(DeclarationError::Json)?;
    decode_type_declarations_value(&value)
}

/// 复用同一次有界解析；调用方不能传入未经 JSON parser 检查的外部树。
pub(crate) fn decode_type_declarations_value(
    value: &Value,
) -> Result<UnverifiedTypeDeclarations, DeclarationError> {
    let root = object(
        value,
        "",
        &[
            "contracts",
            "digest_algorithm",
            "effects",
            "enum_types",
            "format",
            "ir_version",
            "nodes",
            "outputs",
            "record_types",
            "semantics",
            "table_types",
        ],
    )?;
    exact(root, "format", "", "axiom-ir")?;
    let version = IrVersion::parse(string(member(root, "ir_version"), "/ir_version")?)
        .ok_or_else(|| error(DeclarationErrorKind::UnsupportedValue, "/ir_version"))?;
    exact(root, "digest_algorithm", "", "sha-256")?;
    let semantics = object(member(root, "semantics"), "/semantics", &["name", "sha256"])?;
    exact(
        semantics,
        "name",
        "/semantics",
        "keyed-finite-table-semantics",
    )?;
    exact(
        semantics,
        "sha256",
        "/semantics",
        version.semantics_sha256(),
    )?;
    if !array(member(root, "effects"), "/effects")?.is_empty() {
        return Err(error(DeclarationErrorKind::NonEmptyEffects, "/effects"));
    }
    for key in ["nodes", "contracts", "outputs"] {
        array(member(root, key), &child("", key))?;
    }
    let result = UnverifiedTypeDeclarations {
        version,
        enum_types: declarations(member(root, "enum_types"), "/enum_types", enum_type)?,
        record_types: declarations(member(root, "record_types"), "/record_types", record_type)?,
        table_types: declarations(member(root, "table_types"), "/table_types", table_type)?,
    };
    check_references_and_keys(&result)?;
    Ok(result)
}

pub(crate) type Members = [(String, Value, usize)];

pub(crate) fn error(kind: DeclarationErrorKind, path: &str) -> DeclarationError {
    DeclarationError::Structure {
        kind,
        path: path.to_owned(),
    }
}

pub(crate) fn child(path: &str, key: &str) -> String {
    format!("{path}/{}", key.replace('~', "~0").replace('/', "~1"))
}

pub(crate) fn object<'a>(
    value: &'a Value,
    path: &str,
    keys: &[&str],
) -> Result<&'a Members, DeclarationError> {
    let Value::Object(members) = value else {
        return Err(error(DeclarationErrorKind::ExpectedObject, path));
    };
    for (key, _, _) in members {
        if !keys.contains(&key.as_str()) {
            return Err(error(
                DeclarationErrorKind::UnknownMember,
                &child(path, key),
            ));
        }
    }
    for key in keys {
        if !members.iter().any(|(found, _, _)| found == key) {
            return Err(error(
                DeclarationErrorKind::MissingMember,
                &child(path, key),
            ));
        }
    }
    Ok(members)
}

pub(crate) fn member<'a>(members: &'a Members, key: &str) -> &'a Value {
    &members
        .iter()
        .find(|(found, _, _)| found == key)
        .expect("closed members checked")
        .1
}

pub(crate) fn member_mut<'a>(members: &'a mut Members, key: &str) -> &'a mut Value {
    &mut members
        .iter_mut()
        .find(|(found, _, _)| found == key)
        .expect("closed members checked")
        .1
}

pub(crate) fn array<'a>(value: &'a Value, path: &str) -> Result<&'a [Value], DeclarationError> {
    match value {
        Value::Array(values) => Ok(values),
        _ => Err(error(DeclarationErrorKind::ExpectedArray, path)),
    }
}

pub(crate) fn string<'a>(value: &'a Value, path: &str) -> Result<&'a str, DeclarationError> {
    match value {
        Value::String(text) => Ok(text),
        _ => Err(error(DeclarationErrorKind::ExpectedString, path)),
    }
}

fn exact(members: &Members, key: &str, path: &str, expected: &str) -> Result<(), DeclarationError> {
    let path = child(path, key);
    if string(member(members, key), &path)? != expected {
        return Err(error(DeclarationErrorKind::UnsupportedValue, &path));
    }
    Ok(())
}

pub(crate) fn name(value: &Value, path: &str) -> Result<String, DeclarationError> {
    let text = string(value, path)?;
    if text.is_empty()
        || text
            .chars()
            .any(|ch| matches!(ch, '\u{0}'..='\u{1f}' | '\u{80}'..='\u{9f}'))
    {
        return Err(error(DeclarationErrorKind::InvalidName, path));
    }
    Ok(text.to_owned())
}

pub(crate) fn id(value: &Value, path: &str) -> Result<String, DeclarationError> {
    let text = string(value, path)?;
    let valid = text.strip_prefix("sha256:").is_some_and(|hex| {
        hex.len() == 64
            && hex
                .bytes()
                .all(|byte| matches!(byte, b'0'..=b'9' | b'a'..=b'f'))
    });
    if !valid {
        return Err(error(DeclarationErrorKind::InvalidId, path));
    }
    Ok(text.to_owned())
}

pub(crate) fn integer(
    value: &Value,
    path: &str,
    nonnegative: bool,
) -> Result<Integer, DeclarationError> {
    let integer = Integer::parse(string(value, path)?)
        .ok_or_else(|| error(DeclarationErrorKind::InvalidInteger, path))?;
    if nonnegative && integer.is_negative() {
        return Err(error(DeclarationErrorKind::NegativeInteger, path));
    }
    Ok(integer)
}

fn names(value: &Value, path: &str) -> Result<Vec<String>, DeclarationError> {
    let values = array(value, path)?;
    if values.is_empty() {
        return Err(error(DeclarationErrorKind::EmptyCollection, path));
    }
    let mut seen = BTreeSet::new();
    let mut result = Vec::new();
    for (index, value) in values.iter().enumerate() {
        let path = child(path, &index.to_string());
        let name = name(value, &path)?;
        if !seen.insert(name.clone()) {
            return Err(error(DeclarationErrorKind::DuplicateName, &path));
        }
        result.push(name);
    }
    Ok(result)
}

fn declarations<T>(
    value: &Value,
    path: &str,
    decode: fn(&Value, &str) -> Result<T, DeclarationError>,
) -> Result<Vec<UnverifiedDeclaration<T>>, DeclarationError> {
    let mut result = Vec::new();
    let mut seen = BTreeSet::new();
    for (index, value) in array(value, path)?.iter().enumerate() {
        let path = child(path, &index.to_string());
        let members = object(value, &path, &["definition", "id"])?;
        let id_path = child(&path, "id");
        let supplied_id = id(member(members, "id"), &id_path)?;
        if !seen.insert(supplied_id.clone()) {
            return Err(error(DeclarationErrorKind::DuplicateId, &id_path));
        }
        result.push(UnverifiedDeclaration {
            supplied_id,
            definition: decode(member(members, "definition"), &child(&path, "definition"))?,
        });
    }
    Ok(result)
}

fn enum_type(value: &Value, path: &str) -> Result<EnumType, DeclarationError> {
    let members = object(value, path, &["name", "members"])?;
    Ok(EnumType {
        name: name(member(members, "name"), &child(path, "name"))?,
        members: names(member(members, "members"), &child(path, "members"))?,
    })
}

fn record_type(value: &Value, path: &str) -> Result<RecordType, DeclarationError> {
    let members = object(value, path, &["fields"])?;
    let path = child(path, "fields");
    let values = array(member(members, "fields"), &path)?;
    if values.is_empty() {
        return Err(error(DeclarationErrorKind::EmptyCollection, &path));
    }
    let mut fields = Vec::new();
    let mut seen = BTreeSet::new();
    for (index, value) in values.iter().enumerate() {
        let path = child(&path, &index.to_string());
        let field = object(value, &path, &["name", "label", "type"])?;
        let name_path = child(&path, "name");
        let name = name(member(field, "name"), &name_path)?;
        if !seen.insert(name.clone()) {
            return Err(error(DeclarationErrorKind::DuplicateName, &name_path));
        }
        let label_path = child(&path, "label");
        let label = match string(member(field, "label"), &label_path)? {
            "public" => Label::Public,
            "sensitive" => Label::Sensitive,
            _ => return Err(error(DeclarationErrorKind::UnsupportedValue, &label_path)),
        };
        fields.push(Field {
            name,
            label,
            value_type: value_type(member(field, "type"), &child(&path, "type"))?,
        });
    }
    Ok(RecordType { fields })
}

fn table_type(value: &Value, path: &str) -> Result<TableType, DeclarationError> {
    let members = object(value, path, &["capacity", "primary_key", "record_type"])?;
    Ok(TableType {
        capacity: integer(member(members, "capacity"), &child(path, "capacity"), true)?,
        primary_key: names(member(members, "primary_key"), &child(path, "primary_key"))?,
        record_type: id(member(members, "record_type"), &child(path, "record_type"))?,
    })
}

pub(crate) fn value_type(value: &Value, path: &str) -> Result<ValueType, DeclarationError> {
    let Value::Object(members) = value else {
        return Err(error(DeclarationErrorKind::ExpectedObject, path));
    };
    let kind_path = child(path, "kind");
    let kind = members
        .iter()
        .find(|(key, _, _)| key == "kind")
        .ok_or_else(|| error(DeclarationErrorKind::MissingMember, &kind_path))?;
    let kind = string(&kind.1, &kind_path)?;
    let keys: &[&str] = match kind {
        "bool" | "text" => &["kind"],
        "int" => &["kind", "lower", "upper"],
        "fixed" => &["kind", "scale", "lower", "upper"],
        "enum" => &["kind", "enum_type"],
        "option" => &["kind", "inner"],
        "record" => &["kind", "record_type"],
        _ => return Err(error(DeclarationErrorKind::UnsupportedValue, &kind_path)),
    };
    let members = object(value, path, keys)?;
    Ok(match kind {
        "bool" => ValueType::Bool,
        "text" => ValueType::Text,
        "int" | "fixed" => {
            let lower = integer(member(members, "lower"), &child(path, "lower"), false)?;
            let upper = integer(member(members, "upper"), &child(path, "upper"), false)?;
            if lower > upper {
                return Err(error(DeclarationErrorKind::ReversedRange, path));
            }
            if kind == "int" {
                ValueType::Int { lower, upper }
            } else {
                ValueType::Fixed {
                    lower,
                    upper,
                    scale: integer(member(members, "scale"), &child(path, "scale"), true)?,
                }
            }
        }
        "enum" => ValueType::Enum {
            enum_type: id(member(members, "enum_type"), &child(path, "enum_type"))?,
        },
        "record" => ValueType::Record {
            record_type: id(member(members, "record_type"), &child(path, "record_type"))?,
        },
        "option" => ValueType::Option {
            inner: Box::new(value_type(member(members, "inner"), &child(path, "inner"))?),
        },
        _ => unreachable!("kind validated"),
    })
}

fn check_references_and_keys(types: &UnverifiedTypeDeclarations) -> Result<(), DeclarationError> {
    let enum_ids: BTreeSet<_> = types
        .enum_types
        .iter()
        .map(|value| value.supplied_id.as_str())
        .collect();
    let record_ids: BTreeMap<_, _> = types
        .record_types
        .iter()
        .enumerate()
        .map(|(index, value)| (value.supplied_id.as_str(), index))
        .collect();
    // 类型引用图可能比 JSON 嵌套深，使用队列消除依赖，避免沿引用递归导致栈溢出。
    let mut dependent_records = vec![Vec::new(); types.record_types.len()];
    let mut dependency_count = vec![0usize; types.record_types.len()];
    for (index, record) in types.record_types.iter().enumerate() {
        for (field_index, field) in record.definition.fields.iter().enumerate() {
            let mut path = format!("/record_types/{index}/definition/fields/{field_index}/type");
            let mut value_type = &field.value_type;
            while let ValueType::Option { inner } = value_type {
                value_type = inner;
                path.push_str("/inner");
            }
            match value_type {
                ValueType::Enum { enum_type } if !enum_ids.contains(enum_type.as_str()) => {
                    return Err(error(
                        DeclarationErrorKind::UnresolvedReference,
                        &child(&path, "enum_type"),
                    ));
                }
                ValueType::Record { record_type } => {
                    let referenced = record_ids.get(record_type.as_str()).ok_or_else(|| {
                        error(
                            DeclarationErrorKind::UnresolvedReference,
                            &child(&path, "record_type"),
                        )
                    })?;
                    dependency_count[index] += 1;
                    dependent_records[*referenced].push(index);
                }
                _ => {}
            }
        }
    }
    let mut ready: VecDeque<_> = dependency_count
        .iter()
        .enumerate()
        .filter_map(|(index, count)| (*count == 0).then_some(index))
        .collect();
    let mut visited = 0;
    while let Some(index) = ready.pop_front() {
        visited += 1;
        for dependent in &dependent_records[index] {
            dependency_count[*dependent] -= 1;
            if dependency_count[*dependent] == 0 {
                ready.push_back(*dependent);
            }
        }
    }
    if visited != types.record_types.len() {
        return Err(error(
            DeclarationErrorKind::RecursiveRecord,
            "/record_types",
        ));
    }
    // 多张表可以共享一个宽记录，字段索引只构造一次，避免交叉放大处理量。
    let record_fields: Vec<BTreeMap<_, _>> = types
        .record_types
        .iter()
        .map(|record| {
            record
                .definition
                .fields
                .iter()
                .map(|field| (field.name.as_str(), field))
                .collect()
        })
        .collect();
    for (index, table) in types.table_types.iter().enumerate() {
        let path = format!("/table_types/{index}/definition");
        let record_index = record_ids
            .get(table.definition.record_type.as_str())
            .ok_or_else(|| {
                error(
                    DeclarationErrorKind::UnresolvedReference,
                    &child(&path, "record_type"),
                )
            })?;
        let fields = &record_fields[*record_index];
        for (key_index, key) in table.definition.primary_key.iter().enumerate() {
            let key_path = format!("{path}/primary_key/{key_index}");
            let field = fields
                .get(key.as_str())
                .ok_or_else(|| error(DeclarationErrorKind::InvalidPrimaryKey, &key_path))?;
            if field.label != Label::Public
                || matches!(
                    field.value_type,
                    ValueType::Option { .. } | ValueType::Record { .. }
                )
            {
                return Err(error(DeclarationErrorKind::InvalidPrimaryKey, &key_path));
            }
        }
    }
    Ok(())
}
