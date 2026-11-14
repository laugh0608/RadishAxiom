use super::*;
pub(in crate::evidence_review) mod fixtures;
mod independent;
mod negative;
mod review;
mod structured;
use fixtures::*;

#[test]
fn source_bound_complete_document_and_consumer_policy_are_distinct() {
    let mut bundle = Bundle::new(MINIMAL);
    bundle.add_all(Run::Unsat);
    bundle.finish();
    let result = bundle.verify().unwrap();
    assert_eq!(
        result.artifact_digest,
        raw_digest(&encode(&bundle.document))
    );
    let backend = result.backend.unwrap();
    assert_eq!(backend.scope, "simulation");
    assert_eq!(backend.policy, BackendPolicyStatus::TrustAllowed);
    assert_eq!(backend.remaining_trust.len(), 3);
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
            .verify_policy(ProofPolicy::AttestationAllowed, &["proof-backend"])
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
}

#[test]
fn replay_nonviolation_and_unknown_keep_runtime_trust() {
    for run in [Run::Unknown, Run::Sat] {
        let mut bundle = Bundle::new(MINIMAL);
        bundle.add_all(run);
        bundle.finish();
        let readback = bundle.verify().unwrap();
        assert_eq!(
            string(get(get(&bundle.document, "conclusion"), "kind"), "kind").unwrap(),
            "inconclusive"
        );
        assert_eq!(
            readback.backend.unwrap().remaining_trust.len(),
            if matches!(run, Run::Sat) { 2 } else { 1 }
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
    }
}

#[test]
fn captured_failures_keep_the_first_cause_and_distinguish_absent_streams() {
    for contract in [BackendContract::Legacy, BackendContract::StructuredV02] {
        for (run, reason) in [
            (Run::Timeout, "timeout"),
            (Run::MemoryThenTimeout, "resource-exhausted"),
            (Run::TimeoutThenMemory, "timeout"),
            (Run::Exit137, "operational-error"),
            (Run::Cleanup, "operational-error"),
            (Run::Prefix, "operational-error"),
            (Run::Absent, "operational-error"),
            (Run::ToolUnavailable, "backend-unavailable"),
            (Run::Protocol, "operational-error"),
            (Run::StdoutLimit, "resource-exhausted"),
            (Run::StderrLimit, "resource-exhausted"),
        ] {
            let mut bundle = Bundle::with_contract(MINIMAL, contract);
            bundle.add_all(run);
            assert_eq!(
                string(
                    get(bundle.results.values().next().unwrap(), "reason"),
                    "reason"
                )
                .unwrap(),
                reason
            );
            bundle.finish();
            bundle
                .verify()
                .unwrap_or_else(|error| panic!("{run:?}: {error}"));
        }
    }
}

#[test]
fn completed_support_survives_later_unknown_and_preserves_every_attempt() {
    for contract in [BackendContract::Legacy, BackendContract::StructuredV02] {
        for sequence in [[Run::Timeout, Run::Unsat], [Run::Unsat, Run::Timeout]] {
            let mut bundle = Bundle::with_contract(MINIMAL, contract);
            let target = bundle.targets[0].clone();
            let mut completed = None;
            for run in sequence {
                bundle.attempt(&target, run);
                if matches!(run, Run::Unsat) {
                    completed = Some(copied(&bundle.results[&target]));
                }
            }
            bundle.results.insert(target.clone(), completed.unwrap());
            bundle.finish();
            let result = bundle.verify().unwrap();
            assert_eq!(result.backend.unwrap().remaining_trust.len(), 4);
            assert_eq!(
                array_mut(field_mut(&mut bundle.batch, "executions")).len(),
                2
            );
            let row = array_mut(field_mut(&mut bundle.document, "obligations"))
                .iter_mut()
                .find(|o| string(get(o, "id"), "id").unwrap() == target)
                .unwrap();
            *field_mut(row, "result") = test_unknown(
                "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "timeout",
            );
            assert!(matches!(
                bundle.verify(),
                Err(ReviewError::Invalid {
                    at: "backend",
                    reason: "result support or aggregation"
                })
            ));
        }
    }
}

#[test]
fn numeric_attempt_order_and_matching_terminal_refs_are_recomputed() {
    for contract in [BackendContract::Legacy, BackendContract::StructuredV02] {
        let mut bundle = Bundle::with_contract(MINIMAL, contract);
        let target = bundle.targets[0].clone();
        for _ in 0..11 {
            bundle.attempt(&target, Run::Unknown);
        }
        bundle.attempt(&target, Run::Timeout);
        bundle.finish();
        bundle.verify().unwrap();
        assert_eq!(
            array_mut(field_mut(&mut bundle.batch, "executions")).len(),
            12
        );

        let mut repeated = Bundle::with_contract(MINIMAL, contract);
        repeated.attempt(&target, Run::Timeout);
        let first = copied(get(&repeated.results[&target], "attempts"));
        repeated.attempt(&target, Run::Unknown);
        repeated.attempt(&target, Run::Timeout);
        let Value::Array(first) = first else {
            panic!("attempts")
        };
        let refs = array_mut(field_mut(
            repeated.results.get_mut(&target).unwrap(),
            "attempts",
        ));
        refs.extend(first);
        refs.sort_by(|a, b| string(a, "ref").unwrap().cmp(string(b, "ref").unwrap()));
        repeated.finish();
        repeated.verify().unwrap();
    }
}

#[test]
fn sealed_batch_rejects_deleted_history_and_a_self_replaced_authority_pin() {
    let mut history = Bundle::new(MINIMAL);
    let target = history.targets[0].clone();
    history.attempt(&target, Run::Timeout);
    history.attempt(&target, Run::Unsat);
    history.finish();
    history.verify().unwrap();
    let original_batch = encode(&history.batch);
    let original_pin = raw_digest(&original_batch);
    let mut shortened = Bundle::new(MINIMAL);
    shortened.add_all(Run::Unsat);
    shortened.finish();
    shortened.verify().unwrap();
    let context = BackendReviewContext {
        batch: &original_batch,
        expected_batch_digest: &original_pin,
        consumer_policy: ProofPolicy::AttestationAllowed,
        allowed_trust_categories: ALLOWED,
        solver_limits: solver_limits(),
        replay_limits: replay_limits(),
    };
    let result = readback_v02_with_backend(
        &encode(&shortened.document),
        |pin| shortened.blobs.get(pin).map(Vec::as_slice),
        review_limits(),
        context,
    );
    assert!(matches!(
        result,
        Err(ReviewError::Invalid {
            at: "backend source",
            reason: "complete execution inventory"
        })
    ));
    let shortened_batch = encode(&shortened.batch);
    let result = readback_v02_with_backend(
        &encode(&shortened.document),
        |pin| shortened.blobs.get(pin).map(Vec::as_slice),
        review_limits(),
        BackendReviewContext {
            batch: &shortened_batch,
            ..context
        },
    );
    assert!(matches!(
        result,
        Err(ReviewError::Invalid {
            at: "backend source",
            reason: "batch authority"
        })
    ));
}

#[test]
fn production_certificate_policy_and_replay_budget_failures_have_real_attempts() {
    let mut bundle = Bundle::new(MINIMAL);
    bundle.production_policy = "certificate-required";
    bundle.add_all(Run::Unsat);
    assert_eq!(
        string(
            get(bundle.results.values().next().unwrap(), "reason"),
            "reason"
        )
        .unwrap(),
        "incomplete-certificate"
    );
    bundle.finish();
    let result = bundle
        .verify_policy(ProofPolicy::CertificateRequired, &["host-runtime"])
        .unwrap();
    assert_eq!(
        result.backend.unwrap().policy,
        BackendPolicyStatus::TrustAllowed
    );

    let mut decode = Bundle::new(MINIMAL);
    decode.budgets.base.world_bytes = 0;
    decode.add_all(Run::Sat);
    decode.finish();
    decode.verify().unwrap();
    let mut replay = Bundle::new(MINIMAL);
    replay.replay_budget.world_bytes = 0;
    replay.add_all(Run::Sat);
    replay.finish();
    replay.verify().unwrap();
}

#[test]
fn full_ax_b01_has_thirteen_core_obligations_and_nine_bound_solver_results() {
    let mut bundle = Bundle::new(CORRECT);
    assert_eq!(bundle.p2.obligations().len(), 13);
    assert_eq!(bundle.targets.len(), 9);
    bundle.add_all(Run::Unsat);
    bundle.finish();
    let result = bundle.verify().unwrap();
    assert_eq!(
        result.backend.unwrap().policy,
        BackendPolicyStatus::TrustAllowed
    );
    assert_eq!(
        string(get(get(&bundle.document, "conclusion"), "kind"), "kind").unwrap(),
        "satisfied"
    );
    let target = bundle.targets[0].clone();
    array_mut(field_mut(&mut bundle.document, "obligations"))
        .retain(|o| string(get(o, "id"), "id").unwrap() != target);
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "obligations",
            reason: "incomplete or extra"
        })
    ));
}

