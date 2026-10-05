//! 节点结构、局部类型、图分析及内容身份。
//! analyze_node_graph 只检查 ID 词法和引用；normalize_node_graph 另核对规范内容。
//! 重建保守字段 / 控制标签，不检查契约或证明非干扰，不提供完整 IR / P1 成功入口。

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fmt;

use crate::declarations::{self as decode, DeclarationError, Members, TableType};
use crate::expressions::{ExpressionError, RowTypeChecker};
use crate::json::{self, JsonLimits, Value};
use crate::normalization::{NormalizedTypeDeclarations, normalize_decoded_declarations};

mod flow;
mod normalization;
mod typing;

pub use flow::{FieldLabelGap, NodeFlowAnalysis};
pub use normalization::{NormalizedNode, NormalizedNodeGraph, normalize_node_graph};

#[cfg(test)]
mod tests;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NodeKind {
    Input,
    Filter,
    Map,
    LookupJoin,
    Group,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NodeErrorKind {
    UnknownKind,
    MissingInput,
    MissingOutput,
    DuplicateId,
    DuplicateName,
    UnresolvedReference,
    Cycle,
    DeadNode,
    UnknownField,
    IncompleteFields,
    TypeMismatch,
    FilterShapeMismatch,
    CapacityMismatch,
    EmptyPairs,
    DuplicatePair,
    InvalidGroupKey,
    InvalidAggregate,
    InvalidKeyProjection,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum NodeError {
    Input(DeclarationError),
    Expression(ExpressionError),
    ContentIdMismatch {
        path: String,
        supplied: String,
        computed: String,
    },
    Structure {
        kind: NodeErrorKind,
        path: String,
    },
    /// 首批只识别直接读取源键的投影；复杂表达式不被误判为规范非法。
    UnsupportedKeyExpression {
        path: String,
    },
}

impl fmt::Display for NodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Input(error) => write!(f, "node input: {error}"),
            Self::Expression(error) => error.fmt(f),
            Self::ContentIdMismatch {
                path,
                supplied,
                computed,
            } => {
                write!(
                    f,
                    "IR node content ID mismatch at {path:?}: supplied {supplied}, computed {computed}"
                )
            }
            Self::Structure { kind, path } => write!(f, "IR node {kind:?} at {path:?}"),
            Self::UnsupportedKeyExpression { path } => {
                write!(f, "unsupported key projection expression at {path:?}")
            }
        }
    }
}

impl std::error::Error for NodeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Input(error) => Some(error),
            Self::Expression(error) => Some(error),
            _ => None,
        }
    }
}

impl From<DeclarationError> for NodeError {
    fn from(value: DeclarationError) -> Self {
        Self::Input(value)
    }
}

impl From<ExpressionError> for NodeError {
    fn from(value: ExpressionError) -> Self {
        Self::Expression(value)
    }
}

/// 原输入顺序下的局部分析摘要，不是规范节点 definition。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NodeAnalysis {
    supplied_id: String,
    kind: NodeKind,
    table_type: String,
    input_port: Option<String>,
    predecessors: Vec<usize>,
}

