//! 世界值使用平坦 arena 和有界任务栈，深 Record DAG 不形成递归所有权。
use super::{
    encoding,
    layout::{Input, ShapeKind},
    *,
};
use crate::{
    json::{Value, emit_string},
    obligations::raw_digest,
};
use std::{cmp::Ordering, collections::BTreeSet};

struct TextClasses<'a> {
    replacements: BTreeMap<&'a str, String>,
    groups: Vec<(&'a str, Vec<&'a str>)>,
}
fn text_classes<'a>(
    request: &'a SolverRequest,
    model: &'a SatModel,
    b: &mut Budget,
) -> Result<TextClasses<'a>> {
    let mut groups: BTreeMap<&str, (Option<&str>, Vec<&str>)> = BTreeMap::new();
    let mut literals = BTreeSet::new();
    for symbol in request.query.symbols() {
        b.step()?;
        if symbol.sort() != "Text" {
            continue;
        }
        let ModelValue::Text(atom) = model.values[symbol.name()].as_ref() else {
            return Err(SolverError::Internal("Text sort"));
        };
        b.charge(SolverResource::ValueCells, 2)?;
        let entry = groups.entry(atom.as_str()).or_default();
        entry.1.push(symbol.name());
        if let crate::query::SymbolOrigin::TextLiteral(v) = symbol.origin() {
            if entry.0.is_some_and(|known| known != v) {
                return Err(SolverError::LiteralClassConflict);
            }
            entry.0 = Some(v);
            literals.insert(v.as_str());
        }
    }
    let mut fresh = Vec::new();
    let mut replacements = BTreeMap::new();
    for (atom, (literal, names)) in groups {
        b.step()?;
        let order = super::order::sorted_indices(&names, b, |a, c, _| Ok(a.cmp(c)))?;
        b.charge(SolverResource::ValueCells, names.len())?;
        let names: Vec<_> = order.into_iter().map(|i| names[i]).collect();
        if let Some(v) = literal {
            b.charge(SolverResource::TextBytes, v.len())?;
            replacements.insert(atom, b.copy(v)?);
        } else {
            fresh.push((atom, names));
        }
    }
    let order = super::order::sorted_indices(&fresh, b, |a, c, _| Ok(a.1[0].cmp(c.1[0])))?;
    b.charge(SolverResource::ValueCells, fresh.len())?;
    let mut ordered = Vec::with_capacity(fresh.len());
    for at in order {
        b.charge(SolverResource::ValueCells, fresh[at].1.len())?;
        ordered.push((fresh[at].0, fresh[at].1.clone()));
    }
    let fresh = ordered;
    for (i, (atom, _)) in fresh.iter().enumerate() {
        let mut nonce = 0usize;
        loop {
            b.step()?;
            let number = i.to_string();
            let suffix = nonce.to_string();
            b.observe(
                SolverResource::IntegerDigits,
                number.len().max(suffix.len()),
            )?;
            let size = "@axiom-text::"
                .len()
                .checked_add(number.len())
                .and_then(|v| v.checked_add(suffix.len()))
                .ok_or_else(|| b.error(SolverResource::TextBytes))?;
            b.charge(SolverResource::TextBytes, size)?;
            b.charge(SolverResource::ValueCells, size)?;
            let candidate = format!("@axiom-text:{number}:{suffix}");
            if !literals.contains(candidate.as_str()) {
                replacements.insert(*atom, candidate);
                break;
            }
            nonce = nonce
                .checked_add(1)
                .ok_or_else(|| b.error(SolverResource::DecodeSteps))?;
        }
    }
    Ok(TextClasses {
        replacements,
        groups: fresh,
    })
}
enum WorldValue {
    Scalar {
        shape: usize,
        value: Arc<ModelValue>,
    },
    None,
    Some(usize),
    Record {
        shape: usize,
        fields: Vec<usize>,
    },
}
struct WorldTable<'a> {
    input: &'a Input,
    rows: Vec<(usize, usize)>,
}
struct Materializer<'a, 'b> {
    request: &'a SolverRequest,
    model: &'a SatModel,
    budget: &'b mut Budget,
    values: Vec<WorldValue>,
    used_text: BTreeSet<&'a str>,
}
impl<'a> Materializer<'a, '_> {
    fn push(&mut self, value: WorldValue) -> Result<usize> {
        self.budget.charge(SolverResource::ValueCells, 1)?;
        let id = self.values.len();
        self.values.push(value);
        Ok(id)
    }
    fn invalid(
        &self,
        input: &Input,
        slot: usize,
        path: &[&str],
        reason: &'static str,
    ) -> SolverError {
        SolverError::InvalidInput {
            interface: input.interface.clone(),
            slot,
            path: path.iter().map(|s| (*s).to_owned()).collect(),
            reason,
        }
    }
    fn row(&mut self, input: &Input, slot: usize) -> Result<usize> {
        enum Task<'a> {
            Visit(usize, usize),
            FinishRecord(usize, usize),
            FinishSome,
            Name(&'a str),
            Pop,
        }
        self.budget.charge(SolverResource::ValueCells, 1)?;
        let mut tasks = vec![Task::Visit(input.shape, 0)];
        let mut results = Vec::new();
        let mut path = Vec::new();
        while let Some(task) = tasks.pop() {
            self.budget.step()?;
            match task {
                Task::Name(name) => {
                    self.budget.charge(SolverResource::ValueCells, 1)?;
                    path.push(name);
                }
                Task::Pop => {
                    path.pop();
                }
                Task::FinishSome => {
                    let child = results.pop().ok_or(SolverError::Internal("Some child"))?;
                    results.push(self.push(WorldValue::Some(child))?);
                }
                Task::FinishRecord(shape, len) => {
                    self.budget.charge(SolverResource::ValueCells, len)?;
                    let fields = results.split_off(results.len() - len);
                    let id = self.push(WorldValue::Record { shape, fields })?;
                    results.push(id);
                }
                Task::Visit(id, at) => {
                    self.budget.charge(SolverResource::ValueCells, 1)?;
                    match &self.request.layout.shapes[id].kind {
                        ShapeKind::Record(_, fields) => {
                            self.budget.charge(
                                SolverResource::ValueCells,
                                fields
                                    .len()
                                    .checked_mul(3)
                                    .and_then(|v| v.checked_add(1))
                                    .ok_or_else(|| self.budget.error(SolverResource::ValueCells))?,
                            )?;
                            tasks.push(Task::FinishRecord(id, fields.len()));
                            let mut offset = at + self.request.layout.shapes[id].width;
                            for (name, shape) in fields.iter().rev() {
                                offset -= self.request.layout.shapes[*shape].width;
                                tasks.push(Task::Pop);
                                tasks.push(Task::Visit(*shape, offset));
                                tasks.push(Task::Name(name));
                            }
                        }
                        ShapeKind::Option(child) => {
                            let sym = &self.request.query.symbols()[input.slots[slot][at + 1]];
                            let ModelValue::Bool(some) = self.model.values[sym.name()].as_ref()
                            else {
                                return Err(SolverError::Internal("Option tag"));
                            };
                            if *some {
                                self.budget.charge(SolverResource::ValueCells, 2)?;
                                tasks.push(Task::FinishSome);
                                tasks.push(Task::Visit(*child, at + 1));
                            } else {
                                results.push(self.push(WorldValue::None)?);
                            }
                        }
                        kind => {
                            let sym = &self.request.query.symbols()[input.slots[slot][at + 1]];
                            let value = &self.model.values[sym.name()];
                            match (kind, value.as_ref()) {
                                (
                                    ShapeKind::Int(lo, hi) | ShapeKind::Fixed(_, lo, hi),
                                    ModelValue::Int(n),
                                ) if n < lo || n > hi => {
                                    return Err(self.invalid(input, slot, &path, "numeric-range"));
                                }
                                (ShapeKind::Enum(_, members), ModelValue::Int(n))
                                    if n.as_str()
                                        .parse::<usize>()
                                        .ok()
                                        .is_none_or(|i| i >= members.len()) =>
                                {
                                    return Err(self.invalid(input, slot, &path, "enum-index"));
                                }
                                (ShapeKind::Text, ModelValue::Text(_)) => {
                                    self.budget.charge(SolverResource::ValueCells, 1)?;
                                    self.used_text.insert(sym.name());
                                }
                                _ => {}
                            }
                            results.push(self.push(WorldValue::Scalar {
                                shape: id,
                                value: value.clone(),
                            })?);
                        }
                    }
                }
            }
        }
        if results.len() != 1 {
            return Err(SolverError::Internal("row root"));
        }
        Ok(results[0])
    }
    fn sort(
        &mut self,
        input: &Input,
        rows: &mut Vec<(usize, usize)>,
        texts: &TextClasses<'_>,
    ) -> Result<()> {
        let values = &self.values;
        let order = super::order::sorted_indices(rows, self.budget, |a, c, b| {
            compare_rows(values, b, input, a.0, c.0, texts)
        })?;
        self.budget.charge(SolverResource::ValueCells, rows.len())?;
        let sorted = order.into_iter().map(|i| rows[i]).collect();
        *rows = sorted;
        for pair in rows.windows(2) {
            if compare_rows(values, self.budget, input, pair[0].0, pair[1].0, texts)?
                == Ordering::Equal
            {
                return Err(self.invalid(input, pair[1].1, &[], "duplicate-key"));
            }
        }
        Ok(())
    }
    fn emit_value(&self, root: usize, texts: &TextClasses<'_>, out: &mut dyn FnMut(&[u8])) {
        enum Task<'a> {
            Node(usize),
            Raw(&'static [u8]),
            String(&'a str),
        }
        let mut stack = vec![Task::Node(root)];
        while let Some(task) = stack.pop() {
            match task {
                Task::Raw(v) => out(v),
                Task::String(v) => emit_string(v, &mut |v| out(v)),
                Task::Node(id) => match &self.values[id] {
                    WorldValue::None => out(b"{\"kind\":\"none\"}"),
                    WorldValue::Some(child) => {
                        out(b"{\"kind\":\"some\",\"value\":");
                        stack.push(Task::Raw(b"}"));
                        stack.push(Task::Node(*child));
                    }
                    WorldValue::Record { shape, fields } => {
                        let ShapeKind::Record(ty, names) = &self.request.layout.shapes[*shape].kind
                        else {
                            unreachable!()
                        };
                        out(b"{\"fields\":[");
                        stack.push(Task::Raw(b"}"));
                        stack.push(Task::String(ty));
                        stack.push(Task::Raw(b"],\"kind\":\"record\",\"record_type\":"));
                        for (i, child) in fields.iter().enumerate().rev() {
                            stack.push(Task::Raw(b"}"));
                            stack.push(Task::Node(*child));
                            stack.push(Task::Raw(b",\"value\":"));
                            stack.push(Task::String(&names[i].0));
                            stack.push(Task::Raw(b"{\"name\":"));
                            if i > 0 {
                                stack.push(Task::Raw(b","));
                            }
                        }
                    }
                    WorldValue::Scalar { shape, value } => {
                        match (&self.request.layout.shapes[*shape].kind, value.as_ref()) {
                            (ShapeKind::Bool, ModelValue::Bool(v)) => out(if *v {
                                b"{\"kind\":\"bool\",\"value\":true}"
                            } else {
                                b"{\"kind\":\"bool\",\"value\":false}"
                            }),
                            (ShapeKind::Int(..), ModelValue::Int(n)) => {
                                out(b"{\"kind\":\"int\",\"value\":");
                                emit_string(n.as_str(), &mut |v| out(v));
                                out(b"}");
                            }
                            (ShapeKind::Fixed(scale, ..), ModelValue::Int(n)) => {
                                out(b"{\"coefficient\":");
                                emit_string(n.as_str(), &mut |v| out(v));
                                out(b",\"kind\":\"fixed\",\"scale\":");
                                emit_string(scale, &mut |v| out(v));
                                out(b"}");
                            }
                            (ShapeKind::Enum(ty, members), ModelValue::Int(n)) => {
                                out(b"{\"enum_type\":");
                                emit_string(ty, &mut |v| out(v));
                                out(b",\"kind\":\"enum\",\"member\":");
                                emit_string(
                                    &members[n.as_str().parse::<usize>().expect("checked Enum")],
                                    &mut |v| out(v),
                                );
                                out(b"}");
                            }
                            (ShapeKind::Text, ModelValue::Text(atom)) => {
                                out(b"{\"kind\":\"text\",\"value\":");
                                emit_string(&texts.replacements[atom.as_str()], &mut |v| out(v));
                                out(b"}");
                            }
                            _ => unreachable!("typed model"),
                        }
                    }
                },
            }
        }
    }
}

