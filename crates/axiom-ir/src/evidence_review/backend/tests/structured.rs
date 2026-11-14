use super::review::{mutate_artifact, rekey};
use super::*;
use std::{
    io::Write,
    process::{Command, Stdio},
};

const INTERRUPTION: &str = "axiom-evidence-replay-interruption";
const POLICY: &str = "axiom-evidence-component-policy";

fn interrupted_bundle(model: bool) -> Bundle {
    let mut bundle = Bundle::structured(MINIMAL);
    if model {
        bundle.budgets.base.world_bytes = 0;
    } else {
        bundle.replay_budget.world_bytes = 0;
    }
    bundle.add_all(Run::Sat);
    bundle.finish();
    bundle
}

fn artifact(bundle: &Bundle, format: &str) -> String {
    let Value::Array(rows) = get(&bundle.document, "artifacts") else {
        panic!("artifacts")
    };
    string(
        get(
            rows.iter()
                .find(|row| string(get(row, "format"), "format").unwrap() == format)
                .unwrap(),
            "content_digest",
        ),
        "digest",
    )
    .unwrap()
    .to_owned()
}

fn check_exchange(name: &str, bundle: &Bundle) {
    let packet = value_object([
        ("name", value_string(name)),
        ("document", copied(&bundle.document)),
        ("batch", copied(&bundle.batch)),
        (
            "blobs",
            Value::Object(
                bundle
                    .blobs
                    .iter()
                    .map(|(pin, raw)| {
                        let hex: String = raw.iter().map(|byte| format!("{byte:02x}")).collect();
                        (pin.clone(), value_string(&hex), 0)
                    })
                    .collect(),
            ),
        ),
    ]);
    let mut child = Command::new("python3")
        .args(["-I", "-B"])
        .arg(root().join("scripts/test-evidence-exchange-review.py"))
        .arg("--structured-packet")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(&encode(&packet))
        .unwrap();
    let output = child.wait_with_output().unwrap();
    assert!(
        output.status.success(),
        "{name}: {}\n{}",
        String::from_utf8_lossy(&output.stderr),
        String::from_utf8_lossy(&output.stdout)
    );
    eprint!("{}", String::from_utf8_lossy(&output.stdout));
}

#[test]
fn new_batch_is_explicit_and_never_upgrades_old_debug_bytes() {
    for model in [true, false] {
        let mut bundle = interrupted_bundle(model);
        let result = bundle.verify().unwrap();
        assert_eq!(
            result.backend.unwrap().contract_digest,
            raw_digest(STRUCTURED_CONTRACT)
        );
        // Public API, not only the fixture's private selection path.
        let batch = encode(&bundle.batch);
        let context = BackendReviewContext {
            batch: &batch,
            expected_batch_digest: &raw_digest(&batch),
            consumer_policy: ProofPolicy::AttestationAllowed,
            allowed_trust_categories: ALLOWED,
            solver_limits: solver_limits(),
            replay_limits: replay_limits(),
        };
        readback_v02_with_backend_v02(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            context,
        )
        .unwrap();
        assert!(matches!(
            readback_v02_with_backend(
                &encode(&bundle.document),
                |pin| bundle.blobs.get(pin).map(Vec::as_slice),
                review_limits(),
                context
            ),
            Err(ReviewError::Version)
        ));
        *field_mut(&mut bundle.batch, "version") = value_string("0.1");
        assert!(matches!(bundle.verify(), Err(ReviewError::Version)));
        *field_mut(&mut bundle.batch, "version") = value_string("0.2");
        *field_mut(&mut bundle.batch, "contract") = value_string(&raw_digest(CONTRACT));
        assert!(matches!(
            bundle.verify(),
            Err(ReviewError::Invalid {
                at: "backend source",
                ..
            })
        ));
    }
    let mut old = Bundle::new(MINIMAL);
    old.budgets.base.world_bytes = 0;
    old.add_all(Run::Sat);
    old.finish();
    old.verify().unwrap();
    old.contract = BackendContract::StructuredV02;
    *field_mut(&mut old.batch, "version") = value_string("0.2");
    *field_mut(&mut old.batch, "contract") = value_string(&raw_digest(STRUCTURED_CONTRACT));
    assert!(matches!(
        old.verify(),
        Err(ReviewError::Invalid {
            at: "artifact",
            reason: "format or version"
        })
    ));
    let pin = artifact(&old, INTERRUPTION);
    for row in array_mut(field_mut(&mut old.document, "artifacts")) {
        if string(get(row, "content_digest"), "pin").unwrap() == pin {
            *field_mut(row, "format_version") = value_string("0.2");
        }
    }
    mutate_artifact(&mut old, INTERRUPTION, |row| {
        *field_mut(row, "version") = value_string("0.2")
    });
    assert!(matches!(old.verify(), Err(ReviewError::Shape(_))));
}

