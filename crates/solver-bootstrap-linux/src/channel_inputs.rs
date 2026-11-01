//! Explicit pure L1 source export; never a build/acceptance record.
use crate::{
    channel_json::{J, obj, s},
    channel_profile::*,
};
pub const GENERATOR: &str = "crates/solver-bootstrap-linux/examples/export_linux_channel_inputs.rs";
fn captured() -> Vec<(&'static str, &'static [u8])> {
    macro_rules! src {
        ($p:literal) => {
            ($p, include_bytes!(concat!("../../../", $p)).as_slice())
        };
    }
    vec![
        src!("Cargo.lock"),
        src!("Cargo.toml"),
        src!("crates/digest/Cargo.toml"),
        src!("crates/digest/src/lib.rs"),
        src!("crates/solver-bootstrap-linux/Cargo.toml"),
        src!("crates/solver-bootstrap-linux/examples/export_linux_channel_inputs.rs"),
        src!("crates/solver-bootstrap-linux/src/abi.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_init.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_init_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_inputs.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_json.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_profile.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_report.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_report_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/child.rs"),
        src!("crates/solver-bootstrap-linux/src/child_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/configuration.rs"),
        src!("crates/solver-bootstrap-linux/src/fd.rs"),
        src!("crates/solver-bootstrap-linux/src/lib.rs"),
        src!("crates/solver-bootstrap-linux/src/observation.rs"),
        src!("crates/solver-bootstrap-linux/src/observation_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/setup.rs"),
        src!("crates/solver-bootstrap-linux/src/setup_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/supervisor.rs"),
        src!("crates/solver-bootstrap-linux/src/supervisor_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/syscall.rs"),
        src!("crates/solver-bootstrap-linux/src/syscall_channel.rs"),
        src!("crates/solver-bootstrap-linux/src/syscall_listener.rs"),
        src!("crates/solver-bootstrap-linux/src/syscall_signals.rs"),
        src!("crates/solver-bootstrap-linux/src/syscall_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/test_support.rs"),
        src!("crates/solver-supervision-core/Cargo.toml"),
        src!("crates/solver-supervision-core/src/abi.rs"),
        src!("crates/solver-supervision-core/src/bootstrap_start.rs"),
        src!("crates/solver-supervision-core/src/cgroup.rs"),
        src!("crates/solver-supervision-core/src/handshake.rs"),
        src!("crates/solver-supervision-core/src/lib.rs"),
        src!("crates/solver-supervision-core/src/policy.rs"),
        src!("crates/solver-supervision-core/src/policy/supervisor.rs"),
        src!("crates/solver-supervision-core/src/wire.rs"),
        src!("rust-toolchain.toml"),
        src!("scripts/check-linux-channel-inputs.py"),
        src!("scripts/cvc5-build-support/channel_report.py"),
        src!("scripts/cvc5-build-support/inspect_linux_host.sh"),
        src!("scripts/test-linux-channel.py"),
    ]
}
pub fn export() -> Result<Vec<u8>, &'static str> {
    validate_collector(COLLECTOR)?;
    let sources = J::A(
        captured()
            .into_iter()
            .map(|(path, raw)| {
                obj([
                    ("path", s(path)),
                    ("bytes", J::U(raw.len() as u64)),
                    ("digest", s(digest(raw))),
                ])
            })
            .collect(),
    );
    let value = obj([
        ("format", s("radishaxiom-private-linux-channel-inputs")),
        ("version", s("0.1")),
        ("scope", s("offline-source-binding-only")),
        ("generator", s(GENERATOR)),
        ("target", s(TARGET)),
        ("profile", s(PROFILE)),
        ("budgets", budgets()),
        ("collector", collector_record()),
        ("collector_reads", reads()),
        ("source_set_digest", s(digest(&sources.bytes()))),
        ("sources", sources),
        ("build_inputs", J::N),
        ("native_build", s("not-accepted")),
        ("build_ready", J::B(false)),
        ("execution_ready", J::B(false)),
    ]);
    let bytes = value.bytes();
    if bytes.len() > 1024 * 1024 {
        return Err("inputs-size");
    };
    Ok(bytes)
}
pub fn check(raw: &[u8]) -> Result<(), &'static str> {
    if raw != export()? {
        return Err("source-binding");
    };
    Ok(())
}
