use super::*;
use crate::{
    query::GeneratorIdentity,
    replay::{
        ReplayError, ReplayInput, ReplayOutcome, ReplayProfile, ReplayWorldInput, replay_target,
    },
    solver::{SolverError, decode_model_world},
};

pub(super) fn rebuild(
    run: &Execution<'_>,
    entry: &source::Entry,
    solved: &solve::Solved,
    materials: Materials<'_, '_, '_>,
    context: BackendReviewContext<'_>,
    assumptions: Vec<String>,
) -> Result<Value> {
    let Materials {
        subject,
        artifacts,
        limits: review_limits,
    } = materials;
    let limits = limits::replay(run, context.replay_limits)?;
    let source_value = record(
        artifacts,
        run.provenance,
        "axiom-evidence-backend-replay-source",
        review_limits.evidence_json,
    )?;
    let source = shape(
        &source_value,
        "replay source",
        &[
            "format",
            "version",
            "scope",
            "invocation",
            "observation",
            "solve_execution",
            "terminal",
        ],
    )?;
    format(source, "axiom-evidence-backend-replay-source")?;
    if text(source, "scope")? != "simulation"
        || text(source, "invocation")? != entry.invocation
        || Some(text(source, "solve_execution")?) != entry.upstream.as_deref()
    {
        return Err(invalid("backend source", "replay binding"));
    }
    let request = &solved.request;
    let response = solved
        .response
        .as_ref()
        .ok_or(invalid("backend replay", "missing solve response"))?;
    let model = response
        .sat_model()
        .ok_or(invalid("backend replay", "missing sat model"))?;
    let document = subject
        .document
        .as_ref()
        .ok_or(invalid("backend replay", "missing IR"))?;
    let p2 = subject
        .p2
        .as_ref()
        .ok_or(invalid("backend replay", "missing P2"))?;
    if run.inputs.get("canonical-ir").copied() != Some(subject.artifact)
        || run.inputs.get("obligation-set").copied() != Some(p2.artifact_digest())
        || run.inputs.get("request").copied() != Some(request.artifact_digest())
        || run.inputs.get("response").copied() != Some(response.artifact_digest())
    {
        return Err(invalid("backend replay", "input binding"));
    }
    artifacts.get(subject.artifact, Some(("axiom-ir", "0.2")))?;
    artifacts.get(p2.artifact_digest(), Some(("axiom-obligation-set", "0.2")))?;
    let observation_pin = text(source, "observation")?;
    let decoded = match decode_model_world(request, model) {
        Ok(candidate) => candidate,
        Err(error) => {
            solve::roles(
                &run.inputs,
                &["canonical-ir", "obligation-set", "request", "response"],
            )?;
            let code = if matches!(error, SolverError::ResourceLimit { .. }) {
                "component-limit"
            } else {
                "model-decode"
            };
            return interrupted(
                run,
                entry,
                source,
                materials,
                observation_pin,
                Interruption {
                    stage: "model",
                    code,
                    detail: format!("{error:?}"),
                },
            );
        }
    };
    solve::roles(
        &run.inputs,
        &[
            "canonical-ir",
            "model-world-candidate",
            "obligation-set",
            "request",
            "response",
            "world",
        ],
    )?;
    if artifacts.get(
        run.inputs["model-world-candidate"],
        Some(("axiom-p4-model-world-candidate", "0.1")),
    )? != decoded.canonical_bytes()
        || artifacts.get(run.inputs["world"], Some(("axiom-p4-world", "0.1")))?
            != decoded.world_bytes()
    {
        return Err(invalid("backend replay", "candidate or world rebuild"));
    }
    let completed = matches!(run.attempt, Attempt::Completed);
    let observation = record(
        artifacts,
        observation_pin,
        if completed {
            "axiom-p4-target-replay-observation"
        } else {
            "axiom-evidence-replay-interruption"
        },
        review_limits.evidence_json,
    )?;
    let generator_pin = if completed {
        string(
            named(named(&observation, "binding")?, "generator")?,
            "replay generator",
        )?
    } else {
        string(named(&observation, "generator")?, "replay generator")?
    };
    artifacts.get(generator_pin, Some(("generator-source", "0.1")))?;
    let generator = GeneratorIdentity::new(generator_pin).map_err(ReviewError::Query)?;
    let rebuilt = match replay_target(
        ReplayProfile::MapFilterV0_1,
        ReplayInput {
            document,
            obligations: p2,
            obligation_id: run.target,
            generator: &generator,
            world: ReplayWorldInput::ModelCandidate {
                request,
                model,
                candidate: &decoded,
            },
        },
        limits,
    ) {
        Ok(rebuilt) => rebuilt,
        Err(error) => {
            let code = match error {
                ReplayError::ResourceLimit { .. } => "component-limit",
                ReplayError::UnsupportedProfile
                | ReplayError::UnsupportedIrVersion(_)
                | ReplayError::UnsupportedKind(_)
                | ReplayError::UnsupportedFeature { .. } => "unsupported",
                _ => "replay-error",
            };
            return interrupted(
                run,
                entry,
                source,
                materials,
                observation_pin,
                Interruption {
                    stage: "replay",
                    code,
                    detail: format!("{error:?}"),
                },
            );
        }
    };
    execution_terminal(run, None)?;
    solve::roles(&run.outputs, &["target-replay"])?;
    if run.outputs["target-replay"] != observation_pin
        || encode(&observation) != rebuilt.canonical_bytes()
    {
        return Err(invalid("backend replay", "observation rebuild"));
    }
    let outcome = match rebuilt.outcome() {
        ReplayOutcome::InputRejected => "input-rejected",
        ReplayOutcome::PreRejected => "pre-rejected",
        ReplayOutcome::TargetNotViolated => "target-not-violated",
        ReplayOutcome::TargetViolated => "target-violated",
    };
    if encode(member(source, "terminal"))
        != encode(&value_object([
            ("kind", value_string("completed")),
            ("outcome", value_string(outcome)),
        ]))
    {
        return Err(invalid("backend replay", "terminal"));
    }
    if rebuilt.outcome() != ReplayOutcome::TargetViolated {
        return Ok(unknown(&entry.execution, "indeterminate"));
    }
    let ir = strict(
        document.canonical_bytes(),
        review_limits.evidence_json,
        "IR",
    )?;
    let contracts =
        decode::array(named(&ir, "contracts")?, "contracts").map_err(ReviewError::Shape)?;
    let mut assumes = Vec::new();
    for contract in contracts {
        if string(named(named(contract, "definition")?, "role")?, "role")? == "assume" {
            assumes.push(string(named(contract, "id")?, "contract id")?.to_owned());
        }
    }
    let counterexample = value_object([
        ("kind", value_string("target-replay")),
        (
            "minimality",
            value_object([("kind", value_string("unreduced"))]),
        ),
        (
            "observed",
            strict(
                &encode(named(named(&observation, "result")?, "witness")?),
                review_limits.evidence_json,
                "witness",
            )?,
        ),
        ("preconditions", strings_value(assumes)),
        (
            "worlds",
            Value::Array(vec![strict(
                decoded.world_bytes(),
                review_limits.evidence_json,
                "world",
            )?]),
        ),
        (
            "trace",
            Value::Array(vec![
                value_object([
                    ("kind", value_string("obligation")),
                    ("ref", value_string(run.target)),
                ]),
                value_object([
                    ("kind", value_string("replay-observation")),
                    ("artifact", value_string(observation_pin)),
                ]),
            ]),
        ),
    ]);
    Ok(value_object([
        ("kind", value_string("failed")),
        ("execution", value_string(&entry.execution)),
        ("assumptions", strings_value(assumptions)),
        ("counterexample", counterexample),
    ]))
}

