//! Single bounded entry: first clock, supervision/transport, then raw exit.
use crate::{
    channel_init::{self, Budget, Cause, Report},
    channel_io::Io,
    channel_report::{Binding, Exit, Fault, Final, Reason, Signal},
    syscall::{Error, ErrorKind, Kernel, Linux, Result},
};
use std::ffi::CString;

fn fault(e: Error) -> Fault {
    let (kind, detail) = match e.kind {
        ErrorKind::Errno(n) => ("errno", n),
        ErrorKind::InvalidInput => ("invalid-input", 0),
        ErrorKind::InvalidReturn => ("invalid-return", 0),
        ErrorKind::UnexpectedLayout => ("layout", 0),
        ErrorKind::Ownership => ("ownership", 0),
    };
    Fault {
        operation: e.operation.into(),
        kind: kind.into(),
        detail,
    }
}
fn exit(e: crate::abi::ChildExit) -> Exit {
    Exit {
        pid: e.pid,
        uid: e.uid,
        code: e.code as u8,
        status: e.status as u8,
    }
}
fn final_value(report: &Report, io: &Io, budget: &Budget, binding: Binding) -> Final {
    let mut value = Final {
        binding,
        cause: report.cause.map(|c| match c {
            Cause::Kernel(e) => Reason::Kernel(fault(e)),
            Cause::WorkDeadline => Reason::Deadline,
            Cause::Cancelled(n) => Reason::Cancelled(n as u8),
            Cause::UnexpectedSignal(n) => Reason::Signal(n as u8),
            Cause::OrphanedChild => Reason::Orphan,
            Cause::EventLimit => Reason::Budget,
            Cause::Capture => Reason::Capture,
            Cause::Transport => Reason::Transport,
        }),
        child_pid: report.child_pid,
        main_exit: report.main_exit.map(exit),
        exits: report.exits.iter().copied().map(exit).collect(),
        signals: report
            .signals
            .iter()
            .map(|s| Signal {
                pid: s.pid,
                error: s.result.err().map(fault),
            })
            .collect(),
        errors: report.errors.iter().copied().map(fault).collect(),
        clone_attempted: report.clone_attempted,
        no_children: report.no_children,
        overflowed: report.observations_overflowed,
        stdout: io.stats(0),
        stderr: io.stats(1),
        first_ns: budget.first,
        last_ns: budget.last,
        capture_failed: io.capture_failed,
        transport_failed: io.transport_failed,
        selected_exit_code: 125,
    };
    value.selected_exit_code = value.selected_code();
    value
}
fn failed_code(report: &Report) -> u8 {
    match report.cause {
        Some(Cause::WorkDeadline) => 124,
        Some(Cause::Cancelled(s)) => 128 + s as u8,
        _ => 125,
    }
}
// All allocations occur after the sole t0. This function never creates a second
// relative budget and is exercised unchanged by finite in-memory kernel scripts.
pub(super) fn drive<K: Kernel, T>(
    linux: &mut Linux<K>,
    budget: &mut Budget,
    binding: Binding,
    collector: &std::ffi::CStr,
    terminal: impl FnOnce(&mut Linux<K>, u8, Report) -> T,
) -> T {
    let mut io = Io::new(binding.clone());
    let mut report = channel_init::run(linux, collector, budget, &mut io);
    // Explicit close consumes every parent-owned token even on EINTR; failures
    // enter the same report before Final is frozen. Borrowed stdio lasts to exit.
    io.close_all(linux, &mut report);
    if let Err(e) = budget.now(linux) {
        report.error(e);
        return terminal(linux, failed_code(&report), report);
    }
    if budget.last >= budget.final_end {
        return terminal(linux, failed_code(&report), report);
    }
    if !io.settle(linux, budget, &mut report) {
        return terminal(linux, failed_code(&report), report);
    }
    if let Err(e) = budget.now(linux) {
        report.error(e);
        return terminal(linux, failed_code(&report), report);
    }
    if budget.last >= budget.final_end {
        return terminal(linux, failed_code(&report), report);
    }
    let value = final_value(&report, &io, budget, binding);
    let code = if io.finish(linux, budget, &mut report, &value) {
        value.selected_exit_code
    } else {
        failed_code(&report)
    };
    // Native terminal never returns: IO/Final/binding allocations stay alive,
    // with no destructor, std flush or atexit after the terminal frame. Only the
    // explicitly scripted tests return values through this private boundary.
    terminal(linux, code, report)
}
pub(super) fn enter<K: Kernel>(
    linux: &mut Linux<K>,
    prepare: impl FnOnce() -> Result<(Binding, CString)>,
) -> ! {
    // No Report/Vec/args/hook/binding construction before the first raw clock.
    let first = match linux.boottime_ns() {
        Ok(t) => t,
        Err(_) => linux.exit_group(125),
    };
    let mut budget = match Budget::new(first) {
        Ok(b) => b,
        Err(_) => linux.exit_group(125),
    };
    let (binding, collector) = match prepare() {
        Ok(v) => v,
        Err(_) => linux.exit_group(125),
    };
    drive(
        linux,
        &mut budget,
        binding,
        &collector,
        |linux, code, _report| linux.exit_group(code),
    )
}
fn run_id(text: &str) -> Result<[u8; 32]> {
    if text.len() != 64
        || !text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(Error::invalid("channel-run-id"));
    }
    let mut out = [0; 32];
    for (i, byte) in out.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&text[i * 2..i * 2 + 2], 16)
            .map_err(|_| Error::invalid("channel-run-id"))?;
    }
    Ok(out)
}
fn prepare(emergency: fn() -> !, captured_inputs: &[u8]) -> Result<(Binding, CString)> {
    std::panic::set_hook(Box::new(move |_| emergency()));
    let mut args = std::env::args_os();
    args.next();
    if args.next().as_deref() != Some(std::ffi::OsStr::new("--run-id")) {
        return Err(Error::invalid("channel-arguments"));
    }
    let id = args.next().ok_or(Error::invalid("channel-arguments"))?;
    if args.next().is_some() {
        return Err(Error::invalid("channel-arguments"));
    }
    let id = run_id(id.to_str().ok_or(Error::invalid("channel-run-id"))?)?;
    crate::channel_profile::validate_collector(crate::channel_profile::COLLECTOR)
        .map_err(|_| Error::invalid("channel-body"))?;
    let binding = crate::channel_inputs::native_binding(captured_inputs, id)
        .map_err(|_| Error::invalid("channel-inputs"))?;
    let collector = CString::new(crate::channel_profile::COLLECTOR)
        .map_err(|_| Error::invalid("channel-body"))?;
    Ok((binding, collector))
}

