mod common;
use common::*;
use radishaxiom_ir::{
    query::QueryProfile,
    solver::{PROCESS_LIMITS, SolverProfile, SolverRequestInput, SolverToolIdentity},
};
use radishaxiom_solver_diagnostic_host::{bootstrap_start::*, e3_wire::*};
use radishaxiom_solver_supervision_core::{bootstrap_start::*, handshake::*};

fn declarations() -> StartMaterialDeclarations {
    StartMaterialDeclarations {
        attempt: [1; 32],
        policy_bundle: [2; 32],
        image: [3; 32],
        configuration: [4; 32],
    }
}
fn plan(
    case: &Case,
    request_bytes: &[u8],
    actual_query: &[u8],
    tool: &SolverToolIdentity,
) -> Result<StartupDeclarationPlan, StartupPlanError> {
    StartupDeclarationPlan::from_request_bytes(
        request_bytes,
        SolverProfile::Cvc5Query0_3ModelV0_1,
        SolverRequestInput {
            document: &case.document,
            obligations: &case.obligations,
            obligation_id: case.request.query().binding().obligation(),
            query_profile: QueryProfile::MapFilterV0_5,
            query: case.request.query(),
            generator: &generator(),
            tool,
        },
        solver_limits().with_compact(compact_limits()),
        declarations(),
        actual_query,
    )
}
#[test]
fn strict_request_query_and_existing_wire_are_bound_without_execution_authority() {
    let case = minimal();
    let tool = tool();
    let planned = plan(
        &case,
        case.request.canonical_bytes(),
        case.request.stdin_bytes(),
        &tool,
    )
    .unwrap();
    assert_eq!(planned.scope(), "external-declaration-check-and-plan");
    assert_eq!(planned.description().scope(), "external-declarations-only");
    let fields = planned.description().fields();
    assert_eq!(
        fields.request,
        radishaxiom_digest::digest(case.request.canonical_bytes())
    );
    assert_eq!(
        fields.query_digest,
        radishaxiom_digest::digest(case.request.stdin_bytes())
    );
    assert_eq!(
        fields.query_bytes as usize,
        case.request.stdin_bytes().len()
    );
    assert_eq!(
        format!(
            "sha256:{}",
            fields
                .cli_acceptance
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<String>()
        ),
        tool.acceptance_record_digest()
    );
    let descriptor = StartDescription::parse(
        &planned.description().canonical_bytes(),
        process_wire_limits(),
    )
    .unwrap();
    let binding = descriptor.binding([5; 32]);
    let local = LocalReadyDeclaration {
        boot_digest: [6; 32],
        namespace_digest: [7; 32],
        configuration_digest: fields.configuration,
        nonce: [5; 32],
    };
    let mut s = SupervisorHandshake::new(
        descriptor.clone(),
        LinuxInstant::declared_ns(1000),
        local,
        process_handshake_window().unwrap(),
    )
    .unwrap();
    let ready = s.ready(LinuxInstant::declared_ns(1100)).unwrap();
    let encoded = BootstrapEncoder::new(Direction::SupervisorToMac)
        .encode(&ready)
        .unwrap();
    let frame = BootstrapDecoder::new_bound(Direction::SupervisorToMac, binding.clone())
        .poll(&encoded)
        .unwrap()
        .frame
        .unwrap();
    let mut mac = MacHandshake::new(
        descriptor,
        MacInstant::declared_ns(100),
        10,
        ExpectedReadyDeclaration {
            boot_digest: [6; 32],
            namespace_digest: [7; 32],
        },
        process_handshake_window().unwrap(),
    )
    .unwrap();
    let arm = mac
        .receive_ready(MacInstant::declared_ns(300), &frame)
        .unwrap();
    let encoded = BootstrapEncoder::new(Direction::MacToSupervisor)
        .encode(&arm)
        .unwrap();
    let arm = BootstrapDecoder::new_bound(Direction::MacToSupervisor, binding.clone())
        .poll(&encoded)
        .unwrap()
        .frame
        .unwrap();
    s.receive_arm(LinuxInstant::declared_ns(1200), &arm)
        .unwrap();
    assert_eq!(
        s.query_complete(
            LinuxInstant::declared_ns(1300),
            &binding,
            case.request.stdin_bytes()
        )
        .unwrap()
        .scope(),
        planned.scope()
    );
}
#[test]
fn strict_corruption_wrong_request_tool_and_actual_query_are_rejected() {
    let case = minimal();
    let tool = tool();
    let mut corrupt = case.request.canonical_bytes().to_vec();
    corrupt.push(b'\n');
    assert!(matches!(
        plan(&case, &corrupt, case.request.stdin_bytes(), &tool),
        Err(StartupPlanError::Solver(_))
    ));
    let mut wrong = case.request.stdin_bytes().to_vec();
    wrong[0] ^= 1;
    assert!(matches!(
        plan(&case, case.request.canonical_bytes(), &wrong, &tool),
        Err(StartupPlanError::Start(StartError::QueryDigest))
    ));
    assert!(matches!(
        plan(
            &case,
            case.request.canonical_bytes(),
            &wrong[..wrong.len() - 1],
            &tool
        ),
        Err(StartupPlanError::Start(StartError::QueryLength { .. }))
    ));
    let changed = SolverToolIdentity::new(
        "linux-arm64",
        tool.payload_digest(),
        &format!("sha256:{}", "0".repeat(64)),
    )
    .unwrap();
    assert!(matches!(
        plan(
            &case,
            case.request.canonical_bytes(),
            case.request.stdin_bytes(),
            &changed
        ),
        Err(StartupPlanError::Solver(_))
    ));
    let other = composite();
    assert!(matches!(
        plan(
            &case,
            other.request.canonical_bytes(),
            case.request.stdin_bytes(),
            &tool
        ),
        Err(StartupPlanError::Solver(_))
    ));
}
#[test]
fn original_capacity_query_and_original_byte_budget_are_preserved() {
    let case = wrong_add();
    let tool = tool();
    assert!(case.request.stdin_bytes().len() > 250_000);
    assert!(case.request.stdin_bytes().len() <= PROCESS_LIMITS.stdin_bytes);
    let plan = plan(
        &case,
        case.request.canonical_bytes(),
        case.request.stdin_bytes(),
        &tool,
    )
    .unwrap();
    assert_eq!(plan.request().stdin_bytes(), case.request.stdin_bytes());
    assert_eq!(
        process_handshake_window().unwrap().wall_clock_ns,
        PROCESS_LIMITS.wall_clock_ms * 1_000_000
    );
    let limits = process_wire_limits();
    for size in [1, PROCESS_LIMITS.stdin_bytes] {
        let bytes = vec![b'x'; size];
        let mut fields = plan.description().fields().clone();
        fields.query_bytes = size as u32;
        fields.query_digest = radishaxiom_digest::digest(&bytes);
        let description = StartDescription::new(fields, limits).unwrap();
        assert_eq!(description.validate_query(&bytes), Ok(()));
        assert_eq!(
            StartDescription::parse(&description.canonical_bytes(), limits).unwrap(),
            description
        );
    }
    let mut fields = plan.description().fields().clone();
    fields.query_bytes = (PROCESS_LIMITS.stdin_bytes + 1) as u32;
    assert!(matches!(
        StartDescription::new(fields, limits),
        Err(StartError::QueryLength { .. })
    ));
}

