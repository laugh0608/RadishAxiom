use radishaxiom_ir::declarations::{DeclarationError, DeclarationErrorKind, Label};
use radishaxiom_ir::json::{JsonErrorKind, JsonLimits, ResourceLimit};
use radishaxiom_ir::normalization::{NormalizedTypeDeclarations, normalize_type_declarations};

const INPUT: &str = include_str!("fixtures/type-identities/input.json");
const PERMUTED: &str = include_str!("fixtures/type-identities/permuted.json");
const EXPECTED: &str = include_str!("fixtures/type-identities/expected.tsv");
const WRONG_HASHES: &str = include_str!("fixtures/type-identities/wrong-hashes.tsv");

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 1024 * 1024,
        max_values: 100_000,
        max_nesting: 128,
    }
}

fn normalize(input: &str) -> NormalizedTypeDeclarations {
    normalize_type_declarations(input.as_bytes(), limits()).unwrap()
}

// 期望来自已留存的 Python json / hashlib 向量；不调用生产 encoder 或 digest 构造期望。
fn expected_rows() -> Vec<(&'static str, &'static str, &'static str)> {
    EXPECTED
        .lines()
        .map(|line| {
            let parts: Vec<_> = line.splitn(3, '\t').collect();
            assert_eq!(parts.len(), 3);
            (parts[0], parts[1], parts[2])
        })
        .collect()
}

