use std::error::Error;
use std::ffi::{CStr, CString};
use std::fmt;
use std::fs::{self, File, Metadata, Permissions};
use std::io::{self, Read, Seek, Write};
use std::os::fd::{AsRawFd, FromRawFd, IntoRawFd, RawFd};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::path::Path;
use std::ptr::NonNull;

const RENAME_NOFOLLOW_ANY: libc::c_uint = 0x0000_0010;
const RENAME_RESOLVE_BENEATH: libc::c_uint = 0x0000_0020;
const EXCLUSIVE_RENAME_FLAGS: libc::c_uint =
    libc::RENAME_EXCL | RENAME_NOFOLLOW_ANY | RENAME_RESOLVE_BENEATH;

#[derive(Debug)]
pub struct PlatformError {
    operation: &'static str,
    component: Box<str>,
    source: io::Error,
}

impl PlatformError {
    fn new(operation: &'static str, component: impl Into<Box<str>>, source: io::Error) -> Self {
        Self {
            operation,
            component: component.into(),
            source,
        }
    }

    fn last(operation: &'static str, component: &str) -> Self {
        Self::new(operation, component, io::Error::last_os_error())
    }

    fn invalid(operation: &'static str, component: impl Into<Box<str>>) -> Self {
        Self::new(
            operation,
            component,
            io::Error::from(io::ErrorKind::InvalidInput),
        )
    }

    pub fn operation(&self) -> &'static str {
        self.operation
    }

    pub fn component(&self) -> &str {
        &self.component
    }

    pub fn raw_os_error(&self) -> Option<i32> {
        self.source.raw_os_error()
    }

    pub fn io_kind(&self) -> io::ErrorKind {
        self.source.kind()
    }

    pub fn is_symlink_loop(&self) -> bool {
        self.raw_os_error() == Some(libc::ELOOP)
    }

    pub fn is_cross_device(&self) -> bool {
        self.raw_os_error() == Some(libc::EXDEV)
    }

    pub fn is_unsupported_capability(&self) -> bool {
        matches!(self.raw_os_error(), Some(value) if value == libc::EINVAL || value == libc::ENOTSUP)
    }
}

impl fmt::Display for PlatformError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "{}: {}: {}",
            self.operation, self.component, self.source
        )
    }
}

impl Error for PlatformError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        Some(&self.source)
    }
}

#[derive(Debug)]
pub struct Directory {
    file: File,
}

#[derive(Debug)]
pub struct RegularFile {
    file: File,
}

#[derive(Debug)]
pub enum Entry {
    Directory { name: String, directory: Directory },
    File { name: String, file: RegularFile },
}

impl Entry {
    pub fn name(&self) -> &str {
        match self {
            Self::Directory { name, .. } | Self::File { name, .. } => name,
        }
    }
}

impl Directory {
    pub fn open_private_root(path: &Path) -> Result<Self, PlatformError> {
        let display = path.display().to_string();
        if !path.is_absolute() {
            return Err(PlatformError::invalid("root-not-absolute", display));
        }
        let before = fs::symlink_metadata(path)
            .map_err(|source| PlatformError::new("root-metadata", display.as_str(), source))?;
        if before.file_type().is_symlink()
            || !before.is_dir()
            || mode(&before) != 0o700
            || before.uid() != effective_uid()
        {
            return Err(PlatformError::invalid("root-boundary", display));
        }
        let canonical = fs::canonicalize(path)
            .map_err(|source| PlatformError::new("root-canonicalize", display.as_str(), source))?;
        if canonical != path {
            return Err(PlatformError::invalid("root-not-canonical", display));
        }
        let path = CString::new(path.as_os_str().as_bytes())
            .map_err(|_| PlatformError::invalid("root-path", display.as_str()))?;
        let flags = libc::O_RDONLY | libc::O_DIRECTORY | libc::O_CLOEXEC | libc::O_NOFOLLOW;
        // SAFETY: `path` is NUL-terminated, and the returned descriptor is checked before ownership.
        let raw = unsafe { libc::open(path.as_ptr(), flags) };
        let file = owned_file(raw, "root-open", display.as_str())?;
        let after = file
            .metadata()
            .map_err(|source| PlatformError::new("root-fd-metadata", display.as_str(), source))?;
        if !after.is_dir()
            || mode(&after) != 0o700
            || after.uid() != effective_uid()
            || before.dev() != after.dev()
            || before.ino() != after.ino()
        {
            return Err(PlatformError::invalid("root-identity", display));
        }
        Ok(Self { file })
    }

