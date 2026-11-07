//! Dedicated binary allocator wrapper. No global allocator is set by the library.
use std::alloc::{GlobalAlloc, Layout};

#[doc(hidden)]
pub struct ChannelAllocator<A> {
    inner: A,
    exit: fn() -> !,
}
impl<A> ChannelAllocator<A> {
    /// # Safety
    /// `exit` must terminate without unwinding, allocating or reentering this
    /// allocator, including before main and during allocation failure.
    pub const unsafe fn new(inner: A, exit: fn() -> !) -> Self {
        Self { inner, exit }
    }
}
// Kept outside GlobalAlloc so null handling can be fault-injected without ever
// unwinding through a GlobalAlloc method (which would violate its contract).
fn require(ptr: *mut u8, exit: fn() -> !) -> *mut u8 {
    if ptr.is_null() {
        exit();
    }
    ptr
}
// SAFETY: forwards the caller's exact allocation/layout contract to A; no
// allocation, formatting, retry or IO on failure. Production exit never unwinds.
unsafe impl<A: GlobalAlloc> GlobalAlloc for ChannelAllocator<A> {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        require(unsafe { self.inner.alloc(layout) }, self.exit)
    }
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        require(unsafe { self.inner.alloc_zeroed(layout) }, self.exit)
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, size: usize) -> *mut u8 {
        require(unsafe { self.inner.realloc(ptr, layout, size) }, self.exit)
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { self.inner.dealloc(ptr, layout) }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::{alloc::System, panic::catch_unwind};
    fn scripted_exit() -> ! {
        std::panic::panic_any(125u8)
    }
    #[test]
    fn null_failure_uses_only_terminal_callback() {
        // No GlobalAlloc method or actual OOM participates in this injection.
        assert_eq!(
            *catch_unwind(|| require(std::ptr::null_mut(), scripted_exit))
                .unwrap_err()
                .downcast::<u8>()
                .unwrap(),
            125
        );
    }
    #[test]
    fn system_layout_zeroing_reallocation_and_release_are_forwarded() {
        // SAFETY: abort terminates without allocation or unwinding; no actual
        // failure is induced inside a GlobalAlloc method.
        let a = unsafe { ChannelAllocator::new(System, std::process::abort) };
        let layout = Layout::from_size_align(32, 16).unwrap();
        // SAFETY: nonzero valid layouts, each allocation released exactly once.
        unsafe {
            let p = a.alloc(layout);
            assert_eq!((p as usize) % 16, 0);
            p.write(7);
            let p = a.realloc(p, layout, 64);
            assert_eq!(p.read(), 7);
            a.dealloc(p, Layout::from_size_align(64, 16).unwrap());
            let p = a.alloc_zeroed(layout);
            assert_eq!(std::slice::from_raw_parts(p, 32), &[0; 32]);
            a.dealloc(p, layout);
        }
    }
}
