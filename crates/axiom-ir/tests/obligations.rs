use radishaxiom_ir::{
    document::{CanonicalDocument, check_canonical_document, normalize_document},
    json::{JsonErrorKind, JsonLimits, ResourceLimit},
    obligations::{
        GenerationError, ObligationKind, ObligationLimits, ObligationProfile, ObligationResource,
        SetError, SetErrorKind, check_obligation_set, generate_obligations,
    },
    version::IrVersion,
};
use std::{collections::BTreeSet, path::PathBuf};

const CASES: &str = include_str!("../../../contracts/ir-derived-obligations-v0.2/cases.tsv");
const PROFILE: ObligationProfile = ObligationProfile::VerificationV0_2;
fn json_limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16 * 1024 * 1024,
        max_values: 2_000_000,
        max_nesting: 128,
    }
}
fn limits() -> ObligationLimits {
    ObligationLimits {
        ir_json: json_limits(),
        max_obligations: 100_000,
        max_definition_bytes: 16 * 1024 * 1024,
        max_path_bytes: 8 * 1024 * 1024,
        max_output_bytes: 24 * 1024 * 1024,
    }
}
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn vectors() -> PathBuf {
    root().join("contracts/ir-derived-obligations-v0.2")
}
fn row(name: &str) -> Vec<&str> {
    CASES
        .lines()
        .find(|line| line.split('\t').next() == Some(name))
        .unwrap()
        .split('\t')
        .collect()
}
fn document(name: &str) -> CanonicalDocument {
    check_canonical_document(
        &std::fs::read(root().join(row(name)[1])).unwrap(),
        json_limits(),
    )
    .unwrap()
}
fn golden(name: &str) -> Vec<u8> {
    std::fs::read(vectors().join(format!("sets/{name}.jcs"))).unwrap()
}
fn category(error: &SetError) -> String {
    match error {
        SetError::Invalid { kind, .. } => format!("{kind:?}"),
        other => panic!("unexpected error: {other:?}"),
    }
}

#[test]
fn independent_definitions_ids_complete_bytes_and_raw_digests_match_all_cases() {
    assert_eq!(CASES.lines().count(), 26);
    let mut total = 0;
    for line in CASES.lines() {
        let parts: Vec<_> = line.split('\t').collect();
        let name = parts[0];
        let doc = document(name);
        let before = doc.clone();
        let result = generate_obligations(&doc, PROFILE, limits()).unwrap();
        assert_eq!(result.ir_document_digest(), parts[2], "{name}");
        assert_eq!(result.ir_artifact(), parts[3], "{name}");
        assert_eq!(result.obligations().len().to_string(), parts[4], "{name}");
        assert_eq!(
            result
                .obligations()
                .iter()
                .map(|item| item.canonical_definition().len())
                .sum::<usize>()
                .to_string(),
            parts[5],
            "{name}"
        );
        assert_eq!(
            result.canonical_bytes().len().to_string(),
            parts[7],
            "{name}"
        );
        assert_eq!(result.artifact_digest(), parts[8], "{name}");
        assert_eq!(result.canonical_bytes(), golden(name), "{name}");
        assert_eq!(
            check_obligation_set(&golden(name), &doc, PROFILE, limits(), json_limits()).unwrap(),
            result,
            "{name}"
        );
        assert_eq!(result.scope(), "ir-derived");
        assert_eq!(result.profile(), PROFILE);
        assert_eq!(doc, before, "P2 must not mutate P1");
        total += result.obligations().len();
        for item in result.obligations() {
            let text = std::str::from_utf8(item.canonical_definition()).unwrap();
            assert!(text.contains(&format!(
                "\"expectation\":\"{}\"",
                item.kind().expectation()
            )));
            assert!(!text.contains("\"result\":"));
        }
    }
    assert_eq!(total, 482);
    // 逐项 golden 来自独立 Python；完整集合一致性不能只靠本生产 strict 自证。
    let expected = include_str!("../../../docs/evidence/p2-profile-review/obligations.tsv");
    for line in expected.lines() {
        let parts: Vec<_> = line.splitn(3, '\t').collect();
        let generated = generate_obligations(&document(parts[0]), PROFILE, limits()).unwrap();
        let item = generated
            .obligations()
            .iter()
            .find(|item| item.id() == parts[1])
            .unwrap();
        assert_eq!(item.canonical_definition(), parts[2].as_bytes());
    }
}

