//! 跨图 / 契约入口回归；复用节点合成输入 builder，期望由规范人工指定。
use super::*;
use crate::contracts::{
    ContractAnalysis, ContractError, ContractErrorKind as ContractKindError, ContractKind,
    FormulaRole, InterfaceKind, analyze_contracts,
};

#[path = "contract_table_tests.rs"]
mod table_tests;

const TRUE: &str = r#"{"op":"literal_bool","value":true}"#;
const FALSE: &str = r#"{"op":"literal_bool","value":false}"#;
const ZERO: &str =
    r#"{"op":"literal_int","type":{"kind":"int","lower":"0","upper":"10"},"value":"0"}"#;

fn contract_doc() -> Value {
    let (mut doc, _) = base("4");
    output(&mut doc, "result", 0);
    doc
}
fn add_contract(doc: &mut Value, index: usize, definition: Value) {
    // 仅为契约分析构造词法 ID；本测试入口不核验内容身份。
    array_mut(doc, &["contracts"]).push(object([
        ("id", text(&node_id(1000 + index))),
        ("definition", definition),
    ]));
}
fn formula(role: &str, expression: Value) -> Value {
    object([
        ("kind", text("formula")),
        ("role", text(role)),
        ("expression", expression),
    ])
}
fn table(kind: &str, name: &str) -> Value {
    object([("kind", text(kind)), ("name", text(name))])
}
fn quantify(op: &str, kind: &str, name: &str, body: Value) -> Value {
    object([
        ("op", text(op)),
        ("table", table(kind, name)),
        ("body", body),
    ])
}
fn lookup(kind: &str, name: &str, keys: Vec<Value>) -> Value {
    object([
        ("op", text("lookup")),
        ("table", table(kind, name)),
        ("keys", Value::Array(keys)),
    ])
}
fn matched(subject: Value, some: Value) -> Value {
    object([
        ("op", text("match_option")),
        ("subject", subject),
        ("none", parsed(FALSE)),
        ("some", some),
        ("result_type", parsed(BOOL)),
    ])
}
fn eq(left: Value, right: Value) -> Value {
    object([("op", text("eq")), ("left", left), ("right", right)])
}
fn count(predicate: Value, ty: &str) -> Value {
    object([
        ("op", text("count_where")),
        ("table", table("input", "source")),
        ("predicate", predicate),
        ("result_type", parsed(ty)),
    ])
}
fn sum(predicate: Value, value: Value, ty: &str) -> Value {
    object([
        ("op", text("sum_where")),
        ("table", table("input", "source")),
        ("predicate", predicate),
        ("value", value),
        ("result_type", parsed(ty)),
    ])
}
fn inspect(doc: &Value) -> Result<ContractAnalysis, ContractError> {
    analyze_contracts(&bytes(doc), limits())
}
fn with_formula(expression: Value) -> Value {
    let mut doc = contract_doc();
    add_contract(&mut doc, 0, formula("guarantee", expression));
    doc
}
fn expression_error(doc: &Value, kind: TypeErrorKind, suffix: &str) {
    assert_eq!(
        inspect(doc).unwrap_err(),
        ContractError::Expression(ExpressionError::Type {
            kind,
            path: format!("/contracts/0/definition/expression{suffix}")
        })
    );
}
fn structure_error(doc: &Value, kind: ContractKindError, path: &str) {
    assert_eq!(
        inspect(doc).unwrap_err(),
        ContractError::Structure {
            kind,
            path: path.to_owned()
        }
    );
}

#[test]
fn all_twelve_candidates_check_real_contracts_without_consulting_algorithm_outcomes() {
    let cases = [
        (
            "ax-b01",
            ["correct", "wrong-add", "wrong-drop-zero"],
            2,
            "net_orders",
        ),
        (
            "ax-b02",
            ["correct", "wrong-constant-tier", "wrong-region-join"],
            2,
            "order_tiers",
        ),
        (
            "ax-b03",
            ["correct", "wrong-single-group", "wrong-unit-sum"],
            1,
            "account_usage",
        ),
        (
            "ax-b04",
            [
                "correct",
                "wrong-sensitive-filter",
                "wrong-sensitive-priority",
            ],
            2,
            "export",
        ),
    ];
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../benchmarks/keyed-finite-table-v0.1");
    for (task, names, count, output) in cases {
        for name in names {
            let mut pretty = None;
            for ext in ["ir.json", "ir.jcs"] {
                let bytes = std::fs::read(
                    root.join(task)
                        .join("candidates")
                        .join(format!("{name}.{ext}")),
                )
                .unwrap();
                let result = analyze_contracts(&bytes, limits())
                    .unwrap_or_else(|error| panic!("{task}/{name}: {error}"));
                assert_eq!(result.contracts().len(), count);
                let guarantee = result
                    .contracts()
                    .iter()
                    .find(|entry| {
                        entry.kind()
                            == &ContractKind::Formula {
                                role: FormulaRole::Guarantee,
                            }
                    })
                    .unwrap();
                assert!(
                    guarantee
                        .interfaces()
                        .iter()
                        .any(|reference| reference.kind == InterfaceKind::Output
                            && reference.name == output)
                );
                for entry in result.contracts() {
                    if entry.kind()
                        == &(ContractKind::Formula {
                            role: FormulaRole::Assume,
                        })
                    {
                        assert!(
                            entry
                                .interfaces()
                                .iter()
                                .all(|reference| reference.kind == InterfaceKind::Input)
                        );
                    }
                    for reference in entry.interfaces() {
                        assert!(reference.node < result.graph().nodes().len());
                    }
                }
                if let Some(previous) = &pretty {
                    assert_eq!(previous, &result);
                } else {
                    pretty = Some(result);
                }
            }
        }
    }
}

