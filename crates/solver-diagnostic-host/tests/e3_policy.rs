use radishaxiom_solver_diagnostic_host::e3_abi::*;
use radishaxiom_solver_diagnostic_host::e3_policy::*;

fn positive_calls() -> Vec<SeccompData> {
    let mut calls = Vec::new();
    let mut add = |nr, args| calls.push(SeccompData::aarch64(nr, args));
    for nr in [NR_READ, NR_READV, NR_WRITE, NR_WRITEV, NR_CLOSE, NR_FSTAT] {
        add(
            nr,
            [
                if nr == NR_WRITE || nr == NR_WRITEV {
                    1
                } else {
                    0
                },
                0,
                0,
                0,
                0,
                0,
            ],
        );
    }
    add(NR_FCNTL, [2, 3, 0, 0, 0, 0]);
    add(NR_IOCTL, [2, 0x5401, 0, 0, 0, 0]);
    for nr in [
        NR_BRK,
        NR_MUNMAP,
        NR_RT_SIGRETURN,
        NR_SIGALTSTACK,
        NR_GETPID,
        NR_GETTID,
        NR_SCHED_YIELD,
        NR_SET_TID_ADDRESS,
        NR_EXIT,
        NR_EXIT_GROUP,
    ] {
        add(nr, [0; 6]);
    }
    add(NR_MMAP, [0, 8192, 3, 0x22, u64::MAX, 0]);
    add(NR_MMAP, [0, 8192, 0, 0x4022, u64::MAX, 0]);
    add(NR_MPROTECT, [0, 8192, 1, 0, 0, 0]);
    add(NR_MREMAP, [0, 8192, 16384, 1, 0, 0]);
    add(NR_MADVISE, [0, 8192, 8, 0, 0, 0]);
    add(NR_RT_SIGACTION, [2, 0, 0, 8, 0, 0]);
    add(NR_RT_SIGPROCMASK, [2, 0, 0, 8, 0, 0]);
    for nr in [NR_CLOCK_GETTIME, NR_CLOCK_GETRES] {
        add(nr, [7, 0, 0, 0, 0, 0]);
    }
    add(NR_GETRUSAGE, [1, 0, 0, 0, 0, 0]);
    for op in [128, 129, 137, 138] {
        add(NR_FUTEX, [0, op, 0, 0, 0, 0]);
    }
    add(NR_SET_ROBUST_LIST, [0, 24, 0, 0, 0, 0]);
    for flags in [0, 1] {
        add(NR_RSEQ, [0, 32, flags, 0xd428_bc00, 0, 0]);
    }
    add(NR_PRLIMIT64, [0, 9, 0, 0, 0, 0]);
    add(NR_SENDMSG, [4, 0, 0x4000, 0, 0, 0]);
    add(NR_EXECVEAT, [3, 0, 0, 0, 0x1000, 0]);
    calls
}

#[test]
fn generated_filter_matches_separate_oracle_for_raw_register_mutations() {
    let policy = worker_policy();
    for seed in positive_calls() {
        assert_ne!(semantic_worker_decision(&seed), SECCOMP_RET_KILL_PROCESS);
        assert_eq!(
            policy.evaluate(&seed).unwrap(),
            semantic_worker_decision(&seed)
        );
        for arg in 0..6 {
            for bit in 0..64 {
                let mut mutated = seed;
                mutated.args[arg] ^= 1 << bit;
                assert_eq!(
                    policy.evaluate(&mutated).unwrap(),
                    semantic_worker_decision(&mutated),
                    "{mutated:?}"
                );
            }
        }
        for arch in [0, 0x4000_0028, 0xc000_003e, 0x8000_00b7, u32::MAX] {
            let mut mutated = seed;
            mutated.arch = arch;
            assert_eq!(policy.evaluate(&mutated).unwrap(), SECCOMP_RET_KILL_PROCESS);
        }
        let mut x32 = seed;
        x32.nr |= 0x4000_0000;
        assert_eq!(policy.evaluate(&x32).unwrap(), SECCOMP_RET_KILL_PROCESS);
    }
    for nr in -1..=512 {
        for fill in [0, 1, u32::MAX as u64, 1u64 << 32, u64::MAX] {
            let data = SeccompData::aarch64(nr, [fill; 6]);
            assert_eq!(
                policy.evaluate(&data).unwrap(),
                semantic_worker_decision(&data),
                "{data:?}"
            );
        }
    }
}

