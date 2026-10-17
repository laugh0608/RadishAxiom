use super::*;
use crate::{
    document::check_canonical_document,
    json::JsonLimits,
    obligations::{ObligationKind, ObligationLimits, ObligationProfile, generate_obligations},
    query::encode_query,
};
use std::path::PathBuf;

mod adversarial;
mod binding;
mod compact;
mod compact_replay;
mod independent;
mod legacy;
mod resources;
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn limits() -> SolverLimits {
    SolverLimits {
        query: QueryLimits {
            ir_json: JsonLimits {
                max_input_bytes: 16_000_000,
                max_values: 2_000_000,
                max_nesting: 128,
            },
            max_input_slots: 10000,
            max_value_cells: 10000000,
            max_expression_instances: 1000000,
            max_slot_comparisons: 1000000,
            max_smt_nodes: 10000000,
            max_output_bytes: 100000000,
        },
        request_bytes: 100000,
        response_bytes: 10000,
        symbol_bytes: 2_000_000,
        layout_bytes: 2_000_000,
        tokens: 1000000,
        token_bytes: 4_194_304,
        syntax_nodes: 2_000_000,
        syntax_depth: 128,
        integer_digits: 1000,
        definitions: 100000,
        alias_edges: 100000,
        layout_items: 1_000_000,
        input_slots: 10000,
        value_cells: 10_000_000,
        decode_steps: 1_000_000,
        text_bytes: 2_000_000,
        world_bytes: 4_000_000,
        candidate_bytes: 5_000_000,
    }
}
fn tool() -> SolverToolIdentity {
    SolverToolIdentity::new(
        "macos-arm64",
        &format!("sha256:{}", "b".repeat(64)),
        &format!("sha256:{}", "c".repeat(64)),
    )
    .unwrap()
}
fn generator() -> GeneratorIdentity {
    GeneratorIdentity::new(&format!("sha256:{}", "a".repeat(64))).unwrap()
}
fn setup(path: &str, l: SolverLimits) -> (CanonicalDocument, ObligationSet, EncodedQuery) {
    let doc = check_canonical_document(&std::fs::read(root().join(path)).unwrap(), l.query.ir_json)
        .unwrap();
    let set = generate_obligations(
        &doc,
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
    let id = set
        .obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::ContractGuarantee)
        .unwrap()
        .id();
    let q = encode_query(
        QueryProfile::MapFilterV0_4,
        &doc,
        &set,
        id,
        &generator(),
        l.query,
    )
    .unwrap();
    (doc, set, q)
}
fn plan(
    doc: &CanonicalDocument,
    set: &ObligationSet,
    q: &EncodedQuery,
    l: SolverLimits,
) -> Result<SolverRequest> {
    plan_solver_request(
        SolverProfile::Cvc5Query0_2ModelV0_1,
        SolverRequestInput {
            document: doc,
            obligations: set,
            obligation_id: q.binding().obligation(),
            query_profile: QueryProfile::MapFilterV0_4,
            query: q,
            generator: &generator(),
            tool: &tool(),
        },
        l,
    )
}
fn request(name: &str) -> SolverRequest {
    let l = limits();
    let (d, s, q) = setup(
        &format!("contracts/map-filter-query-v0.1/inputs/{name}.jcs"),
        l,
    );
    plan(&d, &s, &q, l).unwrap()
}
fn response<'a>(req: &'a SolverRequest, stdout: &'a [u8]) -> SolverResponseInput<'a> {
    SolverResponseInput {
        request_digest: req.artifact_digest(),
        stdout,
        stderr: b"",
        stdout_complete: true,
        stderr_complete: true,
        exit: ProcessExit::Exited(0),
        outer_termination: OuterTermination::None,
    }
}
fn synthetic(req: &SolverRequest, active: bool) -> String {
    // 合成所有活动值为零的模型；具体世界期望在独立测试或手算断言中确定。
    let mut text = "sat\n(\n".to_owned();
    let mut literal = 0usize;
    for sym in req.query.symbols() {
        let v = match sym.origin() {
            crate::query::SymbolOrigin::TextLiteral(_) => {
                let s = format!("(as @Text_{literal} Text)");
                literal += 1;
                s
            }
            crate::query::SymbolOrigin::Input {
                component: None, ..
            } => active.to_string(),
            _ => match sym.sort() {
                "Bool" => "false".into(),
                "Int" => "0".into(),
                "Text" => "(as @Text_0 Text)".into(),
                _ => unreachable!(),
            },
        };
        text.push_str(&format!(
            "(define-fun {} () {} {v})\n",
            sym.name(),
            sym.sort()
        ));
    }
    text.push_str(")\n");
    text
}
fn replace_value(req: &SolverRequest, stdout: &str, name: &str, value: &str) -> String {
    let sort = req.catalogue[name].name();
    let prefix = format!("(define-fun {name} () {sort} ");
    let mut found = false;
    let lines = stdout
        .lines()
        .map(|line| {
            if line.starts_with(&prefix) {
                found = true;
                format!("{prefix}{value})")
            } else {
                line.to_owned()
            }
        })
        .collect::<Vec<_>>();
    assert!(found);
    lines.join("\n") + "\n"
}
fn input_symbol(req: &SolverRequest, slot: usize, component: Option<usize>) -> String {
    req.query.symbols().iter().find(|s|matches!(s.origin(),crate::query::SymbolOrigin::Input{slot:i,component:c,..} if *i==slot&&*c==component)).unwrap().name().to_owned()
}
#[test]
fn minimal_request_response_and_empty_world_are_bound() {
    let req = request("minimal");
    let bytes = synthetic(&req, false);
    let resp = parse_solver_response(&req, response(&req, bytes.as_bytes())).unwrap();
    assert_eq!(resp.status(), SolverStatus::Sat);
    let world = decode_model_world(&req, resp.sat_model().unwrap()).unwrap();
    let table = &req.layout.inputs[0].table_type;
    assert_eq!(
        world.world_bytes(),
        format!("[{{\"interface\":\"in\",\"rows\":[],\"table_type\":\"{table}\"}}]").as_bytes()
    );
    assert_eq!(world.text_class_bytes(), b"[]");
    assert_eq!(
        world.artifact_digest(),
        crate::obligations::raw_digest(world.canonical_bytes())
    );
    assert_eq!(req.stdin_bytes(), req.query.bytes());
    assert_eq!(
        crate::obligations::raw_digest(req.canonical_bytes()),
        req.artifact_digest()
    );
    assert_eq!(
        crate::json::canonicalize_json(req.canonical_bytes(), limits().query.ir_json).unwrap(),
        req.canonical_bytes()
    );
    let mut bad = world.canonical_bytes().to_vec();
    bad.push(b'\n');
    assert!(matches!(
        check_model_world(&bad, &req, resp.sat_model().unwrap()),
        Err(SolverError::NonCanonical { .. })
    ));
}
