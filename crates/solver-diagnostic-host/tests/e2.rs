mod common;

use common::{host_limits, identity, minimal};
use radishaxiom_ir::solver::{OuterTermination, ProcessExit};
use radishaxiom_solver_diagnostic_host::{
    SimulationPlan,
    controller::{
        ControlOperation, Rejection, SimulationActionKind, SimulationController, SimulationEvent,
        SimulationEventKind as Event, SimulationTransition,
    },
    observation::FailureKind,
    transport::{CONTROL_DIAGNOSTIC_LIMIT, STDERR_LIMIT, STDOUT_LIMIT, StreamKind},
};

fn step(
    controller: &mut SimulationController<'_, '_>,
    at_ms: u64,
    kind: Event,
) -> SimulationTransition {
    controller.advance(SimulationEvent {
        token: controller.token().clone(),
        at_ms,
        kind,
    })
}

fn start(controller: &mut SimulationController<'_, '_>, stdin: &[u8]) {
    for (at, event) in [
        (1, Event::Created),
        (2, Event::Attached),
        (3, Event::Started),
        (4, Event::StdinWritten(stdin.to_vec())),
        (5, Event::StdinClosed),
    ] {
        assert_eq!(step(controller, at, event).rejection, None);
    }
}

fn failed_tail(controller: &mut SimulationController<'_, '_>, base: u64) {
    for (delta, event) in [
        (0, Event::TreeTerminated),
        (1, Event::Exit(ProcessExit::Exited(137))),
        (2, Event::Inspected),
        (3, Event::TreeEmpty),
        (4, Event::Cleaned),
    ] {
        if matches!(event, Event::Exit(_)) && !controller.started() {
            continue;
        }
        assert_eq!(step(controller, base + delta, event).rejection, None);
    }
}

#[test]
fn plan_request_and_container_tokens_cannot_be_rebound() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    for field in 0..3 {
        let (mut controller, initial) =
            SimulationController::new(&plan, "sim-one", 0, host_limits()).unwrap();
        assert_eq!(initial.kind, SimulationActionKind::Create);
        let mut token = controller.token().clone();
        match field {
            0 => token.plan_digest.push('0'),
            1 => token.request_digest.push('0'),
            _ => token.container.push('0'),
        }
        let rejected = controller.advance(SimulationEvent {
            token,
            at_ms: 1,
            kind: Event::Created,
        });
        assert_eq!(rejected.rejection, Some(Rejection::Binding));
        assert_eq!(
            rejected.actions[0].kind,
            SimulationActionKind::TerminateTree
        );
        assert_eq!(
            step(&mut controller, 2, Event::Started).rejection,
            Some(Rejection::Sequence)
        );
        failed_tail(&mut controller, 3);
        assert!(
            controller
                .finish(8)
                .unwrap()
                .simulation_response_input()
                .is_err()
        );
    }
}

#[test]
fn out_of_order_duplicate_start_and_modified_stdin_fail_closed() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    for event in [
        Event::Attached,
        Event::Started,
        Event::StdinClosed,
        Event::TreeEmpty,
        Event::Cleaned,
        Event::Exit(ProcessExit::Exited(0)),
    ] {
        let (mut controller, _) =
            SimulationController::new(&plan, "sim-sequence", 0, host_limits()).unwrap();
        assert_eq!(
            step(&mut controller, 1, event).rejection,
            Some(Rejection::Sequence)
        );
        assert!(
            controller
                .finish(2)
                .unwrap()
                .simulation_response_input()
                .is_err()
        );
    }
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-double", 0, host_limits()).unwrap();
    start(&mut controller, case.request.stdin_bytes());
    assert_eq!(
        step(&mut controller, 6, Event::Started).rejection,
        Some(Rejection::Sequence)
    );
    failed_tail(&mut controller, 7);
    assert!(
        controller
            .finish(12)
            .unwrap()
            .simulation_response_input()
            .is_err()
    );

    let (mut controller, _) =
        SimulationController::new(&plan, "sim-stdin", 0, host_limits()).unwrap();
    for (at, event) in [
        (1, Event::Created),
        (2, Event::Attached),
        (3, Event::Started),
    ] {
        assert_eq!(step(&mut controller, at, event).rejection, None);
    }
    assert_eq!(
        step(
            &mut controller,
            4,
            Event::StdinWritten(b"(check-sat)".to_vec())
        )
        .rejection,
        Some(Rejection::StdinMismatch)
    );
    failed_tail(&mut controller, 5);
    assert!(
        controller
            .finish(10)
            .unwrap()
            .simulation_response_input()
            .is_err()
    );
}

