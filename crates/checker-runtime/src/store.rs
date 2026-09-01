use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;
use std::fs::{self, File};
use std::io;
use std::path::{Path, PathBuf};
use std::sync::Arc;

#[cfg(not(target_os = "macos"))]
use std::fs::OpenOptions;
#[cfg(not(target_os = "macos"))]
use std::io::{Read, Write};

#[cfg(target_os = "macos")]
use radishaxiom_checker_runtime_darwin_store::{
    Directory as DarwinDirectory, Entry as DarwinEntry, PlatformError, RegularFile as DarwinFile,
};

#[cfg(all(unix, any(test, not(target_os = "macos"))))]
use std::os::unix::fs::PermissionsExt;
#[cfg(all(unix, not(target_os = "macos")))]
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};

use crate::canonical::{Value, domain_digest_value};
use crate::policy::LauncherPolicy;
use crate::portable_path::validate_portable_relative_path;
use crate::receipt::{parse_installation_receipt, slot_relative_identity};
use crate::registration::RegistrationRecord;
use crate::selection::NativeTarget;
use crate::sha256::digest_hex;

mod evidence;

pub use evidence::{AppendedAttempt, PersistedQualification};

pub const CHECKER_RUNTIME_STORE_INTERFACE: &str = "checker-runtime-store-v0.1";
const SLOT_TREE_DOMAIN: &str = "radishaxiom.checker-runtime-slot-tree.v0.1";

#[derive(Debug)]
pub struct StoreError {
    code: &'static str,
    path: Box<str>,
    source: Option<Box<dyn Error + Send + Sync>>,
}

impl StoreError {
    fn contract(code: &'static str, path: impl Into<Box<str>>) -> Self {
        Self {
            code,
            path: path.into(),
            source: None,
        }
    }

    fn io(code: &'static str, path: &Path, source: io::Error) -> Self {
        Self {
            code,
            path: path.display().to_string().into(),
            source: Some(Box::new(source)),
        }
    }

    #[cfg(target_os = "macos")]
    fn platform(code: &'static str, path: impl Into<Box<str>>, source: PlatformError) -> Self {
        Self {
            code,
            path: path.into(),
            source: Some(Box::new(source)),
        }
    }

    pub fn code(&self) -> &'static str {
        self.code
    }

    pub fn path(&self) -> &str {
        &self.path
    }
}

impl fmt::Display for StoreError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}: {}", self.code, self.path)?;
        if let Some(source) = &self.source {
            write!(formatter, ": {source}")?;
        }
        Ok(())
    }
}

