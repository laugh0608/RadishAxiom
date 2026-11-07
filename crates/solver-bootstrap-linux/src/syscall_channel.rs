//! Diagnostic PID 1 operations; never added to the solver W/S final policies.
use super::*;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum WaitAny {
    Exited(ChildExit),
    Running,
    NoChildren,
}

impl<K: Kernel> Linux<K> {
    pub(crate) fn check_channel_identity(&mut self) -> Result<()> {
        if self.getpid()? != 1 || self.gettid()? != 1 || self.getppid()? != 0 {
            return Err(Error::invalid("channel-init-pid"));
        }
        for nr in [NR_GETUID, NR_GETEUID, NR_GETGID, NR_GETEGID] {
            if self.scalar("channel-init-identity", nr, [0; 6])? != 65532 {
                return Err(Error::invalid("channel-init-identity"));
            }
        }
        if self.scalar("channel-init-groups", NR_GETGROUPS, [0; 6])? != 0 {
            return Err(Error::invalid("channel-init-groups"));
        }
        self.check_no_new_privs()
    }
    pub(crate) fn channel_close_inherited(&mut self) -> Result<()> {
        self.scalar_zero(
            "channel-init-close-inherited",
            NR_CLOSE_RANGE,
            [3, u32::MAX as u64, 0, 0, 0, 0],
        )
    }
    pub(crate) fn channel_pidfd(&mut self, pid: u32) -> Result<OwnedFd> {
        if pid <= 1 || pid > i32::MAX as u32 {
            return Err(Error::invalid("channel-init-child-pid"));
        }
        let fd = self.scalar(
            "channel-init-pidfd",
            NR_PIDFD_OPEN,
            [pid as u64, 0, 0, 0, 0, 0],
        )?;
        own("channel-init-pidfd", fd)
    }
    pub(crate) fn channel_wait_any(&mut self) -> Result<WaitAny> {
        // P_ALL=0, id=0; only exit events are consumed. Do not treat ECHILD as
        // equivalent to a successful WNOHANG result with a live child.
        match self.wait_info(0, 0) {
            Ok(Some(exit)) => Ok(WaitAny::Exited(exit)),
            Ok(None) => Ok(WaitAny::Running),
            Err(e) if e.errno() == Some(10) => Ok(WaitAny::NoChildren),
            Err(e) => Err(e),
        }
    }
    pub(crate) fn channel_signal(&mut self, timeout_ns: u64) -> Result<Option<u32>> {
        let set = BLOCKED_SIGNALS;
        let timeout = Timespec::from_ns(timeout_ns);
        let mut info = SigInfo::default();
        // SAFETY: exact 8-byte immutable kernel mask, 128-byte exclusive output
        // and 16-byte immutable timeout live for this synchronous call.
        let result = unsafe {
            self.call(
                "channel-init-signal",
                Call {
                    nr: NR_RT_SIGTIMEDWAIT,
                    args: [
                        &set as *const _ as u64,
                        &mut info as *mut _ as u64,
                        &timeout as *const _ as u64,
                        KERNEL_SIGSET_SIZE,
                        0,
                        0,
                    ],
                },
            )
        };
        match result {
            Err(e) if e.errno() == Some(11) => Ok(None),
            Err(e) => Err(e),
            Ok(signal) => {
                let actual = i32::from_le_bytes(info.bytes[..4].try_into().expect("fixed header"));
                if !(1..=64).contains(&signal)
                    || signal == 9
                    || signal == 19
                    || actual as u64 != signal
                {
                    return Err(Error::returned("channel-init-signal"));
                }
                Ok(Some(signal as u32))
            }
        }
    }
}
