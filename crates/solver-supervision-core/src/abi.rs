//! Linux v6.12 AArch64 little-endian ABI facts for offline E3 models.
//! These are value encodings, never Rust FFI layouts or execution capability.
//! Provenance and the deliberately unimplemented unsafe boundary are documented
//! in docs/query/solver-linux-abi-v0.1.md.

pub const LINUX_UAPI_VERSION: &str = "v6.12";
pub const AUDIT_ARCH_AARCH64: u32 = 0xc000_00b7;
pub const SECCOMP_RET_KILL_PROCESS: u32 = 0x8000_0000;
pub const SECCOMP_RET_USER_NOTIF: u32 = 0x7fc0_0000;
pub const SECCOMP_RET_ALLOW: u32 = 0x7fff_0000;
pub const SECCOMP_USER_NOTIF_FLAG_CONTINUE: u32 = 1;
pub const SECCOMP_IOCTL_NOTIF_RECV: u64 = 0xc050_2100;
pub const SECCOMP_IOCTL_NOTIF_SEND: u64 = 0xc018_2101;
pub const SECCOMP_IOCTL_NOTIF_ID_VALID: u64 = 0x4008_2102;

// scripts/syscall.tbl common/64 entries, selected by the arm64 build rules.
pub const NR_FCNTL: i32 = 25;
pub const NR_IOCTL: i32 = 29;
pub const NR_CLOSE: i32 = 57;
pub const NR_LSEEK: i32 = 62;
pub const NR_READ: i32 = 63;
pub const NR_WRITE: i32 = 64;
pub const NR_READV: i32 = 65;
pub const NR_WRITEV: i32 = 66;
pub const NR_PPOLL: i32 = 73;
pub const NR_FSTAT: i32 = 80;
pub const NR_EXIT: i32 = 93;
pub const NR_EXIT_GROUP: i32 = 94;
pub const NR_WAITID: i32 = 95;
pub const NR_SET_TID_ADDRESS: i32 = 96;
pub const NR_FUTEX: i32 = 98;
pub const NR_SET_ROBUST_LIST: i32 = 99;
pub const NR_CLOCK_GETTIME: i32 = 113;
pub const NR_CLOCK_GETRES: i32 = 114;
pub const NR_SCHED_YIELD: i32 = 124;
pub const NR_SIGALTSTACK: i32 = 132;
pub const NR_RT_SIGACTION: i32 = 134;
pub const NR_RT_SIGPROCMASK: i32 = 135;
pub const NR_RT_SIGRETURN: i32 = 139;
pub const NR_GETRUSAGE: i32 = 165;
pub const NR_GETPID: i32 = 172;
pub const NR_GETTID: i32 = 178;
pub const NR_SENDMSG: i32 = 211;
pub const NR_BRK: i32 = 214;
pub const NR_MUNMAP: i32 = 215;
pub const NR_MREMAP: i32 = 216;
pub const NR_MMAP: i32 = 222;
pub const NR_MPROTECT: i32 = 226;
pub const NR_MADVISE: i32 = 233;
pub const NR_PRLIMIT64: i32 = 261;
pub const NR_EXECVEAT: i32 = 281;
pub const NR_RSEQ: i32 = 293;
pub const NR_PIDFD_SEND_SIGNAL: i32 = 424;

pub const F_GETFL: u64 = 3;
pub const TCGETS: u64 = 0x5401;
pub const AT_EMPTY_PATH: u64 = 0x1000;
pub const MSG_NOSIGNAL: u64 = 0x4000;
pub const MAP_PRIVATE: u64 = 2;
pub const MAP_ANONYMOUS: u64 = 0x20;
pub const MAP_NORESERVE: u64 = 0x4000;
pub const MREMAP_MAYMOVE: u64 = 1;
pub const MADV_DONTNEED: u64 = 4;
pub const MADV_FREE: u64 = 8;
pub const CLOCK_BOOTTIME: u64 = 7;
pub const SIGKILL: u64 = 9;
pub const P_PIDFD: u64 = 3;
pub const WEXITED: u64 = 4;
pub const WNOHANG: u64 = 1;
pub const SEEK_SET: u64 = 0;
pub const RSEQ_SIZE: u64 = 32;
pub const RSEQ_SIG: u64 = 0xd428_bc00;
pub const ROBUST_LIST_HEAD_SIZE: u64 = 24;
pub const KERNEL_SIGSET_SIZE: u64 = 8;

