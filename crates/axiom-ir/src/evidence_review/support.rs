use super::{
    Artifacts, BTreeMap, BTreeSet, CanonicalDocument, DocumentError, Entries, IrVersion,
    JsonLimits, Result, ReviewError, ReviewLimits, Subject, V0_2_SEMANTICS_SHA256, Value, decimal,
    encode,
    execution::{Attempt, Execution, Mode},
    invalid, kind, member, named, ordered, shape, strict, string, strings, text, value_object,
    value_string,
};
use crate::{
    contracts::ContractError,
    declarations::{DeclarationError, DeclarationErrorKind, Label, ValueType},
    document::{check_canonical_document, normalize_document},
    effects::{EFFECT_ARTIFACT, EffectLimits, EffectProfile, check_empty_effects},
    json::{self, JsonErrorKind, ResourceLimit},
    nodes::{NodeError, NodeKind},
    origins::{ORIGIN_ARTIFACT, OriginProfile, check_field_origin},
    query::GeneratorIdentity,
};

pub(super) enum Verdict {
    Checked(Vec<String>),
    Rejected(Value),
    Replayed,
    Interrupted,
}

pub(super) fn rebuild(
    run: &Execution<'_>,
    target_kind: &str,
    subject: &Subject<'_>,
    artifacts: &Artifacts<'_, '_>,
    limits: ReviewLimits,
) -> Result<Verdict> {
    if run.mode.target() != target_kind {
        return Err(invalid("execution", "target kind"));
    }
    match run.mode {
        Mode::Structure => structure(run, subject, artifacts),
        Mode::Effect | Mode::Origin => proof(run, subject, artifacts, limits.evidence_json),
    }
}

fn require_roles(references: &BTreeMap<&str, &str>, expected: &[&str]) -> Result<()> {
    if !references.keys().copied().eq(expected.iter().copied()) {
        return Err(invalid("execution", "input or output roles"));
    }
    Ok(())
}

fn structure(
    run: &Execution<'_>,
    subject: &Subject<'_>,
    artifacts: &Artifacts<'_, '_>,
) -> Result<Verdict> {
    require_roles(&run.inputs, &["candidate"])?;
    let pin = run.inputs["candidate"];
    if pin != subject.artifact {
        return Err(invalid("normalize", "original candidate binding"));
    }
    let valid = subject.document.as_ref();
    let format = if valid.is_some() {
        ("axiom-ir", "0.2")
    } else {
        ("ir-candidate", "0.1")
    };
    let raw = artifacts.get(pin, Some(format))?;
    if let Attempt::Interrupted { kind, code, .. } = run.attempt {
        if valid.is_none() {
            return Err(invalid("normalize", "unclassified subject"));
        }
        if kind == "resource-exhausted" {
            let error = check_canonical_document(raw, run.limits.ir_json).err();
            if resource_code(error.as_ref()) != Some(code) {
                return Err(invalid("normalize", "resource observation"));
            }
        }
        return Ok(Verdict::Interrupted);
    }
    let outputs: &[_] = if valid.is_some() {
        &["canonical-ir", "structure-observation"]
    } else {
        &["structure-observation"]
    };
    require_roles(&run.outputs, outputs)?;
    let observation = artifacts.get(
        run.outputs["structure-observation"],
        Some(("axiom-ir-structure-observation", "0.1")),
    )?;
    let outcome = check_canonical_document(raw, run.limits.ir_json);
    if let Some(document) = valid {
        let rebuilt = outcome.map_err(ReviewError::Ir)?;
        if rebuilt.document_id() != document.document_id() || run.outputs["canonical-ir"] != pin {
            return Err(invalid("normalize", "canonical output binding"));
        }
        let expected = value_object([
            ("document", value_string(document.document_id())),
            ("kind", value_string("accepted")),
        ]);
        if observation != encode(&expected) {
            return Err(invalid("normalize", "accepted observation"));
        }
        let pins: BTreeSet<_> = run
            .inputs
            .values()
            .chain(run.outputs.values())
            .copied()
            .collect();
        Ok(Verdict::Checked(
            pins.into_iter().map(str::to_owned).collect(),
        ))
    } else {
        let error = outcome
            .err()
            .ok_or(invalid("normalize", "candidate passed"))?;
        let rejection = rejection(raw, run.limits.ir_json, error)?;
        if observation
            != encode(&value_object([
                ("kind", value_string("rejected")),
                ("reason", value_string(rejection.reason)),
                ("location", rejection.location(None)),
            ]))
        {
            return Err(invalid("normalize", "rejected observation"));
        }
        Ok(Verdict::Rejected(value_object([
            ("kind", value_string("structure-path")),
            (
                "minimality",
                value_object([("kind", value_string("unreduced"))]),
            ),
            (
                "observed",
                value_object([("reason", value_string(rejection.reason))]),
            ),
            ("preconditions", Value::Array(Vec::new())),
            ("worlds", Value::Array(Vec::new())),
            ("trace", Value::Array(vec![rejection.location(Some(pin))])),
        ])))
    }
}

