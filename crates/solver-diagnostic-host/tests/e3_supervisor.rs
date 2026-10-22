use radishaxiom_solver_diagnostic_host::{e3_cgroup::*, e3_supervisor::*, e3_wire::*};

const QUERY: &[u8] = b"(check-sat)\n";
const ZERO_EVENTS: &[u8] = b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n";
fn binding() -> BootstrapBinding {
    BootstrapBinding {
        attempt: [1; 32],
        request: [2; 32],
        policy: [3; 32],
        image: [4; 32],
        nonce: [5; 32],
    }
}
fn identity() -> CgroupIdentity {
    CgroupIdentity {
        daemon: [6; 32],
        container: [7; 32],
        boot: [8; 32],
        pid_namespace: [9; 32],
        cgroup_namespace: [10; 32],
    }
}
fn config() -> SimulationSupervisorConfig {
    SimulationSupervisorConfig {
        binding: binding(),
        identity: identity(),
        configuration_digest: [11; 32],
        mac_create_start_ns: 100,
        linux_entry_ns: 1000,
        declared_clock_error_ns: 10,
        expected_query_len: QUERY.len() as u32,
        expected_query_digest: radishaxiom_digest::digest(QUERY),
        pointers: SyntheticExecPointers {
            empty_path: 100,
            fixed_argv: 200,
            empty_envp: 300,
        },
    }
}
fn files<'a>(members: &'a [u8], current: &'a [u8]) -> SyntheticCgroupFiles<'a> {
    SyntheticCgroupFiles {
        memory_max: b"134217728\n",
        memory_swap_max: b"0\n",
        memory_events: ZERO_EVENTS,
        memory_events_local: ZERO_EVENTS,
        memory_current: b"32\n",
        memory_peak: b"64\n",
        memory_oom_group: b"0\n",
        pids_max: b"2\n",
        pids_current: current,
        pids_events: b"max 0\n",
        cgroup_procs: members,
        cgroup_events: b"populated 1\nfrozen 0\n",
    }
}
fn observation(at: u64, stage: CgroupStage) -> SyntheticCgroupObservation {
    let (members, current) = match stage {
        CgroupStage::SupervisorAndChild(_) => (&b"1\n2\n"[..], &b"2\n"[..]),
        _ => (&b"1\n"[..], &b"1\n"[..]),
    };
    SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(at, at).unwrap(),
        files(members, current),
        stage,
    )
    .unwrap()
}
fn child() -> SyntheticChildToken {
    SyntheticChildToken {
        pid: 2,
        pidfd_identity: [15; 32],
    }
}
fn notification() -> SyntheticExecNotification {
    SyntheticExecNotification {
        binding: binding(),
        id: 30,
        id_valid: true,
        child: child(),
        audit_arch: AARCH64_AUDIT_ARCH,
        syscall_number: radishaxiom_solver_diagnostic_host::e3_abi::NR_EXECVEAT,
        notification_flags: 0,
        executable_fd: 3,
        flags: EXECVEAT_EMPTY_PATH,
        pointers: config().pointers,
    }
}
fn prepared() -> SimulationSupervisor {
    let mut s = SimulationSupervisor::new(config()).unwrap();
    let ready = s
        .ready(1100, observation(1050, CgroupStage::SupervisorOnly))
        .unwrap();
    let arm = s
        .make_arm(
            300,
            &ready,
            QUERY.len() as u32,
            radishaxiom_digest::digest(QUERY),
        )
        .unwrap();
    s.arm(1200, &binding(), arm).unwrap();
    s
}
fn awaiting() -> SimulationSupervisor {
    let mut s = prepared();
    assert_eq!(
        s.query_complete(1300, &binding(), QUERY),
        Ok(SimulationAction::CloneOnce)
    );
    s.clone_returned(
        1400,
        child(),
        observation(1350, CgroupStage::SupervisorAndChild(2)),
    )
    .unwrap();
    s.listener_received(1500, &binding(), &child(), 1, false)
        .unwrap();
    s
}
fn running() -> SimulationSupervisor {
    let mut s = awaiting();
    assert!(matches!(
        s.grant_first_exec(1600, notification()),
        Ok(SimulationAction::ContinueOnce {
            notification_id: 30,
            ..
        })
    ));
    s.continue_send_result(1700, true).unwrap();
    s
}
fn local_final(s: &mut SimulationSupervisor) {
    s.stdout(1800, b"sat\n").unwrap();
    s.stdout_eof(1900).unwrap();
    s.stderr_eof(2000).unwrap();
    s.child_reaped(
        2100,
        &child(),
        ChildExit::Exited(0),
        observation(2050, CgroupStage::ReapedSupervisorOnly),
    )
    .unwrap();
    s.supervisor_final(2200, &binding()).unwrap();
}
fn outer() -> SyntheticOuterState {
    SyntheticOuterState {
        identity: identity(),
        running: false,
        init_pid: 0,
        restart_count: 0,
    }
}

