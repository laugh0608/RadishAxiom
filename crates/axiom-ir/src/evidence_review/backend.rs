//! Candidate-only backend binding. No process, filesystem, or qualification entry.
mod limits;
mod replay;
mod solve;
mod source;
#[cfg(test)]
mod tests;

use super::*;
use crate::{replay::ReplayLimits, solver::SolverBudgets};
use execution::{Attempt, Mode};

pub(super) const SOLVE_RULE: (&str, &[u8]) = (
    "sha256:f34d5a57434d9783ebff7aba0153c47c14c93a9317bb083409445be5dbf5cf9b",
    include_bytes!("../../../../docs/query/p4-request-response-model-v0.2.md"),
);
pub(super) const REPLAY_RULE: (&str, &[u8]) = (
    "sha256:238568bf79bdced0a15996ba51d05defcaf1ef943a14cb07b5f9fb6f3c76cff6",
    include_bytes!("../../../../docs/query/p4-concrete-target-replay-v0.1.md"),
);
const CONTRACT: &[u8] =
    include_bytes!("../../../../docs/evidence/evidence-v0.2-machine-contract/backend.json");
const HOST_CLAIM: &str = "The scoped runtime and capture report the execution faithfully.";
const GENERATOR_CLAIM: &str = "Every valid violating world has a satisfying query assignment.";
const BACKEND_CLAIM: &str = "The scoped backend is sound for the bound unsat query.";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProofPolicy {
    AttestationAllowed,
    CertificateRequired,
}
impl ProofPolicy {
    fn read(value: &str) -> Result<Self> {
        match value {
            "attestation-allowed" => Ok(Self::AttestationAllowed),
            "certificate-required" => Ok(Self::CertificateRequired),
            _ => Err(invalid("backend policy", "unknown policy")),
        }
    }
}

/// The expected pin must come from the caller's separate capture authority.
/// These inputs are not read from the Evidence document. This first candidate
/// accepts only simulation batches; qualified/native scopes are always refused.
#[derive(Clone, Copy)]
pub struct BackendReviewContext<'a> {
    pub batch: &'a [u8],
    pub expected_batch_digest: &'a str,
    pub consumer_policy: ProofPolicy,
    pub allowed_trust_categories: &'a [&'a str],
    pub solver_limits: SolverBudgets,
    pub replay_limits: ReplayLimits,
}

#[derive(Debug, Eq, PartialEq)]
pub enum BackendPolicyStatus {
    TrustAllowed,
    Incomplete,
}

#[derive(Debug, Eq, PartialEq)]
pub struct BackendReadback {
    pub scope: &'static str,
    pub batch_digest: String,
    pub contract_digest: String,
    pub policy: BackendPolicyStatus,
    pub remaining_trust: Vec<String>,
}

pub(super) struct Support {
    pub results: BTreeMap<String, Value>,
    pub readback: BackendReadback,
}

#[derive(Clone, Copy)]
struct Materials<'a, 'document, 'blob> {
    subject: &'a Subject<'document>,
    artifacts: &'a Artifacts<'document, 'blob>,
    limits: ReviewLimits,
}

pub(super) fn target_kind(kind: &str) -> bool {
    matches!(
        kind,
        "numeric-range" | "totality" | "key-cardinality" | "row-coverage" | "contract-guarantee"
    )
}

pub(super) fn interrupted_reason(mode: Mode, code: &str) -> Result<&'static str> {
    match (mode, code) {
        (Mode::Solve, "deadline") => Ok("timeout"),
        (Mode::Solve, "memory" | "stdout-limit" | "stderr-limit" | "component-limit")
        | (Mode::Replay, "component-limit") => Ok("resource-exhausted"),
        (Mode::Solve, "tool-unavailable") => Ok("backend-unavailable"),
        (Mode::Solve, "cleanup" | "exit" | "protocol" | "streams-incomplete")
        | (Mode::Replay, "model-decode" | "replay-error") => Ok("operational-error"),
        (Mode::Replay, "unsupported") => Ok("unsupported"),
        _ => Err(invalid("backend", "interruption code")),
    }
}

