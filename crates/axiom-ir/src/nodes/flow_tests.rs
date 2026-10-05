use super::*;
use crate::declarations::Label::{self, Public, Sensitive};
use crate::expressions::RowScope;
use crate::normalization::normalize_type_declarations;

fn secret_condition() -> Value {
    object([
        ("op", text("eq")),
        ("left", field("0", "secret")),
        (
            "right",
            parsed(r#"{"op":"literal_text","value":"synthetic"}"#),
        ),
    ])
}
fn expression_label(doc: &Value, expression: &Value) -> Result<Label, ExpressionError> {
    let types = normalize_type_declarations(&bytes(doc), limits()).unwrap();
    let input = analyze(doc).unwrap();
    let table = &input.nodes()[0].table_type;
    let table = types
        .table_types()
        .iter()
        .find(|t| t.id() == table)
        .unwrap();
    RowTypeChecker::new(&types)
        .analyze_labels(
            &bytes(expression),
            limits(),
            RowScope::Single {
                record_type: &table.definition().record_type,
            },
        )
        .map(|result| result.label())
}
fn if_expression(condition: Value, yes: Value, no: Value, ty: Value) -> Value {
    object([
        ("op", text("if")),
        ("condition", condition),
        ("then", yes),
        ("else", no),
        ("result_type", ty),
    ])
}
fn match_expression(subject: Value, none: Value, some: Value, ty: Value) -> Value {
    object([
        ("op", text("match_option")),
        ("subject", subject),
        ("none", none),
        ("some", some),
        ("result_type", ty),
    ])
}

#[test]
fn expression_dependencies_cover_branches_and_option_binding_shifts_without_short_circuiting() {
    let (mut doc, _) = base("4");
    output(&mut doc, "out", 0);
    let boolean = parsed(r#"{"op":"literal_bool","value":false}"#);
    let public = field("0", "flag");
    let secret = secret_condition();
    let hidden_branch = if_expression(copy(&boolean), copy(&secret), copy(&public), parsed(BOOL));
    let secret_selector = if_expression(copy(&secret), copy(&public), copy(&public), parsed(BOOL));
    let both = object([
        ("op", text("and")),
        ("values", Value::Array(vec![copy(&boolean), copy(&secret)])),
    ]);
    for expression in [public, hidden_branch, secret_selector, both]
        .iter()
        .zip([Public, Sensitive, Sensitive, Sensitive])
    {
        assert_eq!(expression_label(&doc, expression.0).unwrap(), expression.1);
    }
    let some = object([("op", text("some")), ("value", field("0", "secret"))]);
    let literal = parsed(r#"{"op":"literal_text","value":"none"}"#);
    let match_secret = match_expression(
        some,
        copy(&literal),
        parsed(r#"{"op":"bound","index":"0"}"#),
        parsed(TEXT),
    );
    assert_eq!(expression_label(&doc, &match_secret).unwrap(), Sensitive);
    let some_public = object([("op", text("some")), ("value", copy(&boolean))]);
    let shifted = match_expression(
        copy(&some_public),
        copy(&literal),
        field("1", "secret"),
        parsed(TEXT),
    );
    assert_eq!(expression_label(&doc, &shifted).unwrap(), Sensitive);
    let nested = match_expression(
        copy(&some_public),
        copy(&literal),
        field("2", "secret"),
        parsed(TEXT),
    );
    let nested = match_expression(some_public, copy(&literal), nested, parsed(TEXT));
    assert_eq!(expression_label(&doc, &nested).unwrap(), Sensitive);
    let mut bad = copy(&match_secret);
    *at_mut(&mut bad, &["none"]) = field("1", "secret");
    assert!(matches!(
        expression_label(&doc, &bad),
        Err(ExpressionError::Type {
            kind: TypeErrorKind::BoundOutOfRange,
            ..
        })
    ));
}

#[test]
fn numeric_operations_and_all_operands_carry_dependencies() {
    let mut doc = document();
    let table = schema(
        &mut doc,
        &[
            ("id", TEXT, "public"),
            ("number", INT, "sensitive"),
            ("cash", FIXED, "sensitive"),
        ],
        &["id"],
        "4",
    );
    input(&mut doc, 0, &table, "in");
    output(&mut doc, "out", 0);
    for (op, name, ty) in [
        ("int_add", "number", INT),
        ("int_sub", "number", INT),
        ("fixed_add", "cash", FIXED),
        ("fixed_sub", "cash", FIXED),
    ] {
        let value = field("0", name);
        let expression = if op.ends_with("add") {
            object([
                ("op", text(op)),
                ("values", Value::Array(vec![copy(&value), copy(&value)])),
                ("result_type", parsed(ty)),
            ])
        } else {
            object([
                ("op", text(op)),
                ("left", copy(&value)),
                ("right", copy(&value)),
                ("result_type", parsed(ty)),
            ])
        };
        // x - x is intentionally not constant-folded into a public value.
        assert_eq!(expression_label(&doc, &expression).unwrap(), Sensitive);
    }
    for op in ["eq", "lt", "le", "gt", "ge"] {
        let expression = object([
            ("op", text(op)),
            ("left", field("0", "number")),
            ("right", field("0", "number")),
        ]);
        assert_eq!(expression_label(&doc, &expression).unwrap(), Sensitive);
    }
}

#[test]
fn record_access_distinguishes_selection_from_sibling_contents_and_none_reads_nothing() {
    let (mut doc, table) = base("4");
    output(&mut doc, "out", 0);
    let graph = analyze(&doc).unwrap();
    let record = graph
        .types()
        .table_types()
        .iter()
        .find(|entry| entry.id() == table)
        .unwrap()
        .definition()
        .record_type
        .clone();
    let record_type = object([("kind", text("record")), ("record_type", text(&record))]);
    let bound = parsed(r#"{"op":"bound","index":"0"}"#);
    assert_eq!(expression_label(&doc, &bound).unwrap(), Sensitive);
    assert_eq!(expression_label(&doc, &field("0", "flag")).unwrap(), Public);
    let chosen = if_expression(
        secret_condition(),
        copy(&bound),
        copy(&bound),
        copy(&record_type),
    );
    let projected = object([
        ("op", text("field")),
        ("record", chosen),
        ("field", text("flag")),
    ]);
    assert_eq!(expression_label(&doc, &projected).unwrap(), Sensitive);
    let none_type = object([("kind", text("option")), ("inner", copy(&record_type))]);
    let none = object([("op", text("none")), ("type", none_type)]);
    assert_eq!(expression_label(&doc, &none).unwrap(), Public);
    let impossible = match_expression(
        none,
        parsed(r#"{"op":"literal_text","value":"none"}"#),
        field("0", "secret"),
        parsed(TEXT),
    );
    assert_eq!(
        expression_label(&doc, &impossible).unwrap(),
        Sensitive,
        "the some branch still reads a declared sensitive field"
    );
    let some_row = object([("op", text("some")), ("value", bound)]);
    let matched = match_expression(
        some_row,
        parsed(r#"{"op":"literal_bool","value":false}"#),
        field("0", "flag"),
        parsed(BOOL),
    );
    assert_eq!(
        expression_label(&doc, &matched).unwrap(),
        Sensitive,
        "the subject reads the whole record"
    );
}

#[test]
fn mislabeled_projection_is_reported_and_cannot_launder_a_downstream_dependency() {
    let (mut doc, _) = base("4");
    let target = schema(
        &mut doc,
        &[("id", TEXT, "public"), ("copy/~😀", TEXT, "public")],
        &["id"],
        "4",
    );
    map(
        &mut doc,
        1,
        0,
        &target,
        vec![
            projection("id", field("0", "id")),
            projection("copy/~😀", field("0", "secret")),
        ],
    );
    map(
        &mut doc,
        2,
        1,
        &target,
        vec![
            projection("copy/~😀", field("0", "copy/~😀")),
            projection("id", field("0", "id")),
        ],
    );
    output(&mut doc, "out", 2);
    let graph = analyze(&doc).unwrap();
    for index in [1, 2] {
        assert_eq!(graph.node_flows()[index].row_control(), Public);
        assert_eq!(graph.node_flows()[index].field_labels()["id"], Public);
        assert_eq!(
            graph.node_flows()[index].field_labels()["copy/~😀"],
            Sensitive
        );
        assert_eq!(graph.node_flows()[index].label_gaps().len(), 1);
    }
    assert_eq!(
        graph.node_flows()[1].label_gaps()[0].path,
        "/nodes/1/definition/fields/1/expression"
    );
    assert_eq!(
        graph.node_flows()[2].label_gaps()[0].path,
        "/nodes/2/definition/fields/0/expression"
    );
    array_mut(&mut doc, &["nodes"]).reverse();
    let reordered = analyze(&doc).unwrap();
    assert_eq!(
        reordered.node_flows()[0].label_gaps()[0].path,
        "/nodes/0/definition/fields/0/expression"
    );
    assert_eq!(
        reordered.node_flows()[0].field_labels(),
        graph.node_flows()[2].field_labels()
    );
}

fn aggregate_after_filter(sensitive: bool) -> Value {
    let (mut doc, table) = base("4");
    filter(
        &mut doc,
        1,
        0,
        &table,
        if sensitive {
            secret_condition()
        } else {
            field("0", "flag")
        },
    );
    map(&mut doc, 2, 1, &table, identity_fields());
    let target = schema(
        &mut doc,
        &[
            ("key", TEXT, "public"),
            ("n", r#"{"kind":"int","lower":"0","upper":"4"}"#, "public"),
            ("sum", INT, "public"),
        ],
        &["key"],
        "4",
    );
    node(
        &mut doc,
        3,
        object([
            ("kind", text("group")),
            ("source", text(&node_id(2))),
            ("table_type", text(&target)),
            ("keys", parsed(r#"[{"name":"key","source_field":"other"}]"#)),
            (
                "aggregates",
                parsed(
                    r#"[{"kind":"count","name":"n"},{"kind":"sum","field":"units","name":"sum"}]"#,
                ),
            ),
        ]),
    );
    output(&mut doc, "out", 3);
    doc
}

#[test]
fn sensitive_membership_survives_maps_and_affects_count_and_sum() {
    for (sensitive, expected) in [(false, Public), (true, Sensitive)] {
        let graph = analyze(&aggregate_after_filter(sensitive)).unwrap();
        for index in 1..=3 {
            assert_eq!(graph.node_flows()[index].row_control(), expected);
        }
        let group = &graph.node_flows()[3];
        assert_eq!(group.field_labels()["n"], expected);
        assert_eq!(group.field_labels()["sum"], expected);
        assert_eq!(group.field_labels()["key"], Public);
        assert_eq!(group.label_gaps().len(), if sensitive { 2 } else { 0 });
    }
}

#[test]
fn declared_sensitive_outputs_remain_sensitive_even_when_derived_from_a_literal() {
    let (mut doc, table) = base("4");
    let mut fields = identity_fields();
    fields[5] = projection(
        "secret",
        parsed(r#"{"op":"literal_text","value":"constant"}"#),
    );
    map(&mut doc, 1, 0, &table, fields);
    filter(&mut doc, 2, 1, &table, secret_condition());
    output(&mut doc, "out", 2);
    let graph = analyze(&doc).unwrap();
    assert_eq!(graph.node_flows()[1].field_labels()["secret"], Sensitive);
    assert!(graph.node_flows()[1].label_gaps().is_empty());
    assert_eq!(graph.node_flows()[2].row_control(), Sensitive);
}

#[test]
fn join_match_values_and_right_membership_are_control_dependencies() {
    for mode in ["public", "secret", "right_filter"] {
        let (mut doc, table) = base("4");
        input(&mut doc, 1, &table, "right");
        let right = if mode == "right_filter" {
            filter(&mut doc, 2, 1, &table, secret_condition());
            2
        } else {
            1
        };
        let joined = array_mut(&mut doc, &["nodes"]).len();
        let pair_field = if mode == "secret" { "secret" } else { "id" };
        let pairs = Value::Array(vec![object([
            ("left", text(pair_field)),
            ("right", text(pair_field)),
        ])]);
        let target = schema(
            &mut doc,
            &[("id", TEXT, "public"), ("value", TEXT, "public")],
            &["id"],
            "4",
        );
        node(
            &mut doc,
            3,
            object([
                ("kind", text("lookup_join")),
                ("left", text(&node_id(0))),
                ("right", text(&node_id(right))),
                ("table_type", text(&target)),
                ("pairs", pairs),
                (
                    "fields",
                    Value::Array(vec![
                        projection("id", field("0", "id")),
                        projection("value", field("1", "other")),
                    ]),
                ),
            ]),
        );
        output(&mut doc, "out", 3);
        let graph = analyze(&doc).unwrap();
        let flow = &graph.node_flows()[joined];
        let expected = if mode == "public" { Public } else { Sensitive };
        assert_eq!(flow.row_control(), expected, "{mode}");
        assert_eq!(flow.field_labels()["value"], expected, "{mode}");
        assert_eq!(
            flow.label_gaps().len(),
            if mode == "public" { 0 } else { 2 }
        );
    }
}

#[test]
fn b04_flow_findings_are_separate_from_structure_and_relational_proofs() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../benchmarks/keyed-finite-table-v0.1/ax-b04/candidates");
    for (candidate, control, priority, gaps) in [
        ("correct", Public, Public, 0),
        ("wrong-sensitive-filter", Sensitive, Public, 0),
        ("wrong-sensitive-priority", Public, Sensitive, 1),
    ] {
        for ext in ["ir.json", "ir.jcs"] {
            let input = std::fs::read(root.join(format!("{candidate}.{ext}"))).unwrap();
            let normalized = normalize_node_graph(&input, limits()).unwrap();
            let graph = normalized.analysis();
            let result = &graph.node_flows()[graph.outputs()[0].node];
            assert_eq!(result.row_control(), control, "{candidate}");
            assert_eq!(result.field_labels()["priority"], priority, "{candidate}");
            assert_eq!(result.label_gaps().len(), gaps, "{candidate}");
        }
    }
}

#[test]
fn nested_records_and_option_tags_preserve_parent_field_dependencies() {
    let mut doc = document();
    let child = declaration(
        &mut doc,
        "record_types",
        "record-type",
        object([(
            "fields",
            parsed(
                r#"[{"label":"public","name":"open","type":{"kind":"bool"}},{"label":"sensitive","name":"secret","type":{"kind":"bool"}}]"#,
            ),
        )]),
    );
    let child_type = format!(r#"{{"kind":"record","record_type":"{child}"}}"#);
    let option_type = format!(r#"{{"kind":"option","inner":{child_type}}}"#);
    let table = schema(
        &mut doc,
        &[
            ("id", TEXT, "public"),
            ("nested", &child_type, "public"),
            ("hidden", &child_type, "sensitive"),
            ("maybe", &option_type, "sensitive"),
        ],
        &["id"],
        "4",
    );
    input(&mut doc, 0, &table, "in");
    output(&mut doc, "out", 0);
    for (outer, inner, expected) in [
        ("nested", "open", Public),
        ("nested", "secret", Sensitive),
        ("hidden", "open", Sensitive),
    ] {
        let expression = object([
            ("op", text("field")),
            ("record", field("0", outer)),
            ("field", text(inner)),
        ]);
        assert_eq!(expression_label(&doc, &expression).unwrap(), expected);
    }
    let optional = match_expression(
        field("0", "maybe"),
        parsed(r#"{"op":"literal_bool","value":false}"#),
        field("0", "open"),
        parsed(BOOL),
    );
    assert_eq!(expression_label(&doc, &optional).unwrap(), Sensitive);
}

#[test]
fn group_key_and_sum_cannot_hide_an_upstream_label_gap() {
    for name in ["other", "units"] {
        let mut doc = aggregate_after_filter(false);
        let fields = array_mut(&mut doc, &["nodes", "2", "definition", "fields"]);
        let slot = if name == "other" { 1 } else { 3 };
        fields[slot] = projection(
            name,
            if name == "other" {
                field("0", "secret")
            } else {
                if_expression(
                    secret_condition(),
                    field("0", "units"),
                    field("0", "units"),
                    parsed(INT),
                )
            },
        );
        let graph = analyze(&doc).unwrap();
        let group = &graph.node_flows()[3];
        assert_eq!(group.field_labels()["sum"], Sensitive);
        assert_eq!(
            group.field_labels()["n"],
            if name == "other" { Sensitive } else { Public }
        );
        assert_eq!(
            group.row_control(),
            if name == "other" { Sensitive } else { Public }
        );
    }
}

#[test]
fn record_label_summaries_follow_deep_reference_graphs_without_recursive_expansion() {
    let mut doc = document();
    let mut record = declaration(
        &mut doc,
        "record_types",
        "record-type",
        object([(
            "fields",
            parsed(r#"[{"label":"sensitive","name":"secret","type":{"kind":"text"}}]"#),
        )]),
    );
    for _ in 0..5000 {
        record = declaration(
            &mut doc,
            "record_types",
            "record-type",
            object([(
                "fields",
                Value::Array(vec![object([
                    ("name", text("child")),
                    ("label", text("public")),
                    (
                        "type",
                        object([("kind", text("record")), ("record_type", text(&record))]),
                    ),
                ])]),
            )]),
        );
    }
    let nested = format!(r#"{{"kind":"record","record_type":"{record}"}}"#);
    let table = schema(
        &mut doc,
        &[("id", TEXT, "public"), ("nested", &nested, "public")],
        &["id"],
        "4",
    );
    input(&mut doc, 0, &table, "in");
    output(&mut doc, "out", 0);
    let graph = analyze(&doc).unwrap();
    assert_eq!(graph.node_flows()[0].field_labels()["nested"], Sensitive);
    assert_eq!(graph.node_flows()[0].field_labels()["id"], Public);
    assert_eq!(graph.node_flows()[0].row_control(), Public);
    assert_eq!(
        expression_label(&doc, &field("0", "nested")).unwrap(),
        Sensitive
    );
}
