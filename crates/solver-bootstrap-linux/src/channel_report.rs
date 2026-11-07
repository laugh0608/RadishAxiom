//! Private observation-only framing. No IO, OS calls, acceptance or solver wire.
use crate::channel_json::{J, R, obj, parse, s};
use crate::channel_profile::*;
use radishaxiom_digest::Sha256;
const MAGIC: &[u8; 8] = b"AXCHN001";
fn yes(ok: bool) -> R<()> {
    if ok { Ok(()) } else { Err("report-invariant") }
}
fn hex(v: &[u8; 32]) -> String {
    v.iter().map(|b| format!("{b:02x}")).collect()
}
fn unhex(v: &str, prefix: bool) -> R<[u8; 32]> {
    let v = if prefix {
        v.strip_prefix("sha256:").ok_or("digest-prefix")?
    } else {
        v
    };
    yes(v.len() == 64
        && v.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)))?;
    let mut out = [0; 32];
    for (i, b) in out.iter_mut().enumerate() {
        *b = u8::from_str_radix(&v[i * 2..i * 2 + 2], 16).map_err(|_| "digest")?
    }
    Ok(out)
}
fn hash_j(v: &[u8; 32]) -> J {
    s(format!("sha256:{}", hex(v)))
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Binding {
    pub run_id: [u8; 32],
    pub input: [u8; 32],
    pub collector: [u8; 32],
}
impl Binding {
    fn json(&self) -> J {
        obj([
            ("run_id", s(hex(&self.run_id))),
            ("input_binding", hash_j(&self.input)),
            ("collector_digest", hash_j(&self.collector)),
        ])
    }
    fn from(j: &J) -> R<Self> {
        let a = j.fields(&["run_id", "input_binding", "collector_digest"])?;
        Ok(Self {
            run_id: unhex(a[0].1.text()?, false)?,
            input: unhex(a[1].1.text()?, true)?,
            collector: unhex(a[2].1.text()?, true)?,
        })
    }
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Fault {
    pub operation: String,
    pub kind: String,
    pub detail: u16,
}
impl Fault {
    fn json(&self) -> R<J> {
        yes(!self.operation.is_empty()
            && self.operation.len() <= 64
            && self
                .operation
                .bytes()
                .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-'))?;
        yes([
            "errno",
            "invalid-input",
            "invalid-return",
            "layout",
            "ownership",
        ]
        .contains(&self.kind.as_str()))?;
        yes(if self.kind == "errno" {
            (1..=4095).contains(&self.detail)
        } else {
            self.detail == 0
        })?;
        Ok(obj([
            ("operation", s(&self.operation)),
            ("kind", s(&self.kind)),
            ("detail", J::U(self.detail.into())),
        ]))
    }
    fn from(j: &J) -> R<Self> {
        let a = j.fields(&["operation", "kind", "detail"])?;
        let f = Self {
            operation: a[0].1.text()?.into(),
            kind: a[1].1.text()?.into(),
            detail: a[2].1.u()?.try_into().map_err(|_| "detail")?,
        };
        f.json()?;
        Ok(f)
    }
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Reason {
    Kernel(Fault),
    Deadline,
    Cancelled(u8),
    Signal(u8),
    Orphan,
    Budget,
    Capture,
    Transport,
}
fn reason_j(v: &Option<Reason>) -> R<J> {
    let Some(v) = v else { return Ok(J::N) };
    let (k, signal, error) = match v {
        Reason::Kernel(e) => ("kernel", J::N, e.json()?),
        Reason::Deadline => ("deadline", J::N, J::N),
        Reason::Cancelled(n) => {
            yes([1, 2, 3, 15].contains(n))?;
            ("cancelled", J::U((*n).into()), J::N)
        }
        Reason::Signal(n) => {
            yes((1..=64).contains(n) && ![9, 17, 19].contains(n))?;
            ("signal", J::U((*n).into()), J::N)
        }
        Reason::Orphan => ("orphan", J::N, J::N),
        Reason::Budget => ("budget", J::N, J::N),
        Reason::Capture => ("capture", J::N, J::N),
        Reason::Transport => ("transport", J::N, J::N),
    };
    Ok(obj([("kind", s(k)), ("signal", signal), ("error", error)]))
}
fn reason_from(j: &J) -> R<Option<Reason>> {
    if *j == J::N {
        return Ok(None);
    }
    let a = j.fields(&["kind", "signal", "error"])?;
    let v = match a[0].1.text()? {
        "kernel" => Reason::Kernel(Fault::from(&a[2].1)?),
        "deadline" => Reason::Deadline,
        "cancelled" => Reason::Cancelled(a[1].1.u()?.try_into().map_err(|_| "signal")?),
        "signal" => Reason::Signal(a[1].1.u()?.try_into().map_err(|_| "signal")?),
        "orphan" => Reason::Orphan,
        "budget" => Reason::Budget,
        "capture" => Reason::Capture,
        "transport" => Reason::Transport,
        _ => return Err("reason"),
    };
    yes(reason_j(&Some(v.clone()))? == *j)?;
    Ok(Some(v))
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Exit {
    pub pid: u32,
    pub uid: u32,
    pub code: u8,
    pub status: u8,
}
impl Exit {
    fn json(&self) -> R<J> {
        yes(self.pid > 1
            && self.pid <= i32::MAX as u32
            && (1..=3).contains(&self.code)
            && (self.code == 1 || (1..=64).contains(&self.status)))?;
        Ok(obj([
            ("pid", J::U(self.pid.into())),
            ("uid", J::U(self.uid.into())),
            ("code", J::U(self.code.into())),
            ("status", J::U(self.status.into())),
        ]))
    }
    fn from(j: &J) -> R<Self> {
        let a = j.fields(&["pid", "uid", "code", "status"])?;
        let e = Self {
            pid: a[0].1.u()?.try_into().map_err(|_| "pid")?,
            uid: a[1].1.u()?.try_into().map_err(|_| "uid")?,
            code: a[2].1.u()?.try_into().map_err(|_| "code")?,
            status: a[3].1.u()?.try_into().map_err(|_| "status")?,
        };
        e.json()?;
        Ok(e)
    }
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Signal {
    pub pid: u32,
    pub error: Option<Fault>,
}
impl Signal {
    fn json(&self) -> R<J> {
        yes(self.pid > 1 && self.pid <= i32::MAX as u32)?;
        Ok(obj([
            ("pid", J::U(self.pid.into())),
            (
                "error",
                match &self.error {
                    Some(f) => f.json()?,
                    None => J::N,
                },
            ),
        ]))
    }
    fn from(j: &J) -> R<Self> {
        let a = j.fields(&["pid", "error"])?;
        let v = Self {
            pid: a[0].1.u()?.try_into().map_err(|_| "pid")?,
            error: if a[1].1 == J::N {
                None
            } else {
                Some(Fault::from(&a[1].1)?)
            },
        };
        v.json()?;
        Ok(v)
    }
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Stream {
    pub seen: u64,
    pub exported: u32,
    pub digest: [u8; 32],
    pub prefix_only: bool,
    pub eof: bool,
}
impl Stream {
    fn json(&self) -> J {
        obj([
            ("seen_bytes", J::U(self.seen)),
            ("exported_bytes", J::U(self.exported.into())),
            ("sha256", hash_j(&self.digest)),
            ("prefix_only", J::B(self.prefix_only)),
            ("eof", J::B(self.eof)),
        ])
    }
    fn from(j: &J) -> R<Self> {
        let a = j.fields(&[
            "seen_bytes",
            "exported_bytes",
            "sha256",
            "prefix_only",
            "eof",
        ])?;
        Ok(Self {
            seen: a[0].1.u()?,
            exported: a[1].1.u()?.try_into().map_err(|_| "bytes")?,
            digest: unhex(a[2].1.text()?, true)?,
            prefix_only: a[3].1.b()?,
            eof: a[4].1.b()?,
        })
    }
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Final {
    pub binding: Binding,
    pub cause: Option<Reason>,
    pub child_pid: Option<u32>,
    pub main_exit: Option<Exit>,
    pub exits: Vec<Exit>,
    pub signals: Vec<Signal>,
    pub errors: Vec<Fault>,
    pub clone_attempted: bool,
    pub no_children: bool,
    pub overflowed: bool,
    pub stdout: Stream,
    pub stderr: Stream,
    pub first_ns: u64,
    pub last_ns: u64,
    pub capture_failed: bool,
    pub transport_failed: bool,
    pub selected_exit_code: u8,
}
impl Final {
    pub fn selected_code(&self) -> u8 {
        match &self.cause {
            Some(Reason::Deadline) => 124,
            Some(Reason::Cancelled(s)) if [1, 2, 3, 15].contains(s) => 128 + s,
            Some(_) => 125,
            None => {
                if !self.no_children
                    || !self.errors.is_empty()
                    || self.overflowed
                    || self.capture_failed
                    || self.transport_failed
                    || [&self.stdout, &self.stderr]
                        .iter()
                        .any(|s| s.prefix_only || !s.eof)
                {
                    125
                } else {
                    match self.main_exit {
                        Some(e) if e.code == 1 => e.status,
                        Some(e) if (2..=3).contains(&e.code) && (1..=64).contains(&e.status) => {
                            128 + e.status
                        }
                        Some(_) => 125,
                        None => 125,
                    }
                }
            }
        }
    }
    fn json(&self) -> R<J> {
        yes(self.exits.len() <= EVENT_LIMIT
            && self.signals.len() <= EVENT_LIMIT
            && self.errors.len() <= EVENT_LIMIT)?;
        yes(self.first_ns.checked_add(TOTAL_NS).is_some()
            && self.last_ns >= self.first_ns
            && self.last_ns < self.first_ns + TOTAL_NS)?;
        if let Some(pid) = self.child_pid {
            yes(self.clone_attempted && pid > 1 && pid <= i32::MAX as u32)?
        } else {
            yes(self.main_exit.is_none() && self.exits.is_empty() && self.signals.is_empty())?
        }
        if let Some(e) = self.main_exit {
            yes(Some(e.pid) == self.child_pid
                && self.exits.iter().find(|x| Some(x.pid) == self.child_pid) == Some(&e))?
        }
        if self.no_children && self.child_pid.is_some() {
            yes(self.main_exit.is_some() || (self.cause.is_some() && !self.errors.is_empty()))?
        }
        for stream in [&self.stdout, &self.stderr] {
            yes(stream.seen >= stream.exported as u64)?;
            if !stream.prefix_only {
                yes(stream.seen == stream.exported as u64)?
            }
        }
        if self.cause.is_none() {
            yes(self.exits.len() <= 1
                && self.exits.iter().all(|e| Some(e.pid) == self.child_pid)
                && self.signals.is_empty())?
        }
        yes(self.selected_exit_code == self.selected_code())?;
        Ok(obj([
            ("binding", self.binding.json()),
            ("cause", reason_j(&self.cause)?),
            ("child_pid", self.child_pid.map_or(J::N, |p| J::U(p.into()))),
            ("main_exit", self.main_exit.map_or(Ok(J::N), |e| e.json())?),
            (
                "exits",
                J::A(self.exits.iter().map(Exit::json).collect::<R<_>>()?),
            ),
            (
                "signals",
                J::A(self.signals.iter().map(Signal::json).collect::<R<_>>()?),
            ),
            (
                "errors",
                J::A(self.errors.iter().map(Fault::json).collect::<R<_>>()?),
            ),
            ("clone_attempted", J::B(self.clone_attempted)),
            ("no_children", J::B(self.no_children)),
            ("observations_overflowed", J::B(self.overflowed)),
            ("stdout", self.stdout.json()),
            ("stderr", self.stderr.json()),
            (
                "clock",
                obj([
                    ("first_ns", J::U(self.first_ns)),
                    ("work_ns", J::U(self.first_ns + WORK_NS)),
                    ("cleanup_ns", J::U(self.first_ns + CLEANUP_NS)),
                    ("final_ns", J::U(self.first_ns + TOTAL_NS)),
                    ("last_ns", J::U(self.last_ns)),
                ]),
            ),
            ("capture_failed", J::B(self.capture_failed)),
            ("transport_failed", J::B(self.transport_failed)),
            ("selected_exit_code", J::U(self.selected_exit_code.into())),
        ]))
    }
    fn from(j: &J) -> R<Self> {
        let a = j.fields(&[
            "binding",
            "cause",
            "child_pid",
            "main_exit",
            "exits",
            "signals",
            "errors",
            "clone_attempted",
            "no_children",
            "observations_overflowed",
            "stdout",
            "stderr",
            "clock",
            "capture_failed",
            "transport_failed",
            "selected_exit_code",
        ])?;
        let c = a[12]
            .1
            .fields(&["first_ns", "work_ns", "cleanup_ns", "final_ns", "last_ns"])?;
        let f = Self {
            binding: Binding::from(&a[0].1)?,
            cause: reason_from(&a[1].1)?,
            child_pid: if a[2].1 == J::N {
                None
            } else {
                Some(a[2].1.u()?.try_into().map_err(|_| "pid")?)
            },
            main_exit: if a[3].1 == J::N {
                None
            } else {
                Some(Exit::from(&a[3].1)?)
            },
            exits: a[4].1.array()?.iter().map(Exit::from).collect::<R<_>>()?,
            signals: a[5].1.array()?.iter().map(Signal::from).collect::<R<_>>()?,
            errors: a[6].1.array()?.iter().map(Fault::from).collect::<R<_>>()?,
            clone_attempted: a[7].1.b()?,
            no_children: a[8].1.b()?,
            overflowed: a[9].1.b()?,
            stdout: Stream::from(&a[10].1)?,
            stderr: Stream::from(&a[11].1)?,
            first_ns: c[0].1.u()?,
            last_ns: c[4].1.u()?,
            capture_failed: a[13].1.b()?,
            transport_failed: a[14].1.b()?,
            selected_exit_code: a[15].1.u()?.try_into().map_err(|_| "exit-code")?,
        };
        yes(f.json()? == *j)?;
        Ok(f)
    }
}
fn start(binding: &Binding) -> J {
    obj([
        ("format", s("radishaxiom-private-linux-channel-report")),
        ("version", s("0.1")),
        ("binding", binding.json()),
        ("profile", s(PROFILE)),
        ("budgets", budgets()),
    ])
}
struct State {
    binding: Binding,
    seq: u32,
    wire: usize,
    phase: u8,
    counts: [usize; 2],
    hashes: [Sha256; 2],
    final_value: Option<Final>,
}
impl State {
    fn new(binding: Binding) -> Self {
        Self {
            binding,
            seq: 0,
            wire: 0,
            phase: 0,
            counts: [0; 2],
            hashes: [Sha256::new(), Sha256::new()],
            final_value: None,
        }
    }
    fn accept(&mut self, seq: u32, kind: u8, stream: u8, payload: &[u8]) -> R<()> {
        yes(self.phase != 2 && seq == self.seq && (self.seq as usize) < FRAME_LIMIT)?;
        let total = self
            .wire
            .checked_add(20 + payload.len())
            .ok_or("wire-size")?;
        yes(total <= WIRE_LIMIT)?;
        match (kind, stream) {
            (1, 0) => {
                yes(self.phase == 0
                    && payload.len() <= START_LIMIT
                    && payload == start(&self.binding).bytes())?;
                self.phase = 1
            }
            (2, 1 | 2) => {
                yes(self.phase == 1
                    && !payload.is_empty()
                    && payload.len() <= CHUNK_LIMIT
                    && (self.seq as usize) < FRAME_LIMIT - 1)?;
                yes(total + 20 + FINAL_LIMIT <= WIRE_LIMIT)?;
                let i = stream as usize - 1;
                let count = self.counts[i] + payload.len();
                yes(count <= if i == 0 { STDOUT_LIMIT } else { STDERR_LIMIT })?;
                self.hashes[i].update(payload).map_err(|_| "digest-size")?;
                self.counts[i] = count
            }
            (3, 0) => {
                yes(self.phase == 1 && payload.len() <= FINAL_LIMIT)?;
                let f = Final::from(&parse(payload)?)?;
                yes(f.binding == self.binding)?;
                for (i, stats) in [&f.stdout, &f.stderr].iter().enumerate() {
                    yes(stats.exported as usize == self.counts[i]
                        && stats.digest == self.hashes[i].clone().finalize())?
                }
                self.final_value = Some(f);
                self.phase = 2
            }
            _ => return Err("frame-kind"),
        }
        self.wire = total;
        self.seq += 1;
        Ok(())
    }
}
pub struct Encoder {
    state: State,
    failed: bool,
}
impl Encoder {
    pub fn new(binding: Binding) -> Self {
        Self {
            state: State::new(binding),
            failed: false,
        }
    }
    fn frame(&mut self, kind: u8, stream: u8, payload: &[u8]) -> R<Vec<u8>> {
        if self.failed {
            return Err("terminal");
        };
        let seq = self.state.seq;
        if let Err(e) = self.state.accept(seq, kind, stream, payload) {
            self.failed = true;
            return Err(e);
        }
        let mut out = Vec::with_capacity(20 + payload.len());
        out.extend_from_slice(MAGIC);
        out.extend_from_slice(&seq.to_be_bytes());
        out.extend_from_slice(&[kind, stream, 0, 0]);
        out.extend_from_slice(&(payload.len() as u32).to_be_bytes());
        out.extend_from_slice(payload);
        Ok(out)
    }
    pub fn start(&mut self) -> R<Vec<u8>> {
        self.frame(1, 0, &start(&self.state.binding).bytes())
    }
    pub fn chunk(&mut self, stream: u8, bytes: &[u8]) -> R<Vec<u8>> {
        self.frame(2, stream, bytes)
    }
    pub fn finish(&mut self, final_value: &Final) -> R<Vec<u8>> {
        match final_value.json() {
            Ok(v) => self.frame(3, 0, &v.bytes()),
            Err(e) => {
                self.failed = true;
                Err(e)
            }
        }
    }
}
pub struct Decoder {
    state: State,
    buffer: Vec<u8>,
    expected: usize,
    failed: bool,
    received: usize,
}
impl Decoder {
    pub fn new(binding: Binding) -> Self {
        Self {
            state: State::new(binding),
            buffer: Vec::with_capacity(FINAL_LIMIT + 20),
            expected: 20,
            failed: false,
            received: 0,
        }
    }
    pub fn feed(&mut self, bytes: &[u8]) -> R<()> {
        if self.failed {
            return Err("terminal");
        };
        let result = self.push(bytes);
        if result.is_err() {
            self.failed = true
        }
        result
    }
    fn push(&mut self, bytes: &[u8]) -> R<()> {
        for &b in bytes {
            yes(self.state.phase != 2)?;
            self.received += 1;
            yes(self.received <= WIRE_LIMIT)?;
            self.buffer.push(b);
            if self.buffer.len() == 20 {
                let h = &self.buffer;
                yes(&h[..8] == MAGIC && h[14..16] == [0, 0])?;
                let size = u32::from_be_bytes(h[16..20].try_into().map_err(|_| "header")?) as usize;
                let cap = match (h[12], h[13]) {
                    (1, 0) => START_LIMIT,
                    (2, 1 | 2) => CHUNK_LIMIT,
                    (3, 0) => FINAL_LIMIT,
                    _ => return Err("frame-kind"),
                };
                yes(size > 0 && size <= cap)?;
                self.expected = 20 + size;
            }
            if self.buffer.len() == self.expected {
                let seq = u32::from_be_bytes(self.buffer[8..12].try_into().map_err(|_| "header")?);
                self.state
                    .accept(seq, self.buffer[12], self.buffer[13], &self.buffer[20..])?;
                self.buffer.clear();
                self.expected = 20;
            }
        }
        Ok(())
    }
    pub fn finish(self) -> R<Final> {
        yes(!self.failed && self.buffer.is_empty() && self.state.phase == 2)?;
        self.state.final_value.ok_or("missing-final")
    }
}
#[cfg(test)]
#[path = "channel_report_tests.rs"]
mod tests;