fn resource_code(error: Option<&DocumentError>) -> Option<&'static str> {
    let Some(DocumentError::Ir(ContractError::Input(DeclarationError::Json(error)))) = error else {
        return None;
    };
    match error.kind {
        JsonErrorKind::ResourceLimit(ResourceLimit::InputBytes) => Some("input-bytes"),
        JsonErrorKind::ResourceLimit(ResourceLimit::Values) => Some("values"),
        JsonErrorKind::ResourceLimit(ResourceLimit::Nesting) => Some("nesting"),
        _ => None,
    }
}

enum Location {
    Byte { offset: usize, length: usize },
    Member(String),
}

struct Rejection {
    reason: &'static str,
    location: Location,
}

impl Rejection {
    fn location(&self, artifact: Option<&str>) -> Value {
        let mut fields = match &self.location {
            Location::Byte { offset, length } => vec![
                ("kind".to_owned(), value_string("candidate-bytes"), 0),
                ("length".to_owned(), value_string(&length.to_string()), 0),
                ("offset".to_owned(), value_string(&offset.to_string()), 0),
            ],
            Location::Member(name) => vec![
                ("kind".to_owned(), value_string("candidate-member"), 0),
                ("path".to_owned(), Value::Array(vec![value_string(name)]), 0),
            ],
        };
        if let Some(pin) = artifact {
            fields.insert(0, ("artifact".to_owned(), value_string(pin), 0));
        }
        Value::Object(fields)
    }
}

fn rejection(raw: &[u8], limits: JsonLimits, error: DocumentError) -> Result<Rejection> {
    match error {
        DocumentError::NonCanonical { offset } => {
            let normalized = normalize_document(raw, limits).map_err(ReviewError::Ir)?;
            if normalized.version() != IrVersion::V0_2 {
                return Err(ReviewError::Version);
            }
            Ok(Rejection {
                reason: "noncanonical-ir",
                location: Location::Byte {
                    offset,
                    length: usize::from(offset < raw.len()),
                },
            })
        }
        DocumentError::Ir(ContractError::Input(DeclarationError::Json(error)))
            if error.kind == JsonErrorKind::InvalidUtf8 =>
        {
            Ok(Rejection {
                reason: "invalid-utf8",
                location: Location::Byte {
                    offset: error.offset,
                    length: 1,
                },
            })
        }
        DocumentError::Ir(ContractError::Node(NodeError::Input(DeclarationError::Structure {
            kind: DeclarationErrorKind::UnknownMember,
            path,
        }))) => {
            let name = path
                .strip_prefix('/')
                .filter(|p| !p.contains('/'))
                .ok_or(invalid("normalize", "unknown member is not top-level"))?;
            let value = json::parse(raw, limits).map_err(ReviewError::Json)?;
            let semantics = named(&value, "semantics")?;
            if string(named(&value, "ir_version")?, "/ir_version")? != "0.2"
                || string(named(semantics, "name")?, "/semantics/name")?
                    != "keyed-finite-table-semantics"
                || string(named(semantics, "sha256")?, "/semantics/sha256")?
                    != V0_2_SEMANTICS_SHA256
            {
                return Err(ReviewError::Version);
            }
            Ok(Rejection {
                reason: "unknown-top-level-member",
                location: Location::Member(name.replace("~1", "/").replace("~0", "~")),
            })
        }
        error => Err(ReviewError::Ir(error)),
    }
}

