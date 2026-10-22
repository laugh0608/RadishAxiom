use super::*;
use crate::contracts::ContractError;
use crate::declarations::{
    self as decode, DeclarationError, DeclarationErrorKind as InputKind, Label, ValueType,
};
use crate::document::{DocumentError, check_canonical_document, normalize_document};
use crate::expressions::{
    ExpressionError, RowScope, RowTypeChecker, TypeErrorKind as TypeKind, UnsupportedTyping,
};
use crate::json::{self, JsonErrorKind, JsonLimits, ResourceLimit, Value};
use crate::nodes::{NodeError, NodeErrorKind, analyze_node_graph};
use crate::normalization::{content_id, normalize_type_declarations};

const INPUT: &[u8] = include_bytes!("../../tests/fixtures/v0.2/records-input.json");
const CANONICAL: &[u8] = include_bytes!("../../tests/fixtures/v0.2/records.jcs");
const FALSE: &str = r#"{"op":"literal_bool","value":false}"#;

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16 * 1024 * 1024,
        max_values: 1_000_000,
        max_nesting: 128,
    }
}
fn id(name: &str) -> &str {
    include_str!("../../tests/fixtures/v0.2/record-ids.tsv")
        .lines()
        .filter_map(|row| row.split_once('\t'))
        .find(|(key, _)| *key == name)
        .unwrap()
        .1
}
fn parsed(input: &[u8]) -> Value {
    json::parse(input, limits()).unwrap()
}
fn bytes(value: &Value) -> Vec<u8> {
    let mut bytes = vec![];
    json::encode(value, &mut bytes);
    bytes
}
fn at_mut<'a>(mut value: &'a mut Value, path: &[&str]) -> &'a mut Value {
    for key in path {
        value = match value {
            Value::Array(values) => &mut values[key.parse::<usize>().unwrap()],
            Value::Object(members) => decode::member_mut(members, key),
            _ => panic!("fixture path"),
        };
    }
    value
}
fn array(value: &mut Value) -> &mut Vec<Value> {
    let Value::Array(values) = value else {
        panic!("fixture array")
    };
    values
}
fn set(value: &mut Value, key: &str, new: Value) {
    let Value::Object(members) = value else {
        panic!("fixture object")
    };
    if let Some((_, value, _)) = members.iter_mut().find(|(name, _, _)| name == key) {
        *value = new;
    } else {
        members.push((key.to_owned(), new, 0));
    }
    members.sort_by(|left, right| left.0.encode_utf16().cmp(right.0.encode_utf16()));
}
fn text(value: &str) -> Value {
    Value::String(value.to_owned())
}
fn field(name: &str, index: &str) -> Value {
    parsed(
        format!(r#"{{"op":"field","field":"{name}","record":{{"op":"bound","index":"{index}"}}}}"#)
            .as_bytes(),
    )
}
fn record() -> Value {
    let row = include_str!("../../tests/fixtures/v0.2/record-expressions.tsv")
        .lines()
        .next()
        .unwrap();
    parsed(row.split('\t').nth(2).unwrap().as_bytes())
}
fn type_error(kind: TypeKind, path: &str) -> ExpressionError {
    ExpressionError::Type {
        kind,
        path: path.to_owned(),
    }
}
fn input_error(kind: InputKind, path: &str) -> ExpressionError {
    ExpressionError::Input(DeclarationError::Structure {
        kind,
        path: path.to_owned(),
    })
}
fn both_reject(value: &Value, expected: DocumentError) {
    for check in [normalize_document, check_canonical_document] {
        assert_eq!(check(&bytes(value), limits()).unwrap_err(), expected);
    }
}

#[test]
fn record_construction_matches_independent_types_bytes_labels_and_document_identity() {
    let types = normalize_type_declarations(INPUT, limits()).unwrap();
    assert_eq!(types.version(), IrVersion::V0_2);
    let checker = RowTypeChecker::new(&types);
    let scope = RowScope::Single {
        record_type: id("row"),
    };
    for row in include_str!("../../tests/fixtures/v0.2/record-expressions.tsv").lines() {
        let fields: Vec<_> = row.split('\t').collect();
        let expected_type = match fields[0] {
            "record" => ValueType::Record {
                record_type: id("leaf").to_owned(),
            },
            "nested" => ValueType::Record {
                record_type: id("wrapper").to_owned(),
            },
            _ => ValueType::Bool,
        };
        let expression = checker
            .normalize(fields[1].as_bytes(), limits(), scope)
            .unwrap();
        assert_eq!(
            expression.canonical_bytes(),
            fields[2].as_bytes(),
            "{}",
            fields[0]
        );
        assert_eq!(expression.value_type(), &expected_type);
        assert_eq!(
            checker
                .normalize(expression.canonical_bytes(), limits(), scope)
                .unwrap(),
            expression
        );
        let label = checker
            .analyze_labels(fields[1].as_bytes(), limits(), scope)
            .unwrap();
        assert_eq!(
            label.label(),
            if fields[4] == "public" {
                Label::Public
            } else {
                Label::Sensitive
            }
        );
    }
    let document = normalize_document(INPUT, limits()).unwrap();
    assert_eq!(document.canonical_bytes(), CANONICAL);
    assert_eq!(
        document.document_id(),
        include_str!("../../tests/fixtures/v0.2/records-document-id.txt").trim()
    );
    assert!(matches!(
        check_canonical_document(INPUT, limits()).unwrap_err(),
        DocumentError::NonCanonical { .. }
    ));
    let strict = check_canonical_document(CANONICAL, limits()).unwrap();
    assert_eq!(strict.document_id(), document.document_id());
    let graph = document.components().analysis().graph();
    let output = graph.outputs()[0].node;
    assert_eq!(graph.node_flows()[output].row_control(), Label::Public);
    let labels = graph.node_flows()[output].field_labels();
    assert_eq!(labels["built"], Label::Sensitive);
    assert_eq!(labels["maybe"], Label::Sensitive);
    assert_eq!(labels["public"], Label::Public);
    assert_eq!(labels["key"], Label::Public);
    assert_eq!(graph.node_flows()[output].label_gaps().len(), 2);
}

#[test]
fn record_fields_are_closed_complete_unique_and_exactly_typed_before_normalization() {
    let types = normalize_type_declarations(INPUT, limits()).unwrap();
    let checker = RowTypeChecker::new(&types);
    let scope = RowScope::Single {
        record_type: id("row"),
    };
    let mut cases = vec![];
    let mut value = record();
    array(at_mut(&mut value, &["fields"])).pop();
    cases.push((value, type_error(TypeKind::IncompleteFields, "/fields")));
    let mut value = record();
    let duplicate = parsed(&bytes(at_mut(&mut value, &["fields", "0"])));
    array(at_mut(&mut value, &["fields"])).push(duplicate);
    cases.push((
        value,
        input_error(InputKind::DuplicateName, "/fields/2/name"),
    ));
    let mut value = record();
    *at_mut(&mut value, &["fields", "0", "name"]) = text("missing");
    cases.push((value, type_error(TypeKind::UnknownField, "/fields/0/name")));
    let mut value = record();
    set(
        at_mut(&mut value, &["fields", "0"]),
        "cached_type",
        parsed(br#"{"kind":"bool"}"#),
    );
    cases.push((
        value,
        input_error(InputKind::UnknownMember, "/fields/0/cached_type"),
    ));
    let mut value = record();
    let Value::Object(members) = at_mut(&mut value, &["fields", "0"]) else {
        panic!()
    };
    members
        .iter_mut()
        .find(|(key, _, _)| key == "expression")
        .unwrap()
        .0 = "value".to_owned();
    cases.push((
        value,
        input_error(InputKind::UnknownMember, "/fields/0/value"),
    ));
    let mut value = record();
    *at_mut(&mut value, &["fields", "0", "expression"]) =
        parsed(br#"{"op":"literal_text","value":"false"}"#);
    cases.push((
        value,
        type_error(TypeKind::TypeMismatch, "/fields/0/expression"),
    ));
    let mut value = record();
    *at_mut(&mut value, &["record_type"]) = text(&format!("sha256:{}", "0".repeat(64)));
    cases.push((
        value,
        input_error(InputKind::UnresolvedReference, "/record_type"),
    ));
    let mut value = record();
    *at_mut(&mut value, &["fields", "1", "expression"]) = field("flag", "1");
    cases.push((
        value,
        type_error(
            TypeKind::BoundOutOfRange,
            "/fields/1/expression/record/index",
        ),
    ));
    for (value, expected) in cases {
        let input = bytes(&value);
        assert_eq!(
            checker.infer(&input, limits(), scope).unwrap_err(),
            expected
        );
        assert_eq!(
            checker.normalize(&input, limits(), scope).unwrap_err(),
            expected
        );
        assert_eq!(
            checker.analyze_labels(&input, limits(), scope).unwrap_err(),
            expected
        );
    }
    let mut value = record();
    *at_mut(&mut value, &["fields", "0", "expression"]) = parsed(br#"{"op":"is_some"}"#);
    let access = format!(
        r#"{{"op":"field","field":"visible","record":{}}}"#,
        String::from_utf8(bytes(&value)).unwrap()
    );
    assert_eq!(
        checker
            .normalize(access.as_bytes(), limits(), scope)
            .unwrap_err(),
        type_error(TypeKind::UnknownOperator, "/record/fields/0/expression/op")
    );
}

#[test]
fn v02_rejections_do_not_reinterpret_v01_unsupported_forms() {
    let v02 = normalize_type_declarations(INPUT, limits()).unwrap();
    let v01 = normalize_type_declarations(
        include_bytes!("../../tests/fixtures/type-identities/input.json"),
        limits(),
    )
    .unwrap();
    let old = RowTypeChecker::new(&v01);
    let new = RowTypeChecker::new(&v02);
    for op in ["record", "is_some"] {
        let expression = format!(r#"{{"op":"{op}"}}"#);
        assert_eq!(
            old.infer(expression.as_bytes(), limits(), RowScope::Closed)
                .unwrap_err(),
            ExpressionError::Unsupported {
                reason: UnsupportedTyping::UnspecifiedForm,
                path: "/op".to_owned()
            }
        );
    }
    assert_eq!(
        new.infer(br#"{"op":"is_some"}"#, limits(), RowScope::Closed)
            .unwrap_err(),
        type_error(TypeKind::UnknownOperator, "/op")
    );
    let mut operand = r#"{"op":"bound","index":"0"}"#.to_owned();
    for _ in 0..3 {
        let expression = format!(r#"{{"op":"eq","left":{operand},"right":{operand}}}"#);
        assert_eq!(
            new.infer(
                expression.as_bytes(),
                limits(),
                RowScope::Single {
                    record_type: id("row")
                }
            )
            .unwrap_err(),
            type_error(TypeKind::NonEquatableType, "")
        );
        assert_eq!(
            old.infer(
                expression.as_bytes(),
                limits(),
                RowScope::Single {
                    record_type: v01.record_types()[0].id()
                }
            )
            .unwrap_err(),
            ExpressionError::Unsupported {
                reason: UnsupportedTyping::RecordEquality,
                path: "".to_owned()
            }
        );
        operand = format!(r#"{{"op":"some","value":{operand}}}"#);
    }
    let presence = br#"{"op":"match_option","subject":{"op":"none","type":{"kind":"option","inner":{"kind":"bool"}}},"none":{"op":"literal_bool","value":false},"some":{"op":"literal_bool","value":true},"result_type":{"kind":"bool"}}"#;
    assert_eq!(
        new.infer(presence, limits(), RowScope::Closed).unwrap(),
        ValueType::Bool
    );
    assert_eq!(
        new.analyze_labels(presence, limits(), RowScope::Closed)
            .unwrap()
            .label(),
        Label::Public
    );
}

#[test]
fn version_semantics_and_identity_domains_cannot_be_mixed() {
    for (path, new, kind, expected_path) in [
        (
            vec!["ir_version"],
            "0.3",
            InputKind::UnsupportedValue,
            "/ir_version",
        ),
        (
            vec!["ir_version"],
            "1.0",
            InputKind::UnsupportedValue,
            "/ir_version",
        ),
        (
            vec!["ir_version"],
            "0.1",
            InputKind::UnsupportedValue,
            "/semantics/sha256",
        ),
        (
            vec!["semantics", "sha256"],
            V0_1_SEMANTICS_SHA256,
            InputKind::UnsupportedValue,
            "/semantics/sha256",
        ),
    ] {
        let mut doc = parsed(CANONICAL);
        *at_mut(&mut doc, &path) = text(new);
        both_reject(
            &doc,
            DocumentError::Ir(ContractError::Node(NodeError::Input(
                DeclarationError::Structure {
                    kind,
                    path: expected_path.to_owned(),
                },
            ))),
        );
    }
    // 只替换旧版 header 不构成迁移；声明仍使用旧域，目标真实身份核对会拒绝。
    let mut old = parsed(include_bytes!(
        "../../tests/fixtures/document-identities/type.jcs"
    ));
    *at_mut(&mut old, &["ir_version"]) = text("0.2");
    *at_mut(&mut old, &["semantics", "sha256"]) = text(V0_2_SEMANTICS_SHA256);
    for check in [normalize_document, check_canonical_document] {
        assert!(matches!(
            check(&bytes(&old), limits()).unwrap_err(),
            DocumentError::Ir(ContractError::Node(NodeError::Input(
                DeclarationError::ContentIdMismatch { .. }
            )))
        ));
    }
}

#[test]
fn v02_rejects_complex_keys_and_record_join_pairs_before_identity_checks() {
    let mut doc = parsed(CANONICAL);
    // canonical fixture 的第二个节点为 map；直接字段键改为同值 if 仍非法。
    let key = at_mut(
        &mut doc,
        &["nodes", "1", "definition", "fields", "1", "expression"],
    );
    let direct = String::from_utf8(bytes(key)).unwrap();
    *key = parsed(format!(r#"{{"op":"if","condition":{FALSE},"then":{direct},"else":{direct},"result_type":{{"kind":"text"}}}}"#).as_bytes());
    both_reject(
        &doc,
        DocumentError::Ir(ContractError::Node(NodeError::Structure {
            kind: NodeErrorKind::InvalidKeyProjection,
            path: "/nodes/1/definition/fields/1/expression".to_owned(),
        })),
    );
    for payload in ["built", "maybe"] {
        let mut doc = parsed(CANONICAL);
        let fields = ["built", "key", "maybe", "public"]
            .map(|name| {
                format!(
                    r#"{{"name":"{name}","expression":{}}}"#,
                    String::from_utf8(bytes(&field(name, "0"))).unwrap()
                )
            })
            .join(",");
        let new_id = format!("sha256:{}", "f".repeat(64));
        let join = format!(
            r#"{{"id":"{new_id}","definition":{{"kind":"lookup_join","left":"{}","right":"{}","table_type":"{}","pairs":[{{"left":"{payload}","right":"{payload}"}}],"fields":[{fields}]}}}}"#,
            id("map"),
            id("map"),
            id("output-table")
        );
        array(at_mut(&mut doc, &["nodes"])).push(parsed(join.as_bytes()));
        *at_mut(&mut doc, &["outputs", "0", "node"]) = text(&new_id);
        both_reject(
            &doc,
            DocumentError::Ir(ContractError::Node(NodeError::Structure {
                kind: NodeErrorKind::NonEquatablePair,
                path: "/nodes/2/definition/pairs/0".to_owned(),
            })),
        );
        *at_mut(
            &mut doc,
            &["nodes", "2", "definition", "pairs", "0", "left"],
        ) = text("public");
        *at_mut(
            &mut doc,
            &["nodes", "2", "definition", "pairs", "0", "right"],
        ) = text("public");
        assert!(analyze_node_graph(&bytes(&doc), limits()).is_ok());
    }
}

#[test]
fn record_errors_in_contracts_and_original_resource_limits_remain_visible() {
    let mut doc = parsed(CANONICAL);
    *at_mut(
        &mut doc,
        &[
            "contracts",
            "0",
            "definition",
            "expression",
            "body",
            "some",
            "record",
            "fields",
            "1",
            "expression",
            "record",
            "index",
        ],
    ) = text("2");
    both_reject(
        &doc,
        DocumentError::Ir(ContractError::Expression(type_error(
            TypeKind::BoundOutOfRange,
            "/contracts/0/definition/expression/body/some/record/fields/1/expression/record/index",
        ))),
    );
    for budget in [
        JsonLimits {
            max_input_bytes: INPUT.len() - 1,
            ..limits()
        },
        JsonLimits {
            max_values: 100,
            ..limits()
        },
        JsonLimits {
            max_nesting: 10,
            ..limits()
        },
    ] {
        assert!(
            matches!(normalize_document(INPUT, budget).unwrap_err(), DocumentError::Ir(ContractError::Input(DeclarationError::Json(error))) if matches!(error.kind, JsonErrorKind::ResourceLimit(_)))
        );
    }
}

// 以下 helper 仅构造输入身份；独立期望由上方 Python 向量核对，不能当作独立摘要实现。
fn declaration(
    doc: &mut Value,
    collection: &str,
    kind: ContentKind,
    definition: Value,
    version: IrVersion,
) -> String {
    let identity = content_id(&version.domain(kind), &bytes(&definition));
    let entry = format!(
        r#"{{"id":"{identity}","definition":{}}}"#,
        String::from_utf8(bytes(&definition)).unwrap()
    );
    array(at_mut(doc, &[collection])).push(parsed(entry.as_bytes()));
    identity
}

#[test]
fn record_constructor_depth_uses_the_same_json_budget_and_preserves_declared_dependencies() {
    let mut doc = parsed(CANONICAL);
    let mut ty = r#"{"kind":"bool"}"#.to_owned();
    let mut expression = FALSE.to_owned();
    for _ in 0..42 {
        let definition = parsed(
            format!(r#"{{"fields":[{{"name":"inner","type":{ty},"label":"sensitive"}}]}}"#)
                .as_bytes(),
        );
        let identity = declaration(
            &mut doc,
            "record_types",
            ContentKind::RecordType,
            definition,
            IrVersion::V0_2,
        );
        ty = format!(r#"{{"kind":"record","record_type":"{identity}"}}"#);
        expression = format!(
            r#"{{"op":"record","record_type":"{identity}","fields":[{{"name":"inner","expression":{expression}}}]}}"#
        );
    }
    let types = normalize_type_declarations(&bytes(&doc), limits()).unwrap();
    let checker = RowTypeChecker::new(&types);
    let normalized = checker
        .normalize(expression.as_bytes(), limits(), RowScope::Closed)
        .unwrap();
    assert_eq!(
        checker
            .analyze_labels(expression.as_bytes(), limits(), RowScope::Closed)
            .unwrap()
            .label(),
        Label::Sensitive
    );
    assert!(normalized.canonical_bytes().len() <= expression.len());
    let budget = JsonLimits {
        max_nesting: 126,
        ..limits()
    };
    assert!(
        matches!(checker.infer(expression.as_bytes(), budget, RowScope::Closed).unwrap_err(), ExpressionError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Nesting))
    );
}

#[test]
fn migration_rekeys_deep_record_and_node_dags_without_reference_recursion() {
    let mut doc = parsed(CANONICAL);
    for collection in [
        "enum_types",
        "record_types",
        "table_types",
        "nodes",
        "contracts",
        "outputs",
    ] {
        *at_mut(&mut doc, &[collection]) = Value::Array(vec![]);
    }
    *at_mut(&mut doc, &["ir_version"]) = text("0.1");
    *at_mut(&mut doc, &["semantics", "sha256"]) = text(V0_1_SEMANTICS_SHA256);
    let count = 5_000;
    let mut ty = r#"{"kind":"bool"}"#.to_owned();
    let mut record_id = String::new();
    for _ in 0..count {
        let definition = parsed(format!(r#"{{"fields":[{{"name":"child","type":{ty},"label":"public"}},{{"name":"key","type":{{"kind":"text"}},"label":"public"}}]}}"#).as_bytes());
        record_id = declaration(
            &mut doc,
            "record_types",
            ContentKind::RecordType,
            definition,
            IrVersion::V0_1,
        );
        ty = format!(r#"{{"kind":"record","record_type":"{record_id}"}}"#);
    }
    let table = declaration(
        &mut doc,
        "table_types",
        ContentKind::TableType,
        parsed(
            format!(r#"{{"capacity":"1","primary_key":["key"],"record_type":"{record_id}"}}"#)
                .as_bytes(),
        ),
        IrVersion::V0_1,
    );
    let mut node = declaration(
        &mut doc,
        "nodes",
        ContentKind::Node,
        parsed(format!(r#"{{"kind":"input","port":"source","table_type":"{table}"}}"#).as_bytes()),
        IrVersion::V0_1,
    );
    for _ in 0..count {
        node = declaration(&mut doc, "nodes", ContentKind::Node,
            parsed(format!(r#"{{"kind":"filter","source":"{node}","table_type":"{table}","predicate":{FALSE}}}"#).as_bytes()), IrVersion::V0_1);
    }
    array(at_mut(&mut doc, &["outputs"])).push(parsed(
        format!(r#"{{"name":"result","node":"{node}"}}"#).as_bytes(),
    ));
    let source = normalize_document(&bytes(&doc), limits()).unwrap();
    drop(doc);
    let migrated =
        crate::migration::migrate_v0_1_to_v0_2(source.canonical_bytes(), limits()).unwrap();
    let mappings = migrated.record().mappings();
    assert_eq!(
        mappings
            .iter()
            .filter(|entry| entry.kind() == ContentKind::RecordType)
            .count(),
        count
    );
    assert_eq!(
        mappings
            .iter()
            .filter(|entry| entry.kind() == ContentKind::Node)
            .count(),
        count + 1
    );
    assert!(
        mappings
            .iter()
            .all(|entry| entry.source() != entry.target())
    );
    assert_eq!(
        migrated.target().canonical_bytes().len(),
        source.canonical_bytes().len()
    );
    assert_eq!(
        migrated
            .target()
            .components()
            .analysis()
            .graph()
            .nodes()
            .len(),
        count + 1
    );
}
