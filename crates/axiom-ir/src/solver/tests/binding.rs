use super::*;

#[test]
fn every_supported_profile_plans_real_queries_and_keeps_old_bindings_distinct() {
    let l = limits();
    let (d, set, _) = setup("contracts/map-filter-query-v0.1/inputs/int-add.jcs", l);
    let mut profiles = std::collections::BTreeSet::new();
    let mut kinds = std::collections::BTreeSet::new();
    for profile in [
        QueryProfile::MapFilterV0_1,
        QueryProfile::MapFilterV0_2,
        QueryProfile::MapFilterV0_3,
        QueryProfile::MapFilterV0_4,
    ] {
        for target in set.obligations() {
            let query = match encode_query(profile, &d, &set, target.id(), &generator(), l.query) {
                Ok(q) => q,
                Err(QueryError::NotProve(_) | QueryError::UnsupportedKind(_)) => continue,
                Err(e) => panic!("{e}"),
            };
            let req = plan_solver_request(
                SolverProfile::Cvc5Query0_2ModelV0_1,
                SolverRequestInput {
                    document: &d,
                    obligations: &set,
                    obligation_id: target.id(),
                    query_profile: profile,
                    query: &query,
                    generator: &generator(),
                    tool: &tool(),
                },
                l,
            )
            .unwrap();
            assert_eq!(req.stdin_bytes(), query.bytes());
            profiles.insert(req.query.binding().encoding_profile());
            kinds.insert(target.kind().as_str());
            let data = synthetic(&req, false);
            let result = parse_solver_response(&req, response(&req, data.as_bytes())).unwrap();
            assert!(decode_model_world(&req, result.sat_model().unwrap()).is_ok());
        }
    }
    assert_eq!(profiles.len(), 4);
    assert_eq!(kinds.len(), 5);
    for platform in [
        "linux-amd64",
        "linux-arm64",
        "macos-amd64",
        "macos-arm64",
        "windows-amd64",
        "windows-arm64",
    ] {
        assert!(
            SolverToolIdentity::new(
                platform,
                &format!("sha256:{}", "b".repeat(64)),
                &format!("sha256:{}", "c".repeat(64))
            )
            .is_ok()
        );
    }
}

#[test]
fn identities_profiles_and_model_requests_cannot_be_silently_rebound() {
    let l = limits();
    let (d, set, q) = setup("contracts/map-filter-query-v0.1/inputs/identity.jcs", l);
    let req = plan(&d, &set, &q, l).unwrap();
    let identity = GeneratorIdentity::new(&format!("sha256:{}", "d".repeat(64))).unwrap();
    let bad = plan_solver_request(
        SolverProfile::Cvc5Query0_2ModelV0_1,
        SolverRequestInput {
            document: &d,
            obligations: &set,
            obligation_id: q.binding().obligation(),
            query_profile: QueryProfile::MapFilterV0_4,
            query: &q,
            generator: &identity,
            tool: &tool(),
        },
        l,
    );
    assert!(matches!(bad, Err(SolverError::BindingMismatch)));
    let (d2, set2, _) = setup("contracts/map-filter-query-v0.1/inputs/pre-false.jcs", l);
    assert!(plan(&d2, &set2, &q, l).is_err());
    for invalid in [
        "cvc5-1.3.4-qf-uflia-v0.1",
        "axiom-smtlib2-qf-uflia-query0.1",
        "unknown",
    ] {
        assert!(matches!(
            SolverProfile::from_id(invalid),
            Err(SolverError::UnsupportedProfile)
        ));
    }
    for (platform, payload, acceptance) in [
        ("Darwin", "sha256:bad", "sha256:bad"),
        ("macos-arm64", "sha256:bad", "sha256:bad"),
    ] {
        assert!(SolverToolIdentity::new(platform, payload, acceptance).is_err());
    }
    let alt_tool = SolverToolIdentity::new(
        "linux-arm64",
        &format!("sha256:{}", "e".repeat(64)),
        &format!("sha256:{}", "f".repeat(64)),
    )
    .unwrap();
    let alt = plan_solver_request(
        SolverProfile::Cvc5Query0_2ModelV0_1,
        SolverRequestInput {
            document: &d,
            obligations: &set,
            obligation_id: q.binding().obligation(),
            query_profile: QueryProfile::MapFilterV0_4,
            query: &q,
            generator: &generator(),
            tool: &alt_tool,
        },
        l,
    )
    .unwrap();
    assert_ne!(req.artifact_digest(), alt.artifact_digest());
    let source = synthetic(&req, false);
    let response = parse_solver_response(&req, super::response(&req, source.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&alt, response.sat_model().unwrap()),
        Err(SolverError::BindingMismatch)
    ));
    let mut input = super::response(&req, b"unsat");
    input.stderr = b"first diagnostic";
    let first = parse_solver_response(&req, input).unwrap();
    let mut input = super::response(&req, b"unsat");
    input.stderr = b"second diagnostic";
    let second = parse_solver_response(&req, input).unwrap();
    assert_ne!(first.artifact_digest(), second.artifact_digest());
}

