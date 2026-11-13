use super::*;

// Re-key a completed synthetic bundle after a semantic mutation. Tests can then
// distinguish a broken binding from rejection of a stale outer digest.
fn replace(value: &mut Value, changes: &BTreeMap<String, String>) {
    match value {
        Value::String(text) => {
            if let Some(new) = changes.get(text) {
                *text = new.clone();
            }
        }
        Value::Array(items) => items.iter_mut().for_each(|v| replace(v, changes)),
        Value::Object(items) => items.iter_mut().for_each(|(_, v, _)| replace(v, changes)),
        _ => {}
    }
}

fn rekey(bundle: &mut Bundle) {
    for _ in 0..32 {
        let mut changes = BTreeMap::new();
        for (pin, raw) in &bundle.blobs {
            let actual = raw_digest(raw);
            if actual != *pin {
                changes.insert(pin.clone(), actual);
            }
        }
        for (field, domain) in [
            ("tools", TOOL),
            ("executions", EXECUTION),
            ("trust", TRUST),
            ("obligations", OBLIGATION_DOMAIN),
        ] {
            for row in array_mut(field_mut(&mut bundle.document, field)) {
                let old = string(get(row, "id"), "id").unwrap();
                let new = content_id(domain, &encode(get(row, "definition")));
                if new != old {
                    changes.insert(old.to_owned(), new);
                }
            }
        }
        if changes.is_empty() {
            for (field, key) in [
                ("artifacts", "content_digest"),
                ("tools", "id"),
                ("executions", "id"),
                ("trust", "id"),
                ("obligations", "id"),
            ] {
                array_mut(field_mut(&mut bundle.document, field)).sort_by(|a, b| {
                    string(get(a, key), key)
                        .unwrap()
                        .cmp(string(get(b, key), key).unwrap())
                });
            }
            return;
        }
        replace(&mut bundle.document, &changes);
        replace(&mut bundle.batch, &changes);
        bundle.blobs = std::mem::take(&mut bundle.blobs)
            .into_iter()
            .map(|(pin, raw)| {
                let mut raw = raw;
                if let Ok(mut value) = strict(&raw, json_limits(), "test artifact") {
                    replace(&mut value, &changes);
                    raw = encode(&value);
                }
                (changes.get(&pin).cloned().unwrap_or(pin), raw)
            })
            .collect();
        for row in array_mut(field_mut(&mut bundle.document, "artifacts")) {
            let pin = string(get(row, "content_digest"), "digest").unwrap();
            let length = bundle.blobs[pin].len();
            *field_mut(row, "byte_length") = value_string(&length.to_string());
        }
    }
    panic!("synthetic mutation did not converge");
}

fn mutate_artifact(bundle: &mut Bundle, format: &str, mutate: impl FnOnce(&mut Value)) {
    let row = array_mut(field_mut(&mut bundle.document, "artifacts"))
        .iter()
        .find(|row| string(get(row, "format"), "format").unwrap() == format)
        .unwrap();
    let pin = string(get(row, "content_digest"), "digest")
        .unwrap()
        .to_owned();
    let mut value = strict(&bundle.blobs[&pin], json_limits(), "fixture").unwrap();
    mutate(&mut value);
    bundle.blobs.insert(pin, encode(&value));
    rekey(bundle);
}

#[test]
fn sealed_source_rejects_semantic_rebinding_after_all_outer_identities_are_recomputed() {
    for case in ["request", "invocation", "scheduled", "launch", "terminal"] {
        let mut bundle = Bundle::new(MINIMAL);
        bundle.add_all(Run::Unsat);
        bundle.finish();
        if case == "launch" || case == "terminal" {
            mutate_artifact(&mut bundle, "axiom-evidence-backend-capture", |value| {
                if case == "launch" {
                    let other = copied(get(get(value, "launch"), "supervisor"));
                    *field_mut(field_mut(value, "launch"), "cli") = other;
                } else {
                    *field_mut(field_mut(value, "terminal"), "status") = value_string("sat");
                }
            });
        } else {
            mutate_artifact(&mut bundle, "axiom-evidence-capture-observation", |value| {
                *field_mut(value, case) = if case == "scheduled" {
                    Value::Bool(false)
                } else {
                    value_string(&raw_digest(b"different synthetic invocation or request"))
                };
            });
        }
        assert!(
            matches!(
                bundle.verify(),
                Err(ReviewError::Invalid {
                    at: "backend source",
                    ..
                })
            ),
            "{case}"
        );
    }
}

