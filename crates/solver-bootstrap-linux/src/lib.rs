//! Private native bootstrap source boundary. No executable or acceptance bypass.
//! Only the exact Linux AArch64 LE target has a native backend; tests use an
//! explicitly scripted backend and establish no Linux execution fact.
#![deny(unsafe_op_in_unsafe_fn)]
// This crate has no public execution API. Internal modules are independently
// typechecked on Darwin so target cfg cannot hide the protocol implementation.
#![allow(dead_code)]

mod abi;
mod child;
mod configuration;
mod fd;
mod observation;
mod setup;
mod supervisor;
mod syscall;
#[cfg(test)]
mod test_support;
