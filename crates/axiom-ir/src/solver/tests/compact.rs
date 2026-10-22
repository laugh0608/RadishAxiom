use super::*;
use crate::json::Value;
fn get<'a>(v: &'a Value, key: &str) -> &'a Value {
    let Value::Object(m) = v else {
        panic!("object")
    };
    &m.iter().find(|(k, _, _)| k == key).unwrap().1
}
fn text(v: &Value) -> &str {
    let Value::String(s) = v else {
        panic!("string")
    };
    s
}
use crate::query::{CompactQueryLimits, CompactQueryResource as C, CompactQueryUsage};

pub(super) fn compact_limits() -> CompactQueryLimits {
    CompactQueryLimits {
        max_normalized_nodes: 2_000_000,
        max_normalized_edges: 8_000_000,
        max_scratch_cells: 100_000_000,
        max_work_steps: 1_000_000_000,
        max_temporary_bytes: 500_000_000,
        max_integer_digits: 1000,
        max_dag_depth: 100_000,
    }
}
fn input<'a>(
    d: &'a CanonicalDocument,
    s: &'a ObligationSet,
    q: &'a EncodedQuery,
    g: &'a GeneratorIdentity,
    t: &'a SolverToolIdentity,
    profile: QueryProfile,
) -> SolverRequestInput<'a> {
    SolverRequestInput {
        document: d,
        obligations: s,
        obligation_id: q.binding().obligation(),
        query_profile: profile,
        query: q,
        generator: g,
        tool: t,
    }
}
fn encode(d: &CanonicalDocument, s: &ObligationSet, id: &str, l: SolverLimits) -> EncodedQuery {
    encode_query(
        QueryProfile::MapFilterV0_5,
        d,
        s,
        id,
        &generator(),
        l.query.with_compact(compact_limits()),
    )
    .unwrap()
}
fn plan_compact(
    d: &CanonicalDocument,
    s: &ObligationSet,
    q: &EncodedQuery,
    l: SolverLimits,
) -> SolverRequest {
    plan_solver_request(
        SolverProfile::Cvc5Query0_3ModelV0_1,
        input(d, s, q, &generator(), &tool(), QueryProfile::MapFilterV0_5),
        l.with_compact(compact_limits()),
    )
    .unwrap()
}
fn pair(path: &str) -> (CanonicalDocument, ObligationSet, EncodedQuery, EncodedQuery) {
    let (d, s, old) = setup(path, limits());
    let q = encode(&d, &s, old.binding().obligation(), limits());
    (d, s, old, q)
}
#[test]
fn compact_profiles_rules_and_closed_request_members_are_bound() {
    let (d, s, old, q) = pair("contracts/map-filter-query-v0.1/inputs/identity.jcs");
    let l = limits();
    let g = generator();
    let t = tool();
    let req = plan_compact(&d, &s, &q, l);
    assert_eq!(req.profile(), SolverProfile::Cvc5Query0_3ModelV0_1);
    assert_eq!(
        SolverProfile::from_id(COMPACT_PROFILE).unwrap(),
        req.profile()
    );
    let value = crate::json::parse(req.canonical_bytes(), l.query.ir_json).unwrap();
    assert_eq!(text(get(&value, "version")), "0.2");
    assert_eq!(
        text(get(&value, "protocol_rules")),
        crate::obligations::raw_digest(COMPACT_RULES)
    );
    let query = get(&value, "query");
    assert_eq!(
        text(get(query, "query_rules")),
        q.binding().query_rules().unwrap()
    );
    let Value::Object(m) = query else {
        panic!("query")
    };
    assert_eq!(m.len(), 6);
    let c = get(get(get(&value, "limits"), "component"), "query");
    let Value::Object(m) = c else {
        panic!("limits")
    };
    assert_eq!(m.len(), 2);
    assert_eq!(req.stdin_bytes(), q.bytes());
    for (solver, profile, query) in [
        (
            SolverProfile::Cvc5Query0_2ModelV0_1,
            QueryProfile::MapFilterV0_5,
            &q,
        ),
        (
            SolverProfile::Cvc5Query0_3ModelV0_1,
            QueryProfile::MapFilterV0_4,
            &old,
        ),
        (
            SolverProfile::Cvc5Query0_3ModelV0_1,
            QueryProfile::MapFilterV0_5,
            &old,
        ),
        (
            SolverProfile::Cvc5Query0_2ModelV0_1,
            QueryProfile::MapFilterV0_4,
            &q,
        ),
    ] {
        assert!(matches!(
            plan_solver_request(
                solver,
                input(&d, &s, query, &g, &t, profile),
                l.with_compact(compact_limits())
            ),
            Err(SolverError::ProfileMismatch)
        ));
    }
    assert!(matches!(
        plan_solver_request(
            req.profile(),
            input(&d, &s, &q, &g, &t, QueryProfile::MapFilterV0_5),
            l
        ),
        Err(SolverError::Query(QueryError::BudgetProfileMismatch))
    ));
    assert!(matches!(
        plan_solver_request(
            SolverProfile::Cvc5Query0_2ModelV0_1,
            input(&d, &s, &old, &g, &t, QueryProfile::MapFilterV0_4),
            l.with_compact(compact_limits())
        ),
        Err(SolverError::Query(QueryError::BudgetProfileMismatch))
    ));
    check_solver_request(
        req.canonical_bytes(),
        req.profile(),
        input(&d, &s, &q, &g, &t, QueryProfile::MapFilterV0_5),
        l.with_compact(compact_limits()),
    )
    .unwrap();
    // 每个子树均只能由输入重建，规范合法的 JSON 也不能替换绑定。
    for key in [
        "version",
        "protocol_rules",
        "query",
        "binding",
        "symbols",
        "layout",
        "tool",
        "limits",
    ] {
        let mut v = crate::json::parse(req.canonical_bytes(), l.query.ir_json).unwrap();
        let Value::Object(m) = &mut v else {
            unreachable!()
        };
        m.iter_mut().find(|(n, _, _)| n == key).unwrap().1 = Value::Bool(true);
        let mut bytes = Vec::new();
        crate::json::encode(&v, &mut bytes);
        assert!(
            matches!(
                check_solver_request(
                    &bytes,
                    req.profile(),
                    input(&d, &s, &q, &g, &t, QueryProfile::MapFilterV0_5),
                    l.with_compact(compact_limits())
                ),
                Err(SolverError::NonCanonical { .. })
            ),
            "{key}"
        );
    }
    let other = GeneratorIdentity::new(&format!("sha256:{}", "d".repeat(64))).unwrap();
    assert!(matches!(
        plan_solver_request(
            req.profile(),
            input(&d, &s, &q, &other, &t, QueryProfile::MapFilterV0_5),
            l.with_compact(compact_limits())
        ),
        Err(SolverError::BindingMismatch)
    ));
    let mut changed = l;
    changed.tokens += 1;
    assert_ne!(
        plan_compact(&d, &s, &q, changed).artifact_digest(),
        req.artifact_digest()
    );
}
fn set_compact(c: &mut CompactQueryLimits, r: C, n: usize) {
    match r {
        C::NormalizedNodes => c.max_normalized_nodes = n,
        C::NormalizedEdges => c.max_normalized_edges = n,
        C::ScratchCells => c.max_scratch_cells = n,
        C::WorkSteps => c.max_work_steps = n,
        C::TemporaryBytes => c.max_temporary_bytes = n,
        C::IntegerDigits => c.max_integer_digits = n,
        C::DagDepth => c.max_dag_depth = n,
    }
}
fn usage(u: CompactQueryUsage, r: C) -> usize {
    match r {
        C::NormalizedNodes => u.normalized_nodes,
        C::NormalizedEdges => u.normalized_edges,
        C::ScratchCells => u.scratch_cells,
        C::WorkSteps => u.work_steps,
        C::TemporaryBytes => u.temporary_bytes,
        C::IntegerDigits => u.integer_digits,
        C::DagDepth => u.dag_depth,
    }
}
#[test]
fn compact_request_rebuild_charges_all_seven_budgets_without_fallback() {
    let (d, s, _, q) = pair("contracts/map-filter-query-v0.1/inputs/int-add.jcs");
    let g = generator();
    let t = tool();
    let l = limits();
    let u = q.compact_usage().unwrap();
    let initial = plan_compact(&d, &s, &q, l);
    for r in [
        C::NormalizedNodes,
        C::NormalizedEdges,
        C::ScratchCells,
        C::WorkSteps,
        C::TemporaryBytes,
        C::IntegerDigits,
        C::DagDepth,
    ] {
        let n = usage(u, r);
        assert!(n > 0, "{r:?}");
        let mut c = compact_limits();
        set_compact(&mut c, r, n);
        let exact = plan_solver_request(
            initial.profile(),
            input(&d, &s, &q, &g, &t, QueryProfile::MapFilterV0_5),
            l.with_compact(c),
        )
        .unwrap();
        assert_eq!(exact.stdin_bytes(), initial.stdin_bytes());
        assert_ne!(exact.artifact_digest(), initial.artifact_digest());
        set_compact(&mut c, r, n - 1);
        assert!(
            matches!(plan_solver_request(initial.profile(),input(&d,&s,&q,&g,&t,QueryProfile::MapFilterV0_5),l.with_compact(c)),Err(SolverError::Query(QueryError::CompactResourceLimit{resource,..})) if resource==r),
            "{r:?}"
        );
    }
}
#[test]
fn complete_new_models_match_old_worlds_and_enforce_exact_free_and_derived_symbols() {
    for path in [
        "contracts/map-filter-query-v0.1/inputs/identity.jcs",
        "contracts/map-filter-query-v0.1/inputs/unicode-literals.jcs",
        "contracts/solver-model-v0.1/inputs/composite.jcs",
    ] {
        let (d, s, old, q) = pair(path);
        let old = plan(&d, &s, &old, limits()).unwrap();
        let req = plan_compact(&d, &s, &q, limits());
        assert_eq!(old.query.symbols().len(), req.query.symbols().len());
        let mut previous = None;
        let mut pairs = Vec::new();
        for symbol in old.query.symbols() {
            let new = req
                .query
                .symbols()
                .iter()
                .find(|n| n.origin() == symbol.origin())
                .unwrap();
            assert_eq!(new.sort(), symbol.sort());
            pairs.push((symbol.name(), new.name()));
        }
        pairs.sort_unstable();
        for (_, new) in pairs {
            if let Some(p) = previous {
                assert!(p < new)
            }
            previous = Some(new);
        }
        let stdout = synthetic(&req, false);
        let resp = parse_solver_response(&req, response(&req, stdout.as_bytes())).unwrap();
        let candidate = decode_model_world(&req, resp.sat_model().unwrap()).unwrap();
        check_model_world(candidate.canonical_bytes(), &req, resp.sat_model().unwrap()).unwrap();
        let oldstdout = synthetic(&old, false);
        let oldresp = parse_solver_response(&old, response(&old, oldstdout.as_bytes())).unwrap();
        let oldworld = decode_model_world(&old, oldresp.sat_model().unwrap()).unwrap();
        assert_eq!(candidate.world_bytes(), oldworld.world_bytes());
        assert_ne!(candidate.artifact_digest(), oldworld.artifact_digest());
        assert!(
            check_model_world(oldworld.canonical_bytes(), &req, resp.sat_model().unwrap()).is_err()
        );
        let first = req.query.symbols()[0].name();
        let missing = stdout
            .lines()
            .filter(|line| !line.starts_with(&format!("(define-fun {first} ")))
            .collect::<Vec<_>>()
            .join("\n");
        assert!(matches!(
            parse_solver_response(&req, response(&req, missing.as_bytes())),
            Err(SolverError::Model {
                reason: "missing-free-symbol",
                ..
            })
        ));
        let oldname = old.query.symbols()[0].name();
        let unknown = stdout.replacen(first, oldname, 1);
        assert!(parse_solver_response(&req, response(&req, unknown.as_bytes())).is_err());
        let extra = stdout.replacen("\n)", "\n(define-fun d999999999 () Bool true)\n)", 1);
        assert!(parse_solver_response(&req, response(&req, extra.as_bytes())).is_err());
        let declared = req
            .query
            .symbols()
            .iter()
            .map(|s| s.name())
            .collect::<std::collections::BTreeSet<_>>();
        for (name, sort) in &req.catalogue {
            if !declared.contains(name.as_str()) {
                assert!(
                    std::str::from_utf8(req.stdin_bytes())
                        .unwrap()
                        .contains(&format!("(define-fun {name} () {} ", sort.name()))
                );
            }
        }
        for bytes in [
            b"unknown".as_slice(),
            stdout.replacen("sat", "unknown", 1).as_bytes(),
        ] {
            let unknown = parse_solver_response(&req, response(&req, bytes)).unwrap();
            assert_eq!(unknown.status(), SolverStatus::Unknown);
            assert!(unknown.sat_model().is_none());
        }
        let mut terminated = response(&req, stdout.as_bytes());
        terminated.outer_termination = OuterTermination::Deadline;
        terminated.exit = ProcessExit::Exited(1);
        assert!(
            matches!(parse_solver_response(&req,terminated),Err(SolverError::Transport(v)) if v.primary_reason()==Some(TransportReason::Outer(OuterTermination::Deadline)))
        );
    }
}
#[test]
fn compact_ax_b01_original_capacity_all_supported_targets_fit_stdin() {
    let l = limits();
    let mut count = 0;
    let mut maximum = 0;
    let mut kinds = std::collections::BTreeSet::new();
    for line in
        include_str!("../../../../../contracts/ir-derived-obligations-v0.2/cases.tsv").lines()
    {
        let c: Vec<_> = line.split('\t').collect();
        if !c[0].starts_with("ax-b01") {
            continue;
        }
        let (d, s, _) = setup(c[1], l);
        for target in s.obligations() {
            let q = match encode_query(
                QueryProfile::MapFilterV0_5,
                &d,
                &s,
                target.id(),
                &generator(),
                l.query.with_compact(compact_limits()),
            ) {
                Ok(v) => v,
                Err(QueryError::NotProve(_) | QueryError::UnsupportedKind(_)) => continue,
                Err(e) => panic!("{e}"),
            };
            let req = plan_compact(&d, &s, &q, l);
            assert_eq!(req.usage().get(SolverResource::InputSlots), 100);
            assert_eq!(req.query.symbols().len(), 501);
            maximum = maximum.max(req.stdin_bytes().len());
            kinds.insert(target.kind().as_str());
            count += 1;
            eprintln!(
                "P4 compact {} {} stdin={} compact={:?}",
                c[0],
                target.id(),
                req.stdin_bytes().len(),
                q.compact_usage().unwrap()
            );
        }
    }
    assert_eq!(count, 27);
    assert_eq!(kinds.len(), 5);
    assert!(maximum <= 1_048_576);
    eprintln!(
        "P4 compact AX-B01: {count} targets maximum stdin {maximum}, margin {}",
        1_048_576 - maximum
    );
}