#[test]
fn monotonic_clock_is_relative_to_first_action_and_never_wraps() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    assert!(
        SimulationController::new(&plan, "sim-overflow", u64::MAX - 5_999, host_limits()).is_err()
    );
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-rollback", 100, host_limits()).unwrap();
    assert_eq!(step(&mut controller, 101, Event::Created).rejection, None);
    assert_eq!(
        step(&mut controller, 100, Event::Attached).rejection,
        Some(Rejection::ClockRollback)
    );
    assert_eq!(controller.failures()[0].at_ms, 1);
    assert!(
        controller
            .finish(102)
            .unwrap()
            .simulation_response_input()
            .is_err()
    );
}

#[test]
fn simultaneous_stream_limits_preserve_prefixes_and_both_facts_without_drain() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-both-limits", 0, host_limits()).unwrap();
    start(&mut controller, case.request.stdin_bytes());
    let update = step(
        &mut controller,
        6,
        Event::Output {
            stdout: vec![b'o'; STDOUT_LIMIT + 9],
            stderr: vec![b'e'; STDERR_LIMIT + 9],
        },
    );
    assert_eq!(update.rejection, None);
    assert_eq!(update.actions.len(), 1);
    assert_eq!(update.actions[0].kind, SimulationActionKind::TerminateTree);
    for (kind, size) in [
        (StreamKind::Stdout, STDOUT_LIMIT),
        (StreamKind::Stderr, STDERR_LIMIT),
    ] {
        let captured = controller.streams().stream(kind);
        assert_eq!(captured.bytes().len(), size);
        assert_eq!(captured.observed_bytes(), size as u64 + 1);
        assert!(captured.exceeded());
        assert!(!captured.complete());
    }
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::StdoutLimit)
    );
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::StderrLimit)
    );
    assert_eq!(
        step(
            &mut controller,
            7,
            Event::Output {
                stdout: b"do not drain".to_vec(),
                stderr: vec![]
            }
        )
        .rejection,
        Some(Rejection::Sequence)
    );
    assert_eq!(
        controller
            .streams()
            .stream(StreamKind::Stdout)
            .observed_bytes(),
        STDOUT_LIMIT as u64 + 1
    );
    failed_tail(&mut controller, 8);
    assert!(
        controller
            .finish(13)
            .unwrap()
            .simulation_response_input()
            .is_err()
    );
}

#[test]
fn stderr_eof_allows_stdout_to_continue_and_reach_its_own_limit() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-independent-eof", 0, host_limits()).unwrap();
    start(&mut controller, case.request.stdin_bytes());
    step(
        &mut controller,
        6,
        Event::StreamsClosed {
            stdout: false,
            stderr: true,
        },
    );
    assert_eq!(
        step(
            &mut controller,
            7,
            Event::Output {
                stdout: b"sat\n".to_vec(),
                stderr: vec![]
            }
        )
        .rejection,
        None
    );
    assert!(controller.failures().is_empty());
    assert!(controller.streams().stream(StreamKind::Stderr).complete());
    let update = step(
        &mut controller,
        8,
        Event::Output {
            stdout: vec![b'x'; STDOUT_LIMIT - 3],
            stderr: vec![],
        },
    );
    assert_eq!(update.rejection, None);
    assert_eq!(update.actions[0].kind, SimulationActionKind::TerminateTree);
    assert_eq!(controller.failures().len(), 1);
    assert_eq!(controller.failures()[0].kind, FailureKind::StdoutLimit);
    failed_tail(&mut controller, 9);
    let observation = controller.finish(14).unwrap();
    assert!(observation.stderr_complete());
    assert!(observation.stdout_exceeded());
    assert_eq!(observation.primary_outer(), OuterTermination::StdoutLimit);
}

