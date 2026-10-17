//! Exports synthetic E3 wire/policy bytes for the separate Python verifier.
//! This executable runs only pure simulation, never the payload or Linux ABI.
#[path = "../tests/common/mod.rs"]
mod common;
#[path = "../tests/common/e3_workflow.rs"]
mod e3_workflow;
use radishaxiom_solver_diagnostic_host::e3_policy::{
    supervisor::{SupervisorFdRoles, SupervisorRuntimePolicy},
    worker_policy,
};
use std::{
    env, fs,
    io::Write,
    path::{Component, Path},
};

fn write(directory: &Path, name: &str, bytes: &[u8]) -> std::io::Result<()> {
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(directory.join(name))?;
    file.write_all(bytes)
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let argument = env::args()
        .nth(1)
        .ok_or("usage: export_e3_offline .tmp/<new-output>")?;
    let relative = Path::new(&argument);
    if relative.is_absolute()
        || !relative.starts_with(".tmp")
        || relative
            .components()
            .any(|c| !matches!(c, Component::Normal(_)))
        || relative.components().count() != 2
    {
        return Err("output must be a new .tmp/<name> directory".into());
    }
    let directory = common::root().join(relative);
    fs::create_dir(&directory)?;
    let artifact = e3_workflow::full_workflow();
    for (name, bytes) in [
        ("binding.bin", artifact.binding),
        ("query.smt2", artifact.query),
        ("stdout.bin", artifact.stdout),
        ("stderr.bin", artifact.stderr),
        ("mac.wire", artifact.mac_wire),
        ("supervisor.wire", artifact.supervisor_wire),
        ("replay.json", artifact.replay),
        ("request.json", artifact.request),
        ("response.json", artifact.response),
        ("candidate.json", artifact.candidate),
        ("world.json", artifact.world),
    ] {
        write(&directory, name, &bytes)?;
    }
    write(&directory, "worker.cbpf.bin", &worker_policy().bytes())?;
    let supervisor = SupervisorRuntimePolicy::new(SupervisorFdRoles {
        control_input: 0,
        envelope_output: 1,
        diagnostic_output: 2,
        child_stdin: 10,
        child_stdout: 11,
        child_stderr: 12,
        timer: 13,
        pidfd: 14,
        listener: 15,
        cgroup: [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
    })
    .expect("fixed synthetic roles are distinct");
    write(
        &directory,
        "supervisor.cbpf.bin",
        &supervisor.compile().bytes(),
    )?;
    println!("simulation-only exports: {}", directory.display());
    Ok(())
}
