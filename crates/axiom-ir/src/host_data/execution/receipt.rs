//! 公开回执 v0.2 的 P5 部分执行范围。关联实际转换及原始制品。

use std::{collections::BTreeMap, fmt};

use crate::{document::check_canonical_document, version::IrVersion};

use super::{
    FixtureCheckerTool, FixtureExecution, FixtureSlot, HOST_DATA_FORMAT, HOST_DATA_VERSION,
    HostDataLimits, PinnedBytes, RULE, Value,
    case::{FixtureCaseExecution, FixtureCaseRequest, execute_fixture_case},
    content_id, decimal, failure_kind, json, limit_record, object, raw_digest, string,
    tool_definition,
};

mod acceptance;
pub use acceptance::{
    MAX_ACCEPTANCE_BYTES, MAX_PROVENANCE_BYTES, P5_DARWIN_RELEASE_LIMITS, P5ToolAcceptance,
    ToolAcceptanceError,
};

pub const MAX_RECEIPT_BYTES: usize = 64 * 1024;
const PROFILE: &str = "raxc-keyed-finite-table-pipeline-v0.2";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReceiptError {
    IrBinding,
    Observation(super::ObservationError),
    ArtifactFormatConflict,
    ReceiptSize,
    ReceiptDigest,
    ReceiptMismatch,
    ToolAcceptance(ToolAcceptanceError),
}

impl fmt::Display for ReceiptError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P5 receipt: {self:?}")
    }
}

impl std::error::Error for ReceiptError {}

pub struct P5ReceiptRun {
    bytes: Vec<u8>,
    execution: FixtureCaseExecution,
}

impl P5ReceiptRun {
    pub fn canonical_receipt(&self) -> &[u8] {
        &self.bytes
    }

    pub fn execution(&self) -> &FixtureCaseExecution {
        &self.execution
    }
}

/// Runs the P5 case and records the resulting attempts. Tool binding at this
/// boundary supplies observation identity, with acceptance kept separate.
pub fn record_p5_receipt(
    tool: &FixtureCheckerTool,
    request: FixtureCaseRequest<'_>,
    limits: HostDataLimits,
) -> Result<P5ReceiptRun, ReceiptError> {
    record_receipt(tool, request, limits, None)
}

/// Records a P5 case using approval material from the caller's trust boundary.
pub fn record_p5_receipt_with_acceptance(
    tool: &FixtureCheckerTool,
    request: FixtureCaseRequest<'_>,
    limits: HostDataLimits,
    acceptance: P5ToolAcceptance<'_>,
) -> Result<P5ReceiptRun, ReceiptError> {
    record_receipt(tool, request, limits, Some(acceptance))
}

