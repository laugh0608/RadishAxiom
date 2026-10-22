use super::{Result, build::*};
use crate::{declarations::Label, json::Value};
use std::{collections::BTreeMap, sync::Arc};

impl<'a> Builder<'a> {
    fn control(&mut self, anchor: Anchor<'a>, rule: &str, inputs: &[(Role, Id)]) -> Result<Id> {
        let mut refs = vec![];
        let mut inferred = Label::Public;
        for &(role, id) in inputs {
            self.edge(&mut refs, role, id)?;
            inferred = inferred.join(self.label(id));
        }
        self.add(anchor, &[], "", rule, Labels::inferred(inferred), refs)
    }
    fn assign(
        &mut self,
        anchor: Anchor<'a>,
        path: &[Part<'a>],
        record: &'a str,
        name: &'a str,
        rule: &str,
        sources: &[(Role, Id)],
    ) -> Result<Id> {
        let field = self.field(record, name);
        let mut refs = vec![];
        let mut inferred = Label::Public;
        for &(role, id) in sources {
            self.edge(&mut refs, role, id)?;
            inferred = inferred.join(self.label(id));
        }
        self.edge(
            &mut refs,
            Role::Declaration,
            self.field_steps[&(record, name)],
        )?;
        let labels = Labels::field(
            label(text(field, "label")),
            inferred,
            self.type_label(get(field, "type")),
        );
        self.add(anchor, path, name, rule, labels, refs)
    }
    pub fn node(
        &mut self,
        anchor: Anchor<'a>,
        value: &'a Value,
        nodes: &BTreeMap<&'a str, Node<'a>>,
    ) -> Result<Node<'a>> {
        let kind = text(value, "kind");
        let keys: &[&str] = match kind {
            "input" => &["kind", "port", "table_type"],
            "filter" => &["kind", "predicate", "source", "table_type"],
            "map" => &["kind", "fields", "source", "table_type"],
            "lookup_join" => &["kind", "left", "right", "pairs", "fields", "table_type"],
            "group" => &["kind", "source", "keys", "aggregates", "table_type"],
            _ => return Err(invalid(anchor, &[], "unknown origin node")),
        };
        shape(value, keys, anchor, &[])?;
        let table = text(value, "table_type");
        let record_type = text(self.tables[table], "record_type");
        let mut fields = BTreeMap::new();
        let mut evaluation = vec![];
        let control;
        if kind == "input" {
            for field in array(get(self.records[record_type], "fields")) {
                let name = text(field, "name");
                let mut refs = vec![];
                self.edge(
                    &mut refs,
                    Role::Declaration,
                    self.field_steps[&(record_type, name)],
                )?;
                self.edge(&mut refs, Role::Declaration, self.table_steps[table])?;
                let labels = Labels::field(
                    label(text(field, "label")),
                    Label::Public,
                    self.type_label(get(field, "type")),
                );
                let step = self.add(
                    anchor,
                    &[Part::Name("port")],
                    name,
                    "input.field",
                    labels,
                    refs,
                )?;
                self.descriptors(1)?;
                fields.insert(name, step);
            }
            control = self.control(anchor, "input.control", &[])?;
            self.edge(&mut evaluation, Role::Declaration, self.table_steps[table])?;
        } else {
            let source_key = if kind == "lookup_join" {
                "left"
            } else {
                "source"
            };
            let source = nodes
                .get(text(value, source_key))
                .ok_or_else(|| invalid(anchor, &[], "missing predecessor"))?;
            self.edge(&mut evaluation, Role::Evaluation, source.evaluation)?;
            let right = if kind == "lookup_join" {
                Some(
                    nodes
                        .get(text(value, "right"))
                        .ok_or_else(|| invalid(anchor, &[], "missing right predecessor"))?,
                )
            } else {
                None
            };
            self.descriptors(if right.is_some() { 2 } else { 1 })?;
            let mut scope = Vec::new();
            if let Some(right) = right {
                scope.push(right.record.clone());
            }
            scope.push(source.record.clone());
            match kind {
                "filter" => {
                    let flow = self.expression(
                        get(value, "predicate"),
                        anchor,
                        &mut vec![Part::Name("predicate")],
                        &mut scope,
                    )?;
                    control = self.control(
                        anchor,
                        "filter.control",
                        &[
                            (Role::Selection, source.control),
                            (Role::Selection, flow.step),
                        ],
                    )?;
                    self.edge(&mut evaluation, Role::Evaluation, flow.step)?;
                    for (&name, &step) in source.fields.iter() {
                        let out = self.assign(
                            anchor,
                            &[],
                            record_type,
                            name,
                            "filter.field",
                            &[(Role::Value, step)],
                        )?;
                        self.descriptors(1)?;
                        fields.insert(name, out);
                    }
                }
                "map" | "lookup_join" => {
                    let matching = if let Some(right) = right {
                        self.edge(&mut evaluation, Role::Evaluation, right.evaluation)?;
                        let mut refs = vec![];
                        self.edge(&mut refs, Role::Selection, source.control)?;
                        self.edge(&mut refs, Role::Selection, right.control)?;
                        let mut matching_label =
                            self.label(source.control).join(self.label(right.control));
                        for (i, pair) in array(get(value, "pairs")).iter().enumerate() {
                            let path = [Part::Name("pairs"), Part::Index(i)];
                            shape(pair, &["left", "right"], anchor, &path)?;
                            let left_field = source.fields[text(pair, "left")];
                            let right_field = right.fields[text(pair, "right")];
                            let inferred = self.label(left_field).join(self.label(right_field));
                            let mut edges = vec![];
                            self.edge(&mut edges, Role::Value, left_field)?;
                            self.edge(&mut edges, Role::Value, right_field)?;
                            let step = self.add(
                                anchor,
                                &path,
                                "",
                                "join.pair",
                                Labels::inferred(inferred),
                                edges,
                            )?;
                            self.edge(&mut refs, Role::Selection, step)?;
                            matching_label = matching_label.join(inferred);
                        }
                        let matching = self.add(
                            anchor,
                            &[],
                            "",
                            "join.match",
                            Labels::inferred(matching_label),
                            refs,
                        )?;
                        control =
                            self.control(anchor, "join.control", &[(Role::Selection, matching)])?;
                        self.edge(&mut evaluation, Role::Evaluation, matching)?;
                        Some(matching)
                    } else {
                        control = self.control(
                            anchor,
                            "map.control",
                            &[(Role::Selection, source.control)],
                        )?;
                        None
                    };
                    for (i, field) in array(get(value, "fields")).iter().enumerate() {
                        let path = [Part::Name("fields"), Part::Index(i)];
                        shape(field, &["name", "expression"], anchor, &path)?;
                        let mut expression_path = vec![
                            Part::Name("fields"),
                            Part::Index(i),
                            Part::Name("expression"),
                        ];
                        let flow = self.expression(
                            get(field, "expression"),
                            anchor,
                            &mut expression_path,
                            &mut scope,
                        )?;
                        let name = text(field, "name");
                        let sources = [
                            (Role::Value, flow.step),
                            (Role::Selection, matching.unwrap_or(flow.step)),
                        ];
                        let step = self.assign(
                            anchor,
                            &path,
                            record_type,
                            name,
                            "field.assign",
                            &sources[..if matching.is_some() { 2 } else { 1 }],
                        )?;
                        self.descriptors(1)?;
                        fields.insert(name, step);
                        self.edge(&mut evaluation, Role::Evaluation, step)?;
                    }
                }
                "group" => {
                    let mut refs = vec![];
                    self.edge(&mut refs, Role::Selection, source.control)?;
                    let mut inferred = self.label(source.control);
                    for key in array(get(value, "keys")) {
                        let step = source.fields[text(key, "source_field")];
                        self.edge(&mut refs, Role::Selection, step)?;
                        inferred = inferred.join(self.label(step));
                    }
                    control = self.add(
                        anchor,
                        &[],
                        "",
                        "group.control",
                        Labels::inferred(inferred),
                        refs,
                    )?;
                    for (i, key) in array(get(value, "keys")).iter().enumerate() {
                        let path = [Part::Name("keys"), Part::Index(i)];
                        shape(key, &["name", "source_field"], anchor, &path)?;
                        let name = text(key, "name");
                        let step = self.assign(
                            anchor,
                            &path,
                            record_type,
                            name,
                            "field.assign",
                            &[(Role::Value, source.fields[text(key, "source_field")])],
                        )?;
                        self.descriptors(1)?;
                        fields.insert(name, step);
                        self.edge(&mut evaluation, Role::Evaluation, step)?;
                    }
                    for (i, aggregate) in array(get(value, "aggregates")).iter().enumerate() {
                        let path = [Part::Name("aggregates"), Part::Index(i)];
                        let kind = text(aggregate, "kind");
                        let sum = match kind {
                            "count" => {
                                shape(aggregate, &["kind", "name"], anchor, &path)?;
                                None
                            }
                            "sum" => {
                                shape(aggregate, &["kind", "name", "field"], anchor, &path)?;
                                Some(source.fields[text(aggregate, "field")])
                            }
                            _ => return Err(invalid(anchor, &path, "unknown aggregate")),
                        };
                        let sources = [
                            (Role::Selection, control),
                            (Role::Value, sum.unwrap_or(control)),
                        ];
                        let name = text(aggregate, "name");
                        let step = self.assign(
                            anchor,
                            &path,
                            record_type,
                            name,
                            "field.assign",
                            &sources[..if sum.is_some() { 2 } else { 1 }],
                        )?;
                        self.descriptors(1)?;
                        fields.insert(name, step);
                        self.edge(&mut evaluation, Role::Evaluation, step)?;
                    }
                }
                _ => unreachable!("closed node kinds"),
            }
        }
        let prefix = if kind == "lookup_join" { "join" } else { kind };
        let evaluation = self.add(
            anchor,
            &[],
            "",
            &format!("{prefix}.evaluation"),
            Labels::inferred(Label::Public),
            evaluation,
        )?;
        let mut refs = vec![];
        let mut inferred = Label::Public;
        for &step in fields.values() {
            self.edge(&mut refs, Role::Value, step)?;
            inferred = inferred.join(self.label(step));
        }
        self.edge(&mut refs, Role::Evaluation, evaluation)?;
        self.edge(&mut refs, Role::Declaration, self.table_steps[table])?;
        let record_step = self.add(
            anchor,
            &[],
            "",
            "node.record",
            Labels::inferred(inferred),
            refs,
        )?;
        self.descriptors(2)?;
        let fields = Arc::new(fields);
        let record = Flow {
            shape: Shape::Record {
                id: record_type,
                fields: Some(fields.clone()),
            },
            top: Label::Public,
            selection: None,
            base: inferred,
            step: record_step,
        };
        Ok(Node {
            record,
            control,
            evaluation,
            fields,
            record_type,
        })
    }
}
