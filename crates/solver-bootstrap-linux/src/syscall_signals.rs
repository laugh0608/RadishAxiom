//! Parent-only signal reset and exact inherited mask freeze.
use super::*;
impl<K: Kernel> Linux<K> {
    pub(crate) fn freeze_signals(&mut self, deadline_ns: u64) -> Result<u64> {
        // Block before removing handlers; inherited signal handlers cannot race
        // mutations of the fixed child argv/filter/FD buffers thereafter.
        let mut last = self.boottime_ns()?;
        if last >= deadline_ns {
            return Err(Error::invalid("signal-freeze-deadline"));
        }
        let mask = BLOCKED_SIGNALS;
        // SAFETY: live initialized 8-byte set; no oldset requested.
        unsafe {
            self.call_zero(
                "signal-block",
                Call {
                    nr: NR_RT_SIGPROCMASK,
                    args: [
                        SIG_SETMASK,
                        &mask as *const _ as u64,
                        0,
                        KERNEL_SIGSET_SIZE,
                        0,
                        0,
                    ],
                },
            )
        }?;
        let default = SigAction::default();
        for signal in 1..=64u64 {
            if signal == 9 || signal == 19 {
                continue;
            }
            let now = self.boottime_ns()?;
            if now < last {
                return Err(Error::invalid("signal-freeze-clock-rollback"));
            }
            last = now;
            if now >= deadline_ns {
                return Err(Error::invalid("signal-freeze-deadline"));
            }
            // SAFETY: fixed 32-byte kernel sigaction with SIG_DFL, no restorer;
            // all catchable signals reset, including PIPE, CHLD, SEGV and BUS.
            unsafe {
                self.call_zero(
                    "signal-default",
                    Call {
                        nr: NR_RT_SIGACTION,
                        args: [
                            signal,
                            &default as *const _ as u64,
                            0,
                            KERNEL_SIGSET_SIZE,
                            0,
                            0,
                        ],
                    },
                )
            }?;
            let mut actual = SigAction::default();
            // SAFETY: exclusive fixed-layout action output, no new action.
            unsafe {
                self.call_zero(
                    "signal-readback",
                    Call {
                        nr: NR_RT_SIGACTION,
                        args: [
                            signal,
                            0,
                            &mut actual as *mut _ as u64,
                            KERNEL_SIGSET_SIZE,
                            0,
                            0,
                        ],
                    },
                )
            }?;
            if actual.handler != 0 || actual.flags != 0 || actual.mask != 0 || actual.restorer != 0
            {
                return Err(Error::returned("signal-default-readback"));
            }
        }
        let disabled = AltStack {
            flags: 2,
            ..AltStack::default()
        };
        // SAFETY: fixed stack_t input disables altstack, without freeing its
        // mapping or invoking Rust startup handlers/allocator after clone.
        unsafe {
            self.call_zero(
                "sigaltstack-disable",
                Call {
                    nr: NR_SIGALTSTACK,
                    args: [&disabled as *const _ as u64, 0, 0, 0, 0, 0],
                },
            )
        }?;
        let mut actual = AltStack::default();
        // SAFETY: exclusive stack_t output and NULL new stack.
        unsafe {
            self.call_zero(
                "sigaltstack-readback",
                Call {
                    nr: NR_SIGALTSTACK,
                    args: [0, &mut actual as *mut _ as u64, 0, 0, 0, 0],
                },
            )
        }?;
        if actual.flags != 2 {
            return Err(Error::returned("sigaltstack-readback"));
        }
        let mut actual_mask = 0u64;
        // SAFETY: exclusive 8-byte output, NULL set leaves current mask intact.
        unsafe {
            self.call_zero(
                "signal-mask-readback",
                Call {
                    nr: NR_RT_SIGPROCMASK,
                    args: [
                        SIG_SETMASK,
                        0,
                        &mut actual_mask as *mut _ as u64,
                        KERNEL_SIGSET_SIZE,
                        0,
                        0,
                    ],
                },
            )
        }?;
        if actual_mask != mask {
            return Err(Error::returned("signal-mask-readback"));
        }
        let now = self.boottime_ns()?;
        if now < last {
            return Err(Error::invalid("signal-freeze-clock-rollback"));
        }
        if now >= deadline_ns {
            return Err(Error::invalid("signal-freeze-deadline"));
        }
        Ok(now)
    }
}
