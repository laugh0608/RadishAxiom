use super::*;

const PROFILE: QueryProfile = QueryProfile::MapFilterV0_4;

pub(super) fn legacy_baseline() -> std::collections::BTreeMap<String, (String, QueryUsage)> {
    include_str!("../../../../../contracts/map-filter-query-v0.4/v0.3-baseline.tsv")
        .lines()
        .map(|line| {
            let c: Vec<_> = line.split('\t').collect();
            let n = |i: usize| c[i].parse::<usize>().unwrap();
            (
                c[1].to_owned(),
                (
                    c[2].to_owned(),
                    QueryUsage {
                        input_slots: n(3),
                        value_cells: n(4),
                        expression_instances: n(5),
                        slot_comparisons: n(6),
                        smt_nodes: n(7),
                        output_bytes: n(8),
                    },
                ),
            )
        })
        .collect()
}

pub(super) fn trace_bytes(query: &EncodedQuery) -> Vec<u8> {
    let trace = query.coverage_trace.as_ref().unwrap();
    let term = |t: usize| s(format!("q{}_t{t}", &query.binding.obligation[7..]));
    let value = obj(vec![
        ("ready", term(trace.ready)),
        (
            "selected",
            Value::Array(trace.selected.iter().map(|&t| term(t)).collect()),
        ),
        (
            "expected_keys",
            Value::Array(
                trace
                    .expected_keys
                    .iter()
                    .map(|row| Value::Array(row.iter().map(|&t| term(t)).collect()))
                    .collect(),
            ),
        ),
        (
            "output",
            Value::Array(
                trace
                    .output
                    .iter()
                    .map(|(active, lanes)| {
                        obj(vec![
                            ("active", term(*active)),
                            (
                                "lanes",
                                Value::Array(lanes.iter().map(|&t| term(t)).collect()),
                            ),
                        ])
                    })
                    .collect(),
            ),
        ),
    ]);
    let mut bytes = Vec::new();
    json::encode(&value, &mut bytes);
    bytes
}
fn load(path: &str) -> CanonicalDocument {
    check_canonical_document(&std::fs::read(root().join(path)).unwrap(), json_limits()).unwrap()
}
fn target(set: &ObligationSet) -> &str {
    set.obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::RowCoverage)
        .unwrap()
        .id()
}

#[test]
fn coverage_matches_independent_full_observations_and_legacy_queries() {
    compare_semantics(PROFILE, "v0.4", "check-p3-coverage-semantics.py");
}

