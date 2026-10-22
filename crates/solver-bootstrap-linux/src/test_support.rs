//! Explicit in-memory Linux script. Never opens a host descriptor or executes OS calls.
use crate::{
    abi,
    fd::OwnedFd,
    syscall::{Call, Kernel},
};
use std::collections::VecDeque;
#[derive(Debug)]
pub(crate) enum Step {
    Clock(u64),
    Read(i32, Vec<u8>),
    Write(i32, Vec<u8>, usize),
    Poll(Vec<(i32, i16)>),
    Wait(Option<abi::ChildExit>),
    Notification(abi::SeccompNotification),
    Scalar(i32, Option<u64>, u64),
    Listener(i32),
    Stat(i32, u32, u64),
    Clone(u32, i32),
    AltStack,
    Mask,
    Directory(Vec<i32>),
    InstallSupervisor,
    Pread(i32, u64, Vec<u8>),
}
pub(crate) struct Script {
    pub steps: VecDeque<Step>,
    pub calls: Vec<i32>,
    pub auto_clock: u64,
    pub supervisor_policy: bool,
    pub polled: Vec<Vec<i32>>,
}
impl Script {
    pub fn new(steps: impl IntoIterator<Item = Step>) -> Self {
        Self {
            steps: steps.into_iter().collect(),
            calls: Vec::new(),
            auto_clock: 1,
            supervisor_policy: false,
            polled: Vec::new(),
        }
    }
    pub fn supervised(mut self) -> Self {
        self.supervisor_policy = true;
        self
    }
    pub fn done(&self) {
        assert!(self.steps.is_empty(), "unconsumed script: {:?}", self.steps);
    }
}
// SAFETY: each step checks the syscall and writes only the documented extent.
// Pointers are synchronous, do not escape, and no host API/fallback exists.
unsafe impl Kernel for Script {
    unsafe fn invoke(&mut self, call: Call) -> u64 {
        self.calls.push(call.nr);
        if self.supervisor_policy {
            let policy = radishaxiom_solver_supervision_core::policy::SupervisorRuntimePolicy::new(
                radishaxiom_solver_supervision_core::policy::BOOTSTRAP_SUPERVISOR_ROLES,
            )
            .unwrap();
            assert_eq!(
                policy.semantic_action(&abi::SeccompData::aarch64(call.nr, call.args)),
                abi::SECCOMP_RET_ALLOW,
                "S policy denied nr {} args {:?}",
                call.nr,
                call.args
            );
        }

        if call.nr == abi::NR_CLOCK_GETTIME && !matches!(self.steps.front(), Some(Step::Clock(_))) {
            let ns = self.auto_clock;
            self.auto_clock += 1;
            unsafe {
                (call.args[1] as *mut abi::Timespec).write(abi::Timespec::from_ns(ns));
            }
            return 0;
        }
        let step = self
            .steps
            .pop_front()
            .expect("unexpected syscall after script end");
        match step {
            Step::Clock(ns) => {
                assert_eq!(call.nr, abi::NR_CLOCK_GETTIME);
                assert_eq!(call.args[0], 7);
                let value = abi::Timespec::from_ns(ns);
                unsafe {
                    (call.args[1] as *mut abi::Timespec).write(value);
                }
                0
            }
            Step::Read(fd, data) => {
                assert_eq!(call.nr, abi::NR_READ);
                assert_eq!(call.args[0], fd as u64);
                assert!(data.len() <= call.args[2] as usize);
                unsafe {
                    std::ptr::copy_nonoverlapping(
                        data.as_ptr(),
                        call.args[1] as *mut u8,
                        data.len(),
                    );
                }
                data.len() as u64
            }
            Step::Write(fd, data, n) => {
                assert_eq!(call.nr, abi::NR_WRITE);
                assert_eq!(call.args[0], fd as u64);
                let actual = unsafe {
                    std::slice::from_raw_parts(call.args[1] as *const u8, call.args[2] as usize)
                };
                assert_eq!(actual, data);
                n as u64
            }
            Step::Poll(ready) => {
                assert_eq!(call.nr, abi::NR_PPOLL);
                let fds = unsafe {
                    std::slice::from_raw_parts_mut(
                        call.args[0] as *mut abi::PollFd,
                        call.args[1] as usize,
                    )
                };
                self.polled.push(fds.iter().map(|p| p.fd).collect());
                for (fd, flags) in &ready {
                    let entry = fds
                        .iter_mut()
                        .find(|p| p.fd == *fd)
                        .expect("missing poll fd");
                    entry.revents = *flags;
                }
                ready.len() as u64
            }
            Step::Wait(exit) => {
                assert_eq!(call.nr, abi::NR_WAITID);
                assert_eq!(call.args[0], 3);
                assert_eq!(call.args[3], 5);
                if let Some(exit) = exit {
                    let out = unsafe { &mut *(call.args[2] as *mut abi::SigInfo) };
                    out.bytes[..4].copy_from_slice(&17i32.to_le_bytes());
                    out.bytes[8..12].copy_from_slice(&exit.code.to_le_bytes());
                    out.bytes[16..20].copy_from_slice(&exit.pid.to_le_bytes());
                    out.bytes[20..24].copy_from_slice(&exit.uid.to_le_bytes());
                    out.bytes[24..28].copy_from_slice(&exit.status.to_le_bytes());
                }
                0
            }
            Step::Notification(n) => {
                assert_eq!(call.nr, abi::NR_IOCTL);
                assert_eq!(call.args[1], abi::SECCOMP_IOCTL_NOTIF_RECV);
                let mut bytes = [0; 80];
                bytes[..8].copy_from_slice(&n.id.to_le_bytes());
                bytes[8..12].copy_from_slice(&n.pid.to_le_bytes());
                bytes[12..16].copy_from_slice(&n.flags.to_le_bytes());
                bytes[16..].copy_from_slice(&n.data.bytes());
                unsafe {
                    std::ptr::copy_nonoverlapping(bytes.as_ptr(), call.args[2] as *mut u8, 80);
                }
                0
            }
            Step::Listener(fd) => {
                assert_eq!(call.nr, abi::NR_RECVMSG);
                let msg = unsafe { &mut *(call.args[1] as *mut abi::MsgHdr) };
                let iov = unsafe { &*(msg.iov as *const abi::Iovec) };
                unsafe {
                    std::ptr::copy_nonoverlapping(
                        abi::LISTENER_RECORD.as_ptr(),
                        iov.base as *mut u8,
                        8,
                    );
                    std::ptr::copy_nonoverlapping(
                        abi::Ancillary::rights(fd).bytes.as_ptr(),
                        msg.control as *mut u8,
                        24,
                    );
                }
                msg.controllen = 24;
                msg.flags = 0;
                8
            }
            Step::Stat(fd, mode, ino) => {
                assert_eq!(call.nr, abi::NR_FSTAT);
                assert_eq!(call.args[0], fd as u64);
                unsafe {
                    (call.args[1] as *mut abi::Stat).write(abi::Stat {
                        dev: 1,
                        ino,
                        mode,
                        ..abi::Stat::default()
                    });
                }
                0
            }
            Step::Clone(pid, fd) => {
                assert_eq!(call.nr, abi::NR_CLONE3);
                let args = unsafe { &*(call.args[0] as *const abi::CloneArgs) };
                unsafe {
                    (args.pidfd as *mut i32).write(fd);
                }
                pid as u64
            }
            Step::AltStack => {
                assert_eq!(call.nr, abi::NR_SIGALTSTACK);
                unsafe {
                    (call.args[1] as *mut abi::AltStack).write(abi::AltStack {
                        flags: 2,
                        ..abi::AltStack::default()
                    });
                }
                0
            }
            Step::Mask => {
                assert_eq!(call.nr, abi::NR_RT_SIGPROCMASK);
                unsafe {
                    (call.args[2] as *mut u64).write(abi::BLOCKED_SIGNALS);
                }
                0
            }
            Step::Directory(fds) => {
                assert_eq!(call.nr, 61);
                let mut bytes = Vec::new();
                for fd in fds {
                    let name = fd.to_string();
                    let len = (19 + name.len() + 1 + 7) & !7;
                    let start = bytes.len();
                    bytes.resize(start + len, 0);
                    bytes[start + 16..start + 18].copy_from_slice(&(len as u16).to_le_bytes());
                    bytes[start + 19..start + 19 + name.len()].copy_from_slice(name.as_bytes());
                }
                assert!(bytes.len() <= call.args[2] as usize);
                unsafe {
                    std::ptr::copy_nonoverlapping(
                        bytes.as_ptr(),
                        call.args[1] as *mut u8,
                        bytes.len(),
                    );
                }
                bytes.len() as u64
            }
            Step::InstallSupervisor => {
                assert_eq!(call.nr, abi::NR_SECCOMP);
                assert_eq!(call.args[1], 0);
                let p = unsafe { &*(call.args[2] as *const abi::SockFprog) };
                let filters = unsafe {
                    std::slice::from_raw_parts(p.filter as *const abi::SockFilter, p.len as usize)
                };
                let expected =
                    radishaxiom_solver_supervision_core::policy::SupervisorRuntimePolicy::new(
                        radishaxiom_solver_supervision_core::policy::BOOTSTRAP_SUPERVISOR_ROLES,
                    )
                    .unwrap()
                    .compile();
                let mut bytes = Vec::new();
                for f in filters {
                    bytes.extend_from_slice(&f.code.to_le_bytes());
                    bytes.extend_from_slice(&[f.jt, f.jf]);
                    bytes.extend_from_slice(&f.k.to_le_bytes());
                }
                assert_eq!(bytes, expected.bytes());
                self.supervisor_policy = true;
                0
            }
            Step::Scalar(nr, first, result) => {
                assert_eq!(call.nr, nr);
                if let Some(first) = first {
                    assert_eq!(call.args[0], first)
                }
                result
            }
            Step::Pread(fd, offset, data) => {
                assert_eq!(call.nr, abi::NR_PREAD64);
                assert_eq!(call.args[0], fd as u64);
                assert_eq!(call.args[3], offset);
                assert!(data.len() <= call.args[2] as usize);
                unsafe {
                    std::ptr::copy_nonoverlapping(
                        data.as_ptr(),
                        call.args[1] as *mut u8,
                        data.len(),
                    );
                }
                data.len() as u64
            }
        }
    }
}
pub(crate) fn owned(raw: i32) -> OwnedFd {
    // SAFETY: scripted fixtures uniquely assign this descriptor to one owner;
    // no host descriptor is accessed and the test script owns the close event.
    unsafe { OwnedFd::from_raw(raw) }
}
