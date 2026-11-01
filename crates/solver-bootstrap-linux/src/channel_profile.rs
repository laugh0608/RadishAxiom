//! Single diagnostic budget source and compile-captured, never executed collector.
use crate::channel_json::{J, obj, s};
use radishaxiom_digest::digest_hex;
pub const PROFILE: &str = "linux-host-observe-v0.1";
pub const TARGET: &str = "aarch64-unknown-linux-musl";
pub const COLLECTOR: &[u8] =
    include_bytes!("../../../scripts/cvc5-build-support/inspect_linux_host.sh");
pub const WORK_NS: u64 = 18_000_000_000;
pub const CLEANUP_NS: u64 = 19_800_000_000;
pub const TOTAL_NS: u64 = 20_000_000_000;
pub const TICK_NS: u64 = 10_000_000;
pub const CHILD_LIMIT: usize = 15;
pub const EVENT_LIMIT: usize = 64;
pub const WIRE_LIMIT: usize = 2 * 1024 * 1024;
pub const FRAME_LIMIT: usize = 8192;
pub const CHUNK_LIMIT: usize = 4096;
pub const START_LIMIT: usize = 4096;
pub const FINAL_LIMIT: usize = 32768;
pub const STDOUT_LIMIT: usize = 1536 * 1024;
pub const STDERR_LIMIT: usize = 65536;
pub fn digest(raw: &[u8]) -> String {
    format!("sha256:{}", digest_hex(raw))
}
pub fn validate_collector(raw: &[u8]) -> Result<(), &'static str> {
    if raw.is_empty()
        || raw.len() > 32768
        || raw.starts_with(&[239, 187, 191])
        || !raw.ends_with(b"\n")
        || raw.contains(&0)
        || raw.contains(&b'\r')
        || std::str::from_utf8(raw).is_err()
    {
        return Err("collector-encoding");
    };
    Ok(())
}
pub(crate) fn budgets() -> J {
    obj([
        ("work_ns", J::U(WORK_NS)),
        ("cleanup_ns", J::U(CLEANUP_NS)),
        ("total_ns", J::U(TOTAL_NS)),
        ("memory_bytes", J::U(134217728)),
        ("swap_bytes", J::U(0)),
        ("pids", J::U(16)),
        ("nofile", J::U(64)),
        ("wire_bytes", J::U(WIRE_LIMIT as u64)),
        ("frames", J::U(FRAME_LIMIT as u64)),
        ("chunk_bytes", J::U(CHUNK_LIMIT as u64)),
        ("start_bytes", J::U(START_LIMIT as u64)),
        ("final_bytes", J::U(FINAL_LIMIT as u64)),
        ("stdout_bytes", J::U(STDOUT_LIMIT as u64)),
        ("stderr_bytes", J::U(STDERR_LIMIT as u64)),
        ("events", J::U(EVENT_LIMIT as u64)),
    ])
}
pub(crate) fn collector_record() -> J {
    obj([
        (
            "path",
            s("scripts/cvc5-build-support/inspect_linux_host.sh"),
        ),
        ("profile", s(PROFILE)),
        ("bytes", J::U(COLLECTOR.len() as u64)),
        ("digest", s(digest(COLLECTOR))),
    ])
}

pub(crate) fn reads() -> J {
    let fixed = [
        ("/proc/self/status", 65536),
        ("/proc/self/mountinfo", 1048576),
        ("/proc/self/cgroup", 4096),
        ("/proc/self/uid_map", 4096),
        ("/proc/self/gid_map", 4096),
        ("/host-observe/boot-id", 4096),
        ("/host-observe/filesystems", 65536),
        ("/host-observe/init-mountinfo", 1048576),
        ("/host-observe/cgroup/cgroup.controllers", 4096),
        ("/host-observe/cgroup/cgroup.subtree_control", 4096),
    ];
    let mut v: Vec<J> = fixed
        .into_iter()
        .map(|(p, n)| obj([("path", s(p)), ("bytes", J::U(n))]))
        .collect();
    for name in [
        "memory.max",
        "memory.swap.max",
        "pids.max",
        "cpu.max",
        "cgroup.type",
        "cgroup.events",
        "memory.events",
    ] {
        v.push(obj([
            (
                "path",
                s(format!("/host-observe/cgroup/<own-nonroot>/{name}")),
            ),
            ("bytes", J::U(4096)),
        ]));
    }
    for name in ["pid", "mnt", "cgroup", "user", "ipc", "uts"] {
        v.push(obj([
            ("path", s(format!("/proc/self/ns/{name}"))),
            ("bytes", J::U(4096)),
        ]));
    }
    J::A(v)
}
