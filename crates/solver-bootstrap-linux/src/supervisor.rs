//! S2..S7 driver over typed Linux wrappers. No executable entry point exists.
use crate::{
    abi,
    child::FrozenPointers,
    observation::ChildFact,
    setup::{Prepared, SetupError, verify_inventory},
    syscall::{Error, Kernel, Linux},
};
use radishaxiom_solver_supervision_core::{
    abi::{AT_EMPTY_PATH, AUDIT_ARCH_AARCH64, NR_EXECVEAT},
    handshake::LinuxInstant,
    wire::{
        BOOTSTRAP_CHUNK_LIMIT, BootstrapDecoder, BootstrapFrame, BootstrapMessage, ChildExit,
        Direction, Final, PendingFrameBuffer, WireError,
    },
};
#[derive(Debug)]
pub(crate) enum SupervisorError {
    Setup(SetupError),
    System(Error),
    Wire(WireError),
    Protocol,
    Handshake(radishaxiom_solver_supervision_core::handshake::HandshakeError),
    ControlLost,
    ListenerLost,
    Child,
    Notification,
    OutputLimit,
    ZeroWrite,
    Observation(crate::observation::ObservationError),
    Cleanup {
        primary: Box<SupervisorError>,
        errors: Vec<Error>,
    },
}
impl From<SetupError> for SupervisorError {
    fn from(e: SetupError) -> Self {
        Self::Setup(e)
    }
}
impl From<Error> for SupervisorError {
    fn from(e: Error) -> Self {
        Self::System(e)
    }
}
impl From<WireError> for SupervisorError {
    fn from(e: WireError) -> Self {
        Self::Wire(e)
    }
}
#[derive(Clone, Copy, Eq, PartialEq)]
pub(crate) enum ExecGrant {
    Awaiting,
    Consumed,
}
const READ: i16 = 1;
const WRITE: i16 = 4;
const BAD: i16 = 8 | 16 | 32;
fn retry(error: Error) -> bool {
    matches!(error.errno(), Some(4 | 11))
}

