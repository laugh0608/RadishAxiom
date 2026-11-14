use super::*;
use crate::{
    document::{check_canonical_document, normalize_document},
    normalization::content_id,
    version::ContentKind,
};

const CORRECT: &[u8] = include_bytes!("../../tests/fixtures/v0.2/migrated/ax-b01-correct.jcs");
const OLD: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/candidates/correct.ir.jcs"
);
const BASE: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/base.input.json"
);
const BASE_GOLDEN: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/base.golden.json"
);
const BOUNDARY: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/boundary.input.json"
);
const BOUNDARY_GOLDEN: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/boundary.golden.json"
);
const INVALID: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/invalid.input.json"
);

const LIMITS: FixtureLimits = FixtureLimits {
    fixture_json: JsonLimits {
        max_input_bytes: 128 * 1024,
        max_values: 4096,
        max_nesting: 16,
    },
    ir_json: JsonLimits {
        max_input_bytes: 64 * 1024,
        max_values: 4096,
        max_nesting: 64,
    },
    max_tables: 4,
    max_rows: 256,
    max_integer_digits: 64,
    max_precondition_checks: 256,
    max_output_bytes: 128 * 1024,
};

fn digest(bytes: &[u8]) -> String {
    format!("sha256:{}", radishaxiom_digest::digest_hex(bytes))
}

fn correct() -> CanonicalDocument {
    check_canonical_document(CORRECT, LIMITS.ir_json).unwrap()
}

fn check(
    ir: &CanonicalDocument,
    role: FixtureRole,
    bytes: &[u8],
    limits: FixtureLimits,
) -> Result<CheckedFixture, FixtureError> {
    check_fixture(ir, "AX-B01", role, bytes, &digest(bytes), limits)
}

fn projection(tables: &[FixtureTable]) -> Vec<u8> {
    // The checked values are encoded only for comparison with the independent ASCII vectors.
    let value = Value::Array(
        tables
            .iter()
            .map(|table| {
                Value::Object(vec![
                    ("name".into(), Value::String(table.name.clone()), 0),
                    (
                        "rows".into(),
                        Value::Array(
                            table
                                .rows
                                .iter()
                                .map(|row| {
                                    Value::Object(
                                        row.iter()
                                            .map(|(field, value)| {
                                                let text = match value {
                                                    FixtureValue::Int(n) => n.as_str(),
                                                    FixtureValue::Text(s)
                                                    | FixtureValue::Enum(s) => s,
                                                };
                                                (field.clone(), Value::String(text.into()), 0)
                                            })
                                            .collect(),
                                    )
                                })
                                .collect(),
                        ),
                        0,
                    ),
                ])
            })
            .collect(),
    );
    let mut bytes = Vec::new();
    json::encode(&value, &mut bytes);
    bytes
}

#[test]
fn original_samples_match_independent_projections() {
    let ir = correct();
    for (raw, role, expected_digest, expected_size) in [
        (
            BASE,
            FixtureRole::Input,
            "cdf75e9fa4b524bf16836e5007f61e80511a9efe98e97eacb4620c330c0a5a8b",
            273,
        ),
        (
            BASE_GOLDEN,
            FixtureRole::GoldenOutput,
            "01e7ded7d2b992d0aa39ff29769c3454ac97212c0252d2f17a2eddcb4b70bc4f",
            102,
        ),
        (
            BOUNDARY,
            FixtureRole::Input,
            "3dfcac85f47bf6ec8b0bb52385600a5b7870b857c2a36d801b70d65b4ced111d",
            111,
        ),
        (
            BOUNDARY_GOLDEN,
            FixtureRole::GoldenOutput,
            "577ad6d2e25fe4a4e50cdf6ab45455c313c30cfaae252be5570e279f227a692a",
            71,
        ),
    ] {
        let fixture = check(&ir, role, raw, LIMITS).unwrap();
        assert_eq!(fixture.role(), role);
        assert_eq!(fixture.fixture_digest(), digest(raw));
        assert_eq!(
            fixture.ir_document_id(),
            "sha256:90d876b9fdd533944e09f4274ba4aaa313d179454427e60eca81575707054f0b"
        );
        let projected = projection(fixture.tables());
        assert_eq!(projected.len(), expected_size);
        assert_eq!(digest(&projected), format!("sha256:{expected_digest}"));
    }
    let base = check(&ir, FixtureRole::Input, BASE, LIMITS).unwrap();
    let row = &base.tables()[0].rows[0];
    assert!(matches!(&row["discount_cents"], FixtureValue::Int(n) if n.as_str() == "100"));
    assert_eq!(row["order_id"], FixtureValue::Text("O1".into()));
    assert_eq!(row["state"], FixtureValue::Enum("settled".into()));
}

