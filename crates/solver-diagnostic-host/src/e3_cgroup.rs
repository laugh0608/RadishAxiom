//! Bounded synthetic cgroup v2 observations; no filesystem access or runtime qualification.

use std::collections::BTreeMap;

pub const CGROUP_MEMORY_MAX: u64 =
    radishaxiom_ir::solver::PROCESS_LIMITS.working_memory_bytes as u64;
pub const CGROUP_PIDS_MAX: u64 = 2;
pub const CGROUP_FILE_BYTES: usize = 4096;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CgroupError {
    Limit,
    Encoding,
    Number,
    Missing(&'static str),
    Duplicate,
    UnknownField,
    Identity,
    Interval,
    Configuration,
    Membership,
    CounterRollback,
}

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

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MemoryEvents {
    pub low: u64,
    pub high: u64,
    pub max: u64,
    pub oom: u64,
    pub oom_kill: u64,
    pub oom_group_kill: u64,
}
impl MemoryEvents {
    fn values(self) -> [u64; 6] {
        [
            self.low,
            self.high,
            self.max,
            self.oom,
            self.oom_kill,
            self.oom_group_kill,
        ]
    }
    fn follows(self, before: Self) -> bool {
        self.values()
            .iter()
            .zip(before.values())
            .all(|(a, b)| *a >= b)
    }
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
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CgroupStage {
    SupervisorOnly,
    SupervisorAndChild(u32),
    ReapedSupervisorOnly,
}

fn text(bytes: &[u8]) -> Result<&str, CgroupError> {
    if bytes.is_empty() || bytes.len() > CGROUP_FILE_BYTES {
        return Err(CgroupError::Limit);
    }
    if !bytes.is_ascii() || !bytes.ends_with(b"\n") || bytes.contains(&b'\r') {
        return Err(CgroupError::Encoding);
    }
    std::str::from_utf8(bytes).map_err(|_| CgroupError::Encoding)
}
fn number(s: &str) -> Result<u64, CgroupError> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return Err(CgroupError::Number);
    }
    // Fixed decimal input, with no signs, whitespace, max sentinel or overflow.
    s.bytes().try_fold(0_u64, |n, b| {
        n.checked_mul(10)
            .and_then(|n| n.checked_add(u64::from(b - b'0')))
            .ok_or(CgroupError::Number)
    })
}
fn scalar(bytes: &[u8]) -> Result<u64, CgroupError> {
    number(
        text(bytes)?
            .strip_suffix('\n')
            .ok_or(CgroupError::Encoding)?,
    )
}
fn fields<'a>(
    bytes: &'a [u8],
    keys: &[&'static str],
) -> Result<BTreeMap<&'a str, u64>, CgroupError> {
    let mut fields = BTreeMap::new();
    for line in text(bytes)?.lines() {
        let (key, value) = line.split_once(' ').ok_or(CgroupError::Encoding)?;
        if !keys.contains(&key) {
            return Err(CgroupError::UnknownField);
        }
        if fields.insert(key, number(value)?).is_some() {
            return Err(CgroupError::Duplicate);
        }
    }
    for key in keys {
        if !fields.contains_key(key) {
            return Err(CgroupError::Missing(key));
        }
    }
    Ok(fields)
}
fn parse_memory_events(bytes: &[u8]) -> Result<MemoryEvents, CgroupError> {
    let f = fields(
        bytes,
        &["low", "high", "max", "oom", "oom_kill", "oom_group_kill"],
    )?;
    Ok(MemoryEvents {
        low: f["low"],
        high: f["high"],
        max: f["max"],
        oom: f["oom"],
        oom_kill: f["oom_kill"],
        oom_group_kill: f["oom_group_kill"],
    })
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
        if scalar(files.memory_max)? != CGROUP_MEMORY_MAX
            || scalar(files.memory_swap_max)? != 0
            || scalar(files.pids_max)? != CGROUP_PIDS_MAX
        {
            return Err(CgroupError::Configuration);
        }
        let memory_current = scalar(files.memory_current)?;
        let memory_peak = scalar(files.memory_peak)?;
        if memory_current > memory_peak {
            return Err(CgroupError::Configuration);
        }
        let memory_oom_group = match scalar(files.memory_oom_group)? {
            0 => false,
            1 => true,
            _ => return Err(CgroupError::Configuration),
        };
        let events = fields(files.cgroup_events, &["populated", "frozen"])?;
        if events["populated"] != 1 || events["frozen"] != 0 {
            return Err(CgroupError::Membership);
        }
        let mut members = Vec::with_capacity(2);
        for line in text(files.cgroup_procs)?.lines() {
            if members.len() == 2 {
                return Err(CgroupError::Membership);
            }
            let pid = u32::try_from(number(line)?).map_err(|_| CgroupError::Number)?;
            if pid == 0 || members.contains(&pid) {
                return Err(CgroupError::Membership);
            }
            members.push(pid);
        }
        members.sort_unstable();
        let expected = match stage {
            CgroupStage::SupervisorOnly | CgroupStage::ReapedSupervisorOnly => vec![1],
            CgroupStage::SupervisorAndChild(pid) if pid > 1 => vec![1, pid],
            CgroupStage::SupervisorAndChild(_) => return Err(CgroupError::Membership),
        };
        if members != expected || scalar(files.pids_current)? != members.len() as u64 {
            return Err(CgroupError::Membership);
        }
        let memory_events = parse_memory_events(files.memory_events)?;
        let memory_events_local = parse_memory_events(files.memory_events_local)?;
        if !memory_events.follows(memory_events_local) {
            return Err(CgroupError::Configuration);
        }
        Ok(Self {
            identity,
            interval,
            memory_events,
            memory_events_local,
            memory_current,
            memory_peak,
            memory_oom_group,
            pids_max_events: fields(files.pids_events, &["max"])?["max"],
            members,
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