struct ControlInput {
    decoder: BootstrapDecoder,
    bytes: [u8; 8192],
    at: usize,
    used: usize,
}
impl ControlInput {
    fn new(p: &Prepared) -> Self {
        Self {
            decoder: BootstrapDecoder::new_bound(
                Direction::MacToSupervisor,
                p.binding.clone(),
                p.configuration.wire,
            ),
            bytes: [0; 8192],
            at: 0,
            used: 0,
        }
    }
    fn buffered<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
    ) -> Result<Option<BootstrapFrame>, SupervisorError> {
        if self.at == self.used {
            match linux.read(0, &mut self.bytes) {
                Ok(0) => return Err(SupervisorError::ControlLost),
                Ok(n) => {
                    self.at = 0;
                    self.used = n
                }
                Err(e) if retry(e) => return Ok(None),
                Err(e) => return Err(e.into()),
            }
        }
        let step = self.decoder.poll(&self.bytes[self.at..self.used])?;
        self.at += step.consumed;
        Ok(step.frame)
    }
    fn has_bytes(&self) -> bool {
        self.at < self.used
    }
}
pub(crate) struct NativeOutcome {
    pub child: ChildFact,
    pub stdout_bytes: usize,
    pub stderr_bytes: usize,
    pub observations: crate::observation::ObservationLog,
}
#[derive(Default)]
pub(crate) struct CleanupFacts {
    pub kill: Option<Result<(), Error>>,
    pub wait: Option<Result<Option<abi::ChildExit>, Error>>,
    pub close_errors: Vec<Error>,
    pub emergency_write: Option<Result<usize, Error>>,
}
pub(crate) struct NativeFailure {
    pub primary_error: SupervisorError,
    pub child: ChildFact,
    pub cleanup: CleanupFacts,
    pub observations: crate::observation::ObservationLog,
}
/// Local completion cannot convert to normal P4/capture: runtime exit, tree
/// basis and exact deletion are still missing. Failures retain original reads.
pub(crate) fn run<K: Kernel>(
    linux: &mut Linux<K>,
    mut p: Prepared,
) -> Result<NativeOutcome, Box<NativeFailure>> {
    let mut child = ChildFact::Absent;
    let mut pidfd = None;
    let result = run_inner(linux, &mut p, &mut child, &mut pidfd);
    let mut cleanup = CleanupFacts::default();
    if result.is_err()
        && matches!(child, ChildFact::Running(_))
        && let Some(fd) = pidfd
    {
        cleanup.kill = Some(linux.kill(fd));
        let waited = linux.wait(fd);
        if let Ok(Some(exit)) = &waited
            && matches!(child,ChildFact::Running(pid) if pid==exit.pid)
        {
            child = ChildFact::Reaped {
                pid: exit.pid,
                code: exit.code,
                status: exit.status,
            };
        }
        cleanup.wait = Some(waited);
    }
    if let Err(error) = &result {
        cleanup.emergency_write = Some(emergency_diagnostic(linux, error));
    }
    if let Some(mut frozen) = p.frozen.take()
        && let Err(error) = frozen.close_parent_fds(linux)
    {
        cleanup.close_errors.push(error);
    }
    cleanup.close_errors.extend(p.resources.cleanup_all(linux));
    match result {
        Ok((stdout_bytes, stderr_bytes)) if cleanup.close_errors.is_empty() => Ok(NativeOutcome {
            child,
            stdout_bytes,
            stderr_bytes,
            observations: p.observations,
        }),
        Ok(_) => Err(Box::new(NativeFailure {
            primary_error: SupervisorError::System(cleanup.close_errors[0]),
            child,
            cleanup,
            observations: p.observations,
        })),
        Err(primary_error) => Err(Box::new(NativeFailure {
            primary_error,
            child,
            cleanup,
            observations: p.observations,
        })),
    }
}
fn run_inner<K: Kernel>(
    linux: &mut Linux<K>,
    p: &mut Prepared,
    child: &mut ChildFact,
    pidfd_out: &mut Option<i32>,
) -> Result<(usize, usize), SupervisorError> {
    let mut input = ControlInput::new(p);
    let mut output = PendingFrameBuffer::new(Direction::SupervisorToMac, p.configuration.wire);
    let mut chunk = vec![0u8; BOOTSTRAP_CHUNK_LIMIT];
    let now = p.deadline.check(linux)?;
    let ready = p
        .handshake
        .ready(LinuxInstant::declared_ns(now))
        .map_err(SupervisorError::Handshake)?;
    output.push(&ready)?;
    flush(linux, p, &mut output)?;
    // No child exists while ARM/query are received and checked in S memory.
    let arm = next_control(linux, p, &mut input)?;
    let now = p.deadline.check(linux)?;
    let plan = p
        .handshake
        .receive_arm(LinuxInstant::declared_ns(now), &arm)
        .map_err(SupervisorError::Handshake)?;
    p.deadline.narrow(now, plan.deadline().as_ns())?;
    linux.arm_timer(p.timer, p.deadline.until)?;
    loop {
        let frame = next_control(linux, p, &mut input)?;
        match frame.message {
            BootstrapMessage::QueryChunk(bytes) => {
                let len = p
                    .query
                    .len()
                    .checked_add(bytes.len())
                    .filter(|n| *n <= p.configuration.wire.query_bytes)
                    .ok_or(SupervisorError::Protocol)?;
                if len > p.description.fields().query_bytes as usize {
                    return Err(SupervisorError::Protocol);
                }
                p.query.extend_from_slice(&bytes);
            }
            BootstrapMessage::QueryEnd => break,
            _ => return Err(SupervisorError::Protocol),
        }
    }
    let now = p.deadline.check(linux)?;
    p.handshake
        .query_complete(LinuxInstant::declared_ns(now), &p.binding, &p.query)
        .map_err(SupervisorError::Handshake)?;
    p.deadline.check(linux)?;
    ensure_no_control(linux, &input)?;
    let mut frozen = p.frozen.take().ok_or(SupervisorError::Protocol)?;
    let created_result = (|| {
        p.deadline.check(linux)?;
        Ok::<_, SupervisorError>(frozen.clone_once(linux, p.deadline.until)?)
    })();
    // Parent ownership is recorded before even closing scratch descriptors.
    if let Ok(created) = &created_result {
        *child = ChildFact::Running(created.pid);
    }
    let created = match created_result {
        Ok(created) => created,
        Err(primary) => {
            return match frozen.close_parent_fds(linux) {
                Ok(()) => Err(primary),
                Err(error) => Err(SupervisorError::Cleanup {
                    primary: Box::new(primary),
                    errors: vec![error],
                }),
            };
        }
    };
    // Acquire the child before any fallible mapping/close, so failure still kills
    // that exact child. Never retry clone or detach the reaping responsibility.
    *child = ChildFact::Running(created.pid);
    let raw = p.resources.add(created.pidfd);
    *pidfd_out = Some(raw);
    frozen.close_parent_fds(linux)?;
    let pidfd = if raw == 14 {
        raw
    } else {
        let mapped = linux.duplicate(raw, 14, true)?;
        let mapped = p.resources.add(mapped);
        *pidfd_out = Some(mapped);
        p.resources.close(linux, raw)?;
        mapped
    };
    *pidfd_out = Some(pidfd);
    for fd in [
        p.child_stdio[0],
        p.child_stdio[1],
        p.child_stdio[2],
        p.child_socket,
        p.elf,
    ] {
        p.resources.close(linux, fd)?;
    }
    let listener = receive_listener(linux, p, pidfd)?;
    let raw = p.resources.add(listener);
    let listener = p.resources.move_to(linux, raw, 15)?;
    p.resources.close(linux, p.socket)?;
    // Exact 21-role inventory is checked while fcntl/getdents are still allowed.
    let roles = [
        0, 1, 2, p.stdin, p.stdout, p.stderr, p.timer, pidfd, listener,
    ];
    let mut inventory = roles.to_vec();
    inventory.extend_from_slice(&p.cgroup);
    if p.resources.descriptors().len() != 21 {
        return Err(SupervisorError::Protocol);
    }
    verify_inventory(linux, &mut p.deadline, &inventory)?;
    p.deadline.check(linux)?;
    if linux
        .install_filter(&p.configuration.supervisor, false)?
        .is_some()
    {
        return Err(SupervisorError::Protocol);
    }
    grant_first_exec(linux, p, pidfd, listener, created.pid, created.pointers)?;
    capture(linux, p, child, pidfd)?;
    stream_and_reap(
        linux,
        p,
        child,
        pidfd,
        listener,
        StreamBuffers {
            input: &mut input,
            output: &mut output,
            chunk: &mut chunk,
        },
    )
}
struct StreamBuffers<'a> {
    input: &'a mut ControlInput,
    output: &'a mut PendingFrameBuffer,
    chunk: &'a mut [u8],
}
fn stream_and_reap<K: Kernel>(
    linux: &mut Linux<K>,
    p: &mut Prepared,
    child: &mut ChildFact,
    pidfd: i32,
    listener: i32,
    buffers: StreamBuffers<'_>,
) -> Result<(usize, usize), SupervisorError> {
    let StreamBuffers {
        input,
        output,
        chunk,
    } = buffers;
    let mut stdin_at = 0;
    let mut stdin_open = true;
    let mut counts = [0usize; 2];
    let mut eof = [false; 2];
    let mut exit_sent = false;
    let mut final_queued = false;
    loop {
        let now = p.deadline.check(linux)?;
        if stdin_open && stdin_at == p.query.len() {
            p.resources.close(linux, p.stdin)?;
            stdin_open = false;
        }
        if matches!(child, ChildFact::Reaped { .. }) && stdin_at < p.query.len() {
            return Err(SupervisorError::Child);
        }
        if matches!(child, ChildFact::Reaped { .. })
            && eof == [true, true]
            && output.remaining().is_empty()
        {
            if !exit_sent {
                output.push(&frame(
                    p,
                    BootstrapMessage::ChildExit(exit_message(*child)?),
                ))?;
                exit_sent = true;
            } else if !final_queued {
                let sample = capture(linux, p, child, pidfd)?;
                if sample.members != [1] {
                    return Err(SupervisorError::Protocol);
                }
                output.push(&frame(
                    p,
                    BootstrapMessage::Final(Final {
                        child_reaped: true,
                        only_supervisor: true,
                    }),
                ))?;
                final_queued = true;
            } else {
                ensure_no_control(linux, input)?;
                p.deadline.check(linux)?;
                return Ok((counts[0], counts[1]));
            }
        }
        let can_stream = output.remaining().is_empty();
        let mut polls = vec![poll(p.timer, READ), poll(0, READ)];
        let listener_index = if matches!(child, ChildFact::Running(_)) {
            let i = polls.len();
            polls.push(poll(listener, READ));
            Some(i)
        } else {
            None
        };
        let pidfd_index = if matches!(child, ChildFact::Running(_)) {
            let i = polls.len();
            polls.push(poll(pidfd, READ));
            Some(i)
        } else {
            None
        };
        let output_index = polls.len();
        polls.push(poll(1, if can_stream { 0 } else { WRITE }));
        let stdin_index = if stdin_open {
            let i = polls.len();
            polls.push(poll(p.stdin, WRITE));
            Some(i)
        } else {
            None
        };
        let mut indices = [None, None];
        for i in 0..2 {
            if !eof[i] && can_stream {
                indices[i] = Some(polls.len());
                polls.push(poll(if i == 0 { p.stdout } else { p.stderr }, READ));
            }
        }
        match linux.poll(&mut polls, p.deadline.until - now) {
            Ok(_) => {}
            Err(e) if retry(e) => continue,
            Err(e) => return Err(e.into()),
        }
        p.deadline.check(linux)?;
        // Expiration/disconnection has priority over any ready output or notice.
        if polls[0].revents != 0 {
            return Err(SupervisorError::Setup(SetupError::Deadline));
        }
        if polls[1].revents & BAD != 0 {
            return Err(SupervisorError::ControlLost);
        }
        if polls[1].revents & READ != 0 || input.has_bytes() {
            ensure_no_control(linux, input)?;
        }
        if let Some(i) = pidfd_index {
            if polls[i].revents & BAD != 0 && polls[i].revents & READ == 0 {
                return Err(SupervisorError::Child);
            }
            if polls[i].revents & READ != 0 {
                reap(linux, child, pidfd)?;
            }
        }
        if let Some(i) = listener_index {
            if polls[i].revents & READ != 0 {
                return Err(SupervisorError::Notification);
            } // no second RECV
            if polls[i].revents & (8 | 32) != 0 {
                return Err(SupervisorError::ListenerLost);
            }
            if polls[i].revents & 16 != 0 {
                if matches!(child, ChildFact::Running(_)) {
                    reap(linux, child, pidfd)?;
                }
                if !matches!(child, ChildFact::Reaped { .. }) {
                    return Err(SupervisorError::ListenerLost);
                }
            }
        }
        if polls[output_index].revents & BAD != 0 {
            return Err(SupervisorError::ControlLost);
        }
        if polls[output_index].revents & WRITE != 0 {
            write_pending(linux, output)?;
        }
        if let Some(i) = stdin_index {
            if polls[i].revents & BAD != 0 && stdin_at != p.query.len() {
                return Err(SupervisorError::Child);
            }
            if polls[i].revents & WRITE != 0 {
                match linux.write(p.stdin, &p.query[stdin_at..]) {
                    Ok(0) => return Err(SupervisorError::ZeroWrite),
                    Ok(n) => stdin_at += n,
                    Err(e) if retry(e) => {}
                    Err(e) => return Err(e.into()),
                }
            }
        }
        for i in 0..2 {
            if !output.remaining().is_empty() {
                break;
            }
            if let Some(index) = indices[i] {
                let flags = polls[index].revents;
                if flags & (8 | 32) != 0 {
                    return Err(SupervisorError::Child);
                }
                if flags & (READ | 16) != 0 {
                    let max = if i == 0 {
                        p.configuration.wire.stdout_bytes
                    } else {
                        p.configuration.wire.stderr_bytes
                    };
                    let request = (max - counts[i]).saturating_add(1).min(chunk.len());
                    match linux.read(
                        if i == 0 { p.stdout } else { p.stderr },
                        &mut chunk[..request],
                    ) {
                        Ok(0) => {
                            eof[i] = true;
                            output.push(&frame(
                                p,
                                if i == 0 {
                                    BootstrapMessage::StdoutEof
                                } else {
                                    BootstrapMessage::StderrEof
                                },
                            ))?;
                            p.resources
                                .close(linux, if i == 0 { p.stdout } else { p.stderr })?;
                        }
                        Ok(n) => {
                            if n > max - counts[i] {
                                return Err(SupervisorError::OutputLimit);
                            }
                            counts[i] += n;
                            output.push(&frame(
                                p,
                                if i == 0 {
                                    BootstrapMessage::StdoutChunk(chunk[..n].to_vec())
                                } else {
                                    BootstrapMessage::StderrChunk(chunk[..n].to_vec())
                                },
                            ))?;
                        }
                        Err(e) if retry(e) => {}
                        Err(e) => return Err(e.into()),
                    }
                }
            }
        }
        p.deadline.check(linux)?;
    }
}
fn frame(p: &Prepared, message: BootstrapMessage) -> BootstrapFrame {
    BootstrapFrame {
        binding: p.binding.clone(),
        message,
    }
}
fn poll(fd: i32, events: i16) -> abi::PollFd {
    abi::PollFd {
        fd,
        events,
        revents: 0,
    }
}
fn write_pending<K: Kernel>(
    linux: &mut Linux<K>,
    output: &mut PendingFrameBuffer,
) -> Result<(), SupervisorError> {
    match linux.write(1, output.remaining()) {
        Ok(0) => Err(SupervisorError::ZeroWrite),
        Ok(n) => {
            output.consume(n)?;
            Ok(())
        }
        Err(e) if retry(e) => Ok(()),
        Err(e) => Err(e.into()),
    }
}
fn flush<K: Kernel>(
    linux: &mut Linux<K>,
    p: &mut Prepared,
    output: &mut PendingFrameBuffer,
) -> Result<(), SupervisorError> {
    while !output.remaining().is_empty() {
        let now = p.deadline.check(linux)?;
        let mut fds = [poll(p.timer, READ), poll(0, READ), poll(1, WRITE)];
        match linux.poll(&mut fds, p.deadline.until - now) {
            Ok(_) => {}
            Err(e) if retry(e) => continue,
            Err(e) => return Err(e.into()),
        }
        p.deadline.check(linux)?;
        if fds[0].revents != 0 {
            return Err(SetupError::Deadline.into());
        }
        if fds[1].revents & BAD != 0 || fds[2].revents & BAD != 0 {
            return Err(SupervisorError::ControlLost);
        }
        if fds[2].revents & WRITE != 0 {
            write_pending(linux, output)?;
        }
    }
    Ok(())
}
fn next_control<K: Kernel>(
    linux: &mut Linux<K>,
    p: &mut Prepared,
    input: &mut ControlInput,
) -> Result<BootstrapFrame, SupervisorError> {
    loop {
        p.deadline.check(linux)?;
        if input.has_bytes() {
            if let Some(frame) = input.buffered(linux)? {
                return Ok(frame);
            }
            continue;
        }
        let now = p.deadline.check(linux)?;
        let mut fds = [poll(p.timer, READ), poll(0, READ)];
        match linux.poll(&mut fds, p.deadline.until - now) {
            Ok(_) => {}
            Err(e) if retry(e) => continue,
            Err(e) => return Err(e.into()),
        }
        p.deadline.check(linux)?;
        if fds[0].revents != 0 {
            return Err(SetupError::Deadline.into());
        }
        if fds[1].revents & BAD != 0 {
            return Err(SupervisorError::ControlLost);
        }
        if fds[1].revents & READ != 0
            && let Some(frame) = input.buffered(linux)?
        {
            return Ok(frame);
        }
    }
}
fn receive_listener<K: Kernel>(
    linux: &mut Linux<K>,
    p: &mut Prepared,
    pidfd: i32,
) -> Result<crate::fd::OwnedFd, SupervisorError> {
    loop {
        let now = p.deadline.check(linux)?;
        let mut fds = [
            poll(p.timer, READ),
            poll(0, READ),
            poll(pidfd, READ),
            poll(p.socket, READ),
        ];
        match linux.poll(&mut fds, p.deadline.until - now) {
            Ok(_) => {}
            Err(e) if retry(e) => continue,
            Err(e) => return Err(e.into()),
        }
        p.deadline.check(linux)?;
        if fds[0].revents != 0 {
            return Err(SetupError::Deadline.into());
        }
        if fds[1].revents & BAD != 0 {
            return Err(SupervisorError::ControlLost);
        }
        if fds[2].revents != 0 {
            return Err(SupervisorError::Child);
        }
        if fds[1].revents & READ != 0 {
            reject_control_read(linux)?;
        }
        if fds[3].revents & (8 | 32) != 0 {
            return Err(SupervisorError::ListenerLost);
        }
        if fds[3].revents & READ != 0 {
            return Ok(linux.receive_listener(p.socket)?);
        }
        if fds[3].revents & 16 != 0 {
            return Err(SupervisorError::ListenerLost);
        }
    }
}
fn grant_first_exec<K: Kernel>(
    linux: &mut Linux<K>,
    p: &mut Prepared,
    pidfd: i32,
    listener: i32,
    pid: u32,
    pointers: FrozenPointers,
) -> Result<(), SupervisorError> {
    if p.exec_grant != ExecGrant::Awaiting {
        return Err(SupervisorError::Notification);
    }
    loop {
        let now = p.deadline.check(linux)?;
        let mut fds = [
            poll(p.timer, READ),
            poll(0, READ),
            poll(pidfd, READ),
            poll(listener, READ),
        ];
        match linux.poll(&mut fds, p.deadline.until - now) {
            Ok(_) => {}
            Err(e) if retry(e) => continue,
            Err(e) => return Err(e.into()),
        }
        p.deadline.check(linux)?;
        if fds[0].revents != 0 {
            return Err(SetupError::Deadline.into());
        }
        if fds[1].revents & BAD != 0 {
            return Err(SupervisorError::ControlLost);
        }
        if fds[1].revents & READ != 0 {
            reject_control_read(linux)?;
        }
        if fds[2].revents != 0 {
            return Err(SupervisorError::Child);
        }
        if fds[3].revents & BAD != 0 {
            return Err(SupervisorError::ListenerLost);
        }
        if fds[3].revents & READ != 0 {
            if p.exec_grant != ExecGrant::Awaiting {
                return Err(SupervisorError::Notification);
            }
            let notification = linux.receive_notification(listener)?;
            let expected = [
                3,
                pointers.empty_path,
                pointers.argv,
                pointers.envp,
                AT_EMPTY_PATH,
                0,
            ];
            if notification.pid != pid
                || notification.flags != 0
                || notification.data.arch != AUDIT_ARCH_AARCH64
                || notification.data.nr != NR_EXECVEAT
                || notification.data.args != expected
            {
                return Err(SupervisorError::Notification);
            }
            linux.notification_id_valid(listener, notification.id)?;
            reject_control_read(linux)?;
            p.deadline.check(linux)?;
            // Consume before SEND even when SEND errors, never retry a CONTINUE.
            p.exec_grant = ExecGrant::Consumed;
            linux.continue_notification(listener, notification.id)?;
            p.deadline.check(linux)?;
            return Ok(());
        }
    }
}
fn reap<K: Kernel>(
    linux: &mut Linux<K>,
    child: &mut ChildFact,
    pidfd: i32,
) -> Result<(), SupervisorError> {
    if let ChildFact::Running(pid) = *child
        && let Some(exit) = linux.wait(pidfd)?
    {
        if exit.pid != pid {
            return Err(SupervisorError::Child);
        }
        *child = ChildFact::Reaped {
            pid,
            code: exit.code,
            status: exit.status,
        };
    }
    Ok(())
}
fn exit_message(child: ChildFact) -> Result<ChildExit, SupervisorError> {
    match child {
        ChildFact::Reaped {
            code: 1, status, ..
        } if (0..=255).contains(&status) => Ok(ChildExit::Exited(status as u8)),
        ChildFact::Reaped {
            code: 2 | 3,
            status,
            ..
        } if (1..=64).contains(&status) => Ok(ChildExit::Signaled(status as u8)),
        _ => Err(SupervisorError::Child),
    }
}
fn capture<K: Kernel>(
    linux: &mut Linux<K>,
    p: &mut Prepared,
    child: &mut ChildFact,
    pidfd: i32,
) -> Result<radishaxiom_solver_supervision_core::cgroup::ParsedCgroup, SupervisorError> {
    for _ in 0..2 {
        let now = p.deadline.check(linux)?;
        if now >= p.deadline.until {
            return Err(SetupError::Deadline.into());
        }
        if let Some(sample) = p
            .observations
            .capture(
                linux,
                &p.cgroup,
                p.configuration.cgroup,
                p.deadline.until,
                child,
                Some(pidfd),
            )
            .map_err(SupervisorError::Observation)?
        {
            p.deadline.check(linux)?;
            return Ok(sample);
        }
    }
    Err(SupervisorError::Protocol)
}

