use super::*;

const PROFILE: QueryProfile = QueryProfile::MapFilterV0_2;

fn totality(set: &ObligationSet) -> &str {
    set.obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::Totality)
        .unwrap()
        .id()
}

#[test]
fn totality_matches_independent_concrete_semantics_and_legacy_bytes() {
    compare_semantics(PROFILE, "v0.2", "check-p3-totality-semantics.py");
}

#[test]
fn profiles_bind_support_and_preserve_old_queries() {
    let document = doc("int-add");
    let set = set(&document);
    for target in set.obligations() {
        let old = encode_query(
            QueryProfile::MapFilterV0_1,
            &document,
            &set,
            target.id(),
            &identity(),
            limits(),
        );
        let new = encode_query(PROFILE, &document, &set, target.id(), &identity(), limits());
        match target.kind() {
            ObligationKind::Totality => {
                assert!(matches!(
                    old,
                    Err(QueryError::UnsupportedKind(ObligationKind::Totality))
                ));
                let query = new.unwrap();
                assert_eq!(query.binding().encoding_profile(), PROFILE.as_str());
                assert!(matches!(
                    check_query(
                        QueryProfile::MapFilterV0_1,
                        query.bytes(),
                        &document,
                        &set,
                        target.id(),
                        &identity(),
                        limits()
                    ),
                    Err(QueryError::UnsupportedKind(ObligationKind::Totality))
                ));
            }
            ObligationKind::NumericRange | ObligationKind::ContractGuarantee => {
                let (old, new) = (old.unwrap(), new.unwrap());
                assert_eq!(old.bytes(), new.bytes());
                assert_eq!(old.symbols(), new.symbols());
                assert_eq!(old.usage(), new.usage());
                assert_ne!(old.binding(), new.binding());
                assert_eq!(
                    old.binding().encoding_profile(),
                    QueryProfile::MapFilterV0_1.as_str()
                );
            }
            ObligationKind::IrStructure => {
                assert!(matches!(old, Err(QueryError::NotProve(_))));
                assert!(matches!(new, Err(QueryError::NotProve(_))));
            }
            kind => {
                assert!(matches!(old, Err(QueryError::UnsupportedKind(k)) if k == kind));
                assert!(matches!(new, Err(QueryError::UnsupportedKind(k)) if k == kind));
            }
        }
    }
}

