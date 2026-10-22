use super::*;
use crate::{
    declarations,
    document::{check_canonical_document, normalize_document},
    json::Value,
    obligations::{ObligationLimits, ObligationProfile, generate_obligations},
};
use std::path::PathBuf;

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn json_limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16_000_000,
        max_values: 2_000_000,
        max_nesting: 128,
    }
}
fn limits() -> OriginLimits {
    OriginLimits {
        ir_json: json_limits(),
        max_steps: 200_000,
        max_descriptors: 2_000_000,
        max_premise_edges: 500_000,
        max_path_bytes: 16_000_000,
        max_output_bytes: 32_000_000,
    }
}
fn identity() -> GeneratorIdentity {
    GeneratorIdentity::new(&format!("sha256:{}", "a".repeat(64))).unwrap()
}
fn load(path: &str) -> CanonicalDocument {
    check_canonical_document(&std::fs::read(root().join(path)).unwrap(), json_limits()).unwrap()
}
fn set(document: &CanonicalDocument) -> ObligationSet {
    generate_obligations(
        document,
        ObligationProfile::VerificationV0_2,
        ObligationLimits {
            ir_json: json_limits(),
            max_obligations: 100_000,
            max_definition_bytes: 16_000_000,
            max_path_bytes: 8_000_000,
            max_output_bytes: 24_000_000,
        },
    )
    .unwrap()
}
#[test]
fn independent_records_match_all_targets() {
    let directory = std::env::temp_dir().join(format!("radishaxiom-p3f-{}", std::process::id()));
    std::fs::create_dir(&directory).unwrap();
    let mut total = 0;
    for line in include_str!("../../../../contracts/core-field-origin-v0.1/cases.tsv").lines() {
        let c: Vec<_> = line.split('\t').collect();
        let document = load(c[1]);
        assert_eq!(raw_digest(document.canonical_bytes()), c[2]);
        let obligations = set(&document);
        let record = derive_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            &document,
            &obligations,
            c[3],
            &identity(),
            limits(),
        )
        .unwrap();
        let expected = std::fs::read(root().join(c[4])).unwrap();
        if record.canonical_bytes() != expected {
            std::fs::write(directory.join("actual.json"), record.canonical_bytes()).unwrap();
            std::fs::write(directory.join("expected.json"), expected).unwrap();
            panic!("{} differs; {}", c[0], directory.display());
        }
        assert_eq!(record.artifact_digest(), c[5]);
        let u = record.usage();
        assert_eq!(
            [
                u.steps,
                u.premise_edges,
                u.descriptors,
                u.path_bytes,
                u.output_bytes
            ],
            c[6..11]
                .iter()
                .map(|v| v.parse().unwrap())
                .collect::<Vec<usize>>()
                .as_slice(),
            "{}",
            c[0]
        );
        assert_eq!(
            check_field_origin(
                OriginProfile::CoreFieldOriginV0_1,
                record.canonical_bytes(),
                &document,
                &obligations,
                c[3],
                &identity(),
                limits()
            )
            .unwrap(),
            record
        );
        std::fs::write(
            directory.join(format!("{}.jcs", c[0])),
            record.canonical_bytes(),
        )
        .unwrap();
        total += 1;
    }
    assert_eq!(total, 758);
    let result = std::process::Command::new("python3")
        .arg(root().join("scripts/check-p3-origin-derivations.py"))
        .arg(&directory)
        .output()
        .unwrap();
    print!("{}", String::from_utf8_lossy(&result.stdout));
    assert!(
        result.status.success(),
        "{}; retained {}",
        String::from_utf8_lossy(&result.stderr),
        directory.display()
    );
    let mut mutations = 0;
    for line in std::fs::read_to_string(directory.join("mutations.tsv"))
        .unwrap()
        .lines()
    {
        let c: Vec<_> = line.split('\t').collect();
        let doc = load(c[0]);
        let obligations = set(&doc);
        let data = std::fs::read(directory.join(c[2])).unwrap();
        assert!(
            matches!(
                check_field_origin(
                    OriginProfile::CoreFieldOriginV0_1,
                    &data,
                    &doc,
                    &obligations,
                    c[1],
                    &identity(),
                    limits()
                ),
                Err(OriginError::NonCanonical { .. })
            ),
            "{}",
            c[2]
        );
        mutations += 1;
    }
    assert_eq!(mutations, 43);
    std::fs::remove_dir_all(directory).unwrap();
}