#[test]
fn exact_full_width_values_never_accept_low_word_aliases() {
    let policy = worker_policy();
    let cases = [
        (NR_READ, [1 << 32, 0, 0, 0, 0, 0]),
        (NR_WRITE, [(1 << 32) | 1, 0, 0, 0, 0, 0]),
        (NR_FSTAT, [(1 << 32) | 2, 0, 0, 0, 0, 0]),
        (NR_IOCTL, [0, (1 << 32) | TCGETS, 0, 0, 0, 0]),
        (NR_FCNTL, [0, (1 << 32) | F_GETFL, 0, 0, 0, 0]),
        (NR_MMAP, [0, 4096, 3, 0x22, u32::MAX as u64, 0]),
        (NR_MMAP, [0, 4096, 3, (1 << 32) | 0x22, u64::MAX, 0]),
        (NR_MMAP, [0, 4096, 7, 0x22, u64::MAX, 0]),
        (NR_MMAP, [0, 4096, 3, 0x32, u64::MAX, 0]),
        (NR_MPROTECT, [0, 4096, (1 << 32) | 3, 0, 0, 0]),
        (NR_MREMAP, [0, 4096, 8192, 3, 0, 0]),
        (NR_GETRUSAGE, [u64::MAX, 0, 0, 0, 0, 0]),
        (NR_GETRUSAGE, [u32::MAX as u64, 0, 0, 0, 0, 0]),
        (NR_CLOCK_GETTIME, [0, 0, 0, 0, 0, 0]),
        (NR_FUTEX, [0, 256 | 128, 0, 0, 0, 0]),
        (NR_FUTEX, [0, 0, 0, 0, 0, 0]),
        (NR_SET_ROBUST_LIST, [0, 32, 0, 0, 0, 0]),
        (NR_RSEQ, [0, 32, 2, RSEQ_SIG, 0, 0]),
        (NR_PRLIMIT64, [0, 9, 1, 0, 0, 0]),
        (NR_SENDMSG, [4, 0, 0, 0, 0, 0]),
        (NR_SENDMSG, [5, 0, MSG_NOSIGNAL, 0, 0, 0]),
        (NR_EXECVEAT, [3, 0, 0, 0, (1 << 32) | AT_EMPTY_PATH, 0]),
        (NR_EXECVEAT, [4, 0, 0, 0, AT_EMPTY_PATH, 0]),
    ];
    for (nr, args) in cases {
        let data = SeccompData::aarch64(nr, args);
        assert_eq!(
            semantic_worker_decision(&data),
            SECCOMP_RET_KILL_PROCESS,
            "{data:?}"
        );
        assert_eq!(
            policy.evaluate(&data).unwrap(),
            SECCOMP_RET_KILL_PROCESS,
            "{data:?}"
        );
    }
}

#[test]
fn no_worker_syscall_can_create_duplicate_or_receive_a_new_fd() {
    let policy = worker_policy();
    // dup/dup3/openat/pipe2/socket/socketpair/recvmsg/clone/execve/seccomp/
    // memfd_create/pidfd_getfd/clone3/openat2/prctl/bpf/io_uring_setup.
    for nr in [
        23, 24, 56, 59, 198, 199, 212, 220, 221, 277, 279, 438, 435, 437, 167, 280, 425,
    ] {
        for fd in 0..=5 {
            let data = SeccompData::aarch64(nr, [fd; 6]);
            assert_eq!(policy.evaluate(&data).unwrap(), SECCOMP_RET_KILL_PROCESS);
        }
    }
    // Even absolute-path-shaped exec arguments get USER_NOTIF, never ALLOW.
    assert_eq!(
        policy
            .evaluate(&SeccompData::aarch64(
                NR_EXECVEAT,
                [3, 0x1234, 0x2000, 0x3000, AT_EMPTY_PATH, 0]
            ))
            .unwrap(),
        SECCOMP_RET_USER_NOTIF
    );
    for fd in 0..=5 {
        assert_eq!(
            policy
                .evaluate(&SeccompData::aarch64(NR_CLOSE, [fd, 0, 0, 0, 0, 0]))
                .unwrap(),
            SECCOMP_RET_ALLOW
        );
    }
}

