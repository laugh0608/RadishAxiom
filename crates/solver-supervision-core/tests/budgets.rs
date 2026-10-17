use radishaxiom_solver_supervision_core::{cgroup::*, wire::*};
fn binding() -> BootstrapBinding {
    BootstrapBinding {
        attempt: [1; 32],
        request: [2; 32],
        policy: [3; 32],
        image: [4; 32],
        nonce: [5; 32],
    }
}
fn limits() -> WireLimits {
    WireLimits {
        query_bytes: 7,
        stdout_bytes: 5,
        stderr_bytes: 3,
    }
}
#[test]
fn caller_budgets_apply_on_encode_and_before_payload_copy() {
    for (direction, first, extra, resource) in [
        (
            Direction::MacToSupervisor,
            BootstrapMessage::QueryChunk(vec![0; 7]),
            BootstrapMessage::QueryChunk(vec![0]),
            "query",
        ),
        (
            Direction::SupervisorToMac,
            BootstrapMessage::StdoutChunk(vec![0; 5]),
            BootstrapMessage::StdoutChunk(vec![0]),
            "stdout",
        ),
        (
            Direction::SupervisorToMac,
            BootstrapMessage::StderrChunk(vec![0; 3]),
            BootstrapMessage::StderrChunk(vec![0]),
            "stderr",
        ),
    ] {
        let mut encoder = BootstrapEncoder::new(direction, limits());
        let first = BootstrapFrame {
            binding: binding(),
            message: first,
        };
        let bytes = encoder.encode(&first).unwrap();
        let mut decoder = BootstrapDecoder::new_bound(direction, binding(), limits());
        assert_eq!(decoder.poll(&bytes).unwrap().frame, Some(first));
        let extra = BootstrapFrame {
            binding: binding(),
            message: extra,
        };
        assert_eq!(encoder.encode(&extra), Err(WireError::Limit(resource)));
        let mut larger = limits();
        larger.query_bytes += 1;
        larger.stdout_bytes += 1;
        larger.stderr_bytes += 1;
        let mut allowed = BootstrapEncoder::new(direction, larger);
        allowed
            .encode(&BootstrapFrame {
                binding: binding(),
                message: match resource {
                    "query" => BootstrapMessage::QueryChunk(vec![0; 7]),
                    "stdout" => BootstrapMessage::StdoutChunk(vec![0; 5]),
                    _ => BootstrapMessage::StderrChunk(vec![0; 3]),
                },
            })
            .unwrap();
        let extra_bytes = allowed.encode(&extra).unwrap();
        assert_eq!(
            decoder.poll(&extra_bytes[..BOOTSTRAP_HEADER_BYTES]),
            Err(WireError::Limit(resource))
        );
        assert_eq!(decoder.buffered_bytes(), BOOTSTRAP_HEADER_BYTES);
        assert!(decoder.is_poisoned());
    }
    let mut encoder = BootstrapEncoder::new(Direction::MacToSupervisor, limits());
    assert_eq!(
        encoder.encode(&BootstrapFrame {
            binding: binding(),
            message: BootstrapMessage::Arm(Arm {
                deadline_ns: 1,
                query_len: 8,
                query_digest: [4; 32],
            })
        }),
        Err(WireError::Limit("query"))
    );
}
fn files() -> CgroupFiles<'static> {
    let events = b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n";
    CgroupFiles {
        memory_max: b"99\n",
        memory_swap_max: b"0\n",
        memory_events: events,
        memory_events_local: events,
        memory_current: b"1\n",
        memory_peak: b"2\n",
        memory_oom_group: b"0\n",
        pids_max: b"2\n",
        pids_current: b"1\n",
        pids_events: b"max 0\n",
        cgroup_procs: b"1\n",
        cgroup_events: b"populated 1\nfrozen 0\n",
    }
}
#[test]
fn file_parser_receives_all_resource_limits_from_caller() {
    let limits = CgroupLimits {
        memory_max: 99,
        swap_max: 0,
        pids_max: 2,
        file_bytes: 64,
    };
    assert!(ParsedCgroup::parse(files(), CgroupStage::SupervisorOnly, limits).is_ok());
    let mut altered = limits;
    altered.memory_max += 1;
    assert_eq!(
        ParsedCgroup::parse(files(), CgroupStage::SupervisorOnly, altered),
        Err(CgroupError::Configuration)
    );
    let mut altered = limits;
    altered.swap_max += 1;
    assert_eq!(
        ParsedCgroup::parse(files(), CgroupStage::SupervisorOnly, altered),
        Err(CgroupError::Configuration)
    );
    let mut altered = limits;
    altered.pids_max += 1;
    assert_eq!(
        ParsedCgroup::parse(files(), CgroupStage::SupervisorOnly, altered),
        Err(CgroupError::Configuration)
    );
    let mut altered = limits;
    altered.file_bytes = 2;
    assert_eq!(
        ParsedCgroup::parse(files(), CgroupStage::SupervisorOnly, altered),
        Err(CgroupError::Limit)
    );
}
