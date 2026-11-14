//! Candidate structured facts. Serialization does not authenticate an execution.
use super::*;
use crate::{
    replay::{ReplayError, ReplayResource},
    solver::{SolverError, SolverRequest, SolverResource, SolverStage},
};

/// Exact input identities supplied by the producing call site. Diagnostic text
/// is never inspected or generated here; an optional attachment is only a digest.
#[derive(Clone, Copy)]
pub struct InterruptionBinding<'a> {
    pub request: &'a SolverRequest,
    pub solve_execution: &'a str,
    pub generator: &'a str,
    pub diagnostic: Option<&'a str>,
}

/// Two canonical artifacts for a newly observed, supported component error.
/// Callers must retain both artifacts and bind the interruption through replay
/// provenance and the externally pinned batch. This is not a Debug converter.
pub struct ReplayInterruptionV02 {
    bytes: Vec<u8>,
    policy: Vec<u8>,
    code: &'static str,
}

impl ReplayInterruptionV02 {
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn component_policy_bytes(&self) -> &[u8] {
        &self.policy
    }
    pub fn code(&self) -> &'static str {
        self.code
    }

    /// The error must be from decode_model_world for this request and response.
    /// Local readback repeats that call before accepting the facts.
    pub fn from_model_error(
        binding: InterruptionBinding<'_>,
        response_artifact: &str,
        error: &SolverError,
    ) -> Result<Self> {
        let policy = model_policy(binding.request.budgets().base);
        let (code, cause) = model_cause(error, response_artifact, &policy)?;
        Self::build(binding, "model", code, cause, policy)
    }

    /// The error must be from replay_target with these exact production limits.
    /// Ambiguous input errors and internal failures have no supported mapping.
    pub fn from_replay_error(
        binding: InterruptionBinding<'_>,
        world_artifact: &str,
        limits: ReplayLimits,
        error: &ReplayError,
    ) -> Result<Self> {
        let policy = replay_policy(limits);
        let (code, cause) = replay_cause(error, world_artifact, &policy)?;
        Self::build(binding, "replay", code, cause, policy)
    }

    fn build(
        binding: InterruptionBinding<'_>,
        stage: &str,
        code: &'static str,
        cause: Value,
        policy: Policy,
    ) -> Result<Self> {
        if !digest(binding.solve_execution)
            || !digest(binding.generator)
            || binding.diagnostic.is_some_and(|pin| !digest(pin))
        {
            return Err(invalid("structured interruption", "binding digest"));
        }
        let policy = encode(&value_object([
            ("format", value_string("axiom-evidence-component-policy")),
            ("version", value_string("0.1")),
            ("stage", value_string(stage)),
            (
                "limits",
                Value::Array(
                    policy
                        .into_iter()
                        .map(|(name, (unit, value))| {
                            value_object([
                                ("name", value_string(name)),
                                ("unit", value_string(unit)),
                                ("value", value_string(&value.to_string())),
                            ])
                        })
                        .collect(),
                ),
            ),
        ]));
        let diagnostic = match binding.diagnostic {
            None => value_object([("kind", value_string("absent"))]),
            Some(pin) => value_object([
                ("kind", value_string("artifact")),
                ("ref", value_string(pin)),
            ]),
        };
        let bytes = encode(&value_object([
            ("format", value_string("axiom-evidence-replay-interruption")),
            ("version", value_string("0.2")),
            ("scope", value_string("simulation")),
            ("generator", value_string(binding.generator)),
            ("request", value_string(binding.request.artifact_digest())),
            ("solve_execution", value_string(binding.solve_execution)),
            ("component_policy", value_string(&raw_digest(&policy))),
            ("stage", value_string(stage)),
            ("code", value_string(code)),
            ("cause", cause),
            ("diagnostic", diagnostic),
        ]));
        Ok(Self {
            bytes,
            policy,
            code,
        })
    }
}

type Policy = BTreeMap<&'static str, (&'static str, usize)>;

fn model_policy(l: crate::solver::SolverLimits) -> Policy {
    BTreeMap::from([
        ("candidate-bytes", ("byte", l.candidate_bytes)),
        ("decode-steps", ("step", l.decode_steps)),
        ("integer-digits", ("digit", l.integer_digits)),
        ("text-bytes", ("byte", l.text_bytes)),
        ("value-cells", ("cell", l.value_cells)),
        ("world-bytes", ("byte", l.world_bytes)),
    ])
}