struct Interruption {
    stage: &'static str,
    code: &'static str,
    detail: String,
}

fn interrupted(
    run: &Execution<'_>,
    entry: &source::Entry,
    source: &Members,
    materials: Materials<'_, '_, '_>,
    pin: &str,
    interruption: Interruption,
) -> Result<Value> {
    let Materials {
        artifacts, limits, ..
    } = materials;
    let Interruption {
        stage,
        code,
        detail,
    } = interruption;
    execution_terminal(run, Some(code))?;
    solve::roles(&run.outputs, &[])?;
    let value = record(
        artifacts,
        pin,
        "axiom-evidence-replay-interruption",
        limits.evidence_json,
    )?;
    let diagnostic = shape(
        &value,
        "replay interruption",
        &[
            "format",
            "version",
            "scope",
            "request",
            "solve_execution",
            "generator",
            "stage",
            "code",
            "detail",
        ],
    )?;
    format(diagnostic, "axiom-evidence-replay-interruption")?;
    artifacts.get(
        text(diagnostic, "generator")?,
        Some(("generator-source", "0.1")),
    )?;
    if text(diagnostic, "scope")? != "simulation"
        || text(diagnostic, "request")? != entry.request
        || Some(text(diagnostic, "solve_execution")?) != entry.upstream.as_deref()
        || text(diagnostic, "stage")? != stage
        || text(diagnostic, "code")? != code
        || text(diagnostic, "detail")? != detail
        || encode(member(source, "terminal"))
            != encode(&value_object([
                ("kind", value_string("interrupted")),
                ("code", value_string(code)),
            ]))
    {
        return Err(invalid("backend replay", "interruption rebuild"));
    }
    Ok(unknown(
        &entry.execution,
        interrupted_reason(Mode::Replay, code)?,
    ))
}
