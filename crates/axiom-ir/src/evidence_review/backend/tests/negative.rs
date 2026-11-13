use super::*;

#[test]
fn qualified_scope_duplicate_invocations_and_wrong_replay_parent_are_refused() {
    let mut bundle = Bundle::new(MINIMAL);
    bundle.add_all(Run::Sat);
    bundle.finish();
    let original = copied(&bundle.batch);
    *field_mut(&mut bundle.batch, "scope") = value_string("qualified");
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "backend source",
            reason: "batch scope or binding"
        })
    ));
    bundle.batch = copied(&original);
    let entries = array_mut(field_mut(&mut bundle.batch, "executions"));
    let invocation = copied(get(&entries[0], "invocation"));
    *field_mut(&mut entries[1], "invocation") = invocation;
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "backend source",
            reason: "entry binding or repeated invocation"
        })
    ));
    bundle.batch = original;
    let entries = array_mut(field_mut(&mut bundle.batch, "executions"));
    let own = copied(get(&entries[1], "execution"));
    *field_mut(field_mut(&mut entries[1], "upstream"), "execution") = own;
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "backend source",
            reason: "serial replay upstream"
        })
    ));
}

#[test]
fn missing_unknown_runtime_trust_is_refused_even_with_a_matching_obligation_set() {
    let mut bundle = Bundle::new(MINIMAL);
    bundle.add_all(Run::Unknown);
    bundle.finish();
    array_mut(field_mut(&mut bundle.document, "trust")).clear();
    array_mut(field_mut(&mut bundle.document, "obligations"))
        .retain(|row| kind(get(row, "definition")).unwrap() != "trust-boundary");
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "backend trust",
            reason: "missing exact dependency"
        })
    ));
}

#[test]
fn missing_tampered_and_mistyped_capture_bytes_are_distinct_errors() {
    let mut bundle = Bundle::new(MINIMAL);
    bundle.add_all(Run::Unsat);
    bundle.finish();
    let capture = {
        let rows = array_mut(field_mut(&mut bundle.batch, "executions"));
        string(get(&rows[0], "provenance"), "provenance")
            .unwrap()
            .to_owned()
    };
    let raw = bundle.blobs.remove(&capture).unwrap();
    assert!(matches!(bundle.verify(), Err(ReviewError::MissingArtifact(id)) if id == capture));
    let mut tampered = raw.clone();
    tampered.push(b' ');
    bundle.blobs.insert(capture.clone(), tampered);
    assert!(matches!(bundle.verify(), Err(ReviewError::ArtifactIdentity(id)) if id == capture));
    bundle.blobs.insert(capture.clone(), raw);
    let row = array_mut(field_mut(&mut bundle.document, "artifacts"))
        .iter_mut()
        .find(|a| string(get(a, "content_digest"), "digest").unwrap() == capture)
        .unwrap();
    *field_mut(row, "format") = value_string("execution-provenance");
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "artifact",
            reason: "format or version"
        })
    ));
}

#[test]
fn backend_readback_rejects_replay_tool_shape_version_and_roles() {
    for (field, value) in [
        ("version", value_string("latest")),
        (
            "roles",
            Value::Array(vec![
                value_string("counterexample-replayer"),
                value_string("counterexample-replayer"),
            ]),
        ),
        (
            "roles",
            Value::Array(vec![
                value_string("counterexample-replayer"),
                value_string("unregistered-role"),
            ]),
        ),
    ] {
        let mut bundle = Bundle::new(MINIMAL);
        bundle.add_all(Run::Sat);
        bundle.finish();
        let tools = array_mut(field_mut(&mut bundle.document, "tools"));
        let actor = tools
            .iter_mut()
            .find(|actor| {
                string(get(get(actor, "definition"), "name"), "name").unwrap() == "review-replayer"
            })
            .unwrap();
        *field_mut(field_mut(actor, "definition"), field) = value;
        let new_id = id("tool", get(actor, "definition"));
        *field_mut(actor, "id") = value_string(&new_id);
        tools.sort_by(|a, b| {
            string(get(a, "id"), "id")
                .unwrap()
                .cmp(string(get(b, "id"), "id").unwrap())
        });
        assert!(matches!(
            bundle.verify(),
            Err(ReviewError::Invalid {
                at: "tool" | "roles",
                ..
            })
        ));
    }
}

#[test]
fn replay_tool_descriptor_and_consumer_component_caps_are_checked() {
    let mut bundle = Bundle::new(MINIMAL);
    bundle.add_all(Run::Sat);
    bundle.finish();
    let batch = encode(&bundle.batch);
    let pin = raw_digest(&batch);
    let context = BackendReviewContext {
        batch: &batch,
        expected_batch_digest: &pin,
        consumer_policy: ProofPolicy::AttestationAllowed,
        allowed_trust_categories: ALLOWED,
        solver_limits: solver_limits(),
        replay_limits: replay_limits(),
    };
    let mut capped = context;
    capped.solver_limits.base.query.max_smt_nodes = 0;
    assert!(matches!(
        readback_v02_with_backend(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            capped
        ),
        Err(ReviewError::Limit("max_smt_nodes"))
    ));
    let mut capped = context;
    capped.replay_limits.world_bytes = 0;
    assert!(matches!(
        readback_v02_with_backend(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            capped
        ),
        Err(ReviewError::Limit("world-bytes"))
    ));
    let replay_tool = raw_digest(b"synthetic replay executable");
    let row = array_mut(field_mut(&mut bundle.document, "artifacts"))
        .iter_mut()
        .find(|row| string(get(row, "content_digest"), "digest").unwrap() == replay_tool)
        .unwrap();
    *field_mut(row, "format") = value_string("generator-source");
    assert!(matches!(
        bundle.verify(),
        Err(ReviewError::Invalid {
            at: "artifact",
            reason: "format or version"
        })
    ));
}
