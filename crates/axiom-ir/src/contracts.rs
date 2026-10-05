//! 契约结构、类型与接口可见性分析。不计算契约 ID，不证明公式或非干扰。
use std::collections::BTreeSet;
use std::fmt;

use crate::declarations::{self as decode, DeclarationError, DeclarationErrorKind};
use crate::expressions::{ExpressionError, RowTypeChecker, tables::Interfaces};
use crate::json::{self, JsonLimits, Value};
use crate::nodes::{self, NodeError, NodeGraphAnalysis};

pub use crate::expressions::tables::{InterfaceKind, InterfaceReference};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FormulaRole {
    Assume,
    Guarantee,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ContractKind {
    Formula { role: FormulaRole },
    Noninterference,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ContractErrorKind {
    UnknownKind,
    UnknownRole,
    DuplicateId,
    EmptyInterfaces,
    DuplicateInterface,
    UnknownInterface,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ContractError {
    Input(DeclarationError),
    Node(NodeError),
    Expression(ExpressionError),
    Structure {
        kind: ContractErrorKind,
        path: String,
    },
}

impl fmt::Display for ContractError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Input(error) => write!(f, "contract input: {error}"),
            Self::Node(error) => error.fmt(f),
            Self::Expression(error) => error.fmt(f),
            Self::Structure { kind, path } => write!(f, "IR contract {kind:?} at {path:?}"),
        }
    }
}
impl std::error::Error for ContractError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Input(error) => Some(error),
            Self::Node(error) => Some(error),
            Self::Expression(error) => Some(error),
            Self::Structure { .. } => None,
        }
    }
}
impl From<DeclarationError> for ContractError {
    fn from(error: DeclarationError) -> Self {
        Self::Input(error)
    }
}
impl From<NodeError> for ContractError {
    fn from(error: NodeError) -> Self {
        Self::Node(error)
    }
}
impl From<ExpressionError> for ContractError {
    fn from(error: ExpressionError) -> Self {
        Self::Expression(error)
    }
}

/// 原 contracts 数组中的一项；supplied_id 只检查词法 / 唯一性。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ContractEntryAnalysis {
    supplied_id: String,
    kind: ContractKind,
    interfaces: Vec<InterfaceReference>,
}
impl ContractEntryAnalysis {
    pub fn supplied_id(&self) -> &str {
        &self.supplied_id
    }
    pub fn kind(&self) -> &ContractKind {
        &self.kind
    }
    /// 按 kind、名称排序并去除重复读取；node 指向原 nodes 数组。
    pub fn interfaces(&self) -> &[InterfaceReference] {
        &self.interfaces
    }
}

/// 支持范围内的结构 / 类型分析；节点与契约内容身份尚未核对，不是完整 IR 凭证。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ContractAnalysis {
    graph: NodeGraphAnalysis,
    contracts: Vec<ContractEntryAnalysis>,
}
impl ContractAnalysis {
    pub fn graph(&self) -> &NodeGraphAnalysis {
        &self.graph
    }
    pub fn contracts(&self) -> &[ContractEntryAnalysis] {
        &self.contracts
    }
}

/// 同一次有界解析检查图与全部契约；不接受 caller 缓存的接口、绑定或推导结果。
/// 顶层 effects 必须为空，全部支持操作均来自闭合的纯核心集合。
/// 不规范契约、不计算其身份、不求值或生成验证义务，不能称为 P1 完成。
pub fn analyze_contracts(
    input: &[u8],
    limits: JsonLimits,
) -> Result<ContractAnalysis, ContractError> {
    let value = json::parse(input, limits).map_err(DeclarationError::Json)?;
    let graph = nodes::analyze_parsed(&value)?;
    let Value::Object(root) = &value else {
        unreachable!("checked root")
    };
    let interfaces = Interfaces::new(&graph);
    let checker = RowTypeChecker::new(graph.types());
    let entries = decode::array(decode::member(root, "contracts"), "/contracts")?;
    let mut ids = BTreeSet::new();
    let mut contracts = Vec::with_capacity(entries.len());
    for (index, entry) in entries.iter().enumerate() {
        let path = format!("/contracts/{index}");
        let entry = decode::object(entry, &path, &["definition", "id"])?;
        let id_path = decode::child(&path, "id");
        let supplied_id = decode::id(decode::member(entry, "id"), &id_path)?;
        if !ids.insert(supplied_id.clone()) {
            return Err(error(ContractErrorKind::DuplicateId, &id_path));
        }
        let path = decode::child(&path, "definition");
        let definition = decode::member(entry, "definition");
        let kind_path = decode::child(&path, "kind");
        let Value::Object(members) = definition else {
            return Err(decode::error(DeclarationErrorKind::ExpectedObject, &path).into());
        };
        let kind = members
            .iter()
            .find(|(name, _, _)| name == "kind")
            .ok_or_else(|| decode::error(DeclarationErrorKind::MissingMember, &kind_path))?;
        let kind = decode::string(&kind.1, &kind_path)?;
        let (kind, referenced) = match kind {
            "formula" => {
                let members = decode::object(definition, &path, &["expression", "kind", "role"])?;
                let role_path = decode::child(&path, "role");
                let role = match decode::string(decode::member(members, "role"), &role_path)? {
                    "assume" => FormulaRole::Assume,
                    "guarantee" => FormulaRole::Guarantee,
                    _ => return Err(error(ContractErrorKind::UnknownRole, &role_path)),
                };
                let referenced = checker.infer_contract_parsed(
                    decode::member(members, "expression"),
                    &decode::child(&path, "expression"),
                    &interfaces,
                    role == FormulaRole::Guarantee,
                )?;
                (ContractKind::Formula { role }, referenced)
            }
            "noninterference" => {
                let members = decode::object(definition, &path, &["inputs", "kind", "outputs"])?;
                let mut referenced = interface_names(
                    decode::member(members, "inputs"),
                    &decode::child(&path, "inputs"),
                    InterfaceKind::Input,
                    &interfaces,
                )?;
                referenced.extend(interface_names(
                    decode::member(members, "outputs"),
                    &decode::child(&path, "outputs"),
                    InterfaceKind::Output,
                    &interfaces,
                )?);
                (ContractKind::Noninterference, referenced)
            }
            _ => return Err(error(ContractErrorKind::UnknownKind, &kind_path)),
        };
        contracts.push(ContractEntryAnalysis {
            supplied_id,
            kind,
            interfaces: referenced,
        });
    }
    Ok(ContractAnalysis { graph, contracts })
}

fn interface_names(
    value: &Value,
    path: &str,
    kind: InterfaceKind,
    interfaces: &Interfaces<'_>,
) -> Result<Vec<InterfaceReference>, ContractError> {
    let values = decode::array(value, path)?;
    if values.is_empty() {
        return Err(error(ContractErrorKind::EmptyInterfaces, path));
    }
    let mut names = BTreeSet::new();
    let mut result = Vec::with_capacity(values.len());
    for (index, value) in values.iter().enumerate() {
        let path = format!("{path}/{index}");
        let name = decode::name(value, &path)?;
        if !names.insert(name.clone()) {
            return Err(error(ContractErrorKind::DuplicateInterface, &path));
        }
        let (node, _) = interfaces
            .get(kind, &name)
            .ok_or_else(|| error(ContractErrorKind::UnknownInterface, &path))?;
        result.push(InterfaceReference { kind, name, node });
    }
    result.sort();
    Ok(result)
}
fn error(kind: ContractErrorKind, path: &str) -> ContractError {
    ContractError::Structure {
        kind,
        path: path.to_owned(),
    }
}
