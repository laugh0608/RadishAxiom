//! These scripts test submitted register plans, not clone/seccomp execution.
use super::*;
use crate::syscall::ErrorKind;
use std::panic::{AssertUnwindSafe, catch_unwind};

struct ParentScript {
    calls: Vec<Call>,
    clone_result: u64,
    clone_count: usize,
}
// SAFETY: operation-specific writes below stay inside the exact typed buffers.
unsafe impl Kernel for ParentScript {
    unsafe fn invoke(&mut self, call: Call) -> u64 {
        self.calls.push(call);
        match call.nr {
            NR_FCNTL => {
                assert_eq!(call.args[1], F_GETFD);
                1
            }
            NR_FSTAT => {
                // SAFETY: typed fstat supplies a live exclusive Stat output.
                let stat = unsafe { &mut *(call.args[1] as *mut Stat) };
                stat.mode = if call.args[0] == 10 { 0xc000 } else { 0x1000 };
                stat.dev = 7;
                stat.ino = call.args[0];
                0
            }
            NR_CLOCK_GETTIME => {
                // SAFETY: clock wrapper supplies exclusive live timespec.
                unsafe {
                    *(call.args[1] as *mut Timespec) = Timespec { sec: 0, nsec: 1 };
                }
                0
            }
            NR_PRCTL => {
                assert_eq!(call.args[0], PR_GET_NO_NEW_PRIVS);
                1
            }
            NR_RT_SIGPROCMASK => {
                assert_eq!(call.args[3], 8);
                if call.args[1] != 0 {
                    // SAFETY: signal-block supplies a live immutable u64.
                    assert_eq!(unsafe { *(call.args[1] as *const u64) }, BLOCKED_SIGNALS);
                } else {
                    // SAFETY: signal-readback supplies exclusive live u64.
                    unsafe {
                        *(call.args[2] as *mut u64) = BLOCKED_SIGNALS;
                    }
                }
                0
            }
            NR_RT_SIGACTION => {
                assert_eq!(call.args[3], 8);
                if call.args[1] != 0 {
                    // SAFETY: action input remains live throughout invocation.
                    let action = unsafe { &*(call.args[1] as *const SigAction) };
                    assert_eq!(
                        (action.handler, action.flags, action.restorer, action.mask),
                        (0, 0, 0, 0)
                    );
                }
                0
            }
            NR_SIGALTSTACK => {
                if call.args[1] != 0 {
                    // SAFETY: wrapper supplies exclusive AltStack output.
                    unsafe {
                        (*(call.args[1] as *mut AltStack)).flags = 2;
                    }
                }
                0
            }
            NR_CLONE3 => {
                self.clone_count += 1;
                assert_eq!(call.args[1], 88);
                assert_eq!(&call.args[2..], &[0; 4]);
                // SAFETY: clone wrapper supplies initialized CloneArgs with a
                // live exclusive pidfd i32. Script never returns child branch.
                let args = unsafe { &*(call.args[0] as *const CloneArgs) };
                assert_eq!(args.flags, 0x1000);
                assert_eq!(args.exit_signal, 17);
                assert_eq!(
                    [
                        args.child_tid,
                        args.parent_tid,
                        args.stack,
                        args.stack_size,
                        args.tls,
                        args.set_tid,
                        args.set_tid_size,
                        args.cgroup
                    ],
                    [0; 8]
                );
                if self.clone_result == 42 {
                    unsafe {
                        *(args.pidfd as *mut i32) = 50;
                    }
                }
                self.clone_result
            }
            NR_CLOSE => 0,
            _ => panic!("unlisted scripted call {}", call.nr),
        }
    }
}
fn frozen() -> FrozenChild {
    // SAFETY: synthetic unique descriptors never reach a native backend.
    let scratch = [6, 7, 8, 9, 10].map(|fd| unsafe { OwnedFd::from_raw(fd) });
    let tokens = (0..12).map(|i| format!("--bound-{i}")).collect::<Vec<_>>();
    let mut linux = Linux::new(ParentScript {
        calls: vec![],
        clone_result: 42,
        clone_count: 0,
    });
    FrozenChild::new(
        scratch,
        FrozenChildArguments::from_bound_tokens(&tokens).unwrap(),
        &mut linux,
    )
    .unwrap()
}
#[test]
fn clone_is_single_pidfd_sigchld_cow_stack_and_argv_is_frozen() {
    let mut child = frozen();
    let pointers = child.pointers();
    let mut linux = Linux::new(ParentScript {
        calls: vec![],
        clone_result: 42,
        clone_count: 0,
    });
    let result = child.clone_once(&mut linux, 1000).unwrap();
    assert_eq!(result.pid, 42);
    assert_eq!(result.pidfd.raw(), 50);
    assert_eq!(result.pointers.argv, pointers.argv);
    assert_eq!(result.pointers.envp, pointers.envp);
    assert_eq!(
        child.clone_once(&mut linux, 1000).err().unwrap().kind,
        ErrorKind::InvalidInput
    );
    assert_eq!(linux.kernel.clone_count, 1);
    linux.close(result.pidfd).unwrap();
    child.close_parent_fds(&mut linux).unwrap();
    // SAFETY: frozen box remains live; pointer table has argv0+12 args+NULL.
    unsafe {
        let args = core::slice::from_raw_parts(pointers.argv as *const u64, 14);
        assert_eq!(args[13], 0);
        assert_eq!(*(pointers.envp as *const u64), 0);
        assert_eq!(*(pointers.empty_path as *const u8), 0);
    }
}
#[test]
fn interrupted_clone_is_never_retried() {
    let mut child = frozen();
    let mut linux = Linux::new(ParentScript {
        calls: vec![],
        clone_result: 0u64.wrapping_sub(4),
        clone_count: 0,
    });
    assert_eq!(
        child.clone_once(&mut linux, 1000).err().unwrap().errno(),
        Some(4)
    );
    assert!(child.clone_once(&mut linux, 1000).is_err());
    assert_eq!(linux.kernel.clone_count, 1);
    child.close_parent_fds(&mut linux).unwrap();
}
#[derive(Debug)]
struct Terminal;
struct TailScript {
    calls: Vec<Call>,
    listener: u64,
    pipe_dev: u64,
    filtered: bool,
}
// SAFETY: only fstat writes to live exclusive typed buffers. Panic at terminal
// exit is test-only escape from ->! and cannot be selected by native production.
unsafe impl Kernel for TailScript {
    unsafe fn invoke(&mut self, call: Call) -> u64 {
        if self.filtered {
            let data = SeccompData::aarch64(call.nr, call.args);
            let expected = if call.nr == NR_EXECVEAT {
                SECCOMP_RET_USER_NOTIF
            } else {
                SECCOMP_RET_ALLOW
            };
            assert_eq!(
                radishaxiom_solver_supervision_core::policy::semantic_worker_decision(&data),
                expected
            );
            assert_eq!(worker_policy().evaluate(&data).unwrap(), expected);
        }
        self.calls.push(call);
        match call.nr {
            NR_DUP3 => call.args[1],
            NR_CLOSE_RANGE => {
                assert_eq!(call.args, [5, u32::MAX as u64, 0, 0, 0, 0]);
                0
            }
            NR_FSTAT => {
                // SAFETY: tail creates exclusive fixed local Stat for this call.
                let stat = unsafe { &mut *(call.args[1] as *mut Stat) };
                stat.mode = 0x1000;
                stat.dev = self.pipe_dev;
                stat.ino = call.args[0] + 6;
                0
            }
            NR_FCNTL => match call.args[1] {
                F_GETFL => {
                    if call.args[0] == 0 {
                        0
                    } else {
                        1
                    }
                }
                F_GETFD => {
                    if call.args[0] < 3 {
                        0
                    } else {
                        1
                    }
                }
                F_GET_SEALS => 15,
                _ => panic!("unexpected fcntl"),
            },
            NR_CLOCK_GETTIME => {
                // SAFETY: clock wrapper supplies exclusive live timespec.
                unsafe {
                    *(call.args[1] as *mut Timespec) = Timespec { sec: 0, nsec: 1 };
                }
                0
            }
            NR_PRCTL => 1,
            NR_SECCOMP => {
                // SAFETY: tail provides initialized program pointing at live
                // existing generator output; test reads only that exact extent.
                let program = unsafe { &*(call.args[2] as *const SockFprog) };
                assert_eq!(program.len, 782);
                let filters = unsafe {
                    core::slice::from_raw_parts(
                        program.filter as *const SockFilter,
                        program.len as usize,
                    )
                };
                let mut bytes = vec![];
                for i in filters {
                    bytes.extend(i.code.to_le_bytes());
                    bytes.extend([i.jt, i.jf]);
                    bytes.extend(i.k.to_le_bytes());
                }
                assert_eq!(bytes, worker_policy().bytes());
                self.filtered = true;
                self.listener
            }
            NR_SENDMSG => {
                assert_eq!(call.args[0], 4);
                assert_eq!(call.args[2], MSG_NOSIGNAL);
                8
            }
            NR_CLOSE => 0,
            NR_EXECVEAT => {
                assert_eq!(call.args[0], 3);
                assert_eq!(call.args[4], AT_EMPTY_PATH);
                0u64.wrapping_sub(13)
            }
            NR_EXIT_GROUP => std::panic::panic_any(Terminal),
            _ => panic!("unexpected tail syscall {}", call.nr),
        }
    }
}
#[test]
fn child_remaps_before_close_range_then_sends_once_and_executes_exactly() {
    for (listener, pipe_dev, exec_count) in [(5, 7, 1), (6, 7, 0), (5, 8, 0)] {
        let child = frozen();
        let input = TailInputs {
            identities: [(7, 6), (7, 7), (7, 8)],
            sources: [6, 7, 8, 9, 10],
            program: SockFprog {
                len: child.filters.len() as u16,
                pad: [0; 6],
                filter: child.filters.as_ptr() as u64,
            },
            pointers: child.pointers(),
            message: &*child.listener_msg as *const _ as u64,
        };
        let mut script = TailScript {
            calls: vec![],
            listener,
            pipe_dev,
            filtered: false,
        };
        let result = catch_unwind(AssertUnwindSafe(|| {
            // SAFETY: synthetic frozen buffers and Script contracts above;
            // no real clone, descriptor mutation or process exit occurs.
            unsafe { child_tail(&mut script, &input) }
        }));
        assert!(result.unwrap_err().is::<Terminal>());
        assert_eq!(
            script.calls.iter().filter(|c| c.nr == NR_EXECVEAT).count(),
            exec_count
        );
        assert_eq!(
            script.calls.iter().filter(|c| c.nr == NR_SENDMSG).count(),
            exec_count
        );
        assert!(script.calls[..5].iter().all(|c| c.nr == NR_DUP3));
        assert_eq!(script.calls[5].nr, NR_CLOSE_RANGE);
    }
}

