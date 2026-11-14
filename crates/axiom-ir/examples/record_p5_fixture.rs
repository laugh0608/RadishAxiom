//! P5 本机观察、公开回执与精确材料读回入口。

use std::{
    env,
    error::Error,
    fs::{self, File},
    io::{self, Read, Write},
    path::Path,
    process::ExitCode,
};

use radishaxiom_ir::host_data::{
    FixtureConversion, FixtureSlot, PinnedBytes,
    execution::{
        FixtureCheckerTool, MAX_OBSERVED_INPUT_BYTES, MAX_TOOL_BYTES,
        case::{FixtureCaseRequest, execute_fixture_case},
        execute_fixture,
        receipt::{
            MAX_ACCEPTANCE_BYTES, MAX_PROVENANCE_BYTES, MAX_RECEIPT_BYTES,
            P5_DARWIN_RELEASE_LIMITS, P5ToolAcceptance, check_p5_receipt,
            check_p5_receipt_with_acceptance, record_p5_receipt, record_p5_receipt_with_acceptance,
        },
    },
};

fn main() -> ExitCode {
    match observe() {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::FAILURE,
        Err(error) => {
            eprintln!("P5 observation: {error}");
            ExitCode::from(2)
        }
    }
}

fn observe() -> Result<bool, Box<dyn Error>> {
    enum Mode<'a> {
        Slot(FixtureSlot),
        Case {
            golden: Option<&'a str>,
            output: CaseOutput<'a>,
        },
    }
    enum CaseOutput<'a> {
        Private,
        Receipt {
            check: Option<[&'a str; 2]>,
            acceptance: Option<[&'a str; 3]>,
        },
    }
    let args: Vec<_> = env::args().skip(1).collect();
    let [
        tool_pin,
        ir_path,
        ir_pin,
        task_path,
        task_pin,
        case,
        slot,
        fixture_path,
        limit,
        rest @ ..,
    ] = args.as_slice()
    else {
        return Err("expected: TOOL_SHA IR IR_SHA TASK TASK_SHA CASE MODE FIXTURE ENVELOPE_BYTES [GOLDEN_OR_DASH]".into());
    };
    let mode = match (slot.as_str(), rest) {
        ("input", []) => Mode::Slot(FixtureSlot::Input),
        ("golden", []) => Mode::Slot(FixtureSlot::Golden),
        ("case", [golden]) => Mode::Case {
            golden: (golden != "-").then_some(golden.as_str()),
            output: CaseOutput::Private,
        },
        ("receipt" | "receipt-accepted", [golden, material @ ..])
        | ("receipt-check" | "receipt-check-accepted", [golden, material @ ..]) => {
            let (check, acceptance) = match (slot.as_str(), material) {
                ("receipt", []) => (None, None),
                ("receipt-check", [path, pin]) => (Some([path.as_str(), pin.as_str()]), None),
                ("receipt-accepted", [record, trusted_pin, provenance]) => (
                    None,
                    Some([record.as_str(), trusted_pin.as_str(), provenance.as_str()]),
                ),
                ("receipt-check-accepted", [path, pin, record, trusted_pin, provenance]) => (
                    Some([path.as_str(), pin.as_str()]),
                    Some([record.as_str(), trusted_pin.as_str(), provenance.as_str()]),
                ),
                _ => return Err("invalid receipt, acceptance or provenance arguments".into()),
            };
            Mode::Case {
                golden: (golden != "-").then_some(golden.as_str()),
                output: CaseOutput::Receipt { check, acceptance },
            }
        }
        _ => {
            return Err(
                "expected input, golden, case or a receipt mode with its required arguments".into(),
            );
        }
    };
    let envelope_bytes = limit.parse::<usize>()?;
    if envelope_bytes > P5_DARWIN_RELEASE_LIMITS.envelope_bytes
        || envelope_bytes.to_string() != *limit
    {
        return Err("invalid local envelope limit".into());
    }
    let executable = read_bounded(&env::current_exe()?, MAX_TOOL_BYTES)?;
    let tool = FixtureCheckerTool::bind(PinnedBytes {
        bytes: &executable,
        sha256: tool_pin,
    })?;
    drop(executable);

    let ir = read_bounded(Path::new(ir_path), MAX_OBSERVED_INPUT_BYTES)?;
    let task = read_bounded(Path::new(task_path), MAX_OBSERVED_INPUT_BYTES)?;
    let fixture = read_bounded(Path::new(fixture_path), MAX_OBSERVED_INPUT_BYTES)?;
    let canonical_ir = PinnedBytes {
        bytes: &ir,
        sha256: ir_pin,
    };
    let task = PinnedBytes {
        bytes: &task,
        sha256: task_pin,
    };
    let mut limits = P5_DARWIN_RELEASE_LIMITS;
    limits.envelope_bytes = envelope_bytes;
    let mut output = io::stdout().lock();
    let slot = match mode {
        Mode::Slot(slot) => slot,
        Mode::Case {
            golden: golden_path,
            output: case_output,
        } => {
            let golden = golden_path
                .map(|path| read_bounded(Path::new(path), MAX_OBSERVED_INPUT_BYTES))
                .transpose()?;
            let request = FixtureCaseRequest {
                canonical_ir,
                task,
                case,
                input: &fixture,
                golden: golden.as_deref(),
            };
            if let CaseOutput::Receipt { check, acceptance } = case_output {
                let material = acceptance.map(read_acceptance).transpose()?;
                let approval = material.as_ref().map(|material| P5ToolAcceptance {
                    record: PinnedBytes {
                        bytes: &material.record,
                        sha256: material.trusted_pin,
                    },
                    provenance: &material.provenance,
                });
                if let Some([path, pin]) = check {
                    let bytes = read_bounded(Path::new(path), MAX_RECEIPT_BYTES)?;
                    let proposed = PinnedBytes {
                        bytes: &bytes,
                        sha256: pin,
                    };
                    match approval {
                        Some(approval) => check_p5_receipt_with_acceptance(
                            proposed, &tool, request, limits, approval,
                        )?,
                        None => check_p5_receipt(proposed, &tool, request, limits)?,
                    }
                    return Ok(true);
                }
                let run = match approval {
                    Some(approval) => {
                        record_p5_receipt_with_acceptance(&tool, request, limits, approval)?
                    }
                    None => record_p5_receipt(&tool, request, limits)?,
                };
                output.write_all(run.canonical_receipt())?;
                output.flush()?;
                return Ok(run.execution().completed_pair().is_some());
            }
            let execution = execute_fixture_case(&tool, request, limits)?;
            output.write_all(execution.canonical_record())?;
            for attempt in
                std::iter::once(execution.input_execution()).chain(execution.golden_execution())
            {
                output.write_all(b"\n")?;
                output.write_all(attempt.canonical_record())?;
                if let Ok(envelope) = attempt.outcome() {
                    output.write_all(b"\n")?;
                    output.write_all(envelope.canonical_bytes())?;
                }
            }
            output.flush()?;
            return Ok(execution.completed_pair().is_some());
        }
    };
    let execution = execute_fixture(
        &tool,
        FixtureConversion {
            canonical_ir,
            task,
            case,
            slot,
            fixture_bytes: &fixture,
        },
        limits,
    )?;
    output.write_all(execution.canonical_record())?;
    output.write_all(b"\n")?;
    if let Ok(envelope) = execution.outcome() {
        output.write_all(envelope.canonical_bytes())?;
    }
    output.flush()?;
    Ok(execution.outcome().is_ok())
}

struct AcceptanceMaterial<'a> {
    record: Vec<u8>,
    trusted_pin: &'a str,
    provenance: Vec<u8>,
}

fn read_acceptance(
    [record, trusted_pin, provenance]: [&str; 3],
) -> Result<AcceptanceMaterial<'_>, Box<dyn Error>> {
    if !cfg!(all(
        target_os = "macos",
        target_arch = "aarch64",
        not(debug_assertions)
    )) {
        return Err("tool acceptance CLI requires a Darwin arm64 release candidate".into());
    }
    Ok(AcceptanceMaterial {
        record: read_bounded(Path::new(record), MAX_ACCEPTANCE_BYTES)?,
        trusted_pin,
        provenance: read_bounded(Path::new(provenance), MAX_PROVENANCE_BYTES)?,
    })
}

fn read_bounded(path: &Path, limit: usize) -> Result<Vec<u8>, Box<dyn Error>> {
    let meta = fs::symlink_metadata(path)?;
    if !meta.is_file() || meta.len() > limit as u64 {
        return Err("observation requires a bounded regular file".into());
    }
    let mut bytes = Vec::new();
    File::open(path)?
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > limit {
        return Err("observation file exceeds its byte limit".into());
    }
    Ok(bytes)
}
