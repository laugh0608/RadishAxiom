//! 节点局部类型和明确的表形状规则；不求值、不产生或证明范围 / 信息流义务。

use std::collections::{BTreeMap, BTreeSet};

use super::{NodeError, NodeErrorKind as Kind, NodeKind, ParsedNode, error, tagged_kind};
use crate::declarations::{self as decode, Field, Label, RecordType, TableType, ValueType};
use crate::expressions::{RowScope, RowTypeChecker};
use crate::json::Value;
use crate::normalization::NormalizedTypeDeclarations;

pub(super) fn check_node(
    nodes: &[ParsedNode<'_>],
    index: usize,
    types: &NormalizedTypeDeclarations,
    checker: &RowTypeChecker<'_>,
) -> Result<(), NodeError> {
    let node = &nodes[index];
    let output = node.table;
    if node.analysis.kind == NodeKind::Input {
        return Ok(());
    }
    let source = nodes[node.analysis.predecessors[0]].table;
    let type_path = decode::child(&node.path, "table_type");
    let same_capacity = matches!(node.analysis.kind, NodeKind::Map | NodeKind::LookupJoin);
    if (same_capacity && output.capacity != source.capacity)
        || (!same_capacity && output.capacity > source.capacity)
    {
        return Err(error(Kind::CapacityMismatch, &type_path));
    }
    let scope = RowScope::Single {
        record_type: &source.record_type,
    };
    match node.analysis.kind {
        NodeKind::Input => unreachable!(),
        NodeKind::Filter => {
            if output.record_type != source.record_type || output.primary_key != source.primary_key
            {
                return Err(error(Kind::FilterShapeMismatch, &type_path));
            }
            let path = decode::child(&node.path, "predicate");
            let actual =
                checker.infer_parsed(decode::member(node.definition, "predicate"), &path, scope)?;
            same_type(&actual, &ValueType::Bool, &path)
        }
        NodeKind::Map => check_fields(node, source, types, checker, scope),
        NodeKind::LookupJoin => {
            let right = nodes[node.analysis.predecessors[1]].table;
            check_pairs(
                node,
                record(types, &source.record_type),
                record(types, &right.record_type),
            )?;
            check_fields(
                node,
                source,
                types,
                checker,
                RowScope::Join {
                    left_record_type: &source.record_type,
                    right_record_type: &right.record_type,
                },
            )
        }
        NodeKind::Group => check_group(node, source, types),
    }
}

fn record<'a>(types: &'a NormalizedTypeDeclarations, id: &str) -> &'a RecordType {
    let index = types
        .record_types()
        .binary_search_by(|entry| entry.id().cmp(id))
        .expect("normalized table record reference");
    types.record_types()[index].definition()
}

fn field<'a>(record: &'a RecordType, name: &str, path: &str) -> Result<&'a Field, NodeError> {
    let index = record
        .fields
        .binary_search_by(|field| field.name.as_str().cmp(name))
        .map_err(|_| error(Kind::UnknownField, path))?;
    Ok(&record.fields[index])
}

fn same_type(actual: &ValueType, expected: &ValueType, path: &str) -> Result<(), NodeError> {
    if actual == expected {
        Ok(())
    } else {
        Err(error(Kind::TypeMismatch, path))
    }
}

fn check_fields(
    node: &ParsedNode<'_>,
    source: &TableType,
    types: &NormalizedTypeDeclarations,
    checker: &RowTypeChecker<'_>,
    scope: RowScope<'_>,
) -> Result<(), NodeError> {
    let output = record(types, &node.table.record_type);
    let path = decode::child(&node.path, "fields");
    let mut fields = BTreeMap::new();
    for (index, value) in decode::array(decode::member(node.definition, "fields"), &path)?
        .iter()
        .enumerate()
    {
        let path = format!("{path}/{index}");
        let members = decode::object(value, &path, &["expression", "name"])?;
        let name_path = decode::child(&path, "name");
        let name = decode::name(decode::member(members, "name"), &name_path)?;
        let expected = field(output, &name, &name_path)?;
        let expression_path = decode::child(&path, "expression");
        let expression = decode::member(members, "expression");
        if fields
            .insert(name, (expression, expression_path.clone()))
            .is_some()
        {
            return Err(error(Kind::DuplicateName, &name_path));
        }
        let actual = checker.infer_parsed(expression, &expression_path, scope)?;
        same_type(&actual, &expected.value_type, &expression_path)?;
    }
    if fields.len() != output.fields.len() {
        return Err(error(Kind::IncompleteFields, &path));
    }
    // 逐值保持需要一个源键到输出键的双射；不通过求值或重写猜测复杂表达式。
    let source_keys: BTreeSet<_> = source.primary_key.iter().map(String::as_str).collect();
    let mut retained = BTreeSet::new();
    for key in &node.table.primary_key {
        let (expression, expression_path) = &fields[key];
        let Some((slot, source_field)) = direct_field(expression) else {
            return Err(NodeError::UnsupportedKeyExpression {
                path: expression_path.clone(),
            });
        };
        if slot != "0" || !source_keys.contains(source_field) || !retained.insert(source_field) {
            return Err(error(Kind::InvalidKeyProjection, expression_path));
        }
    }
    if retained.len() != source.primary_key.len() {
        return Err(error(Kind::InvalidKeyProjection, &path));
    }
    Ok(())
}

