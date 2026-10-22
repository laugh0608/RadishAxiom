use radishaxiom_solver_diagnostic_host::{
    e3_abi::*,
    e3_policy::{OfflinePolicy, supervisor::*},
};

fn roles() -> SupervisorFdRoles {
    SupervisorFdRoles {
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
    }
}
fn candidate() -> (SupervisorRuntimePolicy, OfflinePolicy) {
    let model = SupervisorRuntimePolicy::new(roles()).unwrap();
    let bytes = model.compile();
    (model, bytes)
}
fn check(
    model: &SupervisorRuntimePolicy,
    bytes: &OfflinePolicy,
    nr: i32,
    args: [u64; 6],
    expected: u32,
) {
    let data = SeccompData::aarch64(nr, args);
    assert_eq!(
        model.semantic_action(&data),
        expected,
        "semantic nr={nr} args={args:?}"
    );
    assert_eq!(
        bytes.evaluate(&data),
        Ok(expected),
        "cBPF nr={nr} args={args:?}"
    );
}
fn allowed_calls() -> Vec<(i32, [u64; 6], Vec<usize>)> {
    let mut calls = vec![
        (NR_READ, [0, 0x1000, 1024, 0, 0, 0], vec![0]),
        (NR_WRITE, [1, 0x1000, 1024, 0, 0, 0], vec![0]),
        (NR_LSEEK, [20, 0, SEEK_SET, 0, 0, 0], vec![0, 1, 2]),
        (NR_CLOSE, [14, 0, 0, 0, 0, 0], vec![0]),
        (
            NR_PPOLL,
            [0x1000, 21, 0x2000, 0, KERNEL_SIGSET_SIZE, 0],
            vec![1, 3, 4],
        ),
        (
            NR_CLOCK_GETTIME,
            [CLOCK_BOOTTIME, 0x1000, 0, 0, 0, 0],
            vec![0],
        ),
        (
            NR_CLOCK_GETRES,
            [CLOCK_BOOTTIME, 0x1000, 0, 0, 0, 0],
            vec![0],
        ),
        (
            NR_PIDFD_SEND_SIGNAL,
            [14, SIGKILL, 0, 0, 0, 0],
            vec![0, 1, 2, 3],
        ),
        (
            NR_WAITID,
            [P_PIDFD, 14, 0x1000, WEXITED | WNOHANG, 0, 0],
            vec![0, 1, 3, 4],
        ),
        (
            NR_IOCTL,
            [15, SECCOMP_IOCTL_NOTIF_RECV, 0x1000, 0, 0, 0],
            vec![0, 1],
        ),
        (
            NR_MMAP,
            [0, 4096, 3, MAP_PRIVATE | MAP_ANONYMOUS, u64::MAX, 0],
            vec![2, 3, 4, 5],
        ),
        (NR_MPROTECT, [0x1000, 4096, 3, 0, 0, 0], vec![2]),
        (
            NR_MREMAP,
            [0x1000, 4096, 8192, MREMAP_MAYMOVE, 0, 0],
            vec![3],
        ),
        (NR_MADVISE, [0x1000, 4096, MADV_DONTNEED, 0, 0, 0], vec![2]),
    ];
    for nr in [NR_BRK, NR_MUNMAP, NR_EXIT, NR_EXIT_GROUP] {
        calls.push((nr, [0; 6], vec![]));
    }
    calls
}

#[test]
fn fd_roles_reject_standard_changes_negative_width_and_all_aliases() {
    let normal = roles();
    assert_eq!(
        SupervisorRuntimePolicy::new(normal.clone())
            .unwrap()
            .roles(),
        &normal
    );
    for index in 0..3 {
        let mut changed = normal.clone();
        match index {
            0 => changed.control_input = 9,
            1 => changed.envelope_output = 9,
            _ => changed.diagnostic_output = 9,
        }
        assert_eq!(
            SupervisorRuntimePolicy::new(changed),
            Err(SupervisorPolicyError::StandardRoles)
        );
    }
    for bad in [i32::MAX as u64 + 1, 1 << 32, u64::MAX] {
        let mut changed = normal.clone();
        changed.child_stdin = bad;
        assert_eq!(
            SupervisorRuntimePolicy::new(changed),
            Err(SupervisorPolicyError::FdRange)
        );
        let mut changed = normal.clone();
        changed.cgroup[11] = bad;
        assert_eq!(
            SupervisorRuntimePolicy::new(changed),
            Err(SupervisorPolicyError::FdRange)
        );
    }
    let all = [
        0, 1, 2, 10, 11, 12, 13, 14, 15, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
    ];
    for fd in all {
        let mut changed = normal.clone();
        changed.cgroup[11] = fd;
        assert_eq!(
            SupervisorRuntimePolicy::new(changed),
            Err(SupervisorPolicyError::AliasedRoles)
        );
    }
    let mut changed = normal;
    changed.child_stdin = changed.child_stdout;
    assert_eq!(
        SupervisorRuntimePolicy::new(changed),
        Err(SupervisorPolicyError::AliasedRoles)
    );
}

