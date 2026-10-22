//! Pure S-runtime cBPF candidate. Fixed FD numbers name pre-existing owned
//! capabilities; bytes neither open them nor certify their underlying objects.
#![forbid(unsafe_code)]

use super::{ArgCheck, OfflinePolicy, Rule, compile_rules};
use crate::abi::*;

pub const SUPERVISOR_CGROUP_FDS: usize = 12;
pub const SUPERVISOR_OWNED_FDS: usize = 21;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SupervisorFdRoles {
    pub control_input: u64,
    pub envelope_output: u64,
    pub diagnostic_output: u64,
    pub child_stdin: u64,
    pub child_stdout: u64,
    pub child_stderr: u64,
    pub timer: u64,
    pub pidfd: u64,
    pub listener: u64,
    pub cgroup: [u64; SUPERVISOR_CGROUP_FDS],
}
/// Fixed ADR 0030 S roles. pidfd/listener are reserved setup targets until
/// acquired and checked; this value does not assert that any FD is open.
pub const BOOTSTRAP_SUPERVISOR_ROLES: SupervisorFdRoles = SupervisorFdRoles {
    control_input: 0,
    envelope_output: 1,
    diagnostic_output: 2,
    child_stdin: 10,
    child_stdout: 11,
    child_stderr: 12,
    timer: 13,
    pidfd: 14,
    listener: 15,
    cgroup: [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
};

impl SupervisorFdRoles {
    fn owned(&self) -> [u64; SUPERVISOR_OWNED_FDS] {
        let mut fds = [0; SUPERVISOR_OWNED_FDS];
        fds[..9].copy_from_slice(&[
            self.control_input,
            self.envelope_output,
            self.diagnostic_output,
            self.child_stdin,
            self.child_stdout,
            self.child_stderr,
            self.timer,
            self.pidfd,
            self.listener,
        ]);
        fds[9..].copy_from_slice(&self.cgroup);
        fds
    }
    fn validate(&self) -> Result<(), SupervisorPolicyError> {
        if [
            self.control_input,
            self.envelope_output,
            self.diagnostic_output,
        ] != [0, 1, 2]
        {
            return Err(SupervisorPolicyError::StandardRoles);
        }
        let owned = self.owned();
        for (index, fd) in owned.iter().enumerate() {
            if *fd > i32::MAX as u64 {
                return Err(SupervisorPolicyError::FdRange);
            }
            if owned[..index].contains(fd) {
                return Err(SupervisorPolicyError::AliasedRoles);
            }
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SupervisorPolicyError {
    StandardRoles,
    FdRange,
    AliasedRoles,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SupervisorRuntimePolicy {
    roles: SupervisorFdRoles,
}
impl SupervisorRuntimePolicy {
    pub fn new(roles: SupervisorFdRoles) -> Result<Self, SupervisorPolicyError> {
        roles.validate()?;
        Ok(Self { roles })
    }
    pub fn roles(&self) -> &SupervisorFdRoles {
        &self.roles
    }
    pub fn compile(&self) -> OfflinePolicy {
        let f = &self.roles;
        let mut reads = vec![f.control_input, f.child_stdout, f.child_stderr, f.timer];
        reads.extend_from_slice(&f.cgroup);
        let writes = [f.envelope_output, f.diagnostic_output, f.child_stdin];
        let owned = f.owned();
        let counts = (1..=SUPERVISOR_OWNED_FDS as u64).collect::<Vec<_>>();
        let mut rules = vec![
            allow(NR_READ, &[(0, &reads)]),
            allow(NR_WRITE, &[(0, &writes)]),
            allow(NR_LSEEK, &[(0, &f.cgroup), (1, &[0]), (2, &[SEEK_SET])]),
            allow(NR_CLOSE, &[(0, &owned)]),
            // The array, pointers and timeout are trusted S-owned structures.
            allow(
                NR_PPOLL,
                &[(1, &counts), (3, &[0]), (4, &[KERNEL_SIGSET_SIZE])],
            ),
            allow(NR_CLOCK_GETTIME, &[(0, &[CLOCK_BOOTTIME])]),
            allow(NR_CLOCK_GETRES, &[(0, &[CLOCK_BOOTTIME])]),
            allow(
                NR_PIDFD_SEND_SIGNAL,
                &[(0, &[f.pidfd]), (1, &[SIGKILL]), (2, &[0]), (3, &[0])],
            ),
            allow(
                NR_WAITID,
                &[
                    (0, &[P_PIDFD]),
                    (1, &[f.pidfd]),
                    (3, &[WEXITED | WNOHANG]),
                    (4, &[0]),
                ],
            ),
            allow(
                NR_IOCTL,
                &[
                    (0, &[f.listener]),
                    (
                        1,
                        &[
                            SECCOMP_IOCTL_NOTIF_RECV,
                            SECCOMP_IOCTL_NOTIF_SEND,
                            SECCOMP_IOCTL_NOTIF_ID_VALID,
                        ],
                    ),
                ],
            ),
        ];
        // Explicit S subset; no worker rule list is inherited.
        for nr in [NR_BRK, NR_MUNMAP, NR_EXIT, NR_EXIT_GROUP] {
            rules.push(allow(nr, &[]));
        }
        rules.push(allow(
            NR_MMAP,
            &[
                (2, &[0, 1, 2, 3]),
                (
                    3,
                    &[
                        MAP_PRIVATE | MAP_ANONYMOUS,
                        MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE,
                    ],
                ),
                (4, &[u64::MAX]),
                (5, &[0]),
            ],
        ));
        rules.push(allow(NR_MPROTECT, &[(2, &[0, 1, 2, 3])]));
        rules.push(allow(NR_MREMAP, &[(3, &[0, MREMAP_MAYMOVE])]));
        rules.push(allow(NR_MADVISE, &[(2, &[MADV_DONTNEED, MADV_FREE])]));
        compile_rules(rules)
    }

    /// Independently written predicate: does not read rules, emitted bytes or
    /// interpreter results. Full u64 register comparisons retain high bits.
    pub fn semantic_action(&self, data: &SeccompData) -> u32 {
        if data.arch != AUDIT_ARCH_AARCH64 {
            return SECCOMP_RET_KILL_PROCESS;
        }
        let f = &self.roles;
        let a = data.args;
        let permitted = match data.nr {
            NR_READ => {
                a[0] == f.control_input
                    || a[0] == f.child_stdout
                    || a[0] == f.child_stderr
                    || a[0] == f.timer
                    || f.cgroup.contains(&a[0])
            }
            NR_WRITE => {
                a[0] == f.envelope_output || a[0] == f.diagnostic_output || a[0] == f.child_stdin
            }
            NR_LSEEK => f.cgroup.contains(&a[0]) && a[1] == 0 && a[2] == SEEK_SET,
            NR_CLOSE => f.owned().contains(&a[0]),
            NR_PPOLL => {
                (1..=SUPERVISOR_OWNED_FDS as u64).contains(&a[1])
                    && a[3] == 0
                    && a[4] == KERNEL_SIGSET_SIZE
            }
            NR_CLOCK_GETTIME | NR_CLOCK_GETRES => a[0] == CLOCK_BOOTTIME,
            NR_PIDFD_SEND_SIGNAL => a[0] == f.pidfd && a[1] == SIGKILL && a[2] == 0 && a[3] == 0,
            NR_WAITID => {
                a[0] == P_PIDFD && a[1] == f.pidfd && a[3] == WEXITED | WNOHANG && a[4] == 0
            }
            NR_IOCTL => {
                a[0] == f.listener
                    && matches!(
                        a[1],
                        SECCOMP_IOCTL_NOTIF_RECV
                            | SECCOMP_IOCTL_NOTIF_SEND
                            | SECCOMP_IOCTL_NOTIF_ID_VALID
                    )
            }
            NR_BRK | NR_MUNMAP | NR_EXIT | NR_EXIT_GROUP => true,
            NR_MMAP => {
                a[2] <= 3
                    && (a[3] == MAP_PRIVATE | MAP_ANONYMOUS
                        || a[3] == MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE)
                    && a[4] == u64::MAX
                    && a[5] == 0
            }
            NR_MPROTECT => a[2] <= 3,
            NR_MREMAP => a[3] == 0 || a[3] == MREMAP_MAYMOVE,
            NR_MADVISE => a[2] == MADV_DONTNEED || a[2] == MADV_FREE,
            _ => false,
        };
        if permitted {
            SECCOMP_RET_ALLOW
        } else {
            SECCOMP_RET_KILL_PROCESS
        }
    }
}

fn allow(nr: i32, checks: &[(usize, &[u64])]) -> Rule {
    Rule {
        nr,
        checks: checks
            .iter()
            .map(|(index, values)| ArgCheck {
                index: *index,
                values: values.to_vec(),
            })
            .collect(),
        action: SECCOMP_RET_ALLOW,
    }
}
