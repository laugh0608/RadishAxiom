mod common;

use common::*;
use radishaxiom_ir::{
    query::{QueryProfile, encode_query},
    solver::{
        OuterTermination, ProcessExit, SolverProfile, SolverRequest, SolverRequestInput,
        SolverToolIdentity, TransportReason, plan_solver_request,
    },
};
use radishaxiom_solver_diagnostic_host::*;

fn identity_input(digests: &[String; 13]) -> SimulationIdentityInput<'_> {
    let m = |i: usize| MaterialInput {
        bytes: MATERIALS[i],
        expected_raw_digest: &digests[i],
        byte_limit: MATERIALS[i].len(),
    };
    SimulationIdentityInput {
        payload: SimulationPayloadInput {
            platform: "linux-arm64",
            cli_member: "cvc5-Linux-arm64-static/bin/cvc5",
            archive: m(0),
            cli: m(1),
            inventory: m(2),
            licenses: m(3),
            acceptance: m(4),
        },
        host: SimulationHostInput {
            platform: "linux-arm64",
            context: "orbstack",
            host: m(5),
            context_record: m(6),
            daemon: m(7),
            kernel: m(8),
            runtime: m(9),
            image: m(10),
            bootstrap: m(11),
            policy: m(12),
        },
    }
}
fn material_mut<'a, 'b>(
    input: &'b mut SimulationIdentityInput<'a>,
    index: usize,
) -> &'b mut MaterialInput<'a> {
    match index {
        0 => &mut input.payload.archive,
        1 => &mut input.payload.cli,
        2 => &mut input.payload.inventory,
        3 => &mut input.payload.licenses,
        4 => &mut input.payload.acceptance,
        5 => &mut input.host.host,
        6 => &mut input.host.context_record,
        7 => &mut input.host.daemon,
        8 => &mut input.host.kernel,
        9 => &mut input.host.runtime,
        10 => &mut input.host.image,
        11 => &mut input.host.bootstrap,
        12 => &mut input.host.policy,
        _ => unreachable!(),
    }
}
fn object_mutations(bytes: &[u8]) -> Vec<Vec<u8>> {
    let text = std::str::from_utf8(bytes).unwrap();
    vec![
        format!("{{\"scope\":\"simulation\",{}", &text[1..]).into_bytes(),
        format!("{{\"unexpected\":true,{}", &text[1..]).into_bytes(),
        text.replace(",\"scope\":\"simulation\"", "").into_bytes(),
        format!("{text}\n").into_bytes(),
        text.replace("\"version\":\"0.1\"", "\"version\":\"0.2\"")
            .into_bytes(),
        text.replace("\"scope\":\"simulation\"", "\"scope\":\"real\"")
            .into_bytes(),
    ]
}
fn stream(bytes: &[u8]) -> SimulationStreamInput<'_> {
    SimulationStreamInput {
        bytes,
        observed_bytes: bytes.len(),
        complete: true,
        exceeded: false,
    }
}
fn observation_input(stdout: &[u8]) -> SimulationObservationInput<'_> {
    SimulationObservationInput {
        stdout: stream(stdout),
        stderr: stream(b""),
        control_diagnostics: stream(b""),
        exit: ProcessExit::Exited(0),
        started: true,
        elapsed_ms: 20,
        cleanup: CleanupStatus::ConfirmedEmpty,
        failures: &[],
    }
}
fn custom_request(
    case: &Case,
    tool: &SolverToolIdentity,
    compact: bool,
    response_bytes: usize,
) -> SolverRequest {
    let mut limits = solver_limits();
    limits.response_bytes = response_bytes;
    let target = case.request.query().binding().obligation();
    let profile = if compact {
        QueryProfile::MapFilterV0_5
    } else {
        QueryProfile::MapFilterV0_4
    };
    let query = if compact {
        encode_query(
            profile,
            &case.document,
            &case.obligations,
            target,
            &generator(),
            limits.query.with_compact(compact_limits()),
        )
        .unwrap()
    } else {
        encode_query(
            profile,
            &case.document,
            &case.obligations,
            target,
            &generator(),
            limits.query,
        )
        .unwrap()
    };
    plan_solver_request(
        if compact {
            SolverProfile::Cvc5Query0_3ModelV0_1
        } else {
            SolverProfile::Cvc5Query0_2ModelV0_1
        },
        SolverRequestInput {
            document: &case.document,
            obligations: &case.obligations,
            obligation_id: target,
            query_profile: profile,
            query: &query,
            generator: &generator(),
            tool,
        },
        if compact {
            limits.with_compact(compact_limits())
        } else {
            limits.into()
        },
    )
    .unwrap()
}

