//! Native LP64 AArch64 LE layouts, separate from core's value codecs.
//! Linux v6.12 UAPI sources and exact field layouts: native-boundary.md.
//! Pointers use u64 to make the target ABI independent of the test host.
pub(crate) use radishaxiom_solver_supervision_core::abi::*;

pub(crate) const O_CLOEXEC: u64 = 0x80000;
pub(crate) const O_NONBLOCK: u64 = 0x800;
pub(crate) const O_NOFOLLOW: u64 = 0x20000;
pub(crate) const FD_CLOEXEC: u64 = 1;
pub(crate) const F_GETFD: u64 = 1;
pub(crate) const F_SETFD: u64 = 2;
pub(crate) const F_SETFL: u64 = 4;
pub(crate) const F_DUPFD_CLOEXEC: u64 = 1030;
pub(crate) const F_ADD_SEALS: u64 = 1033;
pub(crate) const F_GET_SEALS: u64 = 1034;
pub(crate) const ALL_SEALS: u64 = 15;
pub(crate) const NR_DUP3: i32 = 24;
pub(crate) const NR_FSTATFS: i32 = 44;
pub(crate) const NR_FTRUNCATE: i32 = 46;
pub(crate) const NR_OPENAT: i32 = 56;
pub(crate) const NR_PIPE2: i32 = 59;
pub(crate) const NR_PREAD64: i32 = 67;
pub(crate) const NR_READLINKAT: i32 = 78;
pub(crate) const NR_TIMERFD_CREATE: i32 = 85;
pub(crate) const NR_TIMERFD_SETTIME: i32 = 86;
pub(crate) const NR_PRCTL: i32 = 167;
pub(crate) const NR_GETPPID: i32 = 173;
pub(crate) const NR_SOCKETPAIR: i32 = 199;
pub(crate) const NR_RECVMSG: i32 = 212;
pub(crate) const NR_SECCOMP: i32 = 277;
pub(crate) const NR_GETRANDOM: i32 = 278;
pub(crate) const NR_MEMFD_CREATE: i32 = 279;
pub(crate) const NR_CLONE3: i32 = 435;
pub(crate) const NR_CLOSE_RANGE: i32 = 436;
pub(crate) const PR_SET_NO_NEW_PRIVS: u64 = 38;
pub(crate) const PR_GET_NO_NEW_PRIVS: u64 = 39;
pub(crate) const SECCOMP_SET_MODE_FILTER: u64 = 1;
pub(crate) const SECCOMP_GET_NOTIF_SIZES: u64 = 3;
pub(crate) const SECCOMP_FILTER_FLAG_NEW_LISTENER: u64 = 8;
pub(crate) const CLONE_PIDFD: u64 = 0x1000;
pub(crate) const SIGCHLD: u64 = 17;
pub(crate) const SIG_SETMASK: u64 = 2;
// Every kernel signal except unmaskable SIGKILL (9) and SIGSTOP (19).
pub(crate) const BLOCKED_SIGNALS: u64 = !(1 << 8) & !(1 << 18);
pub(crate) const LISTENER_RECORD: &[u8; 8] = b"AXB-LST1";

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub(crate) struct Timespec {
    pub sec: i64,
    pub nsec: i64,
}
impl Timespec {
    pub(crate) fn from_ns(ns: u64) -> Self {
        Self {
            sec: (ns / 1_000_000_000) as i64,
            nsec: (ns % 1_000_000_000) as i64,
        }
    }
    pub(crate) fn ns(self) -> Option<u64> {
        if self.sec < 0 || !(0..1_000_000_000).contains(&self.nsec) {
            return None;
        }
        (self.sec as u64)
            .checked_mul(1_000_000_000)?
            .checked_add(self.nsec as u64)
    }
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Itimer {
    pub interval: Timespec,
    pub value: Timespec,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Stat {
    pub dev: u64,
    pub ino: u64,
    pub mode: u32,
    pub nlink: u32,
    pub uid: u32,
    pub gid: u32,
    pub rdev: u64,
    pub pad1: u64,
    pub size: i64,
    pub blksize: i32,
    pub pad2: i32,
    pub blocks: i64,
    pub atime: i64,
    pub atime_nsec: u64,
    pub mtime: i64,
    pub mtime_nsec: u64,
    pub ctime: i64,
    pub ctime_nsec: u64,
    pub unused: [u32; 2],
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct StatFs {
    pub kind: i64,
    pub bsize: i64,
    pub blocks: i64,
    pub bfree: i64,
    pub bavail: i64,
    pub files: i64,
    pub ffree: i64,
    pub fsid: [i32; 2],
    pub namelen: i64,
    pub frsize: i64,
    pub flags: i64,
    pub spare: [i64; 4],
}
#[repr(C, align(8))]
#[derive(Clone, Copy, Debug)]
pub(crate) struct SigInfo {
    pub bytes: [u8; 128],
}
impl Default for SigInfo {
    fn default() -> Self {
        Self { bytes: [0; 128] }
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct ChildExit {
    pub pid: u32,
    pub uid: u32,
    pub code: i32,
    pub status: i32,
}
impl SigInfo {
    pub(crate) fn child(self) -> Option<ChildExit> {
        let i = |n| i32::from_le_bytes(self.bytes[n..n + 4].try_into().expect("fixed offset"));
        if i(16) == 0 {
            return None;
        }
        Some(ChildExit {
            pid: i(16) as u32,
            uid: i(20) as u32,
            code: i(8),
            status: i(24),
        })
    }
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct PollFd {
    pub fd: i32,
    pub events: i16,
    pub revents: i16,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct CloneArgs {
    pub flags: u64,
    pub pidfd: u64,
    pub child_tid: u64,
    pub parent_tid: u64,
    pub exit_signal: u64,
    pub stack: u64,
    pub stack_size: u64,
    pub tls: u64,
    pub set_tid: u64,
    pub set_tid_size: u64,
    pub cgroup: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct SigAction {
    pub handler: u64,
    pub flags: u64,
    pub restorer: u64,
    pub mask: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct AltStack {
    pub pointer: u64,
    pub flags: i32,
    pub padding: u32,
    pub size: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Iovec {
    pub base: u64,
    pub len: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct MsgHdr {
    pub name: u64,
    pub namelen: i32,
    pub pad: u32,
    pub iov: u64,
    pub iovlen: u64,
    pub control: u64,
    pub controllen: u64,
    pub flags: u32,
    pub tail: u32,
}
#[repr(C, align(8))]
#[derive(Clone, Copy, Debug)]
pub(crate) struct Ancillary {
    pub bytes: [u8; 24],
}
impl Ancillary {
    pub(crate) fn rights(fd: i32) -> Self {
        let mut bytes = [0; 24];
        bytes[..8].copy_from_slice(&20u64.to_le_bytes());
        bytes[8..12].copy_from_slice(&1i32.to_le_bytes());
        bytes[12..16].copy_from_slice(&1i32.to_le_bytes());
        bytes[16..20].copy_from_slice(&fd.to_le_bytes());
        Self { bytes }
    }
}
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub(crate) struct SockFilter {
    pub code: u16,
    pub jt: u8,
    pub jf: u8,
    pub k: u32,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct SockFprog {
    pub len: u16,
    pub pad: [u8; 6],
    pub filter: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use core::mem::{align_of, offset_of, size_of};
    #[test]
    fn native_layouts_match_lp64_uapi() {
        macro_rules! layout {
            ($t:ty,$size:expr,$align:expr) => {
                assert_eq!(size_of::<$t>(), $size);
                assert_eq!(align_of::<$t>(), $align);
            };
        }
        layout!(Stat, 128, 8);
        layout!(StatFs, 120, 8);
        layout!(SigInfo, 128, 8);
        layout!(CloneArgs, 88, 8);
        layout!(SigAction, 32, 8);
        layout!(AltStack, 24, 8);
        layout!(Timespec, 16, 8);
        layout!(Itimer, 32, 8);
        layout!(PollFd, 8, 4);
        layout!(MsgHdr, 56, 8);
        layout!(Iovec, 16, 8);
        layout!(Ancillary, 24, 8);
        layout!(SockFilter, 8, 4);
        layout!(SockFprog, 16, 8);
        assert_eq!(offset_of!(Stat, mode), 16);
        assert_eq!(offset_of!(Stat, size), 48);
        assert_eq!(offset_of!(Stat, blksize), 56);
        assert_eq!(offset_of!(Stat, blocks), 64);
        assert_eq!(offset_of!(Stat, atime), 72);
        assert_eq!(offset_of!(Stat, ctime_nsec), 112);
        assert_eq!(offset_of!(StatFs, fsid), 56);
        assert_eq!(offset_of!(StatFs, flags), 80);
        assert_eq!(offset_of!(CloneArgs, pidfd), 8);
        assert_eq!(offset_of!(CloneArgs, exit_signal), 32);
        assert_eq!(offset_of!(CloneArgs, cgroup), 80);
        assert_eq!(offset_of!(SigAction, mask), 24);
        assert_eq!(offset_of!(AltStack, size), 16);
        assert_eq!(offset_of!(MsgHdr, iov), 16);
        assert_eq!(offset_of!(MsgHdr, control), 32);
        assert_eq!(offset_of!(MsgHdr, flags), 48);
        assert_eq!(offset_of!(SockFprog, filter), 8);
    }
}
