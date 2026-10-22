//! 现有节点的保守值 / 行存在性传播；提示留给后续义务，不提前拒绝 wrong 算法。
use std::collections::BTreeMap;
use std::sync::Arc;

use super::{NodeKind, ParsedNode};
use crate::declarations::{self as decode, Label};
use crate::expressions::labels::{LabelAnalyzer, RecordScope, array, members, string};
use crate::normalization::NormalizedTypeDeclarations;

/// 声明低于保守推导标签。不是反例、结构错误或正式义务；path 指向原输入。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FieldLabelGap {
    pub name: String,
    pub path: String,
    pub declared: Label,
    pub inferred: Label,
}

/// 只读摘要；不包含契约级非干扰或故障 / 总性证明。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NodeFlowAnalysis {
    row_control: Label,
    field_labels: Arc<BTreeMap<String, Label>>,
    label_gaps: Vec<FieldLabelGap>,
}

impl NodeFlowAnalysis {
    /// 决定行存在性 / 成员集合的保守控制标签，不是外部输入表级标签。
    pub fn row_control(&self) -> Label {
        self.row_control
    }
    /// Unicode scalar 字段序；值为声明与推导标签的上确界，不能由声明降密。
    /// 复合字段取整个值的摘要，可能保守包含嵌套字段的标签。
    pub fn field_labels(&self) -> &BTreeMap<String, Label> {
        &self.field_labels
    }
    pub fn label_gaps(&self) -> &[FieldLabelGap] {
        &self.label_gaps
    }
}

pub(super) fn analyze_checked(
    nodes: &[ParsedNode<'_>],
    order: &[usize],
    types: &NormalizedTypeDeclarations,
) -> Vec<NodeFlowAnalysis> {
    let analyzer = LabelAnalyzer::new(types);
    let mut input_fields = BTreeMap::<&str, Arc<BTreeMap<String, Label>>>::new();
    let mut flows: Vec<Option<NodeFlowAnalysis>> = vec![None; nodes.len()];
    for &index in order {
        let node = &nodes[index];
        let get = |key| decode::member(node.definition, key);
        let mut result = NodeFlowAnalysis {
            row_control: Label::Public,
            field_labels: Arc::new(BTreeMap::new()),
            label_gaps: vec![],
        };
        if node.analysis.kind == NodeKind::Input {
            result.field_labels = input_fields
                .entry(&node.table.record_type)
                .or_insert_with(|| {
                    Arc::new(
                        analyzer
                            .record(&node.table.record_type)
                            .fields
                            .iter()
                            .map(|field| {
                                (
                                    field.name.clone(),
                                    field.label.join(analyzer.type_label(&field.value_type)),
                                )
                            })
                            .collect(),
                    )
                })
                .clone();
        } else {
            let source_index = node.analysis.predecessors[0];
            let source = flows[source_index].as_ref().expect("topological source");
            let source_record = &nodes[source_index].table.record_type;
            let mut scopes = vec![RecordScope {
                record_type: source_record,
                fields: Some(&source.field_labels),
            }];
            result.row_control = source.row_control;
            match node.analysis.kind {
                NodeKind::Input => unreachable!(),
                NodeKind::Filter => {
                    result.row_control = result
                        .row_control
                        .join(analyzer.analyze_checked(get("predicate"), &scopes));
                    result.field_labels = source.field_labels.clone();
                }
                NodeKind::Map | NodeKind::LookupJoin => {
                    let mut matching = Label::Public;
                    if node.analysis.kind == NodeKind::LookupJoin {
                        let right_index = node.analysis.predecessors[1];
                        let right = flows[right_index].as_ref().expect("topological right");
                        scopes.push(RecordScope {
                            record_type: &nodes[right_index].table.record_type,
                            fields: Some(&right.field_labels),
                        });
                        matching = source.row_control.join(right.row_control);
                        for pair in array(get("pairs")) {
                            let pair = members(pair);
                            matching = matching
                                .join(source.field_labels[string(decode::member(pair, "left"))])
                                .join(right.field_labels[string(decode::member(pair, "right"))]);
                        }
                        result.row_control = result.row_control.join(matching);
                    }
                    for (index, field) in array(get("fields")).iter().enumerate() {
                        let field = members(field);
                        let name = string(decode::member(field, "name"));
                        let label = analyzer
                            .analyze_checked(decode::member(field, "expression"), &scopes)
                            .join(matching);
                        insert_field(
                            &mut result,
                            &analyzer,
                            node,
                            name,
                            label,
                            format!("{}/fields/{index}/expression", node.path),
                        );
                    }
                }
                NodeKind::Group => {
                    // 分组键虽须声明 public，仍可能通过此前标签缺口受敏感值影响。
                    for key in array(get("keys")) {
                        let key = members(key);
                        result.row_control = result
                            .row_control
                            .join(source.field_labels[string(decode::member(key, "source_field"))]);
                    }
                    for (index, key) in array(get("keys")).iter().enumerate() {
                        let key = members(key);
                        let name = string(decode::member(key, "name"));
                        let label =
                            source.field_labels[string(decode::member(key, "source_field"))];
                        insert_field(
                            &mut result,
                            &analyzer,
                            node,
                            name,
                            label,
                            format!("{}/keys/{index}/source_field", node.path),
                        );
                    }
                    for (index, aggregate) in array(get("aggregates")).iter().enumerate() {
                        let aggregate = members(aggregate);
                        let name = string(decode::member(aggregate, "name"));
                        let mut label = result.row_control;
                        if string(decode::member(aggregate, "kind")) == "sum" {
                            label = label.join(
                                source.field_labels[string(decode::member(aggregate, "field"))],
                            );
                        }
                        insert_field(
                            &mut result,
                            &analyzer,
                            node,
                            name,
                            label,
                            format!("{}/aggregates/{index}", node.path),
                        );
                    }
                }
            }
        }
        flows[index] = Some(result);
    }
    flows
        .into_iter()
        .map(|flow| flow.expect("all nodes visited"))
        .collect()
}

fn insert_field(
    result: &mut NodeFlowAnalysis,
    analyzer: &LabelAnalyzer<'_>,
    node: &ParsedNode<'_>,
    name: &str,
    inferred: Label,
    path: String,
) {
    let record = analyzer.record(&node.table.record_type);
    let field = &record.fields[record
        .fields
        .binary_search_by(|field| field.name.as_str().cmp(name))
        .expect("checked output field")];
    if field.label == Label::Public && inferred == Label::Sensitive {
        result.label_gaps.push(FieldLabelGap {
            name: name.to_owned(),
            path,
            declared: field.label,
            inferred,
        });
    }
    Arc::get_mut(&mut result.field_labels)
        .expect("new map / join / group field accumulator")
        .insert(
            name.to_owned(),
            field
                .label
                .join(inferred)
                .join(analyzer.type_label(&field.value_type)),
        );
}
