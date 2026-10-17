//! Root acceptance path: production query/P4 bytes cross only synthetic E3 inputs.
#![allow(dead_code)]
use super::common::*;
use radishaxiom_ir::{
    replay::{ReplayInput, ReplayOutcome, ReplayProfile, ReplayWorldInput, replay_target},
    solver::{ProcessExit, decode_model_world, parse_solver_response},
};
use radishaxiom_solver_diagnostic_host::SimulationPlan;
use radishaxiom_solver_diagnostic_host::{e3_cgroup::*, e3_supervisor::*, e3_wire::*};

pub struct ExportedWorkflow {
    pub binding: Vec<u8>,
    pub query: Vec<u8>,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub mac_wire: Vec<u8>,
    pub supervisor_wire: Vec<u8>,
    pub replay: Vec<u8>,
    pub request: Vec<u8>,
    pub response: Vec<u8>,
    pub candidate: Vec<u8>,
    pub world: Vec<u8>,
}

fn cgroup(identity: &CgroupIdentity, at: u64, child: bool) -> SyntheticCgroupObservation {
    let zeros = b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n";
    SyntheticCgroupObservation::parse(
        identity.clone(),
        ObservationInterval::new(at, at).unwrap(),
        SyntheticCgroupFiles {
            memory_max: b"134217728\n",
            memory_swap_max: b"0\n",
            memory_events: zeros,
            memory_events_local: zeros,
            memory_current: b"1048576\n",
            memory_peak: b"2097152\n",
            memory_oom_group: b"0\n",
            pids_max: b"2\n",
            pids_current: if child { b"2\n" } else { b"1\n" },
            pids_events: b"max 0\n",
            cgroup_procs: if child { b"1\n2\n" } else { b"1\n" },
            cgroup_events: b"populated 1\nfrozen 0\n",
        },
        if child {
            CgroupStage::SupervisorAndChild(2)
        } else {
            CgroupStage::SupervisorOnly
        },
    )
    .unwrap()
}

fn transfer(
    pending: &mut PendingFrameBuffer,
    decoder: &mut BootstrapDecoder,
    binding: &BootstrapBinding,
    message: BootstrapMessage,
    transcript: &mut Vec<u8>,
) -> BootstrapFrame {
    pending
        .push(&BootstrapFrame {
            binding: binding.clone(),
            message,
        })
        .unwrap();
    let mut decoded = None;
    while !pending.remaining().is_empty() {
        // Deliberately split both header and payload. No decoder frame-list exists.
        let chunk = &pending.remaining()[..pending.remaining().len().min(113)];
        let step = decoder.poll(chunk).unwrap();
        assert!(step.consumed > 0);
        transcript.extend_from_slice(&chunk[..step.consumed]);
        if let Some(frame) = step.frame {
            assert!(decoded.is_none());
            assert_eq!(&frame.binding, binding);
            decoded = Some(frame);
        }
        pending.consume(step.consumed).unwrap();
    }
    decoded.unwrap()
}

