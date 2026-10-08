use super::*;

const PROFILE: QueryProfile = QueryProfile::MapFilterV0_3;

fn target(set: &ObligationSet) -> &str {
    set.obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::KeyCardinality)
        .unwrap()
        .id()
}
fn load(path: &str) -> CanonicalDocument {
    check_canonical_document(&std::fs::read(root().join(path)).unwrap(), json_limits()).unwrap()
}

#[test]
fn cardinality_matches_independent_semantics_and_both_legacy_baselines() {
    compare_semantics(PROFILE, "v0.3", "check-p3-cardinality-semantics.py");
}

#[test]
fn cardinality_profiles_binding_and_target_tampering_are_checked() {
    let document = doc("filter-capacity");
    let set = set(&document);
    let targets: Vec<_> = set
        .obligations()
        .iter()
        .filter(|o| o.kind() == ObligationKind::KeyCardinality)
        .collect();
    assert_eq!(targets.len(), 2);
    let id = targets[0].id();
    let query = encode_query(PROFILE, &document, &set, id, &identity(), limits()).unwrap();
    for old in [QueryProfile::MapFilterV0_1, QueryProfile::MapFilterV0_2] {
        assert!(matches!(
            encode_query(old, &document, &set, id, &identity(), limits()),
            Err(QueryError::UnsupportedKind(ObligationKind::KeyCardinality))
        ));
        assert!(matches!(
            check_query(
                old,
                query.bytes(),
                &document,
                &set,
                id,
                &identity(),
                limits()
            ),
            Err(QueryError::UnsupportedKind(ObligationKind::KeyCardinality))
        ));
    }
    assert_eq!(
        check_query(
            PROFILE,
            query.bytes(),
            &document,
            &set,
            id,
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
            &set,
            targets[1].id(),
            &identity(),
            limits()
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let other = doc("identity");
    assert!(matches!(
        encode_query(PROFILE, &other, &set, id, &identity(), limits()),
        Err(QueryError::BindingMismatch)
    ));
    assert!(matches!(
        encode_query(PROFILE, &document, &set, "missing", &identity(), limits()),
        Err(QueryError::UnknownObligation(_))
    ));
    let mut tampered = query.bytes().to_vec();
    tampered.push(b'\n');
    assert!(matches!(
        check_query(
            PROFILE,
            &tampered,
            &document,
            &set,
            id,
            &identity(),
            limits()
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let changed = GeneratorIdentity::new(&format!("sha256:{}", "b".repeat(64))).unwrap();
    let changed = encode_query(PROFILE, &document, &set, id, &changed, limits()).unwrap();
    assert_eq!(changed.bytes(), query.bytes());
    assert_ne!(changed.binding(), query.binding());
    for o in set
        .obligations()
        .iter()
        .filter(|o| o.kind() == ObligationKind::RowCoverage)
    {
        assert!(matches!(
            encode_query(PROFILE, &document, &set, o.id(), &identity(), limits()),
            Err(QueryError::UnsupportedKind(ObligationKind::RowCoverage))
        ));
    }
}

#[test]
fn cardinality_budgets_are_exact_and_use_inherited_extent_and_all_keys() {
    let document = load("contracts/map-filter-query-v0.3/inputs/composite-unicode.jcs");
    let set = set(&document);
    for obligation in set
        .obligations()
        .iter()
        .filter(|o| o.kind() == ObligationKind::KeyCardinality)
    {
        let id = obligation.id();
        let query = encode_query(PROFILE, &document, &set, id, &identity(), limits()).unwrap();
        let used = query.usage();
        // 输入和输出各 2 个槽位、2 个键分量；输出声明容量 1 不得免除比较。
        assert_eq!(used.slot_comparisons, 4);
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
            encode_query(PROFILE, &document, &set, id, &identity(), exact).unwrap(),
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
                matches!(encode_query(PROFILE, &document, &set, id, &identity(), reduced),
                Err(QueryError::ResourceLimit { resource: actual, .. }) if actual == resource),
                "{resource:?}"
            );
        }
        let mut preflight = limits();
        preflight.max_slot_comparisons = 3;
        preflight.max_value_cells = 0;
        assert!(matches!(
            encode_query(PROFILE, &document, &set, id, &identity(), preflight),
            Err(QueryError::ResourceLimit {
                resource: QueryResource::SlotComparisons,
                ..
            })
        ));
        let mut json = limits();
        json.ir_json.max_input_bytes = document.canonical_bytes().len() - 1;
        assert!(matches!(
            encode_query(PROFILE, &document, &set, id, &identity(), json),
            Err(QueryError::Json(_))
        ));
    }
}

#[test]
fn cardinality_retains_resource_feature_version_and_no_guarantee_boundaries() {
    for (path, expected) in [
        (
            "contracts/map-filter-query-v0.1/resource-inputs/nested-expansion.jcs",
            "instances",
        ),
        (
            "contracts/map-filter-query-v0.1/resource-inputs/deep-type-and-graph.jcs",
            "deep",
        ),
        (
            "contracts/map-filter-query-v0.2/inputs/no-guarantee.jcs",
            "ok",
        ),
        (
            "contracts/map-filter-query-v0.1/inputs/zero-capacity.jcs",
            "zero",
        ),
        (
            "contracts/map-filter-query-v0.2/resource-inputs/huge-input.jcs",
            "huge",
        ),
        (
            "contracts/map-filter-query-v0.2/resource-inputs/exists_rows.jcs",
            "exists_rows",
        ),
        (
            "contracts/map-filter-query-v0.2/resource-inputs/count_where.jcs",
            "count_where",
        ),
        (
            "contracts/map-filter-query-v0.2/resource-inputs/sum_where.jcs",
            "sum_where",
        ),
    ] {
        let document = load(path);
        let set = set(&document);
        let result = encode_query(
            PROFILE,
            &document,
            &set,
            target(&set),
            &identity(),
            limits(),
        );
        match expected {
            "instances" => assert!(matches!(
                result,
                Err(QueryError::ResourceLimit {
                    resource: QueryResource::ExpressionInstances,
                    ..
                })
            )),
            "huge" => assert!(matches!(
                result,
                Err(QueryError::ResourceLimit {
                    resource: QueryResource::InputSlots,
                    ..
                })
            )),
            "deep" => {
                let used = result.unwrap().usage();
                assert_eq!(used.input_slots, 1);
                assert_eq!(used.slot_comparisons, 0);
                assert_eq!(used.expression_instances, 5001);
            }
            "zero" => {
                assert_eq!(result.unwrap().usage().slot_comparisons, 0);
                let mut zero = limits();
                zero.max_input_slots = 0;
                zero.max_slot_comparisons = 0;
                encode_query(PROFILE, &document, &set, target(&set), &identity(), zero).unwrap();
            }
            "ok" => {
                result.unwrap();
                assert!(
                    !set.obligations()
                        .iter()
                        .any(|o| o.kind() == ObligationKind::ContractGuarantee)
                );
            }
            feature => assert!(
                matches!(result, Err(QueryError::UnsupportedFeature { feature: actual, .. }) if actual == feature)
            ),
        }
    }
    let old = load("crates/axiom-ir/tests/fixtures/document-identities/contract.jcs");
    let document = doc("identity");
    let set = set(&document);
    assert!(matches!(
        encode_query(PROFILE, &old, &set, target(&set), &identity(), limits()),
        Err(QueryError::UnsupportedIrVersion(IrVersion::V0_1))
    ));
}

#[test]
fn output_unique_predicate_is_independently_checked_with_synthetic_collisions() {
    use super::super::{
        encode::{Slot, output_unique},
        layout::Layouts,
        smt::{Arena, Sort},
    };
    let document = load("contracts/map-filter-query-v0.3/inputs/composite-unicode.jcs");
    let set = set(&document);
    let mut budget = Budget {
        limits: limits(),
        usage: QueryUsage::default(),
        obligation: target(&set).to_owned(),
    };
    let types = document.components().analysis().graph().types();
    let layouts = Layouts::new(types, &mut budget).unwrap();
    let table = types
        .table_types()
        .iter()
        .find(|t| t.definition().capacity.as_str() == "2")
        .unwrap()
        .definition();
    let layout = layouts.records[&table.record_type];
    let mut arena = Arena::new(budget).unwrap();
    let sorts = layouts.leaves(layout, &mut arena.budget).unwrap();
    let mut slots = Vec::new();
    for slot in 0..2 {
        let active = arena
            .symbol(
                Sort::Bool,
                SymbolOrigin::Input {
                    interface: "in".into(),
                    slot,
                    component: None,
                },
            )
            .unwrap();
        let lanes = sorts
            .iter()
            .enumerate()
            .map(|(component, &sort)| {
                arena
                    .symbol(
                        sort,
                        SymbolOrigin::Input {
                            interface: "in".into(),
                            slot,
                            component: Some(component),
                        },
                    )
                    .unwrap()
            })
            .collect();
        slots.push(Slot {
            active,
            data: layouts.make(layout, lanes),
        });
    }
    // 合成 O* 注入入口不调用完整程序 WF；只检查同一生产输出唯一键谓词。
    let unique = output_unique(&slots, &table.primary_key, &layouts, &mut arena).unwrap();
    let (bytes, symbols, _) = arena.render(unique).unwrap();
    let directory =
        std::env::temp_dir().join(format!("radishaxiom-p3c-unique-{}", std::process::id()));
    std::fs::create_dir(&directory).unwrap();
    std::fs::write(directory.join("unique.smt2"), bytes).unwrap();
    std::fs::write(directory.join("unique.json"), symbol_list(&symbols)).unwrap();
    let result = std::process::Command::new("python3")
        .arg(root().join("scripts/check-p3-cardinality-semantics.py"))
        .arg(&directory)
        .arg("--unique-only")
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "artifacts: {}\n{}",
        directory.display(),
        String::from_utf8_lossy(&result.stderr)
    );
    eprintln!("{}", String::from_utf8_lossy(&result.stdout));
    std::fs::remove_dir_all(directory).unwrap();
}

#[test]
fn target_comparison_preflight_checks_zero_pairs_cumulative_cost_and_overflow() {
    // 仅规划器算术测试：大表示规模不分配任何槽位，也不是合法程序反例。
    let document = load("contracts/map-filter-query-v0.3/inputs/composite-unicode.jcs");
    let root = json::parse(document.canonical_bytes(), json_limits()).unwrap();
    let set = set(&document);
    let mut budget = Budget {
        limits: limits(),
        usage: QueryUsage::default(),
        obligation: target(&set).to_owned(),
    };
    let mut plan = planning::Plan::new(&document, &root, &mut budget).unwrap();
    let anchor = text(
        plan.nodes
            .iter()
            .find(|n| text(get(n, "definition"), "kind") == "filter")
            .unwrap(),
        "id",
    );
    let base = budget.usage.slot_comparisons;
    assert_eq!(base, 2);
    for n in [0, 1, 2, 3, 4] {
        budget.usage.slot_comparisons = base;
        plan.extents.insert(anchor, n);
        plan.target_comparisons(
            &document,
            anchor,
            ObligationKind::KeyCardinality,
            &mut budget,
        )
        .unwrap();
        assert_eq!(
            budget.usage.slot_comparisons,
            base + n * n.saturating_sub(1)
        );
    }
    budget.limits.max_slot_comparisons = usize::MAX;
    budget.usage.slot_comparisons = 0;
    plan.extents.insert(anchor, usize::MAX);
    assert!(matches!(
        plan.target_comparisons(
            &document,
            anchor,
            ObligationKind::KeyCardinality,
            &mut budget
        ),
        Err(QueryError::ResourceLimit {
            resource: QueryResource::SlotComparisons,
            ..
        })
    ));
    // 乘积可表示，但累计已有成本仍会溢出。
    plan.extents.insert(anchor, 2);
    budget.usage.slot_comparisons = usize::MAX - 1;
    assert!(matches!(
        plan.target_comparisons(
            &document,
            anchor,
            ObligationKind::KeyCardinality,
            &mut budget
        ),
        Err(QueryError::ResourceLimit {
            resource: QueryResource::SlotComparisons,
            ..
        })
    ));
}
