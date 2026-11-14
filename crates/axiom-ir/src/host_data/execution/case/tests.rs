use super::super::receipt::{ReceiptError, check_p5_receipt, record_p5_receipt};
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
const GOLDEN: &[u8] = include_bytes!(
    "../../../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/base.golden.json"
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
    let request = FixtureCaseRequest {
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
    };
    let execution = execute_fixture_case(&tool, request, LIMITS).unwrap();
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
    let run = record_p5_receipt(&tool, request, LIMITS).unwrap();
    let raw = run.canonical_receipt();
    let public = std::str::from_utf8(raw).unwrap();
    assert!(public.contains(r#""outcome":"blocked""#));
    assert!(
        public.contains(
            r#""result":{"code":"observation-input-size","kind":"error","slot":"golden"}"#
        )
    );
    assert!(!public.contains(r#""ordinal":"1""#));
    assert!(
        check_p5_receipt(
            PinnedBytes {
                bytes: raw,
                sha256: &raw_digest(raw)
            },
            &tool,
            request,
            LIMITS,
        )
        .is_ok()
    );
}

#[test]
fn public_receipt_does_not_promote_completion_to_tool_acceptance_or_an_open_gate() {
    let binary = b"synthetic receipt test artifact";
    let binary_sha = raw_digest(binary);
    let tool = FixtureCheckerTool::bind(PinnedBytes {
        bytes: binary,
        sha256: &binary_sha,
    })
    .unwrap();
    let ir_sha = raw_digest(IR);
    let task_sha = raw_digest(TASK);
    let request = FixtureCaseRequest {
        canonical_ir: PinnedBytes {
            bytes: IR,
            sha256: &ir_sha,
        },
        task: PinnedBytes {
            bytes: TASK,
            sha256: &task_sha,
        },
        case: "base",
        input: INPUT,
        golden: Some(GOLDEN),
    };
    let run = record_p5_receipt(&tool, request, LIMITS).unwrap();
    assert!(run.execution().completed_pair().is_some());
    let bytes = run.canonical_receipt();
    let text = std::str::from_utf8(bytes).unwrap();
    assert!(text.contains(r#""acceptance":{"kind":"not-accepted"}"#));
    assert!(
        text.contains(r#""verification_gate":{"decision":"closed","reason":"p6-not-evaluated"}"#)
    );
    assert!(
        check_p5_receipt(
            PinnedBytes {
                bytes,
                sha256: &raw_digest(bytes)
            },
            &tool,
            request,
            LIMITS
        )
        .is_ok()
    );

    let relabelled = text.replace(r#""kind":"not-accepted""#, r#""kind":"accepted""#);
    let pin = PinnedBytes {
        bytes: relabelled.as_bytes(),
        sha256: &raw_digest(relabelled.as_bytes()),
    };
    assert_eq!(
        check_p5_receipt(pin, &tool, request, LIMITS),
        Err(ReceiptError::ReceiptMismatch)
    );
}
