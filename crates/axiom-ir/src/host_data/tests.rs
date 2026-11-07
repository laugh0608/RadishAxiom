use super::*;
use crate::{
    document::normalize_document, fixtures::FixtureResource, normalization::content_id,
    version::ContentKind,
};

const IR: &[u8] = include_bytes!("../../tests/fixtures/v0.2/migrated/ax-b01-correct.jcs");
const OLD_IR: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/candidates/correct.ir.jcs"
);
const TASK: &[u8] =
    include_bytes!("../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/task.json");
const BASE: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/base.input.json"
);
const BASE_GOLDEN: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/base.golden.json"
);
const BOUNDARY: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/boundary.input.json"
);
const BOUNDARY_GOLDEN: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/boundary.golden.json"
);
const INVALID: &[u8] = include_bytes!(
    "../../../../benchmarks/keyed-finite-table-v0.1/ax-b01/fixtures/invalid.input.json"
);
const IR_SHA: &str = "sha256:9a62d3b9397f2db664786d64ad77b848a53c46e62186edc29d2c31f665db9f2a";
const IR_ID: &str = "sha256:90d876b9fdd533944e09f4274ba4aaa313d179454427e60eca81575707054f0b";
const OLD_IR_ID: &str = "sha256:1fa8846fb3ba15937e3e4b5848e74d84d89050711086d7462eb16175510b4154";
const TASK_SHA: &str = "sha256:94da3e83f9767aa8db3321beddbd6ff58ae834a6a7e3564621ef52fb40bb15b0";
const JSON: JsonLimits = JsonLimits {
    max_input_bytes: 64 * 1024,
    max_values: 4096,
    max_nesting: 64,
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
        max_output_bytes: 64 * 1024,
    },
    envelope_bytes: 64 * 1024,
};

fn request<'a>(case: &'a str, slot: FixtureSlot, fixture_bytes: &'a [u8]) -> FixtureConversion<'a> {
    FixtureConversion {
        canonical_ir: PinnedBytes {
            bytes: IR,
            sha256: IR_SHA,
        },
        task: PinnedBytes {
            bytes: TASK,
            sha256: TASK_SHA,
        },
        case,
        slot,
        fixture_bytes,
    }
}

fn fixture_request(fixture: &[u8]) -> FixtureConversion<'_> {
    request("boundary", FixtureSlot::Input, fixture)
}

#[test]
fn reproduces_four_independent_reference_envelopes() {
    for (case, slot, fixture, len, digest) in [
        (
            "base",
            FixtureSlot::Input,
            BASE,
            444,
            "sha256:f2e62589dfdabf4b8da1c7767f48c0a3719cf2ff8418726d3454e95efe2ab307",
        ),
        (
            "base",
            FixtureSlot::Golden,
            BASE_GOLDEN,
            274,
            "sha256:e2395dbafded36de5a4b0974484a1b31c64c6f57e0ac85dce38e143ed2eb88a3",
        ),
        (
            "boundary",
            FixtureSlot::Input,
            BOUNDARY,
            282,
            "sha256:c044278f53053a8b6cbfe787d1099990052c3d045dae2af73e1d0f738152f270",
        ),
        (
            "boundary",
            FixtureSlot::Golden,
            BOUNDARY_GOLDEN,
            243,
            "sha256:d0f8a189b1941f35fcc37ae61cbfba26f0991cf5a591622cfd51aa9ea84369d4",
        ),
    ] {
        let req = request(case, slot, fixture);
        let data = convert_fixture(req, LIMITS).unwrap();
        let role = match slot {
            FixtureSlot::Input => FixtureRole::Input,
            FixtureSlot::Golden => FixtureRole::GoldenOutput,
        };
        assert_eq!(
            data.binding(),
            &HostDataBinding {
                ir_artifact: IR_SHA.into(),
                ir_document_id: IR_ID.into(),
                task_artifact: TASK_SHA.into(),
                benchmark_id: "AX-B01".into(),
                case: case.into(),
                slot,
                source_role: role,
                fixture_artifact: raw_digest(fixture),
                limits: LIMITS,
            }
        );
        assert_eq!(data.canonical_bytes().len(), len);
        assert_eq!(data.artifact_digest(), digest);
        assert_eq!(
            check_host_data(
                req,
                LIMITS,
                PinnedBytes {
                    bytes: data.canonical_bytes(),
                    sha256: digest
                }
            )
            .unwrap(),
            data
        );
    }
}

