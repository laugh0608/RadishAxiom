use super::*;
use crate::attempt::BoundedAttemptObservation;
#[cfg(target_os = "macos")]
use crate::attempt::{AttemptDocument, MAX_ATTEMPTS_PER_REGISTRATION};
#[cfg(target_os = "macos")]
use crate::qualification::QUALIFICATION_RECORD_FILENAME;
use crate::qualification::QualificationArtifacts;
#[cfg(target_os = "macos")]
use crate::registration::RegistrationStatus;

#[cfg(target_os = "macos")]
const QUALIFICATIONS_ROOT: &str = "qualifications";
#[cfg(target_os = "macos")]
const QUALIFICATION_STAGING_ROOT: &str = ".qualification-staging";
#[cfg(target_os = "macos")]
const ATTEMPTS_ROOT: &str = "attempts";
#[cfg(target_os = "macos")]
const ATTEMPT_STAGING_ROOT: &str = ".attempt-staging";
#[cfg(target_os = "macos")]
const REGISTRATION_LOCK_ROOT: &str = "registrations";
#[cfg(target_os = "macos")]
const ATTEMPT_FILENAME: &str = "attempt-v0.1.jcs";

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PersistedQualification {
    relative_identity: Box<str>,
    document_digest: Box<str>,
}

impl PersistedQualification {
    pub fn relative_identity(&self) -> &str {
        &self.relative_identity
    }

    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AppendedAttempt {
    relative_identity: Box<str>,
    ordinal: u64,
    document_digest: Box<str>,
}

impl AppendedAttempt {
    pub fn relative_identity(&self) -> &str {
        &self.relative_identity
    }

    pub fn ordinal(&self) -> u64 {
        self.ordinal
    }

    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }
}

#[cfg(target_os = "macos")]
struct HeldRegistrationLock {
    file: File,
}

#[cfg(target_os = "macos")]
impl Drop for HeldRegistrationLock {
    fn drop(&mut self) {
        let _ = self.file.unlock();
    }
}

impl FilesystemStore {
    pub fn create_qualification_exclusive(
        &self,
        record: &RegistrationRecord,
        artifacts: &QualificationArtifacts,
    ) -> Result<PersistedQualification, StoreError> {
        #[cfg(target_os = "macos")]
        {
            if record.status() != RegistrationStatus::RegisteredInactive {
                return Err(StoreError::contract(
                    "qualification-requires-registered-inactive",
                    "$",
                ));
            }
            if artifacts.registration_digest() != record.document_digest() {
                return Err(StoreError::contract(
                    "qualification-registration-binding",
                    "$",
                ));
            }
            let _lock = self.acquire_registration_lock(record)?;
            evidence_crash_checkpoint("qualification-after-lock");
            self.create_qualification_darwin(record, artifacts)
        }
        #[cfg(not(target_os = "macos"))]
        {
            let _ = (record, artifacts);
            Err(StoreError::contract("unsupported-store-capability", "$"))
        }
    }

    pub fn append_attempt(
        &self,
        record: &RegistrationRecord,
        observation: &BoundedAttemptObservation,
    ) -> Result<AppendedAttempt, StoreError> {
        #[cfg(target_os = "macos")]
        {
            let _lock = self.acquire_registration_lock(record)?;
            evidence_crash_checkpoint("attempt-after-lock");
            self.append_attempt_darwin(record, observation)
        }
        #[cfg(not(target_os = "macos"))]
        {
            let _ = (record, observation);
            Err(StoreError::contract("unsupported-store-capability", "$"))
        }
    }

