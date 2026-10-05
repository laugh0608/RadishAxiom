use super::*;

#[test]
fn projections_are_closed_complete_unique_and_exactly_typed() {
    let mut doc = mapped();
    let fields = array_mut(&mut doc, &["nodes", "1", "definition", "fields"]);
    fields.push(projection("id", field("0", "id")));
    rejects(
        &doc,
        NodeErrorKind::DuplicateName,
        "/nodes/1/definition/fields/7/name",
    );
    let mut doc = mapped();
    array_mut(&mut doc, &["nodes", "1", "definition", "fields"]).pop();
    rejects(
        &doc,
        NodeErrorKind::IncompleteFields,
        "/nodes/1/definition/fields",
    );
    let mut doc = mapped();
    *at_mut(
        &mut doc,
        &["nodes", "1", "definition", "fields", "0", "name"],
    ) = text("absent");
    rejects(
        &doc,
        NodeErrorKind::UnknownField,
        "/nodes/1/definition/fields/0/name",
    );
    let mut doc = mapped();
    *at_mut(
        &mut doc,
        &["nodes", "1", "definition", "fields", "0", "expression"],
    ) = field("0", "flag");
    rejects(
        &doc,
        NodeErrorKind::TypeMismatch,
        "/nodes/1/definition/fields/0/expression",
    );
    let mut doc = mapped();
    set(
        at_mut(&mut doc, &["nodes", "1", "definition", "fields", "0"]),
        "type",
        parsed(TEXT),
    );
    rejects_input(
        &doc,
        InputKind::UnknownMember,
        "/nodes/1/definition/fields/0/type",
    );
}

#[test]
fn renamed_fields_and_ports_are_not_tied_to_benchmark_names() {
    let mut doc = document();
    let input_table = schema(
        &mut doc,
        &[("编号/😀", TEXT, "public"), ("开关~", BOOL, "public")],
        &["编号/😀"],
        "9007199254740993123456789",
    );
    let output_table = schema(
        &mut doc,
        &[("新键", TEXT, "public"), ("允许", BOOL, "public")],
        &["新键"],
        "9007199254740993123456789",
    );
    input(&mut doc, 5, &input_table, "合成源");
    map(
        &mut doc,
        9,
        5,
        &output_table,
        vec![
            projection("新键", field("0", "编号/😀")),
            projection("允许", field("0", "开关~")),
        ],
    );
    output(&mut doc, "结果/😀", 9);
    let result = analyze(&doc).unwrap();
    assert_eq!(result.nodes()[1].table_type(), output_table);
    assert_eq!(result.nodes()[0].supplied_id(), node_id(5));
    assert_eq!(result.outputs()[0].name, "结果/😀");
    // NFC 与 NFD 名称保持不同，两个输出可以指向同一节点。
    output(&mut doc, "é", 9);
    output(&mut doc, "e\u{301}", 9);
    assert_eq!(analyze(&doc).unwrap().outputs().len(), 3);
}

#[test]
fn key_projection_checks_bijections_without_guessing_complex_expressions() {
    let mut doc = mapped();
    *at_mut(
        &mut doc,
        &["nodes", "1", "definition", "fields", "0", "expression"],
    ) = field("0", "other");
    rejects(
        &doc,
        NodeErrorKind::InvalidKeyProjection,
        "/nodes/1/definition/fields/0/expression",
    );
    let mut doc = mapped();
    let expression = object([
        ("op", text("if")),
        ("condition", field("0", "flag")),
        ("then", field("0", "id")),
        ("else", field("0", "id")),
        ("result_type", parsed(TEXT)),
    ]);
    *at_mut(
        &mut doc,
        &["nodes", "1", "definition", "fields", "0", "expression"],
    ) = expression;
    assert_eq!(
        analyze(&doc).unwrap_err(),
        NodeError::UnsupportedKeyExpression {
            path: "/nodes/1/definition/fields/0/expression".to_owned()
        }
    );
    let mut doc = document();
    let source = schema(
        &mut doc,
        &[("a", TEXT, "public"), ("b", TEXT, "public")],
        &["a", "b"],
        "4",
    );
    let target = schema(
        &mut doc,
        &[("x", TEXT, "public"), ("y", TEXT, "public")],
        &["x", "y"],
        "4",
    );
    input(&mut doc, 0, &source, "in");
    map(
        &mut doc,
        1,
        0,
        &target,
        vec![
            projection("x", field("0", "a")),
            projection("y", field("0", "b")),
        ],
    );
    output(&mut doc, "out", 1);
    assert!(analyze(&doc).is_ok());
    *at_mut(
        &mut doc,
        &["nodes", "1", "definition", "fields", "1", "expression"],
    ) = field("0", "a");
    rejects(
        &doc,
        NodeErrorKind::InvalidKeyProjection,
        "/nodes/1/definition/fields/1/expression",
    );
}