pub fn full_workflow() -> ExportedWorkflow {
    let case = wrong_add();
    let request = &case.request;
    let original = request.process_limits();
    assert_eq!(original.stdin_bytes, BOOTSTRAP_QUERY_LIMIT);
    assert_eq!(original.stdout_bytes, BOOTSTRAP_STDOUT_LIMIT);
    assert_eq!(original.stderr_bytes, BOOTSTRAP_STDERR_LIMIT);
    assert_eq!(original.working_memory_bytes as u64, CGROUP_MEMORY_MAX);
    assert_eq!(original.wall_clock_ms * 1_000_000, SIMULATION_WINDOW_NS);
    assert_eq!(original.internal_wall_clock_ms, 5000);
    assert_eq!(original.semantic_steps, 1_000_000);
    assert_eq!(request.stdin_bytes().len(), 962_642);
    assert_eq!(request.query().symbols().len(), 501);
    assert_eq!(request.query().artifact_digest(), WRONG_ADD_QUERY);
    let binding = BootstrapBinding {
        attempt: [1; 32],
        request: radishaxiom_digest::digest(request.canonical_bytes()),
        policy: radishaxiom_digest::digest(
            &radishaxiom_solver_diagnostic_host::e3_policy::worker_policy().bytes(),
        ),
        image: [4; 32],
        nonce: [5; 32],
    };
    let id = CgroupIdentity {
        daemon: [6; 32],
        container: [7; 32],
        boot: [8; 32],
        pid_namespace: [9; 32],
        cgroup_namespace: [10; 32],
    };
    let pointers = SyntheticExecPointers {
        empty_path: 0x1000,
        fixed_argv: 0x2000,
        empty_envp: 0x3000,
    };
    let config = SimulationSupervisorConfig {
        binding: binding.clone(),
        identity: id.clone(),
        configuration_digest: [11; 32],
        mac_create_start_ns: 0,
        linux_entry_ns: 100,
        declared_clock_error_ns: 1_000_000,
        expected_query_len: request.stdin_bytes().len() as u32,
        expected_query_digest: radishaxiom_digest::digest(request.stdin_bytes()),
        pointers,
    };
    let mut supervisor = SimulationSupervisor::new(config).unwrap();
    let mut mac_send = PendingFrameBuffer::new(Direction::MacToSupervisor);
    let mut linux_send = PendingFrameBuffer::new(Direction::SupervisorToMac);
    let mut mac_decode = BootstrapDecoder::new_bound(Direction::SupervisorToMac, binding.clone());
    let mut linux_decode = BootstrapDecoder::new_bound(Direction::MacToSupervisor, binding.clone());
    let mut mac_wire = Vec::new();
    let mut supervisor_wire = Vec::new();
    let ready = supervisor.ready(200, cgroup(&id, 150, false)).unwrap();
    let ready = transfer(
        &mut linux_send,
        &mut mac_decode,
        &binding,
        BootstrapMessage::Ready(ready),
        &mut supervisor_wire,
    );
    let BootstrapMessage::Ready(ready) = ready.message else {
        panic!("READY")
    };
    let arm = supervisor
        .make_arm(
            1_000_000,
            &ready,
            request.stdin_bytes().len() as u32,
            radishaxiom_digest::digest(request.stdin_bytes()),
        )
        .unwrap();
    let arm = transfer(
        &mut mac_send,
        &mut linux_decode,
        &binding,
        BootstrapMessage::Arm(arm),
        &mut mac_wire,
    );
    let BootstrapMessage::Arm(arm) = arm.message else {
        panic!("ARM")
    };
    supervisor.arm(1_000_100, &binding, arm).unwrap();
    let mut query = Vec::new();
    for chunk in request.stdin_bytes().chunks(BOOTSTRAP_CHUNK_LIMIT) {
        let frame = transfer(
            &mut mac_send,
            &mut linux_decode,
            &binding,
            BootstrapMessage::QueryChunk(chunk.to_vec()),
            &mut mac_wire,
        );
        let BootstrapMessage::QueryChunk(bytes) = frame.message else {
            panic!("query")
        };
        assert!(query.len() + bytes.len() <= BOOTSTRAP_QUERY_LIMIT);
        query.extend_from_slice(&bytes);
    }
    let end = transfer(
        &mut mac_send,
        &mut linux_decode,
        &binding,
        BootstrapMessage::QueryEnd,
        &mut mac_wire,
    );
    assert_eq!(end.message, BootstrapMessage::QueryEnd);
    assert_eq!(
        supervisor
            .query_complete(2_000_000, &binding, &query)
            .unwrap(),
        SimulationAction::CloneOnce
    );
    let child = SyntheticChildToken {
        pid: 2,
        pidfd_identity: [12; 32],
    };
    supervisor
        .clone_returned(2_000_100, child.clone(), cgroup(&id, 2_000_050, true))
        .unwrap();
    supervisor
        .listener_received(2_000_200, &binding, &child, 1, false)
        .unwrap();
    let notification = SyntheticExecNotification {
        binding: binding.clone(),
        id: 1,
        id_valid: true,
        child: child.clone(),
        audit_arch: AARCH64_AUDIT_ARCH,
        executable_fd: 3,
        flags: EXECVEAT_EMPTY_PATH,
        syscall_number: 281,
        notification_flags: 0,
        pointers,
    };
    assert!(matches!(
        supervisor
            .grant_first_exec(2_000_300, notification)
            .unwrap(),
        SimulationAction::ContinueOnce { .. }
    ));
    supervisor.continue_send_result(2_000_400, true).unwrap();
    let expected_stdout = model(request, "wrong-add");
    let expected_stderr = b"simulation diagnostic\n";
    let mut stdout = Vec::new();
    for chunk in expected_stdout.chunks(BOOTSTRAP_CHUNK_LIMIT) {
        let frame = transfer(
            &mut linux_send,
            &mut mac_decode,
            &binding,
            BootstrapMessage::StdoutChunk(chunk.to_vec()),
            &mut supervisor_wire,
        );
        let BootstrapMessage::StdoutChunk(bytes) = frame.message else {
            panic!("stdout")
        };
        supervisor.stdout(3_000_000, &bytes).unwrap();
        stdout.extend_from_slice(&bytes);
    }
    let frame = transfer(
        &mut linux_send,
        &mut mac_decode,
        &binding,
        BootstrapMessage::StderrChunk(expected_stderr.to_vec()),
        &mut supervisor_wire,
    );
    let BootstrapMessage::StderrChunk(stderr) = frame.message else {
        panic!("stderr")
    };
    supervisor.stderr(3_000_000, &stderr).unwrap();
    transfer(
        &mut linux_send,
        &mut mac_decode,
        &binding,
        BootstrapMessage::StdoutEof,
        &mut supervisor_wire,
    );
    supervisor.stdout_eof(3_000_100).unwrap();
    transfer(
        &mut linux_send,
        &mut mac_decode,
        &binding,
        BootstrapMessage::StderrEof,
        &mut supervisor_wire,
    );
    supervisor.stderr_eof(3_000_100).unwrap();
    let frame = transfer(
        &mut linux_send,
        &mut mac_decode,
        &binding,
        BootstrapMessage::ChildExit(ChildExit::Exited(0)),
        &mut supervisor_wire,
    );
    let BootstrapMessage::ChildExit(exit) = frame.message else {
        panic!("exit")
    };
    supervisor
        .child_reaped(3_000_200, &child, exit, cgroup(&id, 3_000_150, false))
        .unwrap();
    transfer(
        &mut linux_send,
        &mut mac_decode,
        &binding,
        BootstrapMessage::Final(Final {
            child_reaped: true,
            only_supervisor: true,
        }),
        &mut supervisor_wire,
    );
    supervisor.supervisor_final(3_000_300, &binding).unwrap();
    mac_decode.end_of_input().unwrap();
    supervisor
        .outer_state(
            4_000_000,
            SyntheticOuterState {
                identity: id.clone(),
                running: false,
                init_pid: 0,
                restart_count: 0,
            },
        )
        .unwrap();
    assert!(supervisor.completion().is_none());
    supervisor.removal(4_000_100, &id, true).unwrap();
    let completion = supervisor.completion().unwrap();
    assert_eq!(completion.scope(), "simulation");
    assert!(completion.normal_response_eligible());
    assert!(supervisor.normal_response_eligible());
    assert_eq!(completion.child_exit(), ChildExit::Exited(0));
    assert_eq!(
        completion.real_execution(),
        "blocked-E0-and-runtime-qualification"
    );
    assert_eq!(query, request.stdin_bytes());
    assert_eq!(stdout, expected_stdout);
    assert_eq!(stderr, expected_stderr);
    // The existing simulation adapter independently requires clean process facts.
    let identity = identity();
    let plan = SimulationPlan::new(request, &identity, host_limits()).unwrap();
    let observation = observed(&plan, &stdout, ProcessExit::Exited(0), false);
    let response =
        parse_solver_response(request, observation.simulation_response_input().unwrap()).unwrap();
    let model = response.sat_model().unwrap();
    let candidate = decode_model_world(request, model).unwrap();
    let generator = generator();
    let replay = replay_target(
        ReplayProfile::MapFilterV0_1,
        ReplayInput {
            document: &case.document,
            obligations: &case.obligations,
            obligation_id: request.query().binding().obligation(),
            generator: &generator,
            world: ReplayWorldInput::ModelCandidate {
                request,
                model,
                candidate: &candidate,
            },
        },
        replay_limits(),
    )
    .unwrap();
    assert_eq!(replay.outcome(), ReplayOutcome::TargetViolated);
    let binding_bytes = [
        binding.attempt,
        binding.request,
        binding.policy,
        binding.image,
        binding.nonce,
    ]
    .concat();
    ExportedWorkflow {
        binding: binding_bytes,
        query,
        stdout,
        stderr,
        mac_wire,
        supervisor_wire,
        replay: replay.canonical_bytes().to_vec(),
        request: request.canonical_bytes().to_vec(),
        response: response.canonical_bytes().to_vec(),
        candidate: candidate.canonical_bytes().to_vec(),
        world: candidate.world_bytes().to_vec(),
    }
}