fn replay_policy(l: ReplayLimits) -> Policy {
    BTreeMap::from([
        ("comparisons", ("comparison", l.comparisons)),
        ("digit-work", ("digit", l.digit_work)),
        ("evaluation-steps", ("step", l.evaluation_steps)),
        ("integer-digits", ("digit", l.integer_digits)),
        ("output-bytes", ("byte", l.output_bytes)),
        ("path-bytes", ("byte", l.path_bytes)),
        ("rows", ("row", l.rows)),
        ("text-bytes", ("byte", l.text_bytes)),
        ("type-items", ("item", l.type_items)),
        ("value-cells", ("cell", l.value_cells)),
        ("world-bytes", ("byte", l.world_bytes)),
        ("world-depth", ("level", l.world_depth)),
        ("world-nodes", ("node", l.world_nodes)),
    ])
}

fn resource_cause(name: &str, policy: &Policy) -> Value {
    value_object([
        ("kind", value_string("resource-limit")),
        ("resource", value_string(name)),
        ("limit", value_string(&policy[name].1.to_string())),
    ])
}

fn input_cause(artifact: &str, reason: &str) -> Result<Value> {
    if !digest(artifact) {
        return Err(invalid("structured interruption", "input digest"));
    }
    Ok(value_object([
        ("kind", value_string("input-error")),
        ("artifact", value_string(artifact)),
        ("reason", value_string(reason)),
    ]))
}

fn model_cause(
    error: &SolverError,
    response: &str,
    policy: &Policy,
) -> Result<(&'static str, Value)> {
    use SolverResource as R;
    let cause = match error {
        SolverError::ResourceLimit {
            stage: SolverStage::Decode,
            resource,
        } => {
            let name = match resource {
                R::CandidateBytes => "candidate-bytes",
                R::DecodeSteps => "decode-steps",
                R::IntegerDigits => "integer-digits",
                R::TextBytes => "text-bytes",
                R::ValueCells => "value-cells",
                R::WorldBytes => "world-bytes",
                _ => return Err(ReviewError::UnsupportedModelInterruption(error.clone())),
            };
            return Ok(("component-limit", resource_cause(name, policy)));
        }
        SolverError::BindingMismatch => input_cause(response, "binding-mismatch")?,
        SolverError::InvalidInput { .. } | SolverError::LiteralClassConflict => {
            input_cause(response, "invalid-model")?
        }
        _ => return Err(ReviewError::UnsupportedModelInterruption(error.clone())),
    };
    Ok(("model-decode", cause))
}

fn replay_cause(
    error: &ReplayError,
    world: &str,
    policy: &Policy,
) -> Result<(&'static str, Value)> {
    use ReplayResource as R;
    let feature = match error {
        ReplayError::ResourceLimit { resource, .. } => {
            let name = match resource {
                R::Comparisons => "comparisons",
                R::DigitWork => "digit-work",
                R::EvaluationSteps => "evaluation-steps",
                R::IntegerDigits => "integer-digits",
                R::OutputBytes => "output-bytes",
                R::PathBytes => "path-bytes",
                R::Rows => "rows",
                R::TextBytes => "text-bytes",
                R::TypeItems => "type-items",
                R::ValueCells => "value-cells",
                R::WorldBytes => "world-bytes",
                R::WorldDepth => "world-depth",
                R::WorldNodes => "world-nodes",
            };
            return Ok(("component-limit", resource_cause(name, policy)));
        }
        ReplayError::WorldFormat { .. } => {
            return Ok(("replay-error", input_cause(world, "invalid-world")?));
        }
        ReplayError::NonCanonicalWorld { .. } => {
            return Ok(("replay-error", input_cause(world, "noncanonical-world")?));
        }
        ReplayError::UnsupportedProfile => "profile",
        ReplayError::UnsupportedIrVersion(_) => "ir-version",
        ReplayError::UnsupportedKind(_) => "obligation-kind",
        ReplayError::UnsupportedFeature { .. } => "semantic-feature",
        // BindingMismatch and Json do not identify the blamed input. Nested
        // model errors and Internal also lack a supported stage/source fact.
        _ => return Err(ReviewError::UnsupportedReplayInterruption(error.clone())),
    };
    Ok((
        "unsupported",
        value_object([
            ("kind", value_string("unsupported")),
            ("feature", value_string(feature)),
        ]),
    ))
}

