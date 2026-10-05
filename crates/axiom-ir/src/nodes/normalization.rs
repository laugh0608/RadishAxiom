//! 已通过图分析的节点 definition 规范化与内容身份；不核准完整文档或契约。

use super::{NodeError, NodeGraphAnalysis, NodeKind, analyze_parsed};
use crate::declarations::{self as decode, DeclarationError, Members};
use crate::expressions::normalization::normalize_checked;
use crate::json::{self, JsonLimits, Value};
use crate::normalization::content_id;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NormalizedNode {
    id: String,
    canonical_definition: Vec<u8>,
}

impl NormalizedNode {
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn canonical_definition(&self) -> &[u8] {
        &self.canonical_definition
    }
}

/// 节点按 ID 排序；analysis 的索引仍指向原输入数组，不是此规范数组。
/// 节点 ID 已核对不代表非干扰、契约、完整文档或 P1 成功。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NormalizedNodeGraph {
    analysis: NodeGraphAnalysis,
    nodes: Vec<NormalizedNode>,
}

impl NormalizedNodeGraph {
    pub fn analysis(&self) -> &NodeGraphAnalysis {
        &self.analysis
    }
    pub fn nodes(&self) -> &[NormalizedNode] {
        &self.nodes
    }
}

/// 先在原输入上检查整个节点图，再规范逐行表达式 / 节点无语义顺序数组并重算 ID。
/// 不修复错误 ID、不重绑下游引用、不删除死节点、不接受 caller 缓存的图分析。
pub fn normalize_node_graph(
    input: &[u8],
    limits: JsonLimits,
) -> Result<NormalizedNodeGraph, NodeError> {
    let mut value = json::parse(input, limits).map_err(DeclarationError::Json)?;
    let analysis = analyze_parsed(&value)?;
    let Value::Object(root) = &mut value else {
        unreachable!("checked root")
    };
    let Value::Array(entries) = member_mut(root, "nodes") else {
        unreachable!("checked nodes")
    };
    let mut nodes = Vec::with_capacity(entries.len());
    for &index in analysis.topological_order() {
        let info = &analysis.nodes()[index];
        let Value::Object(entry) = &mut entries[index] else {
            unreachable!("checked entry")
        };
        let definition = member_mut(entry, "definition");
        normalize_definition(definition, info.kind());
        let mut canonical_definition = Vec::new();
        json::encode(definition, &mut canonical_definition);
        let computed = content_id("axiom-ir-v0.1:node", &canonical_definition);
        if computed != info.supplied_id() {
            return Err(NodeError::ContentIdMismatch {
                path: format!("/nodes/{index}/id"),
                supplied: info.supplied_id().to_owned(),
                computed,
            });
        }
        nodes.push(NormalizedNode {
            id: computed,
            canonical_definition,
        });
    }
    nodes.sort_by(|left, right| left.id.cmp(&right.id));
    Ok(NormalizedNodeGraph { analysis, nodes })
}

fn normalize_definition(value: &mut Value, kind: NodeKind) {
    let Value::Object(members) = value else {
        unreachable!("checked definition")
    };
    match kind {
        NodeKind::Input => {}
        NodeKind::Filter => normalize_checked(member_mut(members, "predicate")),
        NodeKind::Map | NodeKind::LookupJoin => {
            let Value::Array(fields) = member_mut(members, "fields") else {
                unreachable!("checked fields")
            };
            for field in fields.iter_mut() {
                let Value::Object(field) = field else {
                    unreachable!("checked field")
                };
                normalize_checked(member_mut(field, "expression"));
            }
            fields.sort_by(|left, right| name(left, "name").cmp(name(right, "name")));
            if kind == NodeKind::LookupJoin {
                let Value::Array(pairs) = member_mut(members, "pairs") else {
                    unreachable!("checked pairs")
                };
                pairs.sort_by(|left, right| {
                    (name(left, "left"), name(left, "right"))
                        .cmp(&(name(right, "left"), name(right, "right")))
                });
            }
        }
        NodeKind::Group => {
            let Value::Array(aggregates) = member_mut(members, "aggregates") else {
                unreachable!("checked aggregates")
            };
            aggregates.sort_by(|left, right| name(left, "name").cmp(name(right, "name")));
            // group.keys 与表主键同序，不可排序。
        }
    }
}

fn member_mut<'a>(members: &'a mut Members, key: &str) -> &'a mut Value {
    &mut members
        .iter_mut()
        .find(|(name, _, _)| name == key)
        .expect("checked member")
        .1
}

fn name<'a>(value: &'a Value, key: &str) -> &'a str {
    let Value::Object(members) = value else {
        unreachable!("checked object")
    };
    let Value::String(text) = decode::member(members, key) else {
        unreachable!("checked name")
    };
    text
}