pub(super) fn decode(request: &SolverRequest, model: &SatModel) -> Result<ModelWorldCandidate> {
    if model.record.request != request.artifact_digest() {
        return Err(SolverError::BindingMismatch);
    }
    let mut b = Budget::new(request.limits, SolverStage::Decode);
    let texts = text_classes(request, model, &mut b)?;
    let mut m = Materializer {
        request,
        model,
        budget: &mut b,
        values: Vec::new(),
        used_text: BTreeSet::new(),
    };
    let mut tables = Vec::new();
    for input in &request.layout.inputs {
        m.budget
            .charge(SolverResource::InputSlots, input.capacity)?;
        m.budget
            .charge(SolverResource::ValueCells, input.capacity)?;
        let mut rows = Vec::new();
        for (slot, names) in input.slots.iter().enumerate() {
            m.budget.step()?;
            let symbol = &request.query.symbols()[names[0]];
            let ModelValue::Bool(active) = model.values[symbol.name()].as_ref() else {
                return Err(SolverError::Internal("active sort"));
            };
            if *active {
                rows.push((m.row(input, slot)?, slot));
            }
        }
        m.sort(input, &mut rows, &texts)?;
        m.budget.charge(SolverResource::ValueCells, 1)?;
        tables.push(WorldTable { input, rows });
    }
    let mut classes = Vec::new();
    for (atom, names) in &texts.groups {
        m.budget.step()?;
        let mut used = Vec::new();
        for &name in names {
            m.budget.step()?;
            if m.used_text.contains(name) {
                used.push(encoding::s(m.budget.copy(name)?));
            }
        }
        if !used.is_empty() {
            classes.push(encoding::obj(vec![
                ("symbols", Value::Array(used)),
                (
                    "text",
                    encoding::s(m.budget.copy(&texts.replacements[atom])?),
                ),
            ]));
        }
    }
    let classes =
        encoding::canonical(&Value::Array(classes), SolverResource::WorldBytes, m.budget)?;
    // 两次编码的显式任务栈容量按 arena 节点 / 边保守收费，避免深树绕过输出限制。
    let workspace = m
        .values
        .len()
        .checked_mul(12)
        .ok_or_else(|| m.budget.error(SolverResource::ValueCells))?;
    m.budget.charge(SolverResource::ValueCells, workspace)?;
    let mut counter = Some(0usize);
    emit_tables(&m, &tables, &texts, &mut |v| {
        counter = counter.and_then(|n| n.checked_add(v.len()))
    });
    let length = counter.ok_or_else(|| m.budget.error(SolverResource::WorldBytes))?;
    m.budget.charge(SolverResource::WorldBytes, length)?;
    let mut world = Vec::with_capacity(length);
    emit_tables(&m, &tables, &texts, &mut |v| world.extend_from_slice(v));
    let bytes = encoding::output(m.budget, SolverResource::CandidateBytes, |out| {
        out(b"{\"format\":\"axiom-p4-model-world-candidate\",\"request\":");
        emit_string(request.artifact_digest(), &mut |v| out(v));
        out(b",\"response\":");
        emit_string(&model.record.digest, &mut |v| out(v));
        out(b",\"text_classes\":");
        out(&classes);
        out(b",\"version\":\"0.1\",\"world\":");
        out(&world);
        out(b"}");
    })?;
    Ok(ModelWorldCandidate {
        digest: raw_digest(&bytes),
        bytes,
        world,
        classes,
        usage: b.usage,
    })
}
fn emit_tables(
    m: &Materializer<'_, '_>,
    tables: &[WorldTable<'_>],
    texts: &TextClasses<'_>,
    out: &mut dyn FnMut(&[u8]),
) {
    out(b"[");
    for (i, table) in tables.iter().enumerate() {
        if i > 0 {
            out(b",");
        }
        out(b"{\"interface\":");
        emit_string(&table.input.interface, &mut |v| out(v));
        out(b",\"rows\":[");
        for (j, (root, _)) in table.rows.iter().enumerate() {
            if j > 0 {
                out(b",");
            }
            m.emit_value(*root, texts, out);
        }
        out(b"],\"table_type\":");
        emit_string(&table.input.table_type, &mut |v| out(v));
        out(b"}");
    }
    out(b"]");
}

fn compare_rows(
    values: &[WorldValue],
    budget: &mut Budget,
    input: &Input,
    left: usize,
    right: usize,
    texts: &TextClasses<'_>,
) -> Result<Ordering> {
    let WorldValue::Record { fields: a, .. } = &values[left] else {
        return Err(SolverError::Internal("key row"));
    };
    let WorldValue::Record { fields: c, .. } = &values[right] else {
        return Err(SolverError::Internal("key row"));
    };
    for &key in &input.keys {
        budget.step()?;
        let WorldValue::Scalar { value: x, .. } = &values[a[key]] else {
            return Err(SolverError::Internal("scalar key"));
        };
        let WorldValue::Scalar { value: y, .. } = &values[c[key]] else {
            return Err(SolverError::Internal("scalar key"));
        };
        let order = match (x.as_ref(), y.as_ref()) {
            (ModelValue::Bool(a), ModelValue::Bool(c)) => a.cmp(c),
            (ModelValue::Int(a), ModelValue::Int(c)) => a.cmp(c),
            (ModelValue::Text(a), ModelValue::Text(c)) => {
                texts.replacements[a.as_str()].cmp(&texts.replacements[c.as_str()])
            }
            _ => return Err(SolverError::Internal("key sort")),
        };
        if order != Ordering::Equal {
            return Ok(order);
        }
    }
    Ok(Ordering::Equal)
}