fn target(obligations: &ObligationSet) -> &str {
    obligations
        .obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::FieldOrigin)
        .unwrap()
        .id()
}
fn baseline() -> CanonicalDocument {
    load("contracts/core-field-origin-v0.1/inputs/constant-after-gap.jcs")
}
fn derive(document: &CanonicalDocument, obligations: &ObligationSet) -> OriginDerivation {
    derive_field_origin(
        OriginProfile::CoreFieldOriginV0_1,
        document,
        obligations,
        target(obligations),
        &identity(),
        limits(),
    )
    .unwrap()
}
#[test]
fn identities_profile_isolation_and_original_order_are_explicit() {
    let document = baseline();
    let obligations = set(&document);
    let record = derive(&document, &obligations);
    let other = load("contracts/map-filter-query-v0.1/inputs/filter-capacity.jcs");
    assert!(matches!(
        derive_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            &other,
            &obligations,
            target(&obligations),
            &identity(),
            limits()
        ),
        Err(OriginError::BindingMismatch)
    ));
    assert!(matches!(
        derive_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            &document,
            &obligations,
            "missing",
            &identity(),
            limits()
        ),
        Err(OriginError::UnknownObligation(_))
    ));
    for item in obligations
        .obligations()
        .iter()
        .filter(|o| o.kind() != ObligationKind::FieldOrigin)
    {
        assert!(
            matches!(derive_field_origin(OriginProfile::CoreFieldOriginV0_1, &document, &obligations, item.id(), &identity(), limits()), Err(OriginError::UnsupportedKind(kind)) if kind == item.kind())
        );
    }
    assert!(matches!(
        crate::effects::derive_empty_effects(
            crate::effects::EffectProfile::CoreV0_1,
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            crate::effects::EffectLimits {
                ir_json: json_limits(),
                max_steps: 0,
                max_premise_edges: 0,
                max_path_bytes: 0,
                max_output_bytes: 0
            }
        ),
        Err(crate::effects::EffectError::UnsupportedKind(
            ObligationKind::FieldOrigin
        ))
    ));
    let changed = GeneratorIdentity::new(&format!("sha256:{}", "b".repeat(64))).unwrap();
    assert!(matches!(
        check_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            record.canonical_bytes(),
            &document,
            &obligations,
            target(&obligations),
            &changed,
            limits()
        ),
        Err(OriginError::NonCanonical { .. })
    ));
    let mut value = json::parse(document.canonical_bytes(), json_limits()).unwrap();
    let Value::Object(root) = &mut value else {
        unreachable!()
    };
    for key in [
        "nodes",
        "contracts",
        "outputs",
        "record_types",
        "table_types",
    ] {
        let Value::Array(entries) = declarations::member_mut(root, key) else {
            unreachable!()
        };
        entries.reverse();
    }
    let mut bytes = vec![];
    json::encode(&value, &mut bytes);
    let reordered = normalize_document(&bytes, json_limits()).unwrap();
    assert_eq!(derive(&reordered, &obligations), record);
    let mut bytes = record.canonical_bytes().to_vec();
    bytes.push(b'\n');
    assert!(matches!(
        check_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            &bytes,
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            limits()
        ),
        Err(OriginError::NonCanonical { .. })
    ));
    let old = load("crates/axiom-ir/tests/fixtures/document-identities/contract.jcs");
    assert!(matches!(
        derive_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            &old,
            &obligations,
            target(&obligations),
            &identity(),
            limits()
        ),
        Err(OriginError::UnsupportedIrVersion(IrVersion::V0_1))
    ));
    for profile in [
        crate::query::QueryProfile::MapFilterV0_1,
        crate::query::QueryProfile::MapFilterV0_2,
        crate::query::QueryProfile::MapFilterV0_3,
        crate::query::QueryProfile::MapFilterV0_4,
    ] {
        let q = crate::query::QueryLimits {
            ir_json: json_limits(),
            max_input_slots: 0,
            max_value_cells: 0,
            max_expression_instances: 0,
            max_slot_comparisons: 0,
            max_smt_nodes: 0,
            max_output_bytes: 0,
        };
        assert!(matches!(
            crate::query::encode_query(
                profile,
                &document,
                &obligations,
                target(&obligations),
                &identity(),
                q
            ),
            Err(crate::query::QueryError::UnsupportedKind(
                ObligationKind::FieldOrigin
            ))
        ));
    }
}