#[test]
fn interpreter_rejects_corruption_and_unreachable_bad_instructions() {
    let data = SeccompData::aarch64(NR_GETPID, [0; 6]).bytes();
    let ret = [6, 0, 0, 0, 0, 0, 255, 127];
    assert_eq!(interpret_cbpf(&ret, &data), Ok(SECCOMP_RET_ALLOW));
    assert_eq!(interpret_cbpf(&[], &data), Err(PolicyError::ProgramSize));
    assert_eq!(
        interpret_cbpf(&ret[..7], &data),
        Err(PolicyError::ProgramSize)
    );
    assert_eq!(
        interpret_cbpf(&ret, &data[..63]),
        Err(PolicyError::DataSize)
    );
    for bad in [
        [0x20, 0, 0, 0, 64, 0, 0, 0],     // load beyond struct
        [0x20, 0, 0, 0, 1, 0, 0, 0],      // misaligned load
        [5, 0, 0, 0, 255, 255, 255, 255], // invalid JA
        [0x15, 0, 255, 0, 0, 0, 0, 0],    // invalid conditional target
        [6, 0, 0, 0, 0, 0, 0, 0],         // KILL_THREAD outside chosen subset
        [0xff; 8],
    ] {
        let mut bytes = ret.to_vec();
        bytes.extend_from_slice(&bad);
        assert!(interpret_cbpf(&bytes, &data).is_err());
    }
    let mut bytes = worker_policy().bytes();
    bytes[0] = 0xff;
    assert!(interpret_cbpf(&bytes, &data).is_err());
}

#[test]
fn explicit_abi_offsets_roundtrip_and_require_exact_sizes() {
    let original = SeccompData {
        nr: -1,
        arch: AUDIT_ARCH_AARCH64,
        instruction_pointer: 0x0123_4567_89ab_cdef,
        args: [1, 0x1234_5678_9abc_def0, u64::MAX, 0, 4, 5],
    };
    let bytes = original.bytes();
    assert_eq!(&bytes[4..8], &AUDIT_ARCH_AARCH64.to_le_bytes());
    assert_eq!(&bytes[24..32], &0x1234_5678_9abc_def0u64.to_le_bytes());
    assert_eq!(SeccompData::decode(&bytes).unwrap(), original);
    for len in [0, 63, 65, 128] {
        assert!(SeccompData::decode(&vec![0; len]).is_err());
    }
    let mut notification = vec![0; 16];
    notification[0..8].copy_from_slice(&123u64.to_le_bytes());
    notification[8..12].copy_from_slice(&7u32.to_le_bytes());
    notification.extend_from_slice(&bytes);
    assert_eq!(
        SeccompNotification::decode(&notification).unwrap(),
        SeccompNotification {
            id: 123,
            pid: 7,
            flags: 0,
            data: original
        }
    );
    assert_eq!(validate_notification_sizes(&[80, 0, 24, 0, 64, 0]), Ok(()));
    for sizes in [
        [81, 0, 24, 0, 64, 0],
        [80, 0, 25, 0, 64, 0],
        [80, 0, 24, 0, 65, 0],
    ] {
        assert_eq!(
            validate_notification_sizes(&sizes),
            Err(AbiError::UnsupportedNotificationSizes)
        );
    }
}

#[test]
fn stable_worker_artifact_digest() {
    let policy = worker_policy();
    assert_eq!(policy.bytes().len(), policy.instructions().len() * 8);
    assert!(policy.instructions().len() <= 4096);
    assert_eq!(policy.instructions().len(), 782);
    assert_eq!(
        policy.digest(),
        "sha256:2f5ff64bffb3b8cd438049d8f33d6ce86f9d3c72f4d61add5eba7da056a04e8f"
    );
    assert_eq!(policy.bytes(), worker_policy().bytes());
}
