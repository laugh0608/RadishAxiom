//! Bounded synthetic cgroup v2 observations; no filesystem access or runtime qualification.

pub const CGROUP_MEMORY_MAX: u64 =
    radishaxiom_ir::solver::PROCESS_LIMITS.working_memory_bytes as u64;
pub const CGROUP_PIDS_MAX: u64 = 2;
pub const CGROUP_FILE_BYTES: usize = 4096;
pub const fn process_cgroup_limits() -> CgroupLimits {
    CgroupLimits {
        memory_max: CGROUP_MEMORY_MAX,
        swap_max: 0,
        pids_max: CGROUP_PIDS_MAX,
        file_bytes: CGROUP_FILE_BYTES,
    }
}

pub use radishaxiom_solver_supervision_core::cgroup::{CgroupError, CgroupStage, MemoryEvents};
use radishaxiom_solver_supervision_core::cgroup::{CgroupLimits, ParsedCgroup};
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CgroupIdentity {
    pub daemon: [u8; 32],
    pub container: [u8; 32],
    pub boot: [u8; 32],
    pub pid_namespace: [u8; 32],
    pub cgroup_namespace: [u8; 32],
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ObservationInterval {
    pub start_ns: u64,
    pub end_ns: u64,
}
impl ObservationInterval {
    pub fn new(start_ns: u64, end_ns: u64) -> Result<Self, CgroupError> {
        if start_ns > end_ns {
            return Err(CgroupError::Interval);
        }
        Ok(Self { start_ns, end_ns })
    }
}

/// Each slice represents one complete read of the named pre-opened file.
#[derive(Clone, Copy)]
pub struct SyntheticCgroupFiles<'a> {
    pub memory_max: &'a [u8],
    pub memory_swap_max: &'a [u8],
    pub memory_events: &'a [u8],
    pub memory_events_local: &'a [u8],
    pub memory_current: &'a [u8],
    pub memory_peak: &'a [u8],
    pub memory_oom_group: &'a [u8],
    pub pids_max: &'a [u8],
    pub pids_current: &'a [u8],
    pub pids_events: &'a [u8],
    pub cgroup_procs: &'a [u8],
    pub cgroup_events: &'a [u8],
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SyntheticCgroupObservation {
    pub(crate) identity: CgroupIdentity,
    pub(crate) interval: ObservationInterval,
    pub(crate) memory_events: MemoryEvents,
    pub(crate) memory_events_local: MemoryEvents,
    pub(crate) memory_current: u64,
    pub(crate) memory_peak: u64,
    pub(crate) memory_oom_group: bool,
    pub(crate) pids_max_events: u64,
    pub(crate) members: Vec<u32>,
}
impl SyntheticCgroupObservation {
    pub fn identity(&self) -> &CgroupIdentity {
        &self.identity
    }
    pub fn interval(&self) -> ObservationInterval {
        self.interval
    }
    pub fn memory_events(&self) -> MemoryEvents {
        self.memory_events
    }
    pub fn memory_events_local(&self) -> MemoryEvents {
        self.memory_events_local
    }
    pub fn memory_current(&self) -> u64 {
        self.memory_current
    }
    pub fn memory_peak(&self) -> u64 {
        self.memory_peak
    }
    pub fn memory_oom_group(&self) -> bool {
        self.memory_oom_group
    }
    pub fn pids_max_events(&self) -> u64 {
        self.pids_max_events
    }
    pub fn members(&self) -> &[u32] {
        &self.members
    }
    pub fn parse(
        identity: CgroupIdentity,
        interval: ObservationInterval,
        files: SyntheticCgroupFiles<'_>,
        stage: CgroupStage,
    ) -> Result<Self, CgroupError> {
        ObservationInterval::new(interval.start_ns, interval.end_ns)?;
        let parsed = ParsedCgroup::parse(
            radishaxiom_solver_supervision_core::cgroup::CgroupFiles {
                memory_max: files.memory_max,
                memory_swap_max: files.memory_swap_max,
                memory_events: files.memory_events,
                memory_events_local: files.memory_events_local,
                memory_current: files.memory_current,
                memory_peak: files.memory_peak,
                memory_oom_group: files.memory_oom_group,
                pids_max: files.pids_max,
                pids_current: files.pids_current,
                pids_events: files.pids_events,
                cgroup_procs: files.cgroup_procs,
                cgroup_events: files.cgroup_events,
            },
            stage,
            process_cgroup_limits(),
        )?;
        Ok(Self {
            identity,
            interval,
            memory_events: parsed.memory_events,
            memory_events_local: parsed.memory_events_local,
            memory_current: parsed.memory_current,
            memory_peak: parsed.memory_peak,
            memory_oom_group: parsed.memory_oom_group,
            pids_max_events: parsed.pids_max_events,
            members: parsed.members,
        })
    }
    pub fn check_follows(&self, before: &Self) -> Result<(), CgroupError> {
        if self.identity != before.identity {
            return Err(CgroupError::Identity);
        }
        if self.memory_oom_group != before.memory_oom_group {
            return Err(CgroupError::Configuration);
        }
        if self.interval.start_ns < before.interval.end_ns {
            return Err(CgroupError::Interval);
        }
        if !self.memory_events.follows(before.memory_events)
            || !self.memory_events_local.follows(before.memory_events_local)
            || self.pids_max_events < before.pids_max_events
            || self.memory_peak < before.memory_peak
        {
            return Err(CgroupError::CounterRollback);
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OomAttribution {
    NoObservedKillIncrement,
    CauseUnresolved,
    LocalMemoryAssociatedNotExclusive,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DeadlineOrdering {
    BeforeDeadline,
    AtOrAfterDeadline,
    OrderUnresolved,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SyntheticOomFacts {
    pub possible_event_interval: ObservationInterval,
    pub local_max_delta: u64,
    pub local_oom_delta: u64,
    pub local_kill_delta: u64,
    pub hierarchical_kill_delta: u64,
    pub attribution: OomAttribution,
    pub ordering: DeadlineOrdering,
}
/// A child exit 137 / SIGKILL alone never supplies a missing cgroup observation.
pub fn observe_oom(
    before: &SyntheticCgroupObservation,
    after: &SyntheticCgroupObservation,
    child_killed: bool,
    deadline_ns: u64,
) -> Result<SyntheticOomFacts, CgroupError> {
    after.check_follows(before)?;
    let a = after.memory_events_local;
    let b = before.memory_events_local;
    let local_max_delta = a.max - b.max;
    let local_oom_delta = a.oom - b.oom;
    let local_kill_delta = a.oom_kill - b.oom_kill;
    let hierarchical_kill_delta = after.memory_events.oom_kill - before.memory_events.oom_kill;
    let possible_event_interval = ObservationInterval {
        start_ns: before.interval.start_ns,
        end_ns: after.interval.end_ns,
    };
    let ordering = if possible_event_interval.end_ns < deadline_ns {
        DeadlineOrdering::BeforeDeadline
    } else if possible_event_interval.start_ns >= deadline_ns {
        DeadlineOrdering::AtOrAfterDeadline
    } else {
        DeadlineOrdering::OrderUnresolved
    };
    let attribution = if local_kill_delta == 0 && hierarchical_kill_delta == 0 {
        OomAttribution::NoObservedKillIncrement
    } else if child_killed && local_max_delta > 0 && local_oom_delta > 0 && local_kill_delta > 0 {
        OomAttribution::LocalMemoryAssociatedNotExclusive
    } else {
        OomAttribution::CauseUnresolved
    };
    Ok(SyntheticOomFacts {
        possible_event_interval,
        local_max_delta,
        local_oom_delta,
        local_kill_delta,
        hierarchical_kill_delta,
        attribution,
        ordering,
    })
}