fn proof(
    run: &Execution<'_>,
    subject: &Subject<'_>,
    artifacts: &Artifacts<'_, '_>,
    mut record_json: JsonLimits,
) -> Result<Verdict> {
    let (Some(document), Some(p2)) = (&subject.document, &subject.p2) else {
        return Err(invalid("prove", "requires legal subject"));
    };
    require_roles(
        &run.inputs,
        &["canonical-ir", "generator-source", "obligation-set"],
    )?;
    if run.inputs["canonical-ir"] != subject.artifact
        || artifacts.get(
            run.inputs["obligation-set"],
            Some(("axiom-obligation-set", "0.2")),
        )? != p2.canonical_bytes()
    {
        return Err(invalid("prove", "IR or P2 binding"));
    }
    let generator = run.inputs["generator-source"];
    artifacts.get(generator, Some(("generator-source", "0.1")))?;
    let generator =
        GeneratorIdentity::new(generator).map_err(|_| invalid("prove", "generator identity"))?;
    if matches!(run.attempt, Attempt::Interrupted { .. }) {
        return Ok(Verdict::Interrupted);
    }
    require_roles(&run.outputs, &["derivation"])?;
    let pin = run.outputs["derivation"];
    if run.mode == Mode::Effect {
        check_empty_effects(
            EffectProfile::CoreV0_1,
            artifacts.get(pin, Some((EFFECT_ARTIFACT, "0.1")))?,
            document,
            p2,
            run.target,
            &generator,
            EffectLimits {
                ir_json: run.limits.ir_json,
                max_steps: run.limits.max_steps,
                max_premise_edges: run.limits.max_premise_edges,
                max_path_bytes: run.limits.max_path_bytes,
                max_output_bytes: run.limits.max_output_bytes,
            },
        )
        .map_err(ReviewError::Effect)?;
    } else {
        let record = check_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            artifacts.get(pin, Some((ORIGIN_ARTIFACT, "0.1")))?,
            document,
            p2,
            run.target,
            &generator,
            run.limits,
        )
        .map_err(ReviewError::Origin)?;
        record_json.max_input_bytes = record_json.max_input_bytes.min(run.limits.max_output_bytes);
        check_origin_conditions(
            document,
            &strict(record.canonical_bytes(), record_json, "origin record")?,
        )?;
    }
    Ok(Verdict::Replayed)
}

fn check_origin_conditions(document: &CanonicalDocument, record: &Value) -> Result<()> {
    let graph = document.components().analysis().graph();
    if graph.nodes().iter().any(|node| {
        !matches!(
            node.kind(),
            NodeKind::Input | NodeKind::Filter | NodeKind::Map
        )
    }) {
        return Err(invalid("origin", "unsupported graph"));
    }
    let target = shape(
        named(record, "target")?,
        "/origin/target",
        &["interface", "name", "node", "record_type"],
    )?;
    let record_type = text(target, "record_type")?;
    let name = text(target, "name")?;
    let field = graph
        .types()
        .record_types()
        .iter()
        .find(|ty| ty.id() == record_type)
        .and_then(|ty| {
            ty.definition()
                .fields
                .iter()
                .find(|field| field.name == name)
        })
        .ok_or(invalid("origin", "field"))?;
    if field.label != Label::Public
        || matches!(
            field.value_type,
            ValueType::Option { .. } | ValueType::Record { .. }
        )
    {
        return Err(invalid("origin", "unsupported field"));
    }
    if !decode_array(named(record, "gaps")?, "/origin/gaps")?.is_empty() {
        return Err(invalid("origin", "gap"));
    }
    let roots = shape(
        named(record, "roots")?,
        "/origin/roots",
        &["control", "evaluation", "value"],
    )?;
    let steps = decode_array(named(record, "steps")?, "/origin/steps")?;
    for root in ["control", "value"] {
        let index = decimal(text(roots, root)?, "origin root")?;
        let step = steps.get(index).ok_or(invalid("origin", "root"))?;
        let labels = shape(
            named(step, "labels")?,
            "/origin/labels",
            &["declared", "inferred", "propagated", "type_summary"],
        )?;
        if text(labels, "propagated")? != "public"
            || (root == "value" && text(labels, "inferred")? != "public")
        {
            return Err(invalid("origin", "public value and control"));
        }
    }
    Ok(())
}