/// 表达式已经完整检查；此处只识别一种现有表达式形状，不另写类型推导器。
fn direct_field(value: &Value) -> Option<(&str, &str)> {
    let Value::Object(members) = value else {
        return None;
    };
    if !matches!(decode::member(members, "op"), Value::String(op) if op == "field") {
        return None;
    }
    let Value::String(field) = decode::member(members, "field") else {
        return None;
    };
    let Value::Object(record) = decode::member(members, "record") else {
        return None;
    };
    if !matches!(decode::member(record, "op"), Value::String(op) if op == "bound") {
        return None;
    }
    let Value::String(index) = decode::member(record, "index") else {
        return None;
    };
    Some((index, field))
}

fn check_pairs(
    node: &ParsedNode<'_>,
    left: &RecordType,
    right: &RecordType,
) -> Result<(), NodeError> {
    let path = decode::child(&node.path, "pairs");
    let pairs = decode::array(decode::member(node.definition, "pairs"), &path)?;
    if pairs.is_empty() {
        return Err(error(Kind::EmptyPairs, &path));
    }
    let mut seen = BTreeSet::new();
    for (index, value) in pairs.iter().enumerate() {
        let path = format!("{path}/{index}");
        let members = decode::object(value, &path, &["left", "right"])?;
        let left_path = decode::child(&path, "left");
        let right_path = decode::child(&path, "right");
        let left_name = decode::name(decode::member(members, "left"), &left_path)?;
        let right_name = decode::name(decode::member(members, "right"), &right_path)?;
        let left = field(left, &left_name, &left_path)?;
        let right = field(right, &right_name, &right_path)?;
        same_type(&left.value_type, &right.value_type, &path)?;
        if !seen.insert((left_name, right_name)) {
            return Err(error(Kind::DuplicatePair, &path));
        }
    }
    // 不要求右字段为主键；恰好一次匹配属于后续验证义务。
    Ok(())
}

fn check_group(
    node: &ParsedNode<'_>,
    source: &TableType,
    types: &NormalizedTypeDeclarations,
) -> Result<(), NodeError> {
    let source_record = record(types, &source.record_type);
    let output = record(types, &node.table.record_type);
    let path = decode::child(&node.path, "keys");
    let keys = decode::array(decode::member(node.definition, "keys"), &path)?;
    if keys.len() != node.table.primary_key.len() {
        return Err(error(Kind::InvalidGroupKey, &path));
    }
    let mut names = BTreeSet::new();
    for (index, value) in keys.iter().enumerate() {
        let path = format!("{path}/{index}");
        let members = decode::object(value, &path, &["name", "source_field"])?;
        let name_path = decode::child(&path, "name");
        let name = decode::name(decode::member(members, "name"), &name_path)?;
        if !names.insert(name.clone()) {
            return Err(error(Kind::DuplicateName, &name_path));
        }
        if name != node.table.primary_key[index] {
            return Err(error(Kind::InvalidGroupKey, &name_path));
        }
        let output_field = field(output, &name, &name_path)?;
        let source_path = decode::child(&path, "source_field");
        let source_name = decode::name(decode::member(members, "source_field"), &source_path)?;
        let source_field = field(source_record, &source_name, &source_path)?;
        if source_field.label != Label::Public
            || matches!(
                source_field.value_type,
                ValueType::Option { .. } | ValueType::Record { .. }
            )
        {
            return Err(error(Kind::InvalidGroupKey, &source_path));
        }
        same_type(
            &source_field.value_type,
            &output_field.value_type,
            &source_path,
        )?;
    }
    let path = decode::child(&node.path, "aggregates");
    for (index, value) in decode::array(decode::member(node.definition, "aggregates"), &path)?
        .iter()
        .enumerate()
    {
        let path = format!("{path}/{index}");
        let kind = tagged_kind(value, &path)?;
        let keys: &[_] = match kind {
            "count" => &["kind", "name"],
            "sum" => &["kind", "name", "field"],
            _ => return Err(error(Kind::InvalidAggregate, &decode::child(&path, "kind"))),
        };
        let members = decode::object(value, &path, keys)?;
        let name_path = decode::child(&path, "name");
        let name = decode::name(decode::member(members, "name"), &name_path)?;
        if !names.insert(name.clone()) {
            return Err(error(Kind::DuplicateName, &name_path));
        }
        let target = &field(output, &name, &name_path)?.value_type;
        if kind == "count" {
            // 现行语义的 count 声明类型为 Int[0, N]；不检查实际组计数。
            if !matches!(target, ValueType::Int { lower, upper } if lower.as_str() == "0" && upper == &source.capacity)
            {
                return Err(error(Kind::TypeMismatch, &name_path));
            }
        } else {
            let source_path = decode::child(&path, "field");
            let source_name = decode::name(decode::member(members, "field"), &source_path)?;
            let source = &field(source_record, &source_name, &source_path)?.value_type;
            let compatible = match (source, target) {
                (ValueType::Int { .. }, ValueType::Int { .. }) => true,
                (ValueType::Fixed { scale: left, .. }, ValueType::Fixed { scale: right, .. }) => {
                    left == right
                }
                _ => false,
            };
            if !compatible {
                return Err(error(Kind::TypeMismatch, &source_path));
            }
            // 不比较 sum 的源 / 目标范围；数学和是否落入目标范围是后续义务。
        }
    }
    if names.len() != output.fields.len() {
        return Err(error(Kind::IncompleteFields, &path));
    }
    Ok(())
}