#[test]
fn all_budgets_charge_before_work_and_reject_exact_minus_one_and_overflow() {
    let document = baseline();
    let obligations = set(&document);
    let record = derive(&document, &obligations);
    let u = record.usage();
    let exact = OriginLimits {
        ir_json: json_limits(),
        max_steps: u.steps,
        max_premise_edges: u.premise_edges,
        max_descriptors: u.descriptors,
        max_path_bytes: u.path_bytes,
        max_output_bytes: u.output_bytes,
    };
    let run = |l| {
        derive_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            l,
        )
    };
    assert_eq!(run(exact).unwrap(), record);
    for resource in [
        OriginResource::Steps,
        OriginResource::PremiseEdges,
        OriginResource::Descriptors,
        OriginResource::PathBytes,
        OriginResource::OutputBytes,
    ] {
        for zero in [false, true] {
            let mut small = exact;
            let limit = match resource {
                OriginResource::Steps => &mut small.max_steps,
                OriginResource::PremiseEdges => &mut small.max_premise_edges,
                OriginResource::Descriptors => &mut small.max_descriptors,
                OriginResource::PathBytes => &mut small.max_path_bytes,
                OriginResource::OutputBytes => &mut small.max_output_bytes,
            };
            *limit = if zero { 0 } else { *limit - 1 };
            assert_eq!(
                run(small).unwrap_err(),
                OriginError::ResourceLimit { resource }
            );
        }
        let mut budget = Budget {
            limits: exact,
            usage: OriginUsage::default(),
        };
        assert_eq!(
            budget.charge(resource, None),
            Err(OriginError::ResourceLimit { resource })
        );
        let used = match resource {
            OriginResource::Steps => &mut budget.usage.steps,
            OriginResource::PremiseEdges => &mut budget.usage.premise_edges,
            OriginResource::Descriptors => &mut budget.usage.descriptors,
            OriginResource::PathBytes => &mut budget.usage.path_bytes,
            OriginResource::OutputBytes => &mut budget.usage.output_bytes,
        };
        *used = usize::MAX;
        assert_eq!(
            budget.charge(resource, Some(1)),
            Err(OriginError::ResourceLimit { resource })
        );
    }
    let mut small = exact;
    small.max_output_bytes -= 1;
    assert_eq!(
        check_field_origin(
            OriginProfile::CoreFieldOriginV0_1,
            record.canonical_bytes(),
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            small
        )
        .unwrap_err(),
        OriginError::ResourceLimit {
            resource: OriginResource::OutputBytes
        }
    );
    for mode in 0..3 {
        let mut small = exact;
        match mode {
            0 => small.ir_json.max_input_bytes = 0,
            1 => small.ir_json.max_values = 0,
            _ => small.ir_json.max_nesting = 0,
        };
        assert!(matches!(run(small), Err(OriginError::Json(_))));
    }
}

