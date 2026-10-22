//! 只从规范 IR 重建；标签缓存不是证据输入。图和声明用共享步骤引用。
use super::{Budget, OriginError, OriginLimits, OriginResource, OriginUsage, Result, encoding};
use crate::{declarations::Label, document::CanonicalDocument, json::Value};
use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

pub(super) type Id = usize;
#[derive(Clone, Copy)]
pub(super) enum Part<'a> {
    Name(&'a str),
    Index(usize),
}
#[derive(Clone, Copy)]
pub(super) struct Anchor<'a> {
    pub kind: &'static str,
    pub id: &'a str,
}
#[derive(Clone, Copy)]
pub(super) enum Role {
    Value,
    Selection,
    Evaluation,
    Declaration,
}
impl Role {
    pub fn name(self) -> &'static str {
        match self {
            Self::Value => "value",
            Self::Selection => "selection",
            Self::Evaluation => "evaluation",
            Self::Declaration => "declaration",
        }
    }
}
pub(super) struct Edge {
    pub role: Role,
    pub step: Id,
}
#[derive(Clone, Copy)]
pub(super) struct Labels {
    pub declared: Label,
    pub inferred: Label,
    pub type_summary: Label,
    pub propagated: Label,
}
impl Labels {
    pub fn inferred(label: Label) -> Self {
        Self {
            declared: Label::Public,
            inferred: label,
            type_summary: Label::Public,
            propagated: label,
        }
    }
    pub fn field(declared: Label, inferred: Label, type_summary: Label) -> Self {
        Self {
            declared,
            inferred,
            type_summary,
            propagated: declared.join(inferred).join(type_summary),
        }
    }
}
pub(super) struct Step<'a> {
    pub anchor: Anchor<'a>,
    pub path: Vec<Part<'a>>,
    pub item: &'a str,
    pub rule: String,
    pub labels: Labels,
    pub gap: bool,
    pub premises: Vec<Edge>,
}
/// Known Option 内值用 Arc 共享，Typed 只借用类型引用，不展开 Record DAG。
#[derive(Clone)]
pub(super) enum Shape<'a> {
    Scalar,
    Record {
        id: &'a str,
        fields: Option<Arc<BTreeMap<&'a str, Id>>>,
    },
    TypedOption {
        inner: &'a Value,
        declared: bool,
    },
    KnownOption(Arc<Flow<'a>>),
}
#[derive(Clone)]
pub(super) struct Flow<'a> {
    pub shape: Shape<'a>,
    pub top: Label,
    pub selection: Option<Id>,
    pub base: Label,
    pub step: Id,
}
#[derive(Clone)]
pub(super) struct Node<'a> {
    pub record: Flow<'a>,
    pub control: Id,
    pub evaluation: Id,
    pub fields: Arc<BTreeMap<&'a str, Id>>,
    pub record_type: &'a str,
}
pub(super) struct Target<'a> {
    pub interface: &'a str,
    pub name: &'a str,
    pub node: &'a str,
    pub record_type: &'a str,
    pub value: Id,
    pub control: Id,
    pub evaluation: Id,
}
pub(super) struct Pruned {
    pub order: Vec<Id>,
    pub remap: Vec<Id>,
}
pub(super) struct Builder<'a> {
    pub steps: Vec<Step<'a>>,
    pub budget: Budget,
    pub records: BTreeMap<&'a str, &'a Value>,
    pub tables: BTreeMap<&'a str, &'a Value>,
    pub record_steps: BTreeMap<&'a str, Id>,
    pub table_steps: BTreeMap<&'a str, Id>,
    pub field_steps: BTreeMap<(&'a str, &'a str), Id>,
}
impl<'a> Builder<'a> {
    pub fn new(limits: OriginLimits) -> Self {
        Self {
            steps: vec![],
            budget: Budget {
                limits,
                usage: OriginUsage::default(),
            },
            records: BTreeMap::new(),
            tables: BTreeMap::new(),
            record_steps: BTreeMap::new(),
            table_steps: BTreeMap::new(),
            field_steps: BTreeMap::new(),
        }
    }
    pub fn descriptors(&mut self, n: usize) -> Result<()> {
        self.budget.charge(OriginResource::Descriptors, Some(n))
    }
    pub fn edge(&mut self, edges: &mut Vec<Edge>, role: Role, step: Id) -> Result<()> {
        if step >= self.steps.len() {
            return Err(OriginError::Internal("forward origin premise"));
        }
        self.budget.charge(OriginResource::PremiseEdges, Some(1))?;
        edges.push(Edge { role, step });
        Ok(())
    }
    pub fn add(
        &mut self,
        anchor: Anchor<'a>,
        path: &[Part<'a>],
        item: &'a str,
        rule: &str,
        labels: Labels,
        premises: Vec<Edge>,
    ) -> Result<Id> {
        self.budget.charge(OriginResource::Steps, Some(1))?;
        let mut size = Some(0usize);
        encoding::path(path, &mut |b| {
            size = size.and_then(|n| n.checked_add(b.len()))
        });
        self.budget.charge(OriginResource::PathBytes, size)?;
        let id = self.steps.len();
        let gap = matches!(rule, "field.assign" | "expr.record-field")
            && labels.declared == Label::Public
            && labels.inferred == Label::Sensitive;
        self.steps.push(Step {
            anchor,
            path: path.to_vec(),
            item,
            rule: rule.to_owned(),
            labels,
            gap,
            premises,
        });
        Ok(id)
    }
    pub fn label(&self, id: Id) -> Label {
        self.steps[id].labels.propagated
    }
    pub fn selection_label(&self, flow: &Flow<'_>) -> Label {
        flow.top
    }
    pub fn field(&self, record: &str, name: &str) -> &'a Value {
        array(get(self.records[record], "fields"))
            .iter()
            .find(|v| text(v, "name") == name)
            .expect("P1 field")
    }
    pub fn type_record(ty: &'a Value) -> Option<&'a str> {
        let mut ty = ty;
        while text(ty, "kind") == "option" {
            ty = get(ty, "inner");
        }
        (text(ty, "kind") == "record").then(|| text(ty, "record_type"))
    }
    pub fn type_label(&self, ty: &'a Value) -> Label {
        Self::type_record(ty)
            .map(|id| self.label(self.record_steps[id]))
            .unwrap_or(Label::Public)
    }
    pub fn shaped(
        &mut self,
        ty: &'a Value,
        declared: bool,
        selection: Option<Id>,
        top: Label,
        step: Id,
    ) -> Result<Flow<'a>> {
        self.descriptors(1)?;
        let shape = match text(ty, "kind") {
            "record" => Shape::Record {
                id: text(ty, "record_type"),
                fields: None,
            },
            "option" => Shape::TypedOption {
                inner: get(ty, "inner"),
                declared,
            },
            _ => Shape::Scalar,
        };
        Ok(Flow {
            shape,
            top,
            selection,
            base: if declared {
                self.type_label(ty)
            } else {
                Label::Public
            },
            step,
        })
    }
    fn declarations(&mut self, root: &'a Value) -> Result<()> {
        let records = array(get(root, "record_types"));
        let tables = array(get(root, "table_types"));
        // 有界索引 / Kahn 工作单元先收费；重复引用以实际边数收费，不展开类型内容。
        self.descriptors(
            records
                .len()
                .checked_mul(6)
                .ok_or(OriginError::ResourceLimit {
                    resource: OriginResource::Descriptors,
                })?,
        )?;
        self.descriptors(
            tables
                .len()
                .checked_mul(2)
                .ok_or(OriginError::ResourceLimit {
                    resource: OriginResource::Descriptors,
                })?,
        )?;
        self.records = records
            .iter()
            .map(|v| (text(v, "id"), get(v, "definition")))
            .collect();
        self.tables = tables
            .iter()
            .map(|v| (text(v, "id"), get(v, "definition")))
            .collect();
        let mut degree = BTreeMap::new();
        let mut parents = BTreeMap::<&str, Vec<&str>>::new();
        let mut depths = BTreeMap::<&str, usize>::new();
        for entry in records {
            let id = text(entry, "id");
            let mut count = 0usize;
            for field in array(get(get(entry, "definition"), "fields")) {
                if let Some(child) = Self::type_record(get(field, "type")) {
                    self.descriptors(1)?;
                    parents.entry(child).or_default().push(id);
                    count += 1;
                }
            }
            degree.insert(id, count);
            depths.insert(id, 0);
        }
        let mut ready: BTreeSet<_> = degree
            .iter()
            .filter(|(_, n)| **n == 0)
            .map(|(&id, _)| (0, id))
            .collect();
        while let Some((depth, id)) = ready.pop_first() {
            let anchor = Anchor {
                kind: "record-type",
                id,
            };
            let mut edges = vec![];
            let mut summary = Label::Public;
            for (i, field) in array(get(self.records[id], "fields")).iter().enumerate() {
                let name = text(field, "name");
                let ty = get(field, "type");
                let mut refs = vec![];
                if let Some(child) = Self::type_record(ty) {
                    self.edge(&mut refs, Role::Declaration, self.record_steps[child])?;
                }
                let labels = Labels::field(
                    label(text(field, "label")),
                    Label::Public,
                    self.type_label(ty),
                );
                let field_id = self.add(
                    anchor,
                    &[Part::Name("fields"), Part::Index(i)],
                    name,
                    "decl.field",
                    labels,
                    refs,
                )?;
                self.descriptors(1)?;
                self.field_steps.insert((id, name), field_id);
                self.edge(&mut edges, Role::Declaration, field_id)?;
                summary = summary.join(labels.propagated);
            }
            let step = self.add(
                anchor,
                &[],
                "",
                "decl.record",
                Labels::inferred(summary),
                edges,
            )?;
            self.record_steps.insert(id, step);
            for &parent in parents.get(id).into_iter().flatten() {
                let remaining = degree.get_mut(parent).expect("P1 record reference");
                *remaining -= 1;
                let d = depths.get_mut(parent).unwrap();
                *d = (*d).max(depth + 1);
                if *remaining == 0 {
                    ready.insert((*d, parent));
                }
            }
        }
        if self.record_steps.len() != records.len() {
            return Err(OriginError::Internal("cyclic origin record declarations"));
        }
        for table in tables {
            let id = text(table, "id");
            let mut refs = vec![];
            self.edge(
                &mut refs,
                Role::Declaration,
                self.record_steps[text(get(table, "definition"), "record_type")],
            )?;
            let step = self.add(
                Anchor {
                    kind: "table-type",
                    id,
                },
                &[],
                "",
                "decl.table",
                Labels::inferred(Label::Public),
                refs,
            )?;
            self.table_steps.insert(id, step);
        }
        Ok(())
    }
    pub fn document(
        &mut self,
        root: &'a Value,
        doc: &'a CanonicalDocument,
        definition: &'a Value,
    ) -> Result<Target<'a>> {
        self.declarations(root)?;
        let entries = array(get(root, "nodes"));
        self.descriptors(
            entries
                .len()
                .checked_mul(5)
                .ok_or(OriginError::ResourceLimit {
                    resource: OriginResource::Descriptors,
                })?,
        )?;
        let by_id: BTreeMap<_, _> = entries
            .iter()
            .map(|v| (text(v, "id"), get(v, "definition")))
            .collect();
        let graph = doc.components().analysis().graph();
        let mut depths = BTreeMap::new();
        for &i in graph.topological_order() {
            let n = &graph.nodes()[i];
            let d = n
                .predecessors()
                .iter()
                .map(|&p| depths[graph.nodes()[p].supplied_id()] + 1usize)
                .max()
                .unwrap_or(0);
            depths.insert(n.supplied_id(), d);
        }
        let mut order: Vec<_> = by_id.keys().copied().collect();
        order.sort_by_key(|id| (depths[id], *id));
        let mut nodes = BTreeMap::new();
        for id in order {
            let node = self.node(Anchor { kind: "node", id }, by_id[id], &nodes)?;
            nodes.insert(id, node);
        }
        let subject = get(definition, "subject");
        let interface = text(subject, "interface");
        let name = text(subject, "name");
        let output = array(get(root, "outputs"))
            .iter()
            .find(|v| text(v, "name") == interface)
            .ok_or(OriginError::Internal("P2 output binding"))?;
        let node_id = text(output, "node");
        let n = &nodes[node_id];
        let mut refs = vec![];
        let source = *n
            .fields
            .get(name)
            .ok_or(OriginError::Internal("P2 field binding"))?;
        self.edge(&mut refs, Role::Value, source)?;
        self.edge(
            &mut refs,
            Role::Declaration,
            self.field_steps[&(n.record_type, name)],
        )?;
        let value = self.add(
            Anchor {
                kind: "output",
                id: interface,
            },
            &[],
            name,
            "output.field",
            Labels::inferred(self.label(source)),
            refs,
        )?;
        Ok(Target {
            interface,
            name,
            node: node_id,
            record_type: n.record_type,
            value,
            control: n.control,
            evaluation: n.evaluation,
        })
    }
    pub fn prune(&mut self, target: &Target<'_>) -> Result<Pruned> {
        let len = self.steps.len();
        self.descriptors(len.checked_mul(3).ok_or(OriginError::ResourceLimit {
            resource: OriginResource::Descriptors,
        })?)?;
        let mut live = vec![false; len];
        for i in [target.value, target.control, target.evaluation] {
            live[i] = true;
        }
        for i in (0..len).rev() {
            if live[i] {
                for edge in &self.steps[i].premises {
                    live[edge.step] = true;
                }
            }
        }
        let mut order = vec![];
        let mut remap = vec![usize::MAX; len];
        for (i, active) in live.into_iter().enumerate() {
            if active {
                remap[i] = order.len();
                order.push(i);
            }
        }
        Ok(Pruned { order, remap })
    }
}
pub(super) fn label(name: &str) -> Label {
    match name {
        "public" => Label::Public,
        "sensitive" => Label::Sensitive,
        _ => unreachable!("P1 label"),
    }
}
pub(super) fn get<'a>(value: &'a Value, name: &str) -> &'a Value {
    let Value::Object(m) = value else {
        unreachable!("P1 object")
    };
    &m.iter().find(|(n, _, _)| n == name).expect("P1 member").1
}
pub(super) fn text<'a>(value: &'a Value, name: &str) -> &'a str {
    string(get(value, name))
}
pub(super) fn string(value: &Value) -> &str {
    let Value::String(s) = value else {
        unreachable!("P1 string")
    };
    s
}
pub(super) fn array(value: &Value) -> &[Value] {
    let Value::Array(a) = value else {
        unreachable!("P1 array")
    };
    a
}
pub(super) fn invalid(anchor: Anchor<'_>, path: &[Part<'_>], reason: &'static str) -> OriginError {
    OriginError::InvalidConstruct {
        anchor: anchor.id.to_owned(),
        path: path
            .iter()
            .map(|p| match p {
                Part::Name(s) => (*s).to_owned(),
                Part::Index(i) => i.to_string(),
            })
            .collect(),
        reason,
    }
}
pub(super) fn shape(
    value: &Value,
    keys: &[&str],
    anchor: Anchor<'_>,
    path: &[Part<'_>],
) -> Result<()> {
    if !matches!(value,Value::Object(m) if m.len()==keys.len() && keys.iter().all(|key| m.iter().any(|(name,_,_)| name==key)))
    {
        return Err(invalid(anchor, path, "non-closed origin construct"));
    }
    Ok(())
}
