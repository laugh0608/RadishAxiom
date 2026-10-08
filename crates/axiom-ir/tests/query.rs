use radishaxiom_ir::{
    document::check_canonical_document,
    json::JsonLimits,
    obligations::{ObligationKind, ObligationLimits, ObligationProfile, generate_obligations},
    query::{GeneratorIdentity, QueryError, QueryLimits, QueryProfile, encode_query},
};
use std::path::PathBuf;

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn json_limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16_000_000,
        max_values: 2_000_000,
        max_nesting: 128,
    }
}
fn p2_limits() -> ObligationLimits {
    ObligationLimits {
        ir_json: json_limits(),
        max_obligations: 100_000,
        max_definition_bytes: 16_000_000,
        max_path_bytes: 8_000_000,
        max_output_bytes: 24_000_000,
    }
}
fn limits() -> QueryLimits {
    QueryLimits {
        ir_json: json_limits(),
        max_input_slots: 10_000,
        max_value_cells: 10_000_000,
        max_expression_instances: 1_000_000,
        max_slot_comparisons: 1_000_000,
        max_smt_nodes: 10_000_000,
        max_output_bytes: 100_000_000,
    }
}
fn identity() -> GeneratorIdentity {
    GeneratorIdentity::new(&format!("sha256:{}", "a".repeat(64))).unwrap()
}

#[test]
fn existing_p2_inventory_is_preserved_and_supported_queries_are_generated() {
    for (profile, expected) in [
        (QueryProfile::MapFilterV0_1, (115, 1, 284, 56, 26)),
        (QueryProfile::MapFilterV0_2, (127, 1, 255, 73, 26)),
        (QueryProfile::MapFilterV0_3, (139, 1, 226, 90, 26)),
    ] {
        let mut generated = 0;
        let mut kinds = 0;
        let mut documents = 0;
        let mut checks = 0;
        let mut resources = 0;
        for line in include_str!("../../../contracts/ir-derived-obligations-v0.2/cases.tsv").lines()
        {
            let columns: Vec<_> = line.split('\t').collect();
            let bytes = std::fs::read(root().join(columns[1])).unwrap();
            let document = check_canonical_document(&bytes, json_limits()).unwrap();
            let set =
                generate_obligations(&document, ObligationProfile::VerificationV0_2, p2_limits())
                    .unwrap();
            for obligation in set.obligations() {
                match encode_query(
                    profile,
                    &document,
                    &set,
                    obligation.id(),
                    &identity(),
                    limits(),
                ) {
                    Ok(query) => {
                        assert!(
                            matches!(
                                obligation.kind(),
                                ObligationKind::NumericRange | ObligationKind::ContractGuarantee
                            ) || (profile != QueryProfile::MapFilterV0_1
                                && obligation.kind() == ObligationKind::Totality)
                                || (profile == QueryProfile::MapFilterV0_3
                                    && obligation.kind() == ObligationKind::KeyCardinality)
                        );
                        assert!(query.bytes().is_ascii());
                        assert!(query.bytes().starts_with(b"(set-logic QF_UFLIA)\n"));
                        assert!(query.bytes().ends_with(b"(check-sat)\n"));
                        assert_eq!(query.binding().ir_artifact(), columns[3]);
                        assert_eq!(
                            query.binding().obligation_set_artifact(),
                            set.artifact_digest()
                        );
                        assert_eq!(query.usage().output_bytes, query.bytes().len());
                        generated += 1;
                    }
                    Err(QueryError::UnsupportedKind(_)) => kinds += 1,
                    Err(QueryError::UnsupportedFeature { .. }) => documents += 1,
                    Err(QueryError::NotProve(_)) => checks += 1,
                    Err(QueryError::ResourceLimit {
                        resource: radishaxiom_ir::query::QueryResource::InputSlots,
                        ..
                    }) if columns[0] == "references" => resources += 1,
                    Err(error) => panic!("{} {}: {error:?}", columns[0], obligation.id()),
                }
            }
        }
        assert_eq!((generated, resources, kinds, documents, checks), expected);
    }
}
