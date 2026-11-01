//! Pure private input generation. References bind bytes, never external acceptance.
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
        src!("crates/solver-bootstrap-linux/src/bin/linux_channel_init.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_allocator.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_entry.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_entry_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_init.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_init_tests.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_inputs.rs"),
        src!("crates/solver-bootstrap-linux/src/channel_io.rs"),
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
        src!("scripts/build-linux-channel.py"),
        src!("scripts/check-linux-channel-inputs.py"),
        src!("scripts/check-solver-bootstrap-inputs.py"),
        src!("scripts/cvc5-build-support/channel_report.py"),
        src!("scripts/cvc5-build-support/inspect_linux_host.sh"),
        src!("scripts/test-linux-channel-build.py"),
        src!("scripts/test-linux-channel.py"),
    ]
}
pub fn export() -> Result<Vec<u8>, &'static str> {
    encode("0.1", "offline-source-binding-only", J::N)
}
fn encode(version: &str, scope: &str, build: J) -> Result<Vec<u8>, &'static str> {
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
        ("version", s(version)),
        ("scope", s(scope)),
        ("generator", s(GENERATOR)),
        ("target", s(TARGET)),
        ("profile", s(PROFILE)),
        ("budgets", budgets()),
        ("collector", collector_record()),
        ("collector_reads", reads()),
        ("source_set_digest", s(digest(&sources.bytes()))),
        ("sources", sources),
        ("build_inputs", build),
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

pub const SIDECARS: [&str; 5] = [
    "source-snapshot.json",
    "target-payload.json",
    "tool-inventory.json",
    "build-plan.json",
    "input-review.json",
];
fn hex(text: &str, n: usize) -> bool {
    text.len() == n
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn build_value(raw: &[u8]) -> Result<J, &'static str> {
    let build = crate::channel_json::parse_bounded(raw, 4096)?;
    let fields = build.fields(&["source_commit", "sidecars"])?;
    if !hex(fields[0].1.text()?, 40) {
        return Err("source-commit");
    }
    let refs = fields[1].1.array()?;
    if refs.len() != SIDECARS.len() {
        return Err("sidecars");
    }
    for (item, name) in refs.iter().zip(SIDECARS) {
        let f = item.fields(&["path", "bytes", "digest"])?;
        let size = f[1].1.u()?;
        let hash = f[2].1.text()?;
        if f[0].1.text()? != name
            || size == 0
            || size > 4 * 1024 * 1024
            || !hash.strip_prefix("sha256:").is_some_and(|h| hex(h, 64))
        {
            return Err("sidecar-reference");
        }
    }
    Ok(build)
}
/// Request is only source_commit + five ordered raw-byte references. The host
/// checker must separately reconcile the sidecars, real inputs and review pin.
pub fn export_v02(request: &[u8]) -> Result<Vec<u8>, &'static str> {
    encode("0.2", "target-build-input-binding", build_value(request)?)
}
/// Native validation never reads a sidecar or trusts a runtime path/environment.
pub fn check_native(raw: &[u8]) -> Result<(), &'static str> {
    let value = crate::channel_json::parse_bounded(raw, 1024 * 1024)?;
    let f = value.fields(&[
        "format",
        "version",
        "scope",
        "generator",
        "target",
        "profile",
        "budgets",
        "collector",
        "collector_reads",
        "source_set_digest",
        "sources",
        "build_inputs",
        "native_build",
        "build_ready",
        "execution_ready",
    ])?;
    let expected = export_v02(&f[11].1.bytes())?;
    if raw != expected {
        return Err("native-input-binding");
    }
    Ok(())
}
/// Same binding logic for native and finite host tests. Not an acceptance check.
pub fn native_binding(
    raw: &[u8],
    run_id: [u8; 32],
) -> Result<crate::channel_report::Binding, &'static str> {
    check_native(raw)?;
    Ok(crate::channel_report::Binding {
        run_id,
        input: radishaxiom_digest::digest(raw),
        collector: radishaxiom_digest::digest(COLLECTOR),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn request() -> Vec<u8> {
        obj([
            ("source_commit", s("01".repeat(20))),
            (
                "sidecars",
                J::A(
                    SIDECARS
                        .into_iter()
                        .map(|p| {
                            obj([
                                ("path", s(p)),
                                ("bytes", J::U(1)),
                                ("digest", s(format!("sha256:{}", "02".repeat(32)))),
                            ])
                        })
                        .collect(),
                ),
            ),
        ])
        .bytes()
    }
    #[test]
    fn native_requires_full_version_and_exact_source_capture() {
        assert!(check_native(&export().unwrap()).is_err());
        let raw = export_v02(&request()).unwrap();
        let b = native_binding(&raw, [7; 32]).unwrap();
        assert_eq!(b.input, radishaxiom_digest::digest(&raw));
        for (from, to) in [
            ("target-build-input-binding", "offline-source-binding-only"),
            ("not-accepted", "accepted"),
            ("build_ready\":false", "build_ready\":true"),
            ("sha256:", "sha257:"),
            ("source_commit", "unknown_commit"),
        ] {
            let bad = String::from_utf8(raw.clone())
                .unwrap()
                .replacen(from, to, 1);
            assert!(check_native(bad.as_bytes()).is_err(), "{from}");
        }
        assert!(check_native(b"").is_err());
        assert!(check_native(&vec![b' '; 1024 * 1024 + 1]).is_err());
        assert!(check_native(&raw[..raw.len() - 1]).is_err());
        // Mutating a source digest and recomputing its set digest is still rejected.
        let mut v = crate::channel_json::parse_bounded(&raw, 1024 * 1024).unwrap();
        if let J::O(f) = &mut v {
            if let J::A(rows) = &mut f[10].1
                && let J::O(row) = &mut rows[0]
            {
                row[2].1 = s(format!("sha256:{}", "00".repeat(32)));
            }
            f[9].1 = s(digest(&f[10].1.bytes()));
        }
        assert!(check_native(&v.bytes()).is_err());
    }
    #[test]
    fn request_rejects_null_duplicate_path_bad_sizes_and_digests() {
        for bad in [
            b"null".as_slice(),
            b"{}",
            b"{\"source_commit\":null,\"sidecars\":[]}",
        ] {
            assert!(export_v02(bad).is_err());
        }
        let text = String::from_utf8(request()).unwrap();
        for (from, to) in [
            ("source-snapshot.json", "../source.json"),
            ("bytes\":1", "bytes\":0"),
            ("bytes\":1", "bytes\":4194305"),
            ("sha256:", "sha257:"),
            ("01", "AB"),
        ] {
            assert!(
                export_v02(text.replacen(from, to, 1).as_bytes()).is_err(),
                "{from}"
            );
        }
    }
}
