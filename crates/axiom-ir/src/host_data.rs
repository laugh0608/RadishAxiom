//! ADR 0033 的 P5 封套转换及严格重建入口。

use std::fmt;

use crate::{
    contracts::ContractError,
    declarations::DeclarationError,
    document::{DocumentError, check_canonical_document},
    fixtures::{self, CheckedFixture, FixtureError, FixtureLimits, FixtureRole, FixtureValue},
    json::{self, JsonErrorKind, JsonLimits, Value},
    obligations::raw_digest,
    version::IrVersion,
};

mod manifest;
#[cfg(test)]
mod tests;

pub const HOST_DATA_FORMAT: &str = "axiom-host-data";
pub const HOST_DATA_VERSION: &str = "0.2";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FixtureSlot {
    Input,
    Golden,
}

impl FixtureSlot {
    fn host_role(self) -> &'static str {
        match self {
            Self::Input => "input",
            Self::Golden => "output",
        }
    }

    pub fn artifact_role(self) -> &'static str {
        match self {
            Self::Input => "host-input",
            Self::Golden => "golden-host-output",
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct PinnedBytes<'a> {
    pub bytes: &'a [u8],
    pub sha256: &'a str,
}

#[derive(Clone, Copy, Debug)]
pub struct FixtureConversion<'a> {
    pub canonical_ir: PinnedBytes<'a>,
    pub task: PinnedBytes<'a>,
    pub case: &'a str,
    pub slot: FixtureSlot,
    /// 使用实际任务清单中所选槽位的摘要核对。
    pub fixture_bytes: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct HostDataLimits {
    pub task_json: JsonLimits,
    pub fixture: FixtureLimits,
    /// 独立于 P5 类型化表预算的完整封套字节上限。
    pub envelope_bytes: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct HostDataBinding {
    pub ir_artifact: String,
    pub ir_document_id: String,
    pub task_artifact: String,
    pub benchmark_id: String,
    pub case: String,
    pub slot: FixtureSlot,
    pub source_role: FixtureRole,
    pub fixture_artifact: String,
    pub limits: HostDataLimits,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct HostData {
    binding: HostDataBinding,
    bytes: Vec<u8>,
    digest: String,
}

impl HostData {
    pub fn binding(&self) -> &HostDataBinding {
        &self.binding
    }

    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }

    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum HostArtifact {
    CanonicalIr,
    Task,
    Envelope,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ConversionFailure {
    Invalid,
    ResourceExhausted,
    Unsupported,
    Error,
}

#[derive(Debug)]
pub enum HostDataError {
    ArtifactDigest(HostArtifact),
    ByteLimit(HostArtifact),
    Ir(Box<DocumentError>),
    IrVersion(IrVersion),
    Task(DeclarationError),
    TaskSelection(&'static str),
    Fixture {
        slot: FixtureSlot,
        cause: Box<FixtureError>,
    },
    EnvelopeMismatch {
        offset: usize,
    },
}

impl HostDataError {
    /// 本地转换的分类供将来的执行记录消费。
    pub fn failure(&self) -> ConversionFailure {
        match self {
            Self::ByteLimit(_) => ConversionFailure::ResourceExhausted,
            Self::Ir(cause)
                if matches!(
                    cause.as_ref(),
                    DocumentError::Ir(ContractError::Input(DeclarationError::Json(error)))
                        if matches!(error.kind, JsonErrorKind::ResourceLimit(_))
                ) =>
            {
                ConversionFailure::ResourceExhausted
            }
            Self::Task(DeclarationError::Json(error))
                if matches!(error.kind, JsonErrorKind::ResourceLimit(_)) =>
            {
                ConversionFailure::ResourceExhausted
            }
            Self::Fixture { slot, cause } => match cause.as_ref() {
                FixtureError::Resource(_) => ConversionFailure::ResourceExhausted,
                FixtureError::Unsupported { .. } => ConversionFailure::Unsupported,
                FixtureError::Binding { .. } => ConversionFailure::Error,
                _ if *slot == FixtureSlot::Input => ConversionFailure::Invalid,
                _ => ConversionFailure::Error,
            },
            _ => ConversionFailure::Error,
        }
    }

    pub fn code(&self) -> &'static str {
        match self {
            Self::ArtifactDigest(HostArtifact::CanonicalIr) => "ir-artifact-mismatch",
            Self::ArtifactDigest(HostArtifact::Task) => "task-artifact-mismatch",
            Self::ArtifactDigest(HostArtifact::Envelope) => "host-artifact-mismatch",
            Self::ByteLimit(HostArtifact::CanonicalIr) => "ir-byte-limit",
            Self::ByteLimit(HostArtifact::Task) => "task-byte-limit",
            Self::ByteLimit(HostArtifact::Envelope) => "host-byte-limit",
            Self::Ir(_) => "ir-check",
            Self::IrVersion(_) => "ir-version-mismatch",
            Self::Task(_) => "task-structure",
            Self::TaskSelection(_) => "task-selection",
            Self::Fixture { cause, .. } => match cause.as_ref() {
                FixtureError::Binding { .. } => "fixture-binding",
                FixtureError::Precondition { .. } => "fixture-precondition",
                FixtureError::Resource(_) => "fixture-resource",
                FixtureError::Unsupported { .. } => "fixture-unsupported",
                _ => "fixture-data",
            },
            Self::EnvelopeMismatch { .. } => "host-replay-mismatch",
        }
    }
}

impl fmt::Display for HostDataError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P5 host data {}: {self:?}", self.code())
    }
}

impl std::error::Error for HostDataError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Ir(cause) => Some(cause.as_ref()),
            Self::Task(cause) => Some(cause),
            Self::Fixture { cause, .. } => Some(cause.as_ref()),
            _ => None,
        }
    }
}