#[test]
fn structured_facts_keep_production_limits_and_stage_specific_inputs() {
    for model in [true, false] {
        let bundle = interrupted_bundle(model);
        bundle.verify().unwrap();
        check_exchange(
            if model {
                "model-world-limit"
            } else {
                "replay-world-limit"
            },
            &bundle,
        );
        let interruption = strict(
            &bundle.blobs[&artifact(&bundle, INTERRUPTION)],
            json_limits(),
            "interruption",
        )
        .unwrap();
        assert_eq!(
            string(get(&interruption, "stage"), "stage").unwrap(),
            if model { "model" } else { "replay" }
        );
        assert_eq!(
            encode(get(&interruption, "cause")),
            br#"{"kind":"resource-limit","limit":"0","resource":"world-bytes"}"#
        );
        let policy = strict(
            &bundle.blobs[&artifact(&bundle, POLICY)],
            json_limits(),
            "policy",
        )
        .unwrap();
        let Value::Array(rows) = get(&policy, "limits") else {
            panic!("limits")
        };
        assert_eq!(rows.len(), if model { 6 } else { 13 });
        let Value::Array(runs) = get(&bundle.document, "executions") else {
            panic!("executions")
        };
        let run = runs
            .iter()
            .map(|r| get(r, "definition"))
            .find(|r| string(get(r, "mode"), "mode").unwrap() == "p4-target-replay-v0.1")
            .unwrap();
        let Value::Array(inputs) = get(run, "inputs") else {
            panic!("inputs")
        };
        assert_eq!(inputs.len(), if model { 4 } else { 6 });
        assert_eq!(
            string(get(get(&bundle.document, "conclusion"), "kind"), "kind").unwrap(),
            "inconclusive"
        );
    }
}

#[test]
fn rekeyed_structured_lies_do_not_become_observed_facts() {
    for case in [
        "limit",
        "resource",
        "stage",
        "code",
        "cause",
        "policy-limit",
        "policy-stage",
        "policy-unit",
        "policy-missing",
        "input",
        "scope",
        "request",
        "solve",
        "extra",
    ] {
        let mut bundle = interrupted_bundle(false);
        if case.starts_with("policy-") {
            mutate_artifact(&mut bundle, POLICY, |row| match case {
                "policy-stage" => *field_mut(row, "stage") = value_string("model"),
                "policy-missing" => {
                    array_mut(field_mut(row, "limits")).pop();
                }
                _ => {
                    let row = &mut array_mut(field_mut(row, "limits"))[0];
                    *field_mut(
                        row,
                        if case == "policy-unit" {
                            "unit"
                        } else {
                            "value"
                        },
                    ) = value_string(if case == "policy-unit" { "byte" } else { "999" });
                }
            });
        } else {
            mutate_artifact(&mut bundle, INTERRUPTION, |row| match case {
                "limit" => *field_mut(field_mut(row, "cause"), "limit") = value_string("1"),
                "resource" => {
                    *field_mut(field_mut(row, "cause"), "resource") = value_string("decode-steps")
                }
                "stage" => *field_mut(row, "stage") = value_string("model"),
                "code" => *field_mut(row, "code") = value_string("replay-error"),
                "scope" => *field_mut(row, "scope") = value_string("qualified"),
                "cause" => {
                    *field_mut(row, "cause") =
                        value_object([("kind", value_string("component-error"))])
                }
                "input" => {
                    *field_mut(row, "cause") = value_object([
                        ("kind", value_string("input-error")),
                        ("artifact", value_string(&raw_digest(b"unrelated input"))),
                        ("reason", value_string("invalid-world")),
                    ])
                }
                "request" => {
                    *field_mut(row, "request") = value_string(&raw_digest(b"another request"))
                }
                "solve" => {
                    *field_mut(row, "solve_execution") = value_string(&raw_digest(b"another solve"))
                }
                "extra" => {
                    let Value::Object(rows) = row else {
                        panic!("object")
                    };
                    rows.push(("detail".into(), value_string("Debug is not a fact"), 0));
                    rows.sort_by(|a, b| a.0.cmp(&b.0));
                }
                _ => unreachable!(),
            });
        }
        let result = bundle.verify();
        assert!(
            matches!(
                result,
                Err(ReviewError::Invalid {
                    at: "structured interruption",
                    ..
                }) | Err(ReviewError::Shape(_))
            ),
            "{case}: {result:?}"
        );
    }
}

