//! 闭合逐构造规则；图不递归展开，表达式递归受 IR JSON 深度上限约束。
use super::{Budget, EffectError, EffectLimits, EffectResource, EffectUsage, Result, encoding};
use crate::{document::CanonicalDocument, json::Value};
use std::collections::BTreeMap;

#[derive(Clone, Copy)]
pub(super) enum PathPart<'a> {
    Name(&'a str),
    Index(usize),
}
#[derive(Clone, Copy)]
pub(super) struct Anchor<'a> {
    pub kind: &'static str,
    pub id: &'a str,
}
pub(super) struct Step<'a> {
    pub anchor: Anchor<'a>,
    pub path: Vec<PathPart<'a>>,
    pub premises: Vec<usize>,
    pub rule: String,
}
#[derive(Clone, Copy)]
struct Context {
    depth: usize,
    assume: Option<bool>,
}
pub(super) struct Builder<'a> {
    pub steps: Vec<Step<'a>>,
    pub budget: Budget,
    inputs: BTreeMap<&'a str, usize>,
    outputs: BTreeMap<&'a str, usize>,
}
impl<'a> Builder<'a> {
    pub fn new(limits: EffectLimits) -> Self {
        Self {
            steps: vec![],
            budget: Budget {
                limits,
                usage: EffectUsage::default(),
            },
            inputs: BTreeMap::new(),
            outputs: BTreeMap::new(),
        }
    }
    fn edge(&mut self, premises: &mut Vec<usize>, step: usize) -> Result<()> {
        if step >= self.steps.len() {
            return Err(EffectError::Internal("effect forward premise"));
        }
        self.budget.charge(EffectResource::PremiseEdges, Some(1))?;
        premises.push(step);
        Ok(())
    }
    fn add(
        &mut self,
        anchor: Anchor<'a>,
        path: &[PathPart<'a>],
        rule: &str,
        premises: Vec<usize>,
    ) -> Result<usize> {
        self.budget.charge(EffectResource::Steps, Some(1))?;
        let mut length = Some(0usize);
        encoding::path(path, &mut |bytes| {
            length = length.and_then(|n| n.checked_add(bytes.len()));
        });
        self.budget.charge(EffectResource::PathBytes, length)?;
        let index = self.steps.len();
        self.steps.push(Step {
            anchor,
            path: path.to_vec(),
            rule: rule.to_owned(),
            premises,
        });
        Ok(index)
    }
    pub fn document(&mut self, value: &'a Value, document: &'a CanonicalDocument) -> Result<()> {
        let entries: BTreeMap<_, _> = array(get(value, "nodes"))
            .iter()
            .map(|e| (text(e, "id"), get(e, "definition")))
            .collect();
        // P1 的原数组顺序不参与记录；只用已有 DAG 分析计算深度后按内容 ID 排序。
        let graph = document.components().analysis().graph();
        let mut depths = BTreeMap::new();
        for &index in graph.topological_order() {
            let node = &graph.nodes()[index];
            let depth = node
                .predecessors()
                .iter()
                .map(|&p| depths[graph.nodes()[p].supplied_id()] + 1usize)
                .max()
                .unwrap_or(0);
            depths.insert(node.supplied_id(), depth);
        }
        let mut order: Vec<_> = entries.keys().copied().collect();
        order.sort_by_key(|id| (depths[id], *id));
        let mut nodes = BTreeMap::new();
        for id in order {
            let node = entries[id];
            let step = self.node(node, Anchor { kind: "node", id }, &nodes)?;
            nodes.insert(id, step);
            if text(node, "kind") == "input" {
                self.inputs.insert(text(node, "port"), step);
            }
        }
        for output in array(get(value, "outputs")) {
            let anchor = Anchor {
                kind: "output",
                id: text(output, "name"),
            };
            shape(output, &["name", "node"], anchor, &[])?;
            let mut premises = vec![];
            self.edge(&mut premises, nodes[text(output, "node")])?;
            let index = self.add(anchor, &[], "output.bind", premises)?;
            self.outputs.insert(anchor.id, index);
        }
        let mut contracts = Vec::new();
        for entry in array(get(value, "contracts")) {
            let anchor = Anchor {
                kind: "contract",
                id: text(entry, "id"),
            };
            let contract = get(entry, "definition");
            let mut premises = vec![];
            let rule = match text(contract, "kind") {
                "formula" => {
                    shape(contract, &["kind", "role", "expression"], anchor, &[])?;
                    let assume = match text(contract, "role") {
                        "assume" => true,
                        "guarantee" => false,
                        _ => return Err(invalid(anchor, &[], "unknown formula role")),
                    };
                    self.child(
                        contract,
                        "expression",
                        anchor,
                        &mut vec![],
                        Context {
                            depth: 0,
                            assume: Some(assume),
                        },
                        &mut premises,
                    )?;
                    if assume {
                        "contract.assume"
                    } else {
                        "contract.guarantee"
                    }
                }
                "noninterference" => {
                    shape(contract, &["kind", "inputs", "outputs"], anchor, &[])?;
                    for name in array(get(contract, "inputs")) {
                        let step = *self
                            .inputs
                            .get(string(name))
                            .ok_or_else(|| invalid(anchor, &[], "unknown noninterference input"))?;
                        self.edge(&mut premises, step)?;
                    }
                    for name in array(get(contract, "outputs")) {
                        let step = *self.outputs.get(string(name)).ok_or_else(|| {
                            invalid(anchor, &[], "unknown noninterference output")
                        })?;
                        self.edge(&mut premises, step)?;
                    }
                    "contract.noninterference"
                }
                _ => return Err(invalid(anchor, &[], "unknown contract kind")),
            };
            let step = self.add(anchor, &[], rule, premises)?;
            // 最终文档边在临时数组分配前收费。
            self.edge(&mut contracts, step)?;
        }
        let anchor = Anchor {
            kind: "document",
            id: document.document_id(),
        };
        let path = [PathPart::Name("effects")];
        if !matches!(get(value, "effects"), Value::Array(v) if v.is_empty()) {
            return Err(invalid(anchor, &path, "nonempty effects"));
        }
        let effects = self.add(anchor, &path, "effects.empty", vec![])?;
        let mut premises = vec![];
        self.edge(&mut premises, effects)?;
        for &step in nodes.values() {
            self.edge(&mut premises, step)?;
        }
        // 接口索引均指向已入表步骤；直接收费并写入，避免另建无预算的临时数组。
        for &step in self.outputs.values() {
            self.budget.charge(EffectResource::PremiseEdges, Some(1))?;
            premises.push(step);
        }
        premises.append(&mut contracts);
        self.add(anchor, &[], "program.empty", premises)?;
        Ok(())
    }
    fn node(
        &mut self,
        value: &'a Value,
        anchor: Anchor<'a>,
        nodes: &BTreeMap<&str, usize>,
    ) -> Result<usize> {
        let kind = text(value, "kind");
        let keys: &[&str] = match kind {
            "input" => &["kind", "port", "table_type"],
            "filter" => &["kind", "predicate", "source", "table_type"],
            "map" => &["kind", "fields", "source", "table_type"],
            "lookup_join" => &["kind", "left", "right", "pairs", "fields", "table_type"],
            "group" => &["kind", "source", "keys", "aggregates", "table_type"],
            _ => return Err(invalid(anchor, &[], "unknown node kind")),
        };
        shape(value, keys, anchor, &[])?;
        let mut premises = vec![];
        if kind != "input" {
            let sources: &[&str] = if kind == "lookup_join" {
                &["left", "right"]
            } else {
                &["source"]
            };
            for key in sources {
                let step = *nodes
                    .get(text(value, key))
                    .ok_or_else(|| invalid(anchor, &[], "missing predecessor derivation"))?;
                self.edge(&mut premises, step)?;
            }
        }
        let context = Context {
            depth: if kind == "lookup_join" { 2 } else { 1 },
            assume: None,
        };
        let mut path = vec![];
        if kind == "filter" {
            self.child(
                value,
                "predicate",
                anchor,
                &mut path,
                context,
                &mut premises,
            )?;
        }
        if kind == "lookup_join" {
            for (i, pair) in array(get(value, "pairs")).iter().enumerate() {
                let path = [PathPart::Name("pairs"), PathPart::Index(i)];
                shape(pair, &["left", "right"], anchor, &path)?;
                let step = self.add(anchor, &path, "join.pair", vec![])?;
                self.edge(&mut premises, step)?;
            }
        }
        if matches!(kind, "map" | "lookup_join") {
            self.fields(value, anchor, &mut path, context, &mut premises)?;
        }
        if kind == "group" {
            for (i, key) in array(get(value, "keys")).iter().enumerate() {
                let path = [PathPart::Name("keys"), PathPart::Index(i)];
                shape(key, &["name", "source_field"], anchor, &path)?;
                let step = self.add(anchor, &path, "group.key", vec![])?;
                self.edge(&mut premises, step)?;
            }
            for (i, aggregate) in array(get(value, "aggregates")).iter().enumerate() {
                let path = [PathPart::Name("aggregates"), PathPart::Index(i)];
                let kind = text(aggregate, "kind");
                let keys: &[&str] = match kind {
                    "count" => &["kind", "name"],
                    "sum" => &["kind", "name", "field"],
                    _ => return Err(invalid(anchor, &path, "unknown group aggregate")),
                };
                shape(aggregate, keys, anchor, &path)?;
                let step = self.add(anchor, &path, &format!("group.{kind}"), vec![])?;
                self.edge(&mut premises, step)?;
            }
        }
        self.add(anchor, &[], &format!("node.{kind}"), premises)
    }
    fn fields(
        &mut self,
        value: &'a Value,
        anchor: Anchor<'a>,
        path: &mut Vec<PathPart<'a>>,
        context: Context,
        premises: &mut Vec<usize>,
    ) -> Result<()> {
        path.push(PathPart::Name("fields"));
        for (i, field) in array(get(value, "fields")).iter().enumerate() {
            path.push(PathPart::Index(i));
            shape(field, &["name", "expression"], anchor, path)?;
            self.child(field, "expression", anchor, path, context, premises)?;
            path.pop();
        }
        path.pop();
        Ok(())
    }
    fn child(
        &mut self,
        value: &'a Value,
        key: &'static str,
        anchor: Anchor<'a>,
        path: &mut Vec<PathPart<'a>>,
        context: Context,
        premises: &mut Vec<usize>,
    ) -> Result<()> {
        path.push(PathPart::Name(key));
        let step = self.expr(get(value, key), anchor, path, context)?;
        path.pop();
        self.edge(premises, step)
    }
    fn expr(
        &mut self,
        value: &'a Value,
        anchor: Anchor<'a>,
        path: &mut Vec<PathPart<'a>>,
        context: Context,
    ) -> Result<usize> {
        let op = text(value, "op");
        let keys: &[&str] = match op {
            "literal_bool" | "literal_text" | "some" | "not" => &["op", "value"],
            "literal_int" => &["op", "type", "value"],
            "literal_fixed" => &["op", "type", "coefficient"],
            "literal_enum" => &["op", "enum_type", "member"],
            "none" => &["op", "type"],
            "bound" => &["op", "index"],
            "field" => &["op", "field", "record"],
            "and" | "or" => &["op", "values"],
            "eq" | "lt" | "le" | "gt" | "ge" => &["op", "left", "right"],
            "int_add" | "fixed_add" => &["op", "values", "result_type"],
            "int_sub" | "fixed_sub" => &["op", "left", "right", "result_type"],
            "if" => &["op", "condition", "then", "else", "result_type"],
            "match_option" => &["op", "subject", "none", "some", "result_type"],
            "record" => &["op", "record_type", "fields"],
            "forall_rows" | "exists_rows" => &["op", "table", "body"],
            "lookup" => &["op", "table", "keys"],
            "count_where" => &["op", "table", "predicate", "result_type"],
            "sum_where" => &["op", "table", "predicate", "value", "result_type"],
            _ => return Err(invalid(anchor, path, "unknown expression op")),
        };
        shape(value, keys, anchor, path)?;
        let mut premises = vec![];
        match op {
            "bound" => {
                if text(value, "index")
                    .parse::<usize>()
                    .ok()
                    .is_none_or(|i| i >= context.depth)
                {
                    return Err(invalid(anchor, path, "out of scope bound"));
                }
            }
            "field" => self.child(value, "record", anchor, path, context, &mut premises)?,
            "some" | "not" => self.child(value, "value", anchor, path, context, &mut premises)?,
            "record" => self.fields(value, anchor, path, context, &mut premises)?,
            "and" | "or" | "int_add" | "fixed_add" => {
                path.push(PathPart::Name("values"));
                for (i, child) in array(get(value, "values")).iter().enumerate() {
                    path.push(PathPart::Index(i));
                    let step = self.expr(child, anchor, path, context)?;
                    path.pop();
                    self.edge(&mut premises, step)?;
                }
                path.pop();
            }
            "eq" | "lt" | "le" | "gt" | "ge" | "int_sub" | "fixed_sub" => {
                for key in ["left", "right"] {
                    self.child(value, key, anchor, path, context, &mut premises)?;
                }
            }
            "if" => {
                for key in ["condition", "then", "else"] {
                    self.child(value, key, anchor, path, context, &mut premises)?;
                }
            }
            "match_option" => {
                for key in ["subject", "none", "some"] {
                    let context = Context {
                        depth: context.depth + usize::from(key == "some"),
                        ..context
                    };
                    self.child(value, key, anchor, path, context, &mut premises)?;
                }
            }
            "forall_rows" | "exists_rows" | "lookup" | "count_where" | "sum_where" => {
                path.push(PathPart::Name("table"));
                let step = self.interface(get(value, "table"), anchor, path, context)?;
                path.pop();
                self.edge(&mut premises, step)?;
                if op == "lookup" {
                    path.push(PathPart::Name("keys"));
                    for (i, key) in array(get(value, "keys")).iter().enumerate() {
                        path.push(PathPart::Index(i));
                        let step = self.expr(key, anchor, path, context)?;
                        path.pop();
                        self.edge(&mut premises, step)?;
                    }
                    path.pop();
                } else {
                    let context = Context {
                        depth: context.depth + 1,
                        ..context
                    };
                    let children: &[&str] = match op {
                        "forall_rows" | "exists_rows" => &["body"],
                        "count_where" => &["predicate"],
                        _ => &["predicate", "value"],
                    };
                    for &key in children {
                        self.child(value, key, anchor, path, context, &mut premises)?;
                    }
                }
            }
            // 闭合形状表已将剩余项限制为字面值 / none。
            _ => {}
        }
        self.add(anchor, path, &format!("expr.{op}"), premises)
    }
    fn interface(
        &mut self,
        value: &'a Value,
        anchor: Anchor<'a>,
        path: &[PathPart<'a>],
        context: Context,
    ) -> Result<usize> {
        shape(value, &["kind", "name"], anchor, path)?;
        let kind = text(value, "kind");
        let map = match (kind, context.assume) {
            ("input", Some(_)) => &self.inputs,
            ("output", Some(false)) => &self.outputs,
            _ => return Err(invalid(anchor, path, "forbidden table interface")),
        };
        let step = *map
            .get(text(value, "name"))
            .ok_or_else(|| invalid(anchor, path, "unknown table interface"))?;
        let mut premises = vec![];
        self.edge(&mut premises, step)?;
        self.add(anchor, path, &format!("interface.{kind}"), premises)
    }
}

fn invalid(anchor: Anchor<'_>, path: &[PathPart<'_>], reason: &'static str) -> EffectError {
    EffectError::InvalidConstruct {
        anchor: anchor.id.to_owned(),
        path: path
            .iter()
            .map(|p| match p {
                PathPart::Name(s) => (*s).to_owned(),
                PathPart::Index(i) => i.to_string(),
            })
            .collect(),
        reason,
    }
}
fn shape(value: &Value, keys: &[&str], anchor: Anchor<'_>, path: &[PathPart<'_>]) -> Result<()> {
    if !matches!(value, Value::Object(m) if m.len() == keys.len() && keys.iter().all(|key| m.iter().any(|(name, _, _)| name == key)))
    {
        return Err(invalid(anchor, path, "non-closed construct"));
    }
    Ok(())
}
fn get<'a>(value: &'a Value, name: &str) -> &'a Value {
    let Value::Object(m) = value else {
        unreachable!("P1 object")
    };
    &m.iter().find(|(n, _, _)| n == name).expect("P1 member").1
}
fn text<'a>(value: &'a Value, name: &str) -> &'a str {
    string(get(value, name))
}
fn string(value: &Value) -> &str {
    let Value::String(s) = value else {
        unreachable!("P1 string")
    };
    s
}
fn array(value: &Value) -> &[Value] {
    let Value::Array(a) = value else {
        unreachable!("P1 array")
    };
    a
}