#[test]
fn every_material_is_checked_and_bound_but_never_accepted_or_qualified() {
    let digests = MATERIALS.map(raw_digest);
    let good = identity_input(&digests);
    let original = SimulationIdentity::new(good, host_limits()).unwrap();
    assert_eq!(
        raw_digest(original.canonical_bytes()),
        original.artifact_digest()
    );
    check_simulation_identity(original.canonical_bytes(), good, host_limits()).unwrap();
    for index in 0..13 {
        let mut wrong = good;
        let material = material_mut(&mut wrong, index);
        material.bytes = b"changed";
        material.byte_limit = material.bytes.len();
        assert!(matches!(
            SimulationIdentity::new(wrong, host_limits()),
            Err(HostError::BindingMismatch(_))
        ));
        let changed = raw_digest(b"changed");
        material_mut(&mut wrong, index).expected_raw_digest = &changed;
        assert!(SimulationIdentity::new(wrong, host_limits()).is_ok());
        assert!(matches!(
            check_simulation_identity(original.canonical_bytes(), wrong, host_limits()),
            Err(HostError::NonCanonical { .. })
        ));
    }
    for bytes in object_mutations(original.canonical_bytes()) {
        assert!(matches!(
            check_simulation_identity(&bytes, good, host_limits()),
            Err(HostError::NonCanonical { .. })
        ));
    }
    for (platform, context, member) in [
        (
            "macos-arm64",
            "orbstack",
            "cvc5-Linux-arm64-static/bin/cvc5",
        ),
        ("linux-arm64", "default", "cvc5-Linux-arm64-static/bin/cvc5"),
        ("linux-arm64", "orbstack", "other/bin/cvc5"),
    ] {
        let mut wrong = good;
        wrong.payload.platform = platform;
        wrong.host.context = context;
        wrong.payload.cli_member = member;
        assert!(matches!(
            SimulationIdentity::new(wrong, host_limits()),
            Err(HostError::BindingMismatch(_))
        ));
    }
}

#[test]
fn identity_budgets_are_exact_checked_and_precede_material_validation() {
    let digests = MATERIALS.map(raw_digest);
    let input = identity_input(&digests);
    let original = SimulationIdentity::new(input, host_limits()).unwrap();
    let total = MATERIALS.iter().map(|m| m.len()).sum();
    let mut limits = host_limits();
    limits.total_material_bytes = total;
    assert!(SimulationIdentity::new(input, limits).is_ok());
    limits.total_material_bytes = total - 1;
    assert!(matches!(
        SimulationIdentity::new(input, limits),
        Err(HostError::ResourceLimit("total_material_bytes"))
    ));
    for i in 0..13 {
        let mut short = input;
        let m = material_mut(&mut short, i);
        m.byte_limit = m.bytes.len() - 1;
        m.expected_raw_digest = "invalid";
        assert!(matches!(
            SimulationIdentity::new(short, host_limits()),
            Err(HostError::ResourceLimit("material_bytes"))
        ));
    }
    limits = host_limits();
    limits.record_bytes = original.canonical_bytes().len();
    assert!(SimulationIdentity::new(input, limits).is_ok());
    limits.record_bytes -= 1;
    assert!(matches!(
        SimulationIdentity::new(input, limits),
        Err(HostError::ResourceLimit("record_bytes"))
    ));
    limits = host_limits();
    limits.json_values = 1;
    assert!(matches!(
        SimulationIdentity::new(input, limits),
        Err(HostError::Json(_))
    ));
    limits = host_limits();
    limits.json_nesting = 1;
    assert!(matches!(
        SimulationIdentity::new(input, limits),
        Err(HostError::Json(_))
    ));
}

