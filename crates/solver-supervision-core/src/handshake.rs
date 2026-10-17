//! Separate Mac/S declaration checks and plans. No OS fact or authenticated
//! capture can be constructed here; all clocks, identities and nonce are claims.
//!
//! Clock types prevent accidental cross-clock arithmetic at call sites.
//! ```compile_fail
//! use radishaxiom_solver_supervision_core::handshake::{MacInstant, LinuxInstant};
//! let mac: MacInstant = LinuxInstant::declared_ns(1);
//! ```
//! Synthetic supervisor objects do not implement this interface.
//! ```compile_fail
//! use radishaxiom_solver_supervision_core::handshake::{MacHandshake, LinuxInstant};
//! fn mixed(mac: &mut MacHandshake) { mac.tick(LinuxInstant::declared_ns(1)); }
//! ```
use crate::{
    bootstrap_start::StartDescription,
    wire::{Arm, BootstrapBinding, BootstrapFrame, BootstrapMessage, Ready},
};
use std::fmt;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MacInstant(u64);
impl MacInstant {
    pub fn declared_ns(ns: u64) -> Self {
        Self(ns)
    }
    pub fn as_ns(self) -> u64 {
        self.0
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LinuxInstant(u64);
impl LinuxInstant {
    pub fn declared_ns(ns: u64) -> Self {
        Self(ns)
    }
    pub fn as_ns(self) -> u64 {
        self.0
    }
}
/// Explicit host-exported window. No default or runtime override is implied.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct HandshakeWindow {
    pub wall_clock_ns: u64,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ExpectedReadyDeclaration {
    pub boot_digest: [u8; 32],
    pub namespace_digest: [u8; 32],
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LocalReadyDeclaration {
    pub boot_digest: [u8; 32],
    pub namespace_digest: [u8; 32],
    pub configuration_digest: [u8; 32],
    pub nonce: [u8; 32],
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ClockSide {
    Mac,
    Supervisor,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum HandshakeError {
    Window,
    ClockOverflow {
        side: ClockSide,
    },
    ClockRollback {
        side: ClockSide,
        previous_ns: u64,
        now_ns: u64,
    },
    Deadline {
        side: ClockSide,
        now_ns: u64,
        deadline_ns: u64,
    },
    Binding {
        field: &'static str,
    },
    Protocol {
        expected: &'static str,
    },
    Query {
        field: &'static str,
    },
}
impl fmt::Display for HandshakeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "bootstrap declaration handshake: {self:?}")
    }
}
impl std::error::Error for HandshakeError {}
fn binding_equal(
    expected: &BootstrapBinding,
    actual: &BootstrapBinding,
) -> Result<(), HandshakeError> {
    for (field, a, b) in [
        ("attempt", expected.attempt, actual.attempt),
        ("request", expected.request, actual.request),
        ("policy_bundle", expected.policy, actual.policy),
        ("image", expected.image, actual.image),
        ("nonce", expected.nonce, actual.nonce),
    ] {
        if a != b {
            return Err(HandshakeError::Binding { field });
        }
    }
    Ok(())
}
fn clock(now: u64, last: &mut u64, deadline: u64, side: ClockSide) -> Result<(), HandshakeError> {
    if now < *last {
        return Err(HandshakeError::ClockRollback {
            side,
            previous_ns: *last,
            now_ns: now,
        });
    }
    *last = now;
    if now >= deadline {
        return Err(HandshakeError::Deadline {
            side,
            now_ns: now,
            deadline_ns: deadline,
        });
    }
    Ok(())
}

pub struct MacHandshake {
    start: StartDescription,
    expected: ExpectedReadyDeclaration,
    window: HandshakeWindow,
    deadline_ns: u64,
    last_ns: u64,
    declared_clock_error_ns: u64,
    binding: Option<BootstrapBinding>,
    failure: Option<HandshakeError>,
}
impl MacHandshake {
    pub fn new(
        start: StartDescription,
        create_start: MacInstant,
        declared_clock_error_ns: u64,
        expected: ExpectedReadyDeclaration,
        window: HandshakeWindow,
    ) -> Result<Self, HandshakeError> {
        if window.wall_clock_ns == 0 {
            return Err(HandshakeError::Window);
        }
        let deadline_ns = create_start.0.checked_add(window.wall_clock_ns).ok_or(
            HandshakeError::ClockOverflow {
                side: ClockSide::Mac,
            },
        )?;
        Ok(Self {
            start,
            expected,
            window,
            deadline_ns,
            last_ns: create_start.0,
            declared_clock_error_ns,
            binding: None,
            failure: None,
        })
    }
    pub fn scope(&self) -> &'static str {
        "external-declaration-check-and-plan"
    }
    pub fn deadline(&self) -> MacInstant {
        MacInstant(self.deadline_ns)
    }
    pub fn failure(&self) -> Option<&HandshakeError> {
        self.failure.as_ref()
    }
    fn finish<T>(&mut self, result: Result<T, HandshakeError>) -> Result<T, HandshakeError> {
        result.inspect_err(|error| {
            self.failure.get_or_insert(error.clone());
        })
    }
    fn live(&mut self, now: MacInstant) -> Result<(), HandshakeError> {
        if let Some(error) = &self.failure {
            return Err(error.clone());
        }
        let result = clock(now.0, &mut self.last_ns, self.deadline_ns, ClockSide::Mac);
        self.finish(result)
    }
    pub fn tick(&mut self, now: MacInstant) -> Result<(), HandshakeError> {
        self.live(now)
    }
    /// Receive once. The first nonce is only a declaration from this READY;
    /// future authenticated adapters must establish its source independently.
    pub fn receive_ready(
        &mut self,
        receive: MacInstant,
        frame: &BootstrapFrame,
    ) -> Result<BootstrapFrame, HandshakeError> {
        self.live(receive)?;
        let result = self.plan_arm(receive, frame);
        self.finish(result)
    }
    fn plan_arm(
        &mut self,
        receive: MacInstant,
        frame: &BootstrapFrame,
    ) -> Result<BootstrapFrame, HandshakeError> {
        if self.binding.is_some() {
            return Err(HandshakeError::Protocol {
                expected: "first READY",
            });
        }
        let BootstrapMessage::Ready(ready) = &frame.message else {
            return Err(HandshakeError::Protocol { expected: "READY" });
        };
        binding_equal(&self.start.binding(frame.binding.nonce), &frame.binding)?;
        for (field, a, b) in [
            (
                "configuration",
                self.start.fields().configuration,
                ready.configuration_digest,
            ),
            ("boot", self.expected.boot_digest, ready.boot_digest),
            (
                "namespace",
                self.expected.namespace_digest,
                ready.namespace_digest,
            ),
        ] {
            if a != b {
                return Err(HandshakeError::Binding { field });
            }
        }
        if ready.preparation_deadline_ns <= ready.linux_ready_ns {
            return Err(HandshakeError::Protocol {
                expected: "Lr < preparation deadline",
            });
        }
        // Subtraction is valid only within Linux's own clock domain.
        if ready.preparation_deadline_ns - ready.linux_ready_ns > self.window.wall_clock_ns {
            return Err(HandshakeError::Protocol {
                expected: "preparation remaining <= original window",
            });
        }
        let remaining = self
            .deadline_ns
            .checked_sub(receive.0)
            .and_then(|v| v.checked_sub(self.declared_clock_error_ns))
            .filter(|v| *v > 0)
            .ok_or(HandshakeError::Deadline {
                side: ClockSide::Mac,
                now_ns: receive.0,
                deadline_ns: self.deadline_ns,
            })?;
        let deadline_ns =
            ready
                .linux_ready_ns
                .checked_add(remaining)
                .ok_or(HandshakeError::ClockOverflow {
                    side: ClockSide::Supervisor,
                })?;
        if deadline_ns > ready.preparation_deadline_ns {
            return Err(HandshakeError::Protocol {
                expected: "DL <= preparation deadline",
            });
        }
        self.binding = Some(frame.binding.clone());
        Ok(BootstrapFrame {
            binding: frame.binding.clone(),
            message: BootstrapMessage::Arm(Arm {
                deadline_ns,
                query_len: self.start.fields().query_bytes,
                query_digest: self.start.fields().query_digest,
            }),
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SupervisorStage {
    Preparing,
    Ready,
    Armed,
    QueryChecked,
}
/// Planning value only; acceptance of an ARM header does not validate the query.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DeadlinePlan {
    deadline: LinuxInstant,
}
impl DeadlinePlan {
    pub fn deadline(&self) -> LinuxInstant {
        self.deadline
    }
    pub fn scope(&self) -> &'static str {
        "external-declaration-check-and-plan"
    }
}
/// Actual bytes matched the declaration in this pure check; this is neither a
/// child-creation capability nor a real execution/capture completion value.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct QueryCheckedPlan {
    binding: BootstrapBinding,
    deadline: LinuxInstant,
}
impl QueryCheckedPlan {
    pub fn binding(&self) -> &BootstrapBinding {
        &self.binding
    }
    pub fn deadline(&self) -> LinuxInstant {
        self.deadline
    }
    pub fn scope(&self) -> &'static str {
        "external-declaration-check-and-plan"
    }
}
pub struct SupervisorHandshake {
    start: StartDescription,
    local: LocalReadyDeclaration,
    binding: BootstrapBinding,
    preparation_deadline_ns: u64,
    last_ns: u64,
    ready_ns: Option<u64>,
    deadline_ns: Option<u64>,
    stage: SupervisorStage,
    failure: Option<HandshakeError>,
}
impl SupervisorHandshake {
    pub fn new(
        start: StartDescription,
        entry: LinuxInstant,
        local: LocalReadyDeclaration,
        window: HandshakeWindow,
    ) -> Result<Self, HandshakeError> {
        if window.wall_clock_ns == 0 {
            return Err(HandshakeError::Window);
        }
        let preparation_deadline_ns =
            entry
                .0
                .checked_add(window.wall_clock_ns)
                .ok_or(HandshakeError::ClockOverflow {
                    side: ClockSide::Supervisor,
                })?;
        if local.configuration_digest != start.fields().configuration {
            return Err(HandshakeError::Binding {
                field: "configuration",
            });
        }
        let binding = start.binding(local.nonce);
        Ok(Self {
            start,
            local,
            binding,
            preparation_deadline_ns,
            last_ns: entry.0,
            ready_ns: None,
            deadline_ns: None,
            stage: SupervisorStage::Preparing,
            failure: None,
        })
    }
    pub fn scope(&self) -> &'static str {
        "external-declaration-check-and-plan"
    }
    pub fn failure(&self) -> Option<&HandshakeError> {
        self.failure.as_ref()
    }
    pub fn preparation_deadline(&self) -> LinuxInstant {
        LinuxInstant(self.preparation_deadline_ns)
    }
    pub fn ready_at(&self) -> Option<LinuxInstant> {
        self.ready_ns.map(LinuxInstant)
    }
    fn finish<T>(&mut self, result: Result<T, HandshakeError>) -> Result<T, HandshakeError> {
        result.inspect_err(|error| {
            self.failure.get_or_insert(error.clone());
        })
    }
    fn live(&mut self, now: LinuxInstant) -> Result<(), HandshakeError> {
        if let Some(error) = &self.failure {
            return Err(error.clone());
        }
        let result = clock(
            now.0,
            &mut self.last_ns,
            self.deadline_ns.unwrap_or(self.preparation_deadline_ns),
            ClockSide::Supervisor,
        );
        self.finish(result)
    }
    pub fn tick(&mut self, now: LinuxInstant) -> Result<(), HandshakeError> {
        self.live(now)
    }
    pub fn ready(&mut self, now: LinuxInstant) -> Result<BootstrapFrame, HandshakeError> {
        self.live(now)?;
        if self.stage != SupervisorStage::Preparing {
            return self.finish(Err(HandshakeError::Protocol {
                expected: "first READY",
            }));
        }
        self.stage = SupervisorStage::Ready;
        self.ready_ns = Some(now.0);
        Ok(BootstrapFrame {
            binding: self.binding.clone(),
            message: BootstrapMessage::Ready(Ready {
                linux_ready_ns: now.0,
                preparation_deadline_ns: self.preparation_deadline_ns,
                boot_digest: self.local.boot_digest,
                namespace_digest: self.local.namespace_digest,
                configuration_digest: self.local.configuration_digest,
            }),
        })
    }
    /// Validate received ARM directly. No Mac clock, local make_arm, or deadline
    /// recomputation is available to S.
    pub fn receive_arm(
        &mut self,
        now: LinuxInstant,
        frame: &BootstrapFrame,
    ) -> Result<DeadlinePlan, HandshakeError> {
        self.live(now)?;
        let result = self.check_arm(now, frame);
        self.finish(result)
    }
    fn check_arm(
        &mut self,
        now: LinuxInstant,
        frame: &BootstrapFrame,
    ) -> Result<DeadlinePlan, HandshakeError> {
        if self.stage != SupervisorStage::Ready {
            return Err(HandshakeError::Protocol {
                expected: "ARM after READY once",
            });
        }
        binding_equal(&self.binding, &frame.binding)?;
        let BootstrapMessage::Arm(arm) = &frame.message else {
            return Err(HandshakeError::Protocol { expected: "ARM" });
        };
        if arm.query_len != self.start.fields().query_bytes {
            return Err(HandshakeError::Query {
                field: "query_bytes",
            });
        }
        if arm.query_digest != self.start.fields().query_digest {
            return Err(HandshakeError::Query {
                field: "query_digest",
            });
        }
        if arm.deadline_ns > self.preparation_deadline_ns {
            return Err(HandshakeError::Protocol {
                expected: "DL <= preparation deadline",
            });
        }
        if now.0 >= arm.deadline_ns {
            return Err(HandshakeError::Deadline {
                side: ClockSide::Supervisor,
                now_ns: now.0,
                deadline_ns: arm.deadline_ns,
            });
        }
        self.deadline_ns = Some(arm.deadline_ns);
        self.stage = SupervisorStage::Armed;
        Ok(DeadlinePlan {
            deadline: LinuxInstant(arm.deadline_ns),
        })
    }
    pub fn query_complete(
        &mut self,
        now: LinuxInstant,
        binding: &BootstrapBinding,
        bytes: &[u8],
    ) -> Result<QueryCheckedPlan, HandshakeError> {
        self.live(now)?;
        let result = self.check_query(binding, bytes);
        self.finish(result)
    }
    fn check_query(
        &mut self,
        binding: &BootstrapBinding,
        bytes: &[u8],
    ) -> Result<QueryCheckedPlan, HandshakeError> {
        if self.stage != SupervisorStage::Armed {
            return Err(HandshakeError::Protocol {
                expected: "complete query after ARM once",
            });
        }
        binding_equal(&self.binding, binding)?;
        if bytes.len() != self.start.fields().query_bytes as usize {
            return Err(HandshakeError::Query {
                field: "query_bytes",
            });
        }
        self.start
            .validate_query(bytes)
            .map_err(|_| HandshakeError::Query {
                field: "query_digest",
            })?;
        let deadline = self.deadline_ns.ok_or(HandshakeError::Protocol {
            expected: "ARM deadline",
        })?;
        self.stage = SupervisorStage::QueryChecked;
        Ok(QueryCheckedPlan {
            binding: self.binding.clone(),
            deadline: LinuxInstant(deadline),
        })
    }
}
