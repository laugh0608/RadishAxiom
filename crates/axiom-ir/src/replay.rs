//! ADR 0026 的有限具体目标重放；不调用 SMT、进程或 Evidence gate。
mod arithmetic;
mod budget;
mod engine;
mod flat;
mod input;
mod observe;
mod target;
#[cfg(test)]
mod tests;

use crate::{
    document::CanonicalDocument,
    json::{self, JsonError, JsonLimits, Value},
    obligations::{ObligationKind, ObligationSet, raw_digest},
    query::GeneratorIdentity,
    solver::{ModelWorldCandidate, SatModel, SolverError, SolverRequest, check_model_world},
    version::IrVersion,
};
use budget::Budget;
use flat::Json;
use std::fmt;

pub const REPLAY_PROFILE: &str = "axiom-p4-map-filter-replay-v0.1";
pub const REPLAY_ARTIFACT: &str = "axiom-p4-target-replay-observation";
const RULE: &[u8] = include_bytes!("../../../docs/query/p4-concrete-target-replay-v0.1.md");

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReplayProfile {
    MapFilterV0_1,
}
impl ReplayProfile {
    pub fn from_id(id: &str) -> Result<Self> {
        if id == REPLAY_PROFILE {
            Ok(Self::MapFilterV0_1)
        } else {
            Err(ReplayError::UnsupportedProfile)
        }
    }
}
#[derive(Clone, Copy, Debug)]
pub struct ReplayLimits {
    pub ir_json: JsonLimits,
    pub world_bytes: usize,
    pub world_nodes: usize,
    pub world_depth: usize,
    pub type_items: usize,
    pub rows: usize,
    pub value_cells: usize,
    pub evaluation_steps: usize,
    pub comparisons: usize,
    pub integer_digits: usize,
    pub digit_work: usize,
    pub text_bytes: usize,
    pub path_bytes: usize,
    pub output_bytes: usize,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReplayResource {
    WorldBytes,
    WorldNodes,
    WorldDepth,
    TypeItems,
    Rows,
    ValueCells,
    EvaluationSteps,
    Comparisons,
    IntegerDigits,
    DigitWork,
    TextBytes,
    PathBytes,
    OutputBytes,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReplayStage {
    Binding,
    World,
    Input,
    Pre,
    Evaluation,
    Output,
}
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ReplayUsage {
    pub world_bytes: usize,
    pub world_nodes: usize,
    pub world_depth: usize,
    pub type_items: usize,
    pub rows: usize,
    pub value_cells: usize,
    pub evaluation_steps: usize,
    pub comparisons: usize,
    pub integer_digits: usize,
    pub digit_work: usize,
    pub text_bytes: usize,
    pub path_bytes: usize,
    pub output_bytes: usize,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ReplayError {
    UnsupportedProfile,
    UnsupportedIrVersion(IrVersion),
    BindingMismatch,
    UnknownObligation(String),
    NotProve(String),
    UnsupportedKind(ObligationKind),
    UnsupportedFeature {
        anchor: String,
        feature: String,
    },
    Json(JsonError),
    Model(SolverError),
    WorldFormat {
        offset: usize,
        reason: &'static str,
    },
    NonCanonicalWorld {
        offset: usize,
    },
    NonCanonicalObservation {
        offset: usize,
    },
    ResourceLimit {
        stage: ReplayStage,
        resource: ReplayResource,
    },
    Internal(&'static str),
}
impl fmt::Display for ReplayError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "P4 replay: {self:?}")
    }
}
impl std::error::Error for ReplayError {}
type Result<T> = std::result::Result<T, ReplayError>;

pub enum ReplayWorldInput<'a> {
    Provided(&'a [u8]),
    ModelCandidate {
        request: &'a SolverRequest,
        model: &'a SatModel,
        candidate: &'a ModelWorldCandidate,
    },
}
pub struct ReplayInput<'a> {
    pub document: &'a CanonicalDocument,
    pub obligations: &'a ObligationSet,
    pub obligation_id: &'a str,
    pub generator: &'a GeneratorIdentity,
    pub world: ReplayWorldInput<'a>,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReplayOutcome {
    InputRejected,
    PreRejected,
    TargetNotViolated,
    TargetViolated,
}
pub struct TargetReplayObservation {
    bytes: Vec<u8>,
    result: Vec<u8>,
    digest: String,
    usage: ReplayUsage,
    outcome: ReplayOutcome,
}
impl TargetReplayObservation {
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn result_bytes(&self) -> &[u8] {
        &self.result
    }
    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
    pub fn usage(&self) -> &ReplayUsage {
        &self.usage
    }
    pub fn outcome(&self) -> ReplayOutcome {
        self.outcome
    }
}