fn record_receipt(
    tool: &FixtureCheckerTool,
    request: FixtureCaseRequest<'_>,
    limits: HostDataLimits,
    acceptance: Option<P5ToolAcceptance<'_>>,
) -> Result<P5ReceiptRun, ReceiptError> {
    let ir = request.canonical_ir;
    if ir.bytes.len() > limits.fixture.ir_json.max_input_bytes
        || ir.bytes.len() > super::MAX_OBSERVED_INPUT_BYTES
        || raw_digest(ir.bytes) != ir.sha256
    {
        return Err(ReceiptError::IrBinding);
    }
    let document = check_canonical_document(ir.bytes, limits.fixture.ir_json)
        .map_err(|_| ReceiptError::IrBinding)?;
    if document.version() != IrVersion::V0_2 {
        return Err(ReceiptError::IrBinding);
    }
    let mut artifacts = Artifacts::default();
    let definition = tool_definition(&tool.digest);
    let tool_id = identity("tool", &definition);
    let acceptance = match acceptance {
        Some(material) => {
            material
                .validate(tool, &tool_id, request, limits)
                .map_err(ReceiptError::ToolAcceptance)?;
            let record = artifacts.add(material.record.bytes, "axiom-p5-tool-acceptance", "0.1")?;
            artifacts.add(material.provenance, "radishaxiom-p5-darwin-build", "0.1")?;
            object([("artifact", string(&record)), ("kind", string("accepted"))])
        }
        None => object([("kind", string("not-accepted"))]),
    };
    let execution =
        execute_fixture_case(tool, request, limits).map_err(ReceiptError::Observation)?;

    let ir_ref = artifacts.add(ir.bytes, "axiom-ir", "0.2")?;
    let task = artifacts.add(request.task.bytes, "axiom-benchmark-task", "0.1")?;
    let rule = artifacts.add(RULE, "axiom-p5-rule", "0.1")?;
    artifacts.insert(tool.digest.clone(), tool.len, "native-executable", "0.1")?;
    let context = AttemptContext {
        request,
        limits,
        ir: &ir_ref,
        task: &task,
        rule: &rule,
        tool: &tool_id,
    };

    let mut attempts = Vec::new();
    let mut ids = Vec::new();
    for (slot, attempt, raw) in [
        (
            FixtureSlot::Input,
            Some(execution.input_execution()),
            Some(request.input),
        ),
        (
            FixtureSlot::Golden,
            execution.golden_execution(),
            request.golden,
        ),
    ] {
        if let (Some(attempt), Some(raw)) = (attempt, raw) {
            let (id, definition) =
                context.attempt(&mut artifacts, slot, raw, attempt, ids.len())?;
            attempts.push(object([("definition", definition), ("id", string(&id))]));
            ids.push(string(&id));
        }
    }
    let receipt = object([
        ("artifacts", artifacts.value()),
        ("attempts", Value::Array(attempts)),
        ("evidence", object([("kind", string("not-assembled"))])),
        ("format", string("axiom-pipeline-receipt")),
        ("format_version", string("0.2")),
        (
            "ir",
            object([
                ("artifact", string(&ir_ref)),
                ("document_id", string(document.document_id())),
                (
                    "semantics",
                    string(&format!("sha256:{}", IrVersion::V0_2.semantics_sha256())),
                ),
                ("version", string("0.2")),
            ]),
        ),
        ("mode", string("benchmark-node24")),
        (
            "outcome",
            string(if execution.completed_pair().is_some() {
                "partial"
            } else {
                "blocked"
            }),
        ),
        (
            "p5",
            object([
                ("attempts", Value::Array(ids)),
                ("case", string(request.case)),
                ("result", execution.result_value()),
                ("task", string(&task)),
            ]),
        ),
        ("pipeline_profile", string(PROFILE)),
        (
            "tool",
            object([
                ("acceptance", acceptance),
                ("definition", definition),
                ("id", string(&tool_id)),
            ]),
        ),
        (
            "verification_gate",
            object([
                ("decision", string("closed")),
                ("reason", string("p6-not-evaluated")),
            ]),
        ),
    ]);
    let bytes = encode(&receipt);
    if bytes.len() > MAX_RECEIPT_BYTES {
        return Err(ReceiptError::ReceiptSize);
    }
    Ok(P5ReceiptRun { bytes, execution })
}

/// Rebuilds the supported receipt from exact material. This check establishes
/// consistency with the replay, without attesting historical execution.
pub fn check_p5_receipt(
    proposed: PinnedBytes<'_>,
    tool: &FixtureCheckerTool,
    request: FixtureCaseRequest<'_>,
    limits: HostDataLimits,
) -> Result<(), ReceiptError> {
    check_receipt(proposed, tool, request, limits, None)
}

/// Rebuilds a receipt using the caller's independently trusted approval pin.
/// Neither the receipt nor its artifact descriptors select that pin.
pub fn check_p5_receipt_with_acceptance(
    proposed: PinnedBytes<'_>,
    tool: &FixtureCheckerTool,
    request: FixtureCaseRequest<'_>,
    limits: HostDataLimits,
    acceptance: P5ToolAcceptance<'_>,
) -> Result<(), ReceiptError> {
    check_receipt(proposed, tool, request, limits, Some(acceptance))
}

fn check_receipt(
    proposed: PinnedBytes<'_>,
    tool: &FixtureCheckerTool,
    request: FixtureCaseRequest<'_>,
    limits: HostDataLimits,
    acceptance: Option<P5ToolAcceptance<'_>>,
) -> Result<(), ReceiptError> {
    if proposed.bytes.len() > MAX_RECEIPT_BYTES {
        return Err(ReceiptError::ReceiptSize);
    }
    if raw_digest(proposed.bytes) != proposed.sha256 {
        return Err(ReceiptError::ReceiptDigest);
    }
    if record_receipt(tool, request, limits, acceptance)?.bytes != proposed.bytes {
        return Err(ReceiptError::ReceiptMismatch);
    }
    Ok(())
}

