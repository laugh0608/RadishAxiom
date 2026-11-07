//! Opt-in private diagnostic leaf. Never run as a host check or solver entry.
#[cfg(all(
    target_os = "linux",
    target_env = "musl",
    target_arch = "aarch64",
    target_endian = "little",
    target_pointer_width = "64"
))]
#[global_allocator]
static ALLOCATOR: radishaxiom_solver_bootstrap_linux::ChannelAllocator<std::alloc::System> =
    // SAFETY: the dedicated raw exit bridge has no allocation or unwind path.
    unsafe {
        radishaxiom_solver_bootstrap_linux::ChannelAllocator::new(
            std::alloc::System,
            radishaxiom_solver_bootstrap_linux::linux_channel_emergency_exit,
        )
    };

fn main() {
    #[cfg(all(
        target_os = "linux",
        target_env = "musl",
        target_arch = "aarch64",
        target_endian = "little",
        target_pointer_width = "64"
    ))]
    radishaxiom_solver_bootstrap_linux::linux_channel_entry();
    #[cfg(not(all(
        target_os = "linux",
        target_env = "musl",
        target_arch = "aarch64",
        target_endian = "little",
        target_pointer_width = "64"
    )))]
    std::process::exit(125);
}
