//! Independent E1–E2 workflow acceptance. Every process observation is simulated.
mod common;

use common::*;
use radishaxiom_ir::{
    json::canonicalize_json,
    replay::{ReplayInput, ReplayOutcome, ReplayProfile, ReplayWorldInput, replay_target},
    solver::{
        OuterTermination, ProcessExit, SolverStatus, TransportReason, decode_model_world,
        parse_solver_response,
    },
};
use radishaxiom_solver_diagnostic_host::*;

#[test]
fn synthetic_sat_bytes_cross_controller_decoder_and_exact_target_replay() {
    for (kind, case) in [
        ("minimal", minimal()),
        ("composite", composite()),
        ("wrong-add", wrong_add()),
    ] {
        let identity = identity();
        let request = &case.request;
        let plan = SimulationPlan::new(request, &identity, host_limits()).unwrap();
        let stdout = model(request, kind);
        let observation = observed(&plan, &stdout, ProcessExit::Exited(0), false);
        let input = observation.simulation_response_input().unwrap();
        assert_eq!(input.stdout, stdout);
        assert_eq!(input.stderr, b"simulation diagnostic\n");
        let response = parse_solver_response(request, input).unwrap();
        assert_eq!(response.status(), SolverStatus::Sat);
        let model = response.sat_model().unwrap();
        let candidate = decode_model_world(request, model).unwrap();
        let generator = generator();
        let replay = |world| {
            replay_target(
                ReplayProfile::MapFilterV0_1,
                ReplayInput {
                    document: &case.document,
                    obligations: &case.obligations,
                    obligation_id: request.query().binding().obligation(),
                    generator: &generator,
                    world,
                },
                replay_limits(),
            )
            .unwrap()
        };
        let from_model = replay(ReplayWorldInput::ModelCandidate {
            request,
            model,
            candidate: &candidate,
        });
        let direct = replay(ReplayWorldInput::Provided(candidate.world_bytes()));
        assert_eq!(from_model.result_bytes(), direct.result_bytes());
        assert_ne!(from_model.artifact_digest(), direct.artifact_digest());
        if kind == "wrong-add" {
            assert_eq!(request.query().binding().obligation(), WRONG_ADD_TARGET);
            assert_eq!(request.stdin_bytes().len(), 962_642);
            assert_eq!(request.query().artifact_digest(), WRONG_ADD_QUERY);
            assert_eq!(request.query().symbols().len(), 501);
            assert_eq!(from_model.outcome(), ReplayOutcome::TargetViolated);
            assert_eq!(
                std::str::from_utf8(candidate.world_bytes())
                    .unwrap()
                    .matches("\"kind\":\"record\"")
                    .count(),
                3
            );
            // Independently computed arithmetic: 10+10=20 violates 10-10=0.
            let result = std::str::from_utf8(from_model.result_bytes()).unwrap();
            assert!(result.contains("target-violated"));
        }
        for bytes in [
            identity.canonical_bytes(),
            plan.canonical_bytes(),
            observation.canonical_bytes(),
        ] {
            assert_eq!(canonicalize_json(bytes, json_limits()).unwrap(), bytes);
            assert!(
                std::str::from_utf8(bytes)
                    .unwrap()
                    .contains("\"scope\":\"simulation\"")
            );
        }
    }
}

#[test]
fn unsat_and_unknown_remain_backend_observations_without_worlds() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    for (bytes, status) in [
        (b"unsat\n".as_slice(), SolverStatus::Unsat),
        (b"unknown\n".as_slice(), SolverStatus::Unknown),
    ] {
        let observation = observed(&plan, bytes, ProcessExit::Exited(0), false);
        let response = parse_solver_response(
            &case.request,
            observation.simulation_response_input().unwrap(),
        )
        .unwrap();
        assert_eq!(response.status(), status);
        assert!(response.sat_model().is_none());
    }
}