#[test]
fn exact_role_capabilities_are_distinct_and_do_not_follow_fd_number_patterns() {
    let (model, bytes) = candidate();
    for fd in 0..=40 {
        let read = [
            0, 11, 12, 13, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
        ]
        .contains(&fd);
        let write = [1, 2, 10].contains(&fd);
        let owned = [
            0, 1, 2, 10, 11, 12, 13, 14, 15, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
        ]
        .contains(&fd);
        for (nr, permitted) in [
            (NR_READ, read),
            (NR_WRITE, write),
            (NR_CLOSE, owned),
            (NR_LSEEK, (20..=31).contains(&fd)),
        ] {
            check(
                &model,
                &bytes,
                nr,
                [fd, 0, 0, 0, 0, 0],
                if permitted {
                    SECCOMP_RET_ALLOW
                } else {
                    SECCOMP_RET_KILL_PROCESS
                },
            );
        }
    }
    for (nr, args, _) in allowed_calls() {
        check(&model, &bytes, nr, args, SECCOMP_RET_ALLOW);
    }
    // A separately selected fixed map is encoded, never a contiguous FD range.
    let mut other = roles();
    other.child_stdout = 100;
    other.cgroup[0] = 200;
    let model = SupervisorRuntimePolicy::new(other).unwrap();
    let bytes = model.compile();
    for fd in [11, 20, 99, 101, 199, 201] {
        check(
            &model,
            &bytes,
            NR_READ,
            [fd, 0, 0, 0, 0, 0],
            SECCOMP_RET_KILL_PROCESS,
        );
    }
    for fd in [100, 200] {
        check(
            &model,
            &bytes,
            NR_READ,
            [fd, 0, 0, 0, 0, 0],
            SECCOMP_RET_ALLOW,
        );
    }
}

#[test]
fn all_constrained_argument_high_halves_and_wrong_arch_are_rejected() {
    let (model, bytes) = candidate();
    for (nr, args, constrained) in allowed_calls() {
        for index in constrained {
            let mut changed = args;
            // Toggle a high bit also catches -1 FD mmap sign-extension mistakes.
            changed[index] ^= 1u64 << 32;
            check(&model, &bytes, nr, changed, SECCOMP_RET_KILL_PROCESS);
        }
        for arch in [
            0,
            0x4000_0028,
            0xc000_003e,
            AUDIT_ARCH_AARCH64 ^ 0x8000_0000,
        ] {
            let mut data = SeccompData::aarch64(nr, args);
            data.arch = arch;
            assert_eq!(model.semantic_action(&data), SECCOMP_RET_KILL_PROCESS);
            assert_eq!(bytes.evaluate(&data), Ok(SECCOMP_RET_KILL_PROCESS));
        }
    }
}

#[test]
fn ppoll_count_sigmask_and_fixed_clock_are_closed() {
    let (model, bytes) = candidate();
    for count in 0..=22 {
        check(
            &model,
            &bytes,
            NR_PPOLL,
            [0x1000, count, 0x2000, 0, 8, 0],
            if (1..=21).contains(&count) {
                SECCOMP_RET_ALLOW
            } else {
                SECCOMP_RET_KILL_PROCESS
            },
        );
    }
    for (index, value) in [(3, 1), (4, 0), (4, 4), (4, 16)] {
        let mut args = [0x1000, 21, 0x2000, 0, 8, 0];
        args[index] = value;
        check(&model, &bytes, NR_PPOLL, args, SECCOMP_RET_KILL_PROCESS);
    }
    for nr in [NR_CLOCK_GETTIME, NR_CLOCK_GETRES] {
        for clock in [0, 1, 2, 3, 6, 7, 8, u64::MAX] {
            check(
                &model,
                &bytes,
                nr,
                [clock, 0x1000, 0, 0, 0, 0],
                if clock == 7 {
                    SECCOMP_RET_ALLOW
                } else {
                    SECCOMP_RET_KILL_PROCESS
                },
            );
        }
    }
}

