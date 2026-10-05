//! 支持范围内的完整文档规范字节、严格规范检查与文档身份。
//! 未支持表达式仍返回原组件错误；成功不证明公式、非干扰或完整 P1 验收。

use std::fmt;

use crate::contracts::{ContractError, NormalizedContracts, normalization::normalize_parsed};
use crate::declarations::{self as decode, DeclarationError, member_mut};
use crate::json::{self, JsonLimits, Value};
use crate::normalization::content_id;
use crate::version::{ContentKind, IrVersion};

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DocumentError {
    /// 保留结构、身份、Unsupported 和资源错误，不能一概解释为非法 IR。
    Ir(ContractError),
    /// 支持范围内输入可规范化，但与规范机器字节不同。offset 是首个差异字节，
    /// 或共同前缀结束处（其中一方 EOF）；不输出修复后文档冒充严格检查成功。
    NonCanonical { offset: usize },
}

impl fmt::Display for DocumentError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Ir(error) => error.fmt(f),
            Self::NonCanonical { offset } => write!(f, "IR is not canonical at byte {offset}"),
        }
    }
}
impl std::error::Error for DocumentError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Ir(error) => Some(error),
            Self::NonCanonical { .. } => None,
        }
    }
}
impl From<ContractError> for DocumentError {
    fn from(error: ContractError) -> Self {
        Self::Ir(error)
    }
}

/// 不可变的规范机器字节与文档域身份；不是 Evidence、proved 或 target gate 凭证。
/// components 的分析位置指向原输入，各规范数组则按 ID 排序。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CanonicalDocument {
    components: NormalizedContracts,
    canonical_bytes: Vec<u8>,
    document_id: String,
}

impl CanonicalDocument {
    pub fn version(&self) -> IrVersion {
        self.components.analysis().graph().types().version()
    }
    pub fn components(&self) -> &NormalizedContracts {
        &self.components
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.canonical_bytes
    }
    /// 按精确 IR 版本的 document 域 + NUL + canonical_bytes 计算的 SHA-256 ID，
    /// 不是文件原始 SHA-256，也不写入 IR 文档自身。
    pub fn document_id(&self) -> &str {
        &self.document_id
    }
}

/// 同一次有界解析完成现有组件检查 / 身份核对后组合整个规范文档。
/// 未支持项不产生成功输出；不修复 ID、删除死节点、去重声明或扩大类型范围。
pub fn normalize_document(
    input: &[u8],
    limits: JsonLimits,
) -> Result<CanonicalDocument, DocumentError> {
    let mut value = json::parse(input, limits)
        .map_err(|error| ContractError::Input(DeclarationError::Json(error)))?;
    let components = normalize_parsed(&mut value)?;
    let Value::Object(root) = &mut value else {
        unreachable!("checked root")
    };
    let Value::Array(outputs) = member_mut(root, "outputs") else {
        unreachable!("checked outputs")
    };
    outputs.sort_by(|left, right| output_name(left).cmp(output_name(right)));

    let types = components.analysis().graph().types();
    let mut canonical_bytes = Vec::with_capacity(input.len());
    canonical_bytes.push(b'{');
    for (index, (key, value, _)) in root.iter().enumerate() {
        if index != 0 {
            canonical_bytes.push(b',');
        }
        // 根成员已经闭合检查并由 JSON parser 按 JCS 对象键序排列。
        json::encode_string(key, &mut canonical_bytes);
        canonical_bytes.push(b':');
        match key.as_str() {
            "enum_types" => encode_entries(
                types
                    .enum_types()
                    .iter()
                    .map(|entry| (entry.id(), entry.canonical_definition())),
                &mut canonical_bytes,
            ),
            "record_types" => encode_entries(
                types
                    .record_types()
                    .iter()
                    .map(|entry| (entry.id(), entry.canonical_definition())),
                &mut canonical_bytes,
            ),
            "table_types" => encode_entries(
                types
                    .table_types()
                    .iter()
                    .map(|entry| (entry.id(), entry.canonical_definition())),
                &mut canonical_bytes,
            ),
            "nodes" => encode_entries(
                components
                    .nodes()
                    .iter()
                    .map(|entry| (entry.id(), entry.canonical_definition())),
                &mut canonical_bytes,
            ),
            "contracts" => encode_entries(
                components
                    .contracts()
                    .iter()
                    .map(|entry| (entry.id(), entry.canonical_definition())),
                &mut canonical_bytes,
            ),
            "digest_algorithm" | "effects" | "format" | "ir_version" | "semantics" | "outputs" => {
                json::encode(value, &mut canonical_bytes);
            }
            _ => unreachable!("checked root members"),
        }
    }
    canonical_bytes.push(b'}');
    let document_id = content_id(
        &types.version().domain(ContentKind::Document),
        &canonical_bytes,
    );
    Ok(CanonicalDocument {
        components,
        canonical_bytes,
        document_id,
    })
}

/// 完成全部支持范围检查后比较原输入与规范机器字节；资源 / 未支持 / 结构错误
/// 保留原诊断，不伪装成单纯格式差异。成功结果与 normalize_document 相同。
pub fn check_canonical_document(
    input: &[u8],
    limits: JsonLimits,
) -> Result<CanonicalDocument, DocumentError> {
    let result = normalize_document(input, limits)?;
    if input != result.canonical_bytes() {
        let offset = input
            .iter()
            .zip(result.canonical_bytes())
            .position(|(left, right)| left != right)
            .unwrap_or_else(|| input.len().min(result.canonical_bytes().len()));
        return Err(DocumentError::NonCanonical { offset });
    }
    Ok(result)
}

fn encode_entries<'a>(entries: impl Iterator<Item = (&'a str, &'a [u8])>, output: &mut Vec<u8>) {
    output.push(b'[');
    for (index, (id, definition)) in entries.enumerate() {
        if index != 0 {
            output.push(b',');
        }
        // 只拼接上游已核对的规范 definition；不另造编码 / 规范化口径或重新解析。
        output.extend_from_slice(b"{\"definition\":");
        output.extend_from_slice(definition);
        output.extend_from_slice(b",\"id\":");
        json::encode_string(id, output);
        output.push(b'}');
    }
    output.push(b']');
}

fn output_name(value: &Value) -> &str {
    let Value::Object(members) = value else {
        unreachable!("checked output")
    };
    decode::string(decode::member(members, "name"), "").expect("checked output name")
}