pub fn timing_matrix() -> (usize, usize) {
    let query = b"(check-sat)\n";
    let binding = BootstrapBinding {
        attempt: [1; 32],
        request: [2; 32],
        policy: [3; 32],
        image: [4; 32],
        nonce: [5; 32],
    };
    let id = CgroupIdentity {
        daemon: [6; 32],
        container: [7; 32],
        boot: [8; 32],
        pid_namespace: [9; 32],
        cgroup_namespace: [10; 32],
    };
    let mut allowed = 0;
    let mut rejected = 0;
    for entry in [0_u64, 100, 3000, 7000] {
        for setup in [0_u64, 1, 1000] {
            for offset in [0_u64, 1_000_000, 1_000_000_000_000] {
                for ready_delay in [0_u64, 1, 100, 3000, 7000] {
                    for arm_delay in [0_u64, 1, 100, 3000, 7000] {
                        for delta in [0_u64, 1, 100] {
                            let ms = 1_000_000;
                            let received = entry + setup + ready_delay;
                            let arrival = received + arm_delay;
                            // Independent unit-rate, no-pause causal reference in ms.
                            let remaining = 6000_i128 - i128::from(received) - i128::from(delta);
                            let expected = remaining > 0
                                && i128::from(arrival)
                                    < 6000_i128 - i128::from(ready_delay) - i128::from(delta);
                            let mut s = SimulationSupervisor::new(SimulationSupervisorConfig {
                                binding: binding.clone(),
                                identity: id.clone(),
                                configuration_digest: [11; 32],
                                mac_create_start_ns: 0,
                                linux_entry_ns: (entry + offset) * ms,
                                declared_clock_error_ns: delta * ms,
                                expected_query_len: query.len() as u32,
                                expected_query_digest: radishaxiom_digest::digest(query),
                                pointers: SyntheticExecPointers {
                                    empty_path: 0x1000,
                                    fixed_argv: 0x2000,
                                    empty_envp: 0x3000,
                                },
                            })
                            .unwrap();
                            let ready_at = (entry + setup + offset) * ms;
                            let ready = s.ready(ready_at, cgroup(&id, ready_at, false)).unwrap();
                            let actual = match s.make_arm(
                                received * ms,
                                &ready,
                                query.len() as u32,
                                radishaxiom_digest::digest(query),
                            ) {
                                Ok(arm) => {
                                    let deadline = arm.deadline_ns;
                                    let accepted =
                                        s.arm((arrival + offset) * ms, &binding, arm).is_ok()
                                            && s.query_complete(
                                                (arrival + offset) * ms,
                                                &binding,
                                                query,
                                            ) == Ok(SimulationAction::CloneOnce);
                                    if accepted {
                                        assert!(deadline - offset * ms <= (6000 - delta) * ms);
                                    }
                                    accepted
                                }
                                Err(_) => false,
                            };
                            assert_eq!(
                                actual, expected,
                                "entry={entry},setup={setup},offset={offset},ready_delay={ready_delay},arm_delay={arm_delay},delta={delta}"
                            );
                            assert_eq!(s.real_execution(), "blocked-E0-and-runtime-qualification");
                            if actual {
                                allowed += 1;
                            } else {
                                rejected += 1;
                            }
                        }
                    }
                }
            }
        }
    }
    (allowed, rejected)
}
