//! 本机受限的 P5 观察入口。stdout 首行是记录，成功时随后是封套原字节。

use std::{
    env,
    error::Error,
    fs::{self, File},
    io::{self, Read, Write},
    path::Path,
    process::ExitCode,
};

use radishaxiom_ir::{
    fixtures::FixtureLimits,
    host_data::{
        FixtureConversion, FixtureSlot, HostDataLimits, PinnedBytes,
        execution::{
            FixtureCheckerTool, MAX_OBSERVED_INPUT_BYTES, MAX_TOOL_BYTES, execute_fixture,
        },
    },
    json::JsonLimits,
};

const JSON: JsonLimits = JsonLimits {
    max_input_bytes: 64 * 1024,
    max_values: 4096,
    max_nesting: 64,
};
const FIXTURE: FixtureLimits = FixtureLimits {
    fixture_json: JSON,
    ir_json: JSON,
    max_tables: 4,
    max_rows: 256,
    max_integer_digits: 64,
    max_precondition_checks: 256,
    max_output_bytes: 64 * 1024,
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
    ] = args.as_slice()
    else {
        return Err("expected: TOOL_SHA IR IR_SHA TASK TASK_SHA CASE INPUT_OR_GOLDEN FIXTURE ENVELOPE_BYTES".into());
    };
    let slot = match slot.as_str() {
        "input" => FixtureSlot::Input,
        "golden" => FixtureSlot::Golden,
        _ => return Err("expected input or golden slot".into()),
    };
    let envelope_bytes = limit.parse::<usize>()?;
    if envelope_bytes > JSON.max_input_bytes || envelope_bytes.to_string() != *limit {
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
    let execution = execute_fixture(
        &tool,
        FixtureConversion {
            canonical_ir: PinnedBytes {
                bytes: &ir,
                sha256: ir_pin,
            },
            task: PinnedBytes {
                bytes: &task,
                sha256: task_pin,
            },
            case,
            slot,
            fixture_bytes: &fixture,
        },
        HostDataLimits {
            task_json: JSON,
            fixture: FIXTURE,
            envelope_bytes,
        },
    )?;
    let mut output = io::stdout().lock();
    output.write_all(execution.canonical_record())?;
    output.write_all(b"\n")?;
    if let Ok(envelope) = execution.outcome() {
        output.write_all(envelope.canonical_bytes())?;
    }
    output.flush()?;
    Ok(execution.outcome().is_ok())
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
