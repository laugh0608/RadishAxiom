//! A single-attempt, simulation-only controller. Actions describe in-memory
//! control intent; none carries a Docker create recipe or an executable callback.

use radishaxiom_ir::solver::ProcessExit;

use crate::observation::{
    CleanupStatus, FailureFact, FailureKind, ObservationStage, SimulationObservation,
    SimulationObservationInput, SimulationStreamInput,
};
use crate::plan::SimulationPlan;
use crate::transport::{CONTROL_DIAGNOSTIC_LIMIT, SeparatedStreams, StreamKind, TransportError};
use crate::{HostError, HostLimits, Result};

pub const LIFECYCLE_MS: u64 = radishaxiom_ir::solver::PROCESS_LIMITS.wall_clock_ms;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SimulationToken {
    pub plan_digest: String,
    pub request_digest: String,
    pub container: String,
}

/// No create arguments are available before the E3 design gates close.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SimulationActionKind {
    Create,
    AttachSeparatedStreams,
    Start,
    SendExactStdin(Vec<u8>),
    CloseStdin,
    Wait,
    Inspect,
    TerminateTree,
    ConfirmEmptyTree,
    Cleanup,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SimulationAction {
    pub token: SimulationToken,
    pub kind: SimulationActionKind,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ControlOperation {
    Create,
    Attach,
    Start,
    Stdin,
    Wait,
    Inspect,
    Terminate,
    EmptyTree,
    Cleanup,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SimulationEventKind {
    Created,
    Attached,
    Started,
    StdinWritten(Vec<u8>),
    StdinClosed,
    /// A simultaneous capture batch preserves both over-limit facts before
    /// requesting termination. Capturing stops at each stream's N+1 byte.
    Output {
        stdout: Vec<u8>,
        stderr: Vec<u8>,
    },
    StreamsClosed {
        stdout: bool,
        stderr: bool,
    },
    Exit(ProcessExit),
    Inspected,
    /// Explicit simulated container OOM attribution; exit 137 and stderr text
    /// alone never produce this event or a memory classification.
    OomKilled,
    Interrupted(Vec<u8>),
    ControlFailed {
        operation: ControlOperation,
        diagnostic: Vec<u8>,
    },
    TransportFailed(Vec<u8>),
    DeadlineTick,
    TreeTerminated,
    TreeEmpty,
    TreeNotEmpty,
    Cleaned,
    CleanupFailed(Vec<u8>),
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SimulationEvent {
    pub token: SimulationToken,
    pub at_ms: u64,
    pub kind: SimulationEventKind,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Rejection {
    Binding,
    ClockRollback,
    Sequence,
    StdinMismatch,
    Budget,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct SimulationTransition {
    pub actions: Vec<SimulationAction>,
    pub rejection: Option<Rejection>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Phase {
    Create,
    Attach,
    Start,
    Stdin,
    StdinEof,
    Running,
    Inspect,
    Drain,
    Terminate,
    EmptyTree,
    Cleanup,
    Finalizable,
}

pub struct SimulationController<'p, 'r> {
    plan: &'p SimulationPlan<'r>,
    token: SimulationToken,
    limits: HostLimits,
    phase: Phase,
    started_at_ms: u64,
    deadline_ms: u64,
    last_ms: u64,
    started: bool,
    failed: bool,
    exit: Option<ProcessExit>,
    cleanup: CleanupStatus,
    streams: SeparatedStreams,
    diagnostics: Vec<u8>,
    diagnostics_exceeded: bool,
    failures: Vec<FailureFact>,
    exhausted: bool,
}

impl<'p, 'r> SimulationController<'p, 'r> {
    pub fn new(
        plan: &'p SimulationPlan<'r>,
        container: &str,
        at_ms: u64,
        limits: HostLimits,
    ) -> Result<(Self, SimulationAction)> {
        if container.is_empty()
            || container.len() > 128
            || !container
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"-_.".contains(&b))
        {
            return Err(HostError::InvalidInput("simulation container token"));
        }
        let process = plan.process_limits();
        let deadline_ms = at_ms
            .checked_add(process.wall_clock_ms)
            .ok_or(HostError::InvalidInput("simulation clock overflow"))?;
        let stream_budget = process
            .stdout_bytes
            .checked_add(process.stderr_bytes)
            .and_then(|bytes| bytes.checked_add(CONTROL_DIAGNOSTIC_LIMIT))
            .and_then(|bytes| bytes.checked_add(plan.request().stdin_bytes().len()))
            .ok_or(HostError::ResourceLimit("controller stream budget"))?;
        if limits.stream_bytes < stream_budget {
            return Err(HostError::ResourceLimit("controller stream budget"));
        }
        if limits.control_diagnostic_bytes != CONTROL_DIAGNOSTIC_LIMIT || limits.failure_facts < 1 {
            return Err(HostError::ResourceLimit("controller observation budget"));
        }
        let token = SimulationToken {
            plan_digest: plan.artifact_digest().to_owned(),
            request_digest: plan.request().artifact_digest().to_owned(),
            container: container.to_owned(),
        };
        let mut controller = Self {
            plan,
            token,
            limits,
            phase: Phase::Create,
            started_at_ms: at_ms,
            deadline_ms,
            last_ms: at_ms,
            started: false,
            failed: false,
            exit: None,
            cleanup: CleanupStatus::Unknown,
            streams: SeparatedStreams::new(),
            diagnostics: Vec::new(),
            diagnostics_exceeded: false,
            failures: Vec::new(),
            exhausted: false,
        };
        controller.diagnostic(b"simulation-container", container.as_bytes());
        let action = controller.action(SimulationActionKind::Create);
        Ok((controller, action))
    }

    pub fn token(&self) -> &SimulationToken {
        &self.token
    }
    pub fn started(&self) -> bool {
        self.started
    }
    pub fn failures(&self) -> &[FailureFact] {
        &self.failures
    }
    pub fn streams(&self) -> &SeparatedStreams {
        &self.streams
    }
    pub fn control_diagnostics(&self) -> &[u8] {
        &self.diagnostics
    }
    fn action(&self, kind: SimulationActionKind) -> SimulationAction {
        SimulationAction {
            token: self.token.clone(),
            kind,
        }
    }
    fn stage(&self) -> ObservationStage {
        match self.phase {
            Phase::Create => ObservationStage::Create,
            Phase::Attach => ObservationStage::Attach,
            Phase::Start => ObservationStage::Start,
            Phase::Stdin | Phase::StdinEof => ObservationStage::Stdin,
            Phase::Running | Phase::Drain => ObservationStage::Capture,
            Phase::Inspect => ObservationStage::Inspect,
            Phase::Terminate => ObservationStage::Terminate,
            Phase::EmptyTree | Phase::Cleanup => ObservationStage::Cleanup,
            Phase::Finalizable => ObservationStage::Publish,
        }
    }
    fn fact(&mut self, kind: FailureKind) {
        let fact = FailureFact {
            kind,
            stage: self.stage(),
            at_ms: self.last_ms - self.started_at_ms,
        };
        if !self.failures.contains(&fact) {
            if self.failures.len() >= self.limits.failure_facts {
                self.exhausted = true;
                return;
            }
            self.failures.push(fact);
        }
    }
    /// Length-prefixed records retain arbitrary diagnostic bytes without
    /// treating them as solver output or letting them escape the fixed budget.
    fn diagnostic(&mut self, label: &[u8], bytes: &[u8]) {
        for part in [
            label,
            b":",
            bytes.len().to_string().as_bytes(),
            b":",
            bytes,
            b"\n",
        ] {
            let remaining = CONTROL_DIAGNOSTIC_LIMIT - self.diagnostics.len();
            self.diagnostics
                .extend_from_slice(&part[..part.len().min(remaining)]);
            if part.len() > remaining {
                self.diagnostics_exceeded = true;
                break;
            }
        }
    }
    fn stop(&mut self, actions: &mut Vec<SimulationAction>) {
        let already_failed = self.failed;
        self.failed = true;
        if !(matches!(
            self.phase,
            Phase::Terminate | Phase::EmptyTree | Phase::Cleanup | Phase::Finalizable
        ) || already_failed && self.phase == Phase::Inspect)
        {
            self.phase = Phase::Terminate;
            actions.push(self.action(SimulationActionKind::TerminateTree));
        }
    }
    fn reject(&mut self, reason: Rejection, update: &mut SimulationTransition) {
        self.fact(FailureKind::InvalidSequence);
        self.diagnostic(b"rejected", format!("{reason:?}").as_bytes());
        update.rejection = Some(reason);
        self.stop(&mut update.actions);
    }
    fn next(
        &mut self,
        phase: Phase,
        kind: SimulationActionKind,
        update: &mut SimulationTransition,
    ) {
        self.phase = phase;
        update.actions.push(self.action(kind));
    }
    fn capture_ready(&self) -> bool {
        self.streams.stream(StreamKind::Stdout).complete()
            && self.streams.stream(StreamKind::Stderr).complete()
    }
    fn allow_capture(&self) -> bool {
        !self.failed
            && matches!(
                self.phase,
                Phase::Stdin | Phase::StdinEof | Phase::Running | Phase::Inspect | Phase::Drain
            )
    }
    fn expected_operation(&self) -> Option<ControlOperation> {
        Some(match self.phase {
            Phase::Create => ControlOperation::Create,
            Phase::Attach => ControlOperation::Attach,
            Phase::Start => ControlOperation::Start,
            Phase::Stdin | Phase::StdinEof => ControlOperation::Stdin,
            Phase::Running | Phase::Drain => ControlOperation::Wait,
            Phase::Inspect => ControlOperation::Inspect,
            Phase::Terminate => ControlOperation::Terminate,
            Phase::EmptyTree => ControlOperation::EmptyTree,
            Phase::Cleanup => ControlOperation::Cleanup,
            Phase::Finalizable => return None,
        })
    }
    fn deadline(&mut self, actions: &mut Vec<SimulationAction>) {
        if self.last_ms >= self.deadline_ms
            && !self
                .failures
                .iter()
                .any(|f| f.kind == FailureKind::Deadline)
        {
            self.fact(FailureKind::Deadline);
            self.stop(actions);
        }
    }

    pub fn advance(&mut self, event: SimulationEvent) -> SimulationTransition {
        let mut update = SimulationTransition::default();
        // Exhausted observation storage must never suppress termination and
        // cleanup intents. The final record still fails with ResourceLimit.
        if event.token != self.token {
            self.reject(Rejection::Binding, &mut update);
            return update;
        }
        if event.at_ms < self.last_ms {
            self.reject(Rejection::ClockRollback, &mut update);
            return update;
        }
        self.last_ms = event.at_ms;
        match event.kind {
            SimulationEventKind::Created if self.phase == Phase::Create => self.next(
                Phase::Attach,
                SimulationActionKind::AttachSeparatedStreams,
                &mut update,
            ),
            SimulationEventKind::Attached if self.phase == Phase::Attach => {
                self.next(Phase::Start, SimulationActionKind::Start, &mut update)
            }
            SimulationEventKind::Started if self.phase == Phase::Start => {
                self.started = true;
                self.next(
                    Phase::Stdin,
                    SimulationActionKind::SendExactStdin(
                        self.plan.request().stdin_bytes().to_vec(),
                    ),
                    &mut update,
                );
            }
            SimulationEventKind::StdinWritten(bytes) if self.phase == Phase::Stdin => {
                if bytes != self.plan.request().stdin_bytes() {
                    self.reject(Rejection::StdinMismatch, &mut update);
                } else {
                    self.next(
                        Phase::StdinEof,
                        SimulationActionKind::CloseStdin,
                        &mut update,
                    );
                }
            }
            SimulationEventKind::StdinClosed if self.phase == Phase::StdinEof => {
                self.next(Phase::Running, SimulationActionKind::Wait, &mut update)
            }
            SimulationEventKind::Output { stdout, stderr } if self.allow_capture() => {
                for (kind, bytes) in [(StreamKind::Stdout, stdout), (StreamKind::Stderr, stderr)] {
                    if bytes.is_empty() {
                        continue;
                    }
                    match self.streams.push(kind, &bytes) {
                        Ok(()) => (),
                        Err(TransportError::StreamLimit(StreamKind::Stdout)) => {
                            self.fact(FailureKind::StdoutLimit)
                        }
                        Err(TransportError::StreamLimit(StreamKind::Stderr)) => {
                            self.fact(FailureKind::StderrLimit)
                        }
                        Err(error) => {
                            update.rejection = Some(Rejection::Sequence);
                            self.fact(FailureKind::Transport);
                            self.diagnostic(b"capture-error", format!("{error:?}").as_bytes());
                        }
                    }
                }
                if !self.failures.is_empty() {
                    self.stop(&mut update.actions);
                }
            }
            SimulationEventKind::StreamsClosed { stdout, stderr }
                if self.allow_capture() && (stdout || stderr) =>
            {
                for (kind, close) in [(StreamKind::Stdout, stdout), (StreamKind::Stderr, stderr)] {
                    if close && let Err(error) = self.streams.eof(kind) {
                        update.rejection = Some(Rejection::Sequence);
                        self.fact(FailureKind::Transport);
                        self.diagnostic(b"stream-eof-error", format!("{error:?}").as_bytes());
                    }
                }
                if !self.failures.is_empty() {
                    self.stop(&mut update.actions);
                } else if self.phase == Phase::Drain && self.capture_ready() {
                    self.next(
                        Phase::EmptyTree,
                        SimulationActionKind::ConfirmEmptyTree,
                        &mut update,
                    );
                }
            }
            SimulationEventKind::Exit(exit)
                if self.started
                    && self.exit.is_none()
                    && (self.phase == Phase::Running
                        || (self.failed
                            && matches!(self.phase, Phase::Terminate | Phase::Inspect))) =>
            {
                self.exit = Some(exit);
                if self.phase == Phase::Running {
                    self.next(Phase::Inspect, SimulationActionKind::Inspect, &mut update);
                }
            }
            SimulationEventKind::Inspected if self.phase == Phase::Inspect => {
                if self.failed || self.capture_ready() {
                    self.next(
                        Phase::EmptyTree,
                        SimulationActionKind::ConfirmEmptyTree,
                        &mut update,
                    );
                } else {
                    self.phase = Phase::Drain;
                }
            }
            SimulationEventKind::OomKilled
                if self.started
                    && self.phase != Phase::Finalizable
                    && !self.failures.iter().any(|f| f.kind == FailureKind::Memory) =>
            {
                self.fact(FailureKind::Memory);
                self.stop(&mut update.actions);
            }
            SimulationEventKind::Interrupted(reason) if self.phase != Phase::Finalizable => {
                self.fact(FailureKind::Interrupted);
                self.diagnostic(b"interrupted", &reason);
                self.stop(&mut update.actions);
            }
            SimulationEventKind::TransportFailed(reason) if self.phase != Phase::Finalizable => {
                self.fact(FailureKind::Transport);
                self.diagnostic(b"transport-failed", &reason);
                self.stop(&mut update.actions);
            }
            SimulationEventKind::ControlFailed {
                operation,
                diagnostic,
            } if self.expected_operation() == Some(operation) => {
                let previously_failed = self.failed;
                self.fact(FailureKind::Control);
                self.diagnostic(format!("control-{operation:?}").as_bytes(), &diagnostic);
                self.failed = true;
                match self.phase {
                    Phase::Terminate => {
                        self.next(Phase::Inspect, SimulationActionKind::Inspect, &mut update)
                    }
                    Phase::Inspect if !previously_failed => self.next(
                        Phase::Terminate,
                        SimulationActionKind::TerminateTree,
                        &mut update,
                    ),
                    Phase::Inspect => self.next(
                        Phase::EmptyTree,
                        SimulationActionKind::ConfirmEmptyTree,
                        &mut update,
                    ),
                    Phase::EmptyTree => {
                        self.cleanup = CleanupStatus::Unknown;
                        self.fact(FailureKind::Cleanup);
                        self.phase = Phase::Finalizable;
                    }
                    Phase::Cleanup => {
                        self.cleanup = CleanupStatus::Failed;
                        self.fact(FailureKind::Cleanup);
                        self.phase = Phase::Finalizable;
                    }
                    _ => self.stop(&mut update.actions),
                }
            }
            SimulationEventKind::DeadlineTick => (),
            SimulationEventKind::TreeTerminated if self.phase == Phase::Terminate => {
                self.next(Phase::Inspect, SimulationActionKind::Inspect, &mut update)
            }
            SimulationEventKind::TreeEmpty if self.phase == Phase::EmptyTree => {
                self.next(Phase::Cleanup, SimulationActionKind::Cleanup, &mut update)
            }
            SimulationEventKind::TreeNotEmpty if self.phase == Phase::EmptyTree => {
                self.cleanup = CleanupStatus::Failed;
                self.fact(FailureKind::Cleanup);
                self.failed = true;
                self.phase = Phase::Finalizable;
            }
            SimulationEventKind::Cleaned if self.phase == Phase::Cleanup => {
                self.cleanup = CleanupStatus::ConfirmedEmpty;
                self.phase = Phase::Finalizable;
            }
            SimulationEventKind::CleanupFailed(reason) if self.phase == Phase::Cleanup => {
                self.cleanup = CleanupStatus::Failed;
                self.fact(FailureKind::Cleanup);
                self.diagnostic(b"cleanup-failed", &reason);
                self.failed = true;
                self.phase = Phase::Finalizable;
            }
            _ => self.reject(Rejection::Sequence, &mut update),
        }
        // Retain observations that actually arrived at the boundary (including
        // Started and control failure), then suppress forward execution intents.
        // A deadline may only emit termination and the cleanup tail.
        self.deadline(&mut update.actions);
        if self.last_ms >= self.deadline_ms {
            let terminating = update
                .actions
                .iter()
                .any(|a| a.kind == SimulationActionKind::TerminateTree);
            update.actions.retain(|action| {
                matches!(
                    action.kind,
                    SimulationActionKind::TerminateTree
                        | SimulationActionKind::ConfirmEmptyTree
                        | SimulationActionKind::Cleanup
                ) || (!terminating && action.kind == SimulationActionKind::Inspect)
            });
        }
        if self.diagnostics_exceeded
            && !self.failures.iter().any(|f| f.kind == FailureKind::Control)
        {
            self.fact(FailureKind::Control);
            self.stop(&mut update.actions);
        }
        if self.exhausted {
            update.rejection = Some(Rejection::Budget);
        }
        update
    }

    /// Consumes the one-shot controller. Missing events remain failures; this
    /// method cannot fabricate successful exit, stream EOF, or cleanup. It only
    /// publishes a failed record for an unfinished tail; it executes no cleanup.
    pub fn finish(mut self, at_ms: u64) -> Result<SimulationObservation> {
        if at_ms < self.last_ms {
            self.fact(FailureKind::InvalidSequence);
        } else {
            self.last_ms = at_ms;
        }
        let mut unused_actions = Vec::new();
        self.deadline(&mut unused_actions);
        if self.phase != Phase::Finalizable {
            self.fact(FailureKind::InvalidSequence);
        }
        if self.exit.is_none() || self.exit == Some(ProcessExit::Unavailable) {
            self.fact(FailureKind::MissingExit);
        }
        if self.cleanup != CleanupStatus::ConfirmedEmpty {
            self.fact(FailureKind::Cleanup);
        }
        if self.exhausted {
            return Err(HostError::ResourceLimit("controller failure facts"));
        }
        let stdout = self.streams.stream(StreamKind::Stdout);
        let stderr = self.streams.stream(StreamKind::Stderr);
        SimulationObservation::new(
            self.plan,
            SimulationObservationInput {
                stdout: SimulationStreamInput {
                    bytes: stdout.bytes(),
                    observed_bytes: usize::try_from(stdout.observed_bytes())
                        .map_err(|_| HostError::ResourceLimit("stdout observed bytes"))?,
                    complete: stdout.complete(),
                    exceeded: stdout.exceeded(),
                },
                stderr: SimulationStreamInput {
                    bytes: stderr.bytes(),
                    observed_bytes: usize::try_from(stderr.observed_bytes())
                        .map_err(|_| HostError::ResourceLimit("stderr observed bytes"))?,
                    complete: stderr.complete(),
                    exceeded: stderr.exceeded(),
                },
                control_diagnostics: SimulationStreamInput {
                    bytes: &self.diagnostics,
                    observed_bytes: self.diagnostics.len() + usize::from(self.diagnostics_exceeded),
                    complete: !self.diagnostics_exceeded,
                    exceeded: self.diagnostics_exceeded,
                },
                exit: self.exit.unwrap_or(ProcessExit::Unavailable),
                started: self.started,
                elapsed_ms: self.last_ms - self.started_at_ms,
                cleanup: self.cleanup,
                failures: &self.failures,
            },
            self.limits,
        )
    }
}
