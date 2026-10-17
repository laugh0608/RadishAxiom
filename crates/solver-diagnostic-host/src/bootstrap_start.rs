//! Pure startup declaration planning from a strictly reconstructed request.
//! This does not accept E0/E4 records or authenticate their source, and grants no
//! execution capability. Future OS adapters must perform those separate checks.
//!
//! Simulation identities cannot be passed as startup declarations.
//! ```compile_fail
//! use radishaxiom_solver_diagnostic_host::{SimulationIdentity, bootstrap_start::StartMaterialDeclarations};
//! fn mixed(identity: SimulationIdentity) {
//!     let declaration: StartMaterialDeclarations = identity;
//! }
//! ```
use radishaxiom_ir::solver::{
    PROCESS_LIMITS, SolverBudgets, SolverError, SolverProfile, SolverRequest, SolverRequestInput,
    check_solver_request,
};
use radishaxiom_solver_supervision_core::{
    bootstrap_start::{StartDescription, StartError, StartFields},
    handshake::HandshakeWindow,
};
use std::fmt;

/// Unauthenticated input claims. They are deliberately separate from
/// SimulationIdentity, any future E0 acceptance, and any future E4 capability.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StartMaterialDeclarations {
    pub attempt: [u8; 32],
    pub policy_bundle: [u8; 32],
    pub image: [u8; 32],
    pub configuration: [u8; 32],
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum StartupPlanError {
    Solver(SolverError),
    Start(StartError),
    Binding { field: &'static str },
    ClockWindowOverflow,
}
impl fmt::Display for StartupPlanError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "bootstrap startup declaration plan: {self:?}")
    }
}
impl std::error::Error for StartupPlanError {}

pub struct StartupDeclarationPlan {
    request: SolverRequest,
    description: StartDescription,
}
impl StartupDeclarationPlan {
    /// Rebuilds bytes from the original semantic inputs before binding actual
    /// query bytes. There is no caller boolean to opt into execution.
    pub fn from_request_bytes(
        request_bytes: &[u8],
        profile: SolverProfile,
        input: SolverRequestInput<'_>,
        budgets: impl Into<SolverBudgets>,
        declarations: StartMaterialDeclarations,
        actual_query: &[u8],
    ) -> Result<Self, StartupPlanError> {
        let request = check_solver_request(request_bytes, profile, input, budgets)
            .map_err(StartupPlanError::Solver)?;
        if profile != SolverProfile::Cvc5Query0_3ModelV0_1 {
            return Err(StartupPlanError::Binding { field: "profile" });
        }
        if request.tool().platform() != "linux-arm64" {
            return Err(StartupPlanError::Binding {
                field: "tool.platform",
            });
        }
        let query_bytes =
            u32::try_from(request.stdin_bytes().len()).map_err(|_| StartupPlanError::Binding {
                field: "query_bytes",
            })?;
        let description = StartDescription::new(
            StartFields {
                attempt: declarations.attempt,
                request: radishaxiom_digest::digest(request.canonical_bytes()),
                query_bytes,
                query_digest: radishaxiom_digest::digest(request.stdin_bytes()),
                policy_bundle: declarations.policy_bundle,
                image: declarations.image,
                cli_acceptance: request_acceptance_digest(
                    request.tool().acceptance_record_digest(),
                )?,
                configuration: declarations.configuration,
            },
            crate::e3_wire::process_wire_limits(),
        )
        .map_err(StartupPlanError::Start)?;
        description
            .validate_query(actual_query)
            .map_err(StartupPlanError::Start)?;
        Ok(Self {
            request,
            description,
        })
    }
    pub fn request(&self) -> &SolverRequest {
        &self.request
    }
    pub fn description(&self) -> &StartDescription {
        &self.description
    }
    pub fn scope(&self) -> &'static str {
        "external-declaration-check-and-plan"
    }
}
/// One resource source; pure core has no independently evolving defaults.
pub fn process_handshake_window() -> Result<HandshakeWindow, StartupPlanError> {
    let wall_clock_ns = PROCESS_LIMITS
        .wall_clock_ms
        .checked_mul(1_000_000)
        .ok_or(StartupPlanError::ClockWindowOverflow)?;
    Ok(HandshakeWindow { wall_clock_ns })
}
fn request_acceptance_digest(text: &str) -> Result<[u8; 32], StartupPlanError> {
    let hex = text
        .strip_prefix("sha256:")
        .filter(|s| s.len() == 64)
        .ok_or(StartupPlanError::Binding {
            field: "tool.acceptance_record_digest",
        })?;
    let mut digest = [0; 32];
    for (index, pair) in hex.as_bytes().chunks_exact(2).enumerate() {
        let mut value = 0;
        for byte in pair {
            let digit = match byte {
                b'0'..=b'9' => byte - b'0',
                b'a'..=b'f' => byte - b'a' + 10,
                _ => {
                    return Err(StartupPlanError::Binding {
                        field: "tool.acceptance_record_digest",
                    });
                }
            };
            value = value * 16 + digit;
        }
        digest[index] = value;
    }
    Ok(digest)
}