pub const SECCOMP_DATA_SIZE: usize = 64;
pub const SECCOMP_NOTIF_SIZE: usize = 80;
pub const SECCOMP_NOTIF_RESP_SIZE: usize = 24;
pub const SECCOMP_NOTIF_SIZES_SIZE: usize = 6;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AbiError {
    Size,
    UnsupportedNotificationSizes,
}

/// Raw register values, not normalized/truncated syscall arguments.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SeccompData {
    pub nr: i32,
    pub arch: u32,
    pub instruction_pointer: u64,
    pub args: [u64; 6],
}

impl SeccompData {
    pub fn aarch64(nr: i32, args: [u64; 6]) -> Self {
        Self {
            nr,
            arch: AUDIT_ARCH_AARCH64,
            instruction_pointer: 0,
            args,
        }
    }

    pub fn bytes(&self) -> [u8; SECCOMP_DATA_SIZE] {
        let mut bytes = [0; SECCOMP_DATA_SIZE];
        bytes[..4].copy_from_slice(&self.nr.to_le_bytes());
        bytes[4..8].copy_from_slice(&self.arch.to_le_bytes());
        bytes[8..16].copy_from_slice(&self.instruction_pointer.to_le_bytes());
        for (index, arg) in self.args.iter().enumerate() {
            bytes[16 + 8 * index..24 + 8 * index].copy_from_slice(&arg.to_le_bytes());
        }
        bytes
    }

    pub fn decode(bytes: &[u8]) -> Result<Self, AbiError> {
        if bytes.len() != SECCOMP_DATA_SIZE {
            return Err(AbiError::Size);
        }
        let mut args = [0; 6];
        for (index, arg) in args.iter_mut().enumerate() {
            *arg = le64(bytes, 16 + 8 * index);
        }
        Ok(Self {
            nr: le32(bytes, 0) as i32,
            arch: le32(bytes, 4),
            instruction_pointer: le64(bytes, 8),
            args,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SeccompNotification {
    pub id: u64,
    pub pid: u32,
    pub flags: u32,
    pub data: SeccompData,
}

impl SeccompNotification {
    pub fn decode(bytes: &[u8]) -> Result<Self, AbiError> {
        if bytes.len() != SECCOMP_NOTIF_SIZE {
            return Err(AbiError::Size);
        }
        Ok(Self {
            id: le64(bytes, 0),
            pid: le32(bytes, 8),
            flags: le32(bytes, 12),
            data: SeccompData::decode(&bytes[16..])?,
        })
    }
}

/// The future syscall boundary must query sizes before allocating a response.
/// No larger layout is silently accepted by this versioned model.
pub fn validate_notification_sizes(bytes: &[u8]) -> Result<(), AbiError> {
    if bytes.len() != SECCOMP_NOTIF_SIZES_SIZE {
        return Err(AbiError::Size);
    }
    let sizes: Vec<u16> = bytes
        .chunks_exact(2)
        .map(|v| u16::from_le_bytes([v[0], v[1]]))
        .collect();
    if sizes != [80, 24, 64] {
        return Err(AbiError::UnsupportedNotificationSizes);
    }
    Ok(())
}

fn le32(bytes: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes(
        bytes[offset..offset + 4]
            .try_into()
            .expect("checked ABI size"),
    )
}
fn le64(bytes: &[u8], offset: usize) -> u64 {
    u64::from_le_bytes(
        bytes[offset..offset + 8]
            .try_into()
            .expect("checked ABI size"),
    )
}
