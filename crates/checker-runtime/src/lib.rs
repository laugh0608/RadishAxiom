#![forbid(unsafe_code)]

mod archive;
mod attempt;
mod canonical;
mod manifest;
mod policy;
mod portable_path;
mod qualification;
mod receipt;
mod registration;
mod result;
mod selection;
mod sha256;
mod spawn;
mod store;

pub use archive::{
    ArchiveMemberExpectation, ArchiveValidationError, CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER,
    CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER, ValidatedArchiveMember, validate_ustar,
};
pub use attempt::{
    AttemptClassification, AttemptStage, BoundedAttemptObservation, MAX_ATTEMPT_OBSERVATION_BYTES,
    MAX_ATTEMPTS_PER_REGISTRATION,
};
pub use canonical::DocumentError;
pub use manifest::{
    MAX_CHECKER_RUNTIME_MANIFEST_BYTES, PayloadManifestContent, PayloadManifestIdentity,
    ValidatedPayloadManifest, ValidatedPayloadManifests, validate_payload_manifests,
};
pub use policy::{InstallationLayout, LauncherPolicy, parse_launcher_policy};
pub use qualification::{
    MAX_QUALIFICATION_COMPANION_BYTES, MAX_QUALIFICATION_RECORD_BYTES, QualificationArtifacts,
    QualificationCompanionInput,
};
pub use receipt::{
    InstallationReceipt, InstallationVerifierIdentity, build_installation_receipt,
    parse_installation_receipt,
};
pub use registration::{
    ArtifactIdentity, CheckerIdentity, ProviderReleaseIdentity, RegistrationRecord,
    RegistrationStatus, parse_registration_record,
};
pub use result::{
    CheckerInvocationFailure, ConsumedIndependentResult, IndependentCheckOutcome,
    IndependentDocumentBinding, MAX_INDEPENDENT_RESULT_BYTES, MAX_INVOCATION_FAILURE_BYTES,
    consume_independent_result, parse_checker_invocation_failure,
};
pub use selection::{
    NativeHostIdentity, NativeProcessMode, NativeTarget, SelectionError, SelectionPurpose,
    select_registration,
};
pub use spawn::{
    CHECKER_STDERR_LIMIT_BYTES, CHECKER_STDOUT_LIMIT_BYTES, CHECKER_WALL_CLOCK_LIMIT_MILLIS,
    CHECKER_WORKING_MEMORY_LIMIT_BYTES, CheckerProcessOutcome, CheckerSpawnPlan,
    ExecutableIdentityObservation, ExecutionProfileContract, FilesystemObjectIdentity,
    IsolatedWorkingDirectoryObservation, MAX_EXECUTION_PROFILE_MANIFEST_BYTES,
    NativeIsolationStatus, OuterFailureClassification, OuterInvocationFailure,
    PostflightExecutableObservation, ProcessObservation, ProcessTerminationObservation,
    ReadonlyBundleObservation, SpawnPurpose, StreamCapture, consume_process_observation,
};
pub use store::{
    AppendedAttempt, CHECKER_RUNTIME_STORE_INTERFACE, FilesystemStore, HeldTargetLock,
    InstalledInactiveSlot, OwnedStaging, PersistedQualification, SlotPublication,
    SlotPublishAction, SlotVerification, StagingRecovery, StoreError, StoreTransactionIdentity,
    VerifiedStaging,
};