    pub fn open_directory(&self, component: &str) -> Result<Self, PlatformError> {
        let component = component_cstring(component, "directory-component")?;
        let flags = libc::O_RDONLY | libc::O_DIRECTORY | libc::O_CLOEXEC | libc::O_NOFOLLOW_ANY;
        let file = openat_file(
            self.file.as_raw_fd(),
            &component,
            flags,
            0,
            "directory-open",
        )?;
        let metadata = metadata(&file, "directory-metadata", &component)?;
        if !metadata.is_dir() {
            return Err(PlatformError::invalid(
                "directory-boundary",
                component_text(&component),
            ));
        }
        Ok(Self { file })
    }

    pub fn try_clone(&self) -> Result<Self, PlatformError> {
        self.file
            .try_clone()
            .map(|file| Self { file })
            .map_err(|source| PlatformError::new("directory-duplicate", "$", source))
    }

    pub fn create_directory_exclusive(
        &self,
        component: &str,
        expected_mode: u32,
    ) -> Result<Self, PlatformError> {
        validate_mode(expected_mode, "directory-mode", component)?;
        let component_c = component_cstring(component, "directory-component")?;
        // SAFETY: the parent descriptor is owned, the component is one NUL-terminated name,
        // and the mode value was restricted to permission bits.
        let result = unsafe {
            libc::mkdirat(
                self.file.as_raw_fd(),
                component_c.as_ptr(),
                expected_mode as libc::mode_t,
            )
        };
        if result != 0 {
            return Err(PlatformError::last("directory-create-exclusive", component));
        }
        let directory = self.open_directory(component)?;
        directory.set_mode(expected_mode)?;
        if directory.mode()? != expected_mode {
            return Err(PlatformError::invalid("directory-mode", component));
        }
        Ok(directory)
    }

    pub fn ensure_directory(
        &self,
        component: &str,
        expected_mode: u32,
    ) -> Result<Self, PlatformError> {
        validate_mode(expected_mode, "directory-mode", component)?;
        let component_c = component_cstring(component, "directory-component")?;
        // SAFETY: the parent descriptor is owned, the component is one NUL-terminated name,
        // and the mode value was restricted to permission bits.
        let result = unsafe {
            libc::mkdirat(
                self.file.as_raw_fd(),
                component_c.as_ptr(),
                expected_mode as libc::mode_t,
            )
        };
        let created = if result == 0 {
            true
        } else {
            let source = io::Error::last_os_error();
            if source.kind() == io::ErrorKind::AlreadyExists {
                false
            } else {
                return Err(PlatformError::new("directory-create", component, source));
            }
        };
        let directory = self.open_directory(component)?;
        if created {
            directory.set_mode(expected_mode)?;
        }
        if directory.mode()? != expected_mode {
            return Err(PlatformError::invalid("directory-mode", component));
        }
        Ok(directory)
    }

    pub fn open_file(&self, component: &str) -> Result<RegularFile, PlatformError> {
        self.open_regular_file(component, libc::O_RDONLY, "file-open")
    }

    pub fn open_file_read_write(&self, component: &str) -> Result<RegularFile, PlatformError> {
        self.open_regular_file(component, libc::O_RDWR, "file-open-read-write")
    }

    fn open_regular_file(
        &self,
        component: &str,
        access: libc::c_int,
        operation: &'static str,
    ) -> Result<RegularFile, PlatformError> {
        let component_c = component_cstring(component, "file-component")?;
        let flags = access | libc::O_CLOEXEC | libc::O_NOFOLLOW_ANY | libc::O_NONBLOCK;
        let file = openat_file(self.file.as_raw_fd(), &component_c, flags, 0, operation)?;
        validate_regular(&file, "file-boundary", &component_c)?;
        Ok(RegularFile { file })
    }

