use super::{
    ReplayError, ReplayResource as R, Result, arithmetic,
    budget::Budget,
    engine::{Engine, Observation, Table, Val},
    flat::{Json, Node},
};
use crate::{declarations::ValueType, integer::Integer};
use std::{cmp::Ordering, sync::Arc};

type InvalidValue = Option<(Vec<String>, &'static str)>;
impl<'a> Engine<'a> {
    pub(super) fn read_inputs(
        &mut self,
        j: &Json,
        root: usize,
        b: &mut Budget,
    ) -> Result<Option<Observation<'a>>> {
        let entries = j.array(root)?;
        let count = self
            .interfaces
            .keys()
            .filter(|(kind, _)| *kind == "input")
            .count();
        b.charge(R::ValueCells, count)?;
        let inputs: Vec<_> = self
            .interfaces
            .iter()
            .filter(|((kind, _), _)| *kind == "input")
            .map(|((_, port), id)| (*port, *id))
            .collect();
        if entries.len() != inputs.len() {
            return Err(j.error(root, "complete input interfaces"));
        }
        let mut first = None;
        for (&entry, (port, id)) in entries.iter().zip(inputs) {
            j.closed(entry, &["interface", "table_type", "rows"])?;
            j.exact(entry, "interface", port)?;
            let tt = super::text(self.node_definition(id), "table_type");
            j.exact(entry, "table_type", tt)?;
            let table = self.table_types[tt];
            let raw = j.array(j.get(entry, "rows")?)?;
            b.charge(R::Rows, raw.len())?;
            let mut rows = Vec::with_capacity(raw.len());
            for (i, &r) in raw.iter().enumerate() {
                let (v, invalid) = self.read_value(j, r, table.record_type.as_str(), b)?;
                rows.push(v);
                if first.is_none()
                    && let Some((path, reason)) = invalid
                {
                    first = Some(Observation::Input {
                        interface: port,
                        rows: vec![i],
                        path,
                        reason,
                    });
                }
            }
            if first.is_none() {
                let n = arithmetic::parse(&rows.len().to_string(), b)?;
                if arithmetic::compare(&n, &table.capacity, b)? == Ordering::Greater {
                    first = Some(Observation::Input {
                        interface: port,
                        rows: Vec::new(),
                        path: Vec::new(),
                        reason: "capacity",
                    });
                } else {
                    for i in 1..rows.len() {
                        match self.row_cmp(rows[i - 1], rows[i], table, b)? {
                            Ordering::Greater => {
                                return Err(ReplayError::NonCanonicalWorld { offset: 0 });
                            }
                            Ordering::Equal => {
                                first = Some(Observation::Input {
                                    interface: port,
                                    rows: vec![i - 1, i],
                                    path: Vec::new(),
                                    reason: "duplicate-key",
                                });
                                break;
                            }
                            Ordering::Less => {}
                        }
                    }
                }
            }
            b.charge(R::ValueCells, 3)?;
            self.computed.insert(
                id,
                Table {
                    ready: true,
                    ok: true,
                    rows: Arc::new(rows),
                    selected: Arc::new(Vec::new()),
                    cause: None,
                },
            );
        }
        Ok(first)
    }
    fn read_value(
        &mut self,
        j: &Json,
        root: usize,
        record: &'a str,
        b: &mut Budget,
    ) -> Result<(usize, InvalidValue)> {
        enum Task<'a> {
            Value(usize, &'a ValueType),
            Record(usize, &'a str),
            FinishRecord(&'a str, usize),
            Some,
            Name(&'a str),
            Pop,
        }
        b.charge(R::ValueCells, 1)?;
        let mut stack = vec![Task::Record(root, record)];
        let mut values = Vec::new();
        let mut path: Vec<&str> = Vec::new();
        let mut invalid = None;
        while let Some(task) = stack.pop() {
            b.step()?;
            match task {
                Task::Name(s) => {
                    b.charge(R::ValueCells, 1)?;
                    path.push(s);
                }
                Task::Pop => {
                    path.pop();
                }
                Task::Some => {
                    b.charge(R::ValueCells, 1)?;
                    let c = values.pop().ok_or(ReplayError::Internal("world Some"))?;
                    values.push(self.push(Val::Some(c), b)?);
                }
                Task::FinishRecord(ty, n) => {
                    b.charge(R::ValueCells, 1)?;
                    b.charge(R::ValueCells, n)?;
                    let fields = values.split_off(values.len() - n);
                    values.push(self.push(Val::Record(ty, fields), b)?);
                }
                Task::Record(id, ty) => {
                    j.closed(id, &["kind", "record_type", "fields"])?;
                    j.exact(id, "kind", "record")?;
                    j.exact(id, "record_type", ty)?;
                    let fields = j.array(j.get(id, "fields")?)?;
                    let decl = &self.records[ty].fields;
                    if fields.len() != decl.len() {
                        return Err(j.error(id, "complete record fields"));
                    }
                    b.charge(
                        R::ValueCells,
                        fields
                            .len()
                            .checked_mul(3)
                            .and_then(|n| n.checked_add(1))
                            .ok_or_else(|| b.error(R::ValueCells))?,
                    )?;
                    stack.push(Task::FinishRecord(ty, fields.len()));
                    for (&field, f) in fields.iter().zip(decl).rev() {
                        j.closed(field, &["name", "value"])?;
                        j.exact(field, "name", &f.name)?;
                        stack.push(Task::Pop);
                        stack.push(Task::Value(j.get(field, "value")?, &f.value_type));
                        stack.push(Task::Name(&f.name));
                    }
                }
                Task::Value(id, ty) => {
                    let mut bad = None;
                    let v = match ty {
                        ValueType::Record { record_type } => {
                            b.charge(R::ValueCells, 1)?;
                            stack.push(Task::Record(id, record_type));
                            continue;
                        }
                        ValueType::Option { inner } => match j.text(id, "kind")? {
                            "none" => {
                                j.closed(id, &["kind"])?;
                                Val::None
                            }
                            "some" => {
                                j.closed(id, &["kind", "value"])?;
                                b.charge(R::ValueCells, 2)?;
                                stack.push(Task::Some);
                                stack.push(Task::Value(j.get(id, "value")?, inner));
                                continue;
                            }
                            _ => return Err(j.error(id, "Option tag")),
                        },
                        ValueType::Bool => {
                            j.closed(id, &["kind", "value"])?;
                            j.exact(id, "kind", "bool")?;
                            let Node::Bool(v) = j.nodes[j.get(id, "value")?] else {
                                return Err(j.error(id, "Bool value"));
                            };
                            Val::Bool(v)
                        }
                        ValueType::Text => {
                            j.closed(id, &["kind", "value"])?;
                            j.exact(id, "kind", "text")?;
                            Val::Text(b.text_copy(j.text(id, "value")?)?)
                        }
                        ValueType::Enum { enum_type } => {
                            j.closed(id, &["kind", "enum_type", "member"])?;
                            j.exact(id, "kind", "enum")?;
                            j.exact(id, "enum_type", enum_type)?;
                            let member = j.text(id, "member")?;
                            let at = self.enums[enum_type.as_str()]
                                .members
                                .iter()
                                .position(|m| m == member);
                            if at.is_none() {
                                bad = Some("enum-member");
                            }
                            Val::Enum(enum_type, at.unwrap_or(0))
                        }
                        ValueType::Int { lower, upper } | ValueType::Fixed { lower, upper, .. } => {
                            let fixed = matches!(ty, ValueType::Fixed { .. });
                            let field = if fixed { "coefficient" } else { "value" };
                            j.closed(
                                id,
                                if fixed {
                                    &["kind", "coefficient", "scale"]
                                } else {
                                    &["kind", "value"]
                                },
                            )?;
                            j.exact(id, "kind", if fixed { "fixed" } else { "int" })?;
                            let s = j.text(id, field)?;
                            b.observe(R::IntegerDigits, s.trim_start_matches('-').len())?;
                            b.charge(R::ValueCells, s.len())?;
                            b.charge(R::DigitWork, s.len())?;
                            let n = Integer::parse(s)
                                .ok_or_else(|| j.error(id, "canonical integer"))?;
                            if arithmetic::compare(&n, lower, b)? == Ordering::Less
                                || arithmetic::compare(&n, upper, b)? == Ordering::Greater
                            {
                                bad = Some("range");
                            }
                            if let ValueType::Fixed { scale, .. } = ty {
                                j.exact(id, "scale", scale.as_str())?;
                                Val::Fixed(scale.as_str(), n)
                            } else {
                                Val::Int(n)
                            }
                        }
                    };
                    if invalid.is_none()
                        && let Some(reason) = bad
                    {
                        let bytes = path
                            .iter()
                            .try_fold(0usize, |n, s| n.checked_add(s.len()))
                            .ok_or_else(|| b.error(R::PathBytes))?;
                        b.charge(R::PathBytes, bytes)?;
                        let p = path.iter().map(|s| b.copy(s)).collect::<Result<Vec<_>>>()?;
                        invalid = Some((p, reason));
                    }
                    b.charge(R::ValueCells, 1)?;
                    values.push(self.push(v, b)?);
                }
            }
        }
        Ok((values[0], invalid))
    }
}
