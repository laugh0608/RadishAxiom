//! Pure host export only. No Linux backend, build or collector invocation.
use radishaxiom_digest::digest;
use radishaxiom_solver_bootstrap_linux::{channel_inputs, channel_profile, channel_report::*};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args_os().skip(1);
    let first = args.next().ok_or("new output directory required")?;
    let v02 = first == "--v02";
    let (path, inputs) = if v02 {
        let request = std::path::PathBuf::from(args.next().ok_or("request file required")?);
        let path = std::path::PathBuf::from(args.next().ok_or("new output directory required")?);
        // Read at most one bounded request, never load native runtime inputs.
        use std::io::Read;
        let mut raw = Vec::new();
        std::fs::File::open(request)?
            .take(4097)
            .read_to_end(&mut raw)?;
        (path, channel_inputs::export_v02(&raw)?)
    } else {
        (std::path::PathBuf::from(first), channel_inputs::export()?)
    };
    if args.next().is_some() {
        return Err("unexpected argument".into());
    }
    if v02 {
        channel_inputs::check_native(&inputs)?;
    } else {
        channel_inputs::check(&inputs)?;
    }
    std::fs::create_dir(&path)?;
    fn write(p: &std::path::Path, b: &[u8]) -> std::io::Result<()> {
        use std::io::Write;
        std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(p)?
            .write_all(b)
    }
    write(&path.join("inputs.json"), &inputs)?;
    write(&path.join("collector.sh"), channel_profile::COLLECTOR)?;
    // Explicit synthetic interoperability sample, never a runtime observation.
    let binding = Binding {
        run_id: [7; 32],
        input: digest(&inputs),
        collector: digest(channel_profile::COLLECTOR),
    };
    let data = b"synthetic-only\n";
    let mut encoder = Encoder::new(binding.clone());
    let mut wire = encoder.start()?;
    wire.extend(encoder.chunk(1, data)?);
    let e = Exit {
        pid: 42,
        uid: 65532,
        code: 1,
        status: 0,
    };
    let f = Final {
        binding,
        cause: None,
        child_pid: Some(42),
        main_exit: Some(e),
        exits: vec![e],
        signals: vec![],
        errors: vec![],
        clone_attempted: true,
        no_children: true,
        overflowed: false,
        stdout: Stream {
            seen: data.len() as u64,
            exported: data.len() as u32,
            digest: digest(data),
            prefix_only: false,
            eof: true,
        },
        stderr: Stream {
            seen: 0,
            exported: 0,
            digest: digest(b""),
            prefix_only: false,
            eof: true,
        },
        first_ns: 1,
        last_ns: 2,
        capture_failed: false,
        transport_failed: false,
        selected_exit_code: 0,
    };
    wire.extend(encoder.finish(&f)?);
    write(&path.join("synthetic-report.bin"), &wire)?;
    Ok(())
}