pub(super) fn rebuild(
    context: Option<BackendReviewContext<'_>>,
    subject: &Subject<'_>,
    artifacts: &Artifacts<'_, '_>,
    tools: &BTreeMap<&str, Tool<'_>>,
    executions: &BTreeMap<&str, Execution<'_>>,
    trust: &Entries<'_>,
    review_limits: ReviewLimits,
) -> Result<Option<Support>> {
    if !executions.values().any(|run| run.mode.is_backend()) {
        if context.is_some() {
            return Err(invalid("backend", "batch without backend executions"));
        }
        return Ok(None);
    }
    let context = context.ok_or(invalid("backend", "separate source authority required"))?;
    let batch = source::Batch::read(context, subject, executions, review_limits)?;
    let materials = Materials {
        subject,
        artifacts,
        limits: review_limits,
    };
    let mut previous = None;
    for &category in context.allowed_trust_categories {
        ordered(&mut previous, category, "allowed trust")?;
        if !matches!(
            category,
            "specification-intent"
                | "sensitivity-classification"
                | "input-origin"
                | "decoder-normalizer"
                | "proof-backend"
                | "production-generator"
                | "host-runtime"
                | "cryptographic-primitive"
        ) {
            return Err(invalid("backend policy", "unknown trust category"));
        }
    }
    let mut chains: BTreeMap<&str, Vec<(usize, Value)>> = BTreeMap::new();
    let mut has_attestation = false;
    for (index, entry) in batch.entries.iter().enumerate() {
        let run = &executions[entry.execution.as_str()];
        artifacts.get(tools[run.tool].artifact, Some(("tool-executable", "0.1")))?;
        let host = require_trust(
            trust,
            "host-runtime",
            "execution",
            &entry.execution,
            HOST_CLAIM,
        )?;
        if run.mode == Mode::Replay {
            continue;
        }
        let solved = solve::rebuild(run, entry, &batch, materials, tools, context)?;
        let result = if let Some(response) = &solved.response {
            match response.status() {
                crate::solver::SolverStatus::Unsat
                    if batch.policy == ProofPolicy::AttestationAllowed =>
                {
                    has_attestation = true;
                    let generator = require_trust(
                        trust,
                        "production-generator",
                        "execution",
                        &entry.execution,
                        GENERATOR_CLAIM,
                    )?;
                    let backend =
                        require_trust(trust, "proof-backend", "tool", run.tool, BACKEND_CLAIM)?;
                    value_object([
                        ("kind", value_string("proved")),
                        (
                            "assumptions",
                            strings_value([host, generator, backend.clone()]),
                        ),
                        (
                            "support",
                            value_object([
                                ("kind", value_string("backend-attestation")),
                                ("execution", value_string(&entry.execution)),
                                ("query", value_string(run.inputs["query"])),
                                ("response", value_string(run.outputs["response"])),
                                ("trust", value_string(&backend)),
                            ]),
                        ),
                    ])
                }
                crate::solver::SolverStatus::Sat => {
                    let child = batch
                        .entries
                        .get(index + 1)
                        .filter(|child| child.upstream.as_deref() == Some(&entry.execution))
                        .ok_or(invalid("backend", "sat missing replay terminal"))?;
                    let replay_run = &executions[child.execution.as_str()];
                    let replay_host = require_trust(
                        trust,
                        "host-runtime",
                        "execution",
                        &child.execution,
                        HOST_CLAIM,
                    )?;
                    replay::rebuild(
                        replay_run,
                        child,
                        &solved,
                        materials,
                        context,
                        vec![host, replay_host],
                    )?
                }
                crate::solver::SolverStatus::Unsat => {
                    unknown(&entry.execution, "incomplete-certificate")
                }
                crate::solver::SolverStatus::Unknown => unknown(&entry.execution, "indeterminate"),
            }
        } else {
            unknown(
                &entry.execution,
                solved
                    .reason
                    .ok_or(invalid("backend", "missing terminal"))?,
            )
        };
        if solved
            .response
            .as_ref()
            .is_none_or(|r| r.status() != crate::solver::SolverStatus::Sat)
            && batch
                .entries
                .get(index + 1)
                .is_some_and(|child| child.upstream.as_deref() == Some(&entry.execution))
        {
            return Err(invalid("backend", "replay of non-sat solve"));
        }
        chains
            .entry(run.target)
            .or_default()
            .push((run.ordinal, result));
    }
    let mut results = BTreeMap::new();
    for (target, mut attempts) in chains {
        attempts.sort_by_key(|(ordinal, _)| *ordinal);
        let completed: Vec<_> = attempts
            .iter()
            .enumerate()
            .filter_map(|(i, (_, v))| kind(v).is_ok_and(|k| k != "unknown").then_some(i))
            .collect();
        let selected = if let Some(&last) = completed.last() {
            if completed
                .iter()
                .any(|&i| kind(&attempts[i].1).ok() != kind(&attempts[last].1).ok())
            {
                return Err(invalid("backend", "conflicting completed supports"));
            }
            attempts.swap_remove(last).1
        } else {
            let (_, last) = attempts
                .last()
                .ok_or(invalid("backend", "empty attempts"))?;
            let reason = string(named(last, "reason")?, "reason")?;
            let mut refs = BTreeSet::new();
            for (_, attempt) in &attempts {
                if string(named(attempt, "reason")?, "reason")? == reason {
                    let attempt = shape(attempt, "unknown", &["kind", "attempts", "reason"])?;
                    refs.extend(strings(attempt, "attempts")?.into_iter().map(str::to_owned));
                }
            }
            value_object([
                ("kind", value_string("unknown")),
                ("reason", value_string(reason)),
                ("attempts", strings_value(refs)),
            ])
        };
        results.insert(target.to_owned(), selected);
    }
    let mut policy =
        if has_attestation && context.consumer_policy == ProofPolicy::CertificateRequired {
            BackendPolicyStatus::Incomplete
        } else {
            BackendPolicyStatus::TrustAllowed
        };
    for row in trust.values() {
        let category = string(named(member(row, "definition"), "category")?, "category")?;
        if !context.allowed_trust_categories.contains(&category) {
            policy = BackendPolicyStatus::Incomplete;
        }
    }
    Ok(Some(Support {
        results,
        readback: BackendReadback {
            scope: "simulation",
            batch_digest: raw_digest(context.batch),
            contract_digest: raw_digest(CONTRACT),
            policy,
            remaining_trust: trust.keys().map(|id| (*id).to_owned()).collect(),
        },
    }))
}

