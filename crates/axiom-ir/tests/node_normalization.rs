use radishaxiom_ir::declarations::{DeclarationError, DeclarationErrorKind, ValueType};
use radishaxiom_ir::expressions::{
    ExpressionError, RowScope, RowTypeChecker, TypeErrorKind, UnsupportedTyping,
};
use radishaxiom_ir::json::{JsonErrorKind, JsonLimits, ResourceLimit};
use radishaxiom_ir::nodes::{NodeError, normalize_node_graph};
use radishaxiom_ir::normalization::normalize_type_declarations;

const INPUT: &str = include_str!("fixtures/node-identities/input.json");
const NORMALIZED: &str = include_str!("fixtures/node-identities/normalized-input.json");
const EXPECTED: &str = include_str!("fixtures/node-identities/expected.tsv");
const EXPRESSIONS: &str = include_str!("fixtures/node-identities/expressions.tsv");
const FALSE: &str = r#"{"op":"literal_bool","value":false}"#;
const TRUE: &str = r#"{"op":"literal_bool","value":true}"#;

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 1024 * 1024,
        max_values: 100_000,
        max_nesting: 128,
    }
}

#[test]
fn expression_bytes_match_independent_vectors_and_normalization_is_idempotent() {
    let types = normalize_type_declarations(INPUT.as_bytes(), limits()).unwrap();
    let checker = RowTypeChecker::new(&types);
    for row in EXPRESSIONS.lines() {
        let parts: Vec<_> = row.splitn(3, '\t').collect();
        let [name, input, expected] = parts.as_slice() else {
            panic!("fixture row")
        };
        let result = checker
            .normalize(input.as_bytes(), limits(), RowScope::Closed)
            .unwrap();
        assert_eq!(result.canonical_bytes(), expected.as_bytes(), "{name}");
        assert_eq!(
            checker
                .normalize(result.canonical_bytes(), limits(), RowScope::Closed)
                .unwrap(),
            result,
            "{name}"
        );
    }
}

#[test]
fn node_definitions_and_ids_match_independent_vectors_for_all_five_kinds() {
    for input in [INPUT, NORMALIZED] {
        let result = normalize_node_graph(input.as_bytes(), limits()).unwrap();
        assert_eq!(result.nodes().len(), 6);
        for (node, expected) in result.nodes().iter().zip(EXPECTED.lines()) {
            let (id, definition) = expected.split_once('\t').unwrap();
            assert_eq!(node.id(), id);
            assert_eq!(node.canonical_definition(), definition.as_bytes());
        }
        // 图分析索引指向原输入：group、join、map、filter、reference、source。
        assert_eq!(result.analysis().topological_order(), &[4, 5, 3, 2, 1, 0]);
        assert_eq!(result.analysis().outputs()[0].node, 0);
    }
}

#[test]
fn existing_twelve_candidate_node_ids_survive_real_normalization() {
    let cases = [
        ("ax-b01", "correct"),
        ("ax-b01", "wrong-add"),
        ("ax-b01", "wrong-drop-zero"),
        ("ax-b02", "correct"),
        ("ax-b02", "wrong-constant-tier"),
        ("ax-b02", "wrong-region-join"),
        ("ax-b03", "correct"),
        ("ax-b03", "wrong-single-group"),
        ("ax-b03", "wrong-unit-sum"),
        ("ax-b04", "correct"),
        ("ax-b04", "wrong-sensitive-filter"),
        ("ax-b04", "wrong-sensitive-priority"),
    ];
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../benchmarks/keyed-finite-table-v0.1");
    for (task, name) in cases {
        let stem = root.join(task).join("candidates");
        let pretty = std::fs::read(stem.join(format!("{name}.ir.json"))).unwrap();
        let canonical = std::fs::read(stem.join(format!("{name}.ir.jcs"))).unwrap();
        let left = normalize_node_graph(&pretty, limits())
            .unwrap_or_else(|error| panic!("{task}/{name}: {error}"));
        let right = normalize_node_graph(&canonical, limits()).unwrap();
        assert_eq!(left, right, "{task}/{name}");
    }
}

