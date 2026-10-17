//! Internal bootstrap-control-v0.1 bytes. Parsing establishes syntax and bounds,
//! never provenance, runtime qualification, or permission to execute anything.
#![forbid(unsafe_code)]

pub const BOOTSTRAP_HEADER_BYTES: usize = 24;
pub const BOOTSTRAP_BINDING_BYTES: usize = 160;
pub const BOOTSTRAP_PAYLOAD_LIMIT: usize = 65_536;
pub const BOOTSTRAP_CHUNK_LIMIT: usize = BOOTSTRAP_PAYLOAD_LIMIT - BOOTSTRAP_BINDING_BYTES;
pub const BOOTSTRAP_CONTROL_LIMIT: usize = 65_536;
/// Conservative fixed split: both directions together cannot exceed 65,536.
pub const BOOTSTRAP_DIRECTION_CONTROL_LIMIT: usize = BOOTSTRAP_CONTROL_LIMIT / 2;
pub const BOOTSTRAP_PENDING_LIMIT: usize = 131_072;
pub const BOOTSTRAP_QUERY_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stdin_bytes;
pub const BOOTSTRAP_STDOUT_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stdout_bytes;
pub const BOOTSTRAP_STDERR_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stderr_bytes;
const MAGIC: &[u8; 4] = b"RAXB";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Direction {
    MacToSupervisor = 1,
    SupervisorToMac = 2,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BootstrapBinding {
    pub attempt: [u8; 32],
    pub request: [u8; 32],
    pub policy: [u8; 32],
    pub image: [u8; 32],
    /// Synthetic in offline simulations. Bytes alone do not prove randomness.
    pub nonce: [u8; 32],
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Ready {
    pub linux_ready_ns: u64,
    pub preparation_deadline_ns: u64,
    pub boot_digest: [u8; 32],
    pub namespace_digest: [u8; 32],
    pub configuration_digest: [u8; 32],
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Arm {
    pub deadline_ns: u64,
    pub query_len: u32,
    pub query_digest: [u8; 32],
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ChildExit {
    Exited(u8),
    Signaled(u8),
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Final {
    pub child_reaped: bool,
    pub only_supervisor: bool,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FailureReason {
    Protocol = 1,
    Deadline = 2,
    ControlLost = 3,
    OutputLimit = 4,
    Policy = 5,
    Resource = 6,
    Loader = 7,
    Child = 8,
    Observation = 9,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum BootstrapMessage {
    Ready(Ready),
    Arm(Arm),
    QueryChunk(Vec<u8>),
    QueryEnd,
    StdoutChunk(Vec<u8>),
    StdoutEof,
    StderrChunk(Vec<u8>),
    StderrEof,
    ChildExit(ChildExit),
    Final(Final),
    Failure(FailureReason),
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BootstrapFrame {
    pub binding: BootstrapBinding,
    pub message: BootstrapMessage,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum WireError {
    Magic,
    Version,
    Direction,
    Binding,
    UnknownKind(u8),
    Reserved,
    Sequence { expected: u64, actual: u64 },
    PayloadLength,
    NonCanonical,
    Duplicate,
    AfterEof,
    AfterTerminal,
    Limit(&'static str),
    CounterOverflow,
    Truncated,
    ControlEof,
    Stopped,
    Backpressure,
    ConsumeBeyondPending,
}
pub type WireResult<T> = Result<T, WireError>;

impl BootstrapMessage {
    fn kind(&self) -> u8 {
        match self {
            Self::Ready(_) => 1,
            Self::Arm(_) => 2,
            Self::QueryChunk(_) => 3,
            Self::QueryEnd => 4,
            Self::StdoutChunk(_) => 5,
            Self::StdoutEof => 6,
            Self::StderrChunk(_) => 7,
            Self::StderrEof => 8,
            Self::ChildExit(_) => 9,
            Self::Final(_) => 10,
            Self::Failure(_) => 11,
        }
    }
    fn body_len(&self) -> usize {
        match self {
            Self::Ready(_) => 112,
            Self::Arm(_) => 44,
            Self::QueryChunk(v) | Self::StdoutChunk(v) | Self::StderrChunk(v) => v.len(),
            Self::QueryEnd | Self::StdoutEof | Self::StderrEof => 0,
            Self::ChildExit(_) | Self::Final(_) => 2,
            Self::Failure(_) => 1,
        }
    }
}
fn direction_for(kind: u8) -> WireResult<Direction> {
    match kind {
        2..=4 => Ok(Direction::MacToSupervisor),
        1 | 5..=11 => Ok(Direction::SupervisorToMac),
        v => Err(WireError::UnknownKind(v)),
    }
}
fn chunk_kind(kind: u8) -> bool {
    matches!(kind, 3 | 5 | 7)
}
fn validate_length(kind: u8, payload_len: usize) -> WireResult<()> {
    if !(BOOTSTRAP_BINDING_BYTES..=BOOTSTRAP_PAYLOAD_LIMIT).contains(&payload_len) {
        return Err(WireError::PayloadLength);
    }
    let body = payload_len - BOOTSTRAP_BINDING_BYTES;
    let valid = match kind {
        1 => body == 112,
        2 => body == 44,
        3 | 5 | 7 => body > 0,
        4 | 6 | 8 => body == 0,
        9 | 10 => body == 2,
        11 => body == 1,
        v => return Err(WireError::UnknownKind(v)),
    };
    if valid {
        Ok(())
    } else {
        Err(WireError::PayloadLength)
    }
}
fn add(total: usize, count: usize, max: usize, name: &'static str) -> WireResult<usize> {
    total
        .checked_add(count)
        .filter(|v| *v <= max)
        .ok_or(WireError::Limit(name))
}

#[derive(Clone, Debug, Default)]
struct WireState {
    sequence: u64,
    control: usize,
    query: usize,
    stdout: usize,
    stderr: usize,
    singletons: u16,
    query_eof: bool,
    stdout_eof: bool,
    stderr_eof: bool,
    terminal: bool,
}
impl WireState {
    /// Called before copying any payload bytes, including for partial frames.
    fn header(
        &mut self,
        kind: u8,
        payload: usize,
        direction: Direction,
        sequence: u64,
    ) -> WireResult<()> {
        if self.terminal {
            return Err(WireError::AfterTerminal);
        }
        if direction_for(kind)? != direction {
            return Err(WireError::Direction);
        }
        if self.sequence != sequence {
            return Err(WireError::Sequence {
                expected: self.sequence,
                actual: sequence,
            });
        }
        validate_length(kind, payload)?;
        self.sequence = self
            .sequence
            .checked_add(1)
            .ok_or(WireError::CounterOverflow)?;
        let data = if chunk_kind(kind) {
            payload - BOOTSTRAP_BINDING_BYTES
        } else {
            0
        };
        self.control = add(
            self.control,
            BOOTSTRAP_HEADER_BYTES + payload - data,
            BOOTSTRAP_DIRECTION_CONTROL_LIMIT,
            "control",
        )?;
        match kind {
            3 => {
                if self.query_eof {
                    return Err(WireError::AfterEof);
                }
                self.query = add(self.query, data, BOOTSTRAP_QUERY_LIMIT, "query")?;
            }
            5 => {
                if self.stdout_eof {
                    return Err(WireError::AfterEof);
                }
                self.stdout = add(self.stdout, data, BOOTSTRAP_STDOUT_LIMIT, "stdout")?;
            }
            7 => {
                if self.stderr_eof {
                    return Err(WireError::AfterEof);
                }
                self.stderr = add(self.stderr, data, BOOTSTRAP_STDERR_LIMIT, "stderr")?;
            }
            _ => {
                let bit = 1u16 << kind;
                if self.singletons & bit != 0 {
                    return Err(WireError::Duplicate);
                }
                self.singletons |= bit;
                match kind {
                    4 => self.query_eof = true,
                    6 => self.stdout_eof = true,
                    8 => self.stderr_eof = true,
                    10 | 11 => self.terminal = true,
                    _ => {}
                }
            }
        }
        Ok(())
    }
}

/// One-frame incremental poll: unconsumed input remains owned by the caller.
/// No input-sized queue or list of decoded frames exists.
#[derive(Clone, Debug)]
pub struct BootstrapDecoder {
    direction: Direction,
    expected_binding: Option<BootstrapBinding>,
    state: WireState,
    header: [u8; BOOTSTRAP_HEADER_BYTES],
    header_bytes: usize,
    payload: Vec<u8>,
    payload_len: usize,
    kind: u8,
    stopped: bool,
    poisoned: bool,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DecodeStep {
    pub consumed: usize,
    pub frame: Option<BootstrapFrame>,
}
impl BootstrapDecoder {
    /// Syntax-only decoding for fixtures; this does not bind an attempt.
    pub fn new(direction: Direction) -> Self {
        Self {
            direction,
            expected_binding: None,
            state: WireState::default(),
            header: [0; BOOTSTRAP_HEADER_BYTES],
            header_bytes: 0,
            payload: Vec::new(),
            payload_len: 0,
            kind: 0,
            stopped: false,
            poisoned: false,
        }
    }
    /// Bind all five fixed fields before accepting any body bytes. This checks
    /// equality with caller-selected bytes, not their authenticity or origin.
    pub fn new_bound(direction: Direction, expected_binding: BootstrapBinding) -> Self {
        let mut decoder = Self::new(direction);
        decoder.expected_binding = Some(expected_binding);
        decoder
    }
    pub fn is_poisoned(&self) -> bool {
        self.poisoned
    }
    pub fn buffered_bytes(&self) -> usize {
        self.header_bytes + self.payload.len()
    }
    pub fn control_bytes(&self) -> usize {
        self.state.control
    }
    pub fn poll(&mut self, bytes: &[u8]) -> WireResult<DecodeStep> {
        if self.stopped {
            return Err(WireError::Stopped);
        }
        let result = self.consume(bytes);
        if result.is_err() {
            self.stopped = true;
            self.poisoned = true;
        }
        result
    }
    fn consume(&mut self, bytes: &[u8]) -> WireResult<DecodeStep> {
        if self.state.terminal && self.header_bytes == 0 {
            return Err(WireError::AfterTerminal);
        }
        let mut consumed = 0;
        if self.header_bytes < BOOTSTRAP_HEADER_BYTES {
            let count = (BOOTSTRAP_HEADER_BYTES - self.header_bytes).min(bytes.len());
            self.header[self.header_bytes..self.header_bytes + count]
                .copy_from_slice(&bytes[..count]);
            self.header_bytes += count;
            consumed += count;
            if self.header_bytes != BOOTSTRAP_HEADER_BYTES {
                return Ok(DecodeStep {
                    consumed,
                    frame: None,
                });
            }
            if &self.header[..4] != MAGIC {
                return Err(WireError::Magic);
            }
            if self.header[4..6] != [0, 1] {
                return Err(WireError::Version);
            }
            if self.header[6] != self.direction as u8 {
                return Err(WireError::Direction);
            }
            if self.header[8..12] != [0; 4] {
                return Err(WireError::Reserved);
            }
            self.kind = self.header[7];
            let seq = u64::from_be_bytes(self.header[12..20].try_into().expect("eight bytes"));
            let declared = u32::from_be_bytes(self.header[20..24].try_into().expect("four bytes"));
            self.payload_len = usize::try_from(declared).map_err(|_| WireError::PayloadLength)?;
            self.state
                .header(self.kind, self.payload_len, self.direction, seq)?;
            // All declared lengths and cumulative budgets were checked first.
            self.payload = Vec::with_capacity(self.payload_len);
        }
        if self.payload.len() < BOOTSTRAP_BINDING_BYTES {
            let count = (BOOTSTRAP_BINDING_BYTES - self.payload.len()).min(bytes.len() - consumed);
            self.payload
                .extend_from_slice(&bytes[consumed..consumed + count]);
            consumed += count;
            if self.payload.len() < BOOTSTRAP_BINDING_BYTES {
                return Ok(DecodeStep {
                    consumed,
                    frame: None,
                });
            }
            if let Some(expected) = &self.expected_binding {
                for (index, field) in [
                    &expected.attempt,
                    &expected.request,
                    &expected.policy,
                    &expected.image,
                    &expected.nonce,
                ]
                .into_iter()
                .enumerate()
                {
                    if self.payload[index * 32..(index + 1) * 32] != *field {
                        return Err(WireError::Binding);
                    }
                }
            }
        }
        let count = (self.payload_len - self.payload.len()).min(bytes.len() - consumed);
        self.payload
            .extend_from_slice(&bytes[consumed..consumed + count]);
        consumed += count;
        if self.payload.len() != self.payload_len {
            return Ok(DecodeStep {
                consumed,
                frame: None,
            });
        }
        let frame = decode_payload(self.kind, &self.payload)?;
        self.payload = Vec::new();
        self.header_bytes = 0;
        self.payload_len = 0;
        Ok(DecodeStep {
            consumed,
            frame: Some(frame),
        })
    }
    /// Physical control EOF is loss even at a frame boundary. Only a received
    /// explicit Final/Failure permits clean framing completion; the supervisor
    /// separately decides whether the entire attempt can finish successfully.
    pub fn end_of_input(&mut self) -> WireResult<()> {
        if self.stopped {
            return Err(WireError::Stopped);
        }
        self.stopped = true;
        let result = if self.header_bytes != 0 {
            Err(WireError::Truncated)
        } else if !self.state.terminal {
            Err(WireError::ControlEof)
        } else {
            Ok(())
        };
        if result.is_err() {
            self.poisoned = true;
        }
        result
    }
}

#[derive(Clone, Debug)]
pub struct BootstrapEncoder {
    direction: Direction,
    state: WireState,
    poisoned: bool,
}
impl BootstrapEncoder {
    pub fn new(direction: Direction) -> Self {
        Self {
            direction,
            state: WireState::default(),
            poisoned: false,
        }
    }
    pub fn is_poisoned(&self) -> bool {
        self.poisoned
    }
    pub fn encode(&mut self, frame: &BootstrapFrame) -> WireResult<Vec<u8>> {
        if self.poisoned {
            return Err(WireError::Stopped);
        }
        let result = self.encode_checked(frame);
        if result.is_err() {
            self.poisoned = true;
        }
        result
    }
    fn encode_checked(&mut self, frame: &BootstrapFrame) -> WireResult<Vec<u8>> {
        validate_message(&frame.message)?;
        let payload = BOOTSTRAP_BINDING_BYTES
            .checked_add(frame.message.body_len())
            .ok_or(WireError::CounterOverflow)?;
        let sequence = self.state.sequence;
        self.state
            .header(frame.message.kind(), payload, self.direction, sequence)?;
        let mut out = Vec::with_capacity(BOOTSTRAP_HEADER_BYTES + payload);
        out.extend_from_slice(MAGIC);
        out.extend_from_slice(&[0, 1, self.direction as u8, frame.message.kind()]);
        out.extend_from_slice(&[0; 4]);
        out.extend_from_slice(&sequence.to_be_bytes());
        out.extend_from_slice(&(payload as u32).to_be_bytes());
        for field in [
            &frame.binding.attempt,
            &frame.binding.request,
            &frame.binding.policy,
            &frame.binding.image,
            &frame.binding.nonce,
        ] {
            out.extend_from_slice(field);
        }
        match &frame.message {
            BootstrapMessage::Ready(v) => {
                out.extend_from_slice(&v.linux_ready_ns.to_be_bytes());
                out.extend_from_slice(&v.preparation_deadline_ns.to_be_bytes());
                out.extend_from_slice(&v.boot_digest);
                out.extend_from_slice(&v.namespace_digest);
                out.extend_from_slice(&v.configuration_digest);
            }
            BootstrapMessage::Arm(v) => {
                out.extend_from_slice(&v.deadline_ns.to_be_bytes());
                out.extend_from_slice(&v.query_len.to_be_bytes());
                out.extend_from_slice(&v.query_digest);
            }
            BootstrapMessage::QueryChunk(v)
            | BootstrapMessage::StdoutChunk(v)
            | BootstrapMessage::StderrChunk(v) => out.extend_from_slice(v),
            BootstrapMessage::ChildExit(ChildExit::Exited(v)) => out.extend_from_slice(&[0, *v]),
            BootstrapMessage::ChildExit(ChildExit::Signaled(v)) => out.extend_from_slice(&[1, *v]),
            BootstrapMessage::Final(_) => out.extend_from_slice(&[1, 1]),
            BootstrapMessage::Failure(v) => out.push(*v as u8),
            BootstrapMessage::QueryEnd
            | BootstrapMessage::StdoutEof
            | BootstrapMessage::StderrEof => {}
        }
        Ok(out)
    }
}

/// Bounded nonblocking write model: one encoded frame, no second enqueue until
/// drained. Only Backpressure is recoverable; every other error poisons writes.
#[derive(Clone, Debug)]
pub struct PendingFrameBuffer {
    encoder: BootstrapEncoder,
    bytes: Vec<u8>,
    consumed: usize,
    poisoned: bool,
}
impl PendingFrameBuffer {
    pub fn new(direction: Direction) -> Self {
        Self {
            encoder: BootstrapEncoder::new(direction),
            bytes: Vec::new(),
            consumed: 0,
            poisoned: false,
        }
    }
    pub fn is_poisoned(&self) -> bool {
        self.poisoned
    }
    fn poison(&mut self) {
        self.poisoned = true;
        self.bytes = Vec::new();
        self.consumed = 0;
    }
    pub fn push(&mut self, frame: &BootstrapFrame) -> WireResult<()> {
        if self.poisoned {
            return Err(WireError::Stopped);
        }
        let result = self.push_checked(frame);
        if result.is_err() && result != Err(WireError::Backpressure) {
            self.poison();
        }
        result
    }
    fn push_checked(&mut self, frame: &BootstrapFrame) -> WireResult<()> {
        if !self.remaining().is_empty() {
            return Err(WireError::Backpressure);
        }
        let payload = BOOTSTRAP_BINDING_BYTES
            .checked_add(frame.message.body_len())
            .ok_or(WireError::CounterOverflow)?;
        let total = BOOTSTRAP_HEADER_BYTES
            .checked_add(payload)
            .ok_or(WireError::CounterOverflow)?;
        if total > BOOTSTRAP_PENDING_LIMIT {
            return Err(WireError::Limit("pending"));
        }
        self.bytes = self.encoder.encode(frame)?;
        self.consumed = 0;
        Ok(())
    }
    pub fn remaining(&self) -> &[u8] {
        &self.bytes[self.consumed..]
    }
    pub fn consume(&mut self, count: usize) -> WireResult<()> {
        if self.poisoned {
            return Err(WireError::Stopped);
        }
        if count > self.remaining().len() {
            self.poison();
            return Err(WireError::ConsumeBeyondPending);
        }
        self.consumed += count;
        if self.consumed == self.bytes.len() {
            self.bytes = Vec::new();
            self.consumed = 0;
        }
        Ok(())
    }
}

fn validate_message(message: &BootstrapMessage) -> WireResult<()> {
    match message {
        BootstrapMessage::Ready(v) if v.linux_ready_ns >= v.preparation_deadline_ns => {
            Err(WireError::NonCanonical)
        }
        BootstrapMessage::Arm(v) if v.query_len as u64 > BOOTSTRAP_QUERY_LIMIT as u64 => {
            Err(WireError::Limit("query"))
        }
        BootstrapMessage::ChildExit(ChildExit::Signaled(v)) if !(1..=64).contains(v) => {
            Err(WireError::NonCanonical)
        }
        BootstrapMessage::Final(v) if !v.child_reaped || !v.only_supervisor => {
            Err(WireError::NonCanonical)
        }
        _ => Ok(()),
    }
}
fn digest(bytes: &[u8], offset: usize) -> [u8; 32] {
    bytes[offset..offset + 32]
        .try_into()
        .expect("validated fixed payload")
}
fn number(bytes: &[u8], offset: usize) -> u64 {
    u64::from_be_bytes(
        bytes[offset..offset + 8]
            .try_into()
            .expect("validated fixed payload"),
    )
}
fn decode_payload(kind: u8, payload: &[u8]) -> WireResult<BootstrapFrame> {
    let binding = BootstrapBinding {
        attempt: digest(payload, 0),
        request: digest(payload, 32),
        policy: digest(payload, 64),
        image: digest(payload, 96),
        nonce: digest(payload, 128),
    };
    let body = &payload[BOOTSTRAP_BINDING_BYTES..];
    let message = match kind {
        1 => BootstrapMessage::Ready(Ready {
            linux_ready_ns: number(body, 0),
            preparation_deadline_ns: number(body, 8),
            boot_digest: digest(body, 16),
            namespace_digest: digest(body, 48),
            configuration_digest: digest(body, 80),
        }),
        2 => BootstrapMessage::Arm(Arm {
            deadline_ns: number(body, 0),
            query_len: u32::from_be_bytes(body[8..12].try_into().expect("four bytes")),
            query_digest: digest(body, 12),
        }),
        3 => BootstrapMessage::QueryChunk(body.to_vec()),
        4 => BootstrapMessage::QueryEnd,
        5 => BootstrapMessage::StdoutChunk(body.to_vec()),
        6 => BootstrapMessage::StdoutEof,
        7 => BootstrapMessage::StderrChunk(body.to_vec()),
        8 => BootstrapMessage::StderrEof,
        9 => BootstrapMessage::ChildExit(match body[0] {
            0 => ChildExit::Exited(body[1]),
            1 => ChildExit::Signaled(body[1]),
            _ => return Err(WireError::NonCanonical),
        }),
        10 => {
            if body != [1, 1] {
                return Err(WireError::NonCanonical);
            }
            BootstrapMessage::Final(Final {
                child_reaped: true,
                only_supervisor: true,
            })
        }
        11 => BootstrapMessage::Failure(match body[0] {
            1 => FailureReason::Protocol,
            2 => FailureReason::Deadline,
            3 => FailureReason::ControlLost,
            4 => FailureReason::OutputLimit,
            5 => FailureReason::Policy,
            6 => FailureReason::Resource,
            7 => FailureReason::Loader,
            8 => FailureReason::Child,
            9 => FailureReason::Observation,
            _ => return Err(WireError::NonCanonical),
        }),
        v => return Err(WireError::UnknownKind(v)),
    };
    validate_message(&message)?;
    Ok(BootstrapFrame { binding, message })
}
