//! S0/S1 preparation. No public constructor supplies acceptance or an executable.
use crate::child::{FrozenChild, FrozenChildArguments};
use crate::observation::{CGROUP_NAMES, ChildFact, ObservationLog};
use crate::{
    abi,
    configuration::{CommandInputs, OfflineConfiguration},
    fd::OwnedFd,
    syscall::{Error, Kernel, Linux},
};
use radishaxiom_digest::{Sha256, digest};
use radishaxiom_solver_supervision_core::{
    bootstrap_start::StartDescription,
    handshake::{HandshakeWindow, LinuxInstant, LocalReadyDeclaration, SupervisorHandshake},
    wire::BootstrapBinding,
};
use std::ffi::{CStr, CString};

#[derive(Debug)]
pub(crate) enum SetupError {
    System(Error),
    Identity(&'static str),
    Deadline,
    ClockRollback,
    Bounds,
    Elf,
    Seals,
    Digest,
    Handshake(radishaxiom_solver_supervision_core::handshake::HandshakeError),
    Observation(crate::observation::ObservationError),
    Cleanup {
        primary: Box<SetupError>,
        errors: Vec<Error>,
    },
    Preparation {
        primary: Box<SetupError>,
        cleanup: Vec<Error>,
        observations: Box<ObservationLog>,
    },
}
impl From<Error> for SetupError {
    fn from(e: Error) -> Self {
        Self::System(e)
    }
}
/// Values from a future reviewed build record; no constructor establishes E0.
pub(crate) struct BuildMaterial {
    pub cli_path: &'static CStr,
    pub cli_len: u64,
    pub cli_digest: [u8; 32],
    pub uid: u32,
    pub gid: u32,
    pub policy_bundle: [u8; 32],
    pub configuration: [u8; 32],
    pub cli_acceptance: [u8; 32],
}
/// Dynamic instance declarations require a future trusted Mac/runtime readback.
/// E4 templates cannot supply mount IDs/namespace inodes for a new instance.
pub(crate) struct ExpectedLocalInstance {
    pub boot_digest: [u8; 32],
    pub namespace_digest: [u8; 32],
    pub mountinfo_digest: [u8; 32],
}
pub(crate) struct Material {
    pub build: BuildMaterial,
    pub instance: ExpectedLocalInstance,
}
pub(crate) struct Deadline {
    pub entry: u64,
    pub until: u64,
    last: u64,
}
impl Deadline {
    pub fn from_entry(entry: u64, window: u64) -> Result<Self, SetupError> {
        Ok(Self {
            entry,
            until: entry
                .checked_add(window)
                .filter(|n| *n > entry)
                .ok_or(SetupError::Bounds)?,
            last: entry,
        })
    }
    pub fn check<K: Kernel>(&mut self, linux: &mut Linux<K>) -> Result<u64, SetupError> {
        let now = linux.boottime_ns()?;
        if now < self.last {
            return Err(SetupError::ClockRollback);
        }
        self.last = now;
        if now >= self.until {
            return Err(SetupError::Deadline);
        }
        Ok(now)
    }
    pub fn narrow(&mut self, now: u64, deadline: u64) -> Result<(), SetupError> {
        if deadline > self.until || deadline <= now {
            return Err(SetupError::Deadline);
        }
        self.until = deadline;
        Ok(())
    }
}
/// All acquired setup descriptors stay in this table until close or transfer.
/// Close consumes once, including on an error; cleanup preserves the first error.
pub(crate) struct Resources {
    owned: Vec<OwnedFd>,
}
impl Resources {
    pub fn new() -> Self {
        Self {
            owned: Vec::with_capacity(48),
        }
    }
    pub fn add(&mut self, fd: OwnedFd) -> i32 {
        let raw = fd.raw();
        self.owned.push(fd);
        raw
    }
    pub fn take(&mut self, raw: i32) -> Result<OwnedFd, SetupError> {
        let i = self
            .owned
            .iter()
            .position(|f| f.raw() == raw)
            .ok_or(SetupError::Identity("fd ownership"))?;
        Ok(self.owned.swap_remove(i))
    }
    pub fn close<K: Kernel>(&mut self, linux: &mut Linux<K>, raw: i32) -> Result<(), SetupError> {
        linux.close(self.take(raw)?)?;
        Ok(())
    }
    pub fn move_to<K: Kernel>(
        &mut self,
        linux: &mut Linux<K>,
        raw: i32,
        target: i32,
    ) -> Result<i32, SetupError> {
        if raw == target {
            return Ok(raw);
        }
        if self.owned.iter().any(|f| f.raw() == target) {
            return Err(SetupError::Identity("occupied role"));
        }
        let moved = linux.duplicate(raw, target, true)?;
        self.add(moved);
        self.close(linux, raw)?;
        Ok(target)
    }
    pub fn cleanup_all<K: Kernel>(&mut self, linux: &mut Linux<K>) -> Vec<Error> {
        let mut errors = Vec::new();
        while let Some(fd) = self.owned.pop() {
            if let Err(e) = linux.close(fd) {
                errors.push(e);
            }
        }
        errors
    }
    pub fn cleanup<K: Kernel>(&mut self, linux: &mut Linux<K>) -> Option<Error> {
        let mut first = None;
        while let Some(fd) = self.owned.pop() {
            if let Err(e) = linux.close(fd) {
                first.get_or_insert(e);
            }
        }
        first
    }
    pub fn descriptors(&self) -> Vec<i32> {
        self.owned.iter().map(OwnedFd::raw).collect()
    }
}
pub(crate) struct Prepared {
    pub configuration: OfflineConfiguration,
    pub command: CommandInputs,
    pub material: Material,
    pub description: StartDescription,
    pub handshake: SupervisorHandshake,
    pub binding: BootstrapBinding,
    pub deadline: Deadline,
    pub resources: Resources,
    pub timer: i32,
    pub cgroup: [i32; 12],
    pub stdin: i32,
    pub stdout: i32,
    pub stderr: i32,
    pub child_stdio: [i32; 3],
    pub socket: i32,
    pub child_socket: i32,
    pub elf: i32,
    pub observations: ObservationLog,
    pub query: Vec<u8>,
    pub frozen: Option<FrozenChild>,
    pub exec_grant: crate::supervisor::ExecGrant,
}
pub(crate) fn prepare<K: Kernel>(
    linux: &mut Linux<K>,
    configuration: OfflineConfiguration,
    command: CommandInputs,
    material: Material,
    description: StartDescription,
) -> Result<Prepared, SetupError> {
    // The first own observation establishes the absolute preparation deadline.
    let entry = linux.boottime_ns()?;
    let until = entry
        .checked_add(configuration.window_ns)
        .ok_or(SetupError::Bounds)?;
    let mut deadline = Deadline {
        entry,
        until,
        last: entry,
    };
    let mut resources = Resources::new();
    let mut observations = ObservationLog::new();
    let mut frozen = None;
    let result = (|| {
        let fd = resources.add(linux.timer()?);
        let timer = resources.move_to(linux, fd, 13)?;
        linux.arm_timer(timer, until)?;
        for fd in linux.take_standard()? {
            resources.add(fd);
        }
        verify_inventory(linux, &mut deadline, &[0, 1, 2, 13])?;
        identity(linux, &mut deadline, &material)?;
        let fields = description.fields();
        if fields.policy_bundle != material.build.policy_bundle
            || fields.configuration != material.build.configuration
            || fields.cli_acceptance != material.build.cli_acceptance
        {
            return Err(SetupError::Identity("build binding"));
        }
        let root = resources.add(linux.open_readonly(c"/sys/fs/cgroup")?);
        let root_stat = linux.fstat(root)?;
        let fs = linux.fstatfs(root)?;
        if root_stat.mode & 0xf000 != 0x4000 || fs.kind != 0x63677270 || fs.flags & 1 == 0 {
            return Err(SetupError::Identity("read-only cgroup2 root"));
        }
        let mut cgroup = [0; 12];
        let mut inodes = Vec::with_capacity(12);
        for (i, name) in CGROUP_NAMES.iter().enumerate() {
            deadline.check(linux)?;
            let path =
                CString::new(format!("/sys/fs/cgroup/{name}")).map_err(|_| SetupError::Bounds)?;
            let raw = resources.add(linux.open_readonly(&path)?);
            let stat = linux.fstat(raw)?;
            let filefs = linux.fstatfs(raw)?;
            if stat.dev != root_stat.dev
                || filefs.kind != fs.kind
                || filefs.fsid != fs.fsid
                || stat.mode & 0xf000 != 0x8000
                || linux.flags(raw)? & 3 != 0
                || inodes.contains(&stat.ino)
            {
                return Err(SetupError::Identity("cgroup file"));
            }
            inodes.push(stat.ino);
            cgroup[i] = resources.move_to(linux, raw, 20 + i as i32)?;
        }
        resources.close(linux, root)?;
        let cli = resources.add(linux.open_readonly(material.build.cli_path)?);
        let stat = linux.fstat(cli)?;
        let fs = linux.fstatfs(cli)?;
        if stat.mode & 0xf000 != 0x8000
            || stat.size < 64
            || stat.size as u64 != material.build.cli_len
            || stat.mode & 0o222 != 0
            || fs.flags & 1 == 0
        {
            return Err(SetupError::Identity("read-only CLI"));
        }
        let elf = resources.add(linux.memfd()?);
        linux.truncate(elf, material.build.cli_len)?;
        copy_cli(linux, &mut deadline, cli, elf, &material)?;
        resources.close(linux, cli)?;
        let mut s = [0; 3];
        let mut child = [0; 3];
        for i in 0..3 {
            let [read, write] = linux.pipe()?;
            let read = resources.add(read);
            let write = resources.add(write);
            let (parent, other) = if i == 0 { (write, read) } else { (read, write) };
            s[i] = resources.move_to(linux, parent, 10 + i as i32)?;
            child[i] = resources.move_to(linux, other, 40 + i as i32)?;
            linux.set_nonblocking(s[i], true)?;
            linux.set_nonblocking(child[i], false)?;
            if linux.flags(s[i])? & abi::O_NONBLOCK == 0
                || linux.flags(child[i])? & abi::O_NONBLOCK != 0
            {
                return Err(SetupError::Identity("pipe blocking"));
            }
        }
        let [parent, child_socket] = linux.socketpair()?;
        let parent = resources.add(parent);
        let child_socket = resources.add(child_socket);
        let child_socket = resources.move_to(linux, child_socket, 43)?;
        for fd in 0..=2 {
            linux.set_nonblocking(fd, true)?;
            if linux.flags(fd)? & abi::O_NONBLOCK == 0 {
                return Err(SetupError::Identity("control nonblocking"));
            }
        }
        let mut nonce = [0; 32];
        let mut used = 0;
        while used < nonce.len() {
            deadline.check(linux)?;
            let n = linux.random(&mut nonce[used..])?;
            if n == 0 || n > nonce.len() - used {
                return Err(SetupError::Bounds);
            }
            used += n;
        }
        linux.notification_sizes()?;
        let mut child_fact = ChildFact::Absent;
        if observations
            .capture(
                linux,
                &cgroup,
                configuration.cgroup,
                until,
                &mut child_fact,
                None,
            )
            .map_err(SetupError::Observation)?
            .is_none()
        {
            return Err(SetupError::Identity("initial cgroup transition"));
        }
        let binding = description.binding(nonce);
        let handshake = SupervisorHandshake::new(
            description.clone(),
            LinuxInstant::declared_ns(entry),
            LocalReadyDeclaration {
                boot_digest: material.instance.boot_digest,
                namespace_digest: material.instance.namespace_digest,
                configuration_digest: material.build.configuration,
                nonce,
            },
            HandshakeWindow {
                wall_clock_ns: configuration.window_ns,
            },
        )
        .map_err(SetupError::Handshake)?;
        let query = Vec::with_capacity(configuration.wire.query_bytes);
        let tokens = command
            .tokens
            .iter()
            .map(|s| {
                s.to_str()
                    .map(str::to_owned)
                    .map_err(|_| SetupError::Bounds)
            })
            .collect::<Result<Vec<_>, _>>()?;
        let arguments = FrozenChildArguments::from_bound_tokens(&tokens)?;
        let mut scratch = [0; 5];
        for (out, fd) in scratch
            .iter_mut()
            .zip([child[0], child[1], child[2], elf, child_socket])
        {
            *out = resources.add(linux.scratch_duplicate(fd)?);
        }
        let scratch = [
            resources.take(scratch[0])?,
            resources.take(scratch[1])?,
            resources.take(scratch[2])?,
            resources.take(scratch[3])?,
            resources.take(scratch[4])?,
        ];
        frozen = Some(FrozenChild::new(scratch, arguments, linux)?);

        deadline.check(linux)?;
        Ok((
            timer,
            cgroup,
            s,
            child,
            parent,
            child_socket,
            elf,
            binding,
            handshake,
            query,
        ))
    })();
    match result {
        Ok((
            timer,
            cgroup,
            s,
            child_stdio,
            socket,
            child_socket,
            elf,
            binding,
            handshake,
            query,
        )) => Ok(Prepared {
            configuration,
            command,
            material,
            description,
            handshake,
            binding,
            deadline,
            resources,
            timer,
            cgroup,
            stdin: s[0],
            stdout: s[1],
            stderr: s[2],
            child_stdio,
            socket,
            child_socket,
            elf,
            observations,
            query,
            frozen,
            exec_grant: crate::supervisor::ExecGrant::Awaiting,
        }),
        Err(e) => {
            let mut cleanup = Vec::new();
            if let Some(mut frozen) = frozen
                && let Err(error) = frozen.close_parent_fds(linux)
            {
                cleanup.push(error);
            }
            cleanup.extend(resources.cleanup_all(linux));
            Err(SetupError::Preparation {
                primary: Box::new(e),
                cleanup,
                observations: Box::new(observations),
            })
        }
    }
}

pub(crate) fn bounded_file<K: Kernel>(
    linux: &mut Linux<K>,
    deadline: &mut Deadline,
    path: &CStr,
    max: usize,
) -> Result<Vec<u8>, SetupError> {
    let fd = linux.open_readonly(path)?;
    let raw = fd.raw();
    let mut bytes = vec![0; max + 1];
    let result = (|| {
        let mut used = 0;
        loop {
            deadline.check(linux)?;
            let n = linux.read(raw, &mut bytes[used..])?;
            if n > bytes.len() - used {
                return Err(SetupError::Bounds);
            }
            used += n;
            deadline.check(linux)?;
            if used > max {
                return Err(SetupError::Bounds);
            }
            if n == 0 {
                bytes.truncate(used);
                return Ok(bytes);
            }
        }
    })();
    let close = linux.close(fd);
    match (result, close) {
        (Err(e), Err(close)) => Err(SetupError::Cleanup {
            primary: Box::new(e),
            errors: vec![close],
        }),
        (Err(e), Ok(())) => Err(e),
        (_, Err(e)) => Err(e.into()),
        (Ok(v), Ok(())) => Ok(v),
    }
}
fn identity<K: Kernel>(
    linux: &mut Linux<K>,
    deadline: &mut Deadline,
    m: &Material,
) -> Result<(), SetupError> {
    if linux.getpid()? != 1
        || linux.gettid()? != 1
        || linux.getppid()? != 0
        || linux.clock_resolution_ns()? == 0
    {
        return Err(SetupError::Identity("PID1/BOOTTIME"));
    }
    let status = bounded_file(linux, deadline, c"/proc/self/status", 16384)?;
    let text = std::str::from_utf8(&status).map_err(|_| SetupError::Identity("status encoding"))?;
    for (key, expected) in [
        ("Pid:", "1".to_owned()),
        ("Tgid:", "1".to_owned()),
        ("Threads:", "1".to_owned()),
        (
            "Uid:",
            format!(
                "{}\t{}\t{}\t{}",
                m.build.uid, m.build.uid, m.build.uid, m.build.uid
            ),
        ),
        (
            "Gid:",
            format!(
                "{}\t{}\t{}\t{}",
                m.build.gid, m.build.gid, m.build.gid, m.build.gid
            ),
        ),
        ("NoNewPrivs:", "1".to_owned()),
    ] {
        let mut lines = text.lines().filter_map(|s| s.strip_prefix(key));
        if lines.next().map(str::trim) != Some(expected.as_str()) || lines.next().is_some() {
            return Err(SetupError::Identity("PID/thread/UID/GID/NNP"));
        }
    }
    if m.build.uid == 0 || m.build.gid == 0 {
        return Err(SetupError::Identity("root identity"));
    }
    for key in ["CapInh:", "CapPrm:", "CapEff:", "CapBnd:", "CapAmb:"] {
        let value = text
            .lines()
            .find_map(|s| s.strip_prefix(key))
            .map(str::trim)
            .ok_or(SetupError::Identity("capabilities"))?;
        if value.len() != 16 || !value.bytes().all(|b| b == b'0') {
            return Err(SetupError::Identity("capabilities"));
        }
    }
    linux.check_no_new_privs()?;
    let boot = bounded_file(linux, deadline, c"/proc/sys/kernel/random/boot_id", 128)?;
    if digest(&boot) != m.instance.boot_digest {
        return Err(SetupError::Identity("boot"));
    }
    let mut hash = Sha256::new();
    let mut buffer = [0; 128];
    for path in [
        c"/proc/self/ns/pid",
        c"/proc/self/ns/cgroup",
        c"/proc/self/ns/mnt",
        c"/proc/self/ns/net",
        c"/proc/self/ns/user",
    ] {
        deadline.check(linux)?;
        let n = linux.readlink(path, &mut buffer)?;
        if n == 0 || n >= buffer.len() {
            return Err(SetupError::Identity("namespace"));
        }
        hash.update(&(n as u64).to_be_bytes())
            .map_err(|_| SetupError::Bounds)?;
        hash.update(&buffer[..n]).map_err(|_| SetupError::Bounds)?;
    }
    if hash.finalize() != m.instance.namespace_digest {
        return Err(SetupError::Identity("namespace binding"));
    }
    if bounded_file(linux, deadline, c"/proc/self/cgroup", 128)? != b"0::/\n" {
        return Err(SetupError::Identity("cgroup membership"));
    }
    if digest(&bounded_file(
        linux,
        deadline,
        c"/proc/self/mountinfo",
        65536,
    )?) != m.instance.mountinfo_digest
    {
        return Err(SetupError::Identity("mount sources"));
    }
    for fd in 0..=2 {
        if linux.fstat(fd)?.mode & 0xf000 != 0x1000
            || linux.flags(fd)? & 3 != if fd == 0 { 0 } else { 1 }
        {
            return Err(SetupError::Identity("inherited pipe"));
        }
    }
    Ok(())
}
fn copy_cli<K: Kernel>(
    linux: &mut Linux<K>,
    deadline: &mut Deadline,
    source: i32,
    target: i32,
    m: &Material,
) -> Result<(), SetupError> {
    let mut hash = Sha256::new();
    let mut bytes = [0u8; 16384];
    let mut total = 0u64;
    loop {
        deadline.check(linux)?;
        let remaining = m
            .build
            .cli_len
            .checked_sub(total)
            .ok_or(SetupError::Bounds)?;
        let request = (remaining.saturating_add(1)).min(bytes.len() as u64) as usize;
        let n = linux.read(source, &mut bytes[..request])?;
        if n > request {
            return Err(SetupError::Bounds);
        }
        deadline.check(linux)?;
        if n == 0 {
            break;
        }
        total = total.checked_add(n as u64).ok_or(SetupError::Bounds)?;
        if total > m.build.cli_len {
            return Err(SetupError::Bounds);
        }
        hash.update(&bytes[..n]).map_err(|_| SetupError::Bounds)?;
        let mut written = 0;
        while written < n {
            deadline.check(linux)?;
            let count = linux.write(target, &bytes[written..n])?;
            if count == 0 || count > n - written {
                return Err(SetupError::Bounds);
            }
            written += count;
            deadline.check(linux)?;
        }
    }
    if total != m.build.cli_len || hash.finalize() != m.build.cli_digest {
        return Err(SetupError::Digest);
    }
    validate_elf(linux, deadline, target, total)?;
    deadline.check(linux)?;
    linux.add_seals(target)?;
    deadline.check(linux)?;
    if linux.seals(target)? != abi::ALL_SEALS {
        return Err(SetupError::Seals);
    }
    Ok(())
}
fn validate_elf<K: Kernel>(
    linux: &mut Linux<K>,
    deadline: &mut Deadline,
    fd: i32,
    len: u64,
) -> Result<(), SetupError> {
    deadline.check(linux)?;
    let mut header = [0; 64];
    if linux.pread(fd, &mut header, 0)? != 64
        || &header[..4] != b"\x7fELF"
        || header[4..7] != [2, 1, 1]
        || u16::from_le_bytes([header[18], header[19]]) != 183
    {
        return Err(SetupError::Elf);
    }
    let u16at = |i| u16::from_le_bytes([header[i], header[i + 1]]);
    let u64at = |i| u64::from_le_bytes(header[i..i + 8].try_into().expect("ELF header width"));
    let phoff = u64at(32);
    let count = u16at(56) as u64;
    if ![2, 3].contains(&u16at(16))
        || u16at(52) != 64
        || u16at(54) != 56
        || count == 0
        || count > 128
        || phoff
            .checked_add(count * 56)
            .filter(|end| *end <= len)
            .is_none()
    {
        return Err(SetupError::Elf);
    }
    let mut executable = false;
    let mut entry_mapped = false;
    let entry = u64at(24);
    deadline.check(linux)?;
    for i in 0..count {
        deadline.check(linux)?;
        let mut ph = [0; 56];
        if linux.pread(fd, &mut ph, phoff + i * 56)? != 56 {
            return Err(SetupError::Elf);
        }
        deadline.check(linux)?;
        let kind = u32::from_le_bytes(ph[..4].try_into().expect("ELF field"));
        let flags = u32::from_le_bytes(ph[4..8].try_into().expect("ELF field"));
        let n = |i| u64::from_le_bytes(ph[i..i + 8].try_into().expect("ELF field"));
        if kind == 3 || kind == 2 || (kind == 0x6474e551 && flags & 1 != 0) {
            return Err(SetupError::Elf);
        }
        if kind == 1 {
            if n(8).checked_add(n(32)).filter(|end| *end <= len).is_none()
                || n(32) > n(40)
                || flags & 3 == 3
            {
                return Err(SetupError::Elf);
            }
            if flags & 1 != 0 {
                executable = true;
                entry_mapped |=
                    entry >= n(16) && n(16).checked_add(n(40)).is_some_and(|end| entry < end);
            }
        }
    }
    if !executable || !entry_mapped {
        return Err(SetupError::Elf);
    }
    Ok(())
}

/// Complete bounded procfs inventory; the directory's own FD is expected only
/// during this read and is always closed before returning.
pub(crate) fn verify_inventory<K: Kernel>(
    linux: &mut Linux<K>,
    deadline: &mut Deadline,
    expected: &[i32],
) -> Result<(), SetupError> {
    let fd = linux.open_fd_inventory()?;
    let raw = fd.raw();
    let result = (|| {
        let mut found = Vec::with_capacity(48);
        let mut buffer = [0u8; 4096];
        loop {
            deadline.check(linux)?;
            let n = linux.read_directory(raw, &mut buffer)?;
            if n == 0 {
                break;
            }
            let mut at = 0;
            while at < n {
                if n - at < 20 {
                    return Err(SetupError::Bounds);
                }
                let len = u16::from_le_bytes([buffer[at + 16], buffer[at + 17]]) as usize;
                if len < 20 || at + len > n {
                    return Err(SetupError::Bounds);
                }
                let name = &buffer[at + 19..at + len];
                let end = name
                    .iter()
                    .position(|b| *b == 0)
                    .ok_or(SetupError::Bounds)?;
                let name = &name[..end];
                if name != b"." && name != b".." {
                    let text = std::str::from_utf8(name).map_err(|_| SetupError::Bounds)?;
                    let item = text.parse::<i32>().map_err(|_| SetupError::Bounds)?;
                    if found.len() >= 48 || found.contains(&item) {
                        return Err(SetupError::Bounds);
                    }
                    found.push(item);
                }
                at += len;
            }
        }
        found.sort_unstable();
        let mut want = expected.to_vec();
        want.push(raw);
        want.sort_unstable();
        if found != want {
            return Err(SetupError::Identity("descriptor inventory"));
        }
        deadline.check(linux)?;
        Ok(())
    })();
    let close = linux.close(fd);
    match (result, close) {
        (Err(e), Err(close)) => Err(SetupError::Cleanup {
            primary: Box::new(e),
            errors: vec![close],
        }),
        (Err(e), Ok(())) => Err(e),
        (_, Err(e)) => Err(e.into()),
        (Ok(()), Ok(())) => Ok(()),
    }
}

#[cfg(test)]
#[path = "setup_tests.rs"]
mod tests;
