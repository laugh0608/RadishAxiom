//! 有类型 DAG 负责物化，完整叶布局与编码器的 origin 逐项核对；不沿 Record 引用递归。
use super::{Budget, Result, SolverError, SolverResource as R, Sort, encoding};
use crate::{
    declarations::ValueType,
    document::CanonicalDocument,
    integer::Integer,
    json::{Value, emit_string},
    query::{QuerySymbol, SymbolOrigin},
};
use std::collections::{BTreeMap, BTreeSet};

pub(super) enum ShapeKind {
    Bool,
    Int(Integer, Integer),
    Fixed(String, Integer, Integer),
    Text,
    Enum(String, Vec<String>),
    Option(usize),
    Record(String, Vec<(String, usize)>),
}
pub(super) struct Shape {
    pub kind: ShapeKind,
    pub width: usize,
    descriptor: Value,
}
pub(super) struct Input {
    pub interface: String,
    pub node: String,
    pub table_type: String,
    pub record_type: String,
    pub capacity: usize,
    pub keys: Vec<usize>,
    pub shape: usize,
    pub slots: Vec<Vec<usize>>,
    pub components: Vec<Component>,
}
pub(super) struct Component {
    path: Vec<String>,
    shape: usize,
    tag: bool,
}
pub(super) struct InputLayout {
    pub shapes: Vec<Shape>,
    pub inputs: Vec<Input>,
}