#[path = "common/e3_workflow.rs"]
mod e3_workflow;
#[test]
fn separated_handshake_matches_2700_case_independent_matrix_and_old_simulation() {
    let query = b"(check-sat)\n";
    let description = StartDescription::new(
        StartFields {
            attempt: [1; 32],
            request: [2; 32],
            query_bytes: query.len() as u32,
            query_digest: radishaxiom_digest::digest(query),
            policy_bundle: [3; 32],
            image: [4; 32],
            cli_acceptance: [5; 32],
            configuration: [11; 32],
        },
        process_wire_limits(),
    )
    .unwrap();
    let window = process_handshake_window().unwrap();
    let ms = 1_000_000;
    let original_ms = i128::from(PROCESS_LIMITS.wall_clock_ms);
    let mut counts = (0, 0);
    for entry in [0_u64, 100, 3000, 7000] {
        for setup in [0_u64, 1, 1000] {
            for offset in [0_u64, 1_000_000, 1_000_000_000_000] {
                for ready_delay in [0_u64, 1, 100, 3000, 7000] {
                    for arm_delay in [0_u64, 1, 100, 3000, 7000] {
                        for delta in [0_u64, 1, 100] {
                            let received = entry + setup + ready_delay;
                            let arrival = received + arm_delay;
                            // Independent unit-rate/no-pause causal reference in ms.
                            // Linux offsets cancel; no comparison of absolute clocks.
                            let remaining = original_ms - i128::from(received) - i128::from(delta);
                            let expected = remaining > 0
                                && i128::from(arrival)
                                    < original_ms - i128::from(ready_delay) - i128::from(delta);
                            let local = LocalReadyDeclaration {
                                boot_digest: [8; 32],
                                namespace_digest: [9; 32],
                                configuration_digest: [11; 32],
                                nonce: [5; 32],
                            };
                            let mut s = SupervisorHandshake::new(
                                description.clone(),
                                LinuxInstant::declared_ns((entry + offset) * ms),
                                local,
                                window,
                            )
                            .unwrap();
                            let mut mac = MacHandshake::new(
                                description.clone(),
                                MacInstant::declared_ns(0),
                                delta * ms,
                                ExpectedReadyDeclaration {
                                    boot_digest: [8; 32],
                                    namespace_digest: [9; 32],
                                },
                                window,
                            )
                            .unwrap();
                            let ready = s
                                .ready(LinuxInstant::declared_ns((entry + setup + offset) * ms))
                                .unwrap();
                            let actual = match mac
                                .receive_ready(MacInstant::declared_ns(received * ms), &ready)
                            {
                                Ok(arm) => {
                                    let now = LinuxInstant::declared_ns((arrival + offset) * ms);
                                    match s.receive_arm(now, &arm) {
                                        Ok(deadline) => {
                                            let accepted =
                                                s.query_complete(now, &arm.binding, query).is_ok();
                                            if accepted {
                                                assert!(
                                                    deadline.deadline().as_ns() - offset * ms
                                                        <= (PROCESS_LIMITS.wall_clock_ms - delta)
                                                            * ms
                                                );
                                            }
                                            accepted
                                        }
                                        Err(_) => false,
                                    }
                                }
                                Err(_) => false,
                            };
                            assert_eq!(
                                actual, expected,
                                "entry={entry},setup={setup},offset={offset},ready_delay={ready_delay},arm_delay={arm_delay},delta={delta}"
                            );
                            if actual {
                                counts.0 += 1;
                            } else {
                                counts.1 += 1;
                            }
                        }
                    }
                }
            }
        }
    }
    assert_eq!(counts, (891, 1809));
    assert_eq!(counts, e3_workflow::timing_matrix());
}