fn document(rows: &[(&str, &str, &str)]) -> String {
    let entries = |kind| {
        rows.iter()
            .filter(|row| row.0 == kind)
            .map(|(_, id, definition)| format!(r#"{{"definition":{definition},"id":"{id}"}}"#))
            .collect::<Vec<_>>()
            .join(",")
    };
    format!(
        r#"{{"contracts":[],"digest_algorithm":"sha-256","effects":[],"enum_types":[{}],"format":"axiom-ir","ir_version":"0.1","nodes":[],"outputs":[],"record_types":[{}],"semantics":{{"name":"keyed-finite-table-semantics","sha256":"6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"}},"table_types":[{}]}}"#,
        entries("enum"),
        entries("record"),
        entries("table")
    )
}

#[test]
fn definitions_and_ids_match_independent_vectors() {
    let result = normalize(INPUT);
    let actual = result
        .enum_types()
        .iter()
        .map(|entry| ("enum", entry.id(), entry.canonical_definition()))
        .chain(
            result
                .record_types()
                .iter()
                .map(|entry| ("record", entry.id(), entry.canonical_definition())),
        )
        .chain(
            result
                .table_types()
                .iter()
                .map(|entry| ("table", entry.id(), entry.canonical_definition())),
        )
        .collect::<Vec<_>>();
    let expected = expected_rows();
    assert_eq!(expected.len(), 7);
    assert_eq!(actual.len(), expected.len());
    for (actual, expected) in actual.into_iter().zip(expected) {
        assert_eq!(actual, (expected.0, expected.1, expected.2.as_bytes()));
    }
    // 对象、声明、记录字段排列与转义形式都可以改变；规范结果必须相同。
    assert_eq!(result, normalize(PERMUTED));
    assert_eq!(result, normalize(&document(&expected_rows())));
}

#[test]
fn semantic_array_orders_are_distinct_from_json_object_order() {
    let result = normalize(INPUT);
    let unicode_record = result
        .record_types()
        .iter()
        .find(|entry| entry.definition().fields.len() == 4)
        .unwrap();
    assert_eq!(
        unicode_record
            .definition()
            .fields
            .iter()
            .map(|field| field.name.as_str())
            .collect::<Vec<_>>(),
        ["e\u{301}", "é", "\u{e000}", "\u{10000}"]
    );
    for entry in result.enum_types() {
        assert_eq!(
            entry.definition().members,
            ["z", "a", "é", "e\u{301}", "😀"]
        );
    }
    // 相同成员的不同名义枚举具有不同 ID；相反主键顺序的表也不能合并。
    assert_ne!(result.enum_types()[0].id(), result.enum_types()[1].id());
    assert_ne!(result.table_types()[0].id(), result.table_types()[1].id());
    assert_eq!(
        result.table_types()[0].definition().primary_key,
        ["\u{e000}", "\u{10000}"]
    );
    assert_eq!(
        result.table_types()[1].definition().primary_key,
        ["\u{10000}", "\u{e000}"]
    );
    let main = result
        .record_types()
        .iter()
        .find(|entry| entry.definition().fields.len() == 7)
        .unwrap();
    assert_eq!(
        main.definition()
            .fields
            .iter()
            .find(|field| field.name == "optional")
            .unwrap()
            .label,
        Label::Sensitive
    );
}

#[test]
fn domain_separator_and_definition_only_hashing_are_mandatory() {
    let expected = expected_rows();
    for row in WRONG_HASHES.lines() {
        let parts: Vec<_> = row.split('\t').collect();
        assert_eq!(parts.len(), 3);
        let original = expected.iter().find(|entry| entry.1 == parts[1]).unwrap();
        let input = document(&[("enum", parts[2], original.2)]);
        assert_eq!(
            normalize_type_declarations(input.as_bytes(), limits()).unwrap_err(),
            DeclarationError::ContentIdMismatch {
                path: "/enum_types/0/id".to_owned(),
                supplied: parts[2].to_owned(),
                computed: parts[1].to_owned(),
            },
            "{}",
            parts[0]
        );
    }
}

#[test]
fn structurally_valid_changes_cannot_reuse_old_content_id() {
    let expected = expected_rows();
    for (kind, from, to) in [
        ("enum", r#"["z","a""#, r#"["a","z""#),
        ("record", r#""label":"sensitive""#, r#""label":"public""#),
        (
            "record",
            r#""scale":"9999999999999999999999999999999999999999""#,
            r#""scale":"9999999999999999999999999999999999999998""#,
        ),
        ("table", r#""capacity":"0""#, r#""capacity":"1""#),
        (
            "table",
            "[\"\u{10000}\",\"\u{e000}\"]",
            "[\"\u{e000}\",\"\u{10000}\"]",
        ),
    ] {
        let index = expected
            .iter()
            .position(|row| row.0 == kind && row.2.contains(from))
            .unwrap();
        let changed = expected[index].2.replacen(from, to, 1);
        assert_ne!(changed, expected[index].2);
        let mut rows = expected.clone();
        rows[index].2 = &changed;
        let input = document(&rows);
        match normalize_type_declarations(input.as_bytes(), limits()).unwrap_err() {
            DeclarationError::ContentIdMismatch {
                path,
                supplied,
                computed,
            } => {
                assert!(path.starts_with(&format!("/{kind}_types/")));
                assert_eq!(supplied, expected[index].1);
                assert_ne!(supplied, computed);
            }
            other => panic!("unexpected error: {other}"),
        }
    }
}

#[test]
fn reference_rebinding_does_not_hide_a_forged_identity() {
    let rows = expected_rows();
    let target = rows.iter().find(|row| row.0 == "enum").unwrap();
    let fake = format!("sha256:{}", "0".repeat(64));
    // 同时替换声明与引用能通过引用解析，但不能通过内容身份核对。
    let input = document(&rows).replace(target.1, &fake);
    assert!(
        matches!(normalize_type_declarations(input.as_bytes(), limits()).unwrap_err(),
        DeclarationError::ContentIdMismatch { supplied, computed, .. } if supplied == fake && computed == target.1)
    );
}

#[test]
fn mismatches_point_to_original_array_position_and_duplicates_are_not_deduplicated() {
    let mut rows = expected_rows();
    rows.reverse();
    let index = rows
        .iter()
        .position(|row| row.0 == "record" && row.2.contains("sensitive"))
        .unwrap();
    let changed = rows[index].2.replace("sensitive", "public");
    rows[index].2 = &changed;
    assert!(
        matches!(normalize_type_declarations(document(&rows).as_bytes(), limits()).unwrap_err(),
        DeclarationError::ContentIdMismatch { path, .. } if path == "/record_types/1/id")
    );
    let row = expected_rows()[0];
    assert_eq!(
        normalize_type_declarations(document(&[row, row]).as_bytes(), limits()).unwrap_err(),
        DeclarationError::Structure {
            kind: DeclarationErrorKind::DuplicateId,
            path: "/enum_types/1/id".to_owned()
        }
    );
}

#[test]
fn structural_and_resource_rejections_survive_normalization() {
    let unknown = INPUT.replacen("\"effects\": []", "\"effects\": [\"io\"]", 1);
    assert_ne!(unknown, INPUT);
    assert_eq!(
        normalize_type_declarations(unknown.as_bytes(), limits()).unwrap_err(),
        DeclarationError::Structure {
            kind: DeclarationErrorKind::NonEmptyEffects,
            path: "/effects".to_owned()
        }
    );
    for budget in [
        JsonLimits {
            max_input_bytes: INPUT.len() - 1,
            ..limits()
        },
        JsonLimits {
            max_values: 1,
            ..limits()
        },
    ] {
        assert!(
            matches!(normalize_type_declarations(INPUT.as_bytes(), budget).unwrap_err(),
            DeclarationError::Json(error) if matches!(error.kind, JsonErrorKind::ResourceLimit(ResourceLimit::InputBytes | ResourceLimit::Values)))
        );
    }
}

#[test]
fn declaration_success_does_not_imply_full_ir_acceptance() {
    // 与生成向量一样，没有 input / output 仍可验收声明；没有完整程序成功入口。
    assert!(normalize(&document(&[])).record_types().is_empty());
    let input =
        document(&expected_rows()).replace("\"nodes\":[]", "\"nodes\":[{\"invalid_node\":true}]");
    assert_eq!(normalize(&input), normalize(INPUT));
}

#[test]
fn every_existing_candidate_has_matching_type_content_identities() {
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
        let result = normalize_type_declarations(&pretty, limits()).unwrap();
        assert!(!result.record_types().is_empty(), "{task}/{candidate}");
        assert!(!result.table_types().is_empty(), "{task}/{candidate}");
        assert_eq!(
            result,
            normalize_type_declarations(&canonical, limits()).unwrap()
        );
    }
}
