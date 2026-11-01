//! Finite in-memory syscall scripts; no host descriptors, process or signal APIs.
use super::*;
use crate::syscall::ErrorKind;
use std::collections::{BTreeMap, VecDeque};
use std::panic::{AssertUnwindSafe, catch_unwind};

fn errno(n: u64) -> u64 {
    0u64.wrapping_sub(n)
}
fn exit(pid: u32, code: i32, status: i32) -> ChildExit {
    ChildExit {
        pid,
        uid: 65532,
        code,
        status,
    }
}
#[derive(Debug)]
enum Wait {
    Exit(ChildExit),
    Running,
    Empty,
    Error(u64),
    Advance(u64),
}
#[derive(Debug)]
enum Fd {
    Stream,
    Inherited,
    Pid(u32),
    Proc(VecDeque<u8>),
}
struct Model {
    calls: Vec<Call>,
    fds: BTreeMap<i32, Fd>,
    waits: VecDeque<Wait>,
    lists: VecDeque<Vec<u8>>,
    pending: VecDeque<u32>,
    now: u64,
    mask: u64,
    flags: u64,
    pid: u64,
    uid: u64,
    clone_result: u64,
    clone_count: usize,
    kills: Vec<u32>,
    kill_result: u64,
    fail_nr: Option<(i32, u64)>,
    fail_pidfd_pid: Option<u32>,
    proc_kind: i64,
    proc_read_chunk: usize,
    signal_errno: Option<u64>,
    clock_values: VecDeque<u64>,
}
impl Model {
    fn new(waits: impl IntoIterator<Item = Wait>, lists: &[&[u8]]) -> Self {
        Self {
            calls: Vec::new(),
            fds: [
                (0, Fd::Stream),
                (1, Fd::Stream),
                (2, Fd::Stream),
                (40, Fd::Inherited),
            ]
            .into(),
            waits: waits.into_iter().collect(),
            lists: lists.iter().map(|s| s.to_vec()).collect(),
            pending: VecDeque::new(),
            now: 0,
            mask: 0,
            flags: 1,
            pid: 1,
            uid: 65532,
            clone_result: 42,
            clone_count: 0,
            kills: Vec::new(),
            kill_result: 0,
            fail_nr: None,
            fail_pidfd_pid: None,
            proc_kind: 0x9fa0,
            proc_read_chunk: usize::MAX,
            signal_errno: None,
            clock_values: VecDeque::new(),
        }
    }
    fn fd(&mut self, value: Fd) -> u64 {
        let fd = (3..64).find(|n| !self.fds.contains_key(n)).unwrap();
        self.fds.insert(fd, value);
        fd as u64
    }
    fn done(&self) {
        assert!(self.waits.is_empty(), "unused waits: {:?}", self.waits);
        assert!(self.lists.is_empty(), "unused snapshots: {:?}", self.lists);
        assert_eq!(self.fds.len(), 3, "leaked synthetic descriptor");
    }
}
// SAFETY: every pointer is used synchronously for the exact documented extent.
// Model has no native backend/fallback and cannot access a real OS descriptor.
unsafe impl Kernel for Model {
    unsafe fn invoke(&mut self, call: Call) -> u64 {
        self.calls.push(call);
        if let Some((nr, result)) = self.fail_nr
            && nr == call.nr
            && (nr != NR_PIDFD_OPEN
                || self
                    .fail_pidfd_pid
                    .is_none_or(|pid| pid as u64 == call.args[0]))
        {
            return result;
        }
        match call.nr {
            NR_GETPID => self.pid,
            NR_GETTID => 1,
            NR_GETPPID => 0,
            NR_GETUID | NR_GETEUID | NR_GETGID | NR_GETEGID => self.uid,
            NR_GETGROUPS => {
                assert_eq!(call.args, [0; 6]);
                0
            }
            NR_PRCTL => {
                assert_eq!(call.args, [PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0, 0]);
                1
            }
            NR_CLOCK_GETTIME => {
                assert_eq!(call.args[0], CLOCK_BOOTTIME);
                let now = self.clock_values.pop_front().unwrap_or(self.now);
                // SAFETY: clock wrapper supplies exactly one exclusive Timespec.
                unsafe {
                    (call.args[1] as *mut Timespec).write(Timespec::from_ns(now));
                }
                0
            }
            NR_CLOSE_RANGE => {
                assert_eq!(call.args, [3, u32::MAX as u64, 0, 0, 0, 0]);
                self.fds.retain(|k, _| *k < 3);
                0
            }
            NR_FSTAT => {
                assert!(self.fds.contains_key(&(call.args[0] as i32)));
                // SAFETY: one live exclusive fixed-layout Stat.
                unsafe {
                    (*(call.args[1] as *mut Stat)).mode =
                        if call.args[0] == 2 { 0x1000 } else { 0x8000 };
                }
                0
            }
            NR_FSTATFS => {
                assert!(matches!(
                    self.fds.get(&(call.args[0] as i32)),
                    Some(Fd::Proc(_))
                ));
                // SAFETY: one live exclusive fixed-layout StatFs.
                unsafe {
                    (*(call.args[1] as *mut StatFs)).kind = self.proc_kind;
                }
                0
            }
            NR_FCNTL => {
                assert_eq!(call.args[0], 2);
                match call.args[1] {
                    F_GETFL => self.flags,
                    F_SETFL => {
                        self.flags = call.args[2];
                        0
                    }
                    _ => panic!("unexpected fcntl"),
                }
            }
            NR_RT_SIGPROCMASK => {
                assert_eq!(call.args[0], SIG_SETMASK);
                assert_eq!(call.args[3], 8);
                if call.args[1] != 0 {
                    // SAFETY: exactly one initialized immutable u64 mask.
                    self.mask = unsafe { *(call.args[1] as *const u64) };
                }
                if call.args[2] != 0 {
                    // SAFETY: exactly one exclusive u64 output.
                    unsafe {
                        (call.args[2] as *mut u64).write(self.mask);
                    }
                }
                0
            }
            NR_RT_SIGACTION => {
                assert_eq!(call.args[3], 8);
                assert!(![9, 19].contains(&call.args[0]));
                if call.args[1] != 0 {
                    // SAFETY: one live initialized SigAction input.
                    let a = unsafe { &*(call.args[1] as *const SigAction) };
                    assert_eq!((a.handler, a.flags, a.restorer, a.mask), (0, 0, 0, 0));
                }
                0
            }
            NR_SIGALTSTACK => {
                if call.args[1] != 0 {
                    // SAFETY: exactly one exclusive AltStack.
                    unsafe {
                        (*(call.args[1] as *mut AltStack)).flags = 2;
                    }
                }
                0
            }
            NR_OPENAT => {
                // SAFETY: wrapper's static NUL-terminated proc path.
                assert_eq!(
                    unsafe { CStr::from_ptr(call.args[1] as *const i8) },
                    c"/proc/self/task/1/children"
                );
                assert_eq!(call.args[2], O_CLOEXEC | O_NOFOLLOW);
                let list = self
                    .lists
                    .pop_front()
                    .expect("unexpected children snapshot");
                self.fd(Fd::Proc(list.into()))
            }
            NR_READ => {
                let Some(Fd::Proc(bytes)) = self.fds.get_mut(&(call.args[0] as i32)) else {
                    panic!("not proc fd")
                };
                let n = bytes
                    .len()
                    .min(call.args[2] as usize)
                    .min(self.proc_read_chunk);
                for i in 0..n {
                    // SAFETY: n never exceeds wrapper's exclusive slice length.
                    unsafe {
                        (call.args[1] as *mut u8)
                            .add(i)
                            .write(bytes.pop_front().unwrap());
                    }
                }
                n as u64
            }
            NR_CLOSE => {
                assert!(self.fds.remove(&(call.args[0] as i32)).is_some());
                0
            }
            NR_CHANNEL_CLONE => {
                self.clone_count += 1;
                assert_eq!(call.args, [SIGCHLD, 0, 0, 0, 0, 0]);
                assert_eq!(self.mask, BLOCKED_SIGNALS);
                self.clone_result
            }
            NR_PIDFD_OPEN => {
                assert!(call.args[0] > 1);
                assert_eq!(&call.args[1..], &[0; 5]);
                self.fd(Fd::Pid(call.args[0] as u32))
            }
            NR_PIDFD_SEND_SIGNAL => {
                assert_eq!(&call.args[1..], &[9, 0, 0, 0, 0]);
                let Some(Fd::Pid(pid)) = self.fds.get(&(call.args[0] as i32)) else {
                    panic!("not pidfd")
                };
                self.kills.push(*pid);
                self.kill_result
            }
            NR_WAITID => {
                assert_eq!((call.args[0], call.args[1], call.args[3]), (0, 0, 5));
                match self.waits.pop_front().expect("unexpected wait") {
                    Wait::Exit(e) => {
                        // SAFETY: one exclusive initialized SigInfo output.
                        let out = unsafe { &mut *(call.args[2] as *mut SigInfo) };
                        out.bytes[..4].copy_from_slice(&17i32.to_le_bytes());
                        out.bytes[8..12].copy_from_slice(&e.code.to_le_bytes());
                        out.bytes[16..20].copy_from_slice(&e.pid.to_le_bytes());
                        out.bytes[20..24].copy_from_slice(&e.uid.to_le_bytes());
                        out.bytes[24..28].copy_from_slice(&e.status.to_le_bytes());
                        0
                    }
                    Wait::Running => 0,
                    Wait::Empty => errno(10),
                    Wait::Error(e) => errno(e),
                    Wait::Advance(t) => {
                        self.now = t;
                        0
                    }
                }
            }
            NR_RT_SIGTIMEDWAIT => {
                assert_eq!(call.args[3], 8);
                // SAFETY: one immutable u64 mask and Timespec.
                assert_eq!(unsafe { *(call.args[0] as *const u64) }, BLOCKED_SIGNALS);
                let timeout = unsafe { *(call.args[2] as *const Timespec) }.ns().unwrap();
                if let Some(e) = self.signal_errno.take() {
                    return errno(e);
                }
                if let Some(sig) = self.pending.pop_front() {
                    // SAFETY: exactly the signum field of exclusive SigInfo.
                    unsafe {
                        (call.args[1] as *mut i32).write(sig as i32);
                    }
                    sig as u64
                } else {
                    self.now += timeout;
                    errno(11)
                }
            }
            _ => panic!("unlisted syscall {}", call.nr),
        }
    }
}
fn run_model(model: Model) -> (Report, Model) {
    let mut linux = Linux::new(model);
    // SAFETY: explicit in-memory backend only; no actual signals/FDs/clone occur.
    let report = unsafe { run(&mut linux, c"printf synthetic") };
    (report, linux.kernel)
}

