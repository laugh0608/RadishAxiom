#![allow(dead_code)]

use radishaxiom_ir::{
    document::{CanonicalDocument, check_canonical_document},
    json::JsonLimits,
    obligations::{
        ObligationKind, ObligationLimits, ObligationProfile, ObligationSet, generate_obligations,
    },
    query::{
        CompactQueryLimits, GeneratorIdentity, QueryLimits, QueryProfile, SymbolOrigin,
        encode_query,
    },
    replay::ReplayLimits,
    solver::{
        SolverLimits, SolverProfile, SolverRequest, SolverRequestInput, SolverToolIdentity,
        plan_solver_request,
    },
};
use radishaxiom_solver_diagnostic_host::*;
use std::path::PathBuf;

pub const WRONG_ADD_TARGET: &str =
    "sha256:4916b2ef17b43cab21bff8ae87433922c60fbf86fb72fc52972e06964584476e";
pub const WRONG_ADD_QUERY: &str =
    "sha256:5ba58e0d9754c3448f299ce4d9be2060c2d91d829253ec3e4a170e0d4d07a85a";
pub const MATERIALS: [&[u8]; 13] = [
    b"simulation-only archive",
    b"simulation-only CLI",
    b"simulation-only inventory",
    b"simulation-only licenses",
    b"simulation-only acceptance claim, NOT accepted",
    b"simulation-only host",
    b"simulation-only context",
    b"simulation-only daemon",
    b"simulation-only kernel",
    b"simulation-only runtime",
    b"simulation-only image",
    b"simulation-only bootstrap",
    b"simulation-only policy",
];

