use super::*;
use crate::{
    query::{
        CompactQueryLimits, GeneratorIdentity, QueryLimits, QueryProfile, SymbolOrigin,
        encode_query,
    },
    replay::{ReplayInput, ReplayLimits, ReplayProfile, ReplayWorldInput, replay_target},
    solver::{
        OuterTermination, ProcessExit, SolverBudgets, SolverLimits, SolverProfile, SolverRequest,
        SolverRequestInput, SolverResponseInput, SolverToolIdentity, decode_model_world,
        parse_solver_response, plan_solver_request,
    },
};
use std::{path::PathBuf, process::Command};
mod replay_fixture;

pub const MINIMAL: &str = "contracts/map-filter-query-v0.1/inputs/minimal.jcs";
pub const CORRECT: &str = "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-correct.jcs";
pub const WRONG: &str = "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-wrong-add.jcs";
pub const ALLOWED: &[&str] = &["host-runtime", "production-generator", "proof-backend"];
const QUERY_SOURCE: &[u8] = b"synthetic source-bound query generator for Evidence review";
const REPLAY_SOURCE: &[u8] = b"synthetic source-bound replay generator for Evidence review";

pub fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
pub fn json_limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16_000_000,
        max_values: 2_000_000,
        max_nesting: 128,
    }
}
pub fn review_limits() -> ReviewLimits {
    ReviewLimits {
        evidence_json: json_limits(),
        max_artifact_bytes: 16_000_000,
        max_total_artifact_bytes: 128_000_000,
        max_executions: 128,
        p2: ObligationLimits {
            ir_json: json_limits(),
            max_obligations: 1000,
            max_definition_bytes: 1_000_000,
            max_path_bytes: 1_000_000,
            max_output_bytes: 2_000_000,
        },
        derivation: OriginLimits {
            ir_json: json_limits(),
            max_steps: 1_000_000,
            max_premise_edges: 1_000_000,
            max_descriptors: 1_000_000,
            max_path_bytes: 1_000_000,
            max_output_bytes: 1_000_000,
        },
    }
}
pub fn solver_limits() -> SolverBudgets {
    SolverLimits {
        query: QueryLimits {
            ir_json: json_limits(),
            max_input_slots: 10000,
            max_value_cells: 10_000_000,
            max_expression_instances: 1_000_000,
            max_slot_comparisons: 1_000_000,
            max_smt_nodes: 10_000_000,
            max_output_bytes: 1_048_576,
        },
        request_bytes: 100_000,
        response_bytes: 8_000_000,
        symbol_bytes: 2_000_000,
        layout_bytes: 2_000_000,
        tokens: 1_000_000,
        token_bytes: 4_194_304,
        syntax_nodes: 2_000_000,
        syntax_depth: 128,
        integer_digits: 1000,
        definitions: 100_000,
        alias_edges: 100_000,
        layout_items: 1_000_000,
        input_slots: 10000,
        value_cells: 10_000_000,
        decode_steps: 1_000_000,
        text_bytes: 2_000_000,
        world_bytes: 4_000_000,
        candidate_bytes: 5_000_000,
    }
    .with_compact(CompactQueryLimits {
        max_normalized_nodes: 2_000_000,
        max_normalized_edges: 8_000_000,
        max_scratch_cells: 100_000_000,
        max_work_steps: 1_000_000_000,
        max_temporary_bytes: 500_000_000,
        max_integer_digits: 1000,
        max_dag_depth: 100_000,
    })
}
pub fn replay_limits() -> ReplayLimits {
    ReplayLimits {
        ir_json: json_limits(),
        world_bytes: 16_000_000,
        world_nodes: 2_000_000,
        world_depth: 30_000,
        type_items: 2_000_000,
        rows: 100_000,
        value_cells: 100_000_000,
        evaluation_steps: 10_000_000,
        comparisons: 10_000_000,
        integer_digits: 1000,
        digit_work: 100_000_000,
        text_bytes: 16_000_000,
        path_bytes: 16_000_000,
        output_bytes: 16_000_000,
    }
}
pub fn copied(value: &Value) -> Value {
    strict(&encode(value), json_limits(), "test copy").unwrap()
}
pub fn get<'a>(value: &'a Value, key: &str) -> &'a Value {
    let Value::Object(rows) = value else {
        panic!("object")
    };
    &rows.iter().find(|(name, _, _)| name == key).unwrap().1
}
pub fn field_mut<'a>(value: &'a mut Value, key: &str) -> &'a mut Value {
    let Value::Object(rows) = value else {
        panic!("object")
    };
    &mut rows.iter_mut().find(|(name, _, _)| name == key).unwrap().1
}
pub fn array_mut(value: &mut Value) -> &mut Vec<Value> {
    let Value::Array(rows) = value else {
        panic!("array")
    };
    rows
}
fn take(value: &mut Value, key: &str) -> Value {
    std::mem::replace(field_mut(value, key), Value::Bool(false))
}
pub fn id(domain: &str, definition: &Value) -> String {
    content_id(
        &format!("axiom-evidence-v0.2:{domain}"),
        &encode(definition),
    )
}
fn entry(domain: &str, definition: Value) -> Value {
    value_object([
        ("id", value_string(&id(domain, &definition))),
        ("definition", definition),
    ])
}
fn refs(values: &[(&str, String)]) -> Value {
    let values: BTreeMap<_, _> = values.iter().map(|(r, p)| (*r, p.as_str())).collect();
    Value::Array(
        values
            .into_iter()
            .map(|(role, pin)| {
                value_object([
                    ("role", value_string(role)),
                    ("artifact", value_string(pin)),
                ])
            })
            .collect(),
    )
}
fn limit_rows(values: &[(&str, &str, usize)]) -> Value {
    let mut values = values.to_vec();
    values.sort_unstable();
    Value::Array(
        values
            .into_iter()
            .map(|(name, unit, value)| {
                value_object([
                    ("name", value_string(name)),
                    ("unit", value_string(unit)),
                    ("value", value_string(&value.to_string())),
                ])
            })
            .collect(),
    )
}
fn solve_limits() -> Value {
    limit_rows(&[
        ("internal-semantic-steps", "step", 1_000_000),
        ("internal-wall-clock", "millisecond", 5000),
        ("outer-stderr", "byte", 65536),
        ("outer-stdin", "byte", 1048576),
        ("outer-stdout", "byte", 4194304),
        ("outer-wall-clock", "millisecond", 6000),
        ("outer-working-memory", "byte", 134217728),
    ])
}
fn replay_limit_rows(l: ReplayLimits) -> Value {
    limit_rows(&[
        ("ir-input-bytes", "byte", l.ir_json.max_input_bytes),
        ("ir-nesting", "level", l.ir_json.max_nesting),
        ("ir-values", "value", l.ir_json.max_values),
        ("world-bytes", "byte", l.world_bytes),
        ("world-nodes", "node", l.world_nodes),
        ("world-depth", "level", l.world_depth),
        ("type-items", "item", l.type_items),
        ("rows", "row", l.rows),
        ("value-cells", "cell", l.value_cells),
        ("evaluation-steps", "step", l.evaluation_steps),
        ("comparisons", "comparison", l.comparisons),
        ("integer-digits", "digit", l.integer_digits),
        ("digit-work", "digit", l.digit_work),
        ("text-bytes", "byte", l.text_bytes),
        ("path-bytes", "byte", l.path_bytes),
        ("output-bytes", "byte", l.output_bytes),
    ])
}