    #[cfg(target_os = "macos")]
    fn acquire_registration_lock(
        &self,
        record: &RegistrationRecord,
    ) -> Result<HeldRegistrationLock, StoreError> {
        let component = registration_component(record);
        let locks = self
            .inner
            .root_directory
            .open_directory(".locks")
            .map_err(|error| StoreError::platform("store-lock-root-boundary", ".locks", error))?;
        let registrations = locks
            .ensure_directory(REGISTRATION_LOCK_ROOT, 0o700)
            .map_err(|error| {
                StoreError::platform(
                    "registration-lock-root-boundary",
                    REGISTRATION_LOCK_ROOT,
                    error,
                )
            })?;
        let filename = format!("{component}.lock");
        let regular = match registrations.create_file_exclusive(&filename, 0o600) {
            Ok(file) => file,
            Err(error) if error.io_kind() == io::ErrorKind::AlreadyExists => registrations
                .open_file_read_write(&filename)
                .map_err(|error| {
                    StoreError::platform("registration-lock-open", &*filename, error)
                })?,
            Err(error) => {
                return Err(StoreError::platform(
                    "registration-lock-open",
                    &*filename,
                    error,
                ));
            }
        };
        regular.validate(0o600).map_err(|error| {
            StoreError::platform("registration-lock-boundary", &*filename, error)
        })?;
        registrations.full_sync().map_err(|error| {
            StoreError::platform("registration-lock-root-sync", &*filename, error)
        })?;
        let file = regular.into_file();
        file.try_lock().map_err(|error| match error {
            fs::TryLockError::WouldBlock => StoreError::io(
                "registration-lock-busy",
                &self.inner.root.join(".locks").join(&filename),
                io::Error::from(io::ErrorKind::WouldBlock),
            ),
            fs::TryLockError::Error(source) => StoreError::io(
                "registration-lock-failed",
                &self.inner.root.join(".locks").join(&filename),
                source,
            ),
        })?;
        Ok(HeldRegistrationLock { file })
    }

    #[cfg(target_os = "macos")]
    fn create_qualification_darwin(
        &self,
        record: &RegistrationRecord,
        artifacts: &QualificationArtifacts,
    ) -> Result<PersistedQualification, StoreError> {
        let final_parent =
            darwin_evidence_parent(&self.inner.root_directory, QUALIFICATIONS_ROOT, record)?;
        let staging_parent = darwin_evidence_parent(
            &self.inner.root_directory,
            QUALIFICATION_STAGING_ROOT,
            record,
        )?;
        let name = digest_component(artifacts.document_digest());
        match final_parent.open_directory(&name) {
            Ok(directory) => {
                verify_qualification_darwin(&directory, artifacts).map_err(|error| {
                    wrap_existing_error("qualification-existing-mismatch", &name, error)
                })?;
                return Err(StoreError::contract("qualification-exists", name));
            }
            Err(error) if error.io_kind() == io::ErrorKind::NotFound => {}
            Err(error) => {
                return Err(StoreError::platform(
                    if error.is_symlink_loop() {
                        "symbolic-link"
                    } else {
                        "qualification-destination-boundary"
                    },
                    &*name,
                    error,
                ));
            }
        }

        let staging = match staging_parent.open_directory(&name) {
            Ok(directory) => match verify_qualification_darwin(&directory, artifacts) {
                Ok(()) => directory,
                Err(_) => {
                    discard_darwin_directory(&staging_parent, &name, directory)?;
                    populate_qualification_darwin(&staging_parent, &name, artifacts)?
                }
            },
            Err(error) if error.io_kind() == io::ErrorKind::NotFound => {
                populate_qualification_darwin(&staging_parent, &name, artifacts)?
            }
            Err(error) => {
                return Err(StoreError::platform(
                    "qualification-staging-boundary",
                    &*name,
                    error,
                ));
            }
        };
        evidence_crash_checkpoint("qualification-after-artifacts");
        verify_qualification_darwin(&staging, artifacts)?;
        staging
            .full_sync()
            .map_err(|error| StoreError::platform("qualification-staging-sync", &*name, error))?;
        staging_parent.full_sync().map_err(|error| {
            StoreError::platform("qualification-staging-parent-sync", &*name, error)
        })?;
        evidence_crash_checkpoint("qualification-after-verify");

        if let Err(error) = staging_parent.rename_directory_exclusive(&name, &final_parent, &name) {
            if error.io_kind() == io::ErrorKind::AlreadyExists {
                let final_directory = final_parent.open_directory(&name).map_err(|error| {
                    StoreError::platform("qualification-destination-boundary", &*name, error)
                })?;
                verify_qualification_darwin(&final_directory, artifacts).map_err(|error| {
                    wrap_existing_error("qualification-existing-mismatch", &name, error)
                })?;
                discard_darwin_named_staging(&staging_parent, &name)?;
                return Err(StoreError::contract("qualification-exists", name));
            }
            return Err(StoreError::platform(
                if error.is_symlink_loop() {
                    "symbolic-link"
                } else if error.is_cross_device() {
                    "cross-filesystem-qualification"
                } else if error.is_unsupported_capability() {
                    "unsupported-store-capability"
                } else {
                    "qualification-publish-rename"
                },
                &*name,
                error,
            ));
        }
        evidence_crash_checkpoint("qualification-after-rename");
        final_parent
            .full_sync()
            .map_err(|error| StoreError::platform("qualification-parent-sync", &*name, error))?;
        staging_parent.full_sync().map_err(|error| {
            StoreError::platform("qualification-staging-parent-sync", &*name, error)
        })?;
        evidence_crash_checkpoint("qualification-after-parent-sync");
        let final_directory = final_parent.open_directory(&name).map_err(|error| {
            StoreError::platform("qualification-post-publication", &*name, error)
        })?;
        verify_qualification_darwin(&final_directory, artifacts)?;
        Ok(PersistedQualification {
            relative_identity: qualification_relative_identity(record, artifacts).into(),
            document_digest: artifacts.document_digest().into(),
        })
    }