fn members_mut(value: &mut Value) -> &mut Vec<(String, Value, usize)> {
    let Value::Object(members) = value else {
        panic!("expected an object in the test source");
    };
    members
}

fn reversed_precondition(op: &str, keep_original: bool) -> CanonicalDocument {
    let mut ir = json::parse(CORRECT, LIMITS.ir_json).unwrap();
    let Value::Array(contracts) = decode::member_mut(members_mut(&mut ir), "contracts") else {
        panic!("expected contracts");
    };
    let original = &contracts[0];
    let mut bytes = Vec::new();
    json::encode(original, &mut bytes);
    let mut new = json::parse(&bytes, LIMITS.ir_json).unwrap();
    let entry = members_mut(&mut new);
    let definition = decode::member_mut(entry, "definition");
    let expression = decode::member_mut(members_mut(definition), "expression");
    let body = decode::member_mut(members_mut(expression), "body");
    let body = members_mut(body);
    // Preserve object order while swapping operands.
    let left = body.iter().position(|(name, _, _)| name == "left").unwrap();
    let right = body
        .iter()
        .position(|(name, _, _)| name == "right")
        .unwrap();
    body.swap(left, right);
    body[left].0 = "left".into();
    body[right].0 = "right".into();
    *decode::member_mut(body, "op") = Value::String(op.into());
    let mut bytes = Vec::new();
    json::encode(definition, &mut bytes);
    *decode::member_mut(entry, "id") = Value::String(content_id(
        &IrVersion::V0_2.domain(ContentKind::Contract),
        &bytes,
    ));
    if keep_original {
        contracts.push(new);
    } else {
        contracts[0] = new;
    }
    let mut bytes = Vec::new();
    json::encode(&ir, &mut bytes);
    normalize_document(&bytes, LIMITS.ir_json).unwrap()
}

#[test]
fn actual_assumes_control_rejection_and_all_are_required() {
    let ir = correct();
    let expected = FixtureError::Precondition {
        contract: "sha256:49489c1f3a97fcdc66fa15edb16e44fc274987c6d37d7cd5fdf0e2e190b8a7ae".into(),
        table: "orders".into(),
        key: "OX".into(),
        left: "discount_cents".into(),
        right: "subtotal_cents".into(),
    };
    assert_eq!(
        check(&ir, FixtureRole::InvalidInput, INVALID, LIMITS),
        Err(expected.clone())
    );
    let reversed = reversed_precondition("le", false);
    let fixture = check(&reversed, FixtureRole::InvalidInput, INVALID, LIMITS).unwrap();
    assert_ne!(fixture.ir_document_id(), ir.document_id());
    assert_eq!(fixture.fixture_digest(), digest(INVALID));
    let both = reversed_precondition("le", true);
    assert_eq!(
        check(&both, FixtureRole::InvalidInput, INVALID, LIMITS),
        Err(expected)
    );

    let unsupported = reversed_precondition("lt", false);
    assert!(matches!(
        check(
            &unsupported,
            FixtureRole::Input,
            input(&[]).as_bytes(),
            LIMITS
        ),
        Err(FixtureError::Unsupported { .. })
    ));
}