impl NodeAnalysis {
    pub fn supplied_id(&self) -> &str {
        &self.supplied_id
    }
    pub fn kind(&self) -> NodeKind {
        self.kind
    }
    pub fn table_type(&self) -> &str {
        &self.table_type
    }
    pub fn input_port(&self) -> Option<&str> {
        self.input_port.as_deref()
    }
    /// 索引指向原 nodes 数组；join 顺序为 [left, right]，允许同一前驱出现两次。
    pub fn predecessors(&self) -> &[usize] {
        &self.predecessors
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OutputReference {
    pub name: String,
    /// 原 nodes 数组中的位置，不是拓扑顺序中的位置。
    pub node: usize,
}

/// 声明 ID 已核对；此类型本身不保证节点 ID 已核对，不能作为完整 IR 或执行门控凭证。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NodeGraphAnalysis {
    types: NormalizedTypeDeclarations,
    nodes: Vec<NodeAnalysis>,
    outputs: Vec<OutputReference>,
    topological_order: Vec<usize>,
    node_flows: Vec<NodeFlowAnalysis>,
}

impl NodeGraphAnalysis {
    pub fn types(&self) -> &NormalizedTypeDeclarations {
        &self.types
    }
    pub fn nodes(&self) -> &[NodeAnalysis] {
        &self.nodes
    }
    pub fn outputs(&self) -> &[OutputReference] {
        &self.outputs
    }
    pub fn topological_order(&self) -> &[usize] {
        &self.topological_order
    }
    /// 与原 nodes 数组一一对应；保守分析提示不是 proved / failed 判定。
    pub fn node_flows(&self) -> &[NodeFlowAnalysis] {
        &self.node_flows
    }
}

struct ParsedNode<'a> {
    analysis: NodeAnalysis,
    definition: &'a Members,
    path: String,
    table: &'a TableType,
    references: Vec<(&'static str, String)>,
}

/// 从同一 candidate bytes 检查声明身份、节点结构 / 类型、DAG 和输出引用。
/// 只解析一次，所有诊断保留原数组位置；不接收调用方缓存的类型或图。
/// contracts 仍只检查数组形状；成功不代表节点身份、完整效果或 P1 已验收。
pub fn analyze_node_graph(
    input: &[u8],
    limits: JsonLimits,
) -> Result<NodeGraphAnalysis, NodeError> {
    let value = json::parse(input, limits).map_err(DeclarationError::Json)?;
    analyze_parsed(&value)
}

fn analyze_parsed(value: &Value) -> Result<NodeGraphAnalysis, NodeError> {
    let types = normalize_decoded_declarations(decode::decode_type_declarations_value(value)?)?;
    let Value::Object(root) = value else {
        unreachable!("declaration decoder checked the root")
    };
    let mut nodes = parse_nodes(decode::member(root, "nodes"), &types)?;
    let ids: BTreeMap<_, _> = nodes
        .iter()
        .enumerate()
        .map(|(index, node)| (node.analysis.supplied_id.clone(), index))
        .collect();
    for node in &mut nodes {
        for (key, id) in &node.references {
            let index = ids.get(id).ok_or_else(|| {
                error(
                    NodeErrorKind::UnresolvedReference,
                    &decode::child(&node.path, key),
                )
            })?;
            node.analysis.predecessors.push(*index);
        }
    }
    let outputs = parse_outputs(decode::member(root, "outputs"), &ids)?;
    let topological_order = check_graph(&nodes, &outputs)?;
    let checker = RowTypeChecker::new(&types);
    for &index in &topological_order {
        typing::check_node(&nodes, index, &types, &checker)?;
    }
    let node_flows = flow::analyze_checked(&nodes, &topological_order, &types);
    let nodes = nodes.into_iter().map(|node| node.analysis).collect();
    Ok(NodeGraphAnalysis {
        types,
        nodes,
        outputs,
        topological_order,
        node_flows,
    })
}

fn error(kind: NodeErrorKind, path: &str) -> NodeError {
    NodeError::Structure {
        kind,
        path: path.to_owned(),
    }
}

fn parse_nodes<'a>(
    value: &'a Value,
    types: &'a NormalizedTypeDeclarations,
) -> Result<Vec<ParsedNode<'a>>, NodeError> {
    let mut result = Vec::new();
    let mut ids = BTreeSet::new();
    let mut ports = BTreeSet::new();
    for (index, value) in decode::array(value, "/nodes")?.iter().enumerate() {
        let entry_path = format!("/nodes/{index}");
        let entry = decode::object(value, &entry_path, &["id", "definition"])?;
        let supplied_id = decode::id(
            decode::member(entry, "id"),
            &decode::child(&entry_path, "id"),
        )?;
        if !ids.insert(supplied_id.clone()) {
            return Err(error(
                NodeErrorKind::DuplicateId,
                &decode::child(&entry_path, "id"),
            ));
        }
        let path = decode::child(&entry_path, "definition");
        let value = decode::member(entry, "definition");
        let kind = tagged_kind(value, &path)?;
        let (kind, keys, references): (NodeKind, &[_], &[_]) = match kind {
            "input" => (NodeKind::Input, &["kind", "port", "table_type"], &[]),
            "filter" => (
                NodeKind::Filter,
                &["kind", "predicate", "source", "table_type"],
                &["source"],
            ),
            "map" => (
                NodeKind::Map,
                &["kind", "fields", "source", "table_type"],
                &["source"],
            ),
            "lookup_join" => (
                NodeKind::LookupJoin,
                &["kind", "fields", "left", "pairs", "right", "table_type"],
                &["left", "right"],
            ),
            "group" => (
                NodeKind::Group,
                &["kind", "aggregates", "keys", "source", "table_type"],
                &["source"],
            ),
            _ => {
                return Err(error(
                    NodeErrorKind::UnknownKind,
                    &decode::child(&path, "kind"),
                ));
            }
        };
        let definition = decode::object(value, &path, keys)?;
        let type_path = decode::child(&path, "table_type");
        let table_type = decode::id(decode::member(definition, "table_type"), &type_path)?;
        let table_index = types
            .table_types()
            .binary_search_by(|entry| entry.id().cmp(&table_type))
            .map_err(|_| error(NodeErrorKind::UnresolvedReference, &type_path))?;
        let input_port = if kind == NodeKind::Input {
            let port_path = decode::child(&path, "port");
            let port = decode::name(decode::member(definition, "port"), &port_path)?;
            if !ports.insert(port.clone()) {
                return Err(error(NodeErrorKind::DuplicateName, &port_path));
            }
            Some(port)
        } else {
            None
        };
        let references = references
            .iter()
            .map(|&key| {
                Ok((
                    key,
                    decode::id(decode::member(definition, key), &decode::child(&path, key))?,
                ))
            })
            .collect::<Result<_, DeclarationError>>()?;
        result.push(ParsedNode {
            analysis: NodeAnalysis {
                supplied_id,
                kind,
                table_type,
                input_port,
                predecessors: Vec::new(),
            },
            definition,
            path,
            table: types.table_types()[table_index].definition(),
            references,
        });
    }
    if ports.is_empty() {
        return Err(error(NodeErrorKind::MissingInput, "/nodes"));
    }
    Ok(result)
}

