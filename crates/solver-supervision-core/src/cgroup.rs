//! Bounded cgroup v2 file-value rules; no identity, IO, or observation claims.
use std::collections::BTreeMap;
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CgroupLimits {
    pub memory_max: u64,
    pub swap_max: u64,
    pub pids_max: u64,
    pub file_bytes: usize,
}
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

/// Each slice represents one complete read of the named pre-opened file.
#[derive(Clone, Copy)]
pub struct CgroupFiles<'a> {
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
    pub fn follows(self, before: Self) -> bool {
        self.values()
            .iter()
            .zip(before.values())
            .all(|(a, b)| *a >= b)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ParsedCgroup {
    pub memory_events: MemoryEvents,
    pub memory_events_local: MemoryEvents,
    pub memory_current: u64,
    pub memory_peak: u64,
    pub memory_oom_group: bool,
    pub pids_max_events: u64,
    pub members: Vec<u32>,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CgroupStage {
    SupervisorOnly,
    SupervisorAndChild(u32),
    ReapedSupervisorOnly,
}

fn text(bytes: &[u8], limits: CgroupLimits) -> Result<&str, CgroupError> {
    if bytes.is_empty() || bytes.len() > limits.file_bytes {
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
fn scalar(bytes: &[u8], limits: CgroupLimits) -> Result<u64, CgroupError> {
    number(
        text(bytes, limits)?
            .strip_suffix('\n')
            .ok_or(CgroupError::Encoding)?,
    )
}
fn fields<'a>(
    bytes: &'a [u8],
    keys: &[&'static str],
    limits: CgroupLimits,
) -> Result<BTreeMap<&'a str, u64>, CgroupError> {
    let mut fields = BTreeMap::new();
    for line in text(bytes, limits)?.lines() {
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
fn parse_memory_events(bytes: &[u8], limits: CgroupLimits) -> Result<MemoryEvents, CgroupError> {
    let f = fields(
        bytes,
        &["low", "high", "max", "oom", "oom_kill", "oom_group_kill"],
        limits,
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
impl ParsedCgroup {
    pub fn parse(
        files: CgroupFiles<'_>,
        stage: CgroupStage,
        limits: CgroupLimits,
    ) -> Result<Self, CgroupError> {
        if scalar(files.memory_max, limits)? != limits.memory_max
            || scalar(files.memory_swap_max, limits)? != limits.swap_max
            || scalar(files.pids_max, limits)? != limits.pids_max
        {
            return Err(CgroupError::Configuration);
        }
        let memory_current = scalar(files.memory_current, limits)?;
        let memory_peak = scalar(files.memory_peak, limits)?;
        if memory_current > memory_peak {
            return Err(CgroupError::Configuration);
        }
        let memory_oom_group = match scalar(files.memory_oom_group, limits)? {
            0 => false,
            1 => true,
            _ => return Err(CgroupError::Configuration),
        };
        let events = fields(files.cgroup_events, &["populated", "frozen"], limits)?;
        if events["populated"] != 1 || events["frozen"] != 0 {
            return Err(CgroupError::Membership);
        }
        let mut members = Vec::with_capacity(2);
        for line in text(files.cgroup_procs, limits)?.lines() {
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
        if members != expected || scalar(files.pids_current, limits)? != members.len() as u64 {
            return Err(CgroupError::Membership);
        }
        let memory_events = parse_memory_events(files.memory_events, limits)?;
        let memory_events_local = parse_memory_events(files.memory_events_local, limits)?;
        if !memory_events.follows(memory_events_local) {
            return Err(CgroupError::Configuration);
        }
        Ok(Self {
            memory_events,
            memory_events_local,
            memory_current,
            memory_peak,
            memory_oom_group,
            pids_max_events: fields(files.pids_events, &["max"], limits)?["max"],
            members,
        })
    }
}