#[test]
fn ax_b01_inventory_preserves_four_profiles_and_refuses_oversize_stdin() {
    let l = limits();
    let mut planned = 0;
    let mut oversized = 0;
    let mut kinds = std::collections::BTreeSet::new();
    for line in
        include_str!("../../../../../contracts/ir-derived-obligations-v0.2/cases.tsv").lines()
    {
        let columns: Vec<_> = line.split('\t').collect();
        if !columns[0].starts_with("ax-b01") {
            continue;
        }
        let document = check_canonical_document(
            &std::fs::read(root().join(columns[1])).unwrap(),
            l.query.ir_json,
        )
        .unwrap();
        let set = generate_obligations(
            &document,
            ObligationProfile::VerificationV0_2,
            ObligationLimits {
                ir_json: l.query.ir_json,
                max_obligations: 100000,
                max_definition_bytes: 16000000,
                max_path_bytes: 8000000,
                max_output_bytes: 24000000,
            },
        )
        .unwrap();
        for profile in [
            QueryProfile::MapFilterV0_1,
            QueryProfile::MapFilterV0_2,
            QueryProfile::MapFilterV0_3,
            QueryProfile::MapFilterV0_4,
        ] {
            for target in set.obligations() {
                let query = match encode_query(
                    profile,
                    &document,
                    &set,
                    target.id(),
                    &generator(),
                    l.query,
                ) {
                    Ok(q) => q,
                    Err(QueryError::NotProve(_) | QueryError::UnsupportedKind(_)) => continue,
                    Err(e) => panic!("{e}"),
                };
                let result = plan_solver_request(
                    SolverProfile::Cvc5Query0_2ModelV0_1,
                    SolverRequestInput {
                        document: &document,
                        obligations: &set,
                        obligation_id: target.id(),
                        query_profile: profile,
                        query: &query,
                        generator: &generator(),
                        tool: &tool(),
                    },
                    l,
                );
                kinds.insert(target.kind().as_str());
                if query.bytes().len() > 1_048_576 {
                    assert!(matches!(
                        result,
                        Err(SolverError::ResourceLimit {
                            resource: SolverResource::StdinBytes,
                            ..
                        })
                    ));
                    oversized += 1;
                } else {
                    let req = result.unwrap();
                    assert_eq!(req.stdin_bytes(), query.bytes());
                    assert_eq!(req.query.symbols(), query.symbols());
                    assert_eq!(req.query.usage(), query.usage());
                    planned += 1;
                }
            }
        }
    }
    assert_eq!(planned, 0, "原容量材料不应通过偷偷放宽 stdin 上限成功");
    assert_eq!(oversized, 72);
    assert_eq!(kinds.len(), 5);
    eprintln!("P4-A AX-B01: {planned} requests, {oversized} stdin-limit refusals");
}

#[test]
fn fresh_text_collisions_skip_literal_names_and_hidden_classes_are_not_exported() {
    let l = limits();
    let (d, set, q) = setup("contracts/solver-model-v0.1/inputs/composite.jcs", l);
    let req = plan(&d, &set, &q, l).unwrap();
    let mut source = synthetic(&req, false);
    let active=req.query.symbols().iter().find(|s|matches!(s.origin(),crate::query::SymbolOrigin::Input{interface,slot:0,component:None} if interface.as_ref()=="in")).unwrap().name();
    source = replace_value(&req, &source, active, "true");
    let name=req.query.symbols().iter().find(|s|matches!(s.origin(),crate::query::SymbolOrigin::Input{interface,slot:0,component:Some(12)} if interface.as_ref()=="in")).unwrap().name();
    source = replace_value(&req, &source, name, "@Text_999");
    let r = parse_solver_response(&req, super::response(&req, source.as_bytes())).unwrap();
    let candidate = decode_model_world(&req, r.sat_model().unwrap()).unwrap();
    assert_eq!(
        std::str::from_utf8(candidate.text_class_bytes()).unwrap(),
        format!("[{{\"symbols\":[\"{name}\"],\"text\":\"@axiom-text:0:1\"}}]")
    );
}