#[test]
fn assumptions_reject_outputs_even_inside_an_unselected_branch() {
    let output_ref = quantify("exists_rows", "output", "result", parsed(TRUE));
    let mut doc = with_formula(object([
        ("op", text("if")),
        ("condition", parsed(FALSE)),
        ("then", output_ref),
        ("else", parsed(TRUE)),
        ("result_type", parsed(BOOL)),
    ]));
    assert!(inspect(&doc).is_ok());
    *at_mut(&mut doc, &["contracts", "0", "definition", "role"]) = text("assume");
    expression_error(&doc, TypeErrorKind::OutputInAssumption, "/then/table/kind");
}

#[test]
fn contracts_resolve_named_interfaces_and_never_internal_ids_or_ambient_rows() {
    for (kind, name, error, suffix) in [
        (
            "node",
            "result".to_owned(),
            TypeErrorKind::UnknownInterfaceKind,
            "/table/kind",
        ),
        (
            "input",
            "result".to_owned(),
            TypeErrorKind::UnknownInterface,
            "/table/name",
        ),
        (
            "output",
            "source".to_owned(),
            TypeErrorKind::UnknownInterface,
            "/table/name",
        ),
        (
            "input",
            node_id(0),
            TypeErrorKind::UnknownInterface,
            "/table/name",
        ),
    ] {
        expression_error(
            &with_formula(quantify("forall_rows", kind, &name, parsed(TRUE))),
            error,
            suffix,
        );
    }
    expression_error(
        &with_formula(field("0", "flag")),
        TypeErrorKind::BoundOutOfRange,
        "/record/index",
    );
    expression_error(&with_formula(parsed(ZERO)), TypeErrorKind::TypeMismatch, "");
    expression_error(
        &with_formula(quantify(
            "forall_rows",
            "input",
            "source",
            field("0", "units"),
        )),
        TypeErrorKind::TypeMismatch,
        "/body",
    );
}

fn policy(inputs: &[&str], outputs: &[&str]) -> Value {
    object([
        ("kind", text("noninterference")),
        (
            "inputs",
            Value::Array(inputs.iter().map(|name| text(name)).collect()),
        ),
        (
            "outputs",
            Value::Array(outputs.iter().map(|name| text(name)).collect()),
        ),
    ])
}

#[test]
fn noninterference_interfaces_are_nonempty_unique_and_kind_specific() {
    for (inputs, outputs, kind, path) in [
        (
            vec![],
            vec!["result"],
            ContractKindError::EmptyInterfaces,
            "/contracts/0/definition/inputs",
        ),
        (
            vec!["source"],
            vec![],
            ContractKindError::EmptyInterfaces,
            "/contracts/0/definition/outputs",
        ),
        (
            vec!["source", "source"],
            vec!["result"],
            ContractKindError::DuplicateInterface,
            "/contracts/0/definition/inputs/1",
        ),
        (
            vec!["source"],
            vec!["result", "result"],
            ContractKindError::DuplicateInterface,
            "/contracts/0/definition/outputs/1",
        ),
        (
            vec!["result"],
            vec!["result"],
            ContractKindError::UnknownInterface,
            "/contracts/0/definition/inputs/0",
        ),
        (
            vec!["source"],
            vec!["source"],
            ContractKindError::UnknownInterface,
            "/contracts/0/definition/outputs/0",
        ),
    ] {
        let mut doc = contract_doc();
        add_contract(&mut doc, 0, policy(&inputs, &outputs));
        structure_error(&doc, kind, path);
    }
}

#[test]
fn interface_names_are_exact_and_analysis_indices_follow_original_nodes() {
    let (mut doc, table) = base("4");
    *at_mut(&mut doc, &["nodes", "0", "definition", "port"]) = text("é");
    input(&mut doc, 1, &table, "e\u{301}");
    output(&mut doc, "𐀀", 1);
    output(&mut doc, "\u{e000}", 0);
    output(&mut doc, "é", 0);
    add_contract(
        &mut doc,
        0,
        policy(&["é", "e\u{301}"], &["𐀀", "é", "\u{e000}"]),
    );
    array_mut(&mut doc, &["nodes"]).reverse();
    let analysis = inspect(&doc).unwrap();
    let refs: Vec<_> = analysis.contracts()[0]
        .interfaces()
        .iter()
        .map(|r| (r.kind, r.name.as_str(), r.node))
        .collect();
    assert_eq!(
        refs,
        vec![
            (InterfaceKind::Input, "e\u{301}", 0),
            (InterfaceKind::Input, "é", 1),
            (InterfaceKind::Output, "é", 1),
            (InterfaceKind::Output, "\u{e000}", 1),
            (InterfaceKind::Output, "𐀀", 0)
        ]
    );
    // Same spelling can name both an input and output; kind remains semantic.
    add_contract(
        &mut doc,
        1,
        formula(
            "assume",
            quantify("forall_rows", "input", "é", parsed(TRUE)),
        ),
    );
    assert!(inspect(&doc).is_ok());
}

