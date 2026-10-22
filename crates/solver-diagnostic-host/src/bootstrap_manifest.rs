//! Explicit offline export inputs for future bootstrap builds. These bytes bind
//! pure resource/policy facts, not a native build, accepted CLI, outer setup
//! policy, image, runtime, or permission to execute. No filesystem access occurs.
use crate::{e3_cgroup, e3_wire, raw_digest};
use radishaxiom_ir::solver::PROCESS_LIMITS;
use radishaxiom_solver_supervision_core::{
    cgroup::CgroupLimits,
    policy::{BOOTSTRAP_SUPERVISOR_ROLES, SupervisorRuntimePolicy, worker_policy},
    wire::WireLimits,
};
use std::fmt::Write;

pub const MANIFEST_FORMAT: &str = "solver-bootstrap-resource-policy-inputs-v0.1";
pub const GENERATOR_ENTRY: &str =
    "crates/solver-diagnostic-host/examples/solver_bootstrap_manifest.rs";

/// Host is the only bridge from the existing P4 resource source to pure rules.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BootstrapResourceInputs {
    pub wire: WireLimits,
    pub cgroup: CgroupLimits,
    pub wall_clock_ms: u64,
    pub semantic_steps: u64,
    pub internal_wall_clock_ms: u64,
}
pub const fn process_resource_inputs() -> BootstrapResourceInputs {
    BootstrapResourceInputs {
        wire: e3_wire::process_wire_limits(),
        cgroup: e3_cgroup::process_cgroup_limits(),
        wall_clock_ms: PROCESS_LIMITS.wall_clock_ms,
        semantic_steps: PROCESS_LIMITS.semantic_steps,
        internal_wall_clock_ms: PROCESS_LIMITS.internal_wall_clock_ms,
    }
}