#[test]
fn exported_mutations_reject_missing_extra_wrong_identity_binding_path_and_result() {
    let negatives = include_str!("../../../contracts/ir-derived-obligations-v0.2/negative.tsv");
    assert_eq!(negatives.lines().count(), 29);
    for line in negatives.lines() {
        let parts: Vec<_> = line.split('\t').collect();
        let input = std::fs::read(vectors().join(format!("negative/{}.jcs", parts[0]))).unwrap();
        let error = check_obligation_set(
            &input,
            &document(parts[1]),
            PROFILE,
            limits(),
            json_limits(),
        )
        .unwrap_err();
        assert_eq!(category(&error), parts[2], "{}: {error:?}", parts[0]);
        assert!(matches!(error, SetError::Invalid { path, .. } if path.starts_with('/')));
    }
}

#[test]
fn paths_use_normalized_fields_and_expressions_not_original_analysis_indices() {
    let raw = std::fs::read(vectors().join("inputs/all-numeric-positions-input.json")).unwrap();
    let reordered = normalize_document(&raw, json_limits()).unwrap();
    let canonical = document("all-numeric-positions");
    assert_eq!(reordered.canonical_bytes(), canonical.canonical_bytes());
    assert_ne!(
        reordered.components().analysis().graph().outputs(),
        canonical.components().analysis().graph().outputs()
    );
    assert_eq!(
        generate_obligations(&reordered, PROFILE, limits()).unwrap(),
        generate_obligations(&canonical, PROFILE, limits()).unwrap()
    );
    let result = generate_obligations(&reordered, PROFILE, limits()).unwrap();
    let numeric: Vec<_> = result
        .obligations()
        .iter()
        .filter(|item| item.kind() == ObligationKind::NumericRange)
        .collect();
    assert_eq!(numeric.len(), 10); // 5 node + 3 assume + 2 guarantee；零容量、死分支仍保留。
    assert_eq!(
        result
            .obligations()
            .iter()
            .filter(|item| item.kind() == ObligationKind::ContractGuarantee)
            .count(),
        1
    );
    let definitions: Vec<_> = numeric
        .iter()
        .map(|item| std::str::from_utf8(item.canonical_definition()).unwrap())
        .collect();
    assert!(
        definitions
            .iter()
            .any(|s| s.contains("\"fields\",\"0\",\"expression\",\"fields\",\"0\",\"expression\""))
    );
    // 两个同值加法位置分别存在；and 的重复公式已在 P1 规范化中合并。
    assert!(
        definitions
            .iter()
            .any(|s| s.contains("\"path\":[\"expression\",\"left\"]"))
    );
    assert!(
        definitions
            .iter()
            .any(|s| s.contains("\"path\":[\"expression\",\"right\"]"))
    );
}

#[test]
fn group_core_positions_are_separate_and_do_not_assign_a_wrong_candidate_truth() {
    for (name, count) in [
        ("ax-b03-correct", 14),
        ("ax-b03-wrong-unit-sum", 17),
        ("ax-b03-wrong-single-group", 17),
    ] {
        let result = generate_obligations(&document(name), PROFILE, limits()).unwrap();
        assert_eq!(result.obligations().len(), count);
        assert_eq!(
            result
                .obligations()
                .iter()
                .filter(|item| item.kind() == ObligationKind::GroupConservation)
                .count(),
            1
        );
        assert_eq!(
            result
                .obligations()
                .iter()
                .filter(|item| item.kind() == ObligationKind::NumericRange)
                .count(),
            4
        );
        let conservation = result
            .obligations()
            .iter()
            .find(|item| item.kind() == ObligationKind::GroupConservation)
            .unwrap();
        let text = std::str::from_utf8(conservation.canonical_definition()).unwrap();
        let coverage = text.replace("group-conservation", "row-coverage");
        assert!(
            result
                .obligations()
                .iter()
                .any(|item| item.canonical_definition() == coverage.as_bytes())
        );
    }
    let empty =
        generate_obligations(&document("empty-group-no-aggregates"), PROFILE, limits()).unwrap();
    assert_eq!(empty.obligations().len(), 7);
    assert_eq!(
        empty
            .obligations()
            .iter()
            .filter(|item| item.kind() == ObligationKind::GroupConservation)
            .count(),
        1
    );
    assert!(
        !empty
            .obligations()
            .iter()
            .any(|item| item.kind() == ObligationKind::NumericRange)
    );
}