    #[cfg(target_os = "macos")]
    fn append_attempt_darwin(
        &self,
        record: &RegistrationRecord,
        observation: &BoundedAttemptObservation,
    ) -> Result<AppendedAttempt, StoreError> {
        let final_parent =
            darwin_evidence_parent(&self.inner.root_directory, ATTEMPTS_ROOT, record)?;
        let existing = read_attempt_inventory_darwin(&final_parent, record)?;
        let ordinal = u64::try_from(existing.len())
            .map_err(|_| StoreError::contract("attempt-capacity", "$"))?;
        if ordinal >= MAX_ATTEMPTS_PER_REGISTRATION {
            return Err(StoreError::contract("attempt-capacity", "$"));
        }
        let attempt = AttemptDocument::build(record, ordinal, observation)
            .map_err(|error| document_store_error("attempt-input", error))?;
        let name = attempt_name(&attempt);
        let staging_parent =
            darwin_evidence_parent(&self.inner.root_directory, ATTEMPT_STAGING_ROOT, record)?;
        let staging = match staging_parent.open_directory(&name) {
            Ok(directory) => match verify_attempt_darwin(&directory, record, &attempt) {
                Ok(()) => directory,
                Err(_) => {
                    discard_darwin_directory(&staging_parent, &name, directory)?;
                    populate_attempt_darwin(&staging_parent, &name, &attempt)?
                }
            },
            Err(error) if error.io_kind() == io::ErrorKind::NotFound => {
                populate_attempt_darwin(&staging_parent, &name, &attempt)?
            }
            Err(error) => {
                return Err(StoreError::platform(
                    "attempt-staging-boundary",
                    &*name,
                    error,
                ));
            }
        };
        evidence_crash_checkpoint("attempt-after-file");
        verify_attempt_darwin(&staging, record, &attempt)?;
        staging
            .full_sync()
            .map_err(|error| StoreError::platform("attempt-staging-sync", &*name, error))?;
        staging_parent
            .full_sync()
            .map_err(|error| StoreError::platform("attempt-staging-parent-sync", &*name, error))?;
        evidence_crash_checkpoint("attempt-after-verify");
        if let Err(error) = staging_parent.rename_directory_exclusive(&name, &final_parent, &name) {
            if error.io_kind() == io::ErrorKind::AlreadyExists {
                let final_directory = final_parent.open_directory(&name).map_err(|error| {
                    StoreError::platform("attempt-destination-boundary", &*name, error)
                })?;
                verify_attempt_darwin(&final_directory, record, &attempt).map_err(|error| {
                    wrap_existing_error("attempt-existing-mismatch", &name, error)
                })?;
                discard_darwin_named_staging(&staging_parent, &name)?;
            } else {
                return Err(StoreError::platform(
                    if error.is_symlink_loop() {
                        "symbolic-link"
                    } else if error.is_cross_device() {
                        "cross-filesystem-attempt"
                    } else if error.is_unsupported_capability() {
                        "unsupported-store-capability"
                    } else {
                        "attempt-publish-rename"
                    },
                    &*name,
                    error,
                ));
            }
        }
        evidence_crash_checkpoint("attempt-after-rename");
        final_parent
            .full_sync()
            .map_err(|error| StoreError::platform("attempt-parent-sync", &*name, error))?;
        staging_parent
            .full_sync()
            .map_err(|error| StoreError::platform("attempt-staging-parent-sync", &*name, error))?;
        evidence_crash_checkpoint("attempt-after-parent-sync");
        let final_directory = final_parent
            .open_directory(&name)
            .map_err(|error| StoreError::platform("attempt-post-publication", &*name, error))?;
        verify_attempt_darwin(&final_directory, record, &attempt)?;
        Ok(AppendedAttempt {
            relative_identity: attempt_relative_identity(record, &name).into(),
            ordinal,
            document_digest: attempt.document_digest().into(),
        })
    }
}