    pub fn create_file_exclusive(
        &self,
        component: &str,
        expected_mode: u32,
    ) -> Result<RegularFile, PlatformError> {
        validate_mode(expected_mode, "file-mode", component)?;
        let component_c = component_cstring(component, "file-component")?;
        let flags =
            libc::O_RDWR | libc::O_CREAT | libc::O_EXCL | libc::O_CLOEXEC | libc::O_NOFOLLOW_ANY;
        let file = openat_file(
            self.file.as_raw_fd(),
            &component_c,
            flags,
            expected_mode,
            "file-create",
        )?;
        let result = RegularFile { file };
        result.set_mode(expected_mode)?;
        result.validate(expected_mode)?;
        Ok(result)
    }

    pub fn open_entry(&self, component: &str) -> Result<Entry, PlatformError> {
        let component_c = component_cstring(component, "entry-component")?;
        let flags = libc::O_RDONLY | libc::O_CLOEXEC | libc::O_NOFOLLOW_ANY | libc::O_NONBLOCK;
        let file = openat_file(self.file.as_raw_fd(), &component_c, flags, 0, "entry-open")?;
        let metadata = metadata(&file, "entry-metadata", &component_c)?;
        let name = component_text(&component_c).to_owned();
        if metadata.is_dir() {
            Ok(Entry::Directory {
                name,
                directory: Directory { file },
            })
        } else if metadata.is_file() {
            Ok(Entry::File {
                name,
                file: RegularFile { file },
            })
        } else {
            Err(PlatformError::invalid("entry-boundary", name))
        }
    }

    pub fn entry_names(&self) -> Result<Vec<String>, PlatformError> {
        let dot = c".";
        let flags = libc::O_RDONLY | libc::O_DIRECTORY | libc::O_CLOEXEC | libc::O_NOFOLLOW_ANY;
        let duplicate = openat_file(
            self.file.as_raw_fd(),
            dot,
            flags,
            0,
            "directory-stream-duplicate",
        )?;
        let raw = duplicate.into_raw_fd();
        // SAFETY: `raw` is a fresh owned directory descriptor. On success `DIR` owns it.
        let pointer = unsafe { libc::fdopendir(raw) };
        let Some(pointer) = NonNull::new(pointer) else {
            // SAFETY: fdopendir failed and therefore did not consume `raw`; reclaim it exactly once.
            drop(unsafe { File::from_raw_fd(raw) });
            return Err(PlatformError::last("directory-stream-open", "$"));
        };
        let stream = DirectoryStream(pointer);
        // SAFETY: `stream` uniquely owns this live DIR pointer; rewind establishes a
        // deterministic start on the independently opened directory description.
        unsafe { libc::rewinddir(stream.0.as_ptr()) };
        let mut names = Vec::new();
        loop {
            // SAFETY: `__error` returns the calling thread's errno address on Darwin.
            unsafe { *libc::__error() = 0 };
            // SAFETY: `stream` owns a live DIR pointer and no concurrent call uses this stream.
            let entry = unsafe { libc::readdir(stream.0.as_ptr()) };
            if entry.is_null() {
                let source = io::Error::last_os_error();
                if source.raw_os_error() == Some(0) {
                    break;
                }
                return Err(PlatformError::new("directory-read", "$", source));
            }
            // SAFETY: readdir returned a live dirent whose d_name is NUL-terminated until
            // the next call on this same stream; bytes are copied before that call.
            let bytes = unsafe { CStr::from_ptr((*entry).d_name.as_ptr()) }.to_bytes();
            if bytes == b"." || bytes == b".." {
                continue;
            }
            let name = std::str::from_utf8(bytes)
                .map_err(|_| PlatformError::invalid("nonportable-entry", "$"))?;
            validate_component(name)
                .map_err(|_| PlatformError::invalid("nonportable-entry", name))?;
            names.push(name.to_owned());
        }
        names.sort_unstable();
        Ok(names)
    }