#[test]
fn control_failure_and_interruption_retain_diagnostics_outside_solver_streams() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let reason = b"synthetic daemon disconnected\0details";
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-control", 0, host_limits()).unwrap();
    let update = step(
        &mut controller,
        1,
        Event::ControlFailed {
            operation: ControlOperation::Create,
            diagnostic: reason.to_vec(),
        },
    );
    assert_eq!(update.rejection, None);
    assert_eq!(update.actions[0].kind, SimulationActionKind::TerminateTree);
    assert!(
        controller
            .control_diagnostics()
            .windows(reason.len())
            .any(|v| v == reason)
    );
    assert!(
        controller
            .streams()
            .stream(StreamKind::Stderr)
            .bytes()
            .is_empty()
    );
    assert_eq!(
        step(&mut controller, 2, Event::Created).rejection,
        Some(Rejection::Sequence)
    );
    assert_eq!(
        step(
            &mut controller,
            3,
            Event::Interrupted(b"synthetic controller stopped".to_vec())
        )
        .rejection,
        None
    );
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Interrupted)
    );
    failed_tail(&mut controller, 4);
    assert!(
        controller
            .finish(9)
            .unwrap()
            .simulation_response_input()
            .is_err()
    );

    let (mut controller, _) =
        SimulationController::new(&plan, "sim-control-budget", 0, host_limits()).unwrap();
    step(
        &mut controller,
        1,
        Event::ControlFailed {
            operation: ControlOperation::Create,
            diagnostic: vec![b'd'; CONTROL_DIAGNOSTIC_LIMIT + 1],
        },
    );
    assert_eq!(
        controller.control_diagnostics().len(),
        CONTROL_DIAGNOSTIC_LIMIT
    );
    failed_tail(&mut controller, 2);
    let observation = controller.finish(7).unwrap();
    assert!(observation.simulation_response_input().is_err());
    let canonical = std::str::from_utf8(observation.canonical_bytes()).unwrap();
    assert!(canonical.contains("prefix"));
}

#[test]
fn first_inspect_failure_requests_tree_termination_before_cleanup() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-inspect-failure", 0, host_limits()).unwrap();
    start(&mut controller, case.request.stdin_bytes());
    step(
        &mut controller,
        6,
        Event::StreamsClosed {
            stdout: true,
            stderr: true,
        },
    );
    step(&mut controller, 7, Event::Exit(ProcessExit::Exited(0)));
    let update = step(
        &mut controller,
        8,
        Event::ControlFailed {
            operation: ControlOperation::Inspect,
            diagnostic: b"inspect unavailable".to_vec(),
        },
    );
    assert_eq!(update.rejection, None);
    assert_eq!(update.actions[0].kind, SimulationActionKind::TerminateTree);
    step(&mut controller, 9, Event::TreeTerminated);
    step(&mut controller, 10, Event::Inspected);
    step(&mut controller, 11, Event::TreeEmpty);
    step(&mut controller, 12, Event::Cleaned);
    assert!(
        controller
            .finish(13)
            .unwrap()
            .simulation_response_input()
            .is_err()
    );
}

#[test]
fn all_missing_terminal_events_remain_explicit_failures() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    for stop_after in 0..10 {
        let (mut controller, _) =
            SimulationController::new(&plan, "sim-absence", 0, host_limits()).unwrap();
        let events = [
            Event::Created,
            Event::Attached,
            Event::Started,
            Event::StdinWritten(case.request.stdin_bytes().to_vec()),
            Event::StdinClosed,
            Event::Output {
                stdout: b"sat\n".to_vec(),
                stderr: vec![],
            },
            Event::StreamsClosed {
                stdout: true,
                stderr: true,
            },
            Event::Exit(ProcessExit::Exited(0)),
            Event::Inspected,
            Event::TreeEmpty,
        ];
        for (index, event) in events.into_iter().take(stop_after).enumerate() {
            assert_eq!(
                step(&mut controller, index as u64 + 1, event).rejection,
                None
            );
        }
        assert!(
            controller
                .finish(20)
                .unwrap()
                .simulation_response_input()
                .is_err(),
            "missing chain after {stop_after}"
        );
    }
}

#[test]
fn duplicate_eof_and_late_oom_for_another_container_are_rejected() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-eof", 0, host_limits()).unwrap();
    start(&mut controller, case.request.stdin_bytes());
    assert_eq!(
        step(
            &mut controller,
            6,
            Event::StreamsClosed {
                stdout: true,
                stderr: false
            }
        )
        .rejection,
        None
    );
    step(
        &mut controller,
        7,
        Event::StreamsClosed {
            stdout: true,
            stderr: false,
        },
    );
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Transport)
    );
    let mut token = controller.token().clone();
    token.container = "another-sim-container".to_owned();
    assert_eq!(
        controller
            .advance(SimulationEvent {
                token,
                at_ms: 8,
                kind: Event::OomKilled
            })
            .rejection,
        Some(Rejection::Binding)
    );
    assert!(
        !controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Memory)
    );
}