#[test]
fn causal_handshake_and_complete_simulation_never_create_real_qualification() {
    let mut s = running();
    assert_eq!(s.linux_deadline_ns(), Some(6_000_000_890));
    local_final(&mut s);
    assert!(s.completion().is_none());
    s.outer_state(500, outer()).unwrap();
    assert_eq!(
        s.removal(600, &identity(), true),
        Ok(SimulationAction::SimulationComplete)
    );
    let c = s.completion().unwrap();
    assert_eq!(c.scope(), "simulation");
    assert_eq!(c.real_execution(), "blocked-E0-and-runtime-qualification");
    assert_eq!(c.tree_basis(), "pidns-init-exit-and-runtime-state");
}
#[test]
fn overflow_rollback_and_equal_deadline_fail_closed() {
    let mut c = config();
    c.mac_create_start_ns = u64::MAX;
    assert!(matches!(
        SimulationSupervisor::new(c),
        Err(SimulationFailureReason::ClockOverflow)
    ));
    let mut c = config();
    c.linux_entry_ns = u64::MAX;
    assert!(matches!(
        SimulationSupervisor::new(c),
        Err(SimulationFailureReason::ClockOverflow)
    ));
    let mut s = prepared();
    assert_eq!(s.tick(1199), Err(SimulationFailureReason::ClockRollback));
    assert!(s.completion().is_none());
    let mut s = prepared();
    let dl = s.linux_deadline_ns().unwrap();
    assert_eq!(
        s.query_complete(dl, &binding(), QUERY),
        Err(SimulationFailureReason::Deadline)
    );
    let mut s = awaiting();
    let dl = s.linux_deadline_ns().unwrap();
    assert_eq!(
        s.grant_first_exec(dl, notification()),
        Err(SimulationFailureReason::Deadline)
    );
    let mut s = running();
    local_final(&mut s);
    let dm = s.mac_deadline_ns();
    assert_eq!(
        s.outer_state(dm, outer()),
        Err(SimulationFailureReason::Deadline)
    );
}
#[test]
fn arm_offers_cannot_be_extended_replayed_or_rebound() {
    for field in 0..5 {
        let mut s = SimulationSupervisor::new(config()).unwrap();
        let ready = s
            .ready(1100, observation(1050, CgroupStage::SupervisorOnly))
            .unwrap();
        let arm = s
            .make_arm(
                300,
                &ready,
                QUERY.len() as u32,
                radishaxiom_digest::digest(QUERY),
            )
            .unwrap();
        let mut b = binding();
        match field {
            0 => b.attempt[0] ^= 1,
            1 => b.request[0] ^= 1,
            2 => b.policy[0] ^= 1,
            3 => b.image[0] ^= 1,
            _ => b.nonce[0] ^= 1,
        }
        assert_eq!(s.arm(1200, &b, arm), Err(SimulationFailureReason::Binding));
    }
    let mut s = SimulationSupervisor::new(config()).unwrap();
    let ready = s
        .ready(1100, observation(1050, CgroupStage::SupervisorOnly))
        .unwrap();
    let mut arm = s
        .make_arm(
            300,
            &ready,
            QUERY.len() as u32,
            radishaxiom_digest::digest(QUERY),
        )
        .unwrap();
    arm.deadline_ns += 1;
    assert_eq!(
        s.arm(1200, &binding(), arm),
        Err(SimulationFailureReason::Protocol)
    );
    let mut s = prepared();
    assert_eq!(
        s.make_arm(
            400,
            &ready,
            QUERY.len() as u32,
            radishaxiom_digest::digest(QUERY)
        ),
        Err(SimulationFailureReason::Binding)
    );
    let mut s = SimulationSupervisor::new(config()).unwrap();
    let ready = s
        .ready(1100, observation(1050, CgroupStage::SupervisorOnly))
        .unwrap();
    assert_eq!(
        s.make_arm(
            s.mac_deadline_ns() - 10,
            &ready,
            QUERY.len() as u32,
            radishaxiom_digest::digest(QUERY)
        ),
        Err(SimulationFailureReason::Deadline)
    );
}
#[test]
fn query_is_complete_bound_and_clone_intent_once() {
    let mut s = prepared();
    assert_eq!(
        s.query_complete(1300, &binding(), b"(check-sat) "),
        Err(SimulationFailureReason::Query)
    );
    let mut s = prepared();
    assert_eq!(
        s.query_complete(1300, &binding(), &QUERY[..QUERY.len() - 1]),
        Err(SimulationFailureReason::Query)
    );
    let mut s = prepared();
    s.query_complete(1300, &binding(), QUERY).unwrap();
    assert_eq!(
        s.query_complete(1300, &binding(), QUERY),
        Err(SimulationFailureReason::Protocol)
    );
    let mut s = prepared();
    s.query_complete(1300, &binding(), QUERY).unwrap();
    let dl = s.linux_deadline_ns().unwrap();
    assert_eq!(
        s.clone_returned(
            dl,
            child(),
            observation(1350, CgroupStage::SupervisorAndChild(2))
        ),
        Err(SimulationFailureReason::Deadline)
    );
    assert_eq!(s.stop_action().unwrap().kill_bound_child, Some(child()));
}
#[test]
fn trusted_first_exec_checks_full_width_and_is_consumed_before_send() {
    for variant in 0..10 {
        let mut s = awaiting();
        let mut n = notification();
        match variant {
            0 => n.id_valid = false,
            1 => n.id = 0,
            2 => n.child.pidfd_identity[0] ^= 1,
            3 => n.child.pid = 3,
            4 => n.audit_arch = 0x40000003,
            5 => n.executable_fd |= 1_u64 << 32,
            6 => n.flags |= 1_u64 << 32,
            7 => n.pointers.empty_path += 1,
            8 => n.pointers.fixed_argv += 1,
            _ => n.pointers.empty_envp += 1,
        }
        assert_eq!(
            s.grant_first_exec(1600, n),
            Err(SimulationFailureReason::Notification)
        );
    }
    let mut s = awaiting();
    s.grant_first_exec(1600, notification()).unwrap();
    assert_eq!(
        s.grant_first_exec(1600, notification()),
        Err(SimulationFailureReason::Notification)
    );
    let mut s = awaiting();
    s.grant_first_exec(1600, notification()).unwrap();
    assert_eq!(
        s.continue_send_result(1700, false),
        Err(SimulationFailureReason::ContinueSend)
    );
    assert_eq!(
        s.grant_first_exec(1800, notification()),
        Err(SimulationFailureReason::ContinueSend)
    );
    let mut s = running();
    assert_eq!(
        s.grant_first_exec(1800, notification()),
        Err(SimulationFailureReason::Notification)
    );
}
#[test]
fn listener_eof_output_and_reaping_failures_never_reopen_normal_path() {
    let mut s = awaiting();
    assert_eq!(
        s.listener_received(1500, &binding(), &child(), 1, false),
        Err(SimulationFailureReason::Listener)
    );
    let mut s = running();
    assert_eq!(
        s.control_eof(1800),
        Err(SimulationFailureReason::ControlEof)
    );
    s.outer_state(500, outer()).unwrap();
    s.removal(600, &identity(), true).unwrap();
    assert!(s.removal_confirmed());
    assert!(s.completion().is_none());
    let mut s = running();
    assert_eq!(
        s.stderr(1800, &vec![0; SIMULATION_STDERR_MAX + 1]),
        Err(SimulationFailureReason::OutputLimit)
    );
    let mut s = running();
    assert_eq!(s.reaping_failure(), Err(SimulationFailureReason::Reaping));
    let mut s = running();
    assert_eq!(
        s.supervisor_lost(),
        Err(SimulationFailureReason::SupervisorLost)
    );
    assert!(s.final_cgroup_missing());
    let mut s = running();
    assert_eq!(s.listener_lost(), Err(SimulationFailureReason::Listener));
    assert!(s.final_cgroup_missing());
}
#[test]
fn every_final_prerequisite_is_required() {
    for omit in 0..3 {
        let mut s = running();
        if omit != 0 {
            s.stdout_eof(1800).unwrap();
        }
        if omit != 1 {
            s.stderr_eof(1900).unwrap();
        }
        if omit != 2 {
            s.child_reaped(
                2100,
                &child(),
                ChildExit::Exited(0),
                observation(2050, CgroupStage::ReapedSupervisorOnly),
            )
            .unwrap();
        }
        assert_eq!(
            s.supervisor_final(2200, &binding()),
            Err(SimulationFailureReason::Protocol)
        );
    }
    for variant in 0..4 {
        let mut s = running();
        local_final(&mut s);
        let mut o = outer();
        match variant {
            0 => o.running = true,
            1 => o.init_pid = 1,
            2 => o.restart_count = 1,
            _ => o.identity.container[0] ^= 1,
        }
        assert_eq!(
            s.outer_state(500, o),
            Err(SimulationFailureReason::OuterState)
        );
    }
    let mut s = running();
    local_final(&mut s);
    assert_eq!(
        s.removal(600, &identity(), true),
        Err(SimulationFailureReason::Cleanup)
    );
    let mut s = running();
    local_final(&mut s);
    s.outer_state(500, outer()).unwrap();
    assert_eq!(
        s.removal(600, &identity(), false),
        Err(SimulationFailureReason::Cleanup)
    );
}
#[test]
fn cgroup_strict_missing_duplicate_unknown_overflow_and_membership() {
    let interval = ObservationInterval::new(1000, 1001).unwrap();
    let parse =
        |f| SyntheticCgroupObservation::parse(identity(), interval, f, CgroupStage::SupervisorOnly);
    let mut f = files(b"1\n", b"1\n");
    f.memory_events = b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n";
    assert_eq!(parse(f), Err(CgroupError::Missing("oom_group_kill")));
    let mut f = files(b"1\n", b"1\n");
    f.pids_events = b"max 0\nmax 0\n";
    assert_eq!(parse(f), Err(CgroupError::Duplicate));
    let mut f = files(b"1\n", b"1\n");
    f.cgroup_events = b"populated 1\nfrozen 0\nfuture 0\n";
    assert_eq!(parse(f), Err(CgroupError::UnknownField));
    let mut f = files(b"1\n", b"1\n");
    f.memory_peak = b"18446744073709551616\n";
    assert_eq!(parse(f), Err(CgroupError::Number));
    for (members, current) in [
        (&b""[..], &b"0\n"[..]),
        (b"1\n2\n", b"2\n"),
        (b"1\n1\n", b"2\n"),
        (b"0\n", b"1\n"),
        (b"1\n", b"2\n"),
    ] {
        assert!(parse(files(members, current)).is_err());
    }
    let mut f = files(b"1\n", b"1\n");
    f.memory_max = b"max\n";
    assert_eq!(parse(f), Err(CgroupError::Number));
    let mut f = files(b"1\n", b"1\n");
    f.memory_swap_max = b"1\n";
    assert_eq!(parse(f), Err(CgroupError::Configuration));
    let mut f = files(b"1\n", b"1\n");
    f.pids_max = b"3\n";
    assert_eq!(parse(f), Err(CgroupError::Configuration));
    assert_eq!(ObservationInterval::new(2, 1), Err(CgroupError::Interval));
}
#[test]
fn observation_identity_interval_counter_rollback_and_resource_event_poison() {
    let before = observation(1100, CgroupStage::SupervisorOnly);
    let mut f = files(b"1\n", b"1\n");
    f.memory_peak = b"63\n";
    let lower_peak = SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(1200, 1200).unwrap(),
        f,
        CgroupStage::SupervisorOnly,
    )
    .unwrap();
    assert_eq!(
        lower_peak.check_follows(&before),
        Err(CgroupError::CounterRollback)
    );
    let mut id = identity();
    id.boot[0] ^= 1;
    let other = SyntheticCgroupObservation::parse(
        id,
        ObservationInterval::new(1200, 1200).unwrap(),
        files(b"1\n", b"1\n"),
        CgroupStage::SupervisorOnly,
    )
    .unwrap();
    assert_eq!(other.check_follows(&before), Err(CgroupError::Identity));
    assert_eq!(
        observation(1099, CgroupStage::SupervisorOnly).check_follows(&before),
        Err(CgroupError::Interval)
    );
    let mut s = running();
    let events = b"low 0\nhigh 0\nmax 1\noom 1\noom_kill 1\noom_group_kill 0\n";
    let mut f = files(b"1\n2\n", b"2\n");
    f.memory_events = events;
    f.memory_events_local = events;
    let a = SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(1800, 1801).unwrap(),
        f,
        CgroupStage::SupervisorAndChild(2),
    )
    .unwrap();
    assert_eq!(
        s.cgroup_observation(1801, a),
        Err(SimulationFailureReason::Resource)
    );
    assert_eq!(s.latest_cgroup().unwrap().memory_events_local().oom_kill, 1);
    assert!(s.completion().is_none());
}
#[test]
fn oom_window_overlap_and_exit137_are_never_exact_attribution() {
    let before = observation(1100, CgroupStage::SupervisorOnly);
    let exit137 = observe_oom(
        &before,
        &observation(1200, CgroupStage::SupervisorOnly),
        true,
        1150,
    )
    .unwrap();
    assert_eq!(exit137.attribution, OomAttribution::NoObservedKillIncrement);
    assert_eq!(exit137.ordering, DeadlineOrdering::OrderUnresolved);
    let e = b"low 0\nhigh 0\nmax 1\noom 1\noom_kill 1\noom_group_kill 0\n";
    let mut f = files(b"1\n", b"1\n");
    f.memory_events = e;
    f.memory_events_local = e;
    let after = SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(1200, 1250).unwrap(),
        f,
        CgroupStage::SupervisorOnly,
    )
    .unwrap();
    let facts = observe_oom(&before, &after, true, 1150).unwrap();
    assert_eq!(
        facts.possible_event_interval,
        ObservationInterval::new(1100, 1250).unwrap()
    );
    assert_eq!(
        facts.attribution,
        OomAttribution::LocalMemoryAssociatedNotExclusive
    );
    assert_eq!(facts.ordering, DeadlineOrdering::OrderUnresolved);
    let mut f = files(b"1\n", b"1\n");
    f.memory_events = e;
    let global = SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(1200, 1250).unwrap(),
        f,
        CgroupStage::SupervisorOnly,
    )
    .unwrap();
    assert_eq!(
        observe_oom(&before, &global, true, 1300)
            .unwrap()
            .attribution,
        OomAttribution::CauseUnresolved
    );
    assert_eq!(
        observe_oom(
            &after,
            &observation(1300, CgroupStage::SupervisorOnly),
            true,
            1400
        ),
        Err(CgroupError::CounterRollback)
    );
}