#[test]
fn only_unique_pidfd_kill_and_nonblocking_reap_are_permitted() {
    let (model, bytes) = candidate();
    for signal in [0, 1, 9, 15, 64] {
        check(
            &model,
            &bytes,
            NR_PIDFD_SEND_SIGNAL,
            [14, signal, 0, 0, 0, 0],
            if signal == 9 {
                SECCOMP_RET_ALLOW
            } else {
                SECCOMP_RET_KILL_PROCESS
            },
        );
    }
    for (index, value) in [(0, 15), (2, 0x1000), (3, 1)] {
        let mut args = [14, 9, 0, 0, 0, 0];
        args[index] = value;
        check(
            &model,
            &bytes,
            NR_PIDFD_SEND_SIGNAL,
            args,
            SECCOMP_RET_KILL_PROCESS,
        );
    }
    for (index, value) in [
        (0, 0),
        (0, 1),
        (1, 15),
        (3, 0),
        (3, WEXITED),
        (3, WEXITED | WNOHANG | 0x0100_0000),
        (4, 0x1000),
    ] {
        let mut args = [P_PIDFD, 14, 0x1000, WEXITED | WNOHANG, 0, 0];
        args[index] = value;
        check(&model, &bytes, NR_WAITID, args, SECCOMP_RET_KILL_PROCESS);
    }
}

#[test]
fn listener_ioctl_domain_excludes_addfd_foreign_fd_and_compat_sizes() {
    let (model, bytes) = candidate();
    for command in [
        SECCOMP_IOCTL_NOTIF_RECV,
        SECCOMP_IOCTL_NOTIF_SEND,
        SECCOMP_IOCTL_NOTIF_ID_VALID,
    ] {
        check(
            &model,
            &bytes,
            NR_IOCTL,
            [15, command, 0x1000, 0, 0, 0],
            SECCOMP_RET_ALLOW,
        );
        for fd in [0, 1, 2, 10, 13, 14, 20, u64::MAX] {
            check(
                &model,
                &bytes,
                NR_IOCTL,
                [fd, command, 0x1000, 0, 0, 0],
                SECCOMP_RET_KILL_PROCESS,
            );
        }
        check(
            &model,
            &bytes,
            NR_IOCTL,
            [15, command ^ (1 << 16), 0x1000, 0, 0, 0],
            SECCOMP_RET_KILL_PROCESS,
        );
    }
    // Linux v6.12 SECCOMP_IOCTL_NOTIF_ADDFD numeric value is a negative fixture.
    for command in [0, TCGETS, 0x4018_2103, SECCOMP_IOCTL_NOTIF_SEND | 1 << 32] {
        check(
            &model,
            &bytes,
            NR_IOCTL,
            [15, command, 0x1000, 0, 0, 0],
            SECCOMP_RET_KILL_PROCESS,
        );
    }
}

#[test]
fn runtime_does_not_inherit_setup_or_worker_capabilities() {
    let (model, bytes) = candidate();
    for nr in [
        NR_READV,
        NR_WRITEV,
        NR_FSTAT,
        NR_FCNTL,
        NR_SENDMSG,
        NR_EXECVEAT,
        NR_RT_SIGACTION,
        NR_GETPID,
        NR_RSEQ,
        -1,
        i32::MAX,
        29_999,
    ] {
        check(&model, &bytes, nr, [0; 6], SECCOMP_RET_KILL_PROCESS);
    }
    // A dense synthetic sweep catches accidental allow-on-unknown paths.
    for nr in -1..=512 {
        let data = SeccompData::aarch64(nr, [0; 6]);
        assert_eq!(
            bytes.evaluate(&data).unwrap(),
            model.semantic_action(&data),
            "nr={nr}"
        );
    }
    for prot in [0, 1, 2, 3, 4, 5, 6, 7, u64::MAX] {
        check(
            &model,
            &bytes,
            NR_MPROTECT,
            [0, 4096, prot, 0, 0, 0],
            if prot <= 3 {
                SECCOMP_RET_ALLOW
            } else {
                SECCOMP_RET_KILL_PROCESS
            },
        );
    }
    for (index, value) in [
        (3, MAP_ANONYMOUS),
        (3, MAP_PRIVATE),
        (3, MAP_PRIVATE | MAP_ANONYMOUS | 0x10),
        (4, 0xffff_ffff),
        (5, 1),
    ] {
        let mut args = [0, 4096, 3, MAP_PRIVATE | MAP_ANONYMOUS, u64::MAX, 0];
        args[index] = value;
        check(&model, &bytes, NR_MMAP, args, SECCOMP_RET_KILL_PROCESS);
    }
    assert_eq!(bytes.bytes(), model.compile().bytes());
    assert!(bytes.instructions().len() <= 4096);
}