#[test]
fn late_started_and_control_failure_keep_observed_facts_and_only_request_termination() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-late-start", 100, host_limits()).unwrap();
    step(&mut controller, 101, Event::Created);
    step(&mut controller, 102, Event::Attached);
    let update = step(&mut controller, 6_100, Event::Started);
    assert!(controller.started());
    assert_eq!(update.rejection, None);
    assert_eq!(update.actions.len(), 1);
    assert_eq!(update.actions[0].kind, SimulationActionKind::TerminateTree);
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Deadline && f.at_ms == 6_000)
    );
    failed_tail(&mut controller, 6_101);
    let observation = controller.finish(6_106).unwrap();
    assert!(observation.started());
    assert_eq!(observation.elapsed_ms(), 6_006);
    assert_eq!(observation.primary_outer(), OuterTermination::Deadline);
    assert!(observation.simulation_response_input().is_err());

    let (mut controller, _) =
        SimulationController::new(&plan, "sim-late-control", 0, host_limits()).unwrap();
    let update = step(
        &mut controller,
        6_000,
        Event::ControlFailed {
            operation: ControlOperation::Create,
            diagnostic: b"create failed at deadline".to_vec(),
        },
    );
    assert_eq!(update.rejection, None);
    assert_eq!(update.actions.len(), 1);
    assert_eq!(update.actions[0].kind, SimulationActionKind::TerminateTree);
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Control)
    );
    assert!(
        controller
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::Deadline)
    );
    failed_tail(&mut controller, 6_001);
    let observation = controller.finish(6_006).unwrap();
    assert_eq!(observation.primary_outer(), OuterTermination::Deadline);
}

#[test]
fn low_capture_and_event_budgets_are_rejected_before_unbudgeted_allocation() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let required =
        STDOUT_LIMIT + STDERR_LIMIT + CONTROL_DIAGNOSTIC_LIMIT + case.request.stdin_bytes().len();
    let mut limits = host_limits();
    limits.stream_bytes = required - 1;
    assert!(SimulationController::new(&plan, "sim-low-budget", 0, limits).is_err());
    limits.stream_bytes = required;
    assert!(SimulationController::new(&plan, "sim-exact-budget", 0, limits).is_ok());
    limits.failure_facts = 0;
    assert!(SimulationController::new(&plan, "sim-zero-events", 0, limits).is_err());
    limits.failure_facts = 1;
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-one-failure", 0, limits).unwrap();
    assert_eq!(
        step(&mut controller, 1, Event::Started).rejection,
        Some(Rejection::Sequence)
    );
    assert_eq!(
        step(&mut controller, 2, Event::Created).rejection,
        Some(Rejection::Budget)
    );
    let update = step(&mut controller, 3, Event::TreeTerminated);
    assert_eq!(update.rejection, Some(Rejection::Budget));
    assert_eq!(update.actions[0].kind, SimulationActionKind::Inspect);
    let update = step(&mut controller, 4, Event::Inspected);
    assert_eq!(update.rejection, Some(Rejection::Budget));
    assert_eq!(
        update.actions[0].kind,
        SimulationActionKind::ConfirmEmptyTree
    );
    let update = step(&mut controller, 5, Event::TreeEmpty);
    assert_eq!(update.actions[0].kind, SimulationActionKind::Cleanup);
    step(&mut controller, 6, Event::Cleaned);
    assert!(controller.finish(7).is_err());
}

#[test]
fn explicit_unavailable_exit_records_missing_exit_in_final_observation() {
    let case = minimal();
    let identity = identity();
    let plan = SimulationPlan::new(&case.request, &identity, host_limits()).unwrap();
    let (mut controller, _) =
        SimulationController::new(&plan, "sim-unavailable-exit", 0, host_limits()).unwrap();
    start(&mut controller, case.request.stdin_bytes());
    step(
        &mut controller,
        6,
        Event::StreamsClosed {
            stdout: true,
            stderr: true,
        },
    );
    step(&mut controller, 7, Event::Exit(ProcessExit::Unavailable));
    step(&mut controller, 8, Event::Inspected);
    step(&mut controller, 9, Event::TreeEmpty);
    step(&mut controller, 10, Event::Cleaned);
    let observation = controller.finish(11).unwrap();
    assert!(
        observation
            .failures()
            .iter()
            .any(|f| f.kind == FailureKind::MissingExit)
    );
    assert!(observation.simulation_response_input().is_err());
}
