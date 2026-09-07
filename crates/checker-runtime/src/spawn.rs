use std::ffi::OsString;
use std::path::{Component, Path, PathBuf};

use crate::canonical::{
    DocumentError, Value, as_array, as_object, member, parse, parse_decimal, string_member,
    validate_digest,
};
use crate::policy::{CHECKER_EXECUTION_PROFILE_ID, LauncherPolicy};
use crate::registration::{RegistrationRecord, RegistrationStatus};
use crate::result::{
    ConsumedIndependentResult, IndependentDocumentBinding, MAX_INDEPENDENT_RESULT_BYTES,
    MAX_INVOCATION_FAILURE_BYTES, consume_independent_result,
};
use crate::selection::NativeTarget;
use crate::sha256::digest_hex;

const PROFILE_SET_FORMAT: &str = "radishaxiom-execution-profile-set";
const PROFILE_SET_VERSION: &str = "0.1";
const CHECKER_OUTER_LIMIT_SET_ID: &str = "keyed-finite-table-independent-check-process-v0.1";
const CHECKER_EXECUTABLE_NAME: &str = "radishaxiom-independent-checker-go";
const CHECKER_TOOLCHAIN: &str = "go1.26.7";

pub const MAX_EXECUTION_PROFILE_MANIFEST_BYTES: usize = 65_536;
pub const CHECKER_STDOUT_LIMIT_BYTES: u64 = 1_048_576;
pub const CHECKER_STDERR_LIMIT_BYTES: u64 = 65_536;
pub const CHECKER_WALL_CLOCK_LIMIT_MILLIS: u64 = 6_000;
pub const CHECKER_WORKING_MEMORY_LIMIT_BYTES: u64 = 134_217_728;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SpawnPurpose {
    Qualification,
    ProductInvocation,
}

