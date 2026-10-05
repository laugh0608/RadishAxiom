use radishaxiom_ir::contracts::ContractError;
use radishaxiom_ir::declarations::DeclarationError;
use radishaxiom_ir::document::{DocumentError, check_canonical_document, normalize_document};
use radishaxiom_ir::expressions::ExpressionError;
use radishaxiom_ir::json::JsonLimits;
use radishaxiom_ir::migration::{MigrationError, migrate_v0_1_to_v0_2};
use radishaxiom_ir::nodes::NodeError;
use radishaxiom_ir::version::IrVersion;

const CASES: &str = include_str!("fixtures/v0.2/migrations.tsv");
const MAPPINGS: &str = include_str!("fixtures/v0.2/mappings.tsv");
const REFERENCES: &[u8] = include_bytes!("fixtures/v0.2/references-source.jcs");

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 1024 * 1024,
        max_values: 100_000,
        max_nesting: 128,
    }
}

#[test]
fn exported_v02_negative_corpus_rejects_at_independently_specified_boundaries() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/v0.2");
    let manifest = include_str!("fixtures/v0.2/negative.tsv");
    assert_eq!(manifest.lines().count(), 18);
    for line in manifest.lines() {
        let row: Vec<_> = line.split('\t').collect();
        let input = std::fs::read(root.join(row[0])).unwrap();
        for check in [normalize_document, check_canonical_document] {
            let error = check(&input, limits()).unwrap_err();
            let (category, path) = match error {
                DocumentError::Ir(ContractError::Expression(ExpressionError::Type {
                    kind,
                    path,
                })) => (format!("type:{kind:?}"), path),
                DocumentError::Ir(ContractError::Expression(ExpressionError::Input(
                    DeclarationError::Structure { kind, path },
                )))
                | DocumentError::Ir(ContractError::Node(NodeError::Input(
                    DeclarationError::Structure { kind, path },
                ))) => (format!("input:{kind:?}"), path),
                DocumentError::Ir(ContractError::Node(NodeError::Structure { kind, path })) => {
                    (format!("node:{kind:?}"), path)
                }
                other => panic!("{}: unexpected {other:?}", row[0]),
            };
            assert_eq!(
                (category.as_str(), path.as_str()),
                (row[1], row[2]),
                "{}",
                row[0]
            );
        }
    }
}

#[test]
fn twenty_sources_match_independent_migrated_bytes_digests_and_every_identity_mapping() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let mut candidates = 0;
    assert_eq!(CASES.lines().count(), 20);
    for line in CASES.lines() {
        let row: Vec<_> = line.split('\t').collect();
        let source = std::fs::read(root.join("../..").join(row[1])).unwrap();
        let expected = std::fs::read(root.join("tests/fixtures/v0.2").join(row[2])).unwrap();
        let migrated = migrate_v0_1_to_v0_2(&source, limits())
            .unwrap_or_else(|error| panic!("{}: {error}", row[0]));
        assert_eq!(migrated.target().canonical_bytes(), expected, "{}", row[0]);
        assert_eq!(migrated.record().source_document_id(), row[3]);
        assert_eq!(migrated.record().target_document_id(), row[4]);
        assert_eq!(migrated.target().document_id(), row[4]);
        assert_ne!(row[3], row[4]);
        assert_eq!(
            format!("sha256:{}", radishaxiom_digest::digest_hex(&source)),
            row[5]
        );
        assert_eq!(
            format!("sha256:{}", radishaxiom_digest::digest_hex(&expected)),
            row[6]
        );
        assert_eq!(migrated.record().tool_name(), "radishaxiom-ir");
        assert_eq!(migrated.record().tool_version(), "0.0.0");
        assert_eq!(migrated.record().rule_name(), "axiom-ir-0.1-to-0.2");
        assert_eq!(migrated.record().rule_version(), "1");
        assert_eq!(migrated.record().source_version(), IrVersion::V0_1);
        assert_eq!(migrated.record().target_version(), IrVersion::V0_2);
        assert_eq!(migrated.target().version(), IrVersion::V0_2);
        let actual: Vec<_> = migrated
            .record()
            .mappings()
            .iter()
            .map(|entry| (entry.kind().as_str(), entry.source(), entry.target()))
            .collect();
        let expected: Vec<_> = MAPPINGS
            .lines()
            .filter_map(|line| {
                let fields: Vec<_> = line.split('\t').collect();
                (fields[0] == row[0]).then_some((fields[1], fields[2], fields[3]))
            })
            .collect();
        assert_eq!(actual, expected, "{}", row[0]);
        assert!(actual.iter().all(|(_, source, target)| source != target));
        assert_eq!(
            check_canonical_document(migrated.target().canonical_bytes(), limits()).unwrap(),
            *migrated.target()
        );
        assert_eq!(
            normalize_document(migrated.target().canonical_bytes(), limits()).unwrap(),
            *migrated.target()
        );
        // 不把目标作为已迁移的幂等成功；规则只有一个精确源版本。
        assert_eq!(
            migrate_v0_1_to_v0_2(migrated.target().canonical_bytes(), limits()).unwrap_err(),
            MigrationError::WrongSourceVersion {
                actual: IrVersion::V0_2
            }
        );
        candidates += usize::from(row[0].starts_with("ax-b"));
    }
    assert_eq!(candidates, 12);
}