#[test]
fn valid_replayed_violation_conflicts_with_a_bound_unsat_for_the_same_target() {
    for contract in [BackendContract::Legacy, BackendContract::StructuredV02] {
        let mut bundle = Bundle::with_contract(WRONG, contract);
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
        bundle.attempt(&target, Run::Unsat);
        bundle.attempt(&target, Run::Sat);
        assert_eq!(kind(&bundle.results[&target]).unwrap(), "failed");
        bundle.finish();
        assert!(matches!(
            bundle.verify(),
            Err(ReviewError::Invalid {
                at: "backend",
                reason: "conflicting completed supports"
            })
        ));
    }
}

#[test]
fn interleaved_targets_select_the_last_compatible_completed_support() {
    for contract in [BackendContract::Legacy, BackendContract::StructuredV02] {
        let mut bundle = Bundle::with_contract(CORRECT, contract);
        bundle.add_all(Run::Unsat);
        let target = bundle.targets[0].clone();
        let other = bundle.targets[1].clone();
        let old = copied(&bundle.results[&target]);
        bundle.attempt(&other, Run::Unsat);
        bundle.attempt(&target, Run::Unsat);
        let completed = copied(&bundle.results[&target]);
        assert_ne!(encode(&old), encode(&completed));
        bundle.attempt(&target, Run::Timeout);
        bundle.results.insert(target, completed);
        bundle.finish();
        bundle.verify().unwrap();
    }
}