pub fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
pub fn host_limits() -> HostLimits {
    HostLimits {
        material_bytes: 16_000_000,
        total_material_bytes: 128_000_000,
        record_bytes: 32_000_000,
        stream_bytes: 8_000_000,
        control_diagnostic_bytes: 65_536,
        failure_facts: 1000,
        json_values: 100_000,
        json_nesting: 64,
    }
}
pub fn identity() -> SimulationIdentity {
    let digests = MATERIALS.map(raw_digest);
    let material = |i: usize| MaterialInput {
        bytes: MATERIALS[i],
        expected_raw_digest: digests[i].as_str(),
        byte_limit: MATERIALS[i].len(),
    };
    SimulationIdentity::new(
        SimulationIdentityInput {
            payload: SimulationPayloadInput {
                platform: "linux-arm64",
                cli_member: "cvc5-Linux-arm64-static/bin/cvc5",
                archive: material(0),
                cli: material(1),
                inventory: material(2),
                licenses: material(3),
                acceptance: material(4),
            },
            host: SimulationHostInput {
                platform: "linux-arm64",
                context: "orbstack",
                host: material(5),
                context_record: material(6),
                daemon: material(7),
                kernel: material(8),
                runtime: material(9),
                image: material(10),
                bootstrap: material(11),
                policy: material(12),
            },
        },
        host_limits(),
    )
    .unwrap()
}
pub fn tool() -> SolverToolIdentity {
    SolverToolIdentity::new(
        "linux-arm64",
        &raw_digest(MATERIALS[0]),
        &raw_digest(MATERIALS[4]),
    )
    .unwrap()
}
pub fn generator() -> GeneratorIdentity {
    GeneratorIdentity::new(&format!("sha256:{}", "a".repeat(64))).unwrap()
}
pub fn json_limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16_000_000,
        max_values: 2_000_000,
        max_nesting: 128,
    }
}
pub fn solver_limits() -> SolverLimits {
    SolverLimits {
        query: QueryLimits {
            ir_json: json_limits(),
            max_input_slots: 10_000,
            max_value_cells: 10_000_000,
            max_expression_instances: 1_000_000,
            max_slot_comparisons: 1_000_000,
            max_smt_nodes: 10_000_000,
            max_output_bytes: 1_048_576,
        },
        request_bytes: 100_000,
        response_bytes: 8_000_000,
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
        input_slots: 10_000,
        value_cells: 10_000_000,
        decode_steps: 1_000_000,
        text_bytes: 2_000_000,
        world_bytes: 4_000_000,
        candidate_bytes: 5_000_000,
    }
}
pub fn compact_limits() -> CompactQueryLimits {
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
pub struct Case {
    pub document: CanonicalDocument,
    pub obligations: ObligationSet,
    pub request: SolverRequest,
}
pub fn case(path: &str, exact_target: Option<&str>) -> Case {
    let limits = solver_limits();
    let document =
        check_canonical_document(&std::fs::read(root().join(path)).unwrap(), json_limits())
            .unwrap();
    let obligations = generate_obligations(
        &document,
        ObligationProfile::VerificationV0_2,
        ObligationLimits {
            ir_json: json_limits(),
            max_obligations: 100_000,
            max_definition_bytes: 16_000_000,
            max_path_bytes: 8_000_000,
            max_output_bytes: 24_000_000,
        },
    )
    .unwrap();
    let target = exact_target.unwrap_or_else(|| {
        obligations
            .obligations()
            .iter()
            .find(|o| o.kind() == ObligationKind::ContractGuarantee)
            .unwrap()
            .id()
    });
    let generator = generator();
    let query = encode_query(
        QueryProfile::MapFilterV0_5,
        &document,
        &obligations,
        target,
        &generator,
        limits.query.with_compact(compact_limits()),
    )
    .unwrap();
    let request = plan_solver_request(
        SolverProfile::Cvc5Query0_3ModelV0_1,
        SolverRequestInput {
            document: &document,
            obligations: &obligations,
            obligation_id: target,
            query_profile: QueryProfile::MapFilterV0_5,
            query: &query,
            generator: &generator,
            tool: &tool(),
        },
        limits.with_compact(compact_limits()),
    )
    .unwrap();
    Case {
        document,
        obligations,
        request,
    }
}
pub fn minimal() -> Case {
    case("contracts/map-filter-query-v0.1/inputs/minimal.jcs", None)
}
pub fn wrong_add() -> Case {
    case(
        "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-wrong-add.jcs",
        Some(WRONG_ADD_TARGET),
    )
}
pub fn composite() -> Case {
    case("contracts/solver-model-v0.1/inputs/composite.jcs", None)
}

// Hand-selected synthetic terms mirror the documented composite case, without
// reading private IR representations or deriving solver answers from the query.
const COMPOSITE_VALUES: [[&str; 14]; 5] = [
    [
        "8888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888",
        "7",
        "true",
        "10",
        "0",
        "true",
        "@Text_20",
        "true",
        "false",
        "999",
        "false",
        "999",
        "@Text_3",
        "@Text_21",
    ],
    [
        "999", "999", "false", "999", "999", "true", "@Text_22", "true", "true", "999", "true",
        "999", "@Text_22", "@Text_22",
    ],
    [
        "(- 8888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888)",
        "(- 7)",
        "false",
        "(- 2)",
        "1",
        "false",
        "@Text_23",
        "false",
        "false",
        "999",
        "true",
        "2",
        "@Text_20",
        "@Text_0",
    ],
    [
        "0", "0", "false", "(- 10)", "2", "true", "@Text_2", "true", "true", "2", "true", "0",
        "@Text_2", "@Text_21",
    ],
    [
        "0", "0", "true", "10", "1", "false", "@Text_23", "false", "true", "999", "false", "999",
        "@Text_3", "@Text_0",
    ],
];

/// Synthetic complete solver output, generated from the public symbol catalogue.
/// Values are hand selected; no solver or derived query term supplies an answer.
pub fn model(request: &SolverRequest, kind: &str) -> Vec<u8> {
    let mut out = String::from("sat\n(\n");
    for symbol in request.query().symbols() {
        let value = match symbol.origin() {
            SymbolOrigin::TextLiteral(text) => {
                if kind == "composite" {
                    let i = ["", "@axiom-text:0:0", "e\u{301}", "é"]
                        .iter()
                        .position(|v| *v == text)
                        .unwrap();
                    format!("@Text_{i}")
                } else {
                    assert_eq!(text, "");
                    "@Text_0".to_owned()
                }
            }
            SymbolOrigin::Input {
                interface,
                slot,
                component,
            } => {
                if kind == "composite" {
                    if interface.as_ref() == "in" {
                        component
                            .map(|i| COMPOSITE_VALUES[*slot][i].to_owned())
                            .unwrap_or_else(|| (*slot != 1).to_string())
                    } else {
                        assert_eq!(interface.as_ref(), "另一路");
                        component
                            .map(|_| if *slot == 0 { "true" } else { "false" }.to_owned())
                            .unwrap_or_else(|| (*slot == 1).to_string())
                    }
                } else if kind == "wrong-add" {
                    assert_eq!(interface.as_ref(), "orders");
                    match component {
                        None => (*slot < 3).to_string(),
                        // Canonical input leaf order: discount, order_id, state, subtotal.
                        Some(0) => ["10", "5", "0"].get(*slot).unwrap_or(&"0").to_string(),
                        Some(1) => format!("@Text_{}", slot + 1),
                        Some(2) => if *slot < 2 { "1" } else { "0" }.to_owned(),
                        Some(3) => ["10", "20", "8"].get(*slot).unwrap_or(&"0").to_string(),
                        _ => unreachable!(),
                    }
                } else {
                    match (component, symbol.sort()) {
                        (None, _) | (_, "Bool") => "false".into(),
                        (_, "Int") => "0".into(),
                        (_, "Text") => "@Text_0".into(),
                        _ => unreachable!(),
                    }
                }
            }
        };
        out.push_str(&format!(
            "(define-fun {} () {} {value})\n",
            symbol.name(),
            symbol.sort()
        ));
    }
    out.push_str(")\n");
    out.into_bytes()
}
pub fn replay_limits() -> ReplayLimits {
    ReplayLimits {
        ir_json: json_limits(),
        world_bytes: 16_000_000,
        world_nodes: 2_000_000,
        world_depth: 30_000,
        type_items: 2_000_000,
        rows: 100_000,
        value_cells: 100_000_000,
        evaluation_steps: 10_000_000,
        comparisons: 10_000_000,
        integer_digits: 1000,
        digit_work: 100_000_000,
        text_bytes: 16_000_000,
        path_bytes: 16_000_000,
        output_bytes: 16_000_000,
    }
}

pub fn advance(
    controller: &mut SimulationController<'_, '_>,
    at_ms: u64,
    kind: SimulationEventKind,
) -> SimulationTransition {
    controller.advance(SimulationEvent {
        token: controller.token().clone(),
        at_ms,
        kind,
    })
}
pub fn running<'p, 'r>(plan: &'p SimulationPlan<'r>) -> SimulationController<'p, 'r> {
    let (mut controller, action) =
        SimulationController::new(plan, "synthetic-container", 10, host_limits()).unwrap();
    assert_eq!(action.kind, SimulationActionKind::Create);
    let steps = [
        SimulationEventKind::Created,
        SimulationEventKind::Attached,
        SimulationEventKind::Started,
        SimulationEventKind::StdinWritten(plan.request().stdin_bytes().to_vec()),
        SimulationEventKind::StdinClosed,
    ];
    for (i, kind) in steps.into_iter().enumerate() {
        assert_eq!(
            advance(&mut controller, 11 + i as u64, kind).rejection,
            None
        );
    }
    controller
}
pub fn observed(
    plan: &SimulationPlan<'_>,
    stdout: &[u8],
    exit: radishaxiom_ir::solver::ProcessExit,
    cleanup_failed: bool,
) -> SimulationObservation {
    let mut controller = running(plan);
    // Exercise byte boundaries and independent stderr without changing bytes.
    for (index, chunk) in stdout.chunks(7).enumerate() {
        assert_eq!(
            advance(
                &mut controller,
                16,
                SimulationEventKind::Output {
                    stdout: chunk.to_vec(),
                    stderr: if index == 0 {
                        b"simulation diagnostic\n".to_vec()
                    } else {
                        Vec::new()
                    },
                }
            )
            .rejection,
            None
        );
    }
    for (at_ms, kind) in [
        (
            17,
            SimulationEventKind::StreamsClosed {
                stdout: true,
                stderr: true,
            },
        ),
        (18, SimulationEventKind::Exit(exit)),
        (19, SimulationEventKind::Inspected),
        (20, SimulationEventKind::TreeEmpty),
        (
            21,
            if cleanup_failed {
                SimulationEventKind::CleanupFailed(b"simulation cleanup failure".to_vec())
            } else {
                SimulationEventKind::Cleaned
            },
        ),
    ] {
        assert_eq!(advance(&mut controller, at_ms, kind).rejection, None);
    }
    controller.finish(22).unwrap()
}