#[test]
fn independently_rehashed_candidate_cannot_change_version_role_or_case() {
    let req = fixture_request(BOUNDARY);
    let good = convert_fixture(req, LIMITS).unwrap();
    let text = std::str::from_utf8(good.canonical_bytes()).unwrap();
    let wrong_case = convert_fixture(request("base", FixtureSlot::Input, BASE), LIMITS).unwrap();
    let wrong_slot = convert_fixture(
        request("boundary", FixtureSlot::Golden, BOUNDARY_GOLDEN),
        LIMITS,
    )
    .unwrap();
    for candidate in [
        text.replace("\"0.2\"", "\"0.1\""),
        text.replace(IR_ID, OLD_IR_ID),
        text.replace(IR_ID, IR_SHA),
        text.replace("\"input\"", "\"output\""),
        format!("{text}\n"),
        String::from_utf8(wrong_case.bytes).unwrap(),
        String::from_utf8(wrong_slot.bytes).unwrap(),
    ] {
        let bytes = candidate.as_bytes();
        let hash = raw_digest(bytes);
        let error = check_host_data(
            req,
            LIMITS,
            PinnedBytes {
                bytes,
                sha256: &hash,
            },
        )
        .unwrap_err();
        assert_eq!(error.code(), "host-replay-mismatch");
        assert_eq!(error.failure(), ConversionFailure::Error);
    }
    let error = check_host_data(
        req,
        LIMITS,
        PinnedBytes {
            bytes: good.canonical_bytes(),
            sha256: IR_SHA,
        },
    )
    .unwrap_err();
    assert_eq!(error.code(), "host-artifact-mismatch");
}

#[test]
fn pins_both_inputs_and_selects_the_exact_slot() {
    let base = fixture_request(BOUNDARY);
    for (req, code) in [
        (
            FixtureConversion {
                canonical_ir: PinnedBytes {
                    bytes: IR,
                    sha256: IR_ID,
                },
                ..base
            },
            "ir-artifact-mismatch",
        ),
        (
            FixtureConversion {
                task: PinnedBytes {
                    bytes: TASK,
                    sha256: IR_SHA,
                },
                ..base
            },
            "task-artifact-mismatch",
        ),
        (
            FixtureConversion {
                case: "wrong-add",
                ..base
            },
            "task-selection",
        ),
        (
            FixtureConversion {
                case: "invalid",
                slot: FixtureSlot::Golden,
                ..base
            },
            "task-selection",
        ),
        (
            FixtureConversion {
                fixture_bytes: BASE,
                ..base
            },
            "fixture-binding",
        ),
        (
            FixtureConversion {
                fixture_bytes: BOUNDARY_GOLDEN,
                ..base
            },
            "fixture-binding",
        ),
    ] {
        let error = convert_fixture(req, LIMITS).unwrap_err();
        assert_eq!(error.code(), code);
        assert_eq!(error.failure(), ConversionFailure::Error);
    }
    let old = FixtureConversion {
        canonical_ir: PinnedBytes {
            bytes: OLD_IR,
            sha256: &raw_digest(OLD_IR),
        },
        ..base
    };
    assert!(matches!(
        convert_fixture(old, LIMITS),
        Err(HostDataError::IrVersion(IrVersion::V0_1))
    ));
    let noncanonical = [IR, b"\n"].concat();
    let req = FixtureConversion {
        canonical_ir: PinnedBytes {
            bytes: &noncanonical,
            sha256: &raw_digest(&noncanonical),
        },
        ..base
    };
    assert!(matches!(
        convert_fixture(req, LIMITS),
        Err(HostDataError::Ir(cause)) if matches!(*cause, DocumentError::NonCanonical { .. })
    ));
    let crossed = repin_fixture(BOUNDARY, BOUNDARY_GOLDEN);
    let req = FixtureConversion {
        task: PinnedBytes {
            bytes: crossed.as_bytes(),
            sha256: &raw_digest(crossed.as_bytes()),
        },
        fixture_bytes: BOUNDARY_GOLDEN,
        ..base
    };
    assert!(matches!(
        convert_fixture(req, LIMITS),
        Err(HostDataError::Fixture { cause, .. })
            if matches!(*cause, FixtureError::Binding { field: "role" })
    ));

    let duplicate = std::str::from_utf8(TASK)
        .unwrap()
        .replace("\"name\": \"base\"", "\"name\": \"boundary\"");
    let task = duplicate.as_bytes();
    let req = FixtureConversion {
        task: PinnedBytes {
            bytes: task,
            sha256: &raw_digest(task),
        },
        ..base
    };
    assert!(matches!(
        convert_fixture(req, LIMITS),
        Err(HostDataError::TaskSelection("empty or duplicate case name"))
    ));
}

#[test]
fn distinguishes_input_rejection_budget_and_golden_error() {
    let req = request("invalid", FixtureSlot::Input, INVALID);
    let invalid = convert_fixture(req, LIMITS).unwrap_err();
    assert_eq!(invalid.failure(), ConversionFailure::Invalid);
    assert_eq!(invalid.code(), "fixture-precondition");
    assert!(matches!(invalid, HostDataError::Fixture { cause, .. }
        if matches!(cause.as_ref(), FixtureError::Precondition { key, .. } if key == "OX")));
    let no_pre = HostDataLimits {
        fixture: FixtureLimits {
            max_precondition_checks: 0,
            ..LIMITS.fixture
        },
        ..LIMITS
    };
    let exhausted = convert_fixture(req, no_pre).unwrap_err();
    assert_eq!(exhausted.failure(), ConversionFailure::ResourceExhausted);
    assert!(matches!(exhausted, HostDataError::Fixture { cause, .. }
        if matches!(cause.as_ref(), FixtureError::Resource(FixtureResource::PreconditionChecks))));

    let golden = std::str::from_utf8(BOUNDARY_GOLDEN)
        .unwrap()
        .replace("100000", "100001");
    let task = repin_fixture(BOUNDARY_GOLDEN, golden.as_bytes());
    let req = FixtureConversion {
        task: PinnedBytes {
            bytes: task.as_bytes(),
            sha256: &raw_digest(task.as_bytes()),
        },
        ..request("boundary", FixtureSlot::Golden, golden.as_bytes())
    };
    let error = convert_fixture(req, LIMITS).unwrap_err();
    assert_eq!(error.failure(), ConversionFailure::Error);
    assert_eq!(error.code(), "fixture-data");
}

