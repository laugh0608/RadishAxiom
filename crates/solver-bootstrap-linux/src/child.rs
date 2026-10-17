//! Single clone3 and an independent allocation/Drop/unwind-free child tail.
use crate::{
    abi::*,
    fd::OwnedFd,
    syscall::{Call, Error, Kernel, Linux, Result, decode},
};
use radishaxiom_solver_supervision_core::policy::worker_policy;
use std::ffi::CString;

pub(crate) struct FrozenChildArguments {
    strings: Box<[CString]>,
    pointers: Box<[u64; 14]>,
}
impl FrozenChildArguments {
    /// Only configuration's build-artifact-bound command input may supply these
    /// tokens. There is no entry from Start/ARM/environment/command-line values.
    pub(crate) fn from_bound_tokens(tokens: &[String]) -> Result<Self> {
        if tokens.len() != 12
            || tokens.iter().any(|s| {
                s.is_empty()
                    || s.len() > 128
                    || !s.starts_with("--")
                    || !s.bytes().all(|b| (0x21..=0x7e).contains(&b))
            })
        {
            return Err(Error::invalid("bound-child-arguments"));
        }
        let strings = core::iter::once("cvc5")
            .chain(tokens.iter().map(String::as_str))
            .map(|s| CString::new(s).map_err(|_| Error::invalid("bound-child-arguments")))
            .collect::<Result<Vec<_>>>()?
            .into_boxed_slice();
        let mut pointers = Box::new([0; 14]);
        for (out, arg) in pointers.iter_mut().zip(strings.iter()) {
            *out = arg.as_ptr() as u64;
        }
        Ok(Self { strings, pointers })
    }
}
#[derive(Clone, Copy, Debug)]
pub(crate) struct FrozenPointers {
    pub empty_path: u64,
    pub argv: u64,
    pub envp: u64,
}
pub(crate) struct ParentChild {
    pub pid: u32,
    pub pidfd: OwnedFd,
    pub pointers: FrozenPointers,
}
pub(crate) struct FrozenChild {
    scratch: Option<[OwnedFd; 5]>,
    arguments: FrozenChildArguments,
    filters: Box<[SockFilter]>,
    empty_environment: Box<[u64; 1]>,
    listener: Box<Ancillary>,
    listener_iov: Box<Iovec>,
    listener_msg: Box<MsgHdr>,
    attempted: bool,
}
impl FrozenChild {
    pub(crate) fn new<K: Kernel>(
        scratch: [OwnedFd; 5],
        arguments: FrozenChildArguments,
        linux: &mut Linux<K>,
    ) -> Result<Self> {
        for (i, fd) in scratch.iter().enumerate() {
            if fd.raw() < 6 || scratch[..i].iter().any(|v| v.raw() == fd.raw()) {
                let mut error = Error::invalid("child-scratch-fds");
                let raw = scratch.each_ref().map(OwnedFd::raw);
                for (index, fd) in scratch.into_iter().enumerate() {
                    if fd.raw() >= 0
                        && !raw[..index].contains(&fd.raw())
                        && let Err(close) = linux.close(fd)
                    {
                        error = close;
                    }
                }
                return Err(error);
            }
        }
        // Existing generator is the sole source for final W/B bytes.
        let filters = worker_policy()
            .instructions()
            .iter()
            .map(|i| SockFilter {
                code: i.code,
                jt: i.jt,
                jf: i.jf,
                k: i.k,
            })
            .collect::<Vec<_>>()
            .into_boxed_slice();
        let listener = Box::new(Ancillary::rights(5));
        let listener_iov = Box::new(Iovec {
            base: LISTENER_RECORD.as_ptr() as u64,
            len: 8,
        });
        let listener_msg = Box::new(MsgHdr {
            iov: &*listener_iov as *const _ as u64,
            iovlen: 1,
            control: &*listener as *const _ as u64,
            controllen: 24,
            ..MsgHdr::default()
        });
        Ok(Self {
            scratch: Some(scratch),
            arguments,
            filters,
            empty_environment: Box::new([0]),
            listener,
            listener_iov,
            listener_msg,
            attempted: false,
        })
    }
    pub(crate) fn pointers(&self) -> FrozenPointers {
        FrozenPointers {
            empty_path: c"".as_ptr() as u64,
            argv: self.arguments.pointers.as_ptr() as u64,
            envp: self.empty_environment.as_ptr() as u64,
        }
    }
    pub(crate) fn clone_once<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
        deadline_ns: u64,
    ) -> Result<ParentChild> {
        if self.attempted {
            return Err(Error::invalid("clone3-already-attempted"));
        }
        self.attempted = true;
        let fds = self
            .scratch
            .as_ref()
            .ok_or(Error::invalid("child-scratch-closed"))?;
        for fd in fds {
            if linux.descriptor_flags(fd.raw())? != FD_CLOEXEC {
                return Err(Error::invalid("child-scratch-cloexec"));
            }
        }
        linux.check_no_new_privs()?;
        let frozen_at = linux.freeze_signals(deadline_ns)?;
        let mut identities = [(0u64, 0u64); 3];
        for (identity, fd) in identities.iter_mut().zip(&fds[..3]) {
            let stat = linux.fstat(fd.raw())?;
            if stat.mode & 0xf000 != 0x1000 {
                return Err(Error::invalid("child-source-pipe"));
            }
            *identity = (stat.dev, stat.ino);
        }
        if linux.fstat(fds[4].raw())?.mode & 0xf000 != 0xc000 {
            return Err(Error::invalid("child-source-socket"));
        }
        let pointers = self.pointers();
        let mut pidfd = -1i32;
        let args = CloneArgs {
            flags: CLONE_PIDFD,
            pidfd: &mut pidfd as *mut _ as u64,
            exit_signal: SIGCHLD,
            ..CloneArgs::default()
        };
        let program = SockFprog {
            len: self.filters.len() as u16,
            pad: [0; 6],
            filter: self.filters.as_ptr() as u64,
        };
        let frozen = TailInputs {
            identities,
            sources: [
                fds[0].raw(),
                fds[1].raw(),
                fds[2].raw(),
                fds[3].raw(),
                fds[4].raw(),
            ],
            program,
            pointers,
            message: &*self.listener_msg as *const _ as u64,
        };
        let now = linux.boottime_ns()?;
        if now < frozen_at {
            return Err(Error::invalid("clone3-clock-rollback"));
        }
        if now >= deadline_ns {
            return Err(Error::invalid("clone3-deadline"));
        }
        // SAFETY: args and pidfd live on parent stack; CLONE_VM/FILES/THREAD are
        // absent and stack=0 preserves a COW copy of this exact frame. Child
        // never returns through Rust destructors and only reads frozen buffers.
        let raw = unsafe {
            linux.kernel.invoke(Call {
                nr: NR_CLONE3,
                args: [&args as *const _ as u64, 88, 0, 0, 0, 0],
            })
        };
        if raw == 0 {
            // SAFETY: clone child has private VM/files and blocked signals; all
            // pointed data was allocated and frozen before the single clone.
            unsafe { child_tail(&mut linux.kernel, &frozen) }
        }
        let pid = decode("clone3", raw)?;
        let pid = u32::try_from(pid).map_err(|_| Error::returned("clone3-pid"))?;
        if pid == 0 || pidfd < 0 {
            return Err(Error::returned("clone3-pidfd"));
        }
        // SAFETY: successful CLONE_PIDFD writes a newly allocated parent fd.
        Ok(ParentChild {
            pid,
            pidfd: unsafe { OwnedFd::from_raw(pidfd) },
            pointers,
        })
    }
    pub(crate) fn close_parent_fds<K: Kernel>(&mut self, linux: &mut Linux<K>) -> Result<()> {
        let mut failed = None;
        if let Some(fds) = self.scratch.take() {
            for fd in fds {
                if let Err(e) = linux.close(fd) {
                    failed = Some(e);
                }
            }
        }
        if let Some(error) = failed {
            Err(error)
        } else {
            Ok(())
        }
    }
}