impl SpawnPurpose {
    fn required_status(self) -> RegistrationStatus {
        match self {
            Self::Qualification => RegistrationStatus::RegisteredInactive,
            Self::ProductInvocation => RegistrationStatus::Active,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ExecutionProfileContract {
    manifest_raw_sha256: Box<str>,
    profile_id: Box<str>,
    outer_limit_set_id: Box<str>,
    stdout_bytes: u64,
    stderr_bytes: u64,
    wall_clock_millis: u64,
    working_memory_bytes: u64,
}

impl ExecutionProfileContract {
    pub fn parse(
        canonical_manifest: &[u8],
        policy: &LauncherPolicy,
    ) -> Result<Self, DocumentError> {
        if canonical_manifest.is_empty()
            || canonical_manifest.len() > MAX_EXECUTION_PROFILE_MANIFEST_BYTES
        {
            return Err(DocumentError::new("execution-profile-length", "$"));
        }
        let raw_sha256 = format!("sha256:{}", digest_hex(canonical_manifest));
        if raw_sha256 != policy.execution_profile().raw_sha256.as_ref() {
            return Err(DocumentError::new("execution-profile-identity", "$"));
        }

        let value = parse(canonical_manifest, true)?;
        let root = as_object(&value, "$")?;
        require_fields(
            root,
            &[
                "certificate_capabilities",
                "counts",
                "coverage",
                "format",
                "format_version",
                "level",
                "limit_sets",
                "profiles",
                "references",
                "source_bindings",
            ],
            "$",
        )?;
        expect_string(
            root,
            "format",
            PROFILE_SET_FORMAT,
            "$",
            "execution-profile-format",
        )?;
        expect_string(
            root,
            "format_version",
            PROFILE_SET_VERSION,
            "$",
            "execution-profile-version",
        )?;
        expect_string(root, "level", "specified", "$", "execution-profile-level")?;

        let profile_id = policy.execution_profile().id.as_ref();
        if profile_id != CHECKER_EXECUTION_PROFILE_ID {
            return Err(DocumentError::new(
                "execution-profile-id",
                "$.profiles[].id",
            ));
        }
        let profile = unique_object_by_id(
            as_array(member(root, "profiles", "$")?, "$.profiles")?,
            profile_id,
            "$.profiles",
        )?;
        validate_checker_profile(profile)?;

        let limit_set = unique_object_by_id(
            as_array(member(root, "limit_sets", "$")?, "$.limit_sets")?,
            CHECKER_OUTER_LIMIT_SET_ID,
            "$.limit_sets",
        )?;
        let limits = validate_outer_limits(limit_set)?;
        Ok(Self {
            manifest_raw_sha256: raw_sha256.into(),
            profile_id: profile_id.into(),
            outer_limit_set_id: CHECKER_OUTER_LIMIT_SET_ID.into(),
            stdout_bytes: limits.stdout_bytes,
            stderr_bytes: limits.stderr_bytes,
            wall_clock_millis: limits.wall_clock_millis,
            working_memory_bytes: limits.working_memory_bytes,
        })
    }

    pub fn manifest_raw_sha256(&self) -> &str {
        &self.manifest_raw_sha256
    }

    pub fn profile_id(&self) -> &str {
        &self.profile_id
    }

    pub fn outer_limit_set_id(&self) -> &str {
        &self.outer_limit_set_id
    }

    pub fn stdout_bytes(&self) -> u64 {
        self.stdout_bytes
    }

    pub fn stderr_bytes(&self) -> u64 {
        self.stderr_bytes
    }

    pub fn wall_clock_millis(&self) -> u64 {
        self.wall_clock_millis
    }

    pub fn working_memory_bytes(&self) -> u64 {
        self.working_memory_bytes
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FilesystemObjectIdentity {
    device: u64,
    inode: u64,
}

impl FilesystemObjectIdentity {
    pub fn try_new(device: u64, inode: u64) -> Result<Self, DocumentError> {
        if inode == 0 {
            return Err(DocumentError::new("filesystem-object-identity", "$"));
        }
        Ok(Self { device, inode })
    }

    pub fn device(self) -> u64 {
        self.device
    }

    pub fn inode(self) -> u64 {
        self.inode
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ExecutableIdentityObservation {
    canonical_path: PathBuf,
    object_identity: FilesystemObjectIdentity,
    target: NativeTarget,
    byte_length: u64,
    raw_sha256: Box<str>,
}

impl ExecutableIdentityObservation {
    pub fn try_new(
        canonical_path: impl Into<PathBuf>,
        object_identity: FilesystemObjectIdentity,
        target: NativeTarget,
        byte_length: u64,
        raw_sha256: impl Into<Box<str>>,
    ) -> Result<Self, DocumentError> {
        let canonical_path = canonical_path.into();
        validate_observed_path(&canonical_path, "executable-observation-path")?;
        let raw_sha256 = raw_sha256.into();
        validate_digest(&raw_sha256, "$.executable.raw_sha256")?;
        if byte_length == 0 {
            return Err(DocumentError::new(
                "executable-observation-length",
                "$.executable.byte_length",
            ));
        }
        Ok(Self {
            canonical_path,
            object_identity,
            target,
            byte_length,
            raw_sha256,
        })
    }

    pub fn canonical_path(&self) -> &Path {
        &self.canonical_path
    }

    pub fn object_identity(&self) -> FilesystemObjectIdentity {
        self.object_identity
    }

    pub fn target(&self) -> &NativeTarget {
        &self.target
    }

    pub fn byte_length(&self) -> u64 {
        self.byte_length
    }

    pub fn raw_sha256(&self) -> &str {
        &self.raw_sha256
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReadonlyBundleObservation {
    canonical_path: PathBuf,
    object_identity: FilesystemObjectIdentity,
}

impl ReadonlyBundleObservation {
    pub fn try_new(
        canonical_path: impl Into<PathBuf>,
        object_identity: FilesystemObjectIdentity,
    ) -> Result<Self, DocumentError> {
        let canonical_path = canonical_path.into();
        validate_observed_path(&canonical_path, "bundle-observation-path")?;
        Ok(Self {
            canonical_path,
            object_identity,
        })
    }

    pub fn canonical_path(&self) -> &Path {
        &self.canonical_path
    }

    pub fn object_identity(&self) -> FilesystemObjectIdentity {
        self.object_identity
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IsolatedWorkingDirectoryObservation {
    canonical_path: PathBuf,
    object_identity: FilesystemObjectIdentity,
}

impl IsolatedWorkingDirectoryObservation {
    pub fn try_new_empty(
        canonical_path: impl Into<PathBuf>,
        object_identity: FilesystemObjectIdentity,
    ) -> Result<Self, DocumentError> {
        let canonical_path = canonical_path.into();
        validate_observed_path(&canonical_path, "working-directory-observation-path")?;
        Ok(Self {
            canonical_path,
            object_identity,
        })
    }

    pub fn canonical_path(&self) -> &Path {
        &self.canonical_path
    }

    pub fn object_identity(&self) -> FilesystemObjectIdentity {
        self.object_identity
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NativeIsolationStatus {
    RequiredNotProven,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CheckerSpawnPlan {
    purpose: SpawnPurpose,
    executable: ExecutableIdentityObservation,
    bundle: ReadonlyBundleObservation,
    working_directory: IsolatedWorkingDirectoryObservation,
    arguments: Box<[OsString]>,
    environment: Box<[(OsString, OsString)]>,
    profile: ExecutionProfileContract,
    registration_id: Box<str>,
    registration_digest: Box<str>,
}

impl CheckerSpawnPlan {
    #[allow(clippy::too_many_arguments)]
    pub fn try_new(
        policy: &LauncherPolicy,
        canonical_execution_profile_manifest: &[u8],
        record: &RegistrationRecord,
        purpose: SpawnPurpose,
        executable: ExecutableIdentityObservation,
        bundle: ReadonlyBundleObservation,
        working_directory: IsolatedWorkingDirectoryObservation,
    ) -> Result<Self, DocumentError> {
        if record.status() != purpose.required_status() {
            return Err(DocumentError::new(
                "spawn-registration-status",
                "$.registration.status",
            ));
        }
        if !policy.supports(record.target()) {
            return Err(DocumentError::new("unsupported-target", "$.target"));
        }
        if executable.target() != record.target()
            || executable.byte_length() != record.artifact().byte_length()
            || executable.raw_sha256() != record.artifact().raw_sha256()
        {
            return Err(DocumentError::new(
                "spawn-executable-identity",
                "$.executable",
            ));
        }
        if executable.canonical_path() == bundle.canonical_path()
            || executable.canonical_path() == working_directory.canonical_path()
            || bundle.canonical_path() == working_directory.canonical_path()
        {
            return Err(DocumentError::new("spawn-path-alias", "$"));
        }

        let profile =
            ExecutionProfileContract::parse(canonical_execution_profile_manifest, policy)?;
        let mut bundle_argument = OsString::from("--bundle-root=");
        bundle_argument.push(bundle.canonical_path());
        let arguments = vec![OsString::from("check"), bundle_argument].into_boxed_slice();
        Ok(Self {
            purpose,
            executable,
            bundle,
            working_directory,
            arguments,
            environment: Vec::new().into_boxed_slice(),
            profile,
            registration_id: record.id().into(),
            registration_digest: record.document_digest().into(),
        })
    }

    pub fn purpose(&self) -> SpawnPurpose {
        self.purpose
    }

    pub fn executable(&self) -> &ExecutableIdentityObservation {
        &self.executable
    }

    pub fn bundle(&self) -> &ReadonlyBundleObservation {
        &self.bundle
    }

    pub fn working_directory(&self) -> &IsolatedWorkingDirectoryObservation {
        &self.working_directory
    }

    pub fn arguments(&self) -> &[OsString] {
        &self.arguments
    }

    pub fn environment(&self) -> &[(OsString, OsString)] {
        &self.environment
    }

    pub fn stdin_is_empty_then_eof(&self) -> bool {
        true
    }

    pub fn network_is_forbidden(&self) -> bool {
        true
    }

    pub fn profile(&self) -> &ExecutionProfileContract {
        &self.profile
    }

    pub fn native_isolation_status(&self) -> NativeIsolationStatus {
        NativeIsolationStatus::RequiredNotProven
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum StreamCapture {
    Complete(Box<[u8]>),
    LimitExceeded,
}

impl StreamCapture {
    pub fn complete(bytes: impl Into<Box<[u8]>>) -> Self {
        Self::Complete(bytes.into())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ProcessTerminationObservation {
    SpawnFailed,
    TimedOut,
    WorkingMemoryLimitExceeded,
    Signaled {
        signal: u32,
    },
    Exited {
        exit_code: u32,
        stdout: StreamCapture,
        stderr: StreamCapture,
        wall_clock_millis: u64,
        peak_working_memory_bytes: u64,
    },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum PostflightExecutableObservation {
    Observed(ExecutableIdentityObservation),
    Unavailable,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProcessObservation {
    termination: ProcessTerminationObservation,
    postflight_executable: PostflightExecutableObservation,
}

impl ProcessObservation {
    pub fn new(
        termination: ProcessTerminationObservation,
        postflight_executable: PostflightExecutableObservation,
    ) -> Self {
        Self {
            termination,
            postflight_executable,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OuterFailureClassification {
    ProcessFailure,
    IdentityFailure,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OuterInvocationFailure {
    classification: OuterFailureClassification,
    code: &'static str,
}

impl OuterInvocationFailure {
    pub fn classification(&self) -> OuterFailureClassification {
        self.classification
    }

    pub fn code(&self) -> &'static str {
        self.code
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CheckerProcessOutcome {
    Result(ConsumedIndependentResult),
    Failure(OuterInvocationFailure),
}

pub fn consume_process_observation(
    plan: &CheckerSpawnPlan,
    current_record: &RegistrationRecord,
    request: &IndependentDocumentBinding,
    evidence: &IndependentDocumentBinding,
    observation: ProcessObservation,
) -> CheckerProcessOutcome {
    if current_record.id() != plan.registration_id.as_ref()
        || current_record.document_digest() != plan.registration_digest.as_ref()
        || current_record.status() != plan.purpose.required_status()
    {
        return identity_failure("registration-identity-drift");
    }
    match observation.postflight_executable {
        PostflightExecutableObservation::Observed(postflight) if postflight == plan.executable => {}
        PostflightExecutableObservation::Observed(_) => {
            return identity_failure("executable-identity-drift");
        }
        PostflightExecutableObservation::Unavailable => {
            return identity_failure("executable-postflight-unavailable");
        }
    }

    let ProcessTerminationObservation::Exited {
        exit_code,
        stdout,
        stderr,
        wall_clock_millis,
        peak_working_memory_bytes,
    } = observation.termination
    else {
        return match observation.termination {
            ProcessTerminationObservation::SpawnFailed => process_failure("spawn-failed"),
            ProcessTerminationObservation::TimedOut => process_failure("wall-clock-timeout"),
            ProcessTerminationObservation::WorkingMemoryLimitExceeded => {
                process_failure("working-memory-limit-exceeded")
            }
            ProcessTerminationObservation::Signaled { .. } => process_failure("process-signaled"),
            ProcessTerminationObservation::Exited { .. } => unreachable!(),
        };
    };

    if wall_clock_millis > plan.profile.wall_clock_millis() {
        return process_failure("wall-clock-limit-exceeded");
    }
    if peak_working_memory_bytes > plan.profile.working_memory_bytes() {
        return process_failure("working-memory-limit-exceeded");
    }
    let stdout = match complete_stream(stdout, plan.profile.stdout_bytes()) {
        Ok(bytes) => bytes,
        Err(()) => return process_failure("stdout-limit-exceeded"),
    };
    let stderr = match complete_stream(stderr, plan.profile.stderr_bytes()) {
        Ok(bytes) => bytes,
        Err(()) => return process_failure("stderr-limit-exceeded"),
    };
    if std::str::from_utf8(&stderr).is_err() {
        return process_failure("stderr-invalid-utf8");
    }
    if exit_code != 0 {
        return process_failure("nonzero-exit");
    }

    match consume_independent_result(stdout, current_record, request, evidence) {
        Ok(result) => CheckerProcessOutcome::Result(result),
        Err(error)
            if matches!(
                error.code(),
                "result-checker-identity"
                    | "result-request-identity"
                    | "result-evidence-identity"
                    | "result-tcb-identity"
            ) =>
        {
            identity_failure("result-identity-mismatch")
        }
        Err(_) => process_failure("stdout-not-canonical-result"),
    }
}

fn validate_checker_profile(profile: &[(String, Value)]) -> Result<(), DocumentError> {
    require_fields(
        profile,
        &[
            "capability_boundary",
            "environment",
            "id",
            "invocation",
            "logical_memory_accounting",
            "outer_limit_set",
            "registry_profile",
            "request_limit_set",
            "resource_counters",
            "result_boundary",
            "role",
        ],
        "$.profiles[]",
    )?;
    expect_string(
        profile,
        "id",
        CHECKER_EXECUTION_PROFILE_ID,
        "$.profiles[]",
        "execution-profile-id",
    )?;
    expect_string(
        profile,
        "role",
        "independent-checker",
        "$.profiles[]",
        "execution-profile-role",
    )?;
    expect_string(
        profile,
        "outer_limit_set",
        CHECKER_OUTER_LIMIT_SET_ID,
        "$.profiles[]",
        "execution-profile-limit-set",
    )?;
    expect_string(
        profile,
        "registry_profile",
        CHECKER_EXECUTION_PROFILE_ID,
        "$.profiles[]",
        "execution-profile-registry",
    )?;

    let capability = object_member(profile, "capability_boundary", "$.profiles[]")?;
    require_fields(
        capability,
        &[
            "environment",
            "fallback",
            "filesystem",
            "network",
            "production_tools",
            "working_directory",
        ],
        "$.profiles[].capability_boundary",
    )?;
    for (field, expected) in [
        ("environment", "empty"),
        ("fallback", "forbidden"),
        ("filesystem", "resolved-readonly-bundle-only"),
        ("network", "forbidden"),
        ("production_tools", "forbidden"),
        ("working_directory", "isolated-empty"),
    ] {
        expect_string(
            capability,
            field,
            expected,
            "$.profiles[].capability_boundary",
            "execution-profile-capability",
        )?;
    }

    let environment = object_member(profile, "environment", "$.profiles[]")?;
    require_fields(environment, &["inherit", "set"], "$.profiles[].environment")?;
    expect_string(
        environment,
        "inherit",
        "none",
        "$.profiles[].environment",
        "execution-profile-environment",
    )?;
    if !as_array(
        member(environment, "set", "$.profiles[].environment")?,
        "$.profiles[].environment.set",
    )?
    .is_empty()
    {
        return Err(DocumentError::new(
            "execution-profile-environment",
            "$.profiles[].environment.set",
        ));
    }

    let invocation = object_member(profile, "invocation", "$.profiles[]")?;
    require_fields(
        invocation,
        &["argument_tokens", "executable", "stderr", "stdin", "stdout"],
        "$.profiles[].invocation",
    )?;
    for (field, expected) in [
        ("stderr", "bounded-utf8-diagnostic-not-result"),
        ("stdin", "empty"),
        ("stdout", "one-canonical-independent-result-or-no-result"),
    ] {
        expect_string(
            invocation,
            field,
            expected,
            "$.profiles[].invocation",
            "execution-profile-invocation",
        )?;
    }
    let executable = object_member(invocation, "executable", "$.profiles[].invocation")?;
    require_fields(
        executable,
        &["artifact", "name", "resolution", "toolchain"],
        "$.profiles[].invocation.executable",
    )?;
    for (field, expected) in [
        ("artifact", "required-not-materialized"),
        ("name", CHECKER_EXECUTABLE_NAME),
        ("resolution", "future-registered-checker-artifact-only"),
        ("toolchain", CHECKER_TOOLCHAIN),
    ] {
        expect_string(
            executable,
            field,
            expected,
            "$.profiles[].invocation.executable",
            "execution-profile-executable",
        )?;
    }

    let arguments = as_array(
        member(invocation, "argument_tokens", "$.profiles[].invocation")?,
        "$.profiles[].invocation.argument_tokens",
    )?;
    if arguments.len() != 2 {
        return Err(DocumentError::new(
            "execution-profile-arguments",
            "$.profiles[].invocation.argument_tokens",
        ));
    }
    let literal = as_object(&arguments[0], "$.profiles[].invocation.argument_tokens[0]")?;
    require_fields(
        literal,
        &["kind", "value"],
        "$.profiles[].invocation.argument_tokens[0]",
    )?;
    expect_string(
        literal,
        "kind",
        "literal",
        "$.profiles[].invocation.argument_tokens[0]",
        "execution-profile-arguments",
    )?;
    expect_string(
        literal,
        "value",
        "check",
        "$.profiles[].invocation.argument_tokens[0]",
        "execution-profile-arguments",
    )?;
    let bundle = as_object(&arguments[1], "$.profiles[].invocation.argument_tokens[1]")?;
    require_fields(
        bundle,
        &["artifact_role", "kind", "prefix", "resolution"],
        "$.profiles[].invocation.argument_tokens[1]",
    )?;
    for (field, expected) in [
        ("artifact_role", "bundle-root"),
        ("kind", "artifact-directory-option"),
        ("prefix", "--bundle-root="),
        ("resolution", "caller-mounted-readonly-canonical-realpath"),
    ] {
        expect_string(
            bundle,
            field,
            expected,
            "$.profiles[].invocation.argument_tokens[1]",
            "execution-profile-arguments",
        )?;
    }
    Ok(())
}

struct OuterLimits {
    stdout_bytes: u64,
    stderr_bytes: u64,
    wall_clock_millis: u64,
    working_memory_bytes: u64,
}

fn validate_outer_limits(limit_set: &[(String, Value)]) -> Result<OuterLimits, DocumentError> {
    require_fields(limit_set, &["id", "limits", "scope"], "$.limit_sets[]")?;
    expect_string(
        limit_set,
        "scope",
        "process-outer",
        "$.limit_sets[]",
        "execution-profile-limit-scope",
    )?;
    let limits = as_array(
        member(limit_set, "limits", "$.limit_sets[]")?,
        "$.limit_sets[].limits",
    )?;
    let expected = [
        ("stderr-bytes", "byte", "65536", "launcher-stream-cap"),
        ("stdout-bytes", "byte", "1048576", "launcher-stream-cap"),
        (
            "wall-clock",
            "millisecond",
            "6000",
            "launcher-hard-deadline",
        ),
        (
            "working-memory",
            "byte",
            "134217728",
            "launcher-os-hard-limit",
        ),
    ];
    if limits.len() != expected.len() {
        return Err(DocumentError::new(
            "execution-profile-limit-set",
            "$.limit_sets[].limits",
        ));
    }
    let mut values = [0_u64; 4];
    for (index, (value, (name, unit, expected_value, enforcement))) in
        limits.iter().zip(expected).enumerate()
    {
        let path = format!("$.limit_sets[].limits[{index}]");
        let row = as_object(value, &path)?;
        require_fields(row, &["enforcement", "name", "unit", "value"], &path)?;
        for (field, expected) in [
            ("enforcement", enforcement),
            ("name", name),
            ("unit", unit),
            ("value", expected_value),
        ] {
            expect_string(row, field, expected, &path, "execution-profile-limit-set")?;
        }
        values[index] = parse_decimal(
            string_member(row, "value", &path)?,
            &format!("{path}.value"),
        )?;
    }
    let result = OuterLimits {
        stderr_bytes: values[0],
        stdout_bytes: values[1],
        wall_clock_millis: values[2],
        working_memory_bytes: values[3],
    };
    if result.stdout_bytes != CHECKER_STDOUT_LIMIT_BYTES
        || result.stderr_bytes != CHECKER_STDERR_LIMIT_BYTES
        || result.wall_clock_millis != CHECKER_WALL_CLOCK_LIMIT_MILLIS
        || result.working_memory_bytes != CHECKER_WORKING_MEMORY_LIMIT_BYTES
        || result.stdout_bytes
            != u64::try_from(MAX_INDEPENDENT_RESULT_BYTES).expect("constant fits")
        || result.stderr_bytes
            != u64::try_from(MAX_INVOCATION_FAILURE_BYTES).expect("constant fits")
    {
        return Err(DocumentError::new(
            "execution-profile-limit-set",
            "$.limit_sets[].limits",
        ));
    }
    Ok(result)
}

fn unique_object_by_id<'a>(
    values: &'a [Value],
    id: &str,
    path: &str,
) -> Result<&'a [(String, Value)], DocumentError> {
    let mut found = None;
    for (index, value) in values.iter().enumerate() {
        let item_path = format!("{path}[{index}]");
        let object = as_object(value, &item_path)?;
        if string_member(object, "id", &item_path)? == id {
            if found.is_some() {
                return Err(DocumentError::new("duplicate-member", item_path));
            }
            found = Some(object);
        }
    }
    found.ok_or_else(|| DocumentError::new("missing-member", format!("{path}[id={id}]")))
}

fn object_member<'a>(
    object: &'a [(String, Value)],
    name: &str,
    path: &str,
) -> Result<&'a [(String, Value)], DocumentError> {
    as_object(member(object, name, path)?, &format!("{path}.{name}"))
}

fn require_fields(
    object: &[(String, Value)],
    expected: &[&str],
    path: &str,
) -> Result<(), DocumentError> {
    for (name, _) in object {
        if expected.binary_search(&name.as_str()).is_err() {
            return Err(DocumentError::new(
                "unknown-member",
                format!("{path}.{name}"),
            ));
        }
    }
    for name in expected {
        if object
            .binary_search_by(|(actual, _)| actual.as_str().cmp(name))
            .is_err()
        {
            return Err(DocumentError::new(
                "missing-member",
                format!("{path}.{name}"),
            ));
        }
    }
    Ok(())
}

fn expect_string(
    object: &[(String, Value)],
    name: &str,
    expected: &str,
    path: &str,
    code: &'static str,
) -> Result<(), DocumentError> {
    if string_member(object, name, path)? == expected {
        Ok(())
    } else {
        Err(DocumentError::new(code, format!("{path}.{name}")))
    }
}

fn validate_observed_path(path: &Path, code: &'static str) -> Result<(), DocumentError> {
    if !path.is_absolute() || path.as_os_str().is_empty() {
        return Err(DocumentError::new(code, "$"));
    }
    let mut normal_components = 0_usize;
    for component in path.components() {
        match component {
            Component::RootDir | Component::Prefix(_) => {}
            Component::Normal(value) if !value.is_empty() => normal_components += 1,
            _ => return Err(DocumentError::new(code, "$")),
        }
    }
    if normal_components == 0 {
        return Err(DocumentError::new(code, "$"));
    }
    Ok(())
}

fn complete_stream(capture: StreamCapture, limit: u64) -> Result<Box<[u8]>, ()> {
    match capture {
        StreamCapture::Complete(bytes) => {
            if u64::try_from(bytes.len()).map_err(|_| ())? > limit {
                Err(())
            } else {
                Ok(bytes)
            }
        }
        StreamCapture::LimitExceeded => Err(()),
    }
}

fn process_failure(code: &'static str) -> CheckerProcessOutcome {
    CheckerProcessOutcome::Failure(OuterInvocationFailure {
        classification: OuterFailureClassification::ProcessFailure,
        code,
    })
}

fn identity_failure(code: &'static str) -> CheckerProcessOutcome {
    CheckerProcessOutcome::Failure(OuterInvocationFailure {
        classification: OuterFailureClassification::IdentityFailure,
        code,
    })
}

#[cfg(test)]
mod tests {
    use std::ffi::OsString;
    use std::fs;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};

    use super::{
        CHECKER_STDERR_LIMIT_BYTES, CHECKER_STDOUT_LIMIT_BYTES, CHECKER_WALL_CLOCK_LIMIT_MILLIS,
        CHECKER_WORKING_MEMORY_LIMIT_BYTES, CheckerProcessOutcome, CheckerSpawnPlan,
        ExecutableIdentityObservation, ExecutionProfileContract, FilesystemObjectIdentity,
        IsolatedWorkingDirectoryObservation, NativeIsolationStatus, OuterFailureClassification,
        PostflightExecutableObservation, ProcessObservation, ProcessTerminationObservation,
        ReadonlyBundleObservation, SpawnPurpose, StreamCapture, consume_process_observation,
    };
    use crate::canonical::{Value, as_object, canonical_bytes, domain_digest, member, parse};
    use crate::result::IndependentDocumentBinding;
    use crate::{parse_launcher_policy, parse_registration_record};

    const POLICY: &[u8] =
        include_bytes!("../../../contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs");
    const PROFILE_MANIFEST: &[u8] =
        include_bytes!("../../../contracts/execution-profiles-v0.1/manifest.jcs");
    const RECORD: &[u8] = include_bytes!(concat!(
        "../../../contracts/checker-runtime-payloads-v0.1/records/",
        "checker-go0.1-dev-darwin-arm64-current-registered-inactive.json"
    ));
    const RESULT: &[u8] = include_bytes!(concat!(
        "../../../contracts/independent-check-v0.1/fixtures/",
        "strict-evidence-rejection/expected-result.jcs"
    ));

    static TEMPORARY_COUNTER: AtomicU64 = AtomicU64::new(0);

    struct TemporaryRoot(PathBuf);

    impl TemporaryRoot {
        fn create() -> Self {
            let counter = TEMPORARY_COUNTER.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "radishaxiom-spawn-{}-{counter}",
                std::process::id()
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
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

    fn set_string(value: &mut Value, path: &[&str], replacement: &str) {
        let mut current = value;
        for component in &path[..path.len() - 1] {
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
            .iter_mut()
            .find(|(name, _)| name == path[path.len() - 1])
            .unwrap()
            .1 = Value::String(replacement.into());
    }

    fn active_record() -> crate::RegistrationRecord {
        let mut value = parse(RECORD, false).unwrap();
        set_string(&mut value, &["registration", "status"], "active");
        let digest = domain_digest(
            "radishaxiom.checker-runtime-payload-registration.v0.1",
            &value,
            "record_digest",
        )
        .unwrap();
        set_string(&mut value, &["record_digest"], &digest);
        parse_registration_record(&canonical_bytes(&value)).unwrap()
    }

    fn executable(
        root: &TemporaryRoot,
        record: &crate::RegistrationRecord,
    ) -> ExecutableIdentityObservation {
        let slot = root.path().join("slot/payload/checker");
        fs::create_dir_all(slot.parent().unwrap()).unwrap();
        fs::write(&slot, b"synthetic-observation-only").unwrap();
        ExecutableIdentityObservation::try_new(
            fs::canonicalize(slot).unwrap(),
            FilesystemObjectIdentity::try_new(1, 10).unwrap(),
            record.target().clone(),
            record.artifact().byte_length(),
            record.artifact().raw_sha256(),
        )
        .unwrap()
    }

    fn plan_for(
        root: &TemporaryRoot,
        record: &crate::RegistrationRecord,
        purpose: SpawnPurpose,
    ) -> CheckerSpawnPlan {
        let bundle = root.path().join("readonly-bundle");
        let working = root.path().join("empty-working-directory");
        fs::create_dir(&bundle).unwrap();
        fs::create_dir(&working).unwrap();
        CheckerSpawnPlan::try_new(
            &parse_launcher_policy(POLICY).unwrap(),
            PROFILE_MANIFEST,
            record,
            purpose,
            executable(root, record),
            ReadonlyBundleObservation::try_new(
                fs::canonicalize(bundle).unwrap(),
                FilesystemObjectIdentity::try_new(1, 20).unwrap(),
            )
            .unwrap(),
            IsolatedWorkingDirectoryObservation::try_new_empty(
                fs::canonicalize(working).unwrap(),
                FilesystemObjectIdentity::try_new(1, 30).unwrap(),
            )
            .unwrap(),
        )
        .unwrap()
    }

    fn bound_result(
        record: &crate::RegistrationRecord,
    ) -> (
        Vec<u8>,
        IndependentDocumentBinding,
        IndependentDocumentBinding,
    ) {
        let mut value = parse(RESULT, true).unwrap();
        let checker = record.checker();
        for (field, replacement) in [
            ("artifact", record.artifact().raw_sha256()),
            ("name", checker.implementation()),
            ("source", checker.source()),
            ("toolchain", checker.toolchain()),
            ("version", checker.version()),
        ] {
            set_string(&mut value, &["checker", field], replacement);
        }
        let Value::Object(root) = &mut value else {
            unreachable!();
        };
        let Value::Array(tcb) = &mut root.iter_mut().find(|(name, _)| name == "tcb").unwrap().1
        else {
            unreachable!();
        };
        for item in tcb {
            let Value::Object(item) = item else {
                unreachable!();
            };
            item.iter_mut()
                .find(|(name, _)| name == "artifact")
                .unwrap()
                .1 = Value::String(record.artifact().raw_sha256().into());
            item.iter_mut()
                .find(|(name, _)| name == "version")
                .unwrap()
                .1 = Value::String(checker.version().into());
        }
        let bytes = canonical_bytes(&value);
        let root = as_object(&value, "$").unwrap();
        let binding = |name: &str| {
            let object = as_object(member(root, name, "$").unwrap(), name).unwrap();
            let content = crate::canonical::string_member(object, "content_digest", name).unwrap();
            let document =
                as_object(member(object, "document_digest", name).unwrap(), name).unwrap();
            match crate::canonical::string_member(document, "kind", name).unwrap() {
                "available" => IndependentDocumentBinding::try_available(
                    content,
                    crate::canonical::string_member(document, "value", name).unwrap(),
                )
                .unwrap(),
                "unavailable" => IndependentDocumentBinding::try_unavailable(content).unwrap(),
                _ => unreachable!(),
            }
        };
        (bytes, binding("request"), binding("evidence"))
    }

    fn exited(stdout: StreamCapture) -> ProcessTerminationObservation {
        ProcessTerminationObservation::Exited {
            exit_code: 0,
            stdout,
            stderr: StreamCapture::complete(Vec::<u8>::new()),
            wall_clock_millis: 5_999,
            peak_working_memory_bytes: 134_217_727,
        }
    }

    fn exited_with(
        exit_code: u32,
        stdout: StreamCapture,
        stderr: StreamCapture,
        wall_clock_millis: u64,
        peak_working_memory_bytes: u64,
    ) -> ProcessTerminationObservation {
        ProcessTerminationObservation::Exited {
            exit_code,
            stdout,
            stderr,
            wall_clock_millis,
            peak_working_memory_bytes,
        }
    }

    fn failure(outcome: CheckerProcessOutcome) -> (&'static str, OuterFailureClassification) {
        let CheckerProcessOutcome::Failure(failure) = outcome else {
            panic!("expected outer failure");
        };
        (failure.code(), failure.classification())
    }

    #[test]
    fn profile_and_plan_close_the_single_spawn_configuration() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let profile = ExecutionProfileContract::parse(PROFILE_MANIFEST, &policy).unwrap();
        assert_eq!(profile.stdout_bytes(), CHECKER_STDOUT_LIMIT_BYTES);
        assert_eq!(profile.stderr_bytes(), CHECKER_STDERR_LIMIT_BYTES);
        assert_eq!(profile.wall_clock_millis(), CHECKER_WALL_CLOCK_LIMIT_MILLIS);
        assert_eq!(
            profile.working_memory_bytes(),
            CHECKER_WORKING_MEMORY_LIMIT_BYTES
        );

        let root = TemporaryRoot::create();
        let record = parse_registration_record(RECORD).unwrap();
        let plan = plan_for(&root, &record, SpawnPurpose::Qualification);
        assert_eq!(plan.arguments().len(), 2);
        assert_eq!(plan.arguments()[0], OsString::from("check"));
        let mut expected = OsString::from("--bundle-root=");
        expected.push(plan.bundle().canonical_path());
        assert_eq!(plan.arguments()[1], expected);
        assert!(plan.environment().is_empty());
        assert!(plan.stdin_is_empty_then_eof());
        assert!(plan.network_is_forbidden());
        assert_eq!(
            plan.native_isolation_status(),
            NativeIsolationStatus::RequiredNotProven
        );
    }

    #[test]
    fn profile_identity_status_and_executable_drift_fail_closed() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        let mut changed = PROFILE_MANIFEST.to_vec();
        changed.push(b'\n');
        assert_eq!(
            ExecutionProfileContract::parse(&changed, &policy)
                .unwrap_err()
                .code(),
            "execution-profile-identity"
        );

        let root = TemporaryRoot::create();
        let inactive = parse_registration_record(RECORD).unwrap();
        let active = active_record();
        let mut wrong_executable = executable(&root, &inactive);
        wrong_executable.raw_sha256 = format!("sha256:{}", "a".repeat(64)).into();
        assert_eq!(
            CheckerSpawnPlan::try_new(
                &policy,
                PROFILE_MANIFEST,
                &inactive,
                SpawnPurpose::Qualification,
                wrong_executable,
                ReadonlyBundleObservation::try_new(
                    root.path().join("wrong-executable-bundle"),
                    FilesystemObjectIdentity::try_new(1, 21).unwrap(),
                )
                .unwrap(),
                IsolatedWorkingDirectoryObservation::try_new_empty(
                    root.path().join("wrong-executable-working"),
                    FilesystemObjectIdentity::try_new(1, 31).unwrap(),
                )
                .unwrap(),
            )
            .unwrap_err()
            .code(),
            "spawn-executable-identity"
        );
        assert_eq!(
            CheckerSpawnPlan::try_new(
                &policy,
                PROFILE_MANIFEST,
                &inactive,
                SpawnPurpose::ProductInvocation,
                executable(&root, &inactive),
                ReadonlyBundleObservation::try_new(
                    root.path().join("bundle"),
                    FilesystemObjectIdentity::try_new(1, 20).unwrap(),
                )
                .unwrap(),
                IsolatedWorkingDirectoryObservation::try_new_empty(
                    root.path().join("working"),
                    FilesystemObjectIdentity::try_new(1, 30).unwrap(),
                )
                .unwrap(),
            )
            .unwrap_err()
            .code(),
            "spawn-registration-status"
        );
        let plan = plan_for(&root, &active, SpawnPurpose::ProductInvocation);
        assert_eq!(plan.purpose(), SpawnPurpose::ProductInvocation);
    }

    #[test]
    fn profile_digest_rebinding_cannot_weaken_outer_limits() {
        let mut manifest = parse(PROFILE_MANIFEST, true).unwrap();
        let Value::Object(root) = &mut manifest else {
            unreachable!();
        };
        let Value::Array(limit_sets) = &mut root
            .iter_mut()
            .find(|(name, _)| name == "limit_sets")
            .unwrap()
            .1
        else {
            unreachable!();
        };
        let Value::Object(limit_set) = limit_sets
            .iter_mut()
            .find(|value| {
                let Value::Object(object) = value else {
                    return false;
                };
                object.iter().any(|(name, value)| {
                    name == "id"
                        && matches!(
                            value,
                            Value::String(id)
                                if id == "keyed-finite-table-independent-check-process-v0.1"
                        )
                })
            })
            .unwrap()
        else {
            unreachable!();
        };
        let Value::Array(limits) = &mut limit_set
            .iter_mut()
            .find(|(name, _)| name == "limits")
            .unwrap()
            .1
        else {
            unreachable!();
        };
        let Value::Object(wall_limit) = limits
            .iter_mut()
            .find(|value| {
                let Value::Object(object) = value else {
                    return false;
                };
                object.iter().any(|(name, value)| {
                    name == "name" && matches!(value, Value::String(name) if name == "wall-clock")
                })
            })
            .unwrap()
        else {
            unreachable!();
        };
        wall_limit
            .iter_mut()
            .find(|(name, _)| name == "value")
            .unwrap()
            .1 = Value::String("6001".into());
        let manifest = canonical_bytes(&manifest);
        let manifest_digest = format!("sha256:{}", crate::sha256::digest_hex(&manifest));

        let mut policy = parse(POLICY, true).unwrap();
        set_string(
            &mut policy,
            &["invocation", "execution_profile", "raw_sha256"],
            &manifest_digest,
        );
        let policy_digest = domain_digest(
            "radishaxiom.checker-runtime-launcher-policy.v0.3",
            &policy,
            "policy_digest",
        )
        .unwrap();
        set_string(&mut policy, &["policy_digest"], &policy_digest);
        let policy = parse_launcher_policy(&canonical_bytes(&policy)).unwrap();
        assert_eq!(
            ExecutionProfileContract::parse(&manifest, &policy)
                .unwrap_err()
                .code(),
            "execution-profile-limit-set"
        );
    }

    #[test]
    fn one_clean_observation_yields_exactly_one_consumed_result() {
        let root = TemporaryRoot::create();
        let record = parse_registration_record(RECORD).unwrap();
        let plan = plan_for(&root, &record, SpawnPurpose::Qualification);
        let (result, request, evidence) = bound_result(&record);
        let outcome = consume_process_observation(
            &plan,
            &record,
            &request,
            &evidence,
            ProcessObservation::new(
                exited(StreamCapture::complete(result)),
                PostflightExecutableObservation::Observed(plan.executable().clone()),
            ),
        );
        let CheckerProcessOutcome::Result(result) = outcome else {
            panic!("expected consumed result");
        };
        assert_eq!(result.registration_digest(), record.document_digest());
    }

    #[test]
    fn process_stream_resource_and_parse_failures_never_become_results() {
        let root = TemporaryRoot::create();
        let record = parse_registration_record(RECORD).unwrap();
        let plan = plan_for(&root, &record, SpawnPurpose::Qualification);
        let (_, request, evidence) = bound_result(&record);
        let cases = [
            (ProcessTerminationObservation::SpawnFailed, "spawn-failed"),
            (
                ProcessTerminationObservation::TimedOut,
                "wall-clock-timeout",
            ),
            (
                ProcessTerminationObservation::WorkingMemoryLimitExceeded,
                "working-memory-limit-exceeded",
            ),
            (
                ProcessTerminationObservation::Signaled { signal: 9 },
                "process-signaled",
            ),
            (
                exited(StreamCapture::LimitExceeded),
                "stdout-limit-exceeded",
            ),
            (
                exited(StreamCapture::complete(b"not-json".to_vec())),
                "stdout-not-canonical-result",
            ),
            (
                exited_with(
                    1,
                    StreamCapture::complete(Vec::<u8>::new()),
                    StreamCapture::complete(b"failed".to_vec()),
                    1,
                    1,
                ),
                "nonzero-exit",
            ),
            (
                exited_with(
                    0,
                    StreamCapture::complete(Vec::<u8>::new()),
                    StreamCapture::LimitExceeded,
                    1,
                    1,
                ),
                "stderr-limit-exceeded",
            ),
            (
                exited_with(
                    0,
                    StreamCapture::complete(Vec::<u8>::new()),
                    StreamCapture::complete(vec![0xff]),
                    1,
                    1,
                ),
                "stderr-invalid-utf8",
            ),
            (
                exited_with(
                    0,
                    StreamCapture::complete(Vec::<u8>::new()),
                    StreamCapture::complete(Vec::<u8>::new()),
                    CHECKER_WALL_CLOCK_LIMIT_MILLIS + 1,
                    1,
                ),
                "wall-clock-limit-exceeded",
            ),
            (
                exited_with(
                    0,
                    StreamCapture::complete(Vec::<u8>::new()),
                    StreamCapture::complete(Vec::<u8>::new()),
                    1,
                    CHECKER_WORKING_MEMORY_LIMIT_BYTES + 1,
                ),
                "working-memory-limit-exceeded",
            ),
        ];
        for (termination, expected) in cases {
            assert_eq!(
                failure(consume_process_observation(
                    &plan,
                    &record,
                    &request,
                    &evidence,
                    ProcessObservation::new(
                        termination,
                        PostflightExecutableObservation::Observed(plan.executable().clone()),
                    ),
                )),
                (expected, OuterFailureClassification::ProcessFailure)
            );
        }
    }

    #[test]
    fn postflight_registration_and_result_identity_failures_are_not_consumable() {
        let root = TemporaryRoot::create();
        let record = parse_registration_record(RECORD).unwrap();
        let plan = plan_for(&root, &record, SpawnPurpose::Qualification);
        let (result, request, evidence) = bound_result(&record);

        let mut drifted_executable = plan.executable().clone();
        drifted_executable.object_identity = FilesystemObjectIdentity::try_new(1, 99).unwrap();
        assert_eq!(
            failure(consume_process_observation(
                &plan,
                &record,
                &request,
                &evidence,
                ProcessObservation::new(
                    exited(StreamCapture::complete(result.clone())),
                    PostflightExecutableObservation::Observed(drifted_executable),
                ),
            )),
            (
                "executable-identity-drift",
                OuterFailureClassification::IdentityFailure
            )
        );

        assert_eq!(
            failure(consume_process_observation(
                &plan,
                &record,
                &request,
                &evidence,
                ProcessObservation::new(
                    exited(StreamCapture::complete(result.clone())),
                    PostflightExecutableObservation::Unavailable,
                ),
            )),
            (
                "executable-postflight-unavailable",
                OuterFailureClassification::IdentityFailure
            )
        );

        let active = active_record();
        assert_eq!(
            failure(consume_process_observation(
                &plan,
                &active,
                &request,
                &evidence,
                ProcessObservation::new(
                    exited(StreamCapture::complete(result.clone())),
                    PostflightExecutableObservation::Observed(plan.executable().clone()),
                ),
            )),
            (
                "registration-identity-drift",
                OuterFailureClassification::IdentityFailure
            )
        );

        let other_request = IndependentDocumentBinding::try_available(
            format!("sha256:{}", "a".repeat(64)),
            format!("sha256:{}", "b".repeat(64)),
        )
        .unwrap();
        assert_eq!(
            failure(consume_process_observation(
                &plan,
                &record,
                &other_request,
                &evidence,
                ProcessObservation::new(
                    exited(StreamCapture::complete(result)),
                    PostflightExecutableObservation::Observed(plan.executable().clone()),
                ),
            )),
            (
                "result-identity-mismatch",
                OuterFailureClassification::IdentityFailure
            )
        );
    }
}
