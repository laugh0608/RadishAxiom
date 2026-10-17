//! E3 offline cBPF generation and interpretation. No filter installation API.
//! The semantic oracle deliberately does not consume the generator's rule list.

use crate::abi::*;

pub mod supervisor;
pub use supervisor::*;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BpfInstruction {
    pub code: u16,
    pub jt: u8,
    pub jf: u8,
    pub k: u32,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OfflinePolicy {
    instructions: Vec<BpfInstruction>,
}

impl OfflinePolicy {
    pub fn instructions(&self) -> &[BpfInstruction] {
        &self.instructions
    }

    /// Stable AArch64 LE encoding of sock_filter, eight bytes per instruction.
    /// This is an offline artifact, not a kernel-installed policy.
    pub fn bytes(&self) -> Vec<u8> {
        let mut out = Vec::with_capacity(self.instructions.len() * 8);
        for i in &self.instructions {
            out.extend_from_slice(&i.code.to_le_bytes());
            out.extend_from_slice(&[i.jt, i.jf]);
            out.extend_from_slice(&i.k.to_le_bytes());
        }
        out
    }

    pub fn digest(&self) -> String {
        crate::raw_digest(&self.bytes())
    }

    pub fn evaluate(&self, data: &SeccompData) -> Result<u32, PolicyError> {
        interpret_cbpf(&self.bytes(), &data.bytes())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PolicyError {
    ProgramSize,
    UnsupportedInstruction,
    InvalidLoad,
    InvalidJump,
    InvalidReturn,
    MissingReturn,
    DataSize,
}

/// Independent small interpreter for this project's closed cBPF subset.
/// It validates *every* instruction, including unreachable instructions.
pub fn interpret_cbpf(program: &[u8], data: &[u8]) -> Result<u32, PolicyError> {
    if data.len() != SECCOMP_DATA_SIZE {
        return Err(PolicyError::DataSize);
    }
    if program.is_empty() || !program.len().is_multiple_of(8) || program.len() / 8 > 4096 {
        return Err(PolicyError::ProgramSize);
    }
    let mut instructions = Vec::with_capacity(program.len() / 8);
    for (pc, bytes) in program.chunks_exact(8).enumerate() {
        let code = u16::from_le_bytes([bytes[0], bytes[1]]);
        let jt = bytes[2];
        let jf = bytes[3];
        let k = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        let count = program.len() / 8;
        match code {
            0x20 if jt == 0 && jf == 0 => {
                if k % 4 != 0 || k > 60 {
                    return Err(PolicyError::InvalidLoad);
                }
                if pc + 1 >= count {
                    return Err(PolicyError::MissingReturn);
                }
            }
            0x15 => {
                if pc + 1 + usize::from(jt) >= count || pc + 1 + usize::from(jf) >= count {
                    return Err(PolicyError::InvalidJump);
                }
            }
            0x05 if jt == 0 && jf == 0 => {
                if u64::try_from(pc).expect("bounded program") + 1 + u64::from(k) >= count as u64 {
                    return Err(PolicyError::InvalidJump);
                }
            }
            0x06 if jt == 0 && jf == 0 => {
                if ![
                    SECCOMP_RET_ALLOW,
                    SECCOMP_RET_KILL_PROCESS,
                    SECCOMP_RET_USER_NOTIF,
                ]
                .contains(&k)
                {
                    return Err(PolicyError::InvalidReturn);
                }
            }
            _ => return Err(PolicyError::UnsupportedInstruction),
        }
        instructions.push((code, jt, jf, k));
    }
    let mut accumulator = 0u32;
    let mut pc = 0;
    // Forward-only checked jumps make the instruction count an execution bound.
    for _ in 0..instructions.len() {
        let (code, jt, jf, k) = instructions[pc];
        match code {
            0x20 => {
                let off = k as usize;
                accumulator =
                    u32::from_le_bytes(data[off..off + 4].try_into().expect("validated load"));
                pc += 1;
            }
            0x15 => pc += 1 + usize::from(if accumulator == k { jt } else { jf }),
            0x05 => pc += 1 + k as usize,
            0x06 => return Ok(k),
            _ => unreachable!("validated instruction"),
        }
    }
    Err(PolicyError::MissingReturn)
}

pub(super) struct ArgCheck {
    pub index: usize,
    pub values: Vec<u64>,
}
pub(super) struct Rule {
    pub nr: i32,
    pub checks: Vec<ArgCheck>,
    pub action: u32,
}

fn rule(nr: i32, checks: &[(usize, &[u64])]) -> Rule {
    Rule {
        nr,
        checks: checks
            .iter()
            .map(|(index, values)| ArgCheck {
                index: *index,
                values: values.to_vec(),
            })
            .collect(),
        action: SECCOMP_RET_ALLOW,
    }
}

/// Complete candidate final B/W filter from the accepted policy table.
/// The B-only branches remain in bytes; separate FD lifecycle invariants close
/// those capabilities before untrusted W runs. No compatibility claim is made.
pub fn worker_policy() -> OfflinePolicy {
    let stdio: &[u64] = &[0, 1, 2];
    let mut rules = Vec::new();
    for nr in [NR_READ, NR_READV] {
        rules.push(rule(nr, &[(0, &[0])]));
    }
    for nr in [NR_WRITE, NR_WRITEV] {
        rules.push(rule(nr, &[(0, &[1, 2])]));
    }
    rules.push(rule(NR_CLOSE, &[(0, &[0, 1, 2, 3, 4, 5])]));
    rules.push(rule(NR_FSTAT, &[(0, stdio)]));
    rules.push(rule(NR_FCNTL, &[(0, stdio), (1, &[F_GETFL])]));
    rules.push(rule(NR_IOCTL, &[(0, stdio), (1, &[TCGETS])]));
    for nr in [
        NR_BRK,
        NR_MUNMAP,
        NR_RT_SIGRETURN,
        NR_SIGALTSTACK,
        NR_GETPID,
        NR_GETTID,
        NR_SCHED_YIELD,
        NR_SET_TID_ADDRESS,
        NR_EXIT,
        NR_EXIT_GROUP,
    ] {
        rules.push(rule(nr, &[]));
    }
    rules.push(rule(
        NR_MMAP,
        &[
            (2, &[0, 1, 2, 3]),
            (
                3,
                &[
                    MAP_PRIVATE | MAP_ANONYMOUS,
                    MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE,
                ],
            ),
            (4, &[u64::MAX]),
            (5, &[0]),
        ],
    ));
    rules.push(rule(NR_MPROTECT, &[(2, &[0, 1, 2, 3])]));
    rules.push(rule(NR_MREMAP, &[(3, &[0, MREMAP_MAYMOVE])]));
    rules.push(rule(NR_MADVISE, &[(2, &[4, 8])]));
    rules.push(rule(NR_RT_SIGACTION, &[(3, &[KERNEL_SIGSET_SIZE])]));
    rules.push(rule(
        NR_RT_SIGPROCMASK,
        &[(0, &[0, 1, 2]), (3, &[KERNEL_SIGSET_SIZE])],
    ));
    for nr in [NR_CLOCK_GETTIME, NR_CLOCK_GETRES] {
        rules.push(rule(nr, &[(0, &[1, 7, 2, 3])]));
    }
    rules.push(rule(NR_GETRUSAGE, &[(0, &[0, 1])]));
    rules.push(rule(NR_FUTEX, &[(1, &[128, 129, 137, 138])]));
    rules.push(rule(NR_SET_ROBUST_LIST, &[(1, &[ROBUST_LIST_HEAD_SIZE])]));
    rules.push(rule(
        NR_RSEQ,
        &[(1, &[RSEQ_SIZE]), (2, &[0, 1]), (3, &[RSEQ_SIG])],
    ));
    rules.push(rule(NR_PRLIMIT64, &[(0, &[0]), (1, &[9, 3, 2]), (2, &[0])]));
    rules.push(rule(NR_SENDMSG, &[(0, &[4]), (2, &[MSG_NOSIGNAL])]));
    let mut exec = rule(NR_EXECVEAT, &[(0, &[3]), (4, &[AT_EMPTY_PATH])]);
    exec.action = SECCOMP_RET_USER_NOTIF;
    rules.push(exec);
    compile_rules(rules)
}

/// Oracle expressed directly as raw-register predicates, independent of rules
/// and code generation. Pointers and deep arrays are left to the kernel/TCB.
pub fn semantic_worker_decision(data: &SeccompData) -> u32 {
    if data.arch != AUDIT_ARCH_AARCH64 {
        return SECCOMP_RET_KILL_PROCESS;
    }
    let a = data.args;
    let allow = match data.nr {
        NR_READ | NR_READV => a[0] == 0,
        NR_WRITE | NR_WRITEV => a[0] == 1 || a[0] == 2,
        NR_CLOSE => a[0] <= 5,
        NR_FSTAT => a[0] <= 2,
        NR_FCNTL => a[0] <= 2 && a[1] == 3,
        NR_IOCTL => a[0] <= 2 && a[1] == 0x5401,
        NR_BRK | NR_MUNMAP | NR_RT_SIGRETURN | NR_SIGALTSTACK | NR_GETPID | NR_GETTID
        | NR_SCHED_YIELD | NR_SET_TID_ADDRESS | NR_EXIT | NR_EXIT_GROUP => true,
        NR_MMAP => {
            a[2] & !3 == 0 && (a[3] == 0x22 || a[3] == 0x4022) && a[4] == u64::MAX && a[5] == 0
        }
        NR_MPROTECT => a[2] & !3 == 0,
        NR_MREMAP => a[3] <= 1,
        NR_MADVISE => a[2] == 4 || a[2] == 8,
        NR_RT_SIGACTION => a[3] == 8,
        NR_RT_SIGPROCMASK => a[0] <= 2 && a[3] == 8,
        NR_CLOCK_GETTIME | NR_CLOCK_GETRES => matches!(a[0], 1 | 2 | 3 | 7),
        NR_GETRUSAGE => matches!(a[0], 0 | 1),
        NR_FUTEX => matches!(a[1], 128 | 129 | 137 | 138),
        NR_SET_ROBUST_LIST => a[1] == 24,
        NR_RSEQ => a[1] == 32 && a[2] <= 1 && a[3] == 0xd428_bc00,
        NR_PRLIMIT64 => a[0] == 0 && matches!(a[1], 2 | 3 | 9) && a[2] == 0,
        NR_SENDMSG => a[0] == 4 && a[2] == 0x4000,
        NR_EXECVEAT if a[0] == 3 && a[4] == 0x1000 => return SECCOMP_RET_USER_NOTIF,
        _ => false,
    };
    if allow {
        SECCOMP_RET_ALLOW
    } else {
        SECCOMP_RET_KILL_PROCESS
    }
}

enum Asm {
    Load(u32),
    Equal(u32, usize, usize),
    Jump(usize),
    Return(u32),
    Label(usize),
}
struct Assembler {
    ops: Vec<Asm>,
    next_label: usize,
}
impl Assembler {
    fn label(&mut self) -> usize {
        let label = self.next_label;
        self.next_label += 1;
        label
    }
    fn bind(&mut self, label: usize) {
        self.ops.push(Asm::Label(label));
    }
    fn finish(self) -> OfflinePolicy {
        let mut labels = vec![0; self.next_label];
        let mut pc = 0usize;
        for op in &self.ops {
            if let Asm::Label(label) = op {
                labels[*label] = pc;
            } else {
                pc += if matches!(op, Asm::Equal(..)) { 3 } else { 1 };
            }
        }
        assert!(pc <= 4096, "internal fixed policy size");
        let mut instructions = Vec::with_capacity(pc);
        for op in self.ops {
            let pc = instructions.len();
            let jump = |target: usize, at: usize| BpfInstruction {
                code: 0x05,
                jt: 0,
                jf: 0,
                k: u32::try_from(labels[target].checked_sub(at + 1).expect("forward branch"))
                    .expect("bounded policy"),
            };
            match op {
                Asm::Load(k) => instructions.push(BpfInstruction {
                    code: 0x20,
                    jt: 0,
                    jf: 0,
                    k,
                }),
                Asm::Equal(k, yes, no) => {
                    instructions.push(BpfInstruction {
                        code: 0x15,
                        jt: 0,
                        jf: 1,
                        k,
                    });
                    instructions.push(jump(yes, pc + 1));
                    instructions.push(jump(no, pc + 2));
                }
                Asm::Jump(label) => instructions.push(jump(label, pc)),
                Asm::Return(k) => instructions.push(BpfInstruction {
                    code: 0x06,
                    jt: 0,
                    jf: 0,
                    k,
                }),
                Asm::Label(_) => (),
            }
        }
        OfflinePolicy { instructions }
    }
}

pub(super) fn compile_rules(rules: Vec<Rule>) -> OfflinePolicy {
    let mut asm = Assembler {
        ops: Vec::new(),
        next_label: 0,
    };
    let arch_ok = asm.label();
    let arch_bad = asm.label();
    asm.ops.push(Asm::Load(4));
    asm.ops
        .push(Asm::Equal(AUDIT_ARCH_AARCH64, arch_ok, arch_bad));
    asm.bind(arch_bad);
    asm.ops.push(Asm::Return(SECCOMP_RET_KILL_PROCESS));
    asm.bind(arch_ok);
    for rule in rules {
        let body = asm.label();
        let next_rule = asm.label();
        asm.ops.push(Asm::Load(0));
        asm.ops.push(Asm::Equal(rule.nr as u32, body, next_rule));
        asm.bind(body);
        for check in rule.checks {
            assert!(
                check.index < 6 && !check.values.is_empty(),
                "internal policy argument"
            );
            let passed = asm.label();
            for value in check.values {
                let low = asm.label();
                let next_value = asm.label();
                let offset = 16 + check.index as u32 * 8;
                asm.ops.push(Asm::Load(offset + 4));
                asm.ops
                    .push(Asm::Equal((value >> 32) as u32, low, next_value));
                asm.bind(low);
                asm.ops.push(Asm::Load(offset));
                asm.ops.push(Asm::Equal(value as u32, passed, next_value));
                asm.bind(next_value);
            }
            asm.ops.push(Asm::Jump(next_rule));
            asm.bind(passed);
        }
        asm.ops.push(Asm::Return(rule.action));
        asm.bind(next_rule);
    }
    asm.ops.push(Asm::Return(SECCOMP_RET_KILL_PROCESS));
    asm.finish()
}