#[test]
fn diagnostic_attachment_is_bound_but_never_used_as_semantic_input() {
    let mut bundle = Bundle::structured(MINIMAL);
    bundle.replay_budget.world_bytes = 0;
    bundle.interruption_diagnostic = Some(b"synthetic diagnostic A");
    bundle.add_all(Run::Sat);
    bundle.finish();
    bundle.verify().unwrap();
    let pin = artifact(&bundle, "component-diagnostic-text");
    bundle.blobs.insert(
        pin,
        b"different text: unsupported / success / timeout".to_vec(),
    );
    rekey(&mut bundle);
    bundle.verify().unwrap();
    let pin = artifact(&bundle, "component-diagnostic-text");
    let raw = bundle.blobs.remove(&pin).unwrap();
    assert!(matches!(bundle.verify(), Err(ReviewError::MissingArtifact(id)) if id == pin));
    bundle.blobs.insert(pin.clone(), b"wrong bytes".to_vec());
    assert!(matches!(bundle.verify(), Err(ReviewError::ArtifactIdentity(id)) if id == pin));
    bundle.blobs.insert(pin, raw);
    mutate_artifact(&mut bundle, INTERRUPTION, |row| {
        *field_mut(row, "diagnostic") = value_object([
            ("kind", value_string("absent")),
            ("ref", value_string(&raw_digest(b"hidden reference"))),
        ])
    });
    assert!(matches!(bundle.verify(), Err(ReviewError::Shape(_))));
}

#[test]
fn consumer_caps_cannot_be_reported_as_a_producer_interruption() {
    let bundle = interrupted_bundle(false);
    let batch = encode(&bundle.batch);
    let mut context = BackendReviewContext {
        batch: &batch,
        expected_batch_digest: &raw_digest(&batch),
        consumer_policy: ProofPolicy::AttestationAllowed,
        allowed_trust_categories: ALLOWED,
        solver_limits: solver_limits(),
        replay_limits: replay_limits(),
    };
    context.replay_limits.evaluation_steps = 0;
    assert!(matches!(
        readback_v02_with_backend_v02(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            context
        ),
        Err(ReviewError::Limit("evaluation-steps"))
    ));
    context.replay_limits = replay_limits();
    context.solver_limits.base.decode_steps = 0;
    assert!(matches!(
        readback_v02_with_backend_v02(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            context
        ),
        Err(ReviewError::Limit("decode_steps"))
    ));
}

#[test]
fn exact_replay_world_budget_completes_and_one_less_preserves_the_world() {
    let mut base = Bundle::structured(MINIMAL);
    base.add_all(Run::Sat);
    base.finish();
    base.verify().unwrap();
    let size = base.blobs[&artifact(&base, "axiom-p4-world")].len();
    assert!(size > 0);
    for cap in [size, size - 1] {
        let mut bundle = Bundle::structured(MINIMAL);
        bundle.replay_budget.world_bytes = cap;
        bundle.add_all(Run::Sat);
        bundle.finish();
        bundle.verify().unwrap();
        assert_eq!(
            bundle.blobs[&artifact(&bundle, "axiom-p4-world")].len(),
            size
        );
        let Value::Array(rows) = get(&bundle.document, "artifacts") else {
            panic!("artifacts")
        };
        let interrupted = rows
            .iter()
            .any(|row| string(get(row, "format"), "format").unwrap() == INTERRUPTION);
        assert_eq!(interrupted, cap < size);
        if interrupted {
            let value = strict(
                &bundle.blobs[&artifact(&bundle, INTERRUPTION)],
                json_limits(),
                "interruption",
            )
            .unwrap();
            assert_eq!(
                string(get(get(&value, "cause"), "limit"), "limit").unwrap(),
                cap.to_string()
            );
        }
    }
}

