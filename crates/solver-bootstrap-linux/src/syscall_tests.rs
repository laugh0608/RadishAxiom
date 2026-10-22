//! Explicit scripted ABI tests, never host kernel observations.
use super::*;
use std::collections::VecDeque;

struct Step {
    nr: i32,
    action: Box<dyn FnOnce(Call) -> u64>,
}
struct Script {
    steps: VecDeque<Step>,
}
impl Script {
    fn new(steps: Vec<Step>) -> Self {
        Self {
            steps: steps.into(),
        }
    }
    fn finished(&self) {
        assert!(self.steps.is_empty());
    }
}
fn step(nr: i32, action: impl FnOnce(Call) -> u64 + 'static) -> Step {
    Step {
        nr,
        action: Box::new(action),
    }
}
// SAFETY: each action below writes only the exact operation's supplied live
// buffers during invoke. No script retains pointers, invokes native or guesses
// successful operations: missing/wrong steps fail the test immediately.
unsafe impl Kernel for Script {
    unsafe fn invoke(&mut self, call: Call) -> u64 {
        let step = self
            .steps
            .pop_front()
            .expect("unexpected scripted operation");
        assert_eq!(step.nr, call.nr);
        (step.action)(call)
    }
}
#[test]
fn raw_negative_errno_range_preserves_all_bits() {
    assert_eq!(decode("raw", 0), Ok(0));
    assert_eq!(decode("raw", u64::MAX - 4095), Ok(u64::MAX - 4095));
    for errno in 1..=4095u16 {
        let error = decode("operation", 0u64.wrapping_sub(errno as u64)).unwrap_err();
        assert_eq!(error.operation, "operation");
        assert_eq!(error.errno(), Some(errno));
    }
    assert_eq!(decode("raw", 0x00000000ffffffff), Ok(0x00000000ffffffff));
}
#[test]
fn reads_expose_short_io_eintr_and_oversize_without_retry() {
    let mut linux = Linux::new(Script::new(vec![
        step(NR_READ, |call| {
            assert_eq!(call.args[0], 11);
            assert_eq!(call.args[2], 4);
            // SAFETY: wrapper gives this action an exclusive four-byte output.
            unsafe {
                (call.args[1] as *mut u8).write(b'a');
            }
            1
        }),
        step(NR_READ, |_| 0u64.wrapping_sub(4)),
        step(NR_READ, |_| 5),
    ]));
    let mut bytes = [0; 4];
    assert_eq!(linux.read(11, &mut bytes), Ok(1));
    assert_eq!(bytes, [b'a', 0, 0, 0]);
    assert_eq!(linux.read(11, &mut bytes).unwrap_err().errno(), Some(4));
    assert_eq!(
        linux.read(11, &mut bytes).unwrap_err().kind,
        ErrorKind::InvalidReturn
    );
    linux.kernel.finished();
}
#[test]
fn raw_ppoll_supplies_writable_remaining_timeout() {
    let mut linux = Linux::new(Script::new(vec![step(NR_PPOLL, |call| {
        assert_eq!(&call.args[3..], &[0, 8, 0]);
        assert_eq!(call.args[1], 1);
        // SAFETY: wrapper owns a live exclusive Timespec; raw ppoll writes its
        // remaining timeout. This test models that write on the Darwin host.
        let timeout = unsafe { &mut *(call.args[2] as *mut Timespec) };
        assert_eq!(*timeout, Timespec { sec: 1, nsec: 2 });
        timeout.sec = 0;
        timeout.nsec = 3;
        // SAFETY: a single valid exclusive pollfd was supplied by wrapper.
        unsafe {
            (*(call.args[0] as *mut PollFd)).revents = 1;
        }
        1
    })]));
    let mut fds = [PollFd {
        fd: 13,
        events: 1,
        revents: 0,
    }];
    assert_eq!(linux.poll(&mut fds, 1_000_000_002), Ok(1));
    assert_eq!(fds[0].revents, 1);
    linux.kernel.finished();
}
#[test]
fn close_consumes_once_even_on_eintr_and_dup_does_not_replace() {
    let mut linux = Linux::new(Script::new(vec![
        step(NR_CLOSE, |call| {
            assert_eq!(call.args[0], 10);
            0u64.wrapping_sub(4)
        }),
        step(NR_FCNTL, |call| {
            assert_eq!(call.args[..2], [14, F_GETFD]);
            1
        }),
    ]));
    // SAFETY: synthetic unique token; Script never reaches the OS.
    let owned = unsafe { OwnedFd::from_raw(10) };
    assert_eq!(linux.close(owned).unwrap_err().errno(), Some(4));
    assert_eq!(
        linux.duplicate(20, 14, true).unwrap_err().kind,
        ErrorKind::Ownership
    );
    assert!(linux.duplicate(20, 20, true).is_err());
    linux.kernel.finished();
}
#[test]
fn fstat_requires_zero_and_waitid_checks_signal_header() {
    let mut linux = Linux::new(Script::new(vec![
        step(NR_FSTAT, |_| 1),
        step(NR_WAITID, |call| {
            assert_eq!(call.args[0], 3);
            assert_eq!(call.args[1], 14);
            assert_eq!(&call.args[3..], &[5, 0, 0]);
            // SAFETY: wait wrapper supplies exclusive zeroed 128-byte SigInfo.
            let info = unsafe { &mut *(call.args[2] as *mut SigInfo) };
            info.bytes[..4].copy_from_slice(&11i32.to_le_bytes());
            info.bytes[8..12].copy_from_slice(&1i32.to_le_bytes());
            info.bytes[16..20].copy_from_slice(&2u32.to_le_bytes());
            0
        }),
        step(NR_WAITID, |_| 0),
    ]));
    assert!(linux.fstat(10).is_err());
    assert!(linux.wait(14).is_err());
    assert_eq!(linux.wait(14), Ok(None));
    linux.kernel.finished();
}
fn received(call: Call, rights: &[i32], payload: &[u8; 8], flags: u32) -> u64 {
    assert_eq!(call.args[2], 0x40000040);
    // SAFETY: recv wrapper gives exact live exclusive header and nested buffers.
    unsafe {
        let msg = &mut *(call.args[1] as *mut MsgHdr);
        let iov = &*(msg.iov as *const Iovec);
        core::ptr::copy_nonoverlapping(payload.as_ptr(), iov.base as *mut u8, 8);
        let control =
            core::slice::from_raw_parts_mut(msg.control as *mut u8, msg.controllen as usize);
        let len = 16 + rights.len() * 4;
        control[..8].copy_from_slice(&(len as u64).to_le_bytes());
        control[8..12].copy_from_slice(&1i32.to_le_bytes());
        control[12..16].copy_from_slice(&1i32.to_le_bytes());
        for (chunk, fd) in control[16..len].chunks_exact_mut(4).zip(rights) {
            chunk.copy_from_slice(&fd.to_le_bytes());
        }
        msg.controllen = ((len + 7) & !7) as u64;
        msg.flags = flags;
    }
    8
}
#[test]
fn listener_rejection_closes_every_received_descriptor_before_return() {
    let mut linux = Linux::new(Script::new(vec![
        step(NR_RECVMSG, |call| {
            received(call, &[40, 41], LISTENER_RECORD, 0)
        }),
        step(NR_CLOSE, |call| {
            assert_eq!(call.args[0], 40);
            0
        }),
        step(NR_CLOSE, |call| {
            assert_eq!(call.args[0], 41);
            0
        }),
        step(NR_RECVMSG, |call| received(call, &[42], b"BAD-LST1", 8)),
        step(NR_CLOSE, |call| {
            assert_eq!(call.args[0], 42);
            0
        }),
        step(NR_RECVMSG, |call| received(call, &[43], LISTENER_RECORD, 0)),
        step(NR_CLOSE, |call| {
            assert_eq!(call.args[0], 43);
            0
        }),
    ]));
    assert!(linux.receive_listener(9).is_err());
    assert!(linux.receive_listener(9).is_err());
    let listener = linux.receive_listener(9).unwrap();
    assert_eq!(listener.raw(), 43);
    linux.close(listener).unwrap();
    linux.kernel.finished();
}
#[test]
fn notification_continue_uses_existing_exact_value_encoding_once() {
    let mut linux = Linux::new(Script::new(vec![step(NR_IOCTL, |call| {
        assert_eq!(call.args[0], 15);
        assert_eq!(call.args[1], SECCOMP_IOCTL_NOTIF_SEND);
        // SAFETY: wrapper provides an immutable 24-byte response until return.
        let bytes = unsafe { core::slice::from_raw_parts(call.args[2] as *const u8, 24) };
        assert_eq!(&bytes[..8], &7u64.to_le_bytes());
        assert_eq!(&bytes[8..20], &[0; 12]);
        assert_eq!(&bytes[20..], &1u32.to_le_bytes());
        0u64.wrapping_sub(2)
    })]));
    assert_eq!(
        linux.continue_notification(15, 7).unwrap_err().errno(),
        Some(2)
    );
    linux.kernel.finished();
}

