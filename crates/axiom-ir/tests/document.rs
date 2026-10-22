use radishaxiom_ir::contracts::ContractError;
use radishaxiom_ir::declarations::{DeclarationError, DeclarationErrorKind};
use radishaxiom_ir::document::{DocumentError, check_canonical_document, normalize_document};
use radishaxiom_ir::expressions::{ExpressionError, TypeErrorKind, UnsupportedTyping};
use radishaxiom_ir::json::{JsonErrorKind, JsonLimits, ResourceLimit, canonicalize_json};
use radishaxiom_ir::nodes::{NodeError, NodeErrorKind};

const NODE_INPUT: &[u8] = include_bytes!("fixtures/node-identities/input.json");
const CONTRACT_INPUT: &[u8] = include_bytes!("fixtures/contract-identities/input.json");
const TYPE_INPUT: &[u8] = include_bytes!("fixtures/document-identities/type-input.json");
const BASE: &str = include_str!("fixtures/contract-identities/base.json");
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

fn golden(name: &str) -> &'static [u8] {
    match name {
        "node" => include_bytes!("fixtures/document-identities/node.jcs"),
        "contract" => include_bytes!("fixtures/document-identities/contract.jcs"),
        "type" => include_bytes!("fixtures/document-identities/type.jcs"),
        "renamed-output" => include_bytes!("fixtures/document-identities/renamed-output.jcs"),
        "unicode-nfc" => include_bytes!("fixtures/document-identities/unicode-nfc.jcs"),
        "unicode-nfd" => include_bytes!("fixtures/document-identities/unicode-nfd.jcs"),
        "reordered-key" => include_bytes!("fixtures/document-identities/reordered-key.jcs"),
        "deep-binders" => include_bytes!("fixtures/document-identities/deep-binders.jcs"),
        "mixed-int-ranges" => include_bytes!("fixtures/document-identities/mixed-int-ranges.jcs"),
        _ => panic!("unknown test vector"),
    }
}

fn both_reject(input: &str, expected: DocumentError) {
    assert_eq!(
        normalize_document(input.as_bytes(), limits()).unwrap_err(),
        expected
    );
    assert_eq!(
        check_canonical_document(input.as_bytes(), limits()).unwrap_err(),
        expected
    );
}