#[test]
fn wrong_domains_delimiters_newlines_and_wrappers_are_not_repaired() {
    let rows = include_str!("fixtures/node-identities/wrong-hashes.tsv");
    for row in rows.lines() {
        let parts: Vec<_> = row.split('\t').collect();
        let [name, original, wrong] = parts.as_slice() else {
            panic!("fixture row")
        };
        // 同时重绑输出，确保抵达内容身份检查，而不是停在悬空引用。
        let input = INPUT.replace(original, wrong);
        assert_eq!(
            normalize_node_graph(input.as_bytes(), limits()).unwrap_err(),
            NodeError::ContentIdMismatch {
                path: "/nodes/0/id".to_owned(),
                supplied: (*wrong).to_owned(),
                computed: (*original).to_owned(),
            },
            "{name}"
        );
    }
}

#[test]
fn content_edits_fail_at_original_positions_without_cascading_reference_rewrites() {
    let changed = INPUT.replace("\"port\": \"source\"", "\"port\": \"renamed\"");
    assert_ne!(changed, INPUT);
    assert!(
        matches!(normalize_node_graph(changed.as_bytes(), limits()).unwrap_err(), NodeError::ContentIdMismatch { path, supplied, computed } if path == "/nodes/5/id" && supplied != computed)
    );
    let extra = INPUT.replace(
        "\"kind\": \"filter\",",
        "\"kind\": \"filter\", \"extra\": true,",
    );
    assert_ne!(extra, INPUT);
    assert_eq!(
        normalize_node_graph(extra.as_bytes(), limits()).unwrap_err(),
        NodeError::Input(DeclarationError::Structure {
            kind: DeclarationErrorKind::UnknownMember,
            path: "/nodes/3/definition/extra".to_owned(),
        })
    );
}

