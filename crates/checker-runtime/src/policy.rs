use crate::canonical::{
    DocumentError, ShapeSpec, Value, as_array, as_object, domain_digest, member, parse,
    parse_decimal, string_member, validate_digest, validate_shape,
};
use crate::portable_path::validate_portable_relative_path;
use crate::selection::NativeTarget;

const POLICY_FORMAT: &str = "radishaxiom-checker-runtime-launcher-policy";
const POLICY_VERSION: &str = "0.3";
const POLICY_DOMAIN: &str = "radishaxiom.checker-runtime-launcher-policy.v0.3";
pub(crate) const CHECKER_EXECUTION_PROFILE_ID: &str = "keyed-finite-table-independent-check-v0.1";
pub(crate) const CHECKER_EXECUTION_PROFILE_PATH: &str =
    "contracts/execution-profiles-v0.1/manifest.jcs";

const POLICY_OBJECT_FIELDS: &[(&str, &str)] = &[
    (
        "$",
        "activation,authority,digest_domain,failure_boundary,format,format_version,host_selection,implementation,installation,invocation,level,persistence,policy_digest,runtime_companion,runtime_interfaces",
    ),
    (
        "$.activation",
        "authorization,current_status,preconditions,product_selection,runtime_cardinality",
    ),
    ("$.authority[]", "name,path,raw_sha256"),
    (
        "$.failure_boundary[]",
        "classification,condition,independent_result",
    ),
    (
        "$.host_selection",
        "current_supported_targets,executable_format_verification,forbidden_resolution,host_identity_source,match,product_registration_status,qualification_registration_status,rosetta_policy,selection_cardinality,unknown_target,variant_policy",
    ),
    (
        "$.host_selection.current_supported_targets[]",
        "executable_format,goarch,goarm64,goos",
    ),
    (
        "$.implementation",
        "checker_boundary,component,dependency_status,edition,language,network_capability,platform_binding,public_surface,python_conformance,toolchain,workspace",
    ),
    (
        "$.implementation.platform_binding",
        "build_boundary,crate,dependency,ffi,target,unsafe_boundary",
    ),
    (
        "$.implementation.platform_binding.dependency",
        "crates_io_checksum,license,name,version",
    ),
    (
        "$.installation",
        "authorization,current_status,executable,fetch,filesystem,installed_state,network_boundary,publication,receipt,recovery,root,single_writer,slot_identity,slot_mutation,staging_rejections",
    ),
    (
        "$.installation.executable",
        "mode,relative_path,required_checks",
    ),
    (
        "$.installation.receipt",
        "canonicalization,digest_domain,filename,format,format_version,required_bindings,status",
    ),
    (
        "$.installation.filesystem",
        "containment,durability,platform,publication,required_primitives,unsupported",
    ),
    (
        "$.invocation",
        "argument_tokens,bundle,environment,executable_resolution,execution_profile,identity_revalidation,network,retry,stderr,stdin,stdout,working_directory",
    ),
    ("$.invocation.execution_profile", "id,path,raw_sha256"),
    (
        "$.persistence",
        "attempt_storage,canonical_identity_excludes,capabilities,interface,qualification_storage,recovery,root,root_discovery,slot_identity",
    ),
    (
        "$.runtime_companion",
        "current_status,format,format_version,identity_requirements,invocation_failure_format,qualification_record,qualification_scenarios,qualification_status,role,strict_contract",
    ),
    (
        "$.runtime_companion.qualification_record",
        "canonicalization,current_status,digest_domain,format,format_version,required_bindings,storage",
    ),
    (
        "$.runtime_companion.qualification_scenarios[]",
        "byte_length,id,outcome,raw_sha256",
    ),
    (
        "$.runtime_interfaces",
        "fetch,host_identity,installation_input,outer_failure,registry_input,result_consumer,spawn_plan",
    ),
];