#[test]
fn closed_contract_forms_and_ids_do_not_accept_unknown_policy_or_metadata() {
    for (definition, kind, path) in [
        (
            object([("kind", text("warning"))]),
            ContractKindError::UnknownKind,
            "/contracts/0/definition/kind",
        ),
        (
            formula("advisory", parsed(TRUE)),
            ContractKindError::UnknownRole,
            "/contracts/0/definition/role",
        ),
    ] {
        let mut doc = contract_doc();
        add_contract(&mut doc, 0, definition);
        structure_error(&doc, kind, path);
    }
    let mut doc = with_formula(parsed(TRUE));
    set(
        at_mut(&mut doc, &["contracts", "0", "definition"]),
        "label",
        text("public"),
    );
    assert_eq!(
        inspect(&doc).unwrap_err(),
        ContractError::Input(decode::error(
            InputKind::UnknownMember,
            "/contracts/0/definition/label"
        ))
    );
    let mut doc = with_formula(parsed(TRUE));
    add_contract(&mut doc, 0, formula("assume", parsed(FALSE)));
    structure_error(&doc, ContractKindError::DuplicateId, "/contracts/1/id");
    let mut doc = with_formula(parsed(TRUE));
    *at_mut(&mut doc, &["contracts", "0", "id"]) = text("sha256:no");
    assert_eq!(
        inspect(&doc).unwrap_err(),
        ContractError::Input(decode::error(InputKind::InvalidId, "/contracts/0/id"))
    );
}

#[test]
fn unsupported_forms_and_forbidden_external_effects_never_become_success() {
    for op in ["record", "is_some"] {
        let doc = with_formula(object([("op", text(op))]));
        assert_eq!(
            inspect(&doc).unwrap_err(),
            ContractError::Expression(ExpressionError::Unsupported {
                reason: UnsupportedTyping::UnspecifiedForm,
                path: "/contracts/0/definition/expression/op".to_owned()
            })
        );
    }
    for op in ["read_file", "random", "environment", "call"] {
        expression_error(
            &with_formula(object([("op", text(op))])),
            TypeErrorKind::UnknownOperator,
            "/op",
        );
    }
    let mut doc = with_formula(parsed(TRUE));
    *at_mut(&mut doc, &["effects"]) = parsed(r#"["filesystem"]"#);
    assert_eq!(
        inspect(&doc).unwrap_err(),
        ContractError::Node(NodeError::Input(decode::error(
            InputKind::NonEmptyEffects,
            "/effects"
        )))
    );
    let mut expression = quantify("forall_rows", "input", "source", parsed(TRUE));
    set(&mut expression, "effects", parsed("[]"));
    assert_eq!(
        inspect(&with_formula(expression)).unwrap_err(),
        ContractError::Expression(ExpressionError::Input(decode::error(
            InputKind::UnknownMember,
            "/contracts/0/definition/expression/effects"
        )))
    );
}

#[test]
fn contract_checks_do_not_assert_truth_noninterference_or_content_identity() {
    let mut doc = with_formula(parsed(FALSE));
    add_contract(&mut doc, 1, policy(&["source"], &["result"]));
    let result = inspect(&doc).unwrap();
    assert_eq!(result.contracts().len(), 2);
    assert_eq!(result.contracts()[0].supplied_id(), node_id(1000));
    assert_eq!(result.graph().nodes()[0].supplied_id(), node_id(0));
    let empty = contract_doc();
    assert!(inspect(&empty).unwrap().contracts().is_empty());
}

#[test]
fn contract_json_errors_and_resource_exhaustion_preserve_the_original_failure() {
    let doc = with_formula(quantify("forall_rows", "input", "source", parsed(TRUE)));
    let data = bytes(&doc);
    for budget in [
        JsonLimits {
            max_input_bytes: data.len() - 1,
            ..limits()
        },
        JsonLimits {
            max_values: 10,
            ..limits()
        },
        JsonLimits {
            max_nesting: 2,
            ..limits()
        },
    ] {
        let expected = json::parse(&data, budget).unwrap_err();
        assert_eq!(
            analyze_contracts(&data, budget).unwrap_err(),
            ContractError::Input(DeclarationError::Json(expected))
        );
    }
    let malformed = b"{\"contracts\":[],\"contracts\":[]}";
    let expected = json::parse(malformed, limits()).unwrap_err();
    assert_eq!(
        analyze_contracts(malformed, limits()).unwrap_err(),
        ContractError::Input(DeclarationError::Json(expected))
    );
}