#[test]
fn baseline_resource_events_and_oom_group_drift_are_rejected() {
    let e = b"low 0\nhigh 0\nmax 1\noom 0\noom_kill 0\noom_group_kill 0\n";
    let mut f = files(b"1\n", b"1\n");
    f.memory_events = e;
    let base = SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(1050, 1050).unwrap(),
        f,
        CgroupStage::SupervisorOnly,
    )
    .unwrap();
    let mut s = SimulationSupervisor::new(config()).unwrap();
    assert_eq!(s.ready(1100, base), Err(SimulationFailureReason::Resource));
    let mut f = files(b"1\n", b"1\n");
    f.pids_events = b"max 1\n";
    let base = SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(1050, 1050).unwrap(),
        f,
        CgroupStage::SupervisorOnly,
    )
    .unwrap();
    let mut s = SimulationSupervisor::new(config()).unwrap();
    assert_eq!(s.ready(1100, base), Err(SimulationFailureReason::Resource));
    let before = observation(1100, CgroupStage::SupervisorOnly);
    let mut f = files(b"1\n", b"1\n");
    f.memory_oom_group = b"1\n";
    let after = SyntheticCgroupObservation::parse(
        identity(),
        ObservationInterval::new(1200, 1200).unwrap(),
        f,
        CgroupStage::SupervisorOnly,
    )
    .unwrap();
    assert_eq!(
        after.check_follows(&before),
        Err(CgroupError::Configuration)
    );
}
#[test]
fn nonzero_exit_keeps_lifecycle_facts_and_disables_normal_response() {
    for exit in [ChildExit::Exited(137), ChildExit::Signaled(9)] {
        let mut s = running();
        s.stdout_eof(1800).unwrap();
        s.stderr_eof(1900).unwrap();
        s.child_reaped(
            2100,
            &child(),
            exit,
            observation(2050, CgroupStage::ReapedSupervisorOnly),
        )
        .unwrap();
        s.supervisor_final(2200, &binding()).unwrap();
        s.outer_state(500, outer()).unwrap();
        s.removal(600, &identity(), true).unwrap();
        assert_eq!(s.completion().unwrap().child_exit(), exit);
        assert!(!s.normal_response_eligible());
        assert!(!s.completion().unwrap().normal_response_eligible());
    }
}
#[test]
fn failed_cleanup_keeps_late_and_rollback_facts_visible() {
    let mut s = running();
    s.supervisor_lost().unwrap_err();
    s.outer_state(500, outer()).unwrap();
    s.removal(400, &identity(), true).unwrap();
    assert!(!s.cleanup_timing_valid());
    assert!(s.completion().is_none());
    let mut s = running();
    s.supervisor_lost().unwrap_err();
    s.outer_state(s.mac_deadline_ns(), outer()).unwrap();
    assert!(!s.cleanup_timing_valid());
    assert!(s.final_cgroup_missing());
}
#[test]
fn syscall_notification_header_is_closed() {
    let mut s = awaiting();
    let mut n = notification();
    n.syscall_number += 1;
    assert_eq!(
        s.grant_first_exec(1600, n),
        Err(SimulationFailureReason::Notification)
    );
    let mut s = awaiting();
    let mut n = notification();
    n.notification_flags = 1;
    assert_eq!(
        s.grant_first_exec(1600, n),
        Err(SimulationFailureReason::Notification)
    );
}