impl From<DeclarationError> for HostDataError {
    fn from(error: DeclarationError) -> Self {
        Self::Task(error)
    }
}

/// 检查选定夹具并产生有界规范封套。此入口返回转换事实，供后续生产执行记录使用。
pub fn convert_fixture(
    request: FixtureConversion<'_>,
    limits: HostDataLimits,
) -> Result<HostData, HostDataError> {
    verify_pin(
        request.canonical_ir,
        limits.fixture.ir_json.max_input_bytes,
        HostArtifact::CanonicalIr,
    )?;
    verify_pin(
        request.task,
        limits.task_json.max_input_bytes,
        HostArtifact::Task,
    )?;
    let document = check_canonical_document(request.canonical_ir.bytes, limits.fixture.ir_json)
        .map_err(|cause| HostDataError::Ir(Box::new(cause)))?;
    if document.version() != IrVersion::V0_2 {
        return Err(HostDataError::IrVersion(document.version()));
    }
    let selection = manifest::select(
        request.task.bytes,
        request.case,
        request.slot,
        limits.task_json,
    )?;
    let checked = fixtures::check_fixture(
        &document,
        &selection.benchmark_id,
        selection.role,
        request.fixture_bytes,
        &selection.sha256,
        limits.fixture,
    )
    .map_err(|cause| HostDataError::Fixture {
        slot: request.slot,
        cause: Box::new(cause),
    })?;
    let bytes = encode(&checked, request.slot, limits.envelope_bytes)?;
    let digest = raw_digest(&bytes);
    Ok(HostData {
        binding: HostDataBinding {
            ir_artifact: request.canonical_ir.sha256.into(),
            ir_document_id: checked.ir_document_id().into(),
            task_artifact: request.task.sha256.into(),
            benchmark_id: selection.benchmark_id,
            case: request.case.into(),
            slot: request.slot,
            source_role: checked.role(),
            fixture_artifact: checked.fixture_digest().into(),
            limits,
        },
        bytes,
        digest,
    })
}

/// 同实现重建。外部摘要与候选字节相符后仍须核对完整转换，含版本、角色与规范编码。
pub fn check_host_data(
    request: FixtureConversion<'_>,
    limits: HostDataLimits,
    proposed: PinnedBytes<'_>,
) -> Result<HostData, HostDataError> {
    verify_pin(proposed, limits.envelope_bytes, HostArtifact::Envelope)?;
    let actual = convert_fixture(request, limits)?;
    if actual.bytes != proposed.bytes {
        let offset = actual
            .bytes
            .iter()
            .zip(proposed.bytes)
            .position(|(a, b)| a != b)
            .unwrap_or_else(|| actual.bytes.len().min(proposed.bytes.len()));
        return Err(HostDataError::EnvelopeMismatch { offset });
    }
    Ok(actual)
}

fn verify_pin(
    input: PinnedBytes<'_>,
    limit: usize,
    artifact: HostArtifact,
) -> Result<(), HostDataError> {
    if input.bytes.len() > limit {
        return Err(HostDataError::ByteLimit(artifact));
    }
    if raw_digest(input.bytes) != input.sha256 {
        return Err(HostDataError::ArtifactDigest(artifact));
    }
    Ok(())
}

fn encode(
    checked: &CheckedFixture,
    slot: FixtureSlot,
    limit: usize,
) -> Result<Vec<u8>, HostDataError> {
    let tables = checked.tables().iter().map(|table| {
        let rows = table.rows.iter().map(|row| {
            let mut fields = row.iter().collect::<Vec<_>>();
            fields.sort_unstable_by(|(left, _), (right, _)| {
                left.encode_utf16().cmp(right.encode_utf16())
            });
            Value::Object(
                fields
                    .into_iter()
                    .map(|(name, value)| {
                        let text = match value {
                            FixtureValue::Int(value) => value.as_str(),
                            FixtureValue::Text(value) | FixtureValue::Enum(value) => value,
                        };
                        (name.clone(), string(text), 0)
                    })
                    .collect(),
            )
        });
        object([
            ("name", string(&table.name)),
            ("rows", Value::Array(rows.collect())),
        ])
    });
    let value = object([
        ("format", string(HOST_DATA_FORMAT)),
        ("format_version", string(HOST_DATA_VERSION)),
        ("ir_document_digest", string(checked.ir_document_id())),
        ("role", string(slot.host_role())),
        ("tables", Value::Array(tables.collect())),
    ]);
    let mut remaining = Some(limit);
    json::emit(&value, &mut |bytes| {
        remaining = remaining.and_then(|budget| budget.checked_sub(bytes.len()));
    });
    let size = limit - remaining.ok_or(HostDataError::ByteLimit(HostArtifact::Envelope))?;
    let mut bytes = Vec::with_capacity(size);
    json::encode(&value, &mut bytes);
    Ok(bytes)
}

fn string(text: &str) -> Value {
    Value::String(text.into())
}

fn object<const N: usize>(members: [(&str, Value); N]) -> Value {
    Value::Object(
        members
            .into_iter()
            .map(|(name, value)| (name.into(), value, 0))
            .collect(),
    )
}