#[test]
fn named_outputs_are_not_deduplicated_by_node_and_composites_are_top_level_only() {
    let result =
        generate_obligations(&document("same-node-two-outputs"), PROFILE, limits()).unwrap();
    assert_eq!(
        result
            .obligations()
            .iter()
            .filter(|item| item.kind() == ObligationKind::FieldOrigin)
            .count(),
        2
    );
    let composite =
        generate_obligations(&document("all-numeric-positions"), PROFILE, limits()).unwrap();
    let fields: Vec<_> = composite
        .obligations()
        .iter()
        .filter(|item| item.kind() == ObligationKind::FieldOrigin)
        .collect();
    assert_eq!(fields.len(), 8);
    assert!(fields.iter().all(|item| {
        !std::str::from_utf8(item.canonical_definition())
            .unwrap()
            .contains("x/😀")
    }));
}

#[test]
fn pre_and_unicode_changes_rebind_every_obligation_without_upgrading_results() {
    for (first, second) in [
        ("all-numeric-positions", "changed-pre"),
        ("unicode-nfc", "unicode-nfd"),
        ("ax-b01-correct", "ax-b01-wrong-add"),
    ] {
        let a = generate_obligations(&document(first), PROFILE, limits()).unwrap();
        let b = generate_obligations(&document(second), PROFILE, limits()).unwrap();
        assert_eq!(a.obligations().len(), b.obligations().len());
        let ids: BTreeSet<_> = a.obligations().iter().map(|item| item.id()).collect();
        assert!(b.obligations().iter().all(|item| !ids.contains(item.id())));
        assert_ne!(a.artifact_digest(), b.artifact_digest());
        assert!(matches!(
            check_obligation_set(
                a.canonical_bytes(),
                &document(second),
                PROFILE,
                limits(),
                json_limits()
            ),
            Err(SetError::Invalid {
                kind: SetErrorKind::BindingMismatch,
                ..
            })
        ));
    }
}

#[test]
fn each_cumulative_budget_accepts_exact_boundary_and_rejects_one_less() {
    for name in ["ax-b03-correct", "all-numeric-positions", "deep-numeric"] {
        let parts = row(name);
        let exact = ObligationLimits {
            max_obligations: parts[4].parse().unwrap(),
            max_definition_bytes: parts[5].parse().unwrap(),
            max_path_bytes: parts[6].parse().unwrap(),
            max_output_bytes: parts[7].parse().unwrap(),
            ..limits()
        };
        let doc = document(name);
        assert_eq!(
            generate_obligations(&doc, PROFILE, exact)
                .unwrap()
                .canonical_bytes(),
            golden(name)
        );
        for (budget, resource) in [
            (
                ObligationLimits {
                    max_obligations: exact.max_obligations - 1,
                    ..exact
                },
                ObligationResource::Count,
            ),
            (
                ObligationLimits {
                    max_definition_bytes: exact.max_definition_bytes - 1,
                    ..exact
                },
                ObligationResource::DefinitionBytes,
            ),
            (
                ObligationLimits {
                    max_path_bytes: exact.max_path_bytes - 1,
                    ..exact
                },
                ObligationResource::PathBytes,
            ),
            (
                ObligationLimits {
                    max_output_bytes: exact.max_output_bytes - 1,
                    ..exact
                },
                ObligationResource::OutputBytes,
            ),
        ] {
            let error = generate_obligations(&doc, PROFILE, budget).unwrap_err();
            assert!(
                matches!(error, GenerationError::ResourceLimit { resource: actual, .. } if actual == resource),
                "{name}: {error:?}"
            );
            assert_eq!(
                check_obligation_set(&golden(name), &doc, PROFILE, budget, json_limits())
                    .unwrap_err(),
                SetError::Generation(error)
            );
        }
    }
}

