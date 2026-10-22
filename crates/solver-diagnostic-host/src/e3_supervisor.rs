//! ADR 0029 pure supervision simulation. No action here executes a syscall.
use crate::{
    e3_cgroup::*,
    e3_wire::{Arm, BootstrapBinding, ChildExit, Ready},
};

pub const SIMULATION_WINDOW_NS: u64 =
    radishaxiom_ir::solver::PROCESS_LIMITS.wall_clock_ms * 1_000_000;
pub const SIMULATION_QUERY_MAX: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stdin_bytes;
pub const SIMULATION_STDOUT_MAX: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stdout_bytes;
pub const SIMULATION_STDERR_MAX: usize = radishaxiom_ir::solver::PROCESS_LIMITS.stderr_bytes;
pub const AARCH64_AUDIT_ARCH: u32 = crate::e3_abi::AUDIT_ARCH_AARCH64;
pub const EXECVEAT_EMPTY_PATH: u64 = crate::e3_abi::AT_EMPTY_PATH;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SimulationFailureReason {
    ClockOverflow,
    ClockRollback,
    Deadline,
    Binding,
    Protocol,
    Query,
    Cgroup,
    Resource,
    Clone,
    Listener,
    Notification,
    ContinueSend,
    ControlEof,
    OutputLimit,
    Reaping,
    SupervisorLost,
    OuterState,
    Cleanup,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SyntheticChildToken {
    pub pid: u32,
    /// An opaque synthetic identity, never a numeric OS descriptor.
    pub pidfd_identity: [u8; 32],
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SyntheticExecPointers {
    pub empty_path: u64,
    pub fixed_argv: u64,
    pub empty_envp: u64,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SyntheticExecNotification {
    pub binding: BootstrapBinding,
    pub id: u64,
    pub id_valid: bool,
    pub child: SyntheticChildToken,
    pub audit_arch: u32,
    pub syscall_number: i32,
    pub notification_flags: u32,
    pub executable_fd: u64,
    pub flags: u64,
    pub pointers: SyntheticExecPointers,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SimulationAction {
    Ready,
    InstallAbsoluteDeadline {
        deadline_ns: u64,
    },
    CloneOnce,
    AwaitTrustedFirstExec,
    ContinueOnce {
        notification_id: u64,
        child: SyntheticChildToken,
    },
    RecordOnly,
    LocalFinal,
    SimulationComplete,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SimulationStopAction {
    pub stop_stdin: bool,
    pub kill_bound_child: Option<SyntheticChildToken>,
    pub exit_supervisor: bool,
    pub rely_on_pid_namespace_teardown: bool,
}
#[derive(Clone, Debug)]
pub struct SimulationSupervisorConfig {
    pub binding: BootstrapBinding,
    pub identity: CgroupIdentity,
    pub configuration_digest: [u8; 32],
    pub mac_create_start_ns: u64,
    pub linux_entry_ns: u64,
    /// Declared synthetic bound only. This is never a runtime qualification.
    pub declared_clock_error_ns: u64,
    pub expected_query_len: u32,
    pub expected_query_digest: [u8; 32],
    pub pointers: SyntheticExecPointers,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Stage {
    Preparing,
    Ready,
    Armed,
    Cloning,
    AwaitingExec,
    ContinueConsumed,
    Running,
    LocalFinal,
    Complete,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SyntheticOuterState {
    pub identity: CgroupIdentity,
    pub running: bool,
    pub init_pid: u64,
    pub restart_count: u64,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SimulationCompletion {
    child_exit: ChildExit,
    normal_response_eligible: bool,
}
impl SimulationCompletion {
    pub fn scope(&self) -> &'static str {
        "simulation"
    }
    pub fn tree_basis(&self) -> &'static str {
        "pidns-init-exit-and-runtime-state"
    }
    pub fn child_exit(&self) -> ChildExit {
        self.child_exit
    }
    pub fn real_execution(&self) -> &'static str {
        "blocked-E0-and-runtime-qualification"
    }
    pub fn normal_response_eligible(&self) -> bool {
        self.normal_response_eligible
    }
}

pub struct SimulationSupervisor {
    config: SimulationSupervisorConfig,
    mac_deadline_ns: u64,
    preparation_deadline_ns: u64,
    last_linux_ns: u64,
    last_mac_ns: u64,
    ready_linux_ns: Option<u64>,
    deadline_ns: Option<u64>,
    arm: Option<Arm>,
    stage: Stage,
    child: Option<SyntheticChildToken>,
    listener_received: bool,
    continue_sent: bool,
    stdout_bytes: usize,
    stderr_bytes: usize,
    stdout_eof: bool,
    stderr_eof: bool,
    child_exit: Option<ChildExit>,
    child_reaped: bool,
    self_only: bool,
    latest_cgroup: Option<SyntheticCgroupObservation>,
    final_cgroup_missing: bool,
    outer_confirmed: bool,
    removal_confirmed: bool,
    cleanup_timing_valid: bool,
    supervisor_alive: bool,
    failure: Option<SimulationFailureReason>,
}
impl SimulationSupervisor {
    pub fn new(config: SimulationSupervisorConfig) -> Result<Self, SimulationFailureReason> {
        let mac_deadline_ns = config
            .mac_create_start_ns
            .checked_add(SIMULATION_WINDOW_NS)
            .ok_or(SimulationFailureReason::ClockOverflow)?;
        let preparation_deadline_ns = config
            .linux_entry_ns
            .checked_add(SIMULATION_WINDOW_NS)
            .ok_or(SimulationFailureReason::ClockOverflow)?;
        if config.pointers.empty_path == 0
            || config.pointers.fixed_argv == 0
            || config.pointers.empty_envp == 0
        {
            return Err(SimulationFailureReason::Notification);
        }
        if config.expected_query_len as usize > SIMULATION_QUERY_MAX {
            return Err(SimulationFailureReason::Query);
        }
        Ok(Self {
            last_linux_ns: config.linux_entry_ns,
            last_mac_ns: config.mac_create_start_ns,
            config,
            mac_deadline_ns,
            preparation_deadline_ns,
            ready_linux_ns: None,
            deadline_ns: None,
            arm: None,
            stage: Stage::Preparing,
            child: None,
            listener_received: false,
            continue_sent: false,
            stdout_bytes: 0,
            stderr_bytes: 0,
            stdout_eof: false,
            stderr_eof: false,
            child_exit: None,
            child_reaped: false,
            self_only: false,
            latest_cgroup: None,
            final_cgroup_missing: true,
            outer_confirmed: false,
            removal_confirmed: false,
            cleanup_timing_valid: true,
            supervisor_alive: true,
            failure: None,
        })
    }
    pub fn scope(&self) -> &'static str {
        "simulation"
    }
    pub fn real_execution(&self) -> &'static str {
        "blocked-E0-and-runtime-qualification"
    }
    pub fn failure(&self) -> Option<SimulationFailureReason> {
        self.failure
    }
    pub fn mac_deadline_ns(&self) -> u64 {
        self.mac_deadline_ns
    }
    pub fn linux_deadline_ns(&self) -> Option<u64> {
        self.deadline_ns
    }
    pub fn final_cgroup_missing(&self) -> bool {
        self.final_cgroup_missing
    }
    pub fn latest_cgroup(&self) -> Option<&SyntheticCgroupObservation> {
        self.latest_cgroup.as_ref()
    }
    pub fn removal_confirmed(&self) -> bool {
        self.removal_confirmed
    }
    pub fn cleanup_timing_valid(&self) -> bool {
        self.cleanup_timing_valid
    }
    pub fn normal_response_eligible(&self) -> bool {
        self.failure.is_none()
            && self.stage == Stage::Complete
            && matches!(self.child_exit, Some(ChildExit::Exited(0)))
    }
    pub fn stop_action(&self) -> Option<SimulationStopAction> {
        self.failure.map(|_| SimulationStopAction {
            stop_stdin: true,
            kill_bound_child: if self.child_reaped || !self.supervisor_alive {
                None
            } else {
                self.child.clone()
            },
            exit_supervisor: self.supervisor_alive,
            rely_on_pid_namespace_teardown: !self.supervisor_alive,
        })
    }
    fn fail<T>(&mut self, reason: SimulationFailureReason) -> Result<T, SimulationFailureReason> {
        let first = *self.failure.get_or_insert(reason);
        Err(first)
    }
    fn live(&mut self) -> Result<(), SimulationFailureReason> {
        if let Some(failure) = self.failure {
            return Err(failure);
        }
        if self.stage == Stage::Complete {
            return self.fail(SimulationFailureReason::Protocol);
        }
        Ok(())
    }
    fn linux_now(&mut self, now_ns: u64) -> Result<(), SimulationFailureReason> {
        self.live()?;
        if now_ns < self.last_linux_ns {
            return self.fail(SimulationFailureReason::ClockRollback);
        }
        self.last_linux_ns = now_ns;
        if now_ns >= self.deadline_ns.unwrap_or(self.preparation_deadline_ns) {
            return self.fail(SimulationFailureReason::Deadline);
        }
        Ok(())
    }
    fn mac_now(&mut self, now_ns: u64) -> Result<(), SimulationFailureReason> {
        self.live()?;
        if now_ns < self.last_mac_ns {
            return self.fail(SimulationFailureReason::ClockRollback);
        }
        self.last_mac_ns = now_ns;
        if now_ns >= self.mac_deadline_ns {
            return self.fail(SimulationFailureReason::Deadline);
        }
        Ok(())
    }
    fn cleanup_mac_now(&mut self, now_ns: u64) -> Result<(), SimulationFailureReason> {
        if self.failure.is_none() {
            return self
                .mac_now(now_ns)
                .inspect_err(|_| self.cleanup_timing_valid = false);
        }
        if now_ns < self.last_mac_ns || now_ns >= self.mac_deadline_ns {
            self.cleanup_timing_valid = false;
        }
        self.last_mac_ns = self.last_mac_ns.max(now_ns);
        Ok(())
    }
    fn binding(&mut self, binding: &BootstrapBinding) -> Result<(), SimulationFailureReason> {
        if *binding != self.config.binding {
            return self.fail(SimulationFailureReason::Binding);
        }
        Ok(())
    }
    fn observe_cgroup(
        &mut self,
        now_ns: u64,
        observation: SyntheticCgroupObservation,
        members: &[u32],
    ) -> Result<(), SimulationFailureReason> {
        if observation.identity != self.config.identity
            || observation.members != members
            || observation.interval.end_ns > now_ns
            || observation.interval.start_ns < self.config.linux_entry_ns
        {
            return self.fail(SimulationFailureReason::Cgroup);
        }
        let mut resource_event = false;
        if let Some(before) = &self.latest_cgroup {
            if observation.check_follows(before).is_err() {
                return self.fail(SimulationFailureReason::Cgroup);
            }
            let a = observation.memory_events;
            let b = before.memory_events;
            resource_event = a.max > b.max
                || a.oom > b.oom
                || a.oom_kill > b.oom_kill
                || a.oom_group_kill > b.oom_group_kill
                || observation.pids_max_events > before.pids_max_events;
        } else if observation.memory_events.max > 0
            || observation.memory_events.oom > 0
            || observation.memory_events.oom_kill > 0
            || observation.memory_events.oom_group_kill > 0
            || observation.pids_max_events > 0
        {
            resource_event = true;
        }
        self.latest_cgroup = Some(observation);
        if resource_event {
            return self.fail(SimulationFailureReason::Resource);
        }
        Ok(())
    }
    pub fn ready(
        &mut self,
        now_ns: u64,
        observation: SyntheticCgroupObservation,
    ) -> Result<Ready, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        if self.stage != Stage::Preparing {
            return self.fail(SimulationFailureReason::Protocol);
        }
        self.observe_cgroup(now_ns, observation, &[1])?;
        self.ready_linux_ns = Some(now_ns);
        self.stage = Stage::Ready;
        Ok(Ready {
            linux_ready_ns: now_ns,
            preparation_deadline_ns: self.preparation_deadline_ns,
            boot_digest: self.config.identity.boot,
            namespace_digest: self.config.identity.pid_namespace,
            configuration_digest: self.config.configuration_digest,
        })
    }
    /// Causal READY-to-ARM arithmetic: never subtract absolute Mac and Linux clocks.
    pub fn make_arm(
        &mut self,
        mac_receive_ns: u64,
        ready: &Ready,
        query_len: u32,
        query_digest: [u8; 32],
    ) -> Result<Arm, SimulationFailureReason> {
        self.mac_now(mac_receive_ns)?;
        if query_len != self.config.expected_query_len
            || query_digest != self.config.expected_query_digest
        {
            return self.fail(SimulationFailureReason::Query);
        }
        if self.stage != Stage::Ready
            || self.ready_linux_ns != Some(ready.linux_ready_ns)
            || ready.preparation_deadline_ns != self.preparation_deadline_ns
            || ready.boot_digest != self.config.identity.boot
            || ready.namespace_digest != self.config.identity.pid_namespace
            || ready.configuration_digest != self.config.configuration_digest
        {
            return self.fail(SimulationFailureReason::Binding);
        }
        let remaining = self
            .mac_deadline_ns
            .checked_sub(mac_receive_ns)
            .and_then(|n| n.checked_sub(self.config.declared_clock_error_ns))
            .filter(|n| *n > 0);
        let Some(remaining) = remaining else {
            return self.fail(SimulationFailureReason::Deadline);
        };
        let Some(deadline_ns) = ready.linux_ready_ns.checked_add(remaining) else {
            return self.fail(SimulationFailureReason::ClockOverflow);
        };
        if deadline_ns > self.preparation_deadline_ns || query_len as usize > SIMULATION_QUERY_MAX {
            return self.fail(SimulationFailureReason::Protocol);
        }
        let arm = Arm {
            deadline_ns,
            query_len,
            query_digest,
        };
        // Retain the exact offer; arm cannot replace it with an arbitrary later deadline.
        if self.arm.is_some() {
            return self.fail(SimulationFailureReason::Protocol);
        }
        self.arm = Some(arm.clone());
        Ok(arm)
    }
    pub fn arm(
        &mut self,
        now_ns: u64,
        binding: &BootstrapBinding,
        arm: Arm,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        self.binding(binding)?;
        if self.stage != Stage::Ready
            || self.arm.as_ref() != Some(&arm)
            || arm.deadline_ns > self.preparation_deadline_ns
        {
            return self.fail(SimulationFailureReason::Protocol);
        }
        if now_ns >= arm.deadline_ns {
            return self.fail(SimulationFailureReason::Deadline);
        }
        self.deadline_ns = Some(arm.deadline_ns);
        self.stage = Stage::Armed;
        Ok(SimulationAction::InstallAbsoluteDeadline {
            deadline_ns: arm.deadline_ns,
        })
    }
    /// Called only with a fully decoded query; hashes actual bytes without caching a copy.
    pub fn query_complete(
        &mut self,
        now_ns: u64,
        binding: &BootstrapBinding,
        bytes: &[u8],
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        self.binding(binding)?;
        if self.stage != Stage::Armed {
            return self.fail(SimulationFailureReason::Protocol);
        }
        let Some(arm) = &self.arm else {
            return self.fail(SimulationFailureReason::Protocol);
        };
        if bytes.len() > SIMULATION_QUERY_MAX
            || bytes.len() != arm.query_len as usize
            || radishaxiom_digest::digest(bytes) != arm.query_digest
        {
            return self.fail(SimulationFailureReason::Query);
        }
        self.stage = Stage::Cloning;
        Ok(SimulationAction::CloneOnce)
    }
    pub fn clone_returned(
        &mut self,
        now_ns: u64,
        token: SyntheticChildToken,
        observation: SyntheticCgroupObservation,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        if self.stage != Stage::Cloning
            || token.pid <= 1
            || token.pidfd_identity == [0; 32]
            || self.child.is_some()
        {
            return self.fail(SimulationFailureReason::Clone);
        }
        // Bind the returned child even when subsequent readback fails: cleanup targets this token.
        self.child = Some(token.clone());
        self.linux_now(now_ns)?;
        self.observe_cgroup(now_ns, observation, &[1, token.pid])?;
        self.stage = Stage::AwaitingExec;
        Ok(SimulationAction::AwaitTrustedFirstExec)
    }
    pub fn listener_received(
        &mut self,
        now_ns: u64,
        binding: &BootstrapBinding,
        child: &SyntheticChildToken,
        fd_count: usize,
        truncated: bool,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        self.binding(binding)?;
        if self.stage != Stage::AwaitingExec
            || self.listener_received
            || self.child.as_ref() != Some(child)
            || fd_count != 1
            || truncated
        {
            return self.fail(SimulationFailureReason::Listener);
        }
        self.listener_received = true;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn grant_first_exec(
        &mut self,
        now_ns: u64,
        notification: SyntheticExecNotification,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        self.binding(&notification.binding)?;
        if self.stage != Stage::AwaitingExec
            || !self.listener_received
            || !notification.id_valid
            || notification.id == 0
            || self.child.as_ref() != Some(&notification.child)
            || notification.audit_arch != AARCH64_AUDIT_ARCH
            || notification.syscall_number != crate::e3_abi::NR_EXECVEAT
            || notification.notification_flags != 0
            || notification.executable_fd != 3
            || notification.flags != EXECVEAT_EMPTY_PATH
            || notification.pointers != self.config.pointers
        {
            return self.fail(SimulationFailureReason::Notification);
        }
        // Consume before returning the only send intent, including when send later fails.
        self.stage = Stage::ContinueConsumed;
        Ok(SimulationAction::ContinueOnce {
            notification_id: notification.id,
            child: notification.child,
        })
    }
    pub fn continue_send_result(
        &mut self,
        now_ns: u64,
        sent: bool,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        if self.stage != Stage::ContinueConsumed {
            return self.fail(SimulationFailureReason::Protocol);
        }
        if !sent {
            return self.fail(SimulationFailureReason::ContinueSend);
        }
        self.continue_sent = true;
        self.stage = Stage::Running;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn cgroup_observation(
        &mut self,
        now_ns: u64,
        observation: SyntheticCgroupObservation,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        if self.stage != Stage::Running {
            return self.fail(SimulationFailureReason::Protocol);
        }
        let members = if self.child_reaped {
            vec![1]
        } else {
            vec![
                1,
                self.child
                    .as_ref()
                    .ok_or(SimulationFailureReason::Clone)?
                    .pid,
            ]
        };
        self.observe_cgroup(now_ns, observation, &members)?;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn stdout(
        &mut self,
        now_ns: u64,
        bytes: &[u8],
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.stream(now_ns, bytes, true)
    }
    pub fn stderr(
        &mut self,
        now_ns: u64,
        bytes: &[u8],
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.stream(now_ns, bytes, false)
    }
    fn stream(
        &mut self,
        now_ns: u64,
        bytes: &[u8],
        stdout: bool,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        if self.stage != Stage::Running
            || if stdout {
                self.stdout_eof
            } else {
                self.stderr_eof
            }
        {
            return self.fail(SimulationFailureReason::Protocol);
        }
        let (count, max) = if stdout {
            (&mut self.stdout_bytes, SIMULATION_STDOUT_MAX)
        } else {
            (&mut self.stderr_bytes, SIMULATION_STDERR_MAX)
        };
        let Some(total) = count.checked_add(bytes.len()).filter(|n| *n <= max) else {
            return self.fail(SimulationFailureReason::OutputLimit);
        };
        *count = total;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn stdout_eof(&mut self, now_ns: u64) -> Result<SimulationAction, SimulationFailureReason> {
        self.stream_eof(now_ns, true)
    }
    pub fn stderr_eof(&mut self, now_ns: u64) -> Result<SimulationAction, SimulationFailureReason> {
        self.stream_eof(now_ns, false)
    }
    fn stream_eof(
        &mut self,
        now_ns: u64,
        stdout: bool,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        if self.stage != Stage::Running {
            return self.fail(SimulationFailureReason::Protocol);
        }
        let eof = if stdout {
            &mut self.stdout_eof
        } else {
            &mut self.stderr_eof
        };
        if *eof {
            return self.fail(SimulationFailureReason::Protocol);
        }
        *eof = true;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn child_reaped(
        &mut self,
        now_ns: u64,
        child: &SyntheticChildToken,
        exit: ChildExit,
        observation: SyntheticCgroupObservation,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        if self.stage != Stage::Running
            || self.child_reaped
            || self.child.as_ref() != Some(child)
            || matches!(exit, ChildExit::Signaled(signal) if !(1..=64).contains(&signal))
        {
            return self.fail(SimulationFailureReason::Reaping);
        }
        self.child_reaped = true;
        self.child_exit = Some(exit);
        let observed = self.observe_cgroup(now_ns, observation, &[1]);
        if observed.is_ok() || observed == Err(SimulationFailureReason::Resource) {
            self.self_only = true;
            self.final_cgroup_missing = false;
        }
        observed?;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn supervisor_final(
        &mut self,
        now_ns: u64,
        binding: &BootstrapBinding,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        self.binding(binding)?;
        if self.stage != Stage::Running
            || !self.continue_sent
            || !self.stdout_eof
            || !self.stderr_eof
            || !self.child_reaped
            || !self.self_only
        {
            return self.fail(SimulationFailureReason::Protocol);
        }
        self.stage = Stage::LocalFinal;
        Ok(SimulationAction::LocalFinal)
    }
    pub fn outer_state(
        &mut self,
        mac_now_ns: u64,
        state: SyntheticOuterState,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        // Cleanup facts remain recordable after failure, but cannot reopen normal completion.
        self.cleanup_mac_now(mac_now_ns)?;
        let invalid = state.identity != self.config.identity
            || state.running
            || state.init_pid != 0
            || state.restart_count != 0;
        if invalid {
            return self.fail(SimulationFailureReason::OuterState);
        }
        if self.failure.is_some() {
            self.outer_confirmed = true;
            return Ok(SimulationAction::RecordOnly);
        }
        if self.stage != Stage::LocalFinal || self.outer_confirmed {
            return self.fail(SimulationFailureReason::OuterState);
        }
        self.outer_confirmed = true;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn removal(
        &mut self,
        mac_now_ns: u64,
        identity: &CgroupIdentity,
        confirmed: bool,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.cleanup_mac_now(mac_now_ns)?;
        if identity != &self.config.identity || !confirmed {
            return self.fail(SimulationFailureReason::Cleanup);
        }
        if self.failure.is_some() {
            self.removal_confirmed = true;
            return Ok(SimulationAction::RecordOnly);
        }
        if self.stage != Stage::LocalFinal || !self.outer_confirmed || self.removal_confirmed {
            return self.fail(SimulationFailureReason::Cleanup);
        }
        self.removal_confirmed = true;
        self.stage = Stage::Complete;
        Ok(SimulationAction::SimulationComplete)
    }
    pub fn completion(&self) -> Option<SimulationCompletion> {
        if self.failure.is_some() || self.stage != Stage::Complete {
            return None;
        }
        Some(SimulationCompletion {
            child_exit: self.child_exit?,
            normal_response_eligible: self.normal_response_eligible(),
        })
    }
    pub fn tick(&mut self, now_ns: u64) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        Ok(SimulationAction::RecordOnly)
    }
    pub fn control_eof(
        &mut self,
        now_ns: u64,
    ) -> Result<SimulationAction, SimulationFailureReason> {
        self.linux_now(now_ns)?;
        self.fail(SimulationFailureReason::ControlEof)
    }
    pub fn protocol_failure(&mut self) -> Result<SimulationAction, SimulationFailureReason> {
        self.fail(SimulationFailureReason::Protocol)
    }
    pub fn reaping_failure(&mut self) -> Result<SimulationAction, SimulationFailureReason> {
        self.fail(SimulationFailureReason::Reaping)
    }
    pub fn supervisor_lost(&mut self) -> Result<SimulationAction, SimulationFailureReason> {
        self.supervisor_alive = false;
        self.final_cgroup_missing = true;
        self.fail(SimulationFailureReason::SupervisorLost)
    }
    pub fn listener_lost(&mut self) -> Result<SimulationAction, SimulationFailureReason> {
        self.final_cgroup_missing = true;
        self.fail(SimulationFailureReason::Listener)
    }
}
