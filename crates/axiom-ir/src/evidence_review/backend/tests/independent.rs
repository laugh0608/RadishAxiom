use super::*;
use std::{
    io::Write,
    process::{Command, Stdio},
};

fn false_pre_bundle() -> Bundle {
    let mut document = strict(
        &std::fs::read(root().join(MINIMAL)).unwrap(),
        json_limits(),
        "IR",
    )
    .unwrap();
    let pre = strict(
        &std::fs::read(root().join("contracts/map-filter-query-v0.1/inputs/pre-false.jcs"))
            .unwrap(),
        json_limits(),
        "IR",
    )
    .unwrap();
    *field_mut(&mut document, "contracts") = copied(get(&pre, "contracts"));
    let path = root().join(format!(
        "target/evidence-backend-review-pre-false-{}.jcs",
        std::process::id()
    ));
    std::fs::write(&path, encode(&document)).unwrap();
    let bundle = Bundle::new(path.to_str().unwrap());
    std::fs::remove_file(path).unwrap();
    bundle
}

#[test]
fn five_target_kinds_and_counterexample_attribution_match_independent_finite_semantics() {
    for (name, path) in [
        ("correct", CORRECT),
        ("wrong-add", WRONG),
        (
            "wrong-drop-zero",
            "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-wrong-drop-zero.jcs",
        ),
        (
            "pre-false",
            "contracts/map-filter-query-v0.1/inputs/pre-false.jcs",
        ),
    ] {
        let mut bundle = if name == "pre-false" {
            false_pre_bundle()
        } else {
            Bundle::new(path)
        };
        bundle.add_all(Run::Sat);
        bundle.finish();
        let readback = bundle.verify().unwrap();
        assert_eq!(
            readback.document_digest,
            content_id(DOCUMENT, &encode(&bundle.document))
        );
        // Rewrap the very same Evidence with the separately selected new batch.
        // Neither the old fixture nor its fixed fingerprints are rewritten.
        let mut new_batch = copied(&bundle.batch);
        *field_mut(&mut new_batch, "version") = value_string("0.2");
        *field_mut(&mut new_batch, "contract") = value_string(&raw_digest(STRUCTURED_CONTRACT));
        let new_batch = encode(&new_batch);
        let exchange_pins = json::parse(include_bytes!(
            "../../../../../../docs/evidence/evidence-v0.2-machine-contract/independent-check-v0.2/packet-fingerprints.json"
        ), json_limits()).unwrap();
        assert_eq!(
            raw_digest(&new_batch),
            string(get(get(&exchange_pins, name), "batch_raw"), "batch pin").unwrap()
        );
        let new_readback = readback_v02_with_backend_v02(
            &encode(&bundle.document),
            |pin| bundle.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            BackendReviewContext {
                batch: &new_batch,
                expected_batch_digest: &raw_digest(&new_batch),
                consumer_policy: ProofPolicy::AttestationAllowed,
                allowed_trust_categories: ALLOWED,
                solver_limits: solver_limits(),
                replay_limits: replay_limits(),
            },
        )
        .unwrap();
        assert_eq!(readback.artifact_digest, new_readback.artifact_digest);
        assert_eq!(readback.document_digest, new_readback.document_digest);
        assert_eq!(
            readback.backend.as_ref().unwrap().remaining_trust,
            new_readback.backend.as_ref().unwrap().remaining_trust
        );
        let blobs = Value::Object(
            bundle
                .blobs
                .iter()
                .map(|(pin, raw)| {
                    let hex: String = raw.iter().map(|byte| format!("{byte:02x}")).collect();
                    (pin.clone(), value_string(&hex), 0)
                })
                .collect(),
        );
        let packet = value_object([
            ("name", value_string(name)),
            ("document", copied(&bundle.document)),
            ("batch", copied(&bundle.batch)),
            ("blobs", blobs),
        ]);
        let mut child = Command::new("python3")
            .args(["-I", "-B"])
            .arg(
                root()
                    .join("docs/evidence/evidence-v0.2-machine-contract/check_backend_readback.py"),
            )
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
            "{name}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        eprint!("{}", String::from_utf8_lossy(&output.stdout));
    }
}