fn require_trust(
    trust: &Entries<'_>,
    category: &str,
    scope_kind: &str,
    scope: &str,
    claim: &str,
) -> Result<String> {
    let definition = value_object([
        ("category", value_string(category)),
        ("claim", value_string(claim)),
        (
            "scope",
            value_object([
                ("kind", value_string(scope_kind)),
                ("ref", value_string(scope)),
            ]),
        ),
        ("mitigations", Value::Array(Vec::new())),
    ]);
    let id = content_id(TRUST, &encode(&definition));
    if !trust.contains_key(id.as_str()) {
        return Err(invalid("backend trust", "missing exact dependency"));
    }
    Ok(id)
}

fn unknown(execution: &str, reason: &str) -> Value {
    value_object([
        ("kind", value_string("unknown")),
        ("reason", value_string(reason)),
        ("attempts", Value::Array(vec![value_string(execution)])),
    ])
}

fn strings_value(values: impl IntoIterator<Item = String>) -> Value {
    let values: BTreeSet<_> = values.into_iter().collect();
    Value::Array(values.into_iter().map(Value::String).collect())
}

fn record(
    artifacts: &Artifacts<'_, '_>,
    pin: &str,
    format: &str,
    limits: JsonLimits,
) -> Result<Value> {
    strict(
        artifacts.get(pin, Some((format, "0.1")))?,
        limits,
        "backend artifact",
    )
}

fn format(row: &Members, expected: &str) -> Result<()> {
    if text(row, "format")? != expected || text(row, "version")? != "0.1" {
        return Err(ReviewError::Version);
    }
    Ok(())
}

fn execution_terminal(run: &Execution<'_>, code: Option<&str>) -> Result<()> {
    if !matches!((run.attempt, code), (Attempt::Completed, None))
        && !matches!((run.attempt, code), (Attempt::Interrupted { code: actual, .. }, Some(expected)) if actual == expected)
    {
        return Err(invalid("backend", "execution terminal"));
    }
    Ok(())
}
