//! Explicit FD ownership: no implicit destructor can run in B or after seccomp.

/// A unique descriptor token. Intentionally neither Clone nor Copy nor Drop.
/// Linux close releases the descriptor even on EINTR: it is never retried.
#[derive(Debug, Eq, PartialEq)]
#[must_use = "an owned descriptor must be explicitly closed or transferred"]
pub(crate) struct OwnedFd(i32);
impl OwnedFd {
    /// # Safety
    /// `raw` must be nonnegative and uniquely owned by the caller, acquired by a
    /// successful kernel operation; no other owner may close or replace it.
    pub(crate) unsafe fn from_raw(raw: i32) -> Self {
        Self(raw)
    }
    pub(crate) fn raw(&self) -> i32 {
        self.0
    }
    pub(crate) fn into_raw(self) -> i32 {
        self.0
    }
}
