use radishaxiom_ir::contracts::{
    ContractError, ContractErrorKind, InterfaceKind, normalize_contracts,
};
use radishaxiom_ir::declarations::{DeclarationError, DeclarationErrorKind};
use radishaxiom_ir::expressions::{ExpressionError, TypeErrorKind, UnsupportedTyping};
use radishaxiom_ir::json::{JsonErrorKind, JsonLimits, ResourceLimit};
use radishaxiom_ir::nodes::{NodeError, normalize_node_graph};

const BASE: &str = include_str!("fixtures/contract-identities/base.json");
const INPUT: &str = include_str!("fixtures/contract-identities/input.json");
const NORMALIZED: &str = include_str!("fixtures/contract-identities/normalized-input.json");
const EXPECTED: &str = include_str!("fixtures/contract-identities/expected.tsv");
const FALSE: &str = r#"{"op":"literal_bool","value":false}"#;
const TRUE: &str = r#"{"op":"literal_bool","value":true}"#;
const LEXICAL_ID: &str = "sha256:0000000000000000000000000000000000000000000000000000000000000000";

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 1024 * 1024,
        max_values: 100_000,
        max_nesting: 128,
    }
}

fn vector(name: &str) -> (&str, &str) {
    EXPECTED
        .lines()
        .find_map(|line| {
            let mut parts = line.splitn(3, '\t');
            (parts.next().unwrap() == name).then(|| (parts.next().unwrap(), parts.next().unwrap()))
        })
        .unwrap()
}

