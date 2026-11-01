//! One pending frame, explicit pipe ownership and nonblocking parent IO.
use crate::{
    abi::{O_NONBLOCK, PollFd},
    channel_init::{Budget, Cause, Report, close, receive_signal},
    channel_profile::{CHUNK_LIMIT, STDERR_LIMIT, STDOUT_LIMIT, TICK_NS},
    channel_report::{Binding, Encoder, Stream},
    fd::OwnedFd,
    syscall::{Error, Kernel, Linux, Result},
};
use radishaxiom_digest::Sha256;

struct Capture {
    fd: Option<OwnedFd>,
    seen: u64,
    exported: u32,
    hash: Sha256,
    eof: bool,
}
impl Capture {
    fn new() -> Self {
        Self {
            fd: None,
            seen: 0,
            exported: 0,
            hash: Sha256::new(),
            eof: false,
        }
    }
    fn stats(&self) -> Stream {
        Stream {
            seen: self.seen,
            exported: self.exported,
            digest: self.hash.clone().finalize(),
            prefix_only: self.seen != self.exported as u64 || !self.eof,
            eof: self.eof,
        }
    }
}
struct Pending {
    bytes: Vec<u8>,
    offset: usize,
    stream: u8,
    terminal: bool,
}
pub(super) struct Io {
    encoder: Encoder,
    pending: Option<Pending>,
    streams: [Capture; 2],
    child: [Option<OwnedFd>; 3],
    next: usize,
    pub capture_failed: bool,
    pub transport_failed: bool,
    dead: bool,
    ready: bool,
}
impl Io {
    pub fn new(binding: Binding) -> Self {
        Self {
            encoder: Encoder::new(binding),
            pending: None,
            streams: [Capture::new(), Capture::new()],
            child: [None, None, None],
            next: 0,
            capture_failed: false,
            transport_failed: false,
            dead: false,
            ready: false,
        }
    }
    pub fn prepare<K: Kernel>(&mut self, linux: &mut Linux<K>, report: &mut Report) -> Result<()> {
        // Borrow 0/1/2 for this process lifetime. Validate all before creating any
        // pipe, so sources cannot alias stdio even when an inherited role is shut.
        // External stdin is never read. It only has to occupy fd0 so a new
        // owned pipe cannot alias stdio; noninteractive runtimes may use /dev/null.
        linux.flags(0)?;
        for fd in [1, 2] {
            let flags = linux.flags(fd)?;
            if linux.fstat(fd)?.mode & 0xf000 != 0x1000 || flags & 3 != 1 {
                return Err(Error::invalid("channel-stdio-pipe"));
            }
        }
        for fd in [1, 2] {
            linux.set_nonblocking(fd, true)?;
        }
        let [read, write] = linux.pipe()?;
        self.child[0] = Some(read);
        close(linux, report, write); // EOF is established before any child exists.
        if report.cause.is_some() {
            return Err(Error::invalid("channel-stdin-close"));
        }
        for i in 0..2 {
            let [read, write] = linux.pipe()?;
            self.streams[i].fd = Some(read);
            self.child[i + 1] = Some(write);
            linux.set_nonblocking(self.streams[i].fd.as_ref().expect("owned read").raw(), true)?;
        }
        // A failing raw child can report its fixed 16 bytes without blocking.
        linux.set_nonblocking(self.child[2].as_ref().expect("owned stderr").raw(), true)?;
        for fd in self
            .child
            .iter()
            .flatten()
            .chain(self.streams.iter().filter_map(|s| s.fd.as_ref()))
        {
            if fd.raw() < 3 {
                return Err(Error::invalid("channel-pipe-role"));
            }
        }
        // Readback includes access modes, not merely the O_NONBLOCK bit.
        for s in &self.streams {
            if linux.flags(s.fd.as_ref().expect("owned read").raw())? & (O_NONBLOCK | 3)
                != O_NONBLOCK
            {
                return Err(Error::invalid("channel-read-flags"));
            }
        }
        self.pending = Some(Pending {
            bytes: self
                .encoder
                .start()
                .map_err(|_| Error::invalid("channel-start"))?,
            offset: 0,
            stream: 0,
            terminal: false,
        });
        self.ready = true;
        Ok(())
    }
    pub fn child_fds(&self) -> [i32; 3] {
        std::array::from_fn(|i| self.child[i].as_ref().expect("prepared child pipe").raw())
    }
    pub fn close_child<K: Kernel>(&mut self, linux: &mut Linux<K>, report: &mut Report) {
        for fd in &mut self.child {
            if let Some(fd) = fd.take() {
                close(linux, report, fd);
            }
        }
    }
    pub fn close_all<K: Kernel>(&mut self, linux: &mut Linux<K>, report: &mut Report) {
        self.close_child(linux, report);
        for stream in &mut self.streams {
            if let Some(fd) = stream.fd.take() {
                close(linux, report, fd);
            }
        }
    }
    pub fn finished(&self) -> bool {
        self.pending.is_none() && self.streams.iter().all(|s| s.fd.is_none())
    }
    pub fn stats(&self, i: usize) -> Stream {
        self.streams[i].stats()
    }
    pub fn can_finish(&self) -> bool {
        self.ready && !self.dead && self.pending.is_none()
    }
    fn flush<K: Kernel>(&mut self, linux: &mut Linux<K>, report: &mut Report) -> bool {
        if self.dead {
            return false;
        }
        let Some(p) = &mut self.pending else {
            return false;
        };
        match linux.write(1, &p.bytes[p.offset..]) {
            Ok(0) => {
                self.dead = true;
                self.transport_failed = true;
                report.fail(Cause::Transport);
                report.error(Error::returned("channel-write-zero"));
                true
            }
            Ok(n) => {
                p.offset += n;
                if p.offset == p.bytes.len() {
                    if p.stream != 0 {
                        let s = &mut self.streams[p.stream as usize - 1];
                        let bytes = &p.bytes[20..];
                        // Encoder has already checked the stricter <=1.5 MiB
                        // bound; only complete actually written chunks count.
                        s.hash.update(bytes).expect("bounded stream digest");
                        s.exported += bytes.len() as u32;
                    }
                    if !p.terminal {
                        self.pending = None;
                    }
                }
                false
            }
            Err(e) if e.errno() == Some(11) => false,
            Err(e) => {
                self.transport_failed = true;
                report.fail(Cause::Transport);
                report.error(e);
                // EINTR retains the same frame/offset for the cleanup phase.
                if e.errno() != Some(4) {
                    self.dead = true;
                }
                true
            }
        }
    }
    pub fn progress<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
        budget: &mut Budget,
        report: &mut Report,
        end: u64,
    ) {
        if !self.ready {
            return;
        }
        if let Err(e) = budget.remaining(linux, end) {
            report.error(e);
            return;
        }
        self.flush(linux, report);
        if self.pending.is_some() || self.dead {
            return;
        }
        // At most one read per stream per turn. A perpetually ready stream cannot
        // starve signals, clocks or the sole reaper; alternate the first stream.
        for _ in 0..2 {
            let i = self.next;
            self.next ^= 1;
            let Some(fd) = self.streams[i].fd.as_ref() else {
                continue;
            };
            if let Err(e) = budget.remaining(linux, end) {
                report.error(e);
                return;
            }
            let cap = if i == 0 { STDOUT_LIMIT } else { STDERR_LIMIT };
            let room = cap - self.streams[i].exported as usize;
            let mut bytes = [0; CHUNK_LIMIT];
            let count = bytes.len().min(room + 1);
            match linux.read(fd.raw(), &mut bytes[..count]) {
                Ok(0) => {
                    let s = &mut self.streams[i];
                    s.eof = true;
                    close(linux, report, s.fd.take().expect("owned read"));
                }
                Ok(n) => {
                    self.streams[i].seen += n as u64;
                    let keep = n.min(room);
                    if n > room {
                        self.capture_failed = true;
                        report.fail(Cause::Capture);
                        close(
                            linux,
                            report,
                            self.streams[i].fd.take().expect("owned read"),
                        );
                    }
                    if keep != 0 {
                        match self.encoder.chunk(i as u8 + 1, &bytes[..keep]) {
                            Ok(bytes) => {
                                self.pending = Some(Pending {
                                    bytes,
                                    offset: 0,
                                    stream: i as u8 + 1,
                                    terminal: false,
                                })
                            }
                            Err(_) => {
                                self.dead = true;
                                self.capture_failed = true;
                                report.fail(Cause::EventLimit);
                                report.error(Error::invalid("channel-chunk-budget"));
                            }
                        }
                    }
                    return;
                }
                Err(e) if e.errno() == Some(11) => {}
                Err(e) => {
                    self.capture_failed = true;
                    report.fail(Cause::Capture);
                    report.error(e);
                    if e.errno() != Some(4) {
                        close(
                            linux,
                            report,
                            self.streams[i].fd.take().expect("owned read"),
                        );
                    }
                }
            }
        }
    }
    pub fn wait<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
        report: &mut Report,
        left: u64,
    ) -> Result<()> {
        // A broken output descriptor can remain permanently poll-ready. Once
        // transport is dead, wait only for signals/time while reaping continues.
        if self.dead {
            return receive_signal(linux, report, left.min(TICK_NS));
        }
        let mut fds = [PollFd {
            fd: 1,
            events: 0,
            revents: 0,
        }; 3];
        let mut len = 1;
        if !self.dead {
            if self.pending.is_some() {
                fds[0].events = 4;
            } else {
                for s in &self.streams {
                    if let Some(fd) = &s.fd {
                        fds[len] = PollFd {
                            fd: fd.raw(),
                            events: 1,
                            revents: 0,
                        };
                        len += 1;
                    }
                }
            }
        }
        linux.poll(&mut fds[..len], left.min(TICK_NS))?;
        if fds[0].revents & (8 | 16 | 32) != 0 {
            self.dead = true;
            self.transport_failed = true;
            report.fail(Cause::Transport);
            return Err(Error::invalid("channel-output-poll-disconnect"));
        }
        if fds[1..len].iter().any(|fd| fd.revents & 32 != 0) {
            self.capture_failed = true;
            report.fail(Cause::Capture);
            return Err(Error::invalid("channel-capture-poll-invalid"));
        }
        Ok(()) // Data/HUP still requires a real read, including buffered bytes.
    }
    pub fn settle<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
        budget: &mut Budget,
        report: &mut Report,
    ) -> bool {
        // Finish a pre-existing frame at its real offset before freezing Final.
        // Pending capture bytes only become exported after this succeeds.
        while self.ready && self.pending.is_some() && !self.dead {
            if let Err(e) = budget.remaining(linux, budget.final_end) {
                report.error(e);
                return false;
            }
            if let Err(e) = receive_signal(linux, report, 0) {
                report.error(e);
                return false;
            }
            self.flush(linux, report);
            if self.pending.is_some()
                && !self.dead
                && let Err(e) = budget
                    .remaining(linux, budget.final_end)
                    .and_then(|left| self.wait(linux, report, left))
            {
                report.error(e);
                return false;
            }
        }
        self.can_finish()
    }
    pub fn finish<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
        budget: &mut Budget,
        report: &mut Report,
        value: &crate::channel_report::Final,
    ) -> bool {
        if !self.can_finish() {
            return false;
        }
        let Ok(bytes) = self.encoder.finish(value) else {
            report.error(Error::invalid("channel-final"));
            return false;
        };
        self.pending = Some(Pending {
            bytes,
            offset: 0,
            stream: 0,
            terminal: true,
        });
        let frozen_cause = report.cause;
        while self
            .pending
            .as_ref()
            .is_some_and(|p| p.offset < p.bytes.len())
            && !self.dead
        {
            if let Err(e) = receive_signal(linux, report, 0) {
                report.error(e);
                return false;
            }
            if report.cause != frozen_cause {
                return false;
            }
            if let Err(e) = budget.remaining(linux, budget.final_end) {
                report.error(e);
                return false;
            }
            // Once Final is frozen, any new write error makes it untrustworthy.
            if self.flush(linux, report) {
                return false;
            }
            if self
                .pending
                .as_ref()
                .is_some_and(|p| p.offset < p.bytes.len())
            {
                let result = budget
                    .remaining(linux, budget.final_end)
                    .and_then(|left| self.wait(linux, report, left));
                if let Err(e) = result {
                    report.error(e);
                    return false;
                }
            }
        }
        if let Err(e) = receive_signal(linux, report, 0) {
            report.error(e);
            return false;
        }
        !self.dead
            && report.cause == frozen_cause
            && self
                .pending
                .as_ref()
                .is_some_and(|p| p.offset == p.bytes.len())
            && match budget.remaining(linux, budget.final_end) {
                Ok(_) => true,
                Err(e) => {
                    report.error(e);
                    false
                }
            }
    }
}