#[test]
fn totality_binding_tampering_identity_and_order_are_checked() {
    let document = doc("filter-capacity");
    let obligations = set(&document);
    let targets: Vec<_> = obligations
        .obligations()
        .iter()
        .filter(|o| o.kind() == ObligationKind::Totality)
        .collect();
    assert_eq!(targets.len(), 2);
    let target = targets[0].id();
    let query = encode_query(
        PROFILE,
        &document,
        &obligations,
        target,
        &identity(),
        limits(),
    )
    .unwrap();
    assert_eq!(
        check_query(
            PROFILE,
            query.bytes(),
            &document,
            &obligations,
            target,
            &identity(),
            limits()
        )
        .unwrap(),
        query
    );
    assert!(matches!(
        check_query(
            PROFILE,
            query.bytes(),
            &document,
            &obligations,
            targets[1].id(),
            &identity(),
            limits()
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let mut bytes = query.bytes().to_vec();
    bytes.push(b'\n');
    assert!(matches!(
        check_query(
            PROFILE,
            &bytes,
            &document,
            &obligations,
            target,
            &identity(),
            limits()
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let other = doc("identity");
    assert!(matches!(
        encode_query(PROFILE, &other, &obligations, target, &identity(), limits()),
        Err(QueryError::BindingMismatch)
    ));
    assert!(matches!(
        encode_query(
            PROFILE,
            &document,
            &obligations,
            "missing",
            &identity(),
            limits()
        ),
        Err(QueryError::UnknownObligation(_))
    ));
    let changed = GeneratorIdentity::new(&format!("sha256:{}", "b".repeat(64))).unwrap();
    let changed =
        encode_query(PROFILE, &document, &obligations, target, &changed, limits()).unwrap();
    assert_eq!(changed.bytes(), query.bytes());
    assert_ne!(changed.binding(), query.binding());
    let mut value = json::parse(document.canonical_bytes(), json_limits()).unwrap();
    let Value::Object(members) = &mut value else {
        unreachable!()
    };
    for key in [
        "nodes",
        "contracts",
        "record_types",
        "table_types",
        "outputs",
    ] {
        let Value::Array(values) = declarations::member_mut(members, key) else {
            unreachable!()
        };
        values.reverse();
    }
    let mut reordered = Vec::new();
    json::encode(&value, &mut reordered);
    let reordered = normalize_document(&reordered, json_limits()).unwrap();
    assert_eq!(
        encode_query(
            PROFILE,
            &reordered,
            &obligations,
            target,
            &identity(),
            limits()
        )
        .unwrap(),
        query
    );
}

#[test]
fn totality_resource_bounds_are_exact_and_no_guarantee_is_required() {
    let document = check_canonical_document(
        &std::fs::read(root().join("contracts/map-filter-query-v0.2/inputs/no-guarantee.jcs"))
            .unwrap(),
        json_limits(),
    )
    .unwrap();
    let obligations = set(&document);
    assert!(
        !obligations
            .obligations()
            .iter()
            .any(|o| o.kind() == ObligationKind::ContractGuarantee)
    );
    let target = totality(&obligations);
    let query = encode_query(
        PROFILE,
        &document,
        &obligations,
        target,
        &identity(),
        limits(),
    )
    .unwrap();
    let used = query.usage();
    let exact = QueryLimits {
        ir_json: json_limits(),
        max_input_slots: used.input_slots,
        max_value_cells: used.value_cells,
        max_expression_instances: used.expression_instances,
        max_slot_comparisons: used.slot_comparisons,
        max_smt_nodes: used.smt_nodes,
        max_output_bytes: used.output_bytes,
    };
    assert_eq!(
        encode_query(PROFILE, &document, &obligations, target, &identity(), exact).unwrap(),
        query
    );
    for resource in [
        QueryResource::InputSlots,
        QueryResource::ValueCells,
        QueryResource::ExpressionInstances,
        QueryResource::SlotComparisons,
        QueryResource::SmtNodes,
        QueryResource::OutputBytes,
    ] {
        let mut reduced = exact;
        match resource {
            QueryResource::InputSlots => reduced.max_input_slots -= 1,
            QueryResource::ValueCells => reduced.max_value_cells -= 1,
            QueryResource::ExpressionInstances => reduced.max_expression_instances -= 1,
            QueryResource::SlotComparisons => reduced.max_slot_comparisons -= 1,
            QueryResource::SmtNodes => reduced.max_smt_nodes -= 1,
            QueryResource::OutputBytes => reduced.max_output_bytes -= 1,
        }
        assert!(
            matches!(encode_query(PROFILE, &document, &obligations, target, &identity(), reduced), Err(QueryError::ResourceLimit { resource: actual, .. }) if actual == resource),
            "{resource:?}"
        );
    }
    let mut json = limits();
    json.ir_json.max_input_bytes = document.canonical_bytes().len() - 1;
    assert!(matches!(
        encode_query(PROFILE, &document, &obligations, target, &identity(), json),
        Err(QueryError::Json(_))
    ));
}

#[test]
fn totality_preserves_whole_document_feature_and_resource_rejections() {
    let load = |name: &str| {
        check_canonical_document(
            &std::fs::read(root().join(format!(
                "contracts/map-filter-query-v0.1/resource-inputs/{name}.jcs"
            )))
            .unwrap(),
            json_limits(),
        )
        .unwrap()
    };
    let nested = load("nested-expansion");
    let obligations = set(&nested);
    assert!(matches!(
        encode_query(
            PROFILE,
            &nested,
            &obligations,
            totality(&obligations),
            &identity(),
            limits()
        ),
        Err(QueryError::ResourceLimit {
            resource: QueryResource::ExpressionInstances,
            ..
        })
    ));
    let deep = load("deep-type-and-graph");
    let obligations = set(&deep);
    let query = encode_query(
        PROFILE,
        &deep,
        &obligations,
        totality(&obligations),
        &identity(),
        limits(),
    )
    .unwrap();
    assert_eq!(query.usage().expression_instances, 5001);
    assert_eq!(query.usage().input_slots, 1);
    let empty = doc("zero-capacity");
    let obligations = set(&empty);
    let mut zero = limits();
    zero.max_input_slots = 0;
    assert_eq!(
        encode_query(
            PROFILE,
            &empty,
            &obligations,
            totality(&obligations),
            &identity(),
            zero
        )
        .unwrap()
        .usage()
        .input_slots,
        0
    );
    // 全部材料有合法内容身份；请求确实抵达整文档功能 / 预算检查。
    for name in ["exists_rows", "count_where", "sum_where", "huge-input"] {
        let bytes = std::fs::read(root().join(format!(
            "contracts/map-filter-query-v0.2/resource-inputs/{name}.jcs"
        )))
        .unwrap();
        let document = check_canonical_document(&bytes, json_limits()).unwrap();
        let obligations = set(&document);
        let result = encode_query(
            PROFILE,
            &document,
            &obligations,
            totality(&obligations),
            &identity(),
            limits(),
        );
        if name == "huge-input" {
            assert!(matches!(
                result,
                Err(QueryError::ResourceLimit {
                    resource: QueryResource::InputSlots,
                    ..
                })
            ));
        } else {
            assert!(
                matches!(result, Err(QueryError::UnsupportedFeature { feature, .. }) if feature == name)
            );
        }
    }
    let old = check_canonical_document(
        &std::fs::read(
            root().join("crates/axiom-ir/tests/fixtures/document-identities/contract.jcs"),
        )
        .unwrap(),
        json_limits(),
    )
    .unwrap();
    assert!(matches!(
        encode_query(
            PROFILE,
            &old,
            &obligations,
            totality(&obligations),
            &identity(),
            limits()
        ),
        Err(QueryError::UnsupportedIrVersion(IrVersion::V0_1))
    ));
}