fn decode_array<'a>(value: &'a Value, path: &str) -> Result<&'a [Value]> {
    crate::declarations::array(value, path).map_err(ReviewError::Shape)
}

pub(super) fn check_result(
    id: &str,
    row: &super::Members,
    trust: &Entries<'_>,
    checked: &BTreeMap<&str, Verdict>,
    executions: &BTreeMap<&str, Execution<'_>>,
) -> Result<bool> {
    let definition = shape(
        member(row, "definition"),
        "/obligation/definition",
        &["expectation", "kind", "subject"],
    )?;
    let expected = text(definition, "expectation")?;
    let value = member(row, "result");
    let verify = |execution_id| {
        if !executions
            .get(execution_id)
            .is_some_and(|run| run.target == id)
        {
            return Err(invalid("result", "execution target"));
        }
        checked
            .get(execution_id)
            .ok_or(invalid("result", "execution"))
    };
    let assumptions = |result| {
        let mut previous = None;
        for id in strings(result, "assumptions")? {
            ordered(&mut previous, id, "assumptions")?;
            if !trust.contains_key(id) {
                return Err(invalid("result", "trust reference"));
            }
        }
        Ok(())
    };
    match (kind(value)?, expected) {
        ("checked", "check") => {
            let result = shape(
                value,
                "/result/checked",
                &["artifacts", "assumptions", "execution", "kind"],
            )?;
            assumptions(result)?;
            let Verdict::Checked(artifacts) = verify(text(result, "execution")?)? else {
                return Err(invalid("result", "checked support"));
            };
            if !strings(result, "artifacts")?
                .into_iter()
                .eq(artifacts.iter().map(String::as_str))
            {
                return Err(invalid("result", "checked artifacts"));
            }
        }
        ("failed", "check") => {
            let result = shape(
                value,
                "/result/failed",
                &["assumptions", "counterexample", "execution", "kind"],
            )?;
            assumptions(result)?;
            let Verdict::Rejected(witness) = verify(text(result, "execution")?)? else {
                return Err(invalid("result", "failed support"));
            };
            if encode(member(result, "counterexample")) != encode(witness) {
                return Err(invalid("result", "structure witness"));
            }
        }
        ("proved", "prove") => {
            let result = shape(value, "/result/proved", &["assumptions", "kind", "support"])?;
            assumptions(result)?;
            let support = shape(
                member(result, "support"),
                "/result/support",
                &["execution", "kind"],
            )?;
            if text(support, "kind")? != "kernel-replay"
                || !matches!(verify(text(support, "execution")?)?, Verdict::Replayed)
            {
                return Err(invalid("result", "proof support"));
            }
        }
        ("unknown", "prove" | "check") => {
            let result = shape(value, "/result/unknown", &["attempts", "kind", "reason"])?;
            let ids = strings(result, "attempts")?;
            if ids.is_empty() {
                return Err(invalid("result", "missing attempt"));
            }
            let mut previous = None;
            for execution in ids {
                ordered(&mut previous, execution, "attempt references")?;
                if !matches!(verify(execution)?, Verdict::Interrupted)
                    || !matches!(executions[execution].attempt, Attempt::Interrupted { reason, .. } if reason == text(result, "reason")?)
                {
                    return Err(invalid("result", "attempt reason"));
                }
            }
            return Ok(true);
        }
        ("trusted", "trust") => {
            let result = shape(value, "/result/trusted", &["kind", "trust"])?;
            let subject = shape(
                member(definition, "subject"),
                "/obligation/subject",
                &["category", "kind", "scope"],
            )?;
            let pin = text(result, "trust")?;
            if text(subject, "scope")? != pin || !trust.contains_key(pin) {
                return Err(invalid("result", "trusted binding"));
            }
        }
        _ => return Err(invalid("result", "state and expectation")),
    }
    Ok(false)
}
