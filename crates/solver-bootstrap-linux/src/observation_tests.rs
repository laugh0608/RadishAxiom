use super::*;
use crate::{
    abi,
    test_support::{Script, Step},
};
fn limits() -> CgroupLimits {
    crate::configuration::tests::exported().cgroup
}
pub(crate) fn files(members: &str, count: &str) -> [Vec<u8>; 12] {
    let l = limits();
    [
        format!("{}\n", l.memory_max).into_bytes(),
        b"0\n".to_vec(),
        b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n".to_vec(),
        b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n".to_vec(),
        b"512\n".to_vec(),
        b"1024\n".to_vec(),
        b"0\n".to_vec(),
        b"2\n".to_vec(),
        count.as_bytes().to_vec(),
        b"max 0\n".to_vec(),
        members.as_bytes().to_vec(),
        b"populated 1\nfrozen 0\n".to_vec(),
    ]
}
pub(crate) fn reads(files: &[Vec<u8>; 12]) -> Vec<Step> {
    let mut steps = Vec::new();
    for (i, bytes) in files.iter().enumerate() {
        steps.push(Step::Scalar(abi::NR_LSEEK, Some(20 + i as u64), 0));
        steps.push(Step::Read(20 + i as i32, bytes.clone()));
        steps.push(Step::Read(20 + i as i32, Vec::new()));
    }
    steps
}
fn exit() -> abi::ChildExit {
    abi::ChildExit {
        pid: 2,
        uid: 1000,
        code: 1,
        status: 0,
    }
}
fn fds() -> [i32; 12] {
    [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]
}
#[test]
fn exit_transition_keeps_both_samples_and_no_deadline_renewal() {
    let first = files("1\n", "2\n");
    let stable = files("1\n", "1\n");
    let mut steps = vec![Step::Wait(None)];
    steps.extend(reads(&first));
    steps.push(Step::Wait(Some(exit())));
    steps.extend(reads(&stable));
    let mut linux = Linux::new(Script::new(steps));
    let mut log = ObservationLog::new();
    let mut child = ChildFact::Running(2);
    assert!(
        log.capture(
            &mut linux,
            &fds(),
            limits(),
            1_000_000,
            &mut child,
            Some(14)
        )
        .unwrap()
        .is_none()
    );
    let sample = log
        .capture(
            &mut linux,
            &fds(),
            limits(),
            1_000_000,
            &mut child,
            Some(14),
        )
        .unwrap()
        .unwrap();
    assert_eq!(sample.members, [1]);
    assert_eq!(log.reads.len(), 2);
    assert_eq!(log.reads[0].before, ChildFact::Running(2));
    assert_eq!(
        log.reads[0].after,
        ChildFact::Reaped {
            pid: 2,
            code: 1,
            status: 0
        }
    );
    for read in &log.reads {
        assert!(read.completed.iter().all(|v| *v));
        assert!(
            read.intervals
                .windows(2)
                .all(|w| w[0].end_ns <= w[1].start_ns)
        );
    }
    linux.kernel.done();
}
#[test]
fn every_nonmembership_syntax_error_stops_before_retry() {
    for index in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11] {
        for mode in 0..3 {
            let mut bad = files("1\n", "2\n");
            match mode {
                0 => {
                    bad[index].pop();
                }
                1 => {
                    let at = if [2, 3, 9, 11].contains(&index) {
                        bad[index].iter().position(|b| *b == b' ').unwrap() + 1
                    } else {
                        0
                    };
                    bad[index].insert(at, b'+');
                }
                _ => {
                    if [2, 3, 9, 11].contains(&index) {
                        let line = bad[index]
                            .split_inclusive(|b| *b == b'\n')
                            .next()
                            .unwrap()
                            .to_vec();
                        bad[index].extend(line);
                    } else {
                        bad[index].extend_from_slice(b"0\n");
                    }
                }
            }
            let mut steps = vec![Step::Wait(None)];
            steps.extend(reads(&bad));
            steps.push(Step::Wait(Some(exit())));
            let mut linux = Linux::new(Script::new(steps));
            let mut log = ObservationLog::new();
            let mut child = ChildFact::Running(2);
            assert!(
                log.capture(
                    &mut linux,
                    &fds(),
                    limits(),
                    1_000_000,
                    &mut child,
                    Some(14)
                )
                .is_err(),
                "index {index} mode {mode}"
            );
            assert!(!log.retry_used);
            assert_eq!(log.reads[0].files, bad);
            linux.kernel.done();
        }
    }
}
#[test]
fn drift_events_extra_pid_and_counter_rollback_are_never_transition() {
    for variant in 0..6 {
        let baseline = files("1\n", "1\n");
        let mut bad = files("1\n", "2\n");
        match variant {
            0 => bad[11] = b"populated 1\nfrozen 1\n".to_vec(),
            1 => bad[6] = b"1\n".to_vec(),
            2 => bad[5] = b"1000\n".to_vec(),
            3 => bad[10] = b"1\n2\n3\n".to_vec(),
            4 => {
                bad[2] = b"low 0\nhigh 0\nmax 1\noom 0\noom_kill 0\noom_group_kill 0\n".to_vec();
            }
            _ => bad[9] = b"max 1\n".to_vec(),
        };
        let mut steps = reads(&baseline);
        steps.push(Step::Wait(None));
        steps.extend(reads(&bad));
        steps.push(Step::Wait(Some(exit())));
        let mut linux = Linux::new(Script::new(steps));
        let mut log = ObservationLog::new();
        let mut child = ChildFact::Absent;
        log.capture(&mut linux, &fds(), limits(), 1_000_000, &mut child, None)
            .unwrap();
        child = ChildFact::Running(2);
        assert!(
            log.capture(
                &mut linux,
                &fds(),
                limits(),
                1_000_000,
                &mut child,
                Some(14)
            )
            .is_err()
        );
        assert!(!log.retry_used);
        assert_eq!(log.reads.len(), 2);
        linux.kernel.done();
    }
}
#[test]
fn partial_facts_survive_file_failure_and_each_clock_is_monotone() {
    let mut linux = Linux::new(Script::new([
        Step::Clock(10),
        Step::Scalar(abi::NR_LSEEK, Some(20), 0),
        Step::Read(20, b"12\n".to_vec()),
        Step::Clock(20),
        Step::Read(20, Vec::new()),
        Step::Clock(15),
    ]));
    let mut log = ObservationLog::new();
    let mut child = ChildFact::Absent;
    assert!(matches!(
        log.capture(&mut linux, &fds(), limits(), 100, &mut child, None),
        Err(ObservationError::ClockRollback)
    ));
    assert_eq!(log.reads[0].files[0], b"12\n");
    assert!(!log.reads[0].completed[0]);
    linux.kernel.done();
}
#[test]
fn at_most_four_prescribed_reads_are_stored() {
    let sample = files("1\n", "1\n");
    let mut steps = Vec::new();
    for _ in 0..4 {
        steps.extend(reads(&sample));
    }
    let mut linux = Linux::new(Script::new(steps));
    let mut log = ObservationLog::new();
    let mut child = ChildFact::Absent;
    for _ in 0..4 {
        log.capture(&mut linux, &fds(), limits(), 1_000_000, &mut child, None)
            .unwrap();
    }
    assert!(matches!(
        log.capture(&mut linux, &fds(), limits(), 1_000_000, &mut child, None),
        Err(ObservationError::Budget)
    ));
    assert_eq!(log.reads.len(), 4);
    linux.kernel.done();
}