#[test]
fn anomalous_partial_pair_output_is_closed_and_cleanup_errno_preserved() {
    let mut linux = Linux::new(Script::new(vec![
        step(NR_PIPE2, |call| {
            // SAFETY: pair wrapper provides live exclusive two-i32 output.
            unsafe {
                *(call.args[0] as *mut i32) = 40;
            }
            1
        }),
        step(NR_CLOSE, |call| {
            assert_eq!(call.args[0], 40);
            0u64.wrapping_sub(5)
        }),
    ]));
    let error = linux.pipe().err().unwrap();
    assert_eq!(error.errno(), Some(5));
    assert_eq!(error.operation, "pair-invalid-output-cleanup-close");
    linux.kernel.finished();
}

fn clock_step(ns: u64) -> Step {
    step(NR_CLOCK_GETTIME, move |call| {
        // SAFETY: boottime wrapper gives a live exclusive Timespec output.
        unsafe {
            *(call.args[1] as *mut Timespec) = Timespec::from_ns(ns);
        }
        0
    })
}
#[test]
fn signal_freeze_rejects_clock_rollback_before_handler_reset() {
    let mut linux = Linux::new(Script::new(vec![
        clock_step(10),
        step(NR_RT_SIGPROCMASK, |_| 0),
        clock_step(9),
    ]));
    assert_eq!(
        linux.freeze_signals(100).unwrap_err().operation,
        "signal-freeze-clock-rollback"
    );
    linux.kernel.finished();
}
#[test]
fn signal_freeze_final_clock_check_is_not_omitted() {
    let mut steps = vec![clock_step(10), step(NR_RT_SIGPROCMASK, |_| 0)];
    for signal in 1..=64u64 {
        if signal == 9 || signal == 19 {
            continue;
        }
        steps.push(clock_step(11));
        steps.push(step(NR_RT_SIGACTION, move |call| {
            assert_eq!(call.args[0], signal);
            assert_ne!(call.args[1], 0);
            0
        }));
        steps.push(step(NR_RT_SIGACTION, move |call| {
            assert_eq!(call.args[0], signal);
            assert_ne!(call.args[2], 0);
            0
        }));
    }
    steps.push(step(NR_SIGALTSTACK, |_| 0));
    steps.push(step(NR_SIGALTSTACK, |call| {
        // SAFETY: readback supplies exclusive live AltStack.
        unsafe {
            (*(call.args[1] as *mut AltStack)).flags = 2;
        }
        0
    }));
    steps.push(step(NR_RT_SIGPROCMASK, |call| {
        // SAFETY: mask readback supplies exclusive live u64.
        unsafe {
            *(call.args[2] as *mut u64) = BLOCKED_SIGNALS;
        }
        0
    }));
    steps.push(clock_step(10));
    let mut linux = Linux::new(Script::new(steps));
    assert_eq!(
        linux.freeze_signals(100).unwrap_err().operation,
        "signal-freeze-clock-rollback"
    );
    linux.kernel.finished();
}
#[test]
fn bad_listener_with_close_error_keeps_record_rejection_context() {
    let mut linux = Linux::new(Script::new(vec![
        step(NR_RECVMSG, |call| received(call, &[40], b"BAD-LST1", 0)),
        step(NR_CLOSE, |_| 0u64.wrapping_sub(5)),
    ]));
    let error = linux.receive_listener(9).err().unwrap();
    assert_eq!(error.operation, "listener-record-rejected-cleanup-close");
    assert_eq!(error.errno(), Some(5));
    linux.kernel.finished();
}
