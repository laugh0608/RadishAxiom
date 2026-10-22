//! 仅处理已通过逐行类型检查的树。记录引用摘要迭代计算，不递归展开类型 DAG。
use std::borrow::Cow;
use std::collections::{BTreeMap, VecDeque};

use crate::declarations::{self as decode, Label, Members, RecordType, ValueType};
use crate::json::Value;
use crate::normalization::NormalizedTypeDeclarations;

pub(crate) struct RecordScope<'a> {
    pub record_type: &'a str,
    pub fields: Option<&'a BTreeMap<String, Label>>,
}

// 记录的选择依赖与整个记录的内容摘要分开，直接读公开字段不受敏感兄弟字段污染。
// 条件产生的复合值允许保守合并为整体标签，不声称最小依赖集。
#[derive(Clone)]
enum FlowValue<'a> {
    Scalar(Label),
    Record {
        id: String,
        label: Label,
        declared: bool,
        fields: Option<Cow<'a, BTreeMap<String, Label>>>,
    },
    Option {
        label: Label,
        inner: Box<Self>,
    },
}

impl FlowValue<'_> {
    fn taint(&mut self, dependency: Label) {
        let label = match self {
            Self::Scalar(label) | Self::Record { label, .. } | Self::Option { label, .. } => label,
        };
        *label = label.join(dependency);
    }

    fn shaped(ty: &ValueType, declared: bool) -> Self {
        match ty {
            ValueType::Record { record_type } => Self::Record {
                id: record_type.clone(),
                label: Label::Public,
                declared,
                fields: None,
            },
            ValueType::Option { inner } => Self::Option {
                label: Label::Public,
                inner: Box::new(Self::shaped(inner, declared)),
            },
            _ => Self::Scalar(Label::Public),
        }
    }
}

pub(crate) struct LabelAnalyzer<'a> {
    types: &'a NormalizedTypeDeclarations,
    record_labels: Vec<Label>,
}

impl<'a> LabelAnalyzer<'a> {
    pub(crate) fn new(types: &'a NormalizedTypeDeclarations) -> Self {
        let mut result = Self {
            types,
            record_labels: vec![Label::Public; types.record_types().len()],
        };
        let mut parents = vec![Vec::new(); result.record_labels.len()];
        let mut sensitive = VecDeque::new();
        for (index, record) in types.record_types().iter().enumerate() {
            for field in &record.definition().fields {
                if field.label == Label::Sensitive && result.record_labels[index] == Label::Public {
                    result.record_labels[index] = Label::Sensitive;
                    sensitive.push_back(index);
                }
                let mut ty = &field.value_type;
                while let ValueType::Option { inner } = ty {
                    ty = inner;
                }
                if let ValueType::Record { record_type } = ty {
                    parents[result.record_index(record_type)].push(index);
                }
            }
        }
        while let Some(child) = sensitive.pop_front() {
            for &parent in &parents[child] {
                if result.record_labels[parent] == Label::Public {
                    result.record_labels[parent] = Label::Sensitive;
                    sensitive.push_back(parent);
                }
            }
        }
        result
    }

    fn record_index(&self, id: &str) -> usize {
        self.types
            .record_types()
            .binary_search_by(|entry| entry.id().cmp(id))
            .expect("checked record reference")
    }

    pub(crate) fn record(&self, id: &str) -> &RecordType {
        self.types.record_types()[self.record_index(id)].definition()
    }

    pub(crate) fn type_label(&self, mut ty: &ValueType) -> Label {
        while let ValueType::Option { inner } = ty {
            ty = inner;
        }
        match ty {
            ValueType::Record { record_type } => self.record_labels[self.record_index(record_type)],
            _ => Label::Public,
        }
    }

    fn summary(&self, value: &FlowValue<'_>) -> Label {
        match value {
            FlowValue::Scalar(label) => *label,
            FlowValue::Option { label, inner } => label.join(self.summary(inner)),
            FlowValue::Record {
                id,
                label,
                declared,
                fields,
            } => {
                let contents = if let Some(fields) = fields {
                    fields.values().fold(Label::Public, |a, b| a.join(*b))
                } else if *declared {
                    self.record_labels[self.record_index(id)]
                } else {
                    Label::Public
                };
                label.join(contents)
            }
        }
    }