fn type_value(ty: &ValueType, b: &mut Budget) -> Result<Value> {
    let mut inner = ty;
    let mut options = 0usize;
    while let ValueType::Option { inner: v } = inner {
        b.charge(R::LayoutItems, 1)?;
        options += 1;
        inner = v;
    }
    b.charge(R::LayoutItems, 1)?;
    let mut value = match inner {
        ValueType::Bool => encoding::obj(vec![("kind", encoding::s("bool"))]),
        ValueType::Text => encoding::obj(vec![("kind", encoding::s("text"))]),
        ValueType::Int { lower, upper } => encoding::obj(vec![
            ("kind", encoding::s("int")),
            ("lower", encoding::s(b.copy(lower.as_str())?)),
            ("upper", encoding::s(b.copy(upper.as_str())?)),
        ]),
        ValueType::Fixed {
            scale,
            lower,
            upper,
        } => encoding::obj(vec![
            ("kind", encoding::s("fixed")),
            ("scale", encoding::s(b.copy(scale.as_str())?)),
            ("lower", encoding::s(b.copy(lower.as_str())?)),
            ("upper", encoding::s(b.copy(upper.as_str())?)),
        ]),
        ValueType::Enum { enum_type } => encoding::obj(vec![
            ("kind", encoding::s("enum")),
            ("enum_type", encoding::s(b.copy(enum_type)?)),
        ]),
        ValueType::Record { record_type } => encoding::obj(vec![
            ("kind", encoding::s("record")),
            ("record_type", encoding::s(b.copy(record_type)?)),
        ]),
        ValueType::Option { .. } => unreachable!(),
    };
    for _ in 0..options {
        value = encoding::obj(vec![("kind", encoding::s("option")), ("inner", value)]);
    }
    Ok(value)
}
impl InputLayout {
    fn push(
        &mut self,
        kind: ShapeKind,
        width: usize,
        descriptor: Value,
        b: &mut Budget,
    ) -> Result<usize> {
        b.charge(R::LayoutItems, 1)?;
        if width > b.limits.value_cells {
            return Err(b.error(R::ValueCells));
        }
        let id = self.shapes.len();
        self.shapes.push(Shape {
            kind,
            width,
            descriptor,
        });
        Ok(id)
    }
    fn ty(
        &mut self,
        ty: &ValueType,
        records: &BTreeMap<&str, usize>,
        enums: &BTreeMap<&str, &Vec<String>>,
        b: &mut Budget,
    ) -> Result<usize> {
        // Option 深度由 P1 JSON 限制；Record 引用只查已完成的 DAG 节点。
        let mut base = ty;
        let mut options = Vec::new();
        while let ValueType::Option { inner } = base {
            b.charge(R::LayoutItems, 1)?;
            options.push(base);
            base = inner;
        }
        let mut id = match base {
            ValueType::Record { record_type } => records[record_type.as_str()],
            _ => {
                let kind = match base {
                    ValueType::Bool => ShapeKind::Bool,
                    ValueType::Text => ShapeKind::Text,
                    ValueType::Int { lower, upper } => {
                        b.charge(R::ValueCells, lower.as_str().len() + upper.as_str().len())?;
                        ShapeKind::Int(lower.clone(), upper.clone())
                    }
                    ValueType::Fixed {
                        scale,
                        lower,
                        upper,
                    } => {
                        b.charge(R::ValueCells, lower.as_str().len() + upper.as_str().len())?;
                        ShapeKind::Fixed(b.copy(scale.as_str())?, lower.clone(), upper.clone())
                    }
                    ValueType::Enum { enum_type } => {
                        b.charge(R::LayoutItems, enums[enum_type.as_str()].len())?;
                        let members = enums[enum_type.as_str()]
                            .iter()
                            .map(|s| b.copy(s))
                            .collect::<Result<Vec<_>>>()?;
                        ShapeKind::Enum(b.copy(enum_type)?, members)
                    }
                    _ => unreachable!(),
                };
                self.push(kind, 1, type_value(base, b)?, b)?
            }
        };
        for ty in options.into_iter().rev() {
            let width = self.shapes[id]
                .width
                .checked_add(1)
                .ok_or_else(|| b.error(R::ValueCells))?;
            id = self.push(ShapeKind::Option(id), width, type_value(ty, b)?, b)?;
        }
        Ok(id)
    }
    pub fn build(doc: &CanonicalDocument, symbols: &[QuerySymbol], b: &mut Budget) -> Result<Self> {
        let types = doc.components().analysis().graph().types();
        b.charge(R::LayoutItems, types.record_types().len())?;
        let definitions: BTreeMap<_, _> = types
            .record_types()
            .iter()
            .map(|r| (r.id(), r.definition()))
            .collect();
        let enums: BTreeMap<_, _> = types
            .enum_types()
            .iter()
            .map(|e| (e.id(), &e.definition().members))
            .collect();
        let mut degrees = BTreeMap::new();
        let mut parents: BTreeMap<&str, BTreeSet<&str>> = BTreeMap::new();
        for (&id, r) in &definitions {
            let mut deps = BTreeSet::new();
            for f in &r.fields {
                b.charge(R::LayoutItems, 1)?;
                let mut ty = &f.value_type;
                while let ValueType::Option { inner } = ty {
                    ty = inner;
                }
                if let ValueType::Record { record_type } = ty {
                    deps.insert(record_type.as_str());
                }
            }
            degrees.insert(id, deps.len());
            for d in deps {
                parents.entry(d).or_default().insert(id);
            }
        }
        let mut ready: BTreeSet<_> = degrees
            .iter()
            .filter(|(_, n)| **n == 0)
            .map(|(&id, _)| id)
            .collect();
        let mut layout = Self {
            shapes: Vec::new(),
            inputs: Vec::new(),
        };
        let mut records = BTreeMap::new();
        while let Some(id) = ready.pop_first() {
            let r = definitions[id];
            b.charge(R::LayoutItems, r.fields.len())?;
            let mut fields = Vec::with_capacity(r.fields.len());
            let mut width = 0usize;
            for f in &r.fields {
                let shape = layout.ty(&f.value_type, &records, &enums, b)?;
                width = width
                    .checked_add(layout.shapes[shape].width)
                    .ok_or_else(|| b.error(R::ValueCells))?;
                fields.push((b.copy(&f.name)?, shape));
            }
            let descriptor = encoding::obj(vec![
                ("kind", encoding::s("record")),
                ("record_type", encoding::s(b.copy(id)?)),
            ]);
            let shape =
                layout.push(ShapeKind::Record(b.copy(id)?, fields), width, descriptor, b)?;
            records.insert(id, shape);
            if let Some(users) = parents.get(id) {
                for &p in users {
                    let n = degrees.get_mut(p).expect("P1 reference");
                    *n -= 1;
                    if *n == 0 {
                        ready.insert(p);
                    }
                }
            }
        }
        if records.len() != definitions.len() {
            return Err(SolverError::Internal("P1 type DAG"));
        }
        let tables: BTreeMap<_, _> = types
            .table_types()
            .iter()
            .map(|t| (t.id(), t.definition()))
            .collect();
        for node in doc.components().analysis().graph().nodes() {
            let Some(port) = node.input_port() else {
                continue;
            };
            b.charge(R::LayoutItems, 1)?;
            let table = tables[node.table_type()];
            b.observe(R::IntegerDigits, table.capacity.as_str().len())?;
            let capacity = table
                .capacity
                .as_str()
                .parse::<usize>()
                .map_err(|_| b.error(R::InputSlots))?;
            b.charge(R::InputSlots, capacity)?;
            let shape = records[table.record_type.as_str()];
            let width = layout.shapes[shape].width;
            let slot_width = width.checked_add(1).ok_or_else(|| b.error(R::ValueCells))?;
            b.charge(
                R::ValueCells,
                capacity
                    .checked_mul(slot_width)
                    .ok_or_else(|| b.error(R::ValueCells))?,
            )?;
            let slots = (0..capacity)
                .map(|_| vec![usize::MAX; slot_width])
                .collect();
            let ShapeKind::Record(_, fields) = &layout.shapes[shape].kind else {
                unreachable!()
            };
            b.charge(R::LayoutItems, table.primary_key.len())?;
            let keys = table
                .primary_key
                .iter()
                .map(|k| fields.binary_search_by(|(n, _)| n.cmp(k)).expect("P1 key"))
                .collect();
            let components = layout.components(shape, b)?;
            layout.inputs.push(Input {
                interface: b.copy(port)?,
                node: b.copy(node.supplied_id())?,
                table_type: b.copy(node.table_type())?,
                record_type: b.copy(&table.record_type)?,
                capacity,
                keys,
                shape,
                slots,
                components,
            });
        }
        layout.inputs.sort_by(|a, c| a.interface.cmp(&c.interface));
        for (i, symbol) in symbols.iter().enumerate() {
            let SymbolOrigin::Input {
                interface,
                slot,
                component,
            } = symbol.origin()
            else {
                continue;
            };
            let input = layout
                .inputs
                .binary_search_by(|v| v.interface.as_str().cmp(interface))
                .map_err(|_| SolverError::Internal("input origin"))?;
            let row = layout.inputs[input]
                .slots
                .get_mut(*slot)
                .ok_or(SolverError::Internal("slot origin"))?;
            let at = component.map_or(0, |n| n + 1);
            if at >= row.len() || row[at] != usize::MAX {
                return Err(SolverError::Internal("duplicate component"));
            }
            row[at] = i;
            let expected = component.map_or(Sort::Bool, |n| {
                layout.sort(layout.inputs[input].components[n].shape)
            });
            if Sort::parse(symbol.sort())? != expected {
                return Err(SolverError::Internal("component sort"));
            }
        }
        if layout
            .inputs
            .iter()
            .flat_map(|v| &v.slots)
            .flatten()
            .any(|&n| n == usize::MAX)
        {
            return Err(SolverError::Internal("incomplete layout"));
        }
        Ok(layout)
    }
    pub fn sort(&self, shape: usize) -> Sort {
        match self.shapes[shape].kind {
            ShapeKind::Bool | ShapeKind::Option(_) => Sort::Bool,
            ShapeKind::Text => Sort::Text,
            _ => Sort::Int,
        }
    }
    fn components(&self, shape: usize, b: &mut Budget) -> Result<Vec<Component>> {
        enum Task<'a> {
            Walk(usize),
            Name(&'a str),
            Pop,
        }
        b.charge(R::LayoutItems, 1)?;
        let mut pending = vec![Task::Walk(shape)];
        let mut path: Vec<&str> = Vec::new();
        let mut result = Vec::new();
        while let Some(task) = pending.pop() {
            b.charge(R::LayoutItems, 1)?;
            match task {
                Task::Name(name) => {
                    b.charge(R::ValueCells, 1)?;
                    path.push(name);
                }
                Task::Pop => {
                    path.pop();
                }
                Task::Walk(id) => match &self.shapes[id].kind {
                    ShapeKind::Record(_, fields) => {
                        b.charge(
                            R::LayoutItems,
                            fields
                                .len()
                                .checked_mul(3)
                                .ok_or_else(|| b.error(R::LayoutItems))?,
                        )?;
                        for (name, child) in fields.iter().rev() {
                            pending.push(Task::Pop);
                            pending.push(Task::Walk(*child));
                            pending.push(Task::Name(name));
                        }
                    }
                    kind => {
                        b.charge(R::ValueCells, path.len())?;
                        let copied = path.iter().map(|s| b.copy(s)).collect::<Result<Vec<_>>>()?;
                        let tag = matches!(kind, ShapeKind::Option(_));
                        result.push(Component {
                            path: copied,
                            shape: id,
                            tag,
                        });
                        if let ShapeKind::Option(child) = kind {
                            b.charge(R::LayoutItems, 1)?;
                            pending.push(Task::Walk(*child));
                        }
                    }
                },
            }
        }
        Ok(result)
    }
    pub fn emit(&self, ir: &str, query: &str, out: &mut impl FnMut(&[u8])) {
        out(b"{\"format\":\"axiom-p4-input-layout\",\"inputs\":[");
        for (i, v) in self.inputs.iter().enumerate() {
            if i > 0 {
                out(b",");
            }
            out(b"{\"capacity\":");
            emit_string(&v.capacity.to_string(), out);
            out(b",\"components\":[");
            for (j, c) in v.components.iter().enumerate() {
                if j > 0 {
                    out(b",");
                }
                out(b"{\"index\":");
                emit_string(&j.to_string(), out);
                out(b",\"path\":[");
                for (k, p) in c.path.iter().enumerate() {
                    if k > 0 {
                        out(b",");
                    }
                    emit_string(p, out);
                }
                out(b"],\"role\":");
                emit_string(if c.tag { "option-tag" } else { "value" }, out);
                out(b",\"sort\":");
                emit_string(self.sort(c.shape).name(), out);
                out(b",\"value_type\":");
                encoding::emit(&self.shapes[c.shape].descriptor, out);
                out(b"}");
            }
            out(b"],\"interface\":");
            emit_string(&v.interface, out);
            out(b",\"node\":");
            emit_string(&v.node, out);
            out(b",\"primary_key\":[");
            let ShapeKind::Record(_, fields) = &self.shapes[v.shape].kind else {
                unreachable!()
            };
            for (j, &k) in v.keys.iter().enumerate() {
                if j > 0 {
                    out(b",");
                }
                emit_string(&fields[k].0, out);
            }
            out(b"],\"record_type\":");
            emit_string(&v.record_type, out);
            out(b",\"table_type\":");
            emit_string(&v.table_type, out);
            out(b"}");
        }
        out(b"],\"ir_artifact\":");
        emit_string(ir, out);
        out(b",\"query_raw_digest\":");
        emit_string(query, out);
        out(b",\"version\":\"0.1\"}");
    }
}
