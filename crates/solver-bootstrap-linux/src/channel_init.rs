//! Private diagnostic PID 1 source entry; no CLI, Docker adapter or solver path.
use crate::{
    abi::*,
    fd::OwnedFd,
    syscall::{Call, Error, Kernel, Linux, Result, WaitAny, decode},
};
use std::ffi::CStr;

const SECOND: u64 = 1_000_000_000;
const WORK_NS: u64 = 18 * SECOND;
const TOTAL_NS: u64 = 20 * SECOND;
const TICK_NS: u64 = 10_000_000;
const CHILD_LIMIT: usize = 15; // PID 1 + children remain inside the candidate 16.
const EVENT_LIMIT: usize = 64;
const CHILDREN_BYTES: usize = 256;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Cause {
    Kernel(Error),
    WorkDeadline,
    Cancelled(u32),
    UnexpectedSignal(u32),
    OrphanedChild,
    EventLimit,
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
    fn new() -> Self {
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
    fn fail(&mut self, cause: Cause) {
        self.cause.get_or_insert(cause);
    }
    fn error(&mut self, error: Error) {
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
struct Budget {
    last: u64,
    work: u64,
    end: u64,
}
impl Budget {
    fn new(start: u64) -> Result<Self> {
        Ok(Self {
            last: start,
            work: start
                .checked_add(WORK_NS)
                .ok_or(Error::invalid("channel-init-clock"))?,
            end: start
                .checked_add(TOTAL_NS)
                .ok_or(Error::invalid("channel-init-clock"))?,
        })
    }
    fn now<K: Kernel>(&mut self, linux: &mut Linux<K>) -> Result<u64> {
        let now = linux.boottime_ns()?;
        if now < self.last {
            return Err(Error::invalid("channel-init-clock-rollback"));
        }
        self.last = now;
        Ok(now)
    }
    fn remaining<K: Kernel>(&mut self, linux: &mut Linux<K>, end: u64) -> Result<u64> {
        let now = self.now(linux)?;
        if now >= end {
            return Err(Error::invalid("channel-init-final-deadline"));
        }
        Ok(end - now)
    }
}

/// # Safety
/// Future native entry must be a dedicated, single-threaded namespace PID 1,
/// with private PID/proc namespaces verified by the outer adapter, no concurrent
/// fork/wait or auto-reaper, and only trusted bound collector text. This is not
/// a safe API for embedding in another running process: signals and fd>=3 are
/// replaced. Caller must preserve Report and raw-exit immediately after return;
/// it must never resume service or start another child. No public caller exists.
pub(crate) unsafe fn run<K: Kernel>(linux: &mut Linux<K>, collector: &CStr) -> Report {
    let mut report = Report::new();
    let prepared = (|| {
        if collector.is_empty() || collector.to_bytes().len() > 32768 {
            return Err(Error::invalid("channel-init-collector-size"));
        }
        let mut budget = Budget::new(linux.boottime_ns()?)?;
        linux.check_channel_identity()?;
        linux.channel_close_inherited()?;
        // Emergency child failure reporting must never block on inherited fd2.
        if linux.fstat(2)?.mode & 0xf000 != 0x1000 {
            return Err(Error::invalid("channel-init-stderr-pipe"));
        }
        linux.set_nonblocking(2, true)?;
        if linux.flags(2)? & (O_NONBLOCK | 3) != O_NONBLOCK | 1 {
            return Err(Error::invalid("channel-init-stderr-flags"));
        }
        let frozen = linux.freeze_signals(budget.work)?;
        if frozen < budget.last {
            return Err(Error::invalid("channel-init-clock-rollback"));
        }
        budget.last = frozen;
        if children(linux, &mut budget, &mut report, false)?.len != 0 {
            return Err(Error::invalid("channel-init-existing-children"));
        }
        budget.remaining(linux, budget.work)?;
        Ok(budget)
    })();
    let mut budget = match prepared {
        Ok(budget) if report.cause.is_none() => budget,
        Ok(_) => return report,
        Err(e) => {
            report.error(e);
            return report;
        }
    };
    report.clone_attempted = true;
    let pid = match clone_collector(linux, collector, budget.work) {
        Ok(pid) => pid,
        Err(e) => {
            report.error(e);
            return report;
        }
    };
    report.child_pid = Some(pid);
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
    monitor(linux, &mut budget, &mut report);
    cleanup(linux, &mut budget, &mut report, &child);
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

fn monitor<K: Kernel>(linux: &mut Linux<K>, budget: &mut Budget, report: &mut Report) {
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
                if let Err(e) = receive_signal(linux, report, left.min(TICK_NS)) {
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
fn receive_signal<K: Kernel>(
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
fn close<K: Kernel>(linux: &mut Linux<K>, report: &mut Report, fd: OwnedFd) {
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
                    return;
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
        match budget.remaining(linux, budget.end) {
            Ok(left) => {
                if let Err(e) = receive_signal(linux, report, left.min(TICK_NS)) {
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
    // Preserve the exact failed syscall result in a bounded stderr record. The
    // future adapter must make fd2 nonblocking; its provenance is not accepted
    // by this source entry. No shell fallback or retry of exec is permitted.
    macro_rules! require {
        ($nr:expr, $args:expr, $expected:expr) => {{
            let result = raw!($nr, $args);
            if result != $expected {
                tail_error(kernel, $nr, result);
            }
        }};
    }
    let pid = raw!(NR_GETPID, [0; 6]);
    if !(2..=i32::MAX as u64).contains(&pid) {
        tail_error(kernel, NR_GETPID, pid);
    }
    require!(NR_GETPPID, [0; 6], 1);
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
