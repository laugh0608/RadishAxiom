//! Typed kernel operations. No public arbitrary syscall or raw-pointer entry.
use crate::{abi::*, fd::OwnedFd};
use radishaxiom_solver_supervision_core::{abi as core_abi, policy::OfflinePolicy};
use std::ffi::CStr;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Call {
    pub nr: i32,
    pub args: [u64; 6],
}
/// # Safety
/// Implementations must obey the Linux v6.12 AArch64 syscall memory contracts:
/// only access documented pointer extents synchronously, preserve memory beyond
/// those extents, and return raw negative errno. Scripted implementations must
/// explicitly model each write, never call a host OS fallback or retain pointers.
pub(crate) unsafe trait Kernel {
    unsafe fn invoke(&mut self, call: Call) -> u64;
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ErrorKind {
    Errno(u16),
    InvalidInput,
    InvalidReturn,
    UnexpectedLayout,
    Ownership,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Error {
    pub operation: &'static str,
    pub kind: ErrorKind,
}
impl Error {
    pub(crate) fn invalid(operation: &'static str) -> Self {
        Self {
            operation,
            kind: ErrorKind::InvalidInput,
        }
    }
    pub(crate) fn returned(operation: &'static str) -> Self {
        Self {
            operation,
            kind: ErrorKind::InvalidReturn,
        }
    }
    pub(crate) fn errno(self) -> Option<u16> {
        if let ErrorKind::Errno(e) = self.kind {
            Some(e)
        } else {
            None
        }
    }
}
pub(crate) type Result<T> = core::result::Result<T, Error>;
pub(crate) fn decode(operation: &'static str, raw: u64) -> Result<u64> {
    if raw >= u64::MAX - 4094 {
        Err(Error {
            operation,
            kind: ErrorKind::Errno(raw.wrapping_neg() as u16),
        })
    } else {
        Ok(raw)
    }
}
fn fd_arg(fd: i32) -> Result<u64> {
    u64::try_from(fd).map_err(|_| Error::invalid("descriptor"))
}
fn count(operation: &'static str, result: u64, size: usize) -> Result<usize> {
    let n = usize::try_from(result).map_err(|_| Error::returned(operation))?;
    if n > size {
        Err(Error::returned(operation))
    } else {
        Ok(n)
    }
}
fn own(operation: &'static str, raw: u64) -> Result<OwnedFd> {
    let fd = i32::try_from(raw).map_err(|_| Error::returned(operation))?;
    // SAFETY: only successful descriptor-producing operations reach this helper;
    // Linux gives the process a newly allocated, uniquely owned descriptor.
    Ok(unsafe { OwnedFd::from_raw(fd) })
}

pub(crate) struct Linux<K> {
    pub(crate) kernel: K,
    inherited_taken: bool,
}
impl<K: Kernel> Linux<K> {
    pub(crate) fn new(kernel: K) -> Self {
        Self {
            kernel,
            inherited_taken: false,
        }
    }
    /// The caller must construct all pointed-to objects in typed wrappers below.
    /// # Safety
    /// All pointers/lengths in call must be valid for this operation until return.
    pub(crate) unsafe fn call(&mut self, operation: &'static str, call: Call) -> Result<u64> {
        // SAFETY: forwarded local wrapper preconditions; Kernel's implementation
        // contract prevents access outside the syscall's documented buffers.
        decode(operation, unsafe { self.kernel.invoke(call) })
    }
    /// # Safety
    /// Same operation-specific buffer requirements as `call`.
    unsafe fn call_zero(&mut self, operation: &'static str, call: Call) -> Result<()> {
        // SAFETY: forwarded exact buffer preconditions from each typed wrapper.
        if unsafe { self.call(operation, call) }? != 0 {
            return Err(Error::returned(operation));
        }
        Ok(())
    }
    fn scalar(&mut self, operation: &'static str, nr: i32, args: [u64; 6]) -> Result<u64> {
        // SAFETY: scalar helper is private; its callers use only pointer-free calls.
        unsafe { self.call(operation, Call { nr, args }) }
    }
    fn scalar_zero(&mut self, operation: &'static str, nr: i32, args: [u64; 6]) -> Result<()> {
        if self.scalar(operation, nr, args)? != 0 {
            return Err(Error::returned(operation));
        }
        Ok(())
    }
    pub(crate) fn read(&mut self, fd: i32, out: &mut [u8]) -> Result<usize> {
        let args = [
            fd_arg(fd)?,
            out.as_mut_ptr() as u64,
            out.len() as u64,
            0,
            0,
            0,
        ];
        // SAFETY: out is uniquely borrowed and live for exactly out.len() bytes.
        let n = unsafe { self.call("read", Call { nr: NR_READ, args }) }?;
        count("read", n, out.len())
    }
    pub(crate) fn write(&mut self, fd: i32, bytes: &[u8]) -> Result<usize> {
        let args = [
            fd_arg(fd)?,
            bytes.as_ptr() as u64,
            bytes.len() as u64,
            0,
            0,
            0,
        ];
        // SAFETY: bytes is live immutable storage; write only reads these bytes.
        let n = unsafe { self.call("write", Call { nr: NR_WRITE, args }) }?;
        count("write", n, bytes.len())
    }
    pub(crate) fn pread(&mut self, fd: i32, out: &mut [u8], offset: u64) -> Result<usize> {
        if offset > i64::MAX as u64 {
            return Err(Error::invalid("pread64"));
        }
        let args = [
            fd_arg(fd)?,
            out.as_mut_ptr() as u64,
            out.len() as u64,
            offset,
            0,
            0,
        ];
        // SAFETY: the exclusive slice bounds the only writable buffer.
        let n = unsafe {
            self.call(
                "pread64",
                Call {
                    nr: NR_PREAD64,
                    args,
                },
            )
        }?;
        count("pread64", n, out.len())
    }
    pub(crate) fn rewind(&mut self, fd: i32) -> Result<()> {
        match self.scalar("lseek", NR_LSEEK, [fd_arg(fd)?, 0, SEEK_SET, 0, 0, 0])? {
            0 => Ok(()),
            _ => Err(Error::returned("lseek")),
        }
    }
    pub(crate) fn fstat(&mut self, fd: i32) -> Result<Stat> {
        let mut out = Stat::default();
        // SAFETY: out has the fixed 128-byte AArch64 layout and exclusive lifetime.
        unsafe {
            self.call_zero(
                "fstat",
                Call {
                    nr: NR_FSTAT,
                    args: [fd_arg(fd)?, &mut out as *mut _ as u64, 0, 0, 0, 0],
                },
            )
        }?;
        Ok(out)
    }
    pub(crate) fn fstatfs(&mut self, fd: i32) -> Result<StatFs> {
        let mut out = StatFs::default();
        // SAFETY: out has the fixed 120-byte AArch64 layout and exclusive lifetime.
        unsafe {
            self.call_zero(
                "fstatfs",
                Call {
                    nr: NR_FSTATFS,
                    args: [fd_arg(fd)?, &mut out as *mut _ as u64, 0, 0, 0, 0],
                },
            )
        }?;
        Ok(out)
    }
    pub(crate) fn open_readonly(&mut self, path: &CStr) -> Result<OwnedFd> {
        let args = [
            (-100i64) as u64,
            path.as_ptr() as u64,
            O_CLOEXEC | O_NOFOLLOW,
            0,
            0,
            0,
        ];
        // SAFETY: CStr provides a live NUL-terminated input; flags are read-only.
        let n = unsafe {
            self.call(
                "openat-readonly",
                Call {
                    nr: NR_OPENAT,
                    args,
                },
            )
        }?;
        own("openat", n)
    }
    pub(crate) fn open_fd_inventory(&mut self) -> Result<OwnedFd> {
        // /proc/self/fd is a directory; open_readonly deliberately rejects final
        // symlinks but permits this fixed procfs directory, never an input path.
        self.open_readonly(c"/proc/self/fd")
    }
    pub(crate) fn read_directory(&mut self, fd: i32, out: &mut [u8]) -> Result<usize> {
        // SAFETY: kernel writes bounded linux_dirent64 bytes into exclusive out;
        // callers parse offsets from bytes, never cast unaligned records.
        let n = unsafe {
            self.call(
                "getdents64",
                Call {
                    nr: 61,
                    args: [
                        fd_arg(fd)?,
                        out.as_mut_ptr() as u64,
                        out.len() as u64,
                        0,
                        0,
                        0,
                    ],
                },
            )
        }?;
        count("getdents64", n, out.len())
    }
    pub(crate) fn readlink(&mut self, path: &CStr, out: &mut [u8]) -> Result<usize> {
        // SAFETY: path is NUL-terminated; kernel writes at most exclusive out.len().
        let n = unsafe {
            self.call(
                "readlinkat",
                Call {
                    nr: NR_READLINKAT,
                    args: [
                        (-100i64) as u64,
                        path.as_ptr() as u64,
                        out.as_mut_ptr() as u64,
                        out.len() as u64,
                        0,
                        0,
                    ],
                },
            )
        }?;
        count("readlinkat", n, out.len())
    }
    fn pair(&mut self, socket: bool) -> Result<[OwnedFd; 2]> {
        let mut out = [-1i32; 2];
        let (nr, args) = if socket {
            (
                NR_SOCKETPAIR,
                [1, 5 | O_CLOEXEC, 0, out.as_mut_ptr() as u64, 0, 0],
            )
        } else {
            (NR_PIPE2, [out.as_mut_ptr() as u64, O_CLOEXEC, 0, 0, 0, 0])
        };
        // SAFETY: out is a live two-i32 exclusive output for pipe2/socketpair.
        let result = unsafe {
            self.call_zero(
                if socket { "socketpair" } else { "pipe2" },
                Call { nr, args },
            )
        };
        if result.is_err() || out[0] < 0 || out[1] < 0 || out[0] == out[1] {
            // Even anomalous kernel/script output must not leak a received fd.
            let mut failure = result.err().unwrap_or(Error::returned("pair"));
            for (index, raw) in out.into_iter().enumerate() {
                if raw >= 0
                    && (index == 0 || raw != out[0])
                    && let Err(error) = self.close(own("pair-cleanup", raw as u64)?)
                {
                    failure = Error {
                        operation: "pair-invalid-output-cleanup-close",
                        kind: error.kind,
                    };
                }
            }
            return Err(failure);
        }
        Ok([own("pair", out[0] as u64)?, own("pair", out[1] as u64)?])
    }
    pub(crate) fn pipe(&mut self) -> Result<[OwnedFd; 2]> {
        self.pair(false)
    }
    pub(crate) fn socketpair(&mut self) -> Result<[OwnedFd; 2]> {
        self.pair(true)
    }
    pub(crate) fn duplicate(&mut self, fd: i32, target: i32, cloexec: bool) -> Result<OwnedFd> {
        if fd == target {
            return Err(Error::invalid("dup3-identical"));
        }
        let target_arg = fd_arg(target)?;
        // Never silently replace an existing owner at a fixed role.
        match self.descriptor_flags(target) {
            Err(e) if e.errno() == Some(9) => {}
            _ => {
                return Err(Error {
                    operation: "dup3-target-occupied",
                    kind: ErrorKind::Ownership,
                });
            }
        }
        let n = self.scalar(
            "dup3",
            NR_DUP3,
            [
                fd_arg(fd)?,
                target_arg,
                if cloexec { O_CLOEXEC } else { 0 },
                0,
                0,
                0,
            ],
        )?;
        if n != target_arg {
            return Err(Error::returned("dup3"));
        }
        own("dup3", n)
    }
    pub(crate) fn scratch_duplicate(&mut self, fd: i32) -> Result<OwnedFd> {
        let n = self.scalar(
            "fcntl-dupfd-cloexec",
            NR_FCNTL,
            [fd_arg(fd)?, F_DUPFD_CLOEXEC, 6, 0, 0, 0],
        )?;
        if n < 6 {
            return Err(Error::returned("fcntl-dupfd-cloexec"));
        }
        own("fcntl", n)
    }
    pub(crate) fn close(&mut self, fd: OwnedFd) -> Result<()> {
        {
            let n = self.scalar("close", NR_CLOSE, [fd_arg(fd.into_raw())?, 0, 0, 0, 0, 0])?;
            if n == 0 {
                Ok(())
            } else {
                Err(Error::returned("close"))
            }
        }
    }
    pub(crate) fn descriptor_flags(&mut self, fd: i32) -> Result<u64> {
        self.scalar("fcntl-getfd", NR_FCNTL, [fd_arg(fd)?, F_GETFD, 0, 0, 0, 0])
    }
    pub(crate) fn flags(&mut self, fd: i32) -> Result<u64> {
        self.scalar("fcntl-getfl", NR_FCNTL, [fd_arg(fd)?, F_GETFL, 0, 0, 0, 0])
    }
    pub(crate) fn set_nonblocking(&mut self, fd: i32, enabled: bool) -> Result<()> {
        let old = self.flags(fd)?;
        let flags = if enabled {
            old | O_NONBLOCK
        } else {
            old & !O_NONBLOCK
        };
        self.scalar_zero(
            "fcntl-setfl",
            NR_FCNTL,
            [fd_arg(fd)?, F_SETFL, flags, 0, 0, 0],
        )?;
        if self.flags(fd)? != flags {
            return Err(Error::returned("fcntl-setfl-readback"));
        }
        Ok(())
    }
    pub(crate) fn take_standard(&mut self) -> Result<[OwnedFd; 3]> {
        if self.inherited_taken {
            return Err(Error {
                operation: "inherit-stdio",
                kind: ErrorKind::Ownership,
            });
        }
        // Mark before any operation so a partial failure cannot re-adopt.
        self.inherited_taken = true;
        for fd in 0..3 {
            self.fstat(fd)?;
            self.descriptor_flags(fd)?;
        }
        Ok([
            own("inherit-stdio", 0)?,
            own("inherit-stdio", 1)?,
            own("inherit-stdio", 2)?,
        ])
    }
    fn clock(&mut self, nr: i32) -> Result<u64> {
        let mut out = Timespec::default();
        // SAFETY: fixed 16-byte exclusive output, no pointer escapes this call.
        unsafe {
            self.call_zero(
                "boottime",
                Call {
                    nr,
                    args: [CLOCK_BOOTTIME, &mut out as *mut _ as u64, 0, 0, 0, 0],
                },
            )
        }?;
        out.ns().ok_or(Error::returned("boottime"))
    }
    pub(crate) fn boottime_ns(&mut self) -> Result<u64> {
        self.clock(NR_CLOCK_GETTIME)
    }
    pub(crate) fn clock_resolution_ns(&mut self) -> Result<u64> {
        self.clock(NR_CLOCK_GETRES)
    }
    pub(crate) fn getpid(&mut self) -> Result<u32> {
        u32::try_from(self.scalar("getpid", NR_GETPID, [0; 6])?)
            .map_err(|_| Error::returned("getpid"))
    }
    pub(crate) fn getppid(&mut self) -> Result<u32> {
        u32::try_from(self.scalar("getppid", NR_GETPPID, [0; 6])?)
            .map_err(|_| Error::returned("getppid"))
    }
    pub(crate) fn gettid(&mut self) -> Result<u32> {
        u32::try_from(self.scalar("gettid", NR_GETTID, [0; 6])?)
            .map_err(|_| Error::returned("gettid"))
    }
    pub(crate) fn timer(&mut self) -> Result<OwnedFd> {
        let n = self.scalar(
            "timerfd-create",
            NR_TIMERFD_CREATE,
            [CLOCK_BOOTTIME, O_CLOEXEC | O_NONBLOCK, 0, 0, 0, 0],
        )?;
        own("timerfd-create", n)
    }
    pub(crate) fn arm_timer(&mut self, fd: i32, deadline_ns: u64) -> Result<()> {
        if deadline_ns == 0 {
            return Err(Error::invalid("timerfd-settime"));
        }
        let value = Itimer {
            interval: Timespec::default(),
            value: Timespec::from_ns(deadline_ns),
        };
        // SAFETY: fixed initialized itimerspec remains live and immutable.
        unsafe {
            self.call_zero(
                "timerfd-settime",
                Call {
                    nr: NR_TIMERFD_SETTIME,
                    args: [fd_arg(fd)?, 1, &value as *const _ as u64, 0, 0, 0],
                },
            )
        }?;
        Ok(())
    }
    pub(crate) fn random(&mut self, out: &mut [u8]) -> Result<usize> {
        // SAFETY: exclusive out bounds all writes; GRND_NONBLOCK avoids waiting
        // for entropy in setup. EAGAIN is surfaced, never fabricated randomness.
        let n = unsafe {
            self.call(
                "getrandom",
                Call {
                    nr: NR_GETRANDOM,
                    args: [out.as_mut_ptr() as u64, out.len() as u64, 1, 0, 0, 0],
                },
            )
        }?;
        count("getrandom", n, out.len())
    }
    pub(crate) fn memfd(&mut self) -> Result<OwnedFd> {
        // SAFETY: static C string lives throughout operation; exact EXEC flags.
        let n = unsafe {
            self.call(
                "memfd-create",
                Call {
                    nr: NR_MEMFD_CREATE,
                    args: [c"axiom-solver".as_ptr() as u64, 0x13, 0, 0, 0, 0],
                },
            )
        }?;
        own("memfd-create", n)
    }
    pub(crate) fn truncate(&mut self, fd: i32, len: u64) -> Result<()> {
        if len > i64::MAX as u64 {
            return Err(Error::invalid("ftruncate"));
        }
        self.scalar_zero("ftruncate", NR_FTRUNCATE, [fd_arg(fd)?, len, 0, 0, 0, 0])
            .map(|_| ())
    }
    pub(crate) fn add_seals(&mut self, fd: i32) -> Result<()> {
        self.scalar_zero(
            "fcntl-add-seals",
            NR_FCNTL,
            [fd_arg(fd)?, F_ADD_SEALS, ALL_SEALS, 0, 0, 0],
        )?;
        if self.seals(fd)? != ALL_SEALS {
            return Err(Error::returned("seals-readback"));
        }
        Ok(())
    }
    pub(crate) fn seals(&mut self, fd: i32) -> Result<u64> {
        self.scalar(
            "fcntl-get-seals",
            NR_FCNTL,
            [fd_arg(fd)?, F_GET_SEALS, 0, 0, 0, 0],
        )
    }
    pub(crate) fn no_new_privs(&mut self) -> Result<()> {
        self.scalar_zero(
            "prctl-set-no-new-privs",
            NR_PRCTL,
            [PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0, 0],
        )?;
        self.check_no_new_privs()
    }
    pub(crate) fn check_no_new_privs(&mut self) -> Result<()> {
        if self.scalar(
            "prctl-get-no-new-privs",
            NR_PRCTL,
            [PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0, 0],
        )? != 1
        {
            return Err(Error::returned("no-new-privs-readback"));
        }
        Ok(())
    }
    pub(crate) fn install_filter(
        &mut self,
        policy: &OfflinePolicy,
        listener: bool,
    ) -> Result<Option<OwnedFd>> {
        let filters = policy
            .instructions()
            .iter()
            .map(|i| SockFilter {
                code: i.code,
                jt: i.jt,
                jf: i.jf,
                k: i.k,
            })
            .collect::<Vec<_>>();
        if filters.is_empty() || filters.len() > 4096 {
            return Err(Error::invalid("seccomp-filter"));
        }
        let program = SockFprog {
            len: filters.len() as u16,
            pad: [0; 6],
            filter: filters.as_ptr() as u64,
        };
        // SAFETY: program and its owned repr(C) filter array live until return;
        // conversion copies fields from the existing generator, never casts Vec.
        let n = unsafe {
            self.call(
                "seccomp-filter",
                Call {
                    nr: NR_SECCOMP,
                    args: [
                        SECCOMP_SET_MODE_FILTER,
                        if listener {
                            SECCOMP_FILTER_FLAG_NEW_LISTENER
                        } else {
                            0
                        },
                        &program as *const _ as u64,
                        0,
                        0,
                        0,
                    ],
                },
            )
        }?;
        if listener {
            Ok(Some(own("seccomp-listener", n)?))
        } else if n == 0 {
            Ok(None)
        } else {
            Err(Error::returned("seccomp-filter"))
        }
    }
    pub(crate) fn notification_sizes(&mut self) -> Result<()> {
        let mut bytes = [0u8; SECCOMP_NOTIF_SIZES_SIZE];
        // SAFETY: exact 6-byte writable UAPI buffer, no alignment requirement
        // beyond bytes because kernel copies these fields through user pointer.
        unsafe {
            self.call_zero(
                "seccomp-notif-sizes",
                Call {
                    nr: NR_SECCOMP,
                    args: [
                        SECCOMP_GET_NOTIF_SIZES,
                        0,
                        bytes.as_mut_ptr() as u64,
                        0,
                        0,
                        0,
                    ],
                },
            )
        }?;
        core_abi::validate_notification_sizes(&bytes).map_err(|_| Error {
            operation: "seccomp-notif-sizes",
            kind: ErrorKind::UnexpectedLayout,
        })
    }
    pub(crate) fn receive_notification(&mut self, fd: i32) -> Result<SeccompNotification> {
        let mut bytes = [0u8; SECCOMP_NOTIF_SIZE];
        // SAFETY: RECV has exactly an 80-byte initialized exclusive output buffer.
        unsafe {
            self.call_zero(
                "notif-recv",
                Call {
                    nr: NR_IOCTL,
                    args: [
                        fd_arg(fd)?,
                        SECCOMP_IOCTL_NOTIF_RECV,
                        bytes.as_mut_ptr() as u64,
                        0,
                        0,
                        0,
                    ],
                },
            )
        }?;
        SeccompNotification::decode(&bytes).map_err(|_| Error::returned("notif-recv"))
    }
    pub(crate) fn notification_id_valid(&mut self, fd: i32, id: u64) -> Result<()> {
        // SAFETY: ID_VALID reads one live u64; it does not retain its address.
        unsafe {
            self.call_zero(
                "notif-id-valid",
                Call {
                    nr: NR_IOCTL,
                    args: [
                        fd_arg(fd)?,
                        SECCOMP_IOCTL_NOTIF_ID_VALID,
                        &id as *const _ as u64,
                        0,
                        0,
                        0,
                    ],
                },
            )
        }?;
        Ok(())
    }
    pub(crate) fn continue_notification(&mut self, fd: i32, id: u64) -> Result<()> {
        let mut bytes = [0u8; SECCOMP_NOTIF_RESP_SIZE];
        bytes[..8].copy_from_slice(&id.to_le_bytes());
        bytes[20..24].copy_from_slice(&SECCOMP_USER_NOTIF_FLAG_CONTINUE.to_le_bytes());
        // SAFETY: SEND has a live exclusive 24-byte response buffer (the ioctl
        // direction is IOWR); no mutation could alias a shared Rust reference.
        unsafe {
            self.call_zero(
                "notif-send-continue",
                Call {
                    nr: NR_IOCTL,
                    args: [
                        fd_arg(fd)?,
                        SECCOMP_IOCTL_NOTIF_SEND,
                        bytes.as_mut_ptr() as u64,
                        0,
                        0,
                        0,
                    ],
                },
            )
        }?;
        Ok(())
    }
    pub(crate) fn poll(&mut self, fds: &mut [PollFd], timeout_ns: u64) -> Result<usize> {
        if fds.is_empty() || fds.len() > 21 || fds.iter().any(|f| f.fd < 0) {
            return Err(Error::invalid("ppoll"));
        }
        let mut timeout = Timespec::from_ns(timeout_ns);
        // SAFETY: repr(C) exclusive pollfd slice and writable remaining-timespec
        // (raw ppoll writes it unlike libc's wrapper), NULL
        // sigmask exactly matches the fixed final S policy's full-u64 arguments.
        let n = unsafe {
            self.call(
                "ppoll",
                Call {
                    nr: NR_PPOLL,
                    args: [
                        fds.as_mut_ptr() as u64,
                        fds.len() as u64,
                        &mut timeout as *mut _ as u64,
                        0,
                        KERNEL_SIGSET_SIZE,
                        0,
                    ],
                },
            )
        }?;
        count("ppoll", n, fds.len())
    }
    pub(crate) fn kill(&mut self, fd: i32) -> Result<()> {
        self.scalar_zero(
            "pidfd-sigkill",
            NR_PIDFD_SEND_SIGNAL,
            [fd_arg(fd)?, SIGKILL, 0, 0, 0, 0],
        )
    }
    pub(crate) fn wait(&mut self, fd: i32) -> Result<Option<ChildExit>> {
        let mut out = SigInfo::default();
        // SAFETY: 128-byte, 8-aligned exclusive siginfo; zeroing makes WNOHANG
        // no-state distinguishable without reading uninitialized fields.
        unsafe {
            self.call_zero(
                "waitid-pidfd",
                Call {
                    nr: NR_WAITID,
                    args: [
                        P_PIDFD,
                        fd_arg(fd)?,
                        &mut out as *mut _ as u64,
                        WEXITED | WNOHANG,
                        0,
                        0,
                    ],
                },
            )
        }?;
        let signum = i32::from_le_bytes(out.bytes[..4].try_into().expect("siginfo header"));
        let errno = i32::from_le_bytes(out.bytes[4..8].try_into().expect("siginfo header"));
        if let Some(exit) = out.child() {
            if signum != 17 || errno != 0 {
                return Err(Error::returned("waitid-siginfo"));
            }
            if exit.pid == 0
                || exit.pid > i32::MAX as u32
                || !(1..=3).contains(&exit.code)
                || (exit.code == 1 && !(0..=255).contains(&exit.status))
                || (exit.code != 1 && !(1..=64).contains(&exit.status))
            {
                return Err(Error::returned("waitid-pidfd"));
            }
            Ok(Some(exit))
        } else {
            if signum != 0 || errno != 0 || out.bytes[8..12] != [0; 4] {
                return Err(Error::returned("waitid-no-state"));
            }
            Ok(None)
        }
    }
}

#[cfg(all(
    target_os = "linux",
    target_arch = "aarch64",
    target_endian = "little",
    target_pointer_width = "64"
))]
pub(crate) struct NativeKernel;
#[cfg(all(
    target_os = "linux",
    target_arch = "aarch64",
    target_endian = "little",
    target_pointer_width = "64"
))]
// SAFETY: this is the exact Linux native ABI; all memory arguments are validated
// at typed wrappers, and asm declares effects instead of nomem/pure/readonly.
unsafe impl Kernel for NativeKernel {
    unsafe fn invoke(&mut self, call: Call) -> u64 {
        let mut x0 = call.args[0];
        // SAFETY: caller supplies live syscall buffers. Linux AArch64 svc uses
        // x8 for syscall, x0..x5 arguments and x0 result; kernel preserves other
        // user registers. No memory-eliding option permits compiler reordering.
        unsafe {
            core::arch::asm!("svc 0",in("x8") call.nr as u64,inout("x0") x0,
            in("x1") call.args[1],in("x2") call.args[2],in("x3") call.args[3],
            in("x4") call.args[4],in("x5") call.args[5],options(nostack));
        }
        x0
    }
}

impl<K: Kernel> Linux<K> {
    pub(crate) fn exit_group(&mut self, status: u8) -> ! {
        // No return to std cleanup. A kernel claiming exit_group returned cannot
        // be trusted; repeat only this terminal syscall, never resume execution.
        loop {
            // SAFETY: exit_group has no pointer arguments and terminates this
            // process. This loop contains neither allocator nor panic path.
            unsafe {
                self.kernel.invoke(Call {
                    nr: NR_EXIT_GROUP,
                    args: [status as u64, 0, 0, 0, 0, 0],
                });
            }
        }
    }
}

#[path = "syscall_listener.rs"]
mod listener;
#[path = "syscall_signals.rs"]
mod signals;
#[cfg(test)]
#[path = "syscall_tests.rs"]
mod tests;