fn tagged_kind<'a>(value: &'a Value, path: &str) -> Result<&'a str, NodeError> {
    let Value::Object(members) = value else {
        return Err(decode::error(decode::DeclarationErrorKind::ExpectedObject, path).into());
    };
    let kind_path = decode::child(path, "kind");
    let value = members
        .iter()
        .find(|(key, _, _)| key == "kind")
        .ok_or_else(|| decode::error(decode::DeclarationErrorKind::MissingMember, &kind_path))?;
    Ok(decode::string(&value.1, &kind_path)?)
}

fn parse_outputs(
    value: &Value,
    ids: &BTreeMap<String, usize>,
) -> Result<Vec<OutputReference>, NodeError> {
    let mut result = Vec::new();
    let mut names = BTreeSet::new();
    for (index, value) in decode::array(value, "/outputs")?.iter().enumerate() {
        let path = format!("/outputs/{index}");
        let members = decode::object(value, &path, &["name", "node"])?;
        let name_path = decode::child(&path, "name");
        let name = decode::name(decode::member(members, "name"), &name_path)?;
        if !names.insert(name.clone()) {
            return Err(error(NodeErrorKind::DuplicateName, &name_path));
        }
        let node_path = decode::child(&path, "node");
        let id = decode::id(decode::member(members, "node"), &node_path)?;
        let node = *ids
            .get(&id)
            .ok_or_else(|| error(NodeErrorKind::UnresolvedReference, &node_path))?;
        result.push(OutputReference { name, node });
    }
    if result.is_empty() {
        return Err(error(NodeErrorKind::MissingOutput, "/outputs"));
    }
    Ok(result)
}

fn check_graph(
    nodes: &[ParsedNode<'_>],
    outputs: &[OutputReference],
) -> Result<Vec<usize>, NodeError> {
    let mut indegrees: Vec<_> = nodes
        .iter()
        .map(|node| node.analysis.predecessors.len())
        .collect();
    let mut successors = vec![Vec::new(); nodes.len()];
    let mut ready = VecDeque::new();
    for (index, node) in nodes.iter().enumerate() {
        if indegrees[index] == 0 {
            ready.push_back(index);
        }
        for &source in &node.analysis.predecessors {
            successors[source].push(index);
        }
    }
    let mut order = Vec::with_capacity(nodes.len());
    while let Some(index) = ready.pop_front() {
        order.push(index);
        for &next in &successors[index] {
            indegrees[next] -= 1;
            if indegrees[next] == 0 {
                ready.push_back(next);
            }
        }
    }
    if order.len() != nodes.len() {
        // Kahn 的残余可能含环的下游；沿残余前驱迭代，定位真正成环的引用。
        let mut index = indegrees
            .iter()
            .position(|&degree| degree != 0)
            .expect("residual graph");
        let mut seen = vec![false; nodes.len()];
        loop {
            seen[index] = true;
            let node = &nodes[index];
            let edge = node
                .analysis
                .predecessors
                .iter()
                .position(|&source| indegrees[source] != 0)
                .expect("each residual node has a residual predecessor");
            let source = node.analysis.predecessors[edge];
            if seen[source] {
                return Err(error(
                    NodeErrorKind::Cycle,
                    &decode::child(&node.path, node.references[edge].0),
                ));
            }
            index = source;
        }
    }
    // 所有无前驱节点都是 input，因此 DAG 中每个节点均由 input 到达。
    let mut live = vec![false; nodes.len()];
    let mut pending = Vec::new();
    for output in outputs {
        if !live[output.node] {
            live[output.node] = true;
            pending.push(output.node);
        }
    }
    while let Some(index) = pending.pop() {
        for &source in &nodes[index].analysis.predecessors {
            if !live[source] {
                live[source] = true;
                pending.push(source);
            }
        }
    }
    for (index, node) in nodes.iter().enumerate() {
        if !live[index] && node.analysis.kind != NodeKind::Input {
            return Err(error(NodeErrorKind::DeadNode, &format!("/nodes/{index}")));
        }
    }
    Ok(order)
}