#[test]
fn migration_preserves_id_shaped_names_literals_and_recanonicalizes_expression_order() {
    let preserved = include_str!("fixtures/v0.2/preserved-text.txt").trim();
    let result = migrate_v0_1_to_v0_2(REFERENCES, limits()).unwrap();
    let output = std::str::from_utf8(result.target().canonical_bytes()).unwrap();
    for member in ["name", "port", "value"] {
        assert!(output.contains(&format!(r#""{member}":"{preserved}""#)));
    }
    assert!(
        result
            .record()
            .mappings()
            .iter()
            .any(|entry| entry.source() == preserved && entry.target() != preserved)
    );
    assert_eq!(
        result.target().canonical_bytes(),
        include_bytes!("fixtures/v0.2/migrated/references.jcs")
    );
    // fixture 的多个 enum 引用换域后会改变 and 排序；独立目标已重排，不能只换字符串。
    let source = check_canonical_document(REFERENCES, limits()).unwrap();
    assert_ne!(
        source.components().contracts()[0].canonical_definition(),
        result.target().components().contracts()[0].canonical_definition()
    );
}

#[test]
fn migration_never_repairs_noncanonical_invalid_or_resource_limited_sources() {
    let source = std::str::from_utf8(REFERENCES).unwrap();
    for input in [format!(" {source}"), format!("{source}\n")] {
        assert!(matches!(
            migrate_v0_1_to_v0_2(input.as_bytes(), limits()).unwrap_err(),
            MigrationError::Source(DocumentError::NonCanonical { .. })
        ));
    }
    for input in [
        source.replacen("\"effects\":[]", "\"effects\":[\"network\"]", 1),
        source.replacen("\"ir_version\":\"0.1\"", "\"ir_version\":\"0.2\"", 1),
        source.replacen("sha256:", "sha512:", 1),
        source.replacen("\"literal_enum\"", "\"is_some\"", 1),
        source.replacen("\"literal_enum\"", "\"record\"", 1),
    ] {
        let expected = check_canonical_document(input.as_bytes(), limits()).unwrap_err();
        assert_eq!(
            migrate_v0_1_to_v0_2(input.as_bytes(), limits()).unwrap_err(),
            MigrationError::Source(expected)
        );
    }
    for budget in [
        JsonLimits {
            max_input_bytes: REFERENCES.len() - 1,
            ..limits()
        },
        JsonLimits {
            max_values: 100,
            ..limits()
        },
        JsonLimits {
            max_nesting: 3,
            ..limits()
        },
    ] {
        let expected = check_canonical_document(REFERENCES, budget).unwrap_err();
        assert_eq!(
            migrate_v0_1_to_v0_2(REFERENCES, budget).unwrap_err(),
            MigrationError::Source(expected)
        );
    }
}