fn contract_document(expression: &str, id: &str) -> String {
    let entry = format!(
        r#"{{"definition":{{"expression":{expression},"kind":"formula","role":"guarantee"}},"id":"{id}"}}"#
    );
    BASE.replace(r#""contracts": []"#, &format!(r#""contracts": [{entry}]"#))
}

#[test]
fn mixed_int_ranges_work_in_nodes_contracts_labels_and_document_identity() {
    let input = include_bytes!("fixtures/document-identities/mixed-int-ranges-input.json");
    let result = normalize_document(input, limits()).unwrap();
    assert_eq!(result.canonical_bytes(), golden("mixed-int-ranges"));
    assert_eq!(
        check_canonical_document(result.canonical_bytes(), limits())
            .unwrap()
            .document_id(),
        result.document_id()
    );
    let graph = result.components().analysis().graph();
    let output = graph.outputs()[0].node;
    assert_eq!(
        graph.node_flows()[output].row_control(),
        radishaxiom_ir::declarations::Label::Sensitive
    );
    assert_eq!(
        result.components().analysis().contracts()[0].interfaces()[0].name,
        "source"
    );
    // 类型比较不会隐式成为相等、数字转换、范围证明或规范化求值。
    let old = std::str::from_utf8(input).unwrap();
    let changed = old.replace("\"op\": \"lt\"", "\"op\": \"eq\"");
    for check in [normalize_document, check_canonical_document] {
        assert!(matches!(
            check(changed.as_bytes(), limits()).unwrap_err(),
            DocumentError::Ir(ContractError::Node(NodeError::Expression(
                ExpressionError::Type {
                    kind: TypeErrorKind::TypeMismatch,
                    ..
                }
            )))
        ));
    }
}

#[test]
fn complete_document_bytes_and_identities_match_independent_component_compositions() {
    for (name, input) in [
        ("node", NODE_INPUT),
        ("contract", CONTRACT_INPUT),
        ("type", TYPE_INPUT),
    ] {
        let result = normalize_document(input, limits()).unwrap();
        assert_eq!(result.canonical_bytes(), golden(name), "{name}");
        assert!(result.canonical_bytes().len() <= input.len());
        let strict = check_canonical_document(result.canonical_bytes(), limits()).unwrap();
        assert_eq!(strict.document_id(), result.document_id());
        assert_eq!(strict.canonical_bytes(), result.canonical_bytes());
    }
    for row in include_str!("fixtures/document-identities/identities.tsv").lines() {
        let parts: Vec<_> = row.split('\t').collect();
        let result = check_canonical_document(golden(parts[0]), limits()).unwrap();
        assert_eq!(result.document_id(), parts[1], "{}", parts[0]);
        assert_ne!(
            result.document_id(),
            parts[2],
            "document identity is not a raw file digest"
        );
        assert_eq!(
            normalize_document(golden(parts[0]), limits()).unwrap(),
            result
        );
    }
}

#[test]
fn all_twelve_candidates_match_committed_ir_bytes_and_manifest_document_digests() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../benchmarks/keyed-finite-table-v0.1");
    let rows = include_str!("fixtures/document-identities/candidates.tsv");
    assert_eq!(rows.lines().count(), 12);
    for row in rows.lines() {
        let parts: Vec<_> = row.split('\t').collect();
        let path = root.join(parts[0]);
        let expected = std::fs::read(&path).unwrap();
        let pretty = std::fs::read(path.with_extension("json")).unwrap();
        let result = normalize_document(&pretty, limits())
            .unwrap_or_else(|error| panic!("{}: {error}", parts[0]));
        assert_eq!(result.canonical_bytes(), expected, "{}", parts[0]);
        assert_eq!(result.document_id(), parts[1]);
        assert_ne!(result.document_id(), parts[2]);
        assert_eq!(
            check_canonical_document(&expected, limits()).unwrap(),
            result
        );
        assert_eq!(
            check_canonical_document(&pretty, limits()).unwrap_err(),
            DocumentError::NonCanonical { offset: 1 }
        );
    }
}