/// Validates the attachment's identity and descriptor without interpreting text.
pub(super) fn diagnostic<'a>(
    row: &'a Members,
    artifacts: &Artifacts<'_, '_>,
) -> Result<Option<&'a str>> {
    let value = member(row, "diagnostic");
    match kind(value)? {
        "absent" => {
            shape(value, "interruption diagnostic", &["kind"])?;
            Ok(None)
        }
        "artifact" => {
            let row = shape(value, "interruption diagnostic", &["kind", "ref"])?;
            let pin = text(row, "ref")?;
            artifacts.get(pin, Some(("component-diagnostic-text", "0.1")))?;
            Ok(Some(pin))
        }
        _ => Err(invalid("interruption diagnostic", "kind")),
    }
}

pub(super) fn members(value: &Value) -> Result<&Members> {
    shape(
        value,
        "structured interruption",
        &[
            "format",
            "version",
            "scope",
            "generator",
            "request",
            "solve_execution",
            "component_policy",
            "stage",
            "code",
            "cause",
            "diagnostic",
        ],
    )
}

pub(super) fn check(
    value: &Value,
    row: &Members,
    expected: &ReplayInterruptionV02,
    artifacts: &Artifacts<'_, '_>,
) -> Result<()> {
    if artifacts.get(
        text(row, "component_policy")?,
        Some(("axiom-evidence-component-policy", "0.1")),
    )? != expected.component_policy_bytes()
    {
        return Err(invalid("structured interruption", "production policy"));
    }
    if encode(value) != expected.canonical_bytes() {
        return Err(invalid("structured interruption", "facts or binding"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::super::tests::fixtures::{replay_limits, solver_limits};
    use super::*;
    use crate::{obligations::ObligationKind, replay::ReplayStage};

    #[test]
    fn registered_resources_have_exact_names_units_and_bound_values() {
        let model = model_policy(solver_limits().base);
        for (resource, name, unit, value) in [
            (
                SolverResource::CandidateBytes,
                "candidate-bytes",
                "byte",
                5_000_000,
            ),
            (
                SolverResource::DecodeSteps,
                "decode-steps",
                "step",
                1_000_000,
            ),
            (
                SolverResource::IntegerDigits,
                "integer-digits",
                "digit",
                1000,
            ),
            (SolverResource::TextBytes, "text-bytes", "byte", 2_000_000),
            (
                SolverResource::ValueCells,
                "value-cells",
                "cell",
                10_000_000,
            ),
            (SolverResource::WorldBytes, "world-bytes", "byte", 4_000_000),
        ] {
            assert_eq!(model[name], (unit, value));
            let (code, cause) = model_cause(
                &SolverError::ResourceLimit {
                    stage: SolverStage::Decode,
                    resource,
                },
                "",
                &model,
            )
            .unwrap();
            assert_eq!(code, "component-limit");
            assert_eq!(
                encode(&cause),
                format!(r#"{{"kind":"resource-limit","limit":"{value}","resource":"{name}"}}"#)
                    .as_bytes()
            );
            for stage in [SolverStage::Request, SolverStage::Response] {
                assert!(matches!(
                    model_cause(&SolverError::ResourceLimit { stage, resource }, "", &model),
                    Err(ReviewError::UnsupportedModelInterruption(_))
                ));
            }
        }
        let replay = replay_policy(replay_limits());
        for (resource, name, unit, value) in [
            (
                ReplayResource::Comparisons,
                "comparisons",
                "comparison",
                10_000_000,
            ),
            (
                ReplayResource::DigitWork,
                "digit-work",
                "digit",
                100_000_000,
            ),
            (
                ReplayResource::EvaluationSteps,
                "evaluation-steps",
                "step",
                10_000_000,
            ),
            (
                ReplayResource::IntegerDigits,
                "integer-digits",
                "digit",
                1000,
            ),
            (
                ReplayResource::OutputBytes,
                "output-bytes",
                "byte",
                16_000_000,
            ),
            (ReplayResource::PathBytes, "path-bytes", "byte", 16_000_000),
            (ReplayResource::Rows, "rows", "row", 100_000),
            (ReplayResource::TextBytes, "text-bytes", "byte", 16_000_000),
            (ReplayResource::TypeItems, "type-items", "item", 2_000_000),
            (
                ReplayResource::ValueCells,
                "value-cells",
                "cell",
                100_000_000,
            ),
            (
                ReplayResource::WorldBytes,
                "world-bytes",
                "byte",
                16_000_000,
            ),
            (ReplayResource::WorldDepth, "world-depth", "level", 30_000),
            (ReplayResource::WorldNodes, "world-nodes", "node", 2_000_000),
        ] {
            assert_eq!(replay[name], (unit, value));
            let (code, cause) = replay_cause(
                &ReplayError::ResourceLimit {
                    stage: ReplayStage::Evaluation,
                    resource,
                },
                "",
                &replay,
            )
            .unwrap();
            assert_eq!(code, "component-limit");
            assert_eq!(
                encode(&cause),
                format!(r#"{{"kind":"resource-limit","limit":"{value}","resource":"{name}"}}"#)
                    .as_bytes()
            );
        }
    }

    #[test]
    fn supported_error_categories_do_not_depend_on_debug_text() {
        let model = model_policy(solver_limits().base);
        let replay = replay_policy(replay_limits());
        let pin = raw_digest(b"synthetic input");
        for (error, reason) in [
            (SolverError::BindingMismatch, "binding-mismatch"),
            (SolverError::LiteralClassConflict, "invalid-model"),
            (
                SolverError::InvalidInput {
                    interface: "synthetic".into(),
                    slot: 0,
                    path: vec![],
                    reason: "arbitrary diagnostic A",
                },
                "invalid-model",
            ),
            (
                SolverError::InvalidInput {
                    interface: "different".into(),
                    slot: 1,
                    path: vec!["x".into()],
                    reason: "arbitrary diagnostic B",
                },
                "invalid-model",
            ),
        ] {
            let (code, cause) = model_cause(&error, &pin, &model).unwrap();
            assert_eq!(code, "model-decode");
            assert_eq!(
                encode(&cause),
                format!(r#"{{"artifact":"{pin}","kind":"input-error","reason":"{reason}"}}"#)
                    .as_bytes()
            );
        }
        for (error, reason) in [
            (
                ReplayError::WorldFormat {
                    offset: 10,
                    reason: "synthetic",
                },
                "invalid-world",
            ),
            (
                ReplayError::NonCanonicalWorld { offset: 12 },
                "noncanonical-world",
            ),
        ] {
            let (code, cause) = replay_cause(&error, &pin, &replay).unwrap();
            assert_eq!(code, "replay-error");
            assert_eq!(
                encode(&cause),
                format!(r#"{{"artifact":"{pin}","kind":"input-error","reason":"{reason}"}}"#)
                    .as_bytes()
            );
        }
        for (error, feature) in [
            (ReplayError::UnsupportedProfile, "profile"),
            (
                ReplayError::UnsupportedIrVersion(IrVersion::V0_1),
                "ir-version",
            ),
            (
                ReplayError::UnsupportedKind(ObligationKind::IrStructure),
                "obligation-kind",
            ),
            (
                ReplayError::UnsupportedFeature {
                    anchor: "synthetic".into(),
                    feature: "unregistered detail".into(),
                },
                "semantic-feature",
            ),
        ] {
            let (code, cause) = replay_cause(&error, &pin, &replay).unwrap();
            assert_eq!(code, "unsupported");
            assert_eq!(
                encode(&cause),
                format!(r#"{{"feature":"{feature}","kind":"unsupported"}}"#).as_bytes()
            );
        }
    }

    #[test]
    fn unmapped_errors_preserve_the_original_cause_without_a_component_error_fallback() {
        let model = model_policy(solver_limits().base);
        for error in [
            SolverError::ResourceLimit {
                stage: SolverStage::Decode,
                resource: SolverResource::InputSlots,
            },
            SolverError::Internal("synthetic internal failure"),
            SolverError::UnsupportedProfile,
        ] {
            assert!(
                matches!(model_cause(&error, "", &model), Err(ReviewError::UnsupportedModelInterruption(actual)) if actual == error)
            );
        }
        let replay = replay_policy(replay_limits());
        for error in [
            ReplayError::BindingMismatch,
            ReplayError::Model(SolverError::LiteralClassConflict),
            ReplayError::Internal("synthetic internal failure"),
            ReplayError::UnknownObligation("synthetic".into()),
            ReplayError::NonCanonicalObservation { offset: 0 },
        ] {
            assert!(
                matches!(replay_cause(&error, "", &replay), Err(ReviewError::UnsupportedReplayInterruption(actual)) if actual == error)
            );
        }
    }
}
