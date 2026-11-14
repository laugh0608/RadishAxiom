//! 把同一 case 的真实 P5 转换归在一起，保留已发生的步骤和阻断原因。

use super::{
    FixtureCheckerTool, FixtureConversion, FixtureExecution, FixtureSlot, HostData, HostDataLimits,
    ObservationError, PinnedBytes, RULE, Value, decimal, execute_fixture, failure_kind, json,
    object, raw_digest, string,
};

#[cfg(test)]
mod tests;

#[derive(Clone, Copy, Debug)]
pub struct FixtureCaseRequest<'a> {
    pub canonical_ir: PinnedBytes<'a>,
    pub task: PinnedBytes<'a>,
    pub case: &'a str,
    pub input: &'a [u8],
    pub golden: Option<&'a [u8]>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FixtureCaseStatus {
    Completed,
    InputFailed,
    MissingGolden,
    GoldenPreflight(ObservationError),
    GoldenFailed,
}

pub struct FixtureCaseExecution {
    record: Vec<u8>,
    input: FixtureExecution,
    golden: Option<FixtureExecution>,
    status: FixtureCaseStatus,
}

impl FixtureCaseExecution {
    pub fn canonical_record(&self) -> &[u8] {
        &self.record
    }

    pub fn input_execution(&self) -> &FixtureExecution {
        &self.input
    }

    pub fn golden_execution(&self) -> Option<&FixtureExecution> {
        self.golden.as_ref()
    }

    pub fn status(&self) -> FixtureCaseStatus {
        self.status
    }

    pub(super) fn result_value(&self) -> Value {
        case_result(self.status, &self.input, self.golden.as_ref())
    }

    /// P5 的两个成功封套。调用方还须单独核对生成门控。
    pub fn completed_pair(&self) -> Option<(&HostData, &HostData)> {
        Some((
            self.input.outcome().ok()?,
            self.golden.as_ref()?.outcome().ok()?,
        ))
    }
}

/// 输入和黄金转换共用一个工具、IR、清单、case 和预算。
pub fn execute_fixture_case(
    tool: &FixtureCheckerTool,
    request: FixtureCaseRequest<'_>,
    limits: HostDataLimits,
) -> Result<FixtureCaseExecution, ObservationError> {
    let input_request = FixtureConversion {
        canonical_ir: request.canonical_ir,
        task: request.task,
        case: request.case,
        slot: FixtureSlot::Input,
        fixture_bytes: request.input,
    };
    let input = execute_fixture(tool, input_request, limits)?;
    let (golden, status) = match (input.outcome(), request.golden) {
        (Err(_), _) => (None, FixtureCaseStatus::InputFailed),
        (Ok(_), None) => (None, FixtureCaseStatus::MissingGolden),
        (Ok(_), Some(bytes)) => {
            let golden_request = FixtureConversion {
                slot: FixtureSlot::Golden,
                fixture_bytes: bytes,
                ..input_request
            };
            match execute_fixture(tool, golden_request, limits) {
                Ok(golden) => {
                    let status = if golden.outcome().is_ok() {
                        FixtureCaseStatus::Completed
                    } else {
                        FixtureCaseStatus::GoldenFailed
                    };
                    (Some(golden), status)
                }
                Err(error) => (None, FixtureCaseStatus::GoldenPreflight(error)),
            }
        }
    };
    let mut attempts = vec![attempt_ref("input", &input)];
    if let Some(golden) = &golden {
        attempts.push(attempt_ref("golden", golden));
    }
    let record = object([
        ("attempts", Value::Array(attempts)),
        ("case", string(request.case)),
        ("expected_ir", string(request.canonical_ir.sha256)),
        ("expected_task", string(request.task.sha256)),
        ("format", string("radishaxiom-private-p5-case")),
        ("result", case_result(status, &input, golden.as_ref())),
        ("rule", string(&raw_digest(RULE))),
        ("tool", string(&tool.id)),
        ("version", string("0.1")),
    ]);
    let mut bytes = Vec::new();
    json::encode(&record, &mut bytes);
    Ok(FixtureCaseExecution {
        record: bytes,
        input,
        golden,
        status,
    })
}

fn case_result(
    status: FixtureCaseStatus,
    input: &FixtureExecution,
    golden: Option<&FixtureExecution>,
) -> Value {
    match status {
        FixtureCaseStatus::Completed => object([("kind", string("completed"))]),
        FixtureCaseStatus::MissingGolden => stopped("golden", "error", "missing-golden"),
        FixtureCaseStatus::GoldenPreflight(error) => stopped("golden", "error", error.code()),
        FixtureCaseStatus::InputFailed | FixtureCaseStatus::GoldenFailed => {
            let (slot, attempt) = if status == FixtureCaseStatus::InputFailed {
                ("input", input)
            } else {
                ("golden", golden.expect("executed golden"))
            };
            let error = attempt.outcome().expect_err("failed attempt");
            stopped(slot, failure_kind(error), error.code())
        }
    }
}

fn stopped(slot: &str, kind: &str, code: &str) -> Value {
    object([
        ("code", string(code)),
        ("kind", string(kind)),
        ("slot", string(slot)),
    ])
}

fn attempt_ref(slot: &str, attempt: &FixtureExecution) -> Value {
    let bytes = attempt.canonical_record();
    object([
        ("byte_length", decimal(bytes.len())),
        ("content_digest", string(&raw_digest(bytes))),
        ("slot", string(slot)),
    ])
}