    pub fn rename_directory_exclusive(
        &self,
        source_component: &str,
        destination_parent: &Directory,
        destination_component: &str,
    ) -> Result<(), PlatformError> {
        let source = component_cstring(source_component, "rename-source")?;
        let destination = component_cstring(destination_component, "rename-destination")?;
        // SAFETY: both descriptors are owned directory capabilities; both names are single,
        // NUL-terminated components; flags are SDK-defined and contain no uninitialized bits.
        let result = unsafe {
            libc::renameatx_np(
                self.file.as_raw_fd(),
                source.as_ptr(),
                destination_parent.file.as_raw_fd(),
                destination.as_ptr(),
                EXCLUSIVE_RENAME_FLAGS,
            )
        };
        if result == 0 {
            Ok(())
        } else {
            Err(PlatformError::last(
                "rename-exclusive",
                destination_component,
            ))
        }
    }

    pub fn remove_file(&self, component: &str) -> Result<(), PlatformError> {
        self.unlink(component, 0, "file-remove")
    }

    pub fn remove_directory(&self, component: &str) -> Result<(), PlatformError> {
        self.unlink(component, libc::AT_REMOVEDIR, "directory-remove")
    }

    pub fn remove_tree_contents(&self) -> Result<(), PlatformError> {
        for name in self.entry_names()? {
            match self.open_entry(&name)? {
                Entry::Directory { directory, .. } => {
                    directory.remove_tree_contents()?;
                    directory.full_sync()?;
                    drop(directory);
                    self.remove_directory(&name)?;
                }
                Entry::File { file, .. } => {
                    drop(file);
                    self.remove_file(&name)?;
                }
            }
        }
        self.full_sync()
    }

    pub fn full_sync(&self) -> Result<(), PlatformError> {
        full_sync_fd(self.file.as_raw_fd(), "directory-full-sync", "$")
    }

    pub fn mode(&self) -> Result<u32, PlatformError> {
        self.file
            .metadata()
            .map(|metadata| mode(&metadata))
            .map_err(|source| PlatformError::new("directory-metadata", "$", source))
    }

    pub fn device(&self) -> Result<u64, PlatformError> {
        self.file
            .metadata()
            .map(|metadata| metadata.dev())
            .map_err(|source| PlatformError::new("directory-metadata", "$", source))
    }

    fn set_mode(&self, expected_mode: u32) -> Result<(), PlatformError> {
        self.file
            .set_permissions(Permissions::from_mode(expected_mode))
            .map_err(|source| PlatformError::new("directory-set-mode", "$", source))
    }

    fn unlink(
        &self,
        component: &str,
        flags: libc::c_int,
        operation: &'static str,
    ) -> Result<(), PlatformError> {
        let component_c = component_cstring(component, operation)?;
        // SAFETY: the descriptor is an owned directory and the path is one NUL-terminated name.
        let result = unsafe { libc::unlinkat(self.file.as_raw_fd(), component_c.as_ptr(), flags) };
        if result == 0 {
            Ok(())
        } else {
            Err(PlatformError::last(operation, component))
        }
    }
}

impl RegularFile {
    pub fn write_all(&mut self, bytes: &[u8]) -> Result<(), PlatformError> {
        self.file
            .write_all(bytes)
            .map_err(|source| PlatformError::new("file-write", "$", source))
    }

    pub fn read_all(&mut self) -> Result<Vec<u8>, PlatformError> {
        self.file
            .rewind()
            .map_err(|source| PlatformError::new("file-rewind", "$", source))?;
        let mut bytes = Vec::new();
        self.file
            .read_to_end(&mut bytes)
            .map_err(|source| PlatformError::new("file-read", "$", source))?;
        Ok(bytes)
    }

    pub fn full_sync(&self) -> Result<(), PlatformError> {
        full_sync_fd(self.file.as_raw_fd(), "file-full-sync", "$")
    }

    pub fn set_mode(&self, expected_mode: u32) -> Result<(), PlatformError> {
        validate_mode(expected_mode, "file-mode", "$")?;
        self.file
            .set_permissions(Permissions::from_mode(expected_mode))
            .map_err(|source| PlatformError::new("file-set-mode", "$", source))
    }