fn order(key: &str) -> String {
    format!(r#"{{"order_id":"{key}","state":"pending","discount_cents":"0","subtotal_cents":"0"}}"#)
}

fn input(rows: &[String]) -> String {
    format!(
        r#"{{"format":"axiom-benchmark-data","data_version":"0.1","benchmark_id":"AX-B01","role":"input","tables":[{{"name":"orders","rows":[{}]}}]}}"#,
        rows.join(",")
    )
}

#[test]
fn text_key_order_uniqueness_and_original_capacity() {
    let ir = correct();
    let ordered = ["O1", "O3", "\u{e000}", "\u{10000}"];
    let reversed = ordered
        .iter()
        .rev()
        .map(|key| order(key))
        .collect::<Vec<_>>();
    let fixture = check(&ir, FixtureRole::Input, input(&reversed).as_bytes(), LIMITS).unwrap();
    let keys = fixture.tables()[0]
        .rows
        .iter()
        .map(|row| key(row, "order_id"))
        .collect::<Vec<_>>();
    assert_eq!(keys, ordered);
    let duplicated = input(&[order("O1"), order("O2"), order("O1")]);
    assert_eq!(
        check(&ir, FixtureRole::Input, duplicated.as_bytes(), LIMITS),
        Err(FixtureError::DuplicateKey {
            table: "orders".into(),
            key: "O1".into()
        })
    );
    let rows = (0..101)
        .map(|n| order(&format!("O{n:03}")))
        .collect::<Vec<_>>();
    assert_eq!(
        check(
            &ir,
            FixtureRole::Input,
            input(&rows[..100]).as_bytes(),
            LIMITS
        )
        .unwrap()
        .tables()[0]
            .rows
            .len(),
        100
    );
    assert_eq!(
        check(&ir, FixtureRole::Input, input(&rows).as_bytes(), LIMITS),
        Err(FixtureError::Capacity {
            table: "orders".into()
        })
    );
}

#[test]
fn uses_all_declared_input_interfaces_in_corpus_table_order() {
    let baseline = correct();
    let components = baseline.components();
    let input_node = components
        .analysis()
        .graph()
        .nodes()
        .iter()
        .find(|node| node.input_port() == Some("orders"))
        .unwrap();
    let original = components
        .nodes()
        .iter()
        .find(|entry| entry.id() == input_node.supplied_id())
        .unwrap();
    let mut node = json::parse(original.canonical_definition(), LIMITS.ir_json).unwrap();
    *decode::member_mut(members_mut(&mut node), "port") = Value::String("spare".into());
    let mut bytes = Vec::new();
    json::encode(&node, &mut bytes);
    let id = content_id(&IrVersion::V0_2.domain(ContentKind::Node), &bytes);
    let mut raw = json::parse(CORRECT, LIMITS.ir_json).unwrap();
    let Value::Array(nodes) = decode::member_mut(members_mut(&mut raw), "nodes") else {
        panic!("expected nodes");
    };
    nodes.push(Value::Object(vec![
        ("definition".into(), node, 0),
        ("id".into(), Value::String(id), 0),
    ]));
    let mut bytes = Vec::new();
    json::encode(&raw, &mut bytes);
    let ir = normalize_document(&bytes, LIMITS.ir_json).unwrap();

    let fixture = |tables: &str| {
        format!(
            r#"{{"format":"axiom-benchmark-data","data_version":"0.1","benchmark_id":"AX-B01","role":"input","tables":[{tables}]}}"#
        )
    };
    let orders = r#"{"name":"orders","rows":[]}"#;
    let spare = r#"{"name":"spare","rows":[]}"#;
    let run = |tables: &str| check(&ir, FixtureRole::Input, fixture(tables).as_bytes(), LIMITS);
    let checked = run(&format!("{orders},{spare}")).unwrap();
    assert_eq!(checked.tables()[0].name, "orders");
    assert_eq!(checked.tables()[1].name, "spare");
    assert_eq!(
        run(orders),
        Err(FixtureError::MissingTable {
            table: "spare".into()
        })
    );
    assert_eq!(
        run(&format!("{orders},{orders}")),
        Err(FixtureError::DuplicateTable {
            table: "orders".into()
        })
    );
    assert_eq!(
        run(&format!("{spare},{orders}")),
        Err(FixtureError::TableOrder {
            previous: "spare".into(),
            table: "orders".into()
        })
    );
}

#[test]
fn binds_role_task_version_and_exact_bytes() {
    let ir = correct();
    let old = check_canonical_document(OLD, LIMITS.ir_json).unwrap();
    assert!(matches!(
        check(&old, FixtureRole::Input, BASE, LIMITS),
        Err(FixtureError::Unsupported { .. })
    ));
    assert_eq!(
        check_fixture(
            &ir,
            "AX-B01",
            FixtureRole::Input,
            BASE,
            &digest(BOUNDARY),
            LIMITS
        ),
        Err(FixtureError::Binding { field: "sha256" })
    );
    assert_eq!(
        check_fixture(
            &ir,
            "AX-B02",
            FixtureRole::Input,
            BASE,
            &digest(BASE),
            LIMITS
        ),
        Err(FixtureError::Binding {
            field: "benchmark_id"
        })
    );
    assert_eq!(
        check(&ir, FixtureRole::Input, INVALID, LIMITS),
        Err(FixtureError::Binding { field: "role" })
    );
    let new_version = std::str::from_utf8(BASE)
        .unwrap()
        .replace("\"0.1\"", "\"0.2\"");
    assert_eq!(
        check(&ir, FixtureRole::Input, new_version.as_bytes(), LIMITS),
        Err(FixtureError::Binding {
            field: "data_version"
        })
    );
}

#[test]
fn closed_shapes_values_and_golden_schema() {
    let ir = correct();
    let raw = std::str::from_utf8(BOUNDARY).unwrap();
    for (raw, kind) in [
        (
            raw.replace("\"settled\"", "\"unknown\""),
            FixtureValueError::UnknownEnumMember,
        ),
        (
            raw.replace("\"100000\"", "\"100001\""),
            FixtureValueError::IntegerRange,
        ),
        (
            raw.replace("\"100000\"", "\"010000\""),
            FixtureValueError::IntegerSyntax,
        ),
    ] {
        assert!(matches!(
            check(&ir, FixtureRole::Input, raw.as_bytes(), LIMITS),
            Err(FixtureError::InvalidValue { kind: got, .. }) if got == kind
        ));
    }
    let extra = raw.replace("\"state\"", "\"extra\": \"extra\", \"state\"");
    assert!(matches!(
        check(&ir, FixtureRole::Input, extra.as_bytes(), LIMITS),
        Err(FixtureError::Structure(DeclarationError::Structure {
            kind: DeclarationErrorKind::UnknownMember,
            ..
        }))
    ));
    let duplicate = raw.replace("\"state\"", "\"state\": \"settled\", \"state\"");
    assert!(matches!(
        check(&ir, FixtureRole::Input, duplicate.as_bytes(), LIMITS),
        Err(FixtureError::Json(JsonError {
            kind: JsonErrorKind::DuplicateKey,
            ..
        }))
    ));
    let golden = std::str::from_utf8(BOUNDARY_GOLDEN).unwrap();
    let wrong_but_well_typed = golden.replace("\"100000\"", "\"99999\"");
    assert!(
        check(
            &ir,
            FixtureRole::GoldenOutput,
            wrong_but_well_typed.as_bytes(),
            LIMITS
        )
        .is_ok()
    );
    let wrong_type = golden.replace("\"100000\"", "\"100001\"");
    assert!(matches!(
        check(
            &ir,
            FixtureRole::GoldenOutput,
            wrong_type.as_bytes(),
            LIMITS
        ),
        Err(FixtureError::InvalidValue {
            kind: FixtureValueError::IntegerRange,
            ..
        })
    ));
}

#[test]
fn exhaustion_never_returns_a_conformance_result() {
    let ir = correct();
    for (limits, resource) in [
        (
            FixtureLimits {
                max_tables: 0,
                ..LIMITS
            },
            FixtureResource::Tables,
        ),
        (
            FixtureLimits {
                max_rows: 0,
                ..LIMITS
            },
            FixtureResource::Rows,
        ),
        (
            FixtureLimits {
                max_integer_digits: 5,
                ..LIMITS
            },
            FixtureResource::IntegerDigits,
        ),
        (
            FixtureLimits {
                max_precondition_checks: 0,
                ..LIMITS
            },
            FixtureResource::PreconditionChecks,
        ),
        (
            FixtureLimits {
                max_output_bytes: 204,
                ..LIMITS
            },
            FixtureResource::OutputBytes,
        ),
    ] {
        assert_eq!(
            check(&ir, FixtureRole::Input, BOUNDARY, limits),
            Err(FixtureError::Resource(resource))
        );
    }
    let exact = FixtureLimits {
        max_rows: 1,
        max_integer_digits: 6,
        max_precondition_checks: 1,
        max_output_bytes: 205,
        ..LIMITS
    };
    assert!(check(&ir, FixtureRole::Input, BOUNDARY, exact).is_ok());
    let no_work = FixtureLimits {
        max_precondition_checks: 0,
        ..LIMITS
    };
    assert_eq!(
        check(&ir, FixtureRole::InvalidInput, INVALID, no_work),
        Err(FixtureError::Resource(FixtureResource::PreconditionChecks))
    );
    let tiny = FixtureLimits {
        fixture_json: JsonLimits {
            max_nesting: 2,
            ..LIMITS.fixture_json
        },
        ..LIMITS
    };
    assert!(matches!(
        check(&ir, FixtureRole::Input, BOUNDARY, tiny),
        Err(FixtureError::Resource(FixtureResource::FixtureJson(
            JsonError {
                kind: JsonErrorKind::ResourceLimit(json::ResourceLimit::Nesting),
                ..
            }
        )))
    ));
}
