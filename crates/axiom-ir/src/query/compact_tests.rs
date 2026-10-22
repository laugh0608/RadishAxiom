use super::*;
use crate::query::{self, QueryError, QueryProfile, check_query, encode_query};

fn limits() -> CompactQueryLimits {
    CompactQueryLimits {
        max_normalized_nodes: 1_000_000,
        max_normalized_edges: 2_000_000,
        max_scratch_cells: 20_000_000,
        max_work_steps: 100_000_000,
        max_temporary_bytes: 100_000_000,
        max_integer_digits: 1000,
        max_dag_depth: 100_000,
    }
}
fn dag() -> Dag {
    Dag::new(Meter::new(limits(), "obl-test".into()))
}
fn app(d: &mut Dag, op: Op, args: &[usize]) -> usize {
    let sort = if matches!(op, Op::Add | Op::Sub) {
        Sort::Int
    } else {
        Sort::Bool
    };
    d.app(sort, op, args.to_vec()).unwrap()
}
#[test]
fn hand_rules_preserve_types_order_and_integer_precision() {
    let mut d = dag();
    let f = d.boolean(false).unwrap();
    let t = d.boolean(true).unwrap();
    let x = d.intern(Node::Free(Sort::Bool, 2)).unwrap();
    let y = d.intern(Node::Free(Sort::Bool, 3)).unwrap();
    assert_eq!(app(&mut d, Op::Not, &[f]), t);
    let not = app(&mut d, Op::Not, &[x]);
    assert_eq!(app(&mut d, Op::Not, &[not]), x);
    assert_eq!(app(&mut d, Op::And, &[x, f, y]), f);
    assert_eq!(app(&mut d, Op::Or, &[x, t, y]), t);
    assert_eq!(app(&mut d, Op::And, &[t, x, x]), x);
    assert_eq!(app(&mut d, Op::Or, &[f, x, x]), x);
    assert_eq!(app(&mut d, Op::And, &[]), t);
    assert_eq!(app(&mut d, Op::Or, &[]), f);
    let xy = app(&mut d, Op::And, &[x, y]);
    let yx = app(&mut d, Op::And, &[y, x]);
    assert_ne!(xy, yx);
    assert_eq!(app(&mut d, Op::And, &[x, y]), xy);
    assert_eq!(app(&mut d, Op::Eq, &[x, x]), t);
    assert_eq!(app(&mut d, Op::Eq, &[x, y]), app(&mut d, Op::Eq, &[y, x]));
    assert_eq!(app(&mut d, Op::Eq, &[t, f]), f);
    let text1 = d.intern(Node::Free(Sort::Text, 4)).unwrap();
    let text2 = d.intern(Node::Free(Sort::Text, 5)).unwrap();
    assert_eq!(app(&mut d, Op::Eq, &[text1, text1]), t);
    let unequal = app(&mut d, Op::Eq, &[text1, text2]);
    assert!(matches!(d.nodes[unequal], Node::App(_, Op::Eq, _)));
    let zero = d.int("0").unwrap();
    let big = d.int("999999999999999999999999999999").unwrap();
    let one = d.int("1").unwrap();
    let sum = app(&mut d, Op::Add, &[big, one]);
    assert!(matches!(&d.nodes[sum],Node::Int(v) if v=="1000000000000000000000000000000"));
    let negative = app(&mut d, Op::Sub, &[one, sum]);
    assert!(matches!(&d.nodes[negative],Node::Int(v) if v=="-999999999999999999999999999999"));
    let free = d.intern(Node::Free(Sort::Int, 6)).unwrap();
    assert_eq!(app(&mut d, Op::Add, &[free, zero]), free);
    assert_eq!(app(&mut d, Op::Add, &[zero, free]), free);
    assert_eq!(app(&mut d, Op::Sub, &[free, zero]), free);
    assert_eq!(app(&mut d, Op::Sub, &[free, free]), zero);
    for op in [Op::Lt, Op::Le, Op::Gt, Op::Ge] {
        assert_eq!(
            app(&mut d, op, &[free, free]),
            if matches!(op, Op::Le | Op::Ge) { t } else { f }
        );
    }
    assert_eq!(app(&mut d, Op::Lt, &[negative, one]), t);
    assert_eq!(app(&mut d, Op::Gt, &[sum, big]), t);
    assert_eq!(app(&mut d, Op::Ite, &[t, x, y]), x);
    assert_eq!(app(&mut d, Op::Ite, &[f, x, y]), y);
    assert_eq!(app(&mut d, Op::Ite, &[x, y, y]), y);
    assert_eq!(app(&mut d, Op::Ite, &[x, t, f]), x);
    assert_eq!(app(&mut d, Op::Ite, &[x, f, t]), not);
}
#[test]
fn mathematical_add_subtract_and_digit_growth_are_bounded() {
    let mut m = Meter::new(limits(), "obl-test".into());
    for (a, b, sub, want) in [
        ("-5", "-7", false, "-12"),
        ("-5", "7", false, "2"),
        ("5", "-7", true, "12"),
        ("-5", "-7", true, "2"),
        ("5", "5", true, "0"),
        ("0", "0", true, "0"),
    ] {
        assert_eq!(integer::calculate(a, b, sub, &mut m).unwrap(), want);
    }
    m.limits.max_integer_digits = 2;
    assert!(matches!(
        integer::calculate("99", "1", false, &mut m),
        Err(QueryError::CompactResourceLimit {
            resource: R::IntegerDigits,
            ..
        })
    ));
    assert!(matches!(
        m.add(usize::MAX, 1, R::ScratchCells),
        Err(QueryError::CompactResourceLimit {
            resource: R::ScratchCells,
            ..
        })
    ));
    assert!(matches!(
        m.mul(usize::MAX, 2, R::WorkSteps),
        Err(QueryError::CompactResourceLimit {
            resource: R::WorkSteps,
            ..
        })
    ));
    m.usage.work_steps = usize::MAX;
    m.limits.max_work_steps = usize::MAX;
    assert!(m.work(1).is_err());
}
fn arena() -> Arena {
    Arena::new(query::Budget {
        limits: query::tests::limits(),
        usage: QueryUsage::default(),
        obligation: format!("sha256:{}", "a".repeat(64)),
    })
    .unwrap()
}
#[test]
fn fixed_bytes_keep_dead_frees_and_ascii_term_order() {
    let mut a = arena();
    a.enable_compact(limits()).unwrap();
    for i in 0..12 {
        a.symbol(
            Sort::Text,
            query::SymbolOrigin::TextLiteral(format!("literal{i}")),
        )
        .unwrap();
    }
    let goal = a.boolean(false);
    let (bytes, symbols, _, _) = render(a, goal, limits()).unwrap();
    let mut want = "(set-logic QF_UFLIA)\n(declare-sort Text 0)\n".to_owned();
    for i in 0..12 {
        want.push_str(&format!("(declare-const s{i:02} Text)\n"));
    }
    want.push_str("(assert false)\n(check-sat)\n");
    assert_eq!(bytes, want.as_bytes());
    // old term names end t10, t11, t12, t13, t2…t9.
    assert_eq!(
        symbols[0].origin(),
        &query::SymbolOrigin::TextLiteral("literal8".into())
    );
    assert_eq!(
        symbols[4].origin(),
        &query::SymbolOrigin::TextLiteral("literal0".into())
    );
}
#[test]
fn compact_strict_binding_and_each_exact_resource_boundary() {
    let document = query::tests::doc("int-add");
    let obligations = query::tests::set(&document);
    let target = query::tests::guarantee(&obligations);
    let identity = query::tests::identity();
    let profile = QueryProfile::MapFilterV0_5;
    let base = query::tests::limits();
    assert_eq!(
        encode_query(profile, &document, &obligations, target, &identity, base),
        Err(QueryError::BudgetProfileMismatch)
    );
    assert_eq!(
        encode_query(
            QueryProfile::MapFilterV0_4,
            &document,
            &obligations,
            target,
            &identity,
            base.with_compact(limits())
        ),
        Err(QueryError::BudgetProfileMismatch)
    );
    let q = encode_query(
        profile,
        &document,
        &obligations,
        target,
        &identity,
        base.with_compact(limits()),
    )
    .unwrap();
    assert_eq!(q.binding().artifact_type(), query::QUERY_COMPACT_ARTIFACT);
    assert_eq!(
        q.binding().query_rules(),
        Some(
            crate::obligations::raw_digest(include_bytes!(
                "../../../../docs/query/map-filter-query-v0.5.md"
            ))
            .as_str()
        )
    );
    assert_eq!(
        check_query(
            profile,
            q.bytes(),
            &document,
            &obligations,
            target,
            &identity,
            base.with_compact(limits())
        )
        .unwrap(),
        q
    );
    let mut changed = q.bytes().to_vec();
    changed[0] = b' ';
    assert!(matches!(
        check_query(
            profile,
            &changed,
            &document,
            &obligations,
            target,
            &identity,
            base.with_compact(limits())
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let u = q.compact_usage().unwrap();
    let exact = CompactQueryLimits {
        max_normalized_nodes: u.normalized_nodes,
        max_normalized_edges: u.normalized_edges,
        max_scratch_cells: u.scratch_cells,
        max_work_steps: u.work_steps,
        max_temporary_bytes: u.temporary_bytes,
        max_integer_digits: u.integer_digits,
        max_dag_depth: u.dag_depth,
    };
    assert_eq!(
        encode_query(
            profile,
            &document,
            &obligations,
            target,
            &identity,
            base.with_compact(exact)
        )
        .unwrap(),
        q
    );
    for resource in [
        R::NormalizedNodes,
        R::NormalizedEdges,
        R::ScratchCells,
        R::WorkSteps,
        R::TemporaryBytes,
        R::IntegerDigits,
        R::DagDepth,
    ] {
        for zero in [false, true] {
            let mut lower = exact;
            let value = match resource {
                R::NormalizedNodes => &mut lower.max_normalized_nodes,
                R::NormalizedEdges => &mut lower.max_normalized_edges,
                R::ScratchCells => &mut lower.max_scratch_cells,
                R::WorkSteps => &mut lower.max_work_steps,
                R::TemporaryBytes => &mut lower.max_temporary_bytes,
                R::IntegerDigits => &mut lower.max_integer_digits,
                R::DagDepth => &mut lower.max_dag_depth,
            };
            assert!(*value > 0);
            *value = if zero { 0 } else { *value - 1 };
            assert!(
                matches!(encode_query(profile,&document,&obligations,target,&identity,base.with_compact(lower)),Err(QueryError::CompactResourceLimit{resource:r,..}) if r==resource),
                "{resource:?}"
            );
        }
    }
    let u = q.usage();
    let exact_base = query::QueryLimits {
        ir_json: base.ir_json,
        max_input_slots: u.input_slots,
        max_value_cells: u.value_cells,
        max_expression_instances: u.expression_instances,
        max_slot_comparisons: u.slot_comparisons,
        max_smt_nodes: u.smt_nodes,
        max_output_bytes: u.output_bytes,
    };
    assert_eq!(
        encode_query(
            profile,
            &document,
            &obligations,
            target,
            &identity,
            exact_base.with_compact(exact)
        )
        .unwrap(),
        q
    );
    let mut too_short = exact_base;
    too_short.max_output_bytes -= 1;
    assert!(matches!(
        encode_query(
            profile,
            &document,
            &obligations,
            target,
            &identity,
            too_short.with_compact(exact)
        ),
        Err(QueryError::ResourceLimitAtStage {
            resource: query::QueryResource::OutputBytes,
            stage: QueryStage::Rendering,
            ..
        })
    ));
    let old = encode_query(
        QueryProfile::MapFilterV0_4,
        &document,
        &obligations,
        target,
        &identity,
        base,
    )
    .unwrap();
    assert!(old.compact_usage().is_none());
    assert!(old.binding().query_rules().is_none());
    let mut old_usage = old.usage();
    old_usage.output_bytes = q.usage().output_bytes;
    assert_eq!(old_usage, q.usage());
}
#[test]
fn inline_policy_has_strict_cost_and_fixed_height_boundaries() {
    let mut m = Meter::new(limits(), "obl-test".into());
    let mut inline = |constant, uses, bytes, height, definition, name| {
        rendering::choose_inline(constant, uses, bytes, height, definition, name, &mut m).unwrap()
    };
    assert!(inline(true, 100, 16, 0, 42, 2));
    assert!(!inline(true, 100, 17, 0, 43, 2));
    assert!(inline(false, 1, 128, 8, 154, 2));
    assert!(!inline(false, 1, 129, 8, 155, 2));
    assert!(!inline(false, 1, 128, 9, 154, 2));
    assert!(inline(false, 2, 16, 8, 42, 2));
    assert!(!inline(false, 2, 32, 8, 58, 2));
    assert!(!inline(false, 3, 32, 8, 90, 2)); // exact tie retains the definition
    assert!(!inline(false, 2, 16, 9, 42, 2));
}
#[test]
fn zero_resources_high_arity_and_deep_raw_dependencies_reject_before_growth() {
    let mut low = limits();
    low.max_scratch_cells = 0;
    let mut a = arena();
    assert!(matches!(
        a.enable_compact(low),
        Err(QueryError::CompactResourceLimit {
            resource: R::ScratchCells,
            ..
        })
    ));
    let mut low = limits();
    low.max_dag_depth = 3;
    let mut a = arena();
    a.enable_compact(low).unwrap();
    let x = a
        .symbol(
            Sort::Int,
            query::SymbolOrigin::TextLiteral("synthetic".into()),
        )
        .unwrap();
    let one = a.integer("1").unwrap();
    let mut term = x;
    for _ in 0..2 {
        term = a.app(Op::Add, &[term, one]).unwrap();
    }
    let before = a.nodes.len();
    assert!(matches!(
        a.app(Op::Add, &[term, one]),
        Err(QueryError::CompactResourceLimit {
            resource: R::DagDepth,
            stage: QueryStage::Construction,
            ..
        })
    ));
    assert_eq!(a.nodes.len(), before);
    let mut a = arena();
    a.enable_compact(limits()).unwrap();
    let mut terms = Vec::new();
    for i in 0..1024 {
        terms.push(
            a.symbol(
                Sort::Bool,
                query::SymbolOrigin::TextLiteral(format!("synthetic{i}")),
            )
            .unwrap(),
        );
    }
    let goal = a.and(&terms).unwrap();
    let (bytes, _, _, u) = render(a, goal, limits()).unwrap();
    assert!(bytes.windows(15).any(|s| s == b"(define-fun d0 "));
    assert!(u.normalized_edges >= 1024);
}
#[test]
fn p3_allows_explicitly_budgeted_output_over_one_mib() {
    let mut a = arena();
    a.enable_compact(limits()).unwrap();
    for i in 0..40_000 {
        a.symbol(
            Sort::Text,
            query::SymbolOrigin::TextLiteral(format!("synthetic{i}")),
        )
        .unwrap();
    }
    let goal = a.boolean(false);
    let (bytes, symbols, usage, _) = render(a, goal, limits()).unwrap();
    assert!(bytes.len() > 1_048_576);
    assert_eq!(symbols.len(), 40_000);
    assert_eq!(usage.output_bytes, bytes.len());
}
#[test]
fn staged_base_limits_are_exclusive_to_v05() {
    let document = query::tests::doc("int-add");
    let obligations = query::tests::set(&document);
    let target = query::tests::guarantee(&obligations);
    let identity = query::tests::identity();
    for (resource, stage) in [
        (query::QueryResource::ValueCells, QueryStage::Construction),
        (query::QueryResource::OutputBytes, QueryStage::Rendering),
    ] {
        let mut base = query::tests::limits();
        match resource {
            query::QueryResource::ValueCells => base.max_value_cells = 0,
            query::QueryResource::OutputBytes => base.max_output_bytes = 0,
            _ => unreachable!(),
        }
        assert!(
            matches!(encode_query(QueryProfile::MapFilterV0_5,&document,&obligations,target,&identity,base.with_compact(limits())),Err(QueryError::ResourceLimitAtStage{resource:r,stage:s,..}) if r==resource && s==stage)
        );
        assert!(
            matches!(encode_query(QueryProfile::MapFilterV0_4,&document,&obligations,target,&identity,base),Err(QueryError::ResourceLimit{resource:r,..}) if r==resource)
        );
    }
    let mut base = query::tests::limits();
    base.max_output_bytes = 0;
    assert!(matches!(
        check_query(
            QueryProfile::MapFilterV0_5,
            b"x",
            &document,
            &obligations,
            target,
            &identity,
            base.with_compact(limits())
        ),
        Err(QueryError::ResourceLimitAtStage {
            resource: query::QueryResource::OutputBytes,
            stage: QueryStage::Rendering,
            ..
        })
    ));
    assert!(matches!(
        check_query(
            QueryProfile::MapFilterV0_4,
            b"x",
            &document,
            &obligations,
            target,
            &identity,
            base
        ),
        Err(QueryError::ResourceLimit {
            resource: query::QueryResource::OutputBytes,
            ..
        })
    ));
}
#[test]
fn collision_comparison_is_interruptible_before_candidate_insertion() {
    let mut d = dag();
    let false_id = d.boolean(false).unwrap();
    let candidate = Node::Free(Sort::Text, 1234);
    let hash = d.hash(&candidate).unwrap();
    let bucket = hash as usize & (d.table.len() - 1);
    // Force a collision bucket to exercise comparison without relying on naturally occurring hashes.
    d.table[bucket] = Some((hash, false_id));
    d.meter.limits.max_work_steps = d.meter.usage.work_steps + 11;
    let before = d.nodes.len();
    assert!(matches!(
        d.intern(candidate),
        Err(QueryError::CompactResourceLimit {
            resource: R::WorkSteps,
            ..
        })
    ));
    assert_eq!(d.nodes.len(), before);
}
