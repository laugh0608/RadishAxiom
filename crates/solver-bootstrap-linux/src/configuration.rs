//! Typed consumption of an explicit F1 export. This is an offline input, never
//! an E0/E4 acceptance token or a complete native build manifest.
use radishaxiom_digest::digest;
use radishaxiom_solver_supervision_core::{
    cgroup::CgroupLimits,
    policy::{BOOTSTRAP_SUPERVISOR_ROLES, OfflinePolicy, SupervisorRuntimePolicy, worker_policy},
    wire::{self, WireLimits},
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ConfigurationError {
    Encoding,
    Missing,
    Digest,
    Policy,
    Roles,
    Bounds,
}
#[derive(Clone, Copy)]
pub(crate) struct ExportDigests {
    pub manifest: [u8; 32],
    pub inputs: [u8; 32],
    pub worker: [u8; 32],
    pub supervisor: [u8; 32],
}
pub(crate) struct OfflineConfiguration {
    pub wire: WireLimits,
    pub cgroup: CgroupLimits,
    pub window_ns: u64,
    pub semantic_steps: u64,
    pub internal_wall_clock_ms: u64,
    pub worker: OfflinePolicy,
    pub supervisor: OfflinePolicy,
    pub export_digest: [u8; 32],
}
impl OfflineConfiguration {
    pub fn from_export(
        manifest: &[u8],
        inputs: &[u8],
        worker: &[u8],
        supervisor: &[u8],
        expected: ExportDigests,
    ) -> Result<Self, ConfigurationError> {
        for (bytes, hash) in [
            (manifest, expected.manifest),
            (inputs, expected.inputs),
            (worker, expected.worker),
            (supervisor, expected.supervisor),
        ] {
            if digest(bytes) != hash {
                return Err(ConfigurationError::Digest);
            }
        }
        // Manifest is opaque reviewed material bound by its exact raw digest.
        // We deliberately do not infer schema/source authenticity from substring
        // matches. F1's exporter and its independent checker own that validation.
        let worker_policy = worker_policy();
        let supervisor_policy = SupervisorRuntimePolicy::new(BOOTSTRAP_SUPERVISOR_ROLES)
            .map_err(|_| ConfigurationError::Roles)?
            .compile();
        if worker != worker_policy.bytes() || supervisor != supervisor_policy.bytes() {
            return Err(ConfigurationError::Policy);
        }
        let mut c = Cursor {
            bytes: inputs,
            offset: 0,
        };
        c.literal(b"{\"resources\":{")?;
        let query = c.field(b"\"stdin_bytes\":")?;
        let stdout = c.field(b",\"stdout_bytes\":")?;
        let stderr = c.field(b",\"stderr_bytes\":")?;
        let wall = c.field(b",\"wall_clock_ms\":")?;
        let memory = c.field(b",\"working_memory_bytes\":")?;
        let swap = c.field(b",\"swap_bytes\":")?;
        let pids = c.field(b",\"pids_max\":")?;
        let file = c.field(b",\"cgroup_file_bytes\":")?;
        let steps = c.field(b",\"semantic_steps\":")?;
        let internal = c.field(b",\"internal_wall_clock_ms\":")?;
        c.literal(b"},\"wire\":{")?;
        for (key, value) in [
            (
                b"\"header_bytes\":".as_slice(),
                wire::BOOTSTRAP_HEADER_BYTES,
            ),
            (b",\"binding_bytes\":", wire::BOOTSTRAP_BINDING_BYTES),
            (b",\"payload_bytes\":", wire::BOOTSTRAP_PAYLOAD_LIMIT),
            (b",\"chunk_bytes\":", wire::BOOTSTRAP_CHUNK_LIMIT),
            (b",\"control_bytes\":", wire::BOOTSTRAP_CONTROL_LIMIT),
            (
                b",\"direction_control_bytes\":",
                wire::BOOTSTRAP_DIRECTION_CONTROL_LIMIT,
            ),
            (b",\"pending_bytes\":", wire::BOOTSTRAP_PENDING_LIMIT),
        ] {
            if c.field(key)? != value as u64 {
                return Err(ConfigurationError::Bounds);
            }
        }
        c.literal(b"},\"supervisor_fd_roles\":{")?;
        let roles = BOOTSTRAP_SUPERVISOR_ROLES;
        for (key, value) in [
            (b"\"control_input\":".as_slice(), roles.control_input),
            (b",\"envelope_output\":", roles.envelope_output),
            (b",\"diagnostic_output\":", roles.diagnostic_output),
            (b",\"child_stdin\":", roles.child_stdin),
            (b",\"child_stdout\":", roles.child_stdout),
            (b",\"child_stderr\":", roles.child_stderr),
            (b",\"timer\":", roles.timer),
            (b",\"pidfd\":", roles.pidfd),
            (b",\"listener\":", roles.listener),
        ] {
            if c.field(key)? != value {
                return Err(ConfigurationError::Roles);
            }
        }
        c.literal(b",\"cgroup\":[")?;
        for (i, value) in roles.cgroup.iter().enumerate() {
            if i > 0 {
                c.literal(b",")?;
            }
            if c.number()? != *value {
                return Err(ConfigurationError::Roles);
            }
        }
        c.literal(b"]}}")?;
        if c.offset != inputs.len() {
            return Err(ConfigurationError::Encoding);
        }
        let usize_value = |n| usize::try_from(n).map_err(|_| ConfigurationError::Bounds);
        let window_ns = wall
            .checked_mul(1_000_000)
            .filter(|n| *n > 0)
            .ok_or(ConfigurationError::Bounds)?;
        if query == 0
            || stdout == 0
            || stderr == 0
            || file == 0
            || memory == 0
            || pids != 2
            || swap != 0
            || internal >= wall
            || steps == 0
        {
            return Err(ConfigurationError::Bounds);
        }
        Ok(Self {
            wire: WireLimits {
                query_bytes: usize_value(query)?,
                stdout_bytes: usize_value(stdout)?,
                stderr_bytes: usize_value(stderr)?,
            },
            cgroup: CgroupLimits {
                memory_max: memory,
                swap_max: swap,
                pids_max: pids,
                file_bytes: usize_value(file)?,
            },
            window_ns,
            semantic_steps: steps,
            internal_wall_clock_ms: internal,
            worker: worker_policy,
            supervisor: supervisor_policy,
            export_digest: expected.manifest,
        })
    }
}
struct Cursor<'a> {
    bytes: &'a [u8],
    offset: usize,
}
impl Cursor<'_> {
    fn literal(&mut self, s: &[u8]) -> Result<(), ConfigurationError> {
        if self.bytes.get(self.offset..self.offset + s.len()) != Some(s) {
            return Err(ConfigurationError::Encoding);
        }
        self.offset += s.len();
        Ok(())
    }
    fn field(&mut self, s: &[u8]) -> Result<u64, ConfigurationError> {
        self.literal(s)?;
        self.number()
    }
    fn number(&mut self) -> Result<u64, ConfigurationError> {
        let start = self.offset;
        let mut n = 0u64;
        while let Some(b @ b'0'..=b'9') = self.bytes.get(self.offset) {
            n = n
                .checked_mul(10)
                .and_then(|n| n.checked_add(u64::from(*b - b'0')))
                .ok_or(ConfigurationError::Bounds)?;
            self.offset += 1;
        }
        if self.offset == start || (self.offset > start + 1 && self.bytes[start] == b'0') {
            return Err(ConfigurationError::Encoding);
        }
        Ok(n)
    }
}