impl Error for StoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        self.source
            .as_deref()
            .map(|source| source as &(dyn Error + 'static))
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StoreTransactionIdentity(Box<str>);

impl StoreTransactionIdentity {
    pub fn try_new(value: impl Into<Box<str>>) -> Result<Self, StoreError> {
        let value = value.into();
        if value.len() > 96
            || value.contains('/')
            || validate_portable_relative_path(&value).is_err()
        {
            return Err(StoreError::contract("invalid-transaction-identity", "$"));
        }
        Ok(Self(value))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone)]
pub struct FilesystemStore {
    inner: Arc<StoreInner>,
}

struct StoreInner {
    root: PathBuf,
    #[cfg(target_os = "macos")]
    root_directory: DarwinDirectory,
}

pub struct HeldTargetLock {
    store: Arc<StoreInner>,
    target: NativeTarget,
    file: File,
}

impl HeldTargetLock {
    pub fn target(&self) -> &NativeTarget {
        &self.target
    }
}

impl Drop for HeldTargetLock {
    fn drop(&mut self) {
        let _ = self.file.unlock();
    }
}

pub struct OwnedStaging {
    store: Arc<StoreInner>,
    target: NativeTarget,
    transaction: StoreTransactionIdentity,
    path: PathBuf,
    #[cfg(target_os = "macos")]
    parent_directory: DarwinDirectory,
    #[cfg(target_os = "macos")]
    directory: DarwinDirectory,
}

impl OwnedStaging {
    pub fn transaction(&self) -> &StoreTransactionIdentity {
        &self.transaction
    }

    pub fn create_directory(&self, relative_path: &str) -> Result<(), StoreError> {
        validate_staging_relative_path(relative_path)?;
        #[cfg(target_os = "macos")]
        {
            let mut current = self.directory.try_clone().map_err(|error| {
                StoreError::platform("staging-directory-boundary", relative_path, error)
            })?;
            for component in relative_path.split('/') {
                current = current
                    .ensure_directory(component, 0o755)
                    .map_err(|error| {
                        StoreError::platform("staging-directory-boundary", relative_path, error)
                    })?;
            }
            Ok(())
        }
        #[cfg(not(target_os = "macos"))]
        {
            let mut current = self.path.clone();
            for component in relative_path.split('/') {
                current.push(component);
                ensure_directory(&current, 0o755, "staging-directory-boundary")?;
            }
            Ok(())
        }
    }

    pub fn write_file_exclusive(
        &self,
        relative_path: &str,
        contents: &[u8],
        mode: u32,
    ) -> Result<(), StoreError> {
        validate_staging_relative_path(relative_path)?;
        if !matches!(mode, 0o644 | 0o755) {
            return Err(StoreError::contract("staging-file-mode", relative_path));
        }
        #[cfg(target_os = "macos")]
        {
            let (parent_path, filename) = split_parent(relative_path)?;
            let parent =
                darwin_open_directory_chain(&self.directory, parent_path).map_err(|error| {
                    StoreError::platform("staging-parent-boundary", relative_path, error)
                })?;
            let mut file = parent
                .create_file_exclusive(filename, mode)
                .map_err(|error| {
                    StoreError::platform(
                        if error.io_kind() == io::ErrorKind::AlreadyExists {
                            "staging-entry-exists"
                        } else {
                            "staging-file-create"
                        },
                        relative_path,
                        error,
                    )
                })?;
            file.write_all(contents).map_err(|error| {
                StoreError::platform("staging-file-write", relative_path, error)
            })?;
            file.full_sync()
                .map_err(|error| StoreError::platform("staging-file-sync", relative_path, error))?;
            file.validate(mode).map_err(|error| {
                StoreError::platform("staging-file-boundary", relative_path, error)
            })?;
            Ok(())
        }
        #[cfg(not(target_os = "macos"))]
        {
            let destination = join_portable(&self.path, relative_path);
            let parent = destination
                .parent()
                .ok_or_else(|| StoreError::contract("staging-parent-boundary", relative_path))?;
            validate_directory(parent, 0o755, "staging-parent-boundary")?;

            let mut options = OpenOptions::new();
            options.write(true).create_new(true);
            #[cfg(unix)]
            options.mode(mode);
            let mut file = options.open(&destination).map_err(|error| {
                StoreError::io(
                    if error.kind() == io::ErrorKind::AlreadyExists {
                        "staging-entry-exists"
                    } else {
                        "staging-file-create"
                    },
                    &destination,
                    error,
                )
            })?;
            file.write_all(contents)
                .map_err(|error| StoreError::io("staging-file-write", &destination, error))?;
            file.sync_all()
                .map_err(|error| StoreError::io("staging-file-sync", &destination, error))?;
            set_mode(&destination, mode)?;
            validate_regular_file(&destination, mode, "staging-file-boundary")?;
            Ok(())
        }
    }
}

pub struct VerifiedStaging {
    staging: OwnedStaging,
    policy: LauncherPolicy,
    record: RegistrationRecord,
    verification: SlotVerification,
    slot_relative_identity: Box<str>,
}

impl VerifiedStaging {
    pub fn verification(&self) -> &SlotVerification {
        &self.verification
    }

    pub fn slot_relative_identity(&self) -> &str {
        &self.slot_relative_identity
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SlotVerification {
    artifact_raw_sha256: Box<str>,
    artifact_byte_length: u64,
    receipt_document_digest: Box<str>,
    tree_digest: Box<str>,
}

impl SlotVerification {
    pub fn artifact_raw_sha256(&self) -> &str {
        &self.artifact_raw_sha256
    }

    pub fn artifact_byte_length(&self) -> u64 {
        self.artifact_byte_length
    }

    pub fn receipt_document_digest(&self) -> &str {
        &self.receipt_document_digest
    }

    pub fn tree_digest(&self) -> &str {
        &self.tree_digest
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SlotPublishAction {
    Published,
    Reused,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InstalledInactiveSlot {
    relative_identity: Box<str>,
    verification: SlotVerification,
}

impl InstalledInactiveSlot {
    pub fn relative_identity(&self) -> &str {
        &self.relative_identity
    }

    pub fn verification(&self) -> &SlotVerification {
        &self.verification
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SlotPublication {
    slot: InstalledInactiveSlot,
    action: SlotPublishAction,
}

impl SlotPublication {
    pub fn slot(&self) -> &InstalledInactiveSlot {
        &self.slot
    }

    pub fn action(&self) -> SlotPublishAction {
        self.action
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StagingRecovery {
    Discarded,
    Absent,
}

impl FilesystemStore {
    pub fn open(canonical_private_root: impl AsRef<Path>) -> Result<Self, StoreError> {
        #[cfg(target_os = "macos")]
        {
            let root = canonical_private_root.as_ref();
            let root_directory = DarwinDirectory::open_private_root(root).map_err(|error| {
                let code = match error.operation() {
                    "root-not-absolute" => "store-root-not-absolute",
                    "root-not-canonical" => "store-root-not-canonical",
                    _ => "store-root-boundary",
                };
                StoreError::platform(code, root.display().to_string(), error)
            })?;
            root_directory
                .ensure_directory(".locks", 0o700)
                .map_err(|error| {
                    StoreError::platform("store-lock-root-boundary", ".locks", error)
                })?;
            root_directory
                .ensure_directory(".staging", 0o700)
                .map_err(|error| {
                    StoreError::platform("store-staging-root-boundary", ".staging", error)
                })?;
            root_directory.full_sync().map_err(|error| {
                StoreError::platform("store-root-sync", root.display().to_string(), error)
            })?;
            Ok(Self {
                inner: Arc::new(StoreInner {
                    root: root.to_path_buf(),
                    root_directory,
                }),
            })
        }

        #[cfg(not(unix))]
        {
            let _ = canonical_private_root;
            return Err(StoreError::contract("unsupported-store-platform", "$"));
        }

        #[cfg(all(unix, not(target_os = "macos")))]
        {
            let root = canonical_private_root.as_ref();
            if !root.is_absolute() {
                return Err(StoreError::contract(
                    "store-root-not-absolute",
                    root.display().to_string(),
                ));
            }
            validate_directory(root, 0o700, "store-root-boundary")?;
            let canonical = fs::canonicalize(root)
                .map_err(|error| StoreError::io("store-root-canonicalize", root, error))?;
            if canonical != root {
                return Err(StoreError::contract(
                    "store-root-not-canonical",
                    root.display().to_string(),
                ));
            }
            ensure_directory(&root.join(".locks"), 0o700, "store-lock-root-boundary")?;
            ensure_directory(&root.join(".staging"), 0o700, "store-staging-root-boundary")?;
            Ok(Self {
                inner: Arc::new(StoreInner {
                    root: root.to_path_buf(),
                }),
            })
        }
    }

    pub fn acquire_target_lock(&self, target: &NativeTarget) -> Result<HeldTargetLock, StoreError> {
        #[cfg(target_os = "macos")]
        {
            let locks = self
                .inner
                .root_directory
                .open_directory(".locks")
                .map_err(|error| {
                    StoreError::platform("store-lock-root-boundary", ".locks", error)
                })?;
            let parent = darwin_target_parent(&locks, target, 0o700)?;
            let filename = format!("{}.lock", target.executable_format());
            let regular = match parent.create_file_exclusive(&filename, 0o600) {
                Ok(file) => file,
                Err(error) if error.io_kind() == io::ErrorKind::AlreadyExists => parent
                    .open_file_read_write(&filename)
                    .map_err(|error| StoreError::platform("target-lock-open", &*filename, error))?,
                Err(error) => {
                    return Err(StoreError::platform("target-lock-open", &*filename, error));
                }
            };
            regular
                .validate(0o600)
                .map_err(|error| StoreError::platform("target-lock-boundary", &*filename, error))?;
            let file = regular.into_file();
            file.try_lock().map_err(|error| match error {
                fs::TryLockError::WouldBlock => StoreError::io(
                    "target-lock-busy",
                    &self.inner.root.join(".locks").join(&filename),
                    io::Error::from(io::ErrorKind::WouldBlock),
                ),
                fs::TryLockError::Error(source) => StoreError::io(
                    "target-lock-failed",
                    &self.inner.root.join(".locks").join(&filename),
                    source,
                ),
            })?;
            Ok(HeldTargetLock {
                store: Arc::clone(&self.inner),
                target: target.clone(),
                file,
            })
        }
        #[cfg(not(target_os = "macos"))]
        {
            validate_directory(&self.inner.root, 0o700, "store-root-boundary")?;
            let parent = target_parent(&self.inner.root.join(".locks"), target, 0o700)?;
            let path = parent.join(format!("{}.lock", target.executable_format()));
            if let Ok(metadata) = fs::symlink_metadata(&path) {
                validate_regular_metadata(&path, &metadata, 0o600, "target-lock-boundary")?;
            }
            let mut options = OpenOptions::new();
            options.read(true).write(true).create(true);
            #[cfg(unix)]
            options.mode(0o600);
            let file = options
                .open(&path)
                .map_err(|error| StoreError::io("target-lock-open", &path, error))?;
            set_mode(&path, 0o600)?;
            validate_regular_metadata(
                &path,
                &file
                    .metadata()
                    .map_err(|error| StoreError::io("target-lock-metadata", &path, error))?,
                0o600,
                "target-lock-boundary",
            )?;
            file.try_lock().map_err(|error| match error {
                fs::TryLockError::WouldBlock => StoreError::io(
                    "target-lock-busy",
                    &path,
                    io::Error::from(io::ErrorKind::WouldBlock),
                ),
                fs::TryLockError::Error(source) => {
                    StoreError::io("target-lock-failed", &path, source)
                }
            })?;
            Ok(HeldTargetLock {
                store: Arc::clone(&self.inner),
                target: target.clone(),
                file,
            })
        }
    }

    pub fn create_owned_staging(
        &self,
        lock: &HeldTargetLock,
        transaction: &StoreTransactionIdentity,
    ) -> Result<OwnedStaging, StoreError> {
        self.validate_lock(lock, lock.target())?;
        #[cfg(target_os = "macos")]
        {
            let staging_root = self
                .inner
                .root_directory
                .open_directory(".staging")
                .map_err(|error| {
                    StoreError::platform("store-staging-root-boundary", ".staging", error)
                })?;
            let target_parent = darwin_target_parent(&staging_root, lock.target(), 0o700)?;
            let parent_directory = target_parent
                .ensure_directory(lock.target().executable_format(), 0o700)
                .map_err(|error| {
                    StoreError::platform(
                        "staging-parent-boundary",
                        lock.target().executable_format(),
                        error,
                    )
                })?;
            let directory = parent_directory
                .create_directory_exclusive(transaction.as_str(), 0o755)
                .map_err(|error| {
                    StoreError::platform(
                        if error.io_kind() == io::ErrorKind::AlreadyExists {
                            "staging-exists"
                        } else {
                            "staging-create"
                        },
                        transaction.as_str(),
                        error,
                    )
                })?;
            Ok(OwnedStaging {
                store: Arc::clone(&self.inner),
                target: lock.target().clone(),
                transaction: transaction.clone(),
                path: staging_path(&self.inner.root, lock.target(), transaction),
                parent_directory,
                directory,
            })
        }
        #[cfg(not(target_os = "macos"))]
        {
            let parent = target_parent(&self.inner.root.join(".staging"), lock.target(), 0o700)?
                .join(lock.target().executable_format());
            ensure_directory(&parent, 0o700, "staging-parent-boundary")?;
            let path = parent.join(transaction.as_str());
            fs::create_dir(&path).map_err(|error| {
                StoreError::io(
                    if error.kind() == io::ErrorKind::AlreadyExists {
                        "staging-exists"
                    } else {
                        "staging-create"
                    },
                    &path,
                    error,
                )
            })?;
            set_mode(&path, 0o755)?;
            Ok(OwnedStaging {
                store: Arc::clone(&self.inner),
                target: lock.target().clone(),
                transaction: transaction.clone(),
                path,
            })
        }
    }

    pub fn verify_owned_staging(
        &self,
        lock: &HeldTargetLock,
        staging: OwnedStaging,
        policy: &LauncherPolicy,
        record: &RegistrationRecord,
    ) -> Result<VerifiedStaging, StoreError> {
        self.validate_lock(lock, record.target())?;
        self.validate_staging_capability(&staging, lock.target())?;
        if !policy.supports(record.target()) {
            return Err(StoreError::contract("unsupported-target", "$"));
        }
        #[cfg(target_os = "macos")]
        let verification = verify_slot_directory(&staging.directory, policy, record)?;
        #[cfg(not(target_os = "macos"))]
        let verification = verify_slot_path(&self.inner.root, &staging.path, policy, record)?;
        Ok(VerifiedStaging {
            staging,
            policy: policy.clone(),
            record: record.clone(),
            verification,
            slot_relative_identity: slot_relative_identity(record).into(),
        })
    }

    pub fn publish_slot_exclusive(
        &self,
        lock: &HeldTargetLock,
        verified: VerifiedStaging,
    ) -> Result<SlotPublication, StoreError> {
        self.validate_lock(lock, verified.record.target())?;
        self.validate_staging_capability(&verified.staging, lock.target())?;
        #[cfg(target_os = "macos")]
        {
            let (parent_relative, final_name) = split_parent(&verified.slot_relative_identity)?;
            let final_parent =
                darwin_ensure_directory_chain(&self.inner.root_directory, parent_relative, 0o755)
                    .map_err(|error| {
                    StoreError::platform("slot-parent-boundary", parent_relative, error)
                })?;
            if verified.staging.directory.device().map_err(|error| {
                StoreError::platform("staging-metadata", &*verified.slot_relative_identity, error)
            })? != final_parent.device().map_err(|error| {
                StoreError::platform("slot-parent-metadata", parent_relative, error)
            })? {
                return Err(StoreError::contract(
                    "cross-filesystem-publication",
                    &*verified.slot_relative_identity,
                ));
            }

            match final_parent.open_directory(final_name) {
                Ok(final_directory) => {
                    let final_verification = verify_slot_directory(
                        &final_directory,
                        &verified.policy,
                        &verified.record,
                    )?;
                    if final_verification != verified.verification {
                        return Err(StoreError::contract(
                            "existing-slot-mismatch",
                            &*verified.slot_relative_identity,
                        ));
                    }
                    final_parent.full_sync().map_err(|error| {
                        StoreError::platform(
                            "publication-durability-unknown",
                            &*verified.slot_relative_identity,
                            error,
                        )
                    })?;
                    darwin_discard_staging(&verified.staging)?;
                    return Ok(SlotPublication {
                        slot: InstalledInactiveSlot {
                            relative_identity: verified.slot_relative_identity,
                            verification: final_verification,
                        },
                        action: SlotPublishAction::Reused,
                    });
                }
                Err(error) if error.io_kind() == io::ErrorKind::NotFound => {}
                Err(error) => {
                    return Err(StoreError::platform(
                        if error.is_symlink_loop() {
                            "symbolic-link"
                        } else {
                            "slot-destination-metadata"
                        },
                        &*verified.slot_relative_identity,
                        error,
                    ));
                }
            }

            darwin_full_sync_tree(&verified.staging.directory)?;
            verified
                .staging
                .parent_directory
                .full_sync()
                .map_err(|error| {
                    StoreError::platform(
                        "staging-parent-sync",
                        verified.staging.transaction.as_str(),
                        error,
                    )
                })?;
            let staging_parent_relative = format!(
                ".staging/{}/{}/{}/{}",
                lock.target().goos(),
                lock.target().goarch(),
                lock.target().variant(),
                lock.target().executable_format(),
            );
            darwin_sync_directory_chain(&self.inner.root_directory, &staging_parent_relative)?;
            darwin_sync_directory_chain(&self.inner.root_directory, parent_relative)?;

            if let Err(error) = verified
                .staging
                .parent_directory
                .rename_directory_exclusive(
                    verified.staging.transaction.as_str(),
                    &final_parent,
                    final_name,
                )
            {
                if error.io_kind() == io::ErrorKind::AlreadyExists {
                    let final_directory =
                        final_parent.open_directory(final_name).map_err(|error| {
                            StoreError::platform(
                                "slot-destination-metadata",
                                &*verified.slot_relative_identity,
                                error,
                            )
                        })?;
                    let final_verification = verify_slot_directory(
                        &final_directory,
                        &verified.policy,
                        &verified.record,
                    )?;
                    if final_verification != verified.verification {
                        return Err(StoreError::contract(
                            "existing-slot-mismatch",
                            &*verified.slot_relative_identity,
                        ));
                    }
                    final_parent.full_sync().map_err(|error| {
                        StoreError::platform(
                            "publication-durability-unknown",
                            &*verified.slot_relative_identity,
                            error,
                        )
                    })?;
                    darwin_discard_staging(&verified.staging)?;
                    return Ok(SlotPublication {
                        slot: InstalledInactiveSlot {
                            relative_identity: verified.slot_relative_identity,
                            verification: final_verification,
                        },
                        action: SlotPublishAction::Reused,
                    });
                }
                let code = if error.is_cross_device() {
                    "cross-filesystem-publication"
                } else if error.is_symlink_loop() {
                    "symbolic-link"
                } else if error.is_unsupported_capability() {
                    "unsupported-store-capability"
                } else {
                    "slot-publish-rename"
                };
                return Err(StoreError::platform(
                    code,
                    &*verified.slot_relative_identity,
                    error,
                ));
            }

            #[cfg(test)]
            test_crash_checkpoint("after-exclusive-rename");

            final_parent.full_sync().map_err(|error| {
                StoreError::platform(
                    "publication-durability-unknown",
                    &*verified.slot_relative_identity,
                    error,
                )
            })?;
            verified
                .staging
                .parent_directory
                .full_sync()
                .map_err(|error| {
                    StoreError::platform(
                        "publication-durability-unknown",
                        &*verified.slot_relative_identity,
                        error,
                    )
                })?;
            #[cfg(test)]
            test_crash_checkpoint("after-parent-sync");
            let final_directory = final_parent.open_directory(final_name).map_err(|error| {
                StoreError::platform(
                    "post-publication-verification",
                    &*verified.slot_relative_identity,
                    error,
                )
            })?;
            let final_verification =
                verify_slot_directory(&final_directory, &verified.policy, &verified.record)?;
            if final_verification != verified.verification {
                return Err(StoreError::contract(
                    "post-publication-verification",
                    &*verified.slot_relative_identity,
                ));
            }
            Ok(SlotPublication {
                slot: InstalledInactiveSlot {
                    relative_identity: verified.slot_relative_identity,
                    verification: final_verification,
                },
                action: SlotPublishAction::Published,
            })
        }
        #[cfg(not(target_os = "macos"))]
        {
            let final_path = join_portable(&self.inner.root, &verified.slot_relative_identity);
            let final_parent = final_path
                .parent()
                .ok_or_else(|| StoreError::contract("invalid-slot-depth", "$"))?;
            ensure_slot_parent_chain(&self.inner.root, final_parent)?;
            ensure_same_filesystem(&verified.staging.path, final_parent)?;

            match fs::symlink_metadata(&final_path) {
                Ok(_) => {
                    let final_verification = verify_slot_path(
                        &self.inner.root,
                        &final_path,
                        &verified.policy,
                        &verified.record,
                    )?;
                    if final_verification != verified.verification {
                        return Err(StoreError::contract(
                            "existing-slot-mismatch",
                            &*verified.slot_relative_identity,
                        ));
                    }
                    discard_staging_path(&self.inner.root, &verified.staging.path)?;
                    Ok(SlotPublication {
                        slot: InstalledInactiveSlot {
                            relative_identity: verified.slot_relative_identity,
                            verification: final_verification,
                        },
                        action: SlotPublishAction::Reused,
                    })
                }
                Err(error) if error.kind() == io::ErrorKind::NotFound => {
                    fs::rename(&verified.staging.path, &final_path).map_err(|error| {
                        StoreError::io("slot-publish-rename", &final_path, error)
                    })?;
                    let final_verification = verify_slot_path(
                        &self.inner.root,
                        &final_path,
                        &verified.policy,
                        &verified.record,
                    )?;
                    if final_verification != verified.verification {
                        return Err(StoreError::contract(
                            "post-publication-verification",
                            &*verified.slot_relative_identity,
                        ));
                    }
                    Ok(SlotPublication {
                        slot: InstalledInactiveSlot {
                            relative_identity: verified.slot_relative_identity,
                            verification: final_verification,
                        },
                        action: SlotPublishAction::Published,
                    })
                }
                Err(error) => Err(StoreError::io(
                    "slot-destination-metadata",
                    &final_path,
                    error,
                )),
            }
        }
    }

    pub fn read_slot_exact(
        &self,
        policy: &LauncherPolicy,
        record: &RegistrationRecord,
    ) -> Result<InstalledInactiveSlot, StoreError> {
        if !policy.supports(record.target()) {
            return Err(StoreError::contract("unsupported-target", "$"));
        }
        let relative_identity = slot_relative_identity(record);
        #[cfg(target_os = "macos")]
        let verification = {
            let directory =
                darwin_open_directory_chain(&self.inner.root_directory, &relative_identity)
                    .map_err(|error| {
                        StoreError::platform("slot-root-boundary", &*relative_identity, error)
                    })?;
            verify_slot_directory(&directory, policy, record)?
        };
        #[cfg(not(target_os = "macos"))]
        let verification = {
            let path = join_portable(&self.inner.root, &relative_identity);
            verify_slot_path(&self.inner.root, &path, policy, record)?
        };
        Ok(InstalledInactiveSlot {
            relative_identity: relative_identity.into(),
            verification,
        })
    }

    pub fn discard_owned_staging(
        &self,
        lock: &HeldTargetLock,
        transaction: &StoreTransactionIdentity,
    ) -> Result<StagingRecovery, StoreError> {
        self.validate_lock(lock, lock.target())?;
        #[cfg(target_os = "macos")]
        {
            let staging_root = self
                .inner
                .root_directory
                .open_directory(".staging")
                .map_err(|error| {
                    StoreError::platform("store-staging-root-boundary", ".staging", error)
                })?;
            let target_parent = darwin_target_parent(&staging_root, lock.target(), 0o700)?;
            let parent = target_parent
                .open_directory(lock.target().executable_format())
                .map_err(|error| {
                    StoreError::platform(
                        "staging-parent-boundary",
                        lock.target().executable_format(),
                        error,
                    )
                })?;
            match parent.open_directory(transaction.as_str()) {
                Ok(directory) => {
                    directory.remove_tree_contents().map_err(|error| {
                        StoreError::platform("staging-discard", transaction.as_str(), error)
                    })?;
                    drop(directory);
                    parent
                        .remove_directory(transaction.as_str())
                        .map_err(|error| {
                            StoreError::platform("staging-discard", transaction.as_str(), error)
                        })?;
                    parent.full_sync().map_err(|error| {
                        StoreError::platform("staging-parent-sync", transaction.as_str(), error)
                    })?;
                    Ok(StagingRecovery::Discarded)
                }
                Err(error) if error.io_kind() == io::ErrorKind::NotFound => {
                    Ok(StagingRecovery::Absent)
                }
                Err(error) => Err(StoreError::platform(
                    "unowned-staging",
                    transaction.as_str(),
                    error,
                )),
            }
        }
        #[cfg(not(target_os = "macos"))]
        {
            let path = staging_path(&self.inner.root, lock.target(), transaction);
            match fs::symlink_metadata(&path) {
                Ok(metadata) => {
                    if metadata.file_type().is_symlink() || !metadata.is_dir() {
                        return Err(StoreError::contract(
                            "unowned-staging",
                            path.display().to_string(),
                        ));
                    }
                    discard_staging_path(&self.inner.root, &path)?;
                    Ok(StagingRecovery::Discarded)
                }
                Err(error) if error.kind() == io::ErrorKind::NotFound => {
                    Ok(StagingRecovery::Absent)
                }
                Err(error) => Err(StoreError::io("staging-recovery-metadata", &path, error)),
            }
        }
    }

    fn validate_lock(
        &self,
        lock: &HeldTargetLock,
        target: &NativeTarget,
    ) -> Result<(), StoreError> {
        if !Arc::ptr_eq(&self.inner, &lock.store) {
            return Err(StoreError::contract("foreign-target-lock", "$"));
        }
        if lock.target() != target {
            return Err(StoreError::contract("target-lock-mismatch", "$"));
        }
        Ok(())
    }

    fn validate_staging_capability(
        &self,
        staging: &OwnedStaging,
        target: &NativeTarget,
    ) -> Result<(), StoreError> {
        if !Arc::ptr_eq(&self.inner, &staging.store) {
            return Err(StoreError::contract("foreign-staging", "$"));
        }
        if &staging.target != target
            || staging.path != staging_path(&self.inner.root, target, &staging.transaction)
        {
            return Err(StoreError::contract("unowned-staging", "$"));
        }
        Ok(())
    }
}

fn split_parent(relative: &str) -> Result<(&str, &str), StoreError> {
    validate_staging_relative_path(relative)?;
    Ok(relative.rsplit_once('/').unwrap_or(("", relative)))
}

#[cfg(all(test, target_os = "macos"))]
fn test_crash_checkpoint(name: &str) {
    if std::env::var("RADISHAXIOM_STORE_TEST_CRASH_AT").as_deref() == Ok(name) {
        std::process::exit(89);
    }
}

#[cfg(target_os = "macos")]
fn darwin_open_directory_chain(
    root: &DarwinDirectory,
    relative: &str,
) -> Result<DarwinDirectory, PlatformError> {
    let mut current = root.try_clone()?;
    if relative.is_empty() {
        return Ok(current);
    }
    for component in relative.split('/') {
        current = current.open_directory(component)?;
    }
    Ok(current)
}

#[cfg(target_os = "macos")]
fn darwin_ensure_directory_chain(
    root: &DarwinDirectory,
    relative: &str,
    mode: u32,
) -> Result<DarwinDirectory, PlatformError> {
    let mut current = root.try_clone()?;
    if relative.is_empty() {
        return Ok(current);
    }
    for component in relative.split('/') {
        current = current.ensure_directory(component, mode)?;
    }
    Ok(current)
}

#[cfg(target_os = "macos")]
fn darwin_target_parent(
    base: &DarwinDirectory,
    target: &NativeTarget,
    mode: u32,
) -> Result<DarwinDirectory, StoreError> {
    let mut current = base
        .try_clone()
        .map_err(|error| StoreError::platform("target-state-parent-boundary", "$", error))?;
    for component in [target.goos(), target.goarch(), target.variant()] {
        current = current.ensure_directory(component, mode).map_err(|error| {
            StoreError::platform("target-state-parent-boundary", component, error)
        })?;
    }
    Ok(current)
}

#[cfg(target_os = "macos")]
fn darwin_sync_directory_chain(root: &DarwinDirectory, relative: &str) -> Result<(), StoreError> {
    let mut chain = vec![
        root.try_clone()
            .map_err(|error| StoreError::platform("slot-parent-sync", relative, error))?,
    ];
    if !relative.is_empty() {
        for component in relative.split('/') {
            let next = chain
                .last()
                .expect("root directory is always present")
                .open_directory(component)
                .map_err(|error| StoreError::platform("slot-parent-sync", relative, error))?;
            chain.push(next);
        }
    }
    for directory in chain.iter().rev() {
        directory
            .full_sync()
            .map_err(|error| StoreError::platform("slot-parent-sync", relative, error))?;
    }
    Ok(())
}

#[cfg(target_os = "macos")]
fn darwin_full_sync_tree(directory: &DarwinDirectory) -> Result<(), StoreError> {
    for name in directory
        .entry_names()
        .map_err(|error| StoreError::platform("staging-directory-read", "$", error))?
    {
        match directory.open_entry(&name).map_err(|error| {
            StoreError::platform(
                if error.is_symlink_loop() {
                    "symbolic-link"
                } else {
                    "staging-entry-boundary"
                },
                &*name,
                error,
            )
        })? {
            DarwinEntry::Directory { directory, .. } => darwin_full_sync_tree(&directory)?,
            DarwinEntry::File { .. } => {}
        }
    }
    directory
        .full_sync()
        .map_err(|error| StoreError::platform("staging-directory-sync", "$", error))
}

#[cfg(target_os = "macos")]
fn darwin_discard_staging(staging: &OwnedStaging) -> Result<(), StoreError> {
    staging.directory.remove_tree_contents().map_err(|error| {
        StoreError::platform("staging-discard", staging.transaction.as_str(), error)
    })?;
    staging
        .parent_directory
        .remove_directory(staging.transaction.as_str())
        .map_err(|error| {
            StoreError::platform("staging-discard", staging.transaction.as_str(), error)
        })?;
    staging.parent_directory.full_sync().map_err(|error| {
        StoreError::platform("staging-parent-sync", staging.transaction.as_str(), error)
    })
}

#[cfg(target_os = "macos")]
fn verify_slot_directory(
    slot_root: &DarwinDirectory,
    policy: &LauncherPolicy,
    record: &RegistrationRecord,
) -> Result<SlotVerification, StoreError> {
    if slot_root
        .mode()
        .map_err(|error| StoreError::platform("slot-directory-mode", "$", error))?
        != 0o755
    {
        return Err(StoreError::contract("slot-directory-mode", "$"));
    }

    let DarwinSlotEntries {
        mut files,
        directories,
    } = collect_darwin_slot_entries(slot_root)?;
    let layout = policy.installation_layout();
    let expected_files = BTreeSet::from([
        layout.executable_relative_path().to_owned(),
        layout.receipt_filename().to_owned(),
    ]);
    let mut expected_directories = BTreeSet::new();
    for name in &expected_files {
        let components: Vec<&str> = name.split('/').collect();
        for end in 1..components.len() {
            expected_directories.insert(components[..end].join("/"));
        }
    }
    if files.keys().cloned().collect::<BTreeSet<_>>() != expected_files
        || directories.keys().cloned().collect::<BTreeSet<_>>() != expected_directories
    {
        return Err(StoreError::contract("slot-inventory-mismatch", "$"));
    }
    for (name, directory) in &directories {
        if directory
            .mode()
            .map_err(|error| StoreError::platform("slot-directory-mode", name.as_str(), error))?
            != 0o755
        {
            return Err(StoreError::contract("slot-directory-mode", name.as_str()));
        }
    }

    let executable = files
        .get_mut(layout.executable_relative_path())
        .ok_or_else(|| StoreError::contract("slot-inventory-mismatch", "$"))?;
    executable.validate(0o755).map_err(|error| {
        StoreError::platform(
            "executable-file-boundary",
            layout.executable_relative_path(),
            error,
        )
    })?;
    let executable_bytes = executable.read_all().map_err(|error| {
        StoreError::platform("executable-read", layout.executable_relative_path(), error)
    })?;
    let artifact = record.artifact();
    let executable_length = u64::try_from(executable_bytes.len()).map_err(|_| {
        StoreError::contract("executable-too-large", layout.executable_relative_path())
    })?;
    if executable_length != artifact.byte_length() {
        return Err(StoreError::contract(
            "executable-length-mismatch",
            layout.executable_relative_path(),
        ));
    }
    let executable_digest = raw_digest(&executable_bytes);
    if executable_digest != artifact.raw_sha256() {
        return Err(StoreError::contract(
            "executable-digest-mismatch",
            layout.executable_relative_path(),
        ));
    }
    inspect_executable(&executable_bytes, record.target())?;

    let receipt_file = files
        .get_mut(layout.receipt_filename())
        .ok_or_else(|| StoreError::contract("slot-inventory-mismatch", "$"))?;
    receipt_file.validate(0o644).map_err(|error| {
        StoreError::platform("receipt-file-boundary", layout.receipt_filename(), error)
    })?;
    let receipt_bytes = receipt_file
        .read_all()
        .map_err(|error| StoreError::platform("receipt-read", layout.receipt_filename(), error))?;
    let receipt = parse_installation_receipt(&receipt_bytes, policy, record)
        .map_err(|error| StoreError::contract(error.code(), error.path()))?;
    let tree_digest = darwin_tree_digest(&mut files, &directories)?;

    Ok(SlotVerification {
        artifact_raw_sha256: executable_digest.into(),
        artifact_byte_length: artifact.byte_length(),
        receipt_document_digest: receipt.document_digest().into(),
        tree_digest: tree_digest.into(),
    })
}

#[cfg(target_os = "macos")]
struct DarwinSlotEntries {
    files: BTreeMap<String, DarwinFile>,
    directories: BTreeMap<String, DarwinDirectory>,
}

#[cfg(target_os = "macos")]
fn collect_darwin_slot_entries(root: &DarwinDirectory) -> Result<DarwinSlotEntries, StoreError> {
    fn visit(
        directory: &DarwinDirectory,
        prefix: &str,
        files: &mut BTreeMap<String, DarwinFile>,
        directories: &mut BTreeMap<String, DarwinDirectory>,
    ) -> Result<(), StoreError> {
        for name in directory
            .entry_names()
            .map_err(|error| StoreError::platform("slot-directory-read", prefix, error))?
        {
            let relative = if prefix.is_empty() {
                name.clone()
            } else {
                format!("{prefix}/{name}")
            };
            validate_portable_relative_path(&relative)
                .map_err(|_| StoreError::contract("nonportable-slot-entry", &*relative))?;
            let entry = directory.open_entry(&name).map_err(|error| {
                StoreError::platform(
                    if error.is_symlink_loop() {
                        "symbolic-link"
                    } else {
                        "slot-entry-boundary"
                    },
                    &*relative,
                    error,
                )
            })?;
            match entry {
                DarwinEntry::Directory {
                    directory: child, ..
                } => {
                    visit(&child, &relative, files, directories)?;
                    directories.insert(relative, child);
                }
                DarwinEntry::File { file, .. } => {
                    files.insert(relative, file);
                }
            }
        }
        Ok(())
    }

    let mut files = BTreeMap::new();
    let mut directories = BTreeMap::new();
    visit(root, "", &mut files, &mut directories)?;
    Ok(DarwinSlotEntries { files, directories })
}

#[cfg(target_os = "macos")]
fn darwin_tree_digest(
    files: &mut BTreeMap<String, DarwinFile>,
    directories: &BTreeMap<String, DarwinDirectory>,
) -> Result<String, StoreError> {
    let mut rows = Vec::with_capacity(files.len() + directories.len());
    for (name, directory) in directories {
        let mode = directory
            .mode()
            .map_err(|error| StoreError::platform("entry-mode-metadata", name.as_str(), error))?;
        rows.push(Value::Object(vec![
            ("kind".into(), Value::String("directory".into())),
            ("mode".into(), Value::String(format!("{mode:04o}"))),
            ("path".into(), Value::String(name.clone())),
        ]));
    }
    for (name, file) in files {
        let bytes = file
            .read_all()
            .map_err(|error| StoreError::platform("slot-tree-file-read", name.as_str(), error))?;
        let mode = file
            .mode()
            .map_err(|error| StoreError::platform("entry-mode-metadata", name.as_str(), error))?;
        rows.push(Value::Object(vec![
            ("byte_length".into(), Value::String(bytes.len().to_string())),
            ("kind".into(), Value::String("file".into())),
            ("mode".into(), Value::String(format!("{mode:04o}"))),
            ("path".into(), Value::String(name.clone())),
            ("raw_sha256".into(), Value::String(raw_digest(&bytes))),
        ]));
    }
    Ok(domain_digest_value(SLOT_TREE_DOMAIN, &Value::Array(rows)))
}

#[cfg(not(target_os = "macos"))]
fn verify_slot_path(
    store_root: &Path,
    slot_root: &Path,
    policy: &LauncherPolicy,
    record: &RegistrationRecord,
) -> Result<SlotVerification, StoreError> {
    require_contained_directory(store_root, slot_root)?;
    validate_directory(slot_root, 0o755, "slot-directory-mode")?;

    let SlotEntries { files, directories } = collect_slot_entries(slot_root)?;
    let layout = policy.installation_layout();
    let expected_files = BTreeSet::from([
        layout.executable_relative_path().to_owned(),
        layout.receipt_filename().to_owned(),
    ]);
    let mut expected_directories = BTreeSet::new();
    for name in &expected_files {
        let components: Vec<&str> = name.split('/').collect();
        for end in 1..components.len() {
            expected_directories.insert(components[..end].join("/"));
        }
    }
    if files.keys().cloned().collect::<BTreeSet<_>>() != expected_files
        || directories.keys().cloned().collect::<BTreeSet<_>>() != expected_directories
    {
        return Err(StoreError::contract("slot-inventory-mismatch", "$"));
    }
    for path in directories.values() {
        validate_directory(path, 0o755, "slot-directory-mode")?;
    }

    let executable = files
        .get(layout.executable_relative_path())
        .ok_or_else(|| StoreError::contract("slot-inventory-mismatch", "$"))?;
    validate_regular_file(executable, 0o755, "executable-file-boundary")?;
    let executable_bytes = read_file(executable, "executable-read")?;
    let artifact = record.artifact();
    let executable_length = u64::try_from(executable_bytes.len()).map_err(|_| {
        StoreError::contract("executable-too-large", layout.executable_relative_path())
    })?;
    if executable_length != artifact.byte_length() {
        return Err(StoreError::contract(
            "executable-length-mismatch",
            layout.executable_relative_path(),
        ));
    }
    let executable_digest = raw_digest(&executable_bytes);
    if executable_digest != artifact.raw_sha256() {
        return Err(StoreError::contract(
            "executable-digest-mismatch",
            layout.executable_relative_path(),
        ));
    }
    inspect_executable(&executable_bytes, record.target())?;

    let receipt_path = files
        .get(layout.receipt_filename())
        .ok_or_else(|| StoreError::contract("slot-inventory-mismatch", "$"))?;
    validate_regular_file(receipt_path, 0o644, "receipt-file-boundary")?;
    let receipt_bytes = read_file(receipt_path, "receipt-read")?;
    let receipt = parse_installation_receipt(&receipt_bytes, policy, record)
        .map_err(|error| StoreError::contract(error.code(), error.path()))?;
    let tree_digest = tree_digest(&files, &directories)?;

    Ok(SlotVerification {
        artifact_raw_sha256: executable_digest.into(),
        artifact_byte_length: artifact.byte_length(),
        receipt_document_digest: receipt.document_digest().into(),
        tree_digest: tree_digest.into(),
    })
}

#[cfg(not(target_os = "macos"))]
struct SlotEntries {
    files: BTreeMap<String, PathBuf>,
    directories: BTreeMap<String, PathBuf>,
}

#[cfg(not(target_os = "macos"))]
fn collect_slot_entries(root: &Path) -> Result<SlotEntries, StoreError> {
    let mut files = BTreeMap::new();
    let mut directories = BTreeMap::new();
    let mut pending = vec![(root.to_path_buf(), String::new())];
    while let Some((directory, prefix)) = pending.pop() {
        let entries = fs::read_dir(&directory)
            .map_err(|error| StoreError::io("slot-directory-read", &directory, error))?;
        for entry in entries {
            let entry =
                entry.map_err(|error| StoreError::io("slot-entry-read", &directory, error))?;
            let name = entry.file_name().into_string().map_err(|_| {
                StoreError::contract("nonportable-slot-entry", directory.display().to_string())
            })?;
            let relative = if prefix.is_empty() {
                name
            } else {
                format!("{prefix}/{name}")
            };
            validate_portable_relative_path(&relative)
                .map_err(|_| StoreError::contract("nonportable-slot-entry", relative.as_str()))?;
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path)
                .map_err(|error| StoreError::io("slot-entry-metadata", &path, error))?;
            if metadata.file_type().is_symlink() {
                return Err(StoreError::contract("symbolic-link", relative));
            }
            if metadata.is_dir() {
                directories.insert(relative.clone(), path.clone());
                pending.push((path, relative));
            } else if metadata.is_file() {
                files.insert(relative, path);
            } else {
                return Err(StoreError::contract("slot-special-file", relative));
            }
        }
    }
    Ok(SlotEntries { files, directories })
}

#[cfg(not(target_os = "macos"))]
fn tree_digest(
    files: &BTreeMap<String, PathBuf>,
    directories: &BTreeMap<String, PathBuf>,
) -> Result<String, StoreError> {
    let mut rows = Vec::with_capacity(files.len() + directories.len());
    for (name, path) in directories {
        rows.push(Value::Object(vec![
            ("kind".into(), Value::String("directory".into())),
            (
                "mode".into(),
                Value::String(format!("{:04o}", file_mode(path)?)),
            ),
            ("path".into(), Value::String(name.clone())),
        ]));
    }
    for (name, path) in files {
        let bytes = read_file(path, "slot-tree-file-read")?;
        rows.push(Value::Object(vec![
            ("byte_length".into(), Value::String(bytes.len().to_string())),
            ("kind".into(), Value::String("file".into())),
            (
                "mode".into(),
                Value::String(format!("{:04o}", file_mode(path)?)),
            ),
            ("path".into(), Value::String(name.clone())),
            ("raw_sha256".into(), Value::String(raw_digest(&bytes))),
        ]));
    }
    Ok(domain_digest_value(SLOT_TREE_DOMAIN, &Value::Array(rows)))
}

fn inspect_executable(bytes: &[u8], target: &NativeTarget) -> Result<(), StoreError> {
    if target.executable_format() != "macho-64-arm64" {
        return Err(StoreError::contract(
            "unsupported-executable-format",
            target.executable_format(),
        ));
    }
    if bytes.len() < 32 || bytes[..4] != [0xcf, 0xfa, 0xed, 0xfe] {
        return Err(StoreError::contract("executable-format-mismatch", "$"));
    }
    if u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]) != 0x0100_000c {
        return Err(StoreError::contract(
            "executable-architecture-mismatch",
            "$",
        ));
    }
    Ok(())
}

#[cfg(not(target_os = "macos"))]
fn require_contained_directory(store_root: &Path, target: &Path) -> Result<(), StoreError> {
    validate_directory(store_root, 0o700, "store-root-boundary")?;
    let relative = target
        .strip_prefix(store_root)
        .map_err(|_| StoreError::contract("slot-root-escape", target.display().to_string()))?;
    let mut current = store_root.to_path_buf();
    for component in relative.components() {
        current.push(component.as_os_str());
        let metadata = fs::symlink_metadata(&current)
            .map_err(|error| StoreError::io("slot-component-metadata", &current, error))?;
        if metadata.file_type().is_symlink() {
            return Err(StoreError::contract(
                "symbolic-link",
                current.display().to_string(),
            ));
        }
    }
    let real = fs::canonicalize(target)
        .map_err(|error| StoreError::io("slot-root-canonicalize", target, error))?;
    if !real.starts_with(store_root) {
        return Err(StoreError::contract(
            "slot-root-escape",
            target.display().to_string(),
        ));
    }
    Ok(())
}

#[cfg(not(target_os = "macos"))]
fn ensure_slot_parent_chain(store_root: &Path, final_parent: &Path) -> Result<(), StoreError> {
    let relative = final_parent.strip_prefix(store_root).map_err(|_| {
        StoreError::contract("slot-root-escape", final_parent.display().to_string())
    })?;
    let mut current = store_root.to_path_buf();
    for component in relative.components() {
        current.push(component.as_os_str());
        ensure_directory(&current, 0o755, "slot-parent-boundary")?;
    }
    Ok(())
}

#[cfg(not(target_os = "macos"))]
fn target_parent(base: &Path, target: &NativeTarget, mode: u32) -> Result<PathBuf, StoreError> {
    let mut current = base.to_path_buf();
    for component in [target.goos(), target.goarch(), target.variant()] {
        current.push(component);
        ensure_directory(&current, mode, "target-state-parent-boundary")?;
    }
    Ok(current)
}

fn staging_path(
    root: &Path,
    target: &NativeTarget,
    transaction: &StoreTransactionIdentity,
) -> PathBuf {
    root.join(".staging")
        .join(target.goos())
        .join(target.goarch())
        .join(target.variant())
        .join(target.executable_format())
        .join(transaction.as_str())
}

#[cfg(not(target_os = "macos"))]
fn discard_staging_path(store_root: &Path, path: &Path) -> Result<(), StoreError> {
    let staging_root = store_root.join(".staging");
    let relative = path
        .strip_prefix(&staging_root)
        .map_err(|_| StoreError::contract("unowned-staging", path.display().to_string()))?;
    if relative.components().count() != 5 {
        return Err(StoreError::contract(
            "unowned-staging",
            path.display().to_string(),
        ));
    }
    let mut current = staging_root;
    for component in relative.components() {
        current.push(component.as_os_str());
        let metadata = fs::symlink_metadata(&current)
            .map_err(|error| StoreError::io("staging-discard-metadata", &current, error))?;
        if metadata.file_type().is_symlink() || !metadata.is_dir() {
            return Err(StoreError::contract(
                "unowned-staging",
                current.display().to_string(),
            ));
        }
    }
    fs::remove_dir_all(path).map_err(|error| StoreError::io("staging-discard", path, error))
}

#[cfg(not(target_os = "macos"))]
fn ensure_same_filesystem(staging: &Path, final_parent: &Path) -> Result<(), StoreError> {
    #[cfg(unix)]
    {
        let staging_device = fs::metadata(staging)
            .map_err(|error| StoreError::io("staging-metadata", staging, error))?
            .dev();
        let final_device = fs::metadata(final_parent)
            .map_err(|error| StoreError::io("slot-parent-metadata", final_parent, error))?
            .dev();
        if staging_device != final_device {
            return Err(StoreError::contract(
                "cross-filesystem-publication",
                staging.display().to_string(),
            ));
        }
        Ok(())
    }
    #[cfg(not(unix))]
    {
        let _ = (staging, final_parent);
        Err(StoreError::contract("unsupported-store-platform", "$"))
    }
}

#[cfg(not(target_os = "macos"))]
fn ensure_directory(path: &Path, mode: u32, code: &'static str) -> Result<(), StoreError> {
    match fs::symlink_metadata(path) {
        Ok(_) => validate_directory(path, mode, code),
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            fs::create_dir(path).map_err(|error| StoreError::io(code, path, error))?;
            set_mode(path, mode)?;
            validate_directory(path, mode, code)
        }
        Err(error) => Err(StoreError::io(code, path, error)),
    }
}

#[cfg(not(target_os = "macos"))]
fn validate_directory(path: &Path, mode: u32, code: &'static str) -> Result<(), StoreError> {
    let metadata = fs::symlink_metadata(path).map_err(|error| StoreError::io(code, path, error))?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() || file_mode_from(&metadata) != mode
    {
        return Err(StoreError::contract(code, path.display().to_string()));
    }
    Ok(())
}

#[cfg(not(target_os = "macos"))]
fn validate_regular_file(path: &Path, mode: u32, code: &'static str) -> Result<(), StoreError> {
    let metadata = fs::symlink_metadata(path).map_err(|error| StoreError::io(code, path, error))?;
    validate_regular_metadata(path, &metadata, mode, code)
}

#[cfg(not(target_os = "macos"))]
fn validate_regular_metadata(
    path: &Path,
    metadata: &fs::Metadata,
    mode: u32,
    code: &'static str,
) -> Result<(), StoreError> {
    #[cfg(unix)]
    if metadata.file_type().is_symlink()
        || !metadata.is_file()
        || metadata.nlink() != 1
        || file_mode_from(metadata) != mode
    {
        return Err(StoreError::contract(code, path.display().to_string()));
    }
    #[cfg(not(unix))]
    {
        let _ = (path, metadata, mode);
        return Err(StoreError::contract("unsupported-store-platform", "$"));
    }
    Ok(())
}

#[cfg(any(test, not(target_os = "macos")))]
fn set_mode(path: &Path, mode: u32) -> Result<(), StoreError> {
    #[cfg(unix)]
    {
        fs::set_permissions(path, fs::Permissions::from_mode(mode))
            .map_err(|error| StoreError::io("set-mode", path, error))
    }
    #[cfg(not(unix))]
    {
        let _ = (path, mode);
        Err(StoreError::contract("unsupported-store-platform", "$"))
    }
}

#[cfg(not(target_os = "macos"))]
fn file_mode(path: &Path) -> Result<u32, StoreError> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| StoreError::io("entry-mode-metadata", path, error))?;
    Ok(file_mode_from(&metadata))
}

#[cfg(not(target_os = "macos"))]
fn file_mode_from(metadata: &fs::Metadata) -> u32 {
    #[cfg(unix)]
    {
        metadata.mode() & 0o7777
    }
    #[cfg(not(unix))]
    {
        let _ = metadata;
        0
    }
}

#[cfg(not(target_os = "macos"))]
fn read_file(path: &Path, code: &'static str) -> Result<Vec<u8>, StoreError> {
    let mut file = File::open(path).map_err(|error| StoreError::io(code, path, error))?;
    let length = file
        .metadata()
        .map_err(|error| StoreError::io(code, path, error))?
        .len();
    let capacity = usize::try_from(length)
        .map_err(|_| StoreError::contract("file-too-large", path.display().to_string()))?;
    let mut bytes = Vec::with_capacity(capacity);
    file.read_to_end(&mut bytes)
        .map_err(|error| StoreError::io(code, path, error))?;
    Ok(bytes)
}

fn validate_staging_relative_path(path: &str) -> Result<(), StoreError> {
    validate_portable_relative_path(path)
        .map_err(|_| StoreError::contract("staging-relative-path", path))
}

#[cfg(not(target_os = "macos"))]
fn join_portable(root: &Path, relative: &str) -> PathBuf {
    let mut path = root.to_path_buf();
    for component in relative.split('/') {
        path.push(component);
    }
    path
}

fn raw_digest(bytes: &[u8]) -> String {
    format!("sha256:{}", digest_hex(bytes))
}

#[cfg(all(test, unix))]
mod tests {
    use std::fs;
    use std::io::{BufRead, BufReader, Write as _};
    use std::os::unix::fs::symlink;
    use std::path::{Path, PathBuf};
    use std::process::{Command, Output, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::thread;
    use std::time::Duration;

    use super::{
        FilesystemStore, SlotPublishAction, StagingRecovery, StoreTransactionIdentity, raw_digest,
        set_mode,
    };
    use crate::canonical::{Value, canonical_bytes, domain_digest, domain_digest_value, parse};
    use crate::{
        AttemptClassification, AttemptStage, BoundedAttemptObservation, InstallationReceipt,
        InstallationVerifierIdentity, LauncherPolicy, OwnedStaging, QualificationArtifacts,
        QualificationCompanionInput, RegistrationRecord, build_installation_receipt,
        parse_launcher_policy, parse_registration_record,
    };

    const POLICY: &[u8] =
        include_bytes!("../../../contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs");
    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));
    const REGISTRATION_DOMAIN: &str = "radishaxiom.checker-runtime-payload-registration.v0.1";
    const POLICY_DOMAIN: &str = "radishaxiom.checker-runtime-launcher-policy.v0.3";
    const QUALIFICATION_DOMAIN: &str = "radishaxiom.checker-runtime-qualification-record.v0.1";
    const INDEPENDENT_RESULT_DOMAIN: &str = "axiom-independent-check-v0.1:result";

    static TEMPORARY_COUNTER: AtomicU64 = AtomicU64::new(0);

    struct TemporaryRoot(PathBuf);

    impl TemporaryRoot {
        fn new() -> Self {
            let sequence = TEMPORARY_COUNTER.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "radishaxiom-store-{}-{sequence}",
                std::process::id()
            ));
            fs::create_dir(&path).unwrap();
            set_mode(&path, 0o700).unwrap();
            Self(fs::canonicalize(path).unwrap())
        }

        fn path(&self) -> &Path {
            &self.0
        }
    }

    impl Drop for TemporaryRoot {
        fn drop(&mut self) {
            if self.0.exists() {
                fs::remove_dir_all(&self.0).unwrap();
            }
        }
    }

    fn object_mut<'a>(value: &'a mut Value, path: &[&str]) -> &'a mut Vec<(String, Value)> {
        let mut current = value;
        for component in path {
            let Value::Object(object) = current else {
                panic!("fixture path must contain objects");
            };
            current = &mut object
                .iter_mut()
                .find(|(name, _)| name == component)
                .unwrap()
                .1;
        }
        let Value::Object(object) = current else {
            panic!("fixture target must be an object");
        };
        object
    }

    fn set_string(value: &mut Value, path: &[&str], replacement: &str) {
        let (parents, leaf) = path.split_at(path.len() - 1);
        let object = object_mut(value, parents);
        let (_, member) = object.iter_mut().find(|(name, _)| name == leaf[0]).unwrap();
        *member = Value::String(replacement.into());
    }

    fn refresh_registration_digest(value: &mut Value) {
        let digest = domain_digest(REGISTRATION_DOMAIN, value, "record_digest").unwrap();
        set_string(value, &["record_digest"], &digest);
    }

    fn synthetic_binary() -> Vec<u8> {
        let mut binary = vec![0_u8; 32];
        binary[..4].copy_from_slice(&[0xcf, 0xfa, 0xed, 0xfe]);
        binary[4..8].copy_from_slice(&0x0100_000c_u32.to_le_bytes());
        binary.extend_from_slice(b"radishaxiom-synthetic-checker");
        binary
    }

    fn synthetic_record(binary: &[u8]) -> RegistrationRecord {
        let mut value = parse(RECORD, false).unwrap();
        set_string(
            &mut value,
            &["artifact", "byte_length"],
            &binary.len().to_string(),
        );
        set_string(&mut value, &["artifact", "raw_sha256"], &raw_digest(binary));
        let distribution = b"synthetic-distribution-for-local-fixtures";
        let distribution_length = distribution.len().to_string();
        let distribution_digest = raw_digest(distribution);
        set_string(
            &mut value,
            &[
                "durable_registration",
                "distribution_package",
                "byte_length",
            ],
            &distribution_length,
        );
        set_string(
            &mut value,
            &["durable_registration", "distribution_package", "raw_sha256"],
            &distribution_digest,
        );
        for field in ["raw_sha256", "digest"] {
            set_string(
                &mut value,
                &[
                    "durable_registration",
                    "provider",
                    "release",
                    "asset",
                    field,
                ],
                &distribution_digest,
            );
        }
        set_string(
            &mut value,
            &[
                "durable_registration",
                "provider",
                "release",
                "asset",
                "byte_length",
            ],
            &distribution_length,
        );
        refresh_registration_digest(&mut value);
        parse_registration_record(&canonical_bytes(&value)).unwrap()
    }

    fn verifier() -> InstallationVerifierIdentity {
        InstallationVerifierIdentity::try_new(
            format!("sha256:{}", "1".repeat(64)),
            "radishaxiom-launcher-conformance-core",
            "0.1-test",
        )
        .unwrap()
    }

    fn fixture() -> (LauncherPolicy, RegistrationRecord, Vec<u8>) {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let binary = synthetic_binary();
        let record = synthetic_record(&binary);
        (policy, record, binary)
    }

    fn string(value: impl Into<String>) -> Value {
        Value::String(value.into())
    }

    fn object<const N: usize>(members: [(&str, Value); N]) -> Value {
        assert!(members.windows(2).all(|pair| pair[0].0 < pair[1].0));
        Value::Object(
            members
                .into_iter()
                .map(|(name, value)| (name.into(), value))
                .collect(),
        )
    }

    fn synthetic_result(record: &RegistrationRecord, outcome: &str) -> Vec<u8> {
        let checker = record.checker();
        canonical_bytes(&object([
            (
                "checker",
                object([
                    ("artifact", string(record.artifact().raw_sha256())),
                    ("name", string(checker.implementation())),
                    ("source", string(checker.source())),
                    ("toolchain", string(checker.toolchain())),
                    ("version", string(checker.version())),
                ]),
            ),
            ("result", object([("kind", string(outcome))])),
            ("result_version", string("0.1")),
        ]))
    }

    fn synthetic_qualification_fixture(
        record: &RegistrationRecord,
    ) -> (LauncherPolicy, InstallationReceipt, QualificationArtifacts) {
        let outcomes = [
            ("ax-b01-correct", "accepted-with-trust"),
            ("chk-digest-01", "rejected"),
            ("chk-resource-01", "incomplete"),
        ];
        let results: Vec<(String, Vec<u8>)> = outcomes
            .iter()
            .map(|(scenario, outcome)| ((*scenario).into(), synthetic_result(record, outcome)))
            .collect();

        let mut policy_value = parse(POLICY, true).unwrap();
        let runtime = object_mut(&mut policy_value, &["runtime_companion"]);
        let (_, Value::Array(rows)) = runtime
            .iter_mut()
            .find(|(name, _)| name == "qualification_scenarios")
            .unwrap()
        else {
            panic!("qualification scenarios must be an array");
        };
        for row in rows {
            let Value::Object(row) = row else {
                panic!("qualification scenario must be an object");
            };
            let Value::String(id) = &row.iter().find(|(name, _)| name == "id").unwrap().1 else {
                panic!("qualification scenario id must be a string");
            };
            let bytes = &results
                .iter()
                .find(|(scenario, _)| scenario == id)
                .unwrap()
                .1;
            let (_, length) = row
                .iter_mut()
                .find(|(name, _)| name == "byte_length")
                .unwrap();
            *length = string(bytes.len().to_string());
            let (_, digest) = row
                .iter_mut()
                .find(|(name, _)| name == "raw_sha256")
                .unwrap();
            *digest = string(raw_digest(bytes));
        }
        let policy_digest = domain_digest(POLICY_DOMAIN, &policy_value, "policy_digest").unwrap();
        set_string(&mut policy_value, &["policy_digest"], &policy_digest);
        let policy = parse_launcher_policy(&canonical_bytes(&policy_value)).unwrap();

        let receipt =
            build_installation_receipt(&policy, record, "2026-08-30T10:00:00Z", &verifier())
                .unwrap();
        let companions: Vec<QualificationCompanionInput> = results
            .iter()
            .map(|(scenario, bytes)| {
                QualificationCompanionInput::try_new(
                    scenario.as_str(),
                    bytes.clone().into_boxed_slice(),
                )
                .unwrap()
            })
            .collect();
        let companion_rows = companions
            .iter()
            .map(|companion| {
                let result = parse(companion.canonical_result(), true).unwrap();
                object([
                    (
                        "byte_length",
                        string(companion.canonical_result().len().to_string()),
                    ),
                    (
                        "document_digest",
                        string(domain_digest_value(INDEPENDENT_RESULT_DOMAIN, &result)),
                    ),
                    (
                        "outcome",
                        string(
                            outcomes
                                .iter()
                                .find(|(id, _)| *id == companion.scenario_id())
                                .unwrap()
                                .1,
                        ),
                    ),
                    ("raw_sha256", string(companion.raw_sha256())),
                    ("scenario_id", string(companion.scenario_id())),
                ])
            })
            .collect();
        let profile = policy.execution_profile();
        let target = record.target();
        let mut qualification_members = vec![
            (
                "artifact".into(),
                object([
                    (
                        "byte_length",
                        string(record.artifact().byte_length().to_string()),
                    ),
                    ("raw_sha256", string(record.artifact().raw_sha256())),
                ]),
            ),
            ("companions".into(), Value::Array(companion_rows)),
            ("digest_domain".into(), string(QUALIFICATION_DOMAIN)),
            (
                "execution_profile".into(),
                object([
                    ("id", string(&*profile.id)),
                    ("path", string(&*profile.path)),
                    ("raw_sha256", string(&*profile.raw_sha256)),
                ]),
            ),
            (
                "format".into(),
                string("radishaxiom-checker-runtime-qualification-record"),
            ),
            ("format_version".into(), string("0.1")),
            (
                "installation_receipt_digest".into(),
                string(receipt.document_digest()),
            ),
            (
                "launcher_policy".into(),
                object([
                    (
                        "format",
                        string("radishaxiom-checker-runtime-launcher-policy"),
                    ),
                    ("format_version", string("0.3")),
                    ("policy_digest", string(policy.document_digest())),
                ]),
            ),
            ("qualified_at".into(), string("2026-08-30T10:01:00Z")),
            (
                "registration".into(),
                object([
                    ("id", string(record.id())),
                    ("record_digest", string(record.document_digest())),
                ]),
            ),
            ("status".into(), string("qualified-installed-inactive")),
            (
                "target".into(),
                object([
                    ("executable_format", string(target.executable_format())),
                    ("goarch", string(target.goarch())),
                    ("goarm64", string(target.variant())),
                    ("goos", string(target.goos())),
                ]),
            ),
        ];
        let body = Value::Object(qualification_members.clone());
        let qualification_digest = domain_digest_value(QUALIFICATION_DOMAIN, &body);
        qualification_members.insert(3, ("document_digest".into(), string(qualification_digest)));
        let qualification_bytes = canonical_bytes(&Value::Object(qualification_members));
        let artifacts = QualificationArtifacts::validate(
            &policy,
            record,
            &receipt,
            qualification_bytes.into_boxed_slice(),
            companions,
        )
        .unwrap();
        (policy, receipt, artifacts)
    }

    fn observation(
        stage: AttemptStage,
        classification: AttemptClassification,
        code: &str,
    ) -> BoundedAttemptObservation {
        BoundedAttemptObservation::try_new(stage, classification, code, "2026-09-01T10:00:00Z")
            .unwrap()
    }

    fn populate_staging(
        staging: &OwnedStaging,
        policy: &LauncherPolicy,
        record: &RegistrationRecord,
        binary: &[u8],
        installed_at: &str,
    ) {
        let executable = policy.installation_layout().executable_relative_path();
        if let Some((parent, _)) = executable.rsplit_once('/') {
            staging.create_directory(parent).unwrap();
        }
        staging
            .write_file_exclusive(executable, binary, 0o755)
            .unwrap();
        let receipt =
            build_installation_receipt(policy, record, installed_at, &verifier()).unwrap();
        staging
            .write_file_exclusive(
                policy.installation_layout().receipt_filename(),
                receipt.canonical_bytes(),
                0o644,
            )
            .unwrap();
    }

    fn transaction(value: &str) -> StoreTransactionIdentity {
        StoreTransactionIdentity::try_new(value).unwrap()
    }

    #[cfg(target_os = "macos")]
    fn helper_command(root: &Path, transaction: &str, mode: &str) -> Command {
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .arg("--exact")
            .arg("store::tests::darwin_process_helper")
            .arg("--nocapture")
            .arg("--test-threads=1")
            .env("RADISHAXIOM_STORE_HELPER_MODE", mode)
            .env("RADISHAXIOM_STORE_HELPER_ROOT", root)
            .env("RADISHAXIOM_STORE_HELPER_TRANSACTION", transaction)
            .env_remove("RADISHAXIOM_STORE_TEST_CRASH_AT");
        command
    }

    #[cfg(target_os = "macos")]
    fn run_helper(root: &Path, transaction: &str, mode: &str) -> Output {
        helper_command(root, transaction, mode).output().unwrap()
    }

    #[cfg(target_os = "macos")]
    fn acquire_with_retry(
        store: &FilesystemStore,
        record: &RegistrationRecord,
    ) -> super::HeldTargetLock {
        for _ in 0..1_000 {
            match store.acquire_target_lock(record.target()) {
                Ok(lock) => return lock,
                Err(error) if error.code() == "target-lock-busy" => {
                    thread::sleep(Duration::from_millis(2));
                }
                Err(error) => panic!("target lock failed: {error}"),
            }
        }
        panic!("target lock did not become available");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn darwin_process_helper() {
        let Ok(mode) = std::env::var("RADISHAXIOM_STORE_HELPER_MODE") else {
            return;
        };
        let root = PathBuf::from(std::env::var_os("RADISHAXIOM_STORE_HELPER_ROOT").unwrap());
        let transaction_id = std::env::var("RADISHAXIOM_STORE_HELPER_TRANSACTION").unwrap();
        let store = FilesystemStore::open(&root).unwrap();
        let (policy, record, binary) = fixture();

        if mode == "qualification" {
            let (_, _, qualification) = synthetic_qualification_fixture(&record);
            for _ in 0..1_000 {
                match store.create_qualification_exclusive(&record, &qualification) {
                    Ok(_) => {
                        println!("qualification=created");
                        return;
                    }
                    Err(error) if error.code() == "qualification-exists" => {
                        println!("qualification=exists");
                        return;
                    }
                    Err(error) if error.code() == "registration-lock-busy" => {
                        thread::sleep(Duration::from_millis(2));
                    }
                    Err(error) => panic!("qualification persistence failed: {error}"),
                }
            }
            panic!("qualification registration lock did not become available");
        }

        if mode == "attempt" {
            let code = format!("process-{transaction_id}");
            let observation = observation(
                AttemptStage::Invocation,
                AttemptClassification::ProcessFailure,
                &code,
            );
            for _ in 0..1_000 {
                match store.append_attempt(&record, &observation) {
                    Ok(attempt) => {
                        println!("attempt={}", attempt.ordinal());
                        return;
                    }
                    Err(error) if error.code() == "registration-lock-busy" => {
                        thread::sleep(Duration::from_millis(2));
                    }
                    Err(error) => panic!("attempt append failed: {error}"),
                }
            }
            panic!("attempt registration lock did not become available");
        }

        let lock = acquire_with_retry(&store, &record);

        if mode == "hold-lock" {
            println!("LOCKED");
            std::io::stdout().flush().unwrap();
            loop {
                thread::park();
            }
        }

        let staging = store
            .create_owned_staging(&lock, &transaction(&transaction_id))
            .unwrap();
        if mode == "after-staging" {
            std::process::exit(88);
        }
        if mode == "after-binary" {
            let executable = policy.installation_layout().executable_relative_path();
            if let Some((parent, _)) = executable.rsplit_once('/') {
                staging.create_directory(parent).unwrap();
            }
            staging
                .write_file_exclusive(executable, &binary, 0o755)
                .unwrap();
            std::process::exit(88);
        }
        populate_staging(&staging, &policy, &record, &binary, "2026-08-30T10:00:00Z");
        if mode == "after-receipt" {
            std::process::exit(88);
        }
        let verified = store
            .verify_owned_staging(&lock, staging, &policy, &record)
            .unwrap();
        if mode == "after-verify" {
            std::process::exit(88);
        }
        let publication = store.publish_slot_exclusive(&lock, verified).unwrap();
        println!("action={:?}", publication.action());
        std::io::stdout().flush().unwrap();
        if mode == "after-publish" {
            std::process::exit(88);
        }
    }

    #[cfg(target_os = "macos")]
    fn retry_exact_publication(
        root: &Path,
        transaction_id: &str,
    ) -> (SlotPublishAction, StagingRecovery) {
        let store = FilesystemStore::open(root).unwrap();
        let (policy, record, binary) = fixture();
        let lock = store.acquire_target_lock(record.target()).unwrap();
        let prior = store
            .discard_owned_staging(&lock, &transaction(transaction_id))
            .unwrap();
        let retry = format!("{transaction_id}-retry");
        let staging = store
            .create_owned_staging(&lock, &transaction(&retry))
            .unwrap();
        populate_staging(&staging, &policy, &record, &binary, "2026-08-30T10:00:00Z");
        let verified = store
            .verify_owned_staging(&lock, staging, &policy, &record)
            .unwrap();
        let publication = store.publish_slot_exclusive(&lock, verified).unwrap();
        assert!(store.read_slot_exact(&policy, &record).is_ok());
        (publication.action(), prior)
    }

    #[test]
    fn root_and_transaction_boundaries_are_closed() {
        for invalid in ["", ".", "..", "/absolute", "a/b", "unsafe value"] {
            assert_eq!(
                StoreTransactionIdentity::try_new(invalid)
                    .unwrap_err()
                    .code(),
                "invalid-transaction-identity"
            );
        }
        let relative = Path::new("relative-store-root");
        assert_eq!(
            FilesystemStore::open(relative).err().unwrap().code(),
            "store-root-not-absolute"
        );

        let root = TemporaryRoot::new();
        set_mode(root.path(), 0o755).unwrap();
        assert_eq!(
            FilesystemStore::open(root.path()).err().unwrap().code(),
            "store-root-boundary"
        );
    }

    #[test]
    fn target_lock_is_real_exclusive_and_store_scoped() {
        let root = TemporaryRoot::new();
        let first_store = FilesystemStore::open(root.path()).unwrap();
        let second_store = FilesystemStore::open(root.path()).unwrap();
        let (_, record, _) = fixture();
        let first_lock = first_store.acquire_target_lock(record.target()).unwrap();
        assert_eq!(
            second_store
                .acquire_target_lock(record.target())
                .err()
                .unwrap()
                .code(),
            "target-lock-busy"
        );

        let other_root = TemporaryRoot::new();
        let other_store = FilesystemStore::open(other_root.path()).unwrap();
        assert_eq!(
            other_store
                .create_owned_staging(&first_lock, &transaction("foreign"))
                .err()
                .unwrap()
                .code(),
            "foreign-target-lock"
        );
        drop(first_lock);
        assert!(second_store.acquire_target_lock(record.target()).is_ok());
    }

    #[test]
    fn publish_reuse_read_and_mismatch_match_python_oracle() {
        let root = TemporaryRoot::new();
        let store = FilesystemStore::open(root.path()).unwrap();
        let (policy, record, binary) = fixture();
        let lock = store.acquire_target_lock(record.target()).unwrap();

        let first = store
            .create_owned_staging(&lock, &transaction("first"))
            .unwrap();
        populate_staging(&first, &policy, &record, &binary, "2026-08-30T10:00:00Z");
        let first = store
            .verify_owned_staging(&lock, first, &policy, &record)
            .unwrap();
        let published = store.publish_slot_exclusive(&lock, first).unwrap();
        assert_eq!(published.action(), SlotPublishAction::Published);
        assert_eq!(
            published.slot().verification().tree_digest(),
            "sha256:856141f47eceb4962bc290c8d2bcacfb39ef6a6e90631af6d241e5b5ab4f81fd"
        );
        assert_eq!(
            store.read_slot_exact(&policy, &record).unwrap(),
            published.slot().clone()
        );

        let second = store
            .create_owned_staging(&lock, &transaction("second"))
            .unwrap();
        let second_path = second.path.clone();
        populate_staging(&second, &policy, &record, &binary, "2026-08-30T10:00:00Z");
        let second = store
            .verify_owned_staging(&lock, second, &policy, &record)
            .unwrap();
        let reused = store.publish_slot_exclusive(&lock, second).unwrap();
        assert_eq!(reused.action(), SlotPublishAction::Reused);
        assert_eq!(reused.slot(), published.slot());
        assert!(!second_path.exists());

        let mismatch = store
            .create_owned_staging(&lock, &transaction("mismatch"))
            .unwrap();
        let mismatch_path = mismatch.path.clone();
        populate_staging(&mismatch, &policy, &record, &binary, "2026-08-30T10:00:01Z");
        let mismatch = store
            .verify_owned_staging(&lock, mismatch, &policy, &record)
            .unwrap();
        assert_eq!(
            store
                .publish_slot_exclusive(&lock, mismatch)
                .unwrap_err()
                .code(),
            "existing-slot-mismatch"
        );
        assert!(mismatch_path.exists());
        assert_eq!(
            store.read_slot_exact(&policy, &record).unwrap(),
            published.slot().clone()
        );
    }

    #[test]
    fn staging_inventory_links_modes_and_recovery_fail_closed() {
        let root = TemporaryRoot::new();
        let store = FilesystemStore::open(root.path()).unwrap();
        let (policy, record, binary) = fixture();
        let lock = store.acquire_target_lock(record.target()).unwrap();

        let extra = store
            .create_owned_staging(&lock, &transaction("extra"))
            .unwrap();
        populate_staging(&extra, &policy, &record, &binary, "2026-08-30T10:00:00Z");
        extra
            .write_file_exclusive("extra", b"closed", 0o644)
            .unwrap();
        assert_eq!(
            store
                .verify_owned_staging(&lock, extra, &policy, &record)
                .err()
                .unwrap()
                .code(),
            "slot-inventory-mismatch"
        );

        let hardlink = store
            .create_owned_staging(&lock, &transaction("hardlink"))
            .unwrap();
        populate_staging(&hardlink, &policy, &record, &binary, "2026-08-30T10:00:00Z");
        let receipt_path = hardlink
            .path
            .join(policy.installation_layout().receipt_filename());
        fs::hard_link(&receipt_path, root.path().join("receipt-hardlink")).unwrap();
        assert_eq!(
            store
                .verify_owned_staging(&lock, hardlink, &policy, &record)
                .err()
                .unwrap()
                .code(),
            "receipt-file-boundary"
        );

        let wrong_mode = store
            .create_owned_staging(&lock, &transaction("wrong-mode"))
            .unwrap();
        populate_staging(
            &wrong_mode,
            &policy,
            &record,
            &binary,
            "2026-08-30T10:00:00Z",
        );
        set_mode(
            &wrong_mode
                .path
                .join(policy.installation_layout().receipt_filename()),
            0o600,
        )
        .unwrap();
        assert_eq!(
            store
                .verify_owned_staging(&lock, wrong_mode, &policy, &record)
                .err()
                .unwrap()
                .code(),
            "receipt-file-boundary"
        );

        let linked = store
            .create_owned_staging(&lock, &transaction("linked"))
            .unwrap();
        populate_staging(&linked, &policy, &record, &binary, "2026-08-30T10:00:00Z");
        let executable = linked
            .path
            .join(policy.installation_layout().executable_relative_path());
        fs::remove_file(&executable).unwrap();
        symlink(
            linked
                .path
                .join(policy.installation_layout().receipt_filename()),
            &executable,
        )
        .unwrap();
        assert_eq!(
            store
                .verify_owned_staging(&lock, linked, &policy, &record)
                .err()
                .unwrap()
                .code(),
            "symbolic-link"
        );

        let recovery = transaction("recovery");
        let abandoned = store.create_owned_staging(&lock, &recovery).unwrap();
        let abandoned_path = abandoned.path.clone();
        drop(abandoned);
        assert_eq!(
            store.discard_owned_staging(&lock, &recovery).unwrap(),
            StagingRecovery::Discarded
        );
        assert!(!abandoned_path.exists());
        assert_eq!(
            store.discard_owned_staging(&lock, &recovery).unwrap(),
            StagingRecovery::Absent
        );

        let linked_recovery = transaction("linked-recovery");
        let abandoned = store.create_owned_staging(&lock, &linked_recovery).unwrap();
        let abandoned_path = abandoned.path.clone();
        drop(abandoned);
        fs::remove_dir(&abandoned_path).unwrap();
        let outside = root.path().join("outside-staging");
        fs::create_dir(&outside).unwrap();
        symlink(&outside, &abandoned_path).unwrap();
        assert_eq!(
            store
                .discard_owned_staging(&lock, &linked_recovery)
                .unwrap_err()
                .code(),
            "unowned-staging"
        );
        assert!(outside.is_dir());
    }

    #[test]
    fn qualification_is_exclusive_and_attempts_are_append_only() {
        let root = TemporaryRoot::new();
        let store = FilesystemStore::open(root.path()).unwrap();
        let (slot_policy, record, binary) = fixture();
        let lock = store.acquire_target_lock(record.target()).unwrap();
        let staging = store
            .create_owned_staging(&lock, &transaction("evidence-slot"))
            .unwrap();
        populate_staging(
            &staging,
            &slot_policy,
            &record,
            &binary,
            "2026-08-30T10:00:00Z",
        );
        let verified = store
            .verify_owned_staging(&lock, staging, &slot_policy, &record)
            .unwrap();
        let slot = store.publish_slot_exclusive(&lock, verified).unwrap();
        let receipt_path = root
            .path()
            .join(slot.slot().relative_identity())
            .join(slot_policy.installation_layout().receipt_filename());
        let original_receipt = fs::read(&receipt_path).unwrap();
        drop(lock);

        let (_, _, qualification) = synthetic_qualification_fixture(&record);
        let persisted = store
            .create_qualification_exclusive(&record, &qualification)
            .unwrap();
        assert!(persisted.relative_identity().starts_with("qualifications/"));
        let qualification_root = root.path().join(persisted.relative_identity());
        assert_eq!(
            fs::read(qualification_root.join("qualification-record-v0.1.jcs")).unwrap(),
            qualification.qualification_record()
        );
        assert_eq!(fs::read(&receipt_path).unwrap(), original_receipt);
        assert_eq!(
            store
                .create_qualification_exclusive(&record, &qualification)
                .unwrap_err()
                .code(),
            "qualification-exists"
        );

        let first_observation = observation(
            AttemptStage::Installation,
            AttemptClassification::InstallationFailed,
            "distribution-digest-mismatch",
        );
        let first = store.append_attempt(&record, &first_observation).unwrap();
        let second = store
            .append_attempt(
                &record,
                &observation(
                    AttemptStage::Qualification,
                    AttemptClassification::ResourceExhausted,
                    "stdout-limit",
                ),
            )
            .unwrap();
        let repeated = store.append_attempt(&record, &first_observation).unwrap();
        assert_eq!(
            (first.ordinal(), second.ordinal(), repeated.ordinal()),
            (0, 1, 2)
        );
        assert_ne!(first.relative_identity(), repeated.relative_identity());
        for attempt in [&first, &second, &repeated] {
            let bytes = fs::read(
                root.path()
                    .join(attempt.relative_identity())
                    .join("attempt-v0.1.jcs"),
            )
            .unwrap();
            assert!(
                !bytes
                    .windows(root.path().as_os_str().len())
                    .any(|window| window == root.path().as_os_str().as_encoded_bytes())
            );
        }
        assert_eq!(fs::read(&receipt_path).unwrap(), original_receipt);
    }

    #[test]
    fn qualification_matches_python_canonical_golden() {
        let (_, record, _) = fixture();
        let (_, _, qualification) = synthetic_qualification_fixture(&record);
        assert_eq!(qualification.qualification_record().len(), 2_020);
        assert_eq!(
            raw_digest(qualification.qualification_record()),
            "sha256:e09b055f2784a3df2e9fc81c4f204f083484ba04231cba03069ea55a0b916f1a"
        );
        assert_eq!(
            qualification.document_digest(),
            "sha256:c82f6576c49d55f4fcc30b6e2419e5497bfd2e10aaa720dedd062baf71cd3b97"
        );
    }

    #[test]
    fn qualification_input_binding_drift_fails_closed() {
        let (_, record, _) = fixture();
        let (policy, receipt, qualification) = synthetic_qualification_fixture(&record);
        let mut missing = qualification.companions().to_vec();
        missing.pop();
        assert_eq!(
            QualificationArtifacts::validate(
                &policy,
                &record,
                &receipt,
                qualification.qualification_record(),
                missing,
            )
            .unwrap_err()
            .code(),
            "qualification-scenario-set"
        );

        let other_record = synthetic_record(b"different-synthetic-checker");
        let other_receipt =
            build_installation_receipt(&policy, &other_record, "2026-08-30T10:00:00Z", &verifier())
                .unwrap();
        let mut drifted = parse(qualification.qualification_record(), true).unwrap();
        set_string(
            &mut drifted,
            &["installation_receipt_digest"],
            other_receipt.document_digest(),
        );
        let digest = domain_digest(QUALIFICATION_DOMAIN, &drifted, "document_digest").unwrap();
        set_string(&mut drifted, &["document_digest"], &digest);
        assert_eq!(
            QualificationArtifacts::validate(
                &policy,
                &record,
                &other_receipt,
                canonical_bytes(&drifted),
                qualification.companions().to_vec(),
            )
            .unwrap_err()
            .code(),
            "receipt-binding-mismatch"
        );
    }

    #[test]
    fn qualification_and_attempt_inventory_tampering_fail_closed() {
        let root = TemporaryRoot::new();
        let store = FilesystemStore::open(root.path()).unwrap();
        let (_, record, _) = fixture();
        let (_, _, qualification) = synthetic_qualification_fixture(&record);
        let persisted = store
            .create_qualification_exclusive(&record, &qualification)
            .unwrap();
        let qualification_path = root.path().join(persisted.relative_identity());
        fs::write(qualification_path.join("extra"), b"unexpected").unwrap();
        set_mode(&qualification_path.join("extra"), 0o644).unwrap();
        assert_eq!(
            store
                .create_qualification_exclusive(&record, &qualification)
                .unwrap_err()
                .code(),
            "qualification-existing-mismatch"
        );

        let first = store
            .append_attempt(
                &record,
                &observation(
                    AttemptStage::Invocation,
                    AttemptClassification::ProcessFailure,
                    "process-exit",
                ),
            )
            .unwrap();
        let first_file = root
            .path()
            .join(first.relative_identity())
            .join("attempt-v0.1.jcs");
        fs::hard_link(&first_file, root.path().join("attempt-hardlink")).unwrap();
        assert_eq!(
            store
                .append_attempt(
                    &record,
                    &observation(
                        AttemptStage::Invocation,
                        AttemptClassification::IdentityFailure,
                        "postflight-drift",
                    ),
                )
                .unwrap_err()
                .code(),
            "attempt-file-boundary"
        );
        let attempts_parent = root
            .path()
            .join(first.relative_identity().rsplit_once('/').unwrap().0);
        assert_eq!(fs::read_dir(attempts_parent).unwrap().count(), 1);
    }

    #[test]
    fn attempt_inventory_gap_and_document_drift_fail_closed() {
        let root = TemporaryRoot::new();
        let store = FilesystemStore::open(root.path()).unwrap();
        let (_, record, _) = fixture();
        let first = store
            .append_attempt(
                &record,
                &observation(
                    AttemptStage::Invocation,
                    AttemptClassification::ProcessFailure,
                    "process-exit",
                ),
            )
            .unwrap();
        let first_path = root.path().join(first.relative_identity());
        let name = first_path.file_name().unwrap().to_str().unwrap();
        let gap_name = format!("{:020}{}", 1, &name[20..]);
        fs::rename(&first_path, first_path.parent().unwrap().join(gap_name)).unwrap();
        assert_eq!(
            store
                .append_attempt(
                    &record,
                    &observation(
                        AttemptStage::Invocation,
                        AttemptClassification::IdentityFailure,
                        "postflight-drift",
                    ),
                )
                .unwrap_err()
                .code(),
            "attempt-inventory-gap"
        );

        let root = TemporaryRoot::new();
        let store = FilesystemStore::open(root.path()).unwrap();
        let first = store
            .append_attempt(
                &record,
                &observation(
                    AttemptStage::Invocation,
                    AttemptClassification::ProcessFailure,
                    "process-exit",
                ),
            )
            .unwrap();
        let file = root
            .path()
            .join(first.relative_identity())
            .join("attempt-v0.1.jcs");
        let mut drifted = fs::read(&file).unwrap();
        let index = drifted
            .windows(b"process-exit".len())
            .position(|window| window == b"process-exit")
            .unwrap();
        drifted[index] = b'q';
        fs::write(&file, drifted).unwrap();
        set_mode(&file, 0o644).unwrap();
        assert_eq!(
            store
                .append_attempt(
                    &record,
                    &observation(
                        AttemptStage::Invocation,
                        AttemptClassification::IdentityFailure,
                        "postflight-drift",
                    ),
                )
                .unwrap_err()
                .code(),
            "attempt-document"
        );
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn qualification_and_attempt_process_concurrency_is_serialized() {
        let root = TemporaryRoot::new();
        let first = helper_command(root.path(), "qualification-first", "qualification")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let second = helper_command(root.path(), "qualification-second", "qualification")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let first = first.wait_with_output().unwrap();
        let second = second.wait_with_output().unwrap();
        assert!(first.status.success(), "{first:?}");
        assert!(second.status.success(), "{second:?}");
        let combined = format!(
            "{}{}",
            String::from_utf8(first.stdout).unwrap(),
            String::from_utf8(second.stdout).unwrap()
        );
        assert_eq!(
            combined.matches("qualification=created").count(),
            1,
            "{combined}"
        );
        assert_eq!(
            combined.matches("qualification=exists").count(),
            1,
            "{combined}"
        );

        let first = helper_command(root.path(), "attempt-first", "attempt")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let second = helper_command(root.path(), "attempt-second", "attempt")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let first = first.wait_with_output().unwrap();
        let second = second.wait_with_output().unwrap();
        assert!(first.status.success(), "{first:?}");
        assert!(second.status.success(), "{second:?}");
        let combined = format!(
            "{}{}",
            String::from_utf8(first.stdout).unwrap(),
            String::from_utf8(second.stdout).unwrap()
        );
        assert_eq!(combined.matches("attempt=0").count(), 1, "{combined}");
        assert_eq!(combined.matches("attempt=1").count(), 1, "{combined}");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn evidence_process_crash_matrix_preserves_only_published_state() {
        for checkpoint in [
            "qualification-after-lock",
            "qualification-after-artifacts",
            "qualification-after-verify",
        ] {
            let root = TemporaryRoot::new();
            let mut command = helper_command(root.path(), "qualification-crash", "qualification");
            let output = command
                .env("RADISHAXIOM_STORE_TEST_CRASH_AT", checkpoint)
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(89), "{checkpoint}: {output:?}");
            let retry = run_helper(root.path(), "qualification-retry", "qualification");
            assert!(retry.status.success(), "{checkpoint}: {retry:?}");
            assert!(
                String::from_utf8(retry.stdout)
                    .unwrap()
                    .contains("qualification=created"),
                "{checkpoint}"
            );
        }

        for checkpoint in [
            "qualification-after-rename",
            "qualification-after-parent-sync",
        ] {
            let root = TemporaryRoot::new();
            let mut command = helper_command(root.path(), "qualification-crash", "qualification");
            let output = command
                .env("RADISHAXIOM_STORE_TEST_CRASH_AT", checkpoint)
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(89), "{checkpoint}: {output:?}");
            let retry = run_helper(root.path(), "qualification-retry", "qualification");
            assert!(retry.status.success(), "{checkpoint}: {retry:?}");
            assert!(
                String::from_utf8(retry.stdout)
                    .unwrap()
                    .contains("qualification=exists"),
                "{checkpoint}"
            );
        }

        for checkpoint in [
            "attempt-after-lock",
            "attempt-after-file",
            "attempt-after-verify",
        ] {
            let root = TemporaryRoot::new();
            let mut command = helper_command(root.path(), "attempt-crash", "attempt");
            let output = command
                .env("RADISHAXIOM_STORE_TEST_CRASH_AT", checkpoint)
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(89), "{checkpoint}: {output:?}");
            let retry = run_helper(root.path(), "attempt-crash", "attempt");
            assert!(retry.status.success(), "{checkpoint}: {retry:?}");
            assert!(
                String::from_utf8(retry.stdout)
                    .unwrap()
                    .contains("attempt=0"),
                "{checkpoint}"
            );
        }

        for checkpoint in ["attempt-after-rename", "attempt-after-parent-sync"] {
            let root = TemporaryRoot::new();
            let mut command = helper_command(root.path(), "attempt-crash", "attempt");
            let output = command
                .env("RADISHAXIOM_STORE_TEST_CRASH_AT", checkpoint)
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(89), "{checkpoint}: {output:?}");
            let retry = run_helper(root.path(), "attempt-crash", "attempt");
            assert!(retry.status.success(), "{checkpoint}: {retry:?}");
            assert!(
                String::from_utf8(retry.stdout)
                    .unwrap()
                    .contains("attempt=1"),
                "{checkpoint}"
            );
        }
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn native_process_crash_matrix_recovers_without_false_success() {
        for (mode, transaction_id) in [
            ("after-staging", "crash-staging"),
            ("after-binary", "crash-binary"),
            ("after-receipt", "crash-receipt"),
            ("after-verify", "crash-verified"),
        ] {
            let root = TemporaryRoot::new();
            let output = run_helper(root.path(), transaction_id, mode);
            assert_eq!(output.status.code(), Some(88), "{mode}: {output:?}");
            let store = FilesystemStore::open(root.path()).unwrap();
            let (policy, record, _) = fixture();
            let lock = store.acquire_target_lock(record.target()).unwrap();
            assert_eq!(
                store
                    .discard_owned_staging(&lock, &transaction(transaction_id))
                    .unwrap(),
                StagingRecovery::Discarded,
                "{mode}"
            );
            assert!(store.read_slot_exact(&policy, &record).is_err(), "{mode}");
        }

        for (checkpoint, transaction_id) in [
            ("after-exclusive-rename", "crash-after-rename"),
            ("after-parent-sync", "crash-after-parent-sync"),
        ] {
            let root = TemporaryRoot::new();
            let mut command = helper_command(root.path(), transaction_id, "publish");
            let output = command
                .env("RADISHAXIOM_STORE_TEST_CRASH_AT", checkpoint)
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(89), "{checkpoint}: {output:?}");
            let (action, prior) = retry_exact_publication(root.path(), transaction_id);
            assert_eq!(action, SlotPublishAction::Reused, "{checkpoint}");
            assert_eq!(prior, StagingRecovery::Absent, "{checkpoint}");
        }

        let root = TemporaryRoot::new();
        let output = run_helper(root.path(), "crash-after-publish", "after-publish");
        assert_eq!(output.status.code(), Some(88), "{output:?}");
        let (action, prior) = retry_exact_publication(root.path(), "crash-after-publish");
        assert_eq!(action, SlotPublishAction::Reused);
        assert_eq!(prior, StagingRecovery::Absent);
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn independent_publishers_and_killed_lock_holder_recover() {
        let root = TemporaryRoot::new();
        let first = helper_command(root.path(), "publisher-first", "publish")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let second = helper_command(root.path(), "publisher-second", "publish")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let first = first.wait_with_output().unwrap();
        let second = second.wait_with_output().unwrap();
        assert!(first.status.success(), "{first:?}");
        assert!(second.status.success(), "{second:?}");
        let combined = format!(
            "{}{}",
            String::from_utf8(first.stdout).unwrap(),
            String::from_utf8(second.stdout).unwrap()
        );
        assert_eq!(
            combined.matches("action=Published").count(),
            1,
            "{combined}"
        );
        assert_eq!(combined.matches("action=Reused").count(), 1, "{combined}");

        let mut holder = helper_command(root.path(), "killed-holder", "hold-lock")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let stdout = holder.stdout.take().unwrap();
        let mut lines = BufReader::new(stdout).lines();
        let mut locked = false;
        for line in lines.by_ref().take(8) {
            if line.unwrap().contains("LOCKED") {
                locked = true;
                break;
            }
        }
        assert!(locked, "lock helper did not reach checkpoint");
        holder.kill().unwrap();
        assert!(!holder.wait().unwrap().success());

        let store = FilesystemStore::open(root.path()).unwrap();
        let (_, record, _) = fixture();
        assert!(store.acquire_target_lock(record.target()).is_ok());
    }
}
