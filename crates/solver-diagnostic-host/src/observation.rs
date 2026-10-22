//! simulation 观察闭合记录。完整字节与前缀有不同摘要字段，任何失败都拒绝正常 P4 适配。
use crate::{
    HostError, HostLimits, Result, SimulationPlan, checked_size, compare, encoding::Writer,
    raw_digest,
};
use radishaxiom_ir::solver::{
    OuterTermination, ProcessExit, SolverResponseInput, TransportSummary,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub enum ObservationStage {
    Plan,
    Create,
    Attach,
    Start,
    Stdin,
    Capture,
    Wait,
    Inspect,
    Terminate,
    Cleanup,
    Publish,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub enum FailureKind {
    Deadline,
    Memory,
    StdoutLimit,
    StderrLimit,
    Crash,
    Transport,
    Control,
    Interrupted,
    Cleanup,
    MissingExit,
    InvalidSequence,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FailureFact {
    pub kind: FailureKind,
    pub stage: ObservationStage,
    pub at_ms: u64,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CleanupStatus {
    ConfirmedEmpty,
    Failed,
    Unknown,
    NotStarted,
}
#[derive(Clone, Copy)]
pub struct SimulationStreamInput<'a> {
    pub bytes: &'a [u8],
    /// 完整流为精确长度；前缀为至少已观察到的字节数。N+1 是超限最小观察。
    pub observed_bytes: usize,
    pub complete: bool,
    pub exceeded: bool,
}
#[derive(Clone, Copy)]
pub struct SimulationObservationInput<'a> {
    pub stdout: SimulationStreamInput<'a>,
    pub stderr: SimulationStreamInput<'a>,
    pub control_diagnostics: SimulationStreamInput<'a>,
    pub exit: ProcessExit,
    pub started: bool,
    pub elapsed_ms: u64,
    pub cleanup: CleanupStatus,
    pub failures: &'a [FailureFact],
}
struct Stream {
    bytes: Vec<u8>,
    complete: bool,
    exceeded: bool,
    observed: usize,
}
impl Stream {
    fn copy(input: SimulationStreamInput<'_>) -> Self {
        Self {
            bytes: input.bytes.to_vec(),
            complete: input.complete,
            exceeded: input.exceeded,
            observed: input.observed_bytes,
        }
    }
}

pub struct SimulationObservation {
    bytes: Vec<u8>,
    digest: String,
    request: String,
    plan: String,
    stdout: Stream,
    stderr: Stream,
    diagnostics: Stream,
    exit: ProcessExit,
    started: bool,
    elapsed_ms: u64,
    cleanup: CleanupStatus,
    failures: Vec<FailureFact>,
    primary: OuterTermination,
}
impl SimulationObservation {
    pub fn new(
        plan: &SimulationPlan<'_>,
        input: SimulationObservationInput<'_>,
        limits: HostLimits,
    ) -> Result<Self> {
        let process = plan.process_limits();
        validate_stream(input.stdout, process.stdout_bytes)?;
        validate_stream(input.stderr, process.stderr_bytes)?;
        validate_stream(input.control_diagnostics, limits.control_diagnostic_bytes)?;
        let total = checked_size(
            input.stdout.bytes.len(),
            input.stderr.bytes.len(),
            limits.stream_bytes,
            "stream_bytes",
        )?;
        checked_size(
            total,
            input.control_diagnostics.bytes.len(),
            limits.stream_bytes,
            "stream_bytes",
        )?;
        if input.failures.len() > limits.failure_facts {
            return Err(HostError::ResourceLimit("failure_facts"));
        }
        if input.failures.iter().any(|f| f.at_ms > input.elapsed_ms) {
            return Err(HostError::InvalidInput("failure after observation"));
        }
        if input
            .failures
            .iter()
            .any(|f| f.kind == FailureKind::Deadline && f.at_ms < process.wall_clock_ms)
        {
            return Err(HostError::InvalidInput("early deadline"));
        }
        if input.elapsed_ms >= process.wall_clock_ms
            && !input
                .failures
                .iter()
                .any(|f| f.kind == FailureKind::Deadline)
        {
            return Err(HostError::InvalidInput("missing deadline fact"));
        }
        if input.stdout.exceeded
            && !input
                .failures
                .iter()
                .any(|f| f.kind == FailureKind::StdoutLimit)
            || input.stderr.exceeded
                && !input
                    .failures
                    .iter()
                    .any(|f| f.kind == FailureKind::StderrLimit)
        {
            return Err(HostError::InvalidInput("missing stream-limit fact"));
        }
        if !input.started
            && (input.exit != ProcessExit::Unavailable
                || !input.stdout.bytes.is_empty()
                || !input.stderr.bytes.is_empty())
        {
            return Err(HostError::InvalidInput("unstarted process observations"));
        }
        if input.started && input.cleanup == CleanupStatus::NotStarted {
            return Err(HostError::InvalidInput("started cleanup"));
        }
        let has = |kind| input.failures.iter().any(|fact| fact.kind == kind);
        if matches!(
            input.cleanup,
            CleanupStatus::Failed | CleanupStatus::Unknown
        ) && !has(FailureKind::Cleanup)
        {
            return Err(HostError::InvalidInput("missing cleanup fact"));
        }
        if (input.exit == ProcessExit::Unavailable) != has(FailureKind::MissingExit) {
            return Err(HostError::InvalidInput("missing-exit fact mismatch"));
        }
        if input.control_diagnostics.exceeded && !has(FailureKind::Control) {
            return Err(HostError::InvalidInput("missing control-limit fact"));
        }
        if !input.started && has(FailureKind::Memory) {
            return Err(HostError::InvalidInput("memory fact before start"));
        }
        // 预算已检查后才复制和排序。拒绝重复事实以免计数与时间线被不透明合并。
        let mut failures = input.failures.to_vec();
        failures.sort_by_key(|f| (f.at_ms, f.kind, f.stage));
        if failures.windows(2).any(|v| v[0] == v[1]) {
            return Err(HostError::InvalidInput("duplicate failure fact"));
        }
        let primary = failures
            .first()
            .map(|f| f.kind.outer())
            .unwrap_or(OuterTermination::None);
        let mut out = Writer::new(limits.record_bytes);
        out.raw(b"{")?;
        out.field("format", "axiom-solver-simulation-observation")?;
        out.raw(b",")?;
        out.field("version", "0.1")?;
        out.raw(b",")?;
        out.field("scope", "simulation")?;
        out.raw(b",")?;
        out.field("source", "simulation-not-authenticated-capture")?;
        out.raw(b",")?;
        out.field("plan_record_raw_digest", plan.artifact_digest())?;
        out.raw(b",")?;
        out.field("identity_record_raw_digest", plan.identity_digest())?;
        out.raw(b",")?;
        out.field("request_raw_digest", plan.request().artifact_digest())?;
        out.raw(b",")?;
        out.field("query_raw_digest", plan.request().query().artifact_digest())?;
        out.raw(b",")?;
        out.key("started")?;
        out.boolean(input.started)?;
        out.raw(b",")?;
        out.field("elapsed_ms", &input.elapsed_ms.to_string())?;
        out.raw(b",")?;
        out.field("cleanup", input.cleanup.name())?;
        out.raw(b",")?;
        out.field("primary_outer", outer_name(primary))?;
        out.raw(b",")?;
        out.key("exit")?;
        emit_exit(&mut out, input.exit)?;
        out.raw(b",")?;
        out.key("stdout")?;
        emit_stream(&mut out, input.stdout)?;
        out.raw(b",")?;
        out.key("stderr")?;
        emit_stream(&mut out, input.stderr)?;
        out.raw(b",")?;
        out.key("control_diagnostics")?;
        emit_stream(&mut out, input.control_diagnostics)?;
        out.raw(b",")?;
        out.key("failures")?;
        out.raw(b"[")?;
        for (i, fact) in failures.iter().enumerate() {
            if i != 0 {
                out.raw(b",")?;
            }
            out.raw(b"{")?;
            out.field("kind", fact.kind.name())?;
            out.raw(b",")?;
            out.field("stage", fact.stage.name())?;
            out.raw(b",")?;
            out.field("at_ms", &fact.at_ms.to_string())?;
            out.raw(b"}")?;
        }
        out.raw(b"]}")?;
        let bytes = out.finish(limits)?;
        let digest = raw_digest(&bytes);
        Ok(Self {
            bytes,
            digest,
            request: plan.request().artifact_digest().to_owned(),
            plan: plan.artifact_digest().to_owned(),
            stdout: Stream::copy(input.stdout),
            stderr: Stream::copy(input.stderr),
            diagnostics: Stream::copy(input.control_diagnostics),
            exit: input.exit,
            started: input.started,
            elapsed_ms: input.elapsed_ms,
            cleanup: input.cleanup,
            failures,
            primary,
        })
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
    pub fn request_digest(&self) -> &str {
        &self.request
    }
    pub fn plan_digest(&self) -> &str {
        &self.plan
    }
    pub fn stdout_bytes(&self) -> &[u8] {
        &self.stdout.bytes
    }
    pub fn stderr_bytes(&self) -> &[u8] {
        &self.stderr.bytes
    }
    pub fn control_diagnostics(&self) -> &[u8] {
        &self.diagnostics.bytes
    }
    pub fn stdout_complete(&self) -> bool {
        self.stdout.complete
    }
    pub fn stderr_complete(&self) -> bool {
        self.stderr.complete
    }
    pub fn stdout_exceeded(&self) -> bool {
        self.stdout.exceeded
    }
    pub fn stderr_exceeded(&self) -> bool {
        self.stderr.exceeded
    }
    pub fn stdout_observed_bytes(&self) -> usize {
        self.stdout.observed
    }
    pub fn stderr_observed_bytes(&self) -> usize {
        self.stderr.observed
    }
    pub fn exit(&self) -> ProcessExit {
        self.exit
    }
    pub fn started(&self) -> bool {
        self.started
    }
    pub fn elapsed_ms(&self) -> u64 {
        self.elapsed_ms
    }
    pub fn cleanup_status(&self) -> CleanupStatus {
        self.cleanup
    }
    pub fn failures(&self) -> &[FailureFact] {
        &self.failures
    }
    pub fn primary_outer(&self) -> OuterTermination {
        self.primary
    }
    pub fn p4_transport_summary(&self) -> TransportSummary {
        TransportSummary {
            exit: self.exit,
            outer_termination: self.primary,
            stdout_complete: self.stdout.complete,
            stderr_complete: self.stderr.complete,
            stdout_bytes: self.stdout.bytes.len(),
            stderr_bytes: self.stderr.bytes.len(),
            stdout_exceeded: self.stdout.exceeded,
            stderr_exceeded: self.stderr.exceeded,
        }
    }
    /// 只适配没有外层失败的模拟字节；返回值依然不认证真实进程来源。
    pub fn simulation_response_input(&self) -> Result<SolverResponseInput<'_>> {
        if !self.started
            || self.exit != ProcessExit::Exited(0)
            || self.cleanup != CleanupStatus::ConfirmedEmpty
            || !self.failures.is_empty()
            || !self.stdout.complete
            || !self.stderr.complete
            || !self.diagnostics.complete
            || self.stdout.exceeded
            || self.stderr.exceeded
            || self.diagnostics.exceeded
        {
            return Err(HostError::SimulationFailure);
        }
        Ok(SolverResponseInput {
            request_digest: &self.request,
            stdout: &self.stdout.bytes,
            stderr: &self.stderr.bytes,
            stdout_complete: true,
            stderr_complete: true,
            exit: self.exit,
            outer_termination: OuterTermination::None,
        })
    }
}

fn validate_stream(input: SimulationStreamInput<'_>, cap: usize) -> Result<()> {
    if input.bytes.len() > cap {
        return Err(HostError::ResourceLimit("captured_stream_bytes"));
    }
    let valid = if input.exceeded {
        !input.complete && input.bytes.len() == cap && input.observed_bytes > cap
    } else {
        input.observed_bytes == input.bytes.len()
    };
    if !valid {
        return Err(HostError::InvalidInput(
            "stream completeness or observed length",
        ));
    }
    Ok(())
}
fn emit_stream(out: &mut Writer, stream: SimulationStreamInput<'_>) -> Result<()> {
    out.raw(b"{")?;
    out.field(
        "kind",
        if stream.complete {
            "complete"
        } else {
            "prefix"
        },
    )?;
    out.raw(b",")?;
    out.key("complete")?;
    out.boolean(stream.complete)?;
    out.raw(b",")?;
    out.key("exceeded")?;
    out.boolean(stream.exceeded)?;
    out.raw(b",")?;
    out.field("captured_bytes", &stream.bytes.len().to_string())?;
    out.raw(b",")?;
    out.field(
        "observed_bytes_lower_bound",
        &stream.observed_bytes.to_string(),
    )?;
    out.raw(b",")?;
    out.field(
        if stream.complete {
            "full_raw_digest"
        } else {
            "prefix_raw_digest"
        },
        &raw_digest(stream.bytes),
    )?;
    out.raw(b",")?;
    out.key("raw_hex")?;
    out.hex(stream.bytes)?;
    out.raw(b"}")
}
fn emit_exit(out: &mut Writer, exit: ProcessExit) -> Result<()> {
    out.raw(b"{")?;
    match exit {
        ProcessExit::Exited(code) => {
            out.field("kind", "exited")?;
            out.raw(b",")?;
            out.field("code", &code.to_string())?;
        }
        ProcessExit::Signaled(code) => {
            out.field("kind", "signaled")?;
            out.raw(b",")?;
            out.field("code", &code.to_string())?;
        }
        ProcessExit::Unavailable => out.field("kind", "unavailable")?,
    }
    out.raw(b"}")
}
impl FailureKind {
    fn name(self) -> &'static str {
        match self {
            Self::Deadline => "deadline",
            Self::Memory => "memory",
            Self::StdoutLimit => "stdout-limit",
            Self::StderrLimit => "stderr-limit",
            Self::Crash => "crash",
            Self::Transport => "transport",
            Self::Control => "control",
            Self::Interrupted => "interrupted",
            Self::Cleanup => "cleanup",
            Self::MissingExit => "missing-exit",
            Self::InvalidSequence => "invalid-sequence",
        }
    }
    fn outer(self) -> OuterTermination {
        match self {
            Self::Deadline => OuterTermination::Deadline,
            Self::Memory => OuterTermination::Memory,
            Self::StdoutLimit => OuterTermination::StdoutLimit,
            Self::StderrLimit => OuterTermination::StderrLimit,
            Self::Crash => OuterTermination::Crash,
            _ => OuterTermination::Unavailable,
        }
    }
}
impl ObservationStage {
    fn name(self) -> &'static str {
        match self {
            Self::Plan => "plan",
            Self::Create => "create",
            Self::Attach => "attach",
            Self::Start => "start",
            Self::Stdin => "stdin",
            Self::Capture => "capture",
            Self::Wait => "wait",
            Self::Inspect => "inspect",
            Self::Terminate => "terminate",
            Self::Cleanup => "cleanup",
            Self::Publish => "publish",
        }
    }
}
impl CleanupStatus {
    fn name(self) -> &'static str {
        match self {
            Self::ConfirmedEmpty => "confirmed-empty",
            Self::Failed => "failed",
            Self::Unknown => "unknown",
            Self::NotStarted => "not-started",
        }
    }
}
fn outer_name(outer: OuterTermination) -> &'static str {
    match outer {
        OuterTermination::None => "none",
        OuterTermination::Deadline => "deadline",
        OuterTermination::Memory => "memory",
        OuterTermination::StdoutLimit => "stdout-limit",
        OuterTermination::StderrLimit => "stderr-limit",
        OuterTermination::Crash => "crash",
        OuterTermination::Unavailable => "unavailable",
    }
}

pub fn check_simulation_observation(
    bytes: &[u8],
    plan: &SimulationPlan<'_>,
    input: SimulationObservationInput<'_>,
    limits: HostLimits,
) -> Result<SimulationObservation> {
    if bytes.len() > limits.record_bytes {
        return Err(HostError::ResourceLimit("record_bytes"));
    }
    let observation = SimulationObservation::new(plan, input, limits)?;
    compare(
        bytes,
        observation.canonical_bytes(),
        "simulation-observation",
        limits,
    )?;
    Ok(observation)
}