#[test]
fn plans_reuse_request_metadata_and_reject_all_cross_bindings() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    assert_eq!(plan.argument_tokens(), case.request.argument_tokens());
    assert_eq!(plan.process_limits(), case.request.process_limits());
    assert_eq!(
        case.request.tool().payload_digest(),
        identity.archive_raw_digest()
    );
    assert_ne!(identity.archive_raw_digest(), identity.cli_raw_digest());
    check_simulation_plan(
        plan.canonical_bytes(),
        &case.request,
        &identity,
        host_limits(),
    )
    .unwrap();
    for bytes in object_mutations(plan.canonical_bytes()) {
        assert!(matches!(
            check_simulation_plan(&bytes, &case.request, &identity, host_limits()),
            Err(HostError::NonCanonical { .. })
        ));
    }
    let wrong = raw_digest(b"wrong");
    for tool in [
        SolverToolIdentity::new("linux-arm64", &wrong, identity.acceptance_raw_digest()).unwrap(),
        SolverToolIdentity::new("linux-arm64", identity.archive_raw_digest(), &wrong).unwrap(),
        SolverToolIdentity::new(
            "macos-arm64",
            identity.archive_raw_digest(),
            identity.acceptance_raw_digest(),
        )
        .unwrap(),
        SolverToolIdentity::new(
            "linux-arm64",
            identity.cli_raw_digest(),
            identity.acceptance_raw_digest(),
        )
        .unwrap(),
    ] {
        let request = custom_request(&case, &tool, true, solver_limits().response_bytes);
        assert!(matches!(
            SimulationPlan::new(&request, &identity, host_limits()),
            Err(HostError::BindingMismatch(_))
        ));
    }
    let old = custom_request(&case, &tool(), false, solver_limits().response_bytes);
    assert!(matches!(
        SimulationPlan::new(&old, &identity, host_limits()),
        Err(HostError::BindingMismatch("profile"))
    ));
    let changed_limits = custom_request(&case, &tool(), true, solver_limits().response_bytes - 1);
    assert!(matches!(
        check_simulation_plan(
            plan.canonical_bytes(),
            &changed_limits,
            &identity,
            host_limits()
        ),
        Err(HostError::NonCanonical { .. })
    ));
    let changed_query = composite();
    assert!(matches!(
        check_simulation_plan(
            plan.canonical_bytes(),
            &changed_query.request,
            &identity,
            host_limits()
        ),
        Err(HostError::NonCanonical { .. })
    ));
    let mut limits = host_limits();
    limits.record_bytes = plan.canonical_bytes().len();
    assert!(SimulationPlan::new(&case.request, &identity, limits).is_ok());
    limits.record_bytes -= 1;
    assert!(matches!(
        SimulationPlan::new(&case.request, &identity, limits),
        Err(HostError::ResourceLimit(_))
    ));
}

#[test]
fn observation_identity_includes_exit_completeness_plan_and_every_fact() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let good = observation_input(b"unsat\n");
    let normal = SimulationObservation::new(&plan, good, host_limits()).unwrap();
    assert_eq!(
        normal.simulation_response_input().unwrap().stdout,
        b"unsat\n"
    );
    check_simulation_observation(normal.canonical_bytes(), &plan, good, host_limits()).unwrap();
    for bytes in object_mutations(normal.canonical_bytes()) {
        assert!(matches!(
            check_simulation_observation(&bytes, &plan, good, host_limits()),
            Err(HostError::NonCanonical { .. })
        ));
    }
    for variant in 0..5 {
        let mut input = good;
        let cleanup_fact = [FailureFact {
            kind: FailureKind::Cleanup,
            stage: ObservationStage::Cleanup,
            at_ms: 20,
        }];
        match variant {
            0 => input.exit = ProcessExit::Exited(137),
            1 => input.stdout.complete = false,
            2 => {
                input.cleanup = CleanupStatus::Failed;
                input.failures = &cleanup_fact;
            }
            3 => input.stderr.complete = false,
            4 => input.control_diagnostics.complete = false,
            _ => unreachable!(),
        }
        let failed = SimulationObservation::new(&plan, input, host_limits()).unwrap();
        assert_ne!(normal.artifact_digest(), failed.artifact_digest());
        assert!(matches!(
            failed.simulation_response_input(),
            Err(HostError::SimulationFailure)
        ));
        assert!(matches!(
            check_simulation_observation(normal.canonical_bytes(), &plan, input, host_limits()),
            Err(HostError::NonCanonical { .. })
        ));
    }
    let mut missing = good;
    missing.started = false;
    missing.exit = ProcessExit::Unavailable;
    missing.stdout = stream(b"");
    missing.cleanup = CleanupStatus::NotStarted;
    let missing_fact = [FailureFact {
        kind: FailureKind::MissingExit,
        stage: ObservationStage::Start,
        at_ms: 20,
    }];
    missing.failures = &missing_fact;
    assert!(
        SimulationObservation::new(&plan, missing, host_limits())
            .unwrap()
            .simulation_response_input()
            .is_err()
    );
    let other = composite();
    let other_plan = SimulationPlan::new(&other.request, &identity, host_limits()).unwrap();
    assert!(matches!(
        check_simulation_observation(normal.canonical_bytes(), &other_plan, good, host_limits()),
        Err(HostError::NonCanonical { .. })
    ));
}