#[cfg(target_os = "macos")]
fn registration_component(record: &RegistrationRecord) -> String {
    digest_component(record.document_digest())
}

#[cfg(target_os = "macos")]
fn digest_component(digest: &str) -> String {
    format!(
        "sha256-{}",
        digest.strip_prefix("sha256:").unwrap_or("invalid")
    )
}

#[cfg(target_os = "macos")]
fn qualification_relative_identity(
    record: &RegistrationRecord,
    artifacts: &QualificationArtifacts,
) -> String {
    evidence_relative_parent(QUALIFICATIONS_ROOT, record)
        + "/"
        + &digest_component(artifacts.document_digest())
}

#[cfg(target_os = "macos")]
fn attempt_relative_identity(record: &RegistrationRecord, name: &str) -> String {
    evidence_relative_parent(ATTEMPTS_ROOT, record) + "/" + name
}

#[cfg(target_os = "macos")]
fn evidence_relative_parent(root: &str, record: &RegistrationRecord) -> String {
    let target = record.target();
    format!(
        "{root}/{}/{}/{}/{}/{}",
        target.goos(),
        target.goarch(),
        target.variant(),
        target.executable_format(),
        registration_component(record),
    )
}

#[cfg(target_os = "macos")]
fn attempt_name(attempt: &AttemptDocument) -> String {
    format!(
        "{:020}-{}",
        attempt.ordinal(),
        digest_component(attempt.document_digest())
    )
}

#[cfg(target_os = "macos")]
fn parse_attempt_name(name: &str) -> Result<(u64, String), StoreError> {
    if name.len() != 92 || name.as_bytes().get(20) != Some(&b'-') {
        return Err(StoreError::contract("attempt-inventory", name));
    }
    let ordinal_text = &name[..20];
    if !ordinal_text.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err(StoreError::contract("attempt-inventory", name));
    }
    let ordinal = ordinal_text
        .parse::<u64>()
        .map_err(|_| StoreError::contract("attempt-inventory", name))?;
    if format!("{ordinal:020}") != ordinal_text {
        return Err(StoreError::contract("attempt-inventory", name));
    }
    let digest = &name[21..];
    let Some(hex) = digest.strip_prefix("sha256-") else {
        return Err(StoreError::contract("attempt-inventory", name));
    };
    if hex.len() != 64
        || !hex
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
    {
        return Err(StoreError::contract("attempt-inventory", name));
    }
    Ok((ordinal, format!("sha256:{hex}")))
}

