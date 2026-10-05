use radishaxiom_ir::declarations::{
    DeclarationError, DeclarationErrorKind as InputKind, ValueType,
};
use radishaxiom_ir::expressions::{
    ExpressionError, RowScope, RowTypeChecker, TypeErrorKind as Kind, UnsupportedTyping,
};
use radishaxiom_ir::integer::Integer;
use radishaxiom_ir::json::{JsonErrorKind, JsonLimits, ResourceLimit};
use radishaxiom_ir::normalization::{NormalizedTypeDeclarations, normalize_type_declarations};

const BOOL: &str = r#"{"op":"literal_bool","value":true}"#;
const TEXT: &str = r#"{"op":"literal_text","value":"text"}"#;
const BOOL_TYPE: &str = r#"{"kind":"bool"}"#;
const TEXT_TYPE: &str = r#"{"kind":"text"}"#;

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 1024 * 1024,
        max_values: 100_000,
        max_nesting: 128,
    }
}
fn types() -> NormalizedTypeDeclarations {
    normalize_type_declarations(
        include_bytes!("fixtures/type-identities/input.json"),
        limits(),
    )
    .unwrap()
}
fn int_type(lower: &str, upper: &str) -> ValueType {
    ValueType::Int {
        lower: Integer::parse(lower).unwrap(),
        upper: Integer::parse(upper).unwrap(),
    }
}
fn int_json(lower: &str, upper: &str) -> String {
    format!(r#"{{"kind":"int","lower":"{lower}","upper":"{upper}"}}"#)
}
fn int(lower: &str, upper: &str, value: &str) -> String {
    format!(
        r#"{{"op":"literal_int","type":{},"value":"{value}"}}"#,
        int_json(lower, upper)
    )
}
fn fixed_type(scale: &str, lower: &str, upper: &str) -> String {
    format!(r#"{{"kind":"fixed","scale":"{scale}","lower":"{lower}","upper":"{upper}"}}"#)
}
fn fixed(scale: &str, lower: &str, upper: &str, coefficient: &str) -> String {
    format!(
        r#"{{"op":"literal_fixed","type":{},"coefficient":"{coefficient}"}}"#,
        fixed_type(scale, lower, upper)
    )
}
fn field(index: usize, field: &str) -> String {
    format!(r#"{{"op":"field","record":{{"op":"bound","index":"{index}"}},"field":"{field}"}}"#)
}
fn some(value: &str) -> String {
    format!(r#"{{"op":"some","value":{value}}}"#)
}
fn match_option(subject: &str, none: &str, some: &str, result_type: &str) -> String {
    format!(
        r#"{{"op":"match_option","subject":{subject},"none":{none},"some":{some},"result_type":{result_type}}}"#
    )
}
fn binary(op: &str, left: &str, right: &str) -> String {
    format!(r#"{{"op":"{op}","left":{left},"right":{right}}}"#)
}
fn closed(checker: &RowTypeChecker<'_>, input: &str) -> Result<ValueType, ExpressionError> {
    checker.infer(input.as_bytes(), limits(), RowScope::Closed)
}
fn rejects(checker: &RowTypeChecker<'_>, input: &str, kind: Kind, path: &str) {
    assert_eq!(
        closed(checker, input).unwrap_err(),
        ExpressionError::Type {
            kind,
            path: path.to_owned()
        }
    );
}

#[test]
fn literals_and_option_constructors_have_exact_types() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    assert_eq!(closed(&checker, BOOL).unwrap(), ValueType::Bool);
    assert_eq!(
        closed(
            &checker,
            r#"{"op":"literal_text","value":"\u0000é\ud83d\ude00"}"#
        )
        .unwrap(),
        ValueType::Text
    );
    let upper = "9007199254740993123456789";
    assert_eq!(
        closed(&checker, &int("-9007199254740993123456789", upper, upper)).unwrap(),
        int_type("-9007199254740993123456789", upper)
    );
    assert_eq!(
        closed(
            &checker,
            &fixed("99999999999999999999999", "-10", "-9", "-10")
        )
        .unwrap(),
        ValueType::Fixed {
            scale: Integer::parse("99999999999999999999999").unwrap(),
            lower: Integer::parse("-10").unwrap(),
            upper: Integer::parse("-9").unwrap()
        }
    );
    let id = types.enum_types()[0].id();
    assert_eq!(
        closed(
            &checker,
            &format!(r#"{{"op":"literal_enum","enum_type":"{id}","member":"z"}}"#)
        )
        .unwrap(),
        ValueType::Enum {
            enum_type: id.to_owned()
        }
    );
    assert_eq!(
        closed(
            &checker,
            r#"{"op":"none","type":{"kind":"option","inner":{"kind":"bool"}}}"#
        )
        .unwrap(),
        ValueType::Option {
            inner: Box::new(ValueType::Bool)
        }
    );
    assert_eq!(
        closed(&checker, &some(&some(BOOL))).unwrap(),
        ValueType::Option {
            inner: Box::new(ValueType::Option {
                inner: Box::new(ValueType::Bool)
            })
        }
    );
}

#[test]
fn invalid_literals_and_type_annotations_are_rejected() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    rejects(
        &checker,
        r#"{"op":"literal_bool","value":"true"}"#,
        Kind::ExpectedBoolean,
        "/value",
    );
    rejects(
        &checker,
        &int("0", "9007199254740992", "9007199254740993"),
        Kind::LiteralOutOfRange,
        "/value",
    );
    rejects(
        &checker,
        &fixed("2", "-10", "0", "1"),
        Kind::LiteralOutOfRange,
        "/coefficient",
    );
    rejects(
        &checker,
        r#"{"op":"literal_int","type":{"kind":"text"},"value":"0"}"#,
        Kind::ExpectedInt,
        "/type",
    );
    rejects(
        &checker,
        r#"{"op":"literal_fixed","type":{"kind":"bool"},"coefficient":"0"}"#,
        Kind::ExpectedFixed,
        "/type",
    );
    rejects(
        &checker,
        r#"{"op":"none","type":{"kind":"text"}}"#,
        Kind::ExpectedOption,
        "/type",
    );
    let id = types.enum_types()[0].id();
    rejects(
        &checker,
        &format!(r#"{{"op":"literal_enum","enum_type":"{id}","member":"absent"}}"#),
        Kind::UnknownEnumMember,
        "/member",
    );
    assert_eq!(
        closed(&checker, &int("2", "1", "1")).unwrap_err(),
        ExpressionError::Input(DeclarationError::Structure {
            kind: InputKind::ReversedRange,
            path: "/type".to_owned()
        })
    );
    assert_eq!(
        closed(&checker, &int("0", "1", "-0")).unwrap_err(),
        ExpressionError::Input(DeclarationError::Structure {
            kind: InputKind::InvalidInteger,
            path: "/value".to_owned()
        })
    );
    let missing = format!(
        r#"{{"op":"none","type":{{"kind":"option","inner":{{"kind":"enum","enum_type":"sha256:{}"}}}}}}"#,
        "0".repeat(64)
    );
    assert_eq!(
        closed(&checker, &missing).unwrap_err(),
        ExpressionError::Input(DeclarationError::Structure {
            kind: InputKind::UnresolvedReference,
            path: "/type/inner/enum_type".to_owned()
        })
    );
}

#[test]
fn row_scopes_resolve_records_fields_and_join_positions() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    let main = types
        .record_types()
        .iter()
        .find(|entry| entry.definition().fields.len() == 7)
        .unwrap()
        .id();
    let leaf = types
        .record_types()
        .iter()
        .find(|entry| entry.definition().fields.len() == 4)
        .unwrap()
        .id();
    let scope = RowScope::Join {
        left_record_type: main,
        right_record_type: leaf,
    };
    for (index, id) in [(0, main), (1, leaf)] {
        assert_eq!(
            checker
                .infer(
                    format!(r#"{{"op":"bound","index":"{index}"}}"#).as_bytes(),
                    limits(),
                    scope
                )
                .unwrap(),
            ValueType::Record {
                record_type: id.to_owned()
            }
        );
    }
    assert_eq!(
        checker
            .infer(field(0, "key").as_bytes(), limits(), scope)
            .unwrap(),
        ValueType::Text
    );
    assert_eq!(
        checker
            .infer(field(1, "𐀀").as_bytes(), limits(), scope)
            .unwrap(),
        ValueType::Text
    );
    let nested = format!(
        r#"{{"op":"field","field":"é","record":{}}}"#,
        field(0, "nested")
    );
    assert_eq!(
        checker
            .infer(
                nested.as_bytes(),
                limits(),
                RowScope::Single { record_type: main }
            )
            .unwrap(),
        ValueType::Text
    );
    assert_eq!(
        checker
            .infer(field(1, "key").as_bytes(), limits(), scope)
            .unwrap_err(),
        ExpressionError::Type {
            kind: Kind::UnknownField,
            path: "/field".to_owned()
        }
    );
    assert!(matches!(
        checker
            .infer(
                BOOL.as_bytes(),
                limits(),
                RowScope::Single {
                    record_type: "unknown"
                }
            )
            .unwrap_err(),
        ExpressionError::UnknownScopeRecord { slot: 0, .. }
    ));
    rejects(
        &checker,
        r#"{"op":"bound","index":"9999999999999999999999999999999"}"#,
        Kind::BoundOutOfRange,
        "/index",
    );
    rejects(
        &checker,
        &format!(r#"{{"op":"field","field":"a","record":{BOOL}}}"#),
        Kind::ExpectedRecord,
        "/record",
    );
}

#[test]
fn match_binders_shift_outer_rows_and_do_not_leak_between_branches() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    let main = types
        .record_types()
        .iter()
        .find(|entry| entry.definition().fields.len() == 7)
        .unwrap()
        .id();
    let leaf = types
        .record_types()
        .iter()
        .find(|entry| entry.definition().fields.len() == 4)
        .unwrap()
        .id();
    let scope = RowScope::Join {
        left_record_type: main,
        right_record_type: leaf,
    };
    let inner = match_option(&some(BOOL), &field(1, "key"), &field(3, "𐀀"), TEXT_TYPE);
    let expression = match_option(&some(TEXT), &field(1, "𐀀"), &inner, TEXT_TYPE);
    assert_eq!(
        checker
            .infer(expression.as_bytes(), limits(), scope)
            .unwrap(),
        ValueType::Text
    );
    let current = match_option(
        &some(BOOL),
        BOOL,
        r#"{"op":"bound","index":"0"}"#,
        BOOL_TYPE,
    );
    assert_eq!(closed(&checker, &current).unwrap(), ValueType::Bool);
    // none 分支不会得到 some binder；不能根据已知 Some 常量跳过它的检查。
    rejects(
        &checker,
        &match_option(
            &some(BOOL),
            r#"{"op":"bound","index":"0"}"#,
            BOOL,
            BOOL_TYPE,
        ),
        Kind::BoundOutOfRange,
        "/none/index",
    );
    rejects(
        &checker,
        &match_option(&some(BOOL), BOOL, TEXT, BOOL_TYPE),
        Kind::TypeMismatch,
        "/some",
    );
    rejects(
        &checker,
        &match_option(BOOL, BOOL, BOOL, BOOL_TYPE),
        Kind::ExpectedOption,
        "/subject",
    );
    assert_eq!(closed(&checker, &current).unwrap(), ValueType::Bool);
}

#[test]
fn all_boolean_operands_and_both_conditional_branches_are_checked() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    assert_eq!(
        closed(&checker, &format!(r#"{{"op":"not","value":{BOOL}}}"#)).unwrap(),
        ValueType::Bool
    );
    for op in ["and", "or"] {
        assert_eq!(
            closed(
                &checker,
                &format!(r#"{{"op":"{op}","values":[{BOOL},{BOOL},{BOOL}]}}"#)
            )
            .unwrap(),
            ValueType::Bool
        );
        rejects(
            &checker,
            &format!(r#"{{"op":"{op}","values":[{BOOL}]}}"#),
            Kind::WrongArity,
            "/values",
        );
        rejects(
            &checker,
            &format!(r#"{{"op":"{op}","values":[{{"op":"literal_bool","value":false}},{TEXT}]}}"#),
            Kind::TypeMismatch,
            "/values/1",
        );
    }
    let if_text = format!(
        r#"{{"op":"if","condition":{BOOL},"then":{TEXT},"else":{TEXT},"result_type":{TEXT_TYPE}}}"#
    );
    assert_eq!(closed(&checker, &if_text).unwrap(), ValueType::Text);
    let invalid = format!(
        r#"{{"op":"if","condition":{BOOL},"then":{BOOL},"else":{TEXT},"result_type":{BOOL_TYPE}}}"#
    );
    rejects(&checker, &invalid, Kind::TypeMismatch, "/else");
    rejects(
        &checker,
        &invalid.replace(
            &format!("\"condition\":{BOOL}"),
            &format!("\"condition\":{TEXT}"),
        ),
        Kind::TypeMismatch,
        "/condition",
    );
}

#[test]
fn arithmetic_checks_type_and_scale_but_does_not_discharge_range_obligations() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    let one = int("0", "1", "1");
    // 1+1 肯定不在 [0,0]，但类型推导不能代替后续范围义务；不得改写结果类型。
    let addition = format!(
        r#"{{"op":"int_add","values":[{one},{one}],"result_type":{}}}"#,
        int_json("0", "0")
    );
    assert_eq!(closed(&checker, &addition).unwrap(), int_type("0", "0"));
    let subtraction = format!(
        r#"{{"op":"int_sub","left":{one},"right":{one},"result_type":{}}}"#,
        int_json("-1", "1")
    );
    assert_eq!(closed(&checker, &subtraction).unwrap(), int_type("-1", "1"));
    rejects(
        &checker,
        &addition.replace(&format!("[{one},{one}]"), &format!("[{one}]")),
        Kind::WrongArity,
        "/values",
    );
    rejects(
        &checker,
        &subtraction.replace(
            &format!("\"right\":{one}"),
            &format!("\"right\":{}", int("0", "2", "1")),
        ),
        Kind::TypeMismatch,
        "/right",
    );
    let left = fixed("2", "-1", "0", "0");
    let right = fixed("2", "0", "1", "1");
    for op in ["fixed_add", "fixed_sub"] {
        let args = if op.ends_with("add") {
            format!(r#""values":[{left},{right}]"#)
        } else {
            format!(r#""left":{left},"right":{right}"#)
        };
        let expression = format!(
            r#"{{"op":"{op}",{args},"result_type":{}}}"#,
            fixed_type("2", "0", "0")
        );
        assert_eq!(
            closed(&checker, &expression).unwrap(),
            ValueType::Fixed {
                scale: Integer::parse("2").unwrap(),
                lower: Integer::parse("0").unwrap(),
                upper: Integer::parse("0").unwrap()
            }
        );
        rejects(
            &checker,
            &expression.replacen("\"scale\":\"2\"", "\"scale\":\"3\"", 1),
            Kind::ScaleMismatch,
            if op.ends_with("add") {
                "/values/1"
            } else {
                "/right"
            },
        );
    }
}

#[test]
fn int_ordering_accepts_distinct_bounds_without_conversion_or_rewriting() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    let large = "99999999999999999999999999999999999999999999999999";
    let cases = [
        int("0", "1", "0"),
        int("0", "100", "1"),
        int("-100", "-1", "-1"),
        int("0", "0", "0"),
        int(large, large, large),
        int(&format!("-{large}"), "-1", "-1"),
    ];
    for op in ["lt", "le", "gt", "ge"] {
        for left in &cases {
            for right in &cases {
                let expression = binary(op, left, right);
                assert_eq!(closed(&checker, &expression).unwrap(), ValueType::Bool);
                let expected = format!(r#"{{"left":{left},"op":"{op}","right":{right}}}"#);
                assert_eq!(
                    checker
                        .normalize(expression.as_bytes(), limits(), RowScope::Closed)
                        .unwrap()
                        .canonical_bytes(),
                    expected.as_bytes()
                );
                assert_eq!(
                    checker
                        .analyze_labels(expression.as_bytes(), limits(), RowScope::Closed)
                        .unwrap()
                        .label(),
                    radishaxiom_ir::declarations::Label::Public
                );
            }
        }
        rejects(
            &checker,
            &binary(op, &cases[0], &fixed("0", "0", "1", "0")),
            Kind::TypeMismatch,
            "/right",
        );
        rejects(
            &checker,
            &binary(op, &cases[0], BOOL),
            Kind::TypeMismatch,
            "/right",
        );
        rejects(
            &checker,
            &binary(op, &some(&cases[0]), &some(&cases[1])),
            Kind::ExpectedNumeric,
            "/left",
        );
        rejects(
            &checker,
            &binary(op, &int("0", "1", "2"), &cases[1]),
            Kind::LiteralOutOfRange,
            "/left/value",
        );
    }
    rejects(
        &checker,
        &binary("eq", &cases[0], &cases[1]),
        Kind::TypeMismatch,
        "/right",
    );
    let sum = format!(
        r#"{{"op":"int_add","values":[{},{}],"result_type":{}}}"#,
        cases[0],
        cases[1],
        int_json("0", "101")
    );
    rejects(&checker, &sum, Kind::TypeMismatch, "/values/1");
}

#[test]
fn equality_is_nominal_and_ordering_is_numeric() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    let zero = int("0", "1", "0");
    for op in ["eq", "lt", "le", "gt", "ge"] {
        assert_eq!(
            closed(&checker, &binary(op, &zero, &zero)).unwrap(),
            ValueType::Bool
        );
    }
    assert_eq!(
        closed(&checker, &binary("eq", &some(TEXT), &some(TEXT))).unwrap(),
        ValueType::Bool
    );
    assert_eq!(
        closed(
            &checker,
            &binary(
                "lt",
                &fixed("2", "-1", "0", "0"),
                &fixed("2", "0", "1", "1")
            )
        )
        .unwrap(),
        ValueType::Bool
    );
    rejects(
        &checker,
        &binary("lt", TEXT, TEXT),
        Kind::ExpectedNumeric,
        "/left",
    );
    rejects(
        &checker,
        &binary("eq", &zero, &int("0", "2", "0")),
        Kind::TypeMismatch,
        "/right",
    );
    let enum_literal = |index: usize| {
        format!(
            r#"{{"op":"literal_enum","enum_type":"{}","member":"a"}}"#,
            types.enum_types()[index].id()
        )
    };
    rejects(
        &checker,
        &binary("eq", &enum_literal(0), &enum_literal(1)),
        Kind::TypeMismatch,
        "/right",
    );
    assert_eq!(
        closed(&checker, &binary("lt", &zero, &int("0", "2", "0"))).unwrap(),
        ValueType::Bool
    );
    let scope = RowScope::Single {
        record_type: types.record_types()[0].id(),
    };
    let bound = r#"{"op":"bound","index":"0"}"#;
    assert_eq!(
        checker
            .infer(binary("eq", bound, bound).as_bytes(), limits(), scope)
            .unwrap_err(),
        ExpressionError::Unsupported {
            reason: UnsupportedTyping::RecordEquality,
            path: "".to_owned()
        }
    );
}

#[test]
fn closed_shapes_forbidden_contract_operations_and_unsupported_forms_are_distinct() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    rejects(
        &checker,
        r#"{"op":"int_mul"}"#,
        Kind::UnknownOperator,
        "/op",
    );
    for op in [
        "forall_rows",
        "exists_rows",
        "lookup",
        "count_where",
        "sum_where",
    ] {
        rejects(
            &checker,
            &format!(r#"{{"op":"{op}"}}"#),
            Kind::ContractOperationInRow,
            "/op",
        );
    }
    for op in ["record", "is_some"] {
        assert_eq!(
            closed(&checker, &format!(r#"{{"op":"{op}"}}"#)).unwrap_err(),
            ExpressionError::Unsupported {
                reason: UnsupportedTyping::UnspecifiedForm,
                path: "/op".to_owned()
            }
        );
    }
    for key in ["inferred_type", "label", "effects"] {
        let expression = format!(r#"{{"op":"literal_bool","value":true,"{key}":true}}"#);
        assert_eq!(
            closed(&checker, &expression).unwrap_err(),
            ExpressionError::Input(DeclarationError::Structure {
                kind: InputKind::UnknownMember,
                path: format!("/{key}")
            })
        );
    }
    assert_eq!(
        closed(&checker, r#"{"op":"literal_int","value":"1"}"#).unwrap_err(),
        ExpressionError::Input(DeclarationError::Structure {
            kind: InputKind::MissingMember,
            path: "/type".to_owned()
        })
    );
}

#[test]
fn json_and_resource_failures_are_preserved() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    let maximum = format!(
        "{}{}{}",
        r#"{"op":"some","value":"#.repeat(127),
        BOOL,
        "}".repeat(127)
    );
    let result = closed(&checker, &maximum).unwrap();
    let mut value_type = &result;
    let mut count = 0;
    while let ValueType::Option { inner } = value_type {
        value_type = inner;
        count += 1;
    }
    assert_eq!(count, 127);
    assert_eq!(value_type, &ValueType::Bool);
    assert!(
        matches!(closed(&checker, r#"{"op":"literal_int","value":0}"#).unwrap_err(), ExpressionError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::NumberOrNull)
    );
    let expression = format!(
        "{}{}{}",
        r#"{"op":"some","value":"#.repeat(1000),
        BOOL,
        "}".repeat(1000)
    );
    assert!(
        matches!(closed(&checker, &expression).unwrap_err(), ExpressionError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Nesting))
    );
    assert!(
        matches!(checker.infer(BOOL.as_bytes(), JsonLimits { max_input_bytes: 1, ..limits() }, RowScope::Closed).unwrap_err(), ExpressionError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::InputBytes))
    );
}

#[test]
fn deepest_recursive_operator_paths_fit_the_json_nesting_budget() {
    let types = types();
    let checker = RowTypeChecker::new(&types);
    for op in [
        "not",
        "eq",
        "if",
        "match_option",
        "and",
        "int_sub",
        "fixed_sub",
    ] {
        let numeric = op.ends_with("sub");
        let (leaf, ty, expected, depth) = match op {
            "int_sub" => (
                int("0", "1", "1"),
                int_json("0", "1"),
                int_type("0", "1"),
                126,
            ),
            "fixed_sub" => (
                fixed("2", "0", "1", "1"),
                fixed_type("2", "0", "1"),
                ValueType::Fixed {
                    scale: Integer::parse("2").unwrap(),
                    lower: Integer::parse("0").unwrap(),
                    upper: Integer::parse("1").unwrap(),
                },
                126,
            ),
            "match_option" => (BOOL.to_owned(), BOOL_TYPE.to_owned(), ValueType::Bool, 126),
            "and" => (BOOL.to_owned(), BOOL_TYPE.to_owned(), ValueType::Bool, 63),
            _ => (BOOL.to_owned(), BOOL_TYPE.to_owned(), ValueType::Bool, 127),
        };
        // 两侧 / 两分支分别作为最深路径，避免只覆盖首个递归调用。
        for deep_first in [true, false] {
            let mut expression = leaf.clone();
            for _ in 0..depth {
                let (left, right) = if deep_first {
                    (expression.as_str(), leaf.as_str())
                } else {
                    (leaf.as_str(), expression.as_str())
                };
                expression = match op {
                    "not" => format!(r#"{{"op":"not","value":{expression}}}"#),
                    "eq" => binary("eq", left, right),
                    "if" => format!(
                        r#"{{"op":"if","condition":{BOOL},"then":{left},"else":{right},"result_type":{ty}}}"#
                    ),
                    "match_option" => match_option(&some(BOOL), left, right, &ty),
                    "and" => format!(r#"{{"op":"and","values":[{left},{right}]}}"#),
                    _ if numeric => format!(
                        r#"{{"op":"{op}","left":{left},"right":{right},"result_type":{ty}}}"#
                    ),
                    _ => unreachable!(),
                };
            }
            assert_eq!(
                closed(&checker, &expression).unwrap(),
                expected,
                "{op}, {deep_first}"
            );
            let analysis = checker
                .analyze_labels(expression.as_bytes(), limits(), RowScope::Closed)
                .unwrap();
            assert_eq!(analysis.value_type(), &expected);
            assert_eq!(
                analysis.label(),
                radishaxiom_ir::declarations::Label::Public
            );
        }
    }
}
