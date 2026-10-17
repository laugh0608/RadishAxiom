use radishaxiom_solver_supervision_core::cgroup::*;
fn limits() -> CgroupLimits {
    CgroupLimits {
        memory_max: 128,
        swap_max: 0,
        pids_max: 2,
        file_bytes: 4096,
    }
}
fn files() -> [Vec<u8>; 12] {
    [
        b"128\n".to_vec(),
        b"0\n".to_vec(),
        b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n".to_vec(),
        b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n".to_vec(),
        b"12\n".to_vec(),
        b"32\n".to_vec(),
        b"0\n".to_vec(),
        b"2\n".to_vec(),
        b"1\n".to_vec(),
        b"max 0\n".to_vec(),
        b"1\n".to_vec(),
        b"populated 1\nfrozen 0\n".to_vec(),
    ]
}
fn view(f: &[Vec<u8>; 12]) -> CgroupFiles<'_> {
    CgroupFiles {
        memory_max: &f[0],
        memory_swap_max: &f[1],
        memory_events: &f[2],
        memory_events_local: &f[3],
        memory_current: &f[4],
        memory_peak: &f[5],
        memory_oom_group: &f[6],
        pids_max: &f[7],
        pids_current: &f[8],
        pids_events: &f[9],
        cgroup_procs: &f[10],
        cgroup_events: &f[11],
    }
}
#[test]
fn stable_values_match_original_parse_and_membership_stays_explicit() {
    for stage in [
        CgroupStage::SupervisorOnly,
        CgroupStage::SupervisorAndChild(7),
        CgroupStage::ReapedSupervisorOnly,
    ] {
        let mut f = files();
        if matches!(stage, CgroupStage::SupervisorAndChild(_)) {
            f[8] = b"2\n".to_vec();
            f[10] = b"7\n1\n".to_vec();
        }
        let values = ParsedCgroup::parse_values(view(&f), limits()).unwrap();
        values.check_stage(stage).unwrap();
        assert_eq!(
            values.parsed,
            ParsedCgroup::parse(view(&f), stage, limits()).unwrap()
        );
    }
    let mut f = files();
    f[8] = b"2\n".to_vec();
    let values = ParsedCgroup::parse_values(view(&f), limits()).unwrap();
    assert_eq!(
        values.check_stage(CgroupStage::ReapedSupervisorOnly),
        Err(CgroupError::Membership)
    );
}
#[test]
fn nonmembership_errors_cannot_hide_behind_exit_membership() {
    for i in 0..12 {
        for mode in 0..3 {
            let mut f = files();
            f[8] = b"2\n".to_vec();
            match mode {
                0 => {
                    f[i].pop();
                }
                1 => {
                    let at = if [2, 3, 9, 11].contains(&i) {
                        f[i].iter().position(|b| *b == b' ').unwrap() + 1
                    } else {
                        0
                    };
                    f[i].insert(at, b'+');
                }
                _ => f[i].extend_from_slice(b"0\n"),
            };
            assert!(
                ParsedCgroup::parse_values(view(&f), limits()).is_err(),
                "field {i} mode {mode}"
            );
        }
    }
}
#[test]
fn unknown_fields_duplicate_events_and_frozen_reject() {
    for bytes in [
        b"populated 1\nfrozen 1\n".as_slice(),
        b"populated 0\nfrozen 0\n",
        b"populated 1\nfrozen 0\nfrozen 0\n",
        b"populated 1\nfrozen 0\nunknown 0\n",
    ] {
        let mut f = files();
        f[11] = bytes.to_vec();
        assert!(ParsedCgroup::parse_values(view(&f), limits()).is_err());
    }
}
