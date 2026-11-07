//! 从已固定的语料清单选择 case，引用原字节摘要。

use std::collections::BTreeSet;

use super::{FixtureSlot, HostDataError};
use crate::{
    declarations::{self as decode, DeclarationError, Members},
    fixtures::FixtureRole,
    json::{self, JsonLimits},
};

pub(super) struct Selection {
    pub benchmark_id: String,
    pub role: FixtureRole,
    pub sha256: String,
}

pub(super) fn select(
    raw: &[u8],
    case: &str,
    slot: FixtureSlot,
    limits: JsonLimits,
) -> Result<Selection, HostDataError> {
    let value = json::parse(raw, limits).map_err(DeclarationError::Json)?;
    let task = decode::object(
        &value,
        "",
        &[
            "benchmark_id",
            "candidates",
            "corpus_version",
            "fixtures",
            "format",
            "input_ports",
            "output",
            "scenarios",
            "task_contract_ids",
            "task_digest",
            "task_version",
        ],
    )?;
    if field(task, "format", "")? != "axiom-benchmark-task"
        || field(task, "task_version", "")? != "0.1"
        || field(task, "corpus_version", "")? != "0.1"
    {
        return Err(HostDataError::TaskSelection("manifest version or format"));
    }
    let benchmark_id = decode::name(decode::member(task, "benchmark_id"), "/benchmark_id")?;
    let fixtures = decode::array(decode::member(task, "fixtures"), "/fixtures")?;
    let mut names = BTreeSet::new();
    let mut selected = None;
    for (i, value) in fixtures.iter().enumerate() {
        let path = format!("/fixtures/{i}");
        let has_golden = matches!(value, json::Value::Object(fields) if fields.iter().any(|(name, _, _)| name == "golden"));
        let keys: &[_] = if has_golden {
            &["name", "kind", "input", "golden"]
        } else {
            &["name", "kind", "input"]
        };
        let fixture = decode::object(value, &path, keys)?;
        let name = field(fixture, "name", &path)?;
        if name.is_empty() || !names.insert(name) {
            return Err(HostDataError::TaskSelection("empty or duplicate case name"));
        }
        let role = match (field(fixture, "kind", &path)?, has_golden) {
            ("valid", true) => FixtureRole::Input,
            ("invalid", false) => FixtureRole::InvalidInput,
            _ => return Err(HostDataError::TaskSelection("case kind and slots")),
        };
        if name == case {
            selected = Some((fixture, role, path));
        }
    }
    let (fixture, input_role, path) =
        selected.ok_or(HostDataError::TaskSelection("unknown case"))?;
    let (slot_name, role) = match slot {
        FixtureSlot::Input => ("input", input_role),
        FixtureSlot::Golden if input_role == FixtureRole::Input => {
            ("golden", FixtureRole::GoldenOutput)
        }
        FixtureSlot::Golden => return Err(HostDataError::TaskSelection("case has no golden slot")),
    };
    let path = decode::child(&path, slot_name);
    let reference = decode::object(
        decode::member(fixture, slot_name),
        &path,
        &["path", "sha256"],
    )?;
    field(reference, "path", &path)?;
    let sha256 = decode::id(
        decode::member(reference, "sha256"),
        &decode::child(&path, "sha256"),
    )?;
    Ok(Selection {
        benchmark_id,
        role,
        sha256,
    })
}

fn field<'a>(members: &'a Members, name: &str, path: &str) -> Result<&'a str, DeclarationError> {
    decode::string(decode::member(members, name), &decode::child(path, name))
}
