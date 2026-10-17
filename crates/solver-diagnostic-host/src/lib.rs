#![forbid(unsafe_code)]

//! ADR 0028 E1–E2 与 ADR 0029 E3 的纯内存模拟组件。所有记录固定 simulation；没有真实执行能力。
//! E0 的工具接受与 E3 的宿主资格尚未闭合，不能从这些模拟声明构造真实能力。

pub mod controller;
pub mod e3_abi;
pub mod e3_cgroup;
pub mod e3_policy;
pub mod e3_supervisor;
pub mod e3_wire;
mod encoding;
pub mod identity;
pub mod observation;
pub mod plan;
pub mod transport;

pub use controller::*;
pub use identity::*;
pub use observation::*;
pub use plan::*;
pub use transport::*;

use radishaxiom_ir::{json::JsonError, solver::SolverError};
use std::fmt;

#[derive(Clone, Copy, Debug)]
pub struct HostLimits {
    pub material_bytes: usize,
    pub total_material_bytes: usize,
    pub record_bytes: usize,
    pub stream_bytes: usize,
    pub control_diagnostic_bytes: usize,
    pub failure_facts: usize,
    pub json_values: usize,
    pub json_nesting: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum HostError {
    ResourceLimit(&'static str),
    BindingMismatch(&'static str),
    InvalidInput(&'static str),
    NonCanonical {
        artifact: &'static str,
        offset: usize,
    },
    SimulationFailure,
    Solver(SolverError),
    Json(JsonError),
}
impl fmt::Display for HostError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "solver simulation: {self:?}")
    }
}
impl std::error::Error for HostError {}
pub type Result<T> = std::result::Result<T, HostError>;

pub fn raw_digest(bytes: &[u8]) -> String {
    format!("sha256:{}", radishaxiom_digest::digest_hex(bytes))
}

fn checked_size(total: usize, add: usize, max: usize, resource: &'static str) -> Result<usize> {
    total
        .checked_add(add)
        .filter(|v| *v <= max)
        .ok_or(HostError::ResourceLimit(resource))
}

fn compare(
    actual: &[u8],
    expected: &[u8],
    artifact: &'static str,
    limits: HostLimits,
) -> Result<()> {
    if actual.len() > limits.record_bytes {
        return Err(HostError::ResourceLimit("record_bytes"));
    }
    if actual == expected {
        return Ok(());
    }
    Err(HostError::NonCanonical {
        artifact,
        offset: actual
            .iter()
            .zip(expected)
            .position(|(a, b)| a != b)
            .unwrap_or(actual.len().min(expected.len())),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn size_accounting_rejects_overflow_without_saturation() {
        assert_eq!(
            checked_size(usize::MAX, 0, usize::MAX, "bytes"),
            Ok(usize::MAX)
        );
        assert_eq!(
            checked_size(usize::MAX, 1, usize::MAX, "bytes"),
            Err(HostError::ResourceLimit("bytes"))
        );
        assert_eq!(
            checked_size(10, 1, 10, "bytes"),
            Err(HostError::ResourceLimit("bytes"))
        );
    }
}