fn entry(id: &str, definition: &str) -> String {
    format!(r#"{{"id":"{id}","definition":{definition}}}"#)
}

fn document(entries: &str) -> String {
    BASE.replace(
        r#""contracts": []"#,
        &format!(r#""contracts": [{entries}]"#),
    )
}

fn formula(expression: &str) -> String {
    entry(
        LEXICAL_ID,
        &format!(r#"{{"kind":"formula","role":"guarantee","expression":{expression}}}"#),
    )
}

#[test]
fn definitions_and_ids_match_independent_vectors_with_nested_table_operations() {
    for input in [INPUT, NORMALIZED] {
        let result = normalize_contracts(input.as_bytes(), limits()).unwrap();
        assert_eq!(result.contracts().len(), 11);
        assert_eq!(
            result.nodes(),
            normalize_node_graph(input.as_bytes(), limits())
                .unwrap()
                .nodes()
        );
        for (contract, row) in result.contracts().iter().zip(EXPECTED.lines()) {
            let parts: Vec<_> = row.splitn(3, '\t').collect();
            assert_eq!(contract.id(), parts[1], "{}", parts[0]);
            assert_eq!(
                contract.canonical_definition(),
                parts[2].as_bytes(),
                "{}",
                parts[0]
            );
        }
    }
    // 对每个规范 definition 重新进入真实检查路径，验证幂等性。
    for row in EXPECTED.lines() {
        let parts: Vec<_> = row.splitn(3, '\t').collect();
        let result =
            normalize_contracts(document(&entry(parts[1], parts[2])).as_bytes(), limits()).unwrap();
        assert_eq!(
            result.contracts()[0].canonical_definition(),
            parts[2].as_bytes()
        );
        assert_eq!(result.contracts()[0].id(), parts[1]);
    }
}

#[test]
fn normalization_preserves_original_analysis_positions_and_exact_unicode_interfaces() {
    let result = normalize_contracts(INPUT.as_bytes(), limits()).unwrap();
    assert_eq!(
        result.analysis().contracts()[0].supplied_id(),
        vector("forall-assume").0
    );
    let ni = &result.analysis().contracts()[10];
    assert_eq!(ni.supplied_id(), vector("unicode-interfaces").0);
    let names = ["e\u{301}", "source", "é", "\u{e000}", "\u{10000}"];
    let indices = [3, 5, 4, 1, 2];
    for ((reference, name), node) in ni.interfaces()[..5].iter().zip(names).zip(indices) {
        assert_eq!(reference.kind, InterfaceKind::Input);
        assert_eq!(reference.name, name);
        assert_eq!(reference.node, node);
        assert_eq!(
            result.analysis().graph().nodes()[node].input_port(),
            Some(name)
        );
    }
    assert_eq!(ni.interfaces()[6].kind, InterfaceKind::Output);
    assert_eq!(ni.interfaces()[6].name, "result");
    assert_eq!(ni.interfaces()[6].node, 0);
    assert!(
        result
            .contracts()
            .windows(2)
            .all(|pair| pair[0].id() < pair[1].id())
    );
}

#[test]
fn all_twelve_candidate_contract_ids_are_checked_without_judging_algorithm_outcomes() {
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
    let mut count = 0;
    let mut previous = None;
    for (index, (task, name)) in cases.into_iter().enumerate() {
        let stem = root.join(task).join("candidates");
        let pretty = std::fs::read(stem.join(format!("{name}.ir.json"))).unwrap();
        let canonical = std::fs::read(stem.join(format!("{name}.ir.jcs"))).unwrap();
        let left = normalize_contracts(&pretty, limits())
            .unwrap_or_else(|error| panic!("{task}/{name}: {error}"));
        let right = normalize_contracts(&canonical, limits()).unwrap();
        assert_eq!(left, right, "{task}/{name}");
        count += left.contracts().len();
        // 同题实现变更不改变接口契约；契约 ID 不绑定内部节点 ID。
        if index % 3 == 0 {
            previous = Some(left.contracts().to_vec());
        } else {
            assert_eq!(left.contracts(), previous.as_ref().unwrap());
        }
    }
    assert_eq!(count, 21);
}

#[test]
fn wrong_hash_domains_delimiters_newlines_and_wrappers_are_rejected_without_repair() {
    for row in include_str!("fixtures/contract-identities/wrong-hashes.tsv").lines() {
        let parts: Vec<_> = row.split('\t').collect();
        let changed = INPUT.replace(parts[1], parts[2]);
        assert_ne!(changed, INPUT);
        assert_eq!(
            normalize_contracts(changed.as_bytes(), limits()).unwrap_err(),
            ContractError::ContentIdMismatch {
                path: "/contracts/10/id".to_owned(),
                supplied: parts[2].to_owned(),
                computed: parts[1].to_owned(),
            },
            "{}",
            parts[0]
        );
    }
}

#[test]
fn semantic_positions_and_formula_roles_are_not_normalized_away() {
    let (id, definition) = vector("nested-lookup");
    let changed_binding = definition.replace(r#""index":"2""#, r#""index":"1""#);
    assert_ne!(changed_binding, definition);
    assert_eq!(
        normalize_contracts(document(&entry(id, &changed_binding)).as_bytes(), limits())
            .unwrap_err(),
        ContractError::ContentIdMismatch {
            path: "/contracts/0/id".to_owned(),
            supplied: id.to_owned(),
            computed: vector("different-binding").0.to_owned()
        }
    );
    let old_keys = r#""keys":[{"field":"𐀀","op":"field","record":{"index":"1","op":"bound"}},{"field":"","op":"field","record":{"index":"0","op":"bound"}}]"#;
    let new_keys = r#""keys":[{"field":"","op":"field","record":{"index":"0","op":"bound"}},{"field":"𐀀","op":"field","record":{"index":"1","op":"bound"}}]"#;
    let changed_keys = definition.replace(old_keys, new_keys);
    assert_ne!(changed_keys, definition);
    assert!(
        matches!(normalize_contracts(document(&entry(id, &changed_keys)).as_bytes(), limits()).unwrap_err(), ContractError::ContentIdMismatch { supplied, computed, .. } if supplied == id && computed != id)
    );
    let (id, definition) = vector("false-guarantee");
    let changed_role = definition.replace("guarantee", "assume");
    assert_eq!(
        normalize_contracts(document(&entry(id, &changed_role)).as_bytes(), limits()).unwrap_err(),
        ContractError::ContentIdMismatch {
            path: "/contracts/0/id".to_owned(),
            supplied: id.to_owned(),
            computed: vector("false-assume").0.to_owned()
        }
    );
    let (id, definition) = vector("exists-if");
    let changed_quantifier = definition.replace("exists_rows", "forall_rows");
    assert!(matches!(
        normalize_contracts(
            document(&entry(id, &changed_quantifier)).as_bytes(),
            limits()
        )
        .unwrap_err(),
        ContractError::ContentIdMismatch { .. }
    ));
}

#[test]
fn malformed_unsupported_and_invisible_operands_are_checked_before_normalization() {
    let cases = [
        (
            format!(r#"{{"op":"and","values":[{FALSE},{{"op":"is_some"}}]}}"#),
            ContractError::Expression(ExpressionError::Unsupported {
                reason: UnsupportedTyping::UnspecifiedForm,
                path: "/contracts/0/definition/expression/values/1/op".to_owned(),
            }),
        ),
        (
            format!(
                r#"{{"op":"if","condition":{TRUE},"then":{FALSE},"else":{{"op":"bound","index":"0"}},"result_type":{{"kind":"bool"}}}}"#
            ),
            ContractError::Expression(ExpressionError::Type {
                kind: TypeErrorKind::BoundOutOfRange,
                path: "/contracts/0/definition/expression/else/index".to_owned(),
            }),
        ),
        (
            format!(r#"{{"op":"or","values":[{TRUE},{{"op":"literal_text","value":"x"}}]}}"#),
            ContractError::Expression(ExpressionError::Type {
                kind: TypeErrorKind::TypeMismatch,
                path: "/contracts/0/definition/expression/values/1".to_owned(),
            }),
        ),
        (
            format!(r#"{{"op":"and","values":[{FALSE}]}}"#),
            ContractError::Expression(ExpressionError::Type {
                kind: TypeErrorKind::WrongArity,
                path: "/contracts/0/definition/expression/values".to_owned(),
            }),
        ),
    ];
    for (expression, expected) in cases {
        assert_eq!(
            normalize_contracts(document(&formula(&expression)).as_bytes(), limits()).unwrap_err(),
            expected
        );
    }
    let output = format!(
        r#"{{"op":"forall_rows","table":{{"kind":"output","name":"result"}},"body":{TRUE}}}"#
    );
    let expression = format!(r#"{{"op":"or","values":[{TRUE},{output}]}}"#);
    let assumption = formula(&expression).replace("guarantee", "assume");
    assert_eq!(
        normalize_contracts(document(&assumption).as_bytes(), limits()).unwrap_err(),
        ContractError::Expression(ExpressionError::Type {
            kind: TypeErrorKind::OutputInAssumption,
            path: "/contracts/0/definition/expression/values/1/table/kind".to_owned()
        })
    );
    // 第一条 ID 故意不匹配；第二条坏结构仍须在任何规范化 / 身份结果之前被检查。
    let entries = format!("{},false", formula(FALSE));
    assert_eq!(
        normalize_contracts(document(&entries).as_bytes(), limits()).unwrap_err(),
        ContractError::Input(DeclarationError::Structure {
            kind: DeclarationErrorKind::ExpectedObject,
            path: "/contracts/1".to_owned()
        })
    );
}

#[test]
fn duplicates_and_extra_members_are_rejected_instead_of_deduplicated() {
    let (id, definition) = vector("false-guarantee");
    let first = entry(id, definition);
    let duplicate = entry(
        id,
        &definition.replace(
            FALSE,
            &format!(r#"{{"op":"or","values":[{FALSE},{FALSE}]}}"#),
        ),
    );
    assert_eq!(
        normalize_contracts(
            document(&format!("{first},{duplicate}")).as_bytes(),
            limits()
        )
        .unwrap_err(),
        ContractError::Structure {
            kind: ContractErrorKind::DuplicateId,
            path: "/contracts/1/id".to_owned()
        }
    );
    let (id, definition) = vector("unicode-interfaces");
    let duplicate_name = definition.replace(r#""inputs":["é""#, r#""inputs":["é","é""#);
    assert_ne!(definition, duplicate_name);
    assert_eq!(
        normalize_contracts(document(&entry(id, &duplicate_name)).as_bytes(), limits())
            .unwrap_err(),
        ContractError::Structure {
            kind: ContractErrorKind::DuplicateInterface,
            path: "/contracts/0/definition/inputs/1".to_owned()
        }
    );
    let extra = definition.replace(
        r#""kind":"noninterference""#,
        r#""kind":"noninterference","proved":true"#,
    );
    assert_eq!(
        normalize_contracts(document(&entry(id, &extra)).as_bytes(), limits()).unwrap_err(),
        ContractError::Input(DeclarationError::Structure {
            kind: DeclarationErrorKind::UnknownMember,
            path: "/contracts/0/definition/proved".to_owned()
        })
    );
}

#[test]
fn contract_identity_success_requires_node_identity_and_preserves_node_diagnostics() {
    let changed = BASE.replace(r#""port": "source""#, r#""port": "renamed""#);
    assert_ne!(changed, BASE);
    assert!(
        matches!(normalize_contracts(changed.as_bytes(), limits()).unwrap_err(),
        ContractError::Node(NodeError::ContentIdMismatch { path, supplied, computed }) if path == "/nodes/5/id" && supplied != computed)
    );
    // 空契约合法，也仍检查节点身份；保留已有节点规范化组件的结果。
    let result = normalize_contracts(BASE.as_bytes(), limits()).unwrap();
    assert!(result.contracts().is_empty());
    assert_eq!(
        result.nodes(),
        normalize_node_graph(BASE.as_bytes(), limits())
            .unwrap()
            .nodes()
    );
}

#[test]
fn deep_and_wide_raw_inputs_are_bounded_before_deduplication() {
    let (id, definition) = vector("false-guarantee");
    let mut deep = FALSE.to_owned();
    for _ in 0..61 {
        deep = format!(r#"{{"op":"and","values":[{deep},{FALSE}]}}"#);
    }
    let wide = format!(
        r#"{{"op":"or","values":[{}]}}"#,
        vec![FALSE; 10_000].join(",")
    );
    for expression in [&deep, &wide] {
        let raw_definition = definition.replace(FALSE, expression);
        let input = document(&entry(id, &raw_definition));
        let result = normalize_contracts(input.as_bytes(), limits()).unwrap();
        assert_eq!(
            result.contracts()[0].canonical_definition(),
            definition.as_bytes()
        );
        assert_eq!(result.contracts()[0].id(), id);
        let small = JsonLimits {
            max_values: 100,
            ..limits()
        };
        assert!(
            matches!(normalize_contracts(input.as_bytes(), small).unwrap_err(), ContractError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Values))
        );
    }
    let too_deep = format!(r#"{{"op":"and","values":[{deep},{FALSE}]}}"#);
    let input = document(&entry(id, &definition.replace(FALSE, &too_deep)));
    assert!(
        matches!(normalize_contracts(input.as_bytes(), limits()).unwrap_err(), ContractError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Nesting))
    );
    assert!(
        matches!(normalize_contracts(INPUT.as_bytes(), JsonLimits { max_input_bytes: 1, ..limits() }).unwrap_err(), ContractError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::InputBytes))
    );
}