#[cfg(target_os = "macos")]
fn darwin_evidence_parent(
    root: &DarwinDirectory,
    top: &str,
    record: &RegistrationRecord,
) -> Result<DarwinDirectory, StoreError> {
    let top_directory = root
        .ensure_directory(top, 0o700)
        .map_err(|error| StoreError::platform("evidence-root-boundary", top, error))?;
    let target = darwin_target_parent(&top_directory, record.target(), 0o700)?;
    let format = target
        .ensure_directory(record.target().executable_format(), 0o700)
        .map_err(|error| {
            StoreError::platform(
                "evidence-target-boundary",
                record.target().executable_format(),
                error,
            )
        })?;
    let registration = registration_component(record);
    let result = format
        .ensure_directory(&registration, 0o700)
        .map_err(|error| {
            StoreError::platform("evidence-registration-boundary", &*registration, error)
        })?;
    let relative = evidence_relative_parent(top, record);
    darwin_sync_directory_chain(root, &relative)
        .map_err(|error| wrap_existing_error("evidence-parent-sync", &relative, error))?;
    Ok(result)
}

#[cfg(target_os = "macos")]
fn populate_qualification_darwin(
    parent: &DarwinDirectory,
    name: &str,
    artifacts: &QualificationArtifacts,
) -> Result<DarwinDirectory, StoreError> {
    let directory = parent
        .create_directory_exclusive(name, 0o700)
        .map_err(|error| StoreError::platform("qualification-staging-create", name, error))?;
    write_darwin_file(
        &directory,
        QUALIFICATION_RECORD_FILENAME,
        artifacts.qualification_record(),
        "qualification-record",
    )?;
    let companions = directory
        .create_directory_exclusive("companions", 0o700)
        .map_err(|error| {
            StoreError::platform("qualification-companion-root-create", "companions", error)
        })?;
    for companion in artifacts.companions() {
        write_darwin_file(
            &companions,
            &format!("{}.jcs", companion.scenario_id()),
            companion.canonical_result(),
            "qualification-companion",
        )?;
    }
    companions.full_sync().map_err(|error| {
        StoreError::platform("qualification-companion-root-sync", "companions", error)
    })?;
    directory
        .full_sync()
        .map_err(|error| StoreError::platform("qualification-staging-sync", name, error))?;
    Ok(directory)
}

#[cfg(target_os = "macos")]
fn verify_qualification_darwin(
    directory: &DarwinDirectory,
    artifacts: &QualificationArtifacts,
) -> Result<(), StoreError> {
    if directory
        .mode()
        .map_err(|error| StoreError::platform("qualification-directory-boundary", "$", error))?
        != 0o700
        || directory
            .entry_names()
            .map_err(|error| StoreError::platform("qualification-inventory", "$", error))?
            != ["companions", QUALIFICATION_RECORD_FILENAME]
    {
        return Err(StoreError::contract("qualification-inventory", "$"));
    }
    verify_darwin_file(
        directory,
        QUALIFICATION_RECORD_FILENAME,
        artifacts.qualification_record(),
        "qualification-record",
    )?;
    let companions = directory.open_directory("companions").map_err(|error| {
        StoreError::platform("qualification-companion-root-boundary", "companions", error)
    })?;
    if companions.mode().map_err(|error| {
        StoreError::platform("qualification-companion-root-boundary", "companions", error)
    })? != 0o700
    {
        return Err(StoreError::contract(
            "qualification-companion-root-boundary",
            "companions",
        ));
    }
    let expected: Vec<String> = artifacts
        .companions()
        .iter()
        .map(|companion| format!("{}.jcs", companion.scenario_id()))
        .collect();
    if companions.entry_names().map_err(|error| {
        StoreError::platform("qualification-companion-inventory", "companions", error)
    })? != expected
    {
        return Err(StoreError::contract(
            "qualification-companion-inventory",
            "companions",
        ));
    }
    for companion in artifacts.companions() {
        verify_darwin_file(
            &companions,
            &format!("{}.jcs", companion.scenario_id()),
            companion.canonical_result(),
            "qualification-companion",
        )?;
    }
    Ok(())
}

