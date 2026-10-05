use super::*;

#[test]
fn nested_quantifiers_options_and_lookup_keys_share_one_de_bruijn_environment() {
    let mut doc = contract_doc();
    let other = schema(
        &mut doc,
        &[("key", TEXT, "public"), ("distinct", BOOL, "public")],
        &["key"],
        "4",
    );
    input(&mut doc, 1, &other, "other");
    let body = matched(
        lookup("input", "other", vec![field("1", "id")]),
        object([
            ("op", text("and")),
            (
                "values",
                Value::Array(vec![
                    field("0", "distinct"),
                    field("1", "distinct"),
                    field("2", "flag"),
                ]),
            ),
        ]),
    );
    let expression = quantify(
        "forall_rows",
        "input",
        "source",
        quantify("exists_rows", "input", "other", body),
    );
    add_contract(&mut doc, 0, formula("assume", expression));
    let result = inspect(&doc).unwrap();
    let references: Vec<_> = result.contracts()[0]
        .interfaces()
        .iter()
        .map(|reference| (reference.name.as_str(), reference.node))
        .collect();
    assert_eq!(references, vec![("other", 1), ("source", 0)]);
    // lookup does not bind its target row while evaluating keys.
    *at_mut(
        &mut doc,
        &[
            "contracts",
            "0",
            "definition",
            "expression",
            "body",
            "body",
            "subject",
            "keys",
            "0",
        ],
    ) = field("0", "id");
    expression_error(
        &doc,
        TypeErrorKind::UnknownField,
        "/body/body/subject/keys/0/field",
    );
}

