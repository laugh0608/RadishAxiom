//! 只从既有 immutable 请求构造模拟计划；不接受字符串 argv 或调用方资源替换。
use crate::{
    HostError, HostLimits, Result, SimulationIdentity, compare, encoding::Writer, raw_digest,
};
use radishaxiom_ir::solver::{SolverProcessLimits, SolverProfile, SolverRequest};

pub struct SimulationPlan<'r> {
    request: &'r SolverRequest,
    bytes: Vec<u8>,
    digest: String,
    identity_digest: String,
}
impl<'r> SimulationPlan<'r> {
    pub fn new(
        request: &'r SolverRequest,
        identity: &SimulationIdentity,
        limits: HostLimits,
    ) -> Result<Self> {
        if request.profile() != SolverProfile::Cvc5Query0_3ModelV0_1 {
            return Err(HostError::BindingMismatch("profile"));
        }
        let tool = request.tool();
        if tool.platform() != "linux-arm64" {
            return Err(HostError::BindingMismatch("tool.platform"));
        }
        // 旧 payload 字段一直标识 ZIP，CLI 单独绑定，不能重解释旧请求。
        if tool.payload_digest() != identity.archive_raw_digest() {
            return Err(HostError::BindingMismatch("tool.archive"));
        }
        if tool.acceptance_record_digest() != identity.acceptance_raw_digest() {
            return Err(HostError::BindingMismatch("tool.acceptance"));
        }
        let process = request.process_limits();
        if request.stdin_bytes().len() > process.stdin_bytes {
            return Err(HostError::ResourceLimit("stdin_bytes"));
        }
        // 复制前检查整个源；生成器已 strict 建立 query/profile/limits/args，外层不另写 parser。
        if request.canonical_bytes().len() > limits.record_bytes
            || request.stdin_bytes().len() > limits.stream_bytes
        {
            return Err(HostError::ResourceLimit("request_bytes"));
        }
        if raw_digest(request.canonical_bytes()) != request.artifact_digest()
            || raw_digest(request.stdin_bytes()) != request.query().artifact_digest()
        {
            return Err(HostError::BindingMismatch("request"));
        }
        let mut out = Writer::new(limits.record_bytes);
        out.raw(b"{")?;
        out.field("format", "axiom-solver-simulation-plan")?;
        out.raw(b",")?;
        out.field("version", "0.1")?;
        out.raw(b",")?;
        out.field("scope", "simulation")?;
        out.raw(b",")?;
        out.field("real_execution", "blocked-E0-E3")?;
        out.raw(b",")?;
        out.field("identity_record_raw_digest", identity.artifact_digest())?;
        out.raw(b",")?;
        out.field("archive_raw_digest", identity.archive_raw_digest())?;
        out.raw(b",")?;
        out.field("cli_raw_digest", identity.cli_raw_digest())?;
        out.raw(b",")?;
        out.field("acceptance_raw_digest", identity.acceptance_raw_digest())?;
        out.raw(b",")?;
        out.field("request_raw_digest", request.artifact_digest())?;
        out.raw(b",")?;
        out.key("request_raw_hex")?;
        out.hex(request.canonical_bytes())?;
        out.raw(b",")?;
        out.field("profile", request.profile().as_str())?;
        out.raw(b",")?;
        out.field("query_raw_digest", request.query().artifact_digest())?;
        out.raw(b",")?;
        out.key("stdin_raw_hex")?;
        out.hex(request.stdin_bytes())?;
        out.raw(b",")?;
        out.field("stdin_protocol", "query-bytes-then-eof")?;
        out.raw(b",")?;
        out.field("attempts", "1")?;
        out.raw(b",")?;
        out.key("environment")?;
        out.raw(b"[]")?;
        out.raw(b",")?;
        out.key("argument_tokens")?;
        out.raw(b"[")?;
        for (i, argument) in request.argument_tokens().iter().enumerate() {
            if i != 0 {
                out.raw(b",")?;
            }
            out.string(argument)?;
        }
        out.raw(b"],")?;
        out.key("limits")?;
        emit_limits(&mut out, process)?;
        out.raw(b"}")?;
        let bytes = out.finish(limits)?;
        let digest = raw_digest(&bytes);
        Ok(Self {
            request,
            bytes,
            digest,
            identity_digest: identity.artifact_digest().to_owned(),
        })
    }
    pub fn request(&self) -> &'r SolverRequest {
        self.request
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
    pub fn identity_digest(&self) -> &str {
        &self.identity_digest
    }
    pub fn process_limits(&self) -> SolverProcessLimits {
        self.request.process_limits()
    }
    pub fn argument_tokens(&self) -> &'static [&'static str] {
        self.request.argument_tokens()
    }
}

fn emit_limits(out: &mut Writer, p: SolverProcessLimits) -> Result<()> {
    out.raw(b"{")?;
    for (i, (key, value)) in [
        ("stdin_bytes", p.stdin_bytes.to_string()),
        ("stdout_bytes", p.stdout_bytes.to_string()),
        ("stderr_bytes", p.stderr_bytes.to_string()),
        ("wall_clock_ms", p.wall_clock_ms.to_string()),
        ("working_memory_bytes", p.working_memory_bytes.to_string()),
        ("semantic_steps", p.semantic_steps.to_string()),
        (
            "internal_wall_clock_ms",
            p.internal_wall_clock_ms.to_string(),
        ),
        ("memory_swap_max", "0".to_owned()),
    ]
    .into_iter()
    .enumerate()
    {
        if i != 0 {
            out.raw(b",")?;
        }
        out.field(key, &value)?;
    }
    out.raw(b"}")
}

pub fn check_simulation_plan<'r>(
    bytes: &[u8],
    request: &'r SolverRequest,
    identity: &SimulationIdentity,
    limits: HostLimits,
) -> Result<SimulationPlan<'r>> {
    if bytes.len() > limits.record_bytes {
        return Err(HostError::ResourceLimit("record_bytes"));
    }
    let plan = SimulationPlan::new(request, identity, limits)?;
    compare(bytes, plan.canonical_bytes(), "simulation-plan", limits)?;
    Ok(plan)
}