// Native routing alone is cfg-gated; the whole engine/FD/allocator body remains
// typechecked and tested on the host. No fake NativeKernel exists on other OSes.
#[cfg(all(
    feature = "linux-channel-entry",
    target_os = "linux",
    target_env = "musl",
    target_arch = "aarch64",
    target_endian = "little",
    target_pointer_width = "64"
))]
pub(crate) fn native() -> ! {
    let mut linux = Linux::new(crate::syscall::NativeKernel);
    enter(&mut linux, || {
        prepare(
            emergency,
            include_bytes!(env!("RADISHAXIOM_LINUX_CHANNEL_INPUTS")),
        )
    })
}
#[cfg(all(
    feature = "linux-channel-entry",
    target_os = "linux",
    target_env = "musl",
    target_arch = "aarch64",
    target_endian = "little",
    target_pointer_width = "64"
))]
pub(crate) fn emergency() -> ! {
    terminal(&mut Linux::new(crate::syscall::NativeKernel))
}
pub(super) fn terminal<K: Kernel>(linux: &mut Linux<K>) -> ! {
    linux.exit_group(125)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn run_ids_reject_implicit_normalization() {
        assert_eq!(run_id(&"07".repeat(32)).unwrap(), [7; 32]);
        for id in [
            "07".repeat(31),
            "AB".repeat(32),
            format!("{}\n", "07".repeat(32)),
            "é".repeat(32),
            "sha256:".to_owned() + &"07".repeat(32),
        ] {
            assert!(run_id(&id).is_err());
        }
    }
}
