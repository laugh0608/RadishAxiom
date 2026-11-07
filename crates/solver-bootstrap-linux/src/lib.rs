//! Private native bootstrap source boundary. Opt-in diagnostic leaf; no acceptance bypass.
//! Only the exact Linux AArch64 LE target has a native backend; tests use an
//! explicitly scripted backend and establish no Linux execution fact.
#![deny(unsafe_op_in_unsafe_fn)]
// Only the opt-in diagnostic leaf has a fixed hidden execution bridge.
// Shared modules are typechecked on Darwin so cfg cannot hide their logic.
#![allow(dead_code)]

mod abi;
mod channel_allocator;
mod channel_entry;
mod channel_init;
pub mod channel_inputs;
mod channel_io;
mod channel_json;
pub mod channel_profile;
pub mod channel_report;
mod child;
mod configuration;
mod fd;
mod observation;
mod setup;
mod supervisor;
mod syscall;
#[cfg(test)]
mod test_support;

#[cfg(feature = "linux-channel-entry")]
#[doc(hidden)]
pub use channel_allocator::ChannelAllocator;
#[cfg(all(
    feature = "linux-channel-entry",
    target_os = "linux",
    target_env = "musl",
    target_arch = "aarch64",
    target_endian = "little",
    target_pointer_width = "64"
))]
#[doc(hidden)]
pub fn linux_channel_entry() -> ! {
    channel_entry::native()
}
#[cfg(all(
    feature = "linux-channel-entry",
    target_os = "linux",
    target_env = "musl",
    target_arch = "aarch64",
    target_endian = "little",
    target_pointer_width = "64"
))]
#[doc(hidden)]
pub fn linux_channel_emergency_exit() -> ! {
    channel_entry::emergency()
}
