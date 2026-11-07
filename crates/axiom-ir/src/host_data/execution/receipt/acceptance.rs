//! P5 生产工具接受记录 v0.1 的精确材料核对。

use crate::{fixtures::FixtureLimits, json::JsonLimits};

use super::{
    FixtureCaseRequest, FixtureCheckerTool, HostDataLimits, PROFILE, PinnedBytes, RULE, encode,
    limit_record, object, raw_digest, string,
};

pub const MAX_ACCEPTANCE_BYTES: usize = 8 * 1024;
pub const MAX_PROVENANCE_BYTES: usize = 1024 * 1024;
const JSON: JsonLimits = JsonLimits {
    max_input_bytes: 64 * 1024,
    max_values: 4096,
    max_nesting: 64,
};
pub const P5_DARWIN_RELEASE_LIMITS: HostDataLimits = HostDataLimits {
    task_json: JSON,
    fixture: FixtureLimits {
        fixture_json: JSON,
        ir_json: JSON,
        max_tables: 4,
        max_rows: 256,
        max_integer_digits: 64,
        max_precondition_checks: 256,
        max_output_bytes: 64 * 1024,
    },
    envelope_bytes: 64 * 1024,
};

/// The caller supplies the approval pin from trusted configuration. The record
/// is never trusted merely because its digest matches a receipt descriptor.
#[derive(Clone, Copy, Debug)]
pub struct P5ToolAcceptance<'a> {
    pub record: PinnedBytes<'a>,
    pub provenance: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ToolAcceptanceError {
    RecordSize,
    RecordDigest,
    ProvenanceSize,
    Limits,
    TaskDigest,
    RecordMismatch,
}

impl P5ToolAcceptance<'_> {
    pub(super) fn validate(
        self,
        tool: &FixtureCheckerTool,
        tool_id: &str,
        request: FixtureCaseRequest<'_>,
        limits: HostDataLimits,
    ) -> Result<(), ToolAcceptanceError> {
        if self.record.bytes.is_empty() || self.record.bytes.len() > MAX_ACCEPTANCE_BYTES {
            return Err(ToolAcceptanceError::RecordSize);
        }
        if raw_digest(self.record.bytes) != self.record.sha256 {
            return Err(ToolAcceptanceError::RecordDigest);
        }
        if self.provenance.is_empty() || self.provenance.len() > MAX_PROVENANCE_BYTES {
            return Err(ToolAcceptanceError::ProvenanceSize);
        }
        if limits.envelope_bytes > P5_DARWIN_RELEASE_LIMITS.envelope_bytes
            || (HostDataLimits {
                envelope_bytes: P5_DARWIN_RELEASE_LIMITS.envelope_bytes,
                ..limits
            }) != P5_DARWIN_RELEASE_LIMITS
        {
            return Err(ToolAcceptanceError::Limits);
        }
        if request.task.bytes.len() > super::super::MAX_OBSERVED_INPUT_BYTES
            || raw_digest(request.task.bytes) != request.task.sha256
        {
            return Err(ToolAcceptanceError::TaskDigest);
        }
        let expected = object([
            ("artifact", string(&tool.digest)),
            ("build_profile", string("release")),
            ("format", string("axiom-p5-tool-acceptance")),
            ("format_version", string("0.1")),
            ("invocation", string("record-p5-fixture-cli-v0.1")),
            ("ir", string(request.canonical_ir.sha256)),
            ("limits", limit_record(P5_DARWIN_RELEASE_LIMITS)),
            ("pipeline_profile", string(PROFILE)),
            ("provenance", string(&raw_digest(self.provenance))),
            ("role", string("fixture-checker")),
            ("rule", string(&raw_digest(RULE))),
            ("target", string("aarch64-apple-darwin")),
            ("task", string(request.task.sha256)),
            ("tool", string(tool_id)),
        ]);
        if encode(&expected) != self.record.bytes {
            return Err(ToolAcceptanceError::RecordMismatch);
        }
        Ok(())
    }
}