#[test]
fn binder_scopes_end_before_siblings_and_the_next_contract() {
    let first = quantify("forall_rows", "input", "source", field("0", "flag"));
    let expression = object([
        ("op", text("and")),
        ("values", Value::Array(vec![first, field("0", "flag")])),
    ]);
    expression_error(
        &with_formula(expression),
        TypeErrorKind::BoundOutOfRange,
        "/values/1/record/index",
    );
    let first = matched(
        lookup(
            "input",
            "source",
            vec![parsed(r#"{"op":"literal_text","value":"id"}"#)],
        ),
        field("0", "flag"),
    );
    let mut doc = with_formula(first);
    add_contract(&mut doc, 1, formula("guarantee", field("0", "flag")));
    assert_eq!(
        inspect(&doc).unwrap_err(),
        ContractError::Expression(ExpressionError::Type {
            kind: TypeErrorKind::BoundOutOfRange,
            path: "/contracts/1/definition/expression/record/index".to_owned()
        })
    );
}

#[test]
fn lookup_checks_composite_key_arity_order_and_exact_types() {
    let mut doc = document();
    let table_type = schema(
        &mut doc,
        &[("a", TEXT, "public"), ("b", BOOL, "public")],
        &["b", "a"],
        "0",
    );
    input(&mut doc, 0, &table_type, "source");
    output(&mut doc, "result", 0);
    let keys = vec![
        parsed(TRUE),
        parsed(r#"{"op":"literal_text","value":"key"}"#),
    ];
    add_contract(
        &mut doc,
        0,
        formula(
            "guarantee",
            matched(lookup("input", "source", keys), parsed(TRUE)),
        ),
    );
    assert!(
        inspect(&doc).is_ok(),
        "zero capacity does not turn a lookup formula into a structural failure"
    );
    array_mut(
        &mut doc,
        &[
            "contracts",
            "0",
            "definition",
            "expression",
            "subject",
            "keys",
        ],
    )
    .reverse();
    expression_error(&doc, TypeErrorKind::TypeMismatch, "/subject/keys/0");
    array_mut(
        &mut doc,
        &[
            "contracts",
            "0",
            "definition",
            "expression",
            "subject",
            "keys",
        ],
    )
    .pop();
    expression_error(&doc, TypeErrorKind::WrongArity, "/subject/keys");
    let mut doc = contract_doc();
    let expr = matched(
        lookup(
            "input",
            "source",
            vec![parsed(r#"{"op":"bound","index":"0"}"#)],
        ),
        parsed(TRUE),
    );
    add_contract(&mut doc, 0, formula("guarantee", expr));
    expression_error(
        &doc,
        TypeErrorKind::BoundOutOfRange,
        "/subject/keys/0/index",
    );
}

#[test]
fn counts_and_sums_bind_predicate_and_value_but_do_not_prove_result_ranges() {
    for aggregate in [
        count(field("0", "flag"), INT),
        sum(field("0", "flag"), field("0", "units"), INT),
    ] {
        let doc = with_formula(eq(aggregate, parsed(ZERO)));
        assert!(inspect(&doc).is_ok());
    }
    let fixed_sum = sum(field("0", "flag"), field("0", "cash"), FIXED);
    let fixed_literal = parsed(
        r#"{"op":"literal_fixed","type":{"kind":"fixed","scale":"2","lower":"0","upper":"10"},"coefficient":"0"}"#,
    );
    assert!(inspect(&with_formula(eq(fixed_sum, fixed_literal))).is_ok());
    // The empty sum is zero, which cannot fit [1,1]; this is an obligation, not a type error.
    let restricted = r#"{"kind":"int","lower":"1","upper":"1"}"#;
    let one =
        parsed(r#"{"op":"literal_int","type":{"kind":"int","lower":"1","upper":"1"},"value":"1"}"#);
    let (mut empty, _) = base("0");
    output(&mut empty, "result", 0);
    add_contract(
        &mut empty,
        0,
        formula(
            "guarantee",
            eq(
                sum(parsed(FALSE), field("0", "units"), restricted),
                copy(&one),
            ),
        ),
    );
    add_contract(
        &mut empty,
        1,
        formula("guarantee", eq(count(parsed(FALSE), restricted), one)),
    );
    assert!(inspect(&empty).is_ok());
}

#[test]
fn aggregate_predicates_numeric_kinds_and_fixed_scale_are_checked() {
    for (aggregate, error, suffix) in [
        (
            count(field("0", "units"), INT),
            TypeErrorKind::TypeMismatch,
            "/predicate",
        ),
        (
            count(parsed(TRUE), BOOL),
            TypeErrorKind::ExpectedInt,
            "/result_type",
        ),
        (
            sum(parsed(TRUE), field("0", "maybe"), INT),
            TypeErrorKind::ExpectedNumeric,
            "/value",
        ),
        (
            sum(parsed(TRUE), field("0", "id"), INT),
            TypeErrorKind::ExpectedNumeric,
            "/value",
        ),
        (
            sum(parsed(TRUE), field("0", "units"), FIXED),
            TypeErrorKind::TypeMismatch,
            "/result_type",
        ),
        (
            sum(
                parsed(TRUE),
                field("0", "cash"),
                r#"{"kind":"fixed","scale":"3","lower":"0","upper":"10"}"#,
            ),
            TypeErrorKind::ScaleMismatch,
            "/result_type",
        ),
    ] {
        expression_error(&with_formula(aggregate), error, suffix);
    }
}

#[test]
fn deepest_contract_binders_use_one_document_budget_and_do_not_skip_empty_tables() {
    // Root/contracts/entry/definition leave 124 expression containers at max_nesting=128.
    let (mut doc, _) = base("0");
    output(&mut doc, "result", 0);
    let mut expression = parsed(TRUE);
    for _ in 0..122 {
        expression = quantify("forall_rows", "input", "source", expression);
    }
    add_contract(&mut doc, 0, formula("assume", expression));
    assert!(inspect(&doc).is_ok());
    let mut path = vec!["contracts", "0", "definition", "expression"];
    path.extend(std::iter::repeat_n("body", 122));
    *at_mut(&mut doc, &path) = parsed(r#"{"op":"bound","index":"122"}"#);
    let expected = format!(
        "/contracts/0/definition/expression{}/index",
        "/body".repeat(122)
    );
    assert_eq!(
        inspect(&doc).unwrap_err(),
        ContractError::Expression(ExpressionError::Type {
            kind: TypeErrorKind::BoundOutOfRange,
            path: expected
        })
    );
    let budget = JsonLimits {
        max_nesting: 126,
        ..limits()
    };
    assert!(matches!(
        analyze_contracts(&bytes(&doc), budget),
        Err(ContractError::Input(DeclarationError::Json(
            crate::json::JsonError {
                kind: JsonErrorKind::ResourceLimit(ResourceLimit::Nesting),
                ..
            }
        )))
    ));
}

#[test]
fn all_table_operators_and_references_have_closed_member_sets() {
    for mut expression in [
        quantify("forall_rows", "input", "source", parsed(TRUE)),
        quantify("exists_rows", "input", "source", parsed(TRUE)),
        lookup(
            "input",
            "source",
            vec![parsed(r#"{"op":"literal_text","value":"id"}"#)],
        ),
        count(parsed(TRUE), INT),
        sum(parsed(TRUE), field("0", "units"), INT),
    ] {
        set(&mut expression, "cached_type", parsed(BOOL));
        assert_eq!(
            inspect(&with_formula(expression)).unwrap_err(),
            ContractError::Expression(ExpressionError::Input(decode::error(
                InputKind::UnknownMember,
                "/contracts/0/definition/expression/cached_type"
            )))
        );
    }
    let mut expression = quantify("forall_rows", "input", "source", parsed(TRUE));
    set(
        at_mut(&mut expression, &["table"]),
        "node",
        text(&node_id(0)),
    );
    assert_eq!(
        inspect(&with_formula(expression)).unwrap_err(),
        ContractError::Expression(ExpressionError::Input(decode::error(
            InputKind::UnknownMember,
            "/contracts/0/definition/expression/table/node"
        )))
    );
    let expression = object([
        ("op", text("exists_rows")),
        ("table", table("input", "source")),
    ]);
    assert_eq!(
        inspect(&with_formula(expression)).unwrap_err(),
        ContractError::Expression(ExpressionError::Input(decode::error(
            InputKind::MissingMember,
            "/contracts/0/definition/expression/body"
        )))
    );
}

#[test]
fn deep_aggregate_values_and_lookup_keys_fit_the_same_json_stack_bound() {
    let mut expression = field("0", "units");
    for _ in 0..120 {
        expression = sum(field("0", "flag"), expression, INT);
    }
    assert!(inspect(&with_formula(eq(expression, parsed(ZERO)))).is_ok());
    let mut key = parsed(r#"{"op":"literal_text","value":"id"}"#);
    for _ in 0..40 {
        key = object([
            ("op", text("match_option")),
            ("subject", lookup("input", "source", vec![key])),
            ("none", parsed(r#"{"op":"literal_text","value":"missing"}"#)),
            ("some", field("0", "id")),
            ("result_type", parsed(TEXT)),
        ]);
    }
    assert!(
        inspect(&with_formula(eq(
            key,
            parsed(r#"{"op":"literal_text","value":"id"}"#)
        )))
        .is_ok()
    );
}
