#![forbid(unsafe_code)]

mod archive;
mod canonical;
mod policy;
mod registration;
mod selection;
mod sha256;

pub use archive::{
    ArchiveMemberExpectation, ArchiveValidationError, CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER,
    CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER, ValidatedArchiveMember, validate_ustar,
};
pub use canonical::DocumentError;
pub use policy::{LauncherPolicy, parse_launcher_policy};
pub use registration::{
    ArtifactIdentity, CheckerIdentity, RegistrationRecord, RegistrationStatus,
    parse_registration_record,
};
pub use selection::{
    NativeHostIdentity, NativeProcessMode, NativeTarget, SelectionError, SelectionPurpose,
    select_registration,
};
