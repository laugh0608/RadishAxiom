//! 带形状的保守值推导。严格求值上下文与值 / 选择边保持不同角色。
use super::{Result, build::*};
use crate::{declarations::Label, json::Value};
use std::{collections::BTreeMap, sync::Arc};

impl<'a> Builder<'a> {
    fn operand(
        &mut self,
        value: &'a Value,
        key: &'static str,
        anchor: Anchor<'a>,
        path: &mut Vec<Part<'a>>,
        scope: &mut Vec<Flow<'a>>,
    ) -> Result<Flow<'a>> {
        path.push(Part::Name(key));
        let result = self.expression(get(value, key), anchor, path, scope);
        path.pop();
        result
    }
    fn use_value(&mut self, refs: &mut Vec<Edge>, flow: &Flow<'_>) -> Result<()> {
        self.edge(refs, Role::Value, flow.step)?;
        self.edge(refs, Role::Evaluation, flow.step)
    }
    pub fn expression(
        &mut self,
        value: &'a Value,
        anchor: Anchor<'a>,
        path: &mut Vec<Part<'a>>,
        scope: &mut Vec<Flow<'a>>,
    ) -> Result<Flow<'a>> {
        let op = text(value, "op");
        let keys: &[&str] = match op {
            "literal_bool" | "literal_text" | "some" | "not" => &["op", "value"],
            "literal_int" => &["op", "type", "value"],
            "literal_fixed" => &["op", "type", "coefficient"],
            "literal_enum" => &["op", "enum_type", "member"],
            "none" => &["op", "type"],
            "bound" => &["op", "index"],
            "field" => &["op", "field", "record"],
            "record" => &["op", "record_type", "fields"],
            "if" => &["op", "condition", "then", "else", "result_type"],
            "match_option" => &["op", "subject", "none", "some", "result_type"],
            "and" | "or" => &["op", "values"],
            "int_add" | "fixed_add" => &["op", "values", "result_type"],
            "eq" | "lt" | "le" | "gt" | "ge" => &["op", "left", "right"],
            "int_sub" | "fixed_sub" => &["op", "left", "right", "result_type"],
            _ => return Err(invalid(anchor, path, "unsupported row expression")),
        };
        shape(value, keys, anchor, path)?;
        let mut refs = vec![];
        let mut inferred = Label::Public;
        let mut result_shape = Shape::Scalar;
        let mut selection = None;
        let mut top = Label::Public;
        let mut base = Label::Public;
        let mut annotation = None;
        let mut inherit_bound = None;
        match op {
            "bound" => {
                let i = text(value, "index")
                    .parse::<usize>()
                    .ok()
                    .filter(|&i| i < scope.len())
                    .ok_or_else(|| invalid(anchor, path, "out of scope bound"))?;
                let flow = &scope[scope.len() - 1 - i];
                self.use_value(&mut refs, flow)?;
                inferred = self.label(flow.step);
                self.descriptors(1)?;
                inherit_bound = Some(flow.clone());
            }
            "none" => {
                annotation = Some((get(value, "type"), false));
            }
            "some" => {
                let inner = self.operand(value, "value", anchor, path, scope)?;
                self.use_value(&mut refs, &inner)?;
                inferred = self.label(inner.step);
                base = inferred;
                self.descriptors(1)?;
                result_shape = Shape::KnownOption(Arc::new(inner));
            }
            "field" => {
                let record = self.operand(value, "record", anchor, path, scope)?;
                let Shape::Record { id, fields, .. } = &record.shape else {
                    return Err(invalid(anchor, path, "field requires record shape"));
                };
                let name = text(value, "field");
                let field = self.field(id, name);
                let declaration = self.field_steps[&(*id, name)];
                let (source, dependency) = if let Some(fields) = fields {
                    let step = fields[name];
                    (step, self.label(step))
                } else {
                    (declaration, label(text(field, "label")))
                };
                self.edge(&mut refs, Role::Value, source)?;
                if let Some(step) = record.selection {
                    self.edge(&mut refs, Role::Selection, step)?;
                }
                self.edge(&mut refs, Role::Evaluation, record.step)?;
                self.edge(&mut refs, Role::Declaration, declaration)?;
                inferred = self.selection_label(&record).join(dependency);
                top = inferred;
                annotation = Some((get(field, "type"), true));
            }
            "record" => {
                let id = text(value, "record_type");
                let mut fields = BTreeMap::new();
                path.push(Part::Name("fields"));
                for (i, field) in array(get(value, "fields")).iter().enumerate() {
                    path.push(Part::Index(i));
                    shape(field, &["name", "expression"], anchor, path)?;
                    let flow = self.operand(field, "expression", anchor, path, scope)?;
                    let name = text(field, "name");
                    let declaration = self.field_steps[&(id, name)];
                    let labels = Labels::field(
                        label(text(self.field(id, name), "label")),
                        self.label(flow.step),
                        Label::Public,
                    );
                    let mut edges = vec![];
                    self.edge(&mut edges, Role::Value, flow.step)?;
                    self.edge(&mut edges, Role::Declaration, declaration)?;
                    let assignment =
                        self.add(anchor, path, name, "expr.record-field", labels, edges)?;
                    self.descriptors(1)?;
                    fields.insert(name, assignment);
                    self.edge(&mut refs, Role::Value, assignment)?;
                    self.edge(&mut refs, Role::Evaluation, flow.step)?;
                    inferred = inferred.join(labels.propagated);
                    path.pop();
                }
                path.pop();
                self.edge(&mut refs, Role::Declaration, self.record_steps[id])?;
                self.descriptors(1)?;
                result_shape = Shape::Record {
                    id,
                    fields: Some(Arc::new(fields)),
                };
                base = inferred;
            }
            "if" => {
                for key in ["condition", "then", "else"] {
                    let child = self.operand(value, key, anchor, path, scope)?;
                    self.edge(
                        &mut refs,
                        if key == "condition" {
                            Role::Selection
                        } else {
                            Role::Value
                        },
                        child.step,
                    )?;
                    self.edge(&mut refs, Role::Evaluation, child.step)?;
                    inferred = inferred.join(self.label(child.step));
                }
                top = inferred;
                annotation = Some((get(value, "result_type"), false));
            }
            "match_option" => {
                let subject = self.operand(value, "subject", anchor, path, scope)?;
                let none = self.operand(value, "none", anchor, path, scope)?;
                self.edge(&mut refs, Role::Selection, subject.step)?;
                self.edge(&mut refs, Role::Evaluation, subject.step)?;
                self.use_value(&mut refs, &none)?;
                path.push(Part::Name("some"));
                let mut edges = vec![];
                self.edge(&mut edges, Role::Value, subject.step)?;
                if let Some(id) = subject.selection {
                    self.edge(&mut edges, Role::Selection, id)?;
                }
                // 内部 shape 保留原选择标签，只把 Option 外层选择标签加进去。
                let (inner_base, inner_top) = match &subject.shape {
                    Shape::KnownOption(inner) => (inner.base, inner.top),
                    Shape::TypedOption { inner, declared } => (
                        if *declared {
                            self.type_label(inner)
                        } else {
                            Label::Public
                        },
                        Label::Public,
                    ),
                    _ => return Err(invalid(anchor, path, "match requires option shape")),
                };
                let inner_top = inner_top.join(subject.top);
                let labels = Labels::inferred(inner_base.join(inner_top));
                let binding = self.add(anchor, path, "", "binding.some", labels, edges)?;
                let inner = match &subject.shape {
                    Shape::KnownOption(inner) => {
                        self.descriptors(1)?;
                        Flow {
                            selection: Some(binding),
                            top: inner_top,
                            step: binding,
                            ..(**inner).clone()
                        }
                    }
                    Shape::TypedOption { inner, declared } => {
                        self.shaped(inner, *declared, Some(binding), inner_top, binding)?
                    }
                    _ => unreachable!("checked option shape"),
                };
                self.descriptors(1)?;
                scope.push(inner);
                let some = self.expression(get(value, "some"), anchor, path, scope)?;
                scope.pop();
                path.pop();
                self.use_value(&mut refs, &some)?;
                inferred = self
                    .label(subject.step)
                    .join(self.label(none.step))
                    .join(self.label(some.step));
                top = inferred;
                annotation = Some((get(value, "result_type"), false));
            }
            "and" | "or" | "int_add" | "fixed_add" => {
                path.push(Part::Name("values"));
                for (i, child) in array(get(value, "values")).iter().enumerate() {
                    path.push(Part::Index(i));
                    let flow = self.expression(child, anchor, path, scope)?;
                    path.pop();
                    self.use_value(&mut refs, &flow)?;
                    inferred = inferred.join(self.label(flow.step));
                }
                path.pop();
                top = inferred;
            }
            "not" => {
                let flow = self.operand(value, "value", anchor, path, scope)?;
                self.use_value(&mut refs, &flow)?;
                inferred = self.label(flow.step);
                top = inferred;
            }
            "eq" | "lt" | "le" | "gt" | "ge" | "int_sub" | "fixed_sub" => {
                for key in ["left", "right"] {
                    let flow = self.operand(value, key, anchor, path, scope)?;
                    self.use_value(&mut refs, &flow)?;
                    inferred = inferred.join(self.label(flow.step));
                }
                top = inferred;
            }
            _ => {} // 闭合模式表仅余字面值。
        }
        let type_summary = annotation
            .filter(|(_, declared)| *declared)
            .map(|(ty, _)| self.type_label(ty))
            .unwrap_or(Label::Public);
        let labels = Labels {
            declared: Label::Public,
            inferred,
            type_summary,
            propagated: inferred.join(type_summary),
        };
        let step = self.add(anchor, path, "", &format!("expr.{op}"), labels, refs)?;
        if let Some(mut flow) = inherit_bound {
            flow.step = step;
            return Ok(flow);
        }
        if let Some((ty, declared)) = annotation {
            return self.shaped(
                ty,
                declared,
                if op == "none" { None } else { Some(step) },
                top,
                step,
            );
        }
        if !matches!(op, "some" | "record") {
            selection = Some(step);
        }
        self.descriptors(1)?;
        Ok(Flow {
            shape: result_shape,
            top,
            base,
            selection,
            step,
        })
    }
}