#[test]
fn exact_main_exit_and_echild_are_both_required() {
    let (r, m) = run_model(Model::new(
        [Wait::Exit(exit(42, 1, 7)), Wait::Empty],
        &[b"", b""],
    ));
    assert_eq!(r.exit_code(), 7);
    assert_eq!(r.main_exit, Some(exit(42, 1, 7)));
    assert!(r.no_children);
    assert!(r.cause.is_none());
    assert_eq!(m.clone_count, 1);
    assert!(m.kills.is_empty());
    m.done();
}
#[test]
fn signalled_main_status_is_not_changed_into_success() {
    let (r, m) = run_model(Model::new(
        [Wait::Exit(exit(42, 3, 11)), Wait::Empty],
        &[b"", b""],
    ));
    assert_eq!(r.exit_code(), 139);
    assert_eq!(r.main_exit.unwrap().code, 3);
    m.done();
}
#[test]
fn deadline_never_renews_and_kills_exact_pidfd_once() {
    let (r, m) = run_model(Model::new(
        [
            Wait::Advance(WORK_NS),
            Wait::Exit(exit(42, 2, 9)),
            Wait::Empty,
        ],
        &[b"", b"42 "],
    ));
    assert_eq!(r.cause, Some(Cause::WorkDeadline));
    assert_eq!(r.exit_code(), 124);
    assert!(r.no_children);
    assert_eq!(m.kills, vec![42]);
    assert_eq!(r.signals.len(), 1);
    m.done();
}
#[test]
fn cancellation_precedes_simultaneous_success_and_preserves_exit() {
    for signal in [1, 2, 3, 15] {
        let mut m = Model::new([Wait::Exit(exit(42, 1, 0)), Wait::Empty], &[b"", b"42 "]);
        m.pending.push_back(signal);
        let (r, m) = run_model(m);
        assert_eq!(r.cause, Some(Cause::Cancelled(signal)));
        assert_eq!(r.exit_code(), 128 + signal as u8);
        assert_eq!(r.main_exit, Some(exit(42, 1, 0)));
        assert_eq!(m.kills, vec![42]);
        m.done();
    }
}
#[test]
fn adopted_orphan_is_pidfd_bound_without_group_or_namespace_broadcast() {
    let (r, m) = run_model(Model::new(
        [
            Wait::Exit(exit(42, 1, 0)),
            Wait::Exit(exit(77, 2, 9)),
            Wait::Empty,
        ],
        &[b"", b"77 "],
    ));
    assert_eq!(r.cause, Some(Cause::OrphanedChild));
    assert_eq!(r.exit_code(), 125);
    assert_eq!(m.kills, vec![77]);
    assert!(r.no_children);
    assert_eq!(r.exits.len(), 2);
    assert_eq!(m.calls.iter().filter(|c| c.nr == NR_PIDFD_OPEN).count(), 2);
    m.done();
}
#[test]
fn new_orphans_are_rescanned_after_parent_reap() {
    let mut m = Model::new(
        [
            Wait::Exit(exit(42, 1, 0)),
            Wait::Exit(exit(77, 2, 9)),
            Wait::Running,
            Wait::Exit(exit(88, 2, 9)),
            Wait::Empty,
        ],
        &[b"", b"77 ", b"88 "],
    );
    m.pending.push_back(17);
    let (r, m) = run_model(m);
    assert_eq!(m.kills, vec![77, 88]);
    assert!(r.no_children);
    m.done();
}
#[test]
fn echild_without_main_exit_is_failure_not_fake_reaping() {
    let (r, m) = run_model(Model::new([Wait::Empty, Wait::Empty], &[b"", b"42 "]));
    assert_eq!(r.exit_code(), 125);
    assert!(r.main_exit.is_none());
    assert!(r.no_children);
    m.done();
}
#[test]
fn failed_kill_and_wait_keep_first_failure_and_unknown_children() {
    let mut m = Model::new([Wait::Error(4)], &[b"", b"42 "]);
    m.pending.push_back(15);
    m.kill_result = errno(1);
    let (r, m) = run_model(m);
    assert_eq!(r.cause, Some(Cause::Cancelled(15)));
    assert_eq!(
        r.errors.iter().map(|e| e.errno()).collect::<Vec<_>>(),
        vec![Some(1), Some(4)]
    );
    assert!(!r.no_children);
    assert!(r.main_exit.is_none());
    m.done();
}
#[test]
fn esrch_is_retained_and_does_not_establish_reap() {
    let mut m = Model::new([Wait::Error(4)], &[b"", b"42 "]);
    m.pending.push_back(2);
    m.kill_result = errno(3);
    let (r, m) = run_model(m);
    assert_eq!(r.signals[0].result.unwrap_err().errno(), Some(3));
    assert!(!r.no_children);
    assert!(r.main_exit.is_none());
    m.done();
}
#[test]
fn wrong_identity_or_existing_child_never_clones_or_signals() {
    let mut m = Model::new([], &[]);
    m.pid = 2;
    let (r, m) = run_model(m);
    assert!(!r.clone_attempted);
    assert_eq!(m.clone_count, 0);
    assert_eq!(m.fds.len(), 4);
    let mut m = Model::new([], &[]);
    m.uid = 0;
    let (r, m) = run_model(m);
    assert!(!r.clone_attempted);
    assert_eq!(m.clone_count, 0);
    let (r, m) = run_model(Model::new([], &[b"99 "]));
    assert!(!r.clone_attempted);
    assert!(m.kills.is_empty());
    m.done();
}
#[test]
fn unsupported_clone_is_never_retried_or_replaced() {
    for e in [4, 11, 38] {
        let mut m = Model::new([], &[b""]);
        m.clone_result = errno(e);
        let (r, m) = run_model(m);
        assert_eq!(m.clone_count, 1);
        assert!(r.child_pid.is_none());
        assert_eq!(r.errors[0].errno(), Some(e as u16));
        assert!(!r.no_children);
        m.done();
    }
}
#[test]
fn wrong_procfs_or_bad_children_fail_before_clone() {
    let mut m = Model::new([], &[b""]);
    m.proc_kind = 0x123;
    let (r, m) = run_model(m);
    assert!(!r.clone_attempted);
    m.done();
    for data in [
        b"1 ".as_slice(),
        b"42 42 ",
        b"+42 ",
        b"/42",
        b"42\n",
        b"2147483648 ",
    ] {
        let (r, m) = run_model(Model::new([], &[data]));
        assert!(!r.clone_attempted);
        m.done();
    }
}
#[test]
fn bounded_parser_rejects_nplusone_duplicate_and_noncanonical_pids() {
    assert_eq!(parse_children(b"2 17 2147483647 ").unwrap().len, 3);
    for b in [b"01 ".as_slice(), b"0 ", b"1 ", b"2 2 ", b"\t2 "] {
        assert!(parse_children(b).is_err());
    }
    assert!(parse_children(&[b' '; 257]).is_err());
    let too_many = (2..18).map(|p| format!("{p} ")).collect::<String>();
    assert!(parse_children(too_many.as_bytes()).is_err());
}
#[test]
fn short_proc_reads_are_joined_without_truncation_acceptance() {
    let mut m = Model::new(
        [
            Wait::Exit(exit(42, 1, 0)),
            Wait::Exit(exit(777, 2, 9)),
            Wait::Empty,
        ],
        &[b"", b"777 "],
    );
    m.proc_read_chunk = 1;
    let (r, m) = run_model(m);
    assert!(r.no_children);
    assert_eq!(m.kills, vec![777]);
    m.done();
}
#[test]
fn unexpected_signal_or_wait_eintr_remains_failure() {
    let mut m = Model::new([Wait::Exit(exit(42, 2, 9)), Wait::Empty], &[b"", b"42 "]);
    m.pending.push_back(10);
    let (r, m) = run_model(m);
    assert_eq!(r.cause, Some(Cause::UnexpectedSignal(10)));
    assert_eq!(r.exit_code(), 125);
    m.done();
    let mut m = Model::new([Wait::Exit(exit(42, 2, 9)), Wait::Empty], &[b"", b"42 "]);
    m.signal_errno = Some(4);
    let (r, m) = run_model(m);
    assert_eq!(r.errors[0].errno(), Some(4));
    m.done();
}
#[test]
fn final_deadline_and_rollback_cannot_claim_no_children() {
    for time in [TOTAL_NS, 0] {
        let mut m = Model::new(
            [Wait::Advance(WORK_NS), Wait::Advance(time)],
            &[b"", b"42 "],
        );
        // First wait enters cleanup; second leaves a live child and advances or
        // rolls back its clock. No new relative deadline may be manufactured.
        m.pending.push_back(17);
        let (r, m) = run_model(m);
        assert!(!r.no_children);
        assert_eq!(r.cause, Some(Cause::WorkDeadline));
        m.done();
    }
}
#[test]
fn budget_overflow_and_record_overflow_are_terminal() {
    assert!(Budget::new(u64::MAX).is_err());
    let mut r = Report::new();
    r.child_pid = Some(42);
    for i in 0..=EVENT_LIMIT {
        r.exited(exit(100 + i as u32, 1, 0));
    }
    assert_eq!(r.exits.len(), EVENT_LIMIT);
    assert!(r.observations_overflowed);
    assert_eq!(r.exit_code(), 125);
}

