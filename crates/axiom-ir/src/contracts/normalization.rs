//! 已检查契约的规范 definition 与身份；不求值、生成证明或规范完整文档。

use super::{ContractAnalysis, ContractError, ContractKind, analyze_parsed};
use crate::declarations::{self as decode, DeclarationError, member_mut};
use crate::expressions::normalization::normalize_checked;
use crate::json::{self, JsonLimits, Value};
use crate::nodes::{NormalizedNode, normalization::normalize_checked_graph};
use crate::normalization::content_id;
use crate::version::ContentKind;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NormalizedContract {
    id: String,
    canonical_definition: Vec<u8>,
}

impl NormalizedContract {
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn canonical_definition(&self) -> &[u8] {
        &self.canonical_definition
    }
}

/// 类型、节点与契约身份均已核对；nodes / contracts 各按 ID 排序。
/// analysis 保留原输入位置；仍不输出 canonical IR、文档摘要或 P1 成功信号。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NormalizedContracts {
    analysis: ContractAnalysis,
    nodes: Vec<NormalizedNode>,
    contracts: Vec<NormalizedContract>,
}

impl NormalizedContracts {
    pub fn analysis(&self) -> &ContractAnalysis {
        &self.analysis
    }
    pub fn nodes(&self) -> &[NormalizedNode] {
        &self.nodes
    }
    pub fn contracts(&self) -> &[NormalizedContract] {
        &self.contracts
    }
}

/// 同一次有界解析先完成全部原始节点 / 契约检查，再规范节点和契约并核对 ID。
/// 不修复 ID、不重绑接口、不合并逻辑等价公式，不改 lookup.keys 或绑定索引。
pub fn normalize_contracts(
    input: &[u8],
    limits: JsonLimits,
) -> Result<NormalizedContracts, ContractError> {
    let mut value = json::parse(input, limits).map_err(DeclarationError::Json)?;
    normalize_parsed(&mut value)
}

/// 保留同一次有界解析的树，供文档组合使用；不接受 caller 提供的分析缓存。
pub(crate) fn normalize_parsed(value: &mut Value) -> Result<NormalizedContracts, ContractError> {
    let analysis = analyze_parsed(value)?;
    let nodes = normalize_checked_graph(value, analysis.graph())?;
    let Value::Object(root) = value else {
        unreachable!("checked root")
    };
    let Value::Array(entries) = member_mut(root, "contracts") else {
        unreachable!("checked contracts")
    };
    let mut contracts = Vec::with_capacity(entries.len());
    for (index, (entry, info)) in entries.iter_mut().zip(analysis.contracts()).enumerate() {
        let Value::Object(entry) = entry else {
            unreachable!("checked entry")
        };
        let definition = member_mut(entry, "definition");
        let Value::Object(members) = definition else {
            unreachable!("checked definition")
        };
        match info.kind() {
            ContractKind::Formula { .. } => normalize_checked(member_mut(members, "expression")),
            ContractKind::Noninterference => {
                for key in ["inputs", "outputs"] {
                    let Value::Array(names) = member_mut(members, key) else {
                        unreachable!("checked interfaces")
                    };
                    names.sort_by(|left, right| {
                        // Rust 字符串序与 Unicode scalar 序相同，不使用 JCS 编码排序。
                        decode::string(left, "")
                            .expect("checked name")
                            .cmp(decode::string(right, "").expect("checked name"))
                    });
                }
            }
        }
        let mut canonical_definition = Vec::new();
        json::encode(definition, &mut canonical_definition);
        let computed = content_id(
            &analysis
                .graph()
                .types()
                .version()
                .domain(ContentKind::Contract),
            &canonical_definition,
        );
        if computed != info.supplied_id() {
            return Err(ContractError::ContentIdMismatch {
                path: format!("/contracts/{index}/id"),
                supplied: info.supplied_id().to_owned(),
                computed,
            });
        }
        contracts.push(NormalizedContract {
            id: computed,
            canonical_definition,
        });
    }
    contracts.sort_by(|left, right| left.id.cmp(&right.id));
    Ok(NormalizedContracts {
        analysis,
        nodes,
        contracts,
    })
}