#[derive(Clone, Copy)]
struct TailInputs {
    identities: [(u64, u64); 3],
    sources: [i32; 5],
    program: SockFprog,
    pointers: FrozenPointers,
    message: u64,
}
/// # Safety
/// Called only in the sole clone3 child, with COW stack, blocked signals, no
/// inherited handlers/altstack and private file table. Every pointer in input
/// names pre-clone initialized heap/static memory, alive until raw process exit.
unsafe fn child_tail<K: Kernel>(kernel: &mut K, input: &TailInputs) -> ! {
    // All calls in this function are scalar or point into frozen parent-owned
    // buffers / fixed local structs. No Result formatting, std, allocation, lock,
    // panic, unwinding, destructor or callback is reachable from the child.
    macro_rules! raw {
        ($nr:expr,$args:expr) => {{
            // SAFETY: each invocation below has fixed scalar args or exact local
            // UAPI buffers; Kernel preserves the same synchronous memory contract.
            unsafe {
                kernel.invoke(Call {
                    nr: $nr,
                    args: $args,
                })
            }
        }};
    }
    macro_rules! require {
        ($condition:expr) => {
            if !$condition {
                die(kernel, 125)
            }
        };
    }
    // Sources are >=6 and unique, so writing each 0..4 cannot destroy a later
    // source even for arbitrary permutations / inherited low descriptor values.
    let [a, b, c, d, e] = input.sources;
    require!(raw!(NR_DUP3, [a as u64, 0, 0, 0, 0, 0]) == 0);
    require!(raw!(NR_DUP3, [b as u64, 1, 0, 0, 0, 0]) == 1);
    require!(raw!(NR_DUP3, [c as u64, 2, 0, 0, 0, 0]) == 2);
    require!(raw!(NR_DUP3, [d as u64, 3, O_CLOEXEC, 0, 0, 0]) == 3);
    require!(raw!(NR_DUP3, [e as u64, 4, O_CLOEXEC, 0, 0, 0]) == 4);
    require!(raw!(NR_CLOSE_RANGE, [5, u32::MAX as u64, 0, 0, 0, 0]) == 0);
    for fd in 0..3u64 {
        let mut stat = Stat {
            dev: 0,
            ino: 0,
            mode: 0,
            nlink: 0,
            uid: 0,
            gid: 0,
            rdev: 0,
            pad1: 0,
            size: 0,
            blksize: 0,
            pad2: 0,
            blocks: 0,
            atime: 0,
            atime_nsec: 0,
            mtime: 0,
            mtime_nsec: 0,
            ctime: 0,
            ctime_nsec: 0,
            unused: [0; 2],
        };
        require!(raw!(NR_FSTAT, [fd, &mut stat as *mut _ as u64, 0, 0, 0, 0]) == 0);
        require!(stat.mode & 0xf000 == 0x1000);
        // Parent freezes dev/ino from the owned child pipe ends before clone;
        // target identity must survive remapping, not merely retain FIFO type.
        let (dev, ino) = match fd {
            0 => input.identities[0],
            1 => input.identities[1],
            _ => input.identities[2],
        };
        require!(stat.dev == dev && stat.ino == ino);
        let flags = raw!(NR_FCNTL, [fd, F_GETFL, 0, 0, 0, 0]);
        require!(flags <= i32::MAX as u64 && flags & O_NONBLOCK == 0);
        require!(flags & 3 == if fd == 0 { 0 } else { 1 });
        require!(raw!(NR_FCNTL, [fd, F_GETFD, 0, 0, 0, 0]) == 0);
    }
    require!(raw!(NR_FCNTL, [3, F_GET_SEALS, 0, 0, 0, 0]) == ALL_SEALS);
    require!(raw!(NR_FCNTL, [3, F_GETFD, 0, 0, 0, 0]) == FD_CLOEXEC);
    require!(raw!(NR_FCNTL, [4, F_GETFD, 0, 0, 0, 0]) == FD_CLOEXEC);
    require!(raw!(NR_PRCTL, [PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0, 0]) == 1);
    require!(
        raw!(
            NR_SECCOMP,
            [
                SECCOMP_SET_MODE_FILTER,
                SECCOMP_FILTER_FLAG_NEW_LISTENER,
                &input.program as *const _ as u64,
                0,
                0,
                0
            ]
        ) == 5
    );
    require!(raw!(NR_SENDMSG, [4, input.message, MSG_NOSIGNAL, 0, 0, 0]) == 8);
    require!(raw!(NR_CLOSE, [5, 0, 0, 0, 0, 0]) == 0);
    require!(raw!(NR_CLOSE, [4, 0, 0, 0, 0, 0]) == 0);
    // This is USER_NOTIF under the unchanged golden filter, never direct ALLOW.
    raw!(
        NR_EXECVEAT,
        [
            3,
            input.pointers.empty_path,
            input.pointers.argv,
            input.pointers.envp,
            AT_EMPTY_PATH,
            0
        ]
    );
    die(kernel, 126)
}
fn die<K: Kernel>(kernel: &mut K, status: u64) -> ! {
    loop {
        // SAFETY: terminal pointer-free exit; returning cannot resume Rust.
        unsafe {
            kernel.invoke(Call {
                nr: NR_EXIT_GROUP,
                args: [status, 0, 0, 0, 0, 0],
            });
        }
    }
}

#[cfg(test)]
#[path = "child_tests.rs"]
mod tests;