#[test]
fn filter_checks_predicate_record_key_and_mathematical_capacity() {
    let (mut doc, table) = base("4");
    filter(&mut doc, 1, 0, &table, field("0", "flag"));
    output(&mut doc, "out", 1);
    assert!(analyze(&doc).is_ok());
    *at_mut(&mut doc, &["nodes", "1", "definition", "predicate"]) = field("0", "id");
    rejects(
        &doc,
        NodeErrorKind::TypeMismatch,
        "/nodes/1/definition/predicate",
    );
    let mut doc = document();
    let fields = [("a", TEXT, "public"), ("b", TEXT, "public")];
    let source = schema(&mut doc, &fields, &["a", "b"], "9007199254740993123456789");
    let smaller = schema(&mut doc, &fields, &["a", "b"], "9007199254740993123456788");
    let larger = schema(&mut doc, &fields, &["a", "b"], "9007199254740993123456790");
    let reordered = schema(&mut doc, &fields, &["b", "a"], "9007199254740993123456789");
    let different_record = schema(
        &mut doc,
        &[("a", TEXT, "public"), ("b", TEXT, "sensitive")],
        &["a"],
        "1",
    );
    input(&mut doc, 0, &source, "in");
    filter(
        &mut doc,
        1,
        0,
        &smaller,
        parsed(r#"{"op":"literal_bool","value":true}"#),
    );
    output(&mut doc, "out", 1);
    assert!(analyze(&doc).is_ok());
    for (target, kind) in [
        (larger, NodeErrorKind::CapacityMismatch),
        (reordered, NodeErrorKind::FilterShapeMismatch),
        (different_record, NodeErrorKind::FilterShapeMismatch),
    ] {
        *at_mut(&mut doc, &["nodes", "1", "definition", "table_type"]) = text(&target);
        rejects(&doc, kind, "/nodes/1/definition/table_type");
    }
}

fn join_doc() -> Value {
    let (mut doc, left) = base("4");
    let right = schema(
        &mut doc,
        &[
            ("id", TEXT, "public"),
            ("other", TEXT, "public"),
            ("tier", BOOL, "public"),
        ],
        &["id"],
        "4",
    );
    let target = schema(
        &mut doc,
        &[("id", TEXT, "public"), ("tier", BOOL, "public")],
        &["id"],
        "4",
    );
    input(&mut doc, 1, &right, "right");
    node(
        &mut doc,
        2,
        object([
            ("kind", text("lookup_join")),
            ("left", text(&node_id(0))),
            ("right", text(&node_id(1))),
            ("pairs", parsed(r#"[{"left":"other","right":"other"}]"#)),
            ("table_type", text(&target)),
            (
                "fields",
                Value::Array(vec![
                    projection("id", field("0", "id")),
                    projection("tier", field("1", "tier")),
                ]),
            ),
        ]),
    );
    output(&mut doc, "out", 2);
    assert_ne!(left, right);
    doc
}

#[test]
fn join_checks_both_scopes_but_does_not_assume_uniqueness() {
    let mut doc = join_doc();
    assert_eq!(analyze(&doc).unwrap().nodes()[2].predecessors(), &[0, 1]);
    // 非键 other = other 良构；它是否恰好一次匹配不由本层断言。
    *at_mut(
        &mut doc,
        &["nodes", "2", "definition", "fields", "1", "expression"],
    ) = field("0", "tier");
    assert_eq!(
        analyze(&doc).unwrap_err(),
        NodeError::Expression(ExpressionError::Type {
            kind: TypeErrorKind::UnknownField,
            path: "/nodes/2/definition/fields/1/expression/field".to_owned(),
        })
    );
    let mut doc = join_doc();
    *at_mut(
        &mut doc,
        &["nodes", "2", "definition", "fields", "0", "expression"],
    ) = field("1", "id");
    rejects(
        &doc,
        NodeErrorKind::InvalidKeyProjection,
        "/nodes/2/definition/fields/0/expression",
    );
    for member in ["left", "right"] {
        let mut doc = join_doc();
        *at_mut(&mut doc, &["nodes", "2", "definition", member]) = text(&node_id(999));
        rejects(
            &doc,
            NodeErrorKind::UnresolvedReference,
            &format!("/nodes/2/definition/{member}"),
        );
    }
}

#[test]
fn join_pairs_are_nonempty_unique_closed_and_type_compatible() {
    for (pairs, kind, path) in [
        ("[]", NodeErrorKind::EmptyPairs, "/nodes/2/definition/pairs"),
        (
            r#"[{"left":"other","right":"other"},{"left":"other","right":"other"}]"#,
            NodeErrorKind::DuplicatePair,
            "/nodes/2/definition/pairs/1",
        ),
        (
            r#"[{"left":"id","right":"tier"}]"#,
            NodeErrorKind::TypeMismatch,
            "/nodes/2/definition/pairs/0",
        ),
        (
            r#"[{"left":"absent","right":"id"}]"#,
            NodeErrorKind::UnknownField,
            "/nodes/2/definition/pairs/0/left",
        ),
    ] {
        let mut doc = join_doc();
        *at_mut(&mut doc, &["nodes", "2", "definition", "pairs"]) = parsed(pairs);
        rejects(&doc, kind, path);
    }
    let mut doc = join_doc();
    set(
        at_mut(&mut doc, &["nodes", "2", "definition", "pairs", "0"]),
        "extra",
        Value::Bool(true),
    );
    rejects_input(
        &doc,
        InputKind::UnknownMember,
        "/nodes/2/definition/pairs/0/extra",
    );
}

#[test]
fn shared_predecessors_and_repeated_join_edges_have_correct_degrees() {
    let (mut doc, table) = base("4");
    node(
        &mut doc,
        1,
        object([
            ("kind", text("lookup_join")),
            ("left", text(&node_id(0))),
            ("right", text(&node_id(0))),
            ("pairs", parsed(r#"[{"left":"id","right":"id"}]"#)),
            ("table_type", text(&table)),
            ("fields", Value::Array(identity_fields())),
        ]),
    );
    filter(&mut doc, 2, 0, &table, field("0", "flag"));
    output(&mut doc, "a", 1);
    output(&mut doc, "b", 2);
    let result = analyze(&doc).unwrap();
    assert_eq!(result.topological_order(), &[0, 1, 2]);
    assert_eq!(result.nodes()[1].predecessors(), &[0, 0]);
}

fn grouped(count_type: &str, sum_type: &str, fixed_type: &str, capacity: &str) -> Value {
    let (mut doc, _) = base("4");
    let target = schema(
        &mut doc,
        &[
            ("group", TEXT, "public"),
            ("count", count_type, "public"),
            ("sum", sum_type, "public"),
            ("cash", fixed_type, "public"),
        ],
        &["group"],
        capacity,
    );
    node(
        &mut doc,
        1,
        object([
            ("kind", text("group")),
            ("source", text(&node_id(0))),
            ("table_type", text(&target)),
            (
                "keys",
                parsed(r#"[{"name":"group","source_field":"other"}]"#),
            ),
            (
                "aggregates",
                parsed(
                    r#"[{"kind":"count","name":"count"},{"kind":"sum","field":"units","name":"sum"},{"kind":"sum","field":"cash","name":"cash"}]"#,
                ),
            ),
        ]),
    );
    output(&mut doc, "out", 1);
    doc
}
fn group_doc() -> Value {
    grouped(
        r#"{"kind":"int","lower":"0","upper":"4"}"#,
        r#"{"kind":"int","lower":"0","upper":"40"}"#,
        r#"{"kind":"fixed","scale":"2","lower":"0","upper":"40"}"#,
        "4",
    )
}

#[test]
fn group_checks_types_and_retains_range_obligations() {
    let mut doc = group_doc();
    assert!(analyze(&doc).is_ok());
    array_mut(&mut doc, &["nodes", "1", "definition", "aggregates"]).reverse();
    assert!(
        analyze(&doc).is_ok(),
        "aggregate array order is not semantic"
    );
    let doc = grouped(
        r#"{"kind":"int","lower":"0","upper":"4"}"#,
        r#"{"kind":"int","lower":"0","upper":"0"}"#,
        r#"{"kind":"fixed","scale":"2","lower":"0","upper":"0"}"#,
        "0",
    );
    assert!(
        analyze(&doc).is_ok(),
        "range/capacity obligations are not discharged by node typing"
    );
    for (count, sum, fixed, capacity) in [
        (INT, INT, FIXED, "4"),
        (r#"{"kind":"int","lower":"1","upper":"4"}"#, INT, FIXED, "4"),
        (
            r#"{"kind":"int","lower":"0","upper":"4"}"#,
            BOOL,
            FIXED,
            "4",
        ),
        (
            r#"{"kind":"int","lower":"0","upper":"4"}"#,
            INT,
            r#"{"kind":"fixed","scale":"3","lower":"0","upper":"40"}"#,
            "4",
        ),
    ] {
        assert!(matches!(
            analyze(&grouped(count, sum, fixed, capacity)).unwrap_err(),
            NodeError::Structure {
                kind: NodeErrorKind::TypeMismatch,
                ..
            }
        ));
    }
    let mut doc = group_doc();
    let target = copy(at_mut(&mut doc, &["table_types", "1", "definition"]));
    let mut target = target;
    set(&mut target, "capacity", text("5"));
    let target = declaration(&mut doc, "table_types", "table-type", target);
    *at_mut(&mut doc, &["nodes", "1", "definition", "table_type"]) = text(&target);
    rejects(
        &doc,
        NodeErrorKind::CapacityMismatch,
        "/nodes/1/definition/table_type",
    );
}

#[test]
fn group_rejects_optional_sensitive_and_mismatched_keys() {
    for (field_name, kind) in [
        ("maybe", NodeErrorKind::InvalidGroupKey),
        ("secret", NodeErrorKind::InvalidGroupKey),
        ("units", NodeErrorKind::TypeMismatch),
        ("absent", NodeErrorKind::UnknownField),
    ] {
        let mut doc = group_doc();
        *at_mut(
            &mut doc,
            &["nodes", "1", "definition", "keys", "0", "source_field"],
        ) = text(field_name);
        rejects(&doc, kind, "/nodes/1/definition/keys/0/source_field");
    }
    let mut doc = group_doc();
    *at_mut(&mut doc, &["nodes", "1", "definition", "keys"]) = Value::Array(vec![]);
    rejects(
        &doc,
        NodeErrorKind::InvalidGroupKey,
        "/nodes/1/definition/keys",
    );
    let mut doc = group_doc();
    *at_mut(&mut doc, &["nodes", "1", "definition", "keys", "0", "name"]) = text("other");
    rejects(
        &doc,
        NodeErrorKind::InvalidGroupKey,
        "/nodes/1/definition/keys/0/name",
    );
}

#[test]
fn group_fields_are_closed_disjoint_complete_and_known() {
    for (member, replacement, kind, path) in [
        (
            "aggregates",
            r#"[{"kind":"count","name":"group"}]"#,
            NodeErrorKind::DuplicateName,
            "/nodes/1/definition/aggregates/0/name",
        ),
        (
            "aggregates",
            "[]",
            NodeErrorKind::IncompleteFields,
            "/nodes/1/definition/aggregates",
        ),
        (
            "aggregates",
            r#"[{"kind":"count","name":"missing"}]"#,
            NodeErrorKind::UnknownField,
            "/nodes/1/definition/aggregates/0/name",
        ),
        (
            "aggregates",
            r#"[{"kind":"average","name":"sum"}]"#,
            NodeErrorKind::InvalidAggregate,
            "/nodes/1/definition/aggregates/0/kind",
        ),
        (
            "aggregates",
            r#"[{"kind":"sum","name":"sum","field":"maybe"}]"#,
            NodeErrorKind::TypeMismatch,
            "/nodes/1/definition/aggregates/0/field",
        ),
    ] {
        let mut doc = group_doc();
        *at_mut(&mut doc, &["nodes", "1", "definition", member]) = parsed(replacement);
        rejects(&doc, kind, path);
    }
    let mut doc = group_doc();
    set(
        at_mut(&mut doc, &["nodes", "1", "definition", "aggregates", "0"]),
        "field",
        text("units"),
    );
    rejects_input(
        &doc,
        InputKind::UnknownMember,
        "/nodes/1/definition/aggregates/0/field",
    );
}

#[test]
fn embedded_expression_unsupported_and_contract_errors_preserve_full_paths() {
    for op in ["record", "is_some"] {
        let mut doc = mapped();
        *at_mut(
            &mut doc,
            &["nodes", "1", "definition", "fields", "1", "expression"],
        ) = object([("op", text(op))]);
        assert_eq!(
            analyze(&doc).unwrap_err(),
            NodeError::Expression(ExpressionError::Unsupported {
                reason: UnsupportedTyping::UnspecifiedForm,
                path: "/nodes/1/definition/fields/1/expression/op".to_owned(),
            })
        );
    }
    let (mut doc, table) = base("4");
    filter(
        &mut doc,
        1,
        0,
        &table,
        object([("op", text("forall_rows"))]),
    );
    output(&mut doc, "out", 1);
    assert_eq!(
        analyze(&doc).unwrap_err(),
        NodeError::Expression(ExpressionError::Type {
            kind: TypeErrorKind::ContractOperationInRow,
            path: "/nodes/1/definition/predicate/op".to_owned(),
        })
    );
}

#[test]
fn embedded_expression_depth_uses_the_whole_document_budget() {
    let (mut doc, table) = base("4");
    let mut expression = parsed(r#"{"op":"literal_bool","value":true}"#);
    for _ in 0..123 {
        expression = object([("op", text("not")), ("value", expression)]);
    }
    filter(&mut doc, 1, 0, &table, expression);
    output(&mut doc, "out", 1);
    assert!(analyze(&doc).is_ok());
    let expression = at_mut(&mut doc, &["nodes", "1", "definition", "predicate"]);
    let previous = std::mem::replace(expression, Value::Bool(false));
    *expression = object([("op", text("not")), ("value", previous)]);
    assert!(
        matches!(analyze(&doc).unwrap_err(), NodeError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Nesting))
    );
}

#[test]
fn map_and_join_require_exact_source_capacity_including_zero() {
    for mut doc in [mapped(), join_doc()] {
        let index = if array_mut(&mut doc, &["nodes"]).len() == 2 {
            "1"
        } else {
            "2"
        };
        let table_id = copy(at_mut(
            &mut doc,
            &["nodes", index, "definition", "table_type"],
        ));
        let Value::String(table_id) = table_id else {
            panic!("fixture ID")
        };
        let table = array_mut(&mut doc, &["table_types"])
            .iter()
            .find(|entry| {
                let Value::Object(members) = entry else {
                    panic!("fixture entry")
                };
                matches!(decode::member(members, "id"), Value::String(id) if id == &table_id)
            })
            .unwrap();
        let Value::Object(members) = table else {
            panic!("fixture table")
        };
        let original = copy(decode::member(members, "definition"));
        for capacity in ["0", "3", "5"] {
            let mut definition = copy(&original);
            set(&mut definition, "capacity", text(capacity));
            let id = declaration(&mut doc, "table_types", "table-type", definition);
            *at_mut(&mut doc, &["nodes", index, "definition", "table_type"]) = text(&id);
            rejects(
                &doc,
                NodeErrorKind::CapacityMismatch,
                &format!("/nodes/{index}/definition/table_type"),
            );
        }
    }
    let (mut doc, table) = base("0");
    map(&mut doc, 1, 0, &table, identity_fields());
    output(&mut doc, "out", 1);
    assert!(analyze(&doc).is_ok());
}

#[test]
fn group_key_order_follows_the_declared_primary_key() {
    let mut doc = document();
    let fields = [("a", TEXT, "public"), ("b", TEXT, "public")];
    let source = schema(&mut doc, &fields, &["a"], "4");
    let target = schema(&mut doc, &fields, &["b", "a"], "4");
    input(&mut doc, 0, &source, "in");
    node(
        &mut doc,
        1,
        object([
            ("kind", text("group")),
            ("source", text(&node_id(0))),
            ("table_type", text(&target)),
            (
                "keys",
                parsed(r#"[{"name":"b","source_field":"b"},{"name":"a","source_field":"a"}]"#),
            ),
            ("aggregates", Value::Array(vec![])),
        ]),
    );
    output(&mut doc, "out", 1);
    assert!(analyze(&doc).is_ok());
    array_mut(&mut doc, &["nodes", "1", "definition", "keys"]).reverse();
    rejects(
        &doc,
        NodeErrorKind::InvalidGroupKey,
        "/nodes/1/definition/keys/0/name",
    );
}
