use super::{
    Artifacts, BTreeMap, BTreeSet, EXECUTION, JsonLimits, OriginLimits, Result, ReviewError,
    ReviewLimits, TOOL, Value, decimal, entries, invalid, items, kind, member, nonempty, ordered,
    shape, strings, text,
};

const PRODUCER: &str = "evidence-producer";
const ROLES: &[(&str, &str)] = &[
    ("normalize", "ir-normalizer"),
    ("generate-obligations", "obligation-generator"),
    ("prove", "prover"),
    ("check-certificate", "certificate-checker"),
    ("check-fixture", "fixture-checker"),
    ("execute-host", "host-executor"),
    ("compare-output", "output-comparator"),
    ("replay-counterexample", "counterexample-replayer"),
];

pub(super) fn read_tools<'a>(
    rows: &'a [Value],
    producer: &str,
    artifacts: &Artifacts<'_, '_>,
) -> Result<BTreeMap<&'a str, BTreeSet<&'a str>>> {
    let mut tools = BTreeMap::new();
    for (id, row) in entries(rows, TOOL, "tools", false)? {
        let definition = shape(
            member(row, "definition"),
            "/tool/definition",
            &["artifact", "name", "roles", "version"],
        )?;
        artifacts.get(text(definition, "artifact")?, None)?;
        nonempty(definition, "name")?;
        let version = nonempty(definition, "version")?;
        if matches!(version, "latest" | "main" | "master" | "dev") {
            return Err(invalid("tool", "mutable version"));
        }
        let mut roles = BTreeSet::new();
        let mut previous = None;
        for role in strings(definition, "roles")? {
            ordered(&mut previous, role, "roles")?;
            if role != PRODUCER && !ROLES.iter().any(|&(_, known)| role == known) {
                return Err(invalid("tool", "unknown role"));
            }
            roles.insert(role);
        }
        if roles.is_empty() {
            return Err(invalid("tool", "missing role"));
        }
        tools.insert(id, roles);
    }
    if !tools
        .get(producer)
        .is_some_and(|roles| roles.contains(PRODUCER))
    {
        return Err(invalid("producer", "role"));
    }
    Ok(tools)
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum Mode {
    Structure,
    Effect,
    Origin,
}

impl Mode {
    fn read(mode: &str, kind: &str) -> Result<Self> {
        match (mode, kind) {
            ("strict-ir-v0.2", "normalize") => Ok(Self::Structure),
            ("core-empty-effects-v0.1", "prove") => Ok(Self::Effect),
            ("core-field-origin-v0.1", "prove") => Ok(Self::Origin),
            _ => Err(invalid("execution", "unsupported mode")),
        }
    }

    pub(super) fn target(self) -> &'static str {
        match self {
            Self::Structure => "ir-structure",
            Self::Effect => "effect-empty",
            Self::Origin => "field-origin",
        }
    }

    fn rule(self) -> (&'static str, &'static [u8]) {
        match self {
            Self::Structure => (
                "sha256:6d4fd0366adc15ab79ea7143b5cd656c0e3dc06df90be446c72c210e53a5480c",
                include_bytes!("../../../../docs/ir/axiom-ir-v0.2.md"),
            ),
            Self::Effect => (
                "sha256:80ec918ae8e5d952ebd7d984db452f22b65d69ebe8fa9f084150bd8d5353bb9b",
                include_bytes!("../../../../docs/query/core-empty-effects-v0.1.md"),
            ),
            Self::Origin => (
                "sha256:2a88689852fba4f505224d2f2043ae0382ba9a18b18e35d83b77fa1d5746878f",
                include_bytes!("../../../../docs/query/core-field-origin-v0.1.md"),
            ),
        }
    }
}

#[derive(Clone, Copy)]
pub(super) enum Attempt<'a> {
    Completed,
    Interrupted {
        kind: &'a str,
        code: &'a str,
        reason: &'static str,
    },
}

fn attempt(value: &Value) -> Result<Attempt<'_>> {
    let tag = kind(value)?;
    if tag == "completed" {
        shape(value, "/execution/result", &["kind"])?;
        return Ok(Attempt::Completed);
    }
    let result = shape(value, "/execution/result", &["kind", "code"])?;
    let code = nonempty(result, "code")?;
    if !code.as_bytes()[0].is_ascii_lowercase()
        || !code
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
    {
        return Err(invalid("execution", "diagnostic code"));
    }
    let reason = match tag {
        "timeout" => "timeout",
        "resource-exhausted" => "resource-exhausted",
        "unsupported" => "unsupported",
        "error" | "unavailable" => "operational-error",
        _ => return Err(invalid("execution", "attempt state")),
    };
    Ok(Attempt::Interrupted {
        kind: tag,
        code,
        reason,
    })
}

pub(super) struct Execution<'a> {
    pub mode: Mode,
    pub target: &'a str,
    pub inputs: BTreeMap<&'a str, &'a str>,
    pub outputs: BTreeMap<&'a str, &'a str>,
    pub limits: OriginLimits,
    pub attempt: Attempt<'a>,
}