struct AttemptContext<'a> {
    request: FixtureCaseRequest<'a>,
    limits: HostDataLimits,
    ir: &'a str,
    task: &'a str,
    rule: &'a str,
    tool: &'a str,
}

impl AttemptContext<'_> {
    fn attempt(
        &self,
        artifacts: &mut Artifacts,
        slot: FixtureSlot,
        raw: &[u8],
        execution: &FixtureExecution,
        ordinal: usize,
    ) -> Result<(String, Value), ReceiptError> {
        let fixture = artifacts.add(raw, "axiom-benchmark-data", "0.1")?;
        let basis = object([
            (
                "inputs",
                Value::Array(vec![
                    reference("benchmark-task", self.task),
                    reference("canonical-ir", self.ir),
                    reference("fixture", &fixture),
                ]),
            ),
            ("kind", string("check-fixture")),
            ("limits", limit_record(self.limits)),
            (
                "options",
                object([
                    ("case", string(self.request.case)),
                    ("expected_ir", string(self.request.canonical_ir.sha256)),
                    ("expected_task", string(self.request.task.sha256)),
                    (
                        "slot",
                        string(match slot {
                            FixtureSlot::Input => "input",
                            FixtureSlot::Golden => "golden",
                        }),
                    ),
                ]),
            ),
            ("rule", string(self.rule)),
            ("tool", string(self.tool)),
        ]);
        let cache_key = identity("cache-key", &basis);
        let (result, outputs) = match execution.outcome() {
            Ok(envelope) => {
                let artifact = artifacts.add(
                    envelope.canonical_bytes(),
                    HOST_DATA_FORMAT,
                    HOST_DATA_VERSION,
                )?;
                (
                    object([("kind", string("completed"))]),
                    vec![reference(slot.artifact_role(), &artifact)],
                )
            }
            Err(error) => (
                object([
                    ("code", string(error.code())),
                    ("kind", string(failure_kind(error))),
                ]),
                vec![],
            ),
        };
        let Value::Object(mut fields) = basis else {
            unreachable!("attempt basis")
        };
        fields.extend([
            ("cache_key".into(), string(&cache_key), 0),
            ("ordinal".into(), decimal(ordinal), 0),
            ("outputs".into(), Value::Array(outputs), 0),
            ("result".into(), result, 0),
        ]);
        fields.sort_unstable_by(|a, b| a.0.cmp(&b.0));
        let definition = Value::Object(fields);
        Ok((identity("attempt", &definition), definition))
    }
}

fn reference(role: &str, artifact: &str) -> Value {
    object([("artifact", string(artifact)), ("role", string(role))])
}

fn encode(value: &Value) -> Vec<u8> {
    let mut raw = Vec::new();
    json::encode(value, &mut raw);
    raw
}

fn identity(kind: &str, value: &Value) -> String {
    content_id(&format!("axiom-pipeline-v0.2:{kind}"), &encode(value))
}

#[derive(Default)]
struct Artifacts(BTreeMap<String, (usize, &'static str, &'static str)>);

impl Artifacts {
    fn add(
        &mut self,
        raw: &[u8],
        format: &'static str,
        version: &'static str,
    ) -> Result<String, ReceiptError> {
        let digest = raw_digest(raw);
        self.insert(digest.clone(), raw.len(), format, version)?;
        Ok(digest)
    }

    fn insert(
        &mut self,
        digest: String,
        len: usize,
        format: &'static str,
        version: &'static str,
    ) -> Result<(), ReceiptError> {
        let descriptor = (len, format, version);
        if self
            .0
            .get(&digest)
            .is_some_and(|existing| *existing != descriptor)
        {
            return Err(ReceiptError::ArtifactFormatConflict);
        }
        self.0.insert(digest, descriptor);
        Ok(())
    }

    fn value(self) -> Value {
        Value::Array(
            self.0
                .into_iter()
                .map(|(digest, (len, format, version))| {
                    object([
                        ("byte_length", decimal(len)),
                        ("content_digest", string(&digest)),
                        ("format", string(format)),
                        ("format_version", string(version)),
                    ])
                })
                .collect(),
        )
    }
}