#[test]
fn coverage_profiles_binding_order_and_tampering_are_checked() {
    let document = doc("filter-capacity");
    let obligations = set(&document);
    let id = target(&obligations);
    let query = encode_query(PROFILE, &document, &obligations, id, &identity(), limits()).unwrap();
    for old in [
        QueryProfile::MapFilterV0_1,
        QueryProfile::MapFilterV0_2,
        QueryProfile::MapFilterV0_3,
    ] {
        assert!(matches!(
            encode_query(old, &document, &obligations, id, &identity(), limits()),
            Err(QueryError::UnsupportedKind(ObligationKind::RowCoverage))
        ));
        assert!(matches!(
            check_query(
                old,
                query.bytes(),
                &document,
                &obligations,
                id,
                &identity(),
                limits()
            ),
            Err(QueryError::UnsupportedKind(ObligationKind::RowCoverage))
        ));
    }
    assert_eq!(
        check_query(
            PROFILE,
            query.bytes(),
            &document,
            &obligations,
            id,
            &identity(),
            limits()
        )
        .unwrap(),
        query
    );
    let other_id = obligations
        .obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::RowCoverage && o.id() != id)
        .unwrap()
        .id();
    assert!(matches!(
        check_query(
            PROFILE,
            query.bytes(),
            &document,
            &obligations,
            other_id,
            &identity(),
            limits()
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let other = doc("identity");
    assert!(matches!(
        encode_query(PROFILE, &other, &obligations, id, &identity(), limits()),
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
    let mut bytes = query.bytes().to_vec();
    bytes.push(b'\n');
    assert!(matches!(
        check_query(
            PROFILE,
            &bytes,
            &document,
            &obligations,
            id,
            &identity(),
            limits()
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let changed = GeneratorIdentity::new(&format!("sha256:{}", "b".repeat(64))).unwrap();
    let changed = encode_query(PROFILE, &document, &obligations, id, &changed, limits()).unwrap();
    assert_eq!(query.bytes(), changed.bytes());
    assert_ne!(query.binding(), changed.binding());
    let mut value = json::parse(document.canonical_bytes(), json_limits()).unwrap();
    let Value::Object(members) = &mut value else {
        unreachable!()
    };
    for name in [
        "nodes",
        "table_types",
        "record_types",
        "outputs",
        "contracts",
    ] {
        let Value::Array(values) = declarations::member_mut(members, name) else {
            unreachable!()
        };
        values.reverse();
    }
    let mut bytes = Vec::new();
    json::encode(&value, &mut bytes);
    let reordered = normalize_document(&bytes, json_limits()).unwrap();
    assert_eq!(
        encode_query(PROFILE, &reordered, &obligations, id, &identity(), limits()).unwrap(),
        query
    );
}

#[test]
fn coverage_exact_budgets_include_cartesian_cost_before_allocation() {
    let document = load("contracts/map-filter-query-v0.3/inputs/composite-unicode.jcs");
    let obligations = set(&document);
    for o in obligations
        .obligations()
        .iter()
        .filter(|o| o.kind() == ObligationKind::RowCoverage)
    {
        let query = encode_query(
            PROFILE,
            &document,
            &obligations,
            o.id(),
            &identity(),
            limits(),
        )
        .unwrap();
        let u = query.usage();
        assert_eq!(u.slot_comparisons, 2 + 2 * 2 * 2); // 输出容量 1，仍继承 2 槽位。
        let exact = QueryLimits {
            ir_json: json_limits(),
            max_input_slots: u.input_slots,
            max_value_cells: u.value_cells,
            max_expression_instances: u.expression_instances,
            max_slot_comparisons: u.slot_comparisons,
            max_smt_nodes: u.smt_nodes,
            max_output_bytes: u.output_bytes,
        };
        assert_eq!(
            encode_query(PROFILE, &document, &obligations, o.id(), &identity(), exact).unwrap(),
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
                matches!(encode_query(PROFILE, &document, &obligations, o.id(), &identity(), reduced), Err(QueryError::ResourceLimit { resource: actual, .. }) if actual == resource)
            );
        }
        let mut early = limits();
        early.max_slot_comparisons = 9;
        early.max_value_cells = 0;
        assert!(matches!(
            encode_query(PROFILE, &document, &obligations, o.id(), &identity(), early),
            Err(QueryError::ResourceLimit {
                resource: QueryResource::SlotComparisons,
                ..
            })
        ));
        let mut json = limits();
        json.ir_json.max_input_bytes = document.canonical_bytes().len() - 1;
        assert!(matches!(
            encode_query(PROFILE, &document, &obligations, o.id(), &identity(), json),
            Err(QueryError::Json(_))
        ));
    }
}

#[test]
fn coverage_resource_feature_and_old_ir_boundaries_remain_explicit() {
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
            "contracts/map-filter-query-v0.1/inputs/zero-capacity.jcs",
            "zero",
        ),
        (
            "contracts/map-filter-query-v0.2/inputs/no-guarantee.jcs",
            "ok",
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
                let u = result.unwrap().usage();
                assert_eq!(u.input_slots, 1);
                assert_eq!(u.slot_comparisons, 1);
                assert_eq!(u.expression_instances, 5001);
            }
            "zero" => {
                assert_eq!(result.unwrap().usage().slot_comparisons, 0);
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
fn coverage_preflight_checks_square_key_factor_and_cumulative_overflow() {
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
    for n in [0, 1, 2, 3] {
        plan.extents.insert(anchor, n);
        budget.usage.slot_comparisons = 2;
        plan.target_comparisons(&document, anchor, ObligationKind::RowCoverage, &mut budget)
            .unwrap();
        assert_eq!(budget.usage.slot_comparisons, 2 + n * n * 2);
    }
    budget.limits.max_slot_comparisons = usize::MAX;
    for n in [usize::MAX, (1usize << (usize::BITS / 2)) - 1] {
        plan.extents.insert(anchor, n);
        budget.usage.slot_comparisons = 0;
        assert!(matches!(
            plan.target_comparisons(&document, anchor, ObligationKind::RowCoverage, &mut budget),
            Err(QueryError::ResourceLimit {
                resource: QueryResource::SlotComparisons,
                ..
            })
        ));
    }
    plan.extents.insert(anchor, 1);
    budget.usage.slot_comparisons = usize::MAX - 1;
    assert!(matches!(
        plan.target_comparisons(&document, anchor, ObligationKind::RowCoverage, &mut budget),
        Err(QueryError::ResourceLimit {
            resource: QueryResource::SlotComparisons,
            ..
        })
    ));
}

#[test]
fn coverage_relation_and_guards_reject_independent_synthetic_mutations() {
    use super::super::{
        coverage,
        encode::Slot,
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
    let mut sides = Vec::new();
    for interface in ["source", "output"] {
        let mut slots = Vec::new();
        for slot in 0..3 {
            let active = arena
                .symbol(
                    Sort::Bool,
                    SymbolOrigin::Input {
                        interface: interface.into(),
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
                                interface: interface.into(),
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
        sides.push(slots);
    }
    let guards: Vec<_> = (0..3)
        .map(|slot| {
            arena
                .symbol(
                    Sort::Bool,
                    SymbolOrigin::Input {
                        interface: "guards".into(),
                        slot,
                        component: None,
                    },
                )
                .unwrap()
        })
        .collect();
    let selected: Vec<_> = sides[0].iter().map(|s| s.active).collect();
    // 两个同型整数键使错误配对在语义层暴露；不依赖 sort mismatch。
    let relation = coverage::relation(
        &sides[0],
        &selected,
        &sides[1],
        &[("key", "key"), ("x", "x")],
        &layouts,
        &mut arena,
    )
    .unwrap();
    let goal = coverage::violation(guards[0], relation, &mut arena).unwrap();
    let (bytes, symbols, _) = arena.render(goal).unwrap();
    let directory =
        std::env::temp_dir().join(format!("radishaxiom-p3d-local-{}", std::process::id()));
    std::fs::create_dir(&directory).unwrap();
    std::fs::write(directory.join("local.smt2"), bytes).unwrap();
    std::fs::write(directory.join("local.json"), symbol_list(&symbols)).unwrap();
    let result = std::process::Command::new("python3")
        .arg(root().join("scripts/check-p3-coverage-semantics.py"))
        .arg(&directory)
        .arg("--local-only")
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}\n{}\n{}",
        directory.display(),
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
    eprintln!("{}", String::from_utf8_lossy(&result.stdout));
    std::fs::remove_dir_all(directory).unwrap();
}