#[cfg(target_os = "macos")]
fn populate_attempt_darwin(
    parent: &DarwinDirectory,
    name: &str,
    attempt: &AttemptDocument,
) -> Result<DarwinDirectory, StoreError> {
    let directory = parent
        .create_directory_exclusive(name, 0o700)
        .map_err(|error| StoreError::platform("attempt-staging-create", name, error))?;
    write_darwin_file(
        &directory,
        ATTEMPT_FILENAME,
        attempt.canonical_bytes(),
        "attempt",
    )?;
    directory
        .full_sync()
        .map_err(|error| StoreError::platform("attempt-staging-sync", name, error))?;
    Ok(directory)
}

#[cfg(target_os = "macos")]
fn verify_attempt_darwin(
    directory: &DarwinDirectory,
    record: &RegistrationRecord,
    expected: &AttemptDocument,
) -> Result<(), StoreError> {
    if directory
        .mode()
        .map_err(|error| StoreError::platform("attempt-directory-boundary", "$", error))?
        != 0o700
        || directory
            .entry_names()
            .map_err(|error| StoreError::platform("attempt-inventory", "$", error))?
            != [ATTEMPT_FILENAME]
    {
        return Err(StoreError::contract("attempt-inventory", "$"));
    }
    let bytes = verify_darwin_file(
        directory,
        ATTEMPT_FILENAME,
        expected.canonical_bytes(),
        "attempt",
    )?;
    let parsed = AttemptDocument::parse(&bytes, record)
        .map_err(|error| document_store_error("attempt-document", error))?;
    if &parsed != expected {
        return Err(StoreError::contract("attempt-document-mismatch", "$"));
    }
    Ok(())
}

#[cfg(target_os = "macos")]
fn read_attempt_inventory_darwin(
    parent: &DarwinDirectory,
    record: &RegistrationRecord,
) -> Result<Vec<AttemptDocument>, StoreError> {
    let names = parent
        .entry_names()
        .map_err(|error| StoreError::platform("attempt-inventory", "$", error))?;
    let mut attempts = Vec::with_capacity(names.len());
    for (expected_ordinal, name) in names.iter().enumerate() {
        let (ordinal, path_digest) = parse_attempt_name(name)?;
        if ordinal != expected_ordinal as u64 {
            return Err(StoreError::contract("attempt-inventory-gap", name.as_str()));
        }
        let directory = parent
            .open_directory(name)
            .map_err(|error| StoreError::platform("attempt-directory-boundary", &**name, error))?;
        if directory
            .mode()
            .map_err(|error| StoreError::platform("attempt-directory-boundary", &**name, error))?
            != 0o700
            || directory
                .entry_names()
                .map_err(|error| StoreError::platform("attempt-inventory", &**name, error))?
                != [ATTEMPT_FILENAME]
        {
            return Err(StoreError::contract("attempt-inventory", name.as_str()));
        }
        let mut file = directory.open_file(ATTEMPT_FILENAME).map_err(|error| {
            StoreError::platform("attempt-file-boundary", ATTEMPT_FILENAME, error)
        })?;
        file.validate(0o644).map_err(|error| {
            StoreError::platform("attempt-file-boundary", ATTEMPT_FILENAME, error)
        })?;
        let bytes = file
            .read_all()
            .map_err(|error| StoreError::platform("attempt-file-read", ATTEMPT_FILENAME, error))?;
        let attempt = AttemptDocument::parse(&bytes, record)
            .map_err(|error| document_store_error("attempt-document", error))?;
        if attempt.ordinal() != ordinal || attempt.document_digest() != path_digest {
            return Err(StoreError::contract(
                "attempt-inventory-binding",
                name.as_str(),
            ));
        }
        attempts.push(attempt);
    }
    Ok(attempts)
}