#[test]
fn attestation_dependencies_cannot_be_moved_to_another_valid_scope() {
    for category in ["production-generator", "proof-backend", "host-runtime"] {
        let mut bundle = Bundle::new(MINIMAL);
        bundle.add_all(Run::Unsat);
        bundle.finish();
        let subject = bundle.ir.document_id().to_owned();
        let trust = array_mut(field_mut(&mut bundle.document, "trust"))
            .iter_mut()
            .find(|row| {
                string(get(get(row, "definition"), "category"), "category").unwrap() == category
            })
            .unwrap();
        *field_mut(field_mut(trust, "definition"), "scope") = value_object([
            ("kind", value_string("subject")),
            ("ref", value_string(&subject)),
        ]);
        rekey(&mut bundle);
        assert!(
            matches!(
                bundle.verify(),
                Err(ReviewError::Invalid {
                    at: "backend trust",
                    reason: "missing exact dependency"
                })
            ),
            "{category}"
        );
    }
}

#[test]
fn earlier_history_and_replay_runtime_trust_cannot_be_hidden_by_the_selected_result() {
    for replay in [false, true] {
        let mut bundle = Bundle::new(MINIMAL);
        let target = bundle.targets[0].clone();
        bundle.attempt(&target, if replay { Run::Sat } else { Run::Timeout });
        bundle.attempt(&target, Run::Unsat);
        bundle.finish();
        bundle.verify().unwrap();
        let history = array_mut(field_mut(&mut bundle.batch, "executions"));
        let execution = string(get(&history[usize::from(replay)], "execution"), "execution")
            .unwrap()
            .to_owned();
        let trusts = array_mut(field_mut(&mut bundle.document, "trust"));
        let removed = trusts
            .iter()
            .find(|row| {
                let def = get(row, "definition");
                string(get(def, "category"), "category").unwrap() == "host-runtime"
                    && string(get(get(def, "scope"), "ref"), "scope").unwrap() == execution
            })
            .map(|row| string(get(row, "id"), "id").unwrap().to_owned())
            .unwrap();
        trusts.retain(|row| string(get(row, "id"), "id").unwrap() != removed);
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
}

#[test]
fn batch_byte_limit_precedes_digest_work_and_identity_checks() {
    let mut bundle = Bundle::new(MINIMAL);
    bundle.add_all(Run::Unknown);
    bundle.finish();
    let batch = encode(&bundle.batch);
    let mut limits = review_limits();
    limits.evidence_json.max_input_bytes = 0;
    let context = BackendReviewContext {
        batch: &batch,
        expected_batch_digest: &raw_digest(b"different batch"),
        consumer_policy: ProofPolicy::AttestationAllowed,
        allowed_trust_categories: ALLOWED,
        solver_limits: solver_limits(),
        replay_limits: replay_limits(),
    };
    assert!(matches!(
        source::Batch::read(
            context,
            &Subject {
                artifact: "",
                document: None,
                p2: None,
            },
            &BTreeMap::new(),
            limits
        ),
        Err(ReviewError::Limit("backend batch bytes"))
    ));
}

#[test]
fn replay_source_cannot_change_parent_or_invocation_after_rekeying() {
    for field in ["solve_execution", "invocation"] {
        let mut bundle = Bundle::new(MINIMAL);
        bundle.add_all(Run::Sat);
        bundle.finish();
        mutate_artifact(
            &mut bundle,
            "axiom-evidence-backend-replay-source",
            |source| {
                *field_mut(source, field) = value_string(&raw_digest(b"other synthetic source"));
            },
        );
        assert!(matches!(
            bundle.verify(),
            Err(ReviewError::Invalid {
                at: "backend source",
                reason: "replay binding"
            })
        ));
    }
}

#[test]
fn replayed_failure_survives_timeout_and_conflicts_with_later_unsat() {
    for later in [Run::Timeout, Run::Sat, Run::Unsat] {
        let mut bundle = Bundle::new(WRONG);
        let target = bundle
            .p2
            .obligations()
            .iter()
            .find(|o| o.kind().as_str() == "contract-guarantee")
            .unwrap()
            .id()
            .to_owned();
        for id in bundle.targets.clone() {
            if id != target {
                bundle.attempt(&id, Run::Unknown);
            }
        }
        bundle.attempt(&target, Run::Sat);
        let first = copied(&bundle.results[&target]);
        assert_eq!(kind(&first).unwrap(), "failed");
        bundle.attempt(&target, later);
        if matches!(later, Run::Timeout) {
            bundle.results.insert(target, first);
        } else if matches!(later, Run::Sat) {
            assert_ne!(encode(&first), encode(&bundle.results[&target]));
        }
        bundle.finish();
        if matches!(later, Run::Unsat) {
            assert!(matches!(
                bundle.verify(),
                Err(ReviewError::Invalid {
                    at: "backend",
                    reason: "conflicting completed supports"
                })
            ));
        } else {
            bundle.verify().unwrap();
        }
    }
}