#[test]
fn enforces_the_exact_encoded_byte_budget() {
    let req = fixture_request(BOUNDARY);
    let exact = HostDataLimits {
        envelope_bytes: 282,
        ..LIMITS
    };
    let produced = convert_fixture(req, exact).unwrap();
    assert_eq!(produced.canonical_bytes().len(), 282);
    let short = HostDataLimits {
        envelope_bytes: 281,
        ..LIMITS
    };
    let error = convert_fixture(req, short).unwrap_err();
    assert_eq!(error.failure(), ConversionFailure::ResourceExhausted);
    assert!(matches!(
        error,
        HostDataError::ByteLimit(HostArtifact::Envelope)
    ));
    assert!(matches!(
        check_host_data(
            req,
            short,
            PinnedBytes {
                bytes: produced.canonical_bytes(),
                sha256: produced.artifact_digest()
            }
        ),
        Err(HostDataError::ByteLimit(HostArtifact::Envelope))
    ));
}

fn repin_fixture(old: &[u8], new: &[u8]) -> String {
    let task = std::str::from_utf8(TASK).unwrap();
    assert!(task.contains(&raw_digest(old)));
    task.replace(&raw_digest(old), &raw_digest(new))
}

#[test]
fn encodes_object_keys_by_utf16_and_rows_by_unicode_scalar() {
    let key = '\u{e000}';
    let other = '\u{10000}';
    let id = |kind: ContentKind, definition: &str| {
        content_id(&IrVersion::V0_2.domain(kind), definition.as_bytes())
    };
    let record = format!(
        r#"{{"fields":[{{"label":"public","name":"{key}","type":{{"kind":"text"}}}},{{"label":"public","name":"{other}","type":{{"kind":"text"}}}}]}}"#
    );
    let record_id = id(ContentKind::RecordType, &record);
    let table =
        format!(r#"{{"capacity":"2","primary_key":["{key}"],"record_type":"{record_id}"}}"#);
    let table_id = id(ContentKind::TableType, &table);
    let node = format!(r#"{{"kind":"input","port":"orders","table_type":"{table_id}"}}"#);
    let node_id = id(ContentKind::Node, &node);
    let semantics = IrVersion::V0_2.semantics_sha256();
    let ir = format!(
        r#"{{"contracts":[],"digest_algorithm":"sha-256","effects":[],"enum_types":[],"format":"axiom-ir","ir_version":"0.2","nodes":[{{"definition":{node},"id":"{node_id}"}}],"outputs":[{{"name":"out","node":"{node_id}"}}],"record_types":[{{"definition":{record},"id":"{record_id}"}}],"semantics":{{"name":"keyed-finite-table-semantics","sha256":"{semantics}"}},"table_types":[{{"definition":{table},"id":"{table_id}"}}]}}"#
    );
    let ir = normalize_document(ir.as_bytes(), JSON).unwrap();
    let fixture = format!(
        r#"{{"format":"axiom-benchmark-data","data_version":"0.1","benchmark_id":"AX-B01","role":"input","tables":[{{"name":"orders","rows":[{{"{key}":"{other}","{other}":"next"}},{{"{key}":"{key}","{other}":"quote\"\n"}}]}}]}}"#
    );
    let task = repin_fixture(BOUNDARY, fixture.as_bytes());
    let req = FixtureConversion {
        canonical_ir: PinnedBytes {
            bytes: ir.canonical_bytes(),
            sha256: &raw_digest(ir.canonical_bytes()),
        },
        task: PinnedBytes {
            bytes: task.as_bytes(),
            sha256: &raw_digest(task.as_bytes()),
        },
        ..fixture_request(fixture.as_bytes())
    };
    let data = convert_fixture(req, LIMITS).unwrap();
    let expected_tables = format!(
        r#""tables":[{{"name":"orders","rows":[{{"{other}":"quote\"\n","{key}":"{key}"}},{{"{other}":"next","{key}":"{other}"}}]}}]"#
    );
    assert!(
        std::str::from_utf8(data.canonical_bytes())
            .unwrap()
            .ends_with(&format!("{expected_tables}}}"))
    );
    check_host_data(
        req,
        LIMITS,
        PinnedBytes {
            bytes: data.canonical_bytes(),
            sha256: data.artifact_digest(),
        },
    )
    .unwrap();
}