const POLICY_ARRAY_PATHS: &[&str] = &[
    "$.activation.preconditions",
    "$.authority",
    "$.failure_boundary",
    "$.host_selection.current_supported_targets",
    "$.host_selection.forbidden_resolution",
    "$.installation.executable.required_checks",
    "$.installation.filesystem.required_primitives",
    "$.installation.receipt.required_bindings",
    "$.installation.staging_rejections",
    "$.invocation.argument_tokens",
    "$.persistence.canonical_identity_excludes",
    "$.persistence.capabilities",
    "$.runtime_companion.identity_requirements",
    "$.runtime_companion.qualification_record.required_bindings",
    "$.runtime_companion.qualification_scenarios",
];

const POLICY_SHAPE: ShapeSpec<'static> = ShapeSpec {
    object_fields: POLICY_OBJECT_FIELDS,
    array_paths: POLICY_ARRAY_PATHS,
    bool_paths: &[],
};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LauncherPolicy {
    document_digest: String,
    supported_targets: Vec<NativeTarget>,
    installation_layout: InstallationLayout,
    execution_profile: ExecutionProfileIdentity,
    qualification_scenarios: Vec<QualificationScenario>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InstallationLayout {
    executable_relative_path: Box<str>,
    receipt_filename: Box<str>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct ExecutionProfileIdentity {
    pub(crate) id: Box<str>,
    pub(crate) path: Box<str>,
    pub(crate) raw_sha256: Box<str>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct QualificationScenario {
    pub(crate) id: Box<str>,
    pub(crate) outcome: Box<str>,
    pub(crate) byte_length: u64,
    pub(crate) raw_sha256: Box<str>,
}

impl InstallationLayout {
    pub fn executable_relative_path(&self) -> &str {
        &self.executable_relative_path
    }

    pub fn receipt_filename(&self) -> &str {
        &self.receipt_filename
    }
}

impl LauncherPolicy {
    pub fn document_digest(&self) -> &str {
        &self.document_digest
    }

    pub fn supported_targets(&self) -> &[NativeTarget] {
        &self.supported_targets
    }

    pub fn installation_layout(&self) -> &InstallationLayout {
        &self.installation_layout
    }

    pub(crate) fn supports(&self, target: &NativeTarget) -> bool {
        self.supported_targets.contains(target)
    }

    pub(crate) fn execution_profile(&self) -> &ExecutionProfileIdentity {
        &self.execution_profile
    }

    pub(crate) fn qualification_scenarios(&self) -> &[QualificationScenario] {
        &self.qualification_scenarios
    }
}

pub fn parse_launcher_policy(bytes: &[u8]) -> Result<LauncherPolicy, DocumentError> {
    let value = parse(bytes, true)?;
    validate_shape(&value, &POLICY_SHAPE)?;
    let root = as_object(&value, "$")?;

    expect_string(root, "format", POLICY_FORMAT, "$", "policy-format")?;
    expect_string(
        root,
        "format_version",
        POLICY_VERSION,
        "$",
        "policy-version",
    )?;
    expect_string(root, "digest_domain", POLICY_DOMAIN, "$", "policy-domain")?;
    expect_string(
        root,
        "level",
        "specified-not-implemented",
        "$",
        "policy-level",
    )?;

    let stored_digest = string_member(root, "policy_digest", "$")?;
    validate_digest(stored_digest, "$.policy_digest")?;
    let calculated_digest = domain_digest(POLICY_DOMAIN, &value, "policy_digest")?;
    if stored_digest != calculated_digest {
        return Err(DocumentError::new("policy-digest", "$.policy_digest"));
    }

    validate_activation(root)?;
    let supported_targets = validate_host_selection(root)?;
    validate_implementation(root)?;
    validate_invocation(root)?;
    let installation_layout = validate_store_boundaries(root)?;
    let (execution_profile, qualification_scenarios) = validate_runtime_companion(root)?;
    validate_runtime_interfaces(root)?;

    Ok(LauncherPolicy {
        document_digest: calculated_digest,
        supported_targets,
        installation_layout,
        execution_profile,
        qualification_scenarios,
    })
}

fn validate_invocation(root: &[(String, Value)]) -> Result<(), DocumentError> {
    let invocation = object_member(root, "invocation", "$")?;
    for (field, expected, code) in [
        (
            "bundle",
            "caller-mounted-readonly-canonical-realpath",
            "invocation-bundle-boundary",
        ),
        (
            "environment",
            "empty-no-inheritance",
            "invocation-environment-boundary",
        ),
        (
            "executable_resolution",
            "exact-active-content-addressed-slot-only",
            "invocation-executable-resolution",
        ),
        (
            "identity_revalidation",
            "before-and-after-every-spawn",
            "invocation-identity-revalidation",
        ),
        ("network", "forbidden", "invocation-network-boundary"),
        (
            "retry",
            "new-attempt-same-exact-slot-only-never-automatic-fallback",
            "invocation-retry-boundary",
        ),
        (
            "stderr",
            "bounded-diagnostic-never-result",
            "invocation-stderr-boundary",
        ),
        ("stdin", "empty-then-eof", "invocation-stdin-boundary"),
        (
            "stdout",
            "one-canonical-independent-result-or-no-result",
            "invocation-stdout-boundary",
        ),
        (
            "working_directory",
            "isolated-empty",
            "invocation-working-directory",
        ),
    ] {
        expect_string(invocation, field, expected, "$.invocation", code)?;
    }

    let arguments = as_array(
        member(invocation, "argument_tokens", "$.invocation")?,
        "$.invocation.argument_tokens",
    )?;
    let expected = [
        "check",
        "--bundle-root=<caller-mounted-readonly-canonical-realpath>",
    ];
    if arguments.len() != expected.len()
        || arguments
            .iter()
            .zip(expected)
            .any(|(actual, expected)| !matches!(actual, Value::String(text) if text == expected))
    {
        return Err(DocumentError::new(
            "invocation-argument-tokens",
            "$.invocation.argument_tokens",
        ));
    }
    Ok(())
}

fn validate_activation(root: &[(String, Value)]) -> Result<(), DocumentError> {
    let activation = object_member(root, "activation", "$")?;
    expect_string(
        activation,
        "product_selection",
        "active-registration-and-qualified-installation-only",
        "$.activation",
        "inactive-product-selection",
    )?;
    expect_string(
        activation,
        "runtime_cardinality",
        "exactly-one-active-record-per-target-or-fail",
        "$.activation",
        "selection-cardinality-policy",
    )
}

fn validate_host_selection(root: &[(String, Value)]) -> Result<Vec<NativeTarget>, DocumentError> {
    let host = object_member(root, "host_selection", "$")?;
    for (field, expected, code) in [
        (
            "match",
            "exact-goos-goarch-goarm64-executable-format",
            "target-fallback",
        ),
        (
            "selection_cardinality",
            "exactly-one-or-fail",
            "selection-cardinality-policy",
        ),
        (
            "product_registration_status",
            "active-only",
            "inactive-product-selection",
        ),
        (
            "qualification_registration_status",
            "registered-inactive-only",
            "qualification-selection",
        ),
        (
            "rosetta_policy",
            "translated-amd64-process-cannot-select-arm64-payload",
            "rosetta-policy",
        ),
        (
            "unknown_target",
            "fail-closed-no-fallback",
            "unknown-target-policy",
        ),
    ] {
        expect_string(host, field, expected, "$.host_selection", code)?;
    }

    let target_values = as_array(
        member(host, "current_supported_targets", "$.host_selection")?,
        "$.host_selection.current_supported_targets",
    )?;
    if target_values.is_empty() {
        return Err(DocumentError::new(
            "supported-target-set",
            "$.host_selection.current_supported_targets",
        ));
    }
    let mut targets = Vec::with_capacity(target_values.len());
    for (index, value) in target_values.iter().enumerate() {
        let target = NativeTarget::from_value(
            value,
            &format!("$.host_selection.current_supported_targets[{index}]"),
        )?;
        if targets.contains(&target) {
            return Err(DocumentError::new(
                "duplicate-supported-target",
                format!("$.host_selection.current_supported_targets[{index}]"),
            ));
        }
        targets.push(target);
    }
    Ok(targets)
}

fn validate_implementation(root: &[(String, Value)]) -> Result<(), DocumentError> {
    let implementation = object_member(root, "implementation", "$")?;
    for (field, expected, code) in [
        ("language", "rust", "product-runtime-host"),
        ("edition", "2024", "product-runtime-host"),
        ("toolchain", "1.97.1", "product-runtime-host"),
        (
            "workspace",
            "same-cargo-workspace-and-product-release-graph-as-raxc",
            "product-runtime-host",
        ),
        (
            "checker_boundary",
            "exact-digest-offline-subprocess-only-no-source-or-parser-reuse",
            "checker-implementation-reuse",
        ),
        (
            "network_capability",
            "absent-from-installer-launcher-core",
            "runtime-core-network-capability",
        ),
        (
            "python_conformance",
            "test-oracle-only-never-product-runtime",
            "python-runtime-dependency",
        ),
        (
            "dependency_status",
            "libc-0.2.189-exact-reviewed-and-authorized",
            "runtime-dependency-boundary",
        ),
    ] {
        expect_string(implementation, field, expected, "$.implementation", code)?;
    }
    let platform = object_member(implementation, "platform_binding", "$.implementation")?;
    for (field, expected) in [
        (
            "build_boundary",
            "libc-upstream-build-script-only-no-project-c-shim",
        ),
        ("crate", "radishaxiom-checker-runtime-darwin-store"),
        ("ffi", "darwin-filesystem-only"),
        ("target", "cfg-target-os-macos"),
        (
            "unsafe_boundary",
            "private-platform-crate-only-core-forbids-unsafe",
        ),
    ] {
        expect_string(
            platform,
            field,
            expected,
            "$.implementation.platform_binding",
            "runtime-platform-binding",
        )?;
    }
    let dependency = object_member(platform, "dependency", "$.implementation.platform_binding")?;
    for (field, expected) in [
        (
            "crates_io_checksum",
            "sha256:3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2",
        ),
        ("license", "MIT OR Apache-2.0"),
        ("name", "libc"),
        ("version", "0.2.189"),
    ] {
        expect_string(
            dependency,
            field,
            expected,
            "$.implementation.platform_binding.dependency",
            "runtime-platform-binding",
        )?;
    }
    Ok(())
}

fn validate_store_boundaries(
    root: &[(String, Value)],
) -> Result<InstallationLayout, DocumentError> {
    let persistence = object_member(root, "persistence", "$")?;
    expect_string(
        persistence,
        "interface",
        "checker-runtime-store-v0.1",
        "$.persistence",
        "runtime-store-interface",
    )?;
    expect_string(
        persistence,
        "root",
        "product-injected-canonical-user-local-private-root",
        "$.persistence",
        "runtime-store-root",
    )?;
    expect_string(
        persistence,
        "root_discovery",
        "never-environment-cwd-repository-or-user-input",
        "$.persistence",
        "runtime-store-root-discovery",
    )?;

    let expected_capabilities = [
        "acquire-target-lock",
        "create-owned-staging",
        "publish-slot-exclusive",
        "read-slot-exact",
        "create-qualification-exclusive",
        "append-attempt",
    ];
    let capabilities = as_array(
        member(persistence, "capabilities", "$.persistence")?,
        "$.persistence.capabilities",
    )?;
    if capabilities.len() != expected_capabilities.len()
        || capabilities
            .iter()
            .zip(expected_capabilities)
            .any(|(actual, expected)| !matches!(actual, Value::String(text) if text == expected))
    {
        return Err(DocumentError::new(
            "runtime-store-capabilities",
            "$.persistence.capabilities",
        ));
    }

    let installation = object_member(root, "installation", "$")?;
    expect_string(
        installation,
        "publication",
        "same-filesystem-descriptor-relative-verified-staging-then-exclusive-renameatx-np",
        "$.installation",
        "runtime-store-publication",
    )?;
    let filesystem = object_member(installation, "filesystem", "$.installation")?;
    for (field, expected) in [
        ("containment", "descriptor-relative-no-follow-beneath"),
        (
            "durability",
            "f-fullfsync-files-and-directories-before-success",
        ),
        ("platform", "darwin"),
        ("publication", "renameatx-np-exclusive-no-follow-beneath"),
        ("unsupported", "fail-closed-no-weaker-fallback"),
    ] {
        expect_string(
            filesystem,
            field,
            expected,
            "$.installation.filesystem",
            "runtime-store-filesystem-boundary",
        )?;
    }
    let required_primitives = as_array(
        member(
            filesystem,
            "required_primitives",
            "$.installation.filesystem",
        )?,
        "$.installation.filesystem.required_primitives",
    )?;
    let expected_primitives = [
        "f-fullfsync",
        "o-nofollow-any",
        "renameatx-np-rename-excl",
        "renameatx-np-rename-nofollow-any",
        "renameatx-np-rename-resolve-beneath",
    ];
    if required_primitives.len() != expected_primitives.len()
        || required_primitives
            .iter()
            .zip(expected_primitives)
            .any(|(value, expected)| !matches!(value, Value::String(actual) if actual == expected))
    {
        return Err(DocumentError::new(
            "runtime-store-filesystem-boundary",
            "$.installation.filesystem.required_primitives",
        ));
    }
    let installation_root = string_member(installation, "root", "$.installation")?;
    let persistence_root = string_member(persistence, "root", "$.persistence")?;
    if installation_root != persistence_root {
        return Err(DocumentError::new(
            "runtime-store-root",
            "$.installation.root",
        ));
    }
    let executable = object_member(installation, "executable", "$.installation")?;
    expect_string(
        executable,
        "mode",
        "0755",
        "$.installation.executable",
        "installation-executable-mode",
    )?;
    let executable_relative_path =
        string_member(executable, "relative_path", "$.installation.executable")?;
    validate_portable_relative_path(executable_relative_path).map_err(|_| {
        DocumentError::new(
            "installation-layout-path",
            "$.installation.executable.relative_path",
        )
    })?;
    let receipt = object_member(installation, "receipt", "$.installation")?;
    let receipt_filename = string_member(receipt, "filename", "$.installation.receipt")?;
    validate_portable_relative_path(receipt_filename).map_err(|_| {
        DocumentError::new(
            "installation-layout-path",
            "$.installation.receipt.filename",
        )
    })?;
    Ok(InstallationLayout {
        executable_relative_path: executable_relative_path.into(),
        receipt_filename: receipt_filename.into(),
    })
}

fn validate_runtime_interfaces(root: &[(String, Value)]) -> Result<(), DocumentError> {
    let interfaces = object_member(root, "runtime_interfaces", "$")?;
    for (field, expected, code) in [
        (
            "fetch",
            "separate-authorized-coordinator-never-core",
            "runtime-fetch-boundary",
        ),
        (
            "result_consumer",
            "single-product-rust-consumer-shared-by-qualification-and-invocation",
            "runtime-result-consumer",
        ),
        (
            "outer_failure",
            "typed-product-outcome-never-independent-result",
            "outer-failure-result-boundary",
        ),
        (
            "host_identity",
            "trusted-native-platform-adapter-only",
            "host-identity-boundary",
        ),
    ] {
        expect_string(interfaces, field, expected, "$.runtime_interfaces", code)?;
    }
    Ok(())
}

fn validate_runtime_companion(
    root: &[(String, Value)],
) -> Result<(ExecutionProfileIdentity, Vec<QualificationScenario>), DocumentError> {
    let invocation = object_member(root, "invocation", "$")?;
    let profile = object_member(invocation, "execution_profile", "$.invocation")?;
    let profile_digest = string_member(profile, "raw_sha256", "$.invocation.execution_profile")?;
    validate_digest(profile_digest, "$.invocation.execution_profile.raw_sha256")?;
    let profile_path = string_member(profile, "path", "$.invocation.execution_profile")?;
    validate_portable_relative_path(profile_path).map_err(|_| {
        DocumentError::new(
            "qualification-execution-profile-path",
            "$.invocation.execution_profile.path",
        )
    })?;
    if profile_path != CHECKER_EXECUTION_PROFILE_PATH {
        return Err(DocumentError::new(
            "qualification-execution-profile-path",
            "$.invocation.execution_profile.path",
        ));
    }
    let profile_id = string_member(profile, "id", "$.invocation.execution_profile")?;
    if profile_id != CHECKER_EXECUTION_PROFILE_ID {
        return Err(DocumentError::new(
            "qualification-execution-profile-id",
            "$.invocation.execution_profile.id",
        ));
    }
    let execution_profile = ExecutionProfileIdentity {
        id: profile_id.into(),
        path: profile_path.into(),
        raw_sha256: profile_digest.into(),
    };

    let runtime = object_member(root, "runtime_companion", "$")?;
    let qualification_record =
        object_member(runtime, "qualification_record", "$.runtime_companion")?;
    for (field, expected, code) in [
        (
            "canonicalization",
            "canonical-json-ascii-no-trailing-newline",
            "qualification-canonicalization",
        ),
        (
            "digest_domain",
            "radishaxiom.checker-runtime-qualification-record.v0.1",
            "qualification-domain",
        ),
        (
            "format",
            "radishaxiom-checker-runtime-qualification-record",
            "qualification-format",
        ),
        ("format_version", "0.1", "qualification-version"),
    ] {
        expect_string(
            qualification_record,
            field,
            expected,
            "$.runtime_companion.qualification_record",
            code,
        )?;
    }

    let rows = as_array(
        member(runtime, "qualification_scenarios", "$.runtime_companion")?,
        "$.runtime_companion.qualification_scenarios",
    )?;
    if rows.len() != 3 {
        return Err(DocumentError::new(
            "qualification-scenario-set",
            "$.runtime_companion.qualification_scenarios",
        ));
    }
    let mut scenarios = Vec::with_capacity(rows.len());
    for (index, row) in rows.iter().enumerate() {
        let path = format!("$.runtime_companion.qualification_scenarios[{index}]");
        let row = as_object(row, &path)?;
        let id = string_member(row, "id", &path)?;
        if id.contains('/') || validate_portable_relative_path(id).is_err() {
            return Err(DocumentError::new(
                "qualification-scenario-id",
                format!("{path}.id"),
            ));
        }
        let outcome = string_member(row, "outcome", &path)?;
        if !matches!(
            outcome,
            "accepted" | "accepted-with-trust" | "incomplete" | "rejected"
        ) {
            return Err(DocumentError::new(
                "qualification-outcome",
                format!("{path}.outcome"),
            ));
        }
        let raw_sha256 = string_member(row, "raw_sha256", &path)?;
        validate_digest(raw_sha256, &format!("{path}.raw_sha256"))?;
        scenarios.push(QualificationScenario {
            id: id.into(),
            outcome: outcome.into(),
            byte_length: parse_decimal(
                string_member(row, "byte_length", &path)?,
                &format!("{path}.byte_length"),
            )?,
            raw_sha256: raw_sha256.into(),
        });
    }
    if !scenarios.windows(2).all(|pair| pair[0].id < pair[1].id) {
        return Err(DocumentError::new(
            "qualification-scenario-set",
            "$.runtime_companion.qualification_scenarios",
        ));
    }
    Ok((execution_profile, scenarios))
}

fn object_member<'a>(
    object: &'a [(String, Value)],
    name: &str,
    path: &str,
) -> Result<&'a [(String, Value)], DocumentError> {
    as_object(member(object, name, path)?, &format!("{path}.{name}"))
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

#[cfg(test)]
mod tests {
    use super::{POLICY_DOMAIN, parse_launcher_policy};
    use crate::canonical::{Value, canonical_bytes, domain_digest, parse};

    const POLICY: &[u8] =
        include_bytes!("../../../contracts/checker-runtime-payloads-v0.1/launcher-policy.jcs");

    fn set_root_string(value: &mut Value, key: &str, replacement: &str) {
        let Value::Object(object) = value else {
            panic!("fixture root must be an object");
        };
        let (_, member) = object.iter_mut().find(|(name, _)| name == key).unwrap();
        *member = Value::String(replacement.into());
    }

    fn set_nested_string(value: &mut Value, parent: &str, key: &str, replacement: &str) {
        let Value::Object(root) = value else {
            panic!("fixture root must be an object");
        };
        let (_, Value::Object(object)) = root.iter_mut().find(|(name, _)| name == parent).unwrap()
        else {
            panic!("fixture parent must be an object");
        };
        let (_, member) = object.iter_mut().find(|(name, _)| name == key).unwrap();
        *member = Value::String(replacement.into());
    }

    fn set_path_string(value: &mut Value, path: &[&str], replacement: &str) {
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

    fn refresh_digest(value: &mut Value) {
        let digest = domain_digest(POLICY_DOMAIN, value, "policy_digest").unwrap();
        set_root_string(value, "policy_digest", &digest);
    }

    #[test]
    fn current_policy_is_strictly_accepted() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        assert_eq!(
            policy.document_digest(),
            "sha256:4c4943002d6c0199d834d3e3361c8bca0cf1329137985a009d3b2b270d5b705c"
        );
        assert_eq!(policy.supported_targets().len(), 1);
        assert_eq!(
            policy.installation_layout().executable_relative_path(),
            "payload/radishaxiom-independent-checker-go"
        );
        assert_eq!(
            policy.installation_layout().receipt_filename(),
            "checker-runtime-installation-receipt-v0.1.jcs"
        );
    }

    #[test]
    fn duplicate_unknown_and_noncanonical_policy_fail_closed() {
        let mut duplicate = br#"{"activation":{},"#.to_vec();
        duplicate.extend_from_slice(&POLICY[1..]);
        assert_eq!(
            parse_launcher_policy(&duplicate).unwrap_err().code(),
            "duplicate-member"
        );

        let mut value = parse(POLICY, true).unwrap();
        let Value::Object(object) = &mut value else {
            panic!("fixture root must be an object");
        };
        object.push(("unknown".into(), Value::String("closed".into())));
        refresh_digest(&mut value);
        assert_eq!(
            parse_launcher_policy(&canonical_bytes(&value))
                .unwrap_err()
                .code(),
            "unknown-member"
        );

        let mut missing = parse(POLICY, true).unwrap();
        let Value::Object(object) = &mut missing else {
            panic!("fixture root must be an object");
        };
        object.retain(|(name, _)| name != "level");
        refresh_digest(&mut missing);
        assert_eq!(
            parse_launcher_policy(&canonical_bytes(&missing))
                .unwrap_err()
                .code(),
            "missing-member"
        );

        let mut spaced = POLICY.to_vec();
        spaced.push(b'\n');
        assert_eq!(
            parse_launcher_policy(&spaced).unwrap_err().code(),
            "noncanonical-json"
        );
    }

    #[test]
    fn version_and_digest_drift_fail_closed() {
        for superseded in ["0.1", "0.2"] {
            let mut version = parse(POLICY, true).unwrap();
            set_root_string(&mut version, "format_version", superseded);
            refresh_digest(&mut version);
            assert_eq!(
                parse_launcher_policy(&canonical_bytes(&version))
                    .unwrap_err()
                    .code(),
                "policy-version"
            );
        }

        let mut digest = parse(POLICY, true).unwrap();
        set_root_string(
            &mut digest,
            "policy_digest",
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        );
        assert_eq!(
            parse_launcher_policy(&canonical_bytes(&digest))
                .unwrap_err()
                .code(),
            "policy-digest"
        );
    }

    #[test]
    fn duplicate_target_and_semantic_boundary_drift_fail_closed() {
        let mut duplicate = parse(POLICY, true).unwrap();
        let Value::Object(root) = &mut duplicate else {
            panic!("fixture root must be an object");
        };
        let (_, Value::Object(host)) = root
            .iter_mut()
            .find(|(name, _)| name == "host_selection")
            .unwrap()
        else {
            panic!("host selection must be an object");
        };
        let (_, Value::Array(targets)) = host
            .iter_mut()
            .find(|(name, _)| name == "current_supported_targets")
            .unwrap()
        else {
            panic!("supported targets must be an array");
        };
        targets.push(targets[0].clone());
        refresh_digest(&mut duplicate);
        assert_eq!(
            parse_launcher_policy(&canonical_bytes(&duplicate))
                .unwrap_err()
                .code(),
            "duplicate-supported-target"
        );

        for (parent, key, replacement, code) in [
            (
                "implementation",
                "language",
                "python",
                "product-runtime-host",
            ),
            (
                "implementation",
                "network_capability",
                "provider-download-enabled",
                "runtime-core-network-capability",
            ),
            (
                "implementation",
                "dependency_status",
                "unreviewed-platform-dependency",
                "runtime-dependency-boundary",
            ),
            (
                "installation",
                "publication",
                "portable-rename-fallback",
                "runtime-store-publication",
            ),
            (
                "host_selection",
                "product_registration_status",
                "registered-inactive-allowed",
                "inactive-product-selection",
            ),
            (
                "invocation",
                "environment",
                "inherit-process-environment",
                "invocation-environment-boundary",
            ),
            (
                "invocation",
                "identity_revalidation",
                "installation-time-only",
                "invocation-identity-revalidation",
            ),
            (
                "invocation",
                "network",
                "allowed",
                "invocation-network-boundary",
            ),
        ] {
            let mut value = parse(POLICY, true).unwrap();
            set_nested_string(&mut value, parent, key, replacement);
            refresh_digest(&mut value);
            assert_eq!(
                parse_launcher_policy(&canonical_bytes(&value))
                    .unwrap_err()
                    .code(),
                code
            );
        }

        let mut arguments = parse(POLICY, true).unwrap();
        let Value::Object(root) = &mut arguments else {
            unreachable!();
        };
        let (_, Value::Object(invocation)) = root
            .iter_mut()
            .find(|(name, _)| name == "invocation")
            .unwrap()
        else {
            unreachable!();
        };
        let (_, Value::Array(tokens)) = invocation
            .iter_mut()
            .find(|(name, _)| name == "argument_tokens")
            .unwrap()
        else {
            unreachable!();
        };
        tokens.push(Value::String("--fallback".into()));
        refresh_digest(&mut arguments);
        assert_eq!(
            parse_launcher_policy(&canonical_bytes(&arguments))
                .unwrap_err()
                .code(),
            "invocation-argument-tokens"
        );

        for (field, replacement, code) in [
            (
                "id",
                "other-profile-v0.1",
                "qualification-execution-profile-id",
            ),
            (
                "path",
                "contracts/other/manifest.jcs",
                "qualification-execution-profile-path",
            ),
        ] {
            let mut value = parse(POLICY, true).unwrap();
            set_path_string(
                &mut value,
                &["invocation", "execution_profile", field],
                replacement,
            );
            refresh_digest(&mut value);
            assert_eq!(
                parse_launcher_policy(&canonical_bytes(&value))
                    .unwrap_err()
                    .code(),
                code
            );
        }
    }
}
