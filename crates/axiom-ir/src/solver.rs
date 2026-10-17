//! ADR 0025 / 0027 的 P4-A 纯组件。请求身份是声明，解析不认证来源，世界候选尚未重放。

mod encoding;
mod layout;
mod order;
mod protocol;
mod request;
#[cfg(test)]
mod tests;
mod world;

use crate::{
    document::CanonicalDocument,
    obligations::ObligationSet,
    query::{
        CompactQueryLimits, EncodedQuery, GeneratorIdentity, QueryBudgets, QueryError, QueryLimits,
        QueryProfile,
    },
};
use std::{collections::BTreeMap, fmt, sync::Arc};

pub const PROFILE: &str = "axiom-p4-cvc5-1.3.4-query0.2-model-v0.1";
pub const COMPACT_PROFILE: &str = "axiom-p4-cvc5-1.3.4-query0.3-model-v0.1";
const COMPACT_RULES: &[u8] =
    include_bytes!("../../../docs/query/p4-request-response-model-v0.2.md");
const RULES: &[u8] = include_bytes!("../../../docs/query/p4-request-response-model-v0.1.md");
const BASE: &[u8] = include_bytes!(
    "../../../contracts/execution-profiles-v0.1/fixtures/positive/cvc5-1.3.4-qf-uflia-v0.1.jcs"
);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SolverProfile {
    Cvc5Query0_2ModelV0_1,
    Cvc5Query0_3ModelV0_1,
}
impl SolverProfile {
    pub fn from_id(id: &str) -> Result<Self> {
        if id == PROFILE {
            Ok(Self::Cvc5Query0_2ModelV0_1)
        } else if id == COMPACT_PROFILE {
            Ok(Self::Cvc5Query0_3ModelV0_1)
        } else {
            Err(SolverError::UnsupportedProfile)
        }
    }
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Cvc5Query0_2ModelV0_1 => PROFILE,
            Self::Cvc5Query0_3ModelV0_1 => COMPACT_PROFILE,
        }
    }
    fn rules(self) -> &'static [u8] {
        match self {
            Self::Cvc5Query0_2ModelV0_1 => RULES,
            Self::Cvc5Query0_3ModelV0_1 => COMPACT_RULES,
        }
    }
}