#[test]
fn simultaneous_and_later_failures_keep_all_facts_and_earliest_outer_cause() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let facts = [
        FailureFact {
            kind: FailureKind::Deadline,
            stage: ObservationStage::Cleanup,
            at_ms: 6000,
        },
        FailureFact {
            kind: FailureKind::Memory,
            stage: ObservationStage::Capture,
            at_ms: 10,
        },
        FailureFact {
            kind: FailureKind::StdoutLimit,
            stage: ObservationStage::Capture,
            at_ms: 10,
        },
        FailureFact {
            kind: FailureKind::Cleanup,
            stage: ObservationStage::Cleanup,
            at_ms: 6001,
        },
    ];
    let mut input = observation_input(b"sat\n()\n");
    input.elapsed_ms = 6001;
    input.failures = &facts;
    input.exit = ProcessExit::Signaled(9);
    input.cleanup = CleanupStatus::Failed;
    let observation = SimulationObservation::new(&plan, input, host_limits()).unwrap();
    assert_eq!(observation.failures().len(), 4);
    assert_eq!(observation.primary_outer(), OuterTermination::Memory);
    assert_eq!(
        observation.p4_transport_summary().primary_reason(),
        Some(TransportReason::Outer(OuterTermination::Memory))
    );
    assert!(observation.simulation_response_input().is_err());
    let tied = [
        FailureFact {
            at_ms: 6000,
            ..facts[1]
        },
        facts[0],
    ];
    input.failures = &tied;
    input.elapsed_ms = 6000;
    input.cleanup = CleanupStatus::ConfirmedEmpty;
    assert_eq!(
        SimulationObservation::new(&plan, input, host_limits())
            .unwrap()
            .primary_outer(),
        OuterTermination::Deadline
    );
    input.failures = &[];
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("missing deadline fact"))
    ));
    input.elapsed_ms = 20;
    input.failures = &facts[..1];
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("failure after observation"))
    ));
    let duplicates = [facts[1], facts[1]];
    input.cleanup = CleanupStatus::ConfirmedEmpty;
    input.failures = &duplicates;
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("duplicate failure fact"))
    ));
}

#[test]
fn stream_boundary_and_prefix_digest_domains_are_distinct() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let cap = plan.process_limits().stderr_bytes;
    let bytes = vec![0xff; cap];
    let mut input = observation_input(b"unsat\n");
    input.stderr = stream(&bytes);
    let exact = SimulationObservation::new(&plan, input, host_limits()).unwrap();
    assert!(exact.stderr_complete());
    let fact = [FailureFact {
        kind: FailureKind::StderrLimit,
        stage: ObservationStage::Capture,
        at_ms: 10,
    }];
    input.stderr.complete = false;
    input.stderr.exceeded = true;
    input.stderr.observed_bytes = cap + 1;
    input.failures = &fact;
    let prefix = SimulationObservation::new(&plan, input, host_limits()).unwrap();
    assert_ne!(prefix.artifact_digest(), exact.artifact_digest());
    let text = std::str::from_utf8(prefix.canonical_bytes()).unwrap();
    assert!(text.contains("\"prefix_raw_digest\""));
    assert!(prefix.simulation_response_input().is_err());
    input.stderr.complete = true;
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput(_))
    ));
    input.stderr.complete = false;
    input.stderr.observed_bytes = cap;
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput(_))
    ));
    input.stderr.exceeded = false;
    input.stderr.observed_bytes = cap;
    input.failures = &[];
    let incomplete = SimulationObservation::new(&plan, input, host_limits()).unwrap();
    assert!(incomplete.simulation_response_input().is_err());
    let over = vec![0; cap + 1];
    input.stderr = stream(&over);
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::ResourceLimit("captured_stream_bytes"))
    ));
}