struct TailModel {
    calls: Vec<i32>,
    record: Vec<u8>,
    fail: Option<i32>,
}
// SAFETY: only synchronous access to exact child-tail buffers; exit uses a
// test-only panic to escape -> !, never a real syscall or production callback.
unsafe impl Kernel for TailModel {
    unsafe fn invoke(&mut self, c: Call) -> u64 {
        self.calls.push(c.nr);
        if self.fail == Some(c.nr) {
            return errno(5);
        }
        match c.nr {
            NR_GETPID => 42,
            NR_GETPPID => 1,
            NR_CLOSE_RANGE => {
                assert_eq!(c.args, [3, u32::MAX as u64, 0, 0, 0, 0]);
                0
            }
            NR_RT_SIGPROCMASK => {
                // SAFETY: tail supplies exactly one immutable u64 mask.
                assert_eq!(unsafe { *(c.args[1] as *const u64) }, 0);
                0
            }
            NR_CLOCK_GETTIME => {
                // SAFETY: one exclusive initialized Timespec.
                unsafe {
                    (c.args[1] as *mut Timespec).write(Timespec::from_ns(1));
                }
                0
            }
            NR_EXECVEAT => {
                assert_eq!(c.args[0], (-100i64) as u64);
                assert_eq!(c.args[4], 0);
                // SAFETY: frozen static pathname and terminated fixed vectors.
                assert_eq!(
                    unsafe { CStr::from_ptr(c.args[1] as *const i8) },
                    c"/bin/busybox"
                );
                let argv = unsafe { std::slice::from_raw_parts(c.args[2] as *const u64, 5) };
                let env = unsafe { std::slice::from_raw_parts(c.args[3] as *const u64, 5) };
                assert_eq!(argv[4], 0);
                assert_eq!(env[4], 0);
                let strings = |v: &[u64]| {
                    v.iter()
                        .map(|p| {
                            unsafe { CStr::from_ptr(*p as *const i8) }
                                .to_bytes()
                                .to_vec()
                        })
                        .collect::<Vec<_>>()
                };
                assert_eq!(
                    strings(&argv[..4]),
                    vec![
                        b"busybox".to_vec(),
                        b"sh".to_vec(),
                        b"-c".to_vec(),
                        b"printf synthetic".to_vec()
                    ]
                );
                assert_eq!(
                    strings(&env[1..4]),
                    vec![b"LANG=C".to_vec(), b"LC_ALL=C".to_vec(), b"TZ=UTC".to_vec()]
                );
                assert!(strings(&env[..1])[0].starts_with(b"PATH="));
                errno(2)
            }
            NR_WRITE => {
                assert_eq!((c.args[0], c.args[2]), (2, 16));
                // SAFETY: tail provides exactly sixteen initialized bytes.
                self.record =
                    unsafe { std::slice::from_raw_parts(c.args[1] as *const u8, 16) }.to_vec();
                16
            }
            NR_EXIT_GROUP => {
                assert_eq!(c.args[0], 126);
                panic!("synthetic exit")
            }
            _ => panic!("unexpected child call"),
        }
    }
}
#[test]
fn child_uses_fixed_exec_closed_environment_and_raw_failure_record() {
    let mut linux = Linux::new(TailModel {
        calls: Vec::new(),
        record: Vec::new(),
        fail: None,
    });
    // Clone model selects child once; tail pointers are the actual pre-frozen
    // vectors from clone_collector, not a parallel hand-assembled argv fixture.
    struct ChildBranch(TailModel);
    // SAFETY: delegates exact writes to TailModel and selects scripted child.
    unsafe impl Kernel for ChildBranch {
        unsafe fn invoke(&mut self, c: Call) -> u64 {
            if c.nr == NR_CHANNEL_CLONE {
                0
            } else {
                unsafe { self.0.invoke(c) }
            }
        }
    }
    let mut child = Linux::new(ChildBranch(linux.kernel));
    assert!(
        catch_unwind(AssertUnwindSafe(|| clone_collector(
            &mut child,
            c"printf synthetic",
            WORK_NS
        )))
        .is_err()
    );
    linux.kernel = child.kernel.0;
    assert_eq!(&linux.kernel.record[..4], b"AXCI");
    assert_eq!(
        i32::from_le_bytes(linux.kernel.record[4..8].try_into().unwrap()),
        NR_EXECVEAT
    );
    assert_eq!(
        u64::from_le_bytes(linux.kernel.record[8..].try_into().unwrap()),
        errno(2)
    );
    assert_eq!(
        linux
            .kernel
            .calls
            .iter()
            .filter(|n| **n == NR_EXECVEAT)
            .count(),
        1
    );
}
#[test]
fn child_setup_failure_never_execs_or_returns() {
    let argv = [0u64; 5];
    let input = Tail {
        argv: argv.as_ptr() as u64,
        env: argv.as_ptr() as u64,
        work_end: WORK_NS,
    };
    let mut k = TailModel {
        calls: Vec::new(),
        record: Vec::new(),
        fail: Some(NR_CLOSE_RANGE),
    };
    // SAFETY: synthetic backend aborts before reading fake argv/env pointers.
    assert!(catch_unwind(AssertUnwindSafe(|| unsafe { tail(&mut k, &input) })).is_err());
    assert!(!k.calls.contains(&NR_EXECVEAT));
    assert_eq!(
        i32::from_le_bytes(k.record[4..8].try_into().unwrap()),
        NR_CLOSE_RANGE
    );
    assert_eq!(
        u64::from_le_bytes(k.record[8..].try_into().unwrap()),
        errno(5)
    );
}
#[test]
fn wrong_signal_return_and_pidfd_shape_are_rejected() {
    let mut m = Model::new([], &[]);
    m.pending.push_back(9);
    let mut linux = Linux::new(m);
    assert_eq!(
        linux.channel_signal(0).unwrap_err().kind,
        ErrorKind::InvalidReturn
    );
    assert!(linux.channel_pidfd(1).is_err());
    assert!(linux.channel_pidfd(u32::MAX).is_err());
}

