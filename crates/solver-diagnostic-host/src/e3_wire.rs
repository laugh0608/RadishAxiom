//! Compatibility codec using the existing P4 resource source.
use radishaxiom_solver_supervision_core::wire as core;
pub use radishaxiom_solver_supervision_core::wire::{
    Arm, BOOTSTRAP_BINDING_BYTES, BOOTSTRAP_CHUNK_LIMIT, BOOTSTRAP_CONTROL_LIMIT,
    BOOTSTRAP_DIRECTION_CONTROL_LIMIT, BOOTSTRAP_HEADER_BYTES, BOOTSTRAP_PAYLOAD_LIMIT,
    BOOTSTRAP_PENDING_LIMIT, BootstrapBinding, BootstrapFrame, BootstrapMessage, ChildExit,
    DecodeStep, Direction, FailureReason, Final, Ready, WireError, WireLimits, WireResult,
};
pub const BOOTSTRAP_QUERY_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stdin_bytes;
pub const BOOTSTRAP_STDOUT_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stdout_bytes;
pub const BOOTSTRAP_STDERR_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stderr_bytes;
pub const fn process_wire_limits() -> WireLimits {
    WireLimits {
        query_bytes: BOOTSTRAP_QUERY_LIMIT,
        stdout_bytes: BOOTSTRAP_STDOUT_LIMIT,
        stderr_bytes: BOOTSTRAP_STDERR_LIMIT,
    }
}

#[derive(Clone, Debug)]
pub struct BootstrapDecoder(core::BootstrapDecoder);
impl BootstrapDecoder {
    pub fn new(direction: Direction) -> Self {
        Self(core::BootstrapDecoder::new(
            direction,
            process_wire_limits(),
        ))
    }

    pub fn new_bound(direction: Direction, binding: BootstrapBinding) -> Self {
        Self(core::BootstrapDecoder::new_bound(
            direction,
            binding,
            process_wire_limits(),
        ))
    }
    pub fn is_poisoned(&self) -> bool {
        self.0.is_poisoned()
    }
    pub fn buffered_bytes(&self) -> usize {
        self.0.buffered_bytes()
    }
    pub fn control_bytes(&self) -> usize {
        self.0.control_bytes()
    }
    pub fn poll(&mut self, bytes: &[u8]) -> WireResult<DecodeStep> {
        self.0.poll(bytes)
    }
    pub fn end_of_input(&mut self) -> WireResult<()> {
        self.0.end_of_input()
    }
}

#[derive(Clone, Debug)]
pub struct BootstrapEncoder(core::BootstrapEncoder);
impl BootstrapEncoder {
    pub fn new(direction: Direction) -> Self {
        Self(core::BootstrapEncoder::new(
            direction,
            process_wire_limits(),
        ))
    }

    pub fn is_poisoned(&self) -> bool {
        self.0.is_poisoned()
    }
    pub fn encode(&mut self, frame: &BootstrapFrame) -> WireResult<Vec<u8>> {
        self.0.encode(frame)
    }
}

#[derive(Clone, Debug)]
pub struct PendingFrameBuffer(core::PendingFrameBuffer);
impl PendingFrameBuffer {
    pub fn new(direction: Direction) -> Self {
        Self(core::PendingFrameBuffer::new(
            direction,
            process_wire_limits(),
        ))
    }

    pub fn is_poisoned(&self) -> bool {
        self.0.is_poisoned()
    }
    pub fn push(&mut self, frame: &BootstrapFrame) -> WireResult<()> {
        self.0.push(frame)
    }
    pub fn remaining(&self) -> &[u8] {
        self.0.remaining()
    }
    pub fn consume(&mut self, count: usize) -> WireResult<()> {
        self.0.consume(count)
    }
}