/// Independently exported build material. It is not accepted from StartDescription.
pub(crate) struct CommandInputs {
    pub tokens: [std::ffi::CString; 12],
    pub digest: [u8; 32],
}
impl CommandInputs {
    pub fn parse(bytes: &[u8], expected: [u8; 32]) -> Result<Self, ConfigurationError> {
        if bytes.len() > 4096 || digest(bytes) != expected {
            return Err(ConfigurationError::Digest);
        }
        if bytes.get(..8) != Some(b"AXBCMD01") || bytes.get(8..12) != Some(&12u32.to_be_bytes()) {
            return Err(ConfigurationError::Encoding);
        }
        let mut at = 12;
        let mut tokens = Vec::with_capacity(12);
        for _ in 0..12 {
            let raw = bytes.get(at..at + 4).ok_or(ConfigurationError::Encoding)?;
            let len = u32::from_be_bytes(raw.try_into().map_err(|_| ConfigurationError::Encoding)?)
                as usize;
            at += 4;
            if !(1..=128).contains(&len) {
                return Err(ConfigurationError::Bounds);
            }
            let token = bytes
                .get(at..at + len)
                .ok_or(ConfigurationError::Encoding)?;
            at += len;
            if !token.starts_with(b"--") || !token.iter().all(|b| (0x21..=0x7e).contains(b)) {
                return Err(ConfigurationError::Encoding);
            }
            tokens.push(std::ffi::CString::new(token).map_err(|_| ConfigurationError::Encoding)?);
        }
        if at != bytes.len() {
            return Err(ConfigurationError::Encoding);
        }
        Ok(Self {
            tokens: tokens
                .try_into()
                .map_err(|_| ConfigurationError::Encoding)?,
            digest: expected,
        })
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use radishaxiom_solver_diagnostic_host::{
        bootstrap_command::{check_offline_command, export_offline_command},
        bootstrap_manifest::{check_offline_inputs, export_offline_inputs},
    };
    pub(crate) fn exported() -> OfflineConfiguration {
        let e = export_offline_inputs();
        check_offline_inputs(&e).unwrap();
        OfflineConfiguration::from_export(
            &e.manifest,
            &e.inputs,
            &e.worker_cbpf,
            &e.supervisor_cbpf,
            ExportDigests {
                manifest: digest(&e.manifest),
                inputs: digest(&e.inputs),
                worker: digest(&e.worker_cbpf),
                supervisor: digest(&e.supervisor_cbpf),
            },
        )
        .unwrap()
    }
    #[test]
    fn actual_f1_export_is_consumed_without_resource_defaults() {
        let config = exported();
        let actual =
            radishaxiom_solver_diagnostic_host::bootstrap_manifest::process_resource_inputs();
        assert_eq!(config.wire, actual.wire);
        assert_eq!(config.cgroup, actual.cgroup);
        assert_eq!(config.window_ns, actual.wall_clock_ms * 1_000_000);
        assert_eq!(config.semantic_steps, actual.semantic_steps);
        assert_eq!(config.internal_wall_clock_ms, actual.internal_wall_clock_ms);
    }
    #[test]
    fn actual_command_export_and_all_truncations() {
        let e = export_offline_command();
        check_offline_command(&e).unwrap();
        let parsed = CommandInputs::parse(&e.command, digest(&e.command)).unwrap();
        assert_eq!(parsed.tokens.len(), 12);
        for n in 0..e.command.len() {
            assert!(CommandInputs::parse(&e.command[..n], digest(&e.command[..n])).is_err());
        }
        let mut trailing = e.command.clone();
        trailing.push(0);
        assert!(CommandInputs::parse(&trailing, digest(&trailing)).is_err());
        let mut altered = e.command;
        altered[16] = 0;
        assert!(CommandInputs::parse(&altered, digest(&altered)).is_err());
    }
    #[test]
    fn digest_and_role_tampering_never_become_input_qualification() {
        let e = export_offline_inputs();
        let expected = ExportDigests {
            manifest: digest(&e.manifest),
            inputs: digest(&e.inputs),
            worker: digest(&e.worker_cbpf),
            supervisor: digest(&e.supervisor_cbpf),
        };
        let mut bytes = e.inputs.clone();
        bytes.push(b' ');
        assert!(matches!(
            OfflineConfiguration::from_export(
                &e.manifest,
                &bytes,
                &e.worker_cbpf,
                &e.supervisor_cbpf,
                expected
            ),
            Err(ConfigurationError::Digest)
        ));
        let text = String::from_utf8(e.inputs.clone())
            .unwrap()
            .replace("\"timer\":13", "\"timer\":14");
        let bytes = text.as_bytes();
        let mut changed = expected;
        changed.inputs = digest(bytes);
        assert!(matches!(
            OfflineConfiguration::from_export(
                &e.manifest,
                bytes,
                &e.worker_cbpf,
                &e.supervisor_cbpf,
                changed
            ),
            Err(ConfigurationError::Roles)
        ));
    }
}
