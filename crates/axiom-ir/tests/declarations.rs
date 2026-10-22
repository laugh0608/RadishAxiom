use radishaxiom_ir::declarations::{
    DeclarationError, DeclarationErrorKind as Kind, Label, UnverifiedTypeDeclarations, ValueType,
    decode_type_declarations,
};
use radishaxiom_ir::json::{JsonErrorKind, JsonLimits, ResourceLimit};

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 4 * 1024 * 1024,
        max_values: 500_000,
        max_nesting: 128,
    }
}

// 这些合成 ID 只满足词法，不伪装为 definition 的真实摘要。
fn id(index: usize) -> String {
    format!("sha256:{index:064x}")
}

fn declaration(index: usize, definition: &str) -> String {
    format!(r#"{{"definition":{definition},"id":"{}"}}"#, id(index))
}

fn candidate(enums: &str, records: &str, tables: &str) -> String {
    // 版本与摘要为人工固定期望，不导入实现的常量生成测试输入。
    format!(
        r#"{{"contracts":[],"digest_algorithm":"sha-256","effects":[],"enum_types":[{enums}],"format":"axiom-ir","ir_version":"0.1","nodes":[],"outputs":[],"record_types":[{records}],"semantics":{{"name":"keyed-finite-table-semantics","sha256":"6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"}},"table_types":[{tables}]}}"#
    )
}

fn field(name_json: &str, label: &str, value_type: &str) -> String {
    format!(r#"{{"name":{name_json},"label":"{label}","type":{value_type}}}"#)
}

fn record(index: usize, fields: &str) -> String {
    declaration(index, &format!(r#"{{"fields":[{fields}]}}"#))
}

fn table(index: usize, record: usize, keys: &str, capacity: &str) -> String {
    declaration(
        index,
        &format!(
            r#"{{"capacity":"{capacity}","primary_key":[{keys}],"record_type":"{}"}}"#,
            id(record)
        ),
    )
}

fn decode(text: &str) -> UnverifiedTypeDeclarations {
    decode_type_declarations(text.as_bytes(), limits()).unwrap()
}

fn rejects(text: &str, kind: Kind, path: &str) {
    assert_eq!(
        decode_type_declarations(text.as_bytes(), limits()).unwrap_err(),
        DeclarationError::Structure {
            kind,
            path: path.to_owned()
        }
    );
}

fn one_type(value_type: &str) -> String {
    candidate("", &record(1, &field(r#""key""#, "public", value_type)), "")
}

#[test]
fn header_is_closed_and_exactly_version_bound() {
    let base = candidate("", "", "");
    rejects("[]", Kind::ExpectedObject, "");
    for (from, to, path) in [
        ("\"axiom-ir\"", "\"other\"", "/format"),
        ("\"0.1\"", "\"0.3\"", "/ir_version"),
        ("\"0.1\"", "\"1.0\"", "/ir_version"),
        ("\"sha-256\"", "\"sha256\"", "/digest_algorithm"),
        (
            "\"keyed-finite-table-semantics\"",
            "\"latest\"",
            "/semantics/name",
        ),
        ("6b18d65e", "6b18d65f", "/semantics/sha256"),
    ] {
        rejects(&base.replacen(from, to, 1), Kind::UnsupportedValue, path);
    }
    rejects(
        &base.replace("\"ir_version\":\"0.1\",", ""),
        Kind::MissingMember,
        "/ir_version",
    );
    rejects(
        &base.replace("\"format\":\"axiom-ir\",", "\"format\":true,"),
        Kind::ExpectedString,
        "/format",
    );
    rejects(
        &base.replacen('{', "{\"a~/\":true,", 1),
        Kind::UnknownMember,
        "/a~0~1",
    );
    rejects(
        &base.replace("\"semantics\":{", "\"semantics\":{\"latest\":true,"),
        Kind::UnknownMember,
        "/semantics/latest",
    );
    rejects(
        &base.replace("\"effects\":[]", "\"effects\":[\"io\"]"),
        Kind::NonEmptyEffects,
        "/effects",
    );
    for key in [
        "contracts",
        "nodes",
        "outputs",
        "effects",
        "enum_types",
        "record_types",
        "table_types",
    ] {
        rejects(
            &base.replace(&format!("\"{key}\":[]"), &format!("\"{key}\":{{}}")),
            Kind::ExpectedArray,
            &format!("/{key}"),
        );
    }
}

#[test]
fn all_inline_types_and_nominal_enum_members_are_preserved() {
    let enums = declaration(1, r#"{"name":"阶段","members":["z","a","é","e\u0301"]}"#);
    let leaf = record(2, &field(r#""leaf""#, "public", r#"{"kind":"text"}"#));
    let type_texts = [
        r#"{"kind":"bool"}"#.to_owned(),
        r#"{"kind":"text"}"#.to_owned(),
        r#"{"kind":"int","lower":"-9007199254740993","upper":"9007199254740993"}"#.to_owned(),
        r#"{"kind":"fixed","lower":"-10","upper":"-9","scale":"100000000000000000000000"}"#
            .to_owned(),
        format!(r#"{{"kind":"enum","enum_type":"{}"}}"#, id(1)),
        format!(r#"{{"kind":"record","record_type":"{}"}}"#, id(2)),
        format!(
            r#"{{"kind":"option","inner":{{"kind":"option","inner":{{"kind":"record","record_type":"{}"}}}}}}"#,
            id(2)
        ),
    ];
    let fields = type_texts
        .iter()
        .enumerate()
        .map(|(index, ty)| {
            field(
                &format!("\"f{index}\""),
                if index == 6 { "sensitive" } else { "public" },
                ty,
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let main = record(3, &fields);
    // 前向引用与非 ID 排序合法；后续规范器才排序，输入顺序有诊断价值。
    let result = decode(&candidate(
        &enums,
        &format!("{main},{leaf}"),
        &table(4, 3, r#""f4","f0""#, "0"),
    ));
    assert_eq!(result.enum_types[0].definition.name, "阶段");
    assert_eq!(
        result.enum_types[0].definition.members,
        ["z", "a", "é", "e\u{301}"]
    );
    let fields = &result.record_types[0].definition.fields;
    assert_eq!(fields[0].value_type, ValueType::Bool);
    assert_eq!(fields[1].value_type, ValueType::Text);
    let ValueType::Int { lower, upper } = &fields[2].value_type else {
        panic!("int")
    };
    assert_eq!(lower.as_str(), "-9007199254740993");
    assert_eq!(upper.as_str(), "9007199254740993");
    let ValueType::Fixed { scale, .. } = &fields[3].value_type else {
        panic!("fixed")
    };
    assert_eq!(scale.as_str(), "100000000000000000000000");
    assert_eq!(fields[6].label, Label::Sensitive);
    assert_eq!(result.table_types[0].definition.primary_key, ["f4", "f0"]);
    assert_eq!(result.table_types[0].definition.capacity.as_str(), "0");
}

#[test]
fn type_shapes_are_closed_and_do_not_accept_host_numeric_shortcuts() {
    let path = "/record_types/0/definition/fields/0/type";
    for (ty, kind, suffix) in [
        (r#"{"kind":"float"}"#, Kind::UnsupportedValue, "/kind"),
        (
            r#"{"kind":"bool","lower":"0"}"#,
            Kind::UnknownMember,
            "/lower",
        ),
        (
            r#"{"kind":"text","extra":false}"#,
            Kind::UnknownMember,
            "/extra",
        ),
        (
            r#"{"kind":"int","lower":"0"}"#,
            Kind::MissingMember,
            "/upper",
        ),
        (
            r#"{"kind":"int","lower":"01","upper":"9"}"#,
            Kind::InvalidInteger,
            "/lower",
        ),
        (
            r#"{"kind":"int","lower":"0","upper":"-0"}"#,
            Kind::InvalidInteger,
            "/upper",
        ),
        (
            r#"{"kind":"int","lower":"9007199254740993","upper":"9007199254740992"}"#,
            Kind::ReversedRange,
            "",
        ),
        (
            r#"{"kind":"fixed","scale":"-1","lower":"0","upper":"1"}"#,
            Kind::NegativeInteger,
            "/scale",
        ),
        (
            r#"{"kind":"fixed","scale":"1e3","lower":"0","upper":"1"}"#,
            Kind::InvalidInteger,
            "/scale",
        ),
        (r#"{"kind":"option"}"#, Kind::MissingMember, "/inner"),
        (
            r#"{"kind":"option","inner":{"kind":"unrecognized"}}"#,
            Kind::UnsupportedValue,
            "/inner/kind",
        ),
        (
            r#"{"kind":"enum","enum_type":"latest"}"#,
            Kind::InvalidId,
            "/enum_type",
        ),
        (
            r#"{"kind":"record","record_type":true}"#,
            Kind::ExpectedString,
            "/record_type",
        ),
        (r#"{"inner":{"kind":"bool"}}"#, Kind::MissingMember, "/kind"),
        (r#"[]"#, Kind::ExpectedObject, ""),
    ] {
        rejects(&one_type(ty), kind, &format!("{path}{suffix}"));
    }
}

#[test]
fn declaration_shapes_ids_and_nonempty_unique_collections_are_enforced() {
    let good = declaration(1, r#"{"name":"E","members":["a"]}"#);
    let base = candidate(&good, "", "");
    for bad in [
        "sha256:ab".to_owned(),
        format!("sha256:{}", "A".repeat(64)),
        "0".repeat(64),
    ] {
        rejects(
            &base.replace(&id(1), &bad),
            Kind::InvalidId,
            "/enum_types/0/id",
        );
    }
    rejects(
        &candidate(&format!("{good},{good}"), "", ""),
        Kind::DuplicateId,
        "/enum_types/1/id",
    );
    rejects(
        &candidate(&declaration(1, r#"{"name":"E","members":[]}"#), "", ""),
        Kind::EmptyCollection,
        "/enum_types/0/definition/members",
    );
    rejects(
        &candidate(
            &declaration(1, r#"{"name":"E","members":["a","\u0061"]}"#),
            "",
            "",
        ),
        Kind::DuplicateName,
        "/enum_types/0/definition/members/1",
    );
    rejects(
        &candidate(&good.replace("\"name\":\"E\",", ""), "", ""),
        Kind::MissingMember,
        "/enum_types/0/definition/name",
    );
    rejects(
        &candidate(
            &good.replace("\"definition\":{", "\"extra\":true,\"definition\":{"),
            "",
            "",
        ),
        Kind::UnknownMember,
        "/enum_types/0/extra",
    );
    rejects(
        &candidate("", &record(1, ""), ""),
        Kind::EmptyCollection,
        "/record_types/0/definition/fields",
    );
    let f = field(r#""a""#, "public", r#"{"kind":"bool"}"#);
    rejects(
        &candidate("", &record(1, &format!("{f},{f}")), ""),
        Kind::DuplicateName,
        "/record_types/0/definition/fields/1/name",
    );
    rejects(
        &candidate("", &record(1, &f.replace("public", "secret")), ""),
        Kind::UnsupportedValue,
        "/record_types/0/definition/fields/0/label",
    );
    rejects(
        &candidate("", &record(1, &f.replace("\"label\":\"public\",", "")), ""),
        Kind::MissingMember,
        "/record_types/0/definition/fields/0/label",
    );
    let records = record(1, &f);
    for (keys, capacity, kind, suffix) in [
        ("", "0", Kind::EmptyCollection, "/primary_key"),
        (r#""a","a""#, "0", Kind::DuplicateName, "/primary_key/1"),
        (r#""a""#, "-1", Kind::NegativeInteger, "/capacity"),
        (r#""a""#, "00", Kind::InvalidInteger, "/capacity"),
    ] {
        rejects(
            &candidate("", &records, &table(2, 1, keys, capacity)),
            kind,
            &format!("/table_types/0/definition{suffix}"),
        );
    }
}

#[test]
fn names_use_exact_unicode_scalars_and_reject_c0_c1() {
    for name in [
        r#""""#.to_owned(),
        (0..=0x1f)
            .map(|c| format!("\\u{c:04x}"))
            .collect::<String>(),
    ] {
        let name = if name.starts_with('"') {
            name
        } else {
            format!("\"{name}\"")
        };
        rejects(
            &candidate(
                "",
                &record(1, &field(&name, "public", r#"{"kind":"text"}"#)),
                "",
            ),
            Kind::InvalidName,
            "/record_types/0/definition/fields/0/name",
        );
    }
    for scalar in (0..=0x1f).chain(0x80..=0x9f) {
        let en = declaration(
            1,
            &format!(r#"{{"name":"E\u{scalar:04x}","members":["a"]}}"#),
        );
        rejects(
            &candidate(&en, "", ""),
            Kind::InvalidName,
            "/enum_types/0/definition/name",
        );
    }
    // 不进行 NFC、大小写折叠或把语义名称按 UTF-16 重排。
    let names = [
        r#""é""#,
        r#""e\u0301""#,
        r#""A""#,
        r#""a""#,
        r#""\ue000""#,
        r#""\ud800\udc00""#,
    ];
    let fields = names
        .iter()
        .map(|n| field(n, "public", r#"{"kind":"text"}"#))
        .collect::<Vec<_>>()
        .join(",");
    let result = decode(&candidate("", &record(1, &fields), ""));
    assert_eq!(
        result.record_types[0]
            .definition
            .fields
            .iter()
            .map(|f| f.name.as_str())
            .collect::<Vec<_>>(),
        ["é", "e\u{301}", "A", "a", "\u{e000}", "\u{10000}"]
    );
}

#[test]
fn references_are_kind_specific_and_record_cycles_are_rejected() {
    let enum_ref = format!(
        r#"{{"kind":"option","inner":{{"kind":"enum","enum_type":"{}"}}}}"#,
        id(1)
    );
    rejects(
        &one_type(&enum_ref),
        Kind::UnresolvedReference,
        "/record_types/0/definition/fields/0/type/inner/enum_type",
    );
    let reference = |index| format!(r#"{{"kind":"record","record_type":"{}"}}"#, id(index));
    rejects(
        &one_type(&reference(99)),
        Kind::UnresolvedReference,
        "/record_types/0/definition/fields/0/type/record_type",
    );
    rejects(
        &one_type(&reference(1)),
        Kind::RecursiveRecord,
        "/record_types",
    );
    let first = record(1, &field(r#""next""#, "public", &reference(2)));
    let second = record(
        2,
        &field(
            r#""next""#,
            "public",
            &format!(r#"{{"kind":"option","inner":{}}}"#, reference(1)),
        ),
    );
    rejects(
        &candidate("", &format!("{first},{second}"), ""),
        Kind::RecursiveRecord,
        "/record_types",
    );
    rejects(
        &candidate("", "", &table(1, 99, r#""key""#, "0")),
        Kind::UnresolvedReference,
        "/table_types/0/definition/record_type",
    );
}

#[test]
fn primary_keys_require_existing_public_nonoptional_scalar_fields() {
    for (name, label, ty) in [
        (r#""other""#, "public", r#"{"kind":"text"}"#),
        (r#""key""#, "sensitive", r#"{"kind":"text"}"#),
        (
            r#""key""#,
            "public",
            r#"{"kind":"option","inner":{"kind":"text"}}"#,
        ),
    ] {
        rejects(
            &candidate(
                "",
                &record(1, &field(name, label, ty)),
                &table(2, 1, r#""key""#, "1"),
            ),
            Kind::InvalidPrimaryKey,
            "/table_types/0/definition/primary_key/0",
        );
    }
    let record_ref = format!(r#"{{"kind":"record","record_type":"{}"}}"#, id(2));
    let nested = record(2, &field(r#""leaf""#, "public", r#"{"kind":"text"}"#));
    let outer = record(1, &field(r#""key""#, "public", &record_ref));
    rejects(
        &candidate(
            "",
            &format!("{outer},{nested}"),
            &table(3, 1, r#""key""#, "1"),
        ),
        Kind::InvalidPrimaryKey,
        "/table_types/0/definition/primary_key/0",
    );
    for ty in [
        r#"{"kind":"bool"}"#,
        r#"{"kind":"text"}"#,
        r#"{"kind":"int","lower":"-1","upper":"1"}"#,
        r#"{"kind":"fixed","scale":"0","lower":"0","upper":"1"}"#,
    ] {
        decode(&candidate(
            "",
            &record(1, &field(r#""key""#, "public", ty)),
            &table(
                2,
                1,
                r#""key""#,
                "99999999999999999999999999999999999999999999",
            ),
        ));
    }
}

#[test]
fn declaration_reference_depth_is_not_native_stack_depth() {
    let count = 5000;
    let records = (0..count)
        .map(|index| {
            let ty = if index + 1 == count {
                r#"{"kind":"text"}"#.to_owned()
            } else {
                format!(r#"{{"kind":"record","record_type":"{}"}}"#, id(index + 1))
            };
            record(index, &field(r#""next""#, "public", &ty))
        })
        .collect::<Vec<_>>()
        .join(",");
    let input = candidate("", &records, "");
    assert_eq!(decode(&input).record_types.len(), count);
    let cycle = input.replace(
        r#"{"kind":"text"}"#,
        &format!(r#"{{"kind":"record","record_type":"{}"}}"#, id(0)),
    );
    rejects(&cycle, Kind::RecursiveRecord, "/record_types");
}

#[test]
fn json_errors_and_resource_exhaustion_remain_distinct() {
    let input = one_type(r#"{"kind":"text"}"#);
    let error = decode_type_declarations(
        input.as_bytes(),
        JsonLimits {
            max_values: 10,
            ..limits()
        },
    )
    .unwrap_err();
    assert!(
        matches!(error, DeclarationError::Json(ref e) if e.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Values))
    );
    let invalid = input.replace("\"kind\":\"text\"", "\"kind\":null");
    assert!(
        matches!(decode_type_declarations(invalid.as_bytes(), limits()).unwrap_err(), DeclarationError::Json(ref e) if e.kind == JsonErrorKind::NumberOrNull)
    );
    let nested = format!(
        "{}{}{}",
        r#"{"kind":"option","inner":"#.repeat(100),
        r#"{"kind":"text"}"#,
        "}".repeat(100)
    );
    assert!(
        matches!(decode_type_declarations(one_type(&nested).as_bytes(), JsonLimits { max_nesting: 16, ..limits() }).unwrap_err(), DeclarationError::Json(ref e) if e.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Nesting))
    );
}

#[test]
fn partial_decoder_never_claims_full_ir_or_id_acceptance() {
    // 没有 input/output、虚构 ID 及未检查的节点均仍可解码声明；结果类型显式为 Unverified。
    let input =
        one_type(r#"{"kind":"text"}"#).replace("\"nodes\":[]", "\"nodes\":[{\"not_a_node\":true}]");
    assert_eq!(decode(&input).record_types[0].supplied_id, id(1));
    assert_eq!(decode(&candidate("", "", "")).record_types.len(), 0);
}

#[test]
fn four_task_candidates_decode_actual_declarations_including_wrong_algorithms() {
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
    for (task, candidate) in cases {
        let stem = root.join(task).join("candidates").join(candidate);
        let pretty = std::fs::read(stem.with_extension("ir.json")).unwrap();
        let canonical = std::fs::read(stem.with_extension("ir.jcs")).unwrap();
        let decoded = decode_type_declarations(&pretty, limits()).unwrap();
        assert!(!decoded.record_types.is_empty(), "{task}/{candidate}");
        assert!(!decoded.table_types.is_empty(), "{task}/{candidate}");
        assert_eq!(
            decoded,
            decode_type_declarations(&canonical, limits()).unwrap()
        );
    }
}
