use super::*;

#[test]
fn deep_shared_type_and_graph_layout_is_linear_and_world_is_iterative() {
    let l = limits();
    let (d, set, q) = setup("contracts/solver-model-v0.1/inputs/deep-type.jcs", l);
    let req = plan(&d, &set, &q, l).unwrap();
    let source = synthetic(&req, false);
    let r = parse_solver_response(&req, response(&req, source.as_bytes())).unwrap();
    assert!(decode_model_world(&req, r.sat_model().unwrap()).is_ok());
    assert!(req.usage().get(SolverResource::ValueCells) < 2_000_000);
    let active = replace_value(&req, &source, &input_symbol(&req, 0, None), "true");
    let r = parse_solver_response(&req, response(&req, active.as_bytes())).unwrap();
    let world = decode_model_world(&req, r.sat_model().unwrap()).unwrap();
    assert!(world.world_bytes().len() > 500_000);
    assert_eq!(
        std::str::from_utf8(world.world_bytes())
            .unwrap()
            .matches("\"kind\":\"record\"")
            .count(),
        5002
    );
}

fn set_limit(l: &mut SolverLimits, r: SolverResource, n: usize) {
    use SolverResource::*;
    match r {
        RequestBytes => l.request_bytes = n,
        ResponseBytes => l.response_bytes = n,
        SymbolBytes => l.symbol_bytes = n,
        LayoutBytes => l.layout_bytes = n,
        Tokens => l.tokens = n,
        TokenBytes => l.token_bytes = n,
        SyntaxNodes => l.syntax_nodes = n,
        SyntaxDepth => l.syntax_depth = n,
        IntegerDigits => l.integer_digits = n,
        Definitions => l.definitions = n,
        AliasEdges => l.alias_edges = n,
        LayoutItems => l.layout_items = n,
        InputSlots => l.input_slots = n,
        ValueCells => l.value_cells = n,
        DecodeSteps => l.decode_steps = n,
        TextBytes => l.text_bytes = n,
        WorldBytes => l.world_bytes = n,
        CandidateBytes => l.candidate_bytes = n,
        _ => unreachable!(),
    }
}
#[test]
fn each_request_budget_refuses_before_success_and_exact_limits_are_inclusive() {
    let l = limits();
    let (d, set, q) = setup("contracts/map-filter-query-v0.1/inputs/identity.jcs", l);
    let request = plan(&d, &set, &q, l).unwrap();
    for resource in [
        SolverResource::SymbolBytes,
        SolverResource::LayoutBytes,
        SolverResource::LayoutItems,
        SolverResource::InputSlots,
        SolverResource::ValueCells,
        SolverResource::IntegerDigits,
    ] {
        let used = request.usage().get(resource);
        assert!(used > 0);
        let mut exact = l;
        set_limit(&mut exact, resource, used);
        assert!(plan(&d, &set, &q, exact).is_ok(), "{resource:?} exact");
        set_limit(&mut exact, resource, used - 1);
        assert!(
            matches!(plan(&d,&set,&q,exact),Err(SolverError::ResourceLimit{resource:r,..}) if r==resource),
            "{resource:?} refusal"
        );
    }
    let mut exact = l;
    for _ in 0..4 {
        exact.request_bytes = plan(&d, &set, &q, exact).unwrap().canonical_bytes().len() + 100;
    }
    // 请求包含自身预算文本；收敛到精确编码长度后检查边界。
    let length = plan(&d, &set, &q, exact).unwrap().canonical_bytes().len();
    exact.request_bytes = length;
    assert_eq!(
        plan(&d, &set, &q, exact).unwrap().canonical_bytes().len(),
        length
    );
    exact.request_bytes = length - 1;
    assert!(matches!(
        plan(&d, &set, &q, exact),
        Err(SolverError::ResourceLimit {
            resource: SolverResource::RequestBytes,
            ..
        })
    ));
}
#[test]
fn response_and_decode_budgets_have_exact_and_one_less_boundaries() {
    let l = limits();
    let (d, set, q) = setup("contracts/map-filter-query-v0.1/inputs/identity.jcs", l);
    let req = plan(&d, &set, &q, l).unwrap();
    let source = replace_value(
        &req,
        &synthetic(&req, false),
        &input_symbol(&req, 0, None),
        &input_symbol(&req, 1, None),
    );
    let resp = parse_solver_response(&req, response(&req, source.as_bytes())).unwrap();
    for resource in [
        SolverResource::ResponseBytes,
        SolverResource::Tokens,
        SolverResource::TokenBytes,
        SolverResource::SyntaxNodes,
        SolverResource::SyntaxDepth,
        SolverResource::IntegerDigits,
        SolverResource::Definitions,
        SolverResource::AliasEdges,
        SolverResource::ValueCells,
        SolverResource::DecodeSteps,
    ] {
        let used = resp.usage().get(resource);
        assert!(used > 0);
        let mut tight = l;
        set_limit(&mut tight, resource, used);
        // Request ValueCells / IntegerDigits 用量可大于 Response，用独立请求保持同一预算语义。
        if req.usage().get(resource) > used {
            continue;
        }
        let req = plan(&d, &set, &q, tight).unwrap();
        assert!(
            parse_solver_response(&req, response(&req, source.as_bytes())).is_ok(),
            "{resource:?} exact"
        );
        set_limit(&mut tight, resource, used - 1);
        let req = match plan(&d, &set, &q, tight) {
            Ok(v) => v,
            Err(SolverError::ResourceLimit { .. }) => continue,
            Err(e) => panic!("{e}"),
        };
        assert!(
            matches!(parse_solver_response(&req,response(&req,source.as_bytes())),Err(SolverError::ResourceLimit{resource:r,..}) if r==resource),
            "{resource:?} refusal"
        );
    }
    let source = replace_value(
        &req,
        &synthetic(&req, false),
        &input_symbol(&req, 0, None),
        "true",
    );
    let source = replace_value(&req, &source, &input_symbol(&req, 0, Some(9)), "@Text_999");
    let resp = parse_solver_response(&req, response(&req, source.as_bytes())).unwrap();
    let decoded = decode_model_world(&req, resp.sat_model().unwrap()).unwrap();
    for resource in [
        SolverResource::TextBytes,
        SolverResource::WorldBytes,
        SolverResource::CandidateBytes,
        SolverResource::DecodeSteps,
    ] {
        let used = decoded.usage().get(resource);
        assert!(used > 0);
        let mut tight = l;
        set_limit(&mut tight, resource, used);
        if req.usage().get(resource) > used || resp.usage().get(resource) > used {
            continue;
        }
        let req = plan(&d, &set, &q, tight).unwrap();
        let resp = parse_solver_response(&req, response(&req, source.as_bytes())).unwrap();
        assert!(
            decode_model_world(&req, resp.sat_model().unwrap()).is_ok(),
            "{resource:?} exact"
        );
        set_limit(&mut tight, resource, used - 1);
        let req = plan(&d, &set, &q, tight).unwrap();
        let resp = match parse_solver_response(&req, response(&req, source.as_bytes())) {
            Ok(v) => v,
            Err(SolverError::ResourceLimit { .. }) => continue,
            Err(e) => panic!("{e}"),
        };
        assert!(
            matches!(decode_model_world(&req,resp.sat_model().unwrap()),Err(SolverError::ResourceLimit{resource:r,..}) if r==resource),
            "{resource:?} refusal"
        );
    }
}
#[test]
fn overflow_deep_frames_and_large_integers_are_bounded() {
    let mut b = Budget::new(limits(), SolverStage::Decode);
    b.limits.value_cells = usize::MAX;
    b.charge(SolverResource::ValueCells, usize::MAX).unwrap();
    assert!(matches!(
        b.charge(SolverResource::ValueCells, 1),
        Err(SolverError::ResourceLimit {
            resource: SolverResource::ValueCells,
            ..
        })
    ));
    let req = request("minimal");
    let nested = format!("sat {}{}", "(".repeat(10000), ")".repeat(10000));
    assert!(parse_solver_response(&req, response(&req, nested.as_bytes())).is_err());
    let l = limits();
    let (d, set, q) = setup("contracts/map-filter-query-v0.1/inputs/identity.jcs", l);
    let mut l = l;
    l.integer_digits = 3;
    let req = plan(&d, &set, &q, l).unwrap();
    let integer = input_symbol(&req, 0, Some(0));
    let model = replace_value(&req, &synthetic(&req, false), &integer, &"9".repeat(10000));
    assert!(matches!(
        parse_solver_response(&req, response(&req, model.as_bytes())),
        Err(SolverError::ResourceLimit {
            resource: SolverResource::IntegerDigits,
            ..
        })
    ));
}