#[derive(Clone, Copy, Debug)]
pub enum Run {
    Unsat,
    Unknown,
    Sat,
    Timeout,
    MemoryThenTimeout,
    TimeoutThenMemory,
    Exit137,
    Cleanup,
    Prefix,
    Absent,
    ToolUnavailable,
    Protocol,
    StdoutLimit,
    StderrLimit,
}

pub struct Bundle {
    pub document: Value,
    pub blobs: BTreeMap<String, Vec<u8>>,
    pub batch: Value,
    pub ir: CanonicalDocument,
    pub p2: ObligationSet,
    pub targets: Vec<String>,
    pub results: BTreeMap<String, Value>,
    pub history: Vec<Value>,
    pub production_policy: &'static str,
    pub budgets: SolverBudgets,
    pub replay_budget: ReplayLimits,
    pub empty_model: bool,
}

impl Bundle {
    pub fn new(path: &str) -> Self {
        let output = Command::new("python3")
            .args(["-I", "-B"])
            .arg(root().join("docs/evidence/evidence-v0.2-machine-contract/check_vectors.py"))
            .arg("--backend-core")
            .arg(root().join(path))
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let mut core = json::parse(&output.stdout, json_limits()).unwrap();
        let document = take(&mut core, "document");
        let Value::Object(blobs) = take(&mut core, "blobs") else {
            panic!("blobs")
        };
        let blobs = blobs
            .into_iter()
            .map(|(pin, raw, _)| {
                let Value::String(raw) = raw else {
                    panic!("hex")
                };
                let bytes = (0..raw.len())
                    .step_by(2)
                    .map(|i| u8::from_str_radix(&raw[i..i + 2], 16).unwrap())
                    .collect();
                (pin, bytes)
            })
            .collect();
        let ir =
            check_canonical_document(&std::fs::read(root().join(path)).unwrap(), json_limits())
                .unwrap();
        let p2 = generate_obligations(&ir, ObligationProfile::VerificationV0_2, review_limits().p2)
            .unwrap();
        let targets = p2
            .obligations()
            .iter()
            .filter(|o| target_kind(o.kind().as_str()))
            .map(|o| o.id().to_owned())
            .collect();
        Self {
            document,
            blobs,
            batch: Value::Bool(false),
            ir,
            p2,
            targets,
            results: BTreeMap::new(),
            history: Vec::new(),
            production_policy: "attestation-allowed",
            budgets: solver_limits(),
            replay_budget: replay_limits(),
            empty_model: false,
        }
    }
    pub fn add(&mut self, raw: &[u8], format: &str, version: &str) -> String {
        let pin = raw_digest(raw);
        if !self.blobs.contains_key(&pin) {
            self.blobs.insert(pin.clone(), raw.to_vec());
            array_mut(field_mut(&mut self.document, "artifacts")).push(value_object([
                ("content_digest", value_string(&pin)),
                ("byte_length", value_string(&raw.len().to_string())),
                ("format", value_string(format)),
                ("format_version", value_string(version)),
            ]));
        }
        pin
    }
    fn tool(&mut self, name: &str, role: &str, raw: &[u8]) -> String {
        let artifact = self.add(raw, "tool-executable", "0.1");
        let tool = entry(
            "tool",
            value_object([
                ("artifact", value_string(&artifact)),
                ("name", value_string(name)),
                ("roles", Value::Array(vec![value_string(role)])),
                ("version", value_string("0.1-review")),
            ]),
        );
        let pin = string(get(&tool, "id"), "id").unwrap().to_owned();
        if !array_mut(field_mut(&mut self.document, "tools"))
            .iter()
            .any(|t| string(get(t, "id"), "id").unwrap() == pin)
        {
            array_mut(field_mut(&mut self.document, "tools")).push(tool);
        }
        pin
    }
    fn trust(&mut self, category: &str, scope_kind: &str, scope: &str) -> String {
        let claim = match category {
            "host-runtime" => "The scoped runtime and capture report the execution faithfully.",
            "production-generator" => {
                "Every valid violating world has a satisfying query assignment."
            }
            "proof-backend" => "The scoped backend is sound for the bound unsat query.",
            _ => panic!("test category"),
        };
        let trust = entry(
            "trust",
            value_object([
                ("category", value_string(category)),
                ("claim", value_string(claim)),
                ("mitigations", Value::Array(vec![])),
                (
                    "scope",
                    value_object([
                        ("kind", value_string(scope_kind)),
                        ("ref", value_string(scope)),
                    ]),
                ),
            ]),
        );
        let pin = string(get(&trust, "id"), "id").unwrap().to_owned();
        let rows = array_mut(field_mut(&mut self.document, "trust"));
        if !rows
            .iter()
            .any(|t| string(get(t, "id"), "id").unwrap() == pin)
        {
            rows.push(trust);
        }
        pin
    }
    fn execution(
        &mut self,
        definition: Value,
        invocation: &str,
        request: &str,
        upstream: Option<&str>,
    ) -> String {
        let run = entry("execution", definition);
        let pin = string(get(&run, "id"), "id").unwrap().to_owned();
        self.history.push(value_object([
            ("execution", value_string(&pin)),
            ("invocation", value_string(invocation)),
            ("request", value_string(request)),
            (
                "provenance",
                copied(get(get(&run, "definition"), "provenance")),
            ),
            (
                "upstream",
                match upstream {
                    None => value_object([("kind", value_string("none"))]),
                    Some(solve) => value_object([
                        ("kind", value_string("solve")),
                        ("execution", value_string(solve)),
                    ]),
                },
            ),
        ]));
        array_mut(field_mut(&mut self.document, "executions")).push(run);
        pin
    }
    pub fn add_all(&mut self, run: Run) {
        for target in self.targets.clone() {
            self.attempt(&target, run);
        }
    }
    pub fn attempt(&mut self, target: &str, run: Run) {
        let ordinal = array_mut(field_mut(&mut self.document, "executions")).len();
        let invocation = raw_digest(format!("synthetic solve invocation {ordinal}").as_bytes());
        let source = self.add(
            format!("synthetic captured source {ordinal}: {run:?}").as_bytes(),
            "captured-source",
            "0.1",
        );
        let archive = self.add(
            b"synthetic source-bound solver archive",
            "tool-archive",
            "0.1",
        );
        let acceptance = self.add(
            b"synthetic acceptance, not qualified",
            "tool-acceptance",
            "0.1",
        );
        let actor = self.tool("review-solver", "prover", b"synthetic solver executable");
        let cli = raw_digest(b"synthetic solver executable");
        let generator_pin = self.add(QUERY_SOURCE, "generator-source", "0.1");
        let generator = GeneratorIdentity::new(&generator_pin).unwrap();
        let query = encode_query(
            QueryProfile::MapFilterV0_5,
            &self.ir,
            &self.p2,
            target,
            &generator,
            self.budgets
                .base
                .query
                .with_compact(self.budgets.compact.unwrap()),
        )
        .unwrap();
        let tool = SolverToolIdentity::new("linux-arm64", &archive, &acceptance).unwrap();
        let request = plan_solver_request(
            SolverProfile::Cvc5Query0_3ModelV0_1,
            SolverRequestInput {
                document: &self.ir,
                obligations: &self.p2,
                obligation_id: target,
                query_profile: QueryProfile::MapFilterV0_5,
                query: &query,
                generator: &generator,
                tool: &tool,
            },
            self.budgets,
        )
        .unwrap();
        let query_pin = self.add(
            request.stdin_bytes(),
            "axiom-smtlib2-qf-uflia-query0.3",
            "0.3",
        );
        let req_pin = self.add(request.canonical_bytes(), "axiom-p4-solver-request", "0.2");
        let symbols = self.add(request.symbol_bytes(), "axiom-p4-query-symbols", "0.1");
        let layout = self.add(request.layout_bytes(), "axiom-p4-input-layout", "0.1");
        let ir_raw = self.ir.canonical_bytes().to_vec();
        let p2_raw = self.p2.canonical_bytes().to_vec();
        let ir_pin = self.add(&ir_raw, "axiom-ir", "0.2");
        let p2_pin = self.add(&p2_raw, "axiom-obligation-set", "0.2");
        let request_value = strict(request.canonical_bytes(), json_limits(), "request").unwrap();
        let query_rule_pin =
            string(get(get(&request_value, "query"), "query_rules"), "rule").unwrap();
        let query_rule = std::fs::read(root().join("docs/query/map-filter-query-v0.5.md")).unwrap();
        assert_eq!(
            self.add(&query_rule, "evidence-rule", "0.1"),
            query_rule_pin
        );
        self.add(
            &std::fs::read(root().join(
                "contracts/execution-profiles-v0.1/fixtures/positive/cvc5-1.3.4-qf-uflia-v0.1.jcs",
            ))
            .unwrap(),
            "execution-profile",
            "0.1",
        );
        let rule = self.add(SOLVE_RULE.1, "evidence-rule", "0.1");
        let launch = value_object([
            ("acceptance", value_string(&acceptance)),
            ("archive", value_string(&archive)),
            ("cli", value_string(&cli)),
            (
                "dependencies",
                value_string(&self.add(b"synthetic dependencies", "tool-dependencies", "0.1")),
            ),
            (
                "host",
                value_string(&self.add(b"synthetic host", "host-qualification", "0.1")),
            ),
            (
                "policy",
                value_string(&self.add(b"synthetic policy", "execution-policy", "0.1")),
            ),
            (
                "qualification",
                value_string(&self.add(b"synthetic qualification", "tool-qualification", "0.1")),
            ),
            (
                "supervisor",
                value_string(&self.add(b"synthetic supervisor", "tool-executable", "0.1")),
            ),
        ]);
        let stdout = match run {
            Run::Unsat => b"unsat\n".to_vec(),
            Run::Unknown => b"unknown\n".to_vec(),
            Run::Sat => model(&request, self.empty_model),
            Run::Protocol => b"bad response\n".to_vec(),
            Run::StdoutLimit => vec![b'x'; 4_194_304],
            _ => b"sat\n".to_vec(),
        };
        let stderr = if matches!(run, Run::StderrLimit) {
            vec![b'x'; 65_536]
        } else {
            Vec::new()
        };
        let absent = matches!(run, Run::Absent | Run::ToolUnavailable);
        let stdout_complete = !matches!(run, Run::Prefix | Run::StdoutLimit) && !absent;
        let stderr_complete = !matches!(run, Run::StderrLimit) && !absent;
        let stdout_ref = if absent {
            value_object([("kind", value_string("absent"))])
        } else {
            value_object([
                (
                    "kind",
                    value_string(if stdout_complete {
                        "complete"
                    } else {
                        "prefix"
                    }),
                ),
                (
                    "artifact",
                    value_string(&self.add(&stdout, "raw-stream", "0.1")),
                ),
            ])
        };
        let stderr_ref = if absent {
            value_object([("kind", value_string("absent"))])
        } else {
            value_object([
                (
                    "kind",
                    value_string(if stderr_complete {
                        "complete"
                    } else {
                        "prefix"
                    }),
                ),
                (
                    "artifact",
                    value_string(&self.add(&stderr, "raw-stream", "0.1")),
                ),
            ])
        };
        let (facts, elapsed, initial_code) = match run {
            Run::Timeout => (vec![(6000, "deadline")], 6001, Some("deadline")),
            Run::MemoryThenTimeout => (
                vec![(20, "memory"), (6000, "deadline")],
                6001,
                Some("memory"),
            ),
            Run::TimeoutThenMemory => (
                vec![(6000, "deadline"), (6001, "memory")],
                6002,
                Some("deadline"),
            ),
            Run::Exit137 => (vec![], 30, Some("exit")),
            Run::Cleanup => (vec![], 30, Some("cleanup")),
            Run::Prefix | Run::Absent => (vec![], 30, Some("streams-incomplete")),
            Run::ToolUnavailable => (vec![(0, "tool-unavailable")], 1, Some("tool-unavailable")),
            Run::StdoutLimit => (vec![(20, "stdout-limit")], 30, Some("stdout-limit")),
            Run::StderrLimit => (vec![(20, "stderr-limit")], 30, Some("stderr-limit")),
            _ => (vec![], 30, None),
        };
        let response = if initial_code.is_none() {
            Some(parse_solver_response(
                &request,
                SolverResponseInput {
                    request_digest: request.artifact_digest(),
                    stdout: &stdout,
                    stderr: &stderr,
                    stdout_complete: true,
                    stderr_complete: true,
                    exit: ProcessExit::Exited(0),
                    outer_termination: OuterTermination::None,
                },
            ))
        } else {
            None
        };
        let code = initial_code.or_else(|| {
            response.as_ref().and_then(|r| r.as_ref().err()).map(|e| {
                if matches!(e, crate::solver::SolverError::ResourceLimit { .. }) {
                    "component-limit"
                } else {
                    "protocol"
                }
            })
        });
        let response = response.and_then(std::result::Result::ok);
        let terminal = if let Some(code) = code {
            value_object([
                ("kind", value_string("interrupted")),
                ("code", value_string(code)),
            ])
        } else {
            value_object([
                ("kind", value_string("completed")),
                (
                    "status",
                    value_string(match run {
                        Run::Unsat => "unsat",
                        Run::Unknown => "unknown",
                        Run::Sat => "sat",
                        _ => panic!("status"),
                    }),
                ),
            ])
        };
        let observation = value_object([
            ("format", value_string("axiom-evidence-capture-observation")),
            ("version", value_string("0.1")),
            ("scope", value_string("simulation")),
            ("invocation", value_string(&invocation)),
            ("request", value_string(&req_pin)),
            ("source", value_string(&source)),
            ("scheduled", Value::Bool(true)),
            ("started", Value::Bool(!matches!(run, Run::ToolUnavailable))),
            (
                "stdin",
                if matches!(run, Run::ToolUnavailable) {
                    value_object([("kind", value_string("absent"))])
                } else {
                    value_object([
                        ("kind", value_string("complete")),
                        ("artifact", value_string(&query_pin)),
                    ])
                },
            ),
            ("stdout", copied(&stdout_ref)),
            ("stderr", copied(&stderr_ref)),
            (
                "stdout_observed",
                value_string(
                    &(if absent {
                        0
                    } else {
                        stdout.len() + usize::from(matches!(run, Run::StdoutLimit))
                    })
                    .to_string(),
                ),
            ),
            (
                "stderr_observed",
                value_string(
                    &(if absent {
                        0
                    } else {
                        stderr.len() + usize::from(matches!(run, Run::StderrLimit))
                    })
                    .to_string(),
                ),
            ),
            (
                "exit",
                if matches!(run, Run::ToolUnavailable) {
                    value_object([("kind", value_string("unavailable"))])
                } else {
                    value_object([
                        ("kind", value_string("exited")),
                        (
                            "code",
                            value_string(if matches!(run, Run::Exit137) {
                                "137"
                            } else {
                                "0"
                            }),
                        ),
                    ])
                },
            ),
            (
                "cleanup",
                value_string(if matches!(run, Run::Cleanup) {
                    "incomplete"
                } else {
                    "confirmed-empty"
                }),
            ),
            (
                "failures",
                Value::Array(
                    facts
                        .into_iter()
                        .map(|(at, code)| {
                            value_object([
                                ("at_ms", value_string(&at.to_string())),
                                ("code", value_string(code)),
                            ])
                        })
                        .collect(),
                ),
            ),
            ("elapsed_ms", value_string(&elapsed.to_string())),
        ]);
        let obs_pin = self.add(
            &encode(&observation),
            "axiom-evidence-capture-observation",
            "0.1",
        );
        let capture = value_object([
            ("format", value_string("axiom-evidence-backend-capture")),
            ("version", value_string("0.1")),
            ("scope", value_string("simulation")),
            ("invocation", value_string(&invocation)),
            ("request", value_string(&req_pin)),
            ("proof_policy", value_string(self.production_policy)),
            ("launch", launch),
            ("observation", value_string(&obs_pin)),
            ("stdout", stdout_ref),
            ("stderr", stderr_ref),
            ("terminal", terminal),
        ]);
        let provenance = self.add(&encode(&capture), "axiom-evidence-backend-capture", "0.1");
        let response_pin = response.as_ref().map(|r| {
            self.add(
                r.canonical_bytes(),
                "axiom-p4-solver-response-observation",
                "0.1",
            )
        });
        let execution = self.execution(
            value_object([
                ("kind", value_string("prove")),
                ("mode", value_string("p4-solver-response-v0.2")),
                ("tool", value_string(&actor)),
                ("rule", value_string(&rule)),
                ("provenance", value_string(&provenance)),
                ("ordinal", value_string(&ordinal.to_string())),
                ("obligation", value_string(target)),
                ("limits", solve_limits()),
                (
                    "inputs",
                    refs(&[
                        ("canonical-ir", ir_pin),
                        ("obligation-set", p2_pin),
                        ("request", req_pin.clone()),
                        ("query", query_pin.clone()),
                        ("symbols", symbols),
                        ("layout", layout),
                    ]),
                ),
                (
                    "outputs",
                    refs(
                        &response_pin
                            .as_ref()
                            .map(|p| vec![("response", p.clone())])
                            .unwrap_or_default(),
                    ),
                ),
                (
                    "result",
                    match code {
                        None => value_object([("kind", value_string("completed"))]),
                        Some(code) => value_object([
                            ("kind", value_string("interrupted")),
                            ("code", value_string(code)),
                        ]),
                    },
                ),
            ]),
            &invocation,
            &req_pin,
            None,
        );
        let host = self.trust("host-runtime", "execution", &execution);
        let result = if let Some(code) = code {
            let reason = match code {
                "deadline" => "timeout",
                "memory" | "stdout-limit" | "stderr-limit" | "component-limit" => {
                    "resource-exhausted"
                }
                "tool-unavailable" => "backend-unavailable",
                _ => "operational-error",
            };
            test_unknown(&execution, reason)
        } else if matches!(run, Run::Sat) {
            self.replay(
                target,
                &execution,
                &request,
                response.as_ref().unwrap(),
                host,
            )
        } else if matches!(run, Run::Unsat) && self.production_policy == "attestation-allowed" {
            let generator = self.trust("production-generator", "execution", &execution);
            let backend = self.trust("proof-backend", "tool", &actor);
            value_object([
                ("kind", value_string("proved")),
                (
                    "assumptions",
                    test_strings(vec![host, generator, backend.clone()]),
                ),
                (
                    "support",
                    value_object([
                        ("kind", value_string("backend-attestation")),
                        ("execution", value_string(&execution)),
                        ("query", value_string(&query_pin)),
                        ("response", value_string(response_pin.as_ref().unwrap())),
                        ("trust", value_string(&backend)),
                    ]),
                ),
            ])
        } else {
            test_unknown(
                &execution,
                if matches!(run, Run::Unsat) {
                    "incomplete-certificate"
                } else {
                    "indeterminate"
                },
            )
        };
        self.results.insert(target.to_owned(), result);
    }
}