#[test]
fn recycled_main_number_gets_a_new_pidfd_and_cannot_replace_main_status() {
    let (r, m) = run_model(Model::new(
        [
            Wait::Exit(exit(42, 1, 7)),
            Wait::Exit(exit(42, 2, 9)),
            Wait::Empty,
        ],
        &[b"", b"42 "],
    ));
    assert_eq!(r.main_exit, Some(exit(42, 1, 7)));
    assert_eq!(r.exits.len(), 2);
    let opened = m
        .calls
        .iter()
        .filter(|c| c.nr == NR_PIDFD_OPEN)
        .collect::<Vec<_>>();
    let killed = m
        .calls
        .iter()
        .filter(|c| c.nr == NR_PIDFD_SEND_SIGNAL)
        .collect::<Vec<_>>();
    assert_eq!(opened.len(), 2);
    assert_eq!(opened[1].args[0], 42);
    assert_ne!(
        killed[0].args[0], 3,
        "old main pidfd must never target a recycled PID"
    );
    assert_eq!(r.cause, Some(Cause::OrphanedChild));
    m.done();
}
#[test]
fn orphan_pidfd_failure_never_falls_back_to_numeric_or_group_kill() {
    let mut m = Model::new([Wait::Exit(exit(42, 1, 0)), Wait::Error(4)], &[b"", b"77 "]);
    m.fail_nr = Some((NR_PIDFD_OPEN, errno(3)));
    m.fail_pidfd_pid = Some(77);
    let (r, m) = run_model(m);
    assert!(!r.no_children);
    assert!(m.kills.is_empty());
    assert_eq!(
        r.errors.iter().map(|e| e.errno()).collect::<Vec<_>>(),
        vec![Some(3), Some(4)]
    );
    m.done();
}
#[test]
fn clock_rollback_across_signal_freeze_is_not_hidden() {
    let mut m = Model::new([], &[]);
    m.now = 1;
    m.clock_values = [10, 1].into();
    let (r, m) = run_model(m);
    assert!(!r.clone_attempted);
    assert_eq!(r.errors[0].operation, "channel-init-clock-rollback");
    m.done();
}
#[test]
fn initial_nonblocking_stderr_and_no_new_privs_are_mandatory() {
    for (nr, result) in [(NR_FCNTL, errno(1)), (NR_PRCTL, 0), (NR_GETGROUPS, 1)] {
        let mut m = Model::new([], &[]);
        m.fail_nr = Some((nr, result));
        let (r, m) = run_model(m);
        assert!(!r.clone_attempted);
        assert_eq!(m.clone_count, 0);
        assert_eq!(r.exit_code(), 125);
    }
}
#[test]
fn oversized_or_short_child_listing_cannot_be_accepted() {
    let large = vec![b' '; CHILDREN_BYTES + 1];
    let (r, m) = run_model(Model::new([], &[&large]));
    assert!(!r.clone_attempted);
    m.done();
}
#[test]
fn child_error_write_failure_still_raw_exits_without_retry() {
    let input = Tail {
        argv: 0,
        env: 0,
        work_end: WORK_NS,
    };
    let mut k = TailModel {
        calls: Vec::new(),
        record: Vec::new(),
        fail: Some(NR_WRITE),
    };
    // Setup fails before fake argv can be touched; write is allowed to fail.
    k.fail = Some(NR_GETPPID);
    assert!(catch_unwind(AssertUnwindSafe(|| unsafe { tail(&mut k, &input) })).is_err());
    assert_eq!(k.calls.iter().filter(|n| **n == NR_WRITE).count(), 1);
    let mut k = TailModel {
        calls: Vec::new(),
        record: Vec::new(),
        fail: Some(NR_WRITE),
    };
    assert!(
        catch_unwind(AssertUnwindSafe(|| tail_error(
            &mut k,
            NR_EXECVEAT,
            errno(2)
        )))
        .is_err()
    );
    assert_eq!(k.calls, vec![NR_WRITE, NR_EXIT_GROUP]);
    assert!(k.record.is_empty());
}

#[test]
fn child_pidfd_acquisition_failure_retains_known_child_without_retry() {
    let mut m = Model::new([], &[b""]);
    m.fail_nr = Some((NR_PIDFD_OPEN, errno(1)));
    let (r, m) = run_model(m);
    assert_eq!(r.child_pid, Some(42));
    assert!(!r.no_children);
    assert_eq!(r.errors[0].errno(), Some(1));
    assert_eq!(m.clone_count, 1);
    assert!(m.kills.is_empty());
    assert_eq!(m.calls.iter().filter(|c| c.nr == NR_PIDFD_OPEN).count(), 1);
    m.done();
}
#[test]
fn incomplete_children_snapshot_cannot_replace_echild() {
    let (r, m) = run_model(Model::new(
        [
            Wait::Exit(exit(42, 1, 0)),
            Wait::Running,
            Wait::Exit(exit(77, 2, 9)),
            Wait::Empty,
        ],
        &[b"", b"", b"77 "],
    ));
    assert_eq!(m.kills, vec![77]);
    assert!(r.no_children);
    assert_eq!(r.exits.len(), 2);
    m.done();
}