#[cfg(target_os = "macos")]
fn write_darwin_file(
    parent: &DarwinDirectory,
    name: &str,
    bytes: &[u8],
    kind: &'static str,
) -> Result<(), StoreError> {
    let mut file = parent.create_file_exclusive(name, 0o644).map_err(|error| {
        StoreError::platform(
            if error.io_kind() == io::ErrorKind::AlreadyExists {
                "evidence-entry-exists"
            } else {
                "evidence-file-create"
            },
            name,
            error,
        )
    })?;
    file.write_all(bytes)
        .map_err(|error| StoreError::platform("evidence-file-write", kind, error))?;
    file.full_sync()
        .map_err(|error| StoreError::platform("evidence-file-sync", kind, error))?;
    file.validate(0o644)
        .map_err(|error| StoreError::platform("evidence-file-boundary", kind, error))
}

#[cfg(target_os = "macos")]
fn verify_darwin_file(
    parent: &DarwinDirectory,
    name: &str,
    expected: &[u8],
    kind: &'static str,
) -> Result<Vec<u8>, StoreError> {
    let mut file = parent
        .open_file(name)
        .map_err(|error| StoreError::platform("evidence-file-boundary", kind, error))?;
    file.validate(0o644)
        .map_err(|error| StoreError::platform("evidence-file-boundary", kind, error))?;
    let bytes = file
        .read_all()
        .map_err(|error| StoreError::platform("evidence-file-read", kind, error))?;
    if bytes != expected {
        return Err(StoreError::contract("evidence-byte-mismatch", kind));
    }
    Ok(bytes)
}

#[cfg(target_os = "macos")]
fn discard_darwin_directory(
    parent: &DarwinDirectory,
    name: &str,
    directory: DarwinDirectory,
) -> Result<(), StoreError> {
    directory
        .remove_tree_contents()
        .map_err(|error| StoreError::platform("evidence-staging-discard", name, error))?;
    drop(directory);
    parent
        .remove_directory(name)
        .map_err(|error| StoreError::platform("evidence-staging-discard", name, error))?;
    parent
        .full_sync()
        .map_err(|error| StoreError::platform("evidence-staging-parent-sync", name, error))
}

#[cfg(target_os = "macos")]
fn discard_darwin_named_staging(parent: &DarwinDirectory, name: &str) -> Result<(), StoreError> {
    let directory = parent
        .open_directory(name)
        .map_err(|error| StoreError::platform("evidence-staging-boundary", name, error))?;
    discard_darwin_directory(parent, name, directory)
}

#[cfg(target_os = "macos")]
fn document_store_error(code: &'static str, error: crate::DocumentError) -> StoreError {
    StoreError {
        code,
        path: error.path().into(),
        source: Some(Box::new(error)),
    }
}

#[cfg(target_os = "macos")]
fn wrap_existing_error(code: &'static str, path: &str, error: StoreError) -> StoreError {
    StoreError {
        code,
        path: path.into(),
        source: Some(Box::new(error)),
    }
}

#[cfg(all(test, target_os = "macos"))]
fn evidence_crash_checkpoint(name: &str) {
    super::test_crash_checkpoint(name);
}

#[cfg(all(not(test), target_os = "macos"))]
fn evidence_crash_checkpoint(_name: &str) {}
