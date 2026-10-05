use super::{
    QueryError, QueryResource, Result, array,
    encode::{Encoder, Evaluated},
    get,
    layout::{Data, LayoutId},
    smt::{Op, Sort, Term},
    text,
};
use crate::{declarations, json::Value};

impl Encoder<'_> {
    fn scalar_value(&mut self, sort: Sort, value: Term, ok: Term) -> Result<Evaluated> {
        let layout = self.layouts.atom(sort, &mut self.arena.budget)?;
        self.arena.budget.charge(QueryResource::ValueCells, 1)?;
        Ok(Evaluated {
            data: self.layouts.make(layout, vec![value]),
            ok,
        })
    }
    fn explicit_layout(&mut self, value: &Value) -> Result<LayoutId> {
        let ty = declarations::value_type(value, "")
            .map_err(|_| QueryError::Internal("P1 expression type"))?;
        self.layouts.value_type(&ty, &mut self.arena.budget)
    }
    fn child(
        &mut self,
        value: &Value,
        key: &str,
        env: &mut Vec<Data>,
        reach: Term,
        anchor: &str,
        path: &mut Vec<String>,
    ) -> Result<Evaluated> {
        path.push(key.to_owned());
        let result = self.eval(get(value, key), env, reach, anchor, path);
        path.pop();
        result
    }
    pub fn eval(
        &mut self,
        expression: &Value,
        env: &mut Vec<Data>,
        reach: Term,
        anchor: &str,
        path: &mut Vec<String>,
    ) -> Result<Evaluated> {
        let yes = self.arena.boolean(true);
        match text(expression, "op") {
            "literal_bool" => {
                let Value::Bool(b) = get(expression, "value") else {
                    unreachable!("typed bool")
                };
                self.scalar_value(Sort::Bool, self.arena.boolean(*b), yes)
            }
            "literal_int" | "literal_fixed" => {
                let key = if text(expression, "op") == "literal_int" {
                    "value"
                } else {
                    "coefficient"
                };
                let value = self.arena.integer(text(expression, key))?;
                self.scalar_value(Sort::Int, value, yes)
            }
            "literal_text" => {
                self.scalar_value(Sort::Text, self.literals[text(expression, "value")], yes)
            }
            "literal_enum" => {
                let index = self.enums[text(expression, "enum_type")]
                    .members
                    .iter()
                    .position(|m| m == text(expression, "member"))
                    .expect("typed enum");
                let value = self.arena.integer(&index.to_string())?;
                self.scalar_value(Sort::Int, value, yes)
            }
            "bound" => {
                let index: usize = text(expression, "index").parse().expect("P1 bounded index");
                Ok(Evaluated {
                    data: env[env.len() - 1 - index].clone(),
                    ok: yes,
                })
            }
            "field" => {
                let parent = self.child(expression, "record", env, reach, anchor, path)?;
                Ok(Evaluated {
                    data: self.layouts.field(&parent.data, text(expression, "field")),
                    ok: parent.ok,
                })
            }
            "none" => {
                let layout = self.explicit_layout(get(expression, "type"))?;
                let data =
                    self.layouts
                        .default_value(layout, self.literals[""], &mut self.arena)?;
                Ok(Evaluated { data, ok: yes })
            }
            "some" => {
                let value = self.child(expression, "value", env, reach, anchor, path)?;
                let layout = self
                    .layouts
                    .option(value.data.layout, &mut self.arena.budget)?;
                self.arena
                    .budget
                    .charge(QueryResource::ValueCells, self.layouts.entries[layout].len)?;
                let mut lanes = Vec::with_capacity(self.layouts.entries[layout].len);
                lanes.push(yes);
                lanes.extend_from_slice(self.layouts.slice(&value.data));
                Ok(Evaluated {
                    data: self.layouts.make(layout, lanes),
                    ok: value.ok,
                })
            }
            "record" => {
                let layout = self.layouts.records[text(expression, "record_type")];
                let len = self.layouts.entries[layout].len;
                self.arena.budget.charge(QueryResource::ValueCells, len)?;
                let mut lanes = Vec::with_capacity(len);
                let mut oks = Vec::new();
                path.push("fields".to_owned());
                for (i, field) in array(get(expression, "fields")).iter().enumerate() {
                    path.push(i.to_string());
                    let value = self.child(field, "expression", env, reach, anchor, path)?;
                    path.pop();
                    lanes.extend_from_slice(self.layouts.slice(&value.data));
                    oks.push(value.ok);
                }
                path.pop();
                let ok = self.arena.and(&oks)?;
                Ok(Evaluated {
                    data: self.layouts.make(layout, lanes),
                    ok,
                })
            }
            "if" => {
                let condition = self.child(expression, "condition", env, reach, anchor, path)?;
                let taken = self.arena.and(&[reach, condition.ok, condition.scalar()])?;
                let not = self.arena.not(condition.scalar())?;
                let untaken = self.arena.and(&[reach, condition.ok, not])?;
                let left = self.child(expression, "then", env, taken, anchor, path)?;
                let right = self.child(expression, "else", env, untaken, anchor, path)?;
                let branch_ok = self.arena.ite(condition.scalar(), left.ok, right.ok)?;
                let ok = self.arena.and(&[condition.ok, branch_ok])?;
                let data = self.layouts.ite(
                    condition.scalar(),
                    &left.data,
                    &right.data,
                    &mut self.arena,
                )?;
                Ok(Evaluated { data, ok })
            }
            "match_option" => {
                let subject = self.child(expression, "subject", env, reach, anchor, path)?;
                let tag = subject.scalar();
                let not = self.arena.not(tag)?;
                let none_reach = self.arena.and(&[reach, subject.ok, not])?;
                let some_reach = self.arena.and(&[reach, subject.ok, tag])?;
                let none = self.child(expression, "none", env, none_reach, anchor, path)?;
                env.push(self.layouts.inner(&subject.data));
                let some = self.child(expression, "some", env, some_reach, anchor, path)?;
                env.pop();
                let branch_ok = self.arena.ite(tag, some.ok, none.ok)?;
                let ok = self.arena.and(&[subject.ok, branch_ok])?;
                let data = self
                    .layouts
                    .ite(tag, &some.data, &none.data, &mut self.arena)?;
                Ok(Evaluated { data, ok })
            }
            "not" => {
                let value = self.child(expression, "value", env, reach, anchor, path)?;
                let result = self.arena.not(value.scalar())?;
                self.scalar_value(Sort::Bool, result, value.ok)
            }
            "and" | "or" => {
                let mut values = Vec::new();
                let mut oks = Vec::new();
                path.push("values".to_owned());
                for (i, child) in array(get(expression, "values")).iter().enumerate() {
                    path.push(i.to_string());
                    let value = self.eval(child, env, reach, anchor, path)?;
                    path.pop();
                    values.push(value.scalar());
                    oks.push(value.ok);
                }
                path.pop();
                let op = if text(expression, "op") == "and" {
                    Op::And
                } else {
                    Op::Or
                };
                let value = self.arena.app(op, &values)?;
                let ok = self.arena.and(&oks)?;
                self.scalar_value(Sort::Bool, value, ok)
            }
            "eq" | "lt" | "le" | "gt" | "ge" => {
                let left = self.child(expression, "left", env, reach, anchor, path)?;
                let right = self.child(expression, "right", env, reach, anchor, path)?;
                let value = match text(expression, "op") {
                    "eq" => self
                        .layouts
                        .equal(&left.data, &right.data, &mut self.arena)?,
                    op => self.arena.app(
                        match op {
                            "lt" => Op::Lt,
                            "le" => Op::Le,
                            "gt" => Op::Gt,
                            _ => Op::Ge,
                        },
                        &[left.scalar(), right.scalar()],
                    )?,
                };
                let ok = self.arena.and(&[left.ok, right.ok])?;
                self.scalar_value(Sort::Bool, value, ok)
            }
            "int_add" | "int_sub" | "fixed_add" | "fixed_sub" => {
                let add = text(expression, "op").ends_with("_add");
                let (left, right) = if add {
                    path.push("values".to_owned());
                    path.push("0".to_owned());
                    let values = array(get(expression, "values"));
                    let a = self.eval(&values[0], env, reach, anchor, path)?;
                    *path.last_mut().expect("value index") = "1".to_owned();
                    let b = self.eval(&values[1], env, reach, anchor, path)?;
                    path.pop();
                    path.pop();
                    (a, b)
                } else {
                    (
                        self.child(expression, "left", env, reach, anchor, path)?,
                        self.child(expression, "right", env, reach, anchor, path)?,
                    )
                };
                let value = self.arena.app(
                    if add { Op::Add } else { Op::Sub },
                    &[left.scalar(), right.scalar()],
                )?;
                let layout = self.explicit_layout(get(expression, "result_type"))?;
                self.arena.budget.charge(QueryResource::ValueCells, 1)?;
                let data = self.layouts.make(layout, vec![value]);
                let within = self.layouts.wf(&data, &mut self.arena)?;
                let operands_ok = self.arena.and(&[left.ok, right.ok])?;
                if anchor == self.target_anchor
                    && path
                        .iter()
                        .map(String::as_str)
                        .eq(self.target_path.iter().copied())
                {
                    let outside = self.arena.not(within)?;
                    self.violations
                        .push(self.arena.and(&[reach, operands_ok, outside])?);
                }
                let ok = self.arena.and(&[operands_ok, within])?;
                Ok(Evaluated { data, ok })
            }
            "forall_rows" => {
                let table = self.tables[self.plan.interface(get(expression, "table"))].clone();
                let mut values = Vec::new();
                let mut oks = vec![table.ok];
                path.push("body".to_owned());
                for slot in &table.slots {
                    let body_reach = self.arena.and(&[reach, table.ok, slot.active])?;
                    env.push(slot.data.clone());
                    let body = self.eval(get(expression, "body"), env, body_reach, anchor, path)?;
                    env.pop();
                    values.push(self.arena.implies(slot.active, body.scalar())?);
                    oks.push(self.arena.implies(slot.active, body.ok)?);
                }
                path.pop();
                let value = self.arena.and(&values)?;
                let ok = self.arena.and(&oks)?;
                self.scalar_value(Sort::Bool, value, ok)
            }
            "lookup" => self.lookup(expression, env, reach, anchor, path),
            _ => Err(QueryError::Internal("P3 feature scan missed operator")),
        }
    }
    fn lookup(
        &mut self,
        expression: &Value,
        env: &mut Vec<Data>,
        reach: Term,
        anchor: &str,
        path: &mut Vec<String>,
    ) -> Result<Evaluated> {
        let table = self.tables[self.plan.interface(get(expression, "table"))].clone();
        let key_reach = self.arena.and(&[reach, table.ok])?;
        let mut keys = Vec::new();
        let mut oks = vec![table.ok];
        path.push("keys".to_owned());
        for (i, key) in array(get(expression, "keys")).iter().enumerate() {
            path.push(i.to_string());
            let key = self.eval(key, env, key_reach, anchor, path)?;
            path.pop();
            oks.push(key.ok);
            keys.push(key.data);
        }
        path.pop();
        let mut payload =
            self.layouts
                .default_value(table.layout, self.literals[""], &mut self.arena)?;
        let mut matches = Vec::new();
        for slot in &table.slots {
            let mut condition = vec![slot.active];
            for (name, key) in table.keys.iter().zip(&keys) {
                condition.push(self.layouts.equal(
                    &self.layouts.field(&slot.data, name),
                    key,
                    &mut self.arena,
                )?);
            }
            let matched = self.arena.and(&condition)?;
            matches.push(matched);
            payload = self
                .layouts
                .ite(matched, &slot.data, &payload, &mut self.arena)?;
        }
        let layout = self.layouts.option(table.layout, &mut self.arena.budget)?;
        self.arena
            .budget
            .charge(QueryResource::ValueCells, self.layouts.entries[layout].len)?;
        let mut lanes = Vec::with_capacity(self.layouts.entries[layout].len);
        lanes.push(self.arena.or(&matches)?);
        lanes.extend_from_slice(self.layouts.slice(&payload));
        let ok = self.arena.and(&oks)?;
        Ok(Evaluated {
            data: self.layouts.make(layout, lanes),
            ok,
        })
    }
}
