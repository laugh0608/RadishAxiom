use super::*;
use crate::{
    fixtures::FixtureLimits, host_data::execution::MAX_OBSERVED_INPUT_BYTES, json::JsonLimits,
};

const IR: &[u8] = include_bytes!("../../../../tests/fixtures/v0.2/migrated/ax-b01-correct.jcs");
const TASK: &[u8] =
    include_bytes!("../../../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/task.json");
const INPUT: &[u8] = include_bytes!(
    "../../../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/base.input.json"
);
const JSON: JsonLimits = JsonLimits {
    max_input_bytes: 65536,
    max_nesting: 64,
    max_values: 4096,
};
const LIMITS: HostDataLimits = HostDataLimits {
    task_json: JSON,
    fixture: FixtureLimits {
        fixture_json: JSON,
        ir_json: JSON,
        max_tables: 4,
        max_rows: 256,
        max_integer_digits: 64,
        max_precondition_checks: 256,
        max_output_bytes: 65536,
    },
    envelope_bytes: 65536,
};

#[test]
fn golden_preflight_preserves_the_completed_input_without_claiming_a_golden_attempt() {
    let fake_tool = b"synthetic unit-test artifact";
    let tool = FixtureCheckerTool::bind(PinnedBytes {
        bytes: fake_tool,
        sha256: &raw_digest(fake_tool),
    })
    .unwrap();
    let golden = vec![b' '; MAX_OBSERVED_INPUT_BYTES + 1];
    let execution = execute_fixture_case(
        &tool,
        FixtureCaseRequest {
            canonical_ir: PinnedBytes {
                bytes: IR,
                sha256: &raw_digest(IR),
            },
            task: PinnedBytes {
                bytes: TASK,
                sha256: &raw_digest(TASK),
            },
            case: "base",
            input: INPUT,
            golden: Some(&golden),
        },
        LIMITS,
    )
    .unwrap();
    assert!(execution.input_execution().outcome().is_ok());
    assert!(execution.golden_execution().is_none());
    assert!(execution.completed_pair().is_none());
    assert_eq!(
        execution.status(),
        FixtureCaseStatus::GoldenPreflight(ObservationError::InputSize)
    );
    let record = std::str::from_utf8(execution.canonical_record()).unwrap();
    assert!(
        record.contains(
            r#""result":{"code":"observation-input-size","kind":"error","slot":"golden"}"#
        )
    );
}
