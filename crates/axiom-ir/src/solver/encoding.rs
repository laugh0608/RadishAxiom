//! 复用 JSON 字符串转义，显式栈先计数后分配。对象键按 JCS UTF-16 顺序。
use super::{Budget, Result, SolverResource};
use crate::json::{Value, emit_string};

pub(super) fn s(v: impl Into<String>) -> Value {
    Value::String(v.into())
}
pub(super) fn obj(fields: Vec<(&str, Value)>) -> Value {
    let mut members: Vec<_> = fields
        .into_iter()
        .map(|(k, v)| (k.to_owned(), v, 0))
        .collect();
    members.sort_by(|(a, _, _), (b, _, _)| a.encode_utf16().cmp(b.encode_utf16()));
    Value::Object(members)
}
pub(super) fn strings<'a>(v: impl IntoIterator<Item = &'a str>) -> Value {
    Value::Array(v.into_iter().map(s).collect())
}
pub(super) fn emit(v: &Value, out: &mut impl FnMut(&[u8])) {
    enum Task<'a> {
        Value(&'a Value),
        String(&'a str),
        Raw(&'static [u8]),
    }
    let mut stack = vec![Task::Value(v)];
    while let Some(t) = stack.pop() {
        match t {
            Task::Raw(b) => out(b),
            Task::String(s) => emit_string(s, out),
            Task::Value(v) => match v {
                Value::String(s) => emit_string(s, out),
                Value::Bool(v) => out(if *v { b"true" } else { b"false" }),
                Value::Array(values) => {
                    out(b"[");
                    stack.push(Task::Raw(b"]"));
                    for (i, v) in values.iter().enumerate().rev() {
                        stack.push(Task::Value(v));
                        if i > 0 {
                            stack.push(Task::Raw(b","));
                        }
                    }
                }
                Value::Object(fields) => {
                    out(b"{");
                    stack.push(Task::Raw(b"}"));
                    for (i, (k, v, _)) in fields.iter().enumerate().rev() {
                        stack.push(Task::Value(v));
                        stack.push(Task::Raw(b":"));
                        stack.push(Task::String(k));
                        if i > 0 {
                            stack.push(Task::Raw(b","));
                        }
                    }
                }
            },
        }
    }
}
pub(super) fn output(
    budget: &mut Budget,
    resource: SolverResource,
    emit: impl Fn(&mut dyn FnMut(&[u8])),
) -> Result<Vec<u8>> {
    let mut count = Some(0usize);
    emit(&mut |bytes| count = count.and_then(|n| n.checked_add(bytes.len())));
    let count = count.ok_or_else(|| budget.error(resource))?;
    budget.charge(resource, count)?;
    let mut bytes = Vec::with_capacity(count);
    emit(&mut |b| bytes.extend_from_slice(b));
    Ok(bytes)
}
pub(super) fn canonical(v: &Value, r: SolverResource, b: &mut Budget) -> Result<Vec<u8>> {
    output(b, r, |out| emit(v, &mut |v| out(v)))
}
