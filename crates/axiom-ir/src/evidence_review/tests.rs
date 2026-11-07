use std::{path::Path, process::Command};

use super::*;

fn limits() -> ReviewLimits {
    let json = JsonLimits {
        max_input_bytes: 1_000_000,
        max_values: 1_000_000,
        max_nesting: 128,
    };
    ReviewLimits {
        evidence_json: json,
        max_artifact_bytes: 1_000_000,
        max_total_artifact_bytes: 2_000_000,
        max_executions: 32,
        p2: ObligationLimits {
            ir_json: json,
            max_obligations: 1000,
            max_definition_bytes: 1_000_000,
            max_path_bytes: 1_000_000,
            max_output_bytes: 1_000_000,
        },
        derivation: OriginLimits {
            ir_json: json,
            max_steps: 1_000_000,
            max_premise_edges: 1_000_000,
            max_descriptors: 1_000_000,
            max_path_bytes: 1_000_000,
            max_output_bytes: 1_000_000,
        },
    }
}

fn member_mut<'a>(value: &'a mut Value, key: &str) -> &'a mut Value {
    let Value::Object(object) = value else {
        panic!("expected object");
    };
    decode::member_mut(object, key)
}

fn array_mut(value: &mut Value) -> &mut Vec<Value> {
    let Value::Array(array) = value else {
        panic!("expected array");
    };
    array
}

#[test]
fn contract_vectors_round_trip_with_exact_identity_and_reject_partial_documents() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let output = Command::new("python3")
        .args([
            "-I",
            "-B",
            "docs/evidence/evidence-v0.2-machine-contract/check_vectors.py",
            "--rust-vectors",
        ])
        .current_dir(root)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let packets = json::parse(
        &output.stdout,
        JsonLimits {
            max_input_bytes: 2_000_000,
            ..limits().evidence_json
        },
    )
    .unwrap();
    let packets = decode::array(&packets, "/vectors").unwrap();
    assert_eq!(packets.len(), 11);
    for packet in packets {
        let packet = shape(
            packet,
            "/vector",
            &[
                "artifact_digest",
                "blobs",
                "complete",
                "document",
                "document_digest",
                "name",
            ],
        )
        .unwrap();
        let name = text(packet, "name").unwrap();
        let Value::Object(blobs) = member(packet, "blobs") else {
            panic!("{name}: blobs");
        };
        let blobs: BTreeMap<_, _> = blobs
            .iter()
            .map(|(pin, raw, _)| {
                let hex = string(raw, "/blob").unwrap();
                let raw: Vec<_> = (0..hex.len())
                    .step_by(2)
                    .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                    .collect();
                (pin.as_str(), raw)
            })
            .collect();
        let raw = text(packet, "document").unwrap().as_bytes();
        let resolve = |pin: &str| blobs.get(pin).map(Vec::as_slice);
        let found = readback_v02(raw, resolve, limits());
        if !matches!(member(packet, "complete"), Value::Bool(true)) {
            assert!(
                matches!(
                    found,
                    Err(ReviewError::Invalid {
                        at: "obligations",
                        reason: "incomplete or extra"
                    })
                ),
                "{name}: {found:?}"
            );
            if name == "s3-sensitive-control" {
                check_sensitive_control(raw, resolve);
            }
            continue;
        }
        let found = found.unwrap_or_else(|err| panic!("{name}: {err}"));
        assert_eq!(
            found.artifact_digest,
            text(packet, "artifact_digest").unwrap(),
            "{name}"
        );
        assert_eq!(
            found.document_digest,
            text(packet, "document_digest").unwrap(),
            "{name}"
        );

        let mut noncanonical = raw.to_vec();
        noncanonical.push(b'\n');
        assert!(matches!(
            readback_v02(&noncanonical, resolve, limits()),
            Err(ReviewError::NonCanonical("evidence"))
        ));
        let mut doc = strict(raw, limits().evidence_json, "test").unwrap();
        *member_mut(&mut doc, "evidence_version") = value_string("0.1");
        assert!(matches!(
            readback_v02(&encode(&doc), resolve, limits()),
            Err(ReviewError::Version)
        ));

        let mut doc = strict(raw, limits().evidence_json, "test").unwrap();
        *member_mut(member_mut(&mut doc, "conclusion"), "refs") =
            Value::Array(vec![value_string("unbound")]);
        assert!(matches!(
            readback_v02(&encode(&doc), resolve, limits()),
            Err(ReviewError::Invalid {
                at: "conclusion",
                ..
            })
        ));

        if name == "s1-rejected" {
            check_rejection_mutations(raw, &blobs);
        }
        if name == "input-only-checked" {
            check_legal_mutations(raw, resolve);
        }
    }
}

fn check_sensitive_control<'a>(raw: &[u8], mut resolve: impl FnMut(&str) -> Option<&'a [u8]>) {
    let limits = limits();
    let doc = strict(raw, limits.evidence_json, "test").unwrap();
    let Value::Object(root) = &doc else {
        panic!("expected evidence object");
    };
    let artifacts =
        Artifacts::read(items(root, "artifacts").unwrap(), &mut resolve, limits).unwrap();
    let subject = Subject::read(member(root, "subject"), &artifacts, limits.p2).unwrap();
    let tools = read_tools(
        items(root, "tools").unwrap(),
        text(root, "producer").unwrap(),
        &artifacts,
    )
    .unwrap();
    let executions = read_executions(
        items(root, "executions").unwrap(),
        &tools,
        &artifacts,
        limits,
    )
    .unwrap();
    assert_eq!(executions.len(), 1);
    let run = executions.values().next().unwrap();
    assert!(matches!(
        support::rebuild(run, "field-origin", &subject, &artifacts, limits),
        Err(ReviewError::Invalid {
            at: "origin",
            reason: "public value and control"
        })
    ));
}