/// The only termination form reserved for a future qualified process entry.
/// Its visibility and absence of an executable keep E0/E4 gates outside this crate.
pub(crate) fn serve_and_exit<K: Kernel>(linux: &mut Linux<K>, prepared: Prepared) -> ! {
    let status = if run(linux, prepared).is_ok() { 0 } else { 125 };
    linux.exit_group(status)
}
#[cfg(test)]
#[path = "supervisor_tests.rs"]
mod tests;

fn reject_control_read<K: Kernel>(linux: &mut Linux<K>) -> Result<(), SupervisorError> {
    let mut byte = [0u8; 1];
    match linux.read(0, &mut byte) {
        Ok(0) => Err(SupervisorError::ControlLost),
        Ok(_) => Err(SupervisorError::Protocol),
        Err(e) if e.errno() == Some(11) => Ok(()),
        Err(e) => Err(e.into()),
    }
}
fn ensure_no_control<K: Kernel>(
    linux: &mut Linux<K>,
    input: &ControlInput,
) -> Result<(), SupervisorError> {
    if input.has_bytes() || input.decoder.buffered_bytes() != 0 {
        return Err(SupervisorError::Protocol);
    }
    reject_control_read(linux)
}

fn emergency_diagnostic<K: Kernel>(
    linux: &mut Linux<K>,
    error: &SupervisorError,
) -> Result<usize, Error> {
    let (operation, errno) = failure_context(error);
    let mut bytes = [0u8; 128];
    let prefix = b"AXB failure operation=";
    let mut used = prefix.len();
    bytes[..used].copy_from_slice(prefix);
    let n = operation.len().min(64);
    bytes[used..used + n].copy_from_slice(&operation.as_bytes()[..n]);
    used += n;
    let label = b" errno=";
    bytes[used..used + label.len()].copy_from_slice(label);
    used += label.len();
    if let Some(errno) = errno {
        for divisor in [1000, 100, 10, 1] {
            bytes[used] = b'0' + ((errno / divisor) % 10) as u8;
            used += 1;
        }
    } else {
        bytes[used..used + 4].copy_from_slice(b"none");
        used += 4;
    }
    bytes[used] = b'\n';
    used += 1;
    // One bounded NONBLOCK write. Partial/EAGAIN/errno is retained by the
    // report; it never extends the deadline or retries diagnostic delivery.
    linux.write(2, &bytes[..used])
}
fn failure_context(error: &SupervisorError) -> (&'static str, Option<u16>) {
    match error {
        SupervisorError::System(e) => (e.operation, e.errno()),
        SupervisorError::Setup(e) => setup_context(e),
        SupervisorError::Observation(crate::observation::ObservationError::System(e)) => {
            (e.operation, e.errno())
        }
        SupervisorError::Cleanup { primary, .. } => failure_context(primary),
        SupervisorError::Wire(_) => ("wire", None),
        SupervisorError::Handshake(_) => ("handshake", None),
        SupervisorError::Protocol => ("protocol", None),
        SupervisorError::ControlLost => ("control-lost", None),
        SupervisorError::ListenerLost => ("listener-lost", None),
        SupervisorError::Child => ("child", None),
        SupervisorError::Notification => ("notification", None),
        SupervisorError::OutputLimit => ("output-limit", None),
        SupervisorError::ZeroWrite => ("zero-write", None),
        SupervisorError::Observation(_) => ("cgroup-observation", None),
    }
}
fn setup_context(error: &SetupError) -> (&'static str, Option<u16>) {
    match error {
        SetupError::System(e) => (e.operation, e.errno()),
        SetupError::Cleanup { primary, .. } | SetupError::Preparation { primary, .. } => {
            setup_context(primary)
        }
        SetupError::Identity(context) => (context, None),
        SetupError::Deadline => ("deadline", None),
        SetupError::ClockRollback => ("clock-rollback", None),
        _ => ("setup", None),
    }
}