    pub fn validate(&self, expected_mode: u32) -> Result<(), PlatformError> {
        let metadata = self
            .file
            .metadata()
            .map_err(|source| PlatformError::new("file-metadata", "$", source))?;
        if !metadata.is_file() || metadata.nlink() != 1 || mode(&metadata) != expected_mode {
            return Err(PlatformError::invalid("file-boundary", "$"));
        }
        Ok(())
    }

    pub fn byte_length(&self) -> Result<u64, PlatformError> {
        self.file
            .metadata()
            .map(|metadata| metadata.len())
            .map_err(|source| PlatformError::new("file-metadata", "$", source))
    }

    pub fn mode(&self) -> Result<u32, PlatformError> {
        self.file
            .metadata()
            .map(|metadata| mode(&metadata))
            .map_err(|source| PlatformError::new("file-metadata", "$", source))
    }

    pub fn into_file(self) -> File {
        self.file
    }
}

struct DirectoryStream(NonNull<libc::DIR>);

impl Drop for DirectoryStream {
    fn drop(&mut self) {
        // SAFETY: this wrapper uniquely owns the live DIR pointer returned by fdopendir.
        unsafe { libc::closedir(self.0.as_ptr()) };
    }
}

fn openat_file(
    parent: RawFd,
    component: &CStr,
    flags: libc::c_int,
    mode: u32,
    operation: &'static str,
) -> Result<File, PlatformError> {
    // SAFETY: `parent` is borrowed from a live owned descriptor; component is NUL-terminated;
    // callers pass the fourth argument whenever O_CREAT may consume it.
    let raw = unsafe { libc::openat(parent, component.as_ptr(), flags, mode as libc::c_uint) };
    owned_file(raw, operation, component_text(component))
}

fn owned_file(
    raw: libc::c_int,
    operation: &'static str,
    component: &str,
) -> Result<File, PlatformError> {
    if raw < 0 {
        Err(PlatformError::last(operation, component))
    } else {
        // SAFETY: a nonnegative successful open/openat return is a new descriptor owned here.
        Ok(unsafe { File::from_raw_fd(raw) })
    }
}

fn metadata(
    file: &File,
    operation: &'static str,
    component: &CStr,
) -> Result<Metadata, PlatformError> {
    file.metadata()
        .map_err(|source| PlatformError::new(operation, component_text(component), source))
}

fn validate_regular(
    file: &File,
    operation: &'static str,
    component: &CStr,
) -> Result<(), PlatformError> {
    let metadata = metadata(file, operation, component)?;
    if !metadata.is_file() || metadata.nlink() != 1 {
        return Err(PlatformError::invalid(operation, component_text(component)));
    }
    Ok(())
}

fn full_sync_fd(fd: RawFd, operation: &'static str, component: &str) -> Result<(), PlatformError> {
    // SAFETY: `fd` is borrowed from a live owned File; F_FULLFSYNC consumes no vararg.
    let result = unsafe { libc::fcntl(fd, libc::F_FULLFSYNC) };
    if result == 0 {
        Ok(())
    } else {
        Err(PlatformError::last(operation, component))
    }
}

fn component_cstring(component: &str, operation: &'static str) -> Result<CString, PlatformError> {
    validate_component(component).map_err(|_| PlatformError::invalid(operation, component))?;
    CString::new(component).map_err(|_| PlatformError::invalid(operation, component))
}

fn validate_component(component: &str) -> Result<(), ()> {
    if component.is_empty()
        || component == "."
        || component == ".."
        || component.len() > 255
        || !component.is_ascii()
        || component.contains('/')
        || component.contains('\0')
        || !component
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
    {
        return Err(());
    }
    Ok(())
}

fn validate_mode(mode: u32, operation: &'static str, component: &str) -> Result<(), PlatformError> {
    if mode == 0 || mode & !0o777 != 0 {
        Err(PlatformError::invalid(operation, component))
    } else {
        Ok(())
    }
}