#[test]
fn sat_cannot_cover_cleanup_failure_and_exit_137_is_not_oom() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let stdout = model(&case.request, "minimal");
    let success = observed(&plan, &stdout, ProcessExit::Exited(0), false);
    let cleanup = observed(&plan, &stdout, ProcessExit::Exited(0), true);
    let crashed = observed(&plan, &stdout, ProcessExit::Exited(137), false);
    assert!(cleanup.simulation_response_input().is_err());
    assert!(crashed.simulation_response_input().is_err());
    assert_eq!(success.stdout_bytes(), cleanup.stdout_bytes());
    assert_eq!(success.stdout_bytes(), crashed.stdout_bytes());
    assert_eq!(crashed.primary_outer(), OuterTermination::None);
    assert_eq!(
        crashed.p4_transport_summary().primary_reason(),
        Some(TransportReason::Exit(ProcessExit::Exited(137)))
    );
    assert_ne!(success.artifact_digest(), cleanup.artifact_digest());
    assert_ne!(success.artifact_digest(), crashed.artifact_digest());
    let raw = std::str::from_utf8(crashed.canonical_bytes()).unwrap();
    assert!(!raw.contains("\"kind\":\"memory\""));
}

#[test]
fn late_timeout_preserves_earlier_oom_and_all_failures() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let mut controller = running(&plan);
    for (at_ms, kind) in [
        (20, SimulationEventKind::OomKilled),
        (6011, SimulationEventKind::DeadlineTick),
        (6012, SimulationEventKind::Exit(ProcessExit::Exited(137))),
        (6013, SimulationEventKind::TreeTerminated),
        (6014, SimulationEventKind::Inspected),
        (6015, SimulationEventKind::TreeEmpty),
        (6016, SimulationEventKind::Cleaned),
    ] {
        assert_eq!(advance(&mut controller, at_ms, kind).rejection, None);
    }
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Memory)
    );
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Deadline)
    );
    let observation = controller.finish(6017).unwrap();
    assert_eq!(observation.primary_outer(), OuterTermination::Memory);
    assert_eq!(
        observation.p4_transport_summary().primary_reason(),
        Some(TransportReason::Outer(OuterTermination::Memory))
    );
    assert!(observation.simulation_response_input().is_err());
    let raw = std::str::from_utf8(observation.canonical_bytes()).unwrap();
    assert!(raw.contains("memory"));
    assert!(raw.contains("deadline"));
}

#[test]
fn strict_observation_cannot_accept_source_or_real_execution_flags() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let stdout = model(&case.request, "minimal");
    let observation = observed(&plan, &stdout, ProcessExit::Exited(0), false);
    let stream = |bytes| SimulationStreamInput {
        bytes,
        observed_bytes: bytes.len(),
        complete: true,
        exceeded: false,
    };
    let input = SimulationObservationInput {
        stdout: stream(observation.stdout_bytes()),
        stderr: stream(observation.stderr_bytes()),
        control_diagnostics: stream(observation.control_diagnostics()),
        exit: observation.exit(),
        started: observation.started(),
        elapsed_ms: observation.elapsed_ms(),
        cleanup: observation.cleanup_status(),
        failures: observation.failures(),
    };
    assert!(
        check_simulation_observation(observation.canonical_bytes(), &plan, input, host_limits())
            .is_ok()
    );
    let original = std::str::from_utf8(observation.canonical_bytes()).unwrap();
    for changed in [
        original.replacen("\"scope\":\"simulation\"", "\"scope\":\"real\"", 1),
        original.replacen(
            "simulation-not-authenticated-capture",
            "authenticated-capture",
            1,
        ),
        original.replacen("{", "{\"E0_accepted\":true,\"E3_qualified\":true,", 1),
    ] {
        assert!(
            check_simulation_observation(changed.as_bytes(), &plan, input, host_limits()).is_err()
        );
    }
}

#[test]
fn canonical_plan_binding_rejects_argv_limits_identity_and_request_changes() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let original = std::str::from_utf8(plan.canonical_bytes()).unwrap();
    for (from, to) in [
        ("simulation", "authenticated"),
        ("blocked-E0-E3", "enabled"),
        ("--rlimit-per=1000000", "--rlimit-per=1000001"),
        ("134217728", "134217729"),
        (
            identity.artifact_digest(),
            "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            case.request.artifact_digest(),
            "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
    ] {
        assert!(original.contains(from), "{from}");
        let changed = original.replacen(from, to, 1);
        assert!(
            check_simulation_plan(changed.as_bytes(), &case.request, &identity, host_limits())
                .is_err()
        );
    }
}