#[test]
fn invalid_scratch_returns_error_and_closes_each_unique_descriptor_once() {
    let mut linux = Linux::new(ParentScript {
        calls: vec![],
        clone_result: 42,
        clone_count: 0,
    });
    // SAFETY: deliberate synthetic duplicated tokens only for malformed input;
    // no native OS descriptors are acquired or passed to this backend.
    let scratch = [6, 6, 8, 9, 10].map(|fd| unsafe { OwnedFd::from_raw(fd) });
    let tokens = (0..12).map(|i| format!("--bound-{i}")).collect::<Vec<_>>();
    assert!(
        FrozenChild::new(
            scratch,
            FrozenChildArguments::from_bound_tokens(&tokens).unwrap(),
            &mut linux
        )
        .is_err()
    );
    assert_eq!(
        linux
            .kernel
            .calls
            .iter()
            .map(|c| (c.nr, c.args[0]))
            .collect::<Vec<_>>(),
        vec![(NR_CLOSE, 6), (NR_CLOSE, 8), (NR_CLOSE, 9), (NR_CLOSE, 10)]
    );
}
#[test]
fn already_expired_signal_freeze_never_clones() {
    let mut child = frozen();
    let mut linux = Linux::new(ParentScript {
        calls: vec![],
        clone_result: 42,
        clone_count: 0,
    });
    assert!(child.clone_once(&mut linux, 1).is_err());
    assert_eq!(linux.kernel.clone_count, 0);
    child.close_parent_fds(&mut linux).unwrap();
}
