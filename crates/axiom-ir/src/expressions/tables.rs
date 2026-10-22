//! 契约表操作的类型规则；共用标量推导与绑定栈，不执行表、范围或存在性证明。
use std::collections::{BTreeMap, BTreeSet};

use super::{
    ExpressionError, RowTypeChecker, TypeErrorKind as Kind, find, require_same, type_error,
};
use crate::declarations::{self as decode, Members, TableType, ValueType};
use crate::json::Value;
use crate::nodes::NodeGraphAnalysis;

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum InterfaceKind {
    Input,
    Output,
}

/// 已解析接口；node 指向原 nodes 数组，不是内部节点引用语法。
#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct InterfaceReference {
    pub kind: InterfaceKind,
    pub name: String,
    pub node: usize,
}

pub(crate) struct Interfaces<'a> {
    inputs: BTreeMap<&'a str, (usize, &'a TableType)>,
    outputs: BTreeMap<&'a str, (usize, &'a TableType)>,
}

impl<'a> Interfaces<'a> {
    pub(crate) fn new(graph: &'a NodeGraphAnalysis) -> Self {
        let table = |index: usize| {
            let id = graph.nodes()[index].table_type();
            graph.types().table_types()
                [find(graph.types().table_types(), id).expect("checked table")]
            .definition()
        };
        let inputs = graph
            .nodes()
            .iter()
            .enumerate()
            .filter_map(|(index, node)| node.input_port().map(|port| (port, (index, table(index)))))
            .collect();
        let outputs = graph
            .outputs()
            .iter()
            .map(|output| (output.name.as_str(), (output.node, table(output.node))))
            .collect();
        Self { inputs, outputs }
    }

    pub(crate) fn get(&self, kind: InterfaceKind, name: &str) -> Option<(usize, &'a TableType)> {
        let index = match kind {
            InterfaceKind::Input => &self.inputs,
            InterfaceKind::Output => &self.outputs,
        };
        index.get(name).copied()
    }
}

#[derive(Clone, Copy)]
pub(super) struct ContractScope<'a> {
    pub interfaces: &'a Interfaces<'a>,
    pub allow_outputs: bool,
}

pub(super) struct TypingContext<'a> {
    pub bindings: Vec<ValueType>,
    pub contract: Option<ContractScope<'a>>,
    pub references: BTreeSet<InterfaceReference>,
}

impl RowTypeChecker<'_> {
    pub(super) fn infer_table(
        &self,
        op: &str,
        members: &Members,
        path: &str,
        context: &mut TypingContext<'_>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let table_path = decode::child(path, "table");
        let reference = decode::object(get("table"), &table_path, &["kind", "name"])?;
        let kind_path = decode::child(&table_path, "kind");
        let kind = match decode::string(decode::member(reference, "kind"), &kind_path)? {
            "input" => InterfaceKind::Input,
            "output" => InterfaceKind::Output,
            _ => return Err(type_error(Kind::UnknownInterfaceKind, &kind_path)),
        };
        let scope = context
            .contract
            .expect("contract operator dispatched only in contract scope");
        if kind == InterfaceKind::Output && !scope.allow_outputs {
            return Err(type_error(Kind::OutputInAssumption, &kind_path));
        }
        let name_path = decode::child(&table_path, "name");
        let name = decode::name(decode::member(reference, "name"), &name_path)?;
        let (node, table) = scope
            .interfaces
            .get(kind, &name)
            .ok_or_else(|| type_error(Kind::UnknownInterface, &name_path))?;
        context
            .references
            .insert(InterfaceReference { kind, name, node });
        if op == "lookup" {
            return self.infer_lookup(get("keys"), &decode::child(path, "keys"), table, context);
        }
        context.bindings.push(ValueType::Record {
            record_type: table.record_type.clone(),
        });
        let result = self.infer_bound_table(op, members, path, context);
        context.bindings.pop();
        result
    }

    fn infer_lookup(
        &self,
        keys: &Value,
        path: &str,
        table: &TableType,
        context: &mut TypingContext<'_>,
    ) -> Result<ValueType, ExpressionError> {
        let keys = decode::array(keys, path)?;
        if keys.len() != table.primary_key.len() {
            return Err(type_error(Kind::WrongArity, path));
        }
        let fields = &self.types.record_types()
            [find(self.types.record_types(), &table.record_type).expect("checked table record")]
        .definition()
        .fields;
        // keys 始终在原环境求值，不插入被查找行；顺序严格等于目标主键顺序。
        for (index, (key, name)) in keys.iter().zip(&table.primary_key).enumerate() {
            let expected = &fields[fields
                .binary_search_by(|field| field.name.cmp(name))
                .expect("checked primary key")]
            .value_type;
            let path = format!("{path}/{index}");
            require_same(&self.infer_value(key, &path, context)?, expected, &path)?;
        }
        Ok(ValueType::Option {
            inner: Box::new(ValueType::Record {
                record_type: table.record_type.clone(),
            }),
        })
    }

    fn infer_bound_table(
        &self,
        op: &str,
        members: &Members,
        path: &str,
        context: &mut TypingContext<'_>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        if matches!(op, "forall_rows" | "exists_rows") {
            require_same(
                &self.infer_value(get("body"), &at("body"), context)?,
                &ValueType::Bool,
                &at("body"),
            )?;
            return Ok(ValueType::Bool);
        }
        require_same(
            &self.infer_value(get("predicate"), &at("predicate"), context)?,
            &ValueType::Bool,
            &at("predicate"),
        )?;
        let result = self.annotation(get("result_type"), &at("result_type"))?;
        if op == "count_where" {
            if !matches!(result, ValueType::Int { .. }) {
                return Err(type_error(Kind::ExpectedInt, &at("result_type")));
            }
        } else {
            let value = self.infer_value(get("value"), &at("value"), context)?;
            match (&value, &result) {
                (ValueType::Int { .. }, ValueType::Int { .. }) => {}
                (ValueType::Fixed { scale: left, .. }, ValueType::Fixed { scale: right, .. }) => {
                    if left != right {
                        return Err(type_error(Kind::ScaleMismatch, &at("result_type")));
                    }
                }
                (ValueType::Int { .. } | ValueType::Fixed { .. }, _) => {
                    return Err(type_error(Kind::TypeMismatch, &at("result_type")));
                }
                _ => return Err(type_error(Kind::ExpectedNumeric, &at("value"))),
            }
        }
        // 只检查类型类别 / scale。计数、数学和（含空集合的零）能否落入范围是后续义务。
        Ok(result)
    }
}
