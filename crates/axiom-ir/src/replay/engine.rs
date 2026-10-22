use super::{
    Budget, ReplayError, ReplayOutcome, ReplayResource as R, ReplayStage, Result, arithmetic,
    array, get, string, text,
};
use crate::{
    declarations::{EnumType, RecordType, TableType, ValueType},
    document::CanonicalDocument,
    integer::Integer,
    json::Value,
    obligations::ObligationKind,
};
use std::{cmp::Ordering, collections::BTreeMap, sync::Arc};

pub(super) enum Val<'a> {
    Bool(bool),
    Int(Integer),
    Fixed(&'a str, Integer),
    Text(String),
    Enum(&'a str, usize),
    None,
    Some(usize),
    Record(&'a str, Vec<usize>),
}
pub(super) struct Context<'a> {
    pub node: &'a str,
    pub key: Vec<usize>,
}
pub(super) struct Location<'a> {
    pub anchor: &'a str,
    pub path: Vec<String>,
    pub context: Vec<Context<'a>>,
}
pub(super) enum Cause<'a> {
    Range(usize),
    Capacity {
        node: &'a str,
        actual: usize,
        capacity: &'a str,
    },
    Dependency {
        node: &'a str,
        source: &'a str,
        cause: usize,
    },
}
pub(super) struct Table {
    pub ready: bool,
    pub ok: bool,
    pub rows: Arc<Vec<usize>>,
    pub selected: Arc<Vec<usize>>,
    pub cause: Option<usize>,
}
pub(super) struct Range<'a> {
    pub location: usize,
    pub operands: [usize; 2],
    pub value: usize,
    pub ty: &'a Value,
}
pub(super) enum Observation<'a> {
    Input {
        interface: &'a str,
        rows: Vec<usize>,
        path: Vec<String>,
        reason: &'static str,
    },
    Pre {
        contract: &'a str,
        reason: &'static str,
        location: usize,
    },
    Holds {
        detail: Detail<'a>,
    },
    Violated {
        detail: Detail<'a>,
    },
}
pub(super) enum Detail<'a> {
    RangeHolds,
    RangeViolation,
    Totality {
        node: &'a str,
        cause: Option<usize>,
    },
    Cardinality {
        node: &'a str,
        ready: bool,
        cause: Option<usize>,
        reason: Option<&'static str>,
        rows: Vec<usize>,
        key: Vec<usize>,
        actual: usize,
        capacity: &'a str,
    },
    Coverage {
        node: &'a str,
        ready: bool,
        cause: Option<usize>,
        direction: Option<&'static str>,
        key: Vec<usize>,
        matches: usize,
    },
    Guarantee {
        contract: &'a str,
        reason: Option<&'static str>,
        cause: Option<usize>,
        location: Option<usize>,
    },
}
type Evaluated = std::result::Result<usize, usize>;
pub(super) struct Engine<'a> {
    pub ir: &'a Value,
    pub kind: ObligationKind,
    pub nodes: Vec<&'a Value>,
    node_index: BTreeMap<&'a str, &'a Value>,
    pub records: BTreeMap<&'a str, &'a RecordType>,
    pub enums: BTreeMap<&'a str, &'a EnumType>,
    pub table_types: BTreeMap<&'a str, &'a TableType>,
    pub interfaces: BTreeMap<(&'a str, &'a str), &'a str>,
    pub computed: BTreeMap<&'a str, Table>,
    pub values: Vec<Val<'a>>,
    pub causes: Vec<Cause<'a>>,
    pub locations: Vec<Location<'a>>,
    pub context: Vec<Context<'a>>,
    pub target_anchor: &'a str,
    pub target_path: Vec<&'a str>,
    pub instances: usize,
    pub range: Option<Range<'a>>,
}
impl<'a> Engine<'a> {
    pub fn new(
        doc: &'a CanonicalDocument,
        ir: &'a Value,
        definition: &'a Value,
        kind: ObligationKind,
        b: &mut Budget,
    ) -> Result<Self> {
        let types = doc.components().analysis().graph().types();
        let count = [
            types.enum_types().len(),
            types.record_types().len(),
            types.table_types().len(),
        ]
        .into_iter()
        .try_fold(0usize, |n, x| n.checked_add(x))
        .ok_or_else(|| b.error(R::TypeItems))?;
        b.charge(R::TypeItems, count)?;
        b.charge(R::ValueCells, count)?;
        for e in types.enum_types() {
            b.charge(R::TypeItems, e.definition().members.len())?;
        }
        for r in types.record_types() {
            for f in &r.definition().fields {
                b.charge(R::TypeItems, 1)?;
                Self::type_budget(&f.value_type, b)?;
            }
        }
        for t in types.table_types() {
            b.charge(R::TypeItems, t.definition().primary_key.len())?;
            b.observe(R::IntegerDigits, t.definition().capacity.as_str().len())?;
        }
        let graph = doc.components().analysis().graph();
        b.charge(R::ValueCells, graph.nodes().len())?;
        let mut depths = vec![0usize; graph.nodes().len()];
        for &i in graph.topological_order() {
            b.step()?;
            depths[i] = graph.nodes()[i]
                .predecessors()
                .iter()
                .map(|&p| depths[p] + 1)
                .max()
                .unwrap_or(0);
        }
        b.charge(R::ValueCells, graph.nodes().len())?;
        let by_depth: BTreeMap<_, _> = graph
            .nodes()
            .iter()
            .enumerate()
            .map(|(i, n)| (n.supplied_id(), depths[i]))
            .collect();
        b.charge(
            R::ValueCells,
            array(get(ir, "nodes"))
                .len()
                .checked_mul(2)
                .ok_or_else(|| b.error(R::ValueCells))?,
        )?;
        let mut nodes: Vec<_> = array(get(ir, "nodes")).iter().collect();
        nodes.sort_by_key(|n| (by_depth[text(n, "id")], text(n, "id")));
        let mut interfaces = BTreeMap::new();
        for n in &nodes {
            let d = get(n, "definition");
            if text(d, "kind") == "input" {
                b.charge(R::ValueCells, 1)?;
                interfaces.insert(("input", text(d, "port")), text(n, "id"));
            }
        }
        for o in array(get(ir, "outputs")) {
            b.charge(R::ValueCells, 1)?;
            interfaces.insert(("output", text(o, "name")), text(o, "node"));
        }
        let subject = get(definition, "subject");
        let target_path = if matches!(kind, ObligationKind::NumericRange) {
            b.charge(R::ValueCells, array(get(subject, "path")).len())?;
            array(get(subject, "path")).iter().map(string).collect()
        } else {
            Vec::new()
        };
        Ok(Self {
            ir,
            kind,
            node_index: nodes
                .iter()
                .map(|n| (text(n, "id"), get(n, "definition")))
                .collect(),
            nodes,
            records: types
                .record_types()
                .iter()
                .map(|r| (r.id(), r.definition()))
                .collect(),
            enums: types
                .enum_types()
                .iter()
                .map(|e| (e.id(), e.definition()))
                .collect(),
            table_types: types
                .table_types()
                .iter()
                .map(|t| (t.id(), t.definition()))
                .collect(),
            interfaces,
            computed: BTreeMap::new(),
            values: Vec::new(),
            causes: Vec::new(),
            locations: Vec::new(),
            context: Vec::new(),
            target_anchor: text(subject, "id"),
            target_path,
            instances: 0,
            range: None,
        })
    }
    fn type_budget(ty: &ValueType, b: &mut Budget) -> Result<()> {
        b.charge(R::TypeItems, 1)?;
        match ty {
            ValueType::Int { lower, upper } => {
                b.observe(
                    R::IntegerDigits,
                    lower.as_str().trim_start_matches('-').len(),
                )?;
                b.observe(
                    R::IntegerDigits,
                    upper.as_str().trim_start_matches('-').len(),
                )?;
            }
            ValueType::Fixed {
                lower,
                upper,
                scale,
            } => {
                b.observe(
                    R::IntegerDigits,
                    lower.as_str().trim_start_matches('-').len(),
                )?;
                b.observe(
                    R::IntegerDigits,
                    upper.as_str().trim_start_matches('-').len(),
                )?;
                b.observe(R::IntegerDigits, scale.as_str().len())?;
            }
            ValueType::Option { inner } => Self::type_budget(inner, b)?,
            _ => {}
        }
        Ok(())
    }
    pub fn push(&mut self, v: Val<'a>, b: &mut Budget) -> Result<usize> {
        b.charge(R::ValueCells, 1)?;
        let i = self.values.len();
        self.values.push(v);
        Ok(i)
    }
    pub fn cause(&mut self, c: Cause<'a>, b: &mut Budget) -> Result<usize> {
        b.charge(R::ValueCells, 1)?;
        let id = self.causes.len();
        self.causes.push(c);
        Ok(id)
    }
    pub fn location(&mut self, anchor: &'a str, path: &[String], b: &mut Budget) -> Result<usize> {
        let size = super::observe::location_size(self, anchor, path, &self.context);
        b.charge(R::PathBytes, size)?;
        b.charge(R::ValueCells, path.len() + self.context.len())?;
        let path = path.iter().map(|s| b.copy(s)).collect::<Result<Vec<_>>>()?;
        let context = self
            .context
            .iter()
            .map(|c| {
                b.charge(R::ValueCells, c.key.len())?;
                Ok(Context {
                    node: c.node,
                    key: c.key.clone(),
                })
            })
            .collect::<Result<Vec<_>>>()?;
        let id = self.locations.len();
        b.charge(R::ValueCells, 1)?;
        self.locations.push(Location {
            anchor,
            path,
            context,
        });
        Ok(id)
    }
    pub fn node_definition(&self, id: &str) -> &'a Value {
        self.node_index[id]
    }
    pub fn table_type(&self, id: &str) -> &'a TableType {
        self.table_types[text(self.node_definition(id), "table_type")]
    }
    pub fn key(&self, row: usize, table: &TableType, b: &mut Budget) -> Result<Vec<usize>> {
        let Val::Record(ty, fields) = &self.values[row] else {
            return Err(ReplayError::Internal("row record"));
        };
        b.charge(R::ValueCells, table.primary_key.len())?;
        Ok(table
            .primary_key
            .iter()
            .map(|k| {
                fields[self.records[ty]
                    .fields
                    .iter()
                    .position(|f| &f.name == k)
                    .expect("P1 key")]
            })
            .collect())
    }
    pub fn scalar_cmp(&self, a: usize, c: usize, b: &mut Budget) -> Result<Ordering> {
        b.charge(R::Comparisons, 1)?;
        match (&self.values[a], &self.values[c]) {
            (Val::Bool(a), Val::Bool(c)) => Ok(a.cmp(c)),
            (Val::Int(a), Val::Int(c)) | (Val::Fixed(_, a), Val::Fixed(_, c)) => {
                arithmetic::compare(a, c, b)
            }
            (Val::Text(a), Val::Text(c)) => {
                b.charge(
                    R::TextBytes,
                    a.len()
                        .checked_add(c.len())
                        .ok_or_else(|| b.error(R::TextBytes))?,
                )?;
                Ok(a.cmp(c))
            }
            (Val::Enum(a, x), Val::Enum(c, y)) if a == c => Ok(x.cmp(y)),
            _ => Err(ReplayError::Internal("scalar comparison types")),
        }
    }
    pub fn key_cmp(&self, a: &[usize], c: &[usize], b: &mut Budget) -> Result<Ordering> {
        for (&a, &c) in a.iter().zip(c) {
            let order = self.scalar_cmp(a, c, b)?;
            if order != Ordering::Equal {
                return Ok(order);
            }
        }
        Ok(Ordering::Equal)
    }
    pub fn row_cmp(&self, a: usize, c: usize, t: &TableType, b: &mut Budget) -> Result<Ordering> {
        let a = self.key(a, t, b)?;
        let c = self.key(c, t, b)?;
        self.key_cmp(&a, &c, b)
    }
    pub fn sort_rows(&self, rows: &mut [usize], t: &TableType, b: &mut Budget) -> Result<()> {
        // 原地插入排序只移动平坦引用；每次比较 / 移动都可中止。
        for i in 1..rows.len() {
            let row = rows[i];
            let mut j = i;
            while j > 0 {
                b.step()?;
                if self.row_cmp(rows[j - 1], row, t, b)? != Ordering::Greater {
                    break;
                }
                rows[j] = rows[j - 1];
                j -= 1;
            }
            rows[j] = row;
        }
        Ok(())
    }
    fn context_push(&mut self, node: &'a str, row: usize, b: &mut Budget) -> Result<()> {
        let key = self.key(row, self.table_type(node), b)?;
        b.charge(R::ValueCells, 1)?;
        self.context.push(Context { node, key });
        Ok(())
    }
    fn child(
        &mut self,
        e: &'a Value,
        key: &str,
        env: &mut Vec<usize>,
        anchor: &'a str,
        path: &mut Vec<String>,
        b: &mut Budget,
    ) -> Result<Evaluated> {
        path.push(b.copy(key)?);
        let v = self.eval(get(e, key), env, anchor, path, b);
        path.pop();
        v
    }
    fn bool(&self, id: usize) -> bool {
        let Val::Bool(v) = self.values[id] else {
            unreachable!("P1 Bool")
        };
        v
    }
    fn equal(&self, a: usize, c: usize, b: &mut Budget) -> Result<bool> {
        let mut left = a;
        let mut right = c;
        loop {
            b.step()?;
            match (&self.values[left], &self.values[right]) {
                (Val::None, Val::None) => return Ok(true),
                (Val::Some(a), Val::Some(c)) => {
                    left = *a;
                    right = *c;
                }
                (Val::None, Val::Some(_)) | (Val::Some(_), Val::None) => return Ok(false),
                _ => return Ok(self.scalar_cmp(left, right, b)? == Ordering::Equal),
            }
        }
    }
    pub fn eval(
        &mut self,
        e: &'a Value,
        env: &mut Vec<usize>,
        anchor: &'a str,
        path: &mut Vec<String>,
        b: &mut Budget,
    ) -> Result<Evaluated> {
        b.step()?;
        let op = text(e, "op");
        let selected = self.kind == ObligationKind::NumericRange
            && anchor == self.target_anchor
            && path
                .iter()
                .map(String::as_str)
                .eq(self.target_path.iter().copied());
        if selected {
            self.instances = self
                .instances
                .checked_add(1)
                .ok_or_else(|| b.error(R::EvaluationSteps))?;
        }
        let value = match op {
            "literal_bool" => {
                let Value::Bool(v) = get(e, "value") else {
                    unreachable!()
                };
                Val::Bool(*v)
            }
            "literal_int" => Val::Int(arithmetic::parse(text(e, "value"), b)?),
            "literal_fixed" => Val::Fixed(
                text(get(e, "type"), "scale"),
                arithmetic::parse(text(e, "coefficient"), b)?,
            ),
            "literal_text" => Val::Text(b.text_copy(text(e, "value"))?),
            "literal_enum" => {
                let ty = text(e, "enum_type");
                Val::Enum(
                    ty,
                    self.enums[ty]
                        .members
                        .iter()
                        .position(|m| m == text(e, "member"))
                        .expect("P1 enum"),
                )
            }
            "bound" => {
                return Ok(Ok(env[env.len()
                    - 1
                    - text(e, "index").parse::<usize>().expect("P1 index")]));
            }
            "field" => {
                let value = self.child(e, "record", env, anchor, path, b)?;
                let Ok(id) = value else {
                    return Ok(value);
                };
                let Val::Record(ty, fields) = &self.values[id] else {
                    unreachable!()
                };
                return Ok(Ok(fields[self.records[ty]
                    .fields
                    .iter()
                    .position(|f| f.name == text(e, "field"))
                    .expect("P1 field")]));
            }
            "none" => Val::None,
            "some" => {
                let v = self.child(e, "value", env, anchor, path, b)?;
                let Ok(id) = v else {
                    return Ok(v);
                };
                Val::Some(id)
            }
            "record" => {
                let mut values = Vec::new();
                let mut fault = None;
                path.push(b.copy("fields")?);
                for (i, f) in array(get(e, "fields")).iter().enumerate() {
                    path.push(b.copy(&i.to_string())?);
                    let v = self.child(f, "expression", env, anchor, path, b)?;
                    path.pop();
                    b.charge(R::ValueCells, 1)?;
                    match v {
                        Ok(id) => values.push(id),
                        Err(c) => {
                            fault.get_or_insert(c);
                        }
                    }
                }
                path.pop();
                if let Some(c) = fault {
                    return Ok(Err(c));
                }
                Val::Record(text(e, "record_type"), values)
            }
            "if" => {
                let c = self.child(e, "condition", env, anchor, path, b)?;
                let Ok(id) = c else {
                    return Ok(c);
                };
                return self.child(
                    e,
                    if self.bool(id) { "then" } else { "else" },
                    env,
                    anchor,
                    path,
                    b,
                );
            }
            "match_option" => {
                let v = self.child(e, "subject", env, anchor, path, b)?;
                let Ok(id) = v else {
                    return Ok(v);
                };
                match self.values[id] {
                    Val::None => return self.child(e, "none", env, anchor, path, b),
                    Val::Some(child) => {
                        b.charge(R::ValueCells, 1)?;
                        env.push(child);
                        let result = self.child(e, "some", env, anchor, path, b);
                        env.pop();
                        return result;
                    }
                    _ => unreachable!(),
                }
            }
            "not" => {
                let v = self.child(e, "value", env, anchor, path, b)?;
                let Ok(id) = v else {
                    return Ok(v);
                };
                Val::Bool(!self.bool(id))
            }
            "and" | "or" => {
                let mut answer = op == "and";
                let mut fault = None;
                path.push(b.copy("values")?);
                for (i, v) in array(get(e, "values")).iter().enumerate() {
                    path.push(b.copy(&i.to_string())?);
                    let r = self.eval(v, env, anchor, path, b)?;
                    path.pop();
                    match r {
                        Err(c) => {
                            fault.get_or_insert(c);
                        }
                        Ok(id) => {
                            if op == "and" {
                                answer &= self.bool(id)
                            } else {
                                answer |= self.bool(id)
                            }
                        }
                    }
                }
                path.pop();
                if let Some(c) = fault {
                    return Ok(Err(c));
                }
                Val::Bool(answer)
            }
            "eq" | "lt" | "le" | "gt" | "ge" => {
                let a = self.child(e, "left", env, anchor, path, b)?;
                let c = self.child(e, "right", env, anchor, path, b)?;
                let (Ok(a), Ok(c)) = (a, c) else {
                    return Ok(Err(a.err().or(c.err()).expect("fault")));
                };
                let v = if op == "eq" {
                    self.equal(a, c, b)?
                } else {
                    let order = self.scalar_cmp(a, c, b)?;
                    match op {
                        "lt" => order == Ordering::Less,
                        "le" => order != Ordering::Greater,
                        "gt" => order == Ordering::Greater,
                        _ => order != Ordering::Less,
                    }
                };
                Val::Bool(v)
            }
            "int_add" | "int_sub" | "fixed_add" | "fixed_sub" => {
                let add = op.ends_with("_add");
                let (a, c) = if add {
                    path.push(b.copy("values")?);
                    path.push(b.copy("0")?);
                    let args = array(get(e, "values"));
                    let a = self.eval(&args[0], env, anchor, path, b)?;
                    *path.last_mut().expect("index") = b.copy("1")?;
                    let c = self.eval(&args[1], env, anchor, path, b)?;
                    path.pop();
                    path.pop();
                    (a, c)
                } else {
                    (
                        self.child(e, "left", env, anchor, path, b)?,
                        self.child(e, "right", env, anchor, path, b)?,
                    )
                };
                let (Ok(a), Ok(c)) = (a, c) else {
                    return Ok(Err(a.err().or(c.err()).expect("operand fault")));
                };
                let number = |id| match &self.values[id] {
                    Val::Int(n) | Val::Fixed(_, n) => n,
                    _ => unreachable!(),
                };
                let n = arithmetic::calculate(number(a), number(c), !add, b)?;
                let ty = get(e, "result_type");
                let lower = arithmetic::parse(text(ty, "lower"), b)?;
                let upper = arithmetic::parse(text(ty, "upper"), b)?;
                let within = arithmetic::compare(&n, &lower, b)? != Ordering::Less
                    && arithmetic::compare(&n, &upper, b)? != Ordering::Greater;
                let value = if op.starts_with("fixed") {
                    Val::Fixed(text(ty, "scale"), n)
                } else {
                    Val::Int(n)
                };
                let id = self.push(value, b)?;
                if !within {
                    let location = self.location(anchor, path, b)?;
                    let cause = self.cause(Cause::Range(location), b)?;
                    if selected && self.range.is_none() {
                        self.range = Some(Range {
                            location,
                            operands: [a, c],
                            value: id,
                            ty,
                        });
                    }
                    return Ok(Err(cause));
                }
                return Ok(Ok(id));
            }
            "forall_rows" | "lookup" => {
                let reference = get(e, "table");
                let node = self.interfaces[&(text(reference, "kind"), text(reference, "name"))];
                let t = &self.computed[node];
                if !t.ok {
                    return Ok(Err(t.cause.expect("table fault")));
                }
                let rows = Arc::clone(&t.rows);
                b.charge(R::ValueCells, 1)?;
                if op == "forall_rows" {
                    let mut answer = true;
                    let mut fault = None;
                    path.push(b.copy("body")?);
                    for &row in rows.iter() {
                        self.context_push(node, row, b)?;
                        b.charge(R::ValueCells, 1)?;
                        env.push(row);
                        let v = self.eval(get(e, "body"), env, anchor, path, b)?;
                        env.pop();
                        self.context.pop();
                        match v {
                            Ok(id) => answer &= self.bool(id),
                            Err(c) => {
                                fault.get_or_insert(c);
                            }
                        }
                    }
                    path.pop();
                    if let Some(c) = fault {
                        return Ok(Err(c));
                    }
                    Val::Bool(answer)
                } else {
                    let mut keys = Vec::new();
                    let mut fault = None;
                    path.push(b.copy("keys")?);
                    for (i, v) in array(get(e, "keys")).iter().enumerate() {
                        path.push(b.copy(&i.to_string())?);
                        let result = self.eval(v, env, anchor, path, b)?;
                        path.pop();
                        b.charge(R::ValueCells, 1)?;
                        match result {
                            Ok(id) => keys.push(id),
                            Err(c) => {
                                fault.get_or_insert(c);
                            }
                        }
                    }
                    path.pop();
                    if let Some(c) = fault {
                        return Ok(Err(c));
                    }
                    let mut found = None;
                    for &row in rows.iter() {
                        b.step()?;
                        let key = self.key(row, self.table_type(node), b)?;
                        if self.key_cmp(&keys, &key, b)? == Ordering::Equal
                            && found.replace(row).is_some()
                        {
                            return Err(ReplayError::Internal(
                                "successful table has duplicate key",
                            ));
                        }
                    }
                    match found {
                        Some(row) => Val::Some(row),
                        None => Val::None,
                    }
                }
            }
            _ => return Err(ReplayError::Internal("scanned P1 op")),
        };
        Ok(Ok(self.push(value, b)?))
    }
    fn node(&mut self, entry: &'a Value, b: &mut Budget) -> Result<()> {
        b.step()?;
        let id = text(entry, "id");
        let def = get(entry, "definition");
        if text(def, "kind") == "input" {
            return Ok(());
        }
        let source = text(def, "source");
        let upstream = &self.computed[source];
        if !upstream.ok {
            let c = upstream.cause.expect("source fault");
            let cause = self.cause(
                Cause::Dependency {
                    node: id,
                    source,
                    cause: c,
                },
                b,
            )?;
            b.charge(R::ValueCells, 1)?;
            self.computed.insert(
                id,
                Table {
                    ready: false,
                    ok: false,
                    rows: Arc::new(Vec::new()),
                    selected: Arc::new(Vec::new()),
                    cause: Some(cause),
                },
            );
            return Ok(());
        }
        let source_rows = Arc::clone(&upstream.rows);
        b.charge(R::ValueCells, 1)?;
        let mut rows = Vec::new();
        let mut fault = None;
        for &row in source_rows.iter() {
            self.context_push(source, row, b)?;
            let mut env = vec![row];
            b.charge(R::ValueCells, 1)?;
            if text(def, "kind") == "filter" {
                let mut path = vec![b.copy("predicate")?];
                match self.eval(get(def, "predicate"), &mut env, id, &mut path, b)? {
                    Ok(v) => {
                        if self.bool(v) {
                            b.charge(R::Rows, 1)?;
                            rows.push(row);
                        }
                    }
                    Err(c) => {
                        fault.get_or_insert(c);
                    }
                }
            } else {
                let mut fields = Vec::new();
                let mut row_fault = None;
                let mut path = vec![b.copy("fields")?];
                for (i, f) in array(get(def, "fields")).iter().enumerate() {
                    path.push(b.copy(&i.to_string())?);
                    let v = self.child(f, "expression", &mut env, id, &mut path, b)?;
                    path.pop();
                    b.charge(R::ValueCells, 1)?;
                    match v {
                        Ok(v) => fields.push(v),
                        Err(c) => {
                            row_fault.get_or_insert(c);
                        }
                    }
                }
                if let Some(c) = row_fault {
                    fault.get_or_insert(c);
                } else {
                    let ty = self.table_type(id).record_type.as_str();
                    let v = self.push(Val::Record(ty, fields), b)?;
                    b.charge(R::Rows, 1)?;
                    rows.push(v);
                }
            }
            self.context.pop();
        }
        let ready = fault.is_none();
        if !ready {
            rows.clear();
        } else {
            self.sort_rows(&mut rows, self.table_type(id), b)?;
        }
        let capacity = self.table_type(id).capacity.as_str();
        let count = arithmetic::parse(&rows.len().to_string(), b)?;
        let cap_ok =
            arithmetic::compare(&count, &self.table_type(id).capacity, b)? != Ordering::Greater;
        let cause = if let Some(c) = fault {
            Some(c)
        } else if !cap_ok {
            Some(self.cause(
                Cause::Capacity {
                    node: id,
                    actual: rows.len(),
                    capacity,
                },
                b,
            )?)
        } else {
            None
        };
        b.charge(R::ValueCells, 3)?;
        let rows = Arc::new(rows);
        let selected = if text(def, "kind") == "filter" {
            Arc::clone(&rows)
        } else {
            source_rows
        };
        self.computed.insert(
            id,
            Table {
                ready,
                ok: ready && cap_ok,
                rows,
                selected,
                cause,
            },
        );
        Ok(())
    }
    pub fn run(
        &mut self,
        world: &super::flat::Json,
        root: usize,
        b: &mut Budget,
    ) -> Result<(Observation<'a>, ReplayOutcome)> {
        if let Some(rejected) = self.read_inputs(world, root, b)? {
            return Ok((rejected, ReplayOutcome::InputRejected));
        }
        b.stage = ReplayStage::Pre;
        let mut first = None;
        for c in array(get(self.ir, "contracts")) {
            b.step()?;
            let def = get(c, "definition");
            if text(def, "kind") != "formula" || text(def, "role") != "assume" {
                continue;
            }
            let anchor = text(c, "id");
            let mut path = vec![b.copy("expression")?];
            let result = self.eval(
                get(def, "expression"),
                &mut Vec::new(),
                anchor,
                &mut path,
                b,
            )?;
            if first.is_none() {
                match result {
                    Ok(v) if self.bool(v) => {}
                    Ok(_) => {
                        let location = self.location(anchor, &path, b)?;
                        first = Some(Observation::Pre {
                            contract: anchor,
                            reason: "false",
                            location,
                        });
                    }
                    Err(c) => {
                        let location = self.root_location(c);
                        first = Some(Observation::Pre {
                            contract: anchor,
                            reason: "fault",
                            location,
                        });
                    }
                }
            }
        }
        if let Some(result) = first {
            return Ok((result, ReplayOutcome::PreRejected));
        }
        // Pre 求值可能到达 assume 中的目标位置；Pre 成立后才有有效目标域。
        b.stage = ReplayStage::Evaluation;
        for i in 0..self.nodes.len() {
            self.node(self.nodes[i], b)?;
        }
        self.target(b)
    }
    pub fn root_location(&self, mut cause: usize) -> usize {
        loop {
            match self.causes[cause] {
                Cause::Range(id) => return id,
                Cause::Dependency { cause: c, .. } => cause = c,
                Cause::Capacity { .. } => unreachable!("input-only formula cannot capacity fault"),
            }
        }
    }
}
