use super::tests::*;
use crate::{
    query::{QueryLimits, QueryProfile, SymbolOrigin, encode_query},
    solver::*,
};
fn request(d: &CanonicalDocument, s: &ObligationSet) -> SolverRequest {
    let query = QueryLimits {
        ir_json: limits().ir_json,
        max_input_slots: 10000,
        max_value_cells: 10_000_000,
        max_expression_instances: 1_000_000,
        max_slot_comparisons: 1_000_000,
        max_smt_nodes: 10_000_000,
        max_output_bytes: 100_000_000,
    };
    let q = encode_query(
        QueryProfile::MapFilterV0_4,
        d,
        s,
        guarantee(s),
        &generator(),
        query,
    )
    .unwrap();
    let tool = SolverToolIdentity::new(
        "macos-arm64",
        &format!("sha256:{}", "b".repeat(64)),
        &format!("sha256:{}", "c".repeat(64)),
    )
    .unwrap();
    let l = SolverLimits {
        query,
        request_bytes: 100000,
        response_bytes: 4_194_304,
        symbol_bytes: 2_000_000,
        layout_bytes: 2_000_000,
        tokens: 1_000_000,
        token_bytes: 4_194_304,
        syntax_nodes: 2_000_000,
        syntax_depth: 128,
        integer_digits: 1000,
        definitions: 100_000,
        alias_edges: 100_000,
        layout_items: 1_000_000,
        input_slots: 10000,
        value_cells: 10_000_000,
        decode_steps: 1_000_000,
        text_bytes: 2_000_000,
        world_bytes: 4_000_000,
        candidate_bytes: 5_000_000,
    };
    plan_solver_request(
        SolverProfile::Cvc5Query0_2ModelV0_1,
        SolverRequestInput {
            document: d,
            obligations: s,
            obligation_id: guarantee(s),
            query_profile: QueryProfile::MapFilterV0_4,
            query: &q,
            generator: &generator(),
            tool: &tool,
        },
        l,
    )
    .unwrap()
}
fn response(req: &SolverRequest, stdout: &[u8]) -> SolverResponse {
    parse_solver_response(
        req,
        SolverResponseInput {
            request_digest: req.artifact_digest(),
            stdout,
            stderr: b"",
            stdout_complete: true,
            stderr_complete: true,
            exit: ProcessExit::Exited(0),
            outer_termination: OuterTermination::None,
        },
    )
    .unwrap()
}
#[test]
fn model_candidate_source_is_checked_and_distinct_from_provided_world() {
    let (d, s) = setup("contracts/map-filter-query-v0.1/inputs/identity.jcs");
    let req = request(&d, &s);
    let mut lines = Vec::new();
    for symbol in req.query().symbols() {
        let v = match symbol.origin() {
            SymbolOrigin::Input {
                slot,
                component: None,
                ..
            } => {
                if *slot == 0 {
                    "true"
                } else {
                    "false"
                }
            }
            _ => match symbol.sort() {
                "Bool" => "false",
                "Int" => "0",
                "Text" => "@Text_0",
                _ => unreachable!(),
            },
        };
        lines.push(format!(
            "(define-fun {} () {} {v})",
            symbol.name(),
            symbol.sort()
        ));
    }
    let first = response(&req, format!("sat\n(\n{}\n)", lines.join("\n")).as_bytes());
    let model = first.sat_model().unwrap();
    let candidate = decode_model_world(&req, model).unwrap();
    let run = |r: &SolverRequest, m: &SatModel, c: &ModelWorldCandidate, id: &str| {
        super::replay_target(
            ReplayProfile::MapFilterV0_1,
            ReplayInput {
                document: &d,
                obligations: &s,
                obligation_id: id,
                generator: &generator(),
                world: ReplayWorldInput::ModelCandidate {
                    request: r,
                    model: m,
                    candidate: c,
                },
            },
            limits(),
        )
    };
    let observed = run(&req, model, &candidate, guarantee(&s)).unwrap();
    let direct = replay(&d, &s, guarantee(&s), candidate.world_bytes(), limits()).unwrap();
    assert_eq!(observed.result_bytes(), direct.result_bytes());
    assert_ne!(observed.artifact_digest(), direct.artifact_digest());
    lines.reverse();
    let second = response(
        &req,
        format!(
            "sat\n(\n{}\n)",
            lines.join("\n").replace("@Text_0", "@Text_71")
        )
        .as_bytes(),
    );
    let candidate2 = decode_model_world(&req, second.sat_model().unwrap()).unwrap();
    let observed2 = run(
        &req,
        second.sat_model().unwrap(),
        &candidate2,
        guarantee(&s),
    )
    .unwrap();
    assert_eq!(candidate.world_bytes(), candidate2.world_bytes());
    assert_eq!(observed.result_bytes(), observed2.result_bytes());
    assert_ne!(observed.artifact_digest(), observed2.artifact_digest());
    assert!(matches!(
        run(&req, second.sat_model().unwrap(), &candidate, guarantee(&s)),
        Err(ReplayError::Model(_))
    ));
    let other = s
        .obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::Totality)
        .unwrap()
        .id();
    assert!(matches!(
        run(&req, model, &candidate, other),
        Err(ReplayError::BindingMismatch)
    ));
    let unknown = response(&req, b"unknown");
    assert!(unknown.sat_model().is_none());
}