    pub(crate) fn analyze_checked(&self, value: &Value, scope: &[RecordScope<'_>]) -> Label {
        let mut bindings = scope
            .iter()
            .rev()
            .map(|record| FlowValue::Record {
                id: record.record_type.to_owned(),
                label: Label::Public,
                declared: true,
                fields: record.fields.map(Cow::Borrowed),
            })
            .collect();
        self.summary(&self.walk(value, &mut bindings))
    }

    fn walk<'b>(&self, value: &Value, bindings: &mut Vec<FlowValue<'b>>) -> FlowValue<'b> {
        let members = members(value);
        let get = |key| decode::member(members, key);
        let op = string(get("op"));
        match op {
            "literal_bool" | "literal_text" | "literal_int" | "literal_fixed" | "literal_enum" => {
                FlowValue::Scalar(Label::Public)
            }
            "none" => FlowValue::shaped(
                &decode::value_type(get("type"), "").expect("checked annotation"),
                false,
            ),
            "some" => FlowValue::Option {
                label: Label::Public,
                inner: Box::new(self.walk(get("value"), bindings)),
            },
            "record" => {
                let id = string(get("record_type"));
                let declared = &self.record(id).fields;
                let fields = array(get("fields"))
                    .iter()
                    .map(|field| {
                        let field = self::members(field);
                        let name = string(decode::member(field, "name"));
                        let index = declared
                            .binary_search_by(|field| field.name.as_str().cmp(name))
                            .expect("checked field");
                        let dependency =
                            self.summary(&self.walk(decode::member(field, "expression"), bindings));
                        (name.to_owned(), declared[index].label.join(dependency))
                    })
                    .collect();
                FlowValue::Record {
                    id: id.to_owned(),
                    label: Label::Public,
                    declared: true,
                    fields: Some(Cow::Owned(fields)),
                }
            }
            "bound" => {
                let index: usize = string(get("index"))
                    .parse()
                    .expect("checked finite binding");
                bindings[bindings.len() - 1 - index].clone()
            }
            "field" => {
                let FlowValue::Record {
                    id, label, fields, ..
                } = self.walk(get("record"), bindings)
                else {
                    unreachable!("checked record access")
                };
                let name = string(get("field"));
                let record = self.record(&id);
                let field = &record.fields[record
                    .fields
                    .binary_search_by(|f| f.name.as_str().cmp(name))
                    .expect("checked field")];
                let dependency = if let Some(fields) = fields {
                    fields[name]
                } else {
                    field.label
                };
                let mut result = FlowValue::shaped(&field.value_type, true);
                result.taint(label.join(dependency));
                result
            }
            "if" | "match_option" => self.conditional(op, members, bindings),
            "not" => FlowValue::Scalar(self.summary(&self.walk(get("value"), bindings))),
            "and" | "or" | "int_add" | "fixed_add" => {
                let label = array(get("values"))
                    .iter()
                    .fold(Label::Public, |label, value| {
                        label.join(self.summary(&self.walk(value, bindings)))
                    });
                FlowValue::Scalar(label)
            }
            "eq" | "lt" | "le" | "gt" | "ge" | "int_sub" | "fixed_sub" => {
                let left = self.summary(&self.walk(get("left"), bindings));
                let right = self.summary(&self.walk(get("right"), bindings));
                FlowValue::Scalar(left.join(right))
            }
            _ => unreachable!("type checker closed supported operators"),
        }
    }

    fn conditional<'b>(
        &self,
        op: &str,
        members: &Members,
        bindings: &mut Vec<FlowValue<'b>>,
    ) -> FlowValue<'b> {
        let get = |key| decode::member(members, key);
        let label = if op == "if" {
            let condition = self.summary(&self.walk(get("condition"), bindings));
            let then = self.summary(&self.walk(get("then"), bindings));
            let otherwise = self.summary(&self.walk(get("else"), bindings));
            condition.join(then).join(otherwise)
        } else {
            let subject = self.walk(get("subject"), bindings);
            let subject_label = self.summary(&subject);
            let none = self.summary(&self.walk(get("none"), bindings));
            let FlowValue::Option { label, mut inner } = subject else {
                unreachable!("checked option")
            };
            inner.taint(label);
            bindings.push(*inner);
            let some = self.summary(&self.walk(get("some"), bindings));
            bindings.pop();
            subject_label.join(none).join(some)
        };
        let ty = decode::value_type(get("result_type"), "").expect("checked annotation");
        let mut result = FlowValue::shaped(&ty, false);
        result.taint(label);
        result
    }
}

pub(crate) fn members(value: &Value) -> &Members {
    let Value::Object(members) = value else {
        unreachable!("checked object")
    };
    members
}
pub(crate) fn string(value: &Value) -> &str {
    let Value::String(value) = value else {
        unreachable!("checked string")
    };
    value
}
pub(crate) fn array(value: &Value) -> &[Value] {
    let Value::Array(value) = value else {
        unreachable!("checked array")
    };
    value
}