pub fn replay_target(
    profile: ReplayProfile,
    input: ReplayInput<'_>,
    limits: ReplayLimits,
) -> Result<TargetReplayObservation> {
    match profile {
        ReplayProfile::MapFilterV0_1 => {}
    }
    if input.document.version() != IrVersion::V0_2 {
        return Err(ReplayError::UnsupportedIrVersion(input.document.version()));
    }
    let ir_raw = raw_digest(input.document.canonical_bytes());
    if input.obligations.ir_artifact() != ir_raw
        || input.obligations.ir_document_digest() != input.document.document_id()
    {
        return Err(ReplayError::BindingMismatch);
    }
    let target = input
        .obligations
        .obligations()
        .iter()
        .find(|o| o.id() == input.obligation_id)
        .ok_or_else(|| ReplayError::UnknownObligation(input.obligation_id.into()))?;
    if target.kind().expectation() != "prove" {
        return Err(ReplayError::NotProve(target.id().into()));
    }
    if !matches!(
        target.kind(),
        ObligationKind::NumericRange
            | ObligationKind::Totality
            | ObligationKind::KeyCardinality
            | ObligationKind::RowCoverage
            | ObligationKind::ContractGuarantee
    ) {
        return Err(ReplayError::UnsupportedKind(target.kind()));
    }
    let ir =
        json::parse(input.document.canonical_bytes(), limits.ir_json).map_err(ReplayError::Json)?;
    let definition =
        json::parse(target.canonical_definition(), limits.ir_json).map_err(ReplayError::Json)?;
    let mut b = Budget::new(limits);
    scan(&ir, &mut b)?;
    let (world, source) = match &input.world {
        ReplayWorldInput::Provided(world) => (*world, vec![("kind", "provided-world")]),
        ReplayWorldInput::ModelCandidate {
            request,
            model,
            candidate,
        } => {
            let binding = request.query().binding();
            if binding.ir_artifact() != ir_raw
                || binding.ir_document_digest() != input.document.document_id()
                || binding.obligation_set_artifact() != input.obligations.artifact_digest()
                || binding.obligation() != input.obligation_id
                || binding.semantics_digest()
                    != format!("sha256:{}", input.document.version().semantics_sha256())
            {
                return Err(ReplayError::BindingMismatch);
            }
            check_model_world(candidate.canonical_bytes(), request, model)
                .map_err(ReplayError::Model)?;
            (
                candidate.world_bytes(),
                vec![
                    ("kind", "model-candidate"),
                    ("request", request.artifact_digest()),
                    ("response", model.response_digest()),
                    ("candidate", candidate.artifact_digest()),
                    ("query", request.query().artifact_digest()),
                    ("query_profile", binding.encoding_profile()),
                    ("query_generator", binding.generator().source_digest()),
                ],
            )
        }
    };
    b.stage = ReplayStage::World;
    b.observe(ReplayResource::WorldBytes, world.len())?;
    let (world_json, root) = Json::parse(world, &mut b)?;
    b.stage = ReplayStage::Input;
    let mut engine = engine::Engine::new(input.document, &ir, &definition, target.kind(), &mut b)?;
    let (result, outcome) = engine.run(&world_json, root, &mut b)?;
    drop(world_json);
    let mut out = Json::new();
    b.stage = ReplayStage::Output;
    let result_id = engine.result_json(&result, &mut out, &mut b)?;
    let source = out.str_object(&source, &mut b)?;
    let binding = out.str_object(
        &[
            ("ir_artifact", &ir_raw),
            ("ir_document_digest", input.document.document_id()),
            (
                "obligation_set_artifact",
                input.obligations.artifact_digest(),
            ),
            ("obligation", input.obligation_id),
            (
                "semantics_digest",
                &format!("sha256:{}", input.document.version().semantics_sha256()),
            ),
            ("generator", input.generator.source_digest()),
        ],
        &mut b,
    )?;
    observe::finish(
        out,
        result_id,
        outcome,
        binding,
        source,
        &raw_digest(world),
        &mut b,
    )
}
pub fn check_target_replay(
    bytes: &[u8],
    profile: ReplayProfile,
    input: ReplayInput<'_>,
    limits: ReplayLimits,
) -> Result<TargetReplayObservation> {
    if bytes.len() > limits.output_bytes {
        return Err(ReplayError::ResourceLimit {
            stage: ReplayStage::Output,
            resource: ReplayResource::OutputBytes,
        });
    }
    let observed = replay_target(profile, input, limits)?;
    if bytes != observed.canonical_bytes() {
        return Err(ReplayError::NonCanonicalObservation {
            offset: difference(bytes, observed.canonical_bytes()),
        });
    }
    Ok(observed)
}
fn difference(a: &[u8], b: &[u8]) -> usize {
    a.iter()
        .zip(b)
        .position(|(x, y)| x != y)
        .unwrap_or(a.len().min(b.len()))
}
fn scan(ir: &Value, b: &mut Budget) -> Result<()> {
    for group in ["nodes", "contracts"] {
        for entry in array(get(ir, group)) {
            let anchor = text(entry, "id");
            let def = get(entry, "definition");
            if group == "nodes" && !matches!(text(def, "kind"), "input" | "filter" | "map") {
                return Err(ReplayError::UnsupportedFeature {
                    anchor: anchor.into(),
                    feature: text(def, "kind").into(),
                });
            }
            b.charge(ReplayResource::ValueCells, 1)?;
            let mut stack = vec![def];
            while let Some(v) = stack.pop() {
                b.step()?;
                match v {
                    Value::Object(m) => {
                        if let Some((_, Value::String(op), _)) =
                            m.iter().find(|(k, _, _)| k == "op")
                            && matches!(op.as_str(), "exists_rows" | "count_where" | "sum_where")
                        {
                            return Err(ReplayError::UnsupportedFeature {
                                anchor: anchor.into(),
                                feature: op.clone(),
                            });
                        }
                        b.charge(ReplayResource::ValueCells, m.len())?;
                        stack.extend(m.iter().map(|(_, v, _)| v));
                    }
                    Value::Array(a) => {
                        b.charge(ReplayResource::ValueCells, a.len())?;
                        stack.extend(a);
                    }
                    _ => {}
                }
            }
        }
    }
    Ok(())
}
fn get<'a>(v: &'a Value, key: &str) -> &'a Value {
    let Value::Object(m) = v else {
        unreachable!("P1/P2 object")
    };
    &m.iter().find(|(k, _, _)| k == key).expect("P1/P2 member").1
}
fn string(v: &Value) -> &str {
    let Value::String(s) = v else {
        unreachable!("P1/P2 string")
    };
    s
}
fn text<'a>(v: &'a Value, key: &str) -> &'a str {
    string(get(v, key))
}
fn array(v: &Value) -> &[Value] {
    let Value::Array(a) = v else {
        unreachable!("P1/P2 array")
    };
    a
}
