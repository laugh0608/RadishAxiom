//! Native read intervals and child facts, deliberately unrelated to Synthetic*.
use crate::syscall::{Error, Kernel, Linux};
use radishaxiom_solver_supervision_core::cgroup::{
    CgroupError, CgroupFiles, CgroupLimits, CgroupStage, ParsedCgroup,
};

pub(crate) const CGROUP_NAMES: [&str; 12] = [
    "memory.max",
    "memory.swap.max",
    "memory.events",
    "memory.events.local",
    "memory.current",
    "memory.peak",
    "memory.oom.group",
    "pids.max",
    "pids.current",
    "pids.events",
    "cgroup.procs",
    "cgroup.events",
];
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct ReadInterval {
    pub start_ns: u64,
    pub end_ns: u64,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ChildFact {
    Absent,
    Running(u32),
    Reaped { pid: u32, code: i32, status: i32 },
}
#[derive(Debug)]
pub(crate) struct NativeCgroupRead {
    pub intervals: [ReadInterval; 12],
    pub files: [Vec<u8>; 12],
    pub completed: [bool; 12],
    pub before: ChildFact,
    pub after: ChildFact,
}
#[derive(Debug)]
pub(crate) enum ObservationError {
    System(Error),
    Deadline,
    ClockRollback,
    FileLimit(usize),
    Parse(CgroupError),
    Resource,
    Transition,
    CounterRollback,
    Budget,
}
impl From<Error> for ObservationError {
    fn from(e: Error) -> Self {
        Self::System(e)
    }
}

#[derive(Debug)]
pub(crate) struct ObservationLog {
    pub reads: Vec<NativeCgroupRead>,
    latest: Option<ParsedCgroup>,
    retry_used: bool,
}
impl ObservationLog {
    pub fn new() -> Self {
        Self {
            reads: Vec::with_capacity(4),
            latest: None,
            retry_used: false,
        }
    }
    pub fn capture<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
        fds: &[i32; 12],
        limits: CgroupLimits,
        deadline: u64,
        child: &mut ChildFact,
        pidfd: Option<i32>,
    ) -> Result<Option<ParsedCgroup>, ObservationError> {
        if self.reads.len() == 4 {
            return Err(ObservationError::Budget);
        }
        let before = observe_child(linux, child, pidfd)?;
        let slot = self.reads.len();
        self.reads.push(NativeCgroupRead {
            intervals: [ReadInterval {
                start_ns: 0,
                end_ns: 0,
            }; 12],
            files: std::array::from_fn(|_| Vec::with_capacity(limits.file_bytes + 1)),
            completed: [false; 12],
            before,
            after: before,
        });
        let mut last = if slot > 0 {
            self.reads[slot - 1].intervals[11].end_ns
        } else {
            0
        };
        for (i, fd) in fds.iter().enumerate() {
            let start = linux.boottime_ns()?;
            if start < last {
                return Err(ObservationError::ClockRollback);
            }
            if start >= deadline {
                return Err(ObservationError::Deadline);
            }
            last = start;
            self.reads[slot].intervals[i].start_ns = start;
            linux.rewind(*fd)?;
            let mut scratch = vec![0; limits.file_bytes + 1];
            loop {
                let used = self.reads[slot].files[i].len();
                let n = linux.read(*fd, &mut scratch[..limits.file_bytes + 1 - used])?;
                self.reads[slot].files[i].extend_from_slice(&scratch[..n]);
                let now = linux.boottime_ns()?;
                if now < last {
                    return Err(ObservationError::ClockRollback);
                }
                last = now;
                self.reads[slot].intervals[i].end_ns = now;
                if now >= deadline {
                    return Err(ObservationError::Deadline);
                }
                if self.reads[slot].files[i].len() > limits.file_bytes {
                    return Err(ObservationError::FileLimit(i));
                }
                if n == 0 {
                    self.reads[slot].completed[i] = true;
                    break;
                }
            }
            let end = linux.boottime_ns()?;
            if end < last {
                return Err(ObservationError::ClockRollback);
            }
            if end >= deadline {
                return Err(ObservationError::Deadline);
            }
            last = end;
            self.reads[slot].intervals[i].end_ns = end;
        }
        let after = observe_child(linux, child, pidfd)?;
        self.reads[slot].after = after;
        let sample = self.reads.last().expect("just stored native read");
        // Check all non-lifecycle values before considering an exit race.
        let values =
            ParsedCgroup::parse_values(sample.view(), limits).map_err(ObservationError::Parse)?;
        let parsed = values.parsed.clone();
        if let Some(before) = &self.latest {
            if !parsed.memory_events.follows(before.memory_events)
                || !parsed
                    .memory_events_local
                    .follows(before.memory_events_local)
                || parsed.memory_peak < before.memory_peak
                || parsed.pids_max_events < before.pids_max_events
            {
                return Err(ObservationError::CounterRollback);
            }
            if parsed.memory_oom_group != before.memory_oom_group {
                return Err(ObservationError::Parse(CgroupError::Configuration));
            }
        }
        for events in [parsed.memory_events, parsed.memory_events_local] {
            if events.max != 0
                || events.oom != 0
                || events.oom_kill != 0
                || events.oom_group_kill != 0
            {
                return Err(ObservationError::Resource);
            }
        }
        if parsed.pids_max_events != 0 {
            return Err(ObservationError::Resource);
        }
        let stage = match after {
            ChildFact::Absent => CgroupStage::SupervisorOnly,
            ChildFact::Running(pid) => CgroupStage::SupervisorAndChild(pid),
            ChildFact::Reaped { .. } => CgroupStage::ReapedSupervisorOnly,
        };
        if let Err(error) = values.check_stage(stage) {
            if !self.retry_used && transition_only(sample, &values) {
                self.latest = Some(parsed);
                self.retry_used = true;
                return Ok(None);
            }
            return Err(ObservationError::Parse(error));
        }
        self.latest = Some(parsed.clone());
        Ok(Some(parsed))
    }
}
impl NativeCgroupRead {
    fn view(&self) -> CgroupFiles<'_> {
        let f = &self.files;
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
}
fn observe_child<K: Kernel>(
    linux: &mut Linux<K>,
    child: &mut ChildFact,
    pidfd: Option<i32>,
) -> Result<ChildFact, ObservationError> {
    if let (ChildFact::Running(pid), Some(fd)) = (*child, pidfd)
        && let Some(exit) = linux.wait(fd)?
    {
        if exit.pid != pid {
            return Err(ObservationError::Transition);
        }
        *child = ChildFact::Reaped {
            pid,
            code: exit.code,
            status: exit.status,
        };
    }
    Ok(*child)
}
fn transition_only(
    sample: &NativeCgroupRead,
    values: &radishaxiom_solver_supervision_core::cgroup::ParsedCgroupValues,
) -> bool {
    let pid = match (sample.before, sample.after) {
        (ChildFact::Running(pid), ChildFact::Reaped { pid: after, .. }) if pid == after => pid,
        _ => return false,
    };
    (values.parsed.members == [1] || values.parsed.members == [1, pid])
        && (values.pids_current == 1 || values.pids_current == 2)
}

#[cfg(test)]
#[path = "observation_tests.rs"]
pub(crate) mod tests;
