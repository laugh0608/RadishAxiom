use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;

#[cfg(unix)]
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};

use crate::canonical::{Value, domain_digest_value};
use crate::policy::LauncherPolicy;
use crate::portable_path::validate_portable_relative_path;
use crate::receipt::{parse_installation_receipt, slot_relative_identity};
use crate::registration::RegistrationRecord;
use crate::selection::NativeTarget;
use crate::sha256::digest_hex;

pub const CHECKER_RUNTIME_STORE_INTERFACE: &str = "checker-runtime-store-v0.1";
const SLOT_TREE_DOMAIN: &str = "radishaxiom.checker-runtime-slot-tree.v0.1";

#[derive(Debug)]
pub struct StoreError {
    code: &'static str,
    path: Box<str>,
    source: Option<io::Error>,
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
            source: Some(source),
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
        self.source.as_ref().map(|source| source as _)
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
}

impl OwnedStaging {
    pub fn transaction(&self) -> &StoreTransactionIdentity {
        &self.transaction
    }

    pub fn create_directory(&self, relative_path: &str) -> Result<(), StoreError> {
        validate_staging_relative_path(relative_path)?;
        let mut current = self.path.clone();
        for component in relative_path.split('/') {
            current.push(component);
            ensure_directory(&current, 0o755, "staging-directory-boundary")?;
        }
        Ok(())
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
        #[cfg(not(unix))]
        {
            let _ = canonical_private_root;
            return Err(StoreError::contract("unsupported-store-platform", "$"));
        }

        #[cfg(unix)]
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
            fs::TryLockError::Error(source) => StoreError::io("target-lock-failed", &path, source),
        })?;
        Ok(HeldTargetLock {
            store: Arc::clone(&self.inner),
            target: target.clone(),
            file,
        })
    }

    pub fn create_owned_staging(
        &self,
        lock: &HeldTargetLock,
        transaction: &StoreTransactionIdentity,
    ) -> Result<OwnedStaging, StoreError> {
        self.validate_lock(lock, lock.target())?;
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
                fs::rename(&verified.staging.path, &final_path)
                    .map_err(|error| StoreError::io("slot-publish-rename", &final_path, error))?;
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

    pub fn read_slot_exact(
        &self,
        policy: &LauncherPolicy,
        record: &RegistrationRecord,
    ) -> Result<InstalledInactiveSlot, StoreError> {
        if !policy.supports(record.target()) {
            return Err(StoreError::contract("unsupported-target", "$"));
        }
        let relative_identity = slot_relative_identity(record);
        let path = join_portable(&self.inner.root, &relative_identity);
        let verification = verify_slot_path(&self.inner.root, &path, policy, record)?;
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
            Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(StagingRecovery::Absent),
            Err(error) => Err(StoreError::io("staging-recovery-metadata", &path, error)),
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

struct SlotEntries {
    files: BTreeMap<String, PathBuf>,
    directories: BTreeMap<String, PathBuf>,
}

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

fn validate_directory(path: &Path, mode: u32, code: &'static str) -> Result<(), StoreError> {
    let metadata = fs::symlink_metadata(path).map_err(|error| StoreError::io(code, path, error))?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() || file_mode_from(&metadata) != mode
    {
        return Err(StoreError::contract(code, path.display().to_string()));
    }
    Ok(())
}

fn validate_regular_file(path: &Path, mode: u32, code: &'static str) -> Result<(), StoreError> {
    let metadata = fs::symlink_metadata(path).map_err(|error| StoreError::io(code, path, error))?;
    validate_regular_metadata(path, &metadata, mode, code)
}

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

fn file_mode(path: &Path) -> Result<u32, StoreError> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| StoreError::io("entry-mode-metadata", path, error))?;
    Ok(file_mode_from(&metadata))
}

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
    use std::os::unix::fs::symlink;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};

    use super::{
        FilesystemStore, SlotPublishAction, StagingRecovery, StoreTransactionIdentity, raw_digest,
        set_mode,
    };
    use crate::canonical::{Value, canonical_bytes, domain_digest, parse};
    use crate::{
        InstallationVerifierIdentity, LauncherPolicy, OwnedStaging, RegistrationRecord,
        build_installation_receipt, parse_launcher_policy, parse_registration_record,
    };

    const POLICY: &[u8] =
        include_bytes!("../../../contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs");
    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));
    const REGISTRATION_DOMAIN: &str = "radishaxiom.checker-runtime-payload-registration.v0.1";

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
}