fn check_rejection_mutations(raw: &[u8], blobs: &BTreeMap<&str, Vec<u8>>) {
    let mut doc = strict(raw, limits().evidence_json, "test").unwrap();
    let pin = string(
        named(named(&doc, "subject").unwrap(), "artifact").unwrap(),
        "/subject",
    )
    .unwrap()
    .to_owned();
    let missing = |id: &str| {
        if id == pin {
            None
        } else {
            blobs.get(id).map(Vec::as_slice)
        }
    };
    let wrong = |id: &str| {
        if id == pin {
            Some(b"wrong".as_slice())
        } else {
            blobs.get(id).map(Vec::as_slice)
        }
    };
    assert!(
        matches!(readback_v02(raw, missing, limits()), Err(ReviewError::MissingArtifact(id)) if id == pin)
    );
    assert!(
        matches!(readback_v02(raw, wrong, limits()), Err(ReviewError::ArtifactIdentity(id)) if id == pin)
    );
    let result = member_mut(
        &mut array_mut(member_mut(&mut doc, "obligations"))[0],
        "result",
    );
    let witness = member_mut(result, "counterexample");
    let trace = array_mut(member_mut(witness, "trace"));
    *member_mut(&mut trace[0], "offset") = value_string("0");
    let resolve = |id: &str| blobs.get(id).map(Vec::as_slice);
    assert!(matches!(
        readback_v02(&encode(&doc), resolve, limits()),
        Err(ReviewError::Invalid {
            at: "result",
            reason: "structure witness"
        })
    ));

    let mut doc = strict(raw, limits().evidence_json, "test").unwrap();
    let tool = &mut array_mut(member_mut(&mut doc, "tools"))[0];
    let definition = member_mut(tool, "definition");
    *member_mut(definition, "roles") = Value::Array(vec![
        value_string("evidence-producer"),
        value_string("fixture-checker"),
    ]);
    let pin = content_id(TOOL, &encode(definition));
    *member_mut(tool, "id") = value_string(&pin);
    *member_mut(&mut doc, "producer") = value_string(&pin);
    let execution = &mut array_mut(member_mut(&mut doc, "executions"))[0];
    let definition = member_mut(execution, "definition");
    *member_mut(definition, "tool") = value_string(&pin);
    let pin = content_id(EXECUTION, &encode(definition));
    *member_mut(execution, "id") = value_string(&pin);
    let result = member_mut(
        &mut array_mut(member_mut(&mut doc, "obligations"))[0],
        "result",
    );
    *member_mut(result, "execution") = value_string(&pin);
    assert!(matches!(
        readback_v02(&encode(&doc), resolve, limits()),
        Err(ReviewError::Invalid {
            at: "execution",
            reason: "tool role"
        })
    ));
}

fn check_legal_mutations<'a>(raw: &[u8], resolve: impl Fn(&str) -> Option<&'a [u8]> + Copy) {
    let mut doc = strict(raw, limits().evidence_json, "test").unwrap();
    array_mut(member_mut(&mut doc, "obligations")).pop();
    assert!(matches!(
        readback_v02(&encode(&doc), resolve, limits()),
        Err(ReviewError::Invalid {
            at: "obligations",
            reason: "incomplete or extra"
        })
    ));

    let mut doc = strict(raw, limits().evidence_json, "test").unwrap();
    let obligations = array_mut(member_mut(&mut doc, "obligations"));
    let origins: Vec<_> = obligations
        .iter()
        .filter(|row| {
            string(
                named(named(row, "definition").unwrap(), "kind").unwrap(),
                "/kind",
            )
            .unwrap()
                == "field-origin"
        })
        .map(|row| string(named(row, "id").unwrap(), "/id").unwrap().to_owned())
        .collect();
    let mut wrong_output = None;
    let mut replace = None;
    for execution in array_mut(member_mut(&mut doc, "executions")).iter_mut() {
        let definition = member_mut(execution, "definition");
        let target = string(named(definition, "obligation").unwrap(), "/target").unwrap();
        if target == origins[0] {
            wrong_output = Some(
                strict(
                    &encode(member_mut(definition, "outputs")),
                    limits().evidence_json,
                    "test",
                )
                .unwrap(),
            );
        } else if target == origins[1] {
            replace = Some(execution);
        }
    }
    let execution = replace.unwrap();
    let definition = member_mut(execution, "definition");
    *member_mut(definition, "outputs") = wrong_output.unwrap();
    let pin = content_id(EXECUTION, &encode(definition));
    *member_mut(execution, "id") = value_string(&pin);
    array_mut(member_mut(&mut doc, "executions")).sort_unstable_by(|a, b| {
        let a = string(named(a, "id").unwrap(), "/id").unwrap();
        let b = string(named(b, "id").unwrap(), "/id").unwrap();
        a.cmp(b)
    });
    let row = array_mut(member_mut(&mut doc, "obligations"))
        .iter_mut()
        .find(|row| string(named(row, "id").unwrap(), "/id").unwrap() == origins[1])
        .unwrap();
    *member_mut(
        member_mut(member_mut(row, "result"), "support"),
        "execution",
    ) = value_string(&pin);
    assert!(matches!(
        readback_v02(&encode(&doc), resolve, limits()),
        Err(ReviewError::Origin(_))
    ));
}