#[test]
fn malformed_or_unsupported_operands_cannot_be_removed_by_normalization() {
    let types = normalize_type_declarations(INPUT.as_bytes(), limits()).unwrap();
    let checker = RowTypeChecker::new(&types);
    let cases = [
        (
            format!(r#"{{"op":"and","values":[{TRUE}]}}"#),
            "/values",
            TypeErrorKind::WrongArity,
        ),
        (
            format!(r#"{{"op":"and","values":[{FALSE},{{"op":"literal_text","value":"x"}}]}}"#),
            "/values/1",
            TypeErrorKind::TypeMismatch,
        ),
        (
            format!(
                r#"{{"op":"if","condition":{TRUE},"then":{FALSE},"else":{{"op":"bound","index":"0"}},"result_type":{{"kind":"bool"}}}}"#
            ),
            "/else/index",
            TypeErrorKind::BoundOutOfRange,
        ),
    ];
    for (input, path, kind) in cases {
        assert_eq!(
            checker
                .normalize(input.as_bytes(), limits(), RowScope::Closed)
                .unwrap_err(),
            ExpressionError::Type {
                kind,
                path: path.to_owned()
            }
        );
    }
    let unsupported = format!(r#"{{"op":"and","values":[{FALSE},{{"op":"is_some"}}]}}"#);
    assert_eq!(
        checker
            .normalize(unsupported.as_bytes(), limits(), RowScope::Closed)
            .unwrap_err(),
        ExpressionError::Unsupported {
            reason: UnsupportedTyping::UnspecifiedForm,
            path: "/values/1/op".to_owned(),
        }
    );
    // 嵌入节点的相同问题也必须先于 ID 重算被报告。
    let changed = NORMALIZED.replacen("\"op\": \"and\"", "\"op\": \"is_some\"", 1);
    assert!(
        matches!(normalize_node_graph(changed.as_bytes(), limits()).unwrap_err(), NodeError::Expression(ExpressionError::Unsupported { reason: UnsupportedTyping::UnspecifiedForm, path }) if path == "/nodes/3/definition/predicate/op")
    );
}

#[test]
fn arithmetic_is_not_evaluated_reassociated_deduplicated_or_widened() {
    let types = normalize_type_declarations(INPUT.as_bytes(), limits()).unwrap();
    let checker = RowTypeChecker::new(&types);
    let zero = r#"{"kind":"int","lower":"0","upper":"0"}"#;
    let one_type = r#"{"kind":"int","lower":"0","upper":"1"}"#;
    let one = format!(r#"{{"op":"literal_int","type":{one_type},"value":"1"}}"#);
    let input = format!(r#"{{"op":"int_add","result_type":{zero},"values":[{one},{one}]}}"#);
    let result = checker
        .normalize(input.as_bytes(), limits(), RowScope::Closed)
        .unwrap();
    assert_eq!(result.canonical_bytes(), input.as_bytes());
    assert_eq!(
        result.value_type(),
        &ValueType::Int {
            lower: radishaxiom_ir::integer::Integer::parse("0").unwrap(),
            upper: radishaxiom_ir::integer::Integer::parse("0").unwrap()
        }
    );
    let inner = format!(r#"{{"op":"int_add","result_type":{one_type},"values":[{one},{one}]}}"#);
    let nested = format!(r#"{{"op":"int_add","result_type":{one_type},"values":[{inner},{one}]}}"#);
    // inner 的 op="int_add" 排在 literal_int 前；两层加法仍保持两层。
    assert_eq!(
        checker
            .normalize(nested.as_bytes(), limits(), RowScope::Closed)
            .unwrap()
            .canonical_bytes(),
        nested.as_bytes()
    );
}

#[test]
fn normalization_is_bounded_before_reducing_deep_or_wide_inputs() {
    let types = normalize_type_declarations(INPUT.as_bytes(), limits()).unwrap();
    let checker = RowTypeChecker::new(&types);
    let mut deep = FALSE.to_owned();
    for _ in 0..127 {
        deep = format!(r#"{{"op":"not","value":{deep}}}"#);
    }
    assert_eq!(
        checker
            .normalize(deep.as_bytes(), limits(), RowScope::Closed)
            .unwrap()
            .canonical_bytes(),
        deep.as_bytes()
    );
    let mut nested = FALSE.to_owned();
    for _ in 0..63 {
        nested = format!(r#"{{"op":"and","values":[{nested},{FALSE}]}}"#);
    }
    assert_eq!(
        checker
            .normalize(nested.as_bytes(), limits(), RowScope::Closed)
            .unwrap()
            .canonical_bytes(),
        FALSE.as_bytes()
    );
    let wide = format!(
        r#"{{"op":"or","values":[{}]}}"#,
        vec![FALSE; 10_000].join(",")
    );
    assert_eq!(
        checker
            .normalize(wide.as_bytes(), limits(), RowScope::Closed)
            .unwrap()
            .canonical_bytes(),
        FALSE.as_bytes()
    );
    let limited = JsonLimits {
        max_values: 100,
        ..limits()
    };
    assert!(
        matches!(checker.normalize(wide.as_bytes(), limited, RowScope::Closed).unwrap_err(), ExpressionError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Values))
    );
    assert!(
        matches!(normalize_node_graph(INPUT.as_bytes(), JsonLimits { max_input_bytes: 1, ..limits() }).unwrap_err(), NodeError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::InputBytes))
    );
}

#[test]
fn normalized_nodes_still_do_not_accept_contracts_or_full_ir() {
    let unchecked_contract = INPUT.replace("\"contracts\": []", "\"contracts\": [false]");
    assert_ne!(unchecked_contract, INPUT);
    assert!(normalize_node_graph(unchecked_contract.as_bytes(), limits()).is_ok());
}