fn component_text(component: &CStr) -> &str {
    component.to_str().unwrap_or("<non-utf8>")
}

fn mode(metadata: &Metadata) -> u32 {
    metadata.mode() & 0o7777
}

fn effective_uid() -> u32 {
    // SAFETY: geteuid has no arguments, memory effects, or failure mode.
    unsafe { libc::geteuid() }
}

#[cfg(test)]
mod tests {
    use super::Directory;
    use std::fs::{self, DirBuilder};
    use std::os::unix::fs::{DirBuilderExt, PermissionsExt, symlink};
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_TEMP: AtomicU64 = AtomicU64::new(1);

    struct TestRoot(PathBuf);

    impl TestRoot {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "radishaxiom-darwin-store-{}-{}",
                std::process::id(),
                NEXT_TEMP.fetch_add(1, Ordering::Relaxed)
            ));
            DirBuilder::new().mode(0o700).create(&path).unwrap();
            Self(fs::canonicalize(path).unwrap())
        }

        fn directory(&self) -> Directory {
            Directory::open_private_root(&self.0).unwrap()
        }
    }

    impl Drop for TestRoot {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }

    #[test]
    fn descriptor_tree_create_inventory_read_and_remove() {
        let temp = TestRoot::new();
        let root = temp.directory();
        let staging = root.ensure_directory("staging", 0o700).unwrap();
        let slot = staging.ensure_directory("slot", 0o755).unwrap();
        let payload = slot.ensure_directory("payload", 0o755).unwrap();
        let mut file = payload.create_file_exclusive("checker", 0o755).unwrap();
        file.write_all(b"checker-bytes").unwrap();
        file.full_sync().unwrap();
        assert_eq!(file.byte_length().unwrap(), 13);
        assert_eq!(payload.entry_names().unwrap(), ["checker"]);
        assert_eq!(
            payload.open_file("checker").unwrap().read_all().unwrap(),
            b"checker-bytes"
        );
        payload.full_sync().unwrap();
        slot.full_sync().unwrap();
        slot.remove_tree_contents().unwrap();
        assert!(slot.entry_names().unwrap().is_empty());
    }

    #[test]
    fn exclusive_rename_never_overwrites_and_preserves_source() {
        let temp = TestRoot::new();
        let root = temp.directory();
        let staging = root.ensure_directory("staging", 0o700).unwrap();
        let slots = root.ensure_directory("slots", 0o755).unwrap();
        let first = staging.ensure_directory("first", 0o755).unwrap();
        first.full_sync().unwrap();
        staging
            .rename_directory_exclusive("first", &slots, "slot")
            .unwrap();
        slots.full_sync().unwrap();
        assert_eq!(slots.open_directory("slot").unwrap().mode().unwrap(), 0o755);

        staging.ensure_directory("second", 0o755).unwrap();
        let error = staging
            .rename_directory_exclusive("second", &slots, "slot")
            .unwrap_err();
        assert_eq!(error.raw_os_error(), Some(libc::EEXIST));
        assert!(staging.open_directory("second").is_ok());
    }

    #[test]
    fn intermediate_symlink_is_rejected() {
        let temp = TestRoot::new();
        let external = std::env::temp_dir().join(format!(
            "radishaxiom-darwin-store-external-{}-{}",
            std::process::id(),
            NEXT_TEMP.fetch_add(1, Ordering::Relaxed)
        ));
        DirBuilder::new().mode(0o700).create(&external).unwrap();
        symlink(&external, temp.0.join("escape")).unwrap();

        let root = temp.directory();
        for invalid in ["", ".", "..", "../escape", "two/components", "unsafe value"] {
            assert_eq!(
                root.open_directory(invalid).unwrap_err().io_kind(),
                std::io::ErrorKind::InvalidInput
            );
        }
        let error = root.open_directory("escape").unwrap_err();
        assert_eq!(error.raw_os_error(), Some(libc::ELOOP));

        fs::remove_file(temp.0.join("escape")).unwrap();
        fs::set_permissions(&external, fs::Permissions::from_mode(0o700)).unwrap();
        fs::remove_dir(external).unwrap();
    }
}