#[test]
fn invalid_model_is_observed_and_bound_to_the_actual_response() {
    let mut bundle = Bundle::structured(CORRECT);
    bundle.duplicate_model_keys = true;
    bundle.add_all(Run::Sat);
    bundle.finish();
    bundle.verify().unwrap();
    check_exchange("model-invalid", &bundle);
    let Value::Array(runs) = get(&bundle.document, "executions") else {
        panic!("executions")
    };
    for run in runs
        .iter()
        .map(|r| get(r, "definition"))
        .filter(|r| string(get(r, "mode"), "mode").unwrap() == "p4-target-replay-v0.1")
    {
        let source = strict(
            &bundle.blobs[string(get(run, "provenance"), "pin").unwrap()],
            json_limits(),
            "source",
        )
        .unwrap();
        let value = strict(
            &bundle.blobs[string(get(&source, "observation"), "pin").unwrap()],
            json_limits(),
            "interruption",
        )
        .unwrap();
        assert_eq!(string(get(&value, "stage"), "stage").unwrap(), "model");
        let Value::Array(inputs) = get(run, "inputs") else {
            panic!("inputs")
        };
        assert_eq!(inputs.len(), 4);
        let response = string(
            get(
                inputs
                    .iter()
                    .find(|i| string(get(i, "role"), "role").unwrap() == "response")
                    .unwrap(),
                "artifact",
            ),
            "pin",
        )
        .unwrap();
        assert_eq!(
            encode(get(&value, "cause")),
            format!(r#"{{"artifact":"{response}","kind":"input-error","reason":"invalid-model"}}"#)
                .as_bytes()
        );
    }
}

#[test]
fn structured_batch_preserves_history_authority_and_all_trust() {
    let mut bundle = Bundle::structured(MINIMAL);
    let target = bundle.targets[0].clone();
    bundle.attempt(&target, Run::Unsat);
    let completed = copied(&bundle.results[&target]);
    bundle.replay_budget.world_bytes = 0;
    bundle.attempt(&target, Run::Sat);
    bundle.results.insert(target, completed);
    bundle.finish();
    let result = bundle.verify().unwrap();
    let trust = array_mut(field_mut(&mut bundle.document, "trust"));
    let expected: Vec<_> = trust
        .iter()
        .map(|row| string(get(row, "id"), "trust ID").unwrap().to_owned())
        .collect();
    assert_eq!(expected.len(), 5);
    assert_eq!(result.backend.unwrap().remaining_trust, expected);
    assert_eq!(
        bundle
            .verify_policy(ProofPolicy::CertificateRequired, ALLOWED)
            .unwrap()
            .backend
            .unwrap()
            .policy,
        BackendPolicyStatus::Incomplete
    );
    assert_eq!(
        bundle
            .verify_policy(ProofPolicy::AttestationAllowed, &[])
            .unwrap()
            .backend
            .unwrap()
            .policy,
        BackendPolicyStatus::Incomplete
    );
    assert!(matches!(
        readback_v02(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits()
        ),
        Err(ReviewError::Invalid {
            at: "backend",
            reason: "separate source authority required"
        })
    ));
    let batch = encode(&bundle.batch);
    let pin = raw_digest(&batch);
    let mut shorter = copied(&bundle.batch);
    array_mut(field_mut(&mut shorter, "executions")).remove(0);
    let shorter = encode(&shorter);
    let context = BackendReviewContext {
        batch: &shorter,
        expected_batch_digest: &pin,
        consumer_policy: ProofPolicy::AttestationAllowed,
        allowed_trust_categories: ALLOWED,
        solver_limits: solver_limits(),
        replay_limits: replay_limits(),
    };
    assert!(matches!(
        readback_v02_with_backend_v02(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            context
        ),
        Err(ReviewError::Invalid {
            at: "backend source",
            reason: "batch authority"
        })
    ));
    assert!(matches!(
        readback_v02_with_backend_v02(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            BackendReviewContext {
                expected_batch_digest: &raw_digest(&shorter),
                ..context
            }
        ),
        Err(ReviewError::Invalid {
            at: "backend source",
            reason: "complete execution inventory"
        })
    ));

    let history = array_mut(field_mut(&mut bundle.batch, "executions"));
    let replay = string(get(&history[2], "execution"), "replay").unwrap();
    let trust = array_mut(field_mut(&mut bundle.document, "trust"));
    let index = trust
        .iter()
        .position(|row| {
            string(get(get(get(row, "definition"), "scope"), "ref"), "scope").unwrap() == replay
        })
        .unwrap();
    let removed = trust.remove(index);
    let removed = string(get(&removed, "id"), "trust ID").unwrap();
    array_mut(field_mut(&mut bundle.document, "obligations")).retain(|row| {
        let definition = get(row, "definition");
        kind(definition).unwrap() != "trust-boundary"
            || string(get(get(definition, "subject"), "scope"), "scope").unwrap() != removed
    });
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "backend trust",
            reason: "missing exact dependency"
        })
    ));
}
