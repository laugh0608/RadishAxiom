use crate::canonical::{
    DocumentError, ShapeSpec, Value, as_array, as_object, domain_digest, member, parse,
    string_member, validate_digest, validate_shape,
};
use crate::portable_path::validate_portable_relative_path;
use crate::selection::NativeTarget;

const POLICY_FORMAT: &str = "radishaxiom-checker-runtime-launcher-policy";
const POLICY_VERSION: &str = "0.2";
const POLICY_DOMAIN: &str = "radishaxiom.checker-runtime-launcher-policy.v0.2";

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
        "checker_boundary,component,dependency_status,edition,language,network_capability,public_surface,python_conformance,toolchain,workspace",
    ),
    (
        "$.installation",
        "authorization,current_status,executable,fetch,installed_state,network_boundary,publication,receipt,recovery,root,single_writer,slot_identity,slot_mutation,staging_rejections",
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
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InstallationLayout {
    executable_relative_path: Box<str>,
    receipt_filename: Box<str>,
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
    let installation_layout = validate_store_boundaries(root)?;
    validate_runtime_interfaces(root)?;

    Ok(LauncherPolicy {
        document_digest: calculated_digest,
        supported_targets,
        installation_layout,
    })
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
    ] {
        expect_string(implementation, field, expected, "$.implementation", code)?;
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

    fn refresh_digest(value: &mut Value) {
        let digest = domain_digest(POLICY_DOMAIN, value, "policy_digest").unwrap();
        set_root_string(value, "policy_digest", &digest);
    }

    #[test]
    fn current_policy_is_strictly_accepted() {
        let policy = parse_launcher_policy(POLICY).unwrap();
        assert_eq!(
            policy.document_digest(),
            "sha256:2a85a00c4e96b204223865b126963dba7e1a2003bf721bfb6660feca1eaeb42d"
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
        let mut version = parse(POLICY, true).unwrap();
        set_root_string(&mut version, "format_version", "0.1");
        refresh_digest(&mut version);
        assert_eq!(
            parse_launcher_policy(&canonical_bytes(&version))
                .unwrap_err()
                .code(),
            "policy-version"
        );

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
                "host_selection",
                "product_registration_status",
                "registered-inactive-allowed",
                "inactive-product-selection",
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
    }
}
