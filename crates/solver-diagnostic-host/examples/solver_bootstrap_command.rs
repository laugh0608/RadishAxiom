//! Explicit offline-only export; never a build.rs or native/solver invocation.
use radishaxiom_solver_diagnostic_host::bootstrap_command::{
    check_offline_command, export_offline_command,
};
use std::{
    env, fs,
    io::Write,
    path::{Component, Path},
};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let argument = env::args()
        .nth(1)
        .ok_or("usage: solver_bootstrap_command .tmp/<new-output>")?;
    if env::args().len() != 2 {
        return Err("exactly one output argument required".into());
    }
    let relative = Path::new(&argument);
    if relative.is_absolute()
        || !relative.starts_with(".tmp")
        || relative.components().count() != 2
        || relative
            .components()
            .any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err("output must be a new .tmp/<name> directory".into());
    }
    let output = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join(relative);
    let export = export_offline_command();
    check_offline_command(&export).map_err(|e| format!("offline input mismatch: {e:?}"))?;
    fs::create_dir(&output)?;
    for (name, bytes) in [
        ("manifest.json", export.manifest),
        ("command.bin", export.command),
    ] {
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(output.join(name))?;
        file.write_all(&bytes)?;
    }
    Ok(())
}