#[test]
fn zero_budgets_and_ir_json_limits_never_return_partial_success() {
    let doc = document("ax-b03-correct");
    for (budget, resource) in [
        (
            ObligationLimits {
                max_output_bytes: 0,
                ..limits()
            },
            ObligationResource::OutputBytes,
        ),
        (
            ObligationLimits {
                max_obligations: 0,
                ..limits()
            },
            ObligationResource::Count,
        ),
        (
            ObligationLimits {
                max_definition_bytes: 0,
                ..limits()
            },
            ObligationResource::DefinitionBytes,
        ),
        (
            ObligationLimits {
                max_path_bytes: 0,
                ..limits()
            },
            ObligationResource::PathBytes,
        ),
    ] {
        assert!(
            matches!(generate_obligations(&doc, PROFILE, budget), Err(GenerationError::ResourceLimit { resource: actual, .. }) if actual == resource)
        );
    }
    for (json, resource) in [
        (
            JsonLimits {
                max_input_bytes: doc.canonical_bytes().len() - 1,
                ..json_limits()
            },
            ResourceLimit::InputBytes,
        ),
        (
            JsonLimits {
                max_values: 1,
                ..json_limits()
            },
            ResourceLimit::Values,
        ),
        (
            JsonLimits {
                max_nesting: 1,
                ..json_limits()
            },
            ResourceLimit::Nesting,
        ),
    ] {
        assert!(
            matches!(generate_obligations(&doc, PROFILE, ObligationLimits { ir_json: json, ..limits() }), Err(GenerationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(resource))
        );
    }
    let deep = document("deep-numeric");
    assert!(
        matches!(generate_obligations(&deep, PROFILE, ObligationLimits { ir_json: JsonLimits { max_nesting: 64, ..json_limits() }, ..limits() }), Err(GenerationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(ResourceLimit::Nesting))
    );
}

#[test]
fn candidate_json_limits_and_strict_bytes_are_independent_from_generation_budget() {
    let doc = document("ax-b03-correct");
    let bytes = golden("ax-b03-correct");
    for (json, resource) in [
        (
            JsonLimits {
                max_input_bytes: bytes.len() - 1,
                ..json_limits()
            },
            ResourceLimit::InputBytes,
        ),
        (
            JsonLimits {
                max_values: 1,
                ..json_limits()
            },
            ResourceLimit::Values,
        ),
        (
            JsonLimits {
                max_nesting: 1,
                ..json_limits()
            },
            ResourceLimit::Nesting,
        ),
    ] {
        assert!(
            matches!(check_obligation_set(&bytes, &doc, PROFILE, limits(), json), Err(SetError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(resource))
        );
    }
    for input in [
        [b" ", bytes.as_slice()].concat(),
        [bytes.as_slice(), b"\n"].concat(),
    ] {
        assert!(matches!(
            check_obligation_set(&input, &doc, PROFILE, limits(), json_limits()),
            Err(SetError::NonCanonical { .. })
        ));
    }
    for (input, kind) in [
        (
            b"{\"scope\":\"a\",\"scope\":\"b\"}".as_slice(),
            JsonErrorKind::DuplicateKey,
        ),
        (b"null".as_slice(), JsonErrorKind::NumberOrNull),
        (b"\"\\ud800\"".as_slice(), JsonErrorKind::UnpairedSurrogate),
        (b"\xff".as_slice(), JsonErrorKind::InvalidUtf8),
    ] {
        assert!(
            matches!(check_obligation_set(input, &doc, PROFILE, limits(), json_limits()), Err(SetError::Json(error)) if error.kind == kind)
        );
    }
}

#[test]
fn old_ir_and_old_sets_are_not_implicitly_migrated() {
    let old = include_bytes!("fixtures/document-identities/node.jcs");
    let old = check_canonical_document(old, json_limits()).unwrap();
    assert_eq!(
        generate_obligations(&old, PROFILE, limits()).unwrap_err(),
        GenerationError::UnsupportedIrVersion(IrVersion::V0_1)
    );
    let old_set = include_bytes!(
        "../../../contracts/pipeline-artifacts-v0.1/fixtures/minimal/obligation-set.jcs"
    );
    assert!(
        check_obligation_set(old_set, &document("node"), PROFILE, limits(), json_limits()).is_err()
    );
}

// 下面的摘要仅构造新的 P1 输入；测试期望是人工计数，不用生产 P2 生成期望。
fn identified(kind: &str, definition: &str) -> (String, String) {
    let bytes = format!("axiom-ir-v0.2:{kind}\0{definition}");
    let id = format!(
        "sha256:{}",
        radishaxiom_digest::digest_hex(bytes.as_bytes())
    );
    let entry = format!(r#"{{"definition":{definition},"id":"{id}"}}"#);
    (id, entry)
}
fn synthetic_document(depth: usize, fields: usize, outputs: usize) -> CanonicalDocument {
    let mut fs: Vec<_> = (0..fields)
        .map(|i| format!(r#"{{"label":"public","name":"f{i:04}","type":{{"kind":"bool"}}}}"#))
        .collect();
    fs.push(r#"{"label":"public","name":"key","type":{"kind":"text"}}"#.to_owned());
    let (record, record_entry) = identified(
        "record-type",
        &format!(r#"{{"fields":[{}]}}"#, fs.join(",")),
    );
    let (table, table_entry) = identified(
        "table-type",
        &format!(r#"{{"capacity":"0","primary_key":["key"],"record_type":"{record}"}}"#),
    );
    let (mut predecessor, first) = identified(
        "node",
        &format!(r#"{{"kind":"input","port":"source","table_type":"{table}"}}"#),
    );
    let mut nodes = vec![first];
    for _ in 0..depth {
        let (id, node) = identified(
            "node",
            &format!(
                r#"{{"kind":"filter","predicate":{{"op":"literal_bool","value":true}},"source":"{predecessor}","table_type":"{table}"}}"#
            ),
        );
        predecessor = id;
        nodes.push(node);
    }
    let outputs: Vec<_> = (0..outputs)
        .map(|i| format!(r#"{{"name":"out{i:04}","node":"{predecessor}"}}"#))
        .collect();
    let text = format!(
        r#"{{"contracts":[],"digest_algorithm":"sha-256","effects":[],"enum_types":[],"format":"axiom-ir","ir_version":"0.2","nodes":[{}],"outputs":[{}],"record_types":[{record_entry}],"semantics":{{"name":"keyed-finite-table-semantics","sha256":"{}"}},"table_types":[{table_entry}]}}"#,
        nodes.join(","),
        outputs.join(","),
        IrVersion::V0_2.semantics_sha256()
    );
    normalize_document(text.as_bytes(), json_limits()).unwrap()
}

#[test]
fn deep_reference_graph_does_not_expand_predecessors_or_use_graph_recursion() {
    let doc = synthetic_document(5000, 0, 1);
    let result = generate_obligations(&doc, PROFILE, limits()).unwrap();
    assert_eq!(result.obligations().len(), 15_003);
    assert_eq!(
        result
            .obligations()
            .iter()
            .filter(|item| item.kind() == ObligationKind::Totality)
            .count(),
        5000
    );
    assert!(matches!(
        generate_obligations(
            &doc,
            PROFILE,
            ObligationLimits {
                max_obligations: 15_002,
                ..limits()
            }
        ),
        Err(GenerationError::ResourceLimit {
            resource: ObligationResource::Count,
            ..
        })
    ));
}

#[test]
fn wide_shared_types_emit_every_named_field_and_enforce_cumulative_budget() {
    let doc = synthetic_document(0, 256, 16);
    let result = generate_obligations(&doc, PROFILE, limits()).unwrap();
    assert_eq!(result.obligations().len(), 2 + 257 * 16);
    let ids: BTreeSet<_> = result.obligations().iter().map(|item| item.id()).collect();
    assert_eq!(ids.len(), result.obligations().len());
    assert!(matches!(
        generate_obligations(
            &doc,
            PROFILE,
            ObligationLimits {
                max_definition_bytes: 4096,
                ..limits()
            }
        ),
        Err(GenerationError::ResourceLimit {
            resource: ObligationResource::DefinitionBytes,
            ..
        })
    ));
}
