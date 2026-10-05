//! 只对已完成 RowTypeChecker 逐行或契约检查的表达式执行规范重写。
//! 不接收外部树；JSON 已有界且所有闭合成员 / 操作数均已检查。

use crate::declarations::{self as decode, Members};
use crate::json::{self, Value};

pub(crate) fn normalize_checked(value: &mut Value) {
    match value {
        Value::Array(values) => {
            for value in values {
                normalize_checked(value);
            }
        }
        Value::Object(members) => {
            for (_, value, _) in members.iter_mut() {
                normalize_checked(value);
            }
            normalize_operator(value);
        }
        Value::String(_) | Value::Bool(_) => {}
    }
}

fn normalize_operator(value: &mut Value) {
    let Value::Object(members) = value else {
        unreachable!()
    };
    let Some((_, Value::String(op), _)) = members.iter().find(|(key, _, _)| key == "op") else {
        // 类型注解也随树遍历，但没有 op，保持其已检查的内容。
        return;
    };
    match op.as_str() {
        "and" | "or" => normalize_boolean(value),
        "eq" => {
            let left = position(members, "left");
            let right = position(members, "right");
            if encoded(&members[left].1) > encoded(&members[right].1) {
                // 解析器已按 JCS 对象键排序，left 在 right 前。
                let (before, after) = members.split_at_mut(right);
                std::mem::swap(&mut before[left].1, &mut after[0].1);
            }
        }
        "int_add" | "fixed_add" => {
            let index = position(members, "values");
            let Value::Array(values) = &mut members[index].1 else {
                unreachable!()
            };
            values.sort_by_cached_key(encoded);
        }
        "record" => {
            let index = position(members, "fields");
            let Value::Array(fields) = &mut members[index].1 else {
                unreachable!("checked record fields")
            };
            fields.sort_by(|left, right| field_name(left).cmp(field_name(right)));
        }
        _ => {}
    }
}

fn field_name(value: &Value) -> &str {
    let Value::Object(members) = value else {
        unreachable!("checked record field")
    };
    decode::string(decode::member(members, "name"), "").expect("checked field name")
}

fn normalize_boolean(value: &mut Value) {
    let Value::Object(members) = value else {
        unreachable!()
    };
    let Value::String(op) = decode::member(members, "op") else {
        unreachable!()
    };
    let op = op.clone();
    let index = position(members, "values");
    let Value::Array(values) = &mut members[index].1 else {
        unreachable!()
    };
    let mut flattened = Vec::new();
    for value in std::mem::take(values) {
        if let Value::Object(mut child) = value {
            if matches!(decode::member(&child, "op"), Value::String(child_op) if child_op == &op) {
                let index = position(&child, "values");
                let (_, Value::Array(children), _) = child.swap_remove(index) else {
                    unreachable!()
                };
                // 子式已递归展平；只移动其子项，不复制表达式或引入新节点。
                flattened.extend(children);
            } else {
                flattened.push(Value::Object(child));
            }
        } else {
            unreachable!("checked boolean operands are expression objects");
        }
    }
    let mut keyed: Vec<_> = flattened
        .into_iter()
        .map(|value| (encoded(&value), value))
        .collect();
    keyed.sort_by(|left, right| left.0.cmp(&right.0));
    keyed.dedup_by(|left, right| left.0 == right.0);
    *values = keyed.into_iter().map(|(_, value)| value).collect();
    if values.len() == 1 {
        *value = values.pop().expect("one operand");
    }
}

fn position(members: &Members, key: &str) -> usize {
    members
        .iter()
        .position(|(name, _, _)| name == key)
        .expect("checked member")
}

fn encoded(value: &Value) -> Vec<u8> {
    let mut result = Vec::new();
    json::encode(value, &mut result);
    result
}
