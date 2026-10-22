use super::*;
use crate::{
    configuration::{CommandInputs, tests::exported},
    observation::ObservationLog,
    setup::{BuildMaterial, Deadline, ExpectedLocalInstance, Material, Resources},
    test_support::{Script, Step, owned},
};
use radishaxiom_solver_supervision_core::{
    bootstrap_start::{StartDescription, StartFields},
    handshake::{HandshakeWindow, LocalReadyDeclaration, SupervisorHandshake},
    wire::{BootstrapBinding, BootstrapEncoder, WireLimits},
};
pub(crate) fn fixture() -> Prepared {
    let configuration = exported();
    let query = b"(check-sat)\n".to_vec();
    let description = StartDescription::new(
        StartFields {
            attempt: [1; 32],
            request: [2; 32],
            query_bytes: query.len() as u32,
            query_digest: radishaxiom_digest::digest(&query),
            policy_bundle: [3; 32],
            image: [4; 32],
            cli_acceptance: [5; 32],
            configuration: [6; 32],
        },
        configuration.wire,
    )
    .unwrap();
    let binding = description.binding([7; 32]);
    let handshake = SupervisorHandshake::new(
        description.clone(),
        LinuxInstant::declared_ns(0),
        LocalReadyDeclaration {
            boot_digest: [8; 32],
            namespace_digest: [9; 32],
            configuration_digest: [6; 32],
            nonce: [7; 32],
        },
        HandshakeWindow {
            wall_clock_ns: configuration.window_ns,
        },
    )
    .unwrap();
    let material = Material {
        build: BuildMaterial {
            cli_path: c"/fixed/cvc5",
            cli_len: 120,
            cli_digest: [10; 32],
            uid: 1000,
            gid: 1000,
            policy_bundle: [3; 32],
            configuration: [6; 32],
            cli_acceptance: [5; 32],
        },
        instance: ExpectedLocalInstance {
            boot_digest: [8; 32],
            namespace_digest: [9; 32],
            mountinfo_digest: [11; 32],
        },
    };
    let command = radishaxiom_solver_diagnostic_host::bootstrap_command::export_offline_command();
    let command = CommandInputs::parse(
        &command.command,
        radishaxiom_digest::digest(&command.command),
    )
    .unwrap();
    let tokens = command
        .tokens
        .iter()
        .map(|s| s.to_str().unwrap().to_owned())
        .collect::<Vec<_>>();
    let frozen = crate::child::FrozenChild::new(
        [owned(50), owned(51), owned(52), owned(53), owned(54)],
        crate::child::FrozenChildArguments::from_bound_tokens(&tokens).unwrap(),
        &mut Linux::new(Script::new([])),
    )
    .unwrap();
    let mut resources = Resources::new();
    for raw in [
        0, 1, 2, 10, 11, 12, 13, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 40, 41, 42, 3, 43,
        4,
    ] {
        resources.add(owned(raw));
    }
    Prepared {
        configuration,
        command,
        material,
        description,
        handshake,
        binding,
        deadline: Deadline::from_entry(0, 6_000_000_000).unwrap(),
        resources,
        timer: 13,
        cgroup: [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
        stdin: 10,
        stdout: 11,
        stderr: 12,
        child_stdio: [40, 41, 42],
        socket: 3,
        child_socket: 43,
        elf: 4,
        observations: ObservationLog::new(),
        query,
        frozen: Some(frozen),
        exec_grant: ExecGrant::Awaiting,
    }
}
fn notif(pointers: FrozenPointers) -> abi::SeccompNotification {
    abi::SeccompNotification {
        id: 44,
        pid: 2,
        flags: 0,
        data: abi::SeccompData::aarch64(
            NR_EXECVEAT,
            [
                3,
                pointers.empty_path,
                pointers.argv,
                pointers.envp,
                AT_EMPTY_PATH,
                0,
            ],
        ),
    }
}
fn pointers() -> FrozenPointers {
    FrozenPointers {
        empty_path: 100,
        argv: 200,
        envp: 300,
    }
}
#[test]
fn deadline_and_disconnect_precede_ready_listener() {
    for (readiness, expected) in [
        (vec![(13, READ), (15, READ)], 0),
        (vec![(0, 16), (15, READ)], 1),
    ] {
        let mut linux = Linux::new(Script::new([Step::Poll(readiness)]));
        let mut p = fixture();
        let error = grant_first_exec(&mut linux, &mut p, 14, 15, 2, pointers()).unwrap_err();
        if expected == 0 {
            assert!(matches!(
                error,
                SupervisorError::Setup(SetupError::Deadline)
            ))
        } else {
            assert!(matches!(error, SupervisorError::ControlLost))
        }
        assert!(!linux.kernel.calls.contains(&abi::NR_IOCTL));
        linux.kernel.done();
    }
}
#[test]
fn first_exec_has_one_recv_and_consumes_continue_before_failed_send() {
    let mut steps = vec![
        Step::Poll(vec![(15, READ)]),
        Step::Notification(notif(pointers())),
        Step::Scalar(abi::NR_IOCTL, Some(15), 0),
        Step::Scalar(abi::NR_READ, Some(0), (-11i64) as u64),
        Step::Scalar(abi::NR_IOCTL, Some(15), (-4i64) as u64),
    ];
    let mut linux = Linux::new(Script::new(steps.drain(..)));
    let mut p = fixture();
    assert!(matches!(
        grant_first_exec(&mut linux, &mut p, 14, 15, 2, pointers()),
        Err(SupervisorError::System(_))
    ));
    assert_eq!(
        linux
            .kernel
            .calls
            .iter()
            .filter(|nr| **nr == abi::NR_IOCTL)
            .count(),
        3
    );
    assert!(p.exec_grant == ExecGrant::Consumed);
    assert!(matches!(
        grant_first_exec(&mut linux, &mut p, 14, 15, 2, pointers()),
        Err(SupervisorError::Notification)
    ));
    linux.kernel.done();
}
#[test]
fn altered_pid_arch_syscall_and_pointer_all_stop_before_id_valid() {
    for index in 0..5 {
        let mut n = notif(pointers());
        match index {
            0 => n.pid = 3,
            1 => n.data.arch = 0,
            2 => n.data.nr = abi::NR_READ,
            3 => n.data.args[2] = 201,
            _ => n.flags = 1,
        };
        let mut linux = Linux::new(Script::new([
            Step::Poll(vec![(15, READ)]),
            Step::Notification(n),
        ]));
        let mut p = fixture();
        assert!(matches!(
            grant_first_exec(&mut linux, &mut p, 14, 15, 2, pointers()),
            Err(SupervisorError::Notification)
        ));
        linux.kernel.done();
    }
}
#[test]
fn second_listener_readiness_never_invokes_another_recv() {
    let mut linux = Linux::new(Script::new([Step::Poll(vec![(15, READ)])]));
    let mut p = fixture();
    let mut child = ChildFact::Running(2);
    let mut input = ControlInput::new(&p);
    let mut out = PendingFrameBuffer::new(Direction::SupervisorToMac, p.configuration.wire);
    assert!(matches!(
        stream_and_reap(
            &mut linux,
            &mut p,
            &mut child,
            14,
            15,
            StreamBuffers {
                input: &mut input,
                output: &mut out,
                chunk: &mut [0; 32]
            }
        ),
        Err(SupervisorError::Notification)
    ));
    assert!(!linux.kernel.calls.contains(&abi::NR_IOCTL));
    linux.kernel.done();
}
#[test]
fn zero_write_and_output_n_plus_one_fail_with_actual_bytes() {
    let mut p = fixture();
    p.configuration.wire.stdout_bytes = 2;
    let mut linux = Linux::new(Script::new([
        Step::Poll(vec![(11, READ)]),
        Step::Read(11, b"abc".to_vec()),
    ]));
    let mut child = ChildFact::Running(2);
    let mut input = ControlInput::new(&p);
    let mut out = PendingFrameBuffer::new(Direction::SupervisorToMac, p.configuration.wire);
    assert!(matches!(
        stream_and_reap(
            &mut linux,
            &mut p,
            &mut child,
            14,
            15,
            StreamBuffers {
                input: &mut input,
                output: &mut out,
                chunk: &mut [0; 32]
            }
        ),
        Err(SupervisorError::OutputLimit)
    ));
    linux.kernel.done();
    let mut p = fixture();
    let query = p.query.clone();
    let mut linux = Linux::new(Script::new([
        Step::Poll(vec![(10, WRITE)]),
        Step::Write(10, query, 0),
    ]));
    let mut child = ChildFact::Running(2);
    let mut input = ControlInput::new(&p);
    let mut out = PendingFrameBuffer::new(Direction::SupervisorToMac, p.configuration.wire);
    assert!(matches!(
        stream_and_reap(
            &mut linux,
            &mut p,
            &mut child,
            14,
            15,
            StreamBuffers {
                input: &mut input,
                output: &mut out,
                chunk: &mut [0; 32]
            }
        ),
        Err(SupervisorError::ZeroWrite)
    ));
    linux.kernel.done();
}
#[test]
fn split_control_reads_reuse_core_decoder_and_preserve_surplus() {
    let p = fixture();
    let first = BootstrapFrame {
        binding: p.binding.clone(),
        message: BootstrapMessage::QueryChunk(b"x".to_vec()),
    };
    let second = BootstrapFrame {
        binding: p.binding.clone(),
        message: BootstrapMessage::QueryEnd,
    };
    let mut encoder = BootstrapEncoder::new(Direction::MacToSupervisor, p.configuration.wire);
    let mut bytes = encoder.encode(&first).unwrap();
    bytes.extend(encoder.encode(&second).unwrap());
    let mut linux = Linux::new(Script::new([
        Step::Read(0, bytes[..7].to_vec()),
        Step::Read(0, bytes[7..].to_vec()),
    ]));
    let mut input = ControlInput::new(&p);
    assert!(input.buffered(&mut linux).unwrap().is_none());
    assert_eq!(input.buffered(&mut linux).unwrap(), Some(first));
    assert!(input.has_bytes());
    assert_eq!(input.buffered(&mut linux).unwrap(), Some(second));
    linux.kernel.done();
}
#[test]
fn pending_short_writes_advance_only_actual_bytes() {
    let limits = WireLimits {
        query_bytes: 10,
        stdout_bytes: 10,
        stderr_bytes: 10,
    };
    let binding = BootstrapBinding {
        attempt: [1; 32],
        request: [2; 32],
        policy: [3; 32],
        image: [4; 32],
        nonce: [5; 32],
    };
    let f = BootstrapFrame {
        binding,
        message: BootstrapMessage::StdoutChunk(vec![0, 255, 10]),
    };
    let mut out = PendingFrameBuffer::new(Direction::SupervisorToMac, limits);
    out.push(&f).unwrap();
    let bytes = out.remaining().to_vec();
    let mut linux = Linux::new(Script::new([
        Step::Write(1, bytes.clone(), 2),
        Step::Scalar(abi::NR_WRITE, Some(1), (-11i64) as u64),
        Step::Write(1, bytes[2..].to_vec(), bytes.len() - 2),
    ]));
    write_pending(&mut linux, &mut out).unwrap();
    assert_eq!(out.remaining(), &bytes[2..]);
    write_pending(&mut linux, &mut out).unwrap();
    assert_eq!(out.remaining(), &bytes[2..]);
    write_pending(&mut linux, &mut out).unwrap();
    assert!(out.remaining().is_empty());
    linux.kernel.done();
}
#[test]
fn wait_no_state_is_distinct_from_reap() {
    let mut linux = Linux::new(Script::new([
        Step::Wait(None),
        Step::Wait(Some(abi::ChildExit {
            pid: 2,
            uid: 1000,
            code: 1,
            status: 0,
        })),
    ]));
    let mut child = ChildFact::Running(2);
    reap(&mut linux, &mut child, 14).unwrap();
    assert_eq!(child, ChildFact::Running(2));
    reap(&mut linux, &mut child, 14).unwrap();
    assert_eq!(exit_message(child).unwrap(), ChildExit::Exited(0));
    linux.kernel.done();
}

fn clone_steps() -> Vec<Step> {
    let mut steps = Vec::new();
    for fd in 50..55 {
        steps.push(Step::Scalar(abi::NR_FCNTL, Some(fd), 1));
    }
    steps.push(Step::Scalar(abi::NR_PRCTL, Some(39), 1));
    steps.push(Step::Scalar(abi::NR_RT_SIGPROCMASK, Some(2), 0));
    for signal in 1..=64 {
        if signal == 9 || signal == 19 {
            continue;
        }
        steps.push(Step::Scalar(abi::NR_RT_SIGACTION, Some(signal), 0));
        steps.push(Step::Scalar(abi::NR_RT_SIGACTION, Some(signal), 0));
    }
    steps.push(Step::Scalar(abi::NR_SIGALTSTACK, None, 0));
    steps.push(Step::AltStack);
    steps.push(Step::Mask);
    for fd in 50..53 {
        steps.push(Step::Stat(fd, 0x1000, 100 + fd as u64));
    }
    steps.push(Step::Stat(54, 0xc000, 200));
    steps.push(Step::Clone(2, 6));
    for fd in 50..55 {
        steps.push(Step::Scalar(abi::NR_CLOSE, Some(fd), 0));
    }
    steps.extend([
        Step::Scalar(abi::NR_FCNTL, Some(14), (-9i64) as u64),
        Step::Scalar(abi::NR_DUP3, Some(6), 14),
        Step::Scalar(abi::NR_CLOSE, Some(6), 0),
    ]);
    for fd in [40, 41, 42, 43, 4] {
        steps.push(Step::Scalar(abi::NR_CLOSE, Some(fd), 0));
    }
    steps
}
fn handoff_steps() -> Vec<Step> {
    let mut fds = vec![0, 1, 2, 3, 10, 11, 12, 13, 14, 15];
    fds.extend(20..32);
    vec![
        Step::Poll(vec![(3, READ | 16)]),
        Step::Listener(5),
        Step::Scalar(abi::NR_FCNTL, Some(15), (-9i64) as u64),
        Step::Scalar(abi::NR_DUP3, Some(5), 15),
        Step::Scalar(abi::NR_CLOSE, Some(5), 0),
        Step::Scalar(abi::NR_CLOSE, Some(3), 0),
        Step::Scalar(abi::NR_OPENAT, None, 3),
        Step::Directory(fds),
        Step::Directory(vec![]),
        Step::Scalar(abi::NR_CLOSE, Some(3), 0),
        Step::InstallSupervisor,
    ]
}
fn output_steps(p: &Prepared, encoder: &mut BootstrapEncoder) -> Vec<Step> {
    let stdout = b"sat\n".to_vec();
    let messages = [
        BootstrapMessage::StdoutChunk(stdout.clone()),
        BootstrapMessage::StdoutEof,
        BootstrapMessage::StderrEof,
        BootstrapMessage::ChildExit(ChildExit::Exited(0)),
        BootstrapMessage::Final(Final {
            child_reaped: true,
            only_supervisor: true,
        }),
    ];
    let frames = messages
        .into_iter()
        .map(|message| encoder.encode(&frame(p, message)).unwrap())
        .collect::<Vec<_>>();
    let query = p.query.clone();
    let mut steps = vec![
        Step::Poll(vec![(10, WRITE)]),
        Step::Write(10, query.clone(), 3),
        Step::Poll(vec![(10, WRITE)]),
        Step::Write(10, query[3..].to_vec(), query.len() - 3),
        Step::Scalar(abi::NR_CLOSE, Some(10), 0),
        Step::Poll(vec![(11, READ)]),
        Step::Read(11, stdout),
        Step::Poll(vec![(1, WRITE)]),
        Step::Write(1, frames[0].clone(), frames[0].len()),
        Step::Poll(vec![(14, READ), (15, 16), (11, 16), (12, 16)]),
        Step::Wait(Some(abi::ChildExit {
            pid: 2,
            uid: 1000,
            code: 1,
            status: 0,
        })),
        Step::Read(11, vec![]),
        Step::Scalar(abi::NR_CLOSE, Some(11), 0),
        Step::Poll(vec![(1, WRITE)]),
        Step::Write(1, frames[1].clone(), frames[1].len()),
        Step::Poll(vec![(12, 16)]),
        Step::Read(12, vec![]),
        Step::Scalar(abi::NR_CLOSE, Some(12), 0),
        Step::Poll(vec![(1, WRITE)]),
        Step::Write(1, frames[2].clone(), frames[2].len()),
        Step::Poll(vec![(1, WRITE)]),
        Step::Write(1, frames[3].clone(), frames[3].len()),
    ];
    steps.extend(crate::observation::tests::reads(
        &crate::observation::tests::files("1\n", "1\n"),
    ));
    steps.extend([
        Step::Poll(vec![(1, WRITE)]),
        Step::Write(1, frames[4].clone(), frames[4].len()),
        Step::Scalar(abi::NR_READ, Some(0), (-11i64) as u64),
    ]);
    steps
}
#[test]
fn complete_run_uses_real_frozen_pointers_and_policy_checks_every_final_syscall() {
    let mut p = fixture();
    let pointers = p.frozen.as_ref().unwrap().pointers();
    let query = p.query.clone();
    let mut encoder = BootstrapEncoder::new(Direction::SupervisorToMac, p.configuration.wire);
    let ready = BootstrapFrame {
        binding: p.binding.clone(),
        message: BootstrapMessage::Ready(radishaxiom_solver_supervision_core::wire::Ready {
            linux_ready_ns: 1,
            preparation_deadline_ns: p.deadline.until,
            boot_digest: [8; 32],
            namespace_digest: [9; 32],
            configuration_digest: [6; 32],
        }),
    };
    let ready = encoder.encode(&ready).unwrap();
    let mut control = BootstrapEncoder::new(Direction::MacToSupervisor, p.configuration.wire);
    let mut inbound = control
        .encode(&frame(
            &p,
            BootstrapMessage::Arm(radishaxiom_solver_supervision_core::wire::Arm {
                deadline_ns: 5_000_000_000,
                query_len: query.len() as u32,
                query_digest: radishaxiom_digest::digest(&query),
            }),
        ))
        .unwrap();
    inbound.extend(
        control
            .encode(&frame(&p, BootstrapMessage::QueryChunk(query.clone())))
            .unwrap(),
    );
    inbound.extend(
        control
            .encode(&frame(&p, BootstrapMessage::QueryEnd))
            .unwrap(),
    );
    let mut steps = vec![
        Step::Poll(vec![(1, WRITE)]),
        Step::Write(1, ready.clone(), ready.len()),
        Step::Poll(vec![(0, READ)]),
        Step::Read(0, inbound),
        Step::Scalar(abi::NR_TIMERFD_SETTIME, Some(13), 0),
        Step::Scalar(abi::NR_READ, Some(0), (-11i64) as u64),
    ];
    steps.extend(clone_steps());
    steps.extend(handoff_steps());
    steps.extend([
        Step::Poll(vec![(15, READ)]),
        Step::Notification(notif(pointers)),
        Step::Scalar(abi::NR_IOCTL, Some(15), 0),
        Step::Scalar(abi::NR_READ, Some(0), (-11i64) as u64),
        Step::Scalar(abi::NR_IOCTL, Some(15), 0),
        Step::Wait(None),
    ]);
    steps.extend(crate::observation::tests::reads(
        &crate::observation::tests::files("1\n2\n", "2\n"),
    ));
    steps.push(Step::Wait(None));
    steps.extend(output_steps(&p, &mut encoder));
    for _ in 0..18 {
        steps.push(Step::Scalar(abi::NR_CLOSE, None, 0));
    }
    p.query.clear();
    let mut linux = Linux::new(Script::new(steps));
    let result =
        run(&mut linux, p).unwrap_or_else(|failure| panic!("failure: {:?}", failure.primary_error));
    assert_eq!(
        result.child,
        ChildFact::Reaped {
            pid: 2,
            code: 1,
            status: 0
        }
    );
    assert_eq!(result.stdout_bytes, 4);
    assert_eq!(result.stderr_bytes, 0);
    assert_eq!(result.observations.reads.len(), 2);
    assert!(linux.kernel.supervisor_policy);
    assert_eq!(
        linux
            .kernel
            .calls
            .iter()
            .filter(|nr| **nr == abi::NR_CLONE3)
            .count(),
        1
    );
    assert_eq!(
        linux
            .kernel
            .calls
            .iter()
            .filter(|nr| **nr == abi::NR_IOCTL)
            .count(),
        3
    );
    assert_eq!(linux.kernel.polled.len(), 14);
    assert!(
        linux.kernel.polled[9..]
            .iter()
            .all(|fds| !fds.contains(&14) && !fds.contains(&15))
    );
    linux.kernel.done();
}
#[test]
fn queued_listener_is_received_once_even_with_socket_hup() {
    let mut p = fixture();
    let mut linux = Linux::new(Script::new([
        Step::Poll(vec![(3, READ | 16)]),
        Step::Listener(5),
        Step::Scalar(abi::NR_CLOSE, Some(5), 0),
    ]));
    let listener = receive_listener(&mut linux, &mut p, 14).unwrap();
    assert_eq!(listener.raw(), 5);
    linux.close(listener).unwrap();
    linux.kernel.done();
}
#[test]
fn every_postquery_byte_is_protocol_failure_even_when_frame_is_incomplete() {
    let p = fixture();
    let input = ControlInput::new(&p);
    let mut linux = Linux::new(Script::new([Step::Read(0, vec![b'A'])]).supervised());
    assert!(matches!(
        ensure_no_control(&mut linux, &input),
        Err(SupervisorError::Protocol)
    ));
    linux.kernel.done();
}
#[test]
fn failed_run_retains_primary_partial_diagnostic_cleanup_and_original_reads() {
    let mut p = fixture();
    let mut steps =
        crate::observation::tests::reads(&crate::observation::tests::files("1\n", "1\n"));
    steps.extend([
        Step::Poll(vec![(13, READ)]),
        Step::Write(
            2,
            b"AXB failure operation=deadline errno=none\n".to_vec(),
            5,
        ),
    ]);
    for fd in 50..55 {
        steps.push(Step::Scalar(
            abi::NR_CLOSE,
            Some(fd),
            if fd == 52 { (-4i64) as u64 } else { 0 },
        ));
    }
    for fd in p.resources.descriptors().into_iter().rev() {
        steps.push(Step::Scalar(abi::NR_CLOSE, Some(fd as u64), 0));
    }
    let mut linux = Linux::new(Script::new(steps));
    let mut child = ChildFact::Absent;
    p.observations
        .capture(
            &mut linux,
            &p.cgroup,
            p.configuration.cgroup,
            p.deadline.until,
            &mut child,
            None,
        )
        .unwrap();
    let failure = match run(&mut linux, p) {
        Err(failure) => failure,
        Ok(_) => panic!("unexpected success"),
    };
    assert!(matches!(
        failure.primary_error,
        SupervisorError::Setup(SetupError::Deadline)
    ));
    assert_eq!(failure.cleanup.emergency_write.unwrap().unwrap(), 5);
    assert_eq!(failure.cleanup.close_errors.len(), 1);
    assert_eq!(failure.cleanup.close_errors[0].errno(), Some(4));
    assert_eq!(failure.observations.reads.len(), 1);
    assert_eq!(failure.observations.reads[0].files[10], b"1\n");
    assert!(failure.cleanup.kill.is_none());
    linux.kernel.done();
}
#[test]
fn interrupted_control_check_cannot_authorize_continue_or_final() {
    let p = fixture();
    let input = ControlInput::new(&p);
    let mut linux =
        Linux::new(Script::new([Step::Scalar(abi::NR_READ, Some(0), (-4i64) as u64)]).supervised());
    assert!(
        matches!(ensure_no_control(&mut linux,&input),Err(SupervisorError::System(error))if error.errno()==Some(4))
    );
    linux.kernel.done();
    let mut p = fixture();
    let mut linux = Linux::new(
        Script::new([
            Step::Poll(vec![(15, READ)]),
            Step::Notification(notif(pointers())),
            Step::Scalar(abi::NR_IOCTL, Some(15), 0),
            Step::Scalar(abi::NR_READ, Some(0), (-4i64) as u64),
        ])
        .supervised(),
    );
    assert!(
        matches!(grant_first_exec(&mut linux,&mut p,14,15,2,pointers()),Err(SupervisorError::System(error))if error.errno()==Some(4))
    );
    assert_eq!(
        linux
            .kernel
            .calls
            .iter()
            .filter(|nr| **nr == abi::NR_IOCTL)
            .count(),
        2
    );
    linux.kernel.done();
}
