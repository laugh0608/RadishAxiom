//! P5 的私有本地执行记录。外层须将所登记的制品绑定到实际执行入口。

use std::fmt;

use super::{
    ConversionFailure, FixtureConversion, FixtureSlot, HOST_DATA_FORMAT, HOST_DATA_VERSION,
    HostData, HostDataError, HostDataLimits, PinnedBytes, convert_fixture, object, string,
};
use crate::{
    json::{self, JsonLimits, Value},
    normalization::content_id,
    obligations::raw_digest,
};

pub mod case;

pub const MAX_OBSERVED_INPUT_BYTES: usize = 128 * 1024;
pub const MAX_TOOL_BYTES: usize = 32 * 1024 * 1024;
const RULE: &[u8] = include_bytes!("../../../../docs/adr/0033-p5-host-data-ir-v02-pairing.md");
const TOOL_DOMAIN: &str = "radishaxiom-private-p5-v0.1:tool";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ObservationError {
    ToolSize,
    ToolDigest,
    InputSize,
    InputPin,
    CaseName,
}

impl fmt::Display for ObservationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.code())
    }
}

impl ObservationError {
    fn code(self) -> &'static str {
        match self {
            Self::ToolSize => "tool-size",
            Self::ToolDigest => "tool-digest",
            Self::InputSize => "observation-input-size",
            Self::InputPin => "observation-input-pin",
            Self::CaseName => "observation-case-name",
        }
    }
}

impl std::error::Error for ObservationError {}

/// 此登记核对制品字节与外部 pin。实际执行关系由外层入口和宿主观察提供。
#[derive(Debug)]
pub struct FixtureCheckerTool {
    digest: String,
    len: usize,
    id: String,
}

impl FixtureCheckerTool {
    pub fn bind(executable: PinnedBytes<'_>) -> Result<Self, ObservationError> {
        if executable.bytes.is_empty() || executable.bytes.len() > MAX_TOOL_BYTES {
            return Err(ObservationError::ToolSize);
        }
        let digest = raw_digest(executable.bytes);
        if digest != executable.sha256 {
            return Err(ObservationError::ToolDigest);
        }
        let mut definition = Vec::new();
        json::encode(&tool_definition(&digest), &mut definition);
        let id = content_id(TOOL_DOMAIN, &definition);
        Ok(Self {
            digest,
            len: executable.bytes.len(),
            id,
        })
    }

    fn record(&self) -> Value {
        object([
            ("artifact_bytes", decimal(self.len)),
            ("definition", tool_definition(&self.digest)),
            ("id", string(&self.id)),
        ])
    }
}

fn tool_definition(digest: &str) -> Value {
    object([
        ("artifact", string(digest)),
        ("name", string("radishaxiom-p5-fixture-check")),
        ("roles", Value::Array(vec![string("fixture-checker")])),
        ("version", string(digest)),
    ])
}

pub struct FixtureExecution {
    record: Vec<u8>,
    outcome: Result<HostData, HostDataError>,
}

impl FixtureExecution {
    pub fn canonical_record(&self) -> &[u8] {
        &self.record
    }

    pub fn outcome(&self) -> Result<&HostData, &HostDataError> {
        self.outcome.as_ref()
    }
}

/// 执行实际转换并记录结果。预检无法完整观察输入时返回错误，未发生转换。
pub fn execute_fixture(
    tool: &FixtureCheckerTool,
    request: FixtureConversion<'_>,
    limits: HostDataLimits,
) -> Result<FixtureExecution, ObservationError> {
    let inputs = [
        ("benchmark-task", request.task.bytes),
        ("canonical-ir", request.canonical_ir.bytes),
        ("fixture", request.fixture_bytes),
    ];
    if inputs
        .iter()
        .any(|(_, bytes)| bytes.len() > MAX_OBSERVED_INPUT_BYTES)
    {
        return Err(ObservationError::InputSize);
    }
    if !valid_pin(request.canonical_ir.sha256) || !valid_pin(request.task.sha256) {
        return Err(ObservationError::InputPin);
    }
    if request.case.is_empty()
        || request.case.len() > 128
        || request.case.chars().any(char::is_control)
    {
        return Err(ObservationError::CaseName);
    }

    let outcome = convert_fixture(request, limits);
    let (result, outputs) = match &outcome {
        Ok(envelope) => {
            let output = object([
                ("byte_length", decimal(envelope.canonical_bytes().len())),
                ("content_digest", string(envelope.artifact_digest())),
                ("format", string(HOST_DATA_FORMAT)),
                ("format_version", string(HOST_DATA_VERSION)),
                ("role", string(request.slot.artifact_role())),
            ]);
            (object([("kind", string("completed"))]), vec![output])
        }
        Err(cause) => (
            object([
                ("code", string(cause.code())),
                ("kind", string(failure_kind(cause))),
            ]),
            vec![],
        ),
    };
    let input_refs = inputs.into_iter().map(|(role, bytes)| {
        object([
            ("byte_length", decimal(bytes.len())),
            ("content_digest", string(&raw_digest(bytes))),
            ("role", string(role)),
        ])
    });
    let slot = match request.slot {
        FixtureSlot::Input => "input",
        FixtureSlot::Golden => "golden",
    };
    let options = object([
        ("case", string(request.case)),
        ("expected_ir", string(request.canonical_ir.sha256)),
        ("expected_task", string(request.task.sha256)),
        ("slot", string(slot)),
    ]);
    let record = object([
        ("format", string("radishaxiom-private-p5-execution")),
        ("inputs", Value::Array(input_refs.collect())),
        ("kind", string("check-fixture")),
        ("limits", limit_record(limits)),
        ("options", options),
        ("outputs", Value::Array(outputs)),
        ("result", result),
        ("rule", string(&raw_digest(RULE))),
        ("tool", tool.record()),
        ("version", string("0.1")),
    ]);
    let mut bytes = Vec::new();
    json::encode(&record, &mut bytes);
    Ok(FixtureExecution {
        record: bytes,
        outcome,
    })
}

fn failure_kind(cause: &HostDataError) -> &'static str {
    match cause.failure() {
        ConversionFailure::Invalid => "invalid",
        ConversionFailure::ResourceExhausted => "resource-exhausted",
        ConversionFailure::Unsupported => "unsupported",
        ConversionFailure::Error => "error",
    }
}

fn valid_pin(text: &str) -> bool {
    text.strip_prefix("sha256:").is_some_and(|hex| {
        hex.len() == 64
            && hex
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    })
}

fn limit_record(limits: HostDataLimits) -> Value {
    let f = limits.fixture;
    object([
        ("envelope_bytes", decimal(limits.envelope_bytes)),
        ("fixture_json", json_limits(f.fixture_json)),
        ("ir_json", json_limits(f.ir_json)),
        ("max_integer_digits", decimal(f.max_integer_digits)),
        ("max_output_bytes", decimal(f.max_output_bytes)),
        (
            "max_precondition_checks",
            decimal(f.max_precondition_checks),
        ),
        ("max_rows", decimal(f.max_rows)),
        ("max_tables", decimal(f.max_tables)),
        ("task_json", json_limits(limits.task_json)),
    ])
}

fn json_limits(limits: JsonLimits) -> Value {
    object([
        ("max_input_bytes", decimal(limits.max_input_bytes)),
        ("max_nesting", decimal(limits.max_nesting)),
        ("max_values", decimal(limits.max_values)),
    ])
}

fn decimal(value: usize) -> Value {
    string(&value.to_string())
}
