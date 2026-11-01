//! Private PID 1 supervision, shared by the single framed diagnostic entry.
use crate::{
    abi::*,
    fd::OwnedFd,
    syscall::{Call, Error, Kernel, Linux, Result, WaitAny, decode},
};
use std::ffi::CStr;

use crate::channel_io::Io;
use crate::channel_profile::{CHILD_LIMIT, CLEANUP_NS, EVENT_LIMIT, TOTAL_NS, WORK_NS};
const SECOND: u64 = 1_000_000_000;
const CHILDREN_BYTES: usize = 256;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Cause {
    Kernel(Error),
    WorkDeadline,
    Cancelled(u32),
    UnexpectedSignal(u32),
    OrphanedChild,
    EventLimit,
    Capture,
    Transport,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct SignalFact {
    pub pid: u32,
    pub result: Result<()>,
}
#[derive(Debug)]
pub(crate) struct Report {
    pub cause: Option<Cause>,
    pub child_pid: Option<u32>,
    pub main_exit: Option<ChildExit>,
    pub exits: Vec<ChildExit>,
    pub signals: Vec<SignalFact>,
    pub errors: Vec<Error>,
    pub no_children: bool,
    pub clone_attempted: bool,
    pub observations_overflowed: bool,
}
impl Report {
    pub(super) fn new() -> Self {
        Self {
            cause: None,
            child_pid: None,
            main_exit: None,
            exits: Vec::with_capacity(EVENT_LIMIT),
            signals: Vec::with_capacity(EVENT_LIMIT),
            errors: Vec::with_capacity(EVENT_LIMIT),
            no_children: false,
            clone_attempted: false,
            observations_overflowed: false,
        }
    }
    pub(super) fn fail(&mut self, cause: Cause) {
        self.cause.get_or_insert(cause);
    }
    pub(super) fn error(&mut self, error: Error) {
        self.fail(Cause::Kernel(error));
        if self.errors.len() < EVENT_LIMIT {
            self.errors.push(error);
        } else {
            self.observations_overflowed = true;
        }
    }
    fn exited(&mut self, exit: ChildExit) {
        if self.main_exit.is_none() && self.child_pid == Some(exit.pid) {
            self.main_exit = Some(exit);
        } else {
            self.fail(Cause::OrphanedChild);
        }
        if self.exits.len() < EVENT_LIMIT {
            self.exits.push(exit);
        } else {
            self.observations_overflowed = true;
            self.fail(Cause::EventLimit);
        }
    }
    pub(crate) fn exit_code(&self) -> u8 {
        match self.cause {
            Some(Cause::WorkDeadline) => 124,
            Some(Cause::Cancelled(signal)) => 128 + signal as u8,
            Some(_) => 125,
            None if !self.no_children
                || !self.errors.is_empty()
                || self.observations_overflowed =>
            {
                125
            }
            None => match self.main_exit {
                Some(exit) if exit.code == 1 => exit.status as u8,
                Some(exit) => 128 + exit.status as u8,
                None => 125,
            },
        }
    }
}
pub(super) struct Budget {
    pub first: u64,
    pub last: u64,
    pub work: u64,
    pub end: u64,
    pub final_end: u64,
}
impl Budget {
    pub(super) fn new(start: u64) -> Result<Self> {
        Ok(Self {
            first: start,
            last: start,
            work: start
                .checked_add(WORK_NS)
                .ok_or(Error::invalid("channel-init-clock"))?,
            end: start
                .checked_add(CLEANUP_NS)
                .ok_or(Error::invalid("channel-init-clock"))?,
            final_end: start
                .checked_add(TOTAL_NS)
                .ok_or(Error::invalid("channel-init-clock"))?,
        })
    }
    pub(super) fn now<K: Kernel>(&mut self, linux: &mut Linux<K>) -> Result<u64> {
        let now = linux.boottime_ns()?;
        if now < self.last {
            return Err(Error::invalid("channel-init-clock-rollback"));
        }
        self.last = now;
        Ok(now)
    }
    pub(super) fn remaining<K: Kernel>(&mut self, linux: &mut Linux<K>, end: u64) -> Result<u64> {
        let now = self.now(linux)?;
        if now >= end {
            return Err(Error::invalid("channel-init-final-deadline"));
        }
        Ok(end - now)
    }
}

// Caller owns the sole t0 and transport before entering. The native caller is
// single-threaded PID 1 and must raw-exit after terminal export, never resume.
pub(super) fn run<K: Kernel>(
    linux: &mut Linux<K>,
    collector: &CStr,
    budget: &mut Budget,
    io: &mut Io,
) -> Report {
    let mut report = Report::new();
    let prepared = (|| {
        budget.remaining(linux, budget.work)?;
        if collector.is_empty() || collector.to_bytes().len() > 32768 {
            return Err(Error::invalid("channel-init-collector-size"));
        }
        linux.check_channel_identity()?;
        linux.channel_close_inherited()?;
        let frozen = linux.freeze_signals(budget.work)?;
        if frozen < budget.last {
            return Err(Error::invalid("channel-init-clock-rollback"));
        }
        budget.last = frozen;
        if children(linux, budget, &mut report, false)?.len != 0 {
            return Err(Error::invalid("channel-init-existing-children"));
        }
        if report.cause.is_some() {
            return Ok(());
        }
        budget.remaining(linux, budget.work)?;
        io.prepare(linux, &mut report)?;
        io.progress(linux, budget, &mut report, budget.work);
        budget.remaining(linux, budget.work)?;
        Ok(())
    })();
    if let Err(e) = prepared {
        if matches!(
            e.operation,
            "channel-init-final-deadline" | "signal-freeze-deadline"
        ) {
            report.fail(Cause::WorkDeadline);
        }
        report.error(e);
    }
    if report.cause.is_some() {
        return report;
    }
    report.clone_attempted = true;
    let pid = match clone_collector(linux, collector, budget.work, io.child_fds()) {
        Ok(pid) => pid,
        Err(e) => {
            report.error(e);
            return report;
        }
    };
    report.child_pid = Some(pid);
    io.close_child(linux, &mut report);
    // No reap or other mutation occurs before opening this exact unreaped
    // child. SIGCHLD is DFL without NOCLDWAIT and this is the sole reaper.
    let pidfd = match linux.channel_pidfd(pid) {
        Ok(fd) => fd,
        Err(e) => {
            report.error(e);
            // Preserve the known child and unknown cleanup. The dedicated
            // entry must raw-exit; never retry or signal a numeric PID instead.
            return report;
        }
    };
    let child = Child { pid, pidfd };
    monitor(linux, budget, &mut report, io);
    cleanup(linux, budget, &mut report, &child, io);
    close(linux, &mut report, child.pidfd);
    report
}

struct Child {
    pid: u32,
    pidfd: OwnedFd,
}
fn clone_collector<K: Kernel>(
    linux: &mut Linux<K>,
    collector: &CStr,
    work_end: u64,
    stdio: [i32; 3],
) -> Result<u32> {
    // All pointers are frozen before clone. Child inherits a private COW image,
    // calls no Rust runtime/allocator and never returns through these frames.
    let argv = [
        c"busybox".as_ptr() as u64,
        c"sh".as_ptr() as u64,
        c"-c".as_ptr() as u64,
        collector.as_ptr() as u64,
        0,
    ];
    let env = [
        c"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin".as_ptr() as u64,
        c"LANG=C".as_ptr() as u64,
        c"LC_ALL=C".as_ptr() as u64,
        c"TZ=UTC".as_ptr() as u64,
        0,
    ];
    let input = Tail {
        argv: argv.as_ptr() as u64,
        env: env.as_ptr() as u64,
        work_end,
        stdio,
    };
    // Fixed clone(SIGCHLD), not a runtime fallback from clone3. No shared VM,
    // files, threads, new namespace, output pointer or alternate stack. This
    // avoids requiring clone3's extra default-seccomp capability exception.
    // SAFETY: all arguments are scalar and stack=0 keeps this private COW frame.
    let raw = unsafe {
        linux.kernel.invoke(Call {
            nr: NR_CHANNEL_CLONE,
            args: [SIGCHLD, 0, 0, 0, 0, 0],
        })
    };
    if raw == 0 {
        // SAFETY: single clone child with private COW stack and frozen pointers.
        unsafe { tail(&mut linux.kernel, &input) }
    }
    let pid = decode("channel-init-clone", raw)?;
    if !(2..=i32::MAX as u64).contains(&pid) {
        return Err(Error::returned("channel-init-clone"));
    }
    Ok(pid as u32)
}

fn monitor<K: Kernel>(linux: &mut Linux<K>, budget: &mut Budget, report: &mut Report, io: &mut Io) {
    while report.cause.is_none() && report.main_exit.is_none() {
        match budget.now(linux) {
            Ok(now) if now < budget.work => {}
            Ok(_) => {
                report.fail(Cause::WorkDeadline);
                break;
            }
            Err(e) => {
                report.error(e);
                break;
            }
        }
        if let Err(e) = receive_signal(linux, report, 0) {
            report.error(e);
            break;
        }
        if report.cause.is_some() {
            break;
        }
        io.progress(linux, budget, report, budget.work);
        if report.cause.is_some() {
            break;
        }
        match linux.channel_wait_any() {
            Ok(WaitAny::Exited(exit)) => {
                report.exited(exit);
                continue;
            }
            Ok(WaitAny::NoChildren) => {
                report.error(Error::invalid("channel-init-missing-main-exit"));
                break;
            }
            Ok(WaitAny::Running) => {}
            Err(e) => {
                report.error(e);
                break;
            }
        }
        match budget.remaining(linux, budget.work) {
            Ok(left) => {
                if let Err(e) = io.wait(linux, report, left) {
                    report.error(e);
                }
            }
            Err(e) if e.operation == "channel-init-final-deadline" => {
                report.fail(Cause::WorkDeadline)
            }
            Err(e) => report.error(e),
        }
    }
}
pub(super) fn receive_signal<K: Kernel>(
    linux: &mut Linux<K>,
    report: &mut Report,
    timeout: u64,
) -> Result<()> {
    match linux.channel_signal(timeout)? {
        None | Some(17) => {}
        Some(signal @ (1 | 2 | 3 | 15)) => report.fail(Cause::Cancelled(signal)),
        Some(signal) => report.fail(Cause::UnexpectedSignal(signal)),
    }
    Ok(())
}

#[derive(Debug)]
struct Children {
    pids: [u32; CHILD_LIMIT],
    len: usize,
}
fn parse_children(bytes: &[u8]) -> Result<Children> {
    if bytes.len() > CHILDREN_BYTES || !bytes.iter().all(|b| b.is_ascii_digit() || *b == b' ') {
        return Err(Error::invalid("channel-init-children-format"));
    }
    let mut out = Children {
        pids: [0; CHILD_LIMIT],
        len: 0,
    };
    for word in bytes.split(|b| *b == b' ').filter(|w| !w.is_empty()) {
        if word.len() > 10 || word[0] == b'0' || out.len == CHILD_LIMIT {
            return Err(Error::invalid("channel-init-children-limit"));
        }
        let mut pid = 0u64;
        for digit in word {
            pid = pid * 10 + (digit - b'0') as u64;
        }
        if !(2..=i32::MAX as u64).contains(&pid) || out.pids[..out.len].contains(&(pid as u32)) {
            return Err(Error::invalid("channel-init-children-pid"));
        }
        out.pids[out.len] = pid as u32;
        out.len += 1;
    }
    Ok(out)
}
fn children<K: Kernel>(
    linux: &mut Linux<K>,
    budget: &mut Budget,
    report: &mut Report,
    finalizing: bool,
) -> Result<Children> {
    let end = if finalizing { budget.end } else { budget.work };
    budget.remaining(linux, end)?;
    let fd = linux.open_readonly(c"/proc/self/task/1/children")?;
    let result = (|| {
        if linux.fstatfs(fd.raw())?.kind != 0x9fa0 || linux.fstat(fd.raw())?.mode & 0xf000 != 0x8000
        {
            return Err(Error::invalid("channel-init-children-procfs"));
        }
        let mut bytes = [0u8; CHILDREN_BYTES + 1];
        let mut count = 0;
        for _ in 0..=CHILDREN_BYTES {
            budget.remaining(linux, end)?;
            let read = linux.read(fd.raw(), &mut bytes[count..])?;
            if read == 0 {
                return parse_children(&bytes[..count]);
            }
            count += read;
            if count > CHILDREN_BYTES {
                break;
            }
        }
        Err(Error::invalid("channel-init-children-bytes"))
    })();
    close(linux, report, fd);
    result
}
pub(super) fn close<K: Kernel>(linux: &mut Linux<K>, report: &mut Report, fd: OwnedFd) {
    if let Err(e) = linux.close(fd) {
        report.error(e);
    }
}
fn signal<K: Kernel>(linux: &mut Linux<K>, report: &mut Report, pid: u32, fd: i32) {
    if report.signals.len() == EVENT_LIMIT {
        report.observations_overflowed = true;
        report.fail(Cause::EventLimit);
        return;
    }
    let result = linux.kill(fd);
    report.signals.push(SignalFact { pid, result });
    // ESRCH is retained as an observation, never a substitute for wait/ECHILD.
    if let Err(e) = result
        && e.errno() != Some(3)
    {
        report.error(e);
    }
}
fn cleanup<K: Kernel>(
    linux: &mut Linux<K>,
    budget: &mut Budget,
    report: &mut Report,
    child: &Child,
    io: &mut Io,
) {
    let mut signalled = [0u32; CHILD_LIMIT];
    if report.main_exit.is_none() {
        if let Err(e) = budget.remaining(linux, budget.end) {
            report.error(e);
            return;
        }
        signal(linux, report, child.pid, child.pidfd.raw());
        signalled[0] = child.pid;
    }
    loop {
        if report.observations_overflowed {
            break;
        }
        if let Err(e) = budget.remaining(linux, budget.end) {
            report.error(e);
            break;
        }
        io.progress(linux, budget, report, budget.end);
        if let Err(e) = receive_signal(linux, report, 0) {
            report.error(e);
            return;
        }
        if report.no_children {
            if io.finished() {
                return;
            }
            match budget
                .remaining(linux, budget.end)
                .and_then(|left| io.wait(linux, report, left))
            {
                Ok(()) => continue,
                Err(e) => {
                    report.error(e);
                    return;
                }
            }
        }
        // No wait occurs between this direct-child snapshot and pidfd acquisition.
        // With SIGCHLD default, a sole reaper and no auto-reap, exited children
        // stay zombies; these numeric PIDs cannot be recycled in this interval.
        let listed = match children(linux, budget, report, true) {
            Ok(listed) => listed,
            Err(e) => {
                report.error(e);
                break;
            }
        };
        for pid in listed.pids[..listed.len].iter().copied() {
            if signalled.contains(&pid) {
                continue;
            }
            if let Err(e) = budget.remaining(linux, budget.end) {
                report.error(e);
                return;
            }
            if report.main_exit.is_none() && pid == child.pid {
                signal(linux, report, pid, child.pidfd.raw());
            } else {
                report.fail(Cause::OrphanedChild);
                match linux.channel_pidfd(pid) {
                    Ok(fd) => {
                        signal(linux, report, pid, fd.raw());
                        close(linux, report, fd);
                    }
                    Err(e) => report.error(e),
                }
            }
            let Some(slot) = signalled.iter_mut().find(|p| **p == 0) else {
                report.fail(Cause::EventLimit);
                return;
            };
            *slot = pid;
        }
        loop {
            if let Err(e) = budget.remaining(linux, budget.end) {
                report.error(e);
                return;
            }
            match linux.channel_wait_any() {
                Ok(WaitAny::NoChildren) => {
                    report.no_children = true;
                    if report.main_exit.is_none() {
                        report.error(Error::invalid("channel-init-missing-main-exit"));
                    }
                    break;
                }
                Ok(WaitAny::Exited(exit)) => {
                    for pid in &mut signalled {
                        if *pid == exit.pid {
                            *pid = 0;
                        }
                    }
                    report.exited(exit);
                    if report.observations_overflowed {
                        return;
                    }
                }
                Ok(WaitAny::Running) => break,
                Err(e) => {
                    report.error(e);
                    return;
                }
            }
        }
        if report.no_children && io.finished() {
            return;
        }
        match budget.remaining(linux, budget.end) {
            Ok(left) => {
                if let Err(e) = io.wait(linux, report, left) {
                    report.error(e);
                    return;
                }
            }
            Err(e) => {
                report.error(e);
                return;
            }
        }
    }
}

struct Tail {
    argv: u64,
    env: u64,
    work_end: u64,
    stdio: [i32; 3],
}
/// # Safety
/// Only the dedicated single clone child can enter, with private COW stack and
/// frozen C strings/argv/envp. No allocation, IO formatting, Drop or callback.
unsafe fn tail<K: Kernel>(kernel: &mut K, input: &Tail) -> ! {
    macro_rules! raw {
        ($nr:expr, $args:expr) => {{
            // SAFETY: scalar or explicitly bounded fixed-layout buffers below.
            unsafe {
                kernel.invoke(Call {
                    nr: $nr,
                    args: $args,
                })
            }
        }};
    }
    // After its first dup, fd2 is the owned internal nonblocking pipe prepared
    // by PID 1. AXCI is opaque Chunk data, never external control or a Final.
    // No shell fallback or retry of exec is permitted.
    macro_rules! require {
        ($nr:expr, $args:expr, $expected:expr) => {{
            let result = raw!($nr, $args);
            if result != $expected {
                tail_error(kernel, $nr, result);
            }
        }};
    }
    // Until stderr has been replaced, no failure record may touch inherited
    // fd2. A failed first dup takes the silent terminal path.
    let stderr = input.stdio[2];
    if stderr < 3 || raw!(NR_DUP3, [stderr as u64, 2, 0, 0, 0, 0]) != 2 {
        tail_exit(kernel);
    }
    let pid = raw!(NR_GETPID, [0; 6]);
    if !(2..=i32::MAX as u64).contains(&pid) {
        tail_error(kernel, NR_GETPID, pid);
    }
    require!(NR_GETPPID, [0; 6], 1);
    // Sources are unique owned CLOEXEC pipe ends >=3. Targets are the only
    // inherited borrowed descriptors, deliberately replaced in this child only.
    for (target, source) in input.stdio[..2].iter().copied().enumerate() {
        if source < 3 {
            tail_error(kernel, NR_DUP3, u64::MAX);
        }
        require!(
            NR_DUP3,
            [source as u64, target as u64, 0, 0, 0, 0],
            target as u64
        );
    }
    require!(NR_CLOSE_RANGE, [3, u32::MAX as u64, 0, 0, 0, 0], 0);
    let mask = 0u64;
    require!(
        NR_RT_SIGPROCMASK,
        [
            SIG_SETMASK,
            &mask as *const _ as u64,
            0,
            KERNEL_SIGSET_SIZE,
            0,
            0
        ],
        0
    );
    let mut now = Timespec { sec: 0, nsec: 0 };
    require!(
        NR_CLOCK_GETTIME,
        [CLOCK_BOOTTIME, &mut now as *mut _ as u64, 0, 0, 0, 0],
        0
    );
    if now.sec < 0
        || !(0..1_000_000_000).contains(&now.nsec)
        || now.sec as u64 > u64::MAX / SECOND
        || (now.sec as u64 * SECOND).saturating_add(now.nsec as u64) >= input.work_end
    {
        tail_error(kernel, NR_CLOCK_GETTIME, u64::MAX);
    }
    let result = raw!(
        NR_EXECVEAT,
        [
            (-100i64) as u64,
            c"/bin/busybox".as_ptr() as u64,
            input.argv,
            input.env,
            0,
            0
        ]
    );
    tail_error(kernel, NR_EXECVEAT, result)
}
fn tail_error<K: Kernel>(kernel: &mut K, nr: i32, raw: u64) -> ! {
    let mut record = [0u8; 16];
    record[..4].copy_from_slice(b"AXCI");
    record[4..8].copy_from_slice(&nr.to_le_bytes());
    record[8..].copy_from_slice(&raw.to_le_bytes());
    // SAFETY: fixed 16-byte initialized record, no arguments/environment echoed.
    unsafe {
        kernel.invoke(Call {
            nr: NR_WRITE,
            args: [2, record.as_ptr() as u64, 16, 0, 0, 0],
        });
    }
    tail_exit(kernel)
}
fn tail_exit<K: Kernel>(kernel: &mut K) -> ! {
    loop {
        // SAFETY: terminal pointer-free syscall; never return to Rust cleanup.
        unsafe {
            kernel.invoke(Call {
                nr: NR_EXIT_GROUP,
                args: [126, 0, 0, 0, 0, 0],
            });
        }
    }
}

#[cfg(test)]
#[path = "channel_init_tests.rs"]
mod tests;
