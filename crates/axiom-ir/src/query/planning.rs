//! 在表 / 量词实例分配前检查容量、乘积及累计实例数。
use super::{Budget, QueryError, QueryResource, Result, array, get, object, text};
use crate::{document::CanonicalDocument, json::Value};
use std::collections::{BTreeMap, BTreeSet};

pub(super) struct Plan<'a> {
    pub nodes: Vec<&'a Value>,
    pub extents: BTreeMap<&'a str, usize>,
    pub interfaces: BTreeMap<(&'a str, &'a str), &'a str>,
    pub literals: BTreeSet<&'a str>,
    node_tables: BTreeMap<&'a str, &'a str>,
}
impl<'a> Plan<'a> {
    pub fn new(document: &CanonicalDocument, root: &'a Value, budget: &mut Budget) -> Result<Self> {
        // 整份 IR 的功能边界与目标独立，不能依据未选中的契约跳过 unsupported。
        for group in ["nodes", "contracts"] {
            for entry in array(get(root, group)) {
                let id = text(entry, "id");
                let definition = get(entry, "definition");
                if group == "nodes"
                    && !matches!(text(definition, "kind"), "input" | "filter" | "map")
                {
                    return Err(QueryError::UnsupportedFeature {
                        anchor: id.to_owned(),
                        feature: text(definition, "kind").to_owned(),
                    });
                }
                let mut pending = vec![definition];
                while let Some(value) = pending.pop() {
                    match value {
                        Value::Object(members) => {
                            if let Some((_, Value::String(op), _)) =
                                members.iter().find(|(k, _, _)| k == "op")
                                && matches!(
                                    op.as_str(),
                                    "exists_rows" | "count_where" | "sum_where"
                                )
                            {
                                return Err(QueryError::UnsupportedFeature {
                                    anchor: id.to_owned(),
                                    feature: op.clone(),
                                });
                            }
                            pending.extend(members.iter().map(|(_, v, _)| v));
                        }
                        Value::Array(values) => pending.extend(values),
                        _ => {}
                    }
                }
            }
        }
        let graph = document.components().analysis().graph();
        let mut depths = vec![0usize; graph.nodes().len()];
        for &i in graph.topological_order() {
            depths[i] = graph.nodes()[i]
                .predecessors()
                .iter()
                .map(|&p| depths[p] + 1)
                .max()
                .unwrap_or(0);
        }
        let depth_by_id: BTreeMap<_, _> = graph
            .nodes()
            .iter()
            .enumerate()
            .map(|(i, n)| (n.supplied_id(), depths[i]))
            .collect();
        let mut nodes: Vec<_> = array(get(root, "nodes")).iter().collect();
        nodes.sort_by_key(|n| (depth_by_id[text(n, "id")], text(n, "id")));
        let tables: BTreeMap<_, _> = graph
            .types()
            .table_types()
            .iter()
            .map(|t| (t.id(), t.definition()))
            .collect();
        let node_tables = nodes
            .iter()
            .map(|n| (text(n, "id"), text(get(n, "definition"), "table_type")))
            .collect();
        let mut result = Self {
            nodes,
            extents: BTreeMap::new(),
            interfaces: BTreeMap::new(),
            literals: BTreeSet::new(),
            node_tables,
        };
        // 空 Text 同时作为不可观察载荷的确定性默认值，绝不解包 None。
        result.literals.insert("");
        for entry in &result.nodes {
            let id = text(entry, "id");
            let node = get(entry, "definition");
            let table = tables[text(node, "table_type")];
            let extent = if text(node, "kind") == "input" {
                let capacity = bounded_capacity(table.capacity.as_str(), budget)?;
                budget.charge(QueryResource::InputSlots, capacity)?;
                let pairs = if capacity % 2 == 0 {
                    (capacity / 2).checked_mul(capacity.saturating_sub(1))
                } else {
                    capacity.checked_mul((capacity - 1) / 2)
                };
                let comparisons = pairs
                    .and_then(|n| n.checked_mul(table.primary_key.len()))
                    .ok_or_else(|| budget.error(QueryResource::SlotComparisons))?;
                budget.charge(QueryResource::SlotComparisons, comparisons)?;
                result.interfaces.insert(("input", text(node, "port")), id);
                capacity
            } else {
                result.extents[text(node, "source")]
            };
            result.extents.insert(id, extent);
        }
        for output in array(get(root, "outputs")) {
            result
                .interfaces
                .insert(("output", text(output, "name")), text(output, "node"));
        }
        for entry in &result.nodes {
            let node = get(entry, "definition");
            let extent = result.extents[text(entry, "id")];
            match text(node, "kind") {
                "filter" => result.expression(get(node, "predicate"), extent, &tables, budget)?,
                "map" => {
                    for field in array(get(node, "fields")) {
                        result.expression(get(field, "expression"), extent, &tables, budget)?;
                    }
                }
                _ => {}
            }
        }
        for contract in array(get(root, "contracts")) {
            let definition = get(contract, "definition");
            if text(definition, "kind") == "formula" {
                result.expression(get(definition, "expression"), 1, &tables, budget)?;
            }
        }
        // 全部字面值都按精确 Unicode 标量序声明，包含非活动分支。
        let mut pending = vec![root];
        while let Some(v) = pending.pop() {
            match v {
                Value::Object(members) => {
                    if members.iter().any(|(k, v, _)| {
                        k == "op" && matches!(v, Value::String(s) if s == "literal_text")
                    }) {
                        result.literals.insert(text(v, "value"));
                    }
                    pending.extend(members.iter().map(|(_, v, _)| v));
                }
                Value::Array(values) => pending.extend(values),
                _ => {}
            }
        }
        // 字面类也需要两两不等；先检查平方成本再创建 SMT 条件。
        let n = result.literals.len();
        let pairs = n
            .checked_mul(n.saturating_sub(1))
            .map(|n| n / 2)
            .ok_or_else(|| budget.error(QueryResource::SlotComparisons))?;
        budget.charge(QueryResource::SlotComparisons, pairs)?;
        Ok(result)
    }
    /// 仅新增目标收费；在布局、槽位或两两比较分配之前检查继承表示规模。
    pub fn output_comparisons(
        &self,
        document: &CanonicalDocument,
        target: &str,
        budget: &mut Budget,
    ) -> Result<()> {
        let table_id = self.node_tables[target];
        let keys = document
            .components()
            .analysis()
            .graph()
            .types()
            .table_types()
            .iter()
            .find(|t| t.id() == table_id)
            .ok_or(QueryError::Internal("missing target table"))?
            .definition()
            .primary_key
            .len();
        let n = self.extents[target];
        let pairs = if n.is_multiple_of(2) {
            (n / 2).checked_mul(n.saturating_sub(1))
        } else {
            n.checked_mul((n - 1) / 2)
        };
        let comparisons = pairs
            .and_then(|p| p.checked_mul(keys))
            .ok_or_else(|| budget.error(QueryResource::SlotComparisons))?;
        budget.charge(QueryResource::SlotComparisons, comparisons)
    }
    pub fn interface(&self, reference: &Value) -> &'a str {
        self.interfaces[&(text(reference, "kind"), text(reference, "name"))]
    }
    fn expression(
        &self,
        value: &Value,
        multiplicity: usize,
        tables: &BTreeMap<&str, &crate::declarations::TableType>,
        budget: &mut Budget,
    ) -> Result<()> {
        match value {
            Value::Object(members) => {
                let op = members
                    .iter()
                    .find(|(k, _, _)| k == "op")
                    .map(|(_, v, _)| super::string(v));
                if op.is_some() {
                    budget.charge(QueryResource::ExpressionInstances, multiplicity)?;
                }
                if op == Some("lookup") {
                    let id = self.interface(get(value, "table"));
                    let keys = tables[self.node_tables[id]].primary_key.len();
                    let amount = multiplicity
                        .checked_mul(self.extents[id])
                        .and_then(|n| n.checked_mul(keys))
                        .ok_or_else(|| budget.error(QueryResource::SlotComparisons))?;
                    budget.charge(QueryResource::SlotComparisons, amount)?;
                }
                for (key, child, _) in object(value) {
                    let count = if op == Some("forall_rows") && key == "body" {
                        multiplicity
                            .checked_mul(self.extents[self.interface(get(value, "table"))])
                            .filter(|n| *n <= budget.limits.max_expression_instances)
                            .ok_or_else(|| budget.error(QueryResource::ExpressionInstances))?
                    } else {
                        multiplicity
                    };
                    self.expression(child, count, tables, budget)?;
                }
            }
            Value::Array(values) => {
                for v in values {
                    self.expression(v, multiplicity, tables, budget)?;
                }
            }
            _ => {}
        }
        Ok(())
    }
}
fn bounded_capacity(value: &str, budget: &Budget) -> Result<usize> {
    let maximum = budget.limits.max_input_slots.to_string();
    if value.len() > maximum.len() || (value.len() == maximum.len() && value > maximum.as_str()) {
        return Err(budget.error(QueryResource::InputSlots));
    }
    value
        .parse()
        .map_err(|_| budget.error(QueryResource::InputSlots))
}
