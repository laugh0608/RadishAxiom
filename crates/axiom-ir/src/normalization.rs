//! 类型声明的规范数组与内容身份。成功只覆盖声明，不覆盖节点、契约、输出或整个 IR。

use crate::declarations::{
    DeclarationError, EnumType, Label, RecordType, TableType, UnverifiedDeclaration,
    UnverifiedTypeDeclarations, ValueType, decode_type_declarations,
};
use crate::json::{self, JsonLimits, Value};

/// 私有字段保证规范 definition、内容 ID 和类型化数据无法被独立修改。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NormalizedDeclaration<T> {
    id: String,
    definition: T,
    canonical_definition: Vec<u8>,
}

impl<T> NormalizedDeclaration<T> {
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn definition(&self) -> &T {
        &self.definition
    }
    pub fn canonical_definition(&self) -> &[u8] {
        &self.canonical_definition
    }
}

/// 三类声明各自按 ID 排序。此类型不代表完整 IR，也不能作为 target gate 的凭证。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NormalizedTypeDeclarations {
    enum_types: Vec<NormalizedDeclaration<EnumType>>,
    record_types: Vec<NormalizedDeclaration<RecordType>>,
    table_types: Vec<NormalizedDeclaration<TableType>>,
}

impl NormalizedTypeDeclarations {
    pub fn enum_types(&self) -> &[NormalizedDeclaration<EnumType>] {
        &self.enum_types
    }
    pub fn record_types(&self) -> &[NormalizedDeclaration<RecordType>] {
        &self.record_types
    }
    pub fn table_types(&self) -> &[NormalizedDeclaration<TableType>] {
        &self.table_types
    }
}

/// 复用有界声明解码，规范记录字段顺序并核对全部声明内容 ID。
/// 不重写引用、不修复错误 ID、不去重输入声明；枚举成员与主键顺序不变。
/// 仍不检查 nodes / contracts / outputs 的元素或完整程序基数。
pub fn normalize_type_declarations(
    input: &[u8],
    limits: JsonLimits,
) -> Result<NormalizedTypeDeclarations, DeclarationError> {
    let decoded = decode_type_declarations(input, limits)?;
    normalize_decoded_declarations(decoded)
}

pub(crate) fn normalize_decoded_declarations(
    decoded: UnverifiedTypeDeclarations,
) -> Result<NormalizedTypeDeclarations, DeclarationError> {
    Ok(NormalizedTypeDeclarations {
        enum_types: normalize(
            decoded.enum_types,
            "enum_types",
            "axiom-ir-v0.1:enum-type",
            enum_definition,
        )?,
        record_types: normalize(
            decoded.record_types,
            "record_types",
            "axiom-ir-v0.1:record-type",
            record_definition,
        )?,
        table_types: normalize(
            decoded.table_types,
            "table_types",
            "axiom-ir-v0.1:table-type",
            table_definition,
        )?,
    })
}

fn normalize<T>(
    entries: Vec<UnverifiedDeclaration<T>>,
    collection: &str,
    domain: &str,
    definition_value: fn(&mut T) -> Value,
) -> Result<Vec<NormalizedDeclaration<T>>, DeclarationError> {
    let mut result = Vec::with_capacity(entries.len());
    for (index, entry) in entries.into_iter().enumerate() {
        let mut definition = entry.definition;
        let value = definition_value(&mut definition);
        let mut canonical_definition = Vec::new();
        json::encode(&value, &mut canonical_definition);
        let computed = content_id(domain, &canonical_definition);
        if entry.supplied_id != computed {
            return Err(DeclarationError::ContentIdMismatch {
                path: format!("/{collection}/{index}/id"),
                supplied: entry.supplied_id,
                computed,
            });
        }
        result.push(NormalizedDeclaration {
            id: computed,
            definition,
            canonical_definition,
        });
    }
    // 解码已拒绝同类重复 ID，身份核对后无需默默去重或重映射引用。
    result.sort_by(|left, right| left.id.cmp(&right.id));
    Ok(result)
}

pub(crate) fn content_id(domain: &str, canonical_definition: &[u8]) -> String {
    let mut hash_input = Vec::with_capacity(domain.len() + 1 + canonical_definition.len());
    hash_input.extend_from_slice(domain.as_bytes());
    hash_input.push(0);
    hash_input.extend_from_slice(canonical_definition);
    format!("sha256:{}", radishaxiom_digest::digest_hex(&hash_input))
}

fn object<const N: usize>(members: [(&str, Value); N]) -> Value {
    let mut members: Vec<_> = members
        .into_iter()
        .map(|(key, value)| (key.to_owned(), value, 0))
        .collect();
    members.sort_by(|left, right| left.0.encode_utf16().cmp(right.0.encode_utf16()));
    Value::Object(members)
}

fn text(value: &str) -> Value {
    Value::String(value.to_owned())
}

fn names(values: &[String]) -> Value {
    Value::Array(values.iter().map(|value| text(value)).collect())
}

fn enum_definition(definition: &mut EnumType) -> Value {
    object([
        ("members", names(&definition.members)),
        ("name", text(&definition.name)),
    ])
}

fn record_definition(definition: &mut RecordType) -> Value {
    // 领域数组要求 Unicode scalar 序列顺序，与 JCS 属性名的 UTF-16 顺序不同。
    definition
        .fields
        .sort_by(|left, right| left.name.chars().cmp(right.name.chars()));
    object([(
        "fields",
        Value::Array(
            definition
                .fields
                .iter()
                .map(|field| {
                    object([
                        (
                            "label",
                            text(match field.label {
                                Label::Public => "public",
                                Label::Sensitive => "sensitive",
                            }),
                        ),
                        ("name", text(&field.name)),
                        ("type", value_type(&field.value_type)),
                    ])
                })
                .collect(),
        ),
    )])
}

fn table_definition(definition: &mut TableType) -> Value {
    object([
        ("capacity", text(definition.capacity.as_str())),
        ("primary_key", names(&definition.primary_key)),
        ("record_type", text(&definition.record_type)),
    ])
}

fn value_type(value: &ValueType) -> Value {
    match value {
        ValueType::Bool => object([("kind", text("bool"))]),
        ValueType::Text => object([("kind", text("text"))]),
        ValueType::Int { lower, upper } => object([
            ("kind", text("int")),
            ("lower", text(lower.as_str())),
            ("upper", text(upper.as_str())),
        ]),
        ValueType::Fixed {
            scale,
            lower,
            upper,
        } => object([
            ("kind", text("fixed")),
            ("lower", text(lower.as_str())),
            ("scale", text(scale.as_str())),
            ("upper", text(upper.as_str())),
        ]),
        ValueType::Enum { enum_type } => {
            object([("enum_type", text(enum_type)), ("kind", text("enum"))])
        }
        ValueType::Record { record_type } => {
            object([("kind", text("record")), ("record_type", text(record_type))])
        }
        ValueType::Option { inner } => {
            object([("inner", value_type(inner)), ("kind", text("option"))])
        }
    }
}
