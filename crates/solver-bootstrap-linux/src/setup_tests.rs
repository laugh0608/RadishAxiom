//! Closed-world in-memory kernel for the complete prepare path. Every supported
//! call is explicitly implemented; unknown calls panic instead of using host IO.
use super::*;
use crate::{
    abi::*,
    configuration::tests::exported,
    syscall::{Call, ErrorKind},
};
use radishaxiom_solver_supervision_core::bootstrap_start::StartFields;
use std::{cell::RefCell, collections::BTreeMap, rc::Rc};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Fault {
    None,
    Deadline,
    CliDigest,
    Interpreter,
    Seals,
    ExtraFd,
    Nnp,
    Cleanup,
}
#[derive(Clone, Copy, Debug)]
enum Kind {
    Standard(u8),
    Timer,
    Inventory,
    CgroupRoot,
    Cgroup(usize),
    Data,
    Cli,
    Memfd,
    Pipe(u8, u64),
    Socket(u64),
}
#[derive(Debug)]
struct Object {
    kind: Kind,
    bytes: Vec<u8>,
    offset: usize,
    flags: u64,
    seals: u64,
}
#[derive(Clone, Debug)]
struct Entry {
    object: Rc<RefCell<Object>>,
    cloexec: bool,
}
struct SetupKernel {
    fds: BTreeMap<i32, Entry>,
    fault: Fault,
    clock: u64,
    serial: u64,
    closed: Vec<i32>,
    calls: Vec<Call>,
    cli: Vec<u8>,
    overwrites: Vec<i32>,
}
fn object(kind: Kind, bytes: Vec<u8>, flags: u64) -> Entry {
    Entry {
        object: Rc::new(RefCell::new(Object {
            kind,
            bytes,
            offset: 0,
            flags,
            seals: 0,
        })),
        cloexec: true,
    }
}
fn boot() -> Vec<u8> {
    b"synthetic-boot-id\n".to_vec()
}
fn mount() -> Vec<u8> {
    b"1 0 0:1 / /sys/fs/cgroup ro - cgroup2 cgroup ro\n".to_vec()
}
fn namespace(path: &str) -> Vec<u8> {
    match path {
        "/proc/self/ns/pid" => b"pid:[101]".to_vec(),
        "/proc/self/ns/cgroup" => b"cgroup:[102]".to_vec(),
        "/proc/self/ns/mnt" => b"mnt:[103]".to_vec(),
        "/proc/self/ns/net" => b"net:[104]".to_vec(),
        "/proc/self/ns/user" => b"user:[105]".to_vec(),
        _ => panic!("unlisted namespace path"),
    }
}
fn status() -> Vec<u8> {
    b"Pid:\t1\nTgid:\t1\nThreads:\t1\nUid:\t1000\t1000\t1000\t1000\nGid:\t1000\t1000\t1000\t1000\nNoNewPrivs:\t1\nCapInh:\t0000000000000000\nCapPrm:\t0000000000000000\nCapEff:\t0000000000000000\nCapBnd:\t0000000000000000\nCapAmb:\t0000000000000000\n".to_vec()
}
fn synthetic_elf(interpreter: bool) -> Vec<u8> {
    let mut bytes = vec![0; 120];
    bytes[..7].copy_from_slice(b"\x7fELF\x02\x01\x01");
    bytes[16..18].copy_from_slice(&2u16.to_le_bytes());
    bytes[18..20].copy_from_slice(&183u16.to_le_bytes());
    bytes[20..24].copy_from_slice(&1u32.to_le_bytes());
    bytes[24..32].copy_from_slice(&0x400000u64.to_le_bytes());
    bytes[32..40].copy_from_slice(&64u64.to_le_bytes());
    bytes[52..54].copy_from_slice(&64u16.to_le_bytes());
    bytes[54..56].copy_from_slice(&56u16.to_le_bytes());
    bytes[56..58].copy_from_slice(&1u16.to_le_bytes());
    bytes[64..68].copy_from_slice(&(if interpreter { 3u32 } else { 1 }).to_le_bytes());
    bytes[68..72].copy_from_slice(&5u32.to_le_bytes());
    bytes[80..88].copy_from_slice(&0x400000u64.to_le_bytes());
    bytes[96..104].copy_from_slice(&120u64.to_le_bytes());
    bytes[104..112].copy_from_slice(&120u64.to_le_bytes());
    bytes[112..120].copy_from_slice(&4096u64.to_le_bytes());
    bytes
}
fn cgroup_files() -> [Vec<u8>; 12] {
    let limits = exported().cgroup;
    [
        format!("{}\n", limits.memory_max).into_bytes(),
        b"0\n".to_vec(),
        b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n".to_vec(),
        b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n".to_vec(),
        b"512\n".to_vec(),
        b"1024\n".to_vec(),
        b"0\n".to_vec(),
        b"2\n".to_vec(),
        b"1\n".to_vec(),
        b"max 0\n".to_vec(),
        b"1\n".to_vec(),
        b"populated 1\nfrozen 0\n".to_vec(),
    ]
}
impl SetupKernel {
    fn new(fault: Fault) -> Self {
        let mut fds = BTreeMap::new();
        for raw in 0..3 {
            let mut fd = object(
                Kind::Standard(raw as u8),
                vec![],
                if raw == 0 { 0 } else { 1 },
            );
            fd.cloexec = false;
            fds.insert(raw, fd);
        }
        if fault == Fault::ExtraFd {
            fds.insert(55, object(Kind::Data, vec![], 0));
        }
        Self {
            fds,
            fault,
            clock: 0,
            serial: 0,
            closed: vec![],
            calls: vec![],
            cli: synthetic_elf(fault == Fault::Interpreter),
            overwrites: vec![],
        }
    }
    fn allocate(&mut self, entry: Entry) -> i32 {
        let raw = (0..64)
            .find(|raw| !self.fds.contains_key(raw))
            .expect("synthetic fd bound");
        self.fds.insert(raw, entry);
        raw
    }
    fn entry(&self, raw: u64) -> Entry {
        self.fds
            .get(&(raw as i32))
            .expect("scripted descriptor exists")
            .clone()
    }
    fn bytes_for_path(&self, path: &str) -> (Kind, Vec<u8>) {
        match path {
            "/proc/self/status" => (Kind::Data, status()),
            "/proc/sys/kernel/random/boot_id" => (Kind::Data, boot()),
            "/proc/self/cgroup" => (Kind::Data, b"0::/\n".to_vec()),
            "/proc/self/mountinfo" => (Kind::Data, mount()),
            "/proc/self/fd" => (Kind::Inventory, vec![]),
            "/sys/fs/cgroup" => (Kind::CgroupRoot, vec![]),
            "/fixed/cvc5" => (Kind::Cli, self.cli.clone()),
            _ => {
                let name = path
                    .strip_prefix("/sys/fs/cgroup/")
                    .expect("fixed path root");
                let index = CGROUP_NAMES
                    .iter()
                    .position(|s| *s == name)
                    .expect("fixed cgroup file");
                (Kind::Cgroup(index), cgroup_files()[index].clone())
            }
        }
    }
    fn stat(&self, raw: u64) -> Stat {
        let entry = self.entry(raw);
        let object = entry.object.borrow();
        let (mode, dev, ino) = match object.kind {
            Kind::Standard(n) => (0x1000, 1, 100 + n as u64),
            Kind::Timer => (0, 2, 1),
            Kind::Inventory => (0x4000, 3, 1),
            Kind::CgroupRoot => (0x4000, 4, 1),
            Kind::Cgroup(i) => (0x8000, 4, 100 + i as u64),
            Kind::Data => (0x8000, 3, 100),
            Kind::Cli => (0x8000 | 0o555, 5, 1),
            Kind::Memfd => (0x8000 | 0o700, 6, 1),
            Kind::Pipe(_, serial) => (0x1000, 7, serial),
            Kind::Socket(serial) => (0xc000, 8, serial),
        };
        Stat {
            mode,
            dev,
            ino,
            size: object.bytes.len() as i64,
            ..Stat::default()
        }
    }
    fn inventory(&self) -> Vec<u8> {
        let mut bytes = vec![];
        for raw in self.fds.keys() {
            let name = raw.to_string();
            let len = (19 + name.len() + 1 + 7) & !7;
            let start = bytes.len();
            bytes.resize(start + len, 0);
            bytes[start + 16..start + 18].copy_from_slice(&(len as u16).to_le_bytes());
            bytes[start + 18] = 8;
            bytes[start + 19..start + 19 + name.len()].copy_from_slice(name.as_bytes());
        }
        bytes
    }
    fn material(&self) -> Material {
        let mut hash = Sha256::new();
        for path in [
            "/proc/self/ns/pid",
            "/proc/self/ns/cgroup",
            "/proc/self/ns/mnt",
            "/proc/self/ns/net",
            "/proc/self/ns/user",
        ] {
            let bytes = namespace(path);
            hash.update(&(bytes.len() as u64).to_be_bytes()).unwrap();
            hash.update(&bytes).unwrap();
        }
        let mut cli_digest = digest(&self.cli);
        if self.fault == Fault::CliDigest {
            cli_digest[0] ^= 1;
        }
        Material {
            build: BuildMaterial {
                cli_path: c"/fixed/cvc5",
                cli_len: self.cli.len() as u64,
                cli_digest,
                uid: 1000,
                gid: 1000,
                policy_bundle: [3; 32],
                configuration: [6; 32],
                cli_acceptance: [5; 32],
            },
            instance: ExpectedLocalInstance {
                boot_digest: digest(&boot()),
                namespace_digest: hash.finalize(),
                mountinfo_digest: digest(&mount()),
            },
        }
    }
}
// SAFETY: this is an explicit, target-independent scripted model. Pointer
// accesses below use the exact nested buffer extents supplied by typed wrappers;
// no pointer escapes invocation, and no host process/file/socket API is called.
unsafe impl Kernel for SetupKernel {
    unsafe fn invoke(&mut self, call: Call) -> u64 {
        self.calls.push(call);
        match call.nr {
            NR_CLOCK_GETTIME => {
                self.clock += 1;
                let ns = if self.fault == Fault::Deadline && self.clock >= 2 {
                    6_000_000_001
                } else {
                    self.clock
                };
                // SAFETY: typed clock wrapper gives exclusive Timespec output.
                unsafe {
                    *(call.args[1] as *mut Timespec) = Timespec::from_ns(ns);
                }
                0
            }
            NR_CLOCK_GETRES => {
                // SAFETY: typed clock wrapper provides exclusive Timespec output.
                unsafe {
                    *(call.args[1] as *mut Timespec) = Timespec::from_ns(1);
                }
                0
            }
            NR_GETPID | NR_GETTID => 1,
            NR_GETPPID => 0,
            NR_PRCTL => {
                assert_eq!(call.args, [PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0, 0]);
                if self.fault == Fault::Nnp { 0 } else { 1 }
            }
            NR_TIMERFD_CREATE => {
                assert_eq!(&call.args[..2], &[CLOCK_BOOTTIME, O_CLOEXEC | O_NONBLOCK]);
                self.allocate(object(Kind::Timer, vec![], O_NONBLOCK)) as u64
            }
            NR_TIMERFD_SETTIME => {
                assert!(matches!(
                    self.entry(call.args[0]).object.borrow().kind,
                    Kind::Timer
                ));
                assert_eq!(call.args[1], 1);
                // SAFETY: timer wrapper holds a live initialized Itimer input.
                let timer = unsafe { &*(call.args[2] as *const Itimer) };
                assert_eq!(timer.interval, Timespec::default());
                assert_eq!(timer.value.ns(), Some(6_000_000_001));
                0
            }
            NR_FCNTL => {
                let fd = call.args[0] as i32;
                let Some(entry) = self.fds.get(&fd).cloned() else {
                    return 0u64.wrapping_sub(9);
                };
                match call.args[1] {
                    F_GETFD => entry.cloexec as u64,
                    F_GETFL => entry.object.borrow().flags,
                    F_SETFL => {
                        entry.object.borrow_mut().flags = call.args[2];
                        0
                    }
                    F_ADD_SEALS => {
                        assert!(matches!(entry.object.borrow().kind, Kind::Memfd));
                        assert_eq!(call.args[2], 15);
                        entry.object.borrow_mut().seals = 15;
                        0
                    }
                    F_GET_SEALS => {
                        if self.fault == Fault::Seals {
                            7
                        } else {
                            entry.object.borrow().seals
                        }
                    }
                    F_DUPFD_CLOEXEC => {
                        assert_eq!(call.args[2], 6);
                        let raw = (6..64).find(|raw| !self.fds.contains_key(raw)).unwrap();
                        let mut copy = entry;
                        copy.cloexec = true;
                        self.fds.insert(raw, copy);
                        raw as u64
                    }
                    _ => panic!("unlisted prepare fcntl"),
                }
            }
            NR_DUP3 => {
                let mut entry = self.entry(call.args[0]);
                entry.cloexec = call.args[2] == O_CLOEXEC;
                let target = call.args[1] as i32;
                if self.fds.insert(target, entry).is_some() {
                    self.overwrites.push(target);
                }
                target as u64
            }
            NR_CLOSE => {
                let fd = call.args[0] as i32;
                assert!(
                    self.fds.remove(&fd).is_some(),
                    "close of unowned synthetic fd {fd}"
                );
                self.closed.push(fd);
                if self.fault == Fault::Cleanup && fd == 13 {
                    0u64.wrapping_sub(5)
                } else {
                    0
                }
            }
            NR_FSTAT => {
                let stat = self.stat(call.args[0]);
                // SAFETY: typed fstat supplies an exclusive 128-byte Stat.
                unsafe {
                    *(call.args[1] as *mut Stat) = stat;
                }
                0
            }
            NR_FSTATFS => {
                let kind = self.entry(call.args[0]).object.borrow().kind;
                let fs = match kind {
                    Kind::CgroupRoot | Kind::Cgroup(_) => StatFs {
                        kind: 0x63677270,
                        fsid: [9, 10],
                        flags: 1,
                        ..StatFs::default()
                    },
                    Kind::Cli => StatFs {
                        kind: 0x73717368,
                        flags: 1,
                        ..StatFs::default()
                    },
                    _ => panic!("unlisted statfs"),
                };
                // SAFETY: typed fstatfs supplies an exclusive 120-byte StatFs.
                unsafe {
                    *(call.args[1] as *mut StatFs) = fs;
                }
                0
            }
            NR_OPENAT => {
                assert_eq!(call.args[0], (-100i64) as u64);
                assert_eq!(call.args[2], O_CLOEXEC | O_NOFOLLOW);
                // SAFETY: typed path wrapper supplies a live NUL-terminated CStr.
                let path = unsafe { CStr::from_ptr(call.args[1] as *const i8) }
                    .to_str()
                    .unwrap();
                let (kind, bytes) = self.bytes_for_path(path);
                self.allocate(object(kind, bytes, 0)) as u64
            }
            61 => {
                let entry = self.entry(call.args[0]);
                assert!(matches!(entry.object.borrow().kind, Kind::Inventory));
                let data = if entry.object.borrow().offset == 0 {
                    self.inventory()
                } else {
                    vec![]
                };
                entry.object.borrow_mut().offset = 1;
                assert!(data.len() <= call.args[2] as usize);
                // SAFETY: exclusive directory-output slice bounds this copy.
                unsafe {
                    core::ptr::copy_nonoverlapping(
                        data.as_ptr(),
                        call.args[1] as *mut u8,
                        data.len(),
                    );
                }
                data.len() as u64
            }
            NR_READLINKAT => {
                // SAFETY: typed path wrapper supplies a live NUL-terminated CStr.
                let path = unsafe { CStr::from_ptr(call.args[1] as *const i8) }
                    .to_str()
                    .unwrap();
                let data = namespace(path);
                assert!(data.len() <= call.args[3] as usize);
                // SAFETY: exclusive readlink output slice bounds this copy.
                unsafe {
                    core::ptr::copy_nonoverlapping(
                        data.as_ptr(),
                        call.args[2] as *mut u8,
                        data.len(),
                    );
                }
                data.len() as u64
            }
            NR_READ | NR_PREAD64 => {
                let entry = self.entry(call.args[0]);
                let mut object = entry.object.borrow_mut();
                assert!(matches!(
                    object.kind,
                    Kind::Data | Kind::Cli | Kind::Memfd | Kind::Cgroup(_)
                ));
                let offset = if call.nr == NR_PREAD64 {
                    call.args[3] as usize
                } else {
                    object.offset
                };
                let max = if call.nr == NR_PREAD64 {
                    call.args[2] as usize
                } else {
                    (call.args[2] as usize).min(17)
                };
                let count = object.bytes.len().saturating_sub(offset).min(max);
                if count > 0 {
                    // SAFETY: count is bounded by read/pread's exclusive output
                    // length and by the initialized object's remaining bytes.
                    unsafe {
                        core::ptr::copy_nonoverlapping(
                            object.bytes[offset..offset + count].as_ptr(),
                            call.args[1] as *mut u8,
                            count,
                        );
                    }
                }
                if call.nr == NR_READ {
                    object.offset += count;
                }
                count as u64
            }
            NR_WRITE => {
                let entry = self.entry(call.args[0]);
                let mut object = entry.object.borrow_mut();
                assert!(matches!(object.kind, Kind::Memfd));
                assert_eq!(object.seals, 0);
                let n = (call.args[2] as usize).min(7);
                // SAFETY: typed write supplies a live immutable input of at
                // least n bytes; this borrowed view is not retained by the model.
                let bytes = unsafe { core::slice::from_raw_parts(call.args[1] as *const u8, n) };
                let at = object.offset;
                let length = (at + n).max(object.bytes.len());
                object.bytes.resize(length, 0);
                object.bytes[at..at + n].copy_from_slice(bytes);
                object.offset += n;
                n as u64
            }
            NR_LSEEK => {
                assert_eq!(call.args[1..3], [0, SEEK_SET]);
                self.entry(call.args[0]).object.borrow_mut().offset = 0;
                0
            }
            NR_MEMFD_CREATE => {
                assert_eq!(call.args[1], 0x13);
                self.allocate(object(Kind::Memfd, vec![], 2)) as u64
            }
            NR_FTRUNCATE => {
                let entry = self.entry(call.args[0]);
                assert!(matches!(entry.object.borrow().kind, Kind::Memfd));
                assert_eq!(call.args[1], self.cli.len() as u64);
                self.entry(call.args[0])
                    .object
                    .borrow_mut()
                    .bytes
                    .resize(call.args[1] as usize, 0);
                0
            }
            NR_PIPE2 => {
                assert_eq!(call.args[1], O_CLOEXEC);
                self.serial += 1;
                let a = self.allocate(object(Kind::Pipe(0, self.serial), vec![], 0));
                let b = self.allocate(object(Kind::Pipe(1, self.serial), vec![], 1));
                let out = call.args[0] as *mut i32;
                // SAFETY: typed pipe2 supplies an exclusive two-i32 output.
                unsafe {
                    out.write(a);
                    out.add(1).write(b);
                }
                0
            }
            NR_SOCKETPAIR => {
                assert_eq!(&call.args[..3], &[1, 5 | O_CLOEXEC, 0]);
                self.serial += 1;
                let a = self.allocate(object(Kind::Socket(self.serial), vec![], 2));
                let b = self.allocate(object(Kind::Socket(self.serial), vec![], 2));
                let out = call.args[3] as *mut i32;
                // SAFETY: typed socketpair supplies exclusive two-i32 output.
                unsafe {
                    out.write(a);
                    out.add(1).write(b);
                }
                0
            }
            NR_GETRANDOM => {
                assert_eq!(call.args[2], 1);
                let n = (call.args[1] as usize).min(7);
                // SAFETY: n never exceeds getrandom's exclusive output slice.
                unsafe {
                    core::ptr::write_bytes(call.args[0] as *mut u8, 7, n);
                }
                n as u64
            }
            NR_SECCOMP => {
                assert_eq!(call.args[0], SECCOMP_GET_NOTIF_SIZES);
                let out = call.args[2] as *mut u8;
                let sizes = [80u16, 24, 64];
                for (i, n) in sizes.into_iter().enumerate() {
                    // SAFETY: query-sizes wrapper supplies six initialized
                    // exclusive bytes; i in 0..3 writes only its two-byte field.
                    unsafe {
                        core::ptr::copy_nonoverlapping(n.to_le_bytes().as_ptr(), out.add(i * 2), 2);
                    }
                }
                0
            }
            _ => panic!("unlisted prepare syscall {}", call.nr),
        }
    }
}
fn fixture(
    fault: Fault,
) -> (
    Linux<SetupKernel>,
    OfflineConfiguration,
    CommandInputs,
    Material,
    StartDescription,
) {
    let kernel = SetupKernel::new(fault);
    let material = kernel.material();
    let configuration = exported();
    let command = radishaxiom_solver_diagnostic_host::bootstrap_command::export_offline_command();
    let command = CommandInputs::parse(&command.command, digest(&command.command)).unwrap();
    let description = StartDescription::new(
        StartFields {
            attempt: [1; 32],
            request: [2; 32],
            query_bytes: 12,
            query_digest: digest(b"(check-sat)\n"),
            policy_bundle: [3; 32],
            image: [4; 32],
            cli_acceptance: [5; 32],
            configuration: [6; 32],
        },
        configuration.wire,
    )
    .unwrap();
    (
        Linux::new(kernel),
        configuration,
        command,
        material,
        description,
    )
}
fn primary(error: &SetupError) -> &SetupError {
    match error {
        SetupError::Preparation { primary, .. } | SetupError::Cleanup { primary, .. } => primary,
        _ => error,
    }
}
#[test]
fn complete_prepare_preserves_identity_fd_roles_copy_seals_and_blocking() {
    let (mut linux, configuration, command, material, description) = fixture(Fault::None);
    let mut prepared = prepare(&mut linux, configuration, command, material, description).unwrap();
    assert_eq!(
        (
            prepared.timer,
            prepared.stdin,
            prepared.stdout,
            prepared.stderr
        ),
        (13, 10, 11, 12)
    );
    assert_eq!(prepared.child_stdio, [40, 41, 42]);
    assert_eq!(prepared.child_socket, 43);
    assert_eq!(
        prepared.cgroup,
        [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]
    );
    assert_eq!(prepared.observations.reads.len(), 1);
    assert!(prepared.observations.reads[0].completed.iter().all(|v| *v));
    assert!(prepared.query.is_empty());
    assert!(linux.kernel.overwrites.is_empty());
    let memfd = linux.kernel.entry(prepared.elf as u64);
    assert_eq!(memfd.object.borrow().bytes, linux.kernel.cli);
    assert_eq!(memfd.object.borrow().seals, 15);
    for (parent, child) in [prepared.stdin, prepared.stdout, prepared.stderr]
        .into_iter()
        .zip(prepared.child_stdio)
    {
        assert_ne!(linux.flags(parent).unwrap() & O_NONBLOCK, 0);
        assert_eq!(linux.flags(child).unwrap() & O_NONBLOCK, 0);
    }
    prepared
        .frozen
        .as_mut()
        .unwrap()
        .close_parent_fds(&mut linux)
        .unwrap();
    assert!(prepared.resources.cleanup_all(&mut linux).is_empty());
    assert!(linux.kernel.fds.is_empty());
    assert!(
        !linux
            .kernel
            .calls
            .iter()
            .any(|call| matches!(call.nr, NR_CLONE3 | NR_EXECVEAT | NR_SENDMSG))
    );
}
#[test]
fn prepare_failures_close_all_acquired_owners_and_keep_primary_reason() {
    for fault in [
        Fault::Deadline,
        Fault::CliDigest,
        Fault::Interpreter,
        Fault::Seals,
        Fault::ExtraFd,
        Fault::Nnp,
    ] {
        let (mut linux, configuration, command, material, description) = fixture(fault);
        let error = prepare(&mut linux, configuration, command, material, description)
            .err()
            .unwrap();
        match fault {
            Fault::Deadline => assert!(matches!(primary(&error), SetupError::Deadline)),
            Fault::CliDigest => assert!(matches!(primary(&error), SetupError::Digest)),
            Fault::Interpreter => assert!(matches!(primary(&error), SetupError::Elf)),
            Fault::Seals => assert!(matches!(
                primary(&error),
                SetupError::System(Error {
                    operation: "seals-readback",
                    ..
                })
            )),
            Fault::ExtraFd => assert!(matches!(
                primary(&error),
                SetupError::Identity("descriptor inventory")
            )),
            Fault::Nnp => assert!(matches!(
                primary(&error),
                SetupError::System(Error {
                    operation: "no-new-privs-readback",
                    ..
                })
            )),
            _ => unreachable!(),
        }
        assert!(linux.kernel.overwrites.is_empty());
        let remaining = linux.kernel.fds.keys().copied().collect::<Vec<_>>();
        assert_eq!(
            remaining,
            if fault == Fault::ExtraFd {
                vec![55]
            } else {
                vec![]
            },
            "{fault:?}"
        );
        if let SetupError::Preparation { cleanup, .. } = error {
            assert!(cleanup.is_empty());
        } else {
            panic!("missing preparation failure context");
        }
    }
}
#[test]
fn prepare_cleanup_failure_retains_both_primary_and_close_errno() {
    let (mut linux, configuration, command, mut material, description) = fixture(Fault::Cleanup);
    material.build.cli_digest[0] ^= 1;
    let error = prepare(&mut linux, configuration, command, material, description)
        .err()
        .unwrap();
    assert!(matches!(primary(&error), SetupError::Digest));
    match error {
        SetupError::Preparation { cleanup, .. } => assert_eq!(
            cleanup.iter().map(|e| e.kind).collect::<Vec<_>>(),
            vec![ErrorKind::Errno(5)]
        ),
        _ => panic!("missing cleanup context"),
    }
    assert!(linux.kernel.fds.is_empty());
    assert_eq!(
        linux.kernel.closed.iter().filter(|fd| **fd == 13).count(),
        1
    );
}