pub(super) fn read_executions<'a>(
    rows: &'a [Value],
    tools: &BTreeMap<&str, BTreeSet<&str>>,
    artifacts: &Artifacts<'_, '_>,
    limits: ReviewLimits,
) -> Result<BTreeMap<&'a str, Execution<'a>>> {
    if rows.len() > limits.max_executions {
        return Err(ReviewError::Limit("executions"));
    }
    let mut result = BTreeMap::new();
    let mut ordinals = BTreeSet::new();
    for (id, row) in entries(rows, EXECUTION, "executions", false)? {
        let definition = shape(
            member(row, "definition"),
            "/execution/definition",
            &[
                "inputs",
                "kind",
                "limits",
                "mode",
                "obligation",
                "ordinal",
                "outputs",
                "provenance",
                "result",
                "rule",
                "tool",
            ],
        )?;
        let kind = text(definition, "kind")?;
        let tool = text(definition, "tool")?;
        let role = ROLES
            .iter()
            .find_map(|&(tag, role)| (tag == kind).then_some(role))
            .ok_or(invalid("execution", "unknown kind"))?;
        if !tools.get(tool).is_some_and(|roles| roles.contains(role)) {
            return Err(invalid("execution", "tool role"));
        }
        let mode = Mode::read(text(definition, "mode")?, kind)?;
        let ordinal = decimal(text(definition, "ordinal")?, "ordinal")?;
        if ordinal >= rows.len() || !ordinals.insert(ordinal) {
            return Err(invalid("execution", "ordinal"));
        }
        let (rule_pin, rule) = mode.rule();
        if text(definition, "rule")? != rule_pin
            || artifacts.get(rule_pin, Some(("evidence-rule", "0.1")))? != rule
        {
            return Err(invalid("execution", "rule binding"));
        }
        artifacts.get(
            text(definition, "provenance")?,
            Some(("execution-provenance", "0.1")),
        )?;
        let inputs = references(items(definition, "inputs")?, artifacts)?;
        let outputs = references(items(definition, "outputs")?, artifacts)?;
        let attempt = attempt(member(definition, "result"))?;
        if matches!(attempt, Attempt::Interrupted { .. }) && !outputs.is_empty() {
            return Err(invalid("execution", "interrupted output"));
        }
        result.insert(
            id,
            Execution {
                mode,
                target: text(definition, "obligation")?,
                inputs,
                outputs,
                attempt,
                limits: read_limits(items(definition, "limits")?, mode, limits.derivation)?,
            },
        );
    }
    Ok(result)
}

fn references<'a>(
    rows: &'a [Value],
    artifacts: &Artifacts<'_, '_>,
) -> Result<BTreeMap<&'a str, &'a str>> {
    let mut refs = BTreeMap::new();
    let mut previous = None;
    for value in rows {
        let row = shape(value, "/execution/reference", &["artifact", "role"])?;
        let role = text(row, "role")?;
        let artifact = text(row, "artifact")?;
        ordered(&mut previous, (role, artifact), "execution references")?;
        artifacts.get(artifact, None)?;
        if refs.insert(role, artifact).is_some() {
            return Err(invalid("execution", "repeated reference role"));
        }
    }
    Ok(refs)
}

fn read_limits(values: &[Value], mode: Mode, cap: OriginLimits) -> Result<OriginLimits> {
    let mut limits = BTreeMap::new();
    let mut previous = None;
    for value in values {
        let row = shape(value, "/execution/limits", &["name", "unit", "value"])?;
        let name = text(row, "name")?;
        let unit = text(row, "unit")?;
        ordered(&mut previous, (name, unit), "execution limits")?;
        limits.insert((name, unit), decimal(text(row, "value")?, "limit value")?);
    }
    let mut take = |name, unit, max| {
        let value = limits
            .remove(&(name, unit))
            .ok_or(invalid("execution limits", "name or unit"))?;
        if value > max {
            return Err(ReviewError::Limit(name));
        }
        Ok(value)
    };
    let ir_json = JsonLimits {
        max_input_bytes: take("max-input-bytes", "byte", cap.ir_json.max_input_bytes)?,
        max_values: take("max-values", "value", cap.ir_json.max_values)?,
        max_nesting: take("max-nesting", "level", cap.ir_json.max_nesting)?,
    };
    let result = if mode == Mode::Structure {
        OriginLimits { ir_json, ..cap }
    } else {
        OriginLimits {
            ir_json,
            max_steps: take("max-steps", "step", cap.max_steps)?,
            max_premise_edges: take("max-premise-edges", "edge", cap.max_premise_edges)?,
            max_descriptors: if mode == Mode::Origin {
                take("max-descriptors", "descriptor", cap.max_descriptors)?
            } else {
                0
            },
            max_path_bytes: take("max-path-bytes", "byte", cap.max_path_bytes)?,
            max_output_bytes: take("max-output-bytes", "byte", cap.max_output_bytes)?,
        }
    };
    if !limits.is_empty() {
        return Err(invalid("execution limits", "extra entry"));
    }
    Ok(result)
}