#[test]
fn compact_models_keep_protocol_faults_masked_payloads_and_transport_precedence() {
    let (d, s, _, q) = pair("contracts/map-filter-query-v0.1/inputs/identity.jcs");
    let req = plan_compact(&d, &s, &q, limits());
    let source = synthetic(&req, false);
    let a = input_symbol(&req, 0, None);
    let b = input_symbol(&req, 1, None);
    let cycle = replace_value(&req, &replace_value(&req, &source, &a, &b), &b, &a);
    assert!(matches!(
        parse_solver_response(&req, response(&req, cycle.as_bytes())),
        Err(SolverError::Model {
            reason: "alias-cycle",
            ..
        })
    ));
    let name = input_symbol(&req, 0, Some(3));
    let hidden = replace_value(&req, &source, &name, "999");
    let parsed = parse_solver_response(&req, response(&req, hidden.as_bytes())).unwrap();
    decode_model_world(&req, parsed.sat_model().unwrap()).unwrap();
    let active = replace_value(&req, &hidden, &a, "true");
    let parsed = parse_solver_response(&req, response(&req, active.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&req, parsed.sat_model().unwrap()),
        Err(SolverError::InvalidInput {
            reason: "enum-index",
            ..
        })
    ));
    let active = replace_value(&req, &source, &a, "true");
    let hidden = replace_value(&req, &active, &input_symbol(&req, 0, Some(8)), "999");
    let parsed = parse_solver_response(&req, response(&req, hidden.as_bytes())).unwrap();
    decode_model_world(&req, parsed.sat_model().unwrap()).unwrap();
    let shown = replace_value(&req, &hidden, &input_symbol(&req, 0, Some(7)), "true");
    let parsed = parse_solver_response(&req, response(&req, shown.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&req, parsed.sat_model().unwrap()),
        Err(SolverError::InvalidInput {
            reason: "numeric-range",
            ..
        })
    ));
    let duplicate = synthetic(&req, true);
    let parsed = parse_solver_response(&req, response(&req, duplicate.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&req, parsed.sat_model().unwrap()),
        Err(SolverError::InvalidInput {
            reason: "duplicate-key",
            ..
        })
    ));
    assert_eq!(
        parse_solver_response(&req, response(&req, b"unsat"))
            .unwrap()
            .status(),
        SolverStatus::Unsat
    );
    for outer in [
        OuterTermination::Deadline,
        OuterTermination::Memory,
        OuterTermination::StdoutLimit,
        OuterTermination::StderrLimit,
    ] {
        let mut observation = response(&req, b"invalid");
        observation.outer_termination = outer;
        observation.exit = ProcessExit::Exited(1);
        observation.stdout_complete = false;
        assert!(
            matches!(parse_solver_response(&req,observation),Err(SolverError::Transport(v)) if v.primary_reason()==Some(TransportReason::Outer(outer)))
        );
    }
    let mut truncated = response(&req, source.as_bytes());
    truncated.stdout_complete = false;
    assert!(
        matches!(parse_solver_response(&req,truncated),Err(SolverError::Transport(v)) if v.primary_reason()==Some(TransportReason::IncompleteStreams))
    );
    let (d, s, _, q) = pair("contracts/map-filter-query-v0.1/inputs/unicode-literals.jcs");
    let req = plan_compact(&d, &s, &q, limits());
    let source = synthetic(&req, false);
    let literals = req
        .query
        .symbols()
        .iter()
        .filter(|s| matches!(s.origin(), crate::query::SymbolOrigin::TextLiteral(_)))
        .collect::<Vec<_>>();
    let conflict = replace_value(&req, &source, literals[1].name(), "@Text_0");
    let parsed = parse_solver_response(&req, response(&req, conflict.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&req, parsed.sat_model().unwrap()),
        Err(SolverError::LiteralClassConflict)
    ));
}