#[test]
fn strict_mode_reports_the_first_byte_difference_for_valid_representation_changes() {
    let bytes = golden("contract");
    let canonical = std::str::from_utf8(bytes).unwrap();
    let position = canonical.find(r#""format":"axiom-ir""#).unwrap() + r#""format":""#.len();
    let escaped_format = canonical.replace(r#""format":"axiom-ir""#, r#""format":"\u0061xiom-ir""#);
    let unicode_position = canonical.find('𐀀').unwrap();
    let escaped_unicode = canonical.replacen('𐀀', "\\ud800\\udc00", 1);
    let variants = [
        (format!(" {canonical}"), 0),
        (format!("{canonical}\n"), bytes.len()),
        (format!("{canonical}\r\n"), bytes.len()),
        (escaped_format, position),
        (escaped_unicode, unicode_position),
    ];
    for (input, offset) in variants {
        assert_eq!(
            normalize_document(input.as_bytes(), limits())
                .unwrap()
                .canonical_bytes(),
            bytes
        );
        assert_eq!(
            check_canonical_document(input.as_bytes(), limits()).unwrap_err(),
            DocumentError::NonCanonical { offset }
        );
    }
    let crlf_pretty = std::str::from_utf8(CONTRACT_INPUT)
        .unwrap()
        .replace('\n', "\r\n");
    assert_eq!(
        normalize_document(crlf_pretty.as_bytes(), limits())
            .unwrap()
            .canonical_bytes(),
        bytes
    );
    assert_eq!(
        check_canonical_document(crlf_pretty.as_bytes(), limits()).unwrap_err(),
        DocumentError::NonCanonical { offset: 1 }
    );
}

#[test]
fn json_canonicalization_is_insufficient_for_ir_semantic_array_and_expression_order() {
    for (name, input) in [
        ("node", NODE_INPUT),
        ("contract", CONTRACT_INPUT),
        ("type", TYPE_INPUT),
    ] {
        let only_json = canonicalize_json(input, limits()).unwrap();
        assert_ne!(only_json, golden(name));
        assert!(matches!(
            check_canonical_document(&only_json, limits()).unwrap_err(),
            DocumentError::NonCanonical { .. }
        ));
        assert_eq!(
            normalize_document(&only_json, limits())
                .unwrap()
                .canonical_bytes(),
            golden(name)
        );
    }
}

#[test]
fn document_domain_and_canonical_bytes_determine_identity_without_self_embedding() {
    let result = normalize_document(CONTRACT_INPUT, limits()).unwrap();
    for row in include_str!("fixtures/document-identities/wrong-hashes.tsv").lines() {
        let (name, wrong) = row.split_once('\t').unwrap();
        assert_ne!(result.document_id(), wrong, "{name}");
    }
    let text = std::str::from_utf8(result.canonical_bytes()).unwrap();
    assert!(!text.contains(result.document_id()));
    let with_digest = text.replacen(
        '{',
        &format!(r#"{{"document_digest":"{}","#, result.document_id()),
        1,
    );
    both_reject(
        &with_digest,
        DocumentError::Ir(ContractError::Node(NodeError::Input(
            DeclarationError::Structure {
                kind: DeclarationErrorKind::UnknownMember,
                path: "/document_digest".to_owned(),
            },
        ))),
    );
}

#[test]
fn interface_names_and_ordered_keys_change_document_identity_while_original_analysis_is_preserved()
{
    let original = normalize_document(TYPE_INPUT, limits()).unwrap();
    let renamed = check_canonical_document(golden("renamed-output"), limits()).unwrap();
    let reordered_key = check_canonical_document(golden("reordered-key"), limits()).unwrap();
    assert_eq!(original.components().nodes(), renamed.components().nodes());
    assert_ne!(original.document_id(), renamed.document_id());
    assert_ne!(original.document_id(), reordered_key.document_id());
    assert_ne!(
        original.components().nodes(),
        reordered_key.components().nodes()
    );
    // 原 nodes 反序；输出分析仍指向原数组，规范输出排序不改写索引语义。
    let node = normalize_document(NODE_INPUT, limits()).unwrap();
    assert_eq!(node.components().analysis().graph().outputs()[0].node, 0);
    assert_eq!(
        node.components().analysis().graph().topological_order(),
        &[4, 5, 3, 2, 1, 0]
    );
    let graph = original.components().analysis().graph();
    assert_eq!(graph.nodes()[0].input_port(), Some("引号\"\\/\u{2028}"));
    // canonical bytes 保留两个枚举成员次序、Option / 记录引用、大整数与复合主键次序。
    assert_eq!(original.canonical_bytes(), golden("type"));
}

#[test]
fn visually_equal_unicode_names_keep_distinct_document_identities() {
    let nfc = check_canonical_document(golden("unicode-nfc"), limits()).unwrap();
    let nfd = check_canonical_document(golden("unicode-nfd"), limits()).unwrap();
    assert_eq!(nfc.components().nodes(), nfd.components().nodes());
    assert_ne!(nfc.document_id(), nfd.document_id());
    let left = std::str::from_utf8(nfc.canonical_bytes()).unwrap();
    let right = std::str::from_utf8(nfd.canonical_bytes()).unwrap();
    assert_eq!(
        left.replace(r#""outputs":[{"name":"é""#, r#""outputs":[{"name":"é""#),
        right
    );
    for (input, expected) in [
        (
            left.replace(
                r#""outputs":[{"name":"é""#,
                r#""outputs":[{"name":"\u00e9""#,
            ),
            &nfc,
        ),
        (
            right.replace(
                r#""outputs":[{"name":"é""#,
                r#""outputs":[{"name":"e\u0301""#,
            ),
            &nfd,
        ),
    ] {
        assert_eq!(
            normalize_document(input.as_bytes(), limits())
                .unwrap()
                .document_id(),
            expected.document_id()
        );
        assert!(matches!(
            check_canonical_document(input.as_bytes(), limits()).unwrap_err(),
            DocumentError::NonCanonical { .. }
        ));
    }
}

#[test]
fn structural_and_identity_errors_are_not_hidden_as_strict_format_differences() {
    for version in ["0.3", "1.0"] {
        both_reject(
            &BASE.replace(
                r#""ir_version": "0.1""#,
                &format!(r#""ir_version": "{version}""#),
            ),
            DocumentError::Ir(ContractError::Node(NodeError::Input(
                DeclarationError::Structure {
                    kind: DeclarationErrorKind::UnsupportedValue,
                    path: "/ir_version".to_owned(),
                },
            ))),
        );
    }
    let unknown = BASE.replacen('{', "{\"metadata\":true,", 1);
    both_reject(
        &unknown,
        DocumentError::Ir(ContractError::Node(NodeError::Input(
            DeclarationError::Structure {
                kind: DeclarationErrorKind::UnknownMember,
                path: "/metadata".to_owned(),
            },
        ))),
    );
    let effects = BASE.replace(r#""effects": []"#, r#""effects": ["network"]"#);
    both_reject(
        &effects,
        DocumentError::Ir(ContractError::Node(NodeError::Input(
            DeclarationError::Structure {
                kind: DeclarationErrorKind::NonEmptyEffects,
                path: "/effects".to_owned(),
            },
        ))),
    );
    let bad_contract = BASE.replace(r#""contracts": []"#, r#""contracts": [false]"#);
    both_reject(
        &bad_contract,
        DocumentError::Ir(ContractError::Input(DeclarationError::Structure {
            kind: DeclarationErrorKind::ExpectedObject,
            path: "/contracts/0".to_owned(),
        })),
    );
    let changed_node = BASE.replace(r#""port": "source""#, r#""port": "renamed""#);
    for check in [normalize_document, check_canonical_document] {
        assert!(
            matches!(check(changed_node.as_bytes(), limits()).unwrap_err(), DocumentError::Ir(ContractError::Node(NodeError::ContentIdMismatch { path, supplied, computed })) if path == "/nodes/5/id" && supplied != computed)
        );
        let fake_contract = contract_document(FALSE, LEXICAL_ID);
        assert!(
            matches!(check(fake_contract.as_bytes(), limits()).unwrap_err(), DocumentError::Ir(ContractError::ContentIdMismatch { path, supplied, computed }) if path == "/contracts/0/id" && supplied == LEXICAL_ID && supplied != computed)
        );
    }
    // 三种前置局部成功均不足以绕过文档层的 input / output 基数和闭合结构。
    let no_nodes = r#"{"contracts":[],"digest_algorithm":"sha-256","effects":[],"enum_types":[],"format":"axiom-ir","ir_version":"0.1","nodes":[],"outputs":[],"record_types":[],"semantics":{"name":"keyed-finite-table-semantics","sha256":"6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"},"table_types":[]}"#;
    both_reject(
        no_nodes,
        DocumentError::Ir(ContractError::Node(NodeError::Structure {
            kind: NodeErrorKind::MissingInput,
            path: "/nodes".to_owned(),
        })),
    );
}

#[test]
fn unsupported_expression_boundaries_survive_both_full_document_entries() {
    for op in ["record", "is_some"] {
        let input = contract_document(
            &format!(r#"{{"op":"and","values":[{FALSE},{{"op":"{op}"}}]}}"#),
            LEXICAL_ID,
        );
        both_reject(
            &input,
            DocumentError::Ir(ContractError::Expression(ExpressionError::Unsupported {
                reason: UnsupportedTyping::UnspecifiedForm,
                path: "/contracts/0/definition/expression/values/1/op".to_owned(),
            })),
        );
    }
    let mixed_int = r#"{"op":"lt","left":{"op":"literal_int","value":"0","type":{"kind":"int","lower":"0","upper":"1"}},"right":{"op":"literal_int","value":"0","type":{"kind":"int","lower":"0","upper":"2"}}}"#;
    // eq 仍明确要求同型，不能因有序比较允许不同范围而放宽。
    both_reject(
        &contract_document(&mixed_int.replace("\"lt\"", "\"eq\""), LEXICAL_ID),
        DocumentError::Ir(ContractError::Expression(ExpressionError::Type {
            kind: TypeErrorKind::TypeMismatch,
            path: "/contracts/0/definition/expression/right".to_owned(),
        })),
    );
    for check in [normalize_document, check_canonical_document] {
        let records = r#"{"op":"forall_rows","table":{"kind":"input","name":"source"},"body":{"op":"eq","left":{"op":"bound","index":"0"},"right":{"op":"bound","index":"0"}}}"#;
        assert!(matches!(
            check(contract_document(records, LEXICAL_ID).as_bytes(), limits()).unwrap_err(),
            DocumentError::Ir(ContractError::Expression(ExpressionError::Unsupported {
                reason: UnsupportedTyping::RecordEquality,
                ..
            }))
        ));
        let direct_key =
            r#""expression":{"field":"𐀀","op":"field","record":{"index":"0","op":"bound"}}"#;
        let read = r#"{"field":"𐀀","op":"field","record":{"index":"0","op":"bound"}}"#;
        let conditional_key = format!(
            r#""expression":{{"op":"if","condition":{TRUE},"then":{read},"else":{read},"result_type":{{"kind":"text"}}}}"#
        );
        let raw = std::str::from_utf8(golden("node")).unwrap();
        let changed = raw.replace(direct_key, &conditional_key);
        assert_ne!(changed, raw);
        assert!(matches!(
            check(changed.as_bytes(), limits()).unwrap_err(),
            DocumentError::Ir(ContractError::Node(
                NodeError::UnsupportedKeyExpression { .. }
            ))
        ));
    }
}

#[test]
fn raw_byte_errors_and_resource_budgets_are_preserved_before_any_document_result() {
    for check in [normalize_document, check_canonical_document] {
        let invalid = [b'{', 0xff];
        assert!(
            matches!(check(&invalid, limits()).unwrap_err(), DocumentError::Ir(ContractError::Input(DeclarationError::Json(error))) if error.kind == JsonErrorKind::InvalidUtf8 && error.offset == 1)
        );
        let duplicate = br#"{"format":"axiom-ir","\u0066ormat":"axiom-ir"}"#;
        assert!(
            matches!(check(duplicate, limits()).unwrap_err(), DocumentError::Ir(ContractError::Input(DeclarationError::Json(error))) if error.kind == JsonErrorKind::DuplicateKey && error.offset == 21)
        );
        let trailing = [golden("node"), b"false"].concat();
        assert!(
            matches!(check(&trailing, limits()).unwrap_err(), DocumentError::Ir(ContractError::Input(DeclarationError::Json(error))) if error.kind == JsonErrorKind::TrailingData && error.offset == golden("node").len())
        );
        for (budget, resource) in [
            (
                JsonLimits {
                    max_input_bytes: 1,
                    ..limits()
                },
                ResourceLimit::InputBytes,
            ),
            (
                JsonLimits {
                    max_values: 1,
                    ..limits()
                },
                ResourceLimit::Values,
            ),
            (
                JsonLimits {
                    max_nesting: 1,
                    ..limits()
                },
                ResourceLimit::Nesting,
            ),
        ] {
            assert!(
                matches!(check(CONTRACT_INPUT, budget).unwrap_err(), DocumentError::Ir(ContractError::Input(DeclarationError::Json(error))) if error.kind == JsonErrorKind::ResourceLimit(resource))
            );
        }
    }
}

#[test]
fn full_document_path_handles_deep_binders_and_limits_raw_wide_expressions_before_reduction() {
    let deep = golden("deep-binders");
    assert_eq!(
        check_canonical_document(deep, limits())
            .unwrap()
            .canonical_bytes(),
        deep
    );
    assert!(
        matches!(normalize_document(deep, JsonLimits { max_nesting: 64, ..limits() }).unwrap_err(), DocumentError::Ir(ContractError::Input(DeclarationError::Json(error))) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Nesting))
    );
    let row = include_str!("fixtures/contract-identities/expected.tsv")
        .lines()
        .find(|line| line.starts_with("false-guarantee\t"))
        .unwrap();
    let id = row.split('\t').nth(1).unwrap();
    let expression = format!(
        r#"{{"op":"or","values":[{}]}}"#,
        vec![FALSE; 10_000].join(",")
    );
    let input = contract_document(&expression, id);
    let small = contract_document(FALSE, id);
    let result = normalize_document(input.as_bytes(), limits()).unwrap();
    assert_eq!(
        result.canonical_bytes(),
        normalize_document(small.as_bytes(), limits())
            .unwrap()
            .canonical_bytes()
    );
    for check in [normalize_document, check_canonical_document] {
        assert!(
            matches!(check(input.as_bytes(), JsonLimits { max_values: 1000, ..limits() }).unwrap_err(), DocumentError::Ir(ContractError::Input(DeclarationError::Json(error))) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Values))
        );
    }
}