pub fn test_unknown(execution: &str, reason: &str) -> Value {
    value_object([
        ("kind", value_string("unknown")),
        ("reason", value_string(reason)),
        ("attempts", Value::Array(vec![value_string(execution)])),
    ])
}
pub fn test_strings(mut values: Vec<String>) -> Value {
    values.sort();
    values.dedup();
    Value::Array(values.into_iter().map(Value::String).collect())
}

fn model(request: &SolverRequest, empty: bool) -> Vec<u8> {
    let mut out = String::from("sat\n(\n");
    for symbol in request.query().symbols() {
        let value = match symbol.origin() {
            SymbolOrigin::TextLiteral(_) => "@Text_0".to_owned(),
            SymbolOrigin::Input {
                interface,
                slot,
                component,
            } if interface.as_ref() == "orders" && !empty => match component {
                None => (*slot < 3).to_string(),
                Some(0) => ["10", "5", "0"].get(*slot).unwrap_or(&"0").to_string(),
                Some(1) => format!("@Text_{}", slot + 1),
                Some(2) => if *slot < 2 { "1" } else { "0" }.to_owned(),
                Some(3) => ["10", "20", "8"].get(*slot).unwrap_or(&"0").to_string(),
                _ => panic!("AX-B01 canonical leaf"),
            },
            SymbolOrigin::Input { component, .. } => match (component, symbol.sort()) {
                (None, _) | (_, "Bool") => "false".into(),
                (_, "Int") => "0".into(),
                (_, "Text") => "@Text_0".into(),
                _ => panic!("sort"),
            },
        };
        out.push_str(&format!(
            "(define-fun {} () {} {value})\n",
            symbol.name(),
            symbol.sort()
        ));
    }
    out.push_str(")\n");
    out.into_bytes()
}