#[test]
fn observation_budget_boundaries_reject_before_copy_or_normal_adaptation() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let input = observation_input(b"unsat\n");
    let observation = SimulationObservation::new(&plan, input, host_limits()).unwrap();
    let mut limits = host_limits();
    limits.stream_bytes = 6;
    assert!(SimulationObservation::new(&plan, input, limits).is_ok());
    limits.stream_bytes = 5;
    assert!(matches!(
        SimulationObservation::new(&plan, input, limits),
        Err(HostError::ResourceLimit("stream_bytes"))
    ));
    limits = host_limits();
    limits.record_bytes = observation.canonical_bytes().len();
    assert!(SimulationObservation::new(&plan, input, limits).is_ok());
    limits.record_bytes -= 1;
    assert!(matches!(
        SimulationObservation::new(&plan, input, limits),
        Err(HostError::ResourceLimit("record_bytes"))
    ));
    limits = host_limits();
    limits.failure_facts = 0;
    let facts = [FailureFact {
        kind: FailureKind::Control,
        stage: ObservationStage::Capture,
        at_ms: 10,
    }];
    let mut failed = input;
    failed.failures = &facts;
    assert!(matches!(
        SimulationObservation::new(&plan, failed, limits),
        Err(HostError::ResourceLimit("failure_facts"))
    ));
    limits = host_limits();
    limits.json_values = 0;
    assert!(matches!(
        SimulationObservation::new(&plan, input, limits),
        Err(HostError::Json(_))
    ));
}

#[test]
fn lifetime_boundary_is_strict_and_early_deadline_claims_are_rejected() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let deadline = plan.process_limits().wall_clock_ms;
    let mut input = observation_input(b"unknown\n");
    input.elapsed_ms = deadline - 1;
    assert!(
        SimulationObservation::new(&plan, input, host_limits())
            .unwrap()
            .simulation_response_input()
            .is_ok()
    );
    input.elapsed_ms = deadline;
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("missing deadline fact"))
    ));
    let fact = [FailureFact {
        kind: FailureKind::Deadline,
        stage: ObservationStage::Cleanup,
        at_ms: deadline,
    }];
    input.failures = &fact;
    let observation = SimulationObservation::new(&plan, input, host_limits()).unwrap();
    assert_eq!(observation.primary_outer(), OuterTermination::Deadline);
    assert!(observation.simulation_response_input().is_err());
    let early = [FailureFact {
        at_ms: deadline - 1,
        ..fact[0]
    }];
    input.failures = &early;
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("early deadline"))
    ));
}

#[test]
fn observations_reject_inconsistent_failure_facts_without_inventing_events() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let good = observation_input(b"unsat\n");
    for started in [false, true] {
        for cleanup in [CleanupStatus::Failed, CleanupStatus::Unknown] {
            let mut input = good;
            input.started = started;
            input.cleanup = cleanup;
            if !started {
                input.exit = ProcessExit::Unavailable;
                input.stdout = stream(b"");
            }
            assert!(matches!(
                SimulationObservation::new(&plan, input, host_limits()),
                Err(HostError::InvalidInput("missing cleanup fact"))
            ));
        }
    }
    let mut input = good;
    input.exit = ProcessExit::Unavailable;
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("missing-exit fact mismatch"))
    ));
    let missing = [FailureFact {
        kind: FailureKind::MissingExit,
        stage: ObservationStage::Wait,
        at_ms: 20,
    }];
    input.failures = &missing;
    assert!(SimulationObservation::new(&plan, input, host_limits()).is_ok());
    input.exit = ProcessExit::Exited(0);
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("missing-exit fact mismatch"))
    ));
    let diagnostics = vec![0; host_limits().control_diagnostic_bytes];
    input = good;
    input.control_diagnostics = SimulationStreamInput {
        bytes: &diagnostics,
        observed_bytes: diagnostics.len() + 1,
        complete: false,
        exceeded: true,
    };
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("missing control-limit fact"))
    ));
    let control = [FailureFact {
        kind: FailureKind::Control,
        stage: ObservationStage::Capture,
        at_ms: 20,
    }];
    input.failures = &control;
    assert!(SimulationObservation::new(&plan, input, host_limits()).is_ok());
    input = good;
    input.started = false;
    input.exit = ProcessExit::Unavailable;
    input.stdout = stream(b"");
    input.cleanup = CleanupStatus::NotStarted;
    let facts = [
        missing[0],
        FailureFact {
            kind: FailureKind::Memory,
            stage: ObservationStage::Create,
            at_ms: 10,
        },
    ];
    input.failures = &facts;
    assert!(matches!(
        SimulationObservation::new(&plan, input, host_limits()),
        Err(HostError::InvalidInput("memory fact before start"))
    ));
}
