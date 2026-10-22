//! Pure, bounded simulation captures. Docker CLI already separates stdout and
//! stderr; only synthetic Engine fixtures use the eight-byte frame decoder.

pub const STDOUT_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stdout_bytes;
pub const STDERR_LIMIT: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stderr_bytes;
pub const CONTROL_DIAGNOSTIC_LIMIT: usize = 65_536;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StreamKind {
    Stdout,
    Stderr,
}

impl StreamKind {
    pub fn limit(self) -> usize {
        match self {
            Self::Stdout => STDOUT_LIMIT,
            Self::Stderr => STDERR_LIMIT,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum TransportError {
    StreamLimit(StreamKind),
    Closed(StreamKind),
    CounterOverflow,
    UnknownStream(u8),
    ReservedHeader,
    FrameTooLarge { stream: StreamKind, declared: u32 },
    TruncatedFrame,
    DecoderStopped,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct StreamCapture {
    bytes: Vec<u8>,
    observed_bytes: u64,
    complete: bool,
    exceeded: bool,
}

impl StreamCapture {
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }
    /// Counts inspected bytes only: capture stops at the first over-limit byte.
    pub fn observed_bytes(&self) -> u64 {
        self.observed_bytes
    }
    pub fn complete(&self) -> bool {
        self.complete
    }
    pub fn exceeded(&self) -> bool {
        self.exceeded
    }
}

#[derive(Clone, Debug, Default)]
pub struct SeparatedStreams {
    stdout: StreamCapture,
    stderr: StreamCapture,
}

impl SeparatedStreams {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn stream(&self, kind: StreamKind) -> &StreamCapture {
        match kind {
            StreamKind::Stdout => &self.stdout,
            StreamKind::Stderr => &self.stderr,
        }
    }
    fn stream_mut(&mut self, kind: StreamKind) -> &mut StreamCapture {
        match kind {
            StreamKind::Stdout => &mut self.stdout,
            StreamKind::Stderr => &mut self.stderr,
        }
    }
    /// Receives bytes from an already separated simulated CLI stream. No header
    /// sniffing occurs, including when solver bytes resemble Engine headers.
    pub fn push(&mut self, kind: StreamKind, bytes: &[u8]) -> Result<(), TransportError> {
        let capture = self.stream_mut(kind);
        if capture.complete || capture.exceeded {
            return Err(TransportError::Closed(kind));
        }
        let remaining = kind.limit() - capture.bytes.len();
        let inspected = bytes.len().min(remaining + 1);
        capture.observed_bytes = capture
            .observed_bytes
            .checked_add(u64::try_from(inspected).map_err(|_| TransportError::CounterOverflow)?)
            .ok_or(TransportError::CounterOverflow)?;
        capture
            .bytes
            .extend_from_slice(&bytes[..bytes.len().min(remaining)]);
        if bytes.len() > remaining {
            capture.exceeded = true;
            return Err(TransportError::StreamLimit(kind));
        }
        Ok(())
    }
    pub fn eof(&mut self, kind: StreamKind) -> Result<(), TransportError> {
        let capture = self.stream_mut(kind);
        if capture.complete || capture.exceeded {
            return Err(TransportError::Closed(kind));
        }
        capture.complete = true;
        Ok(())
    }
}

/// Incremental Docker Engine format decoder for synthetic fixtures only. It
/// never allocates from a declared frame length and is not an Engine adapter.
#[derive(Clone, Debug, Default)]
pub struct SimulatedEngineFrames {
    streams: SeparatedStreams,
    header: [u8; 8],
    header_bytes: usize,
    payload: Option<(StreamKind, usize)>,
    stopped: bool,
}

impl SimulatedEngineFrames {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn streams(&self) -> &SeparatedStreams {
        &self.streams
    }
    pub fn push(&mut self, mut bytes: &[u8]) -> Result<(), TransportError> {
        if self.stopped {
            return Err(TransportError::DecoderStopped);
        }
        let result = self.consume(&mut bytes);
        if result.is_err() {
            self.stopped = true;
        }
        result
    }
    fn consume(&mut self, bytes: &mut &[u8]) -> Result<(), TransportError> {
        while !bytes.is_empty() {
            if let Some((kind, remaining)) = self.payload {
                let count = remaining.min(bytes.len());
                self.streams.push(kind, &bytes[..count])?;
                *bytes = &bytes[count..];
                self.payload = (remaining > count).then_some((kind, remaining - count));
                continue;
            }
            let count = (8 - self.header_bytes).min(bytes.len());
            self.header[self.header_bytes..self.header_bytes + count]
                .copy_from_slice(&bytes[..count]);
            *bytes = &bytes[count..];
            self.header_bytes += count;
            if self.header_bytes != 8 {
                continue;
            }
            let kind = match self.header[0] {
                1 => StreamKind::Stdout,
                2 => StreamKind::Stderr,
                other => return Err(TransportError::UnknownStream(other)),
            };
            if self.header[1..4] != [0, 0, 0] {
                return Err(TransportError::ReservedHeader);
            }
            let length = u32::from_be_bytes(self.header[4..8].try_into().expect("four bytes"));
            if u64::from(length) > kind.limit() as u64 {
                return Err(TransportError::FrameTooLarge {
                    stream: kind,
                    declared: length,
                });
            }
            self.header_bytes = 0;
            self.payload = (length != 0).then_some((kind, length as usize));
        }
        Ok(())
    }
    pub fn finish(&mut self) -> Result<(), TransportError> {
        if self.stopped {
            return Err(TransportError::DecoderStopped);
        }
        self.stopped = true;
        if self.header_bytes != 0 || self.payload.is_some() {
            return Err(TransportError::TruncatedFrame);
        }
        self.streams.eof(StreamKind::Stdout)?;
        self.streams.eof(StreamKind::Stderr)
    }
}