/// 没有隐式无限值；解析与解码使用请求里绑定的同一组限制。
#[derive(Clone, Copy, Debug)]
pub struct SolverLimits {
    pub query: QueryLimits,
    pub request_bytes: usize,
    pub response_bytes: usize,
    pub symbol_bytes: usize,
    pub layout_bytes: usize,
    pub tokens: usize,
    pub token_bytes: usize,
    pub syntax_nodes: usize,
    pub syntax_depth: usize,
    pub integer_digits: usize,
    pub definitions: usize,
    pub alias_edges: usize,
    pub layout_items: usize,
    pub input_slots: usize,
    pub value_cells: usize,
    pub decode_steps: usize,
    pub text_bytes: usize,
    pub world_bytes: usize,
    pub candidate_bytes: usize,
}
/// 新查询必须由调用方显式给齐 compact 预算；旧入口不补缺省限制。
#[derive(Clone, Copy, Debug)]
pub struct SolverBudgets {
    pub base: SolverLimits,
    pub compact: Option<CompactQueryLimits>,
}
impl SolverLimits {
    pub fn with_compact(self, compact: CompactQueryLimits) -> SolverBudgets {
        SolverBudgets {
            base: self,
            compact: Some(compact),
        }
    }
}
impl From<SolverLimits> for SolverBudgets {
    fn from(base: SolverLimits) -> Self {
        Self {
            base,
            compact: None,
        }
    }
}
impl SolverBudgets {
    fn query(self) -> QueryBudgets {
        QueryBudgets {
            base: self.base.query,
            compact: self.compact,
        }
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SolverStage {
    Request,
    Response,
    Decode,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(usize)]
pub enum SolverResource {
    RequestBytes,
    ResponseBytes,
    SymbolBytes,
    LayoutBytes,
    Tokens,
    TokenBytes,
    SyntaxNodes,
    SyntaxDepth,
    IntegerDigits,
    Definitions,
    AliasEdges,
    LayoutItems,
    InputSlots,
    ValueCells,
    DecodeSteps,
    TextBytes,
    WorldBytes,
    CandidateBytes,
    StdinBytes,
    StdoutBytes,
    StderrBytes,
}
impl SolverLimits {
    fn maximum(self, r: SolverResource) -> usize {
        use SolverResource::*;
        match r {
            RequestBytes => self.request_bytes,
            ResponseBytes => self.response_bytes,
            SymbolBytes => self.symbol_bytes,
            LayoutBytes => self.layout_bytes,
            Tokens => self.tokens,
            TokenBytes => self.token_bytes,
            SyntaxNodes => self.syntax_nodes,
            SyntaxDepth => self.syntax_depth,
            IntegerDigits => self.integer_digits,
            Definitions => self.definitions,
            AliasEdges => self.alias_edges,
            LayoutItems => self.layout_items,
            InputSlots => self.input_slots,
            ValueCells => self.value_cells,
            DecodeSteps => self.decode_steps,
            TextBytes => self.text_bytes,
            WorldBytes => self.world_bytes,
            CandidateBytes => self.candidate_bytes,
            StdinBytes => PROCESS_LIMITS.stdin_bytes,
            StdoutBytes => PROCESS_LIMITS.stdout_bytes,
            StderrBytes => PROCESS_LIMITS.stderr_bytes,
        }
    }
}
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct SolverUsage {
    counts: [usize; 21],
}
impl SolverUsage {
    pub fn get(&self, r: SolverResource) -> usize {
        self.counts[r as usize]
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SolverError {
    UnsupportedProfile,
    ProfileMismatch,
    InvalidToolIdentity,
    BindingMismatch,
    Query(QueryError),
    ResourceLimit {
        stage: SolverStage,
        resource: SolverResource,
    },
    Transport(TransportSummary),
    Protocol {
        offset: usize,
        reason: &'static str,
        reported_status: Option<SolverStatus>,
    },
    Model {
        offset: usize,
        reason: &'static str,
        reported_status: SolverStatus,
        symbol: String,
    },
    LiteralClassConflict,
    InvalidInput {
        interface: String,
        slot: usize,
        path: Vec<String>,
        reason: &'static str,
    },
    NonCanonical {
        artifact: &'static str,
        offset: usize,
    },
    Internal(&'static str),
}
impl fmt::Display for SolverError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P4-A: {self:?}")
    }
}
impl std::error::Error for SolverError {}
type Result<T> = std::result::Result<T, SolverError>;

struct Budget {
    limits: SolverLimits,
    usage: SolverUsage,
    stage: SolverStage,
}
impl Budget {
    fn new(limits: SolverLimits, stage: SolverStage) -> Self {
        Self {
            limits,
            stage,
            usage: SolverUsage::default(),
        }
    }
    fn error(&self, r: SolverResource) -> SolverError {
        SolverError::ResourceLimit {
            stage: self.stage,
            resource: r,
        }
    }
    fn charge(&mut self, r: SolverResource, n: usize) -> Result<()> {
        let at = r as usize;
        self.usage.counts[at] = self.usage.counts[at]
            .checked_add(n)
            .filter(|v| *v <= self.limits.maximum(r))
            .ok_or_else(|| self.error(r))?;
        Ok(())
    }
    fn observe(&mut self, r: SolverResource, n: usize) -> Result<()> {
        if n > self.limits.maximum(r) {
            return Err(self.error(r));
        }
        self.usage.counts[r as usize] = self.usage.counts[r as usize].max(n);
        Ok(())
    }
    fn step(&mut self) -> Result<()> {
        self.charge(SolverResource::DecodeSteps, 1)
    }
    fn copy(&mut self, s: &str) -> Result<String> {
        self.charge(SolverResource::ValueCells, s.len())?;
        Ok(s.to_owned())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SolverToolIdentity {
    platform: String,
    payload: String,
    acceptance: String,
}
impl SolverToolIdentity {
    pub fn platform(&self) -> &str {
        &self.platform
    }
    pub fn payload_digest(&self) -> &str {
        &self.payload
    }
    pub fn acceptance_record_digest(&self) -> &str {
        &self.acceptance
    }
    pub fn new(
        platform: &str,
        payload_digest: &str,
        acceptance_record_digest: &str,
    ) -> Result<Self> {
        if !matches!(
            platform,
            "macos-arm64"
                | "macos-amd64"
                | "linux-arm64"
                | "linux-amd64"
                | "windows-arm64"
                | "windows-amd64"
        ) || !digest(payload_digest)
            || !digest(acceptance_record_digest)
        {
            return Err(SolverError::InvalidToolIdentity);
        }
        Ok(Self {
            platform: platform.into(),
            payload: payload_digest.into(),
            acceptance: acceptance_record_digest.into(),
        })
    }
}
fn digest(v: &str) -> bool {
    v.strip_prefix("sha256:").is_some_and(|s| {
        s.len() == 64
            && s.bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    })
}

pub struct SolverRequestInput<'a> {
    pub document: &'a CanonicalDocument,
    pub obligations: &'a ObligationSet,
    pub obligation_id: &'a str,
    pub query_profile: QueryProfile,
    pub query: &'a EncodedQuery,
    pub generator: &'a GeneratorIdentity,
    pub tool: &'a SolverToolIdentity,
}
pub struct SolverRequest {
    bytes: Vec<u8>,
    raw_digest: String,
    symbol_bytes: Vec<u8>,
    layout_bytes: Vec<u8>,
    query: EncodedQuery,
    layout: layout::InputLayout,
    catalogue: BTreeMap<String, Sort>,
    limits: SolverLimits,
    budgets: SolverBudgets,
    profile: SolverProfile,
    usage: SolverUsage,
    tool: SolverToolIdentity,
}
/// 固定进程参数的只读元数据，不认证工具或执行宿主。
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SolverProcessLimits {
    pub stdin_bytes: usize,
    pub stdout_bytes: usize,
    pub stderr_bytes: usize,
    pub wall_clock_ms: u64,
    pub working_memory_bytes: usize,
    pub semantic_steps: u64,
    pub internal_wall_clock_ms: u64,
}
pub const PROCESS_LIMITS: SolverProcessLimits = SolverProcessLimits {
    stdin_bytes: 1_048_576,
    stdout_bytes: 4_194_304,
    stderr_bytes: 65_536,
    wall_clock_ms: 6_000,
    working_memory_bytes: 134_217_728,
    semantic_steps: 1_000_000,
    internal_wall_clock_ms: 5_000,
};
const ARGUMENT_TOKENS: [&str; 12] = [
    "--safe-mode=safe",
    "--strict-parsing",
    "--force-logic=QF_UFLIA",
    "--lang=smt2",
    "--no-incremental",
    "--produce-models",
    "--dump-models",
    "--check-models",
    "--produce-proofs",
    "--check-proofs",
    "--rlimit-per=1000000",
    "--tlimit-per=5000",
];
impl SolverRequest {
    pub fn tool(&self) -> &SolverToolIdentity {
        &self.tool
    }
    pub fn argument_tokens(&self) -> &'static [&'static str] {
        &ARGUMENT_TOKENS
    }
    pub fn process_limits(&self) -> SolverProcessLimits {
        PROCESS_LIMITS
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.raw_digest
    }
    pub fn stdin_bytes(&self) -> &[u8] {
        self.query.bytes()
    }
    pub fn symbol_bytes(&self) -> &[u8] {
        &self.symbol_bytes
    }
    pub fn layout_bytes(&self) -> &[u8] {
        &self.layout_bytes
    }
    pub fn query(&self) -> &EncodedQuery {
        &self.query
    }
    pub fn usage(&self) -> &SolverUsage {
        &self.usage
    }
    pub fn profile(&self) -> SolverProfile {
        self.profile
    }
    pub fn budgets(&self) -> SolverBudgets {
        self.budgets
    }
}
pub fn plan_solver_request(
    profile: SolverProfile,
    input: SolverRequestInput<'_>,
    limits: impl Into<SolverBudgets>,
) -> Result<SolverRequest> {
    request::plan(profile, input, limits.into())
}
/// 导出的内部请求必须由原始输入重建，不提供任意反序列化后信任的入口。
pub fn check_solver_request(
    bytes: &[u8],
    profile: SolverProfile,
    input: SolverRequestInput<'_>,
    limits: impl Into<SolverBudgets>,
) -> Result<SolverRequest> {
    let limits = limits.into();
    if bytes.len() > limits.base.request_bytes {
        return Err(SolverError::ResourceLimit {
            stage: SolverStage::Request,
            resource: SolverResource::RequestBytes,
        });
    }
    let request = plan_solver_request(profile, input, limits)?;
    compare(bytes, request.canonical_bytes(), "request")?;
    Ok(request)
}
fn compare(actual: &[u8], expected: &[u8], artifact: &'static str) -> Result<()> {
    if actual == expected {
        return Ok(());
    }
    Err(SolverError::NonCanonical {
        artifact,
        offset: actual
            .iter()
            .zip(expected)
            .position(|(a, b)| a != b)
            .unwrap_or(actual.len().min(expected.len())),
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProcessExit {
    Exited(u32),
    Signaled(u32),
    Unavailable,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OuterTermination {
    None,
    Deadline,
    Memory,
    StdoutLimit,
    StderrLimit,
    Crash,
    Unavailable,
}
impl OuterTermination {
    fn name(self) -> &'static str {
        match self {
            Self::None => "none",
            Self::Deadline => "deadline",
            Self::Memory => "memory",
            Self::StdoutLimit => "stdout-limit",
            Self::StderrLimit => "stderr-limit",
            Self::Crash => "crash",
            Self::Unavailable => "unavailable",
        }
    }
}
pub struct SolverResponseInput<'a> {
    pub request_digest: &'a str,
    pub stdout: &'a [u8],
    pub stderr: &'a [u8],
    pub stdout_complete: bool,
    pub stderr_complete: bool,
    pub exit: ProcessExit,
    pub outer_termination: OuterTermination,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TransportSummary {
    pub exit: ProcessExit,
    pub outer_termination: OuterTermination,
    pub stdout_complete: bool,
    pub stderr_complete: bool,
    pub stdout_bytes: usize,
    pub stderr_bytes: usize,
    pub stdout_exceeded: bool,
    pub stderr_exceeded: bool,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransportReason {
    Outer(OuterTermination),
    Exit(ProcessExit),
    StdoutLimit,
    StderrLimit,
    IncompleteStreams,
}
impl TransportSummary {
    pub fn primary_reason(&self) -> Option<TransportReason> {
        if self.outer_termination != OuterTermination::None {
            Some(TransportReason::Outer(self.outer_termination))
        } else if self.exit != ProcessExit::Exited(0) {
            Some(TransportReason::Exit(self.exit))
        } else if self.stdout_exceeded {
            Some(TransportReason::StdoutLimit)
        } else if self.stderr_exceeded {
            Some(TransportReason::StderrLimit)
        } else if !self.stdout_complete || !self.stderr_complete {
            Some(TransportReason::IncompleteStreams)
        } else {
            None
        }
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SolverStatus {
    Sat,
    Unsat,
    Unknown,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Sort {
    Bool,
    Int,
    Text,
}
impl Sort {
    fn parse(v: &str) -> Result<Self> {
        match v {
            "Bool" => Ok(Self::Bool),
            "Int" => Ok(Self::Int),
            "Text" => Ok(Self::Text),
            _ => Err(SolverError::Internal("query sort")),
        }
    }
    fn name(self) -> &'static str {
        match self {
            Self::Bool => "Bool",
            Self::Int => "Int",
            Self::Text => "Text",
        }
    }
}
#[derive(Clone, Debug, Eq, PartialEq)]
enum ModelValue {
    Bool(bool),
    Int(crate::integer::Integer),
    Text(String),
}
struct ResponseRecord {
    bytes: Vec<u8>,
    digest: String,
    request: String,
}
pub struct SatModel {
    record: Arc<ResponseRecord>,
    values: BTreeMap<String, Arc<ModelValue>>,
    usage: SolverUsage,
}
impl SatModel {
    pub fn response_bytes(&self) -> &[u8] {
        &self.record.bytes
    }
    pub fn response_digest(&self) -> &str {
        &self.record.digest
    }
    pub fn usage(&self) -> &SolverUsage {
        &self.usage
    }
}
pub struct SolverResponse {
    status: SolverStatus,
    record: Arc<ResponseRecord>,
    model: Option<SatModel>,
    usage: SolverUsage,
    model_present: bool,
}
impl SolverResponse {
    pub fn status(&self) -> SolverStatus {
        self.status
    }
    pub fn sat_model(&self) -> Option<&SatModel> {
        self.model.as_ref()
    }
    pub fn model_present(&self) -> bool {
        self.model_present
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.record.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.record.digest
    }
    pub fn usage(&self) -> &SolverUsage {
        &self.usage
    }
}
pub fn parse_solver_response(
    request: &SolverRequest,
    input: SolverResponseInput<'_>,
) -> Result<SolverResponse> {
    protocol::parse(request, input)
}

pub struct ModelWorldCandidate {
    bytes: Vec<u8>,
    world: Vec<u8>,
    classes: Vec<u8>,
    digest: String,
    usage: SolverUsage,
}
impl ModelWorldCandidate {
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn world_bytes(&self) -> &[u8] {
        &self.world
    }
    pub fn text_class_bytes(&self) -> &[u8] {
        &self.classes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
    pub fn usage(&self) -> &SolverUsage {
        &self.usage
    }
}
pub fn decode_model_world(
    request: &SolverRequest,
    model: &SatModel,
) -> Result<ModelWorldCandidate> {
    world::decode(request, model)
}
pub fn check_model_world(
    bytes: &[u8],
    request: &SolverRequest,
    model: &SatModel,
) -> Result<ModelWorldCandidate> {
    if bytes.len() > request.limits.candidate_bytes {
        return Err(SolverError::ResourceLimit {
            stage: SolverStage::Decode,
            resource: SolverResource::CandidateBytes,
        });
    }
    let candidate = decode_model_world(request, model)?;
    compare(bytes, candidate.canonical_bytes(), "world-candidate")?;
    Ok(candidate)
}
