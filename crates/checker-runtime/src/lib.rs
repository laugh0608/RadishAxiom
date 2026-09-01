#![forbid(unsafe_code)]

mod archive;
mod canonical;
mod policy;
mod portable_path;
mod receipt;
mod registration;
mod selection;
mod sha256;
mod store;

pub use archive::{
    ArchiveMemberExpectation, ArchiveValidationError, CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER,
    CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER, ValidatedArchiveMember, validate_ustar,
};
pub use canonical::DocumentError;
pub use policy::{InstallationLayout, LauncherPolicy, parse_launcher_policy};
pub use receipt::{
    InstallationReceipt, InstallationVerifierIdentity, build_installation_receipt,
    parse_installation_receipt,
};
pub use registration::{
    ArtifactIdentity, CheckerIdentity, ProviderReleaseIdentity, RegistrationRecord,
    RegistrationStatus, parse_registration_record,
};
pub use selection::{
    NativeHostIdentity, NativeProcessMode, NativeTarget, SelectionError, SelectionPurpose,
    select_registration,
};
pub use store::{
    CHECKER_RUNTIME_STORE_INTERFACE, FilesystemStore, HeldTargetLock, InstalledInactiveSlot,
    OwnedStaging, SlotPublication, SlotPublishAction, SlotVerification, StagingRecovery,
    StoreError, StoreTransactionIdentity, VerifiedStaging,
};
