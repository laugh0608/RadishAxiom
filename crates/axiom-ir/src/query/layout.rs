//! 有限复合值使用平坦叶数组，记录类型引用和析构都不沿深 DAG 递归。
use super::{
    Budget, QueryError, QueryResource, Result,
    smt::{Arena, Op, Sort, Term},
};
use crate::{declarations::ValueType, normalization::NormalizedTypeDeclarations};
use std::{
    collections::{BTreeMap, BTreeSet},
    rc::Rc,
};

pub(super) type LayoutId = usize;
pub(super) enum Shape {
    Atom {
        sort: Sort,
        bounds: Option<(String, String)>,
    },
    Option(LayoutId),
    Record(Vec<(String, LayoutId, usize)>),
}
pub(super) struct Layout {
    pub shape: Shape,
    pub len: usize,
}
pub(super) struct Layouts {
    pub entries: Vec<Layout>,
    pub records: BTreeMap<String, LayoutId>,
    enums: BTreeMap<String, usize>,
}
#[derive(Clone)]
pub(super) struct Data {
    pub layout: LayoutId,
    pub lanes: Rc<[Term]>,
    pub start: usize,
}
impl Layouts {
    pub fn new(types: &NormalizedTypeDeclarations, budget: &mut Budget) -> Result<Self> {
        let mut result = Self {
            entries: Vec::new(),
            records: BTreeMap::new(),
            enums: types
                .enum_types()
                .iter()
                .map(|e| (e.id().to_owned(), e.definition().members.len()))
                .collect(),
        };
        let records: BTreeMap<_, _> = types
            .record_types()
            .iter()
            .map(|r| (r.id(), r.definition()))
            .collect();
        let mut degrees = BTreeMap::new();
        let mut parents: BTreeMap<&str, BTreeSet<&str>> = BTreeMap::new();
        for (&id, record) in &records {
            let mut deps = BTreeSet::new();
            for field in &record.fields {
                let mut ty = &field.value_type;
                while let ValueType::Option { inner } = ty {
                    ty = inner;
                }
                if let ValueType::Record { record_type } = ty {
                    deps.insert(record_type.as_str());
                }
            }
            degrees.insert(id, deps.len());
            for dep in deps {
                parents.entry(dep).or_default().insert(id);
            }
        }
        let mut ready: BTreeSet<_> = degrees
            .iter()
            .filter(|(_, n)| **n == 0)
            .map(|(&id, _)| id)
            .collect();
        while let Some(id) = ready.pop_first() {
            let record = records[id];
            budget.charge(QueryResource::ValueCells, record.fields.len())?;
            let mut fields = Vec::with_capacity(record.fields.len());
            let mut len = 0usize;
            for field in &record.fields {
                let layout = result.value_type(&field.value_type, budget)?;
                fields.push((field.name.clone(), layout, len));
                len = len
                    .checked_add(result.entries[layout].len)
                    .filter(|n| *n <= budget.limits.max_value_cells)
                    .ok_or_else(|| budget.error(QueryResource::ValueCells))?;
            }
            let layout = result.add(Shape::Record(fields), len, budget)?;
            result.records.insert(id.to_owned(), layout);
            if let Some(users) = parents.get(id) {
                for &parent in users {
                    let count = degrees.get_mut(parent).expect("known record");
                    *count -= 1;
                    if *count == 0 {
                        ready.insert(parent);
                    }
                }
            }
        }
        if result.records.len() != records.len() {
            return Err(QueryError::Internal("P1 record DAG"));
        }
        Ok(result)
    }
    fn add(&mut self, shape: Shape, len: usize, budget: &mut Budget) -> Result<LayoutId> {
        if len > budget.limits.max_value_cells {
            return Err(budget.error(QueryResource::ValueCells));
        }
        budget.charge(QueryResource::ValueCells, 1)?;
        let id = self.entries.len();
        self.entries.push(Layout { shape, len });
        Ok(id)
    }
    pub fn atom(&mut self, sort: Sort, budget: &mut Budget) -> Result<LayoutId> {
        self.add(Shape::Atom { sort, bounds: None }, 1, budget)
    }
    pub fn option(&mut self, inner: LayoutId, budget: &mut Budget) -> Result<LayoutId> {
        let len = self.entries[inner]
            .len
            .checked_add(1)
            .ok_or_else(|| budget.error(QueryResource::ValueCells))?;
        self.add(Shape::Option(inner), len, budget)
    }
    pub fn value_type(&mut self, ty: &ValueType, budget: &mut Budget) -> Result<LayoutId> {
        match ty {
            ValueType::Record { record_type } => Ok(self.records[record_type]),
            ValueType::Option { inner } => {
                let inner = self.value_type(inner, budget)?;
                self.option(inner, budget)
            }
            ValueType::Bool => self.atom(Sort::Bool, budget),
            ValueType::Text => self.atom(Sort::Text, budget),
            ValueType::Int { lower, upper } | ValueType::Fixed { lower, upper, .. } => {
                budget.charge(
                    QueryResource::ValueCells,
                    lower.as_str().len() + upper.as_str().len(),
                )?;
                self.add(
                    Shape::Atom {
                        sort: Sort::Int,
                        bounds: Some((lower.as_str().to_owned(), upper.as_str().to_owned())),
                    },
                    1,
                    budget,
                )
            }
            ValueType::Enum { enum_type } => self.add(
                Shape::Atom {
                    sort: Sort::Int,
                    bounds: Some(("0".to_owned(), (self.enums[enum_type] - 1).to_string())),
                },
                1,
                budget,
            ),
        }
    }
    pub fn slice<'a>(&self, data: &'a Data) -> &'a [Term] {
        &data.lanes[data.start..data.start + self.entries[data.layout].len]
    }
    pub fn field(&self, data: &Data, name: &str) -> Data {
        let Shape::Record(fields) = &self.entries[data.layout].shape else {
            unreachable!("typed record")
        };
        let index = fields
            .binary_search_by(|(field, _, _)| field.as_str().cmp(name))
            .expect("typed field");
        let (_, layout, offset) = &fields[index];
        Data {
            layout: *layout,
            lanes: data.lanes.clone(),
            start: data.start + offset,
        }
    }
    pub fn inner(&self, data: &Data) -> Data {
        let Shape::Option(layout) = self.entries[data.layout].shape else {
            unreachable!("typed Option")
        };
        Data {
            layout,
            lanes: data.lanes.clone(),
            start: data.start + 1,
        }
    }
    pub fn make(&self, layout: LayoutId, lanes: Vec<Term>) -> Data {
        assert_eq!(self.entries[layout].len, lanes.len());
        Data {
            layout,
            lanes: lanes.into(),
            start: 0,
        }
    }
    /// 返回平坦叶的类型；Option 标签占一个 Bool，内值紧随其后。
    pub fn leaves(&self, layout: LayoutId, budget: &mut Budget) -> Result<Vec<Sort>> {
        budget.charge(QueryResource::ValueCells, self.entries[layout].len)?;
        let mut result = Vec::with_capacity(self.entries[layout].len);
        let mut pending = vec![layout];
        while let Some(id) = pending.pop() {
            match &self.entries[id].shape {
                Shape::Atom { sort, .. } => result.push(*sort),
                Shape::Option(inner) => {
                    result.push(Sort::Bool);
                    pending.push(*inner);
                }
                Shape::Record(fields) => {
                    pending.extend(fields.iter().rev().map(|(_, id, _)| *id));
                }
            }
        }
        Ok(result)
    }
    pub fn default_value(
        &self,
        layout: LayoutId,
        empty_text: Term,
        arena: &mut Arena,
    ) -> Result<Data> {
        let sorts = self.leaves(layout, &mut arena.budget)?;
        arena
            .budget
            .charge(QueryResource::ValueCells, sorts.len())?;
        let mut lanes = Vec::with_capacity(sorts.len());
        for sort in sorts {
            lanes.push(match sort {
                Sort::Bool => arena.boolean(false),
                Sort::Int => arena.integer("0")?,
                Sort::Text => empty_text,
            });
        }
        Ok(self.make(layout, lanes))
    }
    pub fn ite(
        &self,
        condition: Term,
        left: &Data,
        right: &Data,
        arena: &mut Arena,
    ) -> Result<Data> {
        let len = self.entries[left.layout].len;
        if len != self.entries[right.layout].len {
            return Err(QueryError::Internal("typed branch layout"));
        }
        arena.budget.charge(QueryResource::ValueCells, len)?;
        let mut lanes = Vec::with_capacity(len);
        for (&a, &b) in self.slice(left).iter().zip(self.slice(right)) {
            lanes.push(arena.ite(condition, a, b)?);
        }
        Ok(self.make(left.layout, lanes))
    }
    pub fn equal(&self, left: &Data, right: &Data, arena: &mut Arena) -> Result<Term> {
        let mut pending = vec![(left.layout, left.start, right.start, arena.boolean(true))];
        let mut terms = Vec::new();
        while let Some((layout, a, b, guard)) = pending.pop() {
            match &self.entries[layout].shape {
                Shape::Atom { .. } => {
                    let eq = arena.app(Op::Eq, &[left.lanes[a], right.lanes[b]])?;
                    terms.push(arena.implies(guard, eq)?);
                }
                Shape::Option(inner) => {
                    let eq = arena.app(Op::Eq, &[left.lanes[a], right.lanes[b]])?;
                    terms.push(arena.implies(guard, eq)?);
                    let active = arena.and(&[guard, left.lanes[a]])?;
                    pending.push((*inner, a + 1, b + 1, active));
                }
                Shape::Record(_) => {
                    return Err(QueryError::Internal("P1 excludes record equality"));
                }
            }
        }
        arena.and(&terms)
    }
    pub fn wf(&self, data: &Data, arena: &mut Arena) -> Result<Term> {
        let mut terms = Vec::new();
        let mut pending = vec![(data.layout, data.start, arena.boolean(true))];
        while let Some((layout, offset, guard)) = pending.pop() {
            match &self.entries[layout].shape {
                Shape::Atom {
                    bounds: Some((lower, upper)),
                    ..
                } => {
                    let lo = arena.integer(lower)?;
                    let hi = arena.integer(upper)?;
                    let low = arena.app(Op::Le, &[lo, data.lanes[offset]])?;
                    let high = arena.app(Op::Le, &[data.lanes[offset], hi])?;
                    let range = arena.and(&[low, high])?;
                    terms.push(arena.implies(guard, range)?);
                }
                Shape::Atom { bounds: None, .. } => {}
                Shape::Option(inner) => {
                    let guard = arena.and(&[guard, data.lanes[offset]])?;
                    pending.push((*inner, offset + 1, guard));
                }
                Shape::Record(fields) => pending.extend(
                    fields
                        .iter()
                        .rev()
                        .map(|(_, id, at)| (*id, offset + at, guard)),
                ),
            }
        }
        arena.and(&terms)
    }
}