#[test]
fn exact_output_boundary_and_eof_are_one_way() {
    let mut s = running();
    s.stderr(1800, &vec![0; SIMULATION_STDERR_MAX]).unwrap();
    assert_eq!(
        s.stderr(1801, b"x"),
        Err(SimulationFailureReason::OutputLimit)
    );
    let mut s = running();
    s.stdout_eof(1800).unwrap();
    assert_eq!(s.stdout(1801, b"x"), Err(SimulationFailureReason::Protocol));
    let mut s = running();
    s.stderr_eof(1800).unwrap();
    assert_eq!(s.stderr_eof(1801), Err(SimulationFailureReason::Protocol));
}
#[test]
fn late_ready_arm_clone_reap_and_final_are_terminal() {
    let mut s = SimulationSupervisor::new(config()).unwrap();
    assert_eq!(
        s.ready(
            config().linux_entry_ns + SIMULATION_WINDOW_NS,
            observation(1050, CgroupStage::SupervisorOnly)
        ),
        Err(SimulationFailureReason::Deadline)
    );
    let mut s = prepared();
    let arm = Arm {
        deadline_ns: s.linux_deadline_ns().unwrap(),
        query_len: QUERY.len() as u32,
        query_digest: radishaxiom_digest::digest(QUERY),
    };
    assert_eq!(
        s.arm(1250, &binding(), arm),
        Err(SimulationFailureReason::Protocol)
    );
    let mut s = running();
    let dl = s.linux_deadline_ns().unwrap();
    assert_eq!(
        s.child_reaped(
            dl,
            &child(),
            ChildExit::Exited(0),
            observation(2050, CgroupStage::ReapedSupervisorOnly)
        ),
        Err(SimulationFailureReason::Deadline)
    );
    let mut s = running();
    s.stdout_eof(1800).unwrap();
    s.stderr_eof(1900).unwrap();
    s.child_reaped(
        2100,
        &child(),
        ChildExit::Exited(0),
        observation(2050, CgroupStage::ReapedSupervisorOnly),
    )
    .unwrap();
    let dl = s.linux_deadline_ns().unwrap();
    assert_eq!(
        s.supervisor_final(dl, &binding()),
        Err(SimulationFailureReason::Deadline)
    );
}
#[test]
fn future_observations_and_child_identity_mismatch_fail() {
    let mut s = SimulationSupervisor::new(config()).unwrap();
    assert_eq!(
        s.ready(1100, observation(1101, CgroupStage::SupervisorOnly)),
        Err(SimulationFailureReason::Cgroup)
    );
    let mut s = prepared();
    s.query_complete(1300, &binding(), QUERY).unwrap();
    let mut c = child();
    c.pid = 3;
    assert_eq!(
        s.clone_returned(
            1400,
            c.clone(),
            observation(1350, CgroupStage::SupervisorAndChild(2))
        ),
        Err(SimulationFailureReason::Cgroup)
    );
    assert_eq!(s.stop_action().unwrap().kill_bound_child, Some(c));
    let mut s = running();
    s.supervisor_lost().unwrap_err();
    let action = s.stop_action().unwrap();
    assert!(action.rely_on_pid_namespace_teardown);
    assert!(!action.exit_supervisor);
    assert!(action.kill_bound_child.is_none());
}
#[test]
fn cgroup_input_sizes_and_nondecimal_values_are_bounded() {
    let huge = vec![b'0'; CGROUP_FILE_BYTES + 1];
    let mut f = files(b"1\n", b"1\n");
    f.memory_peak = &huge;
    assert_eq!(
        SyntheticCgroupObservation::parse(
            identity(),
            ObservationInterval::new(1000, 1000).unwrap(),
            f,
            CgroupStage::SupervisorOnly
        ),
        Err(CgroupError::Limit)
    );
    for invalid in [&b"+2\n"[..], b"2 \n", b"-1\n", b"2\r\n", b"2"] {
        let mut f = files(b"1\n", b"1\n");
        f.pids_max = invalid;
        assert!(
            SyntheticCgroupObservation::parse(
                identity(),
                ObservationInterval::new(1000, 1000).unwrap(),
                f,
                CgroupStage::SupervisorOnly
            )
            .is_err()
        );
    }
}