/// Source bytes are captured by the compiler, never read from mutable disk by
/// the exporter. This is a scoped source inventory, not complete native build
/// provenance (Rust/std/musl/link inputs remain separately unaccepted).
fn sources() -> Vec<(&'static str, &'static [u8])> {
    macro_rules! source {
        ($path:literal) => {
            (
                $path,
                include_bytes!(concat!("../../../", $path)).as_slice(),
            )
        };
    }
    vec![
        source!("Cargo.toml"),
        source!("Cargo.lock"),
        source!("rust-toolchain.toml"),
        source!("crates/axiom-ir/src/solver.rs"),
        source!("crates/digest/Cargo.toml"),
        source!("crates/digest/src/lib.rs"),
        source!("crates/solver-supervision-core/Cargo.toml"),
        source!("crates/solver-supervision-core/src/lib.rs"),
        source!("crates/solver-supervision-core/src/abi.rs"),
        source!("crates/solver-supervision-core/src/bootstrap_start.rs"),
        source!("crates/solver-supervision-core/src/handshake.rs"),
        source!("crates/solver-supervision-core/src/policy.rs"),
        source!("crates/solver-supervision-core/src/policy/supervisor.rs"),
        source!("crates/solver-supervision-core/src/wire.rs"),
        source!("crates/solver-supervision-core/src/cgroup.rs"),
        source!("crates/solver-diagnostic-host/Cargo.toml"),
        source!("crates/solver-diagnostic-host/src/lib.rs"),
        source!("crates/solver-diagnostic-host/src/e3_cgroup.rs"),
        source!("crates/solver-diagnostic-host/src/e3_wire.rs"),
        source!("crates/solver-diagnostic-host/src/bootstrap_manifest.rs"),
        source!("crates/solver-diagnostic-host/src/bootstrap_start.rs"),
        source!("crates/solver-diagnostic-host/examples/solver_bootstrap_manifest.rs"),
    ]
}
fn source_inventory() -> String {
    let mut json = String::from("[");
    for (index, (path, bytes)) in sources().into_iter().enumerate() {
        if index != 0 {
            json.push(',');
        }
        write!(
            json,
            "{{\"path\":\"{path}\",\"bytes\":{},\"digest\":\"{}\"}}",
            bytes.len(),
            raw_digest(bytes)
        )
        .expect("String write");
    }
    json.push(']');
    json
}
fn input_bytes() -> Vec<u8> {
    let v = process_resource_inputs();
    let f = BOOTSTRAP_SUPERVISOR_ROLES;
    format!(concat!(
        "{{\"resources\":{{\"stdin_bytes\":{},\"stdout_bytes\":{},\"stderr_bytes\":{},",
        "\"wall_clock_ms\":{},\"working_memory_bytes\":{},\"swap_bytes\":{},",
        "\"pids_max\":{},\"cgroup_file_bytes\":{},\"semantic_steps\":{},\"internal_wall_clock_ms\":{}}},",
        "\"wire\":{{\"header_bytes\":{},\"binding_bytes\":{},\"payload_bytes\":{},\"chunk_bytes\":{},",
        "\"control_bytes\":{},\"direction_control_bytes\":{},\"pending_bytes\":{}}},",
        "\"supervisor_fd_roles\":{{\"control_input\":{},\"envelope_output\":{},\"diagnostic_output\":{},",
        "\"child_stdin\":{},\"child_stdout\":{},\"child_stderr\":{},\"timer\":{},\"pidfd\":{},\"listener\":{},",
        "\"cgroup\":[{},{},{},{},{},{},{},{},{},{},{},{}]}}}}"),
        v.wire.query_bytes, v.wire.stdout_bytes, v.wire.stderr_bytes, v.wall_clock_ms,
        v.cgroup.memory_max, v.cgroup.swap_max, v.cgroup.pids_max, v.cgroup.file_bytes,
        v.semantic_steps, v.internal_wall_clock_ms,
        e3_wire::BOOTSTRAP_HEADER_BYTES, e3_wire::BOOTSTRAP_BINDING_BYTES,
        e3_wire::BOOTSTRAP_PAYLOAD_LIMIT, e3_wire::BOOTSTRAP_CHUNK_LIMIT,
        e3_wire::BOOTSTRAP_CONTROL_LIMIT, e3_wire::BOOTSTRAP_DIRECTION_CONTROL_LIMIT,
        e3_wire::BOOTSTRAP_PENDING_LIMIT,
        f.control_input, f.envelope_output, f.diagnostic_output, f.child_stdin,
        f.child_stdout, f.child_stderr, f.timer, f.pidfd, f.listener,
        f.cgroup[0],f.cgroup[1],f.cgroup[2],f.cgroup[3],f.cgroup[4],f.cgroup[5],
        f.cgroup[6],f.cgroup[7],f.cgroup[8],f.cgroup[9],f.cgroup[10],f.cgroup[11],
    ).into_bytes()
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OfflineBootstrapInputs {
    pub manifest: Vec<u8>,
    pub inputs: Vec<u8>,
    pub worker_cbpf: Vec<u8>,
    pub supervisor_cbpf: Vec<u8>,
}
pub fn export_offline_inputs() -> OfflineBootstrapInputs {
    let inputs = input_bytes();
    let worker_cbpf = worker_policy().bytes();
    let supervisor_cbpf = SupervisorRuntimePolicy::new(BOOTSTRAP_SUPERVISOR_ROLES)
        .expect("reviewed fixed distinct FD mapping")
        .compile()
        .bytes();
    let sources = source_inventory();
    let manifest = format!(
        concat!(
            "{{\"format\":\"{}\",\"scope\":\"offline-pure-inputs-only\",",
            "\"generator\":\"{}\",\"source_inventory_digest\":\"{}\",\"sources\":{},",
            "\"inputs\":{{\"file\":\"inputs.json\",\"bytes\":{},\"digest\":\"{}\"}},",
            "\"worker\":{{\"file\":\"worker.cbpf.bin\",\"bytes\":{},\"digest\":\"{}\"}},",
            "\"supervisor\":{{\"file\":\"supervisor.cbpf.bin\",\"bytes\":{},\"digest\":\"{}\"}},",
            "\"outer_setup_policy\":\"not-established\",\"native_build\":\"not-accepted\"}}"
        ),
        MANIFEST_FORMAT,
        GENERATOR_ENTRY,
        raw_digest(sources.as_bytes()),
        sources,
        inputs.len(),
        raw_digest(&inputs),
        worker_cbpf.len(),
        raw_digest(&worker_cbpf),
        supervisor_cbpf.len(),
        raw_digest(&supervisor_cbpf),
    )
    .into_bytes();
    OfflineBootstrapInputs {
        manifest,
        inputs,
        worker_cbpf,
        supervisor_cbpf,
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum InputMismatch {
    Manifest,
    Resources,
    WorkerPolicy,
    SupervisorPolicy,
}
/// Bidirectional equality against this build's sources, resource values and
/// generated policies rejects edits, stale source bindings, and mismatched
/// artifact bytes. It does not authenticate the exporter or any native build.
pub fn check_offline_inputs(export: &OfflineBootstrapInputs) -> Result<(), InputMismatch> {
    let expected = export_offline_inputs();
    if export.inputs != expected.inputs {
        return Err(InputMismatch::Resources);
    }
    if export.worker_cbpf != expected.worker_cbpf {
        return Err(InputMismatch::WorkerPolicy);
    }
    if export.supervisor_cbpf != expected.supervisor_cbpf {
        return Err(InputMismatch::SupervisorPolicy);
    }
    if export.manifest != expected.manifest {
        return Err(InputMismatch::Manifest);
    }
    Ok(())
}