#[test]
fn every_node_label_preserves_p1_analysis_without_consuming_its_results() {
    use build::{array, get, text};
    use std::collections::BTreeSet;
    let mut seen = BTreeSet::new();
    for line in include_str!("../../../../contracts/core-field-origin-v0.1/cases.tsv").lines() {
        let c: Vec<_> = line.split('\t').collect();
        if !seen.insert(c[1]) {
            continue;
        }
        let doc = load(c[1]);
        let obligations = set(&doc);
        let root = json::parse(doc.canonical_bytes(), json_limits()).unwrap();
        let definition = json::parse(
            obligations
                .obligations()
                .iter()
                .find(|o| o.id() == c[3])
                .unwrap()
                .canonical_definition(),
            json_limits(),
        )
        .unwrap();
        let mut builder = build::Builder::new(limits());
        builder.document(&root, &doc, &definition).unwrap();
        let graph = doc.components().analysis().graph();
        for step in &builder.steps {
            if step.anchor.kind != "node" {
                continue;
            }
            let index = graph
                .nodes()
                .iter()
                .position(|n| n.supplied_id() == step.anchor.id)
                .unwrap();
            let flow = &graph.node_flows()[index];
            if matches!(
                step.rule.as_str(),
                "input.field" | "filter.field" | "field.assign"
            ) {
                assert_eq!(
                    step.labels.propagated,
                    flow.field_labels()[step.item],
                    "{} {} {}",
                    c[0],
                    step.rule,
                    step.item
                );
                assert_eq!(
                    step.gap,
                    flow.label_gaps().iter().any(|gap| gap.name == step.item),
                    "{} {}",
                    c[0],
                    step.item
                );
            }
            if step.rule.ends_with(".control") {
                assert_eq!(
                    step.labels.propagated,
                    flow.row_control(),
                    "{} {}",
                    c[0],
                    step.rule
                );
            }
        }
        // Frozen P2 field-origin position inventory remains the exact named output / top field set.
        let count: usize = array(get(&root, "outputs"))
            .iter()
            .map(|o| {
                let n = graph
                    .nodes()
                    .iter()
                    .position(|n| n.supplied_id() == text(o, "node"))
                    .unwrap();
                graph.node_flows()[n].field_labels().len()
            })
            .sum();
        assert_eq!(
            obligations
                .obligations()
                .iter()
                .filter(|o| o.kind() == ObligationKind::FieldOrigin)
                .count(),
            count
        );
    }
    assert_eq!(seen.len(), 130);
}

#[test]
fn deep_shared_types_graphs_and_huge_capacity_do_not_expand_paths_or_worlds() {
    let document = load("contracts/map-filter-query-v0.1/resource-inputs/deep-type-and-graph.jcs");
    let obligations = set(&document);
    let record = derive(&document, &obligations);
    println!("P3-F deep shared graph usage: {:?}", record.usage());
    assert!(record.usage().steps < 100_000);
    assert!(record.usage().premise_edges < record.usage().steps * 8);
    let parsed = json::parse(
        record.canonical_bytes(),
        JsonLimits {
            max_input_bytes: 32_000_000,
            max_values: 4_000_000,
            max_nesting: 128,
        },
    )
    .unwrap();
    let steps = build::array(build::get(&parsed, "steps"));
    assert!(steps.len() <= record.usage().steps);
    for (i, step) in steps.iter().enumerate() {
        for edge in build::array(build::get(step, "premises")) {
            assert!(build::text(edge, "step").parse::<usize>().unwrap() < i);
        }
    }
    for path in [
        "contracts/core-field-origin-v0.1/inputs/huge-capacity.jcs",
        "contracts/map-filter-query-v0.1/resource-inputs/nested-expansion.jcs",
    ] {
        let document = load(path);
        let obligations = set(&document);
        assert!(derive(&document, &obligations).usage().steps < 1000);
    }
}

#[test]
fn local_closed_rules_refuse_hidden_or_out_of_scope_expressions() {
    let document = baseline();
    let obligations = set(&document);
    let definition = json::parse(
        obligations
            .obligations()
            .iter()
            .find(|o| o.id() == target(&obligations))
            .unwrap()
            .canonical_definition(),
        json_limits(),
    )
    .unwrap();
    for (json, reason) in [
        (
            r#"{"op":"external_call","capability":"network"}"#,
            "unsupported row expression",
        ),
        (
            r#"{"op":"literal_bool","value":true,"capability":"network"}"#,
            "non-closed origin construct",
        ),
        (r#"{"op":"bound","index":"0"}"#, "out of scope bound"),
    ] {
        let root = json::parse(document.canonical_bytes(), json_limits()).unwrap();
        let mut builder = build::Builder::new(limits());
        builder.document(&root, &document, &definition).unwrap();
        let expr = json::parse(json.as_bytes(), json_limits()).unwrap();
        let result = builder.expression(
            &expr,
            build::Anchor {
                kind: "node",
                id: document.document_id(),
            },
            &mut vec![],
            &mut vec![],
        );
        assert!(matches!(result,Err(OriginError::InvalidConstruct {reason:r,..}) if r==reason));
    }
}
